#!/usr/bin/env python3
"""MQTT 왕복 시간(RTT) — 한 클라이언트가 보내고, 브로커를 거쳐 자기가 다시 받는다. 보낸 시각과 받은 시각을 "같은 시계"로 잰다.

왜 이 도구가 있나 (11/10~11)
  대시보드의 "전달 지연"은 (서버가 받은 시각 − 장치가 찍은 시각)이라 두 기계의 시계 차이가 그대로 섞인다.
  같은 시드니 서버인데 WSL 에서 보낸 것은 184 ms, Pi 에서 보낸 것은 152 ms, 다음 날 아침엔 144 ms 로 보였다 —
  30~40 ms 가 보내는 쪽과 날에 따라 달라진다는 것 자체가 "지연"이 아니라 "지연 + 시계 차이"라는 표시다.
  왕복은 시계 하나(보내는 쪽의 단조 시계)로 재므로 시계 차이가 들어가지 않는다. 편도는 왕복의 절반으로 어림한다(경로가 대칭이라는 가정).

무엇을 재나
  connect_ms : TCP 연결 + TLS 악수 + MQTT CONNECT/CONNACK 까지 (처음 한 번)
  rtt_ms     : PUBLISH(QoS 0) 를 보내고 → 브로커가 구독자인 나에게 되돌려 준 것을 받을 때까지. count 번, interval 간격.
               TLS·비밀번호·브로커의 라우팅을 실제 장치와 같은 길로 지난다 (ping 은 ICMP 라 브로커를 지나지 않고, 보안 그룹이 막는다).
  transit 과의 관계: (전달 지연 표시값) − (rtt 의 절반) ≈ 두 시계의 차이 (어림)

접속 설정은 다른 도구와 같다 — 환경변수 FLEET_BROKER / FLEET_PORT / FLEET_TLS_CA / FLEET_USER / FLEET_PASS (fleet/common/mqtt_conn.py).
결과 JSON 에는 **서버 주소를 적지 않는다**(저장소에 올라가는 파일이다). 어디서 어디로 쟀는지는 --from-label / --server-label 로 적는다.

사용:
  # [Pi 창] 서비스와 같은 설정으로 (에이전트는 그대로 돈다 — client id 가 달라 서로 건드리지 않는다)
  set -a; . ~/.config/rt-fleet/fleet.env; set +a
  python3 fleet/tools/mqtt_rtt.py --count 300 --from-label "Pi 4 (집, Wi-Fi)" --out ~/rtt_pi.json
  # [WSL 창]
  export FLEET_BROKER=<서버> FLEET_TLS_CA=~/fleet-ca.crt FLEET_USER=fleet;  read -s -p "FLEET_PASS: " FLEET_PASS; export FLEET_PASS
  python3 fleet/tools/mqtt_rtt.py --count 300 --from-label "WSL2 (노트북, 집)" --out docs/measurements/rtt_wsl_sydney.json

읽는 순서: percentile → RttProbe(on_connect / on_message / wait_ready / run) → summarize → main
"""
import argparse
import json
import os
import socket
import sys
import threading
import time
from datetime import datetime, timezone

import paho.mqtt.client as mqtt

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "common"))
import mqtt_conn  # noqa: E402


def percentile(sorted_values, p):
    """정렬된 리스트에서 p 백분위수 (가장 가까운 순위 방식 — 수집기와 같은 정의)"""
    n = len(sorted_values)
    index = int(-(-p / 100.0 * n // 1))  # ceil
    if index < 1:
        index = 1
    if index > n:
        index = n
    return sorted_values[index - 1]


class RttProbe:
    """보내고 → 자기가 받는다. 번호(seq)로 짝을 맞춘다."""

    def __init__(self, host, port, qos=0):
        self.host = host
        self.port = port
        self.qos = qos
        self.client_id = f"rtt-{socket.gethostname()}-{os.getpid()}"
        self.topic = f"rtt/{self.client_id}"       # fleet/ 아래가 아니다 — 수집기·배포기가 구독하지 않는 곳
        self.sent_ns = {}                          # seq -> 보낸 시각 (단조 시계)
        self.rtt_ms = {}                           # seq -> 왕복 ms
        self.lock = threading.Lock()
        self.connected = threading.Event()
        self.connect_error = None                  # 브로커가 접속을 거절한 사유 (비밀번호 틀림 등)
        self.connect_ms = None
        self.t_connect_start = None
        self.client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, client_id=self.client_id, protocol=mqtt.MQTTv311)
        self.client.on_connect = self.on_connect
        self.client.on_message = self.on_message
        self.security = mqtt_conn.apply_security(self.client)

    def on_connect(self, client, userdata, flags, reason_code, properties):
        if reason_code.is_failure:
            self.connect_error = str(reason_code)   # 예: "Not authorized" — 비밀번호가 비었거나 틀리다
            self.connected.set()
            return
        if self.connect_ms is None and self.t_connect_start is not None:
            self.connect_ms = (time.perf_counter_ns() - self.t_connect_start) / 1e6
        client.subscribe(self.topic, qos=self.qos)
        self.connected.set()

    def on_message(self, client, userdata, msg):
        t_recv = time.perf_counter_ns()            # 가장 먼저 시각부터 — 파싱 시간이 왕복에 섞이지 않게
        try:
            seq = int(msg.payload.decode("ascii").split(" ", 1)[0])
        except ValueError:
            return
        with self.lock:
            t_send = self.sent_ns.get(seq)
            if t_send is not None and seq not in self.rtt_ms:
                self.rtt_ms[seq] = (t_recv - t_send) / 1e6

    def send(self, seq, payload_bytes):
        payload = f"{seq} ".ljust(payload_bytes, "x")
        with self.lock:
            self.sent_ns[seq] = time.perf_counter_ns()   # publish 를 부르기 "전에" — 되돌아오는 것이 publish 안에서 올 수도 있다
        self.client.publish(self.topic, payload, qos=self.qos)

    def start(self, timeout_s=20.0):
        """붙는다. 못 붙으면 사유를 담아 ConnectionError (주소·포트·CA 파일·비밀번호 중 무엇인지 메시지로 가른다)"""
        self.t_connect_start = time.perf_counter_ns()
        try:
            self.client.connect(self.host, self.port, keepalive=30)
        except OSError as e:   # 이름 풀이 실패·연결 거부·시간 초과·TLS 인증서 검증 실패가 전부 OSError 의 자식이다
            raise ConnectionError(f"브로커에 연결하지 못했습니다: {e.__class__.__name__}: {e}") from e
        self.client.loop_start()
        if not self.connected.wait(timeout_s):
            raise ConnectionError(f"브로커가 {timeout_s:.0f}초 안에 접속을 받아 주지 않았습니다")
        if self.connect_error is not None:
            raise ConnectionError(f"브로커가 접속을 거절했습니다: {self.connect_error} (FLEET_USER / FLEET_PASS 확인 — 비밀번호가 비어 있지 않은가)")

    def wait_ready(self, timeout_s=10.0):
        """구독이 실제로 걸렸는지 — 탐침(음수 번호)을 보내 하나가 되돌아올 때까지. SUBACK 을 믿지 않고 직접 확인한다"""
        deadline = time.monotonic() + timeout_s
        probe = -1
        while time.monotonic() < deadline:
            self.send(probe, 16)
            wait_until = time.monotonic() + 0.5
            while time.monotonic() < wait_until:
                with self.lock:
                    if probe in self.rtt_ms:
                        return True
                time.sleep(0.01)
            probe -= 1
        return False

    def run(self, count, interval_s, payload_bytes, settle_s=3.0):
        for seq in range(count):
            self.send(seq, payload_bytes)
            time.sleep(interval_s)
        deadline = time.monotonic() + settle_s           # 늦게 오는 것을 조금 기다린다
        while time.monotonic() < deadline:
            with self.lock:
                done = sum(1 for s in self.rtt_ms if s >= 0)
            if done >= count:
                break
            time.sleep(0.05)

    def stop(self):
        self.client.loop_stop()
        self.client.disconnect()

    def results(self, count):
        with self.lock:
            return [self.rtt_ms[s] for s in range(count) if s in self.rtt_ms]


def summarize(values, count):
    """왕복 ms 리스트 → 통계 dict. 하나도 못 받았으면 숫자는 None"""
    s = sorted(values)
    out = {"sent": count, "received": len(s), "lost": count - len(s)}
    if len(s) == 0:
        out.update({"min": None, "p50": None, "p95": None, "p99": None, "max": None, "mean": None})
        return out
    out.update({
        "min": round(s[0], 2), "p50": round(percentile(s, 50), 2), "p95": round(percentile(s, 95), 2),
        "p99": round(percentile(s, 99), 2), "max": round(s[-1], 2), "mean": round(sum(s) / len(s), 2),
    })
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--broker", default=None, help="기본: 환경변수 FLEET_BROKER 또는 localhost")
    ap.add_argument("--port", type=int, default=None)
    ap.add_argument("--count", type=int, default=300)
    ap.add_argument("--interval", type=float, default=0.2, help="보내는 간격(초). 0.2 × 300 = 1분")
    ap.add_argument("--payload-bytes", type=int, default=200, help="메시지 크기 — 텔레메트리 한 건(약 300바이트)과 비슷하게")
    ap.add_argument("--qos", type=int, default=0, choices=[0, 1])
    ap.add_argument("--from-label", default="", help="어디서 쟀나 (예: 'Pi 4 (집, Wi-Fi)'). 주소는 적지 않는다")
    ap.add_argument("--server-label", default=os.environ.get("SERVER_LABEL", "시드니 (AWS ap-southeast-2)"))
    ap.add_argument("--out", default="", help="결과 JSON 경로")
    a = ap.parse_args()

    host, port = mqtt_conn.broker_defaults(a.broker, a.port)
    probe = RttProbe(host, port, qos=a.qos)
    try:
        probe.start()
    except (ConnectionError, FileNotFoundError) as e:
        print(e)
        return 1
    if not probe.wait_ready():
        print("구독한 토픽으로 되돌아오는 메시지가 없습니다 — 브로커 설정(토픽 제한)을 확인하세요")
        probe.stop()
        return 1
    probe.run(a.count, a.interval, a.payload_bytes)
    probe.stop()

    stats = summarize(probe.results(a.count), a.count)
    result = {
        "what": "MQTT 왕복 시간: 같은 클라이언트가 PUBLISH 하고 브로커를 거쳐 자기가 다시 받는다 (시계 하나) — fleet/tools/mqtt_rtt.py",
        "from": a.from_label or "(표기 없음 — --from-label 로 적는다. 호스트 이름은 저장소에 남기지 않는다)",
        "server": a.server_label,
        "security": probe.security,              # ["tls", "auth"] — 실제 장치와 같은 길로 쟀는가
        "port": port,
        "qos": a.qos,
        "interval_s": a.interval,
        "payload_bytes": a.payload_bytes,
        "connect_ms": round(probe.connect_ms, 1) if probe.connect_ms is not None else None,
        "rtt_ms": stats,
        "one_way_estimate_ms": round(stats["p50"] / 2.0, 1) if stats["p50"] is not None else None,
        "note": "편도 어림 = 왕복 p50 의 절반(경로 대칭 가정). 대시보드의 전달 지연(도착 − 장치 측정)과의 차이가 두 시계의 차이다",
        "measured_at_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
    }
    print(f"rtt {result['from']} -> {a.server_label} [{' '.join(probe.security) or '평문'}]  "
          f"connect {result['connect_ms']} ms  "
          f"rtt ms min={stats['min']} p50={stats['p50']} p95={stats['p95']} p99={stats['p99']} max={stats['max']}  "
          f"received {stats['received']}/{stats['sent']}")
    if a.out:
        out = os.path.expanduser(a.out)
        os.makedirs(os.path.dirname(out) or ".", exist_ok=True)
        with open(out, "w", encoding="utf-8") as f:
            json.dump(result, f, ensure_ascii=False, indent=2)
            f.write("\n")
        print(f"json -> {out}")
    return 0 if stats["received"] > 0 else 1


if __name__ == "__main__":
    sys.exit(main())
