# 코드 읽기 가이드 (분석용)

D0 에는 측정기(1~8번), D1 에는 제어 단계·ROS 2 노드·DDS 측정(9~13번)이 들어왔습니다. 전부 합쳐 약 1,900줄.
아래 순서로 읽으면 됩니다. 막히는 곳은 "파일명 + 줄 번호"로 물어보면 그 부분만 설명합니다.

## 1. 읽는 순서

| # | 파일 | 줄 수 | 이 파일이 하는 일 | 읽으면서 확인할 것 |
|---|---|---|---|---|
| 1 | `rt_control/rt_core/include/rt_core/spsc_ring.hpp` | 약 90 | RT 스레드 → 로깅 스레드로 값을 넘기는 "줄 서지 않는 벨트" | push가 왜 기다리지 않는가 · "한 칸 비워 두기"로 꽉 참/비어 있음을 어떻게 구분하는가 · release / acquire 가 짝을 이루는 자리 |
| 2 | `rt_control/rt_core/include/rt_core/rt_loop.hpp` | 약 90 | 루프 설정(RtConfig)·측정값(Sample)·환경 상태(RtStatus) + 준비 5단계 선언 | Sample의 값 4개가 각각 무엇을 재는가 |
| 3 | `rt_control/rt_core/src/rt_loop.cpp` | 약 150 | 준비 5단계 구현 + `run()`의 for 문 | (a)~(e) 순서 · "절대 시각"을 누적하는 이유 · 첫 주기 period_err가 0인 이유 |
| 4 | `rt_control/rt_core/src/jitter_bench.cpp` | 약 250 | 측정기 실행 파일. 스레드 2개 | main의 5단계 · 로깅 스레드가 종료되는 조건 · 종료 코드가 drops로 정해지는 이유 |
| 5 | `rt_control/rt_core/test/test_spsc_ring.cpp` | 약 100 | 링 버퍼 단위 테스트 | 두 스레드 테스트에서 "드롭은 허용, 역순·중복은 금지"인 이유 |
| 6 | `scripts/cyclictest_run.sh` / `scripts/make_table1.py` | 약 60 / 150 | 측정 → 표① 마크다운 | cyclictest 옵션의 뜻 · 히스토그램에서 p99.9를 구하는 방법 |
| 7 | `.github/workflows/ci.yml` | 약 50 | push마다 자동 빌드·테스트 | 무료 러너에서 무엇을 검증하고(돌아간다) 무엇을 검증 못 하는가(지연 수치) |
| 8 | `robots/so101.yaml` | 약 40 | 로봇 프로필 | 왜 관절 수를 설정에서 읽어 "시작할 때" 버퍼를 잡는가 |
| 9 | `rt_control/rt_core/include/rt_core/rt_step.hpp` | 약 40 | 매 주기 "할 일"의 모양. 측정기는 BusyWorkStep, 노드는 ControlStep | 왜 루프와 "할 일"을 분리했나 (같은 루프로 측정과 제어) |
| 10 | `rt_control/rt_core/include/rt_core/joint_types.hpp` · `backend.hpp` · `sim_lag_backend.cpp` | 약 40 / 30 / 50 | 고정 크기 관절 자료형 · 로봇 쪽 인터페이스 · 1차 지연 흉내 | 왜 std::vector 가 아니라 고정 배열인가 |
| 11 | `rt_control/rt_core/src/control_step.cpp` | 약 110 | 제어 한 주기: 최신 명령 → 워치독 → 변화량 제한 → 로봇 쓰기/읽기 → 상태 벨트 | 명령을 "최신 것만" 쓰는 이유 · 워치독이 "멈춤"을 어떻게 구현하나 |
| 12 | `rt_control/ros2_adapter/src/rt_control_node.cpp` | 약 230 | ROS 2 노드(얇은 껍질). 스레드 3개, 토픽 3개 | 이 파일에 제어 논리가 없는 이유 · 콜백 스레드와 RT 스레드가 어떻게 만나나 |
| 13 | `dds_bench/rtt_bench.py` · `run_matrix.sh` · `scripts/make_table2.py` | 약 180 / 50 / 70 | DDS 왕복 지연·손실 측정 → 표② | 왜 한 방향이 아니라 왕복인가 · reliable 과 best_effort 의 차이 |

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

## 4. 코드 작성 규칙 (이 저장소 전체)

- 한 함수는 한 화면(40줄) 안에. 넘으면 쪼갠다.
- 압축 표현 금지: 람다로 꼬지 않기, 삼항 연산자 중첩 금지, 매크로 금지(테스트 포함).
- 비트 연산·memory_order 같은 것은 반드시 옆에 "왜"를 적는다.
- 모든 파일 머리에 "파일 역할 / 읽는 순서 / 왜 이렇게".
- 주석은 '무엇을 하는가'가 아니라 '왜 이렇게 하는가'. 한국어.
- 숫자 상수에는 이름과 단위 (`kRingSize`, `period_ns`, `work_us`).
- 결정은 `docs/DECISIONS.md`, 깨진 것은 `docs/LOG.md`에 그날 적는다.
