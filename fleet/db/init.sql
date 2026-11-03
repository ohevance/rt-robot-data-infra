-- ---------------------------------------------------------------------------
-- 관제 DB 스키마 (TimescaleDB = PostgreSQL + 시계열 확장)
--   devices         : 장치 한 대당 한 줄. 마지막으로 본 시각, 펌웨어 버전, 상태
--   telemetry       : 장치가 보내는 주기 데이터. 하이퍼테이블(시간으로 자동 분할)
--   events          : 온라인/오프라인, 워치독, OTA 같은 "일어난 일"
--   collector_stats : 수집기가 매초 남기는 자기 통계 (초당 메시지, 적재 시간, 수집 지연)
-- 컨테이너가 처음 뜰 때 한 번 실행된다.
-- ---------------------------------------------------------------------------
CREATE EXTENSION IF NOT EXISTS timescaledb;

CREATE TABLE IF NOT EXISTS devices (
  device_id   TEXT PRIMARY KEY,
  first_seen  TIMESTAMPTZ NOT NULL,
  last_seen   TIMESTAMPTZ NOT NULL,
  fw_version  TEXT,
  state       TEXT
);

CREATE TABLE IF NOT EXISTS telemetry (
  time              TIMESTAMPTZ NOT NULL,   -- 장치가 측정한 시각
  device_id         TEXT        NOT NULL,
  seq               BIGINT,                 -- 장치별 일련번호 (빠진 번호 = 유실)
  cpu_pct           REAL,
  temp_c            REAL,
  mem_pct           REAL,
  rssi              INTEGER,                -- 무선 신호 세기 (dBm). 유선이면 NULL
  loop_hz           INTEGER,                -- 제어 루프 주기 (RT 노드일 때)
  wake_p99_us       REAL,                   -- 제어 루프 깨어남 지연 p99 (RT 노드일 때)
  fw_version        TEXT,
  state             TEXT,                   -- ok | tripped | fault ...
  ingest_latency_ms REAL                    -- 수집기 도착 시각 - 측정 시각 (같은 시계일 때만 의미)
);
SELECT create_hypertable('telemetry', 'time', if_not_exists => TRUE);
CREATE INDEX IF NOT EXISTS telemetry_device_time ON telemetry (device_id, time DESC);

CREATE TABLE IF NOT EXISTS events (
  time       TIMESTAMPTZ NOT NULL,
  device_id  TEXT,
  kind       TEXT NOT NULL,                 -- online | offline | watchdog | ota | fault ...
  detail     JSONB
);
SELECT create_hypertable('events', 'time', if_not_exists => TRUE);

CREATE TABLE IF NOT EXISTS collector_stats (
  time          TIMESTAMPTZ NOT NULL,
  msgs_per_s    INTEGER,
  batch_rows    INTEGER,
  insert_ms     REAL,
  lat_p50_ms    REAL,
  lat_p95_ms    REAL,
  lat_max_ms    REAL,
  online        INTEGER
);
SELECT create_hypertable('collector_stats', 'time', if_not_exists => TRUE);
