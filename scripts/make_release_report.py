#!/usr/bin/env python3
"""릴리스 보고서 — 매니페스트 + 카나리 결과(정상·깨진 패키지)를 Release 설명문(마크다운)으로.

GitHub Release 의 본문이 되고, 아티팩트로도 남는다. 숫자는 카나리 JSON(rollout.py 결과)에서 그대로 옮긴다 — 손으로 쓰는 숫자는 없다.

사용: python3 scripts/make_release_report.py --manifest build/release/manifest.json \
        --good build/release_canary/ota_release_good.json --bad build/release_canary/ota_release_bad.json --out RELEASE_NOTES.md
"""
import argparse
import json
import re
import sys


def load(path):
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def stage_times(result):
    """타임라인에서 '단계 N%: 전원 적용 완료 (T초)' 를 뽑는다 → [(N, T)]"""
    out = []
    for e in result.get("timeline", []):
        m = re.match(r"단계 (\d+)%: 전원 적용 완료 \(([\d.]+)초\)", e.get("event", ""))
        if m:
            out.append((int(m.group(1)), float(m.group(2))))
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--manifest", required=True)
    ap.add_argument("--good", required=True)
    ap.add_argument("--bad", required=True)
    ap.add_argument("--out", required=True)
    a = ap.parse_args()
    m = load(a.manifest)
    good = load(a.good)
    bad = load(a.bad)

    lines = []
    lines.append(f"# rt-robot-data-infra {m['version']}")
    lines.append("")
    lines.append(f"커밋 `{str(m.get('commit', ''))[:12]}` · 빌드 {m.get('built_at', '?')} · 배포 정책 {m.get('rollout', {}).get('stages_pct')} %, "
                 f"헬스 대기 {m.get('rollout', {}).get('health_wait_s')} s, 허용 비정상 {m.get('rollout', {}).get('max_fail')}")
    lines.append("")
    lines.append("## 산출물")
    lines.append("")
    lines.append("| 아키텍처 | 파일 | 크기 | sha256 |")
    lines.append("|---|---|---:|---|")
    for arch, e in sorted((m.get("arch") or {}).items()):
        name = str(e.get("url", "")).rsplit("/", 1)[-1]
        lines.append(f"| {arch} | `{name}` | {e.get('size', 0):,} B | `{e.get('sha256', '')}` |")
    lines.append("")
    lines.append("장치는 `manifest.json` 을 읽고 자기 아키텍처 항목을 골라 내려받는다 → sha256 검증 → A/B 슬롯 → 자가 점검 → 전환 (`docs/RELEASE.md`).")
    lines.append("")
    lines.append("## 게시 전 카나리 (가상 함대, GitHub 러너)")
    lines.append("")
    st = stage_times(good)
    st_text = " → ".join(f"{pct}% {t:.1f} s" for pct, t in st) if st else "-"
    lines.append(f"- 정상 패키지: 장치 {good.get('devices')}대, 결과 **{'성공' if good.get('success') else '실패'}** "
                 f"({good.get('updated_devices')}/{good.get('devices')} 갱신), 단계별 적용 완료 {st_text}, 전체 {good.get('total_s', '?')} s "
                 f"(카나리의 헬스 대기 {good.get('health_wait_s', '?')} s × {len(st) or '?'}단계 포함 — 위의 배포 정책 값과 다를 수 있다)")
    first_pct = (bad.get("stages_pct") or [5])[0]
    lines.append(f"- 깨진 패키지(자가 점검 실패): 결과 **{'롤백' if not bad.get('success') else '통과(이상!)'}**, "
                 f"닿은 장치 {bad.get('updated_devices')}/{bad.get('devices')} (첫 단계 {first_pct} %), 롤백 {bad.get('rollback_s', '?')} s")
    reasons = [e["event"] for e in bad.get("timeline", []) if "설치 실패" in e.get("event", "")]
    if reasons:
        lines.append(f"  - 거부 사유: {reasons[0].split('사유', 1)[-1].strip()[:160]}")
    lines.append("")
    lines.append("둘 다 기대대로여야 이 Release 가 게시된다 (`fleet/tests/release_canary.sh` → `fleet/chaos/assert_results.py`).")
    lines.append("")
    lines.append("## 실물에 내보내기")
    lines.append("")
    lines.append("- 지휘소 모드 [WSL 창]: `python3 fleet/ota/rollout.py --manifest <이 Release 의 manifest.json URL>` — 가상 먼저, 실물(kind=real)은 마지막 단계")
    lines.append("- 자율 모드 (Pi): 에이전트가 `releases/latest/download/manifest.json` 을 주기적으로 읽어 스스로 설치한다. pre-release 는 `latest` 에 잡히지 않는다")
    lines.append("")
    with open(a.out, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")
    print(f"report -> {a.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
