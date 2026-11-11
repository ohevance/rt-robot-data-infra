"""느린 구독자 실험 (E24 7절): 노드의 상태(PUB)에 SUB 하나를 붙이고, --pause 초 동안 읽지 않다가 --drain 초 동안 다 읽는다.

받은 수 · 빈 번호 · 처음 받은 상태의 나이를 JSON 한 줄로 찍는다. 나이는 노드의 단조 시계와 빼므로 같은 PC 일 때만 뜻이 있다.
노드가 센 값(states_send_dropped)은 노드를 --status-json 으로 띄워 끝날 때 따로 본다.

  # [WSL 창] 노드를 띄워 두고
  ./build/zmq_adapter/rt_zmq_node --dof 6 --publish-hz 1000 --prio 0 --shm "" --status-json /tmp/st.json &
  PYTHONPATH=sdk/python python3 sdk/python/tools/slow_subscriber.py --pause 12 --hwm 50
  kill %1; cat /tmp/st.json

왜 따로 있나: SDK 의 RobotClient 는 받기 큐(RCVHWM 10,000)를 고정으로 쓴다. 이 도구는 큐와 커널 받기 버퍼를 바꿔 가며
"언제부터 버려지나"를 잰다 — 11/11 밤에 "1,000개(1초)를 넘으면 버린다"는 문서가 틀린 것을 이것으로 확인했다.
"""
import argparse
import json
import os
import sys
import time

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
import zmq  # noqa: E402

from rtsdk import wire  # noqa: E402


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--host", default="127.0.0.1")
    ap.add_argument("--port", type=int, default=5555)
    ap.add_argument("--hwm", type=int, default=10000, help="SUB 받기 큐 개수 (SDK 기본 10,000)")
    ap.add_argument("--rcvbuf", type=int, default=0, help="커널 받기 버퍼 바이트 (0 = 운영체제 기본)")
    ap.add_argument("--pause", type=float, required=True, help="읽지 않는 시간 (초)")
    ap.add_argument("--drain", type=float, default=1.0, help="그 뒤 다 읽는 시간 (초)")
    a = ap.parse_args()

    ctx = zmq.Context()
    sub = ctx.socket(zmq.SUB)
    sub.setsockopt(zmq.RCVHWM, a.hwm)
    if a.rcvbuf:
        sub.setsockopt(zmq.RCVBUF, a.rcvbuf)
    sub.setsockopt(zmq.SUBSCRIBE, b"")
    sub.connect(f"tcp://{a.host}:{a.port}")
    if not sub.poll(3000):
        sys.exit("상태가 오지 않음 — 노드가 떠 있나, 포트가 맞나?")
    last = wire.decode_state(sub.recv()).seq  # 붙은 것을 확인한 첫 장 (세지 않는다)

    time.sleep(a.pause)

    received = missed = 0
    first_age_ms = None
    t_end = time.monotonic() + a.drain
    while time.monotonic() < t_end:
        if not sub.poll(50):
            continue
        s = wire.decode_state(sub.recv())
        if first_age_ms is None:
            first_age_ms = (time.monotonic_ns() - s.rt_stamp_ns) / 1e6
        gap = (s.seq - last - 1) & 0xFFFFFFFF
        if gap < 0x80000000:
            missed += gap
        last = s.seq
        received += 1
    print(json.dumps({"tool": "slow_subscriber", "hwm": a.hwm, "rcvbuf": a.rcvbuf, "pause_s": a.pause, "drain_s": a.drain,
                      "received": received, "missed": missed,
                      "first_age_ms": None if first_age_ms is None else round(first_age_ms, 1)}, ensure_ascii=False))
    sub.close(0)
    ctx.term()
    return 0


if __name__ == "__main__":
    sys.exit(main())
