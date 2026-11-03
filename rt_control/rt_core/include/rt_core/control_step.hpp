#pragma once
// ===========================================================================
// 파일 역할 : 제어 노드의 "한 주기에 할 일" (RtStep 구현). RT 스레드에서 1 kHz 로 불린다.
//
// 매 주기 순서 (step 함수):
//   1) 명령 우편함 비우기  — ROS 2 콜백 스레드가 넣어 둔 명령 중 "가장 최신 것"만 쓴다
//   2) 워치독             — 마지막 명령이 watchdog_ns 보다 오래됐으면 "멈춤": 목표 = 현재 위치
//   3) 변화량 제한        — 한 주기에 목표가 max_step_rad 보다 크게 뛰지 못하게 (급변 명령 차단)
//   4) 로봇에 쓰기 / 읽기 — Backend (오늘은 SimLag, 나중에 MuJoCo·실물)
//   5) 상태 벨트에 올리기 — 발행 스레드가 꺼내 ROS 2 토픽으로 내보낸다. 꽉 차면 버리고 센다.
//
// 스레드 사이 통로 (둘 다 spsc_ring, 락 없음)
//   ROS 2 콜백 스레드 ──JointCommand──▶ cmd_ring ──▶ [RT 스레드] ──JointStateSample──▶ state_ring ──▶ 발행 스레드
// ===========================================================================
#include <atomic>
#include <cstdint>

#include "rt_core/backend.hpp"
#include "rt_core/joint_types.hpp"
#include "rt_core/rt_step.hpp"
#include "rt_core/spsc_ring.hpp"

namespace rt_core {

struct ControlConfig {
  std::uint32_t dof = 0;                  // 관절 수 (로봇 프로필에서)
  std::int64_t period_ns = 1000000;       // 주기
  std::int64_t watchdog_ns = 50000000;    // 명령이 이 시간 동안 끊기면 멈춤 (50 ms)
  double max_step_rad = 0.05;             // 한 주기 최대 목표 변화량
};

// 상위 스레드가 읽어 가는 카운터. 전부 atomic 이라 락 없이 읽고 쓴다.
struct ControlCounters {
  std::atomic<std::uint64_t> commands_applied{0};  // RT 가 실제로 적용한 명령 수
  std::atomic<std::uint64_t> state_drops{0};       // 상태 벨트가 꽉 차서 버린 수
  std::atomic<std::uint64_t> watchdog_trips{0};    // 정상 → 멈춤 으로 넘어간 횟수
  std::atomic<std::uint64_t> step_limited{0};      // 변화량 제한이 실제로 걸린 횟수
  std::atomic<bool> watchdog_tripped{true};        // 지금 멈춤 상태인가 (시작 시 true: 명령 올 때까지 멈춤)
};

using CommandRing = SpscRing<JointCommand, kCommandRingSize>;
using StateRing = SpscRing<JointStateSample, kStateRingSize>;

class ControlStep : public RtStep {
 public:
  ControlStep(const ControlConfig& cfg, Backend& backend, CommandRing& cmd_ring, StateRing& state_ring,
              ControlCounters& counters);

  void step(std::uint64_t iter, std::int64_t wake_lat_ns) override;

 private:
  void take_latest_command(std::int64_t now_ns);  // 1)
  void check_watchdog(std::int64_t now_ns);       // 2)
  void limit_step();                              // 3)

  ControlConfig cfg_;
  Backend& backend_;
  CommandRing& cmd_ring_;
  StateRing& state_ring_;
  ControlCounters& counters_;

  std::int64_t last_cmd_ns_ = 0;                  // 마지막 명령을 받은 시각 (0 = 아직 없음)
  double desired_[kMaxJoints] = {0.0};            // 상위가 원하는 목표 (제한 전)
  double applied_[kMaxJoints] = {0.0};            // 실제로 로봇에 보낸 목표 (제한 후)
  double position_[kMaxJoints] = {0.0};           // 로봇에서 읽은 현재 위치
  double velocity_[kMaxJoints] = {0.0};
  bool tripped_ = true;
};

}  // namespace rt_core
