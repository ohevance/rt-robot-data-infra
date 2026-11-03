#pragma once
// ===========================================================================
// 파일 역할 : "한 주기에 할 일"의 모양(인터페이스)을 정한다.
//
// RtLoop 은 주기를 지키는 일만 하고, 매 주기 step() 을 한 번 부른다.
// step() 안에 무엇을 넣느냐로 용도가 갈린다.
//   - 측정기(jitter_bench)   : BusyWorkStep  — 50 us 동안 바쁘게 돌기만 한다
//   - 제어 노드(ROS 2 어댑터) : ControlStep   — 명령 읽기 → 안전 검사 → 로봇에 쓰기 → 상태 내보내기
//
// 규칙: step() 안에서는 기다리는 일(락, 파일, 메모리 할당, sleep)을 하지 않는다.
// ===========================================================================
#include <cstdint>

namespace rt_core {

class RtStep {
 public:
  virtual ~RtStep() {}

  // iter        : 몇 번째 주기인가 (0부터)
  // wake_lat_ns : 이번 주기에 "깨어나기로 한 시각"보다 얼마나 늦게 깼나 (RtLoop 이 재서 넘겨준다)
  virtual void step(std::uint64_t iter, std::int64_t wake_lat_ns) = 0;
};

// 측정기용: 정해진 시간(work_us) 동안 바쁘게 돈다. 실제 제어 계산의 자리 표시.
class BusyWorkStep : public RtStep {
 public:
  explicit BusyWorkStep(std::uint32_t work_us) : work_target_ns_(static_cast<std::int64_t>(work_us) * 1000) {}
  void step(std::uint64_t iter, std::int64_t wake_lat_ns) override;

 private:
  std::int64_t work_target_ns_;
};

}  // namespace rt_core
