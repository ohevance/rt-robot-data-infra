#!/usr/bin/env python3
"""fleet 논리 단위 테스트 — 브로커·DB 없이 돈다 (paho 를 가짜 모듈로 바꿔 끼움).

확인하는 것
  1) parse_telemetry: 정상 JSON → 행 + 수집 지연, 깨진 JSON → None
  2) DeviceAgent 의 store-and-forward: 끊긴 동안 tick() 은 버퍼에 쌓고, 재접속(on_connect) 때 QoS 1 로 전부 재전송
  3) Collector.flush_once(dry-run): 메시지 수·온라인 수·지연 통계가 맞게 나온다

실행:  python3 fleet/tests/test_fleet_logic.py
"""
import json
import os
import sys
import time
import types

# ---------- 가짜 paho (네트워크 없이 publish 기록만 한다) ----------
class FakeReasonCode:
    is_failure = False


class FakeClient:
    def __init__(self, api_version, client_id=None, protocol=None):
        self.connected = False
        self.published = []
        self.subscribed = []
        self.will = None
        self.on_connect = None
        self.on_disconnect = None
        self.on_message = None

    def will_set(self, topic, payload=None, qos=0, retain=False):
        self.will = (topic, payload, qos, retain)

    def reconnect_delay_set(self, min_delay=1, max_delay=5):
        pass

    def connect(self, host, port, keepalive=60):
        pass

    def connect_async(self, host, port, keepalive=60):
        pass

    def loop_start(self):
        pass

    def loop_stop(self):
        pass

    def disconnect(self):
        pass

    def is_connected(self):
        return self.connected

    def publish(self, topic, payload=None, qos=0, retain=False):
        self.published.append((topic, payload, qos, retain))

    def subscribe(self, topic, qos=0):
        self.subscribed.append(topic)


fake_mqtt = types.ModuleType("paho.mqtt.client")
fake_mqtt.Client = FakeClient
fake_mqtt.CallbackAPIVersion = types.SimpleNamespace(VERSION2=2)
fake_mqtt.MQTTv311 = 4
sys.modules["paho"] = types.ModuleType("paho")
sys.modules["paho.mqtt"] = types.ModuleType("paho.mqtt")
sys.modules["paho.mqtt.client"] = fake_mqtt

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "agent"))
sys.path.insert(0, os.path.join(HERE, "..", "collector"))
from device_agent import DeviceAgent  # noqa: E402
from collector import Collector, parse_telemetry  # noqa: E402

fail_count = 0


def check(condition, message):
    global fail_count
    if not condition:
        print("FAIL:", message)
        fail_count += 1


class FakeMsg:
    def __init__(self, topic, payload):
        self.topic = topic
        self.payload = payload


def test_parse():
    ts = time.time_ns() - 5_000_000  # 5 ms 전에 측정
    good = json.dumps({"device_id": "d1", "seq": 3, "ts_ns": ts, "cpu_pct": 10.0, "temp_c": 40.0,
                       "mem_pct": 20.0, "rssi": -60, "fw_version": "1.0.0", "state": "ok"}).encode()
    parsed = parse_telemetry(good, time.time_ns())
    check(parsed is not None, "정상 JSON 은 파싱된다")
    row, latency_ms = parsed
    check(row[1] == "d1" and row[2] == 3, "device_id, seq 가 행에 들어간다")
    check(4.0 < latency_ms < 500.0, "수집 지연이 ms 단위로 계산된다 (약 5 ms)")
    check(parse_telemetry(b"{not json", time.time_ns()) is None, "깨진 JSON 은 None")
    check(parse_telemetry(json.dumps({"seq": 1}).encode(), time.time_ns()) is None, "필수 키 없으면 None")


def metrics_fixed():
    return {"cpu_pct": 1.0, "temp_c": 2.0, "mem_pct": 3.0, "rssi": -50, "loop_hz": None, "wake_p99_us": None}


def test_store_and_forward():
    agent = DeviceAgent("d1", "localhost", 1883, 1.0, metrics_fixed)
    client = agent.client
    check(client.will is not None and client.will[1] == "offline", "유언(LWT) 이 offline 으로 설정된다")

    # 끊긴 상태에서 3번 tick → 버퍼 3, 발행 0
    client.connected = False
    agent.tick()
    agent.tick()
    agent.tick()
    check(len(agent.buffer) == 3 and agent.buffered_total == 3, "끊긴 동안은 버퍼에 쌓인다")
    check(len(client.published) == 0, "끊긴 동안은 발행하지 않는다")

    # 재접속 → online 발행 + 구독 + 버퍼 3개를 QoS 1 로 재전송
    client.connected = True
    agent.on_connect(client, None, None, FakeReasonCode(), None)
    topics = [p[0] for p in client.published]
    check(topics[0] == "fleet/d1/status" and client.published[0][1] == "online", "접속하면 online 을 먼저 발행")
    resent = [p for p in client.published if p[0] == "fleet/d1/telemetry"]
    check(len(resent) == 3 and all(p[2] == 1 for p in resent), "버퍼 3개가 QoS 1 로 재전송된다")
    check(agent.flushed_total == 3 and len(agent.buffer) == 0, "재전송 뒤 버퍼는 비고 카운터는 3")
    check("fleet/d1/cmd" in client.subscribed, "명령 토픽을 구독한다")

    # 붙은 상태에서 tick → 바로 발행 (QoS 0), seq 는 계속 증가
    agent.tick()
    last = client.published[-1]
    check(last[0] == "fleet/d1/telemetry" and last[2] == 0, "붙어 있으면 바로 발행")
    check(json.loads(last[1])["seq"] == 3, "seq 는 0,1,2 다음 3")

    # ping 명령 → 응답
    agent.on_message(client, None, FakeMsg("fleet/d1/cmd", json.dumps({"cmd": "ping"}).encode()))
    reply = json.loads(client.published[-1][1])
    check(client.published[-1][0] == "fleet/d1/cmd_reply" and reply["ok"] is True, "ping 에 ok 로 답한다")


def test_collector_dry_run():
    c = Collector("localhost", 1883, "postgresql://x", dry_run=True)
    now = time.time_ns()
    for i in range(3):
        for seq in range(2):
            payload = json.dumps({"device_id": f"v{i}", "seq": seq, "ts_ns": now - 2_000_000,
                                  "cpu_pct": 1, "temp_c": 2, "mem_pct": 3, "rssi": -1,
                                  "fw_version": "1.0.0", "state": "ok"}).encode()
            c.on_message(c.client, None, FakeMsg(f"fleet/v{i}/telemetry", payload))
    c.on_message(c.client, None, FakeMsg("fleet/v9/status", b"offline"))
    c.on_message(c.client, None, FakeMsg("fleet/v0/telemetry", b"garbage"))
    s = c.flush_once()
    check(s["msgs"] == 6, "6개 메시지가 묶였다")
    check(s["online"] == 3, "3대가 온라인")
    check(s["bad"] == 1, "깨진 메시지 1개는 버려지고 세어진다")
    check(s["lat_p50"] is not None and 1.0 < s["lat_p50"] < 500.0, "수집 지연 통계가 ms 로 나온다")
    s2 = c.flush_once()
    check(s2["msgs"] == 0 and s2["online"] == 3, "비운 뒤에는 0 메시지, 온라인은 5초 동안 유지")


if __name__ == "__main__":
    test_parse()
    test_store_and_forward()
    test_collector_dry_run()
    if fail_count == 0:
        print("OK: fleet logic")
        sys.exit(0)
    print(f"FAILED: {fail_count}")
    sys.exit(1)
