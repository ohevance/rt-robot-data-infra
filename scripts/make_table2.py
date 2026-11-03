#!/usr/bin/env python3
"""표② 생성기 — dds_bench 의 JSON 결과들을 하나의 마크다운 표로.

사용:  python3 scripts/make_table2.py --json 'docs/measurements/dds_*.json' --out docs/measurements/table2.md
"""
import argparse
import glob
import json
import os
import sys


def fmt_bytes(n):
    if n >= 1048576:
        return f"{n // 1048576} MB"
    if n >= 1024:
        return f"{n // 1024} KB"
    return f"{n} B"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--json", nargs="+", required=True, help="dds_*.json (glob 허용)")
    ap.add_argument("--out", default="-")
    a = ap.parse_args()

    rows = []
    for pat in a.json:
        for p in sorted(glob.glob(pat)):
            with open(p, encoding="utf-8") as f:
                rows.append(json.load(f))
    if not rows:
        print("입력이 없습니다", file=sys.stderr)
        return 2

    # 보기 좋게 정렬: 구현체 → 신뢰성 → 크기
    rows.sort(key=lambda r: (r.get("rmw", ""), r.get("reliability", ""), r.get("payload_bytes", 0)))

    lines = ["### 표② DDS 왕복 지연(RTT)·손실률 (단위 us, 같은 호스트 프로세스 간)", ""]
    lines.append("| 구현체 | 신뢰성 | 깊이 | 크기 | 속도 | 보냄 | 받음 | 손실% | min | p50 | p99 | p99.9 | max |")
    lines.append("|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|")
    for r in rows:
        t = r.get("rtt_us", {}) or {}
        lines.append("| {rmw} | {rel} | {depth} | {size} | {rate:.0f} Hz | {sent} | {recv} | {loss} | {mn} | {p50} | {p99} | {p999} | {mx} |".format(
            rmw=r.get("rmw", "?").replace("rmw_", "").replace("_cpp", ""), rel=r.get("reliability", "?"),
            depth=r.get("depth", "?"), size=fmt_bytes(int(r.get("payload_bytes", 0))), rate=float(r.get("rate_hz", 0)),
            sent=r.get("sent", 0), recv=r.get("received", 0), loss=r.get("loss_pct", 0),
            mn=t.get("min", "-"), p50=t.get("p50", "-"), p99=t.get("p99", "-"), p999=t.get("p999", "-"), mx=t.get("max", "-")))
    lines.append("")
    lines.append("- RTT = 왕복. 한 방향 지연은 대략 RTT/2. 같은 호스트에서는 공유 메모리 전송이 섞이므로 네트워크 수치가 아니다.")
    lines.append("- best_effort 에서 손실이 0 이 아니면 '빠르지만 잃을 수 있다', reliable 에서 p99.9 가 커지면 '재전송 대기'의 흔적.")
    text = "\n".join(lines) + "\n"

    if a.out == "-":
        print(text)
    else:
        os.makedirs(os.path.dirname(a.out) or ".", exist_ok=True)
        with open(a.out, "w", encoding="utf-8") as f:
            f.write(text)
        print(f"wrote {a.out} ({len(rows)} rows)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
