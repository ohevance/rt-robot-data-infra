#!/usr/bin/env python3
"""아키텍처별 manifest.<arch>.json 들을 manifest.json 하나로 합친다 (릴리스 워크플로의 마지막 단계).

왜: 릴리스는 러너(x86_64)와 Pi(aarch64) 둘 다를 위한 패키지를 만든다. 장치는 매니페스트 하나만 보고 자기 아키텍처 항목을 고른다
    (device_agent.pick_artifact). 최상위 url/sha256/size 는 첫 번째(기본) 아키텍처 — 옛 형식만 아는 쪽을 위한 호환용.

사용: python3 scripts/merge_manifests.py --out build/release/manifest.json build/release/manifest.x86_64.json build/release/manifest.aarch64.json
      (bad 패키지도 같은 방법: --out manifest-bad.json manifest-bad.*.json)
"""
import argparse
import json
import sys


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", required=True)
    ap.add_argument("inputs", nargs="+")
    a = ap.parse_args()
    merged = None
    for path in a.inputs:
        with open(path, encoding="utf-8") as f:
            m = json.load(f)
        if merged is None:
            merged = dict(m)
            merged["arch"] = {}
        if m["version"] != merged["version"]:
            print(f"버전이 다르다: {m['version']} != {merged['version']} ({path})")
            return 1
        for arch, entry in m.get("arch", {}).items():
            merged["arch"][arch] = entry
    if merged is None:
        return 1
    with open(a.out, "w", encoding="utf-8") as f:
        json.dump(merged, f, ensure_ascii=False, indent=2)
        f.write("\n")
    print(f"manifest: {a.out} — version {merged['version']}, arch {sorted(merged['arch'])}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
