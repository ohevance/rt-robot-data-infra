#!/usr/bin/env python3
"""수집기 — MQTT 로 들어오는 텔레메트리를 1초마다 묶어 TimescaleDB 에 넣고, 자기 통계를 남긴다.

흐름
  브로커 ──(paho 콜백 스레드: on_message → 파싱 → pending 리스트)──▶ 메인 스레드(1초마다): 묶어서 COPY 적재
                                                                     + devices 갱신 + 통계 한 줄 출력/저장

왜 1초 묶음(batch)인가
  행 하나씩 INSERT 하면 장치 300대 × 1 Hz 에서 DB 왕복 300번/초. 묶어서 COPY 하면 1번/초.
  대신 "수집 지연"에 최대 1초가 더해진다 → 통계에 그대로 드러나게 둔다 (ingest_latency_ms).

읽는 순서: parse_telemetry → Collector.on_message → Collector.flush_once → main
사용:
  python3 fleet/collector/collector.py                # localhost 브로커·DB
  python3 fleet/collector/collector.py --dry-run      # DB 없이 통계만 출력 (브로커는 필요)
"""
import argparse
import json
import statistics
import sys
import threading
import time
from datetime import datetime, timezone

import paho.mqtt.client as mqtt

TELEMETRY_COLUMNS = ("time", "device_id", "seq", "cpu_pct", "temp_c", "mem_pct", "rssi",
                     "loop_hz", "wake_p99_us", "fw_version", "state", "ingest_latency_ms")


def parse_telemetry(payload_bytes, arrival_ns):
    """JSON 바이트 → (행 튜플, 수집 지연 ms). 깨진 메시지면 None."""
    try:
        d = json.loads(payload_bytes.decode("utf-8"))
    except (ValueError, UnicodeDecodeError):
        return None
    if "device_id" not in d or "ts_ns" not in d:
        return None
    ts_ns = int(d["ts_ns"])
    latency_ms = (arrival_ns - ts_ns) / 1e6
    measured_at = datetime.fromtimestamp(ts_ns / 1e9, tz=timezone.utc)
    row = (
        measured_at,
        str(d["device_id"]),
        d.get("seq"),
        d.get("cpu_pct"),
        d.get("temp_c"),
        d.get("mem_pct"),
        d.get("rssi"),
        d.get("loop_hz"),
        d.get("wake_p99_us"),
        d.get("fw_version"),
        d.get("state"),
        round(latency_ms, 3),
    )
    return row, latency_ms


def percentile(values, p):
    """정렬된 리스트에서 p 백분위수"""
    n = len(values)
    index = int(-(-p / 100.0 * n // 1))  # ceil
    if index < 1:
        index = 1
    if index > n:
        index = n
    return values[index - 1]


class Collector:
    def __init__(self, broker_host, broker_port, db_dsn, dry_run):
        self.dry_run = dry_run
        self.db_dsn = db_dsn
        self.conn = None
        self.lock = threading.Lock()
        self.pending_rows = []        # 아직 DB 에 안 넣은 텔레메트리 행
        self.pending_latency = []     # 그 행들의 수집 지연(ms)
        self.pending_status = []      # (device_id, "online"/"offline", 시각)
        self.last_seen = {}           # device_id -> 마지막 메시지 시각 (monotonic)
        self.fw_of = {}               # device_id -> fw_version
        self.state_of = {}            # device_id -> state
        self.dropped_bad = 0

        self.client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, client_id="collector", protocol=mqtt.MQTTv311)
        self.client.on_connect = self.on_connect
        self.client.on_message = self.on_message
        self.client.reconnect_delay_set(min_delay=1, max_delay=5)
        self.client.connect(broker_host, broker_port, keepalive=10)

    # ---------- 브로커 콜백 ----------
    def on_connect(self, client, userdata, flags, reason_code, properties):
        if reason_code.is_failure:
            return
        client.subscribe("fleet/+/telemetry", qos=0)
        client.subscribe("fleet/+/status", qos=1)
        print("collector: connected, subscribed fleet/+/telemetry, fleet/+/status")

    def on_message(self, client, userdata, msg):
        parts = msg.topic.split("/")
        if len(parts) != 3:
            return
        device_id = parts[1]
        kind = parts[2]
        if kind == "status":
            status = msg.payload.decode("utf-8", errors="replace")
            with self.lock:
                self.pending_status.append((device_id, status, datetime.now(timezone.utc)))
            return
        if kind != "telemetry":
            return
        parsed = parse_telemetry(msg.payload, time.time_ns())
        if parsed is None:
            self.dropped_bad += 1
            return
        row, latency_ms = parsed
        with self.lock:
            self.pending_rows.append(row)
            self.pending_latency.append(latency_ms)
            self.last_seen[device_id] = time.monotonic()
            self.fw_of[device_id] = row[9]
            self.state_of[device_id] = row[10]

    # ---------- 1초마다 ----------
    def flush_once(self):
        """pending 을 통째로 가져와 DB 에 넣고 통계를 낸다. 반환: 통계 dict"""
        with self.lock:
            rows = self.pending_rows
            latencies = self.pending_latency
            statuses = self.pending_status
            self.pending_rows = []
            self.pending_latency = []
            self.pending_status = []
            online = 0
            now_mono = time.monotonic()
            for device_id in self.last_seen:
                if now_mono - self.last_seen[device_id] < 5.0:
                    online += 1
            devices_snapshot = []
            for device_id in self.last_seen:
                devices_snapshot.append((device_id, self.fw_of.get(device_id), self.state_of.get(device_id)))

        t0 = time.monotonic()
        if not self.dry_run:
            self.write_db(rows, statuses, devices_snapshot)
        insert_ms = (time.monotonic() - t0) * 1000.0

        stats = {"msgs": len(rows), "insert_ms": round(insert_ms, 1), "online": online, "bad": self.dropped_bad}
        if latencies:
            srt = sorted(latencies)
            stats["lat_p50"] = round(percentile(srt, 50), 1)
            stats["lat_p95"] = round(percentile(srt, 95), 1)
            stats["lat_max"] = round(srt[-1], 1)
        else:
            stats["lat_p50"] = stats["lat_p95"] = stats["lat_max"] = None
        if not self.dry_run:
            self.write_stats(stats)
        return stats

    # ---------- DB ----------
    def connect_db(self):
        import psycopg  # 여기서 import: --dry-run 이면 psycopg 가 없어도 돈다
        self.conn = psycopg.connect(self.db_dsn, autocommit=False)
        print("collector: db connected")

    def write_db(self, rows, statuses, devices_snapshot):
        if self.conn is None:
            self.connect_db()
        with self.conn.cursor() as cur:
            # 1) 텔레메트리: COPY 로 한 번에 (행 단위 INSERT 보다 수십 배 빠르다)
            if rows:
                columns = ", ".join(TELEMETRY_COLUMNS)
                with cur.copy(f"COPY telemetry ({columns}) FROM STDIN") as copy:
                    for row in rows:
                        copy.write_row(row)
            # 2) devices: 마지막으로 본 시각·버전·상태 갱신 (없으면 새로 만든다)
            now = datetime.now(timezone.utc)
            for device_id, fw, state in devices_snapshot:
                cur.execute(
                    "INSERT INTO devices (device_id, first_seen, last_seen, fw_version, state) "
                    "VALUES (%s, %s, %s, %s, %s) "
                    "ON CONFLICT (device_id) DO UPDATE SET last_seen = EXCLUDED.last_seen, "
                    "fw_version = EXCLUDED.fw_version, state = EXCLUDED.state",
                    (device_id, now, now, fw, state))
            # 3) 온라인/오프라인 이벤트
            for device_id, status, when in statuses:
                cur.execute("INSERT INTO events (time, device_id, kind, detail) VALUES (%s, %s, %s, %s)",
                            (when, device_id, status, json.dumps({"source": "mqtt_status"})))
        self.conn.commit()

    def write_stats(self, s):
        if self.conn is None:
            return
        with self.conn.cursor() as cur:
            cur.execute(
                "INSERT INTO collector_stats (time, msgs_per_s, batch_rows, insert_ms, lat_p50_ms, lat_p95_ms, lat_max_ms, online) "
                "VALUES (%s, %s, %s, %s, %s, %s, %s, %s)",
                (datetime.now(timezone.utc), s["msgs"], s["msgs"], s["insert_ms"], s["lat_p50"], s["lat_p95"], s["lat_max"], s["online"]))
        self.conn.commit()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--broker", default="localhost")
    ap.add_argument("--port", type=int, default=1883)
    ap.add_argument("--db", default="postgresql://fleet:fleet@localhost:5432/fleet")
    ap.add_argument("--dry-run", action="store_true", help="DB 없이 통계만 출력")
    ap.add_argument("--interval", type=float, default=1.0, help="적재 주기(초)")
    a = ap.parse_args()

    c = Collector(a.broker, a.port, a.db, a.dry_run)
    c.client.loop_start()
    print("collector: running (Ctrl+C to stop)")
    try:
        next_tick = time.monotonic() + a.interval
        while True:
            delay = next_tick - time.monotonic()
            if delay > 0:
                time.sleep(delay)
            next_tick += a.interval
            s = c.flush_once()
            print("msgs/s={msgs:>5}  online={online:>4}  insert={insert_ms:>7} ms  ingest_latency ms p50={lat_p50} p95={lat_p95} max={lat_max}  bad={bad}".format(**s))
    except KeyboardInterrupt:
        pass
    finally:
        c.client.loop_stop()
        c.client.disconnect()
    return 0


if __name__ == "__main__":
    sys.exit(main())
