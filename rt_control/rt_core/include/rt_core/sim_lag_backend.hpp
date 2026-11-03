#pragma once
// ===========================================================================
// 파일 역할 : 로봇 흉내 — "1차 지연" 모델. 서보 모터가 목표를 향해 서서히 따라가는 성질만 흉내 낸다.
//
//   매 주기:  position += (target - position) * alpha,   alpha = 주기 / 시정수
//   예) 주기 1 ms, 시정수 50 ms → alpha = 0.02 → 목표의 63%에 도달하는 데 약 50 ms
//
// 용도: ROS 2 노드 전체(명령 → RT 루프 → 상태 발행 → 워치독)를 로봇·시뮬레이터 없이 돌려본다.
// 물리는 없다. 관절 한계·충돌·중력 없음. D5 에 MuJoCo 백엔드로 교체한다.
// ===========================================================================
#include <cstdint>

#include "rt_core/backend.hpp"
#include "rt_core/joint_types.hpp"

namespace rt_core {

class SimLagBackend : public Backend {
 public:
  explicit SimLagBackend(double time_constant_s = 0.05) : time_constant_s_(time_constant_s) {}

  bool init(std::uint32_t dof, std::int64_t period_ns) override;
  void write_command(const double* target_position, std::uint32_t dof) override;
  void read_state(double* position, double* velocity, std::uint32_t dof) override;

 private:
  double time_constant_s_;
  double alpha_ = 0.0;        // 주기 / 시정수
  double dt_s_ = 0.001;       // 주기 (초)
  std::uint32_t dof_ = 0;
  double target_[kMaxJoints] = {0.0};
  double position_[kMaxJoints] = {0.0};
  double velocity_[kMaxJoints] = {0.0};
};

}  // namespace rt_core
