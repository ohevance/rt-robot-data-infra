-- 003: 수집기 내성(D4) 통계 컬럼
--   backlog_rows : DB 가 끊긴 동안 수집기가 메모리에 들고 있는 행 수 (0 이면 정상)
--   db_errors    : 지금까지 DB 쓰기 실패 횟수 (누적)
-- 장애 주입(fleet/chaos/inject.py --fault db) 때 "복구 = backlog_rows 가 다시 0" 으로 판정한다.
ALTER TABLE collector_stats ADD COLUMN IF NOT EXISTS backlog_rows INTEGER;
ALTER TABLE collector_stats ADD COLUMN IF NOT EXISTS db_errors   INTEGER;
