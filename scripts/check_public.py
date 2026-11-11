#!/usr/bin/env python3
"""공개 전 점검 — 저장소에 올라갈 파일에 사설 주소·서버 주소·개인 폴더 경로·계정 이름·토큰이 없는지 본다. 글 파일뿐 아니라 pptx·docx 안까지.

왜 이 파일이 있나 (11/11)
  11/06 의 규칙은 커밋 전에 `git grep` 한 줄이었다. 11/11, 이미 공개한 장표(pptx)의 한 장에 계정 이름이 든 명령이 남아 있는 것을 찾았다.
  pptx·docx 는 ZIP 으로 묶은 XML 이라 git grep 이 그 안을 보지 못한다 — 점검은 "통과"였지만 본 범위가 좁았다.
  그래서 (1) 묶음 파일을 풀어서 보고 (2) 못 본 것(그림·바이너리)이 무엇인지도 같이 알린다. "0줄"은 "본 곳에서는 0줄"이다.

무엇을 찾나
  일반 모양 — 이 파일에 적혀 있다. 누구의 저장소에나 해당하고 비밀이 아니다 (GENERIC)
    IPv4 주소(허용 목록 제외 — 사설 주소도, 서버의 공인 주소도 여기 걸린다), 클라우드 호스트 이름(ec2-숫자 넷, ip-숫자 넷),
    개인 폴더 경로(/home/<이름>, /mnt/c/Users/<이름>, C:\\Users\\<이름> — 자리표시와 흔한 이름은 뺀다), 휴대 전화 번호
  내 낱말 — 이 파일에 적지 않는다. 적으면 이 파일이 그 낱말을 공개한다
    계정 이름, 토큰 앞자리, 클라우드 계정 번호 … 를 저장소 밖 파일에 한 줄에 하나씩(정규식, # 으로 시작하는 줄은 주석)
    위치: --patterns 로 준 파일 → 환경변수 PUBLIC_CHECK_PATTERNS → ~/.config/rt-fleet/public_check_patterns.txt
    파일이 없으면 일반 모양만 검사하고 그 사실을 알린다 (조용히 통과하지 않는다)

어디를 보나
  git 이 추적하는 파일 + 아직 add 하지 않은 새 파일(.gitignore 에 걸린 것은 제외) + 파일 이름 + 아직 push 하지 않은 커밋의 메시지
  + 명령줄에 준 추가 파일(예: 제출용 PDF — 저장소 밖 파일에는 "연락처" 규칙을 쓰지 않는다. 이력서에 전화번호가 있는 것은 정상이다)
  글 파일은 그대로. pptx·docx·xlsx 는 ZIP 을 풀어 XML 을 "글"과 "태그 안의 속성"으로 나눠서 본다 — 한 낱말이 서식 경계에서
  두 조각으로 나뉘어 있어도 글만 이어 붙이면 보인다. PDF 는 pdftotext 가 있으면 글을 뽑아서. 그림은 볼 수 없다 → 개수만 알린다.
  커밋 메시지를 보는 이유: bundle 을 fast-forward 가 아닌 병합으로 받으면 병합 메시지에 bundle 의 경로(개인 폴더)가 그대로 적힌다.

사용 (저장소 어디서나)
  python3 scripts/check_public.py                     # 전체. 걸린 것이 있으면 종료 코드 1
  python3 scripts/check_public.py ~/서류/이력서.pdf    # 저장소 + 저장소 밖 파일
  python3 scripts/check_public.py --show              # 걸린 글자를 가리지 않고 보여 준다 (화면을 녹화·공유하는 중이면 쓰지 않는다)
  python3 scripts/check_public.py --selftest          # 이 점검기가 잡아야 할 것을 잡는지 (지어낸 값으로)

읽는 순서: GENERIC → load_private → list_repo_files → texts_of → find_matches → scan_text → check_files → check_messages → main
"""
import argparse
import html
import os
import re
import shutil
import subprocess
import sys
import tempfile
import zipfile

REPO = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
DEFAULT_PATTERNS = os.path.join("~", ".config", "rt-fleet", "public_check_patterns.txt")
CONTEXT_CHARS = 30                 # 걸린 곳 앞뒤로 보여 주는 글자 수
BINARY_PROBE_BYTES = 8192          # 앞의 이만큼에 0 바이트가 있으면 글 파일이 아니라고 본다
ZIP_SUFFIXES = (".pptx", ".docx", ".xlsx", ".potx", ".dotx")
XML_SUFFIXES = (".xml", ".rels", ".vml")
IMAGE_SUFFIXES = (".png", ".jpg", ".jpeg", ".gif", ".bmp", ".webp", ".ico", ".emf", ".wmf")

# 문서에 일부러 적는 주소: 자기 자신, "모든 주소", 클라우드 메타데이터 서비스(어느 계정이나 같다)
ALLOWED_ADDRESSES = {"127.0.0.1", "0.0.0.0", "169.254.169.254", "255.255.255.255"}
# 개인 것이 아닌 계정 이름: CI 러너, 클라우드 이미지의 기본 계정, 예시
ALLOWED_USERS = {"runner", "ubuntu", "user", "Public", "Default"}

# (규칙 이름, 정규식, 묶음). 묶음 "contact" 는 저장소 안 파일에만 쓴다
GENERIC = [
    # 뒤에 "-글자"가 오면 커널 판 번호(6.18.33.2-microsoft…)라서 뺀다
    ("IPv4 주소", r"(?<![\d.])\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}(?![\d.]|-[A-Za-z])", "address"),
    ("클라우드 호스트 이름", r"\b(?:ec2|ip)-\d{1,3}-\d{1,3}-\d{1,3}-\d{1,3}\b", "address"),
    ("개인 폴더(/home)", r"/home/([A-Za-z0-9_.-]+)", "path"),
    ("개인 폴더(Users)", r"(?:/mnt/[a-z]/Users/|[A-Za-z]:\\+Users\\+)([^\s/\\<>…`'\"|)*]+)", "path"),
    ("휴대 전화 번호", r"(?<!\d)01[016789][- .]\d{3,4}[- .]\d{4}(?!\d)", "contact"),
]

# XML 에서 문단·줄·표 칸이 끝나는 자리. 여기서는 글을 이어 붙이지 않는다 (옆 칸의 숫자와 붙어 주소처럼 보이지 않게)
BLOCK_END = re.compile(r"</(?:a|w):p>|<(?:a|w):br\s*/?>|</(?:a|w):tc>")
TAG = re.compile(r"<[^>]+>")


class Rule:
    def __init__(self, name, pattern, group):
        self.name = name
        self.regex = re.compile(pattern)
        self.group = group


def is_allowed(rule, match):
    """일반 모양에 걸렸지만 공개해도 되는 값인가 (허용 목록)"""
    if rule.name == "IPv4 주소":
        return match.group(0) in ALLOWED_ADDRESSES
    if rule.group == "path":
        return match.group(1) in ALLOWED_USERS
    return False


def load_private(path_arg):
    """저장소 밖의 낱말 목록 → (Rule 목록, 읽은 파일 경로 또는 None)"""
    path = path_arg or os.environ.get("PUBLIC_CHECK_PATTERNS") or DEFAULT_PATTERNS
    path = os.path.expanduser(path)
    if not os.path.isfile(path):
        return [], None
    rules = []
    with open(path, encoding="utf-8") as f:
        for number, line in enumerate(f, start=1):
            text = line.strip()
            if not text or text.startswith("#"):
                continue
            # 규칙 이름에 낱말 자체를 쓰지 않는다 — 출력에 낱말 목록이 드러나지 않게 줄 번호만
            rules.append(Rule(f"내 낱말(목록 {number}번째 줄)", text, "private"))
    return rules, path


def list_repo_files():
    """git 이 추적하는 파일 + 새 파일(.gitignore 에 걸리지 않은 것). 저장소 뿌리 기준 경로"""
    out = subprocess.run(["git", "-C", REPO, "ls-files", "-z", "--cached", "--others", "--exclude-standard"],
                         check=True, capture_output=True).stdout
    names = [n for n in out.decode("utf-8").split("\0") if n]
    return sorted(set(names))


def split_xml(xml_text):
    """XML 한 덩어리를 (글, 태그 안의 속성들) 로 나눈다.
    글: 같은 문단 안의 조각은 이어 붙인다 — 한 낱말이 서식 경계에서 <a:t>ab</a:t>…<a:t>cd</a:t> 로 나뉜 것이 다시 한 낱말이 된다.
    속성: 링크 주소 같은 것은 글이 아니라 태그 안에 있다."""
    text = TAG.sub("", BLOCK_END.sub("\n", xml_text))
    attributes = "\n".join(TAG.findall(xml_text))
    return html.unescape(text), html.unescape(attributes)


def texts_of_zip(path, seen):
    """ZIP 묶음(pptx·docx·xlsx) 안의 글 조각들을 (어디, 글) 로 내놓는다"""
    try:
        archive = zipfile.ZipFile(path)
    except zipfile.BadZipFile:
        seen["unreadable"].append(path)
        return
    with archive:
        for member in archive.namelist():
            lower = member.lower()
            if lower.endswith(IMAGE_SUFFIXES):
                seen["images"] += 1
                continue
            if not lower.endswith(XML_SUFFIXES):
                continue
            text, attributes = split_xml(archive.read(member).decode("utf-8", errors="replace"))
            yield member + " 의 글", text
            yield member + " 의 태그 속성", attributes


def texts_of_pdf(path, seen):
    if shutil.which("pdftotext") is None:
        seen["unreadable"].append(path + " (pdftotext 가 없어 PDF 를 읽지 못했다)")
        return
    done = subprocess.run(["pdftotext", "-layout", path, "-"], capture_output=True)
    if done.returncode != 0:
        seen["unreadable"].append(path)
        return
    yield "PDF 의 글", done.stdout.decode("utf-8", errors="replace")


def texts_of(path, seen):
    """파일 하나에서 볼 수 있는 글을 전부 (어디, 글) 로. 못 보는 것은 seen 에 적는다"""
    lower = path.lower()
    if lower.endswith(ZIP_SUFFIXES):
        yield from texts_of_zip(path, seen)
        return
    if lower.endswith(".pdf"):
        yield from texts_of_pdf(path, seen)
        return
    if lower.endswith(IMAGE_SUFFIXES):
        seen["images"] += 1
        return
    try:
        with open(path, "rb") as f:
            data = f.read()
    except OSError:
        seen["unreadable"].append(path)
        return
    if b"\0" in data[:BINARY_PROBE_BYTES]:
        seen["binaries"].append(path)
        return
    yield "", data.decode("utf-8", errors="replace")


def find_matches(text, rules):
    """글 하나에 규칙을 전부 대 본다 → 걸린 자리 [(시작, 끝, 규칙 이름)] (허용 목록은 뺀다)"""
    found = []
    for rule in rules:
        for match in rule.regex.finditer(text):
            if not is_allowed(rule, match):
                found.append((match.start(), match.end(), rule.name))
    return sorted(found)


def excerpt(text, spans, start, end, show):
    """걸린 곳의 앞뒤 글. show 가 아니면 이 창 안에서 걸린 글자를 전부 * 로 가린다 —
    앞뒤 글에 다른 낱말이 걸려 있을 수 있고, 터미널을 녹화·공유하는 중일 수 있다"""
    left = max(0, start - CONTEXT_CHARS)
    right = min(len(text), end + CONTEXT_CHARS)
    chars = list(text[left:right])
    if not show:
        for span_start, span_end, _ in spans:
            for i in range(max(span_start, left), min(span_end, right)):
                chars[i - left] = "*"
    return " ".join("".join(chars).split())


def scan_text(text, rules, show):
    """→ [(규칙 이름, 줄 번호, 앞뒤 글)]"""
    spans = find_matches(text, rules)
    hits = []
    for start, end, rule_name in spans:
        line_no = text.count("\n", 0, start) + 1
        hits.append((rule_name, line_no, excerpt(text, spans, start, end, show)))
    return hits


def check_files(paths, rules, show, label_root):
    """파일들을 본다 → (걸린 줄 목록, 본 것·못 본 것 요약). label_root 가 None 이면 저장소 밖 파일(이름은 파일 이름만 본다)"""
    seen = {"files": 0, "images": 0, "binaries": [], "unreadable": []}
    lines = []
    for path in paths:
        shown = os.path.relpath(path, label_root) if label_root else path
        name_to_check = shown if label_root else os.path.basename(path)
        seen["files"] += 1
        for rule_name, _, around in scan_text(name_to_check, rules, show):
            lines.append(f"{shown}: [파일 이름 · {rule_name}] {around}")
        for where, text in texts_of(path, seen):
            for rule_name, line_no, around in scan_text(text, rules, show):
                place = f"{shown} ({where})" if where else shown
                lines.append(f"{place}:{line_no}: [{rule_name}] {around}")
    return lines, seen


def check_messages(rules, show):
    """아직 push 하지 않은 커밋의 메시지를 본다 (push 한 뒤에는 고칠 수 없으므로 그 전에) → (걸린 줄 목록, 본 커밋 수 또는 None)"""
    done = subprocess.run(["git", "-C", REPO, "log", "--format=%h%x09%B%x00", "@{upstream}..HEAD"], capture_output=True)
    if done.returncode != 0:
        return [], None            # 올라갈 곳(upstream)이 정해지지 않은 저장소 — 볼 범위를 모른다
    lines = []
    commits = [c for c in done.stdout.decode("utf-8", errors="replace").split("\0") if c.strip()]
    for commit in commits:
        short, _, body = commit.strip().partition("\t")
        for rule_name, _, around in scan_text(body, rules, show):
            lines.append(f"커밋 {short} 의 메시지: [{rule_name}] {around}")
    return lines, len(commits)


def report_seen(title, seen):
    print(f"  {title}: 파일 {seen['files']}개를 봤다. 그림 {seen['images']}개는 보지 못한다 (화면 캡처라면 눈으로 본다).")
    for path in seen["binaries"]:
        print(f"    못 봄(바이너리): {path}")
    for path in seen["unreadable"]:
        print(f"    못 봄: {path}")


def selftest_files(work):
    """지어낸 값으로 시험 파일 셋과 낱말 목록을 만든다. 값은 조각을 이어 붙여 만든다 — 이 파일에 그대로 적으면 이 파일이 걸린다"""
    word = "gil" + "dong77"
    dirty_lines = [".".join(["192", "168", "7", "23"]), ".".join(["203", "0", "113", "9"]), "-".join(["ec2", "203", "0", "113", "9"]),
                   "/" + "home" + "/" + "gildong" + "/x", "/mnt/c/" + "Users" + "/" + "gildong" + "/Downloads",
                   "-".join(["010", "1234", "5678"]), word]
    patterns = os.path.join(work, "patterns.txt")
    with open(patterns, "w", encoding="utf-8") as f:
        f.write("# 지어낸 낱말\n" + word + "\n")
    dirty = os.path.join(work, "dirty.md")
    with open(dirty, "w", encoding="utf-8") as f:
        f.write("\n".join(dirty_lines) + "\n")
    clean = os.path.join(work, "clean.md")
    with open(clean, "w", encoding="utf-8") as f:
        f.write("127.0.0.1 0.0.0.0 /home/runner /mnt/c/Users/<사용자> C:\\Users\\…\\Downloads 6.18.33.2-microsoft 0.9 / 1.8 ms\n")
    deck = os.path.join(work, "deck.pptx")
    with zipfile.ZipFile(deck, "w") as z:
        # (1) 낱말을 서식 경계에서 둘로 나눈다 — 글을 이어 붙여야 보인다  (2) 옆 칸의 숫자는 이어 붙이면 안 된다  (3) 자리표시는 XML 에서 &lt; 로 적힌다
        z.writestr("ppt/slides/slide1.xml",
                   "<a:p><a:r><a:t>" + word[:4] + "</a:t></a:r><a:r><a:t>" + word[4:] + "</a:t></a:r></a:p>"
                   "<a:tc><a:p><a:r><a:t>1.2</a:t></a:r></a:p></a:tc><a:tc><a:p><a:r><a:t>2.2</a:t></a:r></a:p></a:tc>"
                   "<a:tc><a:p><a:r><a:t>14.62</a:t></a:r></a:p></a:tc>"      # 세 칸을 붙이면 점이 셋인 숫자가 되어 주소처럼 보인다
                   "<a:p><a:r><a:t>/mnt/c/" + "Users" + "/&lt;사용자&gt;/Downloads</a:t></a:r></a:p>")
    return word, len(dirty_lines), patterns, dirty, clean, deck


def selftest():
    """지어낸 값으로 점검기를 점검한다"""
    work = tempfile.mkdtemp(prefix="check-public-")
    failures = []
    try:
        word, dirty_count, patterns, dirty, clean, deck = selftest_files(work)
        private, _ = load_private(patterns)
        rules = [Rule(*g) for g in GENERIC] + private
        dirty_hits, _ = check_files([dirty], rules, False, work)
        clean_hits, _ = check_files([clean], rules, False, work)
        deck_hits, _ = check_files([deck], rules, False, work)
        if len(dirty_hits) != dirty_count:
            failures.append(f"더러운 글 파일의 {dirty_count}줄을 한 번씩 잡아야 하는데 {len(dirty_hits)}줄: {dirty_hits}")
        if clean_hits:
            failures.append(f"허용된 값·자리표시를 잡았다: {clean_hits}")
        if len(deck_hits) != 1 or "내 낱말" not in deck_hits[0]:
            failures.append(f"pptx 안에서는 나뉜 낱말 하나만 잡아야 한다: {deck_hits}")
        if any(word in line or "gildong" in line for line in dirty_hits + deck_hits):
            failures.append(f"가려야 할 글자가 출력에 그대로 나왔다: {dirty_hits + deck_hits}")
    finally:
        shutil.rmtree(work, ignore_errors=True)
    for failure in failures:
        print("selftest 실패:", failure)
    if failures:
        return 1
    print("selftest 통과: 일반 모양 5종 + 내 낱말 · 허용 목록과 자리표시 · pptx 안의 나뉜 낱말 · 옆 칸 숫자는 붙이지 않음 · 가림")
    return 0


def main():
    ap = argparse.ArgumentParser(description="공개 전 점검 — 글 파일과 pptx·docx 안에 주소·개인 경로·내 낱말이 없는지")
    ap.add_argument("extra", nargs="*", help="저장소 밖에서 같이 볼 파일 (예: 제출용 PDF)")
    ap.add_argument("--patterns", default="", help="내 낱말 목록 파일 (기본: $PUBLIC_CHECK_PATTERNS 또는 " + DEFAULT_PATTERNS + ")")
    ap.add_argument("--show", action="store_true", help="걸린 글자를 가리지 않는다")
    ap.add_argument("--selftest", action="store_true", help="점검기가 잡아야 할 것을 잡는지 본다")
    a = ap.parse_args()
    if a.selftest:
        return selftest()

    private, private_path = load_private(a.patterns)
    generic = [Rule(*g) for g in GENERIC]
    if private_path:
        print(f"내 낱말 목록: {len(private)}줄 (저장소 밖 파일)")
    else:
        print("내 낱말 목록이 없다 → 일반 모양만 본다. 계정 이름·토큰 같은 것은 이번 점검이 보지 않았다.")
        print(f"  만드는 법: {DEFAULT_PATTERNS} 에 한 줄에 하나씩 (저장소 안에 두지 않는다)")

    repo_files = [os.path.join(REPO, name) for name in list_repo_files()]
    repo_files = [p for p in repo_files if os.path.isfile(p)]
    hits, seen = check_files(repo_files, generic + private, a.show, REPO)
    report_seen("저장소", seen)

    message_hits, commit_count = check_messages(generic + private, a.show)
    if commit_count is None:
        print("  커밋 메시지: 올라갈 곳(upstream)이 정해지지 않아 보지 않았다.")
    else:
        print(f"  커밋 메시지: 아직 push 하지 않은 커밋 {commit_count}개를 봤다.")
    hits += message_hits

    if a.extra:
        outside_rules = [r for r in generic if r.group != "contact"] + private
        extra_hits, extra_seen = check_files([os.path.abspath(p) for p in a.extra], outside_rules, a.show, None)
        report_seen("추가 파일(연락처 규칙 제외)", extra_seen)
        hits += extra_hits

    for line in hits:
        print(line)
    if hits:
        print(f"걸린 곳 {len(hits)}줄 — 고친 뒤 다시 돌린다. (아직 push 하지 않은 커밋의 메시지는 git commit --amend 로 고칠 수 있다)")
        return 1
    print("걸린 곳 0줄 (본 범위 안에서).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
