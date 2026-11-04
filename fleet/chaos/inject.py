#!/usr/bin/env python3
"""장애 주입(chaos) — 관제 한 벌에 고장을 일부러 내고, 감지·복구·유실을 숫자로 잰다 (표③의 "장애 복구" 줄).

장애 4종
  broker        : MQTT 브로커 컨테이너를 duration 초 멈춤   → 장치는 버퍼(store-and-forward), 돌아오면 재전송. 기대 유실 0
  db            : TimescaleDB 컨테이너를 duration 초 멈춤   → 수집기는 backlog 에 보관, 돌아오면 적재.          기대 유실 0
  collector     : 수집기 프로세스를 duration 초 죽임       → QoS 0 이면 그 동안 유실 / --qos 1 지속 세션이면 유실 0
  bad_firmware  : 나쁜 펌웨어를 단계 배포                   → 5% 단계 헬스 게이트에서 롤백. 롤백 시간·닿은 장치 수

재는 것
  - 감지(detect_s)      : 주입 → 수집기 통계(msgs/s=0)나 프로브(DB 응답 없음)가 이상을 처음 보인 때
  - 복구(recover_*_s)   : 복구 명령 → 첫 데이터 / 전 장치 / backlog 0 까지 (DB 에 찍힌 시각으로 계산, ±1초 = 1초 묶음 적재)
  - 유실(loss)          : 장치별 일련번호(seq) 범위와 실제 받은 행 수의 차이 (주입 시각부터 집계 시각까지)
  결과는 JSON (docs/measurements/fault_<fault>[_label].json) → scripts/make_table3.py 가 표로 합친다.

전제: docker compose 로 mqtt·db 가 떠 있고, 수집기와 가상 장치(virtual_fleet.py)가 돌고 있을 것.
  collector 장애는 수집기가 (a) 컨테이너 fleet_collector 로 떠 있으면 docker stop/start,
  (b) 호스트 프로세스면 SIGTERM 으로 죽이고 같은 명령으로 다시 띄운다 (출력은 fleet/logs/collector_restarted.log).

읽는 순서: Db(프로브·질의) → measure_loss → wait_for → run_fault_broker / db / collector / bad_firmware → main
사용:
  python3 fleet/chaos/inject.py --fault broker --duration 10
  python3 fleet/chaos/inject.py --fault db --duration 10
  python3 fleet/chaos/inject.py --fault collector --duration 10 --label qos0
  python3 fleet/chaos/inject.py --fault bad_firmware
  python3 fleet/chaos/inject.py --fault all                     # 넷을 차례로 (사이에 settle 초 쉬면서)
"""
import argparse
import json
import os
import shutil
import signal
import subprocess
import sys
import time
from datetime import datetime, timezone

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, "..", ".."))


def now_utc():
    return datetime.now(timezone.utc)


def seconds_between(later, earlier):
    """두 시각의 차이(초, 소수 1자리). 하나라도 None 이면 None"""
    if later is None or earlier is None:
        return None
    return round((later - earlier).total_seconds(), 1)


def log(text):
    print(f"[{time.strftime('%H:%M:%S')}] {text}", flush=True)


# ---------------------------------------------------------------------------
class Db:
    """DB 질의·프로브. 연결이 안 되면 None 을 돌려주고 예외를 밖으로 내지 않는다 (DB 장애 중에도 돌아야 하므로)"""

    def __init__(self, dsn):
        self.dsn = dsn

    def query(self, sql, params=None):
        import psycopg
        try:
            with psycopg.connect(self.dsn, connect_timeout=2, autocommit=True) as conn:
                with conn.cursor() as cur:
                    cur.execute(sql, params)
                    if cur.description is None:
                        return []
                    return cur.fetchall()
        except Exception:
            return None

    def alive(self):
        return self.query("SELECT 1") is not None

    def not_alive(self):
        return not self.alive()

    def event(self, kind, detail):
        self.query("INSERT INTO events (time, device_id, kind, detail) VALUES (%s, NULL, %s, %s)",
                   (now_utc(), kind, json.dumps(detail, ensure_ascii=False)))

    def baseline(self, seconds=5):
        """최근 seconds 초의 (장치 수, 초당 메시지 평균)"""
        devices = 0
        rows = self.query(f"SELECT count(DISTINCT device_id) FROM telemetry WHERE time > now() - interval '{seconds} seconds'")
        if rows:
            devices = rows[0][0]
        rate = 0.0
        rows = self.query(f"SELECT avg(msgs_per_s) FROM collector_stats WHERE time > now() - interval '{seconds} seconds' AND msgs_per_s > 0")
        if rows and rows[0][0] is not None:
            rate = float(rows[0][0])
        return devices, rate

    def devices_active(self, seconds=3):
        rows = self.query(f"SELECT count(DISTINCT device_id) FROM telemetry WHERE time > now() - interval '{seconds} seconds'")
        if not rows:
            return 0
        return rows[0][0]

    def first_stats_time(self, after, condition_sql):
        """after 이후 condition 을 처음 만족한 collector_stats 의 시각 (없으면 None)"""
        rows = self.query(f"SELECT min(time) FROM collector_stats WHERE time > %s AND ({condition_sql})", (after,))
        if not rows or rows[0][0] is None:
            return None
        return rows[0][0]

    def scalar(self, sql, params=None):
        rows = self.query(sql, params)
        if not rows:
            return None
        return rows[0][0]


def measure_loss(db, t_from, t_to):
    """[t_from, t_to] 창에서 장치별 seq 범위 vs 받은 행 수 → dict(expected, received, lost, devices)"""
    rows = db.query("""
        SELECT count(*) AS devices, coalesce(sum(received), 0), coalesce(sum(expected), 0)
        FROM (SELECT device_id, count(*) AS received, max(seq) - min(seq) + 1 AS expected
              FROM telemetry WHERE time >= %s AND time <= %s GROUP BY device_id) t""", (t_from, t_to))
    if not rows:
        return {"expected": None, "received": None, "lost": None, "devices": None}
    devices, received, expected = rows[0]
    return {"expected": int(expected), "received": int(received), "lost": int(expected) - int(received), "devices": int(devices)}


def wait_for(predicate, timeout_s, poll_s=0.5):
    """predicate() 가 참이 될 때까지 기다린다. 참이 되면 True, 시간 초과면 False"""
    start = time.monotonic()
    while True:
        if predicate():
            return True
        if time.monotonic() - start >= timeout_s:
            return False
        time.sleep(poll_s)


# ---------------------------------------------------------------------------
def compose(args, compose_file):
    cmd = ["docker", "compose", "-f", compose_file] + args
    log("$ " + " ".join(cmd))
    subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.STDOUT)


def container_running(name):
    out = subprocess.run(["docker", "ps", "--filter", f"name=^{name}$", "--format", "{{.Names}}"],
                         capture_output=True, text=True).stdout.strip()
    return out == name


class Waiters:
    """wait_for 에 넘기는 조건들을 이름 있는 메서드로 (람다 대신)"""

    def __init__(self, db, devices0, t_restore):
        self.db = db
        self.devices0 = devices0
        self.t_restore = t_restore

    def messages_resumed(self):
        return self.db.first_stats_time(self.t_restore, "msgs_per_s > 0") is not None

    def all_devices_back(self):
        return self.devices0 > 0 and self.db.devices_active(3) >= self.devices0

    def backlog_drained(self):
        return self.db.first_stats_time(self.t_restore, "backlog_rows = 0 AND msgs_per_s > 0") is not None

    def stats_resumed(self):
        return self.db.first_stats_time(self.t_restore, "msgs_per_s >= 0") is not None


def run_fault_broker(db, a):
    """브로커 중단: 장치 버퍼 → 재전송. 감지 = msgs/s 가 0 이 된 때, 복구 = 첫 메시지 / 전 장치 복귀"""
    devices0, rate0 = db.baseline()
    log(f"기준선: 장치 {devices0}대, {rate0:.1f} msgs/s")
    t_inject = now_utc()
    db.event("fault", {"fault": "broker", "phase": "inject", "duration_s": a.duration})
    compose(["stop", "mqtt"], a.compose)
    time.sleep(a.duration)
    t_restore = now_utc()
    compose(["start", "mqtt"], a.compose)

    w = Waiters(db, devices0, t_restore)
    wait_for(w.messages_resumed, 60)
    t_first = db.first_stats_time(t_restore, "msgs_per_s > 0")
    all_back = wait_for(w.all_devices_back, 90)
    t_all = None
    if all_back:
        t_all = now_utc()
    t_detect = db.first_stats_time(t_inject, "msgs_per_s = 0")
    db.event("fault", {"fault": "broker", "phase": "restore"})
    log(f"복구: 첫 메시지 {seconds_between(t_first, t_restore)}s, 전 장치 {seconds_between(t_all, t_restore)}s. 유실 집계까지 {a.settle:.0f}초 대기")
    time.sleep(a.settle)
    loss = measure_loss(db, t_inject, now_utc())
    peak = db.scalar("SELECT max(msgs_per_s) FROM collector_stats WHERE time > %s", (t_restore,))
    return {
        "fault": "broker", "method": "docker compose stop mqtt", "duration_s": a.duration,
        "baseline_devices": devices0, "baseline_rate": round(rate0, 1),
        "detect_s": seconds_between(t_detect, t_inject),
        "recover_first_msg_s": seconds_between(t_first, t_restore),
        "recover_all_devices_s": seconds_between(t_all, t_restore),
        "burst_peak_msgs_per_s": peak, "loss": loss,
        "t_inject": t_inject.isoformat(), "t_restore": t_restore.isoformat(),
    }


def run_fault_db(db, a):
    """DB 중단: 수집기 backlog → 복귀 후 적재. 감지 = 프로브 실패, 복구 = DB 응답 / backlog 0"""
    devices0, rate0 = db.baseline()
    log(f"기준선: 장치 {devices0}대, {rate0:.1f} msgs/s")
    t_inject = now_utc()
    db.event("fault", {"fault": "db", "phase": "inject", "duration_s": a.duration})
    compose(["stop", "db"], a.compose)
    t_detect = None
    if wait_for(db.not_alive, 30):
        t_detect = now_utc()
    time.sleep(a.duration)
    t_restore = now_utc()
    compose(["start", "db"], a.compose)
    t_db_up = None
    if wait_for(db.alive, 120):
        t_db_up = now_utc()
    w = Waiters(db, devices0, t_restore)
    wait_for(w.backlog_drained, 120)
    t_drained = db.first_stats_time(t_restore, "backlog_rows = 0 AND msgs_per_s > 0")
    db.event("fault", {"fault": "db", "phase": "restore"})
    log(f"복구: DB 응답 {seconds_between(t_db_up, t_restore)}s, backlog 0 {seconds_between(t_drained, t_restore)}s. 유실 집계까지 {a.settle:.0f}초 대기")
    time.sleep(a.settle)
    loss = measure_loss(db, t_inject, now_utc())
    # DB 가 죽어 있던 동안의 행은 모두 "나중에" 들어간 것 = 수집기가 들고 있던 backlog 의 크기
    rows_written_late = db.scalar("SELECT count(*) FROM telemetry WHERE time >= %s AND time <= %s", (t_inject, t_db_up or t_restore))
    db_errors = db.scalar("SELECT max(db_errors) FROM collector_stats WHERE time > %s", (t_restore,))
    return {
        "fault": "db", "method": "docker compose stop db", "duration_s": a.duration,
        "baseline_devices": devices0, "baseline_rate": round(rate0, 1),
        "detect_s": seconds_between(t_detect, t_inject),
        "recover_db_up_s": seconds_between(t_db_up, t_restore),
        "recover_backlog_drained_s": seconds_between(t_drained, t_restore),
        "rows_written_late": rows_written_late, "db_errors_total": db_errors, "loss": loss,
        "t_inject": t_inject.isoformat(), "t_restore": t_restore.isoformat(),
    }


class HostCollector:
    """호스트에서 돌고 있는 수집기 프로세스를 찾아 죽이고, 같은 명령·같은 환경(venv 포함)으로 다시 띄운다"""

    def __init__(self):
        self.pid = None
        self.exe = None
        self.argv = None
        self.cwd = None
        self.environ = None
        self.proc = None

    def find(self):
        out = subprocess.run(["pgrep", "-f", "collector/collector.py"], capture_output=True, text=True).stdout.split()
        pids = []
        for p in out:
            if int(p) != os.getpid():
                pids.append(int(p))
        if len(pids) == 0:
            return False
        self.pid = pids[0]
        self.argv = read_proc_list(f"/proc/{self.pid}/cmdline")
        self.environ = read_proc_environ(f"/proc/{self.pid}/environ")
        self.cwd = os.readlink(f"/proc/{self.pid}/cwd")
        self.exe = pick_python(self.argv[0], self.environ, self.pid)
        return True

    def kill(self):
        log(f"수집기 pid {self.pid} 에 SIGTERM")
        os.kill(self.pid, signal.SIGTERM)

    def restart(self):
        """같은 명령으로 재시작. 1.5초 안에 죽으면(모듈 없음 등) False 를 돌려주고 로그 끝을 보여 준다"""
        os.makedirs(os.path.join(REPO, "fleet", "logs"), exist_ok=True)
        log_path = os.path.join(REPO, "fleet", "logs", "collector_restarted.log")
        logfile = open(log_path, "ab")
        cmd = [self.exe] + self.argv[1:]
        log("재시작: " + " ".join(cmd) + f"  (cwd {self.cwd}, 출력 fleet/logs/collector_restarted.log)")
        self.proc = subprocess.Popen(cmd, cwd=self.cwd, env=self.environ, stdout=logfile, stderr=subprocess.STDOUT,
                                     start_new_session=True)
        time.sleep(1.5)
        if self.proc.poll() is not None:
            log(f"재시작한 수집기가 바로 죽음 (종료 코드 {self.proc.returncode}). 로그 끝:")
            print(tail_text(log_path, 15))
            return False
        return True


def read_proc_list(path):
    """/proc/<pid>/cmdline: NUL 로 구분된 문자열 목록"""
    with open(path, "rb") as f:
        parts = f.read().split(b"\0")
    result = []
    for part in parts:
        if part:
            result.append(part.decode())
    return result


def read_proc_environ(path):
    """/proc/<pid>/environ → dict (PATH, VIRTUAL_ENV 등 — 재시작 때 같은 환경을 주기 위해)"""
    env = {}
    for item in read_proc_list(path):
        if "=" in item:
            key, value = item.split("=", 1)
            env[key] = value
    return env


def pick_python(argv0, env, pid):
    """재시작에 쓸 파이썬 실행 파일을 고른다.
    /proc/<pid>/exe 는 심볼릭 링크를 끝까지 풀어 /usr/bin/python3.12 를 가리키므로 venv 정보가 사라진다 →
    1) VIRTUAL_ENV/bin/python3  2) 절대 경로 argv[0]  3) 원래 PATH 에서 argv[0] 찾기  4) 마지막으로 /proc/<pid>/exe"""
    venv = env.get("VIRTUAL_ENV")
    if venv:
        candidate = os.path.join(venv, "bin", "python3")
        if os.path.exists(candidate):
            return candidate
    if argv0.startswith("/") and os.path.exists(argv0):
        return argv0
    found = shutil.which(argv0, path=env.get("PATH"))
    if found:
        return found
    return os.readlink(f"/proc/{pid}/exe")


def tail_text(path, lines):
    try:
        with open(path, "rb") as f:
            data = f.read().decode("utf-8", errors="replace")
    except OSError:
        return "(로그 없음)"
    return "\n".join(data.splitlines()[-lines:])


def run_fault_collector(db, a):
    """수집기 중단: 컨테이너면 docker stop/start, 호스트 프로세스면 SIGTERM 후 재시작"""
    devices0, rate0 = db.baseline()
    log(f"기준선: 장치 {devices0}대, {rate0:.1f} msgs/s")
    in_container = container_running("fleet_collector")
    host = HostCollector()
    if not in_container and not host.find():
        log("수집기를 찾을 수 없습니다 (컨테이너 fleet_collector 도, 호스트 프로세스도 없음)")
        return None
    t_inject = now_utc()
    db.event("fault", {"fault": "collector", "phase": "inject", "duration_s": a.duration, "label": a.label})
    if in_container:
        compose(["stop", "collector"], a.compose)
    else:
        host.kill()
    time.sleep(a.duration)
    t_restore = now_utc()
    if in_container:
        compose(["start", "collector"], a.compose)
    else:
        if not host.restart():
            log("수집기 재시작 실패 → 측정 중단. 터미널에서 수집기를 직접 다시 띄우세요 (브로커가 QoS 1 메시지를 들고 있다가 넘겨 줍니다)")
            db.event("fault", {"fault": "collector", "phase": "restart_failed"})
            return None
    w = Waiters(db, devices0, t_restore)
    wait_for(w.stats_resumed, 60)
    t_first = db.first_stats_time(t_restore, "msgs_per_s >= 0")
    t_all = None
    if wait_for(w.all_devices_back, 90):
        t_all = now_utc()
    db.event("fault", {"fault": "collector", "phase": "restore"})
    log(f"복구: 첫 통계 {seconds_between(t_first, t_restore)}s, 전 장치 {seconds_between(t_all, t_restore)}s. 유실 집계까지 {a.settle:.0f}초 대기")
    time.sleep(a.settle)
    loss = measure_loss(db, t_inject, now_utc())
    method = "SIGTERM + 같은 명령으로 재시작"
    if in_container:
        method = "docker compose stop collector"
    return {
        "fault": "collector", "method": method, "duration_s": a.duration,
        "baseline_devices": devices0, "baseline_rate": round(rate0, 1), "detect_s": None,
        "recover_first_stats_s": seconds_between(t_first, t_restore),
        "recover_all_devices_s": seconds_between(t_all, t_restore),
        "loss": loss, "loss_if_no_protection": int(round(devices0 * rate0 * a.duration)),
        "t_inject": t_inject.isoformat(), "t_restore": t_restore.isoformat(),
    }


def run_fault_bad_firmware(db, a):
    """나쁜 펌웨어 단계 배포 → 헬스 게이트 → 롤백. rollout.py 를 그대로 부른다"""
    sys.path.insert(0, os.path.join(REPO, "fleet", "ota"))
    import rollout
    version = "9.9.9-bad-" + time.strftime("%H%M%S")
    result = rollout.run_rollout(version=version, stages=[5, 50, 100], apply_s=2.0, health_wait=5.0, max_fail=0,
                                 bad=True, discover_s=3.0, broker=a.broker, port=a.port, db=a.db,
                                 out=os.path.join(REPO, "docs", "measurements", f"ota_{version}.json"))
    if result is None:
        return None
    return {
        "fault": "bad_firmware", "method": "rollout.py --bad (5%→50%→100%)", "duration_s": None,
        "baseline_devices": result["devices"], "detect_s": None,
        "devices_touched": result["updated_devices"], "devices_total": result["devices"],
        "rollback_s": result["rollback_s"], "success": result["success"], "version": version,
    }


# ---------------------------------------------------------------------------
def save(result, out):
    os.makedirs(os.path.dirname(out) or ".", exist_ok=True)
    with open(out, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)
    log(f"json -> {out}")


def default_out(fault, label):
    suffix = ""
    if label:
        suffix = "_" + label
    return os.path.join(REPO, "docs", "measurements", f"fault_{fault}{suffix}.json")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--fault", required=True, choices=["broker", "db", "collector", "bad_firmware", "all"])
    ap.add_argument("--duration", type=float, default=10.0, help="멈춰 두는 시간(초)")
    ap.add_argument("--settle", type=float, default=15.0, help="복구 뒤 유실을 세기 전에 기다리는 시간(초)")
    ap.add_argument("--label", default="", help="결과 파일 이름에 붙는 꼬리표 (예: qos0 / qos1)")
    ap.add_argument("--compose", default=os.path.join(REPO, "fleet", "docker-compose.yml"))
    ap.add_argument("--db", default="postgresql://fleet:fleet@localhost:5432/fleet")
    ap.add_argument("--broker", default="localhost")
    ap.add_argument("--port", type=int, default=1883)
    ap.add_argument("--out", default="", help="결과 JSON (기본 docs/measurements/fault_<fault>[_label].json)")
    a = ap.parse_args()

    db = Db(a.db)
    if not db.alive():
        log("DB 에 붙을 수 없습니다. docker compose 가 떠 있나요?")
        return 2

    runners = {"broker": run_fault_broker, "db": run_fault_db, "collector": run_fault_collector,
               "bad_firmware": run_fault_bad_firmware}
    faults = [a.fault]
    if a.fault == "all":
        faults = ["broker", "db", "collector", "bad_firmware"]

    exit_code = 0
    for i, fault in enumerate(faults):
        if i > 0:
            log(f"다음 장애 전 {a.settle:.0f}초 안정화")
            time.sleep(a.settle)
        log(f"=== 장애 주입: {fault} ===")
        result = runners[fault](db, a)
        if result is None:
            exit_code = 1
            continue
        result["label"] = a.label
        result["measured_at"] = now_utc().isoformat()
        out = a.out
        if out == "" or a.fault == "all":
            out = default_out(fault, a.label)
        save(result, out)
        log(json.dumps(result, ensure_ascii=False))
    return exit_code


if __name__ == "__main__":
    sys.exit(main())
