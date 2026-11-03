#pragma once
// ===========================================================================
// 파일 역할 : 실시간(RT) 제어 루프의 뼈대. "정해진 주기마다 반드시 한 번" 도는 루프.
//
// 읽는 순서 : 1) Sample   — 한 주기에서 측정하는 값 4개
//            2) RtConfig — 루프를 어떻게 돌릴지 (주기, 우선순위, CPU, 시간)
//            3) RtStatus — 환경에서 실제로 되었는지/실패했는지 기록
//            4) RtLoop::run() 의 5단계 (구현은 rt_loop.cpp)
//
// 이 코드는 ROS 2를 모른다 (순수 C++17 + 리눅스 POSIX).
// ROS 2 노드는 이 루프를 감싸는 얇은 껍질일 뿐이다 → ROS 2 없는 곳에서도 빌드·시험된다.
// ===========================================================================
#include <atomic>
#include <cstddef>
#include <cstdint>
#include <string>

#include "rt_core/spsc_ring.hpp"

namespace rt_core {

// ---------------------------------------------------------------------------
// 1) 한 주기에서 측정하는 값. 크기가 고정(32바이트)이라 링 버퍼에 복사만 한다.
// ---------------------------------------------------------------------------
struct Sample {
  std::uint64_t iter;          // 몇 번째 주기인가 (0부터)
  std::int64_t wake_lat_ns;    // "깨어나기로 한 시각"보다 얼마나 늦게 깼나. 늘 0 이상 (wake-up latency)
  std::int64_t period_err_ns;  // (이번 깨어남 - 지난 깨어남) - 목표 주기. 흔들림(지터)의 원천
  std::int64_t work_ns;        // "제어 계산" 흉내에 실제로 걸린 시간
};

// ---------------------------------------------------------------------------
// 2) 루프 설정
// ---------------------------------------------------------------------------
struct RtConfig {
  std::int64_t period_ns = 1000000;  // 주기. 1,000,000 ns = 1 ms = 1 kHz
  int prio = 80;                     // SCHED_FIFO 우선순위 1~99. 0 이면 일반 스케줄링으로 돈다
  int cpu = -1;                      // 고정할 CPU 번호. -1 이면 고정하지 않는다
  double seconds = 10.0;             // 얼마나 오래 돌릴지
  std::uint32_t work_us = 50;        // 매 주기 "제어 계산" 흉내로 바쁘게 도는 시간 (마이크로초)
};

// ---------------------------------------------------------------------------
// 3) 환경에서 실제로 적용된 것 / 실패한 것. 표를 만들 때 숫자 옆에 같이 적는다.
//    ("SCHED_FIFO 가 됐는가, RT 커널이었는가"를 모르면 숫자는 의미가 없다)
// ---------------------------------------------------------------------------
struct RtStatus {
  bool rt_sched_ok = false;      // SCHED_FIFO 적용 성공?
  int rt_errno = 0;              // 실패했다면 오류 번호 (EPERM = 권한 없음)
  bool mlock_ok = false;         // 메모리 잠금 성공?
  int mlock_errno = 0;
  bool affinity_ok = false;      // CPU 고정 성공?
  int affinity_errno = 0;
  bool kernel_realtime = false;  // /sys/kernel/realtime 가 1 이면 PREEMPT_RT 커널
  std::string kernel_release;    // uname -r 결과
};

// 링 버퍼 칸 수. 65536 샘플 = 1 kHz 에서 약 65초 분량.
constexpr std::size_t kRingSize = 65536;

// ---------------------------------------------------------------------------
// 4) RT 루프
// ---------------------------------------------------------------------------
class RtLoop {
 public:
  explicit RtLoop(const RtConfig& cfg) : cfg_(cfg) {}

  // "지금 이 스레드"를 RT 스레드로 만들고 루프를 돈다.
  // 매 주기의 측정값을 ring 에 넣고, 꽉 차서 못 넣으면 drops 를 1 올린다 (기다리지 않는다).
  // 반환값: 실제로 돈 주기 수
  std::uint64_t run(SpscRing<Sample, kRingSize>& ring, std::atomic<std::uint64_t>& drops);

  const RtStatus& status() const { return status_; }
  const RtConfig& config() const { return cfg_; }

 private:
  // run() 이 순서대로 부르는 준비 단계 5개. 각각 한 가지 일만 한다.
  void record_kernel_info();     // 0) 커널 이름과 RT 여부를 기록
  void lock_memory();            // 1) mlockall : 메모리를 RAM에 고정
  void pin_cpu();                // 2) CPU 고정 (cfg_.cpu >= 0 일 때만)
  void set_realtime_priority();  // 3) SCHED_FIFO 적용 (cfg_.prio > 0 일 때만)
  void prefault_stack();         // 4) 스택을 미리 밟아 두기

  RtConfig cfg_;
  RtStatus status_;
};

}  // namespace rt_core
