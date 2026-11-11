#pragma once
// ===========================================================================
// 파일 역할 : 같은 컴퓨터의 다른 프로세스에게 "최신 상태 한 장"을 공유 메모리로 넘긴다. 쓰는 쪽은 절대 기다리지 않는다.
//
//   [RT 노드 프로세스]  write() ──▶  /dev/shm/<이름>  ──▶  read()  [같은 PC 의 다른 프로세스: 로거·UI·진단 도구]
//
// 읽는 순서 : 1) SeqlockBlock — 번호(seq) 하나 + 데이터 칸들. write / try_read
//            2) ShmHeader    — 공유 메모리 맨 앞의 "형식 표시". 읽는 쪽이 같은 형식인지 확인한다
//            3) ShmSegment   — shm_open + mmap 으로 만들기(create) / 열기(open)
//
// 왜 seqlock 인가 (DECISIONS 11/11)
//   - 링 버퍼(spsc_ring)는 "하나도 빠짐없이"가 목적이고 읽는 쪽이 하나여야 한다. 여기서 필요한 것은 "최신 한 장"을
//     여러 프로세스가 아무 때나 보는 것 — 읽는 쪽이 몇이든, 느리든, 죽든 쓰는 쪽(RT)에 영향이 없어야 한다.
//   - 뮤텍스는 안 된다: 읽던 프로세스가 락을 쥔 채 멈추면(디버거, kill -STOP) RT 스레드가 기다리게 된다.
//   - seqlock: 쓰는 쪽은 번호를 홀수로 → 데이터 → 짝수로. 읽는 쪽은 번호를 읽고 → 데이터를 복사하고 → 번호를 다시 읽어
//     둘이 같고 짝수일 때만 받아들인다. 다르면(쓰는 도중에 읽었으면) 버리고 다시 읽는다. 쓰는 쪽은 아무것도 기다리지 않는다.
//
// C++ 메모리 모델에서 올바르게: 데이터 칸을 std::atomic<uint64_t> 로 두고 relaxed 로 읽고 쓴다.
//   (보통의 memcpy 로 읽으면 "쓰는 도중의 읽기"가 데이터 경합 = 정의되지 않은 동작이다. 결과를 버리더라도.)
//   순서는 펜스 두 개로 맞춘다 — Boehm, "Can Seqlocks Get Along with Programming Language Memory Models?" (2012) 의 방식.
//
// 전제: 쓰는 쪽은 하나. std::atomic<uint64_t> 가 락 없이 동작해야 프로세스 사이에서도 맞다 (아래 static_assert).
// ===========================================================================
#include <atomic>
#include <cerrno>
#include <cstddef>
#include <cstdint>
#include <cstring>
#include <new>
#include <string>
#include <type_traits>

#include <fcntl.h>
#include <sys/mman.h>
#include <sys/stat.h>
#include <unistd.h>

namespace rt_core {

static_assert(std::atomic<std::uint64_t>::is_always_lock_free, "프로세스 사이 공유에는 락 없는 64비트 atomic 이 필요하다");

// ---------------------------------------------------------------------------
// 1) seqlock 한 칸
// ---------------------------------------------------------------------------
template <typename T>
class SeqlockBlock {
  static_assert(std::is_trivially_copyable<T>::value, "바이트 복사가 가능한 형만 담는다");

 public:
  static constexpr std::size_t kWords = (sizeof(T) + 7) / 8;

  // 쓰는 쪽 (한 스레드만). 기다리지 않는다.
  void write(const T& value) {
    std::uint64_t tmp[kWords] = {0};
    std::memcpy(tmp, &value, sizeof(T));
    std::uint64_t s = seq_.load(std::memory_order_relaxed);
    seq_.store(s + 1, std::memory_order_relaxed);         // 홀수 = 쓰는 중
    std::atomic_thread_fence(std::memory_order_release);  // 위의 "홀수"가 아래 데이터보다 먼저 보이게
    for (std::size_t i = 0; i < kWords; ++i) {
      words_[i].store(tmp[i], std::memory_order_relaxed);
    }
    seq_.store(s + 2, std::memory_order_release);         // 짝수 = 다 씀. 데이터가 이것보다 먼저 보인다
  }

  // 읽는 쪽 (몇 개든). 쓰는 도중이었으면 false — 다시 부르면 된다.
  bool try_read(T& out, std::uint64_t* seq_out = nullptr) const {
    std::uint64_t s1 = seq_.load(std::memory_order_acquire);
    if (s1 & 1) {
      return false;
    }
    std::uint64_t tmp[kWords];
    for (std::size_t i = 0; i < kWords; ++i) {
      tmp[i] = words_[i].load(std::memory_order_relaxed);
    }
    std::atomic_thread_fence(std::memory_order_acquire);  // 위의 데이터 읽기가 아래 번호 읽기보다 먼저 끝나게
    std::uint64_t s2 = seq_.load(std::memory_order_relaxed);
    if (s1 != s2) {
      return false;  // 읽는 동안 새로 쓰였다 — 섞였을 수 있으므로 버린다
    }
    std::memcpy(&out, tmp, sizeof(T));
    if (seq_out != nullptr) {
      *seq_out = s1;
    }
    return true;
  }

  // 성공할 때까지 최대 max_tries 번. 쓰는 쪽이 1 kHz 면 한 번 쓰는 데 수 µs 라 보통 첫 번째에 된다.
  bool read(T& out, int max_tries = 1000, std::uint64_t* seq_out = nullptr) const {
    for (int i = 0; i < max_tries; ++i) {
      if (try_read(out, seq_out)) {
        return true;
      }
    }
    return false;
  }

  // 지금까지 몇 번 썼나 (seq / 2). 0 이면 아직 한 번도 안 씀
  std::uint64_t writes() const { return seq_.load(std::memory_order_acquire) / 2; }

 private:
  alignas(64) std::atomic<std::uint64_t> seq_{0};
  alignas(64) std::atomic<std::uint64_t> words_[kWords] = {};
};

// ---------------------------------------------------------------------------
// 2) 공유 메모리 맨 앞의 형식 표시. 읽는 쪽은 magic·version·크기가 같을 때만 쓴다
//    (노드를 새 버전으로 바꿨는데 옛 도구가 옛 형식으로 읽는 일을 막는다)
// ---------------------------------------------------------------------------
struct ShmHeader {
  std::uint32_t magic = 0x31534852u;   // 'R' 'H' 'S' '1'
  std::uint32_t version = 1;
  std::uint64_t payload_size = 0;      // sizeof(T)
  std::int64_t writer_pid = 0;         // 쓰는 프로세스 (살아 있는지 확인용)
  std::int64_t period_ns = 0;          // 쓰는 주기 (읽는 쪽이 "멈췄나"를 판단하는 기준)
};

template <typename T>
struct ShmLayout {
  ShmHeader header;
  SeqlockBlock<T> block;
};

// ---------------------------------------------------------------------------
// 3) 공유 메모리 한 덩어리. create 는 쓰는 쪽, open 은 읽는 쪽.
//    이름은 "/rt_state" 처럼 / 로 시작한다 → 리눅스에서는 /dev/shm/rt_state 파일로 보인다.
// ---------------------------------------------------------------------------
template <typename T>
class ShmSegment {
 public:
  ShmSegment() {}
  ~ShmSegment() { close(); }
  ShmSegment(const ShmSegment&) = delete;
  ShmSegment& operator=(const ShmSegment&) = delete;

  // 쓰는 쪽: 만들고(있으면 덮어씀) 0 으로 채운 뒤 형식 표시를 쓴다. 실패하면 false, errno 는 error()
  bool create(const std::string& name, std::int64_t period_ns) {
    int fd = ::shm_open(name.c_str(), O_CREAT | O_RDWR, 0644);
    if (fd < 0) {
      return fail();
    }
    if (::ftruncate(fd, static_cast<off_t>(sizeof(ShmLayout<T>))) != 0) {
      ::close(fd);
      return fail();
    }
    if (!map(fd, PROT_READ | PROT_WRITE)) {
      return false;
    }
    layout_ = new (mem_) ShmLayout<T>();  // 새 객체를 그 자리에 (atomic 들을 0 으로)
    layout_->header.payload_size = sizeof(T);
    layout_->header.writer_pid = static_cast<std::int64_t>(::getpid());
    layout_->header.period_ns = period_ns;
    name_ = name;
    owner_ = true;
    return true;
  }

  // 읽는 쪽: 열고 형식을 확인한다. 형식이 다르면 false (error() == EPROTO)
  bool open(const std::string& name) {
    int fd = ::shm_open(name.c_str(), O_RDONLY, 0);
    if (fd < 0) {
      return fail();
    }
    struct stat st;
    if (::fstat(fd, &st) != 0 || static_cast<std::size_t>(st.st_size) < sizeof(ShmLayout<T>)) {
      ::close(fd);
      errno_ = EPROTO;
      return false;
    }
    if (!map(fd, PROT_READ)) {
      return false;
    }
    layout_ = static_cast<ShmLayout<T>*>(mem_);
    const ShmHeader& h = layout_->header;
    ShmHeader expected;
    if (h.magic != expected.magic || h.version != expected.version || h.payload_size != sizeof(T)) {
      close();
      errno_ = EPROTO;
      return false;
    }
    name_ = name;
    return true;
  }

  // 쓰는 쪽이 닫으면 이름도 지운다 (남은 읽는 쪽은 매핑이 풀릴 때까지 마지막 내용을 본다)
  void close() {
    if (mem_ != nullptr) {
      ::munmap(mem_, sizeof(ShmLayout<T>));
      mem_ = nullptr;
      layout_ = nullptr;
    }
    if (owner_ && !name_.empty()) {
      ::shm_unlink(name_.c_str());
    }
    owner_ = false;
  }

  void write(const T& value) { layout_->block.write(value); }
  bool read(T& out, int max_tries = 1000, std::uint64_t* seq_out = nullptr) const {
    return layout_->block.read(out, max_tries, seq_out);
  }
  const ShmHeader& header() const { return layout_->header; }
  std::uint64_t writes() const { return layout_->block.writes(); }
  int error() const { return errno_; }

 private:
  bool map(int fd, int prot) {
    void* p = ::mmap(nullptr, sizeof(ShmLayout<T>), prot, MAP_SHARED, fd, 0);
    ::close(fd);  // 매핑이 살아 있는 동안 fd 는 필요 없다
    if (p == MAP_FAILED) {
      return fail();
    }
    mem_ = p;
    return true;
  }

  bool fail() {
    errno_ = errno;
    return false;
  }

  void* mem_ = nullptr;
  ShmLayout<T>* layout_ = nullptr;
  std::string name_;
  bool owner_ = false;
  int errno_ = 0;
};

}  // namespace rt_core
