#!/usr/bin/env bash
# 그림 다시 만들기: diagrams/*.mmd(Mermaid) → img/*.png (해상도 3배). 실행 위치: docs/deck/build. 필요: mmdc(@mermaid-js/mermaid-cli)
set -euo pipefail
cd "$(dirname "$0")"
mkdir -p img
for f in diagrams/*.mmd; do
  name="$(basename "$f" .mmd)"
  mmdc -i "$f" -o "img/${name}.png" -b white -s 3 >/dev/null
  echo "img/${name}.png"
done
