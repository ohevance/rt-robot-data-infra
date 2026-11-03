-- ---------------------------------------------------------------------------
-- 관제 DB 스키마 (TimescaleDB = PostgreSQL + 시계열 확장)
--   devices         : 장치 한 대당 한 줄. 마지막으로 본 시각, 펌웨어 버전, 상태
--   telemetry       : 장치가 보내는 주기 데이터. 하이퍼테이블(시간으로 자동 분할)
--   events          : 온라인/오프라인, 워치독, OTA 같은 "일어난 일"
--   collector_stats : 수집기가 매초 남기는 자기 통계 (초당 메시지, 적재 시간, 전달 지연, DB 밀린 행)
--   ota_rollouts    : OTA 단계 배포 한 번의 결과 요약
-- 컨테이너가 처음 뜰 때 한 번 실행된다. 이미 떠 있는 DB 에 바뀐 부분만 넣을 때는 migrations/ + migrate.py 를 쓴다.
-- (migrations/002, 003 의 내용은 아래에도 들어 있다 → 새 DB 는 이 파일 하나로 완성, 기존 DB 는 migrate.py 로 추가)
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
  ingest_latency_ms REAL                    -- 전달 지연: 수집기 "도착" 시각 - 장치 측정 시각 (같은 시계일 때만 의미).
                                            --   DB 에 보이기까지는 1초 묶음 적재가 최대 1초 더 걸린다. 컬럼 이름은 호환을 위해 유지
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
  online        INTEGER,
  backlog_rows  INTEGER,                    -- (003) DB 끊긴 동안 수집기가 들고 있는 행 수. 0 이면 정상
  db_errors     INTEGER                     -- (003) DB 쓰기 실패 누적 횟수
);
SELECT create_hypertable('collector_stats', 'time', if_not_exists => TRUE);

-- (002) OTA 단계 배포 결과. 자세한 설명은 migrations/002_ota.sql
CREATE TABLE IF NOT EXISTS ota_rollouts (
  started_at      TIMESTAMPTZ NOT NULL,
  finished_at     TIMESTAMPTZ NOT NULL,
  version         TEXT        NOT NULL,
  bad_firmware    BOOLEAN     NOT NULL,
  stages_pct      TEXT        NOT NULL,
  devices_total   INTEGER     NOT NULL,
  devices_updated INTEGER     NOT NULL,
  success         BOOLEAN     NOT NULL,
  rollback_s      REAL,
  timeline        JSONB
);
