#include "rt_core/robot_state_machine.hpp"

namespace rt_core {

// ---------------------------------------------------------------------------
// 전이표. "이 상태에서 이 사건이 오면 저 상태로". 여기 없는 조합은 전부 불법.
// 읽는 법: 한 줄 = 한 화살표.
// ---------------------------------------------------------------------------
struct Transition {
  RobotState from;
  RobotEvent event;
  RobotState to;
};

static const Transition kTable[] = {
    {RobotState::INIT,       RobotEvent::INIT_DONE,     RobotState::READY},
    {RobotState::READY,      RobotEvent::COMMAND,       RobotState::RUNNING},
    {RobotState::READY,      RobotEvent::WATCHDOG_TRIP, RobotState::READY},      // 대기 중 명령 없음은 정상 (자기 자신으로)
    {RobotState::RUNNING,    RobotEvent::COMMAND,       RobotState::RUNNING},    // 계속 움직임
    {RobotState::RUNNING,    RobotEvent::WATCHDOG_TRIP, RobotState::FAULT},
    {RobotState::FAULT,      RobotEvent::WATCHDOG_TRIP, RobotState::FAULT},      // 계속 끊겨 있음
    {RobotState::FAULT,      RobotEvent::COMMAND,       RobotState::RECOVERING},
    {RobotState::RECOVERING, RobotEvent::COMMAND,       RobotState::RECOVERING}, // 복구 확인 중
    {RobotState::RECOVERING, RobotEvent::WATCHDOG_TRIP, RobotState::FAULT},      // 복구 중 또 끊기면 다시 FAULT
    {RobotState::RECOVERING, RobotEvent::RECOVERED,     RobotState::READY},
    {RobotState::INIT,       RobotEvent::STOP,          RobotState::INIT},
    {RobotState::READY,      RobotEvent::STOP,          RobotState::INIT},
    {RobotState::RUNNING,    RobotEvent::STOP,          RobotState::INIT},
    {RobotState::FAULT,      RobotEvent::STOP,          RobotState::INIT},
    {RobotState::RECOVERING, RobotEvent::STOP,          RobotState::INIT},
};
static const std::size_t kTableSize = sizeof(kTable) / sizeof(kTable[0]);

bool RobotStateMachine::handle(RobotEvent e) {
  for (std::size_t i = 0; i < kTableSize; ++i) {
    if (kTable[i].from == state_ && kTable[i].event == e) {
      if (kTable[i].to != state_) {
        transitions_ = transitions_ + 1;
      }
      state_ = kTable[i].to;
      return true;
    }
  }
  illegal_ = illegal_ + 1;  // 표에 없는 조합: 상태를 바꾸지 않는다
  return false;
}

const char* robot_state_name(RobotState s) {
  switch (s) {
    case RobotState::INIT: return "INIT";
    case RobotState::READY: return "READY";
    case RobotState::RUNNING: return "RUNNING";
    case RobotState::FAULT: return "FAULT";
    case RobotState::RECOVERING: return "RECOVERING";
  }
  return "?";
}

const char* robot_event_name(RobotEvent e) {
  switch (e) {
    case RobotEvent::INIT_DONE: return "INIT_DONE";
    case RobotEvent::COMMAND: return "COMMAND";
    case RobotEvent::WATCHDOG_TRIP: return "WATCHDOG_TRIP";
    case RobotEvent::RECOVERED: return "RECOVERED";
    case RobotEvent::STOP: return "STOP";
  }
  return "?";
}

}  // namespace rt_core
