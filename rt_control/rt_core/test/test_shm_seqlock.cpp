// ===========================================================================
// 파일 역할 : seqlock·공유 메모리(shm_seqlock.hpp) 시험.
//   1) 섞인 읽기가 0번: 쓰는 스레드가 "모든 칸이 같은 값"인 묶음을 쉬지 않고 쓰고, 읽는 스레드가 계속 읽는다.
//      받아들인 묶음에서 칸 값이 하나라도 다르면 "쓰는 도중의 반쪽"을 받아들였다는 뜻 → 실패.
//      (seqlock 의 번호 확인을 지우면 이 시험이 실패하는 것을 확인했다 — 시험이 무엇을 잡는지 알고 쓴다)
//   2) 프로세스 사이: fork 한 자식이 공유 메모리를 열어 읽는다. 부모(쓰는 쪽)는 기다리지 않는다.
//   3) 형식이 다르면 열지 않는다 (크기가 다른 형으로 열기 → EPROTO)
// 실행: ctest 의 shm_seqlock
// ===========================================================================
#include <atomic>
#include <cerrno>
#include <chrono>
#include <cstdio>
#include <string>
#include <thread>

#include <sys/wait.h>
#include <unistd.h>

#include "rt_core/joint_types.hpp"
#include "rt_core/shm_seqlock.hpp"

using namespace rt_core;

static int g_fail = 0;
#define CHECK(cond)                                              \
  do {                                                           \
    if (!(cond)) {                                               \
      std::printf("FAIL %s:%d  %s\n", __FILE__, __LINE__, #cond); \
      g_fail = g_fail + 1;                                       \
    }                                                            \
  } while (0)

// 1.6 KB — JointStateSample 와 같은 규모. 칸이 많을수록 반쪽 읽기가 일어날 틈이 크다
struct Bundle {
  std::uint64_t v[200];
};

static bool consistent(const Bundle& b) {
  for (int i = 1; i < 200; ++i) {
    if (b.v[i] != b.v[0]) {
      return false;
    }
  }
  return true;
}

static void test_no_torn_reads() {
  static SeqlockBlock<Bundle> block;
  std::atomic<bool> stop{false};
  std::thread writer([&]() {
    Bundle b;
    for (std::uint64_t n = 1; !stop.load(std::memory_order_relaxed); ++n) {
      for (int i = 0; i < 200; ++i) {
        b.v[i] = n;
      }
      block.write(b);
    }
  });

  std::uint64_t accepted = 0, retried = 0, torn = 0, last = 0, backwards = 0;
  auto end = std::chrono::steady_clock::now() + std::chrono::milliseconds(700);
  Bundle got;
  while (std::chrono::steady_clock::now() < end) {
    if (block.try_read(got)) {
      accepted = accepted + 1;
      if (!consistent(got)) {
        torn = torn + 1;
      }
      if (got.v[0] < last) {
        backwards = backwards + 1;  // 한 번 본 것보다 옛것을 받으면 안 된다
      }
      last = got.v[0];
    } else {
      retried = retried + 1;
    }
  }
  stop = true;
  writer.join();
  std::printf("  같은 프로세스: 받아들임 %llu, 다시 읽음 %llu, 섞임 %llu, 뒤로 감 %llu, 쓴 횟수 %llu\n",
              static_cast<unsigned long long>(accepted), static_cast<unsigned long long>(retried),
              static_cast<unsigned long long>(torn), static_cast<unsigned long long>(backwards),
              static_cast<unsigned long long>(block.writes()));
  CHECK(accepted > 1000);
  CHECK(torn == 0);
  CHECK(backwards == 0);
}

static void test_cross_process() {
  std::string name = "/rt_core_test_" + std::to_string(::getpid());
  ShmSegment<JointStateSample> writer;
  CHECK(writer.create(name, 1000000));

  pid_t child = ::fork();
  if (child == 0) {
    // 자식: 열고 1초 동안 읽는다. dof 와 position[0..dof) 가 모두 iter 와 맞아야 한다 (쓰는 쪽이 그렇게 쓴다)
    ShmSegment<JointStateSample> reader;
    for (int i = 0; i < 100 && !reader.open(name); ++i) {
      std::this_thread::sleep_for(std::chrono::milliseconds(5));
    }
    JointStateSample s;
    std::uint64_t ok = 0, bad = 0;
    auto end = std::chrono::steady_clock::now() + std::chrono::milliseconds(500);
    while (std::chrono::steady_clock::now() < end) {
      if (reader.read(s, 100)) {
        bool same = (s.dof == 6);
        for (std::uint32_t j = 0; j < 6; ++j) {
          if (s.position[j] != static_cast<double>(s.iter) || s.target[j] != static_cast<double>(s.iter)) {
            same = false;
          }
        }
        if (same) {
          ok = ok + 1;
        } else if (s.iter != 0) {
          bad = bad + 1;
        }
      }
    }
    ::_exit((ok > 100 && bad == 0) ? 0 : 1);
  }

  // 부모: 0.7초 동안 계속 쓴다 (기다리지 않는다)
  JointStateSample s;
  s.dof = 6;
  auto end = std::chrono::steady_clock::now() + std::chrono::milliseconds(700);
  std::uint64_t n = 0;
  while (std::chrono::steady_clock::now() < end) {
    n = n + 1;
    s.iter = n;
    for (std::uint32_t j = 0; j < 6; ++j) {
      s.position[j] = static_cast<double>(n);
      s.target[j] = static_cast<double>(n);
    }
    writer.write(s);
  }
  int status = 0;
  ::waitpid(child, &status, 0);
  std::printf("  프로세스 사이: 부모가 %llu 번 씀, 자식 판정 %s\n", static_cast<unsigned long long>(n),
              (WIFEXITED(status) && WEXITSTATUS(status) == 0) ? "통과" : "실패");
  CHECK(WIFEXITED(status) && WEXITSTATUS(status) == 0);

  // 3) 다른 형으로 열면 거절
  ShmSegment<std::uint64_t> wrong;
  CHECK(!wrong.open(name));
  CHECK(wrong.error() == EPROTO);

  writer.close();  // 이름도 지운다
  ShmSegment<JointStateSample> gone;
  CHECK(!gone.open(name));
}

int main() {
  test_no_torn_reads();
  test_cross_process();
  if (g_fail != 0) {
    std::printf("shm_seqlock: %d 실패\n", g_fail);
    return 1;
  }
  std::printf("OK: shm_seqlock (섞인 읽기 0 · 프로세스 사이 · 형식 확인)\n");
  return 0;
}
