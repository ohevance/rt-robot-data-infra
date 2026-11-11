# 실험 목록 — 무엇을 물었고, 어떻게 쟀고, 무엇이 나왔나 (한 표)

`docs/LOG.md` 는 시간순(깨진 것·원인·해결)이라 "어떤 실험을 했나"를 한눈에 보기 어렵다. 이 표는 그 색인이다.
숫자 옆에는 항상 **환경**과 **원본 파일**(`docs/measurements/`)이 붙는다 — 환경이 다르면 같은 숫자가 아니다.
각 줄의 자세한 이야기는 "기록" 열의 LOG 절에 있다.

## 0. 실험의 흐름 — 어떤 기준을 못 넘어서 다음 실험으로 갈라졌나 (순서도)

사각형은 실험(번호는 아래 표), **마름모는 결과에 들이댄 기준(합격선)**, 화살표의 글은 그 기준에 대한 답이다.
실험은 미리 짠 목록이 아니라 **기준을 못 넘을 때마다 "왜?"를 하나 더 묻는 식**으로 생겼다. 기준을 넘은 가지는 거기서 끝난다.
(GitHub 에서 그림으로 보인다. 글로만 보면: 표① `E01 ✗ → E02 ✗ → E18 ✗ → E19-a ✗ → E19-b ✗ → E19-c ✓`, 곁가지 `E19-a 도구 불일치 → E19-d ✓(측정기 일치 274≈270)`; 표② `E04 작은 크기 ✓ → 1 MB ✗ → Cyclone ✓`; 표③ `E05 ✓ → E06 ✗(증거 불일치) → E07 → E08 ✓ → E13 ✓`, 곁가지 `E09·E10·E11·E12`.)
각 실험의 상세 페이지(왜 했나 · 결과 · 처음 읽는 사람을 위한 분석)는 [`experiments/`](experiments/README.md) 에 하나씩 있다.

### 표① 실시간 지연 — 합격선: 부하 중 max < 200 us, 한가/부하 차이 작음, 두 도구가 같은 급

```mermaid
flowchart TD
  E01["E01 샌드박스 VM, 일반 커널"] --> C01{"max < 1,000 us (1 ms 안)?"}
  C01 -->|"아니오: 3,484"| Q01["가상 머신 탓인가, 커널 탓인가?"]
  Q01 --> E02["E02 WSL: 일반 vs SCHED_FIFO"]
  E02 --> C02{"우선순위로 max 가 줄었나?"}
  C02 -->|"아니오: 921 → 937 (p50 만 92 → 37)"| Q02["우선순위는 줄만 세운다 → 커널이 잘라야 한다 → RT 커널, 실물 보드"]
  C02 -->|"곁가지: 노드 안에서도 드롭 0 인가?"| E03["E03 ROS 2 노드 안 RT 루프<br/>드롭 0, wake p99 278 (WSL 참고값) ✓"]
  Q02 --> E18["E18 Pi 4 일반 커널 '전' 값"]
  E18 --> C18{"일반 커널로 충분한가?<br/>부하 max < 200, 한가도 안정?"}
  C18 -->|"아니오: 부하 781, 한가도 5분에 376"| E19a["E19-a Pi 4 PREEMPT_RT"]
  E19a --> C19a{"부하 max < 200?"}
  C19a -->|"아니오: 301 (781 의 2.6분의 1 이지만)"| Q19a["남은 300 은 CPU 를 옮겨 다녀서인가?"]
  Q19a --> E19b["E19-b RT + CPU 3 고정"]
  E19b --> C19b{"고정으로 줄었나?"}
  C19b -->|"아니오: 311"| Q19b["그 CPU 의 다른 일(stress·IRQ·커널 스레드) 때문인가?"]
  Q19b --> E19c["E19-c RT + isolcpus=3"]
  E19c --> C19c{"부하 max < 200?<br/>일하는 동안 안 밀리나?"}
  C19c -->|"예: 189, work max 135 → 53 ✓ (잔여 189 = Pi 4 바닥)"| OK1(["표① 통과 — 1 ms 예산의 19%"])
  E19a --> C19t{"표준 도구와 내 측정기가 같은 급인가? (±30%)"}
  C19t -->|"아니오: cyclictest 132 vs jitter_bench 301"| E19d["E19-d 도구 불일치 검증: 가설 '50 us 일하는 동안의 노출'<br/>→ --work-us 0 으로 같은 부하"]
  E19d --> C19d{"work 0 이면 ~130 으로 내려오나?"}
  C19d -->|"아니오: 270 (p99 만 169→116) → 가설 기각"| E19d2["같은 설정(1 스레드·CPU 2·prio 80)의 cyclictest"]
  E19d2 --> C19d2{"두 도구가 같은 값?"}
  C19d2 -->|"예: 274 vs 270 ✓ 측정기는 맞다"| E19d3["남은 차이의 출처: prio 90? CPU 마다 스레드(-S)? 부하 512M?"]
  E19d3 --> C19d3{"prio 90 → ? · -S(256M) → ?"}
  C19d3 -->|"prio 무관(290) · -S 로 210 · 나머지 ≈ 부하 정의(512M, 격리 전) 추정"| OK1d(["닫힘 — 두 스크립트의 부하를 lib_stress.sh 한 곳으로"])
```

### 표② DDS — 합격선: 1 MB 메시지도 손실 0

```mermaid
flowchart TD
  E04["E04 DDS 구현체 × QoS × 크기 16조합 (rclpy)"] --> C04a{"64 B ~ 64 KB 에서 손실 0?"}
  C04a -->|"예: 전부 0, RTT p50 0.9~1.2 ms ✓"| C04b{"1 MB 에서도 손실 0?"}
  C04b -->|"아니오: Fast DDS best_effort 99.8%, reliable 22.8% (KEEP_LAST 10 초과)"| Q04["구현체를 바꾸면?"]
  Q04 --> C04c{"Cyclone 은 1 MB 손실 0?"}
  C04c -->|"예: 둘 다 0% (reliable p50 4.4 ms) ✓"| OK2(["표② 통과 — 큰 메시지는 reliable + 충분한 큐 깊이, 구현체 차이는 표②로 남김"])
```

### 표③ 관제·장애 — 합격선: 장애 뒤 유실 0 이고, 그 0 이 다른 증거(diag)와 맞는다

```mermaid
flowchart TD
  E05["E05 가상 50대 1 Hz 기본"] --> C05{"끊김 동안 데이터가 보존되나?"}
  C05 -->|"예: 버퍼 654 = 재전송 654 ✓"| E06["E06 장애 4종 1차 (복구 2.9 / 1.4 / 1.6 s)"]
  E06 --> C06{"유실 0 이 다른 증거와 맞나?"}
  C06 -->|"아니오: 두 장치에 12초 공백인데 0"| E07["E07 유실 기준점 수정<br/>(장애 직전 seq 로)"]
  E07 --> C07{"다시 재면 0 인가?"}
  C07 -->|"아니오: 53 / 1434 — 원인 3가지 (재시작 경쟁 · 종료 순간 · 큐 상한)"| E08["E08 persistence true + 곱게 종료 뒤 재측정"]
  E08 --> C08{"유실 0? diag 틈 없음?"}
  C08 -->|"예: 0 / 1400, 0 / 1311 ✓"| E13["E13 CI 러너(10대 2 Hz)에서 같은 4종"]
  E13 --> C13{"환경이 달라도 같은 모양?"}
  C13 -->|"예: 0·0·0, 롤백 0.4 s ✓"| OK3(["표③ 통과"])
  E05 --> C09{"오프라인 이벤트 = 장치 수 50?"}
  C09 -->|"아니오: 20"| E09["E09 → 브로커 종료 시 일괄 유언 (장치는 멀쩡) ✓ 설명됨"]
  E05 --> C10{"전달 지연이 평탄한가?"}
  C10 -->|"아니오: 10초마다 튐"| E10["E10 keepalive A/B → 30 s 0회 / 10 s 10.0 s 간격 ✓ 원인 확정"]
  E07 --> C12{"지속 세션은 무한 보관인가?"}
  C12 -->|"아니오: 2,450개 버림"| E12["E12 큐 상한 = max_queued_messages → 설계 규칙(허용 중단 × 장치 × Hz)"]
  E08 --> C11{"QoS 1 이 아니어도 0 인가?"}
  C11 -->|"아니오: 508 / 1312"| E11["E11 QoS 0 vs 1 → 표③-2 두 줄"]
```

### 물리 시뮬레이션 · 기록 — 합격선: 물리 비용이 1 ms 예산의 10% 아래 / 기록은 설계 Hz 그대로·틈 0
(E03 의 "노드 안 1 kHz" 가 통과한 뒤 "물리 비용도 1 ms 안에 드나?" 로 이어진 가지. E20 은 그 노드의 100 Hz 를 기록하는 별도의 길.)

```mermaid
flowchart TD
  E15["E15 MuJoCo 한 주기 비용"] --> C15{"예산의 10% 아래?"}
  C15 -->|"예: 0.9% (6.4 / 8.5 / 29.4 us) ✓"| E16["E16 물리가 보여 주는 새 사실?"]
  E16 --> C16{"SimLag 와 결과가 같나?"}
  C16 -->|"아니오: 어깨 Pitch 1.1° 처짐 → 중력 보상 필요 (보류 항목)"| OK5(["물리 통과 + 다음 단계 발견"])
  OK5 --> E20["E20 기록 파이프라인 첫 실행<br/>rosbag2 MCAP → CSV → 요약 (WSL, 30 s)"]
  E20 --> C20{"설계 Hz 그대로·틈 0·드롭 0? 처짐이 자동으로 나오나?"}
  C20 -->|"1차: 스크립트 멈춤(timeout 과 SIGTTIN) → 수정"| E20
  C20 -->|"2차 예: 100.0 / 50.0 / 1.0 Hz, 틈 0, 드롭 0, 어깨 0.019 rad + 팔꿈치 0.009 ✓"| OK6(["기록 통과 — 관제와 다른 길이 실제로 돈다"])
```


## 1. 실시간 루프 (표①)

| # | 질문 | 어떻게 | 결과 | 환경 | 원본 | 기록(LOG) |
|---|---|---|---|---|---|---|
| [E01](experiments/E01.md) | 가상 머신·일반 커널에서 1 kHz 루프가 지켜지나? | `jitter_bench --no-rt` 5 s | p99.9 2,568 / max 3,484 us — 주기의 3배 늦게 깸 | 샌드박스 VM | `jitter_sandbox_generic.json` | 11/03 D0 |
| [E02](experiments/E02.md) | 우선순위(SCHED_FIFO)만으로 꼬리가 잘리나? | WSL 에서 일반 vs `--prio 80` | p50 92 → 37 us 좋아짐, **max 921 → 937 us 그대로** — 우선순위는 줄을 앞세울 뿐 커널을 멈추지 못한다 | WSL2 | `jitter_wsl_generic.json`, `jitter_wsl_fifo.json`, `table1.md` | 11/03 D0 WSL |
| [E03](experiments/E03.md) | ROS 2 노드 안에서도 1 kHz·드롭 0 이 유지되나? 워치독·변화량 제한이 동작하나? | `rt_control_node` + 50 Hz 명령, `/rt_status` 1 Hz | wake p99 278 / max 679 us, 드롭 0, watchdog trips 1, step_limited 10, `/joint_states` 100.0 Hz | WSL2 | `rt_status` 출력(LOG) | 11/03 D1 |
| [E15](experiments/E15.md) | 물리 시뮬레이션(MuJoCo, SO-ARM100 6축) 한 주기 비용이 1 ms 예산의 얼마인가? | `test_mujoco_backend` 2,000주기 · 노드 안 `work_us` | 러너 p50 6.4 / p99 8.5 / max 29.4 us(예산의 0.9%) · WSL 단독 4.9 / 6.3 / 20.8 · 노드 안(제어+물리) 41 / 145 / 247 us | GitHub 러너 · WSL2 | `mujoco_backend_ci.json`, LOG | 11/04 CI 2차 · MuJoCo WSL |
| [E16](experiments/E16.md) | 물리가 있으면 SimLag 로는 못 보는 무엇이 보이나? | 목표 [0.3, −0.2, 0.1, 0, 0, 0.5] 를 주고 정상 상태 위치 읽기 | 어깨 Pitch 만 −0.180 (목표 −0.200, **1.1° 처짐**) = 중력에 걸린 position 액추에이터의 정상 상태 오차 → 중력 보상이 필요한 숫자 근거 | WSL2, MuJoCo | LOG | 11/04 MuJoCo WSL |
| [E21](experiments/E21.md) | 위로보틱스 공개 모델 ALLEX(48 자유도)를 프로필만 바꿔 같은 노드로 돌리면 물리 한 주기 비용은 6 자유도의 몇 배인가? | `scripts/get_allex.sh` → `test_mujoco_backend` 에 `RT_MUJOCO_DOF=48` + 프로필 관절 이름 48개(+ `RT_MUJOCO_PERIOD_US`), 2초 분량 · CI `mujoco` 잡 ALLEX 단계(500 Hz 게이트) | WSL 1 kHz **p50 336 / p99 622 / max 1,785 us** — 6 자유도(4.9 / 6.3 / 20.8)의 약 70~100배, p99 는 예산의 62 %. 러너 1 kHz 382 / 458 / 609(전부 1 ms 안). → **프로필 500 Hz 기본**(모델 걸음 2 ms). 500 Hz 실측 WSL 327 / **1,000** / 1,589(2 ms 의 50 % — "예산만 2배" 어림 31 % 보다 나빴다) · 러너 390 / 510 / 685(26 %, CI 게이트 통과). 러너에선 걸음 2배의 대가가 p99 +11 % 뿐 → WSL 차이는 환경 꼬리로 추정, 반복 측정 남음 | WSL2 · GitHub 러너 | `mujoco_backend_allex_*.json` 4개 | 11/06 |
| [E20](experiments/E20.md) | 로봇 안 100 Hz 원본을 기록하고(rosbag2 MCAP) 검증·전처리를 자동으로 할 수 있나? | `record.sh 30` → `bag_to_csv.py` (CSV 3 + summary.md) | `/joint_states` 2,964행 **100.0 Hz, 틈 0**, 50.0 / 1.0 Hz, 드롭 0. 추종 오차 표에 **어깨 0.0191 rad(1.1°) + 팔꿈치 0.0094** 가 자동으로. 1차는 `timeout` 의 SIGTTIN 정지로 실패 → `--foreground` | WSL2, MuJoCo | `record_summary_wsl_20261105.md`, `record_rt_status_wsl_20261105.csv` | 11/05 |
| [E18](experiments/E18.md) | **Pi 4 일반 커널**(6.8 raspi)의 지연 꼬리는? — RT 비교의 "전" | `jitter_bench --prio 80` 60 s · `cyclictest` 4 CPU 300 s / 120 s, 한가·부하 | jitter max **24.9 / 781.2** us · cyclictest max **376 / 695** us(p99.9 57 / 118). 한가해도 5분 창에선 376. 부하 중 `work time` max 134.9 — 일하다 밀림. 온도 45→75 °C, 스로틀 0 | **Pi 4B**, Ubuntu 24.04, RT 아님 | `table1_pi4.md`, `*_pi4_generic_*` | 11/04 밤 |
| [E19](experiments/E19a.md) (a·[b](experiments/E19b.md)·[c](experiments/E19c.md)·[d](experiments/E19d.md)) | PREEMPT_RT 가 E18 의 max 를 얼마로 줄이나? CPU 고정·isolcpus 는? 두 도구가 같은 급인가? | 같은 4조건 + `--cpu 3` + `isolcpus=3` + 도구 맞추기 4회(일 0 · 같은 설정 cyclictest · prio 90 · -S 256M) | cyclictest max 한가 **37**(376→) / 부하 **132**(695→). jitter 부하 max **781 → 301**(RT) → 311(고정, 효과 없음) → **189**(격리), work max 135 → 53. 비용: p99 146 → 185. 도구 불일치 2.3배 → E19-d: 일 0 이어도 270(가설 기각), 같은 설정 cyclictest **274 ≈ 270**(측정기 맞음), -S 로 210, 나머지는 부하 정의(512M vs 256M, 추정) | **Pi 4B**, `6.8.0-2054-raspi-realtime`, 스로틀 0 | `*_pi4_rt_*`, `table1_pi4.md` | 11/05 |

## 2. DDS (표②)

| # | 질문 | 어떻게 | 결과 | 환경 | 원본 | 기록(LOG) |
|---|---|---|---|---|---|---|
| [E04](experiments/E04.md) | 구현체(Fast DDS·Cyclone) × QoS(reliable·best_effort) × 크기(64 B~1 MB)에서 손실·왕복 지연은? | `dds_bench/run_matrix.sh` 16조합, rclpy | 64 B~64 KB 는 전부 손실 0, RTT p50 0.9~1.2 ms. **1 MB: Fast DDS best_effort 99.8% 손실, reliable 22.8%, Cyclone 0%**(reliable p50 4.4 ms) | WSL2, 같은 PC | `dds_*.json` 16개, `table2.md` | 11/03 D1 |

## 3. 관제·장애·OTA (표③)

| # | 질문 | 어떻게 | 결과 | 환경 | 원본 | 기록(LOG) |
|---|---|---|---|---|---|---|
| [E05](experiments/E05.md) | 가상 50대 1 Hz 의 전달 지연은? 브로커가 10초 죽으면 장치 버퍼가 일을 하나? | 수집기 1 s 묶음 COPY, 대시보드 | 전달 지연 p50 0.9 / p95 1.8 ms. 중단 10초 → 버퍼 654 = 재전송 654, 재접속 50, 복구 폭주 600 msgs/s | WSL2 | `table3.md` ③-1 | 11/03 D2 |
| [E06](experiments/E06.md) | 장애 4종(broker·db·collector·bad_firmware)의 감지·복구·유실은? | `fleet/chaos/inject.py` + `assert_results.py` | broker 10 s → 전 장치 복귀 2.9 s · db 10 s → backlog 0 까지 1.4 s, 뒤늦게 570행 · collector(QoS 1) 10 s → 1.6 s · 나쁜 펌웨어 3/50 에서 롤백 1.0 s. 유실은 "0"이었으나 → E07 | WSL2 | `fault_*.json`, `ota_*.json` | 11/04 D5 1차 |
| [E07](experiments/E07.md) | 유실 "0" 이 진짜인가? | 유실 기준점을 장애 창 안 min(seq) → **장애 직전 30초의 마지막 seq** 로 고침, `diag.py` C절 | broker 재측정 **유실 53 / 1434**. 원인 셋: ① 브로커 재시작 경쟁(persistence false, 4~5대 × 12개) ② 수집기 종료 순간 장치당 1개(pending 1초) ③ 큐 상한 | WSL2 | LOG | 11/04 D5 2차 |
| [E08](experiments/E08.md) | ①② 를 고치면(persistence true + 곱게 종료) 유실이 0 이 되나? | 같은 주입 재측정 | broker **0 / 1400**, collector(QoS 1) **0 / 1311**, 복귀 2.9 s / 1.6 s, diag C "틈 없음" | WSL2 | `fault_broker.json`, `fault_collector_qos1.json`, `table3.md` ③-2 | 11/04 D5 2차 결과 |
| [E09](experiments/E09.md) | 오프라인 이벤트가 50 이 아니라 왜 20 인가? | `diag.py` A절(군집), `events` 시각 비교 | 20개가 같은 1 ms 안 = **브로커 종료 시 일괄 유언**을 소켓 닫기 전까지 쓴 만큼. 장치는 멀쩡 | WSL2 | LOG | 11/04 D5 1차 결과 |
| [E10](experiments/E10.md) | 전달 지연이 10초마다 튀는 원인이 keepalive 인가? | A/B: `--keepalive 30` vs `10`, `diag.py` B절 | 30 s → **튐 0회**(172 s), 10 s → 튐 간격 **정확히 10.0 s** → keepalive 박자 확정. 해법: 장치별 keepalive jitter | WSL2 | LOG | 11/04 소실험 |
| [E11](experiments/E11.md) | QoS 0 이면 수집기 10초 중단에 얼마를 잃나? | 수집기·장치 모두 QoS 0 으로 같은 주입 | **508 / 1312**(예측 500 = 50대 × 10 s) vs QoS 1 지속 세션 0 / 1311 | WSL2 | `fault_collector_qos0.json` | 11/04 소실험 |
| [E12](experiments/E12.md) | 지속 세션은 무한히 보관하나? | 수집기가 7.5분 비어 있던 사고를 그대로 측정 | 412 s × 50 ≈ 20,600 까지 보관, 그 뒤 **2,450개 버림** = `max_queued_messages 20000`. Mosquitto 는 꽉 차면 새 메시지를 버린다 | WSL2 | LOG | 11/04 D5 2차 |
| [E13](experiments/E13.md) | 같은 장애 4종이 다른 환경(GitHub 러너, 10대 2 Hz)에서도 같은 모양인가? | CI `fleet_integration` (진짜 컨테이너) | 유실 0/318 · 0/286 · 0/280, 롤백 0.4 s — 환경이 아니라 설계가 만든 숫자 | ubuntu-24.04 러너 | `table3_ci.md` | 11/04 CI 2차 |
| [E22](experiments/E22.md) | OTA 를 흉내에서 진짜 설치로 바꾸고 태그 → 빌드 → 가상 50대 카나리 → Release 게시를 이으면, 50대에 진짜 산출물이 깔리는 데 몇 초이고 깨진 빌드는 몇 대에서 멈추나? | `scripts/package_release.sh`(tar.gz·sha256·매니페스트) → `rollout.py --manifest` → 장치 `ota_apply.py`(내려받기·sha256·A/B 슬롯·자가 점검·전환) · `release.yml` | **첫 태그 `v0.9.0-rc1`(러너, 진짜 Mosquitto)**: 태그 → 게시 1분 52초, 50대 단계 적용 **1.2 / 2.0 / 2.2 s**, 전체 14.41 s; 깨진 패키지 **3/50 에서 거부 → 롤백 1.0 s**. **정식 `v0.9.0`(같은 날)**: 1분 27초, **1.2 / 2.2 / 2.2 s**, 14.62 s, 3/50 → 롤백 1.0 s. 샌드박스(가짜 브로커, 진짜 설치): 0.6 / 1.0 / 1.2 s, 3.95 s; 롤백 0.2 s — 차이는 보고 주기(1초) | 샌드박스 · GitHub 러너(매 태그) | `ota_release_v0.9.0_*.json` · `ota_release_v0.9.0-rc1_*.json`(Release 자산 그대로), `ota_release_sandbox_*.json` | 11/10 · 11/11 |
| [E24](experiments/E24.md) | 같은 RT 루프를 ZeroMQ 로 감싸면 명령이 RT 루프에 반영되어 상태로 돌아오기까지 몇 ms 이고, 그 몫은 어디서 오나? | `rt_control/zmq_adapter`(같은 `rt_core`, 껍질만 ZeroMQ) + `sdk/python/rtsdk/bench.py`(명령 번호가 상태에 실려 돌아오는 것을 클라이언트 시계 하나로) | **명령 → 반영 WSL p50 0.88 / p99 1.81 ms**(RT 스레드 SCHED_FIFO 0.88 / 1.71 — 스케줄링으로 줄지 않는다), ping 0.21 ms, 1 kHz 상태 10,327개 빠짐 0. 샌드박스는 1.02 / 1.76. 재기 전 예측(5절) 넷 중 둘. 느린 구독자: 12초까지 빠짐 0 대신 12초 묵은 상태, 45초에 빈 번호 12,109 · 노드의 버림 카운터 0 → 문서 정정 + 끝-대-끝 12단계 | WSL2(같은 PC) 1,000회 × 2 · 샌드박스(느린 구독자, 진짜 libzmq) | `zmq_bench_wsl_20261111.json` · `zmq_bench_wsl_fifo_20261111.json` · `zmq_status_wsl_fifo_20261111.json` · `zmq_bench_sandbox_20261111.json` | 11/11 저녁 · 밤 |
| [E23](experiments/E23.md) | 서버(시드니)까지의 왕복은 몇 ms 이고, 대시보드의 전달 지연은 편도 지연인가 시계 차이인가? | `fleet/tools/mqtt_rtt.py`(보내고 자기가 받는다 — 시계 하나) + `nagle_model.py`(가설을 모형으로, 예측을 먼저 적는다) | **왕복 290 ms**(1초 간격, 60회 중 59회가 287~293), 편도 어림 145 ms → 대시보드 전달 지연 146.5 ms 는 거의 그대로 편도(시계 차이 +1.5 ms). 첫 측정(0.2 s 간격) 285 / **707** / 854 ms 는 간격 < 왕복이라 양쪽 Nagle 이 키운 값. 재기 전 예측 넷 중 셋 맞음(1 s 290, 0.35 s 288, NODELAY 464 vs 모형 460), 하나 틀림(0.2 s 재측정 548 vs 710) | Pi 4(집 Wi-Fi) → 시드니 EC2 | `rtt_pi_sydney_20261111T00*Z_*.json` (5개, 개별 값 포함) | 11/11 |

## 4. 사고·함정 (실험은 아니지만 "뭐가 안 됐고 어떻게 풀었나"의 소재)

| 무엇 | 원인 | 해결 | 기록 |
|---|---|---|---|
| 재시작된 수집기가 바로 죽음 | `/proc/<pid>/exe` 는 venv 를 잃은 경로 | `environ` 의 VIRTUAL_ENV·PATH 로 같은 환경 재시작 | 11/04 D5 1차 |
| 수집기 둘·가상 장치 두 벌이 2초마다 서로 밀어냄(reconnects 1,675) | 같은 MQTT client_id | `fleet/common/single_instance.py` flock 잠금 | 11/04 2차 결과 · 소실험 |
| persistence true 뒤 오프라인 이벤트 +50 | 보관(retained)된 유언이 재구독 때 다시 내려옴 | retain=1 상태는 "지금 상태"이지 사건이 아님 → events 제외 | 11/04 2차 결과 |
| CI `fleet_integration` 실패 | TimescaleDB 첫 기동의 임시 서버를 `pg_isready` 가 "준비됨"이라 함 | `migrate.py --wait` 가 소비자와 같은 경로(TCP)로 재시도 | 11/04 CI 1차 |
| `ros2 topic echo` 가 토픽을 못 봄 | 다른 RMW 로 떠 있던 ros2 데몬 | `ros2 daemon stop` | 11/04 MuJoCo WSL |
| colcon install 뒤 `libmujoco.so` 못 찾음 | install 단계에서 rpath 소실 | `CMAKE_INSTALL_RPATH_USE_LINK_PATH TRUE` | 11/03 D3~D5 |
| 노드가 파라미터 파일로 시작 안 됨 | 빈 배열 `mujoco_joints: []` 의 타입 미정 | 빈 배열이면 키를 뺀다 | 11/03 D3~D5 |
| Pi 결과 파일 복사·커밋 실패 | WSL 명령을 Pi 창에 침, sudo 가 만든 root 소유 파일 | 창 표시 [Pi 창]/[WSL 창], `chown -R` | 11/04 밤 |
| Ubuntu One 가입 실패(실시간 커널 토큰) | Launchpad 사용자명 검사 time out(Canonical 쪽) | 재시도 / 플랜 B 커널 직접 빌드 | 11/04 밤 |
| CI `fleet_integration` 빨강(수집기 시작 직후 `NameError: request_stop`) | 11/04 잠금 공용화 패치에서 시그널 핸들러 함수가 통째로 삭제됨. 단위 테스트가 main() 을 안 타서 못 잡음 | 함수 복원 + main() 한 바퀴 스모크 테스트 추가 | 11/05 |
| `record.sh` 가 조용히 안 끝남 | `timeout` 이 recorder 를 뒤 프로세스 그룹에 두고, 키보드 읽기에서 SIGTTIN 정지 | `timeout --foreground` + `--disable-keyboard-controls` | 11/05 (E20) |
| 서버 설치의 보존 정책 단계 실패(`add_retention_policy does not exist`) | DB 컨테이너의 초기화용 임시 서버에 `pg_isready` 가 "준비됨"이라 답했다 — 11/04 CI 와 같은 원인을 새 스크립트에 다시 썼다 | "응답하는가"가 아니라 "확장과 표가 생겼는가"를 기다린다 | 11/10 저녁 |
| 서버가 장치를 거부하는데 장치 화면은 정상 때와 같다 | 여러 줄을 한꺼번에 붙여 넣어 비밀번호 입력(`read -s`)이 건너뛰어짐 → 0자 | 한 줄씩 + 글자 수 확인. Pi 설치 스크립트가 빈 값·자리표시·공백을 서비스 등록 전에 거부 | 11/10 저녁 |
| Pi 에서 에이전트가 뜨지 않음 | paho 가 없었고 안내한 apt 패키지는 1.6(필요 2.0 이상). pip 설치는 자동 보안 업데이트가 dpkg 잠금을 30분 넘게 쥐어 막힘 | PyPI 의 휠을 받아 sha256 확인 뒤 사용자 폴더에(`deploy/pi/get_paho.py`) | 11/10 저녁 |
| 대시보드 "온라인 장치 4"(실제 1대), 지연 패널은 빨강 | 수집기가 본 적 있는 장치 전부의 `last_seen` 을 매초 지금으로 덮어썼다. 패널은 색 기준이 없어 기본값(80)이 걸렸다 | 최근 5초 안에 보낸 장치만, 그 장치의 마지막 도착 시각으로 + 테스트. 패널마다 색 기준 | 11/10 저녁 |
| CI 가 3시간 빨강 — 산출물 OTA 가 첫 장치에서 `exit 127` | 통합 테스트는 상대 경로 슬롯, 단위 테스트는 절대 경로만 썼다. 패치 다섯을 한꺼번에 push 하고 CI 를 보지 않았다 | 설치·자가 점검·훅이 경로를 절대 경로로 굳힌다 + 상대 경로 테스트 | 11/10 밤 |
| "다음 부팅도 RT 커널인가"의 확인 기준이 다음 날 서로 다른 답을 냄 | `/boot/vmlinuz` 링크는 마지막에 설치된 패키지일 뿐, Pi 가 부팅 때 읽는 것은 `/boot/firmware` 의 파일 | 부팅 파일의 sha256 을 RT 커널 파일과 직접 비교 | 11/11 아침 |
| 깨진 패키지를 거부한 장치가 한 세대 뒤로 내려감(실행 전에 찾음) | `ota_rollback` 이 "이전 슬롯이 있는가"를 먼저 봤다 — 시험은 전부 빈 슬롯에서 시작해 우연히 옳은 가지로 갔다 | "직전 설치가 실패했는가"를 먼저 본다 + "정상 2번 → 깨진 것" 테스트 | 11/11 아침 |
| 서버까지 왕복 707 ms(같은 구간의 편도는 146 ms) | 보내는 간격 0.2초가 왕복보다 짧아 양쪽의 Nagle 이 붙잡았다 — 재는 방법이 만든 값 | 기본 간격 1초 → 290 ms. 예측을 먼저 적고 검증(E23) | 11/11 오전 |
| 공개한 장표(pptx) 한 장에 계정 이름이 남아 있었다 | 11/06 의 점검은 `git grep` — pptx·docx 안(ZIP)은 보지 못한다. 장표 생성 코드 폴더도 `.gitignore` 의 `build/` 에 걸려 저장소에 없었다 | pptx·docx 를 풀어서 보는 `scripts/check_public.py` + 생성 코드를 저장소에 | 11/11 낮 |

## 5. 아직 안 한 것
- (완료) E19 Pi 4 PREEMPT_RT, E20 기록 파이프라인 첫 실행, E21 ALLEX 48 자유도(WSL 1 kHz · 500 Hz, 러너 1 kHz), E22 릴리스 → 배포(샌드박스 + 첫 태그 `v0.9.0-rc1` · 정식 `v0.9.0` 러너 값 11/11). Pi 가 Release 를 받아 설치(1초, 자가 점검 0.67초). E22 남음: Pi 서비스의 자율 업데이트(03~05시)가 `v0.9.0` 을 받았는지 확인, 헬스 게이트에 RT 지표, 서명. E23 왕복 시간 290 ms(예측 넷 중 셋 맞음) — 남음: 반복 측정, 양쪽 NODELAY, 세 띠의 원인. E21 남음: 러너 500 Hz 값, 노드 안 `work_us`·drop, 조건별 3회 반복과 10초 측정(테스트에 주기 수 옵션 필요).
- 남은 것: 브로커 로그로 천둥 떼(thundering herd) 가설 확정, 수동 ACK(DB 적재 뒤 PUBACK), 중력 보상(토크 피드포워드), 512M 부하로 cyclictest -S 한 번 더(E19-d 의 부하 정의 vs 격리 전후 가르기), 기록 요약을 관제로 1 Hz 올리기 — 면접에서 "다음 단계"로 말할 것.
