// ===========================================================================
// 파일 역할 : ControlStep 의 구현. control_step.hpp 를 먼저 읽고 오세요.
// 읽는 순서 : step() → take_latest_command() → check_watchdog() → limit_step()
// ===========================================================================
#include "rt_core/control_step.hpp"

#include "rt_core/rt_clock.hpp"

namespace rt_core {

ControlStep::ControlStep(const ControlConfig& cfg, Backend& backend, CommandRing& cmd_ring, StateRing& state_ring,
                         ControlCounters& counters)
    : cfg_(cfg), backend_(backend), cmd_ring_(cmd_ring), state_ring_(state_ring), counters_(counters) {
  for (std::uint32_t j = 0; j < kMaxJoints; ++j) {
    desired_[j] = 0.0;
    applied_[j] = 0.0;
    position_[j] = 0.0;
    velocity_[j] = 0.0;
  }
}

// ---------------------------------------------------------------------------
// 한 주기
// ---------------------------------------------------------------------------
void ControlStep::step(std::uint64_t iter, std::int64_t wake_lat_ns) {
  std::int64_t now = now_ns();

  take_latest_command(now);  // 1) 우편함 비우기 → desired_
  check_watchdog(now);       // 2) 끊겼으면 desired_ = 현재 위치 (멈춤)
  limit_step();              // 3) applied_ 가 한 주기에 max_step_rad 이상 뛰지 않게

  // 4) 로봇에 쓰고 읽는다
  backend_.write_command(applied_, cfg_.dof);
  backend_.read_state(position_, velocity_, cfg_.dof);

  // 5) 상태 벨트에 올린다. 꽉 차면 버리고 센다 (기다리지 않는다)
  JointStateSample s;
  s.iter = iter;
  s.stamp_ns = now;
  s.wake_lat_ns = wake_lat_ns;
  s.dof = cfg_.dof;
  s.watchdog_tripped = tripped_;
  for (std::uint32_t j = 0; j < cfg_.dof; ++j) {
    s.position[j] = position_[j];
    s.velocity[j] = velocity_[j];
    s.target[j] = applied_[j];
  }
  if (!state_ring_.push(s)) {
    counters_.state_drops.fetch_add(1, std::memory_order_relaxed);
  }
}

// 1) 우편함에 쌓인 명령을 전부 꺼내고 마지막 것만 쓴다.
//    (1 kHz 루프에 50 Hz 명령이 오면 대부분의 주기는 빈 우편함이고, 가끔 1개가 들어 있다.
//     네트워크가 밀렸다 풀리면 여러 개가 한꺼번에 올 수 있는데, 오래된 목표를 따라갈 이유는 없다.)
void ControlStep::take_latest_command(std::int64_t now_ns) {
  JointCommand cmd;
  bool got_any = false;
  while (cmd_ring_.pop(cmd)) {
    got_any = true;
  }
  if (!got_any) {
    return;
  }
  if (cmd.dof != cfg_.dof) {
    return;  // 관절 수가 안 맞는 명령은 무시한다 (상위에서 걸러지지만 한 번 더)
  }
  for (std::uint32_t j = 0; j < cfg_.dof; ++j) {
    desired_[j] = cmd.position[j];
  }
  last_cmd_ns_ = now_ns;
  counters_.commands_applied.fetch_add(1, std::memory_order_relaxed);
}

// 2) 워치독. 명령이 watchdog_ns 보다 오래 안 오면 "멈춤": 목표를 현재 위치로 바꿔 더 움직이지 않게 한다.
//    실물에서는 여기서 토크를 끄는 것까지 간다 (Backend 에 safe_stop() 을 추가할 자리).
void ControlStep::check_watchdog(std::int64_t now_ns) {
  bool stale = (last_cmd_ns_ == 0) || (now_ns - last_cmd_ns_ > cfg_.watchdog_ns);

  if (stale) {
    if (!tripped_) {
      counters_.watchdog_trips.fetch_add(1, std::memory_order_relaxed);  // 정상 → 멈춤 전환 횟수
    }
    tripped_ = true;
    for (std::uint32_t j = 0; j < cfg_.dof; ++j) {
      desired_[j] = position_[j];  // 지금 있는 자리에 머문다
    }
  } else {
    tripped_ = false;
  }
  counters_.watchdog_tripped.store(tripped_, std::memory_order_relaxed);
}

// 3) 변화량 제한. 상위가 갑자기 1 rad 를 요구해도 한 주기에는 max_step_rad 만큼만 움직인다.
//    (명령 버그·네트워크 재전송으로 튀는 값이 로봇을 치는 것을 막는 마지막 안전장치)
void ControlStep::limit_step() {
  bool limited = false;
  for (std::uint32_t j = 0; j < cfg_.dof; ++j) {
    double delta = desired_[j] - applied_[j];
    if (delta > cfg_.max_step_rad) {
      delta = cfg_.max_step_rad;
      limited = true;
    } else if (delta < -cfg_.max_step_rad) {
      delta = -cfg_.max_step_rad;
      limited = true;
    }
    applied_[j] = applied_[j] + delta;
  }
  if (limited) {
    counters_.step_limited.fetch_add(1, std::memory_order_relaxed);
  }
}

}  // namespace rt_core
