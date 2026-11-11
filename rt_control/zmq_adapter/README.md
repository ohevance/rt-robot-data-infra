# zmq_adapter — 실시간 제어 노드를 ZeroMQ 로 (rt_zmq_node) + 공유 메모리

ROS 2 노드(`../ros2_adapter`)와 **같은 `rt_core`** (RT 루프 · 제어 단계 · 워치독 · 상태 머신)를 쓰고, 바깥 껍질만 ZeroMQ 로 바꾼 노드다.
`docs/ARCHITECTURE.md` 가 11/03 부터 말해 온 "미들웨어 교체 = 어댑터 교체"를 코드로 보인 것 — `rt_core` 는 한 줄도 ZeroMQ 를 모른다
(바뀐 것은 명령 번호를 상태에 실어 돌려주는 필드 두 개뿐: `JointCommand::seq`, `JointStateSample::cmd_seq`).

```
 [Python SDK: RobotClient]                          [rt_zmq_node]
   SUB  ◀──── STATE (1 kHz 까지) ────── PUB   ◀── 발행 스레드 ◀── 상태 벨트(spsc_ring) ◀──┐
   DEALER ── TARGET·PING·GET_INFO ──▶ ROUTER ──▶ 명령 스레드 ──▶ 명령 우편함(spsc_ring) ──▶ RT 스레드 (1 kHz, SCHED_FIFO)
          ◀── ACK·PONG·INFO ───────                                                         │ ControlStep → Backend
 [같은 PC 의 다른 프로세스: rt_state_peek]                                                    │
   공유 메모리 /rt_state (seqlock) ◀──────────── 발행 스레드가 최신 한 장을 쓴다 ◀─────────────┘
```

## 무엇이 어디에

| 파일 | 하는 일 |
|---|---|
| `src/rt_zmq_node.cpp` | 노드. 스레드 셋(RT · 발행 · 명령), 소켓 둘(PUB · ROUTER), 공유 메모리 하나 |
| `src/rt_state_peek.cpp` | 같은 PC 에서 공유 메모리로 최신 상태를 읽는 C++ 예 (소켓 없음) |
| `../rt_core/include/rt_core/wire.hpp` · `src/wire.cpp` | 통신 패킷 형식 — 머리 24바이트 + 본문, 리틀엔디언. **형식 표는 wire.hpp 머리말** |
| `../rt_core/include/rt_core/shm_seqlock.hpp` | 공유 메모리 seqlock (쓰는 쪽은 기다리지 않는다) + shm_open/mmap |
| `../../sdk/python/rtsdk/` | Python SDK — `RobotClient`, `wire`, `bench` |

## 빌드 · 실행 (WSL / Pi — Ubuntu 24.04)

```bash
# [WSL 창] 또는 [Pi 창]
sudo apt-get install -y libzmq3-dev python3-zmq
cmake -S rt_control/zmq_adapter -B build/zmq_adapter && cmake --build build/zmq_adapter -j
./build/zmq_adapter/rt_zmq_node --dof 6 --prio 0                 # 권한이 있으면 --prio 80 (SCHED_FIFO), Pi 는 --cpu 3 (격리한 코어)
# 다른 창
PYTHONPATH=sdk/python python3 sdk/python/examples/follow_sine.py  # 사인파 목표 → 실제 위치
./build/zmq_adapter/rt_state_peek --count 5                        # 공유 메모리로 최신 상태
RT_ZMQ_NODE=build/zmq_adapter/rt_zmq_node python3 sdk/python/tests/test_zmq_node.py   # 끝-대-끝 시험 (CI 와 같은 것)
```

옵션은 `--help`. 기본 포트는 상태 5555, 명령 5556. **기본 bind 는 `tcp://*`(모든 주소)이고 ZeroMQ 는 암호화·인증이 없다**(CURVE 를 켜지 않았다) —
LAN 안에서만, 밖에서 닿는 곳이면 `--state-ep tcp://127.0.0.1:5555` 처럼 묶거나 방화벽으로 막는다. 클라우드의 MQTT(8883, TLS + 비밀번호)와 다른 층이다:
MQTT 는 함대 관제(1 Hz, 인터넷), ZeroMQ 는 로봇 한 대 안·옆의 제어 경로(1 kHz, LAN/같은 PC).

## 설계에서 정한 것 (이유는 `docs/DECISIONS.md` 11/11)

- **명령은 DEALER ↔ ROUTER**: REQ/REP 는 "보내고 받기"를 번갈아야 해서 답 하나를 잃으면 소켓이 멈춘다. 명령은 100 Hz 로 흘려보내는 것이라
  DEALER 로 연달아 보내고 답(ACK)은 번호로 맞춘다. 노드는 모든 패킷에 답한다 — 거절도 이유(status)와 함께.
- **상태는 PUB → SUB, 높은 물 표시 1,000**: 느린 구독자가 노드를 막지 않는다. 넘치면 노드가 버리고(`states_send_dropped`) SDK 는 빈 번호로 센다.
- **패킷은 고정 머리 + 길이 + 버전**: 받는 쪽이 본문을 읽기 전에 형식·잘림을 판정. 할당 없이 고정 버퍼. C++ 와 Python 이 같은 바이트를 기대하는 골든 시험 둘.
- **NaN 은 노드가 거절**(BAD_VALUE): NaN 은 변화량 제한의 비교를 전부 통과한다(NaN 비교는 늘 거짓) — 마지막 안전장치가 뚫리는 값이다.
- **공유 메모리는 seqlock**: 읽는 프로세스가 몇이든·멈추든 쓰는 쪽은 기다리지 않는다. 데이터 칸을 `std::atomic<uint64_t>` 로 두어 C++ 메모리 모델에서도 정의된 동작.
  섞인 읽기 0 을 시험하고, 번호 확인을 지운 변형에서 시험이 실패하는 것을 확인했다.
- **명령 번호를 상태에 실어 돌려준다**(`cmd_seq`): "내 명령이 RT 루프에 들어가 상태로 돌아오기까지"를 클라이언트가 자기 시계 하나로 잰다.

## 숫자 (`docs/experiments/E24.md`)

샌드박스(2코어 VM, 일반 커널, SCHED_FIFO 없음, 같은 PC)에서 500회: ping 왕복 p50 0.33 ms · 명령 → 상태 반영 p50 1.02 / p99 1.76 ms ·
RT → 클라이언트 한 방향 p50 0.42 ms, 상태 5,170개 중 빠짐 0, 명령 500 중 잃음 0. **WSL·Pi 값은 아직 없다** — 같은 명령으로 재서 E24 에 더한다.

## 하지 않은 것

- Zenoh, C++ 클라이언트 SDK(소켓 쪽), CURVE 암호화, 명령의 시각 기반 보간(지금은 "최신 것 하나") — E24 남은 일.
- 실물 하드웨어 통신(EtherCAT 등): 이 저장소에는 하드웨어가 없다. 들어갈 자리는 `rt_core/backend.hpp` 의 `Backend` 구현 하나다.
