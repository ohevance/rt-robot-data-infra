#!/usr/bin/env bash
# 설명 문서 변환: notes_md/NNN.md → notes/NNN.docx (pandoc). 어디서 불러도 된다.
# 왜 md 와 docx 를 둘 다 두나: md 는 git 에서 읽고 고치기 쉽고, docx 는 사용자가 요청한 형식(장표 하나에 문서 하나)
#
#   ./make_notes.sh 079 080 137     고친 것만 (번호를 준다)
#   ./make_notes.sh                 전부
#
# 같은 md 는 같은 docx 가 되게 만든 시각을 고정한다(SOURCE_DATE_EPOCH) — 안 하면 내용이 같아도 파일이 매번 달라져 git 에 전부 바뀐 것으로 보인다.
# 11/05 에 만든 docx 는 그때의 시각이 들어 있으므로, 처음으로 전부 다시 만들면 내용이 같아도 한 번은 바뀐다. 그래서 평소에는 고친 번호만 준다.
set -euo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
cd "$HERE/.."
export SOURCE_DATE_EPOCH=1793836800          # 2026-11-05 00:00:00 UTC (첫 설명 문서를 만든 날)
if [ ! -f "$HERE/reference.docx" ]; then python3 "$HERE/make_reference.py"; fi
mkdir -p notes
if [ $# -gt 0 ]; then
  files=(); for n in "$@"; do files+=("notes_md/$(printf '%03d' "$((10#$n))").md"); done
else
  files=(notes_md/*.md)
fi
n=0
for md in "${files[@]}"; do
  base="$(basename "$md" .md)"
  pandoc "$md" -f markdown -t docx -o "notes/${base}.docx" --metadata lang=ko --reference-doc="$HERE/reference.docx"
  n=$((n + 1))
done
echo "변환 완료: ${n}개 → notes/"
