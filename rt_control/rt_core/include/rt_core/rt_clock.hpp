#pragma once
// ===========================================================================
// 파일 역할 : 시간 도우미 3개. 여러 파일에서 같이 쓰므로 한 곳에 둔다.
//   커널은 timespec(초 + 나노초) 두 칸을 쓰고, 우리 계산은 나노초 정수 한 칸이 편하다.
// ===========================================================================
#include <time.h>

#include <cstdint>

namespace rt_core {

const std::int64_t kNsPerSec = 1000000000;

inline std::int64_t timespec_to_ns(const timespec& t) {
  return static_cast<std::int64_t>(t.tv_sec) * kNsPerSec + t.tv_nsec;
}

inline timespec ns_to_timespec(std::int64_t ns) {
  timespec t;
  t.tv_sec = static_cast<time_t>(ns / kNsPerSec);
  t.tv_nsec = static_cast<long>(ns % kNsPerSec);
  return t;
}

// 지금 시각(나노초). CLOCK_MONOTONIC = 시스템 시계를 바꿔도 뒤로 가지 않는 "단조 시계"
inline std::int64_t now_ns() {
  timespec t;
  clock_gettime(CLOCK_MONOTONIC, &t);
  return timespec_to_ns(t);
}

}  // namespace rt_core
