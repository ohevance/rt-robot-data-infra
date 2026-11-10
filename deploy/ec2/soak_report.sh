#!/usr/bin/env bash
# ---------------------------------------------------------------------------
# 연속 운영(soak) 보고 — 서버의 DB 에서 장치 한 대의 기록을 세어 JSON 으로 낸다. "밤새 끊김이 없었나"를 그래프가 아니라 숫자로.
#
#   무엇을 세나 (장치가 메시지마다 붙이는 일련번호 seq 로)
#     expected / received / lost : 보냈어야 할 수 / 받은 수 / 빠진 수.  에이전트가 재시작하면 seq 가 0 부터 다시 시작하므로
#                                   "구간(run)"마다 따로 세어 더한다.
#     agent_restarts, restarts[] : 재시작 횟수와 그때의 공백(마지막 수신 → 다시 수신). 재부팅·서비스 재시작이 여기 보인다.
#     max_gap_device_time_s      : 한 구간 안에서 이웃한 두 기록의 "장치 측정 시각" 간격의 최대. 1 Hz 면 1초 안팎이어야 한다.
#     max_gap_arrival_s          : 한 구간 안에서 서버가 아무것도 못 받은 가장 긴 시간. 연결이 끊겼다 이어지면(장치가 버퍼에 모았다 재전송)
#                                   여기는 길고 lost 는 0 이다 — "끊겼지만 잃지 않았다"가 숫자 둘로 보인다.
#     transit_ms                 : 전달 지연 표시값(도착 − 장치 측정). **두 시계의 차이가 섞여 있어 지연으로 인용하지 않는다**
#                                   (왕복 시간은 fleet/tools/mqtt_rtt.py). 시간대별 p50 의 최소·최대를 같이 내어 시계 차이의 흔들림을 본다.
#     events                     : online/offline 이벤트 수.   collector : 수집기의 최대 backlog·DB 오류.
#   왜 도착 순서로 줄을 세우나: 장치 시계는 재부팅 직후(NTP 동기 전)에 뒤로 갈 수 있다. 측정 시각 순서로 세우면 재시작 앞뒤 기록이
#     섞여 구간을 잘못 나눈다. 도착 시각(= 측정 시각 + 전달 지연, 서버 시계)은 뒤로 가지 않는다.
#   한계: 재시작 직전에 만들었지만 보내지 못한 마지막 메시지는 서버가 알 길이 없다(구간의 끝은 "받은 마지막 번호"다).
#
# 사용 (관제 서버 안에서):
#   bash deploy/ec2/soak_report.sh                      # pi-rt, 전체 기간 → ~/soak_pi-rt_<UTC시각>.json 에 저장하고 화면에 출력
#   bash deploy/ec2/soak_report.sh pi-rt
#   SINCE='2026-11-10 18:37:00+09' UNTIL='2026-11-11 18:37:00+09' bash deploy/ec2/soak_report.sh pi-rt
#   SERVER_LABEL='서울 (AWS ap-northeast-2)' …          # 서버 위치 표기 (기본: 시드니)
# 결과 파일을 저장소로: [WSL 창] scp -i <키> ubuntu@<서버>:~/soak_pi-rt_*.json docs/measurements/   (비밀값 없음 — 주소·계정이 들어가지 않는다)
# ---------------------------------------------------------------------------
set -euo pipefail
DEV="${1:-pi-rt}"
SINCE="${SINCE:-1970-01-01}"
UNTIL="${UNTIL:-now}"
SERVER_LABEL="${SERVER_LABEL:-시드니 (AWS ap-southeast-2)}"
OUT="${OUT:-$HOME/soak_${DEV}_$(date -u +%Y%m%dT%H%MZ).json}"
PSQL="${PSQL:-sudo docker exec -i fleet_db psql -U fleet -d fleet}"

$PSQL -tA -v ON_ERROR_STOP=1 -v dev="$DEV" -v since="$SINCE" -v until="$UNTIL" -v server="$SERVER_LABEL" <<'SQL' | python3 -m json.tool --no-ensure-ascii > "$OUT"
WITH base AS (
  SELECT time AS dev_time,
         time + make_interval(secs => coalesce(ingest_latency_ms, 0) / 1000.0) AS arr_time,
         seq, ingest_latency_ms
  FROM telemetry
  WHERE device_id = :'dev' AND seq IS NOT NULL
    AND time >= :'since'::timestamptz AND time <= :'until'::timestamptz
),
ordered AS (
  SELECT *, lag(seq) OVER w AS prev_seq, lag(dev_time) OVER w AS prev_dev, lag(arr_time) OVER w AS prev_arr
  FROM base WINDOW w AS (ORDER BY arr_time, seq)
),
marked AS (
  -- 재시작 = 번호가 줄었고 0 근처로 돌아갔다. (QoS 1 재전송으로 이웃한 두 개의 도착 순서가 바뀐 것은 재시작이 아니다)
  SELECT *, (prev_seq IS NOT NULL AND seq < prev_seq AND seq < 5) AS is_restart FROM ordered
),
runs AS (
  SELECT *, sum(is_restart::int) OVER (ORDER BY arr_time, seq) AS run_id FROM marked
),
per_run AS (
  SELECT run_id, min(arr_time) AS first_arr, max(arr_time) AS last_arr,
         max(seq) - (CASE WHEN run_id = 0 THEN min(seq) ELSE 0 END) + 1 AS expected,   -- 재시작한 구간은 0 번부터 세어야 한다
         count(DISTINCT seq) AS received, count(*) AS n_rows
  FROM runs GROUP BY run_id
),
restarts AS (
  SELECT prev_arr AS down_from, arr_time AS up_at, extract(epoch FROM arr_time - prev_arr) AS gap_s FROM runs WHERE is_restart
),
in_run AS (
  SELECT max(extract(epoch FROM dev_time - prev_dev)) AS max_gap_dev, max(extract(epoch FROM arr_time - prev_arr)) AS max_gap_arr
  FROM runs WHERE prev_seq IS NOT NULL AND NOT is_restart
),
lat AS (
  SELECT percentile_cont(0.5) WITHIN GROUP (ORDER BY ingest_latency_ms) AS p50,
         percentile_cont(0.95) WITHIN GROUP (ORDER BY ingest_latency_ms) AS p95,
         max(ingest_latency_ms) AS max
  FROM base
),
hourly AS (
  SELECT date_trunc('hour', dev_time) AS h, percentile_cont(0.5) WITHIN GROUP (ORDER BY ingest_latency_ms) AS p50
  FROM base GROUP BY 1 HAVING count(*) >= 600
),
span AS (SELECT min(arr_time) AS t0, max(arr_time) AS t1, count(*) AS n FROM base),
ev AS (
  SELECT kind, count(*) AS n FROM events, span
  WHERE device_id = :'dev' AND time >= span.t0 - interval '10 seconds' AND time <= span.t1 + interval '10 seconds' GROUP BY kind
),
cs AS (
  SELECT max(backlog_rows) AS max_backlog, max(db_errors) AS max_db_errors FROM collector_stats, span
  WHERE time >= span.t0 AND time <= span.t1
)
SELECT json_build_object(
  'what', 'soak: 장치 한 대의 연속 보고 기록을 서버 DB 에서 센 것 (deploy/ec2/soak_report.sh)',
  'server', :'server',
  'device_id', :'dev',
  'first_kst', (SELECT to_char(t0 AT TIME ZONE 'Asia/Seoul', 'YYYY-MM-DD HH24:MI:SS') FROM span),
  'last_kst',  (SELECT to_char(t1 AT TIME ZONE 'Asia/Seoul', 'YYYY-MM-DD HH24:MI:SS') FROM span),
  'hours',     (SELECT round((extract(epoch FROM t1 - t0) / 3600.0)::numeric, 2) FROM span),
  'expected',  (SELECT coalesce(sum(expected), 0) FROM per_run),
  'received',  (SELECT coalesce(sum(received), 0) FROM per_run),
  'lost',      (SELECT coalesce(sum(expected) - sum(received), 0) FROM per_run),
  'duplicates', (SELECT coalesce(sum(n_rows - received), 0) FROM per_run),
  'agent_restarts', (SELECT count(*) FROM restarts),
  'restarts', (SELECT coalesce(json_agg(json_build_object(
                   'last_before_kst', to_char(down_from AT TIME ZONE 'Asia/Seoul', 'MM-DD HH24:MI:SS'),
                   'first_after_kst', to_char(up_at AT TIME ZONE 'Asia/Seoul', 'MM-DD HH24:MI:SS'),
                   'gap_s', round(gap_s::numeric, 1)) ORDER BY up_at), '[]'::json) FROM restarts),
  'max_gap_device_time_s', (SELECT round(max_gap_dev::numeric, 2) FROM in_run),
  'max_gap_arrival_s',     (SELECT round(max_gap_arr::numeric, 2) FROM in_run),
  'transit_ms', (SELECT json_build_object(
                   'p50', round(p50::numeric, 1), 'p95', round(p95::numeric, 1), 'max', round(max::numeric, 1),
                   'hourly_p50_min', (SELECT round(min(p50)::numeric, 1) FROM hourly),
                   'hourly_p50_max', (SELECT round(max(p50)::numeric, 1) FROM hourly),
                   'note', '도착 시각 − 장치 측정 시각. 두 시계의 차이가 섞여 있다 — 지연으로 인용하지 않는다') FROM lat),
  'events', (SELECT coalesce(json_object_agg(kind, n), '{}'::json) FROM ev),
  'collector', (SELECT json_build_object('max_backlog_rows', max_backlog, 'max_db_errors', max_db_errors) FROM cs),
  'measured_at_utc', to_char(now() AT TIME ZONE 'UTC', 'YYYY-MM-DD"T"HH24:MI:SS"Z"')
);
SQL
cat "$OUT"
echo "saved: $OUT" >&2
