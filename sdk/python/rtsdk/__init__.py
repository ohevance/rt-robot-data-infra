"""rtsdk — rt_zmq_node(ZeroMQ 로 감싼 실시간 제어 노드)의 Python SDK.

    RobotClient : 상태 받기(SUB) · 목표 보내기 · ping · info (DEALER)
    wire        : 통신 패킷 (C++ rt_core/wire.hpp 와 같은 형식). pyzmq 없이도 import 된다

읽는 순서: wire.py → client.py → bench.py (측정) → ../examples/follow_sine.py (쓰는 예)
"""
from . import wire

__all__ = ["wire", "RobotClient", "CommandRejected"]
__version__ = "0.1.0"


def __getattr__(name):
    # client 는 pyzmq 가 있어야 한다 — wire 만 쓰는 곳(형식 시험)이 pyzmq 없이 돌도록 늦게 가져온다
    if name in ("RobotClient", "CommandRejected"):
        from . import client
        return getattr(client, name)
    raise AttributeError(name)
