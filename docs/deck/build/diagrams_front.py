# 1부·2부의 "그림 한 장" 장표 — 단계마다 들머리 바로 뒤에 들어가는 도형 그림(diagram kind)과 막대 그래프(chart kind)
# 좌표는 인치, 본문 영역 기준(0,0 = 본문 왼쪽 위, 폭 12.33, 높이 5.25; legend 가 있으면 아래 0.75 는 비워 둔다)
# 왜 도형으로 그리나: 그림 파일보다 글자가 선명하고, 숫자·파일 위치를 고칠 때 코드 한 줄만 고치면 된다 (사용자 요구 11/05: 도형과 그림을 많이)

SEC1 = "1. 로봇을 움직이는 길 — 명령에서 움직임까지"
SEC2 = "2. 데이터의 길 — 장치에서 대시보드까지"


def stage1():
    return {"kind": "diagram", "section": SEC1, "title": "단계 1 그림 — 명령이 생긴다: 누가, 무엇을, 어디로 (관절 6개의 목표 각도 6개가 한 묶음)",
            "shapes": [
                {"id": "plan", "type": "round", "tone": "gray", "x": 0.2, "y": 0.3, "w": 2.9, "h": 1.1, "text": "상위 계획기 · 조작기\n(실물에서는 궤적 생성기가 여기)"},
                {"id": "pub", "type": "round", "tone": "blue", "x": 0.2, "y": 2.0, "w": 3.6, "h": 1.5, "fs": 9.5, "align": "left", "text": "시험용 발행(이 저장소에서 쓰는 것):\nros2 topic pub -r 50 /joint_command \\\n  sensor_msgs/msg/JointState \\\n  \"{position: [0.3, -0.2, 0.1, 0.0, 0.0, 0.5]}\""},
                {"id": "topic", "type": "hex", "tone": "amber", "x": 4.6, "y": 1.1, "w": 3.1, "h": 1.3, "text": "토픽 /joint_command\n(sensor_msgs/JointState)\n이름표 붙은 데이터 흐름", "bold": True},
                {"id": "msg", "type": "doc", "tone": "white", "x": 4.4, "y": 2.9, "w": 3.5, "h": 1.5, "fs": 10, "align": "left", "text": "메시지 한 개의 내용\nposition[6] (rad) = [0.3, −0.2, 0.1, 0.0, 0.0, 0.5]\nname · velocity 는 비워도 된다\n크기 수십 바이트"},
                {"id": "node", "type": "round", "tone": "mint", "x": 8.9, "y": 1.1, "w": 3.2, "h": 1.3, "text": "rt_control_node\n(ROS 2 노드 — 받아서 우편함에, 단계 3)", "bold": True},
                {"id": "joints", "type": "round", "tone": "white", "x": 8.6, "y": 2.9, "w": 3.5, "h": 1.5, "fs": 9.5, "align": "left", "text": "관절 순서(우리 쪽 이름, robots/so101.yaml)\n0 shoulder_pan  1 shoulder_lift  2 elbow_flex\n3 wrist_flex  4 wrist_roll  5 gripper\n→ 0.3 rad = 17°, −0.2 rad = −11°, 0.5 rad = 29°"},
            ],
            "arrows": [
                {"from": "plan", "to": "topic", "label": "50 Hz (20 ms 마다 한 번)"},
                {"from": "pub", "to": "topic", "label": "50 Hz (시험)"},
                {"from": "topic", "to": "node", "label": "DDS 가 실어 나른다 (단계 2)"},
                {"from": "msg", "to": "topic", "dashed": True, "noHead": True},
                {"from": "joints", "to": "node", "dashed": True, "noHead": True},
            ],
            "legend": "소스 위치: 토픽 이름·구독 선언 rt_control/ros2_adapter/src/rt_control_node.cpp:110-111 · 메시지 형식 sensor_msgs/msg/JointState(ROS 2 표준, 새로 정의하지 않음) · 시험 발행 명령 docs/VIDEO_SCRIPT.md 장면 3 · 관절 이름 robots/so101.yaml. 50 Hz 면 제어 루프(1 kHz)는 명령 하나당 20번 깬다 — 명령이 없는 주기는 지난 목표를 유지한다(단계 5)"}


def stage2():
    return {"kind": "diagram", "section": SEC1, "title": "단계 2 그림 — ROS 2 / DDS: 두 프로세스 사이를 미들웨어가 잇는다 (발견 → 직렬화 → 전송 → 콜백)",
            "shapes": [
                {"id": "p1", "type": "round", "tone": "gray", "x": 0.2, "y": 0.2, "w": 3.0, "h": 1.0, "text": "발행자 프로세스\n(ros2 topic pub · 계획기)", "bold": True},
                {"id": "r1", "type": "round", "tone": "blue", "x": 0.2, "y": 1.5, "w": 3.0, "h": 0.8, "text": "rclcpp/rclpy → RMW 층\n(rmw_fastrtps_cpp 또는 rmw_cyclonedds_cpp)", "fs": 10},
                {"id": "d1", "type": "hex", "tone": "purple", "x": 0.2, "y": 2.6, "w": 3.0, "h": 1.1, "text": "DDS 참여자\n발견(discovery) · 직렬화 · 전송", "fs": 10.5},
                {"id": "net", "type": "wave", "tone": "amber", "x": 3.9, "y": 2.5, "w": 2.9, "h": 1.3, "text": "같은 PC: 공유 메모리/루프백\n다른 PC: UDP 멀티캐스트", "fs": 10},
                {"id": "d2", "type": "hex", "tone": "purple", "x": 7.5, "y": 2.6, "w": 3.0, "h": 1.1, "text": "DDS 참여자\n수신 · 역직렬화 · QoS 처리", "fs": 10.5},
                {"id": "r2", "type": "round", "tone": "blue", "x": 7.5, "y": 1.5, "w": 3.0, "h": 0.8, "text": "RMW 층 → rclcpp 실행기\n(콜백 스레드, 일반 우선순위)", "fs": 10},
                {"id": "p2", "type": "round", "tone": "mint", "x": 7.5, "y": 0.2, "w": 3.0, "h": 1.0, "text": "구독자 프로세스 rt_control_node\non_command() 가 불린다 (단계 3)", "bold": True},
                {"id": "qos", "type": "round", "tone": "amber", "x": 10.9, "y": 0.2, "w": 1.25, "h": 3.5, "fs": 9, "align": "left", "valign": "top", "text": "QoS\n(품질 약속)\n\nreliable\n못 받으면 재전송\n\nbest_effort\n빠르지만 잃을 수 있음\n\ndepth 10\n큐 깊이"},
            ],
            "arrows": [
                {"from": "p1", "to": "r1"}, {"from": "r1", "to": "d1"}, {"from": "d1", "to": "net"},
                {"from": "net", "to": "d2", "label": "표②: 64 B~64 KB 손실 0, RTT p50 0.9~1.2 ms", "labelW": 3.2},
                {"from": "d2", "to": "r2"}, {"from": "r2", "to": "p2"},
                {"from": "qos", "to": "d2", "dashed": True, "noHead": True},
            ],
            "texts": [
                {"x": 3.6, "y": 0.2, "w": 3.6, "h": 2.0, "fs": 10, "text": ["발행자와 구독자는 서로를 모른다 — DDS 가 토픽 이름으로 '발견'한다", "노드는 메시지가 어떻게 왔는지 모른다 — on_command(msg) 만 불린다", "구현체는 환경 변수 RMW_IMPLEMENTATION 으로 바꾼다. rt_status 에 실제 쓰인 rmw 가 찍힌다", "큰 메시지(1 MB)에서는 구현체·QoS 에 따라 손실이 갈린다 — 영상·점군을 보낼 때의 문제"]},
            ],
            "legend": "소스 위치: 구독 선언(QoS depth 10) rt_control_node.cpp:110-111 · 측정기 dds_bench/rtt_bench.py(ping/pong) · 표 scripts/make_table2.py → docs/measurements/table2.md · 실험 사슬은 3부 장표 {{first:단계 2 검증 — 측정기}}~{{first:단계 2 검증 — E04}}"}


def stage3():
    slots = []
    x0 = 4.75
    for i in range(10):
        filled = i in (3, 4, 5, 6)
        slots.append({"type": "rect", "tone": "amber" if filled else "white", "x": x0 + i * 0.33, "y": 1.75, "w": 0.3, "h": 0.55, "text": "" if not filled else "✉", "fs": 9, "margin": 0})
    return {"kind": "diagram", "section": SEC1, "title": "단계 3 그림 — 우편함: 일반 스레드가 넣고 RT 스레드가 꺼내는 락 없는 링 버퍼 (한쪽만 넣고 한쪽만 꺼낸다 = SPSC)",
            "shapes": [
                {"type": "round", "tone": "gray", "x": 0.1, "y": 0.1, "w": 4.3, "h": 4.2, "text": "ROS 2 실행기 스레드 (일반 우선순위)", "valign": "top", "bold": True, "fs": 11},
                {"id": "oc", "type": "round", "tone": "blue", "x": 0.35, "y": 0.75, "w": 3.8, "h": 1.15, "fs": 10, "align": "left", "text": "on_command(msg)\n• position 길이 ≠ 6 → bad_commands++ 하고 버림\n• 고정 크기 JointCommand 에 복사, stamp_ns = now_ns()"},
                {"id": "push", "type": "round", "tone": "blue", "x": 0.35, "y": 2.45, "w": 3.8, "h": 1.0, "fs": 10, "align": "left", "text": "g_cmd_ring.push(cmd)\n• 값을 먼저 쓰고 head 를 release 로 공개\n• 꽉 차면 false → cmd_ring_full++ (기다리지 않음)"},
                {"type": "round", "tone": "gray", "x": 8.0, "y": 0.1, "w": 4.2, "h": 4.2, "text": "RT 스레드 (SCHED_FIFO 80, 1 kHz)", "valign": "top", "bold": True, "fs": 11},
                {"id": "pop", "type": "round", "tone": "mint", "x": 8.25, "y": 0.75, "w": 3.7, "h": 1.15, "fs": 10, "align": "left", "text": "take_latest_command() — 매 주기\nwhile (cmd_ring_.pop(cmd)) { }\n• head 를 acquire 로 읽고 tail 의 값을 꺼냄\n• 전부 비우고 마지막 것만 쓴다"},
                {"id": "des", "type": "round", "tone": "mint", "x": 8.25, "y": 2.45, "w": 3.7, "h": 1.0, "fs": 10, "align": "left", "text": "desired_[j] = cmd.position[j]\nlast_cmd_ns_ = now (워치독이 본다)\ncommands_applied++"},
            ] + slots + [
                {"type": "round", "tone": "none", "x": 4.6, "y": 0.9, "w": 3.3, "h": 0.7, "text": "SpscRing<JointCommand, 64>\n= 우편함 (칸 64개, 한 칸은 항상 비워 둔다)", "fs": 10, "bold": True},
                {"type": "none", "tone": "none", "x": 4.6, "y": 2.4, "w": 1.6, "h": 0.5, "text": "tail ↑ 꺼내는 자리\n(RT 가 움직임)", "fs": 8.5, "color": "0F766E"},
                {"type": "none", "tone": "none", "x": 6.4, "y": 2.4, "w": 1.6, "h": 0.5, "text": "head ↑ 넣는 자리\n(ROS 2 가 움직임)", "fs": 8.5, "color": "2563EB"},
                {"type": "none", "tone": "none", "x": 4.6, "y": 3.1, "w": 3.3, "h": 1.1, "text": "칸 수가 2의 거듭제곱 → 다음 칸 = (i+1) & 63\nhead == tail 이면 비어 있음, 다음 head == tail 이면 꽉 참\n공유하는 것은 원자 변수 2개(head, tail)뿐 → 락 없음", "fs": 9, "align": "left"},
            ],
            "arrows": [
                {"from": "oc", "to": "push"},
                {"from": "push", "to": {"x": 4.7, "y": 2.02}, "label": "push", "labelW": 0.8, "labelOff": {"x": 0, "y": -0.3}},
                {"from": {"x": 8.05, "y": 2.02}, "to": "pop", "label": "pop", "labelW": 0.8, "labelOff": {"x": 0, "y": -0.3}},
                {"from": "pop", "to": "des"},
            ],
            "legend": "소스 위치: on_command rt_control_node.cpp:184-201 · SpscRing push/pop rt_control/rt_core/include/rt_core/spsc_ring.hpp:38-64 · 꺼내는 쪽 control_step.cpp:61-79. 같은 링 클래스가 세 곳에 쓰인다: 명령 우편함 64칸 · 상태 벨트 2048칸 · 타이밍 65536칸. 왜 락이 아닌가는 두 장 뒤"}


def stage4():
    # 시간축 그림(축척 아님): 목표 시각 4개, 실제 깬 시각은 조금 늦다
    ms = 2.7            # 1 ms 를 2.7 인치로
    x0 = 1.0
    y_axis = 2.65
    shapes = [
        {"type": "none", "tone": "none", "x": 0.0, "y": 0.0, "w": 12.3, "h": 0.75, "fs": 10.5, "align": "left", "text": ["clock_nanosleep(CLOCK_MONOTONIC, TIMER_ABSTIME, next_wake_ns): '지금부터 1 ms' 가 아니라 '그 시각에' 깨워 달라. 다음 목표 = 이번 목표 + 1 ms (실제 깬 시각이 아니라 목표에 더한다) → 늦게 깬 만큼이 쌓이지 않는다(드리프트 0)"]},
    ]
    arrows = [{"from": {"x": 0.4, "y": y_axis}, "to": {"x": 12.1, "y": y_axis}, "tone": "gray", "width": 2, "label": "시간 →", "labelW": 0.9, "labelOff": {"x": 5.3, "y": 0.3}}]
    lates = [0.25, 0.12, 0.95, 0.18]     # 늦게 깬 정도(그림용, 축척 아님)
    for i, late in enumerate(lates):
        tx = x0 + i * ms
        # 목표 시각 눈금
        arrows.append({"from": {"x": tx, "y": y_axis - 0.35}, "to": {"x": tx, "y": y_axis + 0.35}, "tone": "gray", "noHead": True, "width": 1.5})
        shapes.append({"type": "none", "tone": "none", "x": tx - 0.7, "y": y_axis + 0.4, "w": 1.4, "h": 0.5, "fs": 9, "align": "center", "text": f"목표 시각 t{i}\n(= t0 + {i} ms)" if i else "목표 시각 t0"})
        # 실제 깬 시각(점) + 지연 막대
        shapes.append({"type": "rect", "tone": "red", "x": tx, "y": y_axis - 0.14, "w": late, "h": 0.28, "text": "", "margin": 0, "lineW": 0.75})
        shapes.append({"type": "ellipse", "tone": "navy", "x": tx + late - 0.09, "y": y_axis - 0.09, "w": 0.18, "h": 0.18, "text": "", "margin": 0})
        # 일하는 구간(step) 과 잠
        shapes.append({"type": "rect", "tone": "mint", "x": tx + late + 0.08, "y": y_axis - 0.95, "w": 0.55, "h": 0.5, "text": "step()\n일", "fs": 8.5, "margin": 0})
        shapes.append({"type": "none", "tone": "none", "x": tx + late + 0.7, "y": y_axis - 0.95, "w": 1.6, "h": 0.5, "fs": 8.5, "align": "left", "color": "475569", "text": "→ 벨트에 push → 다음 목표까지 잔다"})
    # 설명 글
    shapes += [
        {"type": "callout", "tone": "amber", "x": 6.0, "y": 1.0, "w": 3.3, "h": 0.8, "fs": 9.5, "text": "빨간 막대 = 깨어남 지연 wake_lat\n= 실제 깬 시각 − 목표 시각. 표①이 재는 것"},
        {"type": "none", "tone": "none", "x": 2.6, "y": 1.45, "w": 2.6, "h": 0.4, "fs": 8.5, "color": "DC2626", "text": "period_err = (이번 깸 − 지난 깸) − 1 ms"},
        {"type": "none", "tone": "none", "x": 0.0, "y": 3.55, "w": 12.3, "h": 1.0, "fs": 10.5, "align": "left", "text": ["왜 평균이 아니라 max 인가: 세 번째 깸처럼 한 번만 크게 늦어도 그 주기의 제어가 밀린다. 60초 = 60,000번 중 가장 늦은 한 번이 max, 999번 중 999번이 안에 드는 값이 p99.9", "Pi 4 부하 중 max: 일반 커널 781 us → PREEMPT_RT 301 → CPU 고정 311 → 격리(isolcpus=3) 189 us (1 ms 의 19%). 드롭 0. 측정기·실험 사슬·표①은 3부 장표 {{first:단계 4 검증 — 측정기}}~{{first:단계 4 검증의 결론}}"]},
    ]
    return {"kind": "diagram", "section": SEC1, "title": "단계 4 그림 — 1 ms 마다 '정확히' 깬다: 목표 시각과 실제 깬 시각의 차이가 깨어남 지연 (그림은 축척 아님)",
            "shapes": shapes, "arrows": arrows,
            "foot": "소스 위치: rt_control/rt_core/src/rt_loop.cpp:120-158 run() 본체 — (a) clock_nanosleep :130 (b) wake_lat :137, period_err :138-143 (c) step :147, work_ns :148 (d) ring.push :151-153 (e) next_wake_ns += period :156. 준비 5단계 :29-97"}


def stage5():
    return {"kind": "diagram", "section": SEC1, "title": "단계 5 그림 — 제어 단계 한 주기(1 ms): 최신 명령 → 워치독 → 상태 머신 → 변화량 제한 → 로봇 쓰기/읽기 → 벨트",
            "shapes": [
                {"id": "ring", "type": "hex", "tone": "gray", "x": 0.1, "y": 0.45, "w": 1.5, "h": 0.9, "text": "우편함\n(명령 링 64)", "fs": 10},
                {"id": "s1", "type": "round", "tone": "mint", "x": 1.95, "y": 0.35, "w": 2.35, "h": 1.1, "fs": 10, "text": "① take_latest_command\n전부 비우고 마지막 것만\n→ desired_ (상위가 원하는 목표)"},
                {"id": "wd", "type": "diamond", "tone": "amber", "x": 4.6, "y": 0.2, "w": 2.2, "h": 1.4, "fs": 9.5, "text": "② 워치독\n마지막 명령이 50 ms 보다 오래됐나?"},
                {"id": "stale", "type": "round", "tone": "red", "x": 7.15, "y": 0.05, "w": 2.4, "h": 0.75, "fs": 9.5, "text": "예(stale): desired_ = 현재 위치(멈춤)\ntripped=true, watchdog_trips++"},
                {"id": "ok", "type": "round", "tone": "mint", "x": 7.15, "y": 1.0, "w": 2.4, "h": 0.6, "fs": 9.5, "text": "아니오: tripped=false"},
                {"id": "sm", "type": "round", "tone": "purple", "x": 9.9, "y": 0.2, "w": 2.3, "h": 1.4, "fs": 9.5, "text": "상태 머신 handle(사건)\nCOMMAND / WATCHDOG_TRIP /\nRECOVERED → RUNNING·FAULT·…\n(전이표, 표 밖은 illegal_events++)"},
                {"id": "lim", "type": "diamond", "tone": "amber", "x": 9.9, "y": 2.15, "w": 2.3, "h": 1.4, "fs": 9.5, "text": "③ 변화량 제한\n|desired − applied| > 0.05 rad?"},
                {"id": "lim_y", "type": "round", "tone": "red", "x": 7.15, "y": 2.0, "w": 2.4, "h": 0.7, "fs": 9.5, "text": "예: 이번 주기는 0.05 rad 만 이동\nstep_limited++"},
                {"id": "lim_n", "type": "round", "tone": "mint", "x": 7.15, "y": 2.9, "w": 2.4, "h": 0.6, "fs": 9.5, "text": "아니오: applied_ = desired_"},
                {"id": "be", "type": "cube", "tone": "blue", "x": 3.9, "y": 2.1, "w": 2.9, "h": 1.45, "fs": 9.5, "text": "④ 백엔드(로봇 쪽)\nwrite_command(applied_)\nread_state(position_, velocity_)\nSimLag | MuJoCo | 실물(자리)"},
                {"id": "belt", "type": "hex", "tone": "gray", "x": 0.1, "y": 2.25, "w": 3.4, "h": 1.2, "fs": 9.5, "text": "⑤ 상태 벨트(링 2048)에\nJointStateSample push\n꽉 차면 state_drops++ (기다리지 않음)"},
            ],
            "arrows": [
                {"from": "ring", "to": "s1"}, {"from": "s1", "to": "wd"},
                {"from": "wd", "to": "stale", "label": "예", "labelW": 0.5}, {"from": "wd", "to": "ok", "label": "아니오", "labelW": 0.7, "labelOff": {"x": 0, "y": 0.2}},
                {"from": "stale", "to": "sm"}, {"from": "ok", "to": "sm"},
                {"from": "sm", "to": "lim"},
                {"from": "lim", "to": "lim_y", "label": "예", "labelW": 0.5}, {"from": "lim", "to": "lim_n", "label": "아니오", "labelW": 0.7, "labelOff": {"x": 0, "y": 0.2}},
                {"from": "lim_y", "to": "be"}, {"from": "lim_n", "to": "be"},
                {"from": "be", "to": "belt", "label": "읽은 위치·속도", "labelW": 1.3},
            ],
            "texts": [
                {"x": 0.1, "y": 3.75, "w": 12.1, "h": 0.7, "fs": 10, "text": ["한 주기(1 ms) 안에 이 다섯 가지 전부. 함수 안에 할당·락·파일·네트워크가 없다(RT 규칙). 로봇에 실제로 가는 값은 desired_ 가 아니라 applied_ 다", "카운터(commands_applied · watchdog_trips · step_limited · state_drops · illegal_events)는 std::atomic — ROS 2 스레드가 1 Hz 로 읽어 rt_status 에 싣는다(단계 8)"]},
            ],
            "legend": "소스 위치: control_step.cpp:28-56 step() 본체 · :61-79 take_latest_command · :83-100 check_watchdog · :103-122 update_state_machine · :126-142 limit_step · robot_state_machine.cpp:15-32 전이표, :34-46 handle. 안전 경로(명령이 끊기면 FAULT → RECOVERING → READY)는 1부 끝의 가로지르기 장표"}


def stage6():
    return {"kind": "diagram", "section": SEC1, "title": "단계 6 그림 — 백엔드: 제어 코드는 '세 함수'만 알고, 로봇은 그 아래에서 갈아 끼운다",
            "shapes": [
                {"id": "cs", "type": "round", "tone": "mint", "x": 3.2, "y": 0.1, "w": 5.9, "h": 0.95, "fs": 10.5, "bold": True, "text": "ControlStep (제어 단계, 단계 5)\n매 주기 write_command(applied_, dof) → read_state(position_, velocity_, dof)"},
                {"id": "be", "type": "hex", "tone": "amber", "x": 2.6, "y": 1.5, "w": 7.1, "h": 1.0, "fs": 10, "text": "Backend 인터페이스 (backend.hpp:17-33) — 가상 함수 세 개\ninit(dof, period_ns) 시작 때 한 번(할당 허용) · write_command(target, dof) · read_state(position, velocity, dof) — RT 에서 매 주기, 기다림 금지"},
                {"id": "a", "type": "round", "tone": "blue", "x": 0.2, "y": 3.05, "w": 3.7, "h": 1.4, "fs": 9.5, "align": "left", "text": "A  SimLagBackend (sim_lag_backend.cpp:21-38)\n• position += (target − position) × 0.02\n• 1차 지연, 물리 없음(중력·충돌 없음)\n• 로봇·시뮬레이터 없이 노드 전체 시험, CI 러너에서도"},
                {"id": "b", "type": "round", "tone": "purple", "x": 4.3, "y": 3.05, "w": 3.7, "h": 1.4, "fs": 9.5, "align": "left", "text": "B  MujocoBackend (mujoco_backend.cpp:226-252)\n• ctrl[액추에이터] ← 목표, mj_step × substeps\n• qpos/qvel 읽기. 걸음 맞추기 :110-125\n• 모델 Menagerie SO-ARM100, 한 주기 p99 8.5 us"},
                {"id": "c", "type": "round", "tone": "gray", "x": 8.4, "y": 3.05, "w": 3.7, "h": 1.4, "fs": 9.5, "align": "left", "dashed": True, "text": "C  FeetechSerialBackend (자리만, 2주 밖)\n• 실물 서보 6개, 시리얼 1 Mbps\n• loop_hz 1000 → 200 (프로필 real 절)\n• 바뀌는 것은 이 상자뿐 — 위 두 층은 그대로"},
                {"id": "note", "type": "callout", "tone": "amber", "x": 9.4, "y": 0.1, "w": 2.8, "h": 0.95, "fs": 9.5, "text": "로봇을 바꿔도 제어 코드는 한 줄도 안 바뀐다 — 11/04 SimLag → MuJoCo 교체로 확인"},
                {"id": "sel", "type": "round", "tone": "white", "x": 0.2, "y": 0.1, "w": 2.9, "h": 1.15, "fs": 9, "align": "left", "text": "어느 것을 쓸지: 노드 파라미터\nbackend: sim_lag | mujoco\n(make_backend) ← robots/so101.yaml\n→ profile_to_params.py"},
            ],
            "arrows": [
                {"from": "cs", "to": "be", "label": "세 함수만 부른다"},
                {"from": "be", "to": "a", "label": "구현 A"}, {"from": "be", "to": "b", "label": "구현 B"}, {"from": "be", "to": "c", "label": "구현 C (예정)", "dashed": True},
                {"from": "sel", "to": "be", "dashed": True, "noHead": True},
            ],
            "legend": "소스 위치: 인터페이스 rt_control/rt_core/include/rt_core/backend.hpp:17-33 · A src/sim_lag_backend.cpp:21-38 · B src/mujoco_backend.cpp:110-125(tune_timestep), 226-252(write/read) · 선택 rt_control/ros2_adapter/src/rt_control_node.cpp:135 make_backend() · 프로필 robots/so101.yaml. 물리 비용 측정(E15)은 3부 장표 {{first:단계 7 검증}}"}


def stage7_chart():
    return {"kind": "chart", "section": SEC1, "title": "단계 7 그래프 — 로봇이 움직인 결과: 관절별 추종 오차 |목표 − 실제| (30초 기록 평균, rad) — 중력이 걸리는 관절만 처진다",
            "chart": {"categories": ["shoulder_pan", "shoulder_lift", "elbow_flex", "wrist_flex", "wrist_roll", "gripper"],
                      "series": [{"name": "추종 오차 (rad)", "values": [0.0000, 0.0191, 0.0094, 0.0025, 0.0000, 0.0001]}],
                      "valTitle": "rad (1 rad = 57.3°)", "numFmt": "0.0000", "max": 0.025},
            "bullets": ["목표 [0.3, −0.2, 0.1, 0, 0, 0.5] 를 50 Hz 로 30초 주고 /joint_states 를 기록한 뒤 bag_to_csv.py 가 낸 표(E20)",
                        "shoulder_lift 0.0191 rad = 1.1°, elbow_flex 0.0094 rad = 0.5°, wrist_flex 0.0025 rad = 0.14° — 팔을 '들고 있는' 관절일수록 크다 = 중력 처짐",
                        "shoulder_pan(수평 회전) · wrist_roll · gripper 는 0 — 중력이 토크를 만들지 않는 축",
                        "SimLag 백엔드였다면 여섯 막대가 전부 0 — 이 그래프는 물리(MuJoCo)가 들어와서만 보인다",
                        "다음 단계(보류): 중력 보상(토크 피드포워드)을 넣으면 왼쪽 세 막대가 내려간다"],
            "caption": "출처: docs/measurements/record_summary_wsl_20261105.md '추종 오차' 표(평균 = 최대, 목표가 고정이라). 실측 위치 −0.181 rad 등은 앞 장표. 물리 실험 사슬(E15 → E16)은 3부 장표 {{first:단계 7 검증}}"}


def stage8():
    return {"kind": "diagram", "section": SEC1, "title": "단계 8 그림 — 상태가 밖으로 나가는 길: RT 스레드는 벨트에 올리기만, 발행은 다른 스레드가 자기 박자로",
            "shapes": [
                {"type": "round", "tone": "gray", "x": 0.1, "y": 0.1, "w": 3.9, "h": 3.5, "text": "RT 스레드 (1 kHz)", "valign": "top", "bold": True},
                {"id": "st", "type": "round", "tone": "mint", "x": 0.3, "y": 0.6, "w": 3.5, "h": 1.2, "fs": 10, "align": "left", "text": "step() 끝 ⑤: JointStateSample\n(iter, 시각, dof, 위치·속도·목표) 를\n상태 벨트에 push — 꽉 차면 state_drops++"},
                {"id": "ti", "type": "round", "tone": "mint", "x": 0.3, "y": 2.2, "w": 3.5, "h": 1.2, "fs": 10, "align": "left", "text": "RtLoop::run (d): 타이밍 Sample\n(깨어남 지연 · 주기 오차 · 일한 시간) 을\n타이밍 링에 push — 꽉 차면 drops++"},
                {"id": "r1", "type": "hex", "tone": "amber", "x": 4.5, "y": 0.75, "w": 1.9, "h": 0.9, "text": "상태 벨트\nSpscRing 2048", "fs": 10},
                {"id": "r2", "type": "hex", "tone": "amber", "x": 4.5, "y": 2.35, "w": 1.9, "h": 0.9, "text": "타이밍 링\nSpscRing 65536", "fs": 10},
                {"type": "round", "tone": "gray", "x": 6.9, "y": 0.1, "w": 5.3, "h": 3.5, "text": "ROS 2 실행기 스레드 (일반 우선순위, 타이머 2개)", "valign": "top", "bold": True},
                {"id": "ps", "type": "round", "tone": "blue", "x": 7.1, "y": 0.6, "w": 3.0, "h": 1.2, "fs": 9.5, "align": "left", "text": "publish_state() 100 Hz\n벨트를 전부 비우고 마지막 샘플만\n(1 kHz 샘플 10개 중 최신 1개)"},
                {"id": "pt", "type": "round", "tone": "blue", "x": 7.1, "y": 2.2, "w": 3.0, "h": 1.2, "fs": 9.5, "align": "left", "text": "publish_status() 1 Hz\n지난 1초 샘플 ~1,000개 → p50/p99/max\n+ 카운터 + rt 환경 → JSON 한 줄"},
                {"id": "t1", "type": "doc", "tone": "white", "x": 10.4, "y": 0.6, "w": 1.65, "h": 1.2, "fs": 9.5, "text": "/joint_states\n100 Hz\nJointState"},
                {"id": "t2", "type": "doc", "tone": "white", "x": 10.4, "y": 2.2, "w": 1.65, "h": 1.2, "fs": 9.5, "text": "/rt_status\n1 Hz\nString(JSON)"},
            ],
            "arrows": [
                {"from": "st", "to": "r1", "label": "push 수십 ns"}, {"from": "ti", "to": "r2", "label": "push"},
                {"from": "r1", "to": "ps", "label": "pop 전부"}, {"from": "r2", "to": "pt", "label": "pop 전부"},
                {"from": "ps", "to": "t1"}, {"from": "pt", "to": "t2"},
            ],
            "texts": [
                {"x": 0.1, "y": 3.75, "w": 12.1, "h": 0.7, "fs": 10, "text": ["왜 이렇게: RT 스레드가 직접 ROS 메시지를 발행하면 메모리 할당과 네트워크가 1 ms 안에 들어와 꼬리(max)가 생긴다. 벨트에 올리는 데는 수십 ns 뿐이고, 바깥 스레드가 자기 박자(100 Hz · 1 Hz)로 비운다", "실측(11/05 기록 30초): /joint_states 실제 100.0 Hz, 틈 0, state_drops 0. rt_status 는 wake_us · work_us · drops · state · rt{sched_fifo, mlockall, kernel_realtime} · rmw 를 1초마다"]},
            ],
            "legend": "소스 위치: rt_control_node.cpp:205-207 rt_thread_main · :210-230 publish_state · :233-291 publish_status · 벨트 push 는 control_step.cpp step() ⑤ (:28-56) · 타이밍 push 는 rt_loop.cpp:151-153"}


def stage10():
    return {"kind": "diagram", "section": SEC1, "title": "단계 10 그림 — 관제로: 로봇 안의 1 Hz 요약이 서버의 화면까지 가는 길 (로봇이 51번째 장치가 된다)",
            "shapes": [
                {"id": "a", "type": "doc", "tone": "white", "x": 0.1, "y": 1.3, "w": 1.5, "h": 1.2, "fs": 9.5, "text": "/rt_status\n1 Hz JSON\n(단계 8)"},
                {"id": "b", "type": "round", "tone": "mint", "x": 1.9, "y": 1.15, "w": 2.0, "h": 1.5, "fs": 9.5, "text": "StatusBridge\n(ROS 2 노드, 파이썬)\n구독 → JSON 파싱 →\nmetrics_source"},
                {"id": "c", "type": "round", "tone": "blue", "x": 4.2, "y": 1.15, "w": 1.9, "h": 1.5, "fs": 9.5, "text": "DeviceAgent\n(가상 장치와 같은 클래스)\ndevice_id rt-node-1"},
                {"id": "d", "type": "hex", "tone": "amber", "x": 6.4, "y": 1.2, "w": 1.9, "h": 1.4, "fs": 9.5, "text": "MQTT 브로커\nfleet/rt-node-1/telemetry\n(2부 ②)"},
                {"id": "e", "type": "round", "tone": "blue", "x": 8.6, "y": 1.2, "w": 1.5, "h": 1.4, "fs": 9.5, "text": "수집기\n1초 묶음 COPY\n(2부 ③)"},
                {"id": "f", "type": "cyl", "tone": "gray", "x": 10.35, "y": 0.45, "w": 1.8, "h": 1.15, "fs": 9.5, "text": "TimescaleDB\ntelemetry 표"},
                {"id": "g", "type": "round", "tone": "purple", "x": 10.35, "y": 2.05, "w": 1.8, "h": 1.15, "fs": 9.5, "text": "Grafana 패널\n'RT 노드: 깨어남 지연 p99'\n'멈춤·고장 장치'"},
            ],
            "arrows": [
                {"from": "a", "to": "b", "label": "1 Hz"}, {"from": "b", "to": "c"}, {"from": "c", "to": "d", "label": "publish QoS 0/1"}, {"from": "d", "to": "e", "label": "구독"},
                {"from": "e", "to": "f", "label": "COPY"}, {"from": "f", "to": "g", "label": "SQL"},
            ],
            "texts": [
                {"x": 0.1, "y": 3.0, "w": 12.1, "h": 1.4, "fs": 10, "text": ["가상 장치 50대와 다른 것은 metrics_source(어디서 숫자를 가져오나)뿐: 가상 장치는 난수 걸음, 다리는 rt_status 의 wake p99 · loop_hz · 드롭 · 상태", "watchdog 이 tripped 이면 state 도 tripped 로 올라가 '멈춤·고장 장치' 패널에 잡힌다 — 관제 서버는 로봇이 가상인지 실물인지, ROS 2 인지 모른다", "실물 로봇도 같다: 로봇 안 컴퓨터(Pi 등)에서 이 다리가 돌고, 그 뒤는 2부 데이터의 길 그대로"]},
            ],
            "legend": "소스 위치: fleet/agent/ros_status_bridge.py (123줄: StatusBridge 노드 + DeviceAgent 재사용) · DeviceAgent fleet/agent/device_agent.py · 토픽 이름 규칙 fleet/<device_id>/telemetry · 패널 SQL fleet/grafana/make_dashboard.py"}


def collector_flow():
    return {"kind": "diagram", "section": SEC2, "title": "③ 그림 — 수집기 안의 두 스레드와 1초 묶음: 받는 쪽은 넣기만, 1초마다 묶어서 DB 로, 안 되면 들고 있는다",
            "shapes": [
                {"type": "round", "tone": "gray", "x": 0.1, "y": 0.1, "w": 3.6, "h": 2.3, "text": "paho 콜백 스레드", "valign": "top", "bold": True},
                {"id": "om", "type": "round", "tone": "blue", "x": 0.3, "y": 0.55, "w": 3.2, "h": 1.7, "fs": 9.5, "align": "left", "text": "on_message(msg)\n• 토픽 파싱 → telemetry / status\n• parse_telemetry: ts_ns 와 도착 시각 → 전달 지연 ms\n• with lock: pending_rows.append(row)\n• retain=1 상태는 사건이 아님(events 제외)"},
                {"id": "pend", "type": "hex", "tone": "amber", "x": 4.1, "y": 0.8, "w": 1.8, "h": 1.0, "text": "pending\n(이번 1초 치)", "fs": 10},
                {"type": "round", "tone": "gray", "x": 6.3, "y": 0.1, "w": 5.9, "h": 3.4, "text": "메인 스레드 — 1초마다 flush_once()", "valign": "top", "bold": True},
                {"id": "tb", "type": "round", "tone": "mint", "x": 6.5, "y": 0.55, "w": 2.6, "h": 0.8, "fs": 9.5, "text": "take_batch: pending 을 통째로\nBatch 하나로 (락 한 번)"},
                {"id": "bl", "type": "hex", "tone": "amber", "x": 9.4, "y": 0.5, "w": 2.6, "h": 0.9, "fs": 9.5, "text": "backlog (묶음 목록)\n상한 200,000행 넘으면 오래된 것 버림"},
                {"id": "dr", "type": "diamond", "tone": "amber", "x": 9.55, "y": 1.6, "w": 2.3, "h": 1.2, "fs": 9, "text": "drain: 맨 앞 묶음\nwrite_db(COPY) 성공?"},
                {"id": "okb", "type": "round", "tone": "mint", "x": 6.5, "y": 1.6, "w": 2.6, "h": 0.6, "fs": 9.5, "text": "예: pop → 다음 묶음(순서 유지)"},
                {"id": "ng", "type": "round", "tone": "red", "x": 6.5, "y": 2.4, "w": 2.6, "h": 0.9, "fs": 9.5, "text": "아니오(DB 죽음): db_errors++,\n연결 버리고 멈춤 → 다음 초에 같은 묶음부터"},
                {"id": "db", "type": "cyl", "tone": "gray", "x": 9.9, "y": 3.0, "w": 1.7, "h": 0.5, "fs": 9, "text": "TimescaleDB"},
                {"id": "stats", "type": "doc", "tone": "white", "x": 4.0, "y": 2.3, "w": 2.1, "h": 1.2, "fs": 9, "text": "통계 한 줄 write_stats\nmsgs/s · insert_ms · 지연 p50/p95/max\nonline · backlog_rows · db_errors"},
            ],
            "arrows": [
                {"from": "om", "to": "pend", "label": "append"}, {"from": "pend", "to": "tb", "label": "1초마다"}, {"from": "tb", "to": "bl", "label": "append"},
                {"from": "bl", "to": "dr"}, {"from": "dr", "to": "okb", "label": "예", "labelW": 0.5}, {"from": "dr", "to": "ng", "label": "아니오", "labelW": 0.7, "labelOff": {"x": 0, "y": 0.25}},
                {"from": "dr", "to": "db", "label": "COPY", "labelW": 0.7}, {"from": "okb", "to": "bl", "dashed": True, "label": "다음 묶음", "labelW": 1.0},
                {"from": "tb", "to": "stats", "dashed": True},
            ],
            "texts": [
                {"x": 0.1, "y": 3.65, "w": 12.1, "h": 0.8, "fs": 10, "text": ["왜 1초 묶음 + COPY: 300대 × 1 Hz 를 행마다 INSERT 하면 DB 왕복 300번/초 → 묶으면 1번/초. 대신 DB 에 보이기까지 최대 1초(표③ 비고). DB 가 죽은 동안의 묶음은 메모리에 남아 돌아오면 오래된 것부터(11/04 실측: 뒤늦게 570행 적재, 유실 0 / 1341)"]},
            ],
            "legend": "소스 위치: on_message collector.py:153-181 · take_batch :184-205 · flush_once :207-232 · enforce_backlog_limit :234-240 · drain_backlog :241-255 · 상한 MAX_BACKLOG_ROWS :60 · 종료(request_stop/shutdown) :325, :343-353 · 단일 인스턴스 잠금 fleet/common/single_instance.py"}


def ota_image():
    return {"kind": "image", "section": SEC2, "title": "⑥ 그림 — 나쁜 펌웨어 한 번의 흐름(순서도): 5% 세 대에서 헬스 게이트가 잡고 1초 안에 되돌린다, 47대는 명령을 받은 적도 없다", "image": "img/ota_seq.png",
            "bullets": ["서버(rollout.py)가 3초 동안 텔레메트리를 들어 살아 있는 50대를 찾는다", "5% 단계: 3대에 cmd ota {version 1.2.0-bad, apply_s 1, bad true}", "장치: updating → 1초 뒤 fw_version 교체 → bad 라 state=fault", "서버: 전원 적용 확인 → 헬스 게이트(health_wait) → 비정상 3/3 > 허용 0 → ota_rollback", "장치: fw=1.0.0, state=ok 로 복귀 — 롤백 0.8~1.0초, 50%·100% 단계는 시작도 안 한다", "소스 위치: fleet/ota/rollout.py:183-232 run_stage · :249-262 rollback · 장치 쪽 fleet/agent/device_agent.py:237 apply_ota(이 그림은 흉내 경로) · 실측은 3부 장표 {{first:2부 ⑦⑧ 검증 — 표③-2}} · 진짜 설치는 7부 장표 {{first:덧붙임 (11/10) — 장치의 설치}}"]}
