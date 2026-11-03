# rt-robot-data-infra

로봇과 무관한(robot-agnostic) **실시간 제어 + 데이터 인프라** 저장소.
ROS 2 / PREEMPT_RT / DDS / 장치 텔레메트리 관제 / OTA / CI — 휴머노이드 로봇 회사의
"실시간 제어 및 데이터 인프라" 직무를 겨냥해 2026년 11월에 만들고 있다. (작업 중)

![ci](https://github.com/<아이디>/rt-robot-data-infra/actions/workflows/ci.yml/badge.svg)

| 직무 요구 | 산출물 | 수치 | 상태 |
|---|---|---|---|
| ① 실시간 Linux 미들웨어, ROS 2/DDS | `rt_control/rt_core` RT 루프 + 측정기 + 제어 단계, `rt_control/ros2_adapter` ROS 2 노드, `dds_bench` | 표① 지연·지터 (p99.9/max) · 표② DDS 손실·지연 · 노드 `rt_status` | rt_core·노드·dds_bench 작성 완료, WSL 빌드·측정 대기 |
| ② 실시간 로깅·모니터링·시각화·업데이트 | `fleet` 수집 → TimescaleDB → Grafana, OTA 단계 배포·롤백 | 롤백 시간, 장애 복구 시간 | 예정 (D3~D5) |
| ③ 센서 스트리밍·로깅·전처리 자동화 | `fleet` 장치 에이전트(가상 50 + 실물 1), `data_pipeline` | 초당 메시지, p95 지연 | 예정 (D5~D8) |
| ④ 시뮬레이션 · CI | `backends/mujoco` SO-101, `.github/workflows/ci.yml` | CI 배지, 테스트 수 | CI 1단계 완료 |

## 지금 있는 것 (D1, 2026-11-03)
- `rt_control/rt_core` — ROS 2와 무관한 순수 C++17 RT 핵심: SPSC 락프리 링 버퍼, 1 kHz RT 루프(SCHED_FIFO · mlockall · 절대 시각 타이머), 매 주기 할 일(RtStep), 제어 단계(ControlStep: 최신 명령 · 워치독 · 변화량 제한), 1차 지연 시뮬 백엔드, `jitter_bench` 측정기, 단위 테스트 3개
- `rt_control/ros2_adapter` — ROS 2 Jazzy 노드 `rt_control_node`: `/joint_command` 구독 → RT 스레드 → `/joint_states` 100 Hz · `/rt_status` 1 Hz(JSON)
- `dds_bench` — DDS 구현체 × QoS × 크기별 RTT·손실률 측정 → 표②
- `scripts/` — `cyclictest_run.sh`(표① 측정), `make_table1.py`(표①), `make_table2.py`(표②), `profile_to_params.py`(로봇 프로필 → ROS 파라미터)
- `.github/workflows/ci.yml` — push마다 빌드 · 단위 테스트 · 1 kHz 연기 테스트(드롭 0)
- `robots/` — 로봇 프로필(SO-101 · ALLEX 자리)
- `docs/` — 읽기 가이드 · 구조 · 용어집 · 결정 기록 · 작업 로그 · 설치 안내

## 빠르게 돌려보기
```bash
cmake -S rt_control/rt_core -B build/rt_core -DCMAKE_BUILD_TYPE=Release && cmake --build build/rt_core -j
ctest --test-dir build/rt_core --output-on-failure
./build/rt_core/jitter_bench --no-rt --seconds 5
```

## 문서
- 코드를 읽는 순서: [`docs/READING_GUIDE.md`](docs/READING_GUIDE.md)
- 구조: [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md)
- 용어: [`docs/GLOSSARY.md`](docs/GLOSSARY.md)
- 왜 이렇게 했나: [`docs/DECISIONS.md`](docs/DECISIONS.md) · 깨진 것과 해결: [`docs/LOG.md`](docs/LOG.md)
- 설치: WSL 개발 [`docs/SETUP_WSL.md`](docs/SETUP_WSL.md) · 표① 실측 [`docs/SETUP_RT_MEASURE.md`](docs/SETUP_RT_MEASURE.md)

## 작성 방식
설계·검토·측정·해석은 작성자(오문규). 코드 초안과 스크립트·설정 템플릿은 AI 도구(Claude)의 보조로 작성했고,
모든 코드는 작성자가 읽고 설명할 수 있는 수준으로 단순하게 유지한다(`docs/READING_GUIDE.md`의 작성 규칙).
