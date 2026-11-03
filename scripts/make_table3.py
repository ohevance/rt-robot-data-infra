#!/usr/bin/env python3
"""표③ 생성기 — 관제 DB(collector_stats, telemetry) 에서 최근 N 분의 처리량·수집 지연·유실을 뽑아 마크다운 표로.

사용:  python3 scripts/make_table3.py --minutes 5 --label "가상 50대 1 Hz" --out docs/measurements/table3.md
"""
import argparse
import os
import sys


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", default="postgresql://fleet:fleet@localhost:5432/fleet")
    ap.add_argument("--minutes", type=int, default=5)
    ap.add_argument("--label", default="run")
    ap.add_argument("--out", default="-")
    a = ap.parse_args()

    import psycopg
    conn = psycopg.connect(a.db)
    cur = conn.cursor()
    window = f"now() - interval '{a.minutes} minutes'"

    # 1) 수집기 통계: 초당 메시지·적재 시간·수집 지연
    cur.execute(f"""
        SELECT count(*), avg(msgs_per_s), max(msgs_per_s), max(online),
               avg(insert_ms), max(insert_ms),
               percentile_cont(0.5) WITHIN GROUP (ORDER BY lat_p50_ms),
               percentile_cont(0.5) WITHIN GROUP (ORDER BY lat_p95_ms),
               max(lat_max_ms)
        FROM collector_stats WHERE time > {window} AND msgs_per_s > 0""")
    r = cur.fetchone()
    seconds, msgs_avg, msgs_max, online_max, ins_avg, ins_max, lat_p50, lat_p95, lat_max = r

    # 2) 유실: 장치별 (받은 개수) vs (일련번호 범위)
    cur.execute(f"""
        SELECT count(*) AS devices,
               sum(received) AS received,
               sum(expected) AS expected
        FROM (
          SELECT device_id, count(*) AS received, max(seq) - min(seq) + 1 AS expected
          FROM telemetry WHERE time > {window} GROUP BY device_id
        ) t""")
    devices, received, expected = cur.fetchone()
    loss_pct = 0.0
    if expected:
        loss_pct = 100.0 * (expected - received) / expected

    # 3) 이벤트 수
    cur.execute(f"SELECT kind, count(*) FROM events WHERE time > {window} GROUP BY kind ORDER BY kind")
    events = cur.fetchall()
    conn.close()

    def f(x, nd=1):
        if x is None:
            return "-"
        return f"{float(x):.{nd}f}"

    lines = [f"### 표③ 관제 처리량·수집 지연 — {a.label} (최근 {a.minutes}분)", ""]
    lines.append("| 항목 | 값 |")
    lines.append("|---|---:|")
    lines.append(f"| 측정 구간(초) | {seconds or 0} |")
    lines.append(f"| 온라인 장치(최대) | {online_max or 0} |")
    lines.append(f"| 초당 메시지 평균 / 최대 | {f(msgs_avg)} / {msgs_max or 0} |")
    lines.append(f"| DB 적재 시간 ms 평균 / 최대 (1초 묶음) | {f(ins_avg)} / {f(ins_max)} |")
    lines.append(f"| 수집 지연 ms p50 / p95 / max | {f(lat_p50)} / {f(lat_p95)} / {f(lat_max)} |")
    lines.append(f"| 유실 (일련번호 기준) | {received or 0} / {expected or 0} 수신, {loss_pct:.2f}% |")
    for kind, n in events:
        lines.append(f"| 이벤트: {kind} | {n} |")
    lines.append("")
    lines.append("- 수집 지연 = 수집기 도착 시각 - 장치 측정 시각. 1초 묶음 적재라 최대 약 1초가 더해진다(설계상).")
    lines.append("- 유실 = 장치별 일련번호 범위 대비 실제 받은 개수. 재접속 후 재전송(버퍼)이 있으면 0 에 가까워야 한다.")
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
