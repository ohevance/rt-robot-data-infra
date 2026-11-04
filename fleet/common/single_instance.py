#!/usr/bin/env python3
"""단일 인스턴스 잠금 — 같은 이름의 프로그램이 한 번에 하나만 뜨게 한다 (수집기·가상 장치가 함께 쓴다).

왜: MQTT 는 같은 client_id 의 새 접속이 옛 접속을 밀어낸다. 수집기("collector")나 가상 장치("agent-vdev-001"…)가
    두 벌 뜨면 둘이 2초마다 서로 끊으며 메시지를 반반 받는다 (11/04 실측: 수집기 2개 → 재접속 반복, 장치 2벌 → reconnects 1,675).
어떻게: fleet/logs/<이름>.lock 을 flock(LOCK_EX|LOCK_NB) 으로 잡고 pid 를 적는다. 프로세스가 어떻게 죽든 커널이 잠금을 푼다.

사용:
    lock = acquire("collector")          # 잡으면 열린 파일, 이미 누가 잡고 있으면 None (그 pid 는 파일 안)
    if lock is None: ... 안내하고 종료
    (lock 을 변수로 들고 있어야 잠금이 유지된다 — 닫히면 풀린다)
"""
import fcntl
import os

HERE = os.path.dirname(os.path.abspath(__file__))
LOCK_DIR = os.path.join(HERE, "..", "logs")


def lock_path(name):
    return os.path.join(LOCK_DIR, f"{name}.lock")


def acquire(name):
    """잠금을 잡으면 열린 파일 객체를, 못 잡으면 None 을 돌려준다. 못 잡은 이유는 other_pid(name) 으로 본다"""
    os.makedirs(LOCK_DIR, exist_ok=True)
    lock_file = open(lock_path(name), "a+")
    try:
        fcntl.flock(lock_file, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except OSError:
        lock_file.close()
        return None
    lock_file.seek(0)
    lock_file.truncate()
    lock_file.write(str(os.getpid()))
    lock_file.flush()
    return lock_file


def other_pid(name):
    """이미 잡고 있는 쪽이 적어 둔 pid (없으면 '?')"""
    try:
        with open(lock_path(name), encoding="utf-8") as f:
            text = f.read().strip()
    except OSError:
        return "?"
    if text == "":
        return "?"
    return text
