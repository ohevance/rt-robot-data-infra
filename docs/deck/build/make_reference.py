# 설명 문서(docx)의 바탕 문서 만들기 — pandoc 의 기본 바탕 문서에 한글 설정 두 가지만 더해 reference.docx 로 쓴다.
#
# 왜 필요한가
#   pandoc 은 --reference-doc 으로 준 문서의 글꼴·문단 모양을 빌려 docx 를 만든다. 기본 바탕 문서는 영어용이라
#   (언어 en-US, 동아시아 글꼴 비어 있음) 한글이 워드에서 엉뚱한 글꼴로 보이고 맞춤법 검사가 영어로 돈다.
# 하는 일
#   1) pandoc 에게 기본 바탕 문서를 달라고 한다 (pandoc --print-default-data-file reference.docx)
#   2) word/styles.xml 의 기본 언어를 ko-KR 로, word/theme/theme1.xml 의 동아시아 글꼴을 '맑은 고딕'으로 바꾼다
#   3) reference.docx 로 다시 묶는다
# 이 파일을 저장소에 두고 reference.docx 는 두지 않는 이유: 바탕 문서는 pandoc 이 가진 것에서 두 줄만 바꾼 것이라, 만드는 법만 있으면 된다.
# 실행: python3 make_reference.py   (make_notes.sh 가 reference.docx 가 없으면 부른다)
import io
import os
import subprocess
import sys
import zipfile

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "reference.docx")

EDITS = {
    "word/styles.xml": [('w:val="en-US" w:eastAsia="en-US"', 'w:val="ko-KR" w:eastAsia="ko-KR"')],
    "word/theme/theme1.xml": [('<a:ea typeface="" />', '<a:ea typeface="Malgun Gothic" />'),
                              ('<a:ea typeface=""/>', '<a:ea typeface="Malgun Gothic"/>')],
}


def main():
    default = subprocess.run(["pandoc", "--print-default-data-file", "reference.docx"], check=True, capture_output=True).stdout
    src = zipfile.ZipFile(io.BytesIO(default))
    changed = 0
    with zipfile.ZipFile(OUT, "w", zipfile.ZIP_DEFLATED) as dst:
        for item in src.infolist():
            data = src.read(item.filename)
            for old, new in EDITS.get(item.filename, []):
                text = data.decode("utf-8")
                if old in text:
                    changed += text.count(old)
                    data = text.replace(old, new).encode("utf-8")
            dst.writestr(item, data)
    if changed < 3:   # 언어 1곳 + 글꼴 2곳(제목·본문). pandoc 판이 바뀌어 못 찾으면 조용히 넘어가지 않는다
        print(f"경고: 바꾼 곳이 {changed}곳뿐이다 (기대 3). pandoc 의 기본 바탕 문서가 달라졌는지 본다", file=sys.stderr)
        return 1
    print(f"reference.docx: 바꾼 곳 {changed}곳 (언어 ko-KR, 동아시아 글꼴 Malgun Gothic)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
