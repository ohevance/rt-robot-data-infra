"""SDK 를 쓰는 가장 짧은 예: 관절 하나를 사인파로 흔들고, 목표와 실제 위치를 10번 찍는다.

    [창 1] ./build/zmq_adapter/rt_zmq_node --dof 6 --prio 0          (권한이 있으면 --prio 80)
    [창 2] PYTHONPATH=sdk/python python3 sdk/python/examples/follow_sine.py

명령은 100 Hz 로 보낸다 — 노드의 워치독(기본 50 ms)보다 충분히 자주. 멈추면 노드가 50 ms 뒤 FAULT 로 그 자리에 선다.
"""
import math
import time

from rtsdk import RobotClient

with RobotClient("127.0.0.1") as robot:
    info = robot.info()
    dof = info["dof"]
    print(f"노드: 관절 {dof}, {info['loop_hz']} Hz, 백엔드 {info['backend']}, SCHED_FIFO {info['rt']['sched_fifo']}")
    t0 = time.monotonic()
    for i in range(300):  # 3초
        t = time.monotonic() - t0
        target = [0.0] * dof
        target[0] = 0.3 * math.sin(2 * math.pi * 0.5 * t)  # 0.5 Hz, ±0.3 rad
        robot.send_target(target, wait_ack=False)
        if i % 30 == 0:
            s = robot.latest_state() or robot.wait_state()
            print(f"t={t:4.1f}s 목표 {target[0]:+.3f}  실제 {s.position[0]:+.3f}  상태 {s.robot_state}  명령 {s.cmd_seq}")
        time.sleep(0.01)
    time.sleep(0.1)
    print("명령을 멈춤 →", robot.wait_until(lambda s: s.robot_state == "FAULT").robot_state)
