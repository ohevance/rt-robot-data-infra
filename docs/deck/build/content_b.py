# 장표 내용 B — 1부 로봇을 움직이는 길 (top → down). 단계마다 들머리 + 핵심 코드(파일:줄). 시험·검증 장표는 "verify": True 로 표시 → make_slides.py 가 3부로 옮긴다
from cu import code, ref

SEC3 = "1. 로봇을 움직이는 길 — 명령에서 움직임까지"

RTL = "rt_control/rt_core/src/rt_loop.cpp"
RTH = "rt_control/rt_core/include/rt_core/rt_loop.hpp"
RING = "rt_control/rt_core/include/rt_core/spsc_ring.hpp"
CS = "rt_control/rt_core/src/control_step.cpp"
CSH = "rt_control/rt_core/include/rt_core/control_step.hpp"
SM = "rt_control/rt_core/src/robot_state_machine.cpp"
BE = "rt_control/rt_core/include/rt_core/backend.hpp"
SIM = "rt_control/rt_core/src/sim_lag_backend.cpp"
MJ = "rt_control/rt_core/src/mujoco_backend.cpp"
NODE = "rt_control/ros2_adapter/src/rt_control_node.cpp"
JT = "rt_control/rt_core/include/rt_core/joint_types.hpp"
JB = "rt_control/rt_core/src/jitter_bench.cpp"


def stage_title(n, text):
    return f"단계 {n} — {text}"


def slides():
    s = []
    s.append({"kind": "section", "section": SEC3, "num": "01", "title": "로봇을 움직이는 길 — 명령에서 움직임까지 (위에서 아래로)",
              "subtitle": "명령이 생겨서 관절이 움직이고, 그 결과가 기록·관제까지 가는 10단계. 단계마다 같은 꼴 — 들어온 것 → 문제 → ◇기준 → 핵심 코드(파일:줄) → 결과 → 판단 → 다음. 시험·검증은 3부로 미루고 번호만 적는다",
              "flow": {"from": "출발: 로봇을 움직이고 싶다 — 관절 6개짜리 팔(SO-ARM100 모델)에 '이 각도로 가라'를 전하면 실제로 움직이게 하려면?",
                       "question": "명령 하나가 로봇의 움직임이 되기까지 무엇을 거치고, 각 단계의 코드는 어디에 있고, 어떤 기준을 넘어야 다음으로 가나?",
                       "answer": "10단계를 위에서 아래로. 먼저 왕초보 바탕 지식과 한 장 그림, 소스 코드 지도. 단계마다 들머리 장표(들어온 것 → 문제 → 기준 → 확인 방법 → 결과 → 판단) 뒤에 핵심 코드 장표. 기준을 넘었다는 증거(실험)는 '확인 → 장표 N' 으로 3부를 가리킨다"},
              "agenda": ["바탕 지식(관절·rad·Hz·us·실시간) → 한 장 그림 → 소스 코드 지도(단계 ↔ 파일:줄 ↔ 장표)",
                         "① 명령이 생긴다 → ② ROS 2/DDS 가 전달 → ③ 노드가 우편함에 넣는다 → ④ RT 스레드가 1 ms 마다 깬다 → ⑤ 제어 단계가 안전하게 만든다 → ⑥ 백엔드가 로봇에 쓴다 → ⑦ 로봇이 이렇게 움직인다 → ⑧ 상태를 읽어 올린다 → ⑨ 기록한다 → ⑩ 관제로 올린다",
                         "가로지르기: 명령이 끊기면(안전 경로) · 실물 로봇으로 가면 바뀌는 것 → 다음: 2부 데이터의 길 (시험·검증은 3부)"]})
    # ---- 왕초보 바탕 지식 ----
    s.append({"kind": "cards", "section": SEC3, "title": "바탕 지식 — 로봇이 '움직인다'를 숫자로 말하기 (이 여섯 가지만 알면 아래 10단계가 읽힌다)", "cols": 3,
              "cards": [
                  {"icon": "1", "head": "로봇 = 관절 6개", "lines": ["이 저장소의 로봇은 팔(SO-ARM100 모델, MuJoCo 물리 시뮬레이션). 관절 6개: shoulder_pan · shoulder_lift · elbow_flex · wrist_flex · wrist_roll · gripper (robots/so101.yaml)", "'움직인다' = 관절 6개의 각도가 바뀐다. 그래서 명령도 상태도 숫자 6개 묶음"]},
                  {"icon": "2", "head": "각도의 단위 rad", "lines": ["rad(라디안) = 각도의 SI 단위. 1 rad = 57.3°, 0.05 rad = 2.9°", "목표 [0.3, −0.2, 0.1, 0, 0, 0.5] = 어깨 회전 0.3 rad(17°), 어깨 들기 −0.2 rad(−11°) …"]},
                  {"icon": "3", "head": "목표 위치와 실제 위치", "lines": ["명령은 '목표 위치'(가고 싶은 각도). 로봇이 실제로 있는 각도는 '실제 위치'. 둘의 차이 = 추종 오차", "중력이 걸리는 관절은 목표보다 조금 처진다(어깨 1.1°) — 단계 7 에서 숫자로 본다"]},
                  {"icon": "4", "head": "주기와 Hz", "lines": ["Hz = 1초에 몇 번. 명령 50 Hz(20 ms 마다) · 제어 루프 1 kHz(1 ms 마다) · 상태 발행 100 Hz · 노드 자기 보고 1 Hz", "제어 루프가 가장 빠르다: 명령 하나가 오는 동안 20번 깨서 '지금 목표'를 로봇에 쓴다"]},
                  {"icon": "5", "head": "지연과 us", "lines": ["us = 마이크로초 = 100만분의 1초. 1 ms = 1,000 us", "깨어남 지연 = '1 ms 마다 깨라'고 했는데 실제로 늦게 깬 시간. 평균이 아니라 최악(max)이 문제 — 1 ms 예산 안에 '항상' 들어와야 한다"]},
                  {"icon": "6", "head": "실시간(real-time)", "lines": ["빠른 게 아니라 '정해진 시간 안에 항상'. 리눅스는 기본으로 이것을 보장하지 않아 PREEMPT_RT 커널 · SCHED_FIFO · 격리 같은 장치를 쓴다", "이 장표에서 '참고값'(WSL2 가상 커널)과 '실측'(Pi 4 RT 커널)을 구분하는 이유"]},
              ],
              "foot": "더 자세한 용어는 7부 부록 용어 2장과 docs/GLOSSARY.md. 여기서는 아래 10단계를 읽는 데 필요한 것만"})
    # ---- 한 장 그림 ----
    s.append({"kind": "path", "section": SEC3, "title": "한 장 그림 — 명령에서 움직임까지 10단계 (각 상자가 다음 장표들의 출발점)", "perRow": 5,
              "stages": [
                  {"head": "명령이 생긴다", "text": "상위(계획기·조작기·시험용 ros2 topic pub)가 목표 관절 위치 6개를 50 Hz 로 낸다", "ref": "sensor_msgs/JointState → /joint_command", "color": "accent5"},
                  {"head": "ROS 2 / DDS 전달", "text": "같은 PC 안 프로세스 간 통신. RMW(Fast DDS) 가 토픽을 실어 나른다. QoS 가 손실·지연을 정한다", "ref": "표② dds_bench/rtt_bench.py", "color": "accent5"},
                  {"head": "노드가 우편함에", "text": "on_command: 길이 검사 → JointCommand → 락 없는 링(64칸)에 push. ROS 2 스레드는 여기까지", "ref": ref(NODE, 184, 201) + " · spsc_ring.hpp", "color": "accent1"},
                  {"head": "RT 스레드 1 ms", "text": "RtLoop::run: 준비 5단계 뒤 절대 시각에 깨서 step() 호출. 늦게 깬 만큼이 '깨어남 지연'", "ref": ref(RTL, 100, 162) + " · 표①", "color": "accent1"},
                  {"head": "제어 단계", "text": "최신 명령만 → 워치독(50 ms) + 상태 머신 → 변화량 제한(0.05 rad/주기) → 백엔드에 쓰기", "ref": ref(CS, 28, 56), "color": "accent1"},
                  {"head": "백엔드가 로봇에", "text": "Backend::write_command — SimLag(1차 지연) | MuJoCo(ctrl → mj_step) | 실물(서보 시리얼, 자리)", "ref": ref(MJ, 226, 239), "color": "accent6"},
                  {"head": "로봇이 움직인다", "text": "물리가 목표를 따라간다. 어깨는 중력에 0.019 rad(1.1°) 처진다 — 데이터가 말해 준 사실", "ref": "E15 · E16 · joint_states", "color": "accent2"},
                  {"head": "상태를 읽어 올린다", "text": "read_state(qpos·qvel) → JointStateSample → 상태 벨트(2048) → publish_state 100 Hz, rt_status 1 Hz", "ref": ref(NODE, 210, 230), "color": "accent1"},
                  {"head": "기록한다", "text": "rosbag2 MCAP 30초 → CSV 3개 → summary.md(실제 Hz·틈·추종 오차)", "ref": "data_pipeline/record.sh · bag_to_csv.py · E20", "color": "accent3"},
                  {"head": "관제로 올린다", "text": "ros_status_bridge 가 rt_status 를 51번째 장치로 MQTT 에 → 수집기 → DB → Grafana (2부)", "ref": "fleet/agent/ros_status_bridge.py", "color": "accent3"},
              ],
              "bottom": "읽는 법: 왼쪽 위에서 시작해 뱀처럼 내려온다. ①~③ 은 ROS 2 스레드(일반 우선순위), ④~⑥·⑧ 앞부분은 RT 스레드(SCHED_FIFO 80, 1 kHz), ⑦ 은 물리, ⑨⑩ 은 다시 일반 스레드. 두 세계의 경계는 락 없는 링 버퍼뿐이다"})
    s.append({"kind": "image", "section": SEC3, "title": "같은 길을 구조도로 — 로봇 안(실시간) · 관제(데이터) · 측정", "image": "img/sw_overview.png",
              "caption": "1부는 왼쪽 '로봇 안' 상자를 위에서 아래로 내려간다. 오른쪽 '관제'는 2부, 아래 '측정·검증'은 3부(검증)와 6부(측정 스크립트·테스트·CI)"})

    # ---- 소스 코드 지도 ----
    s.append({"kind": "table", "section": SEC3, "title": "소스 코드 지도 — 단계마다 어느 파일의 어느 함수인가 (장표 번호 = 그 단계의 들머리)", "fontSize": 9,
              "colW": [1.4, 4.6, 3.3, 2.4, 0.6],
              "rows": [["단계", "핵심 파일 : 줄 (함수)", "하는 일", "확인(실험)은 3부", "장표"],
                       ["1 명령이 생긴다", "(발행자) ros2 topic pub · 메시지 sensor_msgs/JointState · 토픽 선언 rt_control/ros2_adapter/src/rt_control_node.cpp:108-111", "관절 6개 목표(rad)를 50 Hz 로 /joint_command 에", "—", "{{first:단계 1 들머리}}"],
                       ["2 DDS 전달", "(미들웨어 Fast DDS/Cyclone) · 측정기 dds_bench/rtt_bench.py · scripts/make_table2.py", "발행자 → 노드 프로세스로 실어 나름. QoS 가 손실·지연을 정함", "표② E04 → 장표 {{first:단계 2 검증 — 측정기}}~{{first:단계 2 검증 — E04}}", "{{first:단계 2 들머리}}"],
                       ["3 우편함", "rt_control_node.cpp:184-201 on_command() · rt_control/rt_core/include/rt_core/spsc_ring.hpp:38-64 push()/pop()", "ROS 2 스레드 → RT 스레드로, 락 없는 링(64칸)에 넣기", "단위 테스트 test_spsc_ring.cpp (6부)", "{{first:단계 3 들머리}}"],
                       ["4 RT 1 ms 루프", "rt_control/rt_core/src/rt_loop.cpp:29-97 준비 5단계 · :120-158 run() 본체", "절대 시각에 깨서 깨어남 지연을 재고 step() 을 부른다", "표① E01~E19 → 장표 {{first:단계 4 검증 — 측정기}}~{{first:단계 4 검증의 결론}}", "{{first:단계 4 들머리}}"],
                       ["5 제어 단계", "rt_control/rt_core/src/control_step.cpp:28-56 step() · :61-79 최신 명령 · :83-100 워치독 · :126-142 변화량 제한 · src/robot_state_machine.cpp:15-46 전이표", "최신 명령 → 워치독(50 ms) → 변화량 제한(0.05 rad) → 상태 머신", "단위 테스트 test_control_step.cpp · test_state_machine.cpp (6부)", "{{first:단계 5 들머리}}"],
                       ["6 백엔드", "rt_core/include/rt_core/backend.hpp:17-33 · src/sim_lag_backend.cpp:21-38 · src/mujoco_backend.cpp:110-125, 226-252 · robots/so101.yaml", "로봇 쪽 인터페이스 세 함수. SimLag(1차 지연) / MuJoCo(물리)", "물리 비용 E15 → 장표 {{first:단계 7 검증}}", "{{first:단계 6 들머리}}"],
                       ["7 로봇이 움직인다", "(MuJoCo 물리) · 읽기: ros2 topic echo /joint_states", "목표를 따라 관절이 움직인다. 어깨는 중력에 0.019 rad 처짐", "E16 → 장표 {{first:단계 7 검증}}", "{{first:단계 7 들머리}}"],
                       ["8 상태 발행", "rt_control_node.cpp:205-230 rt_thread_main() · publish_state() · :233-291 publish_status()", "벨트(링 2048)를 비워 /joint_states 100 Hz, rt_status 1 Hz", "기록 요약의 실제 Hz (단계 9)", "{{first:단계 8 들머리}}"],
                       ["9 기록", "data_pipeline/record.sh · data_pipeline/bag_to_csv.py:31 open_bag · :43 read_messages · :57/:82 write_*_csv · :110 rate_and_gaps · :127 tracking_error · :157 write_summary", "rosbag2 MCAP 30초 → CSV 3개 → summary.md", "E20 (단계 9 장표 자체)", "{{first:단계 9 들머리}}"],
                       ["10 관제로", "fleet/agent/ros_status_bridge.py (123줄, DeviceAgent 재사용)", "rt_status 를 51번째 장치로 MQTT 에 → 2부 데이터의 길", "표③ → 장표 {{first:2부 ⑦⑧ 검증}}~", "{{first:단계 10 들머리}}"]],
              "foot": "경로는 저장소 뿌리 기준(rt_control/rt_core/…). 줄 번호는 2026-11-11 main. 코드 장표마다 상자 위에 같은 '파일:줄' 이 적혀 있다. 전체 읽기 순서(29항목)는 docs/READING_GUIDE.md"})
    s.append({"kind": "image", "section": SEC3, "title": "노드 안의 '두 세계' — 일반 스레드(ROS 2 실행기)와 RT 스레드(1 kHz), 그 사이는 링 버퍼 세 개뿐", "image": "img/node_threads.png",
              "caption": "왼쪽 = ROS 2 실행기 스레드(일반 우선순위): on_command · publish_state 100 Hz · publish_status 1 Hz. 오른쪽 = RT 스레드(SCHED_FIFO 80, 1 kHz): RtLoop::run → ControlStep::step → Backend. 두 세계를 잇는 것은 g_cmd_ring(64) · g_state_ring(2048) · g_timing_ring(65536) — 전부 락 없는 SPSC 링. 단계 3·4·5·8 이 이 그림의 상자들이다. 출처: rt_control/ros2_adapter/src/rt_control_node.cpp 머리말"})
    # ---- 단계 1 ----
    s.append({"kind": "bullets", "section": SEC3, "title": stage_title(1, "명령이 생긴다 — 누가, 무엇을, 얼마나 자주"),
              "bullets": [
                  "무엇: 관절 6개의 목표 위치(rad) 배열 하나. ROS 2 표준 메시지 sensor_msgs/msg/JointState 의 position 필드를 쓴다 (name·velocity 는 비워도 된다)",
                  "누가: 실제 로봇이면 상위 계획기(궤적 생성기)나 조작기. 이 저장소에서는 시험용으로 명령줄에서 낸다 — 50 Hz 로 같은 값을 반복",
                  {"text": "ros2 topic pub -r 50 /joint_command sensor_msgs/msg/JointState \"{position: [0.3, -0.2, 0.1, 0.0, 0.0, 0.5]}\"", "sub": True},
                  "왜 50 Hz 인가: 제어 루프(1 kHz)보다 느려도 된다. 루프는 매 주기 '가장 최신 명령'을 보고, 명령이 없는 주기는 지난 목표를 유지한다 (단계 5)",
                  "왜 rad 인가: 각도의 SI 단위. 1 rad = 57.3°. 0.05 rad = 2.9° — 변화량 제한의 단위도 rad",
                  "명령이 '틀릴' 수 있는 두 가지: 길이가 관절 수와 다름(단계 3 에서 거름), 값이 갑자기 뜀(단계 5 변화량 제한이 막음)",
                  "명령이 '끊길' 수 있다: 50 ms 동안 안 오면 워치독 → 멈춤 (안전 경로 장표)",
              ],
              "callout": {"title": "이 단계의 소스", "text": "메시지 형식: sensor_msgs/JointState (ROS 2 표준)\n토픽 이름: /joint_command (rt_control_node.cpp:110)\n시험 발행 명령: docs/VIDEO_SCRIPT.md 장면 3 (ros2 topic pub -r 50 …) · 흐름 그림: backends/mujoco/README.md\n실물에서 바뀌는 것: 발행자만 바뀐다(계획기). 아래 단계는 그대로"}})
    # ---- 단계 2 ----
    s.append({"kind": "bullets", "section": SEC3, "title": stage_title(2, "ROS 2 / DDS 가 전달한다 — 미들웨어가 하는 일과 QoS"),
              "bullets": [
                  "ROS 2 토픽은 DDS(Data Distribution Service) 위에서 움직인다. 발행자와 구독자는 서로를 모르고, DDS 가 '발견'하고 실어 나른다 (RMW = ROS 가 DDS 를 부르는 층)",
                  "구현체가 둘: Fast DDS(Jazzy 기본) · Cyclone DDS. 환경변수 RMW_IMPLEMENTATION 으로 고른다. 노드의 rt_status 에 실제 쓰인 rmw 이름이 찍힌다",
                  "QoS 두 가지가 결과를 가른다: reliable(못 받으면 재전송 — 늦어도 도착) vs best_effort(빠르지만 잃을 수 있음), 깊이(depth, 큐 길이)",
                  "이 단계에서 잰 것이 표②(E04): 구현체 × QoS × 크기(64 B~1 MB) 16조합의 왕복 지연(RTT)과 손실 — 측정기와 실험 사슬은 3부 장표 {{first:단계 2 검증 — 측정기}}~{{first:단계 2 검증 — E04}}",
                  {"text": "작은 메시지(64 B~64 KB)는 전부 손실 0, RTT p50 0.9~1.2 ms(rclpy 오버헤드 포함) → 관절 명령(수십 B) 은 어느 조합이든 문제없다", "sub": True},
                  {"text": "1 MB 에서 갈린다: Fast DDS best_effort 99.8% 손실, reliable 22.8%(깊이 10 초과) · Cyclone 0% → 큰 데이터(영상·점군)는 구현체·QoS 를 골라야 한다", "sub": True},
                  "함정(11/04): ros2 데몬이 다른 RMW 로 떠 있으면 토픽이 안 보인다 → ros2 daemon stop. 타입을 직접 적으면 데몬을 안 거친다(ros2 topic echo /rt_status std_msgs/msg/String)",
              ],
              "callout": {"title": "이 단계의 소스", "text": "측정기: dds_bench/rtt_bench.py (ping/pong, 191줄), run_matrix.sh\n표: scripts/make_table2.py → docs/measurements/table2.md\n실험 페이지: docs/experiments/E04.md\n결정: DECISIONS 11/03 'DDS 지연은 왕복(RTT)으로'"}})
    s.append({"kind": "image", "verify": True, "section": SEC3, "title": "단계 2 검증 — 측정기 — ping/pong 으로 왕복 지연과 손실을 센다 (표②)", "image": "img/dds_pingpong.png",
              "bullets": ["왕복(RTT)을 재는 이유: 두 컴퓨터의 시계가 달라도 같은 시계로 뺄 수 있다. 한 방향 ≈ RTT/2", "번호를 넣어 보내고 안 돌아온 번호 = 손실", "500회 × 100 Hz, 크기 64 B / 1 KB / 64 KB / 1 MB", "rclpy 라 절대값에 수백 us 파이썬 오버헤드 — 상대 비교용"]})
    s.append({"kind": "chain", "verify": True, "section": SEC3, "title": "단계 2 검증 — E04: DDS 는 1 MB 메시지도 손실 0 인가? (기준 → 못 넘으면 다음 실험)", "perRow": 4,
              "items": [
                  {"text": "E04 16조합 측정\nFast DDS·Cyclone × reliable·best_effort × 4크기"},
                  {"kind": "q", "text": "64 B ~ 64 KB 손실 0?", "answer": "예: 전부 0, RTT p50 0.9~1.2 ms ✓"},
                  {"kind": "q", "text": "1 MB 에서도 손실 0?", "answer": "아니오: Fast best_effort 99.8%, reliable 22.8%"},
                  {"text": "구현체를 바꾸면?"},
                  {"kind": "q", "text": "Cyclone 은 1 MB 손실 0?", "answer": "예: best_effort·reliable 모두 0% (reliable p50 4.4 ms) ✓"},
                  {"kind": "end", "text": "표② 통과 — 큰 메시지는 reliable + 충분한 깊이, 구현체 차이는 표로 남김"},
              ],
              "bottom": "숫자 출처 docs/measurements/table2.md. 로봇 관절 명령은 수십 바이트라 어느 조합이든 손실 0 — 이 실험은 '영상·점군 같은 큰 데이터를 같은 길로 보낼 때 무엇을 골라야 하나'의 답이다"})
    # ---- 단계 3 ----
    s.append({"kind": "code", "section": SEC3, "title": stage_title(3, "노드가 받아 우편함에 넣는다 — on_command()"), "file": ref(NODE, 184, 201),
              "code": code(NODE, 184, 201, dedent=2),
              "points": ["ROS 2 콜백 스레드(일반 우선순위)에서 돈다 — 여기서 제어를 하지 않는다", "길이가 관절 수(6)와 다르면 버리고 센다(bad_commands). 100번에 한 번만 경고(로그 폭주 방지)", "고정 크기 JointCommand 로 복사 → g_cmd_ring.push. 꽉 차면 cmd_ring_full 로 센다(정상이면 0)", "stamp_ns 는 단조 시계(now_ns) — 벽시계가 바뀌어도 뒤로 가지 않는다", "다음: RT 스레드가 매 주기 이 우편함을 통째로 비운다(단계 5)"]})
    s.append({"kind": "code", "section": SEC3, "title": stage_title(3, "우편함의 정체 — 락 없는 SPSC 링 버퍼 push()/pop()"), "file": ref(RING, 38, 64),
              "code": code(RING, 38, 64, dedent=2),
              "points": ["SPSC = 넣는 스레드 하나, 꺼내는 스레드 하나. 그래서 락이 필요 없다", "push: 값을 먼저 쓰고(buffer_) → head 를 release 로 공개. pop: head 를 acquire 로 읽으면 그 값이 보장된다", "꽉 차면 false — RT 스레드는 기다리지 않고 버린다(drop-on-full). 비면 false — 소비자는 쉰다", "칸 수는 2의 거듭제곱: & (N-1) 이 % N 과 같고 빠르다. 한 칸은 항상 비워 '꽉 참/비어 있음'을 가른다", "같은 클래스가 세 곳에 쓰인다: 명령 우편함 64 · 상태 벨트 2048 · 타이밍 65536"]})
    s.append({"kind": "two_col", "section": SEC3, "title": stage_title(3, "왜 락(mutex)이 아니라 링 버퍼인가"),
              "left": {"head": "락(mutex)을 썼다면", "bullets": ["ROS 2 스레드가 락을 잡고 있는 순간 RT 스레드가 깨어나면 → RT 스레드가 기다린다(우선순위 역전)", "기다리는 시간은 운에 따라 수십~수백 us → 1 ms 주기의 꼬리(max)가 커진다", "PREEMPT_RT 의 우선순위 상속이 완화하지만, 애초에 안 기다리는 것이 낫다"]},
              "right": {"head": "SPSC 링 버퍼(현재)", "bullets": ["RT 스레드는 push/pop 만 한다 — 원자 변수 2개 읽고 쓰기, 수십 ns", "꽉 차면 버리고 센다 → 최악 시간이 상수(bounded)", "대가: 메시지를 잃을 수 있다. 그래서 drops 카운터를 rt_status 에 내보내 '잃었는지'를 항상 본다(11/05 실측 전부 0)", "memory_order 셋(relaxed·acquire·release)의 뜻은 spsc_ring.hpp 머리말 주석"]},
              "foot": "결정 기록: DECISIONS 11/03 '로깅 큐는 꽉 차면 버린다(drop-on-full)'. 단위 테스트: test_spsc_ring.cpp (두 스레드, 역전 없음·드롭 허용)"})
    # ---- 단계 4 ----
    s.append({"kind": "code", "section": SEC3, "title": stage_title(4, "RT 스레드가 1 ms 마다 깬다 — 준비 5단계 (run() 이 처음에 부른다)"), "file": ref(RTL, 29, 97) + " (요약 발췌)",
              "code": code(RTL, 44, 50, dedent=0) + [""] + code(RTL, 70, 83, dedent=0) + [""] + code(RTL, 86, 97, dedent=0),
              "codeSize": 10,
              "points": ["0) record_kernel_info: uname -r 와 /sys/kernel/realtime(=1 이면 PREEMPT_RT) 을 기록 — 숫자 옆에 환경을 적기 위해", "1) mlockall: 메모리를 RAM 에 고정 → 루프 중 스왑·페이지 폴트 없음", "2) pin_cpu: --cpu N 이면 그 CPU 에 고정 (Pi 실험 E19-b)", "3) SCHED_FIFO 우선순위 80: '더 급한 스레드가 없으면 CPU 를 내놓지 않는다'. root 또는 RLIMIT_RTPRIO 필요", "4) 스택 256 KB 를 미리 밟아 첫 페이지 폴트를 루프 밖으로", "실패해도 멈추지 않고 RtStatus 에 남긴다 → 표의 비고에 'SCHED_FIFO=ok mlockall=ok'"]})
    s.append({"kind": "code", "section": SEC3, "title": stage_title(4, "루프 본체 (1/2) — 절대 시각에 깨서, 얼마나 늦게 깼는지 잰다"), "file": ref(RTL, 120, 143),
              "code": code(RTL, 120, 143, dedent=2), "codeSize": 10.5,
              "points": ["(a) clock_nanosleep(TIMER_ABSTIME): '지금부터 1 ms' 가 아니라 '그 시각에' — 늦게 깬 만큼이 다음 주기로 쌓이지 않는다(드리프트 0)", "EINTR(신호로 깬 경우)은 같은 시각으로 다시 잔다 — while 로 감싼 이유", "(b) wake_lat = 실제 깬 시각(woke_ns) − 목표 시각(next_wake_ns). 표①의 주인공 '깨어남 지연'", "period_err = 이번 깸 − 지난 깸 − 1 ms. 첫 주기는 비교 대상이 없어 0 으로 두고 통계에서 뺀다", "stop 플래그는 acquire 로 읽는다 — ROS 2 노드가 Ctrl+C 를 받으면 여기서 빠져나온다"]})
    s.append({"kind": "code", "section": SEC3, "title": stage_title(4, "루프 본체 (2/2) — 일하고, 벨트에 올리고, 다음 목표 시각을 정한다"), "file": ref(RTL, 144, 158),
              "code": code(RTL, 144, 158, dedent=2), "codeSize": 11,
              "points": ["(c) step(): 매 주기 할 일. 측정기는 50 us 바쁘게 돌기(BusyWork), 노드는 ControlStep(단계 5) — 같은 루프에 다른 일을 끼운다(RtStep)", "work_ns = step 이 걸린 시간. rt_status 의 work_us 가 이것(제어 + 물리)", "(d) ring.push 실패 = drops++ — RT 스레드는 절대 기다리지 않는다. drops 가 0 이 아니면 로깅 스레드가 못 따라간 것", "(e) 다음 목표 = 이번 목표 + 주기. 실제 깬 시각에 더하면 늦은 만큼 밀려 주기가 길어진다(드리프트) — 목표에 더해야 평균 주기가 정확히 1 ms", "++done: 완료한 주기 수. 측정 끝에 '60,000 주기 중 drops 0' 의 근거"],
              "foot": "이 루프의 깨어남 지연을 잰 것이 표①(Pi 4: 일반 781 → RT 301 → 격리 189 us). 측정기·백분위수·실험 사슬·표·결론은 3부 장표 {{first:단계 4 검증 — 측정기}}~{{first:단계 4 검증의 결론}}"})
    s.append({"kind": "image", "verify": True, "section": SEC3, "title": "단계 4 검증 — 측정기 jitter_bench — RT 스레드는 파일을 만지지 않는다 (스레드 2개)", "image": "img/jitter_bench_td.png",
              "bullets": ["main 스레드가 RT 스레드가 되어 RtLoop::run 을 돈다", "로깅 스레드(일반 우선순위)가 링에서 꺼내 모은다 — 비면 1 ms 쉼", "끝난 뒤 정렬해 min·avg·p50·p99·p99.9·max", "JSON 으로 저장 → make_table1.py → 표①", "종료 코드: drops>0 이면 1 (CI 가 '로깅이 못 따라감'을 실패로)", "옵션: --period-us --seconds --prio|--no-rt --cpu --work-us --label --json"]})
    s.append({"kind": "code", "verify": True, "section": SEC3, "title": "단계 4 검증 — 백분위수 — p99.9 는 '1,000번 중 999번은 이 값 이내'", "file": ref(JB, 128, 157),
              "code": code(JB, 128, 157), "codeSize": 10.5,
              "points": ["정렬한 뒤 위치 ceil(p/100 × n) 의 값 — 1 kHz 60초 = 60,000개면 p99.9 는 59,940번째", "왜 평균이 아닌가: 평균 18 us 여도 한 번 781 us 면 그 주기에 로봇이 명령을 놓친다. 제어 루프는 '최악'으로 설계한다", "max 는 '그 시간 동안 본 가장 나쁜 한 번'. 60초 측정과 300초 측정의 max 는 다를 수 있다(E18: 24.9 vs 376)", "us = 마이크로초 = 100만분의 1초. 1 ms = 1,000 us"]})
    # 표① 실험 사슬
    s.append({"kind": "chain", "verify": True, "section": SEC3, "title": "단계 4 검증 — 표① 실험 사슬 (1/3) — E01 → E02: 우선순위로는 꼬리를 못 자른다", "perRow": 4,
              "items": [
                  {"text": "E01 샌드박스 VM, 일반 커널\njitter_bench --no-rt 5초"},
                  {"kind": "q", "text": "max < 1,000 us (1 ms 안)?", "answer": "아니오: p99.9 2,568 / max 3,484 us"},
                  {"text": "가상 머신 탓인가, 커널 탓인가?\n→ 진짜 PC(WSL)에서"},
                  {"text": "E02 WSL 일반 vs SCHED_FIFO 80"},
                  {"kind": "q", "text": "우선순위로 max 가 줄었나?", "answer": "아니오: p50 92→37 좋아졌지만 max 921→937 그대로"},
                  {"text": "우선순위는 줄을 앞세울 뿐,\n커널이 잘라야 한다 → RT 커널 + 실물 보드"},
                  {"kind": "q", "text": "(곁가지) 노드 안에서도 드롭 0?", "answer": "예: E03 wake p99 278, 드롭 0, 워치독 동작 ✓ (WSL 참고값)"},
                  {"kind": "end", "text": "→ E18 Pi 4 로"},
              ],
              "bottom": "출처: docs/measurements/jitter_wsl_generic.json · jitter_wsl_fifo.json, docs/experiments/E01~E03.md. WSL2 는 가상 커널이라 전부 '참고값' — 하지만 '우선순위 ≠ 꼬리'라는 상대 비교는 여기서 이미 보였다"})
    s.append({"kind": "chain", "verify": True, "section": SEC3, "title": "단계 4 검증 — 표① 실험 사슬 (2/3) — E18 → E19-a/b/c: 커널 → 고정 → 격리", "perRow": 4,
              "items": [
                  {"text": "E18 Pi 4 일반 커널 기준값\n한가 300 s · 부하 120 s"},
                  {"kind": "q", "text": "일반 커널로 충분한가?\n부하 max < 200, 한가도 안정?", "answer": "아니오: 부하 781(jitter)·695(cyclictest), 한가도 5분에 376"},
                  {"text": "E19-a PREEMPT_RT\n6.8.0-2054-raspi-realtime"},
                  {"kind": "q", "text": "부하 max < 200?", "answer": "아니오: 301 (781 의 1/2.6, p99 는 146→185 비용)"},
                  {"text": "E19-b + CPU 3 고정\n옮겨 다님이 원인?"},
                  {"kind": "q", "text": "고정으로 줄었나?", "answer": "아니오: 311"},
                  {"text": "E19-c + isolcpus=3\n그 CPU 의 다른 일 때문?"},
                  {"kind": "end", "text": "예: max 189, work max 135→53\n표① 통과 — 1 ms 의 19%"},
              ],
              "bottom": "cyclictest 도 같은 방향: 한가 376→37(10배), 부하 695→132(5배). 전부 스로틀 0. 출처: docs/measurements/table1_pi4.md, docs/experiments/E18.md·E19a~c.md"})
    s.append({"kind": "chain", "verify": True, "section": SEC3, "title": "단계 4 검증 — 표① 실험 사슬 (3/3) — E19-d: 내 측정기가 맞나? (도구 불일치 2.3배의 정체)", "perRow": 4,
              "items": [
                  {"text": "E19-a 에서 발견\ncyclictest 132 vs jitter_bench 301"},
                  {"kind": "q", "text": "두 도구가 같은 급(±30%)?", "answer": "아니오 → 가설: 50 us 일하는 동안의 노출"},
                  {"text": "A-1 jitter_bench --work-us 0\n(깨기만, CPU 2)"},
                  {"kind": "q", "text": "work 0 이면 ~130 으로?", "answer": "아니오: 270 (p99 만 169→116) → 가설 기각"},
                  {"text": "A-2 cyclictest 를 같은 설정으로\n-t 1 -a 2 -p 80, 256M"},
                  {"kind": "q", "text": "두 도구가 같은 값?", "answer": "예: 274 vs 270 ✓ 측정기는 맞다"},
                  {"text": "B prio 90 → 290 (무관)\nC -S 스레드 배치 → 210"},
                  {"kind": "end", "text": "차이 = 스레드 배치(~60) + 부하 정의 512M vs 256M(~80, 추정)\n→ lib_stress.sh 한 곳으로"},
              ],
              "bottom": "배운 것: 도구를 비교하려면 부하까지 같은 함수에서 나와야 한다(내 두 스크립트의 부하가 달랐던 실수). 출처: docs/experiments/E19d.md, DECISIONS 11/05"})
    s.append({"kind": "table", "verify": True, "section": SEC3, "title": "단계 4 검증 — 표① Pi 4 실측 14줄 중 핵심 8줄 (us, 전부 스로틀 0)", "fontSize": 11,
              "colW": [3.2, 1.6, 0.9, 1.0, 1.1, 1.1, 1.2, 2.2],
              "rows": [["조건", "도구", "RT", "부하", "p99", "p99.9", "max", "비고"],
                       ["pi4_generic_idle 300 s", "cyclictest", "no", "none", "31", "57", "376", "4 CPU 최악"],
                       ["pi4_generic_stress 120 s", "cyclictest", "no", "stress", "84", "118", "695", "vm 512M"],
                       ["pi4_rt_idle 300 s", "cyclictest", "yes", "none", "19", "21", "37", "10배 개선"],
                       ["pi4_rt_stress 120 s", "cyclictest", "yes", "stress", "116", "123", "132", "5배 개선"],
                       ["pi4_generic_stress 60 s", "jitter_bench", "no", "stress", "145.7", "201.9", "781.2", "work max 134.9"],
                       ["pi4_rt_stress 60 s", "jitter_bench", "yes", "stress", "185.2", "241.5", "300.6", "work max 97.7"],
                       ["pi4_rt_stress_pin 60 s", "jitter_bench", "yes", "stress", "169.1", "216.1", "311.5", "cpu 3 고정, 효과 없음"],
                       ["pi4_rt_stress_isol 60 s", "jitter_bench", "yes", "stress", "108.3", "146.2", "189.3", "isolcpus=3, work max 53.1"]],
              "note": "한가 jitter 는 일반 24.9 / RT 27.8 — 경쟁자가 없으면 커널과 무관한 하드웨어 바닥(≈19 us). 전체 14줄과 온도·스로틀은 docs/measurements/table1_pi4.md"})
    s.append({"kind": "compare", "verify": True, "section": SEC3, "title": "단계 4 검증의 결론 — 일반 커널 vs 실시간 커널, 무엇이 다른가",
              "left": {"head": "일반 커널 (6.8.0-1064-raspi)", "big": "max 781 us", "bullets": ["커널이 내부 작업(인터럽트 처리·락 보유·드라이버) 중이면 RT 스레드는 그 작업이 끝날 때까지 기다린다", "한가해도 5분 창에서 376 us — 분 단위로 한 번씩 수백 us 를 뺏긴다", "1 ms 예산의 78% 를 한 번씩 먹는다. 2 kHz(500 us) 루프라면 깨진다"]},
              "right": {"head": "PREEMPT_RT + isolcpus=3", "big": "max 189 us", "bullets": ["인터럽트 핸들러가 스레드가 되고, 스핀락이 잠들 수 있는 락이 되어 커널이 하던 일을 중단시킬 수 있다", "격리로 CPU 3 의 다른 일(stress·IRQ 스레드)이 사라져 일하는 동안 안 밀린다(work max 135 → 53)", "남은 189 는 타이머 인터럽트 자체와 IPI(CPU 간 인터럽트) — 격리로도 못 막는 것. Pi 4 의 알려진 바닥"]},
              "foot": "면접 한 문장: '우선순위는 줄을 앞세울 뿐이고 꼬리를 자르는 건 커널이다 — WSL 에서 p50 은 좋아졌지만 max 는 그대로였던 이유.' 용어: GLOSSARY 'PREEMPT_RT', 'IPI', '스로틀'"})
    # ---- 단계 5 ----
    s.append({"kind": "code", "section": SEC3, "title": stage_title(5, "제어 단계 — 한 주기에 하는 다섯 가지 (ControlStep::step)"), "file": ref(CS, 28, 56),
              "code": code(CS, 28, 56), "codeSize": 10.5,
              "points": ["① 우편함 비우기 → desired_ (상위가 원하는 목표)", "② 워치독: 50 ms 동안 명령이 없으면 목표 = 현재 위치(멈춤) + 상태 머신 갱신", "③ 변화량 제한: applied_ 가 한 주기에 0.05 rad 넘게 못 뛴다", "④ 백엔드에 쓰고 읽는다 (write_command / read_state)", "⑤ 상태 벨트에 올린다 — 꽉 차면 버리고 센다", "이 함수 안에 할당·락·파일이 없다 — RT 규칙"]})
    s.append({"kind": "code", "section": SEC3, "title": stage_title(5, "① 최신 명령만 — 우편함을 전부 비우고 마지막 것만 쓴다 (take_latest_command)"), "file": ref(CS, 61, 79),
              "code": code(CS, 61, 79), "codeSize": 11,
              "points": ["while 로 우편함(링)을 전부 비우고 마지막 것만 cmd 에 남긴다 — 밀렸다 풀린 옛 목표를 순서대로 따라갈 이유가 없다", "got_any 가 false 면 이번 주기엔 새 명령이 없다 → desired_ 는 지난 값 유지(50 Hz 명령 사이의 19주기가 이 경우)", "dof 가 안 맞는 명령은 한 번 더 거른다(단계 3 에서 걸렀어도 — RT 쪽은 바깥을 믿지 않는다)", "last_cmd_ns_ = 마지막으로 명령을 받은 시각. 워치독이 이 값을 본다", "commands_applied 카운터 +1 → rt_status 에서 '초당 50' 으로 보인다"]})
    s.append({"kind": "code", "section": SEC3, "title": stage_title(5, "② 워치독 — 50 ms 동안 명령이 없으면 지금 자리에 멈춘다 (check_watchdog)"), "file": ref(CS, 83, 100),
              "code": code(CS, 83, 100), "codeSize": 11,
              "points": ["stale = 명령이 한 번도 없었거나(last_cmd_ns_ == 0) 50 ms(cfg_.watchdog_ns) 넘게 없음", "stale 이면: tripped = true, 목표(desired_) = 현재 위치(position_) → 로봇은 그 자리에 멈춘다. 급정지도, 0 위치 복귀도 아니다(DECISIONS D1)", "정상 → 멈춤으로 '바뀌는 순간'만 watchdog_trips 를 센다. 11/03 노드 시험에서 명령 발행을 끊자 trips 1", "명령이 다시 오면 tripped = false — 상태 머신 쪽은 RECOVERING 을 거쳐야 READY(다음 장)", "실물에서는 여기서 토크를 끄는 것까지 (Backend::safe_stop 자리, 2주 밖)"]})
    s.append({"kind": "code", "section": SEC3, "title": stage_title(5, "③ 변화량 제한 — 상위가 1 rad 를 요구해도 한 주기에 0.05 rad 만"), "file": ref(CS, 126, 142),
              "code": code(CS, 126, 142),
              "points": ["명령 버그·네트워크 재전송으로 튀는 값이 로봇을 치는 것을 막는 마지막 안전장치", "0.05 rad/주기 × 1,000 주기 = 50 rad/s 까지 허용 — 실물에서는 로봇 프로필(safety.max_step_rad)로 줄인다", "제한이 걸리면 step_limited 를 센다 → rt_status 에서 보인다(11/03 시험: 10회, 목표가 뛸 때)", "실제 로봇에 보내는 값은 desired_ 가 아니라 applied_"]})
    s.append({"kind": "image", "section": SEC3, "title": stage_title(5, "상태 머신 — 로봇이 지금 어떤 상태이고 어떤 일이 생기면 어디로 가나"), "image": "img/state_machine.png",
              "bullets": ["상태 5개: INIT → READY → RUNNING → FAULT → RECOVERING", "사건 5개: INIT_DONE · COMMAND · WATCHDOG_TRIP · RECOVERED · STOP", "표(전이표)에 없는 조합은 전부 '불법'으로 막고 센다(illegal_events, 0 이어야 정상)", "FAULT 에서 바로 RUNNING 으로는 못 간다 — 명령이 다시 오면 RECOVERING, 좋은 주기 100번(100 ms) 연속이어야 READY", "RT 스레드에서 매 주기 불린다 — 정수 비교뿐"]})
    s.append({"kind": "code", "section": SEC3, "title": stage_title(5, "상태 머신 코드 (1/2) — if 문이 아니라 전이표 한 장 (kTable)"), "file": ref(SM, 15, 32),
              "code": code(SM, 15, 32), "codeSize": 11,
              "points": ["한 줄 = 그림의 화살표 하나: {지금 상태, 사건, 다음 상태}. 'FAULT 에서 COMMAND 가 오면 RECOVERING' 이 코드를 다 읽지 않아도 보인다", "표에 없는 조합(예: FAULT + RECOVERED, INIT + COMMAND)은 전부 불법 — 그림에 화살표가 없는 것과 코드가 1:1", "STOP 은 어느 상태에서든 INIT 으로 — 안전한 '처음으로'", "kTableSize = 줄 수. 표에 줄을 더하면 전이가 늘고, 코드는 안 바뀐다", "결정 기록: DECISIONS 11/03 (D3) '상태 머신은 전이표 하나로'"]})
    s.append({"kind": "code", "section": SEC3, "title": stage_title(5, "상태 머신 코드 (2/2) — 표를 훑어 맞는 줄이 있으면 바꾸고, 없으면 센다 (handle)"), "file": ref(SM, 34, 46),
              "code": code(SM, 34, 46), "codeSize": 11.5,
              "points": ["handle(e): 표를 처음부터 훑어 (지금 상태, 사건)이 맞는 줄을 찾는다 — 줄 수가 16개라 매 주기 정수 비교 16번이 최악", "맞는 줄이 있으면 상태를 바꾸고 true. 자기 자신으로의 전이(READY→READY 등)는 transitions 를 세지 않는다", "없으면 illegal_ +1 하고 false — rt_status 의 illegal_events. 0 이어야 정상(11/05 실측 0)", "RT 스레드에서 매 주기 불린다: 할당·락·예외 없음", "단위 테스트: test_state_machine.cpp — 정상 전이와 불법 전이 거부를 둘 다 확인"]})
    s.append({"kind": "table", "section": SEC3, "title": stage_title(5, "rt_status 에 올라가는 카운터 — 제어 단계가 스스로를 설명하는 숫자들"), "fontSize": 11,
              "colW": [2.6, 5.0, 4.7],
              "rows": [["카운터 (ControlCounters)", "뜻", "정상값 · 실측"],
                       ["commands_applied", "RT 가 실제로 적용한 명령 수", "50 Hz 명령이면 초당 50 씩 증가"],
                       ["state_drops", "상태 벨트(2048칸)가 꽉 차서 버린 수", "0 (발행 스레드가 100 Hz 로 비운다)"],
                       ["watchdog_trips", "정상 → 멈춤 전환 횟수", "명령을 끊으면 1 (11/03 시험)"],
                       ["step_limited", "변화량 제한이 실제로 걸린 횟수", "목표가 뛸 때만 (11/03 시험: 10)"],
                       ["watchdog_tripped", "지금 멈춤 상태인가 (시작 시 true)", "명령이 오면 false"],
                       ["robot_state / state_transitions", "현재 상태 / 바뀐 횟수", "RUNNING, 명령 끊김·복구마다 증가"],
                       ["illegal_events", "전이표에 없는 사건", "0 이어야 정상"]],
              "note": "전부 std::atomic — 락 없이 RT 스레드가 쓰고 ROS 2 스레드가 1 Hz 로 읽는다. 출처: control_step.hpp:33-43, rt_control_node.cpp publish_status"})
    # ---- 단계 6 ----
    s.append({"kind": "code", "section": SEC3, "title": stage_title(6, "백엔드가 로봇에 쓴다 — 로봇 쪽의 '모양'(인터페이스) 세 함수"), "file": ref(BE, 17, 33),
              "code": code(BE, 17, 33),
              "points": ["ControlStep 은 이 세 함수만 안다. 구현체를 바꾸면 로봇이 바뀌고 제어 코드는 한 줄도 안 바뀐다(11/04 SimLag → MuJoCo 교체로 확인)", "init: 시작 때 한 번, 할당 허용(RT 밖)", "write_command / read_state: RT 스레드에서 매 주기 → 기다리는 일 금지", "구현체: SimLagBackend(1차 지연) · MujocoBackend(물리) · FeetechSerialBackend(실물 서보, 자리)", "결정: DECISIONS 11/03 'RT 핵심은 ROS 2 와 무관', 11/03 (D5) 'MuJoCo 는 Backend 의 한 구현'"]})
    s.append({"kind": "code", "section": SEC3, "title": stage_title(6, "백엔드 A — SimLag: 로봇 없이 노드 전체를 돌리는 1차 지연 모델"), "file": ref(SIM, 21, 38),
              "code": code(SIM, 21, 38),
              "points": ["position += (target − position) × alpha, alpha = 주기/시정수 = 1 ms / 50 ms = 0.02", "목표의 63% 에 도달하는 데 약 50 ms — 서보가 '서서히 따라가는' 성질만 흉내", "물리 없음: 관절 한계·충돌·중력 없음 → 중력 처짐은 여기서는 절대 안 보인다(E16 과 대비)", "용도: ROS 2 노드 전체(명령 → 루프 → 발행 → 워치독)를 로봇·시뮬레이터 없이 시험. CI 러너에서도 돈다"]})
    s.append({"kind": "code", "section": SEC3, "title": stage_title(6, "백엔드 B — MuJoCo: 목표를 ctrl 에 넣고 물리를 한 주기 진행한다"), "file": ref(MJ, 226, 252),
              "code": code(MJ, 226, 252),
              "points": ["write_command: 관절 i 의 액추에이터(position 타입)에 목표를 쓰고 mj_step 을 substeps 번", "read_state: qpos(위치)·qvel(속도)을 관절 매핑 주소로 읽는다", "mj_step 은 mjData 의 미리 잡은 메모리만 쓴다 → 할당 없음 → RT 스레드에서 불러도 된다", "비용: SO-ARM100 6축 한 주기 p50 6.4 / p99 8.5 / max 29.4 us (러너) = 1 ms 의 0.9% (E15)"]})
    s.append({"kind": "code", "section": SEC3, "title": stage_title(6, "백엔드 B — 시뮬레이션 걸음을 제어 주기에 맞추는 법 (tune_timestep)"), "file": ref(MJ, 110, 125),
              "code": code(MJ, 110, 125),
              "points": ["모델의 기본 걸음(timestep) 2 ms, 제어 주기 1 ms → 걸음 1 ms 로 줄여 주기마다 1번", "제어 주기 5 ms 면 → 걸음 1.67 ms × 3번", "올림(ceil)을 쓰는 이유: 걸음은 모델이 정한 값보다 '작게'만 바꾼다 — 키우면 물리가 불안정해진다", "노드 시작 로그: '제어 주기 1.000 ms = mj_step 1번 x 1.000 ms'"]})
    s.append({"kind": "two_col", "section": SEC3, "title": stage_title(6, "모델과 관절의 연결 — robots/so101.yaml 한 파일로 로봇을 바꾼다"),
              "left": {"head": "로봇 프로필 (robots/so101.yaml)", "bullets": ["dof: 6 · joints: [shoulder_pan, shoulder_lift, elbow_flex, wrist_flex, wrist_roll, gripper] (우리 쪽 이름)", "loop_hz: sim 1000 / real 200 (Feetech 서보 시리얼 1 Mbps 한계)", "backend: sim mujoco / real feetech_serial", "mujoco.model: third_party/mujoco_menagerie/trs_so_arm100/scene.xml", "mujoco.joints: [Rotation, Pitch, Elbow, Wrist_Pitch, Wrist_Roll, Jaw] (모델 안 이름, 같은 순서)", "safety: watchdog_ms 50, max_step_rad 0.05"]},
              "right": {"head": "노드로 가는 길", "bullets": ["scripts/profile_to_params.py --backend mujoco → rt_control/ros2_adapter/config/so101_mujoco.params.yaml (손으로 두 번 쓰지 않기)", "노드는 파라미터로 받는다: backend, mujoco_model(RT_REPO_ROOT 기준 경로), mujoco_joints", "MujocoBackend::init: load_model → tune_timestep → map_joints_by_name(이름이 틀리면 모델의 관절 이름 전체를 출력) → find_actuators → mj_forward → print_mapping", "함정(11/04): 빈 배열 mujoco_joints: [] 는 타입 미정으로 노드가 안 뜸 → 빈 배열이면 키를 뺀다", "두 번째 프로필 robots/allex.yaml(11/06) — 위로보틱스 공개 ALLEX 48 자유도: 관절 이름 48개 + loop_hz 500. 제어 코드·백엔드 무변경(E21, 7부 덧붙임)"]},
              "foot": "관절 이름이 두 벌인 이유: ROS 토픽 쪽 이름은 로봇과 무관하게 유지하고, 모델 쪽 이름은 모델 파일이 정한다. 둘을 잇는 표가 이 YAML 이다"})
    # ---- 단계 7 로봇이 움직인다 ----
    s.append({"kind": "kpi", "section": SEC3, "title": stage_title(7, "로봇이 이렇게 움직인다 — 목표 [0.3, −0.2, 0.1, 0, 0, 0.5] 를 주면"),
              "kpis": [{"value": "−0.181 rad", "label": "shoulder_lift(Pitch) 실제 위치\n목표 −0.200 → 0.019 rad(1.1°) 처짐"},
                       {"value": "0.109 rad", "label": "elbow_flex 실제 위치\n목표 0.100 → 0.009 rad(0.5°) 처짐"},
                       {"value": "0.300 / 0.500", "label": "shoulder_pan · gripper\n목표 그대로 (중력이 안 걸리는 축)"},
                       {"value": "100.0 Hz", "label": "/joint_states 실제 발행 주기\n30초 2,964행, 틈 0"}],
              "bullets": ["명령(단계 1)이 1 ms 마다(단계 4) 안전 검사(단계 5)를 거쳐 MuJoCo 액추에이터에 들어가고(단계 6), 물리가 관절을 움직였다. 그 결과를 /joint_states 로 읽은 값이 위 숫자다 (11/05 12:35 WSL, `ros2 topic echo /joint_states --once --field position`)",
                          "SimLag 였다면 전부 목표와 같았을 것이다 — 처짐은 물리(중력 + 유한한 kp 의 position 액추에이터)가 만든 '진짜 로봇스러운' 정상 상태 오차. 다음 단계는 중력 보상(토크 피드포워드) — 2주 범위 밖, 보류 항목",
                          "같은 숫자가 기록 파이프라인의 자동 요약(단계 9)에 추종 오차 표로 다시 나온다: shoulder_lift 0.0191, elbow_flex 0.0094"],
              "foot": "출처: docs/LOG.md 11/04 MuJoCo WSL, docs/measurements/record_summary_wsl_20261105.md, docs/experiments/E16.md·E20.md. rad → 도: × 57.3. 물리 비용(E15)과 이 처짐(E16)의 실험 사슬은 3부 장표 {{first:단계 7 검증}}"})
    s.append({"kind": "chain", "verify": True, "section": SEC3, "title": "단계 7 검증 — 물리 실험 사슬 E15 → E16 → E21: 6축 물리는 싸고, 새 사실을 보여 주고, 48축은 비싸다", "perRow": 4,
              "items": [
                  {"text": "E15 MuJoCo 한 주기 비용\ntest_mujoco_backend 2,000주기"},
                  {"kind": "q", "text": "1 ms 예산의 10% 아래?", "answer": "예: 러너 p50 6.4 / p99 8.5 / max 29.4 us = 0.9% ✓ (WSL 4.9/6.3/20.8)"},
                  {"text": "노드 안에서는? work_us(제어+물리)\n41 / 145 / 247 us (WSL 참고값)"},
                  {"text": "E16 물리가 보여 주는 새 사실은?\n정상 상태 위치 읽기"},
                  {"kind": "q", "text": "SimLag 와 결과가 같나?", "answer": "아니오: 어깨 Pitch −0.180 (목표 −0.200), 1.1° 처짐"},
                  {"text": "E21 ALLEX 48 자유도 (위로보틱스 공개 모델)\n프로필만 바꿔 같은 테스트 (11/06)"},
                  {"kind": "q", "text": "1 ms 안에 드나?\n6축의 몇 배?", "answer": "러너 p99 458 · WSL 622 us (46~62%) ≈ 6축의 70~100배 → 500 Hz 기본"},
                  {"kind": "end", "text": "물리 통과 + 다음 단계 발견\n중력 보상 · 48축 반복 측정"},
              ],
              "bottom": "출처: docs/measurements/mujoco_backend_ci.json, mujoco_backend_allex_*.json, docs/LOG.md 11/04·11/06, docs/experiments/E15.md·E16.md·E21.md. CI 의 mujoco 잡이 매 push 마다 두 모델(6축 1 kHz, ALLEX 500 Hz)의 움직임 + 비용 p99 < 주기의 90% 를 다시 확인한다"})
    # ---- 단계 8 ----
    s.append({"kind": "code", "section": SEC3, "title": stage_title(8, "상태를 읽어 올린다 — 벨트를 비우고 가장 최신 샘플만 100 Hz 로 발행"), "file": ref(NODE, 205, 230),
              "code": code(NODE, 205, 230, dedent=2),
              "points": ["rt_thread_main 은 3줄: RtLoop::run(ControlStep, 타이밍 링, drops, stop 플래그)", "publish_state(100 Hz 타이머): 상태 벨트(2048칸)를 전부 비우고 마지막 것만 /joint_states 로 — 1 kHz 샘플 10개 중 최신 1개", "RT 가 아직 안 돌았으면 발행하지 않는다", "msg.name 은 로봇 프로필의 우리 쪽 관절 이름 6개"]})
    s.append({"kind": "bullets", "section": SEC3, "title": stage_title(8, "rt_status — 1초마다 노드가 스스로를 설명하는 JSON 한 줄"),
              "bullets": [
                  "publish_status(1 Hz): 지난 1초의 타이밍 샘플(약 1,000개)을 타이밍 링에서 전부 꺼내 깨어남 지연·작업 시간의 p50/p99/max 를 구한다 (rt_control_node.cpp:233-291)",
                  {"text": "wake_us {p50, p99, max} — 단계 4 의 깨어남 지연. WSL 참고값: p99 288~606 us. Pi RT 면 수십 us", "sub": True},
                  {"text": "work_us {p50, p99, max} — ControlStep + 백엔드(물리) 가 걸린 시간. MuJoCo 노드 WSL: 41 / 145 / 247 us", "sub": True},
                  {"text": "timing_drops · state_drops · commands_received · commands_applied · cmd_ring_full · bad_commands", "sub": True},
                  {"text": "watchdog(ok|tripped) · watchdog_trips · step_limited · state(READY|RUNNING|FAULT|…) · state_transitions · illegal_events", "sub": True},
                  {"text": "rt {sched_fifo, mlockall, kernel_realtime, kernel} · backend · loop_hz · rmw — 숫자 옆의 '환경'", "sub": True},
                  "왜 JSON 문자열인가: 사람이 ros2 topic echo 로 바로 읽고, 다리(ros_status_bridge)가 그대로 관제에 올리고, bag_to_csv 가 CSV 로 편다 — 메시지 타입을 새로 정의하지 않아도 된다",
                  "버퍼 1536바이트 고정, snprintf 한 번 — 발행 스레드에서도 할당을 안 한다",
              ],
              "callout": {"title": "실제 한 줄 (11/05)", "text": "{\"iter\": …, \"loop_hz\": 1000, \"backend\": \"mujoco\", \"samples_1s\": 1000, \"wake_us\": {\"p50\": …, \"p99\": 288~606, \"max\": …}, \"work_us\": {…}, \"timing_drops\": 0, \"state\": \"RUNNING\", \"rt\": {\"sched_fifo\": true, \"mlockall\": true, \"kernel_realtime\": false, …}, \"rmw\": \"rmw_fastrtps_cpp\"}"}})
    # ---- 단계 9 ----
    s.append({"kind": "image", "section": SEC3, "title": stage_title(9, "기록한다 — rosbag2(MCAP) → CSV → 검증 요약 (E20, 11/05 첫 실행)"), "image": "img/record_flow_td.png",
              "bullets": ["record.sh 30: 토픽 3개를 30초 MCAP 으로 (1.07 MB)", "bag_to_csv.py: open_bag → read_messages → write_*_csv → rate_and_gaps → tracking_error → write_summary", "결과: 100.0 / 50.0 / 1.0 Hz, 틈(>3주기) 0, 드롭 0", "추종 오차: shoulder_lift 0.0191, elbow_flex 0.0094, wrist_flex 0.0025 rad — 단계 7 의 처짐이 자동으로", "1차 실패: timeout 과 터미널(SIGTTIN) → --foreground + --disable-keyboard-controls"]})
    s.append({"kind": "two_col", "section": SEC3, "title": stage_title(9, "기록(rosbag2)과 관제(MQTT)는 다른 길 — 왜 둘인가"),
              "left": {"head": "기록 — 로봇 안, 100 Hz 원본", "bullets": ["무엇: /joint_states 100 Hz · /joint_command 50 Hz · /rt_status 1 Hz 를 그대로", "어디에: 로봇 안 디스크(MCAP). 네트워크가 끊겨도 남는다", "왜: 사고 분석·제어 튜닝은 원본으로 한다 (블랙박스 영상)", "검증: 설계 Hz 대로 찍혔나, 틈은 없나, 추종 오차는 얼마나 — summary.md 가 자동으로"]},
              "right": {"head": "관제 — 서버로, 1 Hz 요약", "bullets": ["무엇: rt_status 의 요약(wake p99, 드롭, 상태)과 장치 상태", "어디에: MQTT → 수집기 → TimescaleDB → Grafana (2부)", "왜: 수십 대를 한 화면에서 — 원본 100 Hz × 50대를 서버로 보내면 양이 100배", "검증: 전달 지연 p95, 유실 0, 장애 복구 시간 (표③)"]},
              "foot": "둘을 잇는 것이 단계 10 의 다리(ros_status_bridge). 출처: docs/experiments/E20.md, docs/ARCHITECTURE.md"})
    # ---- 단계 10 ----
    s.append({"kind": "bullets", "section": SEC3, "title": stage_title(10, "관제로 올린다 — RT 노드가 51번째 장치가 되는 다리 (ros_status_bridge.py)"),
              "bullets": [
                  "ROS 2 노드(StatusBridge)가 /rt_status 를 구독해 JSON 을 파싱하고, 같은 DeviceAgent 클래스로 fleet/rt-node-1/telemetry 에 1 Hz 로 발행한다 (fleet/agent/ros_status_bridge.py, 123줄)",
                  "가상 장치 50대와 다른 것은 metrics_source(어디서 숫자를 가져오나)뿐: 가상 장치는 난수 걸음, 다리는 rt_status 의 wake p99·loop_hz 등",
                  "watchdog 이 tripped 이면 state 도 tripped 로 올라가 Grafana '멈춤·고장 장치' 패널에 잡힌다",
                  "이 다리를 지나면 로봇의 숫자는 2부 '데이터의 길'을 따라간다: 브로커 → 수집기(1초 묶음 COPY) → TimescaleDB → Grafana 'RT 노드: 깨어남 지연 p99' 패널",
                  "실물 로봇도 같다: 로봇 안 컴퓨터(Pi 등)에서 이 다리가 돌고, 관제 서버는 로봇이 가상인지 실물인지 모른다",
              ],
              "callout": {"title": "여기까지가 본편의 길", "text": "① 명령 → ② DDS → ③ 우편함 → ④ 1 ms 루프 → ⑤ 안전 검사 → ⑥ 백엔드 → ⑦ 움직임 → ⑧ 상태 → ⑨ 기록 → ⑩ 관제\n\n다음 두 장: 명령이 끊기면(안전 경로) · 실물로 가면 바뀌는 것. 그 다음 2부 데이터의 길, 시험·검증은 3부"}})
    # ---- 안전 경로 ----
    s.append({"kind": "chain", "section": SEC3, "title": "안전 경로 — 명령이 끊기면 무슨 일이 일어나나 (워치독 → FAULT → 복구)", "perRow": 4,
              "items": [
                  {"text": "RUNNING: 50 Hz 명령을 따라 움직이는 중"},
                  {"kind": "q", "text": "마지막 명령이 50 ms 보다 오래됐나?\n(check_watchdog)", "answer": "예 → stale"},
                  {"kind": "fail", "text": "tripped = true, 목표 = 현재 위치\nwatchdog_trips +1, 사건 WATCHDOG_TRIP"},
                  {"text": "상태 머신: RUNNING → FAULT\n(rt_status: watchdog tripped, state FAULT)"},
                  {"kind": "q", "text": "명령이 다시 오나?", "answer": "예 → 사건 COMMAND"},
                  {"text": "FAULT → RECOVERING\n좋은 주기를 센다 (good_cycles_)"},
                  {"kind": "q", "text": "100주기(100 ms) 연속 정상?", "answer": "예 → RECOVERED / 중간에 또 끊기면 FAULT"},
                  {"kind": "end", "text": "READY → 다음 명령에 RUNNING\n전이표 밖의 조합은 전부 거부(illegal_events)"},
              ],
              "bottom": "코드: control_step.cpp check_watchdog(83-100) · update_state_machine(103-122), robot_state_machine.cpp 전이표(15-31). 11/03 실측: 명령 발행을 끊자 trips 1, 상태 FAULT → 재개 뒤 RECOVERING → READY. 실물에서는 FAULT 진입 때 토크 오프(Backend::safe_stop 자리)"})
    # ---- 실물로 가면 ----
    s.append({"kind": "two_col", "section": SEC3, "title": "실물 로봇(SO-101, Feetech 서보 6개)으로 가면 — 바뀌는 것과 안 바뀌는 것",
              "left": {"head": "바뀌는 것 (새로 쓸 코드)", "bullets": ["FeetechSerialBackend: Backend 세 함수 구현 — init(시리얼 포트 열기·서보 ID 확인), write_command(목표 위치 6개를 동기 쓰기 패킷으로), read_state(현재 위치·속도 읽기)", "loop_hz: 1000 → 200 (1 Mbps 시리얼 버스에서 6개 서보 왕복 한계, 프로필 loop_hz.real) — RtLoop 은 period_ns 만 바뀐다", "안전: FAULT 진입 때 토크 오프(Backend::safe_stop) — 지금은 '현재 위치 유지'까지", "관절 한계(limits_rad)를 모델에서 읽어 변화량 제한 앞에 클램프", "중력 보상(토크 피드포워드) — E16 이 보여 준 1.1° 를 없애려면"]},
              "right": {"head": "그대로인 것", "bullets": ["단계 1~5·8~10 전부: 명령 토픽, 우편함, RT 루프(준비 5단계·절대 시각), 제어 단계(최신 명령·워치독·변화량 제한·상태 머신), 상태 발행, 기록, 관제 다리", "측정 방법: 같은 jitter_bench·cyclictest 를 로봇 안 컴퓨터(Pi)에서 — 표①이 이미 그 보드의 숫자", "데이터의 길(2부): 서버는 로봇이 가상인지 실물인지 모른다", "테스트: rt_core 단위 테스트 4개는 백엔드와 무관하게 그대로"]},
              "foot": "이것이 '제어 코드를 ROS 2 와 로봇에서 떼어 둔' 이유다 (DECISIONS 11/03). 실물 작업은 2주 범위 밖으로 뺐고(DECISIONS '6주 → 2주'), 자리(robots/so101.yaml serial 절, backend.hpp 주석)만 남겨 두었다"})
    return s
