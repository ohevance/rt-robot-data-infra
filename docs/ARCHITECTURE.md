# 구조 (ARCHITECTURE)

## 1. 2주 완성본의 전체 그림

```
 [MuJoCo 시뮬 로봇 SO-101] <== 1 kHz ==> [RT 제어 노드 : C++ 순수 RT 핵심 + 얇은 ROS 2 어댑터]   ... 공고 ①
                                                   |
                                                   | 텔레메트리(상태·지연·온도) 1~10 Hz
                                                   v
 [가상 장치 x50 (소프트웨어 에이전트)] ---MQTT---> [관제 서버 : 수집기 -> TimescaleDB -> Grafana]     ... 공고 ②③
 [실물 장치 x1 (Pi 5, 도착 시)]      ---MQTT--->        |         <---- OTA 단계 배포(5%->50%->100%) · 롤백
                                                   |
 [GitHub Actions CI] : push마다 빌드 + 단위 테스트 + MuJoCo 헤드리스 테스트 -> 초록 배지               ... 공고 ④
```

| 공고 항목 | 이 저장소에서 답하는 것 | 수치 |
|---|---|---|
| ① 실시간 Linux 미들웨어 · ROS 2/DDS | `rt_control` (RT 커널 실측 + 1 kHz 루프) · `dds_bench` | 표① 지연·지터 · 표② DDS 손실·지연 |
| ② 로깅·모니터링·시각화·업데이트 | `fleet` (수집 → Timescale → Grafana · OTA · 롤백) | 롤백 완료 시간 · 장애 복구 시간 |
| ③ 센서 스트리밍·로깅·전처리 | `fleet` 에이전트(장치→서버 1 Hz) · `data_pipeline`(로봇 안 100 Hz 기록 → CSV → 검증 요약) | 초당 메시지 수 · p95 지연 · 기록 주기·틈·추종 오차 |
| ④ 시뮬레이션 · CI | `backends/mujoco` · `.github/workflows` | CI 배지 · 테스트 수 |

## 2. 오늘(D0)까지 만든 부분: rt_core

```
   +-------------------------------+            +-------------------------------+
   |  RT 스레드 (main)             |            |  로깅 스레드 (일반 우선순위)    |
   |  RtLoop::run()                |            |  logger_thread_main()         |
   |                               |   SPSC     |                               |
   |  매 1 ms:                     |   링 버퍼  |  비어 있으면 1 ms 쉼           |
   |   (a) 목표 시각까지 잠         |  ------->  |  꺼내서 vector 에 모음          |
   |   (b) 얼마나 늦게 깼나 측정    |  push()    |  RT 끝나면 남은 것 비우고 종료   |
   |   (c) 제어 계산 흉내 50 us     |  (안 기다림)|                               |
   |   (d) 샘플을 벨트에 올림       |            |  끝난 뒤: 정렬 → p50/p99/p99.9  |
   |   (e) 다음 목표 = 목표 + 1 ms  |            |          → 화면·JSON·CSV       |
   +-------------------------------+            +-------------------------------+
         파일을 절대 만지지 않는다                        파일은 여기서만 만진다
```

**핵심 규칙 한 줄**: RT 스레드 안에는 "기다리는 것"(락·파일·메모리 할당·상대 시간 sleep)이 없다.

## 3. 왜 ROS 2와 분리했나

```
   rt_core (순수 C++17 + POSIX)  <--- 여기만 보면 RT 규칙이 다 보인다. 어디서나 빌드·테스트.
        ^
        | 링크
   ros2_adapter (얇은 rclcpp 노드) <--- 토픽 발행/구독만. ROS 2 설치된 곳에서만 빌드.
```
- 이득: CI 무료 러너(ROS 2 없음)에서도 핵심이 테스트된다 · 미들웨어 교체(ROS 2 ↔ ZeroMQ)가 어댑터 교체가 된다 · 면접에서 "RT 코드가 어디 있나"에 파일 하나로 답한다.
- 비용: 어댑터 한 겹이 더 있다. (2주 계획에서는 D3에 추가)

## 4. 로봇 프로필 (`robots/*.yaml`)

제어 노드는 시작할 때 프로필을 한 번 읽어 관절 수 N만큼 **고정 크기** 버퍼를 잡는다. 루프 안에서는 N이 6(SO-101)이든 수십(ALLEX)이든 같은 코드가 돈다. 로봇을 바꾸는 일 = 설정 파일을 바꾸는 일.

## 5. D1 까지 만든 부분: 제어 노드 (rt_control_node)

```
 ros2 topic pub /joint_command (50 Hz)
        │
        ▼
 [ROS 2 실행기 스레드 : on_command]  ──cmd_ring(SPSC)──▶  [RT 스레드 1 kHz : RtLoop → ControlStep]
        ▲                                                       │   1) 우편함 비우기 → 최신 명령
        │                                                       │   2) 워치독 (50 ms 끊기면 멈춤)
   publish_state 100 Hz  ◀──state_ring(SPSC)────────────────────┤   3) 변화량 제한 (0.05 rad/주기)
   publish_status 1 Hz   ◀──timing_ring(SPSC)───────────────────┘   4) Backend 쓰기/읽기 (SimLag → 나중에 MuJoCo·실물)
        │                                                           5) 상태 벨트에 올리기
        ▼
 /joint_states (위치·속도)   /rt_status (JSON: 지연 p50/p99/max, 드롭, 워치독, 카운터)
```
- 제어 논리는 전부 `rt_core/control_step.cpp` 에 있고 ROS 2 노드에는 없다 → 로봇·미들웨어를 바꿔도 제어 코드는 그대로.
- 안전장치 두 개(워치독·변화량 제한)는 RT 스레드 안에서 매 주기 돈다. 상위(ROS 2)가 죽어도 로봇은 멈춘다.

## 6. D2 까지 만든 부분: 관제 (fleet)

```
 [가상 장치 x50]────┐
 [rt-node-1 다리]───┼──MQTT 1 Hz──▶ [Mosquitto] ──▶ [collector.py] ──COPY 1초 묶음──▶ [TimescaleDB] ──▶ [Grafana]
 [Pi (나중에)]──────┘      ▲                                   │                          telemetry / devices / events / collector_stats
            끊기면 버퍼 ───┘ 재접속 시 QoS 1 재전송           └─ 매초: msgs/s, 적재 ms, 수집 지연 p50/p95/max, 온라인 수
```
- 장치는 브로커만 안다(서로 모른다). 서버는 장치 수와 무관하게 같은 코드. 300대도 `--count 300`.
- 유실은 "없다"가 아니라 "센다": 장치는 seq 를, 서버는 seq 의 빈칸을 센다. 끊김은 장치 버퍼가 메운다.

## 7. D3: 로봇 상태 머신 (rt_core/robot_state_machine.cpp) — RT 스레드 안, 표 하나

```
            INIT_DONE            COMMAND                 WATCHDOG_TRIP
  [INIT] ───────────▶ [READY] ───────────▶ [RUNNING] ───────────────▶ [FAULT]
                        ▲  ▲                                             │ COMMAND (명령이 다시 옴)
                        │  │ RECOVERED (정상 100주기)                      ▼
                        │  └────────────────────────────────────── [RECOVERING] ──WATCHDOG_TRIP──▶ [FAULT]
                        │ WATCHDOG_TRIP (READY 에서는 그대로 READY)
                 어느 상태 + STOP ──▶ [INIT]        표에 없는 조합 → 거절 + illegal_events++
```
- 사건을 넣는 곳은 한 군데(`ControlStep::update_state_machine`). 결과는 `JointStateSample.robot_state` → `/rt_status` `"state"` → 관제 다리를 거쳐 장치 `state` 로 올라간다(대시보드 "멈춤·고장 장치").

## 8. D3: OTA 단계 배포 (fleet/ota/rollout.py) — 서버가 판단, 장치는 적용/복원만

```
 rollout.py ── 1) 3초 듣고 살아 있는 장치 N대 ──▶ 2) 5%(ceil) 에 {cmd: ota, version} ──▶ 3) 텔레메트리 fw_version 이 바뀔 때까지 대기
                                                                                           │
   ┌───────────────── 6) 다음 단계 50% → 100% ◀── 통과 ── 4) health_wait 초 뒤 state != ok 인 장치 수 ≤ max_fail ?
   │                                                                                       │ 초과
   ▼                                                                                       ▼
 완료 (ota_rollouts.success = true)                    5) 새 버전 받은 전부에 {cmd: ota_rollback} → 이전 버전·ok 까지 시간 측정 → 중단
```
- 장치(`device_agent.py`): ota → 별도 스레드에서 apply_s 초 "updating" → 버전 교체 → ok 또는(bad) fault. ota_rollback → 직전 버전·ok. 겹치는 ota 는 거절.
- 숫자: 50대·나쁜 펌웨어 → 닿은 장치 3/50, 롤백 ≈ 1~2초(1 Hz 텔레메트리 반영 포함). 표③-3.

## 9. D4: 장애 4종과 복구 경로 — "유실은 없게"가 아니라 "세게"

```
  장애                 누가 막나                         복구 판정(DB 에서)                    유실(seq 빈칸)
  ─────────────────    ───────────────────────────────    ───────────────────────────────────    ─────────────
  브로커 중단          장치 버퍼(store-and-forward)       첫 msgs/s>0 · 전 장치 복귀              0 (QoS 1) / ≤장치 수 (QoS 0)
  DB 중단              수집기 backlog(Batch 메모리)        DB 응답 · backlog_rows=0                0
  수집기 중단          브로커 지속 세션(QoS 1 양쪽)         첫 collector_stats · 전 장치             0 (qos1) / 장치×초×Hz (qos0)
  나쁜 펌웨어          헬스 게이트 + 자동 롤백              ota_rollouts.rollback_s                 닿은 장치 5% 만
  (RT) 명령 끊김       워치독 → FAULT → RECOVERING          /rt_status state                        50 ms 감지 + 100주기 복구 = 150 ms
```
- 주입·측정: `fleet/chaos/inject.py` → `docs/measurements/fault_*.json` → `scripts/make_table3.py` 표③-2. 판정: `chaos/assert_results.py`.
- CI 2단계(`fleet_integration` 잡)가 진짜 컨테이너 위에서 이 표의 위 네 줄을 매 push 마다 다시 증명한다.

## 10. D5: 백엔드 자리에 MuJoCo — 제어 코드는 그대로

```
                          ┌─ SimLagBackend   : position += (target-position)*alpha          (D1, 의존성 0)
 ControlStep ── Backend ──┼─ MujocoBackend   : ctrl[act]=target; mj_step×N; qpos/qvel 읽기   (D5, -DRT_CORE_WITH_MUJOCO=ON)
   (불변)       (인터페이스)└─ FeetechSerial  : 서보 버스 (2주 계획 밖)
```
- 모델: Menagerie SO-ARM100 (`robots/so101.yaml` 의 `mujoco.model`, 관절 이름 매핑 `mujoco.joints`). 노드는 파라미터 `backend` 로 고른다.
- 숫자: 한 주기 비용(mj_step + read) p50/p99/max → `/rt_status` `work_us`, 테스트 JSON `mujoco_backend_ci.json`. 판정: p99 < 900 us (1 kHz 안).

## 11. CI 3잡

```
 push ──▶ [rt_core] 빌드·ctest 4·jitter 2초 드롭 0·fleet 가짜 테스트 3·대시보드 JSON ──┬──▶ [fleet_integration] 진짜 mqtt/db 컨테이너 + 장애 3종 + 롤백 + OTA → 판정
                                                                              └──▶ [mujoco] MuJoCo 3.x 내려받아 빌드 → SO-ARM100(6 자유도) 1 kHz 2000주기 → ALLEX(48 자유도, 위로보틱스 공개 모델) 500 Hz 1000주기
  git tag v* ──▶ [release.yml] package x86_64 + aarch64 (tar.gz · sha256 · manifest) ──▶ canary: 가상 50대 단계 배포 + 깨진 패키지 롤백 ──▶ GitHub Release 게시
                 장치(Pi · 가상)는 manifest.json 을 보고 내려받기 → sha256 → A/B 슬롯 → 자가 점검 → 전환 (docs/RELEASE.md)
```
