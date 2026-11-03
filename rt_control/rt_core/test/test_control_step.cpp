// ===========================================================================
// 파일 역할 : ControlStep 단위 테스트 (ROS 2 없이, RtLoop 없이 step() 을 직접 부른다)
//
// 확인하는 것
//   1) 명령을 주면 위치가 목표를 향해 움직인다 (SimLag 백엔드)
//   2) 변화량 제한: 목표가 1.0 rad 로 뛰어도 첫 주기 적용 목표는 max_step_rad 이하
//   3) 워치독: 명령이 끊기면 멈춤 상태가 되고, 다시 오면 풀린다
//   4) 상태 벨트에 매 주기 샘플이 하나씩 올라온다
// ===========================================================================
#include <chrono>
#include <cmath>
#include <cstdio>
#include <thread>

#include "rt_core/control_step.hpp"
#include "rt_core/sim_lag_backend.hpp"

static int g_fail_count = 0;

static void check(bool condition, const char* message) {
  if (!condition) {
    std::fprintf(stderr, "FAIL: %s\n", message);
    g_fail_count = g_fail_count + 1;
  }
}

// 링은 크기가 커서 전역(정적)에 둔다
static rt_core::CommandRing g_cmd_ring;
static rt_core::StateRing g_state_ring;

static void send_command(std::uint32_t dof, double value) {
  rt_core::JointCommand cmd;
  cmd.dof = dof;
  for (std::uint32_t j = 0; j < dof; ++j) {
    cmd.position[j] = value;
  }
  g_cmd_ring.push(cmd);
}

// 벨트에서 마지막 샘플만 꺼낸다 (테스트 편의)
static rt_core::JointStateSample drain_last() {
  rt_core::JointStateSample s;
  rt_core::JointStateSample last;
  while (g_state_ring.pop(s)) {
    last = s;
  }
  return last;
}

int main() {
  rt_core::ControlConfig cfg;
  cfg.dof = 6;
  cfg.period_ns = 1000000;      // 1 ms
  cfg.watchdog_ns = 20000000;   // 20 ms (테스트가 빨리 끝나게 짧게)
  cfg.max_step_rad = 0.05;

  rt_core::SimLagBackend backend(0.05);
  check(backend.init(cfg.dof, cfg.period_ns), "backend init");

  rt_core::ControlCounters counters;
  rt_core::ControlStep ctl(cfg, backend, g_cmd_ring, g_state_ring, counters);

  // 3-앞) 명령이 아직 없으면 멈춤 상태로 시작한다
  ctl.step(0, 0);
  rt_core::JointStateSample s0 = drain_last();
  check(s0.watchdog_tripped == true, "no command yet -> tripped (hold)");

  // 1)+2) 목표 1.0 rad 로 명령 → 첫 주기 적용 목표는 0.05 이하, 위치는 0 보다 커진다
  send_command(cfg.dof, 1.0);
  ctl.step(1, 0);
  rt_core::JointStateSample s1 = drain_last();
  check(s1.watchdog_tripped == false, "command arrived -> not tripped");
  check(std::fabs(s1.target[0] - 0.05) < 1e-9, "first applied target is limited to max_step_rad");
  check(s1.position[0] > 0.0, "position starts moving toward target");
  check(counters.step_limited.load() >= 1, "step limit counter counted");

  // 계속 명령을 주면서 300 주기 → 적용 목표는 1.0 에 도달하고 위치는 그 근처까지 간다
  for (int i = 2; i < 302; ++i) {
    send_command(cfg.dof, 1.0);
    ctl.step(static_cast<std::uint64_t>(i), 0);
  }
  rt_core::JointStateSample s2 = drain_last();
  check(std::fabs(s2.target[0] - 1.0) < 1e-9, "applied target reaches 1.0 after enough cycles (20 x 0.05)");
  check(s2.position[0] > 0.9, "position approaches target (1st-order lag, 300 ms)");
  check(counters.commands_applied.load() == 301, "all commands applied");

  // 3) 명령을 끊고 30 ms 기다린 뒤 한 주기 → 멈춤 상태, trips 카운터 1
  std::this_thread::sleep_for(std::chrono::milliseconds(30));
  ctl.step(302, 0);
  rt_core::JointStateSample s3 = drain_last();
  check(s3.watchdog_tripped == true, "no command for 30 ms -> tripped");
  check(counters.watchdog_trips.load() == 1, "trip counted once");
  check(std::fabs(s3.target[0] - s3.position[0]) < 0.06, "tripped -> target moves to current position (hold)");

  // 명령이 다시 오면 풀린다
  send_command(cfg.dof, 0.5);
  ctl.step(303, 0);
  rt_core::JointStateSample s4 = drain_last();
  check(s4.watchdog_tripped == false, "command resumes -> untripped");

  // 4) 벨트 드롭은 없어야 한다 (매번 비웠으므로)
  check(counters.state_drops.load() == 0, "no state drops");

  if (g_fail_count == 0) {
    std::puts("OK: control_step");
    return 0;
  }
  std::printf("FAILED: %d checks\n", g_fail_count);
  return 1;
}
