# rt-robot-data-infra

로봇과 무관한(robot-agnostic) **실시간 제어 + 데이터 인프라** 저장소.
ROS 2 / PREEMPT_RT / DDS / 장치 텔레메트리 관제 / OTA / 장애 복구 / MuJoCo / CI — 휴머노이드 로봇 회사의
"실시간 제어 및 데이터 인프라" 직무를 겨냥해 2026년 11월에 만들고 있다. (작업 중)

![ci](https://github.com/ohevance/rt-robot-data-infra/actions/workflows/ci.yml/badge.svg)

| 직무 요구 | 산출물 | 수치 | 상태 |
|---|---|---|---|
| ① 실시간 Linux 미들웨어, ROS 2/DDS | `rt_control/rt_core` RT 루프 + 측정기 + 제어 단계 + 상태 머신, `rt_control/ros2_adapter` ROS 2 노드, `dds_bench` | 표① 지연·지터 (p99.9/max) · 표② DDS 손실·지연 · 노드 `rt_status`(wake/work us, state) | 작성 완료, WSL 실행 확인(노드·DDS). Pi 실측 D6~D8 |
| ② 실시간 로깅·모니터링·시각화·업데이트 | `fleet` 수집 → TimescaleDB → Grafana(14 패널), OTA 단계 배포·헬스 게이트·자동 롤백, 장애 주입 4종 | 표③-1 처리량·전달 지연 · 표③-2 장애 감지·복구·유실 · 표③-3 OTA 롤백 시간 | 작성 완료(D3~D4), WSL 관제 실행 확인(D2), 장애·OTA 실측 대기 |
| ③ 센서 스트리밍·로깅·전처리 자동화 | `fleet` 장치 에이전트(가상 50 + RT 노드 1), store-and-forward, 수집기 backlog, QoS 0/1 | 초당 메시지, 전달 지연 p95, 유실 % | 작성 완료 |
| ④ 시뮬레이션 · CI | `rt_core/mujoco_backend` (Menagerie SO-ARM100), CI 3잡(단위 → 통합 컨테이너 · MuJoCo 헤드리스) | CI 배지, 테스트 수(C++ 5 · Python 3 · 통합 1), 물리 한 주기 비용 p99 | 작성 완료(D5), WSL/CI 첫 실행 대기 |

## 지금 있는 것 (D5, 2026-11-03)
- `rt_control/rt_core` — ROS 2와 무관한 순수 C++17 RT 핵심: SPSC 락프리 링 버퍼, 1 kHz RT 루프(SCHED_FIFO · mlockall · 절대 시각 타이머), 매 주기 할 일(RtStep), 제어 단계(ControlStep: 최신 명령 · 워치독 · 변화량 제한 · **상태 머신**), 백엔드 2종(**SimLag · MuJoCo**), `jitter_bench` 측정기, 단위 테스트 4개(+MuJoCo 1)
- `rt_control/ros2_adapter` — ROS 2 Jazzy 노드 `rt_control_node`: `/joint_command` 구독 → RT 스레드 → `/joint_states` 100 Hz · `/rt_status` 1 Hz(JSON: wake/work us, 드롭, 워치독, state, backend, rmw). 파라미터 `backend: sim_lag | mujoco`
- `dds_bench` — DDS 구현체 × QoS × 크기별 RTT·손실률 측정 → 표② (WSL 실측 16행 포함)
- `fleet` — Mosquitto·TimescaleDB·Grafana(docker-compose), 장치 에이전트(버퍼·재전송·유언·**OTA 적용/롤백**), 가상 장치 N대, RT 노드 다리, 수집기(1초 묶음 COPY + 통계 + **DB 끊김 backlog** + **지속 세션 옵션**), **OTA 단계 배포기**, **장애 주입 4종 + 판정**, 진단 도구, DB 마이그레이션, 대시보드 생성기(14 패널), 단위 테스트 3개(가짜 브로커·DB) + 통합 테스트 스크립트
- `scripts/` — `cyclictest_run.sh`(표① 측정), `make_table1/2/3.py`(표), `profile_to_params.py`(로봇 프로필 → ROS 파라미터, 백엔드 선택), **`get_mujoco.sh`**(MuJoCo + Menagerie 모델)
- `.github/workflows/ci.yml` — 3잡: 빌드·단위 테스트·1 kHz 연기 테스트 → 진짜 컨테이너 통합(장애 3종 + OTA) · MuJoCo 헤드리스
- `robots/` — 로봇 프로필(SO-101 · ALLEX 자리) · `backends/mujoco/README.md` — MuJoCo 설치·실행
- `docs/` — 읽기 가이드(25 항목) · 구조 · 용어집 · 결정 기록 · 작업 로그 · 설치 안내 · `measurements/`(표①②③ 원본 JSON)

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
- 왜 이렇게 했나: [`docs/DECISIONS.md`](docs/DECISIONS.md) · 깨진 것과 해결: [`docs/LOG.md`](docs/LOG.md)
- 설치: WSL 개발 [`docs/SETUP_WSL.md`](docs/SETUP_WSL.md) · 표① 실측 [`docs/SETUP_RT_MEASURE.md`](docs/SETUP_RT_MEASURE.md)

## 작성 방식
설계·검토·측정·해석은 작성자(오문규). 코드 초안과 스크립트·설정 템플릿은 AI 도구(Claude)의 보조로 작성했고,
모든 코드는 작성자가 읽고 설명할 수 있는 수준으로 단순하게 유지한다(`docs/READING_GUIDE.md`의 작성 규칙).
