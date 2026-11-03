#pragma once
// ===========================================================================
// 파일 역할 : 로봇 운용 상태 머신. "지금 로봇이 어떤 상태인가"와 "어떤 일이 생기면 어디로 가는가"를 표로 정한다.
//
//   INIT ──INIT_DONE──▶ READY ──COMMAND──▶ RUNNING ──WATCHDOG_TRIP──▶ FAULT
//                         ▲                   ▲                        │
//                         │                   │                    COMMAND (명령이 다시 옴)
//                         │                   │                        ▼
//                         └──RECOVERED────── RECOVERING ◀──────────────┘
//                                            (좋은 주기 N번 연속이면 RECOVERED)
//   어느 상태에서든 STOP ──▶ INIT
//
// 왜 표(table)로 만드나
//   if/else 가 흩어지면 "FAULT 에서 바로 RUNNING 으로 갈 수 있나?" 같은 질문에 코드를 다 읽어야 답한다.
//   전이표는 그 답이 한눈에 보이고, 표에 없는 전이는 전부 "불법"으로 막힌다(카운트).
//
// 규칙: RT 스레드에서 매 주기 불릴 수 있으므로 할당·락·파일이 없다. 전부 정수 비교다.
// ===========================================================================
#include <cstddef>
#include <cstdint>

namespace rt_core {

enum class RobotState : std::uint8_t {
  INIT = 0,        // 켜진 직후. 백엔드 준비 중
  READY = 1,       // 준비 끝. 명령을 기다림 (움직이지 않음)
  RUNNING = 2,     // 명령을 따라 움직이는 중
  FAULT = 3,       // 워치독 등으로 멈춤. 지금 자리를 유지
  RECOVERING = 4,  // 명령이 다시 와서 복구 확인 중 (좋은 주기 N번 연속이면 READY)
};

enum class RobotEvent : std::uint8_t {
  INIT_DONE = 0,      // 백엔드 준비 완료
  COMMAND = 1,        // 유효한 명령이 도착
  WATCHDOG_TRIP = 2,  // 명령 끊김 (watchdog_ms 초과)
  RECOVERED = 3,      // 복구 확인 완료 (좋은 주기 N번 연속)
  STOP = 4,           // 정지/재시작 요청
};

const char* robot_state_name(RobotState s);
const char* robot_event_name(RobotEvent e);

class RobotStateMachine {
 public:
  RobotStateMachine() {}

  // 사건을 넣는다. 표에 있는 전이면 상태를 바꾸고 true, 없으면 상태 그대로 두고 false (불법 전이 카운트 +1)
  bool handle(RobotEvent e);

  RobotState state() const { return state_; }
  std::uint64_t transitions() const { return transitions_; }
  std::uint64_t illegal_events() const { return illegal_; }

 private:
  RobotState state_ = RobotState::INIT;
  std::uint64_t transitions_ = 0;
  std::uint64_t illegal_ = 0;
};

}  // namespace rt_core
