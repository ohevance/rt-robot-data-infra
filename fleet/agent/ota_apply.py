#!/usr/bin/env python3
"""장치 쪽 OTA 설치 — 산출물(tar.gz)을 내려받아 검증하고 A/B 슬롯으로 설치한다. 가상 장치와 실물(Pi)이 같은 코드를 쓴다.

왜 이 파일이 있나
  11/05 까지 OTA 는 "버전 문자열을 바꾸고 몇 초 자는" 흉내였다. 릴리스 파이프라인(태그 → 빌드 → 패키지 → 게시)을
  이으려면 장치가 진짜 산출물을 받아 설치하는 경로가 있어야 한다. 이 파일이 그 경로다.

설치 한 번의 순서 (install)
  1) 내려받기   : url 의 tar.gz 를 slots/.download/<version>.tar.gz 로 (http/https/file, 크기 상한 있음)
  2) 검증       : sha256 이 매니페스트와 같은가. 다르면 여기서 끝 — 디스크에 풀지도 않는다
  3) 풀기       : slots/<version>/ 에 (경로 탈출 '../' 와 절대 경로는 거부)
  4) 자가 점검  : 그 안의 selftest.sh 를 돌린다 (시간 제한). 0 이 아니면 설치하지 않는다
  5) 전환       : current 링크를 새 슬롯으로 — 임시 링크를 만들고 os.replace 로 바꿔치기(원자적). 전원이 꺼져도 current 는
                  옛 슬롯 아니면 새 슬롯, 둘 중 하나다
  6) 기록       : state.json 에 current/previous 버전과 시각
  7) 훅         : 새 슬롯의 post_switch.sh 가 있으면 돌린다(예: 실물에서 노드 재시작). 실패하면 이전 슬롯으로 스스로 되돌린다
롤백(rollback)은 current 를 previous 슬롯으로 되돌린다 — 새로 내려받을 것이 없으니 빠르다.

무엇이 가상이고 무엇이 진짜인가 (정직하게)
  - 내려받기·해시·풀기·링크 전환·자가 점검은 전부 진짜다 (가상 장치 50대면 디렉터리 50개에 진짜로 푼다).
  - "펌웨어"는 rt_core 의 jitter_bench + 로봇 프로필 묶음이다. 실물에서 rt_control_node 를 재시작하는 단계는 없다(다음 단계).
  - sha256 은 무결성(깨지지 않았나)만 보장한다. 진위(누가 만들었나)는 서명이 필요하고 아직 없다(DECISIONS 11/10).

읽는 순서: Result → download → verify_sha256 → extract → selftest → switch_current → install → rollback → read_state
"""
import hashlib
import json
import os
import shutil
import subprocess
import tarfile
import time
import urllib.request

MAX_DOWNLOAD_BYTES = 200 * 1024 * 1024   # 산출물 크기 상한 200 MB — 잘못된 URL 이 디스크를 채우지 않게
SELFTEST_TIMEOUT_S = 60.0


class Result:
    """설치 한 번의 결과. stage 는 어디까지 갔나 (downloaded → verified → extracted → selftest_ok → switched)."""

    def __init__(self):
        self.ok = False
        self.stage = "start"
        self.error = ""
        self.took_s = {}        # 단계별 걸린 시간(초)
        self.bytes = 0

    def as_dict(self):
        return {"ok": self.ok, "stage": self.stage, "error": self.error, "took_s": self.took_s, "bytes": self.bytes}


def _timed(result, name, func):
    """func() 를 돌리고 걸린 시간을 result.took_s[name] 에 적는다"""
    t0 = time.monotonic()
    value = func()
    result.took_s[name] = round(time.monotonic() - t0, 3)
    return value


def download(url, dest_path, max_bytes=MAX_DOWNLOAD_BYTES, timeout_s=60.0):
    """url → dest_path. file:// 과 그냥 경로도 받는다(테스트·로컬 배포용). 받은 바이트 수를 돌려준다"""
    os.makedirs(os.path.dirname(dest_path), exist_ok=True)
    if url.startswith("file://"):
        url = url[len("file://"):]
    if not (url.startswith("http://") or url.startswith("https://")):
        # 로컬 파일 복사
        size = os.path.getsize(url)
        if size > max_bytes:
            raise ValueError(f"산출물이 너무 큼: {size} > {max_bytes}")
        shutil.copyfile(url, dest_path)
        return size
    total = 0
    with urllib.request.urlopen(url, timeout=timeout_s) as resp, open(dest_path, "wb") as out:
        while True:
            chunk = resp.read(1024 * 256)
            if not chunk:
                break
            total += len(chunk)
            if total > max_bytes:
                raise ValueError(f"산출물이 너무 큼: > {max_bytes}")
            out.write(chunk)
    return total


def sha256_of(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        while True:
            chunk = f.read(1024 * 1024)
            if not chunk:
                break
            h.update(chunk)
    return h.hexdigest()


def verify_sha256(path, expected):
    actual = sha256_of(path)
    if actual.lower() != str(expected).lower():
        raise ValueError(f"sha256 불일치: 기대 {str(expected)[:12]}… 실제 {actual[:12]}…")
    return actual


def _safe_members(tar, dest_dir):
    """tar 안의 경로가 dest_dir 밖으로 나가지 않는지 확인한 멤버만 돌려준다 (경로 탈출 방지)"""
    dest_real = os.path.realpath(dest_dir)
    for member in tar.getmembers():
        if member.issym() or member.islnk():
            raise ValueError(f"산출물에 링크가 들어 있음: {member.name}")
        target = os.path.realpath(os.path.join(dest_dir, member.name))
        if not (target == dest_real or target.startswith(dest_real + os.sep)):
            raise ValueError(f"산출물 경로가 밖으로 나감: {member.name}")
        yield member


def extract(tar_path, dest_dir):
    """tar.gz 를 dest_dir 에 푼다. 이미 있으면 지우고 다시 (반쯤 풀린 슬롯이 남지 않게).
    릴리스 tar 는 보통 최상위 폴더 하나(rt-robot-data-infra-<ver>/)로 싸여 있다 — 그 한 겹은 벗겨서 selftest.sh 가 슬롯 바로 아래 오게 한다"""
    if os.path.isdir(dest_dir):
        shutil.rmtree(dest_dir)
    os.makedirs(dest_dir)
    with tarfile.open(tar_path, "r:gz") as tar:
        members = list(_safe_members(tar, dest_dir))
        if hasattr(tarfile, "data_filter"):
            tar.extractall(dest_dir, members=members, filter="data")
        else:  # Python 3.11 이하
            tar.extractall(dest_dir, members=members)
    entries = os.listdir(dest_dir)
    if len(entries) == 1 and os.path.isdir(os.path.join(dest_dir, entries[0])):
        inner = os.path.join(dest_dir, entries[0])
        for name in os.listdir(inner):
            os.rename(os.path.join(inner, name), os.path.join(dest_dir, name))
        os.rmdir(inner)


def selftest(slot_dir, timeout_s=SELFTEST_TIMEOUT_S):
    """slot_dir/selftest.sh 를 돌린다. 없으면 통과로 본다(점검이 없는 산출물). 0 이 아니면 ValueError"""
    slot_dir = os.path.abspath(slot_dir)
    script = os.path.join(slot_dir, "selftest.sh")
    if not os.path.isfile(script):
        return "no selftest"
    try:
        proc = subprocess.run(["bash", script], cwd=slot_dir, capture_output=True, text=True, timeout=timeout_s)
    except subprocess.TimeoutExpired:
        raise ValueError(f"selftest 시간 초과 ({timeout_s:.0f}초)")
    if proc.returncode != 0:
        tail = (proc.stdout + proc.stderr).strip().splitlines()[-3:]
        raise ValueError(f"selftest 실패 (exit {proc.returncode}): {' | '.join(tail)}")
    return proc.stdout.strip().splitlines()[-1] if proc.stdout.strip() else "ok"


def post_switch(slot_dir, timeout_s=SELFTEST_TIMEOUT_S):
    """slot_dir/post_switch.sh 가 있으면 돌린다. 없으면 아무것도 안 한다. 0 이 아니면 ValueError"""
    slot_dir = os.path.abspath(slot_dir)
    script = os.path.join(slot_dir, "post_switch.sh")
    if not os.path.isfile(script):
        return "no hook"
    try:
        proc = subprocess.run(["bash", script], cwd=slot_dir, capture_output=True, text=True, timeout=timeout_s)
    except subprocess.TimeoutExpired:
        raise ValueError(f"post_switch 시간 초과 ({timeout_s:.0f}초)")
    if proc.returncode != 0:
        tail = (proc.stdout + proc.stderr).strip().splitlines()[-3:]
        raise ValueError(f"post_switch 실패 (exit {proc.returncode}): {' | '.join(tail)}")
    return "ok"


def switch_current(slot_root, version):
    """current → slots/<version> 로 원자적으로 바꾼다 (임시 링크 + os.replace)"""
    link = os.path.join(slot_root, "current")
    tmp = os.path.join(slot_root, f".current.tmp.{os.getpid()}")
    if os.path.lexists(tmp):
        os.remove(tmp)
    os.symlink(os.path.join("slots", version), tmp)
    os.replace(tmp, link)


def read_state(slot_root):
    path = os.path.join(slot_root, "state.json")
    if not os.path.isfile(path):
        return {"current": None, "previous": None}
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def write_state(slot_root, state):
    path = os.path.join(slot_root, "state.json")
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(state, f, ensure_ascii=False, indent=1)
    os.replace(tmp, path)


def install(slot_root, version, url, sha256, size=None, keep_download=False):
    """산출물 하나를 설치한다. 성공하면 current 가 새 슬롯을 가리킨다. 실패하면 current 는 그대로다.

    slot_root/ 구조:  slots/<version>/...  current -> slots/<version>  state.json  .download/
    """
    r = Result()
    # 절대 경로로 굳힌다 — 자가 점검·훅은 슬롯 안에서(cwd=슬롯) 돌리므로 상대 경로면 스크립트를 못 찾는다 (11/10 CI: exit 127)
    slot_root = os.path.abspath(slot_root)
    os.makedirs(os.path.join(slot_root, "slots"), exist_ok=True)
    tar_path = os.path.join(slot_root, ".download", f"{version}.tar.gz")
    slot_dir = os.path.join(slot_root, "slots", version)
    try:
        r.bytes = _timed(r, "download", lambda: download(url, tar_path))
        r.stage = "downloaded"
        if size is not None and int(size) != r.bytes:
            raise ValueError(f"크기 불일치: 매니페스트 {size} 실제 {r.bytes}")
        _timed(r, "verify", lambda: verify_sha256(tar_path, sha256))
        r.stage = "verified"
        _timed(r, "extract", lambda: extract(tar_path, slot_dir))
        r.stage = "extracted"
        _timed(r, "selftest", lambda: selftest(slot_dir))
        r.stage = "selftest_ok"
        state = read_state(slot_root)
        _timed(r, "switch", lambda: switch_current(slot_root, version))
        write_state(slot_root, {"current": version, "previous": state.get("current"),
                                "switched_at": time.strftime("%Y-%m-%dT%H:%M:%S"), "sha256": sha256})
        r.stage = "switched"
        _timed(r, "post_switch", lambda: post_switch(slot_dir))
        r.ok = True
    except Exception as e:  # 어느 단계에서 멈췄든 current 는 안 건드렸거나(1~4) 이미 바꿨다(5~7)
        r.error = f"{e.__class__.__name__}: {e}"
        if os.path.isdir(slot_dir) and r.stage in ("extracted",):
            shutil.rmtree(slot_dir, ignore_errors=True)   # selftest 에 실패한 슬롯은 남기지 않는다
        if r.stage == "switched":
            # 훅이 실패했다 — 링크는 이미 새 슬롯이므로 스스로 되돌린다 (서버의 롤백을 기다리지 않는다)
            if rollback(slot_root) is not None:
                r.stage = "post_switch_failed_rolled_back"
    finally:
        if not keep_download and os.path.isfile(tar_path):
            os.remove(tar_path)
    return r


def rollback(slot_root):
    """current 를 previous 슬롯으로. 돌아간 버전을 돌려주고, previous 가 없으면 None"""
    state = read_state(slot_root)
    prev = state.get("previous")
    if prev is None or not os.path.isdir(os.path.join(slot_root, "slots", prev)):
        return None
    switch_current(slot_root, prev)
    write_state(slot_root, {"current": prev, "previous": None,
                            "switched_at": time.strftime("%Y-%m-%dT%H:%M:%S"), "rolled_back_from": state.get("current")})
    return prev


def current_version(slot_root):
    return read_state(slot_root).get("current")
