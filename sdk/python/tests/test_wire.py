"""통신 패킷(rtsdk/wire.py) 시험 — pyzmq 없이 돈다.

  1) 골든 바이트: C++ 시험(rt_control/rt_core/test/test_wire.cpp 의 test_golden_target)과 같은 바이트를 만들고 읽는다.
     두 구현이 같은 형식이라는 증거. 형식을 바꾸면 양쪽 골든을 같이 바꾼다.
  2) STATE 를 손으로 만들어 읽기 (C++ encode_state 와 같은 자리)
  3) 거절: 짧음 · magic · version · 길이 · dof · NaN

실행: python3 sdk/python/tests/test_wire.py
"""
import math
import os
import struct
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
from rtsdk import wire  # noqa: E402

GOLDEN_TARGET = bytes([
    0x52, 0x54, 0x57, 0x31, 0x01, 0x00, 0x02, 0x00, 0x04, 0x03, 0x02, 0x01, 0x14, 0x00, 0x00, 0x00,
    0x88, 0x77, 0x66, 0x55, 0x44, 0x33, 0x22, 0x11, 0x02, 0x00, 0x00, 0x00,
    0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0xF0, 0x3F, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0xE0, 0xBF,
])


def test_golden_target():
    b = wire.encode_target(0x01020304, 0x1122334455667788, [1.0, -0.5])
    assert b == GOLDEN_TARGET, b.hex()


def test_state_decode():
    dof = 3
    body = wire.STATE_FIXED.pack(77, 1000, 15000, 9, dof, 3, 1) + struct.pack("<9d", 0.1, 0.2, 0.3, 1, 2, 3, -1, -2, -3)
    b = wire.encode(wire.STATE, 5, 123, body)
    s = wire.decode_state(b)
    assert (s.seq, s.sent_ns, s.iter, s.rt_stamp_ns, s.wake_lat_ns, s.cmd_seq) == (5, 123, 77, 1000, 15000, 9)
    assert s.robot_state == "FAULT" and s.watchdog_tripped
    assert s.position == [0.1, 0.2, 0.3] and s.velocity == [1, 2, 3] and s.target == [-1, -2, -3]


def test_ack_decode():
    b = wire.encode(wire.ACK, 9, 5, wire.ACK_BODY.pack(41, 1, 0))
    h, acked, status = wire.decode_ack(b)
    assert (h.seq, acked, status) == (9, 41, "bad_dof")


def expect_error(data, name, decoder=wire.decode_state):
    try:
        decoder(data)
    except wire.WireError as e:
        assert str(e) == name, (str(e), name)
        return
    raise AssertionError(f"{name} 를 기대했는데 통과함")


def test_rejects():
    good = wire.encode_target(1, 2, [0.1, 0.2, 0.3])
    expect_error(good[:10], "too_short", wire.decode_header)
    expect_error(b"X" + good[1:], "bad_magic", wire.decode_header)
    expect_error(good[:4] + b"\x02\x00" + good[6:], "bad_version", wire.decode_header)
    expect_error(good[:-8], "length_mismatch", wire.decode_header)
    expect_error(good, "wrong_type", wire.decode_state)
    for bad in ([], [0.0] * 65):
        try:
            wire.encode_target(1, 2, bad)
            raise AssertionError("dof 0 / 65 를 받아들임")
        except wire.WireError as e:
            assert str(e) == "bad_dof"
    try:
        wire.check_finite([0.0, math.nan])
        raise AssertionError("NaN 을 받아들임")
    except wire.WireError as e:
        assert str(e) == "bad_value"


def main():
    test_golden_target()
    test_state_decode()
    test_ack_decode()
    test_rejects()
    print("OK: rtsdk wire (골든 바이트 = C++ 과 같음 · STATE · ACK · 거절)")


if __name__ == "__main__":
    main()
