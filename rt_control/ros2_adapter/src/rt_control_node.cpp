// ===========================================================================
// 파일 역할 : rt_core 를 감싸는 얇은 ROS 2 노드 (rt_control_node)
//
//   토픽
//     구독  joint_command  (sensor_msgs/JointState) : 목표 위치. position 배열 길이 = 관절 수
//     발행  joint_states   (sensor_msgs/JointState) : 실제 위치·속도, publish_hz (기본 100 Hz)
//     발행  rt_status      (std_msgs/String, JSON)  : 지연 통계·드롭·워치독, 1 Hz
//
//   스레드 3개
//     ROS 2 실행기 스레드 : 콜백(on_command)과 타이머(publish_state, publish_status). 일반 우선순위
//     RT 스레드           : RtLoop + ControlStep, 1 kHz, SCHED_FIFO. 이 파일의 rt_thread_main()
//     (둘 사이 통로는 spsc_ring 두 개. 락 없음)
//
// 읽는 순서 : 1) 생성자 (파라미터 → 백엔드·제어 단계 → 토픽·타이머 → RT 스레드 시작)
//            2) on_command()     — 명령을 우편함에 넣는다
//            3) rt_thread_main() — RT 스레드 본체 (3줄)
//            4) publish_state()  — 상태 벨트에서 최신 것을 꺼내 발행
//            5) publish_status() — 1초 동안의 지연 통계를 JSON 으로
//
// 이 파일에는 제어 논리가 없다. 제어는 rt_core/control_step.cpp 에 있다.
// ===========================================================================
#include <algorithm>
#include <atomic>
#include <chrono>
#include <cstdio>
#include <functional>
#include <memory>
#include <stdexcept>
#include <string>
#include <thread>
#include <vector>

#include "rclcpp/rclcpp.hpp"
#include "rmw/rmw.h"  // rmw_get_implementation_identifier: 어떤 DDS 가 실제로 쓰였나
#include "rt_core/control_step.hpp"
#include "rt_core/rt_clock.hpp"
#include "rt_core/rt_loop.hpp"
#include "rt_core/sim_lag_backend.hpp"
#include "sensor_msgs/msg/joint_state.hpp"
#include "std_msgs/msg/string.hpp"

using rt_core::ControlConfig;
using rt_core::ControlCounters;
using rt_core::ControlStep;
using rt_core::JointCommand;
using rt_core::JointStateSample;
using rt_core::RtConfig;
using rt_core::RtLoop;
using rt_core::Sample;

// 링 버퍼들은 크기가 커서(수 MB) 전역(정적)에 둔다
static rt_core::CommandRing g_cmd_ring;                           // ROS 2 콜백 → RT
static rt_core::StateRing g_state_ring;                           // RT → 발행 타이머
static rt_core::SpscRing<Sample, rt_core::kRingSize> g_timing_ring;  // RT 루프 타이밍 → 상태 타이머

class RtControlNode : public rclcpp::Node {
 public:
  RtControlNode() : rclcpp::Node("rt_control_node") {
    // ---------- 1) 파라미터 (로봇 프로필에서 변환한 config/*.params.yaml 로 들어온다) ----------
    joint_names_ = declare_parameter<std::vector<std::string>>("joint_names", std::vector<std::string>());
    int loop_hz = static_cast<int>(declare_parameter<int>("loop_hz", 1000));
    int prio = static_cast<int>(declare_parameter<int>("prio", 80));
    int cpu = static_cast<int>(declare_parameter<int>("cpu", -1));
    int watchdog_ms = static_cast<int>(declare_parameter<int>("watchdog_ms", 50));
    double max_step_rad = declare_parameter<double>("max_step_rad", 0.05);
    publish_hz_ = static_cast<int>(declare_parameter<int>("publish_hz", 100));
    double sim_tau_s = declare_parameter<double>("sim_time_constant_s", 0.05);

    if (joint_names_.empty() || joint_names_.size() > rt_core::kMaxJoints) {
      RCLCPP_FATAL(get_logger(), "joint_names 가 비었거나 %u 개를 넘습니다", rt_core::kMaxJoints);
      throw std::runtime_error("bad joint_names");
    }
    dof_ = static_cast<std::uint32_t>(joint_names_.size());

    rt_cfg_.period_ns = 1000000000LL / loop_hz;
    rt_cfg_.prio = prio;
    rt_cfg_.cpu = cpu;
    rt_cfg_.seconds = 0.0;  // 0 = stop 신호까지 계속

    ctl_cfg_.dof = dof_;
    ctl_cfg_.period_ns = rt_cfg_.period_ns;
    ctl_cfg_.watchdog_ns = static_cast<std::int64_t>(watchdog_ms) * 1000000LL;
    ctl_cfg_.max_step_rad = max_step_rad;

    // ---------- 2) 백엔드와 제어 단계 (오늘은 1차 지연 모델) ----------
    backend_ = std::make_unique<rt_core::SimLagBackend>(sim_tau_s);
    if (!backend_->init(dof_, rt_cfg_.period_ns)) {
      throw std::runtime_error("backend init failed");
    }
    control_ = std::make_unique<ControlStep>(ctl_cfg_, *backend_, g_cmd_ring, g_state_ring, counters_);

    // ---------- 3) 토픽 ----------
    state_pub_ = create_publisher<sensor_msgs::msg::JointState>("joint_states", 10);
    status_pub_ = create_publisher<std_msgs::msg::String>("rt_status", 10);
    cmd_sub_ = create_subscription<sensor_msgs::msg::JointState>(
        "joint_command", 10, std::bind(&RtControlNode::on_command, this, std::placeholders::_1));

    // ---------- 4) 타이머 ----------
    state_timer_ = create_wall_timer(std::chrono::microseconds(1000000 / publish_hz_),
                                     std::bind(&RtControlNode::publish_state, this));
    status_timer_ = create_wall_timer(std::chrono::seconds(1), std::bind(&RtControlNode::publish_status, this));

    // ---------- 5) RT 스레드 시작 ----------
    rt_loop_ = std::make_unique<RtLoop>(rt_cfg_);
    rt_thread_ = std::thread(&RtControlNode::rt_thread_main, this);

    RCLCPP_INFO(get_logger(), "rt_control_node: dof=%u loop=%d Hz prio=%d cpu=%d watchdog=%d ms publish=%d Hz",
                dof_, loop_hz, prio, cpu, watchdog_ms, publish_hz_);
  }

  ~RtControlNode() override {
    stop_.store(true, std::memory_order_release);  // RT 루프는 다음 주기에 멈춘다
    if (rt_thread_.joinable()) {
      rt_thread_.join();
    }
  }

 private:
  // ---------- 2) 명령 콜백: 검사 후 우편함에 넣는다 (RT 스레드와 락 없이 통신) ----------
  void on_command(const sensor_msgs::msg::JointState::SharedPtr msg) {
    if (msg->position.size() != dof_) {
      bad_commands_ = bad_commands_ + 1;
      if (bad_commands_ % 100 == 1) {
        RCLCPP_WARN(get_logger(), "joint_command position 길이 %zu != 관절 수 %u (무시)", msg->position.size(), dof_);
      }
      return;
    }
    JointCommand cmd;
    cmd.stamp_ns = rt_core::now_ns();
    cmd.dof = dof_;
    for (std::uint32_t j = 0; j < dof_; ++j) {
      cmd.position[j] = msg->position[j];
    }
    if (!g_cmd_ring.push(cmd)) {
      cmd_ring_full_ = cmd_ring_full_ + 1;  // RT 스레드가 비우지 못하고 있다는 뜻 (정상이면 0)
    }
    commands_received_ = commands_received_ + 1;
  }

  // ---------- 3) RT 스레드 본체 ----------
  void rt_thread_main() {
    rt_loop_->run(*control_, g_timing_ring, timing_drops_, &stop_);
  }

  // ---------- 4) 상태 발행: 벨트를 비우고 가장 최신 샘플만 보낸다 ----------
  void publish_state() {
    JointStateSample s;
    bool got_any = false;
    while (g_state_ring.pop(s)) {
      got_any = true;
      last_state_ = s;
    }
    if (!got_any) {
      return;  // RT 스레드가 아직 안 돌았거나 멈춘 상태
    }
    sensor_msgs::msg::JointState msg;
    msg.header.stamp = now();
    msg.name = joint_names_;
    msg.position.resize(dof_);
    msg.velocity.resize(dof_);
    for (std::uint32_t j = 0; j < dof_; ++j) {
      msg.position[j] = last_state_.position[j];
      msg.velocity[j] = last_state_.velocity[j];
    }
    state_pub_->publish(msg);
  }

  // ---------- 5) 1초 통계 JSON ----------
  void publish_status() {
    // 지난 1초 동안의 타이밍 샘플을 전부 꺼내 깨어남 지연의 p50/p99/max 를 구한다
    std::vector<std::int64_t> wake_ns;
    Sample t;
    while (g_timing_ring.pop(t)) {
      wake_ns.push_back(t.wake_lat_ns);
    }
    double p50 = 0.0, p99 = 0.0, mx = 0.0;
    if (!wake_ns.empty()) {
      std::sort(wake_ns.begin(), wake_ns.end());
      p50 = static_cast<double>(wake_ns[wake_ns.size() * 50 / 100]) / 1000.0;
      p99 = static_cast<double>(wake_ns[wake_ns.size() * 99 / 100]) / 1000.0;
      mx = static_cast<double>(wake_ns.back()) / 1000.0;
    }

    const rt_core::RtStatus& st = rt_loop_->status();  // RT 스레드가 시작할 때 한 번 써 두는 값 (이후 변하지 않음)
    const char* watchdog = "tripped";
    if (!counters_.watchdog_tripped.load()) {
      watchdog = "ok";
    }

    char buf[896];
    std::snprintf(buf, sizeof(buf),
                  "{\"iter\": %llu, \"loop_hz\": %lld, \"samples_1s\": %zu, "
                  "\"wake_us\": {\"p50\": %.1f, \"p99\": %.1f, \"max\": %.1f}, "
                  "\"timing_drops\": %llu, \"state_drops\": %llu, "
                  "\"commands_received\": %llu, \"commands_applied\": %llu, \"cmd_ring_full\": %llu, \"bad_commands\": %llu, "
                  "\"watchdog\": \"%s\", \"watchdog_trips\": %llu, \"step_limited\": %llu, "
                  "\"rt\": {\"sched_fifo\": %s, \"mlockall\": %s, \"kernel_realtime\": %s, \"kernel\": \"%s\"}, "
                  "\"rmw\": \"%s\"}",
                  static_cast<unsigned long long>(last_state_.iter),
                  static_cast<long long>(1000000000LL / rt_cfg_.period_ns), wake_ns.size(), p50, p99, mx,
                  static_cast<unsigned long long>(timing_drops_.load()),
                  static_cast<unsigned long long>(counters_.state_drops.load()),
                  static_cast<unsigned long long>(commands_received_),
                  static_cast<unsigned long long>(counters_.commands_applied.load()),
                  static_cast<unsigned long long>(cmd_ring_full_), static_cast<unsigned long long>(bad_commands_),
                  watchdog, static_cast<unsigned long long>(counters_.watchdog_trips.load()),
                  static_cast<unsigned long long>(counters_.step_limited.load()),
                  st.rt_sched_ok ? "true" : "false", st.mlock_ok ? "true" : "false",
                  st.kernel_realtime ? "true" : "false", st.kernel_release.c_str(),
                  rmw_get_implementation_identifier());

    std_msgs::msg::String msg;
    msg.data = buf;
    status_pub_->publish(msg);
  }

  // ---------- 멤버 ----------
  std::vector<std::string> joint_names_;
  std::uint32_t dof_ = 0;
  int publish_hz_ = 100;
  RtConfig rt_cfg_;
  ControlConfig ctl_cfg_;
  ControlCounters counters_;
  std::atomic<std::uint64_t> timing_drops_{0};
  std::atomic<bool> stop_{false};
  std::uint64_t commands_received_ = 0;  // ROS 2 실행기 스레드에서만 만진다
  std::uint64_t cmd_ring_full_ = 0;
  std::uint64_t bad_commands_ = 0;
  JointStateSample last_state_;

  std::unique_ptr<rt_core::SimLagBackend> backend_;
  std::unique_ptr<ControlStep> control_;
  std::unique_ptr<RtLoop> rt_loop_;
  std::thread rt_thread_;

  rclcpp::Publisher<sensor_msgs::msg::JointState>::SharedPtr state_pub_;
  rclcpp::Publisher<std_msgs::msg::String>::SharedPtr status_pub_;
  rclcpp::Subscription<sensor_msgs::msg::JointState>::SharedPtr cmd_sub_;
  rclcpp::TimerBase::SharedPtr state_timer_;
  rclcpp::TimerBase::SharedPtr status_timer_;
};

int main(int argc, char** argv) {
  rclcpp::init(argc, argv);
  {
    std::shared_ptr<RtControlNode> node = std::make_shared<RtControlNode>();
    rclcpp::spin(node);  // Ctrl+C 까지. 돌아오면 아래에서 node 가 소멸하며 RT 스레드를 멈춘다
  }
  rclcpp::shutdown();
  return 0;
}
