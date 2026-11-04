#!/usr/bin/env python3
"""수집기 — MQTT 로 들어오는 텔레메트리를 1초마다 묶어 TimescaleDB 에 넣고, 자기 통계를 남긴다.

흐름
  브로커 ──(paho 콜백 스레드: on_message → 파싱 → pending 리스트)──▶ 메인 스레드(1초마다): 묶어서 COPY 적재
                                                                     + devices 갱신 + 통계 한 줄 출력/저장

왜 1초 묶음(batch)인가
  행 하나씩 INSERT 하면 장치 300대 × 1 Hz 에서 DB 왕복 300번/초. 묶어서 COPY 하면 1번/초.
  대신 DB 에 보이기까지 최대 1초가 더해진다. 여기서 재는 "전달 지연(ingest_latency_ms)"은 수집기 "도착" 기준이라
  이 1초가 들어 있지 않다 → 표③에 그렇게 적는다.

DB 가 죽어도 데이터를 잃지 않는다 (D4, 장애 주입 --fault db)
  1초 묶음을 바로 못 넣으면 backlog(메모리)에 쌓아 두고 매초 다시 시도한다. DB 가 돌아오면 오래된 것부터 모두 넣는다.
  상한 MAX_BACKLOG_ROWS 를 넘으면 가장 오래된 묶음을 버리고 센다(backlog_dropped). 통계에 backlog_rows, db_errors 로 보인다.

종료 신호(SIGTERM·Ctrl+C)를 받으면 "곱게" 끝난다 (D5 실측에서 고침)
  먼저 브로커 수신을 멈추고(지속 세션이면 그 뒤 메시지는 브로커가 보관), 아직 DB 에 안 넣은 pending·backlog 를 마지막으로 적재한 뒤 끝낸다.
  왜: 11/04 실측에서 SIGTERM 즉시 종료 → 그 1초 동안 받아 둔 행(장치당 1개, 50개)이 사라졌다. QoS 1 의 확인(PUBACK)은 paho 가
  받는 즉시 보내므로 "받았다 ≠저장했다" — 종료 때만이라도 그 틈을 메운다. (완전한 해법은 DB 적재 뒤 수동 ACK: 2주 계획 밖)

수집기가 죽어도 데이터를 잃지 않으려면 (장애 주입 --fault collector)
  --qos 1 로 띄우면 "지속 세션"(clean_session=False, 고정 client_id)으로 구독한다. 수집기가 없는 동안 브로커가
  QoS 1 메시지를 대신 들고 있다가 다시 붙으면 넘겨 준다. 단, 장치도 QoS 1 로 보내야 한다 (virtual_fleet --telemetry-qos 1).
  QoS 0(기본)이면 수집기가 죽은 동안의 메시지는 유실된다 — 그 차이를 표③에 숫자로 남긴다.

읽는 순서: parse_telemetry → Collector.on_message → Collector.flush_once → drain_backlog → write_db → main → shutdown
사용:
  python3 fleet/collector/collector.py                # localhost 브로커·DB, QoS 0
  python3 fleet/collector/collector.py --qos 1        # 지속 세션 (수집기 끊김 시 유실 0)
  python3 fleet/collector/collector.py --dry-run      # DB 없이 통계만 출력 (브로커는 필요)
"""
import argparse
import json
import signal
import sys
import threading
import time
from datetime import datetime, timezone

import paho.mqtt.client as mqtt

TELEMETRY_COLUMNS = ("time", "device_id", "seq", "cpu_pct", "temp_c", "mem_pct", "rssi",
                     "loop_hz", "wake_p99_us", "fw_version", "state", "ingest_latency_ms")

MAX_BACKLOG_ROWS = 200000   # DB 가 죽은 동안 들고 있을 최대 행 수 (50대 1 Hz 면 약 66분, 300대면 약 11분)


def parse_telemetry(payload_bytes, arrival_ns):
    """JSON 바이트 → (행 튜플, 전달 지연 ms). 깨진 메시지면 None."""
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


def percentile(sorted_values, p):
    """정렬된 리스트에서 p 백분위수 (가장 가까운 순위 방식)"""
    n = len(sorted_values)
    index = int(-(-p / 100.0 * n // 1))  # ceil
    if index < 1:
        index = 1
    if index > n:
        index = n
    return sorted_values[index - 1]


class Batch:
    """1초 동안 모인 것 한 덩어리. DB 에 못 넣으면 이 단위로 backlog 에 남는다."""

    def __init__(self, rows, statuses, devices_snapshot, snapshot_time):
        self.rows = rows                        # 텔레메트리 행
        self.statuses = statuses                # (device_id, "online"/"offline", 시각)
        self.devices_snapshot = devices_snapshot  # (device_id, fw, state)
        self.snapshot_time = snapshot_time      # devices.last_seen 에 쓸 시각


class Collector:
    def __init__(self, broker_host, broker_port, db_dsn, dry_run, qos=0):
        self.dry_run = dry_run
        self.db_dsn = db_dsn
        self.qos = qos
        self.conn = None
        self.lock = threading.Lock()
        self.pending_rows = []        # 아직 묶지 않은 텔레메트리 행
        self.pending_latency = []     # 그 행들의 전달 지연(ms)
        self.pending_status = []      # (device_id, "online"/"offline", 시각)
        self.last_seen = {}           # device_id -> 마지막 메시지 시각 (monotonic)
        self.fw_of = {}               # device_id -> fw_version
        self.state_of = {}            # device_id -> state
        self.dropped_bad = 0
        self.backlog = []             # DB 에 못 넣은 Batch 들 (오래된 것이 앞)
        self.backlog_rows = 0
        self.backlog_dropped = 0      # 상한을 넘어 버린 행 수
        self.db_errors = 0            # DB 쓰기 실패 누적

        # qos 1 이면 지속 세션: 브로커가 이 client_id 의 구독과 밀린 QoS 1 메시지를 기억한다
        clean_session = True
        if qos >= 1:
            clean_session = False
        self.client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, client_id="collector",
                                  clean_session=clean_session, protocol=mqtt.MQTTv311)
        self.client.on_connect = self.on_connect
        self.client.on_message = self.on_message
        self.client.reconnect_delay_set(min_delay=1, max_delay=5)
        self.client.connect(broker_host, broker_port, keepalive=10)

    # ---------- 브로커 콜백 ----------
    def on_connect(self, client, userdata, flags, reason_code, properties):
        if reason_code.is_failure:
            return
        client.subscribe("fleet/+/telemetry", qos=self.qos)
        client.subscribe("fleet/+/status", qos=1)
        print(f"collector: connected, subscribed fleet/+/telemetry (qos {self.qos}), fleet/+/status")

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
    def take_batch(self):
        """pending 을 통째로 꺼내 Batch 하나로 만든다. 반환: (Batch, 지연 리스트, 온라인 수)"""
        with self.lock:
            rows = self.pending_rows
            latencies = self.pending_latency
            statuses = self.pending_status
            self.pending_rows = []
            self.pending_latency = []
            self.pending_status = []
            online = 0
            now_mono = time.monotonic()
            devices_snapshot = []
            for device_id in self.last_seen:
                if now_mono - self.last_seen[device_id] < 5.0:
                    online += 1
                devices_snapshot.append((device_id, self.fw_of.get(device_id), self.state_of.get(device_id)))
        batch = Batch(rows, statuses, devices_snapshot, datetime.now(timezone.utc))
        return batch, latencies, online

    def flush_once(self):
        """1초마다: 묶음을 만들고 DB 에 넣고(안 되면 backlog) 통계를 낸다. 반환: 통계 dict"""
        batch, latencies, online = self.take_batch()

        t0 = time.monotonic()
        if not self.dry_run:
            self.backlog.append(batch)
            self.backlog_rows += len(batch.rows)
            self.enforce_backlog_limit()
            self.drain_backlog()
        insert_ms = (time.monotonic() - t0) * 1000.0

        stats = {"msgs": len(batch.rows), "insert_ms": round(insert_ms, 1), "online": online, "bad": self.dropped_bad,
                 "backlog_rows": self.backlog_rows, "db_errors": self.db_errors}
        if len(latencies) > 0:
            srt = sorted(latencies)
            stats["lat_p50"] = round(percentile(srt, 50), 1)
            stats["lat_p95"] = round(percentile(srt, 95), 1)
            stats["lat_max"] = round(srt[-1], 1)
        else:
            stats["lat_p50"] = None
            stats["lat_p95"] = None
            stats["lat_max"] = None
        if not self.dry_run and self.conn is not None:
            self.write_stats(stats)
        return stats

    def enforce_backlog_limit(self):
        """상한을 넘으면 가장 오래된 묶음부터 버린다 (메모리 보호). 버린 행 수를 센다."""
        while self.backlog_rows > MAX_BACKLOG_ROWS and len(self.backlog) > 1:
            oldest = self.backlog.pop(0)
            self.backlog_rows -= len(oldest.rows)
            self.backlog_dropped += len(oldest.rows)

    def drain_backlog(self):
        """backlog 를 오래된 것부터 DB 에 넣는다. 하나라도 실패하면 거기서 멈추고 다음 초에 다시 시도."""
        while len(self.backlog) > 0:
            batch = self.backlog[0]
            try:
                self.write_db(batch)
            except Exception as e:
                self.db_errors += 1
                self.drop_db_connection()
                if self.db_errors == 1 or self.db_errors % 10 == 0:
                    print(f"collector: DB write failed ({e.__class__.__name__}), backlog {self.backlog_rows} rows, retry next second")
                return
            self.backlog.pop(0)
            self.backlog_rows -= len(batch.rows)

    # ---------- DB ----------
    def connect_db(self):
        import psycopg  # 여기서 import: --dry-run 이면 psycopg 가 없어도 돈다
        self.conn = psycopg.connect(self.db_dsn, autocommit=False, connect_timeout=3)
        print("collector: db connected")

    def drop_db_connection(self):
        if self.conn is not None:
            try:
                self.conn.close()
            except Exception:
                pass
        self.conn = None

    def check_schema(self):
        """시작할 때 한 번: 003 마이그레이션(backlog_rows 컬럼)이 적용돼 있는지. 없으면 안내하고 종료."""
        if self.conn is None:
            self.connect_db()
        try:
            with self.conn.cursor() as cur:
                cur.execute("SELECT backlog_rows, db_errors FROM collector_stats LIMIT 0")
            self.conn.rollback()
        except Exception:
            self.conn.rollback()
            print("collector: DB 스키마가 옛 버전입니다. 먼저 실행:  python3 fleet/db/migrate.py")
            return False
        return True

    def write_db(self, batch):
        if self.conn is None:
            self.connect_db()
        with self.conn.cursor() as cur:
            # 1) 텔레메트리: COPY 로 한 번에 (행 단위 INSERT 보다 수십 배 빠르다)
            if len(batch.rows) > 0:
                columns = ", ".join(TELEMETRY_COLUMNS)
                with cur.copy(f"COPY telemetry ({columns}) FROM STDIN") as copy:
                    for row in batch.rows:
                        copy.write_row(row)
            # 2) devices: 마지막으로 본 시각·버전·상태 갱신 (없으면 새로 만든다)
            for device_id, fw, state in batch.devices_snapshot:
                cur.execute(
                    "INSERT INTO devices (device_id, first_seen, last_seen, fw_version, state) "
                    "VALUES (%s, %s, %s, %s, %s) "
                    "ON CONFLICT (device_id) DO UPDATE SET last_seen = EXCLUDED.last_seen, "
                    "fw_version = EXCLUDED.fw_version, state = EXCLUDED.state",
                    (device_id, batch.snapshot_time, batch.snapshot_time, fw, state))
            # 3) 온라인/오프라인 이벤트
            for device_id, status, when in batch.statuses:
                cur.execute("INSERT INTO events (time, device_id, kind, detail) VALUES (%s, %s, %s, %s)",
                            (when, device_id, status, json.dumps({"source": "mqtt_status"})))
        self.conn.commit()

    def write_stats(self, s):
        try:
            with self.conn.cursor() as cur:
                cur.execute(
                    "INSERT INTO collector_stats (time, msgs_per_s, batch_rows, insert_ms, lat_p50_ms, lat_p95_ms, lat_max_ms, "
                    "online, backlog_rows, db_errors) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)",
                    (datetime.now(timezone.utc), s["msgs"], s["msgs"], s["insert_ms"], s["lat_p50"], s["lat_p95"],
                     s["lat_max"], s["online"], s["backlog_rows"], s["db_errors"]))
            self.conn.commit()
        except Exception:
            self.db_errors += 1
            self.drop_db_connection()


STOP = {"requested": False}   # 종료 신호를 받으면 True (시그널 핸들러는 이 플래그만 세운다)


def request_stop(signum, frame):
    STOP["requested"] = True


def shutdown(c):
    """곱게 끝내기: 수신 중단 → 남은 pending·backlog 마지막 적재 → 결과 출력"""
    c.client.loop_stop()
    c.client.disconnect()
    if c.dry_run:
        return
    last = c.flush_once()
    if c.backlog_rows > 0:
        print(f"collector: 종료 시 DB 에 못 넣은 행 {c.backlog_rows}개 (버린 행 {c.backlog_dropped}개) — DB 가 죽어 있음")
    else:
        print(f"collector: 종료 — 마지막 {last['msgs']}행까지 적재 완료, 남은 backlog 0")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--broker", default="localhost")
    ap.add_argument("--port", type=int, default=1883)
    ap.add_argument("--db", default="postgresql://fleet:fleet@localhost:5432/fleet")
    ap.add_argument("--dry-run", action="store_true", help="DB 없이 통계만 출력")
    ap.add_argument("--interval", type=float, default=1.0, help="적재 주기(초)")
    ap.add_argument("--qos", type=int, default=0, choices=[0, 1], help="텔레메트리 구독 QoS. 1 = 지속 세션(수집기 끊김 시 유실 0)")
    a = ap.parse_args()

    c = Collector(a.broker, a.port, a.db, a.dry_run, qos=a.qos)
    if not a.dry_run:
        try:
            if not c.check_schema():
                return 2
        except Exception as e:
            print(f"collector: DB 에 아직 못 붙음 ({e.__class__.__name__}) — 돌면서 매초 다시 시도합니다")
            c.drop_db_connection()
    signal.signal(signal.SIGTERM, request_stop)   # kill / 장애 주입 → 플래그만 세우고, 루프가 끝나면 shutdown 이 마지막 적재
    signal.signal(signal.SIGINT, request_stop)    # Ctrl+C 도 같은 길
    c.client.loop_start()
    print("collector: running (Ctrl+C to stop)")
    next_tick = time.monotonic() + a.interval
    while not STOP["requested"]:
        delay = next_tick - time.monotonic()
        if delay > 0:
            time.sleep(min(delay, 0.2))   # 0.2초씩 자야 종료 신호에 바로 깬다
            continue
        next_tick += a.interval
        s = c.flush_once()
        print("msgs/s={msgs:>5}  online={online:>4}  insert={insert_ms:>7} ms  transit ms p50={lat_p50} p95={lat_p95} max={lat_max}"
              "  bad={bad}  backlog={backlog_rows}  db_err={db_errors}".format(**s), flush=True)
    shutdown(c)
    return 0


if __name__ == "__main__":
    sys.exit(main())
