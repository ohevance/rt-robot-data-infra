# 장표 내용 공용 도우미 — 저장소 파일에서 코드 조각을 그대로 읽어 온다 (손으로 베끼지 않는다 = 틀릴 수 없다)
import os

# 저장소 뿌리: 환경 변수 RT_REPO_ROOT 가 있으면 그것, 없으면 이 파일 위치(docs/deck/build)에서 세 단계 위
REPO = os.environ.get("RT_REPO_ROOT") or os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", ".."))


def code(rel_path, start, end, dedent=0, max_len=118):
    """rel_path 의 start~end 줄(1부터, 양 끝 포함)을 리스트로. dedent 칸만큼 앞 공백 제거, 너무 긴 줄은 잘라 … 표시"""
    with open(os.path.join(REPO, rel_path), encoding="utf-8") as f:
        lines = f.read().splitlines()
    out = []
    for ln in lines[start - 1:end]:
        ln = ln.replace("\t", "    ").rstrip()
        if dedent and ln[:dedent].strip() == "":
            ln = ln[dedent:]
        if len(ln) > max_len:
            ln = ln[:max_len - 1] + "…"
        out.append(ln)
    return out


def ref(rel_path, start, end=None):
    """장표에 적는 파일 참조 문자열"""
    if end is None or end == start:
        return f"{rel_path}:{start}"
    return f"{rel_path}:{start}-{end}"
