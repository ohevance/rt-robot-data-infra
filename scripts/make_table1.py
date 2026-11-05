#!/usr/bin/env python3
"""표① 생성기 — cyclictest 결과와 jitter_bench 결과를 하나의 마크다운 표로 만든다.

사용 예
  python3 scripts/make_table1.py \
      --cyclictest docs/measurements/cyclictest_*.txt \
      --jitter docs/measurements/jitter_*.json \
      --out docs/measurements/table1.md

표의 뜻
  min/avg/p50/p99/p99.9/max : 깨어남 지연(us). 평균보다 p99.9와 max를 본다.
  cyclictest는 CPU마다 스레드를 하나씩 돌리므로 "가장 나쁜 CPU" 값을 적는다.
"""
import argparse
import glob
import json
import os
import re
import sys


def _percentile_from_hist(hist, total, p):
    """hist: [(us, count)], total: 전체 샘플 수 → p 백분위수(us)"""
    target = p / 100.0 * total
    acc = 0
    for us, cnt in hist:
        acc += cnt
        if acc >= target:
            return us
    return hist[-1][0] if hist else 0


def read_meta(path):
    """<결과 파일>.meta (key=value 한 줄씩) → dict. 없으면 빈 dict"""
    meta = {}
    mpath = path + ".meta"
    if not os.path.exists(mpath):
        return meta
    with open(mpath, encoding="utf-8") as f:
        for line in f:
            if "=" in line:
                k, v = line.strip().split("=", 1)
                meta[k] = v
    return meta


def _mc_to_c(text):
    """밀리도 문자열 → '45.3' 같은 °C 문자열. 숫자가 아니면 None"""
    try:
        return f"{int(text) / 1000.0:.1f}"
    except (TypeError, ValueError):
        return None


def load_note(meta):
    """부하 정의(vm 버퍼 크기)와 jitter_bench 의 prio·work 를 비고에. 11/05 에 두 도구의 부하가 달랐던 것을 뒤늦게 알아 추가"""
    parts = []
    if meta.get("stress_vm_bytes"):
        parts.append("vm " + meta["stress_vm_bytes"])
    if meta.get("prio"):
        parts.append("prio " + meta["prio"])
    if meta.get("work_us"):
        parts.append("work " + meta["work_us"] + " us")
    if meta.get("note"):
        parts.append(meta["note"])
    if not parts:
        return ""
    return " · " + ", ".join(parts)


def thermal_note(meta):
    """온도·스로틀을 비고에 붙일 문자열. 스로틀 플래그가 0 이 아니면 경고 — 그 줄의 수치는 클럭 저하가 섞였을 수 있다"""
    before = _mc_to_c(meta.get("temp_before_mC"))
    after = _mc_to_c(meta.get("temp_after_mC"))
    if before is None or after is None:
        return ""
    note = f" · 온도 {before}→{after} °C"
    throttled = meta.get("throttled_after", "na")
    if throttled in ("0", "0x0"):
        note += ", 스로틀 0"
    elif throttled != "na":
        note += f", ⚠ 스로틀 {throttled}"
    return note


def parse_cyclictest(path):
    """cyclictest -h 출력 파싱. 반환: dict(label, kernel, realtime, stress, min, avg, p50, p99, p999, max, overflow)"""
    meta = read_meta(path)

    per_cpu_hist = {}  # cpu -> [(us, count)]
    mins = avgs = maxs = []
    overflows = []
    with open(path, encoding="utf-8", errors="replace") as f:
        for line in f:
            line = line.rstrip("\n")
            m = re.match(r"^\s*(\d+)\s+(.*)$", line)
            if m and not line.startswith("#"):
                us = int(m.group(1))
                counts = [int(x) for x in m.group(2).split()]
                for cpu, c in enumerate(counts):
                    per_cpu_hist.setdefault(cpu, []).append((us, c))
                continue
            if line.startswith("# Min Latencies:"):
                mins = [int(x) for x in line.split(":", 1)[1].split()]
            elif line.startswith("# Avg Latencies:"):
                avgs = [int(x) for x in line.split(":", 1)[1].split()]
            elif line.startswith("# Max Latencies:"):
                maxs = [int(x) for x in line.split(":", 1)[1].split()]
            elif line.startswith("# Histogram Overflows:"):
                overflows = [int(x) for x in line.split(":", 1)[1].split()]

    if not per_cpu_hist:
        raise ValueError(f"{path}: 히스토그램이 없습니다 (cyclictest -h 로 돌렸나요?)")

    p50 = p99 = p999 = 0
    for cpu, hist in per_cpu_hist.items():
        total = sum(c for _, c in hist)
        if total == 0:
            continue
        p50 = max(p50, _percentile_from_hist(hist, total, 50))
        p99 = max(p99, _percentile_from_hist(hist, total, 99))
        p999 = max(p999, _percentile_from_hist(hist, total, 99.9))

    return {
        "source": "cyclictest",
        "label": meta.get("label", os.path.basename(path).replace("cyclictest_", "").replace(".txt", "")),
        "kernel": meta.get("kernel", "?"),
        "realtime": meta.get("realtime", "0") == "1",
        "stress": meta.get("stress", "none"),
        "min": min(mins) if mins else 0,
        "avg": max(avgs) if avgs else 0,
        "p50": p50,
        "p99": p99,
        "p999": p999,
        "max": max(maxs) if maxs else 0,
        "overflow": sum(overflows) if overflows else 0,
        "note": f"{len(per_cpu_hist)} CPU, worst-CPU values" + load_note(meta) + thermal_note(meta),
    }


def parse_jitter(path):
    with open(path, encoding="utf-8") as f:
        j = json.load(f)
    w = j["wake_us"]
    meta = read_meta(path)      # scripts/jitter_run.sh 가 남긴 부하·온도 (직접 실행한 옛 결과에는 없다 → '-')
    return {
        "source": "jitter_bench",
        "label": j.get("label", os.path.basename(path)),
        "kernel": j.get("kernel", "?"),
        "realtime": bool(j.get("preempt_rt")),
        "stress": meta.get("stress", "-"),
        "min": w["min"], "avg": w["avg"], "p50": w["p50"], "p99": w["p99"], "p999": w["p999"], "max": w["max"],
        "overflow": j.get("drops", 0),
        "note": "SCHED_FIFO={} mlockall={} cpu_pin={} period={}us".format(
            "ok" if j.get("sched_fifo") else "no", "ok" if j.get("mlockall") else "no",
            j.get("cpu_pin", -1), j.get("period_us", "?")) + load_note(meta) + thermal_note(meta),
    }


def fmt(x):
    return f"{x:.1f}" if isinstance(x, float) else str(x)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--cyclictest", nargs="*", default=[], help="cyclictest_*.txt (glob 허용)")
    ap.add_argument("--jitter", nargs="*", default=[], help="jitter_*.json (glob 허용)")
    ap.add_argument("--out", default="-", help="출력 마크다운 파일 ('-'면 화면)")
    a = ap.parse_args()

    rows = []
    for pat in a.cyclictest:
        for p in sorted(glob.glob(pat)):
            rows.append(parse_cyclictest(p))
    for pat in a.jitter:
        for p in sorted(glob.glob(pat)):
            rows.append(parse_jitter(p))
    if not rows:
        print("입력이 없습니다", file=sys.stderr)
        return 2

    lines = []
    lines.append("### 표① 실시간 지연 (wake-up latency, 단위 us)")
    lines.append("")
    lines.append("| 조건 | 도구 | 커널 | RT | 부하 | min | avg | p50 | p99 | p99.9 | max | 드롭/오버플로 | 비고 |")
    lines.append("|---|---|---|---|---|---:|---:|---:|---:|---:|---:|---:|---|")
    for r in rows:
        lines.append("| {label} | {source} | {kernel} | {rt} | {stress} | {mn} | {avg} | {p50} | {p99} | {p999} | {mx} | {ov} | {note} |".format(
            label=r["label"], source=r["source"], kernel=r["kernel"], rt="yes" if r["realtime"] else "no",
            stress=r["stress"], mn=fmt(r["min"]), avg=fmt(r["avg"]), p50=fmt(r["p50"]), p99=fmt(r["p99"]),
            p999=fmt(r["p999"]), mx=fmt(r["max"]), ov=r["overflow"], note=r["note"]))
    lines.append("")
    lines.append("- p99.9 = 1,000번 중 999번은 이 값 이내. 제어 루프는 평균이 아니라 이 값과 max로 판단한다.")
    lines.append("- cyclictest 는 CPU마다 스레드 하나씩이며 가장 나쁜 CPU 값을 적었다.")
    lines.append("- 비고의 온도·스로틀은 측정 스크립트(cyclictest_run.sh · jitter_run.sh)가 남긴 .meta 에서. '⚠ 스로틀' 이 붙은 줄은 클럭 저하가 섞였을 수 있다.")
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
