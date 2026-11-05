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
- 준비: 갖고 있던 Pi 4 Model B 4 GB 의 카드는 다른 곳에서 쓰던 Raspberry Pi OS 12(bookworm)라 지우지 않고 보관, 새 카드(Samsung PRO Plus 512 GB)에 Raspberry Pi Imager 로 **Ubuntu Server 24.04.5 LTS 64-bit** 를 구움(hostname `pi-rt`, 사용자 `mgoh`, Wi-Fi·SSH 비밀번호 인증을 Imager 설정에서 미리 넣음). 첫 부팅만 모니터로 확인(IP 192.168.45.250, 커널 `6.8.0-1064-raspi`, 45 °C), 이후 전부 PC PowerShell 에서 `ssh mgoh@<IP>`. 이더넷 없이 Wi-Fi 로 충분했다.
- 빌드: `apt install git build-essential cmake rt-tests stress-ng` → clone → rt_core 빌드(GCC 13.3, arm64) → **ctest 4/4 통과**. x86(WSL·CI)에서 쓴 코드가 arm64 에서 수정 없이 돌았다(고정 크기 배열·표준 C++17 만 쓴 덕).
- 결과(일반 커널 6.8.0-1064-raspi, governor performance, `docs/measurements/table1_pi4.md`):
  - jitter_bench 60초: 한가 p99.9 18.8 / **max 24.9** us · 부하(stress-ng cpu4+io2+vm1) p99.9 201.9 / **max 781.2** us, `work time` max 134.9 us(50 us 일하는 도중에 밀림), 드롭 0.
  - cyclictest(4 CPU, 가장 나쁜 CPU): 한가 300초 p99.9 57 / **max 376** us · 부하 120초 p99.9 118 / **max 695** us, 오버플로 0.
- 읽기: **한가해도 5분 창에서는 376 us 가 나온다**(60초 단일 스레드 jitter_bench 는 24.9). 드문 커널 내부 작업(타이머 이동·Wi-Fi 드라이버·백그라운드 서비스 중 무엇인지는 미확인)이 분 단위로 한 번씩 수백 us 를 가져간다 → 일반 커널에서는 "부하가 없으면 안전"이 성립하지 않는다. 부하 중 max 695~781 us 는 1 ms 예산의 70~80%. RT 커널의 과제는 이 max 를 200 us 아래로, 한가/부하 차이를 작게.
- 발견(열): 부하 75초에 **45 → 75 °C**(방열판 없음). Pi 4 는 80 °C 부터 펌웨어가 클럭을 내리므로 300초 부하는 수치를 오염시킨다. `/sys/devices/platform/soc/soc:firmware/get_throttled` 가 0 → 오늘 값은 전부 깨끗함. 결정: 부하 측정은 120초까지(RT 커널도 같은 120초로 비교), 측정 스크립트가 온도·스로틀을 `.meta` 에 자동 기록(`scripts/lib_thermal.sh`, `cyclictest_run.sh`, 새 `jitter_run.sh`), `make_table1.py` 가 비고에 "온도 a→b °C, 스로틀 0" 또는 "⚠ 스로틀" 을 붙인다.
- 실수: WSL 용 scp·git 명령을 **Pi 창**에 침 → Pi 가 자기 자신에게 복사하려다 root 소유 파일(sudo 로 만든 결과)에 "Permission denied", git 은 "Author identity unknown". 해결: Pi 에서 `git reset` + `chown -R mgoh`, 명령은 WSL 창에서 다시. 배운 것: 창이 둘 이상이면 안내에 **[Pi 창]/[WSL 창]** 을 붙인다(SETUP 문서 수정). 결과 원본은 WSL 로 `scp` 해 커밋(b4c6f3b) — Pi 는 측정만 하고 커밋하지 않는다.
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
