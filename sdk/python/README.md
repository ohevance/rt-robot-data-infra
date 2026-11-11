# rtsdk — Python SDK (rt_zmq_node 용)

로봇의 실시간 제어 노드(`rt_control/zmq_adapter`)와 ZeroMQ 로 이야기한다. 의존성은 pyzmq 하나(`sudo apt-get install python3-zmq` 또는 `pip install pyzmq`).

```python
from rtsdk import RobotClient, CommandRejected

with RobotClient("127.0.0.1") as robot:          # 상태 5555(SUB), 명령 5556(DEALER)
    info = robot.info()                           # {"dof": 6, "loop_hz": 1000, "backend": "sim_lag", "rt": {...}, ...}
    robot.send_target([0.1] * info["dof"])        # 노드가 받았는지(ACK)까지. 거절이면 CommandRejected(status)
    seq = robot.send_target([0.2] * 6, wait_ack=False)   # 흘려보내기 (100 Hz 등). 답은 robot.ack_status(seq)
    s = robot.wait_state()                        # 다음 상태: position · velocity · target · robot_state · watchdog_tripped · cmd_seq
    s = robot.latest_state()                      # 쌓인 것 중 최신 (기다리지 않음)
    robot.wait_until(lambda st: st.cmd_seq >= seq)   # 내 명령이 RT 루프에 반영된 첫 상태
    print(robot.ping())                           # 왕복(초) — 내 시계 하나로
```

| 모듈 | 하는 일 |
|---|---|
| `rtsdk/wire.py` | 통신 패킷. C++ `rt_core/wire.hpp` 와 같은 형식(골든 바이트 시험으로 확인). pyzmq 없이 import 된다 |
| `rtsdk/client.py` | `RobotClient` — 소켓 둘, 답을 번호로 맞추기, 빠진 상태 세기(`states_missed`) |
| `rtsdk/bench.py` | `python3 -m rtsdk.bench --n 1000 --rate 100 [--same-host] --json out.json` — ping 왕복 · 명령 → 상태 반영 · 상태 흐름 |
| `examples/follow_sine.py` | 사인파 목표를 100 Hz 로 보내고 실제 위치를 찍는다 |
| `tests/test_wire.py` | 형식 시험 (pyzmq 없이) — 4건 |
| `tests/test_zmq_node.py` | 끝-대-끝: 진짜 노드를 띄우고 info·추종·워치독·복구·나쁜 패킷·공유 메모리·종료 (CI rt_core 잡) |

규칙 두 가지 — 노드의 동작에서 온다
- **명령은 워치독(기본 50 ms)보다 충분히 자주.** 시험을 처음 20 Hz(50 ms 간격)로 썼다가 워치독이 9번 걸렸다 — 간격이 워치독과 같으면 경계에 걸린다. 100 Hz 를 쓴다.
- **시각은 같은 PC 일 때만 뺀다.** `State.rt_stamp_ns`·`sent_ns` 는 노드의 단조 시계다. 왕복(ping)과 명령 → 반영은 내 시계 하나로 재므로 어디서나 맞다.
