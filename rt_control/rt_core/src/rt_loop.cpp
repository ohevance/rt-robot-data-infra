// ===========================================================================
// 파일 역할 : RtLoop 의 구현. rt_loop.hpp 를 먼저 읽고 오세요.
//
// 읽는 순서 : 1) 시간 도우미 함수 3개 (ns ↔ timespec, 지금 시각)
//            2) 준비 단계 5개 (record_kernel_info ~ prefault_stack)
//            3) run() — 루프 본체. 이 파일의 핵심은 run() 의 for 문 20줄이다.
// ===========================================================================
#include "rt_core/rt_loop.hpp"

#include <pthread.h>     // pthread_setaffinity_np, pthread_setschedparam
#include <sched.h>       // SCHED_FIFO, cpu_set_t
#include <sys/mman.h>    // mlockall, munlockall
#include <sys/utsname.h> // uname
#include <time.h>        // clock_gettime, clock_nanosleep

#include <cerrno>
#include <fstream>

namespace rt_core {

// ---------------------------------------------------------------------------
// 1) 시간 도우미. 커널은 timespec(초 + 나노초) 를 쓰고, 계산은 나노초 정수가 편하다.
// ---------------------------------------------------------------------------
static const std::int64_t kNsPerSec = 1000000000;

static std::int64_t timespec_to_ns(const timespec& t) {
  return static_cast<std::int64_t>(t.tv_sec) * kNsPerSec + t.tv_nsec;
}

static timespec ns_to_timespec(std::int64_t ns) {
  timespec t;
  t.tv_sec = static_cast<time_t>(ns / kNsPerSec);
  t.tv_nsec = static_cast<long>(ns % kNsPerSec);
  return t;
}

// 지금 시각(나노초). CLOCK_MONOTONIC = 시스템 시계를 바꿔도 뒤로 가지 않는 "단조 시계"
static std::int64_t now_ns() {
  timespec t;
  clock_gettime(CLOCK_MONOTONIC, &t);
  return timespec_to_ns(t);
}

// ---------------------------------------------------------------------------
// 2) 준비 단계
// ---------------------------------------------------------------------------

// 0) 커널 이름(uname -r)과 PREEMPT_RT 여부(/sys/kernel/realtime == 1)를 기록한다.
void RtLoop::record_kernel_info() {
  utsname u{};
  if (uname(&u) == 0) {
    status_.kernel_release = u.release;
  }
  std::ifstream f("/sys/kernel/realtime");  // RT 커널에만 있는 파일
  int value = 0;
  if (f && (f >> value)) {
    status_.kernel_realtime = (value == 1);
  }
}

// 1) 메모리 잠금. 지금 쓰는 페이지(MCL_CURRENT)와 앞으로 쓸 페이지(MCL_FUTURE)를
//    RAM에 고정해서, 루프 중에 디스크(스왑)를 기다리는 일이 없게 한다.
//    권한이나 한도(ulimit -l) 때문에 실패할 수 있다 → 실패해도 계속 돌고, 상태에 남긴다.
void RtLoop::lock_memory() {
  if (mlockall(MCL_CURRENT | MCL_FUTURE) == 0) {
    status_.mlock_ok = true;
  } else {
    status_.mlock_errno = errno;
  }
}

// 2) CPU 고정. 스레드가 CPU 사이를 옮겨 다니면 캐시가 식고 지연이 생긴다.
void RtLoop::pin_cpu() {
  if (cfg_.cpu < 0) {
    return;  // 설정에서 고정하지 않기로 함
  }
  cpu_set_t set;
  CPU_ZERO(&set);
  CPU_SET(cfg_.cpu, &set);
  int rc = pthread_setaffinity_np(pthread_self(), sizeof(set), &set);
  if (rc == 0) {
    status_.affinity_ok = true;
  } else {
    status_.affinity_errno = rc;
  }
}

// 3) 실시간 스케줄링. SCHED_FIFO = "더 급한 스레드가 없으면 CPU를 내놓지 않는다".
//    root 또는 CAP_SYS_NICE 권한이 필요하다. 없으면 EPERM 으로 실패한다.
void RtLoop::set_realtime_priority() {
  if (cfg_.prio <= 0) {
    return;  // 일반 스케줄링으로 돌기로 함 (--no-rt)
  }
  sched_param sp{};
  sp.sched_priority = cfg_.prio;
  int rc = pthread_setschedparam(pthread_self(), SCHED_FIFO, &sp);
  if (rc == 0) {
    status_.rt_sched_ok = true;
  } else {
    status_.rt_errno = rc;
  }
}

// 4) 스택 미리 밟기. 스택 메모리는 "처음 쓸 때" 커널이 페이지를 붙여 준다(페이지 폴트).
//    그 일이 루프 도중에 일어나면 지연이 된다. 그래서 256 KB를 지금 한 번 건드려 둔다.
void RtLoop::prefault_stack() {
  const std::size_t kStackBytes = 256 * 1024;
  const std::size_t kPageBytes = 4096;
  volatile unsigned char pad[kStackBytes];  // volatile: 컴파일러가 "안 쓰는 배열"이라고 지우지 못하게
  for (std::size_t i = 0; i < kStackBytes; i += kPageBytes) {
    pad[i] = 0;
  }
  unsigned char last = pad[kStackBytes - kPageBytes];  // 한 번 읽어서 "쓰기만 하고 안 쓴 변수" 경고를 막는다
  (void)last;
}

// ---------------------------------------------------------------------------
// 3) 루프 본체
// ---------------------------------------------------------------------------
std::uint64_t RtLoop::run(SpscRing<Sample, kRingSize>& ring, std::atomic<std::uint64_t>& drops) {
  record_kernel_info();
  lock_memory();
  pin_cpu();
  set_realtime_priority();
  prefault_stack();

  // 몇 번 돌 것인가 = 시간 / 주기
  const std::uint64_t total_iters =
      static_cast<std::uint64_t>(cfg_.seconds * 1e9 / static_cast<double>(cfg_.period_ns));

  // 매 주기 바쁘게 돌 시간 (마이크로초 → 나노초)
  const std::int64_t work_target_ns = static_cast<std::int64_t>(cfg_.work_us) * 1000;

  std::int64_t next_wake_ns = now_ns() + cfg_.period_ns;  // 첫 번째 목표 시각
  std::int64_t prev_wake_ns = 0;                          // 지난 번 실제로 깬 시각 (첫 주기에는 없음)
  std::uint64_t done = 0;

  for (std::uint64_t i = 0; i < total_iters; ++i) {
    // (a) 목표 시각까지 잔다. "지금부터 1 ms" 가 아니라 "그 시각(절대 시각)에" 깨워 달라고 한다.
    //     그래야 늦게 깬 만큼이 다음 주기로 쌓이지 않는다 (드리프트 없음).
    //     EINTR = 신호 때문에 잠이 깨진 경우 → 같은 시각으로 다시 잔다.
    timespec wake_ts = ns_to_timespec(next_wake_ns);
    while (clock_nanosleep(CLOCK_MONOTONIC, TIMER_ABSTIME, &wake_ts, nullptr) == EINTR) {
    }
    std::int64_t woke_ns = now_ns();

    // (b) 측정: 얼마나 늦게 깼나, 지난 주기와의 간격은 목표와 얼마나 달랐나
    Sample s;
    s.iter = i;
    s.wake_lat_ns = woke_ns - next_wake_ns;
    if (prev_wake_ns == 0) {
      s.period_err_ns = 0;  // 첫 주기는 비교 대상이 없다 (통계에서 제외한다)
    } else {
      s.period_err_ns = (woke_ns - prev_wake_ns) - cfg_.period_ns;
    }
    prev_wake_ns = woke_ns;

    // (c) 제어 계산 흉내: work_us 동안 바쁘게 돈다.
    //     실제 제어 노드에서는 여기서 "관절 상태 읽기 → 명령 계산 → 명령 쓰기"를 한다.
    std::int64_t work_start_ns = now_ns();
    while (now_ns() - work_start_ns < work_target_ns) {
      // 아무것도 안 하고 시간만 보낸다 (busy-wait)
    }
    s.work_ns = now_ns() - work_start_ns;

    // (d) 로깅 스레드로 넘긴다. 꽉 차면 기다리지 않고 "드롭"으로 센다.
    if (!ring.push(s)) {
      drops.fetch_add(1, std::memory_order_relaxed);
    }

    // (e) 다음 목표 시각 = 이번 목표 시각 + 주기  (실제로 깬 시각이 아니라 "목표"에 더한다)
    next_wake_ns += cfg_.period_ns;
    ++done;
  }

  munlockall();  // 메모리 잠금 해제
  return done;
}

}  // namespace rt_core
