#!/usr/bin/env python3
"""가상 장치 N 대 — 실물 없이 관제 서버에 부하를 주고 흐름을 검증한다.

각 장치는 DeviceAgent 한 개(스레드 2개: 주기 스레드 + paho 네트워크 스레드). 숫자는 난수 걸음(random walk).

사용:
  python3 fleet/agent/virtual_fleet.py --count 50 --rate 1.0            # 50대, 1 Hz
  python3 fleet/agent/virtual_fleet.py --count 300 --rate 1.0 --duration 60
  python3 fleet/agent/virtual_fleet.py --count 50 --keepalive 10 --keepalive-jitter 5   # keepalive 를 10~15초로 흩뜨림
Ctrl+C 로 끝내면 전부 정상 종료(offline 발행) 한다.
같은 --prefix 로는 한 번에 한 벌만 뜬다 (fleet/logs/fleet_<prefix>.lock). 두 벌이 뜨면 같은 client_id 를 서로 밀어낸다.

keepalive jitter 가 왜 있나 (11/04 실측)
  50대가 거의 동시에 접속하면 keepalive 박자가 맞아 10초마다 한꺼번에 처리되고, 그 순간 이 프로세스(스레드 100개)가 멈칫해
  전달 지연 p95 가 10 ms 로 튄다. keepalive 를 30초로 늘리면 사라지지만 끊김 감지(1.5배)가 45초로 늦어진다.
  장치마다 0~jitter 초를 더해 박자를 흩뜨리면 감지 시간은 거의 그대로 두고 동기 부하만 없앨 수 있다.
"""
import argparse
import os
import random
import signal
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "common"))
from device_agent import DeviceAgent  # noqa: E402
import single_instance  # noqa: E402


class VirtualMetrics:
    """장치 하나의 가짜 센서. 호출할 때마다 조금씩 움직이는 값을 돌려준다."""

    def __init__(self, seed):
        self.rng = random.Random(seed)
        self.cpu = self.rng.uniform(20, 60)
        self.temp = self.rng.uniform(40, 55)
        self.mem = self.rng.uniform(30, 50)
        self.rssi = self.rng.randint(-70, -50)

    def __call__(self):
        self.cpu = clamp(self.cpu + self.rng.uniform(-3, 3), 0, 100)
        self.temp = clamp(self.temp + self.rng.uniform(-0.3, 0.3), 20, 90)
        self.mem = clamp(self.mem + self.rng.uniform(-0.5, 0.5), 0, 100)
        self.rssi = int(clamp(self.rssi + self.rng.randint(-2, 2), -90, -30))
        return {
            "cpu_pct": round(self.cpu, 1),
            "temp_c": round(self.temp, 1),
            "mem_pct": round(self.mem, 1),
            "rssi": self.rssi,
            "loop_hz": None,
            "wake_p99_us": None,
        }


def clamp(x, lo, hi):
    if x < lo:
        return lo
    if x > hi:
        return hi
    return x


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--count", type=int, default=50)
    ap.add_argument("--rate", type=float, default=1.0, help="장치당 초당 메시지 수")
    ap.add_argument("--broker", default="localhost")
    ap.add_argument("--port", type=int, default=1883)
    ap.add_argument("--duration", type=float, default=0, help="초. 0 이면 Ctrl+C 까지")
    ap.add_argument("--prefix", default="vdev")
    ap.add_argument("--keepalive", type=int, default=10, help="MQTT keepalive 초 (실측: 지연 튐 주기가 이 값을 따라간다)")
    ap.add_argument("--keepalive-jitter", type=int, default=0, help="장치마다 keepalive 에 0~N 초를 더해 박자를 흩뜨린다")
    ap.add_argument("--telemetry-qos", type=int, default=0, choices=[0, 1],
                    help="텔레메트리 QoS. 1 이면 수집기가 잠깐 죽어도(지속 세션) 브로커가 대신 들고 있다")
    ap.add_argument("--slot-root", default="",
                    help="주면 장치마다 <slot-root>/<id>/ 에 A/B 슬롯을 두고 ota 명령(url 있음)을 진짜로 설치한다. 비우면 흉내 경로")
    a = ap.parse_args()

    lock = single_instance.acquire(f"fleet_{a.prefix}")
    if lock is None:
        print(f"virtual fleet: 같은 prefix '{a.prefix}' 의 가상 장치가 이미 떠 있습니다 (pid {single_instance.other_pid(f'fleet_{a.prefix}')}). "
              f"두 벌이 뜨면 같은 client_id 를 서로 밀어냅니다 → 먼저 그쪽을 Ctrl+C 로 끝내세요.")
        return 3

    rng = random.Random(0)   # 재현 가능한 jitter (장치 i 는 항상 같은 값)
    agents = []
    for i in range(a.count):
        device_id = f"{a.prefix}-{i + 1:03d}"
        keepalive = a.keepalive + rng.randint(0, a.keepalive_jitter)
        slot_root = None
        if a.slot_root:
            slot_root = os.path.join(a.slot_root, device_id)
        agent = DeviceAgent(device_id, a.broker, a.port, 1.0 / a.rate, VirtualMetrics(seed=i), fw_version="1.0.0",
                            keepalive_s=keepalive, telemetry_qos=a.telemetry_qos, slot_root=slot_root)
        agents.append(agent)

    stop_flag = {"stop": False}

    def on_signal(signum, frame):
        stop_flag["stop"] = True

    signal.signal(signal.SIGINT, on_signal)
    signal.signal(signal.SIGTERM, on_signal)

    # 한꺼번에 붙으면 브로커가 순간 몰리므로 조금씩 시차를 둔다
    for agent in agents:
        agent.start()
        time.sleep(0.01)
    mode = "artifact OTA (slots in %s)" % a.slot_root if a.slot_root else "simulated OTA"
    print(f"virtual fleet: {a.count} devices @ {a.rate} Hz -> {a.broker}:{a.port}  keepalive={a.keepalive}s(+0~{a.keepalive_jitter}) qos={a.telemetry_qos}  {mode}  (Ctrl+C to stop)")

    started = time.monotonic()
    while not stop_flag["stop"]:
        time.sleep(0.5)
        if a.duration > 0 and time.monotonic() - started > a.duration:
            break

    print("stopping ...")
    for agent in agents:
        agent.stop()
    total_buffered = sum(ag.buffered_total for ag in agents)
    total_flushed = sum(ag.flushed_total for ag in agents)
    total_reconnects = sum(ag.reconnects for ag in agents)
    print(f"done. buffered={total_buffered} flushed={total_flushed} reconnects={total_reconnects}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
