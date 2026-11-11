#pragma once
// ===========================================================================
// 파일 역할 : 관절 명령·관절 상태의 "고정 크기" 자료형.
//
// 왜 고정 크기인가
//   RT 스레드 안에서는 메모리 할당이 금지다. std::vector 처럼 크기가 변하는 것은 쓸 수 없다.
//   그래서 "최대 관절 수"를 컴파일 때 정해 두고(kMaxJoints), 실제 관절 수(dof)는
//   로봇 프로필에서 읽어 그 안에서만 쓴다. SO-101 은 6, ALLEX 는 수십 — 둘 다 64 안.
// ===========================================================================
#include <cstddef>
#include <cstdint>

namespace rt_core {

const std::uint32_t kMaxJoints = 64;

// 상위(ROS 2 콜백 스레드)에서 RT 스레드로 내려오는 "목표 위치" 명령
struct JointCommand {
  std::int64_t stamp_ns = 0;             // 명령을 받은 시각 (단조 시계)
  std::uint32_t dof = 0;                 // 유효한 관절 수
  double position[kMaxJoints] = {0.0};   // 목표 위치 (rad)
  std::uint32_t seq = 0;                 // 명령 번호 (ZeroMQ 패킷의 seq. ROS 2 쪽은 0) — 상태의 cmd_seq 로 돌아간다
};

// RT 스레드에서 상위(발행 스레드)로 올라가는 "한 주기의 상태"
struct JointStateSample {
  std::uint64_t iter = 0;                // 몇 번째 주기
  std::int64_t stamp_ns = 0;             // 상태를 읽은 시각 (단조 시계)
  std::int64_t wake_lat_ns = 0;          // 이번 주기 깨어남 지연 (RtLoop 이 잰 값)
  std::uint32_t dof = 0;
  bool watchdog_tripped = false;         // 명령 끊김으로 "멈춤" 상태인가
  std::uint8_t robot_state = 0;          // RobotState 값 (0 INIT, 1 READY, 2 RUNNING, 3 FAULT, 4 RECOVERING)
  double position[kMaxJoints] = {0.0};   // 실제 위치 (rad)
  double velocity[kMaxJoints] = {0.0};   // 실제 속도 (rad/s)
  double target[kMaxJoints] = {0.0};     // 이번 주기에 로봇에 실제로 보낸 목표 (제한 적용 후)
  std::uint32_t cmd_seq = 0;             // 이 주기까지 반영된 마지막 명령의 번호 (명령 → 반영 지연을 재는 데 쓴다)
};

// 명령 우편함 칸 수 (ROS 2 → RT). RT 는 매 주기 전부 비우고 "가장 최신 것"만 쓴다.
const std::size_t kCommandRingSize = 64;

// 상태 벨트 칸 수 (RT → 발행 스레드). 2048 샘플 = 1 kHz 에서 약 2초 분량.
const std::size_t kStateRingSize = 2048;

}  // namespace rt_core
