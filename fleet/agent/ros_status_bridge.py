#!/usr/bin/env python3
"""ROS 2 → 관제 다리 — RT 제어 노드(rt_control_node)를 관제의 "진짜 장치 한 대"로 올린다.

  /rt_status (JSON, 1 Hz) ──구독──▶ 이 프로그램 ──DeviceAgent──▶ fleet/rt-node-1/telemetry

가상 장치 50대 옆에 실제 RT 노드가 51번째 장치로 붙는다. 대시보드의 "RT 노드: 깨어남 지연 p99" 패널이 여기서 채워진다.
watchdog 이 tripped 이면 state 도 tripped 로 올라가 "멈춤 장치" 패널에 잡힌다.

실행 (ROS 2 환경에서):
  python3 fleet/agent/ros_status_bridge.py --device-id rt-node-1
"""
import argparse
import json
import os
import sys
import threading

import rclpy
from rclpy.node import Node
from std_msgs.msg import String

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from device_agent import DeviceAgent  # noqa: E402


class StatusBridge(Node):
    def __init__(self):
        super().__init__("rt_status_bridge")
        self.latest = {}
        self.lock = threading.Lock()
        self.sub = self.create_subscription(String, "rt_status", self.on_status, 10)

    def on_status(self, msg):
        try:
            d = json.loads(msg.data)
        except ValueError:
            return
        with self.lock:
            self.latest = d

    def metrics(self):
        """DeviceAgent 가 매 주기 부른다. 마지막 rt_status 를 텔레메트리 필드로 바꾼다."""
        with self.lock:
            d = dict(self.latest)
        wake = d.get("wake_us", {})
        return {
            "cpu_pct": None,
            "temp_c": None,
            "mem_pct": None,
            "rssi": None,
            "loop_hz": d.get("loop_hz"),
            "wake_p99_us": wake.get("p99"),
            "wake_max_us": wake.get("max"),
            "work_p99_us": d.get("work_us", {}).get("p99"),
            "timing_drops": d.get("timing_drops"),
            "watchdog_trips": d.get("watchdog_trips"),
            "rmw": d.get("rmw"),
            "backend": d.get("backend"),
            "sched_fifo": d.get("rt", {}).get("sched_fifo"),
        }

    def state(self):
        """상태 머신 이름(READY/RUNNING/FAULT/RECOVERING)을 장치 상태로. 없으면 워치독 값."""
        with self.lock:
            name = self.latest.get("state")
            if name is None:
                name = self.latest.get("watchdog", "unknown")
            return str(name).lower()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--device-id", default="rt-node-1")
    ap.add_argument("--broker", default="localhost")
    ap.add_argument("--port", type=int, default=1883)
    ap.add_argument("--rate", type=float, default=1.0)
    ap.add_argument("--slot-root", default="", help="A/B 슬롯 디렉터리 (예: ~/rt-slots). 주면 ota 명령을 진짜로 설치한다")
    ap.add_argument("--auto-update", default="", help="매니페스트 URL. 주면 지휘소 없이 스스로 새 버전을 받는다 (Release 의 manifest.json)")
    ap.add_argument("--poll-s", type=float, default=600.0, help="자율 업데이트 확인 주기(초)")
    ap.add_argument("--window", default="", help="자율 업데이트 허용 시간대 'H0-H1' (예: 3-5). 비우면 항상")
    a = ap.parse_args()

    rclpy.init()
    bridge = StatusBridge()
    slot_root = os.path.expanduser(a.slot_root) if a.slot_root else None
    agent = DeviceAgent(a.device_id, a.broker, a.port, 1.0 / a.rate, bridge.metrics, fw_version="rt_control_ros2 0.1.0",
                        slot_root=slot_root, kind="real")
    agent.start()
    if a.auto_update:
        if slot_root is None:
            print("--auto-update 에는 --slot-root 가 필요합니다")
            return 2
        agent.enable_auto_update(a.auto_update, a.poll_s, parse_window(a.window))
    print(f"bridge: /rt_status -> fleet/{a.device_id}/telemetry @ {a.rate} Hz (Ctrl+C to stop)")
    try:
        while rclpy.ok():
            rclpy.spin_once(bridge, timeout_sec=0.2)
            # 워치독 상태를 장치 상태로 올리되, OTA 가 진행 중(updating)이거나 설치 실패(fault+ota_error)면 그쪽이 우선
            if agent.ota_thread is None and not (agent.state == "fault" and agent.ota_error):
                agent.state = bridge.state()
    except KeyboardInterrupt:
        pass
    finally:
        agent.stop()
        bridge.destroy_node()
        if rclpy.ok():
            rclpy.shutdown()
    return 0


def parse_window(text):
    """'3-5' → (3, 5). 비어 있으면 None"""
    if not text:
        return None
    h0, h1 = text.split("-")
    return (int(h0), int(h1))


if __name__ == "__main__":
    sys.exit(main())
