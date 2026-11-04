#!/usr/bin/env python3
"""표③ 생성기 — 관제 DB(collector_stats, telemetry) 에서 최근 N 분의 처리량·전달 지연·유실을 뽑고,
장애 주입 결과(docs/measurements/fault_*.json)와 OTA 배포 결과(ota_*.json)를 합쳐 마크다운 표로.

사용:  python3 scripts/make_table3.py --minutes 5 --label "가상 50대 1 Hz" --out docs/measurements/table3.md
       python3 scripts/make_table3.py --no-db --out docs/measurements/table3.md     # DB 없이 JSON 부분만
"""
import argparse
import glob
import json
import os
import sys


def f(x, nd=1):
    if x is None:
        return "-"
    return f"{float(x):.{nd}f}"


def sec(x):
    """초 단위 값. None 이면 단위 없이 '-'"""
    if x is None:
        return "-"
    return f"{float(x):.1f}초"


FAULT_ORDER = {"broker": 0, "db": 1, "collector": 2, "bad_firmware": 3}


def fault_sort_key(r):
    return (FAULT_ORDER.get(r.get("fault"), 9), r.get("label") or "")


def section_throughput(dsn, minutes, label):
    """표③-1: 처리량·전달 지연·유실 (DB)"""
    import psycopg
    conn = psycopg.connect(dsn)
    cur = conn.cursor()
    window = f"now() - interval '{minutes} minutes'"

    cur.execute(f"""
        SELECT count(*), avg(msgs_per_s), max(msgs_per_s), max(online),
               avg(insert_ms), max(insert_ms),
               percentile_cont(0.5) WITHIN GROUP (ORDER BY lat_p50_ms),
               percentile_cont(0.5) WITHIN GROUP (ORDER BY lat_p95_ms),
               max(lat_max_ms)
        FROM collector_stats WHERE time > {window} AND msgs_per_s > 0""")
    seconds, msgs_avg, msgs_max, online_max, ins_avg, ins_max, lat_p50, lat_p95, lat_max = cur.fetchone()

    cur.execute(f"""
        SELECT count(*) AS devices, sum(received) AS received, sum(expected) AS expected
        FROM (SELECT device_id, count(*) AS received, max(seq) - min(seq) + 1 AS expected
              FROM telemetry WHERE time > {window} GROUP BY device_id) t""")
    devices, received, expected = cur.fetchone()
    # sum() 결과는 Decimal 로 온다 → float 로 바꿔 계산 (float * Decimal 은 TypeError)
    loss_pct = 0.0
    if expected:
        loss_pct = 100.0 * (float(expected) - float(received)) / float(expected)

    cur.execute(f"SELECT kind, count(*) FROM events WHERE time > {window} GROUP BY kind ORDER BY kind")
    events = cur.fetchall()
    conn.close()

    lines = [f"### 표③-1 관제 처리량·전달 지연 — {label} (최근 {minutes}분)", ""]
    lines.append("| 항목 | 값 |")
    lines.append("|---|---:|")
    lines.append(f"| 측정 구간(초) | {seconds or 0} |")
    lines.append(f"| 온라인 장치(최대) | {online_max or 0} |")
    lines.append(f"| 초당 메시지 평균 / 최대 | {f(msgs_avg)} / {msgs_max or 0} |")
    lines.append(f"| DB 적재 시간 ms 평균 / 최대 (1초 묶음) | {f(ins_avg)} / {f(ins_max)} |")
    lines.append(f"| 전달 지연(장치→수집기 도착) ms p50 / p95 / max | {f(lat_p50)} / {f(lat_p95)} / {f(lat_max)} |")
    lines.append(f"| 유실 (일련번호 기준) | {received or 0} / {expected or 0} 수신, {loss_pct:.2f}% |")
    for kind, n in events:
        lines.append(f"| 이벤트: {kind} | {n} |")
    lines.append("")
    lines.append("- 전달 지연 = 수집기 \"도착\" 시각 - 장치 측정 시각 (같은 PC 시계). DB 에 보일 때까지는 1초 묶음 적재가 최대 약 1초 더 걸린다(설계상).")
    lines.append("- 유실 = 장치별 일련번호 범위 대비 실제 받은 개수. 재접속 후 재전송(버퍼)이 있으면 0 에 가까워야 한다.")
    return lines


def load_json_files(pattern):
    results = []
    for path in sorted(glob.glob(pattern)):
        with open(path, encoding="utf-8") as fh:
            results.append(json.load(fh))
    return results


def section_faults(measure_dir):
    """표③-2: 장애 주입 결과 (fault_*.json)"""
    faults = load_json_files(os.path.join(measure_dir, "fault_*.json"))
    if len(faults) == 0:
        return []
    faults.sort(key=fault_sort_key)
    lines = ["", "### 표③-2 장애 주입 → 감지·복구·유실", ""]
    lines.append("| 장애 | 주입 방법 | 멈춘 시간 | 감지 | 복구(첫 데이터) | 복구(전 장치/backlog 0) | 유실 행 | 보호 없었다면 | 비고 | 측정 |")
    lines.append("|---|---|---:|---:|---:|---:|---:|---:|---|---|")
    for r in faults:
        name = r["fault"]
        if r.get("label"):
            name = f"{name} ({r['label']})"
        when = (r.get("measured_at") or "")[:16].replace("T", " ")   # 재측정을 구분하기 위해 (UTC)
        loss = r.get("loss") or {}
        lost = loss.get("lost")
        if name.startswith("bad_firmware"):
            lines.append(f"| {name} | {r['method']} | - | - | - | 롤백 {sec(r.get('rollback_s'))} | "
                         f"나쁜 버전 닿은 장치 {r.get('devices_touched')}/{r.get('devices_total')} | "
                         f"{r.get('devices_total')}대 전부 | 5% 단계 헬스 게이트 | {when} |")
            continue
        first = r.get("recover_first_msg_s")
        if first is None:
            first = r.get("recover_first_stats_s")
        if first is None:
            first = r.get("recover_db_up_s")
        full = r.get("recover_all_devices_s")
        if full is None:
            full = r.get("recover_backlog_drained_s")
        note = ""
        if name.startswith("broker") and r.get("burst_peak_msgs_per_s") is not None:
            note = f"재전송 폭주 최대 {r['burst_peak_msgs_per_s']} msgs/s"
        if name.startswith("db") and r.get("rows_written_late") is not None:
            note = f"backlog 로 뒤늦게 들어간 행 {r['rows_written_late']}"
        if name.startswith("collector"):
            note = "QoS 0 은 유실, QoS 1 지속 세션은 0 이어야 함"
        no_protect = r.get("loss_if_no_protection")
        if r.get("baseline_rate") is not None and r.get("duration_s") is not None:
            no_protect = int(round(r["baseline_rate"] * r["duration_s"]))   # 전체 초당 메시지 × 멈춘 시간 (JSON 값보다 이 계산을 우선: 옛 JSON 의 계산 오류 보정)
        lines.append(f"| {name} | {r['method']} | {f(r.get('duration_s'), 0)}초 | {sec(r.get('detect_s'))} | "
                     f"{sec(first)} | {sec(full)} | {lost if lost is not None else '-'} / {loss.get('expected', '-')} | "
                     f"{no_protect if no_protect is not None else '-'} | {note} | {when} |")
    lines.append("")
    lines.append("- 감지 = 주입 → 수집기 통계(msgs/s=0)나 DB 프로브가 이상을 처음 본 때. 복구 = 복구 명령 → DB 에 그 사실이 찍힌 때 (±1초, 1초 묶음 적재). 측정 = UTC.")
    lines.append("- 유실 행 = 장애 직전 마지막 일련번호부터 집계 시각까지 장치가 만든 메시지 수 − 실제 받은 행. '보호 없었다면' = 전체 초당 메시지 × 멈춘 시간.")
    return lines


def section_ota(measure_dir):
    """표③-3: OTA 단계 배포 결과 (ota_*.json)"""
    runs = load_json_files(os.path.join(measure_dir, "ota_*.json"))
    if len(runs) == 0:
        return []
    lines = ["", "### 표③-3 OTA 단계 배포 (5% → 50% → 100%, 헬스 게이트)", ""]
    lines.append("| 버전 | 장치 | 나쁜 펌웨어? | 결과 | 새 버전 닿은 장치 | 롤백 시간 | 적용/헬스 대기(초) |")
    lines.append("|---|---:|---|---|---:|---:|---|")
    for r in runs:
        result = "성공 (100%)"
        if not r.get("success"):
            result = "롤백"
        lines.append(f"| {r['version']} | {r['devices']} | {'예' if r.get('bad') else '아니오'} | {result} | "
                     f"{r['updated_devices']}/{r['devices']} | {sec(r.get('rollback_s'))} | {f(r.get('apply_s'))} / {f(r.get('health_wait_s'))} |")
    lines.append("")
    lines.append("- 나쁜 펌웨어는 5% 단계에서 fault 가 보여 롤백 → 나머지 95% 는 건드리지도 않는다. 롤백 시간 = 롤백 결정 → 닿은 장치 전부 이전 버전·ok.")
    return lines


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", default="postgresql://fleet:fleet@localhost:5432/fleet")
    ap.add_argument("--minutes", type=int, default=5)
    ap.add_argument("--label", default="run")
    ap.add_argument("--no-db", action="store_true", help="DB 질의 생략 (장애·OTA JSON 부분만)")
    ap.add_argument("--measurements", default="docs/measurements")
    ap.add_argument("--out", default="-")
    a = ap.parse_args()

    lines = []
    if not a.no_db:
        lines.extend(section_throughput(a.db, a.minutes, a.label))
    lines.extend(section_faults(a.measurements))
    lines.extend(section_ota(a.measurements))
    if len(lines) == 0:
        lines = ["(표③: 아직 결과 없음)"]

    text = "\n".join(lines) + "\n"
    if a.out == "-":
        print(text)
    else:
        os.makedirs(os.path.dirname(a.out) or ".", exist_ok=True)
        with open(a.out, "w", encoding="utf-8") as fh:
            fh.write(text)
        print(f"wrote {a.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
