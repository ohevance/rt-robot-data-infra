"""통신 패킷 — C++ 쪽 rt_control/rt_core/include/rt_core/wire.hpp 와 같은 형식을 struct 로 읽고 쓴다.

    [ 머리 24바이트 ][ 본문 ]   전부 리틀엔디언("<"), 실수는 double
    머리: magic u32 "RTW1" · version u16 · type u16 · seq u32 · payload_len u32 · stamp_ns i64

형식의 진짜 정의는 wire.hpp 머리말의 표 하나다. 이 파일은 그것을 옮긴 것이고, 두 구현이 같은지는 시험 두 개가 같은
바이트(골든)를 기대하는 것으로 확인한다 — rt_core/test/test_wire.cpp 와 sdk/python/tests/test_wire.py.

이 파일은 소켓을 모른다 (pyzmq 없이 import 된다).
"""
import json
import math
import struct
from dataclasses import dataclass, field
from typing import List

MAGIC = 0x31575452  # 바이트 순서로 b"RTW1"
VERSION = 1
HEADER = struct.Struct("<IHHIIq")  # 24바이트
STATE_FIXED = struct.Struct("<QqqIHBB")  # iter · rt_stamp_ns · wake_lat_ns · cmd_seq · dof · robot_state · watchdog (32바이트)
TARGET_FIXED = struct.Struct("<HH")  # dof · 0
ACK_BODY = struct.Struct("<IHH")  # acked_seq · status · 0
MAX_JOINTS = 64

# type
STATE, TARGET, ACK, PING, PONG, GET_INFO, INFO = 1, 2, 3, 4, 5, 6, 7

# ACK status — wire.hpp 의 AckStatus 와 같은 번호
ACK_STATUS = {0: "ok", 1: "bad_dof", 2: "ring_full", 3: "bad_packet", 4: "unknown_type", 5: "bad_value"}

# 로봇 상태 머신 — robot_state_machine.hpp 의 RobotState
ROBOT_STATES = {0: "INIT", 1: "READY", 2: "RUNNING", 3: "FAULT", 4: "RECOVERING"}


class WireError(ValueError):
    """형식이 맞지 않는 패킷. 받는 쪽은 버리고 센다 (예외를 밖으로 던져 클라이언트를 죽이지 않는다)."""


@dataclass
class Header:
    type: int
    seq: int
    stamp_ns: int
    payload_len: int


@dataclass
class State:
    seq: int  # 노드가 STATE 에 붙인 번호 (구독자가 빠진 것을 센다)
    sent_ns: int  # 노드가 보낸 시각 (노드의 단조 시계 — 같은 PC 일 때만 내 시계와 비교할 수 있다)
    iter: int  # RT 루프의 주기 번호
    rt_stamp_ns: int  # RT 루프가 이 상태를 읽은 시각 (노드의 단조 시계)
    wake_lat_ns: int
    cmd_seq: int  # 이 주기까지 반영된 마지막 명령의 번호
    robot_state: str
    watchdog_tripped: bool
    position: List[float] = field(default_factory=list)
    velocity: List[float] = field(default_factory=list)
    target: List[float] = field(default_factory=list)


def _header(data: bytes) -> Header:
    if len(data) < HEADER.size:
        raise WireError("too_short")
    magic, version, mtype, seq, payload_len, stamp = HEADER.unpack_from(data, 0)
    if magic != MAGIC:
        raise WireError("bad_magic")
    if version != VERSION:
        raise WireError("bad_version")
    if payload_len != len(data) - HEADER.size:
        raise WireError("length_mismatch")
    return Header(mtype, seq, stamp, payload_len)


def decode_header(data: bytes) -> Header:
    return _header(data)


def encode(mtype: int, seq: int, stamp_ns: int, body: bytes = b"") -> bytes:
    return HEADER.pack(MAGIC, VERSION, mtype, seq & 0xFFFFFFFF, len(body), stamp_ns) + body


def encode_target(seq: int, stamp_ns: int, position) -> bytes:
    pos = [float(x) for x in position]
    if not 0 < len(pos) <= MAX_JOINTS:
        raise WireError("bad_dof")
    body = TARGET_FIXED.pack(len(pos), 0) + struct.pack(f"<{len(pos)}d", *pos)
    return encode(TARGET, seq, stamp_ns, body)


def decode_state(data: bytes) -> State:
    h = _header(data)
    if h.type != STATE:
        raise WireError("wrong_type")
    if h.payload_len < STATE_FIXED.size:
        raise WireError("bad_dof")
    it, rt_stamp, wake, cmd_seq, dof, rstate, wd = STATE_FIXED.unpack_from(data, HEADER.size)
    if dof > MAX_JOINTS or len(data) != HEADER.size + STATE_FIXED.size + dof * 24:
        raise WireError("bad_dof")
    vals = struct.unpack_from(f"<{3 * dof}d", data, HEADER.size + STATE_FIXED.size)
    return State(h.seq, h.stamp_ns, it, rt_stamp, wake, cmd_seq, ROBOT_STATES.get(rstate, str(rstate)), bool(wd),
                 list(vals[:dof]), list(vals[dof:2 * dof]), list(vals[2 * dof:]))


def decode_ack(data: bytes):
    """→ (header, acked_seq, status 이름)"""
    h = _header(data)
    if h.type != ACK:
        raise WireError("wrong_type")
    if h.payload_len != ACK_BODY.size:
        raise WireError("length_mismatch")
    acked, status, _ = ACK_BODY.unpack_from(data, HEADER.size)
    return h, acked, ACK_STATUS.get(status, str(status))


def decode_info(data: bytes) -> dict:
    h = _header(data)
    if h.type != INFO:
        raise WireError("wrong_type")
    return json.loads(data[HEADER.size:].decode("utf-8"))


def check_finite(position) -> None:
    """NaN·무한대는 보내기 전에 막는다 (노드도 막지만 — BAD_VALUE — 내 쪽에서 먼저 알린다)."""
    for x in position:
        if not math.isfinite(float(x)):
            raise WireError("bad_value")
