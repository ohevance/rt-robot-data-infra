// ===========================================================================
// 파일 역할 : 같은 PC 의 rt_zmq_node 가 공유 메모리에 쓰는 "최신 상태 한 장"을 소켓 없이 읽어 한 줄 JSON 으로 찍는다.
//            C++ 프로그램이 상태를 읽는 가장 짧은 길의 예 (로거·진단 도구·UI 백엔드가 이렇게 붙는다).
//
//   rt_state_peek [--shm /rt_state] [--count 10] [--interval-ms 100]
//
// 무엇을 찍나: iter · 상태 머신 · 워치독 · 반영된 명령 번호 · 위치 · 그리고 "나이"(쓴 지 얼마나 됐나).
//   나이가 주기보다 훨씬 크면 쓰는 쪽(노드)이 멈췄다는 뜻 — 공유 메모리는 쓰는 쪽이 죽어도 마지막 내용을 그대로 보여 주므로
//   "최신인가"는 읽는 쪽이 시각으로 판단해야 한다. (같은 PC 라 CLOCK_MONOTONIC 이 같다)
// ===========================================================================
#include <cstdio>
#include <cstdlib>
#include <string>

#include <time.h>

#include "rt_core/joint_types.hpp"
#include "rt_core/robot_state_machine.hpp"
#include "rt_core/rt_clock.hpp"
#include "rt_core/shm_seqlock.hpp"

using namespace rt_core;

int main(int argc, char** argv) {
  std::string name = "/rt_state";
  int count = 10;
  int interval_ms = 100;
  for (int i = 1; i + 1 < argc; i += 2) {
    std::string a = argv[i];
    if (a == "--shm") name = argv[i + 1];
    else if (a == "--count") count = std::atoi(argv[i + 1]);
    else if (a == "--interval-ms") interval_ms = std::atoi(argv[i + 1]);
  }

  ShmSegment<JointStateSample> shm;
  if (!shm.open(name)) {
    std::fprintf(stderr, "공유 메모리 %s 를 열 수 없음 (errno %d — 2: 노드가 안 떠 있음, 71: 형식이 다름)\n", name.c_str(), shm.error());
    return 1;
  }
  const ShmHeader& h = shm.header();
  std::fprintf(stderr, "열림: %s, 쓰는 프로세스 %lld, 주기 %lld ns\n", name.c_str(), static_cast<long long>(h.writer_pid),
               static_cast<long long>(h.period_ns));

  timespec nap = {interval_ms / 1000, static_cast<long>(interval_ms % 1000) * 1000000L};
  for (int n = 0; n < count; ++n) {
    JointStateSample s;
    std::uint64_t seq = 0;
    if (!shm.read(s, 1000, &seq)) {
      std::printf("{\"error\": \"1000번 읽는 동안 매번 쓰는 중이었다\"}\n");
    } else if (seq == 0) {
      std::printf("{\"error\": \"아직 한 번도 쓰지 않았다\"}\n");
    } else {
      double age_ms = static_cast<double>(now_ns() - s.stamp_ns) / 1e6;
      std::printf("{\"iter\": %llu, \"age_ms\": %.3f, \"state\": \"%s\", \"watchdog\": %s, \"cmd_seq\": %u, \"dof\": %u, \"position\": [",
                  static_cast<unsigned long long>(s.iter), age_ms, robot_state_name(static_cast<RobotState>(s.robot_state)),
                  s.watchdog_tripped ? "true" : "false", s.cmd_seq, s.dof);
      for (std::uint32_t j = 0; j < s.dof && j < kMaxJoints; ++j) {
        std::printf("%s%.4f", j ? ", " : "", s.position[j]);
      }
      std::printf("]}\n");
    }
    std::fflush(stdout);
    if (n + 1 < count) {
      nanosleep(&nap, nullptr);
    }
  }
  return 0;
}
