#!/usr/bin/env python3
"""실물 보드(Pi) 에이전트 — ROS 2 없이 보드의 진짜 숫자(온도·CPU·메모리·부하)를 보고하고, 자율 업데이트를 돌린다.

왜 따로 있나
  ros_status_bridge.py 는 RT 노드(/rt_status)가 떠 있어야 한다. 노드가 없을 때(보드만 켜 둔 평소)도 보드가 함대의 한 대로
  보이고, 지휘소(브로커·노트북)가 꺼져 있어도 GitHub Release 를 보고 스스로 업데이트하려면 이 가벼운 에이전트가 필요하다.
  11/10 — 항상 켜진 서버가 없다는 현실(노트북은 꺼진다, Pi 는 켜져 있다)에서 나온 설계 (DECISIONS 11/10).

하는 일
  - 1 Hz 텔레메트리: temp_c(/sys/class/thermal), cpu_pct(/proc/stat 차분), mem_pct(/proc/meminfo), load1, kind="real"
  - 브로커가 없으면 메모리에 모아 뒀다가(최대 1시간) 돌아오면 재전송 (device_agent 공통)
  - --auto-update URL: poll_s 마다 매니페스트를 읽어 새 버전이면 내려받기 → sha256 → A/B 슬롯 → 자가 점검 → 전환
  - 지휘소가 있으면 ota 명령(url 포함)도 그대로 받는다 (같은 설치 코드)

사용 (Pi, 사용자 서비스로 등록하면 재부팅 뒤에도 돈다 — docs/RELEASE.md 5절):
  python3 fleet/agent/pi_agent.py --device-id pi-rt --broker <브로커 호스트> \\
      --slot-root ~/rt-slots --auto-update https://github.com/<owner>/<repo>/releases/latest/download/manifest.json \\
      --poll-s 600 --window 3-5
브로커 주소는 환경변수 FLEET_BROKER / FLEET_PORT 로도 준다 (EC2 로 옮길 때 설정만 바꾸기 위해).

읽는 순서: BoardMetrics → parse_window → main
"""
import argparse
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from device_agent import DeviceAgent  # noqa: E402


class BoardMetrics:
    """보드의 진짜 숫자. 파일이 없으면(다른 리눅스) None 을 보낸다 — 가짜 숫자를 만들지 않는다"""

    def __init__(self):
        self.prev_idle = None
        self.prev_total = None

    def cpu_pct(self):
        try:
            with open("/proc/stat", encoding="utf-8") as f:
                parts = f.readline().split()
        except OSError:
            return None
        values = [int(x) for x in parts[1:8]]
        idle = values[3] + values[4]
        total = sum(values)
        if self.prev_total is None:
            self.prev_idle, self.prev_total = idle, total
            return None
        d_total = total - self.prev_total
        d_idle = idle - self.prev_idle
        self.prev_idle, self.prev_total = idle, total
        if d_total <= 0:
            return None
        return round(100.0 * (1.0 - d_idle / d_total), 1)

    @staticmethod
    def temp_c():
        path = "/sys/class/thermal/thermal_zone0/temp"
        try:
            with open(path, encoding="utf-8") as f:
                return round(int(f.read().strip()) / 1000.0, 1)
        except (OSError, ValueError):
            return None

    @staticmethod
    def mem_pct():
        try:
            info = {}
            with open("/proc/meminfo", encoding="utf-8") as f:
                for line in f:
                    key, rest = line.split(":", 1)
                    info[key] = int(rest.strip().split()[0])
            total = info["MemTotal"]
            available = info.get("MemAvailable", info.get("MemFree", 0))
            return round(100.0 * (1.0 - available / total), 1)
        except (OSError, KeyError, ValueError, ZeroDivisionError):
            return None

    @staticmethod
    def load1():
        try:
            return round(os.getloadavg()[0], 2)
        except OSError:
            return None

    def __call__(self):
        return {
            "cpu_pct": self.cpu_pct(),
            "temp_c": self.temp_c(),
            "mem_pct": self.mem_pct(),
            "load1": self.load1(),
            "rssi": None,
            "loop_hz": None,       # RT 노드가 없을 때는 모른다 — 노드가 있으면 ros_status_bridge 가 채운다
            "wake_p99_us": None,
        }


def parse_window(text):
    """'3-5' → (3, 5). 비어 있으면 None(항상 허용)"""
    if not text:
        return None
    h0, h1 = text.split("-")
    return (int(h0), int(h1))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--device-id", default="pi-rt")
    ap.add_argument("--broker", default=os.environ.get("FLEET_BROKER", "localhost"))
    ap.add_argument("--port", type=int, default=int(os.environ.get("FLEET_PORT", "1883")))
    ap.add_argument("--rate", type=float, default=1.0)
    ap.add_argument("--telemetry-qos", type=int, default=1, choices=[0, 1])
    ap.add_argument("--fw-version", default="", help="비우면 슬롯의 현재 버전, 슬롯이 비었으면 0.0.0-none")
    ap.add_argument("--slot-root", default="~/rt-slots", help="A/B 슬롯 디렉터리")
    ap.add_argument("--auto-update", default="", help="매니페스트 URL (예: Release 의 .../releases/latest/download/manifest.json)")
    ap.add_argument("--poll-s", type=float, default=600.0)
    ap.add_argument("--window", default="", help="허용 시간대 'H0-H1' (예: 3-5). 비우면 항상")
    ap.add_argument("--once", action="store_true", help="자율 업데이트를 한 번만 확인하고 끝낸다 (테스트·cron 용)")
    a = ap.parse_args()

    slot_root = os.path.expanduser(a.slot_root)
    fw = a.fw_version or "0.0.0-none"
    agent = DeviceAgent(a.device_id, a.broker, a.port, 1.0 / a.rate, BoardMetrics(), fw_version=fw,
                        telemetry_qos=a.telemetry_qos, slot_root=slot_root, kind="real")
    if a.once:
        if not a.auto_update:
            print("--once 에는 --auto-update URL 이 필요합니다")
            return 2
        agent.running = True
        agent.auto_update = {"url": a.auto_update, "poll_s": a.poll_s, "window": parse_window(a.window)}
        installed = agent.auto_update_once()
        print(f"auto-update once: installed={installed} fw={agent.fw_version} stage={agent.ota_stage} error={agent.ota_error}")
        return 0 if agent.state != "fault" else 1

    agent.start()
    if a.auto_update:
        agent.enable_auto_update(a.auto_update, a.poll_s, parse_window(a.window))
    print(f"pi agent: {a.device_id} fw={agent.fw_version} -> {a.broker}:{a.port} @ {a.rate} Hz  slots={slot_root}  "
          f"auto-update={'on (' + str(int(a.poll_s)) + 's' + (', ' + a.window if a.window else '') + ')' if a.auto_update else 'off'}  (Ctrl+C to stop)")
    try:
        while True:
            time.sleep(1.0)
    except KeyboardInterrupt:
        pass
    finally:
        agent.stop()
    return 0


if __name__ == "__main__":
    sys.exit(main())
