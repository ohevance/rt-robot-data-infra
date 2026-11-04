#!/usr/bin/env python3
"""Grafana 대시보드 JSON 생성기 — 손으로 300줄 JSON 을 고치는 대신 여기서 만든다.

실행:  python3 fleet/grafana/make_dashboard.py   → provisioning/dashboards/fleet_overview.json
패널 14개 (위 → 아래):
  1~6) 숫자 타일: 온라인 장치 · 초당 메시지 · 전달 지연 p95 · 적재 시간 · 오프라인 이벤트 · 멈춤/고장 장치
  7~8) 초당 메시지/온라인 · 전달 지연 p50/p95/max
  9~10) 장치별 온도 · RT 노드 깨어남 지연 p99
  12~13) 수집기 backlog(DB 끊김 때 올라감) · 펌웨어 버전 분포(OTA 단계 배포가 번져 가는 모습)
  14) 최근 이벤트(fault·ota·offline)   11) 장치 표
"""
import json
import os

DS = {"type": "grafana-postgresql-datasource", "uid": "timescale"}


def sql_target(sql, fmt="time_series"):
    return {"datasource": DS, "rawSql": sql, "format": fmt, "rawQuery": True, "refId": "A"}


def stat_panel(pid, title, sql, x, y, w, h, unit="none"):
    return {
        "id": pid, "type": "stat", "title": title, "datasource": DS,
        "gridPos": {"x": x, "y": y, "w": w, "h": h},
        "targets": [sql_target(sql, "table")],
        "fieldConfig": {"defaults": {"unit": unit}, "overrides": []},
        "options": {"reduceOptions": {"calcs": ["lastNotNull"]}, "colorMode": "value", "graphMode": "none"},
    }


def ts_panel(pid, title, sql, x, y, w, h, unit="none"):
    return {
        "id": pid, "type": "timeseries", "title": title, "datasource": DS,
        "gridPos": {"x": x, "y": y, "w": w, "h": h},
        "targets": [sql_target(sql, "time_series")],
        "fieldConfig": {"defaults": {"unit": unit, "custom": {"lineWidth": 1, "fillOpacity": 10}}, "overrides": []},
        "options": {"legend": {"displayMode": "list", "placement": "bottom"}},
    }


def table_panel(pid, title, sql, x, y, w, h):
    return {
        "id": pid, "type": "table", "title": title, "datasource": DS,
        "gridPos": {"x": x, "y": y, "w": w, "h": h},
        "targets": [sql_target(sql, "table")],
        "fieldConfig": {"defaults": {}, "overrides": []},
        "options": {},
    }


def build():
    panels = [
        stat_panel(1, "온라인 장치 (최근 5초)",
                   "SELECT count(*) AS online FROM devices WHERE last_seen > now() - interval '5 seconds'",
                   0, 0, 4, 4),
        stat_panel(2, "초당 메시지 (최근 1초)",
                   "SELECT msgs_per_s FROM collector_stats ORDER BY time DESC LIMIT 1",
                   4, 0, 4, 4),
        stat_panel(3, "전달 지연 p95 (ms, 장치→수집기)",
                   "SELECT lat_p95_ms FROM collector_stats ORDER BY time DESC LIMIT 1",
                   8, 0, 4, 4, unit="ms"),
        stat_panel(4, "DB 적재 시간 (ms, 최근 1초)",
                   "SELECT insert_ms FROM collector_stats ORDER BY time DESC LIMIT 1",
                   12, 0, 4, 4, unit="ms"),
        stat_panel(5, "오프라인 이벤트 (최근 10분, 브로커 종료 유언 포함)",
                   "SELECT count(*) AS offline FROM events WHERE kind = 'offline' AND time > now() - interval '10 minutes'",
                   16, 0, 4, 4),
        stat_panel(6, "멈춤·고장 장치 (tripped/fault/updating)",
                   "SELECT count(*) AS bad FROM devices WHERE state IN ('tripped', 'fault', 'updating', 'recovering') "
                   "AND last_seen > now() - interval '5 seconds'",
                   20, 0, 4, 4),
        ts_panel(7, "초당 메시지 / 온라인 장치",
                 "SELECT time, msgs_per_s AS \"msgs/s\", online FROM collector_stats WHERE $__timeFilter(time) ORDER BY time",
                 0, 4, 12, 8),
        ts_panel(8, "전달 지연 (ms): p50 / p95 / max — 장치 측정 → 수집기 도착",
                 "SELECT time, lat_p50_ms AS p50, lat_p95_ms AS p95, lat_max_ms AS max FROM collector_stats WHERE $__timeFilter(time) ORDER BY time",
                 12, 4, 12, 8, unit="ms"),
        ts_panel(9, "장치별 온도 (앞 8대)",
                 "SELECT time, device_id AS metric, temp_c FROM telemetry WHERE $__timeFilter(time) "
                 "AND device_id IN (SELECT device_id FROM devices ORDER BY device_id LIMIT 8) ORDER BY time",
                 0, 12, 12, 8, unit="celsius"),
        ts_panel(10, "RT 노드: 깨어남 지연 p99 (us)",
                 "SELECT time, device_id AS metric, wake_p99_us FROM telemetry WHERE $__timeFilter(time) "
                 "AND wake_p99_us IS NOT NULL ORDER BY time",
                 12, 12, 12, 8, unit="µs"),
        ts_panel(12, "수집기 backlog (DB 에 못 넣고 들고 있는 행) / DB 오류 누적",
                 "SELECT time, backlog_rows AS backlog, db_errors FROM collector_stats WHERE $__timeFilter(time) ORDER BY time",
                 0, 20, 12, 7),
        ts_panel(13, "펌웨어 버전별 장치 수 (OTA 단계 배포)",
                 "SELECT time_bucket('5 seconds', time) AS time, fw_version AS metric, count(DISTINCT device_id) "
                 "FROM telemetry WHERE $__timeFilter(time) GROUP BY 1, 2 ORDER BY 1",
                 12, 20, 12, 7),
        table_panel(14, "최근 이벤트 (장애 주입 · OTA · 온/오프라인)",
                    "SELECT time, kind, device_id, detail::text AS detail FROM events "
                    "WHERE $__timeFilter(time) ORDER BY time DESC LIMIT 50",
                    0, 27, 24, 8),
        table_panel(11, "장치 목록",
                    "SELECT device_id, state, fw_version, last_seen, "
                    "round(extract(epoch FROM (now() - last_seen))::numeric, 1) AS age_s "
                    "FROM devices ORDER BY device_id",
                    0, 35, 24, 10),
    ]
    dashboard = {
        "uid": "fleet-overview",
        "title": "Fleet Overview — rt-robot-data-infra",
        "tags": ["fleet", "rt-robot-data-infra"],
        "timezone": "browser",
        "schemaVersion": 39,
        "version": 1,
        "refresh": "2s",
        "time": {"from": "now-5m", "to": "now"},
        "panels": panels,
        "templating": {"list": []},
        "annotations": {"list": []},
    }
    return dashboard


def main():
    here = os.path.dirname(os.path.abspath(__file__))
    out = os.path.join(here, "provisioning", "dashboards", "fleet_overview.json")
    with open(out, "w", encoding="utf-8") as f:
        json.dump(build(), f, ensure_ascii=False, indent=2)
    print(f"wrote {out}")


if __name__ == "__main__":
    main()
