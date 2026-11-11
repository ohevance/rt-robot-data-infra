# rt-robot-data-infra

로봇과 무관한(robot-agnostic) **실시간 제어 + 데이터 인프라** 저장소.
ROS 2 / PREEMPT_RT / DDS / ZeroMQ · 공유 메모리 · Python SDK / 장치 텔레메트리 관제 / OTA / 장애 복구 / MuJoCo / CI — 휴머노이드 로봇 회사의
**Framework S/W 엔지니어** 직무(Linux 로봇 프레임워크 · 실시간 제어 · 상태 머신 · ZeroMQ/ROS 통신과 SDK · OTA·로깅)를 겨냥해 2026년 11월에
만들었다 — 2주 본편 + 덧붙임(진행 기록: `docs/LOG.md`).

![ci](https://github.com/ohevance/rt-robot-data-infra/actions/workflows/ci.yml/badge.svg)

| 공고 주요 업무 (Framework S/W 엔지니어) | 산출물 | 수치 | 상태 |
|---|---|---|---|
| ① Linux 로봇 프레임워크 · 프로세스 구조와 미들웨어 · 멀티스레드 데이터 흐름 · IPC | `rt_control/rt_core`: RT 스레드 ↔ 일반 스레드를 락 없는 우편함(`spsc_ring`)으로. 같은 핵심을 노드 둘이 감싼다 — ROS 2(`ros2_adapter`) · ZeroMQ(`zmq_adapter`). 같은 PC 의 다른 프로세스는 공유 메모리 seqlock(`shm_seqlock.hpp`). 로봇은 백엔드 인터페이스 하나 뒤에 — SO-ARM100 6 자유도와 **위로보틱스 공개 ALLEX 48 자유도**가 프로필만 다르다(`rt_core/mujoco_backend`) | 1 kHz 루프 드롭 0(Pi 4, 14조건) · seqlock 섞인 읽기 0 / 36,692(번호 확인을 지운 변형은 3/3 실패) · 우편함이 차면 이유와 함께 거절하고 센다 · ALLEX 500 Hz 물리 p99 510 us(러너, 2 ms 의 26 %) | 완료 |
| ② 실시간 제어 환경(Xenomai · PREEMPT_RT) · 지연 최적화 | PREEMPT_RT 커널 + SCHED_FIFO + mlockall + CPU 고정 + `isolcpus`(Pi 4), 측정기 `jitter_bench` 와 표준 도구 cyclictest 의 교차 확인, 표① 생성기 | 부하 중 깨어남 max **781 → 189 us**(일반 → RT + 격리) · cyclictest max 695 → 132 us · 내 측정기 vs cyclictest 270 vs 274 us | PREEMPT_RT 완료(Pi 4 실측 11/04~05, 재부팅 뒤에도 RT 커널·격리 유지 11/11). **Xenomai 는 하지 않았다** |
| ③ 상태 머신 · 오류 복구 시나리오 | `robot_state_machine`(INIT → READY → RUNNING → FAULT → RECOVERING, 전이 표 + 불법 전이 카운터), 워치독 → FAULT(자리 유지) → 명령이 다시 오면 RECOVERING → 100 ms 연속 정상이면 READY | 명령이 끊기면 **51~52 ms 뒤 FAULT**(워치독 50 ms), 위치 그대로, 불법 전이 0 — CI 끝-대-끝이 매 push | 완료 |
| ④ ZeroMQ · ROS 통신 패킷 · Python/C++ SDK | 패킷 `rt_core/wire.hpp`(머리 24바이트 + 본문, C++·Python 골든 바이트 시험), `rt_zmq_node`(명령 DEALER↔ROUTER, 상태 PUB), Python SDK `sdk/python/rtsdk`, ROS 2 노드 · DDS 측정 `dds_bench` | 명령 → RT 루프 반영 → 상태 **p50 0.88 / p99 1.81 ms**(WSL, 1,000회, 잃음 0 — RT 스레드를 SCHED_FIFO 로 올려도 0.88 / 1.71) · 1 kHz 상태 약 1만 개 빠짐 0 · 표② DDS 손실·지연 | 완료(11/11). C++ 쪽은 노드와 패킷 형식까지 — 소켓 클라이언트 SDK 는 아직. Pi 값은 아직(예측은 E24) |
| ⑤ EtherCAT 마스터 · 슬레이브 진단 · 오류 복구 | **없음** — 하드웨어가 없다. 들어갈 자리는 `rt_core/backend.hpp` 의 `Backend` 하나(SimLag · MuJoCo 백엔드가 같은 자리에 있다) | — | 지원 뒤 판단(DECISIONS 11/11) |
| ⑥ OTA 업데이트 · 로그 수집·분석 | `fleet` 수집 → TimescaleDB → Grafana(14 패널), 장애 주입 4종, **릴리스 → 배포**(태그 → 빌드 → 가상 50대 카나리 → Release 게시 → 장치가 sha256·A/B 슬롯·자가 점검으로 설치, 실물은 자율 업데이트) `docs/RELEASE.md`, 로봇 안 기록 `data_pipeline`(rosbag2 MCAP → CSV → 요약), 클라우드 운영 층 `deploy/ec2/` | 50대 설치 **14.62 s** · 깨진 패키지 **3/50 에서 거부 → 롤백 1.0 s** · 브로커 10초 중단 유실 0 / 1400 · 실물 Pi → 클라우드 53,167건 유실 0 | 완료 — 정식 `v0.9.0` 게시(11/11), 장애 4종은 매 push CI 에서 다시 |
| 필수 역량: Git · Docker · CI/CD | CI 3잡(단위 → 통합 컨테이너 · MuJoCo 헤드리스 ×2 모델) + 릴리스 워크플로(태그 → 4잡) | 테스트 **37건**(C++ 7 · Python 30) + 끝-대-끝 셋(컨테이너 통합 · 릴리스 카나리 · ZeroMQ 노드 12단계) · 태그 → 게시 1분 27초 | 완료, CI 초록 |

11/10 까지 이 표는 다른 채용 공고의 문구(① 실시간 Linux 미들웨어 · ② 로깅·모니터링·업데이트 · ③ 센서 스트리밍 · ④ 시뮬레이션·CI)로 나뉘어 있었다. 산출물은 같고, 11/11 에 지원하는 공고를 하나로 정하면서 그 공고의 주요 업무로 다시 나눴다(DECISIONS 11/11).

## 숫자 한눈에 (2026-11-11 기준 — 어디서 잰 값인지가 숫자만큼 중요하다)

| 무엇 | 값 | 어디서 | 원본 |
|---|---:|---|---|
| RT 루프 1 kHz, 5초, 드롭 | 0 | WSL2(가상 커널, 참고값) | `docs/measurements/jitter_wsl_*.json` |
| 깨어남 지연 p99 / max (ROS 2 노드 안) | 278 / 679 us | WSL2 참고값 | D1 실측 (`docs/LOG.md`) |
| SCHED_FIFO 의 효과 p50 | 92 → 37 us (꼬리는 그대로) | WSL2 참고값 | `table1.md` |
| **Pi 4 일반 커널**, 한가 / 부하 — cyclictest max (4 CPU 중 최악) | **376 / 695 us** (p99.9 57 / 118) | Pi 4B, Ubuntu 24.04 `6.8.0-1064-raspi`, 300 s / 120 s, 스로틀 0 | `table1_pi4.md` |
| 같은 것, 우리 측정기 jitter_bench 60 s max | 24.9 / **781.2** us (부하 중 `work time` max 134.9 — 일하다 밀림) | Pi 4B 일반 커널 | `table1_pi4.md` |
| **Pi 4 PREEMPT_RT**, 같은 cyclictest max 한가 / 부하 | **37 / 132 us** (일반 376 / 695 의 1/10 · 1/5) | Pi 4B `6.8.0-2054-raspi-realtime`, 스로틀 0 | `table1_pi4.md` |
| 부하 중 jitter_bench max: 일반 → RT → +CPU 3 고정 → +isolcpus=3 | **781 → 301 → 311 → 189 us** (work max 135 → 98 → 86 → 53) | Pi 4B | `table1_pi4.md`, `docs/experiments/E19a~c.md` |
| RT 커널의 비용 (숨기지 않는 줄) | 부하 p99 146 → **185** us — 최악은 잘리고 보통 나쁜 경우는 조금 나빠진다 | Pi 4B | `docs/experiments/E19a.md` |
| 내 측정기 vs 표준 도구(cyclictest), **같은 설정**으로 맞췄을 때 | **270 vs 274 us** (처음 2.3배 차이의 원인은 스레드 배치·부하 정의) | Pi 4B RT | `docs/experiments/E19d.md` |
| MuJoCo 물리 한 주기 비용 p50 / p99 / max | 6.4 / 8.5 / 29.4 us (1 ms 의 0.9%) | GitHub 러너, SO-ARM100 6축 | `mujoco_backend_ci.json` |
| 같은 것, **ALLEX 48 자유도**(위로보틱스 공개 모델) 1 kHz | WSL 336 / 622 / 1,785 us (p99 = 예산의 62 %) · 러너 382 / 458 / 609 (46 %) | WSL2 단독(참고값) · GitHub 러너 | `mujoco_backend_allex_wsl_1khz.json`, `…_ci_1khz_run42172730308.json`, E21 |
| 같은 것, 프로필 기본인 **500 Hz** | WSL 327 / 1,000 / 1,589 us (p99 = 2 ms 의 50 %) · 러너 390 / 510 / 685 (26 %) | WSL2 단독(참고값) · GitHub 러너(CI 게이트) | `mujoco_backend_allex_wsl_500hz.json`, `…_ci_500hz_run42175845461.json`, E21 |
| 같은 것, WSL 단독 / ROS 2 노드 안 `work_us`(제어+물리) | 4.9 / 6.3 / 20.8 us · 41 / 145 / 247 us | WSL2 참고값 | `mujoco_backend_wsl_20261104.json` · `docs/LOG.md` 11/04 |
| 물리가 드러낸 중력 처짐 (어깨 Pitch, 목표 −0.200) | −0.180 rad (1.1° 부족) | WSL2, MuJoCo | `docs/LOG.md` 11/04 |
| 로봇 안 기록 파이프라인 30 s: `/joint_states` 실제 Hz / 틈 / 드롭 | **100.0 Hz / 0 / 0** (2,964행), 요약표에 어깨 처짐 0.019 rad + 팔꿈치 0.009 자동 검출 | WSL2, rosbag2 MCAP → CSV | `record_summary_wsl_20261105.md` |
| DDS 1 MB 손실: Fast DDS best_effort / Cyclone | 99.8% / 0% | WSL2, rclpy | `table2.md` |
| 관제 50대 1 Hz 전달 지연 p50 / p95 | 0.9 / 1.8 ms | WSL2 | `table3.md` ③-1 |
| 브로커 10초 중단 → 전 장치 복귀, 유실 | 2.9초, 0 / 1400 | WSL2 | `table3.md` ③-2 |
| DB 10초 중단 → backlog 0, 유실 | 1.4초, 0 / 1341 | WSL2 | ③-2 |
| 수집기 10초 중단 → 유실: 지속 세션(QoS 1) / 보호 없음(QoS 0) | 0 / 1311 · **508** / 1312 (예측 500) | WSL2 | ③-2 |
| 전달 지연 10초 주기 튐의 원인 | keepalive 박자 — 10초: 10.0초 간격 튐, 30초: 0회 | WSL2, A/B | `docs/LOG.md` 11/04 |
| 나쁜 펌웨어 단계 배포 → 닿은 장치, 롤백 | 3 / 50, 1.0초 | WSL2 | ③-3 |
| 같은 장애 4종을 GitHub 러너에서 (10대 2 Hz) | 유실 0·0·0, 롤백 0.4초 | CI `fleet_integration` 1m52s | `table3_ci.md` |
| **진짜 산출물 OTA** 50대(릴리스 카나리): 단계별 적용 완료 5 / 50 / 100 %, 전체 · 깨진 패키지 | **1.2 / 2.2 / 2.2 s, 14.62 s**(헬스 대기 3 s × 3 포함) · **3/50 에서 거부 → 롤백 1.0 s** · 태그 → 게시 **1분 27초** | GitHub 러너, 진짜 Mosquitto, 정식 태그 `v0.9.0`(11/11). 같은 날의 사전 릴리스 `v0.9.0-rc1` 은 1.2 / 2.0 / 2.2 s · 14.41 s · 1분 52초 — 단계별 시간이 두 번 모두 0.2 s 안에서 같다. 샌드박스(가짜 브로커)는 0.6 / 1.0 / 1.2 s · 롤백 0.2 s | `ota_release_v0.9.0_*.json`, `ota_release_v0.9.0-rc1_*.json`, E22 |
| **실물 Pi → 클라우드 서버 연속 보고**(1 Hz, TLS + 비밀번호): 보낸 수 / 받은 수 / 유실 | **53,167 / 53,167 / 0** (14.77 시간, 재시작 0, 서버가 못 받은 최장 1.6 s, 수집기 재시작 1회 포함) | Pi 4(집 Wi-Fi, RT 커널) → **서버: 시드니**(EC2 t3.small), 11/10 18:37 ~ 11/11 09:23 | `soak_pi-rt_20261111T0023Z.json`, `deploy/ec2/soak_report.sh` |
| **Pi ↔ 클라우드 브로커 MQTT 왕복**(TLS + 비밀번호, 1초 간격) · 접속 한 번 | **p50 290 / p95 291 ms**(60회, 최대 383) · 접속 1.2~1.5 s | Pi 4(집 Wi-Fi) → **서버: 시드니**. 0.2초 간격으로 재면 548~707 ms 로 보인다(Nagle — 재는 방법이 만든 값, E23) | `rtt_pi_sydney_20261111T0041Z_A_interval1.00.json`, E23 |
| **실물 Pi 가 Release 를 받아 설치**(GitHub → sha256 → A/B 슬롯 → 자가 점검 → 전환) | **한 번 0.98 ~ 1.62 s**, 그중 자가 점검 0.67 s · 드롭 0/500 | Pi 4, RT 커널, 러너(arm)가 만든 `v0.9.0-rc1` aarch64 패키지 21.7 KB, 3회 | `install_pi4_once_v0.9.0-rc1.json`, E22 |
| **ZeroMQ 노드: 명령 → RT 루프 반영 → 상태**(같은 PC) · ping 왕복 · 1 kHz 상태 흐름 | **p50 0.88 / p99 1.81 ms** · p50 0.21 ms · 10,327개 중 빠짐 0 (1,000회, 잃음 0) — 반영 지연의 절반은 1 kHz 루프의 다음 주기를 기다리는 몫. RT 스레드를 SCHED_FIFO 로 올려도 **0.88 / 1.71 ms**(최댓값 19.7 → 3.7 ms 는 한 번씩이라 원인을 가르지 않는다) | WSL2(가상 커널, 참고값), 11/11 밤. 샌드박스(2코어 VM)는 1.02 / 1.76 ms. Pi 는 아직 | `zmq_bench_wsl_20261111.json`, `zmq_bench_wsl_fifo_20261111.json`, E24 |
| 느린 구독자 — 상태를 읽지 않으면 (ZeroMQ PUB/SUB) | 12초까지 빠짐 0 — 전부 오되 **첫 장이 12초 묵은 채로**. 45초(SDK 기본 큐)면 빈 번호 12,109, 그래도 노드의 버림 카운터는 **0**(PUB 는 조용히 버린다) | 샌드박스, 진짜 libzmq 4.3.5 | E24 7절, `sdk/python/tools/slow_subscriber.py` |
| 큐 상한을 넘겼을 때 (실험) | 7.5분 공백 중 마지막 49초분 2,450개 유실 | WSL2 | `docs/LOG.md` 11/04 |

실시간 **지연의 진짜 값**은 Raspberry Pi 4 + PREEMPT_RT 실측(위 Pi 줄들)이다. 한 변수씩 바꾼 사슬(커널 → 고정 → 격리)과 그 이유는 [`docs/EXPERIMENTS.md`](docs/EXPERIMENTS.md) 의 순서도, 각 실험의 상세는 [`docs/experiments/`](docs/experiments/README.md). WSL 값은 "코드가 돌아간다 + 상대 비교"의 증거다.

## 지금 있는 것 (2026-11-11)
- `rt_control/rt_core` — ROS 2와 무관한 순수 C++17 RT 핵심: SPSC 락프리 링 버퍼, 1 kHz RT 루프(SCHED_FIFO · mlockall · 절대 시각 타이머), 매 주기 할 일(RtStep), 제어 단계(ControlStep: 최신 명령 · 워치독 · 변화량 제한 · **상태 머신**), 백엔드 2종(**SimLag · MuJoCo**), `jitter_bench` 측정기, 단위 테스트 6개(+MuJoCo 1 — 11/11 에 통신 패킷·공유 메모리 seqlock 둘을 더함), 통신 패킷 `wire.hpp`(ZeroMQ 위에 싣는 형식), 공유 메모리 seqlock `shm_seqlock.hpp`
- `rt_control/ros2_adapter` — ROS 2 Jazzy 노드 `rt_control_node`: `/joint_command` 구독 → RT 스레드 → `/joint_states` 100 Hz · `/rt_status` 1 Hz(JSON: wake/work us, 드롭, 워치독, state, backend, rmw). 파라미터 `backend: sim_lag | mujoco`
- `rt_control/zmq_adapter` (11/11) — 같은 `rt_core` 를 ZeroMQ 로 감싼 노드 `rt_zmq_node`: 상태 PUB(1 kHz 까지) · 명령 ROUTER(TARGET → ACK, PING, GET_INFO) · 공유 메모리 `/rt_state`(seqlock, 같은 PC 의 다른 프로세스가 소켓 없이 읽는다 — `rt_state_peek`). 나쁜 패킷·NaN·관절 수 다름은 이유와 함께 거절. [`rt_control/zmq_adapter/README.md`](rt_control/zmq_adapter/README.md)
- `sdk/python/rtsdk` (11/11) — Python SDK: `RobotClient`(상태 받기 · 목표 보내기 · ping · info, 답은 번호로 맞춤, 빠진 상태 세기, 지금 값만 받기 `conflate`), `wire`(패킷, C++ 와 같은 바이트), `bench`(지연 측정), `tools/slow_subscriber.py`(느린 구독자 실험). 끝-대-끝 12단계가 CI 에서 진짜 노드와 돈다. [`sdk/python/README.md`](sdk/python/README.md)
- `dds_bench` — DDS 구현체 × QoS × 크기별 RTT·손실률 측정 → 표② (WSL 실측 16행 포함)
- `fleet` — Mosquitto·TimescaleDB·Grafana(docker-compose), 장치 에이전트(버퍼·재전송·유언·**OTA 진짜 설치**: 내려받기·sha256·A/B 슬롯·자가 점검·롤백, **자율 업데이트**), 실물 보드 에이전트 `pi_agent.py`, 가상 장치 N대, RT 노드 다리, 수집기(1초 묶음 COPY + 통계 + **DB 끊김 backlog** + **지속 세션 옵션**), **OTA 단계 배포기**, **장애 주입 4종 + 판정**, 진단 도구, DB 마이그레이션, 대시보드 생성기(14 패널), MQTT 왕복 시간 도구(`tools/mqtt_rtt.py`), 단위 테스트 4파일 26건(가짜 브로커·DB) + 통합 테스트 · 릴리스 카나리 스크립트
- `scripts/` — `cyclictest_run.sh` · **`jitter_run.sh`**(표① 측정 한 줄, 온도·스로틀 기록), `make_table1/2/3.py`(표), `profile_to_params.py`(로봇 프로필 → ROS 파라미터, 백엔드 선택), **`get_mujoco.sh`**(MuJoCo + Menagerie 모델), **`package_release.sh`**(릴리스 패키지·sha256·매니페스트) · `merge_manifests.py` · `make_release_report.py`, **`check_public.py`**(커밋 전 공개 점검 — 글 파일과 pptx·docx 안까지)
- `.github/workflows/ci.yml` — 3잡: 빌드·단위 테스트·1 kHz 연기 테스트 → 진짜 컨테이너 통합(장애 3종 + OTA 흉내 + **산출물 OTA 정상·깨진 패키지**) · MuJoCo 헤드리스 2모델
- `deploy/` — 운영 층을 클라우드 VM 에(`deploy/ec2/`: 설치 스크립트·자체 CA·보안 그룹 안내, 8883 TLS + 비밀번호) · Pi 서비스 등록(`deploy/pi/`)
- `.github/workflows/release.yml` — **태그 → 패키지(x86_64·aarch64) → 가상 50대 카나리 → GitHub Release 게시** — `docs/RELEASE.md`
- `data_pipeline/` — 로봇 안 고주기 데이터 기록(rosbag2 MCAP) → CSV → 검증 요약(주기·틈·추종 오차)
- `robots/` — 로봇 프로필(SO-101 6 자유도 · **ALLEX 48 자유도**, 위로보틱스 공개 모델 `scripts/get_allex.sh`) · `backends/mujoco/README.md` — MuJoCo 설치·실행, ALLEX 는 §6
- `docs/` — 읽기 가이드(28 항목) · **실험 목록**(한 표) · 구조 · 용어집 · 결정 기록 · 작업 로그 · 설치 안내 · `measurements/`(표①②③ 원본 JSON·txt)

## 빠르게 돌려보기
```bash
cmake -S rt_control/rt_core -B build/rt_core -DCMAKE_BUILD_TYPE=Release && cmake --build build/rt_core -j
ctest --test-dir build/rt_core --output-on-failure          # 링 버퍼 · 제어 단계 · 상태 머신 · 1 kHz 연기(드롭 0)
./build/rt_core/jitter_bench --no-rt --seconds 5
python3 fleet/tests/test_fleet_logic.py && python3 fleet/tests/test_ota_rollout.py && python3 fleet/tests/test_ota_artifact.py && python3 fleet/tests/test_collector_resilience.py
```
관제·OTA·장애 주입(도커 필요): [`fleet/README.md`](fleet/README.md). MuJoCo: [`backends/mujoco/README.md`](backends/mujoco/README.md).

## 문서
- **발표 장표 147장 + 장표마다 설명 문서 1개**(순서도 논리: 로봇을 움직이는 10단계(왕초보 바탕 → 핵심 코드 파일:줄) → 데이터의 길 → 검증 → 공고와 숫자 → 환경 → 어떻게 믿나 → 왜 이렇게 → 결국 로봇은 이렇게 움직인다. 7부 끝에 덧붙임 9장 — ALLEX · 릴리스 → 배포 · 클라우드 운영 층 · 왕복 290 ms · ZeroMQ): [`docs/deck/README.md`](docs/deck/README.md) · 장표 목록 [`docs/deck/SLIDES.md`](docs/deck/SLIDES.md)
- **전체 환경 지도**(개발 PC · Pi · GitHub/CI · 작성 작업본 · 클라우드 서버 — 무엇이 어디서 돌고, 언제 움직이고, 결과를 어떻게 읽나): [`docs/ENVIRONMENT.md`](docs/ENVIRONMENT.md)
- 코드를 읽는 순서: [`docs/READING_GUIDE.md`](docs/READING_GUIDE.md)
- 구조: [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md)
- 용어: [`docs/GLOSSARY.md`](docs/GLOSSARY.md)
- 실험 목록(순서도 + 한 표): [`docs/EXPERIMENTS.md`](docs/EXPERIMENTS.md) · 실험별 상세(왜·결과·처음 읽는 사람을 위한 분석): [`docs/experiments/`](docs/experiments/README.md)
- 왜 이렇게 했나: [`docs/DECISIONS.md`](docs/DECISIONS.md) · 깨진 것과 해결(시간순): [`docs/LOG.md`](docs/LOG.md)
- 설치: WSL 개발 [`docs/SETUP_WSL.md`](docs/SETUP_WSL.md) · 표① 실측(Pi 4 + PREEMPT_RT) [`docs/SETUP_RT_MEASURE.md`](docs/SETUP_RT_MEASURE.md)
- 릴리스 → 배포(태그 하나로 게시까지, 장치의 설치·롤백): [`docs/RELEASE.md`](docs/RELEASE.md) · 운영 층을 클라우드 VM 에(TLS + 비밀번호, 비용, 끄는 법): [`deploy/ec2/README.md`](deploy/ec2/README.md)
- 발표 자료: 2분 영상 대본 [`docs/VIDEO_SCRIPT.md`](docs/VIDEO_SCRIPT.md) · 이력서 문장 [`docs/RESUME_LINES.md`](docs/RESUME_LINES.md) · 작업 상태 요약 [`docs/HANDOVER.md`](docs/HANDOVER.md)

## 작성 방식
설계·검토·측정·해석은 작성자(오문규). 코드 초안과 스크립트·설정 템플릿은 AI 도구(Claude)의 보조로 작성했고,
모든 코드는 작성자가 읽고 설명할 수 있는 수준으로 단순하게 유지한다(`docs/READING_GUIDE.md`의 작성 규칙).
