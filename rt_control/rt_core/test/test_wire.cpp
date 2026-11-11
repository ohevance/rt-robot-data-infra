// ===========================================================================
// 파일 역할 : 통신 패킷(wire.hpp) 시험. 소켓 없이 바이트만 본다.
//   1) STATE·TARGET·ACK 를 쓰고 다시 읽으면 같은 값 (왕복)
//   2) 고정 바이트(골든) — Python SDK 의 시험(sdk/python/tests/test_wire.py)이 같은 바이트를 기대한다.
//      두 언어가 같은 형식을 쓰고 있다는 증거. 형식을 바꾸면 양쪽 골든을 같이 바꿔야 한다.
//   3) 잘못된 패킷은 전부 거절된다: 짧음 · magic · version · 길이 · dof 0 / 초과 · 다른 type · NaN
// 실행: ctest 의 wire (또는 ./test_wire). 실패하면 어느 줄인지 찍고 종료 코드 1
// ===========================================================================
#include <cmath>
#include <cstdio>
#include <cstring>
#include <limits>

#include "rt_core/wire.hpp"

using namespace rt_core;
using namespace rt_core::wire;

static int g_fail = 0;
#define CHECK(cond)                                              \
  do {                                                           \
    if (!(cond)) {                                               \
      std::printf("FAIL %s:%d  %s\n", __FILE__, __LINE__, #cond); \
      g_fail = g_fail + 1;                                       \
    }                                                            \
  } while (0)

static void test_state_roundtrip() {
  JointStateSample s;
  s.iter = 123456789012ULL;
  s.stamp_ns = 987654321;
  s.wake_lat_ns = 15000;
  s.cmd_seq = 42;
  s.dof = 6;
  s.robot_state = 2;
  s.watchdog_tripped = true;
  for (std::uint32_t j = 0; j < 6; ++j) {
    s.position[j] = 0.1 * j - 0.25;
    s.velocity[j] = -1.5 * j;
    s.target[j] = 3.0 + j;
  }
  std::uint8_t buf[kMaxPacket];
  std::size_t n = encode_state(buf, sizeof(buf), 7, 1111, s);
  CHECK(n == state_size(6));
  CHECK(n == 24 + 32 + 6 * 24);

  Header h;
  JointStateSample r;
  CHECK(decode_state(buf, n, h, r) == WireError::OK);
  CHECK(h.type == MsgType::STATE && h.seq == 7 && h.stamp_ns == 1111);
  CHECK(r.iter == s.iter && r.stamp_ns == s.stamp_ns && r.wake_lat_ns == s.wake_lat_ns);
  CHECK(r.cmd_seq == 42 && r.dof == 6 && r.robot_state == 2 && r.watchdog_tripped);
  for (std::uint32_t j = 0; j < 6; ++j) {
    CHECK(r.position[j] == s.position[j] && r.velocity[j] == s.velocity[j] && r.target[j] == s.target[j]);
  }
  CHECK(encode_state(buf, n - 1, 7, 1111, s) == 0);  // 버퍼가 한 바이트 모자라면 쓰지 않는다
}

static void test_golden_target() {
  // dof 2, 위치 1.0 과 -0.5, seq 0x01020304, stamp 0x1122334455667788
  const double pos[2] = {1.0, -0.5};
  std::uint8_t buf[64];
  std::size_t n = encode_target(buf, sizeof(buf), 0x01020304u, 0x1122334455667788LL, pos, 2);
  const std::uint8_t golden[] = {
      0x52, 0x54, 0x57, 0x31,  // "RTW1"
      0x01, 0x00,              // version 1
      0x02, 0x00,              // type TARGET
      0x04, 0x03, 0x02, 0x01,  // seq (리틀엔디언)
      0x14, 0x00, 0x00, 0x00,  // payload_len 20 = 4 + 2 × 8
      0x88, 0x77, 0x66, 0x55, 0x44, 0x33, 0x22, 0x11,  // stamp_ns
      0x02, 0x00, 0x00, 0x00,                          // dof 2, 0
      0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0xF0, 0x3F,  // 1.0
      0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0xE0, 0xBF,  // -0.5
  };
  CHECK(n == sizeof(golden));
  CHECK(std::memcmp(buf, golden, sizeof(golden)) == 0);

  Header h;
  JointCommand c;
  bool bad = true;
  CHECK(decode_target(golden, sizeof(golden), h, c, bad) == WireError::OK);
  CHECK(!bad && c.dof == 2 && c.seq == 0x01020304u && c.position[0] == 1.0 && c.position[1] == -0.5);
}

static void test_ack_roundtrip() {
  std::uint8_t buf[64];
  std::size_t n = encode_ack(buf, sizeof(buf), 9, 5, 41, AckStatus::BAD_DOF);
  CHECK(n == kAckSize);
  Header h;
  std::uint32_t acked = 0;
  AckStatus st = AckStatus::OK;
  CHECK(decode_ack(buf, n, h, acked, st) == WireError::OK);
  CHECK(h.seq == 9 && acked == 41 && st == AckStatus::BAD_DOF);
}

static void test_rejects() {
  const double pos[3] = {0.1, 0.2, 0.3};
  std::uint8_t good[128];
  std::size_t n = encode_target(good, sizeof(good), 1, 2, pos, 3);
  std::uint8_t b[128];
  Header h;
  JointCommand c;
  bool bad = false;

  CHECK(decode_target(good, 10, h, c, bad) == WireError::TOO_SHORT);

  std::memcpy(b, good, n);
  b[0] = 'X';
  CHECK(decode_target(b, n, h, c, bad) == WireError::BAD_MAGIC);

  std::memcpy(b, good, n);
  b[4] = 2;  // version 2
  CHECK(decode_target(b, n, h, c, bad) == WireError::BAD_VERSION);

  CHECK(decode_target(good, n - 8, h, c, bad) == WireError::LENGTH_MISMATCH);  // 끝이 잘림

  std::memcpy(b, good, n);
  b[24] = 0;  // dof 0
  CHECK(decode_target(b, n, h, c, bad) == WireError::BAD_DOF);

  std::memcpy(b, good, n);
  b[24] = 4;  // dof 4 인데 본문은 3개 분량
  CHECK(decode_target(b, n, h, c, bad) == WireError::BAD_DOF);

  std::uint8_t big[kMaxPacket + 64];
  double many[kMaxJoints + 1] = {0.0};
  CHECK(encode_target(big, sizeof(big), 1, 2, many, kMaxJoints + 1) == 0);  // 64 를 넘는 dof 는 쓰지도 않는다

  std::uint8_t ping[32];
  std::size_t pn = encode_simple(ping, sizeof(ping), MsgType::PING, 1, 2);
  CHECK(decode_target(ping, pn, h, c, bad) == WireError::WRONG_TYPE);

  const double nan_pos[3] = {0.1, std::numeric_limits<double>::quiet_NaN(), 0.3};
  std::size_t nn = encode_target(b, sizeof(b), 1, 2, nan_pos, 3);
  CHECK(decode_target(b, nn, h, c, bad) == WireError::OK);
  CHECK(bad);  // 형식은 맞지만 값이 NaN → 노드가 BAD_VALUE 로 거절한다
}

int main() {
  test_state_roundtrip();
  test_golden_target();
  test_ack_roundtrip();
  test_rejects();
  if (g_fail != 0) {
    std::printf("wire: %d 실패\n", g_fail);
    return 1;
  }
  std::printf("OK: wire (왕복 · 골든 바이트 · 거절 9가지)\n");
  return 0;
}
