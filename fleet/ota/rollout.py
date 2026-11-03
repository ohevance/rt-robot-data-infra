#!/usr/bin/env python3
"""OTA 단계 배포(staged rollout) + 헬스 게이트 + 자동 롤백 — 관제 서버 쪽 도구.

한 번의 배포가 이렇게 진행된다 (기본 5% → 50% → 100%):
  1) 장치 찾기     : 텔레메트리를 몇 초 듣고 "지금 살아 있는 장치" 목록을 만든다
  2) 단계 n        : 목록의 n% 까지 장치에 {"cmd":"ota","version":V} 를 보낸다
  3) 적용 대기     : 그 장치들의 텔레메트리 fw_version 이 V 로 바뀔 때까지 기다린다 (시간 제한 있음)
  4) 헬스 게이트   : health_wait 초 동안 지켜보다가, state 가 ok 가 아닌 장치가 max_fail 보다 많으면 → 롤백
  5) 롤백          : 지금까지 V 를 받은 모든 장치에 ota_rollback → 이전 버전으로 돌아올 때까지 시간 측정 → 중단
  6) 통과하면 다음 단계. 100% 까지 통과하면 완료.

측정하는 숫자 (표③ 용)
  - 단계별 적용 완료 시간, 헬스 통과 시간
  - 롤백 결정 → 전 장치 복구 완료까지 시간 (롤백이 일어난 경우)
  - 나쁜 펌웨어가 닿은 장치 수 vs 전체 (canary 가 막아 준 범위. 50대면 5% = 3대에서 멈춘다)

읽는 순서: FleetWatcher(듣기·보내기) → wait_until → Rollout.run → run_stage → rollback → DbLog → run_rollout → main

사용:
  python3 fleet/ota/rollout.py --version 1.1.0                      # 정상 배포 (5→50→100%)
  python3 fleet/ota/rollout.py --version 1.2.0-bad --bad            # 나쁜 펌웨어: 1단계(5%)에서 잡혀 롤백되어야 한다
결과: 화면 타임라인 + docs/measurements/ota_<version>.json
      (+ DB 가 있으면 events 표에 kind='ota' 줄 단위 기록, ota_rollouts 표에 요약 한 줄)
"""
import argparse
import json
import math
import os
import sys
import threading
import time
from datetime import datetime, timezone

import paho.mqtt.client as mqtt


class FleetWatcher:
    """텔레메트리를 듣고 장치별 최신 (fw_version, state) 를 기억한다. 명령도 여기서 보낸다."""

    def __init__(self, broker, port):
        self.lock = threading.Lock()
        self.latest = {}  # device_id -> {"fw": ..., "state": ..., "t": monotonic}
        self.client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, client_id="ota-rollout", protocol=mqtt.MQTTv311)
        self.client.on_connect = self.on_connect
        self.client.on_message = self.on_message
        self.client.connect(broker, port, keepalive=10)
        self.client.loop_start()

    def on_connect(self, client, userdata, flags, reason_code, properties):
        client.subscribe("fleet/+/telemetry", qos=0)

    def on_message(self, client, userdata, msg):
        try:
            d = json.loads(msg.payload.decode("utf-8"))
        except ValueError:
            return
        device_id = d.get("device_id")
        if device_id is None:
            return
        with self.lock:
            self.latest[device_id] = {"fw": d.get("fw_version"), "state": d.get("state"), "t": time.monotonic()}

    def online_devices(self, within_s=5.0):
        """최근 within_s 초 안에 텔레메트리를 보낸 장치 목록 (이름순)"""
        now = time.monotonic()
        with self.lock:
            result = []
            for device_id in self.latest:
                if now - self.latest[device_id]["t"] < within_s:
                    result.append(device_id)
        result.sort()
        return result

    def snapshot(self, device_ids):
        """지정한 장치들의 최신 값 복사본"""
        with self.lock:
            result = {}
            for device_id in device_ids:
                result[device_id] = dict(self.latest.get(device_id, {}))
        return result

    def send(self, device_id, cmd):
        self.client.publish(f"fleet/{device_id}/cmd", json.dumps(cmd), qos=1)

    def close(self):
        self.client.loop_stop()
        self.client.disconnect()


def wait_until(predicate, timeout_s, poll_s=0.2):
    """predicate() 가 True 가 될 때까지 기다린다. 걸린 시간(초)을 돌려주고, 시간 안에 안 되면 None"""
    start = time.monotonic()
    while True:
        if predicate():
            return time.monotonic() - start
        if time.monotonic() - start >= timeout_s:
            return None
        time.sleep(poll_s)


class Rollout:
    def __init__(self, watcher, version, stages_pct, apply_s, health_wait_s, max_fail, bad, db_log):
        self.w = watcher
        self.version = version
        self.stages_pct = stages_pct
        self.apply_s = apply_s
        self.health_wait_s = health_wait_s
        self.max_fail = max_fail
        self.bad = bad
        self.db_log = db_log          # DbLog 또는 None
        self.updated = []             # 새 버전을 받은 장치 (누적)
        self.timeline = []            # {"t_s": 초, "event": 설명}
        self.rollback_s = None        # 롤백이 있었으면 걸린 시간(초)
        self.t0 = time.monotonic()

    def mark(self, text):
        """타임라인에 한 줄 남기고 화면·DB 에도 쓴다"""
        t = time.monotonic() - self.t0
        self.timeline.append({"t_s": round(t, 2), "event": text})
        print(f"[{t:7.2f}s] {text}")
        if self.db_log is not None:
            self.db_log.event(text)

    def run(self, devices):
        """단계를 차례로 진행. 전부 통과하면 True, 롤백했으면 False"""
        n = len(devices)
        self.mark(f"대상 장치 {n}대, 버전 {self.version}, 단계 {self.stages_pct}%")
        done_count = 0
        for pct in self.stages_pct:
            target_count = int(math.ceil(n * pct / 100.0))
            batch = devices[done_count:target_count]
            if len(batch) == 0:
                continue
            ok = self.run_stage(pct, batch)
            done_count = target_count
            if not ok:
                return False
        self.mark(f"완료: {n}/{n} 장치가 {self.version}")
        return True

    def run_stage(self, pct, batch):
        """한 단계: 보내기 → 적용 대기 → 헬스 게이트. 통과하면 True"""
        self.mark(f"단계 {pct}%: {len(batch)}대에 ota 전송")
        for device_id in batch:
            self.w.send(device_id, {"cmd": "ota", "version": self.version, "apply_s": self.apply_s, "bad": self.bad})
        self.updated.extend(batch)

        took = wait_until(make_all_applied_check(self, batch), timeout_s=self.apply_s + 15.0)
        if took is None:
            self.mark(f"단계 {pct}%: 적용 시간 초과 → 롤백")
            self.rollback()
            return False
        self.mark(f"단계 {pct}%: 전원 적용 완료 ({took:.1f}초)")

        # 헬스 게이트: health_wait 동안 지켜본 뒤, 지금까지 새 버전을 받은 모든 장치의 state 를 본다
        time.sleep(self.health_wait_s)
        snap = self.w.snapshot(self.updated)
        unhealthy = []
        for device_id in self.updated:
            if snap.get(device_id, {}).get("state") != "ok":
                unhealthy.append(device_id)
        unhealthy.sort()
        self.mark(f"단계 {pct}%: 헬스 검사 — 비정상 {len(unhealthy)}/{len(self.updated)} (허용 {self.max_fail})")
        if len(unhealthy) > self.max_fail:
            shown = unhealthy[:10]
            more = ""
            if len(unhealthy) > 10:
                more = " ..."
            self.mark(f"비정상 장치: {shown}{more} → 롤백 결정")
            self.rollback()
            return False
        return True

    def rollback(self):
        """새 버전을 받은 모든 장치를 이전 버전으로. 걸린 시간을 rollback_s 에 남긴다"""
        t_start = time.monotonic()
        self.mark(f"롤백: {len(self.updated)}대에 ota_rollback 전송")
        for device_id in self.updated:
            self.w.send(device_id, {"cmd": "ota_rollback"})

        took = wait_until(make_all_restored_check(self), timeout_s=30.0)
        if took is None:
            self.mark("롤백: 시간 초과 (30초) — 수동 확인 필요")
            self.rollback_s = None
        else:
            self.rollback_s = round(time.monotonic() - t_start, 2)
            self.mark(f"롤백 완료: {len(self.updated)}대 복구, {self.rollback_s}초")


# wait_until 에 넘길 "조건 함수"를 만들어 주는 함수들 (람다 대신 이름 있는 함수로 — 읽기 쉽게)
def make_all_applied_check(rollout, batch):
    def all_applied():
        snap = rollout.w.snapshot(batch)
        for device_id in batch:
            if snap.get(device_id, {}).get("fw") != rollout.version:
                return False
        return True
    return all_applied


def make_all_restored_check(rollout):
    def all_restored():
        snap = rollout.w.snapshot(rollout.updated)
        for device_id in rollout.updated:
            info = snap.get(device_id, {})
            if info.get("fw") == rollout.version:
                return False
            if info.get("state") != "ok":
                return False
        return True
    return all_restored


class DbLog:
    """DB 가 있으면 events(kind='ota') 에 줄 단위, ota_rollouts 에 요약을 쓴다"""

    def __init__(self, conn, version):
        self.conn = conn
        self.version = version

    @staticmethod
    def try_open(dsn, version):
        """접속되면 DbLog, 안 되면 None (화면 출력만 하고 계속 진행). dsn 이 비어 있으면 DB 를 안 쓴다"""
        if not dsn:
            return None
        try:
            import psycopg
            conn = psycopg.connect(dsn, autocommit=True)
        except Exception as e:
            print(f"(DB 기록 생략: {e.__class__.__name__})")
            return None
        return DbLog(conn, version)

    def event(self, text):
        detail = json.dumps({"version": self.version, "text": text}, ensure_ascii=False)
        with self.conn.cursor() as cur:
            cur.execute("INSERT INTO events (time, device_id, kind, detail) VALUES (%s, %s, %s, %s)",
                        (datetime.now(timezone.utc), None, "ota", detail))

    def summary(self, result, started_at, finished_at):
        with self.conn.cursor() as cur:
            cur.execute(
                "INSERT INTO ota_rollouts (started_at, finished_at, version, bad_firmware, stages_pct, devices_total, "
                "devices_updated, success, rollback_s, timeline) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)",
                (started_at, finished_at, result["version"], result["bad"],
                 ",".join(str(p) for p in result["stages_pct"]), result["devices"], result["updated_devices"],
                 result["success"], result["rollback_s"], json.dumps(result["timeline"], ensure_ascii=False)))

    def close(self):
        self.conn.close()


def run_rollout(version, stages, apply_s, health_wait, max_fail, bad, discover_s, broker, port, db, out):
    """배포 한 번. 결과 dict 를 돌려준다 (장애 주입 스크립트도 이 함수를 부른다). 장치가 없으면 None"""
    w = FleetWatcher(broker, port)
    print(f"장치 찾는 중 ({discover_s:.0f}초) ...")
    time.sleep(discover_s)
    devices = w.online_devices()
    if len(devices) == 0:
        print("살아 있는 장치가 없습니다 (virtual_fleet 가 떠 있나요?)")
        w.close()
        return None

    db_log = DbLog.try_open(db, version)
    started_at = datetime.now(timezone.utc)
    r = Rollout(w, version, stages, apply_s, health_wait, max_fail, bad, db_log)
    success = r.run(devices)
    finished_at = datetime.now(timezone.utc)
    w.close()

    result = {
        "version": version, "bad": bad, "stages_pct": stages, "devices": len(devices),
        "updated_devices": len(r.updated), "success": success, "rollback_s": r.rollback_s,
        "apply_s": apply_s, "health_wait_s": health_wait, "timeline": r.timeline,
        "started_at": started_at.isoformat(), "finished_at": finished_at.isoformat(),
    }
    if db_log is not None:
        db_log.summary(result, started_at, finished_at)
        db_log.close()
    if out:
        os.makedirs(os.path.dirname(out) or ".", exist_ok=True)
        with open(out, "w", encoding="utf-8") as f:
            json.dump(result, f, ensure_ascii=False, indent=2)
        print(f"json -> {out}")
    return result


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--version", required=True)
    ap.add_argument("--stages", default="5,50,100", help="누적 퍼센트, 쉼표 구분")
    ap.add_argument("--apply-s", type=float, default=2.0, help="장치가 적용에 쓰는 시간(초, 시뮬)")
    ap.add_argument("--health-wait", type=float, default=5.0, help="단계마다 헬스를 지켜보는 시간(초)")
    ap.add_argument("--max-fail", type=int, default=0, help="허용하는 비정상 장치 수")
    ap.add_argument("--bad", action="store_true", help="나쁜 펌웨어 시뮬레이션 (적용 뒤 fault)")
    ap.add_argument("--discover-s", type=float, default=3.0)
    ap.add_argument("--broker", default="localhost")
    ap.add_argument("--port", type=int, default=1883)
    ap.add_argument("--db", default="postgresql://fleet:fleet@localhost:5432/fleet")
    ap.add_argument("--out", default="", help="결과 JSON 경로 (기본 docs/measurements/ota_<version>.json)")
    a = ap.parse_args()

    stages = [int(x) for x in a.stages.split(",")]
    out = a.out
    if out == "":
        out = f"docs/measurements/ota_{a.version}.json"
    result = run_rollout(a.version, stages, a.apply_s, a.health_wait, a.max_fail, a.bad,
                         a.discover_s, a.broker, a.port, a.db, out)
    if result is None:
        return 2
    if result["success"]:
        return 0
    return 1


if __name__ == "__main__":
    sys.exit(main())
