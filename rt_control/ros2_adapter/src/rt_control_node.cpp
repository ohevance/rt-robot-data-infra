// ===========================================================================
// 파일 역할 : rt_core 를 감싸는 얇은 ROS 2 노드 (rt_control_node)
//
//   토픽
//     구독  joint_command  (sensor_msgs/JointState) : 목표 위치. position 배열 길이 = 관절 수
//     발행  joint_states   (sensor_msgs/JointState) : 실제 위치·속도, publish_hz (기본 100 Hz)
//     발행  rt_status      (std_msgs/String, JSON)  : 지연 통계(wake_us)·작업 시간(work_us)·드롭·워치독·상태 머신, 1 Hz
//
//   스레드 3개
//     ROS 2 실행기 스레드 : 콜백(on_command)과 타이머(publish_state, publish_status). 일반 우선순위
//     RT 스레드           : RtLoop + ControlStep, 1 kHz, SCHED_FIFO. 이 파일의 rt_thread_main()
//     (둘 사이 통로는 spsc_ring 두 개. 락 없음)
//
//   백엔드(로봇 쪽) 선택: 파라미터 backend = "sim_lag"(1차 지연 모델) | "mujoco"(물리 시뮬레이터, 빌드 옵션 필요)
//
// 읽는 순서 : 1) 생성자 (파라미터 → 백엔드·제어 단계 → 토픽·타이머 → RT 스레드 시작)
//            1-1) make_backend()  — backend 파라미터로 SimLag / MuJoCo 를 고른다
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
#include <cstdlib>
#include <fstream>
#include <functional>
#include <memory>
#include <stdexcept>
#include <string>
#include <thread>
#include <vector>

#include "rclcpp/rclcpp.hpp"
#include "rmw/rmw.h"  // rmw_get_implementation_identifier: 어떤 DDS 가 실제로 쓰였나
#include "rt_core/control_step.hpp"
#include "rt_core/robot_state_machine.hpp"
#include "rt_core/rt_clock.hpp"
#include "rt_core/rt_loop.hpp"
#include "rt_core/sim_lag_backend.hpp"
#ifdef RT_CORE_WITH_MUJOCO
#include "rt_core/mujoco_backend.hpp"  // -DRT_CORE_WITH_MUJOCO=ON 으로 빌드했을 때만
#endif
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
    sim_tau_s_ = declare_parameter<double>("sim_time_constant_s", 0.05);
    backend_name_ = declare_parameter<std::string>("backend", "sim_lag");
    mujoco_model_ = declare_parameter<std::string>("mujoco_model", "");
    mujoco_joints_ = declare_parameter<std::vector<std::string>>("mujoco_joints", std::vector<std::string>());

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

    // ---------- 2) 백엔드와 제어 단계 ----------
    backend_ = make_backend();
    if (backend_ == nullptr) {
      throw std::runtime_error("backend 를 만들 수 없음 (위 로그 참고)");
    }
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

    RCLCPP_INFO(get_logger(), "rt_control_node: backend=%s dof=%u loop=%d Hz prio=%d cpu=%d watchdog=%d ms publish=%d Hz",
                backend_name_.c_str(), dof_, loop_hz, prio, cpu, watchdog_ms, publish_hz_);
  }

  ~RtControlNode() override {
    stop_.store(true, std::memory_order_release);  // RT 루프는 다음 주기에 멈춘다
    if (rt_thread_.joinable()) {
      rt_thread_.join();
    }
  }

 private:
  // ---------- 1-1) 백엔드 고르기: 파라미터 backend 에 따라 ----------
  std::unique_ptr<rt_core::Backend> make_backend() {
    if (backend_name_ == "sim_lag") {
      return std::make_unique<rt_core::SimLagBackend>(sim_tau_s_);
    }
    if (backend_name_ == "mujoco") {
#ifdef RT_CORE_WITH_MUJOCO
      std::string path = resolve_model_path(mujoco_model_);
      if (path.empty()) {
        RCLCPP_FATAL(get_logger(), "mujoco_model 파일을 찾을 수 없음: '%s' (저장소 루트에서 실행하거나 RT_REPO_ROOT 설정)",
                     mujoco_model_.c_str());
        return nullptr;
      }
      std::unique_ptr<rt_core::MujocoBackend> mj = std::make_unique<rt_core::MujocoBackend>();
      mj->set_model(path);
      mj->set_joint_names(mujoco_joints_);  // 비어 있으면 모델 순서대로
      return mj;
#else
      RCLCPP_FATAL(get_logger(), "backend=mujoco 인데 MuJoCo 없이 빌드됨. colcon build --cmake-args -DRT_CORE_WITH_MUJOCO=ON");
      return nullptr;
#endif
    }
    RCLCPP_FATAL(get_logger(), "모르는 backend '%s' (sim_lag | mujoco)", backend_name_.c_str());
    return nullptr;
  }

  // 모델 경로: 그대로 있으면 그대로, 상대 경로가 안 보이면 $RT_REPO_ROOT 아래에서 찾는다. 없으면 빈 문자열
  static std::string resolve_model_path(const std::string& path) {
    if (path.empty()) {
      return "";
    }
    if (file_exists(path)) {
      return path;
    }
    const char* root = std::getenv("RT_REPO_ROOT");
    if (root != nullptr && path[0] != '/') {
      std::string candidate = std::string(root) + "/" + path;
      if (file_exists(candidate)) {
        return candidate;
      }
    }
    return "";
  }

  static bool file_exists(const std::string& path) {
    std::ifstream f(path);
    return f.good();
  }

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
    // 지난 1초 동안의 타이밍 샘플을 전부 꺼내 깨어남 지연과 작업 시간(제어 단계 + 백엔드)의 p50/p99/max 를 구한다
    std::vector<std::int64_t> wake_ns;
    std::vector<std::int64_t> work_ns;
    Sample t;
    while (g_timing_ring.pop(t)) {
      wake_ns.push_back(t.wake_lat_ns);
      work_ns.push_back(t.work_ns);
    }
    double p50 = 0.0, p99 = 0.0, mx = 0.0;
    double w50 = 0.0, w99 = 0.0, wmx = 0.0;
    if (!wake_ns.empty()) {
      std::sort(wake_ns.begin(), wake_ns.end());
      p50 = static_cast<double>(wake_ns[wake_ns.size() * 50 / 100]) / 1000.0;
      p99 = static_cast<double>(wake_ns[wake_ns.size() * 99 / 100]) / 1000.0;
      mx = static_cast<double>(wake_ns.back()) / 1000.0;
      std::sort(work_ns.begin(), work_ns.end());
      w50 = static_cast<double>(work_ns[work_ns.size() * 50 / 100]) / 1000.0;
      w99 = static_cast<double>(work_ns[work_ns.size() * 99 / 100]) / 1000.0;
      wmx = static_cast<double>(work_ns.back()) / 1000.0;
    }

    const rt_core::RtStatus& st = rt_loop_->status();  // RT 스레드가 시작할 때 한 번 써 두는 값 (이후 변하지 않음)
    const char* watchdog = "tripped";
    if (!counters_.watchdog_tripped.load()) {
      watchdog = "ok";
    }
    const char* state_name = rt_core::robot_state_name(static_cast<rt_core::RobotState>(counters_.robot_state.load()));

    char buf[1536];
    std::snprintf(buf, sizeof(buf),
                  "{\"iter\": %llu, \"loop_hz\": %lld, \"backend\": \"%s\", \"samples_1s\": %zu, "
                  "\"wake_us\": {\"p50\": %.1f, \"p99\": %.1f, \"max\": %.1f}, "
                  "\"work_us\": {\"p50\": %.1f, \"p99\": %.1f, \"max\": %.1f}, "
                  "\"timing_drops\": %llu, \"state_drops\": %llu, "
                  "\"commands_received\": %llu, \"commands_applied\": %llu, \"cmd_ring_full\": %llu, \"bad_commands\": %llu, "
                  "\"watchdog\": \"%s\", \"watchdog_trips\": %llu, \"step_limited\": %llu, "
                  "\"state\": \"%s\", \"state_transitions\": %llu, \"illegal_events\": %llu, "
                  "\"rt\": {\"sched_fifo\": %s, \"mlockall\": %s, \"kernel_realtime\": %s, \"kernel\": \"%s\"}, "
                  "\"rmw\": \"%s\"}",
                  static_cast<unsigned long long>(last_state_.iter),
                  static_cast<long long>(1000000000LL / rt_cfg_.period_ns), backend_name_.c_str(), wake_ns.size(), p50, p99, mx, w50, w99, wmx,
                  static_cast<unsigned long long>(timing_drops_.load()),
                  static_cast<unsigned long long>(counters_.state_drops.load()),
                  static_cast<unsigned long long>(commands_received_),
                  static_cast<unsigned long long>(counters_.commands_applied.load()),
                  static_cast<unsigned long long>(cmd_ring_full_), static_cast<unsigned long long>(bad_commands_),
                  watchdog, static_cast<unsigned long long>(counters_.watchdog_trips.load()),
                  static_cast<unsigned long long>(counters_.step_limited.load()),
                  state_name, static_cast<unsigned long long>(counters_.state_transitions.load()),
                  static_cast<unsigned long long>(counters_.illegal_events.load()),
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
  std::string backend_name_ = "sim_lag";
  double sim_tau_s_ = 0.05;
  std::string mujoco_model_;
  std::vector<std::string> mujoco_joints_;
  RtConfig rt_cfg_;
  ControlConfig ctl_cfg_;
  ControlCounters counters_;
  std::atomic<std::uint64_t> timing_drops_{0};
  std::atomic<bool> stop_{false};
  std::uint64_t commands_received_ = 0;  // ROS 2 실행기 스레드에서만 만진다
  std::uint64_t cmd_ring_full_ = 0;
  std::uint64_t bad_commands_ = 0;
  JointStateSample last_state_;

  std::unique_ptr<rt_core::Backend> backend_;   // SimLagBackend 또는 MujocoBackend
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
