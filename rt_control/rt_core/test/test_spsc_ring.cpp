// ===========================================================================
// 파일 역할 : SPSC 링 버퍼 단위 테스트 (외부 테스트 프레임워크 없이 동작)
//
// 확인하는 것
//   1) 용량 경계 : 7개(= N-1)까지 들어가고, 8번째는 실패하고, 빈 상태에서 pop 은 실패한다
//   2) 순서 보존 : 넣은 순서대로 나온다
//   3) 두 스레드 : 생산자와 소비자가 동시에 돌 때 역순·중복이 없다 (드롭은 허용)
// ===========================================================================
#include <atomic>
#include <cstdio>
#include <thread>

#include "rt_core/spsc_ring.hpp"

static int g_fail_count = 0;

// 조건이 거짓이면 메시지를 찍고 실패를 센다
static void check(bool condition, const char* message) {
  if (!condition) {
    std::fprintf(stderr, "FAIL: %s\n", message);
    g_fail_count = g_fail_count + 1;
  }
}

// 1) + 2) 한 스레드에서 경계와 순서를 본다
static void test_capacity_and_order() {
  rt_core::SpscRing<int, 8> ring;  // 칸 8개 → 실제 용량 7개
  int value = 0;

  check(ring.pop(value) == false, "비어 있을 때 pop 은 실패해야 한다");

  for (int i = 0; i < 7; ++i) {
    check(ring.push(i) == true, "용량 안에서는 push 가 성공해야 한다");
  }
  check(ring.push(99) == false, "꽉 찼을 때 push 는 실패해야 한다");

  for (int i = 0; i < 7; ++i) {
    check(ring.pop(value) == true, "들어 있는 만큼 pop 은 성공해야 한다");
    check(value == i, "넣은 순서대로 나와야 한다");
  }
  check(ring.pop(value) == false, "다 꺼내면 다시 비어 있어야 한다");
}

// 3) 두 스레드. 생산자는 0,1,2,... 를 넣고(꽉 차면 버림), 소비자는 값이 항상 커지는지 본다
static rt_core::SpscRing<std::uint64_t, 1024> g_ring;

static void consumer_main(std::atomic<bool>* producer_done) {
  std::uint64_t expect_at_least = 0;
  std::uint64_t v = 0;
  while (true) {
    if (g_ring.pop(v)) {
      check(v >= expect_at_least, "값은 항상 커져야 한다 (역순·중복 금지)");
      expect_at_least = v + 1;
      continue;
    }
    if (producer_done->load(std::memory_order_acquire)) {
      // 생산자가 끝났으면 남은 것을 비우고 종료
      while (g_ring.pop(v)) {
        check(v >= expect_at_least, "값은 항상 커져야 한다 (마무리 단계)");
        expect_at_least = v + 1;
      }
      return;
    }
    std::this_thread::yield();
  }
}

static void test_two_threads() {
  const std::uint64_t kCount = 1000000;
  std::atomic<bool> producer_done{false};
  std::uint64_t drops = 0;

  std::thread consumer(consumer_main, &producer_done);

  for (std::uint64_t i = 0; i < kCount; ++i) {
    if (!g_ring.push(i)) {
      drops = drops + 1;  // 꽉 차면 버린다 — RT 스레드와 같은 규칙
    }
  }
  producer_done.store(true, std::memory_order_release);
  consumer.join();

  std::printf("two-thread test: produced=%llu drops=%llu\n", static_cast<unsigned long long>(kCount),
              static_cast<unsigned long long>(drops));
}

int main() {
  test_capacity_and_order();
  test_two_threads();

  if (g_fail_count == 0) {
    std::puts("OK: spsc_ring");
    return 0;
  }
  std::printf("FAILED: %d checks\n", g_fail_count);
  return 1;
}
