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
