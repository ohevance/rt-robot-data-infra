// ===========================================================================
// 파일 역할 : wire.hpp 의 구현. 형식 표는 wire.hpp 머리말에 있다.
// 읽는 순서 : put/get (리틀엔디언 한 칸) → encode_header → encode_state → decode_header → decode_target
//
// 바이트를 한 칸씩 옮기는 이유: 구조체를 memcpy 로 통째로 보내면 컴파일러의 빈칸(padding)과 CPU 의 바이트 순서가
// 그대로 실려 간다. 받는 쪽이 Python 이거나 다른 CPU 면 어긋난다. 한 칸씩 쓰면 형식이 코드에 그대로 보인다.
// ===========================================================================
#include "rt_core/wire.hpp"

#include <cmath>
#include <cstring>

namespace rt_core {
namespace wire {

namespace {

void put_u16(std::uint8_t* p, std::uint16_t v) {
  p[0] = static_cast<std::uint8_t>(v);
  p[1] = static_cast<std::uint8_t>(v >> 8);
}

void put_u32(std::uint8_t* p, std::uint32_t v) {
  for (int i = 0; i < 4; ++i) {
    p[i] = static_cast<std::uint8_t>(v >> (8 * i));
  }
}

void put_u64(std::uint8_t* p, std::uint64_t v) {
  for (int i = 0; i < 8; ++i) {
    p[i] = static_cast<std::uint8_t>(v >> (8 * i));
  }
}

void put_f64(std::uint8_t* p, double v) {
  std::uint64_t bits = 0;
  std::memcpy(&bits, &v, sizeof(bits));  // double 의 비트를 그대로 정수로 (값을 바꾸지 않는다)
  put_u64(p, bits);
}

std::uint16_t get_u16(const std::uint8_t* p) {
  return static_cast<std::uint16_t>(p[0] | (p[1] << 8));
}

std::uint32_t get_u32(const std::uint8_t* p) {
  std::uint32_t v = 0;
  for (int i = 0; i < 4; ++i) {
    v |= static_cast<std::uint32_t>(p[i]) << (8 * i);
  }
  return v;
}

std::uint64_t get_u64(const std::uint8_t* p) {
  std::uint64_t v = 0;
  for (int i = 0; i < 8; ++i) {
    v |= static_cast<std::uint64_t>(p[i]) << (8 * i);
  }
  return v;
}

double get_f64(const std::uint8_t* p) {
  std::uint64_t bits = get_u64(p);
  double v = 0.0;
  std::memcpy(&v, &bits, sizeof(v));
  return v;
}

const std::size_t kStateFixed = 32;   // iter 8 · rt_stamp 8 · wake_lat 8 · cmd_seq 4 · dof 2 · robot_state 1 · watchdog 1
const std::size_t kTargetFixed = 4;   // dof 2 · 0 2

}  // namespace

const char* wire_error_name(WireError e) {
  switch (e) {
    case WireError::OK: return "ok";
    case WireError::TOO_SHORT: return "too_short";
    case WireError::BAD_MAGIC: return "bad_magic";
    case WireError::BAD_VERSION: return "bad_version";
    case WireError::LENGTH_MISMATCH: return "length_mismatch";
    case WireError::BAD_DOF: return "bad_dof";
    case WireError::WRONG_TYPE: return "wrong_type";
  }
  return "unknown";
}

std::size_t state_size(std::uint32_t dof) { return kHeaderSize + kStateFixed + dof * 3 * 8; }
std::size_t target_size(std::uint32_t dof) { return kHeaderSize + kTargetFixed + dof * 8; }

std::size_t encode_header(std::uint8_t* buf, std::size_t cap, const Header& h) {
  if (cap < kHeaderSize) {
    return 0;
  }
  put_u32(buf + 0, kMagic);
  put_u16(buf + 4, h.version);
  put_u16(buf + 6, static_cast<std::uint16_t>(h.type));
  put_u32(buf + 8, h.seq);
  put_u32(buf + 12, h.payload_len);
  put_u64(buf + 16, static_cast<std::uint64_t>(h.stamp_ns));
  return kHeaderSize;
}

std::size_t encode_state(std::uint8_t* buf, std::size_t cap, std::uint32_t seq, std::int64_t stamp_ns,
                         const JointStateSample& s) {
  std::uint32_t dof = s.dof;
  if (dof > kMaxJoints || cap < state_size(dof)) {
    return 0;
  }
  Header h;
  h.type = MsgType::STATE;
  h.seq = seq;
  h.stamp_ns = stamp_ns;
  h.payload_len = static_cast<std::uint32_t>(state_size(dof) - kHeaderSize);
  encode_header(buf, cap, h);
  std::uint8_t* p = buf + kHeaderSize;
  put_u64(p + 0, s.iter);
  put_u64(p + 8, static_cast<std::uint64_t>(s.stamp_ns));
  put_u64(p + 16, static_cast<std::uint64_t>(s.wake_lat_ns));
  put_u32(p + 24, s.cmd_seq);
  put_u16(p + 28, static_cast<std::uint16_t>(dof));
  p[30] = s.robot_state;
  p[31] = s.watchdog_tripped ? 1 : 0;
  p += kStateFixed;
  for (std::uint32_t j = 0; j < dof; ++j) {
    put_f64(p + 8 * j, s.position[j]);
    put_f64(p + 8 * (dof + j), s.velocity[j]);
    put_f64(p + 8 * (2 * dof + j), s.target[j]);
  }
  return state_size(dof);
}

std::size_t encode_target(std::uint8_t* buf, std::size_t cap, std::uint32_t seq, std::int64_t stamp_ns,
                          const double* position, std::uint32_t dof) {
  if (dof > kMaxJoints || cap < target_size(dof)) {
    return 0;
  }
  Header h;
  h.type = MsgType::TARGET;
  h.seq = seq;
  h.stamp_ns = stamp_ns;
  h.payload_len = static_cast<std::uint32_t>(target_size(dof) - kHeaderSize);
  encode_header(buf, cap, h);
  std::uint8_t* p = buf + kHeaderSize;
  put_u16(p + 0, static_cast<std::uint16_t>(dof));
  put_u16(p + 2, 0);
  for (std::uint32_t j = 0; j < dof; ++j) {
    put_f64(p + kTargetFixed + 8 * j, position[j]);
  }
  return target_size(dof);
}

std::size_t encode_ack(std::uint8_t* buf, std::size_t cap, std::uint32_t seq, std::int64_t stamp_ns,
                       std::uint32_t acked_seq, AckStatus status) {
  if (cap < kAckSize) {
    return 0;
  }
  Header h;
  h.type = MsgType::ACK;
  h.seq = seq;
  h.stamp_ns = stamp_ns;
  h.payload_len = 8;
  encode_header(buf, cap, h);
  put_u32(buf + kHeaderSize, acked_seq);
  put_u16(buf + kHeaderSize + 4, static_cast<std::uint16_t>(status));
  put_u16(buf + kHeaderSize + 6, 0);
  return kAckSize;
}

std::size_t encode_simple(std::uint8_t* buf, std::size_t cap, MsgType type, std::uint32_t seq, std::int64_t stamp_ns,
                          const std::uint8_t* body, std::size_t body_len) {
  if (cap < kHeaderSize + body_len) {
    return 0;
  }
  Header h;
  h.type = type;
  h.seq = seq;
  h.stamp_ns = stamp_ns;
  h.payload_len = static_cast<std::uint32_t>(body_len);
  encode_header(buf, cap, h);
  if (body_len > 0) {
    std::memcpy(buf + kHeaderSize, body, body_len);
  }
  return kHeaderSize + body_len;
}

WireError decode_header(const std::uint8_t* buf, std::size_t len, Header& out) {
  if (len < kHeaderSize) {
    return WireError::TOO_SHORT;
  }
  if (get_u32(buf + 0) != kMagic) {
    return WireError::BAD_MAGIC;
  }
  out.version = get_u16(buf + 4);
  if (out.version != kVersion) {
    return WireError::BAD_VERSION;
  }
  out.type = static_cast<MsgType>(get_u16(buf + 6));
  out.seq = get_u32(buf + 8);
  out.payload_len = get_u32(buf + 12);
  out.stamp_ns = static_cast<std::int64_t>(get_u64(buf + 16));
  if (static_cast<std::size_t>(out.payload_len) != len - kHeaderSize) {
    return WireError::LENGTH_MISMATCH;
  }
  return WireError::OK;
}

WireError decode_target(const std::uint8_t* buf, std::size_t len, Header& h, JointCommand& out, bool& bad_value) {
  bad_value = false;
  WireError e = decode_header(buf, len, h);
  if (e != WireError::OK) {
    return e;
  }
  if (h.type != MsgType::TARGET) {
    return WireError::WRONG_TYPE;
  }
  if (h.payload_len < kTargetFixed) {
    return WireError::BAD_DOF;
  }
  const std::uint8_t* p = buf + kHeaderSize;
  std::uint32_t dof = get_u16(p);
  if (dof == 0 || dof > kMaxJoints || len != target_size(dof)) {
    return WireError::BAD_DOF;
  }
  out.dof = dof;
  out.seq = h.seq;
  for (std::uint32_t j = 0; j < dof; ++j) {
    double v = get_f64(p + kTargetFixed + 8 * j);
    if (!std::isfinite(v)) {
      bad_value = true;  // NaN·무한대는 변화량 제한도 통과시킨다(NaN 비교는 늘 거짓) → 여기서 막는다
    }
    out.position[j] = v;
  }
  return WireError::OK;
}

WireError decode_state(const std::uint8_t* buf, std::size_t len, Header& h, JointStateSample& out) {
  WireError e = decode_header(buf, len, h);
  if (e != WireError::OK) {
    return e;
  }
  if (h.type != MsgType::STATE) {
    return WireError::WRONG_TYPE;
  }
  if (h.payload_len < kStateFixed) {
    return WireError::BAD_DOF;
  }
  const std::uint8_t* p = buf + kHeaderSize;
  std::uint32_t dof = get_u16(p + 28);
  if (dof > kMaxJoints || len != state_size(dof)) {
    return WireError::BAD_DOF;
  }
  out.iter = get_u64(p + 0);
  out.stamp_ns = static_cast<std::int64_t>(get_u64(p + 8));
  out.wake_lat_ns = static_cast<std::int64_t>(get_u64(p + 16));
  out.cmd_seq = get_u32(p + 24);
  out.dof = dof;
  out.robot_state = p[30];
  out.watchdog_tripped = p[31] != 0;
  p += kStateFixed;
  for (std::uint32_t j = 0; j < dof; ++j) {
    out.position[j] = get_f64(p + 8 * j);
    out.velocity[j] = get_f64(p + 8 * (dof + j));
    out.target[j] = get_f64(p + 8 * (2 * dof + j));
  }
  return WireError::OK;
}

WireError decode_ack(const std::uint8_t* buf, std::size_t len, Header& h, std::uint32_t& acked_seq, AckStatus& status) {
  WireError e = decode_header(buf, len, h);
  if (e != WireError::OK) {
    return e;
  }
  if (h.type != MsgType::ACK) {
    return WireError::WRONG_TYPE;
  }
  if (len != kAckSize) {
    return WireError::LENGTH_MISMATCH;
  }
  acked_seq = get_u32(buf + kHeaderSize);
  status = static_cast<AckStatus>(get_u16(buf + kHeaderSize + 4));
  return WireError::OK;
}

}  // namespace wire
}  // namespace rt_core
