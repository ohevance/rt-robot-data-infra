#pragma once
// ===========================================================================
// 파일 역할 : RT 스레드 → 로깅 스레드로 측정값을 넘기는 "줄 서지 않는 벨트"
//            (SPSC 링 버퍼 = Single Producer / Single Consumer ring buffer)
//
// 읽는 순서 : 1) 맨 아래 멤버 변수 3개 (head_, tail_, buffer_)
//            2) push()  — 생산자(RT 스레드)가 넣는다
//            3) pop()   — 소비자(로깅 스레드)가 꺼낸다
//
// 전제      : 넣는 스레드 하나, 꺼내는 스레드 하나. (둘 이상이면 이 코드는 틀린다)
//
// 왜 필요한가
//   RT 스레드는 절대 기다리면 안 된다. 그런데 파일에 로그를 쓰는 일은 몇 ms씩
//   멈출 수 있다. 그래서 RT 스레드는 값을 이 벨트에 "올려놓기만" 하고,
//   일반 스레드가 꺼내서 파일에 쓴다. 벨트가 꽉 차면 RT 스레드는 그 값을
//   버리고 다음 일을 한다. 기다리지 않는다.
//
// memory_order 쉬운 설명 (이 파일에서 쓰는 세 가지)
//   relaxed : 내가 마지막에 쓴 내 변수를 읽는 것. 순서 보장이 필요 없다.
//   acquire : 상대가 release로 공개한 변수를 읽는다. 상대가 "그 전에 써 둔
//             데이터"까지 같이 보이는 것을 보장받는다.
//   release : 내가 그 전에 써 둔 데이터가 먼저 보이도록 한 뒤에 변수를 공개한다.
//   → push 에서 "값을 먼저 쓰고(buffer_) → head_를 release로 공개" 하면,
//     pop 에서 "head_를 acquire로 읽은" 소비자는 그 값을 안전하게 읽을 수 있다.
// ===========================================================================
#include <array>
#include <atomic>
#include <cstddef>

namespace rt_core {

template <typename T, std::size_t N>  // T: 담을 값의 형, N: 칸 수 (2의 거듭제곱)
class SpscRing {
  static_assert((N & (N - 1)) == 0, "N은 2의 거듭제곱이어야 합니다 (예: 1024, 65536)");

 public:
  // 넣기. 성공하면 true, 꽉 차 있으면 false. 절대 기다리지 않는다.
  bool push(const T& value) {
    std::size_t head = head_.load(std::memory_order_relaxed);  // 내가 다음에 쓸 칸 (내 변수)
    std::size_t next_head = next_index(head);
    std::size_t tail = tail_.load(std::memory_order_acquire);  // 소비자가 다음에 읽을 칸 (상대 변수)

    if (next_head == tail) {
      return false;  // 꽉 참. "한 칸은 항상 비워 둔다"는 규칙으로 꽉 참/비어 있음을 구분한다
    }

    buffer_[head] = value;                                 // 1) 값을 먼저 쓴다
    head_.store(next_head, std::memory_order_release);     // 2) 그 다음에 head를 공개한다 (순서 중요)
    return true;
  }

  // 꺼내기. 성공하면 true, 비어 있으면 false.
  bool pop(T& out) {
    std::size_t tail = tail_.load(std::memory_order_relaxed);  // 내가 다음에 읽을 칸 (내 변수)
    std::size_t head = head_.load(std::memory_order_acquire);  // 생산자가 다음에 쓸 칸 (상대 변수)

    if (tail == head) {
      return false;  // 비어 있음
    }

    out = buffer_[tail];
    tail_.store(next_index(tail), std::memory_order_release);
    return true;
  }

  // 지금 들어 있는 개수. 두 스레드가 동시에 움직이는 중이면 대략값이다.
  std::size_t size() const {
    std::size_t head = head_.load(std::memory_order_acquire);
    std::size_t tail = tail_.load(std::memory_order_acquire);
    return (head - tail) & (N - 1);
  }

  // 실제로 담을 수 있는 최대 개수 (한 칸은 구분용으로 비워 둔다)
  static constexpr std::size_t capacity() { return N - 1; }

 private:
  // 다음 칸 번호. N이 2의 거듭제곱이므로 "& (N - 1)"은 "% N"과 결과가 같고 더 빠르다.
  // 예: N = 8 이면 N - 1 = 7 = 0b111. 7 + 1 = 8 = 0b1000, 8 & 0b111 = 0 → 처음으로 되돌아간다.
  static std::size_t next_index(std::size_t i) { return (i + 1) & (N - 1); }

  // head_ : 생산자가 다음에 쓸 칸 번호
  // tail_ : 소비자가 다음에 읽을 칸 번호
  // alignas(64) : 두 변수를 서로 다른 캐시 라인(64바이트)에 둔다. 같은 줄에 있으면
  //               두 CPU가 서로의 캐시를 계속 무효화해서 느려진다 ("false sharing").
  alignas(64) std::atomic<std::size_t> head_{0};
  alignas(64) std::atomic<std::size_t> tail_{0};
  std::array<T, N> buffer_{};
};

}  // namespace rt_core
