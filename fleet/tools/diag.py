#!/usr/bin/env python3
"""관제 DB 진단 — 실측에서 나온 "이상한 것"을 숫자로 들여다보는 도구.

  A) 오프라인 이벤트가 왜 20개나 찍혔나?
     → 0.5초 안에 몰린 offline 은 "브로커가 종료되며 접속 클라이언트의 유언을 일괄 발행"한 것 (Mosquitto 의 종료 동작).
       50대 중 일부만 찍히는 이유: 유언을 수집기 소켓에 다 쓰기 전에 브로커가 소켓을 닫는다 → 앞쪽 N개만 도착.
       몰려 있지 않은 offline 은 개별 끊김(정상 종료 또는 장치 다운)으로 본다.
  B) 전달 지연 p95 가 10초쯤마다 10 ms 로 튀는 건 무엇인가?
     → p95 가 평소(중앙값)의 3배를 넘는 초를 "튐"으로 잡고 간격의 중앙값을 낸다. 단, 장애 복구 때 밀린 메시지가 쏟아지는 초
       (msgs/s 가 평소의 3배 이상)는 튐이 아니라 "홍수"이므로 뺀다.
       간격이 keepalive(10초)와 같으면 PINGREQ 동시 발생 가설, 2초면 Grafana 새로고침 가설, 1초면 묶음 적재 가설.
  C) 장치별 일련번호(seq) 틈 — 진짜 유실과 "장치가 멈춘 것"을 가른다
     → 연속된 두 행에서 seq 가 1 넘게 뛰면 유실, seq 는 연속인데 시각이 3초 넘게 벌어지면 장치 멈춤(유실 아님).
       (표③의 유실 계산이 장애 창 가장자리에서 놓칠 수 있는 것을 여기서 잡는다)

실행:  python3 fleet/tools/diag.py --minutes 15            # 화면에
       python3 fleet/tools/diag.py --minutes 15 --out docs/measurements/diag_2026-11-04.md
"""
import argparse
import os
import statistics
import sys
from collections import Counter

CLUSTER_WINDOW_S = 0.5     # 이 시간 안에 몰린 offline = 브로커 종료 유언
CLUSTER_MIN = 3            # 몇 개부터 군집으로 보나
BLIP_FACTOR = 3.0          # p95 가 중앙값의 몇 배면 튐인가
FLOOD_FACTOR = 3.0         # msgs/s 가 중앙값의 몇 배면 홍수(복구 폭주)인가
STALL_GAP_S = 3.0          # seq 는 연속인데 시각이 이만큼 벌어지면 "장치 멈춤"


def median_or_none(values):
    if len(values) == 0:
        return None
    return statistics.median(values)


def fmt(x):
    if x is None:
        return "-"
    return f"{x:.1f}"


# ---------------------------------------------------------------------------
# A. 오프라인 이벤트
# ---------------------------------------------------------------------------
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

    cur.execute(f"""
        SELECT e.time, e.device_id,
               (SELECT max(t.time) FROM telemetry t WHERE t.device_id = e.device_id AND t.time <= e.time) AS last_before,
               (SELECT min(t.time) FROM telemetry t WHERE t.device_id = e.device_id AND t.time > e.time) AS first_after
        FROM events e WHERE e.kind = 'offline' AND e.time > {window}
        ORDER BY e.time""")
    offline = cur.fetchall()
    if len(offline) == 0:
        return
    clustered = find_clusters(offline)
    classify_offline_events(offline, clustered, lines)
    report_offline_clusters(offline, clustered, lines)


def find_clusters(offline):
    """0.5초 안에 CLUSTER_MIN 개 이상 몰린 offline 의 인덱스 집합"""
    groups = []
    current = [0]
    for i in range(1, len(offline)):
        if (offline[i][0] - offline[current[-1]][0]).total_seconds() <= CLUSTER_WINDOW_S:
            current.append(i)
        else:
            groups.append(current)
            current = [i]
    groups.append(current)
    clustered = set()
    for group in groups:
        if len(group) >= CLUSTER_MIN:
            clustered.update(group)
    return clustered


def classify_offline_events(offline, clustered, lines):
    """offline 하나하나에 판정을 붙인다: 군집(브로커 종료 유언) / 그 뒤 데이터 없음(정상 종료·장치 다운) / 개별 끊김"""
    verdicts = Counter()
    lines.append("")
    lines.append(f"offline 이벤트 {len(offline)}개 분류:")
    lines.append("")
    lines.append("| 시각 | 장치 | 직전 데이터(초 전) | 다음 데이터(초 후) | 판정 |")
    lines.append("|---|---|---:|---:|---|")
    for i, (when, device_id, last_before, first_after) in enumerate(offline):
        before_s = None
        after_s = None
        if last_before is not None:
            before_s = (when - last_before).total_seconds()
        if first_after is not None:
            after_s = (first_after - when).total_seconds()
        if i in clustered:
            verdict = "브로커 종료 시 일괄 유언 (장치는 멀쩡)"
        elif after_s is None:
            verdict = "그 뒤 데이터 없음 (정상 종료 또는 장치 다운)"
        else:
            verdict = f"개별 끊김 (데이터 공백 {after_s + (before_s or 0):.1f}초)"
        verdicts[verdict.split(" (")[0]] += 1
        lines.append(f"| {when.strftime('%H:%M:%S.%f')[:-3]} | {device_id} | {fmt(before_s)} | {fmt(after_s)} | {verdict} |")
    lines.append("")
    for verdict, n in verdicts.most_common():
        lines.append(f"- {verdict}: {n}개")
    lines.append("- '다음 데이터' 가 0.x초 뒤인 것은 장치가 끊긴 동안 버퍼에 모아 둔 것을 나중에 재전송했기 때문(측정 시각 기준). 연결이 안 끊겼다는 뜻이 아니다.")


def report_offline_clusters(offline, clustered, lines):
    if len(clustered) == 0:
        return
    items = [offline[i] for i in sorted(clustered)]
    span_ms = (items[-1][0] - items[0][0]).total_seconds() * 1000.0
    devices = [r[1] for r in items]
    shown = ", ".join(devices[:8])
    more = ""
    if len(devices) > 8:
        more = f" ... (+{len(devices) - 8})"
    lines.append("")
    lines.append(f"offline 군집: {items[0][0].strftime('%H:%M:%S.%f')[:-3]} 부터 {span_ms:.0f} ms 안에 {len(items)}대: {shown}{more}")
    lines.append("  → Mosquitto 는 종료될 때 접속 중인 클라이언트의 유언을 한꺼번에 발행한다. 장치 번호가 앞쪽(접속 순서)인 것은 "
                 "소켓을 닫기 전에 앞에서부터 쓰다가 끊겼다는 뜻. 대시보드의 '오프라인 이벤트' 는 이 경우를 빼고 세는 것이 맞다.")


# ---------------------------------------------------------------------------
# B. 전달 지연 튐
# ---------------------------------------------------------------------------
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
    msgs_base = median_or_none([r[4] for r in rows])
    normal = []
    floods = []
    for r in rows:
        if msgs_base and r[4] > msgs_base * FLOOD_FACTOR:
            floods.append(r)
        else:
            normal.append(r)
    p95_values = [r[1] for r in normal if r[1] is not None]
    base = median_or_none(p95_values)
    if base is None or base <= 0:
        lines.append("(p95 값 없음)")
        return
    threshold = base * BLIP_FACTOR
    blips = [r for r in normal if r[1] is not None and r[1] > threshold]
    lines.append("")
    lines.append(f"- 측정 {len(rows)}초 중 복구 홍수(msgs/s > {msgs_base * FLOOD_FACTOR:.0f}) {len(floods)}초는 제외. "
                 f"p95 중앙값 {base:.1f} ms, 튐 기준(3배) {threshold:.1f} ms → 튐 {len(blips)}회")
    if len(floods) > 0:
        lines.append("- 제외한 홍수: " + ", ".join(f"{r[0].strftime('%H:%M:%S')}({r[4]} msgs/s, p95 {r[1] / 1000.0:.1f} s)" for r in floods[:6])
                     + " — 밀린 메시지의 '원래 측정 시각' 기준이라 지연이 크게 보인다 (정상)")
    if len(blips) < 2:
        lines.append("- 튐이 2회 미만 → 주기 분석 불가")
        return
    gaps = []
    for i in range(1, len(blips)):
        gaps.append((blips[i][0] - blips[i - 1][0]).total_seconds())
    lines.append(f"- 튐 사이 간격: 중앙값 {statistics.median(gaps):.1f}초, 최소 {min(gaps):.1f}, 최대 {max(gaps):.1f}")
    insert_base = median_or_none([r[3] for r in normal if r[3] is not None])
    insert_on_blip = [r[3] for r in blips if r[3] is not None]
    if insert_base is not None and len(insert_on_blip) > 0:
        if statistics.median(insert_on_blip) > insert_base * 2:
            where = "DB 쪽도 같이 느려짐"
        else:
            where = "DB 적재는 평소와 같음 → 브로커/파이썬(장치 프로세스) 쪽"
        lines.append(f"- 튈 때 insert_ms 중앙값 {statistics.median(insert_on_blip):.1f} vs 평소 {insert_base:.1f} → {where}")
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


# ---------------------------------------------------------------------------
# C. 일련번호 틈 — 유실 vs 장치 멈춤
# ---------------------------------------------------------------------------
def section_seq_gaps(cur, window, lines):
    lines.append("")
    lines.append("## C. 장치별 일련번호(seq) 틈 — 유실인가, 장치가 멈췄나")
    cur.execute(f"""
        SELECT device_id, time, seq, prev_seq, prev_time FROM (
            SELECT device_id, time, seq,
                   lag(seq) OVER w AS prev_seq, lag(time) OVER w AS prev_time
            FROM telemetry WHERE time > {window} AND seq IS NOT NULL
            WINDOW w AS (PARTITION BY device_id ORDER BY time, seq)
        ) t
        WHERE prev_seq IS NOT NULL AND (seq - prev_seq <> 1 OR time - prev_time > interval '{STALL_GAP_S} seconds')
        ORDER BY time LIMIT 200""")
    rows = cur.fetchall()
    if len(rows) == 0:
        lines.append("- 틈 없음: 모든 장치의 seq 가 연속이고 시각 공백도 없다 (유실 0, 멈춤 0)")
        return
    lost_total = 0
    stalled = 0
    reordered = 0
    groups = {}   # (틈 시작 초, 판정 종류) -> [장치, 유실 수, 공백]
    details = []
    for device_id, when, seq, prev_seq, prev_time in rows:
        gap_s = (when - prev_time).total_seconds()
        missing = seq - prev_seq - 1
        if missing > 0:
            kind = "유실"
            lost_total += missing
        elif missing == 0:
            kind = "장치 멈춤 (seq 연속)"
            stalled += 1
        else:
            kind = "순서 뒤바뀜/재시작"
            reordered += 1
        key = (prev_time.strftime("%H:%M:%S"), kind)
        if key not in groups:
            groups[key] = []
        groups[key].append((device_id, missing, gap_s))
        details.append((device_id, prev_time, when, gap_s, prev_seq, seq, kind, missing))
    # 요약: 같은 초에 시작한 틈을 한 줄로 (장애 하나가 50대에 같은 틈을 내면 50줄 대신 1줄)
    lines.append("")
    lines.append("| 틈 시작(초) | 종류 | 장치 수 | 장치당 유실 | 합계 | 공백(초) | 장치 예 |")
    lines.append("|---|---|---:|---|---:|---:|---|")
    for (start, kind), items in sorted(groups.items()):
        per = sorted(set(it[1] for it in items))
        per_text = str(per[0])
        if len(per) > 1:
            per_text = f"{per[0]}~{per[-1]}"
        total = sum(max(it[1], 0) for it in items)
        gap = max(it[2] for it in items)
        examples = ", ".join(it[0] for it in items[:3])
        lines.append(f"| {start} | {kind} | {len(items)} | {per_text} | {total} | {gap:.1f} | {examples} |")
    lines.append("")
    lines.append(f"- 합계: 유실 {lost_total}개, 장치 멈춤 {stalled}건, 순서 이상 {reordered}건 (상세는 앞 20건만 아래)")
    lines.append("")
    lines.append("| 장치 | 틈 시작 | 틈 끝 | 공백(초) | seq 이전→이후 | 판정 |")
    lines.append("|---|---|---|---:|---|---|")
    for device_id, prev_time, when, gap_s, prev_seq, seq, kind, missing in details[:20]:
        verdict = kind
        if missing > 0:
            verdict = f"유실 {missing}개"
        lines.append(f"| {device_id} | {prev_time.strftime('%H:%M:%S.%f')[:-3]} | {when.strftime('%H:%M:%S.%f')[:-3]} | {gap_s:.1f} | {prev_seq}→{seq} | {verdict} |")
    lines.append("- '장치 멈춤' 은 가상 장치 스레드가 그 시간 동안 tick 을 못 돈 것(파이썬 GIL·paho 재접속 대기 등). 실물이면 장치 쪽 로그를 본다.")
    lines.append("- '유실' 은 메시지가 영영 안 온 것. 어느 장애 시각과 겹치는지 A/B 와 대조한다.")


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
    section_seq_gaps(cur, window, lines)
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
