#!/usr/bin/env python3
"""장치 에이전트 — 장치(가상 또는 실물) 한 대가 관제 서버에 자기 상태를 보고하는 프로그램.

하는 일 (매 주기, 기본 1 Hz)
  1) 텔레메트리 JSON 을 fleet/<id>/telemetry 로 발행 (일련번호 seq 포함 → 빠진 번호 = 유실)
  2) 브로커와 끊기면 메시지를 메모리에 모아 두었다가(store-and-forward) 다시 붙으면 QoS 1 로 재전송
  3) 접속 시 fleet/<id>/status 에 "online"(보관 메시지), 끊길 때 브로커가 대신 "offline" 을 남김 (LWT, 유언)
  4) fleet/<id>/cmd 로 오는 명령을 받음 (오늘은 ping 만. D4 에 OTA 명령이 추가된다)

읽는 순서: DeviceAgent.__init__ → start → tick (한 주기) → on_connect (재접속 시 버퍼 비우기)

실물 장치(Pi, RT 노드)도 같은 클래스를 쓴다. 다른 것은 metrics_source(어디서 숫자를 가져오나)뿐이다.
"""
import json
import threading
import time
from collections import deque

import paho.mqtt.client as mqtt

MAX_BUFFER = 3600  # 끊겼을 때 모아 두는 최대 개수 (1 Hz 기준 1시간). 넘치면 가장 오래된 것을 버린다


class DeviceAgent:
    def __init__(self, device_id, broker_host, broker_port, period_s, metrics_source, fw_version="1.0.0"):
        self.device_id = device_id
        self.period_s = period_s
        self.metrics_source = metrics_source  # 호출하면 dict 를 돌려주는 함수 (가상: 난수, 실물: 센서)
        self.fw_version = fw_version
        self.seq = 0
        self.buffer = deque()          # 끊겼을 때 쌓아 두는 (topic, payload)
        self.buffered_total = 0        # 지금까지 버퍼에 들어간 수
        self.flushed_total = 0         # 재접속 뒤 재전송한 수
        self.reconnects = 0
        self.state = "ok"
        self.running = False
        self.thread = None
        self.lock = threading.Lock()

        self.topic_telemetry = f"fleet/{device_id}/telemetry"
        self.topic_status = f"fleet/{device_id}/status"
        self.topic_cmd = f"fleet/{device_id}/cmd"
        self.topic_cmd_reply = f"fleet/{device_id}/cmd_reply"

        self.client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, client_id=f"agent-{device_id}",
                                  protocol=mqtt.MQTTv311)
        # 유언(LWT): 이 클라이언트가 비정상 종료되면 브로커가 대신 "offline" 을 발행한다
        self.client.will_set(self.topic_status, payload="offline", qos=1, retain=True)
        self.client.on_connect = self.on_connect
        self.client.on_disconnect = self.on_disconnect
        self.client.on_message = self.on_message
        self.client.reconnect_delay_set(min_delay=1, max_delay=5)  # 끊기면 1~5초 간격으로 자동 재접속
        self.broker_host = broker_host
        self.broker_port = broker_port

    # ---------- 시작 / 종료 ----------
    def start(self):
        self.running = True
        self.client.connect_async(self.broker_host, self.broker_port, keepalive=10)
        self.client.loop_start()  # paho 가 네트워크 처리용 스레드를 하나 만든다
        self.thread = threading.Thread(target=self.run_loop, name=f"tick-{self.device_id}", daemon=True)
        self.thread.start()

    def stop(self):
        self.running = False
        if self.thread is not None:
            self.thread.join(timeout=2.0)
        # 정상 종료: 내가 직접 offline 을 남기고 끊는다 (유언은 비정상 종료용)
        self.client.publish(self.topic_status, payload="offline", qos=1, retain=True)
        time.sleep(0.2)
        self.client.loop_stop()
        self.client.disconnect()

    # ---------- 한 주기 ----------
    def run_loop(self):
        next_tick = time.monotonic()
        while self.running:
            self.tick()
            next_tick += self.period_s  # 절대 시각 누적 (RT 루프와 같은 원리, 정밀도만 낮음)
            delay = next_tick - time.monotonic()
            if delay > 0:
                time.sleep(delay)

    def tick(self):
        metrics = self.metrics_source()
        payload = {
            "device_id": self.device_id,
            "seq": self.seq,
            "ts_ns": time.time_ns(),      # 벽시계(UTC). 수집기가 "도착 - 측정" 으로 수집 지연을 계산한다
            "fw_version": self.fw_version,
            "state": self.state,
            "buffered": self.buffered_total,
            "flushed": self.flushed_total,
            "reconnects": self.reconnects,
        }
        payload.update(metrics)
        self.seq += 1
        self.send_or_buffer(self.topic_telemetry, json.dumps(payload))

    def send_or_buffer(self, topic, payload):
        if self.client.is_connected():
            self.client.publish(topic, payload, qos=0)
            return
        with self.lock:
            if len(self.buffer) >= MAX_BUFFER:
                self.buffer.popleft()  # 가장 오래된 것을 버린다
            self.buffer.append((topic, payload))
            self.buffered_total += 1

    # ---------- 브로커 콜백 (paho 네트워크 스레드에서 불린다) ----------
    def on_connect(self, client, userdata, flags, reason_code, properties):
        if reason_code.is_failure:
            return
        client.publish(self.topic_status, payload="online", qos=1, retain=True)
        client.subscribe(self.topic_cmd, qos=1)
        self.flush_buffer()

    def flush_buffer(self):
        """끊긴 동안 모아 둔 것을 QoS 1(최소 한 번 도착 보장)로 재전송"""
        with self.lock:
            items = list(self.buffer)
            self.buffer.clear()
        for topic, payload in items:
            self.client.publish(topic, payload, qos=1)
            self.flushed_total += 1

    def on_disconnect(self, client, userdata, disconnect_flags, reason_code, properties):
        if self.running:
            self.reconnects += 1  # paho 가 자동으로 다시 붙는다 (reconnect_delay_set)

    def on_message(self, client, userdata, msg):
        try:
            cmd = json.loads(msg.payload.decode("utf-8"))
        except ValueError:
            return
        name = cmd.get("cmd", "")
        reply = {"device_id": self.device_id, "cmd": name, "ok": False}
        if name == "ping":
            reply["ok"] = True
            reply["seq"] = self.seq
        elif name == "set_state":
            self.state = str(cmd.get("state", "ok"))
            reply["ok"] = True
        client.publish(self.topic_cmd_reply, json.dumps(reply), qos=1)
