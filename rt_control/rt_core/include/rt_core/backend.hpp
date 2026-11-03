#pragma once
// ===========================================================================
// 파일 역할 : "로봇 쪽" 의 모양(인터페이스). 제어 단계(ControlStep)는 이것만 보고 일한다.
//
//   ControlStep ──write_command()──▶ Backend ──read_state()──▶ ControlStep
//
// 구현체를 바꾸면 로봇이 바뀐다. 코드의 다른 부분은 그대로다.
//   - SimLagBackend     : 1차 지연 모델 (오늘). 로봇 없이 노드 전체를 돌려보는 용도
//   - MujocoBackend     : MuJoCo 시뮬레이터 (D5~D6 예정)
//   - FeetechSerialBackend : SO-101 실물 서보 (2주 계획 밖)
//
// 규칙: 두 함수 모두 RT 스레드에서 매 주기 불린다 → 기다리는 일(락·파일·할당)을 하지 않는다.
// ===========================================================================
#include <cstdint>

#include "rt_core/joint_types.hpp"

namespace rt_core {

class Backend {
 public:
  virtual ~Backend() {}

  // 시작할 때 한 번. 관절 수와 주기를 알려준다. 여기서는 할당해도 된다 (RT 스레드 밖).
  virtual bool init(std::uint32_t dof, std::int64_t period_ns) = 0;

  // 이번 주기의 목표 위치를 로봇에 보낸다 (RT 스레드, 매 주기)
  virtual void write_command(const double* target_position, std::uint32_t dof) = 0;

  // 로봇의 현재 위치·속도를 읽는다 (RT 스레드, 매 주기)
  virtual void read_state(double* position, double* velocity, std::uint32_t dof) = 0;
};

}  // namespace rt_core
