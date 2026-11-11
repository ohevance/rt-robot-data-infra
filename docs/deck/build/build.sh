#!/usr/bin/env bash
# 장표 전체 다시 만들기. 어디서 불러도 된다.  필요: python3, node + pptxgenjs(npm i pptxgenjs), (그림을 바꿨으면 mmdc), (설명 문서는 pandoc)
#   1) make_slides.py    : content_a~d.py + gates.py → slides.json (crumb·next·들머리·목차 번호를 여기서 붙인다)
#   2) build_deck.js     : slides.json + img/ → ../rt-robot-data-infra.pptx
#   3) make_slides_md.py : slides.json → ../SLIDES.md (번호 · 부 · 종류 · 제목)
# 그다음에 할 것: python3 check_notes.py (설명 문서가 장표와 맞나) · 저장소 뿌리에서 python3 scripts/check_public.py (공개하면 안 되는 글자가 pptx·docx 안에 없나)
set -euo pipefail
cd "$(dirname "$0")"
python3 make_slides.py
node build_deck.js slides.json ../rt-robot-data-infra.pptx
# 폴더 항목(19개)이 ZIP 에 남으면 일부 클라우드 편집기가 못 연다 → 지운다 (내용 변화 없음)
zip -dq ../rt-robot-data-infra.pptx '*/' 2>/dev/null || true
python3 make_slides_md.py
