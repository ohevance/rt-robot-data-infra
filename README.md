# rt-robot-data-infra

로봇과 무관한(robot-agnostic) **실시간 제어 + 데이터 인프라** 저장소.
ROS 2 / PREEMPT_RT / DDS / 장치 텔레메트리 관제 / OTA / 장애 복구 / MuJoCo / CI — 휴머노이드 로봇 회사의
"실시간 제어 및 데이터 인프라" 직무를 겨냥해 2026년 11월에 만들고 있다. (작업 중)

![ci](https://github.com/ohevance/rt-robot-data-infra/actions/workflows/ci.yml/badge.svg)

| 직무 요구 | 산출물 | 수치 | 상태 |
|---|---|---|---|
| ① 실시간 Linux 미들웨어, ROS 2/DDS | `rt_control/rt_core` RT 루프 + 측정기 + 제어 단계 + 상태 머신, `rt_control/ros2_adapter` ROS 2 노드, `dds_bench` | 표① 지연·지터 (p99.9/max) · 표② DDS 손실·지연 · 노드 `rt_status`(wake/work us, state) | 작성 완료, WSL 실행 확인(노드·DDS). **Pi 4 실측 완료(11/04~05)**: 일반 → PREEMPT_RT → 고정 → 격리, `table1_pi4.md` |
| ② 실시간 로깅·모니터링·시각화·업데이트 | `fleet` 수집 → TimescaleDB → Grafana(14 패널), OTA 단계 배포·헬스 게이트·자동 롤백, 장애 주입 4종 | 표③-1 처리량·전달 지연 · 표③-2 장애 감지·복구·유실 · 표③-3 OTA 롤백 시간 | 작성 완료(D3~D4), WSL 관제 실행 확인(D2), 장애·OTA 실측 대기 |
| ③ 센서 스트리밍·로깅·전처리 자동화 | `fleet` 장치 에이전트(가상 50 + RT 노드 1), store-and-forward, 수집기 backlog, QoS 0/1 · **`data_pipeline`** 로봇 안 100 Hz 기록(rosbag2 MCAP) → CSV → 검증 요약 | 초당 메시지, 전달 지연 p95, 유실 % · 기록 실제 Hz·틈·추종 오차 | 작성 완료, WSL 실행 확인(기록 11/05) |
| ④ 시뮬레이션 · CI | `rt_core/mujoco_backend` (Menagerie SO-ARM100), CI 3잡(단위 → 통합 컨테이너 · MuJoCo 헤드리스) | CI 배지, 테스트 수(C++ 5 · Python 3 · 통합 1), 물리 한 주기 비용 p99 | 작성 완료(D5), WSL/CI 첫 실행 대기 |

## 숫자 한눈에 (2026-11-04 기준 — 어디서 잰 값인지가 숫자만큼 중요하다)

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
| 같은 것, WSL 단독 / ROS 2 노드 안 `work_us`(제어+물리) | 4.9 / 6.3 / 20.8 us · 41 / 145 / 247 us | WSL2 참고값 | `docs/LOG.md` 11/04 |
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
| 큐 상한을 넘겼을 때 (실험) | 7.5분 공백 중 마지막 49초분 2,450개 유실 | WSL2 | `docs/LOG.md` 11/04 |

실시간 **지연의 진짜 값**은 Raspberry Pi 4 + PREEMPT_RT 실측(위 Pi 줄들)이다. 한 변수씩 바꾼 사슬(커널 → 고정 → 격리)과 그 이유는 [`docs/EXPERIMENTS.md`](docs/EXPERIMENTS.md) 의 순서도, 각 실험의 상세는 [`docs/experiments/`](docs/experiments/README.md). WSL 값은 "코드가 돌아간다 + 상대 비교"의 증거다.

## 지금 있는 것 (D6, 2026-11-04)
- `rt_control/rt_core` — ROS 2와 무관한 순수 C++17 RT 핵심: SPSC 락프리 링 버퍼, 1 kHz RT 루프(SCHED_FIFO · mlockall · 절대 시각 타이머), 매 주기 할 일(RtStep), 제어 단계(ControlStep: 최신 명령 · 워치독 · 변화량 제한 · **상태 머신**), 백엔드 2종(**SimLag · MuJoCo**), `jitter_bench` 측정기, 단위 테스트 4개(+MuJoCo 1)
- `rt_control/ros2_adapter` — ROS 2 Jazzy 노드 `rt_control_node`: `/joint_command` 구독 → RT 스레드 → `/joint_states` 100 Hz · `/rt_status` 1 Hz(JSON: wake/work us, 드롭, 워치독, state, backend, rmw). 파라미터 `backend: sim_lag | mujoco`
- `dds_bench` — DDS 구현체 × QoS × 크기별 RTT·손실률 측정 → 표② (WSL 실측 16행 포함)
- `fleet` — Mosquitto·TimescaleDB·Grafana(docker-compose), 장치 에이전트(버퍼·재전송·유언·**OTA 적용/롤백**), 가상 장치 N대, RT 노드 다리, 수집기(1초 묶음 COPY + 통계 + **DB 끊김 backlog** + **지속 세션 옵션**), **OTA 단계 배포기**, **장애 주입 4종 + 판정**, 진단 도구, DB 마이그레이션, 대시보드 생성기(14 패널), 단위 테스트 3개(가짜 브로커·DB) + 통합 테스트 스크립트
- `scripts/` — `cyclictest_run.sh` · **`jitter_run.sh`**(표① 측정 한 줄, 온도·스로틀 기록), `make_table1/2/3.py`(표), `profile_to_params.py`(로봇 프로필 → ROS 파라미터, 백엔드 선택), **`get_mujoco.sh`**(MuJoCo + Menagerie 모델)
- `.github/workflows/ci.yml` — 3잡: 빌드·단위 테스트·1 kHz 연기 테스트 → 진짜 컨테이너 통합(장애 3종 + OTA) · MuJoCo 헤드리스
- `data_pipeline/` — 로봇 안 고주기 데이터 기록(rosbag2 MCAP) → CSV → 검증 요약(주기·틈·추종 오차)
- `robots/` — 로봇 프로필(SO-101 · ALLEX 자리) · `backends/mujoco/README.md` — MuJoCo 설치·실행
- `docs/` — 읽기 가이드(26 항목) · **실험 목록**(한 표) · 구조 · 용어집 · 결정 기록 · 작업 로그 · 설치 안내 · `measurements/`(표①②③ 원본 JSON·txt)

## 빠르게 돌려보기
```bash
cmake -S rt_control/rt_core -B build/rt_core -DCMAKE_BUILD_TYPE=Release && cmake --build build/rt_core -j
ctest --test-dir build/rt_core --output-on-failure          # 링 버퍼 · 제어 단계 · 상태 머신 · 1 kHz 연기(드롭 0)
./build/rt_core/jitter_bench --no-rt --seconds 5
python3 fleet/tests/test_fleet_logic.py && python3 fleet/tests/test_ota_rollout.py && python3 fleet/tests/test_collector_resilience.py
```
관제·OTA·장애 주입(도커 필요): [`fleet/README.md`](fleet/README.md). MuJoCo: [`backends/mujoco/README.md`](backends/mujoco/README.md).

## 문서
- 코드를 읽는 순서: [`docs/READING_GUIDE.md`](docs/READING_GUIDE.md)
- 구조: [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md)
- 용어: [`docs/GLOSSARY.md`](docs/GLOSSARY.md)
- 실험 목록(순서도 + 한 표): [`docs/EXPERIMENTS.md`](docs/EXPERIMENTS.md) · 실험별 상세(왜·결과·처음 읽는 사람을 위한 분석): [`docs/experiments/`](docs/experiments/README.md)
- 왜 이렇게 했나: [`docs/DECISIONS.md`](docs/DECISIONS.md) · 깨진 것과 해결(시간순): [`docs/LOG.md`](docs/LOG.md)
- 설치: WSL 개발 [`docs/SETUP_WSL.md`](docs/SETUP_WSL.md) · 표① 실측(Pi 4 + PREEMPT_RT) [`docs/SETUP_RT_MEASURE.md`](docs/SETUP_RT_MEASURE.md)
- 발표 자료: 2분 영상 대본 [`docs/VIDEO_SCRIPT.md`](docs/VIDEO_SCRIPT.md) · 이력서 문장 [`docs/RESUME_LINES.md`](docs/RESUME_LINES.md) · 인수인계 [`docs/HANDOVER.md`](docs/HANDOVER.md)

## 작성 방식
설계·검토·측정·해석은 작성자(오문규). 코드 초안과 스크립트·설정 템플릿은 AI 도구(Claude)의 보조로 작성했고,
모든 코드는 작성자가 읽고 설명할 수 있는 수준으로 단순하게 유지한다(`docs/READING_GUIDE.md`의 작성 규칙).
