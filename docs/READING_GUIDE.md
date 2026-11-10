# 코드 읽기 가이드 (분석용)

D0 측정기(1~8번), D1 제어 단계·ROS 2 노드·DDS 측정(9~13번), D2 관제(14~16번), D3 상태 머신·OTA(17~19번),
D4 수집기 내성·장애 주입·CI 2단계(20~23번), D5 MuJoCo 백엔드(24~25번), D6 기록 파이프라인(26번). 전부 합쳐 약 5,400줄.
아래 순서로 읽으면 됩니다. 막히는 곳은 "파일명 + 줄 번호"로 물어보면 그 부분만 설명합니다.
실험이 무엇이었는지는 [`EXPERIMENTS.md`](EXPERIMENTS.md)(한 표), 그 과정의 사고와 해결은 [`LOG.md`](LOG.md)(시간순).
코드가 **어디서** 도는지(개발 PC·Pi·GitHub CI·작업본, 트리거, 결과 읽는 법)는 [`ENVIRONMENT.md`](ENVIRONMENT.md) 를 먼저 한 번 읽는다.
처음이라면 코드보다 **장표**([`deck/README.md`](deck/README.md), 139장)로 전체 길을 먼저 본다 — 왕초보 바탕 지식부터 시작해 명령이 로봇의 움직임이 되기까지 10단계를 위에서 아래로 따라가며 단계마다 그림·핵심 코드(파일:줄)·판단이 나오고(시험·검증은 3부에 번호로), 장표마다 왕초보용 설명 문서(`deck/notes/NNN.docx`)가 있다. 아래 26항목은 그 장표의 코드 장표 순서와 같다.

## 1. 읽는 순서

| # | 파일 | 줄 수 | 이 파일이 하는 일 | 읽으면서 확인할 것 |
|---|---|---|---|---|
| 1 | `rt_control/rt_core/include/rt_core/spsc_ring.hpp` | 약 90 | RT 스레드 → 로깅 스레드로 값을 넘기는 "줄 서지 않는 벨트" | push가 왜 기다리지 않는가 · "한 칸 비워 두기"로 꽉 참/비어 있음을 어떻게 구분하는가 · release / acquire 가 짝을 이루는 자리 |
| 2 | `rt_control/rt_core/include/rt_core/rt_loop.hpp` | 약 90 | 루프 설정(RtConfig)·측정값(Sample)·환경 상태(RtStatus) + 준비 5단계 선언 | Sample의 값 4개가 각각 무엇을 재는가 |
| 3 | `rt_control/rt_core/src/rt_loop.cpp` | 약 150 | 준비 5단계 구현 + `run()`의 for 문 | (a)~(e) 순서 · "절대 시각"을 누적하는 이유 · 첫 주기 period_err가 0인 이유 |
| 4 | `rt_control/rt_core/src/jitter_bench.cpp` | 약 250 | 측정기 실행 파일. 스레드 2개 | main의 5단계 · 로깅 스레드가 종료되는 조건 · 종료 코드가 drops로 정해지는 이유 |
| 5 | `rt_control/rt_core/test/test_spsc_ring.cpp` | 약 100 | 링 버퍼 단위 테스트 | 두 스레드 테스트에서 "드롭은 허용, 역순·중복은 금지"인 이유 |
| 6 | `scripts/cyclictest_run.sh` · `jitter_run.sh` · `lib_thermal.sh` / `scripts/make_table1.py` | 약 60 / 60 / 40 / 200 | 측정(부하·온도·스로틀 기록) → 표① 마크다운 | cyclictest 옵션의 뜻 · 히스토그램에서 p99.9를 구하는 방법 · 왜 온도와 스로틀 플래그를 결과 옆에 적는가 |
| 7 | `.github/workflows/ci.yml` | 약 50 | push마다 자동 빌드·테스트 | 무료 러너에서 무엇을 검증하고(돌아간다) 무엇을 검증 못 하는가(지연 수치) |
| 8 | `robots/so101.yaml` | 약 40 | 로봇 프로필 | 왜 관절 수를 설정에서 읽어 "시작할 때" 버퍼를 잡는가 |
| 9 | `rt_control/rt_core/include/rt_core/rt_step.hpp` | 약 40 | 매 주기 "할 일"의 모양. 측정기는 BusyWorkStep, 노드는 ControlStep | 왜 루프와 "할 일"을 분리했나 (같은 루프로 측정과 제어) |
| 10 | `rt_control/rt_core/include/rt_core/joint_types.hpp` · `backend.hpp` · `sim_lag_backend.cpp` | 약 40 / 30 / 50 | 고정 크기 관절 자료형 · 로봇 쪽 인터페이스 · 1차 지연 흉내 | 왜 std::vector 가 아니라 고정 배열인가 |
| 11 | `rt_control/rt_core/src/control_step.cpp` | 약 110 | 제어 한 주기: 최신 명령 → 워치독 → 변화량 제한 → 로봇 쓰기/읽기 → 상태 벨트 | 명령을 "최신 것만" 쓰는 이유 · 워치독이 "멈춤"을 어떻게 구현하나 |
| 12 | `rt_control/ros2_adapter/src/rt_control_node.cpp` | 약 230 | ROS 2 노드(얇은 껍질). 스레드 3개, 토픽 3개 | 이 파일에 제어 논리가 없는 이유 · 콜백 스레드와 RT 스레드가 어떻게 만나나 |
| 13 | `dds_bench/rtt_bench.py` · `run_matrix.sh` · `scripts/make_table2.py` | 약 180 / 50 / 70 | DDS 왕복 지연·손실 측정 → 표② | 왜 한 방향이 아니라 왕복인가 · reliable 과 best_effort 의 차이 |
| 14 | `fleet/agent/device_agent.py` | 약 150 | 장치 한 대: 발행 · 끊기면 버퍼 · 재접속 시 재전송 · 유언 | 끊긴 동안 어디에 쌓이고 언제 비우나 · 왜 재전송은 QoS 1 인가 |
| 15 | `fleet/collector/collector.py` · `fleet/db/init.sql` | 약 220 / 60 | 구독 → 1초 묶음 COPY 적재 → 통계 | 왜 묶음인가 · 수집 지연에 1초가 더해지는 이유 · 유실을 어떻게 세나(seq) |
| 16 | `fleet/grafana/make_dashboard.py` · `fleet/docker-compose.yml` | 약 130 / 70 | 패널 14개의 SQL · 컨테이너 3개(+수집기 선택) | 각 패널이 어느 표의 어느 열을 보나 |
| 17 | `rt_control/rt_core/include/rt_core/robot_state_machine.hpp` · `src/robot_state_machine.cpp` | 약 60 / 90 | 로봇 상태 5개(INIT·READY·RUNNING·FAULT·RECOVERING)와 사건 5개, 허용 전이 **표** 하나 | "표에 없는 전이는 거절하고 센다"가 왜 if 문 더미보다 나은가 · `control_step.cpp` 의 `update_state_machine()` 이 언제 어떤 사건을 넣나 |
| 18 | `fleet/agent/device_agent.py` 의 `on_message` · `apply_ota` | (+40) | 장치 쪽 OTA: ota 명령 → 별도 스레드에서 "적용"(updating → 새 버전) · bad 면 fault · ota_rollback 은 직전 버전 복원 | 왜 적용을 별도 스레드로 하나(텔레메트리가 계속 나가야 서버가 본다) · 겹치는 ota 를 거절하는 이유 |
| 19 | `fleet/ota/rollout.py` | 약 260 | 서버 쪽 OTA: 장치 찾기 → 5%·50%·100% 단계 → 적용 대기 → 헬스 게이트 → 롤백(시간 측정) → events·ota_rollouts 기록 | 롤백을 "장치"가 아니라 "서버"가 결정하는 이유 · 헬스 게이트가 보는 것은 state 하나뿐인 이유(단순함) · 50대에서 나쁜 펌웨어가 닿는 장치는 왜 3대인가 |
| 20 | `fleet/collector/collector.py` (D4 판) | 약 300 | Batch 단위 backlog: DB 쓰기 실패 → 묶음 보관 → 매초 재시도 → 상한 넘으면 오래된 것 버림. `--qos 1` 지속 세션 | 왜 디스크가 아니라 메모리 backlog 인가 · 상한 20만 행의 근거 · QoS 0 과 1 의 비용 차이 |
| 21 | `fleet/chaos/inject.py` · `chaos/assert_results.py` | 약 330 / 90 | 장애 4종을 주입하고 감지·복구·유실을 DB 로 잰다. 판정 규칙 | 각 장애에서 "복구됨"의 정의가 무엇인가(첫 메시지/전 장치/backlog 0) · 유실을 seq 로 세는 식 · broker 장애에서 유실 ≤ 장치 수를 허용하는 이유 |
| 22 | `fleet/tests/fake_mqtt.py` · `fake_psycopg.py` · `test_ota_rollout.py` · `test_collector_resilience.py` | 약 180 / 110 / 130 / 120 | 브로커·DB 없이 끝-대-끝을 돌리는 가짜들과 그 위의 테스트 | 가짜 브로커가 "동기 전달"인 것이 테스트를 어떻게 단순하게 하나 · 어디까지가 가짜고 어디부터가 진짜(integration.sh)인가 |
| 23 | `.github/workflows/ci.yml` · `fleet/tests/integration.sh` · `fleet/db/migrate.py` | 약 110 / 60 / 60 | CI 3잡(rt_core → fleet_integration · mujoco) · 진짜 컨테이너 통합 테스트 · 번호 붙은 마이그레이션 | 1단계와 2단계가 각각 무엇을 증명하나 · init.sql 과 migrations 를 둘 다 두는 이유 |
| 24 | `rt_control/rt_core/include/rt_core/mujoco_backend.hpp` · `src/mujoco_backend.cpp` | 약 90 / 230 | MuJoCo 를 Backend 로: 모델 로드 → 걸음 맞추기(ceil) → 관절 이름/액추에이터 연결 → 매 주기 ctrl 쓰고 mj_step, qpos/qvel 읽기 | init 에서만 할당하고 RT 에서는 안 하는 경계가 어디인가 · substeps 를 올림(ceil)으로 잡는 이유 · 관절 이름이 틀렸을 때 무엇을 출력하나 |
| 25 | `rt_control/rt_core/test/test_mujoco_backend.cpp` · `scripts/get_mujoco.sh` · `rt_control_node.cpp` 의 `make_backend()` | 약 130 / 60 / 50 | 물리 모델 위 2000주기 테스트(움직임 + 한 주기 비용 p99) · 설치 · 파라미터로 백엔드 고르기 | 테스트가 p99 < 900 us 를 보는 이유(1 kHz 안에 물리가 들어오나) · 노드가 MuJoCo 없이 빌드됐을 때 어떻게 실패하나(조용히 바꾸지 않는다) |
| 26 | `data_pipeline/record.sh` · `data_pipeline/bag_to_csv.py` | 약 20 / 230 | rosbag2(MCAP) 기록 → CSV 3개 + 검증 요약(주기·틈·추종 오차) | "로깅"과 "관제"가 왜 다른 길인가 · 추종 오차에서 중력 처짐을 어떻게 읽나 |
| 27 | `fleet/agent/ota_apply.py` · `fleet/ota/rollout.py`(`--manifest`) · `scripts/package_release.sh` · `.github/workflows/release.yml` · `docs/RELEASE.md` | 약 230 / +80 / 100 / 110 | 릴리스 → 배포: 패키지·매니페스트 → 가상 50대 카나리 → 게시 → 장치의 내려받기·sha256·A/B 슬롯·자가 점검·전환, Pi 자율 업데이트 | 왜 A/B 슬롯인가(전원 차단) · 자가 점검이 헬스 게이트보다 먼저 거부하는 이유 · 왜 러너가 실물에 직접 배포하지 않나 · sha256 과 서명의 차이 |

## 2. 모든 파일에 던지는 질문 3개

1. 이 파일이 없으면 무엇이 깨지는가?
2. 이 파일에 "기다리는" 코드(sleep, lock, 파일 쓰기, 메모리 할당)가 있는가? 있다면 RT 스레드에서 도는가?
3. 숫자(상수)마다 단위와 이유가 적혀 있는가? 없는 것이 있으면 그것이 질문거리다.

## 3. 직접 돌려볼 것 (WSL, 5분)

```bash
cd ~/rt-robot-data-infra
cmake -S rt_control/rt_core -B build/rt_core -DCMAKE_BUILD_TYPE=Release
cmake --build build/rt_core -j
./build/rt_core/test_spsc_ring                                   # "OK: spsc_ring"
./build/rt_core/jitter_bench --no-rt --seconds 5 --label wsl_generic \
     --json docs/measurements/jitter_wsl_generic.json            # 표 출력 + JSON
sudo ./build/rt_core/jitter_bench --prio 80 --seconds 5 --label wsl_fifo    # SCHED_FIFO 적용 시도
python3 scripts/make_table1.py --jitter 'docs/measurements/jitter_*.json'  # 표① 형태로 보기
```
WSL 수치는 **참고값**입니다(실시간 커널 아님). 보면서 생각할 것: "이 숫자가 왜 1 ms 주기보다 큰가?"

## 3-1. 직접 돌려볼 것 (D3~D5, 브로커·DB 없이 1분)
```bash
./build/rt_core/test_state_machine                 # "OK: state_machine"  — 허용 전이·거절 전이·STOP
python3 fleet/tests/test_ota_rollout.py            # 가짜 브로커 위 가상 20대: 정상 배포 / 나쁜 펌웨어 롤백(1대에서 멈춤) / 시간 초과
python3 fleet/tests/test_collector_resilience.py   # DB 죽음 → backlog → 복귀, 상한, 지속 세션
```
진짜 컨테이너로 전체: `bash fleet/tests/integration.sh` (fleet/README.md 10번). MuJoCo: `backends/mujoco/README.md`.

## 4. 코드 작성 규칙 (이 저장소 전체)

- 한 함수는 한 화면(40줄) 안에. 넘으면 쪼갠다.
- 압축 표현 금지: 람다로 꼬지 않기, 삼항 연산자 중첩 금지, 매크로 금지(테스트 포함).
- 비트 연산·memory_order 같은 것은 반드시 옆에 "왜"를 적는다.
- 모든 파일 머리에 "파일 역할 / 읽는 순서 / 왜 이렇게".
- 주석은 '무엇을 하는가'가 아니라 '왜 이렇게 하는가'. 한국어.
- 숫자 상수에는 이름과 단위 (`kRingSize`, `period_ns`, `work_us`).
- 결정은 `docs/DECISIONS.md`, 깨진 것은 `docs/LOG.md`에 그날 적는다.
- **"왜 하는가"와 "결과를 보고 어떻게 판단했는가"는 반드시 문서에 남는다** (채팅·머릿속에만 두지 않는다, 2026-11-05 규칙):
  - 개념 설명(이 용어가 무엇이고 왜 중요한가) → `docs/GLOSSARY.md` (예: PREEMPT_RT 항목의 "무엇이 다른가")
  - 실험을 왜 했고 무엇을 물었나 → `docs/EXPERIMENTS.md` 의 "질문" 열
  - 결과를 보고 내린 판단(이 숫자가 뜻하는 것, 정상/비정상, 다음에 할 일) → `docs/LOG.md` 의 "읽기:" 줄 + `EXPERIMENTS.md` 의 "결과" 열
  - 왜 이렇게 만들었나, 버린 대안 → `docs/DECISIONS.md`
  - 측정 안내의 "읽는 법" 표(무엇이 나와야 정상인가) → 해당 `SETUP_*.md`
  채팅에서 한 설명은 같은 날 위 자리 중 하나로 옮긴다. 옮기지 않은 설명은 없는 것과 같다.
