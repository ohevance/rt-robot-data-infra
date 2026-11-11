#pragma once
// ===========================================================================
// 파일 역할 : 로봇 ↔ 상위 SW 사이의 "통신 패킷" 형식 (ZeroMQ 위에 싣는 바이트 배열). 인코딩·디코딩만 한다 — 소켓은 모른다.
//
//   [ 머리 24바이트 ][ 본문 payload_len 바이트 ]
//     magic u32 "RTW1" · version u16 · type u16 · seq u32 · payload_len u32 · stamp_ns i64
//   모든 정수·실수는 리틀엔디언. 실수는 IEEE-754 double. (Python SDK 의 rtsdk/wire.py 가 같은 형식을 struct 로 읽는다)
//
//   type      방향            본문
//   STATE     로봇 → 구독자   iter u64 · rt_stamp_ns i64 · wake_lat_ns i64 · cmd_seq u32 · dof u16 · robot_state u8 · watchdog u8
//                             · position[dof] · velocity[dof] · target[dof]  (double)
//   TARGET    클라이언트 → 로봇  dof u16 · 0 u16 · position[dof] (double)
//   ACK       로봇 → 클라이언트  acked_seq u32 · status u16 · 0 u16
//   PING/PONG 왕복 시간 재기     본문 없음 (PONG 은 PING 의 seq 와 stamp_ns 를 그대로 돌려준다)
//   GET_INFO / INFO              INFO 본문은 UTF-8 JSON (관절 수·주기·백엔드 — 사람이 읽고, 자주 오가지 않는다)
//
// 왜 이 모양인가 (DECISIONS 11/11)
//   - 고정 머리 + 길이: 받는 쪽이 본문을 읽기 전에 "내가 아는 형식인가, 잘린 것인가"를 판정한다. magic·version 이 다르면 거절.
//   - JSON·protobuf 를 쓰지 않는 이유: 상태는 1 kHz 까지 오간다. 할당 없이 고정 버퍼에 쓰고 읽어야 하고(RT 쪽과 같은 규칙),
//     형식이 이 파일 한 장에 다 보여야 C++·Python 두 구현이 어긋나지 않는다. INFO 만 JSON — 드물고 사람이 읽는다.
//   - seq: 명령마다 번호를 붙이고, 로봇은 "마지막으로 반영한 명령 번호"(cmd_seq)를 상태에 실어 돌려준다
//     → 클라이언트가 "내 명령이 실시간 루프에 들어가 상태로 돌아오기까지" 시간을 직접 잰다.
//
// 규칙: 할당·예외 없음. 디코딩 실패는 WireError 로 돌려준다 (잘못된 패킷 하나가 노드를 죽이지 않게).
// ===========================================================================
#include <cstddef>
#include <cstdint>

#include "rt_core/joint_types.hpp"

namespace rt_core {
namespace wire {

const std::uint32_t kMagic = 0x31575452u;  // 바이트 순서로 'R' 'T' 'W' '1'
const std::uint16_t kVersion = 1;
const std::size_t kHeaderSize = 24;

enum class MsgType : std::uint16_t {
  STATE = 1,
  TARGET = 2,
  ACK = 3,
  PING = 4,
  PONG = 5,
  GET_INFO = 6,
  INFO = 7,
};

// ACK 의 status
enum class AckStatus : std::uint16_t {
  OK = 0,
  BAD_DOF = 1,       // 관절 수가 로봇과 다르다
  RING_FULL = 2,     // RT 스레드가 명령 우편함을 비우지 못하고 있다 (정상이면 0)
  BAD_PACKET = 3,    // 형식 오류 (magic·version·길이)
  UNKNOWN_TYPE = 4,  // 이 노드가 받지 않는 type
  BAD_VALUE = 5,     // NaN·무한대가 들어 있다
};

enum class WireError {
  OK = 0,
  TOO_SHORT,        // 머리 24바이트도 안 된다
  BAD_MAGIC,
  BAD_VERSION,
  LENGTH_MISMATCH,  // payload_len 과 실제 길이가 다르다
  BAD_DOF,          // 본문의 dof 가 0 이거나 kMaxJoints 를 넘거나, 본문 길이와 맞지 않는다
  WRONG_TYPE,       // 이 디코더가 기대한 type 이 아니다
};

const char* wire_error_name(WireError e);

struct Header {
  std::uint16_t version = kVersion;
  MsgType type = MsgType::PING;
  std::uint32_t seq = 0;
  std::uint32_t payload_len = 0;
  std::int64_t stamp_ns = 0;
};

// STATE 의 크기: 머리 + 고정 32바이트 + dof × 3 × 8
std::size_t state_size(std::uint32_t dof);
std::size_t target_size(std::uint32_t dof);
const std::size_t kAckSize = kHeaderSize + 8;
// 가장 큰 패킷 (STATE, 관절 kMaxJoints 개). 버퍼를 이만큼 잡으면 어떤 패킷도 들어간다
const std::size_t kMaxPacket = kHeaderSize + 32 + kMaxJoints * 3 * 8;

// ---- 쓰기: 버퍼에 쓰고 쓴 바이트 수를 돌려준다. 버퍼가 작으면 0 ----
std::size_t encode_header(std::uint8_t* buf, std::size_t cap, const Header& h);
std::size_t encode_state(std::uint8_t* buf, std::size_t cap, std::uint32_t seq, std::int64_t stamp_ns,
                         const JointStateSample& s);
std::size_t encode_target(std::uint8_t* buf, std::size_t cap, std::uint32_t seq, std::int64_t stamp_ns,
                          const double* position, std::uint32_t dof);
std::size_t encode_ack(std::uint8_t* buf, std::size_t cap, std::uint32_t seq, std::int64_t stamp_ns,
                       std::uint32_t acked_seq, AckStatus status);
// 본문 없는 패킷 (PING, PONG, GET_INFO) 또는 본문이 바이트열인 패킷 (INFO)
std::size_t encode_simple(std::uint8_t* buf, std::size_t cap, MsgType type, std::uint32_t seq, std::int64_t stamp_ns,
                          const std::uint8_t* body = nullptr, std::size_t body_len = 0);

// ---- 읽기 ----
WireError decode_header(const std::uint8_t* buf, std::size_t len, Header& out);
// TARGET 의 본문을 JointCommand 로 (seq·stamp 는 머리에서). position 에 NaN·무한대가 있으면 bad_value = true
WireError decode_target(const std::uint8_t* buf, std::size_t len, Header& h, JointCommand& out, bool& bad_value);
WireError decode_state(const std::uint8_t* buf, std::size_t len, Header& h, JointStateSample& out);
WireError decode_ack(const std::uint8_t* buf, std::size_t len, Header& h, std::uint32_t& acked_seq, AckStatus& status);

}  // namespace wire
}  // namespace rt_core
