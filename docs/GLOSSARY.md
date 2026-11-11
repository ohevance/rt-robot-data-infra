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

### 실시간 커널은 무엇이 다른가 (조금 길게 — 표①을 읽기 위한 배경)
일반 커널과의 차이는 평균 속도가 아니라 **최악의 지연**이다.

| 상황 | 일반 커널 | 실시간 커널(PREEMPT_RT) |
|---|---|---|
| 커널이 내부 작업 중(인터럽트 처리, 락을 잡고 있음, 드라이버 일)일 때 RT 스레드가 깨어나야 하면 | 그 작업이 **끝날 때까지 기다린다** → 운 나쁘면 수백 us | 그 작업을 **중단시키고** RT 스레드부터 → 수십 us |
| Pi 4 실측 (표①, `docs/measurements/table1_pi4.md`) | 한가 max 376, 부하 max 695~781 us (2026-11-04) | (11/05 측정 — 기대 100~200 us 아래) |

구체적으로 바뀌는 것 세 가지:
1. **인터럽트 핸들러가 스레드가 된다.** Wi-Fi·SD 카드 인터럽트가 "우선순위를 가진 스레드"로 돌아가므로, 우선순위 80인 제어 스레드가 그것들을 밀어낼 수 있다. 일반 커널에서는 인터럽트가 항상 이긴다.
2. **스핀락이 잠들 수 있는 락(rt_mutex)으로 바뀐다.** 커널이 락을 잡고 있는 동안에도 선점이 된다. 일반 커널에서 `work time` 이 50 us 일하다 134.9 us 까지 밀린 것(표① 부하 줄)이 이 구간이다.
3. **우선순위 상속.** 낮은 스레드가 잡은 락을 높은 스레드가 기다리면, 낮은 쪽을 잠깐 높여서 빨리 놓게 한다(우선순위 역전 방지).

비유: 일반 커널은 "계산대 직원이 재고 정리를 시작하면 끝날 때까지 손님이 기다리는 가게", 실시간 커널은 "손님이 오면 정리를 즉시 멈추고 계산부터 하는 가게". 하루 평균 대기 시간은 비슷해도 **가장 오래 기다린 손님**의 시간이 다르다. 1 kHz 제어 루프는 평균이 아니라 그 손님 기준으로 설계한다.

면접 한 문장: "우선순위(SCHED_FIFO)는 줄을 앞에 세울 뿐이고, 커널이 하던 일을 중단시키는 것은 PREEMPT_RT 다 — WSL 에서 p50 은 92 → 37 us 로 좋아졌지만 max 는 그대로(921 → 937)였던 이유." (`docs/LOG.md` 11/03 D0 WSL, 표① Pi 줄이 그 증거.)

## 스로틀 (thermal throttling) — 왜 측정마다 온도를 적나
- 보드가 뜨거워지면(Pi 4 는 80 °C) 펌웨어가 **스스로 CPU 클럭을 내리는 것**. 같은 코드가 느려지고 지연 꼬리가 늘어난다.
- 그 상태에서 잰 지연은 "커널 때문"인지 "클럭 때문"인지 가를 수 없다 → 일반 vs 실시간 커널 비교가 무너진다. 그래서 측정마다 **온도 전·후**와 **스로틀 플래그**(`/sys/devices/platform/soc/soc:firmware/get_throttled`, 0 이면 부팅 후 한 번도 없음)를 결과 옆에 적고, 0 이 아닌 줄은 표에 올리지 않는다.
- 실제: 2026-11-04 부하 75초에 45 → 75 °C(방열판 없음). 그래서 부하 측정은 120초, 시작은 50 °C 아래.
- 비유: 100 m 달리기 기록 옆에 풍속을 적는 것 — 뒷바람이면 기록으로 인정하지 않는다.
- 여기서: `scripts/lib_thermal.sh`(읽기), `cyclictest_run.sh`·`jitter_run.sh`(.meta 기록), `make_table1.py`(비고 "온도 a→b °C, 스로틀 0"), 결정은 `DECISIONS.md` 11/04.
- 면접 한 문장: "임베디드 보드의 지연 측정은 열 조건을 같이 기록하지 않으면 재현도 비교도 안 된다 — 표①의 모든 Pi 줄에 온도와 스로틀 여부가 붙어 있는 이유."

## IPI (Inter-Processor Interrupt, CPU 간 인터럽트) — isolcpus 로도 못 막는 지연
- 한 CPU 가 다른 CPU 들에게 "지금 당장 이것 해라" 하고 보내는 인터럽트. 대표: 메모리 매핑을 지울 때(munmap) 다른 CPU 의 주소 변환 캐시(TLB)를 비우라는 **TLB 동기화**.
- 우선순위(SCHED_FIFO)도, CPU 격리(isolcpus)도 막지 못한다 — 그래서 격리한 CPU 3 에도 189 us 의 꼬리가 남는다(표①, E19-c).
- 비유: 건물 전체 화재 경보. 내 방 문을 잠가도(격리) 경보는 들린다.
- 여기서: `docs/experiments/E19c.md`(잔여 189 의 추정 원인), `E19d.md`(stress-ng `--vm-bytes` 가 작을수록 munmap 이 잦아 IPI 가 는다는 추정), `scripts/lib_stress.sh` 머리말.

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

## ZeroMQ (ØMQ, 11/11)
- 브로커 없이 프로그램끼리 메시지를 주고받는 라이브러리. 소켓 모양(패턴)을 골라 쓴다: **PUB/SUB**(한쪽이 뿌리고 여럿이 받는다 — 상태 흐름), **DEALER/ROUTER**(요청을 연달아 보내고 답은 번호로 맞춘다 — 명령), REQ/REP(번갈아 보내고 받기 — 답 하나를 잃으면 멈춘다).
- MQTT 와의 차이: MQTT 는 가운데 **브로커**가 있고(함대 관제, 인터넷), ZeroMQ 는 **직접 연결**이다(로봇 한 대 안·옆, 1 kHz). DDS 와의 차이: DDS 는 발견·QoS·형식까지 표준이 정하고, ZeroMQ 는 바이트를 나를 뿐이라 형식(여기서는 `wire.hpp`)을 우리가 정한다.
- 높은 물 표시(HWM): 소켓이 쌓아 둘 최대 개수. 넘으면 PUB 는 버린다 — 느린 구독자가 보내는 쪽을 막지 않게. libzmq 는 TCP 연결에 `TCP_NODELAY` 를 스스로 켠다(strace 로 확인 — E24).
- 여기서: `rt_control/zmq_adapter`, `sdk/python/rtsdk`, E24.

## 공유 메모리 · seqlock (11/11)
- 공유 메모리: 두 프로세스가 같은 메모리 한 덩어리를 본다(리눅스 `/dev/shm/<이름>`). 소켓도 복사도 없어 가장 빠르다. 대신 "언제 다 썼나"를 알릴 방법이 필요하다.
- seqlock: 쓰는 쪽은 번호를 홀수로 → 데이터 → 짝수로. 읽는 쪽은 번호 → 데이터 → 번호를 다시 읽어 **둘이 같고 짝수일 때만** 받아들인다(아니면 쓰는 도중이었으므로 다시). **쓰는 쪽은 아무것도 기다리지 않는다** — 읽는 프로세스가 멈추거나 죽어도 RT 쪽은 그대로. 예: 은행 전광판을 사진 찍는데, 찍기 전후의 "갱신 번호"가 다르면 그 사진은 버리고 다시 찍는다.
- 여기서: `rt_core/include/rt_core/shm_seqlock.hpp`, `rt_state_peek`, 시험 `test_shm_seqlock`(번호 확인을 지운 변형에서 시험이 실패하는 것까지 확인).

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
- 여기서: `fleet/ota/rollout.py`(서버: 보내고·기다리고·판정·롤백), `fleet/agent/device_agent.py` + `ota_apply.py`(장치: 진짜 설치 — 내려받기·sha256·A/B 슬롯·자가 점검·전환·롤백; 11/05 까지는 흉내였다).
- 한 문장: "50대에 나쁜 펌웨어를 올려도 3대에서 멈추고 1~2초 안에 돌아온다 — 숫자로 보여 드릴 수 있습니다."

## A/B 슬롯 (A/B slot, 이중 파티션)
- 새 버전을 **다른 폴더(슬롯)에 통째로** 깔고, "지금 켜는 쪽"을 가리키는 링크만 바꾸는 방식. 옛 버전이 온전히 남아 있어 되돌리기는 링크만 바꾸면 끝.
- 왜: 업데이트 도중 전원이 꺼져도 "반쯤 덮어쓴 파일"이 생기지 않는다 — 링크 교체(`os.replace`)는 원자적이라 옛 슬롯 아니면 새 슬롯, 둘 중 하나다.
- 여기서: `fleet/agent/ota_apply.py` — `slots/<버전>/`, `current -> slots/<버전>`, `state.json`(current·previous). `docs/RELEASE.md` 3절.

## 매니페스트 (manifest)
- "이 릴리스에 무엇이 들어 있나"를 적은 작은 JSON: 버전, 파일 이름(아키텍처별), sha256, 크기, 커밋, 배포 정책(5/50/100 %, 헬스 대기).
- 여기서: `scripts/package_release.sh` 가 만들고 `merge_manifests.py` 가 합친다. 배포기(`rollout.py --manifest`)와 장치의 자율 업데이트가 읽는다. GitHub Release 의 `manifest.json`.

## 자가 점검 (selftest) — 켜지는가
- 새 슬롯을 "지금 켜는 쪽"으로 바꾸기 **전에** 장치가 그 안의 프로그램을 짧게 돌려 보는 것. 실패하면 설치하지 않고 슬롯을 지운다.
- 여기서: `selftest.sh` 가 `jitter_bench` 를 0.5초 돌려 실행됨·주기 100회 이상·드롭 10 % 이하면 통과. 깨진 빌드는 헬스 게이트(켜진 뒤 상태를 보는 문) 전에 여기서 걸린다 — 그래서 롤백이 0.2초.
- 왜 드롭 0 이 아닌가: 카나리에서 25대가 한 러너에서 동시에 돌린다. RT 성능은 E05·E19 가 재고, 자가 점검은 "켜지는가"만 본다.

## sha256 과 서명 (integrity vs authenticity)
- **sha256**: 받은 파일이 매니페스트의 파일과 한 바이트도 다르지 않은가(무결성). 전송 중 깨짐·잘못된 파일을 잡는다.
- **서명**: 그 매니페스트를 "우리가" 만들었는가(진위). 비밀키로 서명하고 장치가 공개키로 확인한다. **여기서는 아직 안 했다**(DECISIONS 11/10) — 다음 단계는 ed25519 서명.

## 자율 업데이트 (autonomous / pull-based update)
- 지휘소(서버) 없이 장치가 스스로 "새 버전이 있나" 확인해 설치하는 방식. 밖으로 나가는 연결만 있으면 되므로 공유기 뒤에 있어도 된다.
- 여기서: `pi_agent.py --auto-update <Release 의 latest/manifest.json> --poll-s 600 --window 3-5` — 10분마다, 03~05시에, `state == ok` 일 때만, 정식 릴리스만(pre-release 는 `latest` 에 없음). 함대 차원의 카나리는 CI 의 가상 50대가 매 릴리스 맡는다.
- 왜: 항상 켜진 서버(노트북)가 없다. 로봇은 서버 없이도 움직이고 스스로 업데이트되어야 한다는 설계이기도 하다.

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
- 코드를 올릴 때마다 **자동으로 빌드·테스트를 돌리는 검사원**. 통과하면 README에 초록 배지. 내 노트북이 아니라 GitHub 의 새 가상 머신(러너)에서 돈다.
- 비유: 도면을 보관소에 낼 때마다 검사원이 백지 상태의 작업대에서 다시 조립해 보는 것 — "내 작업대에서만 되는" 문제를 거른다.
- 여기서: `.github/workflows/ci.yml`(정의), `docs/ENVIRONMENT.md` §5(환경·트리거·잡 3개·결과 읽는 법·실패 유형별 첫 행동·Jenkins 대응표). CI 가 실제로 잡은 문제 2건은 §5-5.

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
