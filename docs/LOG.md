# 작업 로그 (LOG) — 깨진 것, 원인, 해결, 배운 것

형식: 날짜 · 증상 · 원인 · 해결 · 배운 것 (각 한 줄). 면접의 "뭐가 안 됐고 어떻게 풀었나"의 원본.

## 2026-11-03 (D0)
- 증상: 샌드박스(가상 머신, 일반 커널)에서 1 kHz 루프의 p99.9가 2,568 us, max 3,484 us — 주기(1,000 us)의 3배 이상 늦게 깸.
- 원인: 실시간 커널이 아니고, 가상 머신이라 호스트 스케줄러가 CPU를 빼앗음. SCHED_FIFO가 됐어도 커널이 선점 불가 구간에서 멈춤.
- 해결: 이 값은 "일반 환경의 참고값"으로만 기록. 실측은 노트북 네이티브 + PREEMPT_RT 커널에서(D1~D2).
- 배운 것: SCHED_FIFO·mlockall이 "ok"여도 커널이 RT가 아니면 소용없다 → 표에 커널·RT 여부를 반드시 같이 적는다.

## 2026-11-03 (D0, WSL2 실측)
- 결과: 1 kHz × 5초, 드롭 0. 일반 스케줄링 p50 92 / p99 305 / p99.9 504 / max 921 us. SCHED_FIFO 적용 시 p50 37 / p99 273 / p99.9 664 / max 937 us.
- 읽기: 우선순위는 "보통 때(p50)"를 92 → 37 us 로 좋게 했지만 꼬리(p99.9·max)는 그대로. 우선순위는 줄을 앞에 세울 뿐 커널이 하던 일을 중단시키지 못한다. 꼬리를 자르는 건 PREEMPT_RT 의 몫.
- max 가 1 ms 주기의 턱밑(921~937 us) → 실제 제어 루프였다면 거의 한 주기를 놓친 상태.
- "work time" max 216 us (목표 50 us) → 바쁘게 도는 동안에도 CPU 를 뺏긴 흔적. 가상 커널에서는 cpu_pin 으로도 해결되지 않는 종류.

## 2026-11-03 (D1)
- 샌드박스에 ROS 2 가 없어 ROS 2 노드는 "스텁 헤더"로 문법만 검사했다. 실제 colcon 빌드는 WSL 에서 처음 한다 → 빌드 오류가 나면 그 출력이 첫 수정 대상.
- 제어 단계(ControlStep)는 ROS 2 없이 단위 테스트했다: 1차 지연 모델로 목표 추종, 변화량 제한(첫 주기 0.05 rad), 워치독(20 ms 끊김 → 멈춤, 명령 재개 → 해제). 3 테스트 통과.

## 2026-11-03 (D1, WSL 실측·발견)
- 결과(노드): 1 kHz 유지, timing/state 드롭 0, wake p50 37 / p99 278 / max 679 us(정상 구간). 워치독 tripped → ok → tripped, trips 1, step_limited 10(0.5 rad 를 0.05 씩 10주기). joint_states 100.0 Hz.
- 증상: 두 번째 실행의 rt_status 에 iter 73917(74초째)이 섞여 나옴. 원인: `kill $NODE` 가 `ros2 run` 껍데기만 죽이고 노드 프로세스는 고아로 남음. 해결: `pkill -f rt_control_node`, 안내는 바이너리 직접 실행으로. 배운 것: 프로세스 트리를 확인하지 않은 kill 은 "죽였다"가 아니다.
- 증상: Fast DDS 조합 8개가 결과 없이 빠짐. 원인: `librmw_fastrtps_cpp.so` 미설치 — ros-base 설치 때 Cyclone 을 명시해 apt 가 구현체를 Cyclone 하나로만 채움. 해결: `apt install ros-jazzy-rmw-fastrtps-cpp`. 배운 것: "기본 미들웨어"를 가정하지 말고 rt_status 에 사용 중인 RMW 이름을 찍는다(추가함).
- 결과(표②, rclpy, 같은 PC): 64 B~64 KB 는 구현체·QoS 무관하게 손실 0, RTT p50 0.9~1.2 ms(파이썬 오버헤드 포함). 1 MB: Fast DDS best_effort 99.8% 손실, Fast DDS reliable 22.8% 손실(KEEP_LAST 10 초과), Cyclone 은 둘 다 0%(reliable p50 4.4 ms).
- 소음: pong 을 SIGTERM 으로 끄면 rclpy 가 ExternalShutdownException 을 출력. 해결: SIGINT 로 종료.

## 2026-11-03 (D2, WSL 실측·발견)
- 결과(관제): 가상 50대 1 Hz, 수집기 50 msgs/s, 적재 수 ms. 브로커 10초 중단 → 장치 버퍼 654 = 재전송 654, 재접속 50, 대시보드에 재전송 폭주 600 msgs/s 와 전달 지연 max 12.5 s 가 그대로 보임(= 밀린 메시지의 "원래 측정 시각" 기준이라 정상).
- 증상 A: 대시보드 "오프라인 이벤트" 20. 50대 모두 끊겼는데 왜 20 인가? 가설 (a) 브로커가 종료되며 소켓을 닫는 순서상 일부 장치의 유언(offline)만 수집기에 전해졌다 (b) 재접속 과정의 keepalive 오판. 도구: `fleet/tools/diag.py` A절이 offline 이벤트마다 전후 텔레메트리 유무로 "진짜 끊김/가짜/정상 종료"를 가른다. **다음 실측에서 확인.**
- 증상 B: 전달 지연 p95 가 약 10초마다 10 ms(max 32 ms)로 튐. 가설 (1) keepalive 10초 — 50대가 같은 때 접속해 PINGREQ 를 동시에 보내고, 가상 장치 프로세스(스레드 100개, GIL)가 그 순간 멈칫한다 (2) Grafana 2초 새로고침 부하(주기가 안 맞아 약함) (3) DB 쪽(insert_ms 가 같이 튀면). 도구: `diag.py` B절이 튐 간격의 중앙값과 insert_ms 동반 여부를 낸다. 실험: `virtual_fleet.py --keepalive 30` → 간격이 30초로 바뀌면 (1) 확정.
- 용어 정정: "수집 지연(ingest latency)" 이라 부른 값은 수집기 **도착** 기준이다(DB 적재 1초 미포함). 문서·출력·표를 "전달 지연(transit)"으로 고치고 컬럼 이름만 호환을 위해 유지.

## 2026-11-03 (D3~D5, 샌드박스 작업)
- 샌드박스에는 Mosquitto·PostgreSQL·pip·MuJoCo 가 없다(네트워크 차단). 해결: 가짜 브로커(`fake_mqtt.py`)·가짜 DB(`fake_psycopg.py`)로 OTA·수집기 내성을 끝-대-끝 테스트(3개 모두 통과, 약 5초). MuJoCo 는 우리가 쓰는 API 만 적은 스텁 헤더 + 빈 공유 라이브러리로 **문법·CMake·rpath 까지만** 검증. 진짜 물리 위 실행은 WSL/CI 가 처음이다.
- **미검증 (WSL 첫 실행에서 확인할 것)**: (1) MuJoCo 릴리스 버전 `3.3.2` 타르볼 존재 여부(없으면 `scripts/get_mujoco.sh <버전>` 과 ci.yml 의 MUJOCO_VERSION 을 같이 바꿈) (2) menagerie `trs_so_arm100` 의 관절 이름 `Rotation, Pitch, Elbow, Wrist_Pitch, Wrist_Roll, Jaw` — 틀리면 백엔드가 모델의 이름을 전부 출력하므로 그걸 `robots/so101.yaml` 에 옮기면 끝 (3) `so_arm100` 모델의 액추에이터가 position 타입인지(ctrl = 목표 각) — 아니면 `ctrl` 의 뜻이 토크가 되어 테스트 2)가 실패한다.
- 함정: ROS 2 파라미터 파일에 빈 배열(`mujoco_joints: []`)을 쓰면 파서가 타입을 못 정해 노드가 시작하지 않는다 → `profile_to_params.py` 가 빈 배열이면 키를 뺀다.
- 함정: colcon `install` 된 실행 파일은 빌드 때 rpath 를 잃는다 → `CMAKE_INSTALL_RPATH_USE_LINK_PATH TRUE` 로 `libmujoco.so` 경로를 유지. (안 하면 `ros2 run` 이 "libmujoco.so.3: cannot open shared object" 로 죽는다)
- 함정: 지속 세션(clean_session=False)은 **구독자가 QoS 1 로 구독하고 발행자도 QoS 1 로 보내야** 브로커가 큐에 담는다. 한쪽만 1 이면 min(0,1)=0 → 유실. 그래서 장애 주입 `collector` 는 qos0/qos1 두 줄로 남긴다.
- 함정: `pgrep -f collector/collector.py` 로 수집기를 찾을 때 주입 스크립트 자신은 패턴에 안 걸린다(`chaos/inject.py`). 재시작은 `/proc/<pid>/exe`(venv 파이썬 경로)와 `cmdline`·`cwd` 를 그대로 써서 "같은 명령"을 보장.
- 함정: CI 2단계의 broker 장애에서 QoS 0 이면 소켓에 이미 실린 메시지 1개/장치를 잃을 수 있어 "유실 ≤ 장치 수"로 판정. 통합 테스트는 QoS 1 로 돌려 0 을 기대.

## 2026-11-04 (D5 실측 1차, WSL)
- 결과(대시보드): OTA 1.1.0 단계 배포가 "펌웨어 버전별 장치 수" 패널에 3 → 25 → 50 으로 보임. 1.2.0-bad 는 3대에서 멈추고 되돌아감. 브로커 10초 중단 → 재전송 폭주 600 msgs/s, 전달 지연 max 12.5 s(밀린 메시지의 원래 측정 시각 기준). DB 10초 중단 → db_errors 11 누적, 복귀 뒤 backlog 0.
- 증상: 장애 주입 `collector` 에서 수집기를 SIGTERM 으로 죽인 뒤 **재시작한 수집기가 바로 죽음** → 대시보드 "온라인 장치 0", 통계가 11:39:17 에서 멈춤, inject.py 는 복구를 150초 기다림.
- 원인: 재시작 명령의 파이썬을 `/proc/<pid>/exe` 로 골랐다. 이것은 심볼릭 링크를 끝까지 푼 `/usr/bin/python3.12` 라서 **venv 정보가 사라진다** → `import paho` 실패. 파이썬은 "실행 파일 경로 옆의 pyvenv.cfg" 로 venv 를 알아보므로 `.venv/bin/python3` 경로 그대로 실행해야 한다.
- 해결: `/proc/<pid>/environ` 의 `VIRTUAL_ENV`·`PATH` 를 읽어 같은 환경으로 재시작(`pick_python`), 1.5초 안에 죽으면 로그 끝을 보여 주고 측정을 중단(150초 헛기다림 제거).
- 배운 것: "같은 명령으로 재시작"은 실행 파일 경로만이 아니라 **환경(venv, PATH)** 까지 같아야 한다. 프로세스 관리자(systemd)가 환경을 통째로 기록하는 이유.
- 증상(재현): "오프라인 이벤트 20" 이 D2 와 똑같이 20. 가설 강화: Mosquitto 는 **자기가 종료될 때 접속 중인 모든 클라이언트의 유언을 발행**하는데, 수집기 소켓에 다 쓰기 전에 소켓을 닫아 앞쪽 20개만 도착 → `diag.py` 가 0.5초 안에 몰린 offline 을 군집으로 묶어 이 경우를 가려낸다. 확인 질의: `SELECT time, device_id FROM events WHERE kind='offline' ORDER BY time DESC LIMIT 25`.
- 환경 함정 2건: (1) venv 는 시스템 패키지를 가리므로 ROS 2(rclpy→yaml·numpy)와 같이 쓰려면 `python3 -m venv --system-site-packages .venv` (2) 터미널마다 `source` 를 잊지 않게 `.bashrc` 에 저장소 이동 + venv + ROS 2 + `RT_REPO_ROOT` 자동 설정을 넣음.

## 2026-11-04 (D5 실측 1차 결과 + 측정 도구 수정)
- 결과(장애 주입, 가상 50대 1 Hz, QoS 1): broker 10초 → 전 장치 복귀 2.9초, 유실 0(가장자리 제외, 아래 참고) · db 10초 → backlog 0 까지 1.4초, 뒤늦게 적재 570행, 유실 0 · collector 10초(지속 세션) → 첫 통계 1.2초, 전 장치 1.6초, 유실 0 / 1312 · bad_firmware → 3/50 에서 롤백 1.0초. `assert_results` 전부 ok.
- 확인됨(오프라인 20): 20개가 **같은 1 ms 안에**(02:38:20.594) vdev-001~019·021 — 브로커 `stop` 시각과 일치, 장치 번호가 접속 순서. = Mosquitto 가 종료되며 유언을 일괄 발행하고 소켓을 닫기 전에 앞쪽 20개만 수집기에 쓴 것. 장치는 멀쩡했다. `diag.py` A절이 이 경우를 "브로커 종료 시 일괄 유언"으로 자동 분류하도록 고침(전에는 재전송된 데이터 때문에 "가짜 offline" 이라는 틀린 이름을 붙였다).
- 확인 강화(10초 튐): 튐 13회, 간격 중앙값 10.4초, insert_ms 는 평소와 같음(36.7 vs 30.8 ms) → DB 아님, keepalive 10초(PINGREQ) 가설 그대로. 결정 실험은 `--keepalive 30` (다음 실측). 복구 폭주 초(590·2532·20057 msgs/s)는 튐이 아니라 홍수이므로 B절에서 제외하도록 고침.
- 발견(측정 맹점): vdev-003·005 는 브로커 중단 직후 12초 데이터 공백인데 유실 계산은 0 이었다. 원인: 유실 = max(seq)−min(seq)+1−행수 를 **장애 창 안에서만** 계산 → 창 시작 직후 잃은 메시지는 min(seq) 기준점 뒤로 숨는다. 해결: 기준점을 **장애 직전 30초의 마지막 seq** 로 고정(`measure_loss`). 두 장치가 "유실"인지 "스레드 멈춤(seq 연속)"인지는 `diag.py` C절(seq 틈)이 가른다 — 다음 실측에서 확인.
- 발견(큐 상한): 재시작 실패로 수집기가 7.5분 비어 있던 동안 브로커가 QoS 1 메시지를 들고 있다가 재접속 때 1초에 20,057개를 넘겼다. 50대 × 450초 = 22,500 > `max_queued_messages 20000` → 약 2,400개는 브로커가 버렸을 것. "지속 세션 = 무한 보관"이 아니라 **상한이 있는 보관**임을 숫자로 봄. 상한은 중단 허용 시간(분) × 장치 수 × Hz 로 정한다.
- 수정: `make_table3.py` 가 Decimal × float 로 죽음(psycopg 의 sum() 은 Decimal) → float 변환. `inject.py` 의 "보호 없었다면" 이 장치 수를 두 번 곱해 25,000 으로 나옴 → rate(전체 msgs/s) × 초 = 500 으로.

## 2026-11-04 (D5 실측 2차 — 고친 측정으로 다시 본 유실 3종)
- 결과: 고친 `measure_loss` 로 broker 10초 재측정 → **유실 53 / 1434** (전에는 0 으로 보이던 것). diag C 절이 어디서 잃었는지 장치·seq 단위로 보여 줌.
- 유실 ① 브로커 재시작 경쟁: 50대 중 4~5대(003·004·011·027 / 1차는 003·005·027·028·031)가 정전 시작부터 **13초** = 12개씩 유실, 1대(042)는 5개. 원인: `persistence false` 라 브로커가 재시작되면 수집기의 지속 세션(구독)이 사라진다 → 수집기보다 **먼저** 재접속한 장치가 버퍼를 쏟아 내면 구독자가 없어 브로커가 버린다. 042 의 "절반만 유실"은 버퍼를 쏟는 도중에 수집기 구독이 들어온 것. 해결: `persistence true` + 데이터 볼륨 → 구독이 재시작을 넘겨 살아 있으므로 큐에 담긴다. **재측정 필요.**
- 유실 ② 수집기 종료 순간: SIGTERM 때마다 **장치당 1개**(11:39:16 50대, 11:50:13 28대). 수집기가 받아서 PUBACK 은 보냈지만 아직 DB 에 안 넣은 "그 1초의 pending" 이 프로세스와 함께 사라짐. 해결: SIGTERM/Ctrl+C 를 플래그로 받아 수신을 끊고 마지막 flush 를 한 뒤 종료(`shutdown()`). 남는 틈: SIGKILL(진짜 크래시)에서는 여전히 잃는다 → 완전한 해법은 DB 적재 뒤 수동 ACK(paho manual_ack) — 2주 계획 밖, DECISIONS 에 기록.
- 유실 ③ 큐 상한(예측 적중): 수집기가 7.5분 비어 있던 동안 11:39:17~11:46:09(412초 × 50 ≈ 20,600)까지는 브로커가 보관하고, 그 뒤 **11:46:09~11:47:00 의 49~50개/장치 = 2,450개는 버림** = `max_queued_messages 20000` 상한. Mosquitto 는 꽉 차면 **새 메시지**를 버린다(오래된 것 유지). 상한은 "허용 중단 시간 × 장치 수 × Hz" 로 정해야 하고, 그 이상은 장치 버퍼(store-and-forward)가 맡는 구조가 맞다.
- 관찰(가설): 20,057개가 1초에 쏟아진 직후 11:47:21 에 전 장치가 1개씩 더 잃고 11:48:13 에 50대가 **동시에 재접속**(online 50) + 11:48:15 에 2,532개 재전송 폭주. 단일 스레드 브로커가 큐 방류에 묶여 keepalive(10초×1.5) 안에 PINGRESP 를 못 보내 전원이 끊겼다가 돌아온 것으로 보인다(천둥 떼, thundering herd). 확정하려면 브로커 로그(`log_type all`)가 필요 — 다음 기회에.
- 표③-1 의 "유실 4.46%" 는 30분 창 전체(수집기 7.5분 공백 실험 포함)라 실험 흔적이 다 들어간 값. 장애별 숫자는 ③-2 가 맞다.

## 2026-11-04 (D5 실측 2차 결과 — 고친 뒤 재측정)
- 결과: broker 10초 → **유실 0 / 1400**(전 53), collector(qos1) 10초 → **유실 0 / 1311**(종료 순간 1개/장치도 사라짐), 전 장치 복귀 2.9초 / 1.6초. diag C 절 "틈 없음". 표③-1 유실 0.00%. 브로커 persistence true 와 수집기 곱게 종료가 각각 겨냥한 유실을 정확히 없앴다.
- 증상(새 발견): 수집기 둘이 동시에 뜨면 2초마다 `connected, subscribed` 가 찍히고 msgs/s 가 50/0 으로 번갈아 나옴. 원인: 장애 주입이 재시작한 수집기(배경, pid 3456)가 살아 있는 채로 터미널에서 또 띄움 → 같은 client_id "collector" → 브로커가 옛 접속을 밀어냄 → 둘이 번갈아 재접속. 해결: `fleet/logs/collector.lock` flock 으로 한 번에 하나만, 두 번째는 pid 를 알려 주고 물러남.
- 증상(새 발견): persistence true 뒤로 브로커 재시작 때 offline 이벤트가 20 + 50 으로 늘어남. 원인: 종료 때 발행된 유언 "offline" 이 **보관(retained)** 되어 재시작 뒤 수집기가 구독하는 순간 50개가 다시 내려옴(retain=1). 해결: retain=1 로 받은 상태 메시지는 "지금 상태"이지 "사건"이 아니므로 events 에 넣지 않는다(카운터만). 대시보드 오프라인 수가 뜻대로 돌아온다.
- diag A 군집 판정 수정: 이전 이벤트 기준으로 이어 붙여 1초 간격 이벤트가 하나의 거대 군집(209대)으로 뭉쳤다 → 첫 이벤트 기준 0.5초로 끊고 군집마다 한 줄.
- 남은 미확정: 10초 튐(keepalive 가설) — 이번 창은 잡음(재접속 싸움)이 섞여 판정 보류. `--keepalive 30` 실험은 다음 실측.

## 2026-11-04 (GitHub 첫 push · CI 1차)
- 저장소 공개: https://github.com/ohevance/rt-robot-data-infra (커밋 D0→D5 + 실측 2회). CI 1단계(rt_core) 통과, 2단계 `fleet_integration` 실패.
- 증상: 컨테이너 안 `pg_isready` 가 "accepting connections" 라고 한 1초 뒤 `migrate.py` 가 "server closed the connection unexpectedly".
- 원인: TimescaleDB(Postgres) 이미지는 첫 기동 때 **임시 서버(유닉스 소켓만)로 init.sql 을 돌린 뒤 끄고 진짜 서버를 다시 띄운다**. 컨테이너 안 pg_isready 는 그 임시 서버에도 "준비됨"이라 답하고, 밖에서 TCP 로 붙는 순간 서버가 재시작 중이라 끊긴다. WSL 에서는 볼륨에 데이터가 이미 있어 init 단계가 없었기에 안 보였다.
- 해결: 준비 확인을 "밖에서 실제로 붙어 보기"로 — `migrate.py --wait N` 이 1초마다 재시도(기본 60초). integration.sh 와 수집기 Dockerfile 이 이것을 그대로 쓴다.
- 배운 것: 헬스 체크는 **소비자와 같은 경로**(같은 호스트·같은 프로토콜)로 해야 한다. 컨테이너 안의 체크는 "프로세스가 있다"지 "밖에서 쓸 수 있다"가 아니다.

## 2026-11-04 (CI 2차 — 3잡 전부 통과)
- `rt_core` 1m13s · `mujoco` 25s · `fleet_integration` 1m52s. 어제 "미검증"으로 남긴 셋이 한 번에 확인됨: MuJoCo 3.3.2 타르볼 존재, menagerie `trs_so_arm100` 경로, 액추에이터가 position 타입(관절 0 이 2초에 0.2988 rad 이동, 목표 0.3).
- 숫자(러너): MuJoCo 한 주기 비용 p50 6.4 / p99 8.5 / max 29.4 us — 1 kHz 주기의 0.9%. 즉 물리 계산은 예산의 1% 이고 나머지는 전부 "깨어나는 지연"의 몫이라는 뜻 → 표①의 RT 커널 실측이 왜 핵심인지가 숫자로 설명된다.
- 숫자(러너, 10대 2 Hz): broker 5초 → 전 장치 3.2초, 유실 0/318 · db 5초 → backlog 0 까지 1.2초, 뒤늦게 112행, 유실 0 · collector(qos1) 5초 → 1.5초, 유실 0/280 · bad_firmware → 1/10 에서 롤백 0.4초. WSL(50대) 결과와 같은 모양 — 환경이 아니라 설계가 만든 숫자.
- 남은 경고: actions/checkout@v4·upload-artifact@v4 의 Node 20 deprecation 안내. 실패 아님. 초록일 때 건드리지 않고, 다음 번들 묶음에서 v5 로 올린다.

## 2026-11-04 (D5 MuJoCo — WSL 노드에 물리 연결 성공)
- `get_mujoco.sh` → `rt_core_mj` 빌드 → 테스트 통과 → colcon(MuJoCo 옵션) → `so101_mujoco.params.yaml` 로 노드 기동. 관절 이름 6개(Rotation·Pitch·Elbow·Wrist_Pitch·Wrist_Roll·Jaw)가 menagerie 모델과 그대로 일치해 매핑 수정 없음.
- 숫자(WSL, 일반 스케줄링 — prlimit 를 안 건 터미널이라 sched_fifo=false):
  - 단독 테스트: 물리 한 주기 p50 4.9 / p99 6.3 / max 20.8 us (러너 6.4 / 8.5 / 29.4 와 같은 급).
  - 노드 안 `work_us`(제어 단계 + mj_step + 상태 벨트): p50 41.3 / p99 145.1 / max 247.4 us — 단독보다 큰 이유는 1 kHz 루프의 캐시 냉각·WSL 가상 커널 선점·RT 우선순위 없음. 그래도 1 ms 예산의 15%(p99) 안. `wake_us` p99 339 / max 2026 us 는 D1 과 같은 WSL 한계.
  - 명령 50 Hz 를 주자 `state` READY → RUNNING, `watchdog` tripped → ok, `step_limited` 10(그리퍼 0.5 rad 를 0.05 씩), 221 명령 전부 적용, 드롭 0.
- 물리가 보여 준 것(SimLag 로는 못 보는 것): 목표 [0.3, -0.2, 0.1, 0, 0, 0.5] 에 대해 위치 [0.299, **-0.180**, 0.109, 0.002, 0.000, 0.499]. 어깨 Pitch 관절만 0.02 rad(약 1.1°) 못 미침 = **중력에 팔 무게가 걸려 position 액추에이터(유한한 kp)가 처지는 정상 상태 오차**. 실물에서도 같은 자리에서 같은 일이 난다 → 중력 보상(토크 피드포워드)이 왜 필요한지의 숫자 근거.
- 함정: 터미널 B 의 `ros2 topic echo` 가 "does not appear to be published yet". 노드는 살아 있고 `node list` 에는 보임. 원인: 아침 DDS 측정 때 다른 RMW 로 떠 있던 **ros2 데몬**이 Fast DDS 노드의 토픽을 못 봄. 해결: `ros2 daemon stop` 후 재시도. 배운 것: RMW 를 바꿔 가며 실험한 뒤에는 데몬을 지운다(데몬은 사용자당 하나, 처음 뜬 RMW 로 고정).
- 소음: `ros2 topic echo /joint_states --once` 가 "A message was lost!!! total count change:10" — 100 Hz 발행을 늦게 구독한 CLI 가 자기 큐(깊이 10)에서 밀린 것을 알려 주는 것. 노드 쪽 드롭(state_drops)은 0.

## 2026-11-04 (D6 시작 — 기록 파이프라인·발표 자료·Pi 안내)
- `data_pipeline/record.sh`(rosbag2 MCAP, timeout -s INT 로 곱게 닫기) + `bag_to_csv.py`(CSV 3개 + summary.md: 토픽별 실제 Hz·틈, rt_status 최대값, 관절별 추종 오차). 샌드박스에는 ROS 2 가 없어 가짜 rosbag2_py 로 논리만 검증(100 Hz 10초, 0.5초 틈 1개, 어깨 처짐 0.02 rad → 요약표에 그대로 나옴). WSL 첫 실행에서 rosbag2_py import 가 첫 확인 대상.
- 영상 대본(`docs/VIDEO_SCRIPT.md`, 6장면 2:00) · 이력서 문장(`docs/RESUME_LINES.md`, 경력 숫자 5개는 빈칸) · Pi 4B 4 GB 기준 표① 안내(`docs/SETUP_RT_MEASURE.md` 전면 개정: Imager → SSH → 일반 커널 기준값 → `pro enable realtime-kernel --variant=raspi` → RT 측정 4조건 → isolcpus 선택).
- CI 액션 checkout/upload-artifact 를 v5 로(Node 24). 다음 push 에서 초록 유지되는지 확인.

## 2026-11-04 (소실험 2건 — keepalive 박자 확정, QoS 0 비교줄)
- 실험 ① A/B(같은 수집기·같은 조건, 가상 50대 QoS 1): keepalive **30초 → 튐 0회(172초)**, keepalive **10초 → 튐 2회, 간격 정확히 10.0초**(05:50:08·05:50:18), p95 ≈ 10 ms, max ≈ 32 ms, insert_ms 는 평소와 같음. → 10초 주기 튐의 원인은 장치 50대의 **keepalive 박자**로 확정(거의 동시에 접속해 박자가 맞고, 그 순간 스레드 100개짜리 장치 프로세스가 멈칫). 횟수가 아침(281초에 13회)보다 적은 것은 QoS 1 양방향 트래픽이 keepalive 를 대부분 가려 주기 때문으로 **추정**.
- 설계 결론: keepalive 는 "죽은 장치 감지 속도(1.5배 뒤 유언)"와 "주기적 동기 부하"의 맞교환. 30초로 늘리면 튐은 없지만 감지가 45초. 더 나은 답은 장치마다 keepalive 에 0~N 초 jitter → `virtual_fleet.py --keepalive-jitter`. (thundering herd 의 작은 버전)
- 실험 ②(수집기·장치 모두 QoS 0): 수집기 10초 중단 → **유실 508 / 1312**(예측 500 = 50대 × 10초, +8 은 종료·재시작 순간). QoS 1 지속 세션의 0 과 나란히 표③-2 두 줄. "QoS 1 은 공짜가 아니지만 수집기 재시작을 공짜로 만든다"의 숫자.
- 증상: 가상 장치 두 벌을 겹쳐 띄워 `reconnects=1675`(50대 × 33회). 같은 client_id 충돌(수집기 때와 동일). 해결: 잠금을 `fleet/common/single_instance.py` 로 빼고 수집기·가상 장치(prefix 별) 둘 다 사용. 수집기 컨테이너 Dockerfile 에 common/ 복사 추가.

## 2026-11-04 밤 (D6 — Pi 4 세팅, 일반 커널 기준값 4줄, Ubuntu One 장애)
- 준비: 갖고 있던 Pi 4 Model B 4 GB 의 카드는 다른 곳에서 쓰던 Raspberry Pi OS 12(bookworm)라 지우지 않고 보관, 새 카드(Samsung PRO Plus 512 GB)에 Raspberry Pi Imager 로 **Ubuntu Server 24.04.5 LTS 64-bit** 를 구움(hostname `pi-rt`, 사용자 계정, Wi-Fi·SSH 비밀번호 인증을 Imager 설정에서 미리 넣음). 첫 부팅만 모니터로 확인(IP, 커널 `6.8.0-1064-raspi`, 45 °C), 이후 전부 PC PowerShell 에서 `ssh <사용자>@<Pi IP>`. 이더넷 없이 Wi-Fi 로 충분했다.
- 빌드: `apt install git build-essential cmake rt-tests stress-ng` → clone → rt_core 빌드(GCC 13.3, arm64) → **ctest 4/4 통과**. x86(WSL·CI)에서 쓴 코드가 arm64 에서 수정 없이 돌았다(고정 크기 배열·표준 C++17 만 쓴 덕).
- 결과(일반 커널 6.8.0-1064-raspi, governor performance, `docs/measurements/table1_pi4.md`):
  - jitter_bench 60초: 한가 p99.9 18.8 / **max 24.9** us · 부하(stress-ng cpu4+io2+vm1) p99.9 201.9 / **max 781.2** us, `work time` max 134.9 us(50 us 일하는 도중에 밀림), 드롭 0.
  - cyclictest(4 CPU, 가장 나쁜 CPU): 한가 300초 p99.9 57 / **max 376** us · 부하 120초 p99.9 118 / **max 695** us, 오버플로 0.
- 읽기: **한가해도 5분 창에서는 376 us 가 나온다**(60초 단일 스레드 jitter_bench 는 24.9). 드문 커널 내부 작업(타이머 이동·Wi-Fi 드라이버·백그라운드 서비스 중 무엇인지는 미확인)이 분 단위로 한 번씩 수백 us 를 가져간다 → 일반 커널에서는 "부하가 없으면 안전"이 성립하지 않는다. 부하 중 max 695~781 us 는 1 ms 예산의 70~80%. RT 커널의 과제는 이 max 를 200 us 아래로, 한가/부하 차이를 작게.
- 발견(열): 부하 75초에 **45 → 75 °C**(방열판 없음). Pi 4 는 80 °C 부터 펌웨어가 클럭을 내리므로 300초 부하는 수치를 오염시킨다. `/sys/devices/platform/soc/soc:firmware/get_throttled` 가 0 → 오늘 값은 전부 깨끗함. 결정: 부하 측정은 120초까지(RT 커널도 같은 120초로 비교), 측정 스크립트가 온도·스로틀을 `.meta` 에 자동 기록(`scripts/lib_thermal.sh`, `cyclictest_run.sh`, 새 `jitter_run.sh`), `make_table1.py` 가 비고에 "온도 a→b °C, 스로틀 0" 또는 "⚠ 스로틀" 을 붙인다.
- 실수: WSL 용 scp·git 명령을 **Pi 창**에 침 → Pi 가 자기 자신에게 복사하려다 root 소유 파일(sudo 로 만든 결과)에 "Permission denied", git 은 "Author identity unknown". 해결: Pi 에서 `git reset` + `chown -R <사용자>`, 명령은 WSL 창에서 다시. 배운 것: 창이 둘 이상이면 안내에 **[Pi 창]/[WSL 창]** 을 붙인다(SETUP 문서 수정). 결과 원본은 WSL 로 `scp` 해 커밋(b4c6f3b) — Pi 는 측정만 하고 커밋하지 않는다.
- 막힘(Ubuntu One): 실시간 커널은 Ubuntu Pro 토큰이 필요한데 Ubuntu One 가입이 두 번 실패. `ubuntu.com/pro` 경유는 "Oops", `login.ubuntu.com/+new_account` 직접은 오류문이 보였다: *"Dry run of setting username(...) with placeholder openid_identifier in Launchpad failed with (The read operation timed out)"* = 가입 시 Launchpad 에 사용자명을 검사하는 호출이 시간 초과 → Canonical 쪽. 입력값(한글 이름 등)과 무관. 내일 오전 재시도. 플랜 B 는 WSL 에서 Pi 커널(rpi-6.12.y)을 PREEMPT_RT 로 크로스 컴파일(2~3시간) — 내일도 막히면 그때.
- 다음: 토큰 → `sudo pro attach` → `sudo pro enable realtime-kernel --variant=raspi` → 재부팅 → `uname -r`, `/sys/kernel/realtime` = 1 → 같은 4조건(한가·부하 × jitter_bench·cyclictest) + CPU 고정(`--cpu 3`) + (선택) isolcpus=3 → `table1_pi4.md` 갱신 → README 숫자.

## 2026-11-05 오전 (D7 — Pi 4 PREEMPT_RT 실측: 커널 → 고정 → 격리, 그리고 도구 불일치)
- Ubuntu One: 어젯밤의 Launchpad time out 이 아침엔 사라져 `login.ubuntu.com` 에서 바로 가입(ubuntu.com/pro 경유 아님) → 인증 메일 → `ubuntu.com/pro/dashboard` 의 Free Personal Token. 교훈 그대로: 입력값이 아니라 서버 쪽 문제였고, 기다리는 것이 답이었다.
- Pi: `git pull` 이 어제 sudo 로 만든 untracked 결과 파일에 막힘("would be overwritten by merge") → GitHub 에 같은 파일이 이미 있으므로 `rm -f docs/measurements/*pi4*` 뒤 pull. `sudo pro attach` → `sudo pro enable realtime-kernel --variant=raspi`(약 2분) → 재부팅 → **`6.8.0-2054-raspi-realtime`, `/sys/kernel/realtime` = 1**.
- 결과(RT 커널, governor performance, 전부 스로틀 0, `docs/measurements/*_pi4_rt_*`):
  - jitter_bench 60 s: 한가 p99.9 20.5 / **max 27.8**(일반 24.9) · 부하 p50 26.1 / p99 185.2 / p99.9 241.5 / **max 300.6**(일반 781.2), work max 97.7(134.9) · 부하+CPU 3 고정 p99 169.1 / **max 311.5**, work max 86.1 · 부하+**isolcpus=3** p99 108.3 / p99.9 146.2 / **max 189.3**, work max **53.1**.
  - cyclictest(4 CPU 최악): 한가 300 s **max 37**(일반 376, CPU 별 34·37·26·29) · 부하 120 s **max 132**(일반 695, CPU 별 67·110·82·132).
  - 온도: 각 부하 측정 45~51 → 64~74 °C. 120초 상한 덕에 80 °C 를 넘기지 않았다.
- 읽기 ① (커널): 최악을 자른다 — jitter 781 → 301(2.6배), cyclictest 376 → 37(10배), 695 → 132(5배). 어제의 "한가해도 5분에 376" 이 37 로: 그 커널 내부 작업이 이제 선점된다. 한가 jitter max 는 24.9 → 27.8 로 같은 급 — 경쟁자가 없으면 커널 종류와 무관(하드웨어 바닥 ≈ 19 us). 1 ms 예산 대비 78% → 30%; 2 kHz(500 us) 루프라면 일반 커널은 깨지고 RT 는 버틴다.
- 읽기 ② (비용, 숨기지 않는다): 부하 p99 146 → 185, p99.9 202 → 242 로 **보통 나쁜 경우는 오히려 나빠졌다**. 인터럽트를 스레드로, 스핀락을 뮤텍스로 바꾼 고정 비용. RT 커널은 평균을 사는 것이 아니라 상한을 사는 것.
- 읽기 ③ (고정 vs 격리): CPU 3 고정만으로는 301 → 311 로 효과 없음 — 그 CPU 에서 stress·IRQ 스레드·커널 스레드가 그대로 돈다. isolcpus=3 으로 그것들을 치우자 max 189, 그리고 **work max 135 → 53**: 50 us 일하는 동안 거의 안 밀린다 = CPU 3 의 경쟁자가 사라졌다는 직접 증거. 잔여 189 는 격리된 CPU 에도 오는 것(타이머 인터럽트 처리, 전역 동기화 IPI)으로 **추정**, Pi 4 의 알려진 바닥(100~200 us)과 맞는다. 예산의 18.9%.
- 발견(도구 불일치)과 검증(E19-d, 1분짜리 4회, 전부 격리 안 된 CPU 2·부하 256M): 같은 부하에서 cyclictest max 132 vs jitter_bench 301 — 2.3배.
  - A-1 `--work-us 0`(일 없이 깨기만) → **max 270** (p99 169 → 116). 가설 "50 us 일하는 동안의 노출" 은 max 에 대해 **기각** — 일은 p99 를 낮추지 max 를 안 낮춘다.
  - A-2 cyclictest 를 같은 설정(`-t 1 -a 2 -p 80`)으로 → **max 274**. **측정기는 맞다**(274 vs 270, 1.5%). "내가 만든 자가 틀렸다"는 닫힘.
  - B jitter_bench prio 90 → 290. 우선순위 무관(80 과 90 사이에 끼어드는 커널 스레드 없음).
  - C cyclictest `-S`(CPU 마다 스레드, 격리라 3개) 256M → **210**(204·99·210). 스레드 배치가 약 60 us 를 설명.
  - 남은 210 → 132 는 **부하 정의**로 추정: E19-a 의 cyclictest 는 `--vm-bytes 512M`(버퍼가 커서 munmap → TLB 동기화 IPI 가 드묾) + 격리 전(stress 4개가 CPU 4개에 분산). 두 요인을 가르는 한 번(512M 로 C 반복)은 생략 — 표①의 결론에 영향 없음.
  - **내 실수**: 두 스크립트의 부하가 달랐다(cyclictest_run 512M, jitter_run 256M). 도구를 비교하려면 부하가 같은 함수에서 나와야 한다 → `scripts/lib_stress.sh` 로 묶고 `.meta` 에 `stress_vm_bytes`·`prio`·`work_us` 기록, `make_table1.py` 비고에 표시, `jitter_run.sh` 에 `JITTER_WORK_US`·`JITTER_PRIO`·`STRESS_VM_BYTES` 환경 변수. 손으로 돌린 4건의 `.meta` 는 손으로 적음.
  - 표① 읽는 법: cyclictest 줄 = "커널이 주는 깨어남 바닥"(CPU 마다 스레드, 큰 버퍼 부하), jitter_bench 줄 = "일하는 스레드 하나가 겪는 지연"(작은 버퍼 부하). 로봇에 가까운 쪽은 후자. 두 도구의 상대 변화(일반 → RT → 격리)는 같은 방향.
- Pi 결과 14건 + .meta 를 WSL 로 scp → `table1_pi4.md` 14줄 → 커밋 8f06d39(사용자). Pi 의 `git pull` 이 untracked 결과 파일에 막힌 일(어제 파일)은 `rm` 으로 해결 — 이제 Pi 에서는 측정 뒤 scp 가 끝나면 결과 파일을 지우거나 다음 pull 전에 지운다.
- 문서(같은 날 옮김 규칙): 실시간 커널이 무엇이 다른가(GLOSSARY), 스로틀을 왜 적나(GLOSSARY), "왜 하는가·어떻게 판단했는가는 반드시 문서에"(READING_GUIDE §4), 표①의 조건이 왜 이 조합인가(DECISIONS), 실험 순서도를 "기준(마름모) → 못 넘으면 다음 실험" 형식으로(EXPERIMENTS §0, 표①②③·물리 4그림), **실험 하나에 한 장**(`docs/experiments/` 20장: 왜·어떻게·결과·처음 읽는 사람을 위한 분석·면접 한 문장·어디에 적혀 있나).
- 기록 파이프라인 첫 실행(WSL): `record.sh 30` 이 "Positional topics deprecated" 경고 뒤 아무것도 안 찍고 30초가 지나도 안 끝남. 원인: 스크립트 안의 `timeout` 이 (기본 동작으로) recorder 를 별도 프로세스 그룹에 두고, `ros2 bag record` 는 키보드 제어(SPACE 일시정지) 때문에 터미널을 읽으려다 **SIGTTIN 으로 정지** → 로그도 없고 30초 뒤 SIGINT 도 못 받음. 해결: `timeout --foreground` + `--disable-keyboard-controls` + `--topics`. 배운 것: 터미널을 읽는 프로그램을 스크립트 안에서 timeout 으로 감쌀 때는 `--foreground` 가 필수 — "조용히 멈춤"은 죽은 것이 아니라 정지된 것일 수 있다(`pkill -CONT` 로 깨운 뒤 `-INT`).
- 기록 파이프라인 2차(수정 뒤): `record.sh 30` → MCAP 1.07 MB → `bag_to_csv.py` → `/joint_states` 2,964행 **100.0 Hz 틈 0**, `/joint_command` 1,482행 50.0 Hz, `/rt_status` 29행 1.0 Hz, 드롭 0. 추종 오차 표: **shoulder_lift 0.0191 rad(1.1°)**, elbow_flex 0.0094, wrist_flex 0.0025 — E16 에서 눈으로 읽은 어깨 처짐이 자동 요약에 그대로, 팔꿈치 0.5° 는 요약이 새로 찾음. rt_status(WSL 참고값): wake p99 288~606 us, work p99 103~151 us. 원본 `docs/measurements/record_*_wsl_20261105.*`(c71a5f2). 상세 `docs/experiments/E20.md`.
- CI 빨강(오늘 push 들 `fleet_integration` X): 로그 `NameError: name 'request_stop' is not defined` — 수집기가 시작 직후 죽어 장치 0대·유실 집계 불가. 원인: 11/04 patch-08(861e628)에서 단일 인스턴스 잠금을 공용 모듈로 옮기며 **`request_stop` 함수를 통째로 지웠다.** 단위 테스트(당시 5개)는 Collector 클래스만 쓰고 `main()` 을 안 타서 못 잡았고, WSL 에서도 그 뒤로 수집기를 다시 띄운 적이 없어 안 보였다 → 통합 테스트(CI)만 빨갰다. 그 사이 push 가 측정 파일·문서 위주라 CI 를 안 봤다(8f06d39 이후 확인 누락). 해결: 함수 복원 + `test_collector_resilience` 에 **main() 한 바퀴 스모크**(STOP 플래그를 미리 세워 루프 0바퀴 → shutdown, 시그널 핸들러 직접 호출). 배운 것: 진입점(main)은 단위 테스트가 최소 한 번은 타야 한다; push 뒤 `gh run list` 는 문서 커밋이라도 본다 — 빨간 배지는 포트폴리오 첫 화면이다.
- 문서: `docs/ENVIRONMENT.md` 신설 — 네 곳(개발 PC·Pi·GitHub/CI·작성 작업본)의 역할과 왜 한 곳으로는 안 되는지, 코드·숫자가 오가는 길과 트리거, 곳마다 "정상" 신호와 비정상 때 첫 명령, CI 의 환경·잡 3개 순서도·실패 유형별 판단·Jenkins 대응표·테스트 목록, 날마다 하는 점검 5분. 오늘 채팅에서 설명한 것(러너는 내 노트북이 아니다, Jenkins job ↔ workflow, 테스트 케이스 등록은 없다)을 옮김.

## 2026-11-05 오후 (D7 — 발표 장표 138장 + 장표마다 설명 문서, 순서도 논리로)
- 요구 사항(순서대로 정리한 것): ppt 는 많을수록 좋고(구조·실험·**모든 소스 코드**), 장표마다 왕초보용 설명 문서(doc) 하나씩, 다양한 도형·화살표, 그림은 최고 해상도 → "실제 로봇을 움직이기 위해 뭐부터 시작해서 결국 로봇을 움직이는지"의 그림이 있어야 하고 각 단계에서 소스까지 추적 → 순서는 **top → down(끝은 로봇이 이렇게 움직임)** → 목차와 내용이 **순서도의 로직처럼** → **왕초보 입장에서 로봇을 움직이기까지의 과정을 앞부분에**, 핵심 소스 코드와 위치 포함, 페이지 수 무관 → 시험·검증은 뒤로 빼고 번호만 → 도형과 그림을 많이.
- 만든 것: `docs/deck/rt-robot-data-infra.pptx`(138장) + `docs/deck/notes/NNN.docx`(138개, 원본 `notes_md/NNN.md`) + `docs/deck/SLIDES.md` + `docs/deck/build/`(생성 코드·그림 원본·규칙). 구조는 DECISIONS 11/05 (장표) 참고.
- 어떻게: 장표 내용은 파이썬 dict(`content_a~d.py`, `gates.py`, `diagrams_front.py`) → `make_slides.py` 가 crumb(지금 어디)·next(다음 ▶)·들머리 16장·그림 11장을 끼우고, `"verify": True` 장표를 1·2부에서 꺼내 3부로 옮기고, `{{first:제목}}` 을 장표 번호로 바꿔 `slides.json` → `build_deck.js`(pptxgenjs) 가 pptx. 코드는 `cu.code(파일, 시작, 끝)` 로 저장소 파일에서 그대로. Mermaid 그림 10장은 `mmdc -s 3`(2352 px 폭). 실험 사슬·들머리·CI 잡·단계 그림 9장·타임라인은 pptx 도형으로 직접(글자 선명, 고치기 쉬움), 관절별 추종 오차는 원생 막대 그래프.
- 검증: `validate.py` 통과 → LibreOffice 로 PDF → 전 장표 축소판을 보며 고침. 고친 것: (1) 코드 상자 글자 크기 자동 맞춤 — 처음엔 가장 긴 줄 기준이라 짧은 코드도 작아짐 → 접힐 줄 수까지 세어 높이에 맞는 가장 큰 크기로; 그래도 작은 긴 코드 7건은 두 장으로 나눔(루프 본체·워치독·전이표·flush/drain·run_stage·integration.sh·thermal/stress). (2) 순서도 화살표의 답(글)이 옆 상자를 덮음 → 화살표 폭 안에만, 줄 바꿈 자리는 빈 쪽에. (3) CI 잡 그림(세로로 긴 Mermaid)이 작게 보임 → 도형 순서도 3장으로. (4) 글자 폭 어림(영문 0.62 em·한글 1.05 em)을 넉넉하게 — LibreOffice 대체 글꼴에서 넘치던 kTable·SQL 코드가 들어옴. (5) 소스 코드 지도 표가 넘침 → 9 pt, 각주로.
- 사실 수정(장표 만들다 발견): fleet 단위 테스트 수가 문서마다 17건으로 적혀 있었는데 실제는 6 + 3 + 6 = **15건**(test_collector_resilience 는 6건) → ENVIRONMENT.md §5, README 표 ④(Python 3 → 15, 상태 '완료, CI 초록') 수정. publish_status 줄 범위 233-307 → **233-291**.
- 설명 문서: 규칙 `build/NOTES_GUIDE.md`(여덟 절: 왜 있나 · 하나씩 읽기 · 용어와 단위 · 쉬운 예시 · 숫자의 출처(확인/추정) · 오해·함정 · 면접 한 문장 · 관련 파일과 다음 장표). 작성 시 코드 장표는 그 줄을 다시 읽고, 숫자는 measurements/experiments/LOG 와 대조. md → docx 는 pandoc.
- 배운 것: 장표도 코드처럼 "생성기 + 원본 데이터"로 두면 순서를 통째로 바꾸는 요구(오늘 세 번)에도 내용 파일은 거의 그대로이고 조립 규칙만 바뀐다. 장표 번호를 손으로 적지 않는다(자리표시). 긴 코드는 글자를 줄이는 것보다 장을 나누는 것이 낫다.
- 남은 것: 작성자가 장표로 직접 설명해 보는 분석 기간(5회차)에서 막히는 장표의 설명 문서를 고친다. 영상 녹화는 그 뒤.

## 2026-11-06 (D8 — 제출 서류 작성, 공개 문서 점검)
- 만든 것(저장소 밖): 제출용 PDF 두 벌 — 이력서 + 자기소개서(4쪽), 포트폴리오 설계서(21쪽, 이 저장소의 README·EXPERIMENTS·DECISIONS·measurements 를 설계 관점으로 추린 것). 숫자는 전부 `docs/measurements/` 와 대조했고, 독립 검토(면접관 시점)를 거쳐 고쳤다.
- 점검에서 나온 것(공개 저장소): (1) `LOG.md`·`SETUP_RT_MEASURE.md`·`VIDEO_SCRIPT.md`·`video/` 에 Pi 의 사설 IP 와 계정 이름, 개인 PC 경로가 그대로 있었다 → 전부 `<Pi IP>`·`<사용자>` 자리표시로 바꾸고 `run.sh` 는 ssh 별칭 `pi-rt`(또는 `PI=` 환경 변수)를 쓰게 했다. 규칙은 처음부터 "IP·계정·토큰은 공개하지 않는다"였는데 작업 로그를 적으면서 새어 나갔다 — 커밋 전에 `git grep` 한 줄(`192\.168\.|사용자명|토큰 앞글자`)을 습관으로. 이미 push 된 이력에는 남아 있다(사설 IP·계정 이름이라 위험은 낮다고 보고 이력은 다시 쓰지 않는다). (2) `HANDOVER.md` 에 다른 지원처·추천 제도 같은 개인 메모가 섞여 있었다 → 뺐다. (3) 결정·로그에 "사용자 요구"라고 적힌 곳 → 저장소 밖 사람이 읽는 문서이므로 "요구 사항"으로. 작업 방식 고지(README '작성 방식')는 그대로 둔다.
- ALLEX(위로보틱스 공개 모델, 2026-06-29, BSD-3) 를 같은 노드로 돌릴 준비: `scripts/get_allex.sh`(고정 커밋) · `robots/allex.yaml`(관절 48개, MJCF 액추에이터 순서 그대로 — 수동 관절 12개는 제외) · `test_mujoco_backend` 환경변수화(`RT_MUJOCO_DOF/JOINTS/OUT`) · CI `mujoco` 잡 ALLEX 단계 · `allex_mujoco.params.yaml` 생성 · E21 페이지(결과는 비워 둠). 확인한 것: 액추에이터 48개 전부 `<position kp kv>`, timestep 2 ms(백엔드 올림 규칙으로 1 ms), 관절 이름 48개가 MJCF 와 일치(스크립트로 대조). 바뀐 제어 코드 없음. 결정 DECISIONS 11/06.
- 정정: DECISIONS 11/03 "SO-101(6관절, 실물 있음)" 은 잘못 — 실물 팔은 없다. 제출 서류·설계서도 "실물 없음"으로 맞췄다. 복귀 순서는 ALLEX(공개 모델) → 중력 보상 → 실물(확보 시).
- 설계서를 쓰며 다시 확인한 것: 읽기 가이드의 "한 함수 40줄" 규칙을 넘는 함수가 아직 여럿 있다(`rt_loop.cpp` run, `rt_control_node.cpp` publish_status, `make_dashboard.py` build, `diag.py` 등). 제출 문서에는 "규칙"이 아니라 "지향"으로 적었고, 쪼개는 일은 분석 기간 과제로 남긴다.
- **E21 첫 실행(WSL, 1 kHz, 2,000주기)**: `nq=60 nu=48`, 관절 48개가 이름으로 액추에이터에 연결(관절 0 R_Shoulder_Pitch = joint 33 = actuator 0), 관절 0 은 0.000 → 0.298 rad. 한 주기 비용 **p50 336.2 / p99 622.0 / max 1,784.5 us** — 같은 PC 의 6 자유도(4.9 / 6.3 / 20.8)의 약 70~100배. p99 는 1 ms 예산의 62 %(합격선 900 안), **max 는 1 ms 초과**. → **ALLEX 프로필 500 Hz 기본**(모델 걸음 2 ms; DECISIONS 11/06 두 번째 항목). 원본 `docs/measurements/mujoco_backend_allex_wsl_1khz.json`(출력에서 전사).
- CI run 42172730308(patch-23, a35d202): 3잡 초록. `mujoco` 잡 44 s(ALLEX 250 MB 내려받기 포함), ALLEX 1 kHz 단계도 통과(러너 p99 < 900 us; 값은 아티팩트 `mujoco-ci` 에서 E21 표로 옮길 것). `rt_core` 잡은 6m42s — 전엔 1m13s. 코드 변경 없는 push 라 러너의 apt 설치 속도 차이로 본다(추정, 다음 run 에서 다시 본다).
- 테스트 `test_mujoco_backend` 에 `RT_MUJOCO_PERIOD_US`(기본 1000): 주기를 바꿔 재면 합격선(p99 < 주기의 90 %)·주기 수(2초 분량)·JSON 의 `period_us` 가 따라 바뀐다. JSON 의 모델 경로는 `third_party/` 부터만(홈 경로의 계정 이름이 측정 파일에 남지 않게). CI 의 ALLEX 게이트는 2 ms(운영점). `get_allex.sh` 가 찍는 "joints : 72" 는 등식 제약의 `<joint …>` 태그가 섞인 수라 글을 고쳤다(실제 관절 60 = 백엔드 `nq`).
- `backends/mujoco/README.md` 에 §5 가 둘 있던 것(patch-22 에서 겹침) → ALLEX 절을 §6 으로. CI 잡 순서·단계 그림(`docs/ENVIRONMENT.md` 5-3, `ARCHITECTURE.md` §11, `ci.yml` 머리 주석)에 ALLEX 단계를 더했다.
- **E21 2차(WSL, 500 Hz, 1,000주기)**: p50 326.7 / **p99 999.8** / max 1,589.4 us(주기 2,000) — 통과(p99 < 1,800). p50 은 1 kHz 와 같고 **p99 는 더 크다**(622 → 1,000). "비용은 같고 예산만 2배" 어림(p99 31 %)이 틀렸다 → E21 4절에 후보 둘(걸음이 커지면 제약 풀이 반복 증가 / 1,000주기 p99 의 흔들림)과 반복 측정 계획, DECISIONS 에 검증 결과를 적었다. 결정(500 Hz)은 유지. 관절 0 움직임 0.2976 rad — 세 환경(WSL 1 kHz · 500 Hz · 러너)에서 소수 4자리까지 같다.
- 러너 1 kHz 값(run 42172730308 아티팩트): p50 381.5 / p99 457.8 / max 608.9 us — 전부 1 ms 안. 1차의 "max 1 ms 초과"는 WSL 의 꼬리였다. `docs/measurements/mujoco_backend_allex_ci_1khz_run42172730308.json` 으로 복사(경로만 third_party/ 부터).
- patch-24·25 push 뒤 CI run 42175845461: 3잡 초록(rt_core 28 s · fleet 2m1s · mujoco 48 s), **ALLEX 500 Hz 게이트 첫 통과**. 러너 500 Hz: p50 390.1 / p99 510.4 / max 684.6 us = 2 ms 의 26 %(아티팩트 → `mujoco_backend_allex_ci_500hz_run42175845461.json`, 경로는 이제 테스트가 third_party/ 부터로 적는다). 러너에선 1 kHz → 500 Hz 가 p99 +11 % 뿐 — WSL 의 +61 % 는 환경 꼬리가 주된 원인으로 본다(추정, E21 4절).
- **장표 139장(138 → 139)**: ALLEX 를 장표에도 넣었다. 새 장표 1장 — 136 "덧붙임 (11/06) — ALLEX 48 자유도를 프로필 하나로"(kpi: 48 / 0줄 · ×70~100 · 458 · 622 · 500 Hz) 를 7부 끝(끝 섹션 바로 앞)에 두었다 — 중간에 끼우면 뒤 장표·설명 문서 번호가 전부 밀리기 때문(설명 문서 안의 장표 번호 참조가 780곳). 제자리에서 고친 장표 10장: 004(목차 7부 답), 037(단계 6 들머리 결과), 043(프로필 — allex.yaml 줄), 096(E15 → E16 → E21 사슬, 상자 8개), 102(공고 표 ④), 104(숫자 한눈에 ② 4번째 KPI "0.9% · 46%" + 글머리표), 115(테스트 목록 C++ MuJoCo 행 "× 2 모델"), 121(CI 잡 3 — ALLEX 500 Hz 두 상자, 45초), 130(2주 일정 D8 11/06), 135(용어 ALLEX), 138(한 장 요약 백엔드 상자). 끝 3장은 136~138 → 137~139 로 밀렸고 설명 문서도 같이 옮겼다(001·003·004 의 장표 수·범위 수정). 설명 문서는 바뀐 16개만 docx 재생성(pandoc 은 생성 시각을 넣어 전부 다시 만들면 138개가 다 바뀐다). `check_notes.py` 139/139 통과(004·009 의 `{{` 경고는 자리표시 문법을 설명한 글 — 전부터 있던 것). pptx 의 ZIP 폴더 항목 19개(일부 클라우드 편집기가 못 여는 원인)를 빌드 끝에 지우도록 `build.sh` 에 한 줄.

## 2026-11-10 (화) — 릴리스 → 배포 파이프라인(B): 흉내 OTA 를 진짜 설치로, 태그 하나로 게시까지, 실물은 자율 업데이트
- 아침 검토: 공고(주요업무 5줄·자격요건·우대)와 포트폴리오 대응을 다시 봄 — CI/CD 는 공고에서 한 줄이지만 지금 OTA 가 "버전 문자열 흉내"라는 약점이 코드에서 보인다 → B 로 결정(제출 11/14 전 1~2일). AWS·오라클 클라우드는 검토만 하고 보류(면접 뒤 EC2 하루; 신규 계정 6개월 무료 확인). 전장 설계 경험은 공고 자격요건에 있으나 포트폴리오로 못 덮는다 — 꾸미지 않고 면접에서 그대로 말한다.
- 노트북은 항상 켜 둘 수 없다 → 지휘소를 노트북에 두지 않는다. 실물 Pi 는 GitHub Release 를 스스로 읽어 설치(자율 모드), 함대 카나리는 CI 의 가상 50대가 맡는다(DECISIONS 11/10 세 항목).
- 코드: `fleet/agent/ota_apply.py`(내려받기·sha256·A/B 슬롯·자가 점검·원자적 전환·훅·롤백), `device_agent.py` 진짜 설치 경로 + `enable_auto_update`(시간대, 아키텍처 선택 `pick_artifact`) + 텔레메트리 `kind/ota_stage/ota_error`, `pi_agent.py`(ROS 없이 보드 숫자), `ros_status_bridge.py` 같은 옵션, `virtual_fleet.py --slot-root`, `rollout.py --manifest`(실물 마지막, 설치 실패 즉시 감지 `wait_apply`), `scripts/package_release.sh`(x86_64/aarch64, `--bad`), `merge_manifests.py`, `make_release_report.py`, `fleet/tests/release_canary.sh`, `.github/workflows/release.yml`(package ×2 → canary → publish), `integration.sh` 4b/4c, `assert_results.py` 산출물 규칙, `make_table3.py` 방식 열.
- 테스트: `test_ota_artifact.py` 9가지 통과(가짜 브로커 + 진짜 설치), 기존 3개 통과. 샌드박스 끝-대-끝(진짜 x86_64 패키지, 가짜 브로커): 50대 단계 배포 5 % 0.6 s → 50 % 1.0 s → 100 % 1.2 s, 전체 3.95 s; 깨진 패키지 3대에서 거부(자가 점검 exit 1) → 롤백 0.2 s. 러너 숫자는 첫 태그 뒤 E22 에.
- 고친 것 둘: tar 의 최상위 폴더 한 겹을 벗기지 않아 `selftest.sh` 를 못 찾고 "점검 없음"으로 통과하던 버그(테스트가 잡음); 진짜 설치 경로에서 롤백이 버전 문자열 기억(`prev_fw_version`)을 써서 슬롯과 어긋나던 것 → 슬롯의 `state.json` 이 기준.
- 문서: `docs/RELEASE.md`(그림·매니페스트·A/B·세 모드·Pi 서비스·면접 질문 9개), E22, DECISIONS 4건, README·EXPERIMENTS·HANDOVER·fleet/README·READING_GUIDE·GLOSSARY.- (같은 날 오후) 운영 층을 EC2 로 올릴 준비: `fleet/common/mqtt_conn.py`(TLS·인증을 환경변수로, 에이전트·수집기·배포기 공통), `fleet/mosquitto/mosquitto-prod.conf`(내부 1883 + 외부 8883 TLS·비밀번호), `fleet/docker-compose.prod.yml`, `deploy/ec2/setup.sh`·`make_certs.sh`·`README.md`(콘솔 순서·보안 그룹·비용), `deploy/pi/`(서비스·환경 파일 예시·설치). 인증서 생성은 샌드박스에서 확인(SAN·검증 OK), 서버 설치 자체는 계정이 생긴 뒤 첫 실행. 단위 테스트 4개 통과(보안 설정이 없으면 전과 같이 돈다).
- AWS 계정 생성(새 가입 방식 Builder ID): 무료 플랜 자동 등록, 루트 사용자 없음, **리전 시드니 고정**(서울 선택 불가). 무료로 시작하고 필요하면 유료 전환 뒤 서울로 이전하기로. `deploy/ec2/README.md` 를 시드니·MFA(settings.aws.com)·예산 30/50/100(크레딧 체크 해제)·탄력적 IP·"서버: 시드니" 표기 규칙으로 고침. DECISIONS 에 앞당긴 이유와 리전 이유.


## 2026-11-10 저녁 — EC2 에 운영 층을 실제로 올림, Pi 가 시드니 서버로 보고 시작 (첫 실제 실행에서 나온 것 여섯)
- 한 일(콘솔, 17:00~17:25): 인스턴스 `rt-fleet`(Ubuntu Server 24.04 LTS x86, t3.small, 20 GiB gp3, 시드니) → 보안 그룹 규칙 셋(22·3000 은 내 IP, 8883 은 전체) → 탄력적 IP 할당·연결. t3.small 은 무료 플랜에서도 고를 수 있었다. 시드니 단가 시간당 0.0264달러(시작 화면) = 월 19.3달러, 크레딧은 180달러(안내 활동 4/5 완료 뒤)라 6개월을 덮는다. 계정 번호·서버 주소·집 IP 는 문서에 적지 않는다(캡처의 주소창도 쓰지 않는다).
- 한 일(서버, 17:30~17:36): `curl … setup.sh | bash` 한 줄 — Docker 29.9 설치 → 저장소 clone → 인증서(SAN 에 공개 DNS·IP) → 비밀번호 → 컨테이너 4개 Up. 3~4분. 밖으로 열린 포트는 8883·3000 뿐(`docker compose ps` 로 확인: DB 는 `5432/tcp` 내부, 브로커 1883 내부).
- **나온 것 1 — 보존 정책 단계 실패**: `function add_retention_policy(…) does not exist`, `relation "collector_stats" does not exist`. DB 컨테이너는 처음 켜질 때 초기화용 임시 서버를 먼저 띄우는데 `pg_isready` 는 거기에도 "준비됨"이라 답한다 → init.sql 이 확장·표를 만들기 전에 명령을 보냈다. 1분 뒤 같은 명령을 손으로 다시 보내니 정책 3개가 들어갔다(작업 id 1000·1001·1002) — 원인 확정. 고침: "응답하는가"가 아니라 "확장 1 + 표 3 이 생겼는가"를 기다린다(`setup.sh` 8단계).
- 접속 시험(WSL → 서버, 17:53): 가상 장치 3대를 TLS + 비밀번호로 붙임 → 수집기 `msgs/s=3 online=3 insert=3.0 ms bad=0 backlog=0 db_err=0`, Grafana(로그인) Fleet Overview 에 3대. 5분 동안 초당 3건이 평평했다. 전달 지연 표시는 p50 184 / p95 200 ms — **시계 차이가 섞인 값이라 지연으로 인용하지 않는다**(README 4b).
- **나온 것 2 — 빈 비밀번호**: `read -s` 줄을 다른 줄과 한꺼번에 붙여 넣으면 입력을 건너뛰어 `FLEET_PASS` 가 0자가 된다. 클라이언트 화면은 정상 때와 똑같고(`virtual fleet: 3 devices … TLS user=fleet`) 서버만 거부한다. 고침: 안내를 "한 줄만 실행 → 붙여 넣기 → 글자 수 확인"으로, Pi 설치 스크립트는 빈 값·자리표시·공백이 있으면 서비스를 등록하기 전에 멈춘다(같은 날 `FLEET_BROKER=rea ec2-…` 처럼 앞 명령의 조각이 값에 섞인 일도 있었다).
- Pi 연결(18:09~18:37): `git pull` 이 Pi 에 남아 있던 측정 원본(추적되지 않는 파일 20개 — 같은 파일이 WSL 을 거쳐 저장소에 있다)에 막힘 → 백업 폴더로 옮기고 받음.
- **나온 것 3 — paho-mqtt**: Pi 에 paho 가 없었다. 설치 안내에 적은 `apt install python3-paho-mqtt` 는 1.6 이라 틀린 안내였다(에이전트는 2.0 이상). pip 도 없어 `apt install python3-pip` 을 걸었더니 **나온 것 4 — 자동 보안 업데이트가 dpkg 잠금을 30분 넘게 쥠**(오래 꺼 둔 Pi 가 70개쯤을 한꺼번에 올림). 끊지 않고 돌아감: PyPI 에서 순수 파이썬 휠을 받아 sha256 을 확인하고 사용자 site-packages 에 풀었다(2.1.0). 이 방법을 `deploy/pi/get_paho.py` 로 넣고 `install.sh` 가 필요할 때 부른다.
- **Pi 보고 시작 18:37:31**: 서비스 `active (running)`, 메모리 12.9 MB. 대시보드 장치 목록에 `pi-rt`(state ok, fw `0.0.0-none` — 아직 릴리스를 설치한 적 없음), 온도 53~57 °C(보드의 실제 값), 이벤트 `online pi-rt`, backlog 0·DB 오류 0. 전달 지연 표시 p95 151 ms(역시 시계 포함). 이 시각부터 노트북과 무관하게 기록이 쌓인다.
- **나온 것 5 — 온라인 장치 4**: 붙어 있는 것은 Pi 1대인데 숫자 패널이 4. 수집기가 본 적 있는 장치 전부의 `last_seen` 을 매초 지금으로 갱신하고 있었다. 고침 + 테스트(DECISIONS 11/10 마지막 항목). **나온 것 6 — 지연 패널이 빨강**: 색 기준을 안 줘서 Grafana 기본값(80)이 걸렸다. 같이 고침.
- 확인해 둘 것(Pi 커널): 자동 업데이트 목록에 일반 커널 `linux-image-raspi` 가 있다. 지금은 `6.8.0-2054-raspi-realtime` 으로 돌고 있고 RT 패키지는 목록에 없다. 재부팅 전에 다음 부팅 커널을 본다(deploy/ec2/README 4절) — 영상 촬영(11/12~13) 전에 반드시.
- 남긴 것(안 고친 것): 브로커의 `per_listener_settings deprecated` 경고 — 인증 설정을 확인 없이 바꾸지 않는다. 서버에 반영하려면 `cd ~/rt-robot-data-infra && git pull && sudo docker compose -f fleet/docker-compose.yml -f fleet/docker-compose.prod.yml up -d --build`(수집기 재빌드, Grafana 재시작).
- 배운 것: 스크립트 셋(`setup.sh`·`install.sh`·서비스 파일)은 샌드박스에서 문법과 인증서까지만 확인했고 실제 기계에서는 오늘이 처음이었다 — 여섯 가지가 나왔고 전부 "실제 기계에서만 보이는 것"(초기화 순서, 패키지 버전, OS 의 백그라운드 작업, 사람이 붙여 넣는 방식, 계속 켜 둔 서버)이었다. 한 번에 안 되는 것이 정상이고, 나온 것을 그날 스크립트에 되돌려 넣는 것이 일이다.

## 2026-11-10 밤 — CI 가 3시간 빨강이었다: 산출물 OTA 가 러너에서 첫 장치부터 실패 (상대 경로 슬롯)
- 증상: patch-31 push 뒤 `fleet_integration` X. 로그: 단계 4b 에서 `설치 실패 1대 ['ci-001'] — selftest 실패 (exit 127): bash: build/integration/devices/ci-001/slots/0.0.0-ci/selftest.sh: No such file or directory` → 롤백. 그 앞의 장애 주입 넷(broker·db·collector·bad_firmware)과 흉내 OTA 는 전부 통과(유실 0).
- 오늘 고친 것 탓이 아니었다: `gh run list` 를 보니 **3시간 전 push(patch-26~30 을 한꺼번에) 때부터 빨강**이었다. 그 사이 AWS 작업을 하느라 CI 를 보지 않았다 — 11/05 에 "push 뒤 `gh run list` 는 문서 커밋이라도 본다"고 적어 놓고 같은 일을 했다.
- 원인: 통합 테스트는 `--slot-root build/integration/devices`(상대 경로)를 준다. `ota_apply.selftest` 는 슬롯 안에서(`cwd=슬롯`) `bash <슬롯>/selftest.sh` 를 돌리는데, 슬롯 경로가 상대 경로면 "슬롯 안에서 다시 본 슬롯 경로"가 되어 파일이 없다. 단위 테스트(`test_ota_artifact`)는 `tempfile.mkdtemp`(절대 경로)만 써서 통과했고, 샌드박스의 끝-대-끝 확인도 절대 경로였다.
- 고침: `install`·`selftest`·`post_switch` 가 경로를 절대 경로로 굳힌다. 테스트 1건 추가(작업 디렉터리를 옮기고 상대 경로 슬롯에 설치) — 고치기 전 코드에서 CI 와 **같은 오류 문장**으로 실패, 고친 뒤 통과. 릴리스 카나리(`release_canary.sh`)도 같은 상대 경로를 쓰므로 첫 태그 전에 잡힌 셈이다.
- 확인 못 한 것: 4b 뒤의 4c(깨진 패키지 거부)와 판정 단계는 이 실패에 가려 러너에서 아직 돈 적이 없다. 이 환경에는 도커가 없어 통합 스크립트를 끝까지 돌려 보지 못했다 → 다음 CI 결과로 확인한다.
- 배운 것: (1) 테스트가 쓰는 경로의 모양(절대/상대)이 실제 호출과 같아야 한다. (2) 여러 패치를 묶어 push 했으면 그 push 의 CI 를 반드시 본다 — 묶음이 클수록 더.
- 덧붙임(같은 실수 두 번): 오늘 저녁 `setup.sh` 의 "pg_isready 가 초기화용 임시 서버에 속았다"는 **11/04 CI 에서 이미 겪고 `ENVIRONMENT.md` 실패 사례 표에 적어 둔 것**과 같은 원인이다. 그때는 통합 스크립트만 고쳤고 일주일 뒤 새 스크립트에 같은 대기 방식을 다시 썼다. 실패 사례 표는 적는 것으로 끝나지 않는다 — DB 를 기다리는 코드를 새로 쓸 때 그 표를 먼저 본다.

## 2026-11-11 아침 — Pi 는 밤새 유실 0, 다음 부팅 커널은 RT 로 확정, 첫 태그 전에 릴리스 경로를 다시 읽음
- **첫 밤의 기록(서버: 시드니)**: 11/10 18:37:32 ~ 11/11 08:43:01, 14.09 시간. Pi 가 보낸 번호 50,730개 중 서버가 받은 것 50,730개 — **유실 0**, 중복 0, 에이전트 재시작 0, 이웃한 기록의 가장 긴 간격 1.00초, offline 이벤트 0, 수집기 backlog 0·DB 오류 0. 그 사이 수집기 재빌드·재시작 1회(11/10 19:02)와 Pi 의 자동 보안 업데이트(패키지 70개쯤)가 있었다. 원본 `docs/measurements/soak_pi_sydney_20261111_0843.json`(질의 출력에서 전사). 대시보드로 본 것은 "지금 온라인 1, 오류 0"까지이고, 밤새 끊김이 없었다는 말은 이 숫자가 한다(DECISIONS 11/11).
- **Pi 커널 — 어제 적은 확인 방법이 부족했다**: 어제는 "`linux-version … | tail -1` 과 `ls -l /boot/vmlinuz` 가 둘 다 realtime 이면 안전"이라고 적었다. 오늘 아침 둘이 갈렸다 — 버전이 가장 높은 것은 `6.8.0-2054-raspi-realtime`, `/boot/vmlinuz` 링크는 `vmlinuz-6.8.0-1065-raspi`(11/10 18:21 에 바뀜, 자동 업데이트가 새 일반 커널을 깔면서). Pi 가 부팅 때 읽는 것은 `/boot/firmware/` 의 파일이므로 그것을 직접 비교했다: `vmlinuz`·`initrd.img` 둘 다 RT 커널 파일과 sha256 앞 16자리가 일치(`5bd512ac780f81c3`, `3c9baee8b40daaee`). 업데이트 로그도 같은 말을 한다 — `flash-kernel: installing version 6.8.0-2054-raspi-realtime`(3회), `Kernel 6.8.0-1064-raspi has been removed. A higher version (6.8.0-2054-raspi-realtime) is still installed, no reflashing required.` → **다음 부팅도 RT 로 확정.** `/boot/vmlinuz` 링크는 "마지막에 설치된 패키지"일 뿐 부팅과 무관했다. `deploy/ec2/README.md` 의 확인 방법을 해시 비교로 고쳤다. `Linger=yes`(재부팅 뒤 로그인 없이 서비스가 뜬다) 도 확인. 지금 커널 `6.8.0-2054-raspi-realtime`, 가동 14시간 27분, `System restart required`(자동 업데이트의 요구) — **재부팅은 아직 하지 않았다.**
- `pgrep unattended-upgr` 에 잡힌 것은 업데이트가 아니라 종료 때 신호를 기다리는 보조 프로세스(`unattended-upgrade-shutdown --wait-for-signal`, 항상 떠 있다) — 어제의 업데이트 프로세스는 끝나 있었다. "끝났는가"를 pgrep 한 줄로 묻지 않는다.
- 전달 지연 표시값이 어젯밤 152 ms → 오늘 아침 144 ms. 같은 장치·같은 서버·같은 경로인데 8 ms 가 움직였다 — 이 값에 시계 차이가 섞여 있다는 또 하나의 표시(경로가 바뀌었을 수도 있어 원인은 추정). 그래서 왕복 시간 도구를 만들었다.
- **첫 태그 전 사전 점검**(어제 첫 실행에서 일곱 번 걸렸으므로, 태그를 올리기 전에 러너에서 처음 돌 것들을 미리 읽고 돌렸다):
  - `release.yml` → `release_canary.sh` → `rollout.py --manifest` → `assert_results.py` → `make_release_report.py` → `gh release create` 의 파일 이름·글롭·종료 코드를 따라가며 읽음.
  - 샌드박스에서 릴리스 흐름을 흉내: 진짜 x86_64 패키지 + (이 PC 에서 못 도는) 가짜 aarch64 패키지 → **병합 매니페스트**(글롭 순서상 최상위 항목이 aarch64 가 된다) → 가상 50대(가짜 브로커, 상대 경로 슬롯) 단계 배포 → 50/50 성공(모두 자기 아키텍처 항목을 골랐다 — aarch64 를 골랐다면 자가 점검이 실패한다), 깨진 패키지 3/50 에서 거부·롤백 1.0초, 판정 통과, 보고서 생성. 적용 시간 1.6 / 2.0 / 1.8초(2코어, 참고값 — 표에 쓰지 않는다).
  - 못 본 것(러너에서 처음): arm 러너의 빌드·ctest, 아티팩트 올리기·받기, 진짜 브로커에서 가상 50대(통합 테스트는 10대), `gh release create`, 그리고 러너가 만든 aarch64 바이너리가 Pi 에서 도는가.
- 사전 점검에서 **고친 것 셋**: (1) `ota_rollback` 의 가지 순서 — 두 번째 릴리스 뒤의 깨진 패키지가 거부한 장치를 한 세대 뒤로 보내던 버그(DECISIONS 11/11). (2) 배포 로그의 "산출물" 줄이 병합 매니페스트의 최상위 항목(aarch64)만 찍어, x86_64 가상 장치에 aarch64 파일을 보내는 것처럼 읽혔다 → 아키텍처별로 한 줄씩, 결과 JSON 에도 `arch`. (3) `pi_agent` 가 SIGTERM(서비스 정지·재부팅)에 그 자리에서 죽어 offline 을 스스로 남기지 못했다 → Ctrl+C 와 같은 길로(`정상 종료` 줄이 서비스 로그에 남는다).
- 새 도구 둘: `deploy/ec2/soak_report.sh`(연속 기록을 세어 JSON 으로), `fleet/tools/mqtt_rtt.py`(MQTT 왕복 — 시계 하나). 테스트 26 → 29건.
- 남은 것(오늘): 첫 태그 `v0.9.0-rc1` → 러너 카나리 값(E22) → Pi 에서 rc1 을 **시험용 슬롯에** 한 번 설치(`pi_agent.py --once --slot-root ~/rt-slots-test` — 돌고 있는 서비스와 기록을 건드리지 않는다) → 왕복 시간 측정 → 정식 태그는 그 결과를 보고. Pi 재부팅 시점(자동 시작의 실제 확인)은 정해야 한다.
- 배운 것: 확인 방법도 틀릴 수 있다 — "이 두 줄이 같으면 안전"이라고 적은 기준이 다음 날 서로 다른 답을 냈다. 기준을 적을 때는 **그 시스템이 실제로 읽는 것**(여기서는 `/boot/firmware`)을 직접 보는 방법을 고른다.

## 2026-11-11 오전 — 첫 태그가 첫 실행에 게시까지, Pi 가 Release 를 받아 설치, 왕복 첫 측정은 예상 밖(707 ms)
- **첫 태그 `v0.9.0-rc1`**: patch-33 push → CI 초록(run 42927108710, 3분 14초) → `git tag v0.9.0-rc1 && git push origin v0.9.0-rc1` → `release` 워크플로 run 42927560505 **첫 실행에 통과, 1분 52초**. 패키지 x86_64 21 s · aarch64(arm 러너) 43 s → 카나리 48 s → 게시 11 s. 사전 릴리스로 게시, 자산 5개. 카나리(진짜 Mosquitto, 가상 50대): 50/50, 적용 1.2 → 2.0 → 2.2 s, 전체 14.41 s; 깨진 패키지 3/50 에서 거부(0.6 s) → 롤백 1.0 s. 원본은 Release 자산을 받아 그대로 `docs/measurements/ota_release_v0.9.0-rc1_{good,bad}.json`·`manifest_v0.9.0-rc1.json`(크기가 원본과 같다). 태그 push 가 `ci` 도 한 번 더 돌린다(트리거가 `push` 전체) — 둘 다 초록.
- 러너 값은 샌드박스 사전 점검(1.6 / 2.0 / 1.8 s, 14.54 s, 롤백 1.0 s)과 거의 같고 어제의 샌드박스 값(0.6 / 1.0 / 1.2 s, 롤백 0.2 s)보다 크다. 차이는 가상 장치의 보고 주기 — 1 Hz 로 보고하는 장치는 설치·복귀를 "다음 보고"에서야 알린다(E22 4절).
- 보고서의 어긋남 하나: Release 본문 머리의 "헬스 대기 5 s"는 매니페스트의 배포 정책이고, 카나리는 3 s 로 돌았다(전체 14.41 s 에는 3 s × 3 이 들어 있다). 본문에 카나리의 실제 대기를 같이 찍도록 `make_release_report.py` 를 고쳤다(다음 태그부터).
- **Pi 가 Release 를 받아 설치(09:21)**: `pi_agent.py --once --slot-root ~/rt-slots-test --auto-update …/v0.9.0-rc1/manifest.json` — 매니페스트에서 aarch64 항목을 골라 내려받고, sha256 `78bc27d3…` 일치, 자가 점검 **500주기 드롭 0**(깨어남 p50 121 / p99 158 / 최대 337 us, `--no-rt`), `current → slots/0.9.0-rc1`. 러너(ubuntu-24.04-arm)가 만든 바이너리가 Pi 4 의 RT 커널에서 돈다 — 사전 점검에서 "못 본 것" 넷이 전부 확인됐다. 시험용 슬롯이라 돌고 있는 서비스·연속 기록은 그대로. `docs/measurements/selftest_pi4_v0.9.0-rc1.json`. `--once` 가 단계별 시간을 찍지 않아 내려받기·자가 점검이 각각 몇 초였는지는 모른다 → 찍게 고쳤다(다시 한 번 설치해 기입).
- **연속 기록 스크립트 첫 실행**(서버에서 `soak_report.sh pi-rt`, 09:23): 14.77 시간, 53,167 / 53,167, **유실 0**, 중복 0, 재시작 0, 장치 쪽 최대 간격 1.0 s, 서버가 못 받은 최장 1.6 s, 전달 지연 p50 146.5(시간대별 138.6~154.1) ms, offline 0. 아침에 손으로 센 것과 같은 결론. TimescaleDB 에서 질의가 그대로 돌았다. `soak_pi-rt_20261111T0023Z.json`.
- **왕복 첫 측정(Pi → 시드니, 0.2초 간격 × 300, TLS + 비밀번호)**: 접속 1,484 ms, 왕복 최소 285 / 중앙 707 / p95 838 / 최대 854 ms, 유실 0/300. 도구는 실제 TLS 경로에서 첫 실행에 돌았다. **값이 예상 밖** — 편도가 146 ms 인데 왕복이 707 ms 일 수는 없다.
  - 읽은 것: 최소 285 = 146 의 두 배. 최대 854 = 285 × 3.0, 중앙 707 = 285 × 2.5, 평균 708 — 285 의 2배와 3배 사이에 고르게 퍼진 모양. 접속 1,484 ms ≈ 왕복 4~5번.
  - 가설: 망의 왕복은 285 ms. 보내는 간격 0.2초가 그보다 짧아 클라이언트(paho)와 브로커(Mosquitto 기본값) 양쪽의 Nagle 이 메시지를 붙잡았다. 사건 기반 모형으로 옮기니 285 / 710 / 845 / 860 — 실측과 한 자리까지 맞는다. 처음 만든 모형(브로커가 되돌림을 한 번에 쓴다)은 285~570 을 내서 안 맞았고, "브로커는 메시지마다 따로 쓴다"를 넣자 맞았다 — 한 묶음으로 온 둘째의 되돌림이 첫째의 ACK 를 한 왕복 기다린다.
  - **틀렸던 것**: 어제 "한국–시드니 편도는 70~80 ms 쯤, 대시보드 값의 나머지는 시계 오차일 것"이라고 어림했다. 지금 데이터는 편도 약 142 ms, 시계 차이 수 ms 를 가리킨다. `deploy/ec2/README.md` 4b 와 DECISIONS 를 고쳤다.
  - 확인 전이다: 모형이 실측 하나를 설명하는 것으로는 부족하다. 간격 1초·0.35초·0.2초(재측정)·0.2초+NODELAY 의 값을 **재기 전에 예측해 E23 2절에 적었다**(09:45). 다음이 그 측정.
- 고친 것·더한 것: `mqtt_rtt.py`(기본 간격 1초, `--nodelay`, 개별 값 `samples_ms`), `nagle_model.py`(모형, 테스트 1건), `pi_agent.py --once`(단계별 시간 출력), `make_release_report.py`. 테스트 29 → 30건.
- 남은 것: E23 검증 측정 넷, Pi 시험 설치 한 번 더(단계별 시간), 정식 태그 `v0.9.0` → 오늘 밤 03~05시 Pi 서비스의 자율 업데이트 → 내일 아침 확인, 장표·설계서 갱신.
- 배운 것: (1) 사전 점검이 값을 했다 — 어제는 첫 실행에서 일곱 번 걸렸고 오늘 워크플로는 한 번에 갔다. (2) 처음 잰 숫자가 다른 숫자와 다투면, 숫자를 고르기 전에 재는 방법을 의심한다. (3) 어림에는 "추정"이라고 적는 것으로 끝이 아니다 — 그 어림 위에 다른 설명을 쌓지 않는다.

## 2026-11-11 오전 (2) — 왕복 290 ms 확정: 예측 넷 중 셋 맞고 하나 틀림. Pi 의 설치 한 번은 1초
- patch-34 push → CI 초록(run 42933116953). Pi 에서 `git pull`(76062ab — 예측이 들어간 커밋, 09:37) 뒤 검증 측정 넷(09:41~09:44, 각 60초, 유실 0):
  - **A 1초 간격**: 287 / **290** / 291 / 383 ms(최소 / 중앙 / p95 / 최대), 60회 중 59회가 287.2~292.5. 예측 285 평평 → 맞음.
  - **D 0.35초**: 279 / **288** / 504 / 1,163. 중앙값은 예측대로. 170개 중 21개는 네 번의 묶음 — 한 번 늦어지면 뒤가 계단처럼 내려온다: 걸음 17개 중 11개가 66.9~68.0 ms(= 간격 350 − 왕복 282.5). 예측에 없던 모양.
  - **C 0.2초(재측정)**: 276 / **548** / 800 / 1,428. 예측 710 → **틀림**. 세 띠: 568~833·중앙 694(처음 58개에서 올라가는 4개와 교란 7개를 뺀 것) → 336~620·중앙 473(144개) → 382~738·중앙 597(마지막 90개). 첫 띠에서 둘째 띠로 넘어간 자리에 1,187 ms 짜리 교란이 있다. 둘째 띠의 평균 474 는 B(한쪽만 Nagle)의 평균 473 과 같다.
  - **B 0.2초 + 클라이언트 NODELAY**: 283 / **464** / 605 / 614(평균 473). 예측 285 / 460 / 610 / 610(평균 474) → 맞음.
  - 판정: 기준 넷 중 셋 충족, "C 의 중앙값이 두 배를 넘는다"만 미달(1.89배). 망의 왕복 **290 ms** 는 A·D 로 확정. 모형의 한계(한 띠만 안다)는 E23 4절에 그대로 적었다. 원본 넷은 개별 값까지 `docs/measurements/rtt_pi_sydney_20261111T004*Z_*.json` — Pi 의 출력을 파일에서 그대로 옮겼다(손으로 옮겨 적지 않았다).
  - 대시보드의 전달 지연 146.5 ms − 왕복의 절반 145.0 ms = **+1.5 ms**. Pi 의 전달 지연은 거의 그대로 편도였다. 어제의 "편도 70~80 ms, 나머지는 시계 오차" 어림은 두 배 틀렸다.
- **Pi 의 설치 시간**(시험용 슬롯을 지우고 다시, 3회): 전체 1.620 / 1.009 / 0.983 초. 내려받기 0.426 / 0.117 / 0.090, 검증 0.001, 풀기 0.029 / 0.026 / 0.027, **자가 점검 0.678 / 0.674 / 0.674**, 전환 0.000, 훅 0.009. 전체 − 단계 합(= 매니페스트 읽기) 0.477 / 0.182 / 0.182. `install_pi4_once_v0.9.0-rc1.json`. 첫 설치(09:21)의 `file` 출력: `ELF 64-bit LSB pie executable, ARM aarch64`, 서비스는 `active` 그대로.
- 측정 파일 이름 하나를 바꿨다: `ota_*.json` 은 표③ 생성기(`make_table3.py`)가 배포 결과로 읽는 이름이라, Pi 설치 시간 파일을 `ota_pi4_…` 로 두면 생성기가 죽는다 → `install_pi4_once_…`. (표③-3 에는 같은 버전 `0.9.0-rc1` 이 샌드박스와 러너 두 줄로 나온다 — 환경 열이 없어 구분이 안 된다. 생성기에 출처 열을 더하는 것이 남았다.)
- 배운 것: (1) 예측을 먼저 적어 두니 "맞은 것"과 "틀린 것"이 갈렸다. 나중에 맞췄다면 C 의 548 도 그럴듯하게 설명하고 넘어갔을 것이다. (2) 모형이 한 조건을 한 자리까지 맞혀도(첫 측정) 다음 측정에서 틀릴 수 있다 — 맞은 횟수가 아니라 "무엇을 직접 쟀나"가 결론을 받친다. 290 ms 는 모형이 아니라 1초 간격의 측정이 말한다.

## 2026-11-11 낮 — 정식 `v0.9.0` 게시, 장표 145장, 그리고 "통과한 점검"이 못 본 곳(pptx 안)과 어긋나 있던 수
- **정식 태그 `v0.9.0`**(커밋 76062ab): `release` run 42934131689 **1분 27초**, 통과, 정식 릴리스로 게시. 카나리(진짜 Mosquitto, 가상 50대): 50/50, 적용 1.2 → 2.2 → 2.2 s, 전체 14.62 s(헬스 대기 3 s × 3 포함); 깨진 패키지 3/50 에서 거부(1.0 s) → 롤백 1.0 s. 아침의 rc1(1.2 → 2.0 → 2.2 s, 14.41 s, 거부 0.6 s, 롤백 1.0 s)과 단계별로 0.2 s 안에서 같다. 자산 5개: aarch64 21,726 B · x86_64 21,446 B · `manifest.json` · 카나리 JSON 2. 원본은 Release 자산 그대로 `docs/measurements/ota_release_v0.9.0_{good,bad}.json` · `manifest_v0.9.0.json`(이름만 바꿈).
  - `releases/latest/download/manifest.json` 을 받아 v0.9.0 의 매니페스트와 같은 파일임을, 그 경로로 받은 aarch64 패키지의 크기·sha256 이 매니페스트와 같음을 확인했다 — Pi 의 서비스가 읽는 주소가 이 릴리스를 가리킨다.
  - patch-35(9b1d99a, 문서와 측정 파일만) push 뒤 CI run 42935300117 초록. 태그는 그 앞 커밋에 있다 — 패키지에 들어가는 것(jitter_bench · 프로필)은 같다.
- **자율 업데이트는 아직 확인 전**: Pi 의 시간대는 `Asia/Seoul`(확인) → 서비스의 설치 허용 시간 03~05시는 한국 시간이다. 10분마다 확인하므로 11/12 03시 조금 지나 `v0.9.0` 을 받을 것으로 **예상**한다. 확인할 것 셋(11/12 아침): Grafana 장치 목록의 fw, Pi 의 `~/rt-slots/state.json`, 서버의 연속 기록(`soak_report.sh`). 결과는 E22 5절에.
- **Pi 전원(계획)**: 낮에 전원을 끄고 22시에 켜기로 했다(이 항목을 쓰는 시점에는 계획이다). 따라오는 것 셋 — (1) 연속 기록이 두 구간으로 나뉜다. 끈 동안은 보고가 없고, `soak_report.sh` 에는 재시작 1회(의도한 것)로 보일 것이다. 숫자를 인용할 때 구간을 나눠 적는다. (2) 미뤄 둔 "재부팅 뒤 자동 시작"의 실제 확인이 된다 — 켠 뒤 `uname -r`(`6.8.0-2054-raspi-realtime` 이어야 한다. 아침에 부팅 파일의 해시로 확인한 것의 실제 결과), `/sys/kernel/realtime`(1), `isolated`(3), `systemctl --user is-active rt-pi-agent`(`active`). (3) 다시 뜬 서비스는 Pi 의 작업 폴더에 있는 코드(09:37 에 받은 76062ab)로 돈다 — 지금까지 돌던 프로세스는 11/10 저녁에 뜬 그때의 코드였다.
- **CI 잡 시간**(11/11 의 run 두 번, `gh run view` 로 본 값): `rt_core` 34초 · 37초, `fleet_integration` 2분 25초 · 2분 34초. 문서에 적혀 있던 "약 1분 10초 / 약 2분"(11/05 무렵)을 "약 35초 / 약 2분 30초"로 고쳤다. `mujoco` 는 다시 보지 않아 45초 그대로 두었다.
- **장표 139 → 145장**: 7부 끝에 덧붙임 여섯 장 — 137 릴리스 → 배포 한 장 그림 · 138 장치의 설치(`ota_apply.install` 코드) · 139 릴리스의 숫자 · 140 운영 층을 클라우드에 · 141 사고와 해결 (3) · 142 왕복 290 ms. 끝 세 장은 143~145 로. 제자리에서 고친 것: 표지 · 목차(145장, 테스트 31건), 공고 표와 "숫자 한눈에 ②", 5부(환경 지도가 11/05 의 그림이라는 표시, 다섯째 곳 비고), 6부(테스트 목록에 릴리스 카나리 행, CI 잡 시간, 통합 테스트 두 장), 7부(결정 수, 일정의 여덟째 걸음, 남은 일, AI 와 일한 방식), 용어(OTA).
  - **코드 장표 10장은 코드가 틀려 있었다.** 장표는 빌드할 때 저장소의 줄을 읽는데(`cu.code(파일, 시작, 끝)`), 11/10~11 의 수정으로 줄이 밀려 같은 번호가 다른 코드를 가리켰다. 범위를 다시 맞추고 읽는 포인트를 고쳤다. "손으로 베끼지 않으니 틀릴 수 없다"는 말은 반만 맞았다 — 글자는 틀릴 수 없지만 **어느 줄인가**는 틀릴 수 있다. 소스를 고친 뒤에는 코드 장표를 한 번 본다(`docs/deck/README.md` 4절).
  - 설명 문서: 새로 6개, 고친 것 65개(번호가 바뀐 끝 세 장 포함). 줄 번호 인용은 옛 줄 → 새 줄 대응표(difflib)로 옮긴 뒤 파일을 열어 하나씩 다시 확인했다 — 자동 변환이 시각(`12:00:12.5`)·옵션 값(`--count 50`)·장표 범위 같은 숫자를 줄 번호로 잘못 본 곳이 있었다. docx 는 바뀐 문서만 다시 만들었다.
- **통과한 점검이 못 본 곳**: 장표를 다시 만들다가, 이미 공개한 pptx 의 108번 장표에 계정 이름이 든 명령 예시(`scp '…@<Pi IP>:…'`)가 남아 있는 것을 찾았다. 11/06 에 정한 커밋 전 점검은 `git grep` 이고, 그동안 매번 통과였다 — pptx·docx 는 ZIP 이라 `git grep` 이 안을 보지 못한다.
  - 고친 것: 그 장표를 자리표시(`<사용자>@<Pi IP>`)로. 점검을 `scripts/check_public.py` 로 — 글 파일과 함께 pptx·docx 를 풀어서 보고, 본 파일 수와 못 본 것(그림)을 같이 알린다. 이 프로젝트에만 해당하는 낱말은 저장소 밖 파일에서 읽는다(DECISIONS 11/11). 고치기 전의 pptx 를 넣으면 108번에서 걸리고, 지금 저장소는 0줄(파일 566개, 그림 20개는 Mermaid 로 그린 것).
  - 같이 드러난 것: **장표 생성 코드 `docs/deck/build/` 가 저장소에 없었다.** 맨 위 `.gitignore` 의 `build/` 가 그 폴더까지 가렸다. 11/05 부터 README·LOG·HANDOVER 가 "생성 코드 `docs/deck/build/`"라고 적었지만 받아 간 사람에게는 없는 폴더였다. `!docs/deck/build/` 로 다시 넣었다. 넣기 전에 손본 것 — 빌드가 쓰던 테마 색 스크립트는 외부 도구에 딸린 파일의 사본이어서 넣지 않고 같은 일을 하는 `theme_colors.js` 를 새로 썼다(두 스크립트가 만든 `theme1.xml` 이 바이트 단위로 같다). `reference.docx` 는 넣지 않고 만드는 스크립트(`make_reference.py`)를 넣었다. `make_notes.sh` 는 만든 시각을 고정한다 — pandoc 이 시각을 넣어, 같은 md 도 만들 때마다 다른 docx 가 됐다. `check_notes.py` 에 적혀 있던 점검용 낱말은 뺐다. 장표 목록 `SLIDES.md` 는 손으로 고치지 않고 `make_slides_md.py` 가 만든다.
  - 이력: 예전 커밋의 pptx 와 11/04 의 병합 커밋 메시지 둘(bundle 의 경로가 적혔다)에는 이름이 남아 있다. 비밀값이 아니고 이력을 다시 쓰면 태그와 Release 가 어긋나므로 그대로 둔다(11/06 과 같은 판단).
- **어긋나 있던 수 셋**(전부 문서의 수이고 측정값은 아니다):
  - 테스트: 장표 "15건"(11/05) · RELEASE.md "20건" · README·ENVIRONMENT "Python 30"(11/10~11). 테스트 함수로 세면 Python 26(9 · 3 · 7 · 7) + C++ 5 = **31건**. 30 은 `test_ota_artifact` 만 확인 가지(11)로 센 값이었다. 이 로그의 "26 → 29건", "29 → 30건"도 같은 섞인 단위다(함수로는 22 → 25 → 26) — 지난 항목은 그대로 둔다.
  - 결정: 장표 "핵심 18건 / 전체 24건" → 세 장의 행은 8 + 9 + 8 = **25**, 파일은 42건(오늘 둘을 더해 **44건**).
  - 장표 116 의 제목 "컨테이너 없이 1초 만에": 네 파일을 재 보니 샌드박스(2코어)에서 1.0 + 4.0 + 3.2 + 0.0 = 약 8초 → "몇 초 만에".
  - 세는 단위를 정했다(DECISIONS 11/11). `check_notes.py` 가 옛 수를 찾으면 실패한다.
- 문서: `ENVIRONMENT.md` 가 다섯 곳으로(클라우드 서버, Pi 의 서비스, 릴리스 워크플로와 그 길 넷) · `READING_GUIDE.md` 28번(클라우드 운영 층·실물 장치) · `EXPERIMENTS.md` 사고 표에 11/10~11 의 아홉 줄 · `RELEASE.md` 의 손으로 쓰던 서비스 파일을 설치 스크립트 안내로 · `SETUP_RT_MEASURE.md` 에 "표① 을 다시 잴 때는 에이전트 서비스를 멈추고" · 틀린 주석 둘(`package_release.sh` 의 "드롭 0 이면 통과" → 실제 규칙은 주기 100회 이상·드롭 10 % 이하, `ci.yml` 의 "fleet 단위 테스트 3개"). 저장소 뿌리에 있던 `mujoco_backend_ci.json` 은 러너 값이 아니라 11/04 의 WSL 단독 값(4.9 / 6.3 / 20.8 us)이었다 — 테스트를 뿌리에서 돌린 출력이 측정 커밋에 섞여 들어간 것. `docs/measurements/mujoco_backend_wsl_20261104.json` 으로 옮기고 뿌리의 그 이름은 `.gitignore` 에 넣었다.
- 남은 것: (1) 11/12 아침 자율 업데이트 확인 → E22 · 장표 139·144 · 설계서에 반영. (2) 22시 Pi 를 켠 뒤 네 줄. (3) 설계서·이력서 PDF 에 릴리스 파이프라인·운영 층·테스트 수 반영. (4) `check_public.py` 를 CI 에(일반 모양만). (5) 표③ 생성기에 출처 열. (6) 2분 영상(11/12~13).
- 배운 것: (1) **통과한 점검은 "본 범위 안에서" 통과한 것이다.** 유실 0(11/04), 다음 부팅 커널(11/11 아침), 그리고 이번 — 세 번 모두 틀린 것은 값이 아니라 **무엇을 보았나**였다. 점검 도구는 무엇을 보지 않았는지를 같이 말해야 한다. (2) "문서가 가리키는 폴더가 저장소에 있는가"는 받아 간 쪽에서만 보인다 — 내 PC 에는 있었다. 새 clone 에서 문서의 경로를 따라가 보는 것이 그 점검이다. (3) 수를 적을 때는 세는 명령을 같이 적는다. 명령이 없는 수는 다음에 고칠 때 틀린다.
