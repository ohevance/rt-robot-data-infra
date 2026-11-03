-- 002: OTA 배포 기록 표
-- 한 번의 단계 배포(rollout.py 실행)가 한 줄. 단계별 타임라인은 events(kind='ota') 에 줄 단위로 남고,
-- 여기에는 결과 요약(성공 여부, 닿은 장치 수, 롤백 시간)만 둔다. 표③ 의 "OTA 롤백 시간" 이 여기서 나온다.
CREATE TABLE IF NOT EXISTS ota_rollouts (
  started_at      TIMESTAMPTZ NOT NULL,
  finished_at     TIMESTAMPTZ NOT NULL,
  version         TEXT        NOT NULL,
  bad_firmware    BOOLEAN     NOT NULL,   -- 시뮬레이션: 나쁜 펌웨어였나
  stages_pct      TEXT        NOT NULL,   -- 예: "5,50,100"
  devices_total   INTEGER     NOT NULL,   -- 배포 대상 전체
  devices_updated INTEGER     NOT NULL,   -- 새 버전이 실제로 닿은 장치 수 (롤백이면 canary 범위)
  success         BOOLEAN     NOT NULL,
  rollback_s      REAL,                   -- 롤백 결정 → 전원 복구까지 초. 롤백이 없었으면 NULL
  timeline        JSONB                   -- [{"t_s":..,"event":".."}, ...]
);
