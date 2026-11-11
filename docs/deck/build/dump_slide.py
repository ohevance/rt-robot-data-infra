# 장표 한 장의 내용을 읽기 쉽게 출력 — 설명 문서를 쓸 때 참고용.  python3 dump_slide.py 37
import json, sys
slides = json.load(open("slides.json", encoding="utf-8"))
for arg in sys.argv[1:]:
    n = int(arg)
    s = slides[n - 1]
    print(f"===== 장표 {n:03d} [{s['kind']}] 섹션: {s['section']}")
    print(json.dumps(s, ensure_ascii=False, indent=1))
