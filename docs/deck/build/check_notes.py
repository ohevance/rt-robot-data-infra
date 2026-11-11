# 설명 문서 점검 — 장표 수만큼 다 있나, 머리말 번호·제목·위치가 장표와 맞나, 여덟 절이 다 있나, '다음 장표'의 번호와 제목이 맞나,
#                   자리표시·표·옛 숫자가 남았나. 어디서 불러도 된다 (slides.json 은 이 폴더, notes_md 는 한 단계 위).
# 공개하면 안 되는 글자(주소·계정 이름 등)의 점검은 여기서 하지 않는다 — 저장소 뿌리의 scripts/check_public.py 가 pptx·docx 안까지 본다.
# 실행: python3 check_notes.py   (먼저 build.sh 로 slides.json 을 만들어 둔다).  종료 코드 0 = 문제 없음
import glob
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
NOTES = os.path.join(HERE, "..", "notes_md")

# 옛 숫자: 장표·문서를 고친 뒤에도 설명 문서에 남아 있기 쉬운 표현. 지금 값과 어긋나는 것만 적는다 (고친 날짜)
STALE = [
    (r"3부 본편|4부 데이터의 길|1부 출발|2부 어디서|5부 믿을|6부 왜", "옛 부 번호 표현 (11/05)"),
    (r"17건|22건|Python 17|233-307", "옛 숫자 17건/22건/233-307 (11/05)"),
    (r"테스트 20건|단위 15건|Python 15 |4파일 30건|테스트 31건|목록 31건|31건 =|31건\(|C\+\+ 5 · Python 26|C\+\+ 5\(", "옛 테스트 수 — 지금은 37건 = C++ 7 + Python 30 (11/11 밤)"),
    (r"장표 13[89]장|설명 문서 13[89]개|\(139장\)|145장|수\(145\)|1부터 145까지", "옛 장표 수 — 지금은 147장 (11/11 밤)"),
    (r"결정 24건|핵심 18건|결정 18건", "옛 결정 건수 — 장표에는 25건 (11/11)"),
    (r"(전체|기준|현재|파일에) \*{0,2}4[24]건", "옛 결정 기록 수 — 지금 파일에는 46건 (11/11 밤)"),
    (r"27항목|28항목", "옛 읽기 가이드 항목 수 — 지금은 29항목 (11/11 밤)"),
    (r"덧붙임 [4-8]장|덧붙임 136~142|143~145", "옛 덧붙임·끝 범위 — 지금은 덧붙임 9장(136~144), 끝 145~147 (11/11 밤)"),
    (r"공고 네 항목|네 항목 전부|네 항목마다", "옛 공고 표 — 지금은 Framework 공고의 주요 업무 여섯 묶음 + 필수 역량 (11/11 밤)"),
    (r"실험 페이지 24장|\(24장\)|모두 24장", "옛 실험 페이지 수 — 지금은 25장 (11/11 밤)"),
    (r"make_all_applied_check", "없어진 함수 이름 — wait_apply 로 바뀜 (11/10)"),
]
# 옛 값을 '예전에는 이랬다'로 일부러 적은 줄은 넘어간다 (같은 줄에 아래 낱말이 있으면)
HISTORY_WORDS = ("11/05 에는", "낮에는", "11/11 낮", "그때는", "11/05 의", "11/05 까지", "11/05 기준", "그날의 수", "없어졌다", "바로잡", "였다", "이었다", "적혀 있었다", "그대로)")


def check(slides):
    n = len(slides)
    problems = []
    sizes = []
    for i, s in enumerate(slides, start=1):
        path = os.path.join(NOTES, f"{i:03d}.md")
        if not os.path.exists(path):
            problems.append((i, "파일 없음"))
            continue
        with open(path, encoding="utf-8") as f:
            t = f.read()
        sizes.append((i, len(t)))
        lines = t.split("\n")
        head = f"# 장표 {i:03d} — "
        if not lines[0].startswith(head):
            problems.append((i, f"머리말 번호 어긋남: {lines[0][:60]}"))
        elif lines[0][len(head):].strip() != s["title"].strip():
            problems.append((i, f"머리말 제목 다름: {lines[0][len(head):][:50]}"))
        if len(lines) < 2 or not lines[1].startswith("*위치:"):
            problems.append((i, "둘째 줄 '*위치:*' 없음"))
        elif s.get("crumb") and lines[1].strip() != f"*위치: {s['crumb']}*":
            problems.append((i, f"위치가 장표의 crumb 와 다름: {lines[1][:60]}"))
        if "{{" in re.sub(r"`[^`\n]*`", "", t):      # 백틱 안(`{{first:…}}` 를 설명하는 글)은 넘어간다
            problems.append((i, "자리표시 {{ 남음"))
        if re.search(r"^\|", t, re.M):
            problems.append((i, "표(|) 사용"))
        for sec in ["## 1.", "## 2.", "## 3.", "## 4.", "## 5.", "## 6.", "## 7.", "## 8."]:
            if sec not in t:
                problems.append((i, f"절 없음 {sec}"))
        for pattern, why in STALE:
            for line in lines:
                if re.search(pattern, line) and not any(w in line for w in HISTORY_WORDS):
                    problems.append((i, f"{why}: …{line[max(0, re.search(pattern, line).start() - 20):][:70]}"))
                    break
        nxt = re.search(r"다음 장표 (\d{3}): (.*)", t)
        if i < n:
            if not nxt:
                problems.append((i, "다음 장표 줄 없음"))
            elif int(nxt.group(1)) != i + 1:
                problems.append((i, f"다음 장표 번호 어긋남: {nxt.group(1)}"))
            elif nxt.group(2).strip() != slides[i]["title"].strip():
                problems.append((i, f"다음 장표 제목 다름: {nxt.group(2)[:50]}"))
        if len(t) < 1500:
            problems.append((i, f"너무 짧음 {len(t)}자"))
    extra = sorted(f for f in glob.glob(os.path.join(NOTES, "*.md")) if int(os.path.basename(f)[:3]) > n)
    return sizes, problems, extra


def main():
    with open(os.path.join(HERE, "slides.json"), encoding="utf-8") as f:
        slides = json.load(f)
    sizes, problems, extra = check(slides)
    if sizes:
        total = sum(size for _, size in sizes)
        small = min(sizes, key=lambda x: x[1])
        big = max(sizes, key=lambda x: x[1])
        print(f"설명 문서 {len(sizes)}/{len(slides)}개, 평균 {total // len(sizes)}자, 가장 짧은 것 {small[0]:03d}({small[1]}자), 가장 긴 것 {big[0]:03d}({big[1]}자)")
    else:
        print(f"설명 문서 0/{len(slides)}개 — notes_md 폴더를 못 찾았다: {NOTES}")
    for number, text in problems[:60]:
        print(f"  문제 {number:03d}: {text}")
    if len(problems) > 60:
        print(f"  … 그 밖에 {len(problems) - 60}건")
    if extra:
        print("  장표 수보다 큰 번호의 파일:", [os.path.basename(f) for f in extra])
    return 1 if (problems or extra or not sizes) else 0


if __name__ == "__main__":
    sys.exit(main())
