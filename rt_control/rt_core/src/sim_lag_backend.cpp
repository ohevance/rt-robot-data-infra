#include "rt_core/sim_lag_backend.hpp"

namespace rt_core {

bool SimLagBackend::init(std::uint32_t dof, std::int64_t period_ns) {
  if (dof == 0 || dof > kMaxJoints) {
    return false;
  }
  dof_ = dof;
  dt_s_ = static_cast<double>(period_ns) / 1e9;
  alpha_ = dt_s_ / time_constant_s_;
  if (alpha_ > 1.0) {
    alpha_ = 1.0;  // 시정수가 주기보다 짧으면 "즉시 도달"로 취급
  }
  for (std::uint32_t j = 0; j < dof_; ++j) {
    target_[j] = 0.0;
    position_[j] = 0.0;
    velocity_[j] = 0.0;
  }
  return true;
}

void SimLagBackend::write_command(const double* target_position, std::uint32_t dof) {
  for (std::uint32_t j = 0; j < dof && j < dof_; ++j) {
    target_[j] = target_position[j];
  }
}

// 읽을 때 한 주기만큼 시간을 진행시킨다 (명령 쓰기 → 한 주기 뒤의 상태 읽기)
void SimLagBackend::read_state(double* position, double* velocity, std::uint32_t dof) {
  for (std::uint32_t j = 0; j < dof && j < dof_; ++j) {
    double before = position_[j];
    position_[j] = before + (target_[j] - before) * alpha_;
    velocity_[j] = (position_[j] - before) / dt_s_;
    position[j] = position_[j];
    velocity[j] = velocity_[j];
  }
}

}  // namespace rt_core
