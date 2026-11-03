#!/usr/bin/env python3
"""관제 DB 진단 — D2 실측에서 나온 "이상한 두 가지"를 숫자로 들여다보는 도구.

  A) 오프라인 이벤트가 왜 20개나 찍혔나?
     → 이벤트 시각을 초 단위로 묶어 보고, 각 offline 이벤트 전후로 그 장치의 텔레메트리가 실제로 끊겼는지 본다.
       - 텔레메트리도 같이 끊김 → 진짜 끊김 (브로커 중단·네트워크)
       - 텔레메트리는 계속 옴      → 가짜 offline (유언 LWT 가 잘못 발행됨: 브로커 종료 순서, keepalive 오판 등)
       - 그 뒤 텔레메트리 없음     → 정상 종료 (Ctrl+C 로 끈 것)
  B) 전달 지연 p95 가 10초쯤마다 10 ms 로 튀는 건 무엇인가?
     → collector_stats 에서 p95 가 평소(중앙값)의 3배를 넘는 초를 "튐"으로 잡고, 튐 사이 간격의 중앙값을 낸다.
       간격이 keepalive(10초)와 같으면 PINGREQ 동시 발생 가설, 2초면 Grafana 새로고침 가설, 1초면 묶음 적재 가설.
       insert_ms 도 같이 튀면 DB 쪽, 아니면 브로커/파이썬(GIL) 쪽.

실행:  python3 fleet/tools/diag.py --minutes 15            # 화면에
       python3 fleet/tools/diag.py --minutes 15 --out docs/measurements/diag_2026-11-04.md
"""
import argparse
import os
import statistics
import sys
from collections import Counter


def median_or_none(values):
    if len(values) == 0:
        return None
    return statistics.median(values)


def section_offline_events(cur, window, lines):
    lines.append("## A. 온라인/오프라인 이벤트")
    cur.execute(f"""
        SELECT date_trunc('second', time) AS sec, kind, count(*)
        FROM events WHERE kind IN ('online', 'offline') AND time > {window}
        GROUP BY sec, kind ORDER BY sec""")
    rows = cur.fetchall()
    if len(rows) == 0:
        lines.append("(이벤트 없음)")
        return
    lines.append("")
    lines.append("| 시각(초) | online | offline |")
    lines.append("|---|---:|---:|")
    by_sec = {}
    for sec, kind, n in rows:
        if sec not in by_sec:
            by_sec[sec] = {"online": 0, "offline": 0}
        by_sec[sec][kind] = n
    for sec in sorted(by_sec):
        lines.append(f"| {sec.strftime('%H:%M:%S')} | {by_sec[sec]['online']} | {by_sec[sec]['offline']} |")

    classify_offline_events(cur, window, lines)


def classify_offline_events(cur, window, lines):
    """offline 이벤트 하나하나: 그 장치의 텔레메트리가 이벤트 직전에 있었나, 뒤에 다시 왔나 → 진짜/가짜/정상 종료"""
    cur.execute(f"""
        SELECT e.time, e.device_id,
               (SELECT max(t.time) FROM telemetry t WHERE t.device_id = e.device_id AND t.time <= e.time) AS last_before,
               (SELECT min(t.time) FROM telemetry t WHERE t.device_id = e.device_id AND t.time > e.time) AS first_after
        FROM events e WHERE e.kind = 'offline' AND e.time > {window}
        ORDER BY e.time""")
    offline = cur.fetchall()
    verdicts = Counter()
    lines.append("")
    lines.append(f"offline 이벤트 {len(offline)}개 분류:")
    lines.append("")
    lines.append("| 시각 | 장치 | 직전 텔레메트리(초 전) | 다음 텔레메트리(초 후) | 판정 |")
    lines.append("|---|---|---:|---:|---|")
    for when, device_id, last_before, first_after in offline:
        before_s = None
        after_s = None
        if last_before is not None:
            before_s = (when - last_before).total_seconds()
        if first_after is not None:
            after_s = (first_after - when).total_seconds()
        if after_s is None:
            verdict = "정상 종료(그 뒤 데이터 없음)"
        elif after_s < 2.0 and before_s is not None and before_s < 2.0:
            verdict = "가짜 offline(데이터는 계속 옴)"
        else:
            verdict = f"진짜 끊김({after_s:.0f}초 뒤 복귀)"
        verdicts[verdict.split("(")[0]] += 1
        lines.append(f"| {when.strftime('%H:%M:%S.%f')[:-3]} | {device_id} | {fmt(before_s)} | {fmt(after_s)} | {verdict} |")
    lines.append("")
    for verdict, n in verdicts.most_common():
        lines.append(f"- {verdict}: {n}개")


def fmt(x):
    if x is None:
        return "-"
    return f"{x:.1f}"


def section_latency_blips(cur, window, lines):
    lines.append("")
    lines.append("## B. 전달 지연 p95 튐(blip) 주기")
    cur.execute(f"""
        SELECT time, lat_p95_ms, lat_max_ms, insert_ms, msgs_per_s
        FROM collector_stats WHERE time > {window} AND msgs_per_s > 0 ORDER BY time""")
    rows = cur.fetchall()
    if len(rows) < 10:
        lines.append("(collector_stats 가 10초 미만 — 더 돌린 뒤 다시)")
        return
    p95_values = [r[1] for r in rows if r[1] is not None]
    base = median_or_none(p95_values)
    if base is None or base <= 0:
        lines.append("(p95 값 없음)")
        return
    threshold = base * 3.0
    blips = [r for r in rows if r[1] is not None and r[1] > threshold]
    lines.append("")
    lines.append(f"- 측정 {len(rows)}초, p95 중앙값 {base:.1f} ms, 튐 기준(3배) {threshold:.1f} ms → 튐 {len(blips)}회")
    if len(blips) >= 2:
        gaps = []
        for i in range(1, len(blips)):
            gaps.append((blips[i][0] - blips[i - 1][0]).total_seconds())
        lines.append(f"- 튐 사이 간격: 중앙값 {statistics.median(gaps):.1f}초, 최소 {min(gaps):.1f}, 최대 {max(gaps):.1f}")
        insert_values = [r[3] for r in rows if r[3] is not None]
        insert_base = median_or_none(insert_values)
        insert_on_blip = [r[3] for r in blips if r[3] is not None]
        if insert_base is not None and len(insert_on_blip) > 0:
            lines.append(f"- 튈 때 insert_ms 중앙값 {statistics.median(insert_on_blip):.1f} vs 평소 {insert_base:.1f} "
                         f"→ {'DB 쪽도 같이 느려짐' if statistics.median(insert_on_blip) > insert_base * 2 else 'DB 적재는 평소와 같음 → 브로커/파이썬 쪽'}")
        lines.append("")
        lines.append("| 시각 | p95 ms | max ms | insert ms | msgs/s |")
        lines.append("|---|---:|---:|---:|---:|")
        for when, p95, mx, ins, msgs in blips[:30]:
            lines.append(f"| {when.strftime('%H:%M:%S')} | {fmt(p95)} | {fmt(mx)} | {fmt(ins)} | {msgs} |")
        lines.append("")
        lines.append("가설과 확인 실험:")
        lines.append("- 간격 ≈ 10초 → keepalive(10초) PINGREQ 동시 발생 가설. 확인: `virtual_fleet.py --keepalive 30` 으로 다시 돌려 간격이 30초로 바뀌는지")
        lines.append("- 간격 ≈ 2초 → Grafana 새로고침(2초) 쿼리 부하 가설. 확인: Grafana 탭을 닫고 튐이 사라지는지")
        lines.append("- 장치 수에 비례 → 파이썬 스레드 100개(50대 × 2)의 GIL 경쟁 가설. 확인: `--count 10` 에서 튐 크기")
    else:
        lines.append("- 튐이 2회 미만 → 주기 분석 불가")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", default="postgresql://fleet:fleet@localhost:5432/fleet")
    ap.add_argument("--minutes", type=int, default=15)
    ap.add_argument("--out", default="-")
    a = ap.parse_args()

    import psycopg
    conn = psycopg.connect(a.db)
    cur = conn.cursor()
    window = f"now() - interval '{a.minutes} minutes'"

    lines = [f"# 진단 (최근 {a.minutes}분)", ""]
    section_offline_events(cur, window, lines)
    section_latency_blips(cur, window, lines)
    conn.close()

    text = "\n".join(lines) + "\n"
    if a.out == "-":
        print(text)
    else:
        os.makedirs(os.path.dirname(a.out) or ".", exist_ok=True)
        with open(a.out, "w", encoding="utf-8") as f:
            f.write(text)
        print(f"wrote {a.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
