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
