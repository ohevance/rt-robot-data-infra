// ===========================================================================
// 파일 역할 : 상태 머신 단위 테스트 — 전이표대로 가는가, 표에 없는 전이는 막히는가
// ===========================================================================
#include <cstdio>

#include "rt_core/robot_state_machine.hpp"

using rt_core::RobotEvent;
using rt_core::RobotState;
using rt_core::RobotStateMachine;

static int g_fail_count = 0;

static void check(bool condition, const char* message) {
  if (!condition) {
    std::fprintf(stderr, "FAIL: %s\n", message);
    g_fail_count = g_fail_count + 1;
  }
}

int main() {
  RobotStateMachine sm;
  check(sm.state() == RobotState::INIT, "시작은 INIT");

  // 정상 경로: INIT → READY → RUNNING → FAULT → RECOVERING → READY → RUNNING
  check(sm.handle(RobotEvent::INIT_DONE) && sm.state() == RobotState::READY, "INIT_DONE → READY");
  check(sm.handle(RobotEvent::WATCHDOG_TRIP) && sm.state() == RobotState::READY, "READY 에서 명령 없음은 정상 (READY 유지)");
  check(sm.handle(RobotEvent::COMMAND) && sm.state() == RobotState::RUNNING, "COMMAND → RUNNING");
  check(sm.handle(RobotEvent::COMMAND) && sm.state() == RobotState::RUNNING, "계속 COMMAND → RUNNING 유지");
  check(sm.handle(RobotEvent::WATCHDOG_TRIP) && sm.state() == RobotState::FAULT, "RUNNING 에서 끊김 → FAULT");
  check(sm.handle(RobotEvent::WATCHDOG_TRIP) && sm.state() == RobotState::FAULT, "계속 끊김 → FAULT 유지");
  check(sm.handle(RobotEvent::COMMAND) && sm.state() == RobotState::RECOVERING, "FAULT 에서 명령 재개 → RECOVERING");
  check(sm.handle(RobotEvent::WATCHDOG_TRIP) && sm.state() == RobotState::FAULT, "RECOVERING 중 또 끊김 → FAULT");
  check(sm.handle(RobotEvent::COMMAND) && sm.state() == RobotState::RECOVERING, "다시 명령 → RECOVERING");
  check(sm.handle(RobotEvent::RECOVERED) && sm.state() == RobotState::READY, "RECOVERED → READY");
  check(sm.handle(RobotEvent::COMMAND) && sm.state() == RobotState::RUNNING, "READY 에서 명령 → RUNNING");

  // 불법 전이: 표에 없는 조합은 상태를 바꾸지 않고 false
  std::uint64_t before = sm.illegal_events();
  check(!sm.handle(RobotEvent::INIT_DONE) && sm.state() == RobotState::RUNNING, "RUNNING 에서 INIT_DONE 은 불법 → 그대로");
  check(!sm.handle(RobotEvent::RECOVERED) && sm.state() == RobotState::RUNNING, "RUNNING 에서 RECOVERED 는 불법 → 그대로");
  check(sm.illegal_events() == before + 2, "불법 사건 2개가 세어진다");

  // FAULT 에서 바로 RUNNING 으로는 못 간다 (반드시 RECOVERING 을 거친다)
  sm.handle(RobotEvent::WATCHDOG_TRIP);
  check(sm.state() == RobotState::FAULT, "FAULT");
  sm.handle(RobotEvent::COMMAND);
  check(sm.state() == RobotState::RECOVERING, "FAULT → COMMAND 는 RUNNING 이 아니라 RECOVERING");

  // STOP 은 어디서든 INIT
  check(sm.handle(RobotEvent::STOP) && sm.state() == RobotState::INIT, "STOP → INIT");

  check(sm.transitions() >= 10, "전이 횟수가 세어진다");

  if (g_fail_count == 0) {
    std::puts("OK: state_machine");
    return 0;
  }
  std::printf("FAILED: %d checks\n", g_fail_count);
  return 1;
}
