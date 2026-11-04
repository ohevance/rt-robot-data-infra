# 용어집 (쉬운 설명) — 면접에서 한 문장으로 말할 수 있게

각 항목: **한 줄 정의 → 비유 → 이 저장소에서 어디에 쓰이나**

## 실시간 (Real-time)
- "빠르다"가 아니라 **"늦어도 반드시 제시간 안에"**. 평균이 빨라도 한 번 늦으면 실패.
- 비유: 택배 '평균 2일'이 아니라 '늦어도 3일 보장'. 로봇은 1 ms 약속을 한 번 어기면 팔이 떨리거나 멈춘다.
- 여기서: `rt_control/rt_core` 전체.

## PREEMPT_RT (실시간 커널 패치)
- 리눅스를 실시간용으로 바꾸는 패치. 급한 일(RT 스레드)이 오면 커널이 하던 일을 **즉시 중단(선점)** 하고 양보한다.
- 비유: 응급차가 오면 모든 차가 바로 비켜주는 도로 규칙.
- 여기서: Ubuntu 24.04 + `pro enable realtime-kernel`. `/sys/kernel/realtime` 가 1이면 켜진 것.

## cyclictest
- "1 ms마다 깨워 달라" 해놓고 실제로 **얼마나 늦게 깼는지** 수십만 번 재는 표준 자(rt-tests 패키지).
- 여기서: `scripts/cyclictest_run.sh` → 표①.

## 지터 (jitter)
- 주기가 **흔들리는 정도**. 1 ms 약속인데 0.9~1.3 ms로 오락가락하면 지터가 크다.
- 여기서: `jitter_bench`의 period error 행.

## p99.9 / max
- **1,000번 중 999번은 이 값 이내**. 평균은 거짓말을 한다 — 999번 빨라도 1번 늦으면 로봇은 멈춘다.
- 여기서: 모든 표의 기준 열.

## SCHED_FIFO
- 리눅스에게 "이 스레드가 제일 급하다"고 알리는 **실시간 스케줄링 정책**. 우선순위 1~99. root 권한 필요.
- 비유: 줄서기 없는 VIP 통로.
- 여기서: `RtLoop::run` 3단계.

## mlockall
- 프로그램의 메모리를 **RAM에 고정**. 루프 도중 메모리가 디스크(스왑)에 가 있어 기다리는 일을 막는다.
- 여기서: `RtLoop::run` 1단계.

## 절대 시각 타이머 (clock_nanosleep + TIMER_ABSTIME)
- "지금부터 1 ms 뒤"가 아니라 **"그 시각에"** 깨워 달라고 말하는 것. 그래야 늦게 깬 만큼이 다음 주기로 쌓이지 않는다(드리프트 없음).
- 여기서: `RtLoop::run` 5단계, `next += period`.

## 락프리 큐 (lock-free queue, SPSC 링 버퍼)
- 두 스레드가 **줄 서지 않고** 값을 넘겨주는 컨베이어 벨트. RT 스레드가 로깅 때문에 멈추지 않게 한다. 꽉 차면 버리고 간다(기다리지 않는다).
- 여기서: `spsc_ring.hpp`. RT 스레드 → 로깅 스레드.

## ROS 2
- 로봇 소프트웨어 부품들이 서로 메시지를 주고받는 **공용 규격과 도구상자**. "토픽"은 우체통 이름, "노드"는 프로그램 하나.
- 여기서: `rt_control/ros2_adapter` (RT 핵심을 감싸는 얇은 껍질).

## DDS
- ROS 2 밑에서 실제로 메시지를 **배달하는 택배 시스템**. 구현체가 여럿(Fast DDS, Cyclone DDS).
- 여기서: `dds_bench` — 구현체·설정별 손실률·지연 표②.

## QoS (reliable / best-effort)
- 배달 옵션. **reliable = 등기**(분실 시 재전송, 느릴 수 있음), **best-effort = 일반 우편**(빠름, 분실 가능). 영상은 일반, 명령은 등기.
- 여기서: 표②의 행.

## MQTT
- 수백 대 장치가 **가벼운 메시지**를 서버에 보내는 우체국. 불안정한 네트워크·저전력 장치용. 브로커(우체국 건물)가 가운데 있다.
- 여기서: `fleet/` — 장치 에이전트 → Mosquitto 브로커 → 수집기.

## TimescaleDB / Grafana
- **시간순 데이터 창고** / 그걸 **그래프로 보여주는 상황판**.
- 여기서: `fleet/` docker-compose.

## OTA (Over-The-Air update)
- 원격 소프트웨어 업데이트. **단계 배포**(5% → 50% → 100%)와 **롤백**(문제 생기면 원복)이 핵심.
- 여기서: `fleet/ota/rollout.py`(서버: 보내고·기다리고·판정·롤백), `fleet/agent/device_agent.py`(장치: 적용 흉내·롤백).
- 한 문장: "50대에 나쁜 펌웨어를 올려도 3대에서 멈추고 1~2초 안에 돌아온다 — 숫자로 보여 드릴 수 있습니다."

## 단계 배포 / 카나리 (staged rollout / canary)
- 전체에 한 번에 올리지 않고 **소수(5%)에 먼저** 올려 지켜본 뒤 넓혀 가는 방식. 그 소수를 광산의 카나리아 새에 비유해 **카나리**라 부른다.
- 여기서: `rollout.py --stages 5,50,100`. 50대면 5% = 3대(올림).

## 헬스 게이트 (health gate)
- 단계를 넘어가기 전에 **건강한지 확인하는 문**. 여기서는 새 버전을 받은 장치의 텔레메트리 `state` 가 `ok` 인지 `health_wait` 초 동안 본다. 허용치(`max_fail`)를 넘으면 롤백.
- 여기서: `Rollout.run_stage()`.

## 상태 머신 (State Machine)
- 로봇의 **상태**(INIT → READY → RUNNING → FAULT → RECOVERING)와 **전환 규칙**을 표로 정한 것. "고장(FAULT)에서 바로 동작(RUNNING)으로는 못 간다, 복구(RECOVERING)를 100주기 거쳐야 한다" 같은 규칙이 코드가 된다.
- **표 기반(table-driven)**: 허용 전이를 `{지금 상태, 사건, 다음 상태}` 줄의 표로 두고, 표에 없는 전이는 거절하고 `illegal_events` 로 센다. if 문 더미보다 읽기 쉽고, 표 한 줄이 곧 테스트 한 줄이다.
- 여기서: `rt_core/robot_state_machine.hpp/.cpp`, 사건을 넣는 곳은 `control_step.cpp` 의 `update_state_machine()`, 결과는 `/rt_status` 의 `state`.

## MuJoCo
- 로봇 **물리 시뮬레이터**. 실물 없이 관절·중력·충돌을 계산. CPU에서 빠르고 결정적(같은 입력 → 같은 결과)이라 자동 테스트에 맞다.
- 용어: **mjModel**(설계도, 읽기 전용) · **mjData**(지금 상태) · **qpos/qvel**(관절 각/속도 배열) · **ctrl**(액추에이터 입력; position 액추에이터면 "원하는 각") · **mj_step**(물리 한 걸음) · **timestep**(한 걸음의 시간; 제어 주기 1 ms 에 맞춘다).
- 여기서: `rt_core/mujoco_backend.cpp`(Backend 구현), 모델은 MuJoCo Menagerie 의 SO-ARM100(`scripts/get_mujoco.sh`), 안내는 `backends/mujoco/README.md`.

## Menagerie (MuJoCo Menagerie)
- Google DeepMind 가 관리하는 **검증된 로봇 모델 모음**(MJCF xml). 직접 모델링하지 않고 가져다 쓴다.
- 여기서: `third_party/mujoco_menagerie/trs_so_arm100/scene.xml` (SO-ARM100; SO-101 과 같은 5축+그리퍼).

## CI (GitHub Actions)
- 코드를 올릴 때마다 **자동으로 빌드·테스트를 돌리는 검사원**. 통과하면 README에 초록 배지.
- 여기서: `.github/workflows/ci.yml`.

## MCAP / rosbag2
- 로봇 데이터(여러 토픽의 메시지)를 **시간순으로 한 파일에 기록**하는 형식(MCAP)과 도구(rosbag2).
- 여기서: `data_pipeline/record.sh`(기록) · `bag_to_csv.py`(표 + 검증). 관제(1 Hz, 수백 대, 가볍게)와 기록(100 Hz, 한 대, 무겁게)은 목적이 다른 두 길.

## 워치독 (watchdog)
- 명령이 **일정 시간 끊기면 스스로 안전 정지**하는 감시 타이머. "50 ms 동안 새 명령이 없으면 토크 오프".
- 여기서: `robots/*.yaml`의 `watchdog_ms`, 3주차 제어 노드.

## 노드 / 토픽 (ROS 2)
- 노드 = 프로그램 하나. 토픽 = 노드끼리 메시지를 주고받는 우체통 이름(`/joint_command`, `/joint_states`).
- 여기서: `rt_control_node` 하나가 구독 1개(명령), 발행 2개(상태·통계).

## 파라미터 파일 (ROS 2)
- 노드가 시작할 때 읽는 설정값 묶음(관절 이름, 주기, 우선순위…). `--params-file` 로 넘긴다.
- 여기서: `robots/so101.yaml` 에서 자동 생성한 `config/so101.params.yaml`.

## RMW (ROS Middleware)
- ROS 2 와 DDS 사이의 어댑터. 어떤 DDS 를 쓸지 환경변수 `RMW_IMPLEMENTATION` 으로 고른다(Fast DDS / Cyclone DDS).
- 여기서: 표②의 "구현체" 열.

## RTT (Round-Trip Time, 왕복 시간)
- 보내고 되돌아올 때까지의 시간. 두 기기의 시계가 달라도 같은 시계로 잴 수 있다. 한 방향 ≈ RTT/2.
- 여기서: `dds_bench/rtt_bench.py`.

## 우편함 (명령 링)
- ROS 2 콜백 스레드가 명령을 넣고 RT 스레드가 매 주기 전부 비워 "가장 최신 것"만 쓰는 SPSC 링.
- 여기서: `control_step.cpp` 의 `take_latest_command()`.

## 변화량 제한 (step limit)
- 한 주기에 목표가 움직일 수 있는 최대량(`max_step_rad`). 튀는 명령이 로봇을 치는 것을 막는 마지막 안전장치.
- 여기서: `control_step.cpp` 의 `limit_step()`.

## prlimit / RLIMIT_RTPRIO
- 일반 사용자가 실시간 우선순위를 쓸 수 있는 한도. `sudo prlimit --pid $$ --rtprio=99 --memlock=unlimited` 로 그 터미널에만 올린다. 서버·Pi 에서는 `/etc/security/limits.conf` 에 영구 설정.

## 브로커 (MQTT broker, Mosquitto)
- 장치들이 메시지를 보내는 우체국 건물. 장치는 서로를 몰라도 되고 브로커만 안다. 토픽 = 우체통 이름(`fleet/<id>/telemetry`).
- 여기서: `fleet/docker-compose.yml` 의 `mqtt`.

## 유언 (LWT, Last Will and Testament)
- 장치가 접속할 때 "내가 소리 없이 죽으면 이 메시지를 대신 보내 달라"고 브로커에 맡겨 두는 것. 전원이 뽑혀도 서버는 `offline` 을 받는다.
- 여기서: `device_agent.py` 의 `will_set`.

## client_id 충돌 (MQTT)
- 같은 client_id 로 두 번째 접속이 오면 브로커는 **먼저 있던 접속을 끊는다**(MQTT 규격). 둘이 모두 자동 재접속하면 2초마다 서로 밀어내며 메시지를 반반 받는다.
- 여기서: 수집기 client_id 는 지속 세션 때문에 "collector" 로 고정 → `fleet/logs/collector.lock` 잠금으로 한 번에 하나만 뜨게 (11/04 실측에서 겪음).

## 보관 메시지 (retained)
- 토픽의 "마지막 값"을 브로커가 기억해 뒀다가 새로 구독하는 쪽에 바로 준다. 장치 상태(online/offline)에 쓴다.

## store-and-forward (모았다 보내기)
- 연결이 끊기면 장치가 데이터를 쌓아 두고, 다시 붙으면 몰아서 보낸다. 유실을 "없애는" 게 아니라 "줄이고 세는" 장치.
- 여기서: `device_agent.py` 의 `buffer`, `flush_buffer()`.

## 하이퍼테이블 (hypertable, TimescaleDB)
- 시간으로 자동 분할되는 큰 표. 보통 PostgreSQL 표처럼 쓰면서 시계열 질의(`time_bucket`)가 빠르다.
- 여기서: `fleet/db/init.sql` 의 `telemetry`, `events`, `collector_stats`.

## COPY (PostgreSQL)
- 행을 하나씩 INSERT 하는 대신 묶음을 한 번에 밀어 넣는 명령. 수십 배 빠르다.
- 여기서: `collector.py` 의 `write_db()`.

## 전달 지연 (transit latency) — 코드의 `ingest_latency_ms`
- 장치가 측정한 시각 → 메시지가 **수집기에 도착**한 시각. 같은 시계(NTP)일 때만 의미.
- D2 문서에 "수집 지연"이라 썼지만 정확히는 **도착** 기준이다. DB 에 보이기까지는 1초 묶음 적재가 최대 약 1초 더 걸린다 — 그 1초는 이 숫자에 **들어 있지 않다**. 컬럼 이름은 호환을 위해 그대로 둔다.
- 여기서: `telemetry.ingest_latency_ms`, `collector_stats.lat_p95_ms`, 수집기 출력의 `transit ms`.

## QoS 0 / 1 (MQTT)
- 0 = **보내고 잊음**(가장 가볍다, 확인 없음). 1 = **적어도 한 번**(브로커가 받았다는 확인(PUBACK)까지, 안 오면 재전송).
- 여기서: 텔레메트리 기본 0, 재전송·명령은 1. 수집기가 죽어도 유실 0 을 원하면 장치 `--telemetry-qos 1` + 수집기 `--qos 1`(지속 세션) 둘 다 필요.

## 지속 세션 (persistent session, clean_session=False)
- 구독자가 끊겨 있는 동안 브로커가 **그 구독자 몫의 QoS 1 메시지를 대신 들고 있다가** 다시 붙으면 넘겨 주는 것. 구독자는 같은 client_id 로 붙어야 한다.
- 여기서: `collector.py --qos 1` (client_id "collector" 고정), 브로커 `max_queued_messages 20000`.
- 함정 둘: ① 브로커가 **재시작**되면 세션도 사라진다 — `persistence true` 여야 넘긴다(11/04 실측: 수집기보다 먼저 재접속한 장치 4~5대의 버퍼가 통째로 버려짐) ② 큐는 **상한**이 있다 — 꽉 차면 새 메시지를 버린다(실측: 7.5분 공백 중 마지막 49초분 2,450개 유실).

## keepalive / PINGREQ (MQTT)
- 클라이언트가 **이 시간 동안 아무것도 못 받으면** 살아 있다는 신호(PINGREQ)를 보낸다. 브로커는 1.5배 시간 안에 아무 소리가 없으면 끊고 유언을 발행한다.
- 여기서: 기본 10초. 전달 지연이 10초마다 튀는 현상의 용의자 → `virtual_fleet.py --keepalive 30` 으로 실험(`fleet/tools/diag.py`).

## backlog (수집기)
- DB 가 죽어서 못 넣은 **1초 묶음들을 메모리에 쌓아 둔 것**. DB 가 돌아오면 오래된 것부터 넣는다. 상한(20만 행)을 넘으면 가장 오래된 묶음을 버리고 센다.
- 여기서: `collector.py` 의 `drain_backlog()`, 통계 `backlog_rows`, 대시보드 패널 12.

## 장애 주입 (fault injection, chaos)
- 고장을 **일부러** 내고 시스템이 어떻게 감지·복구하는지 **숫자로** 재는 것. "장애에 강하다"를 말이 아니라 표로 보여 준다.
- 여기서: `fleet/chaos/inject.py --fault broker|db|collector|bad_firmware` → `docs/measurements/fault_*.json` → 표③-2.

## 마이그레이션 (DB migration)
- 이미 데이터가 있는 DB 의 **스키마를 바꾸는 번호 붙은 SQL 파일**. 어디까지 적용했는지 표(`schema_migrations`)에 기록해 두 번 돌려도 안전하다.
- 여기서: `fleet/db/migrations/002_ota.sql`, `003_collector_resilience.sql`, `fleet/db/migrate.py`.

## 가짜(fake) 모듈 — 테스트용 브로커·DB
- 진짜 Mosquitto·PostgreSQL 없이 **같은 함수 이름을 가진 간단한 흉내**를 끼워 넣어 논리를 테스트하는 기법. 네트워크 없이 1초 안에 돈다. 진짜로 하는 검증은 `integration.sh`.
- 여기서: `fleet/tests/fake_mqtt.py`(프로세스 안 브로커, 와일드카드·유언·끊김 흉내), `fake_psycopg.py`(쓰기 실패 스위치).

## rpath
- 실행 파일 안에 **공유 라이브러리를 찾을 경로를 적어 두는 것**. 없으면 `LD_LIBRARY_PATH` 를 매번 설정해야 한다.
- 여기서: MuJoCo 를 켜면 CMake 가 `libmujoco.so` 위치를 rpath 로 넣는다 (`-Wl,-rpath`, `CMAKE_INSTALL_RPATH_USE_LINK_PATH`).
