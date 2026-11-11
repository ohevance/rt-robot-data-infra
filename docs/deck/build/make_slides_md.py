# 장표 목록 다시 만들기 — slides.json → ../SLIDES.md (번호 · 부 · 종류 · 제목). build.sh 가 부른다.
# 왜 따로 두나: 장표를 끼우거나 빼면 번호가 바뀐다. 목록을 손으로 고치면 설명 문서 번호와 어긋나기 쉽다.
import json
import os

HERE = os.path.dirname(os.path.abspath(__file__))


def main():
    with open(os.path.join(HERE, "slides.json"), encoding="utf-8") as f:
        slides = json.load(f)
    lines = ["# 장표 목록 (번호 = 설명 문서 번호 docs/deck/notes/NNN.docx)", "",
             "| 번호 | 부 | 종류 | 제목 |", "|---|---|---|---|"]
    for i, s in enumerate(slides, start=1):
        title = s["title"].replace("|", "\\|").replace("\n", " ")
        lines.append(f"| {i:03d} | {s['section']} | {s['kind']} | {title} |")
    out = os.path.join(HERE, "..", "SLIDES.md")
    with open(out, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")
    print(f"SLIDES.md: {len(slides)}장")


if __name__ == "__main__":
    main()
