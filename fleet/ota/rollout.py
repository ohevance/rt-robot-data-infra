#!/usr/bin/env python3
"""OTA 단계 배포(staged rollout) + 헬스 게이트 + 자동 롤백 — 관제 서버 쪽 도구.

한 번의 배포가 이렇게 진행된다 (기본 5% → 50% → 100%):
  1) 장치 찾기     : 텔레메트리를 몇 초 듣고 "지금 살아 있는 장치" 목록을 만든다
  2) 단계 n        : 목록의 n% 까지 장치에 {"cmd":"ota","version":V[, "url","sha256","size"]} 를 보낸다
                     (가상 장치 먼저, 실물(kind=real)은 맨 뒤 — 실물은 마지막 단계에서만 받는다)
  3) 적용 대기     : 그 장치들의 텔레메트리 fw_version 이 V 로 바뀔 때까지 기다린다 (시간 제한 있음)
  4) 헬스 게이트   : health_wait 초 동안 지켜보다가, state 가 ok 가 아닌 장치가 max_fail 보다 많으면 → 롤백
  5) 롤백          : 지금까지 V 를 받은 모든 장치에 ota_rollback → 이전 버전으로 돌아올 때까지 시간 측정 → 중단
  6) 통과하면 다음 단계. 100% 까지 통과하면 완료.

측정하는 숫자 (표③ 용)
  - 단계별 적용 완료 시간, 헬스 통과 시간
  - 롤백 결정 → 전 장치 복구 완료까지 시간 (롤백이 일어난 경우)
  - 나쁜 펌웨어가 닿은 장치 수 vs 전체 (canary 가 막아 준 범위. 50대면 5% = 3대에서 멈춘다)

읽는 순서: load_manifest → FleetWatcher(듣기·보내기) → wait_until → Rollout.run → run_stage → wait_apply → rollback → DbLog → run_rollout → main

사용:
  python3 fleet/ota/rollout.py --version 1.1.0                      # 흉내 배포 (버전 문자열만, 5→50→100%)
  python3 fleet/ota/rollout.py --version 1.2.0-bad --bad            # 나쁜 펌웨어 흉내: 1단계(5%)에서 잡혀 롤백되어야 한다
  python3 fleet/ota/rollout.py --manifest build/release/manifest.json            # 진짜 산출물 배포 (11/10 부터)
  python3 fleet/ota/rollout.py --manifest https://github.com/<o>/<r>/releases/download/v1.2.0/manifest.json
      매니페스트의 version·url·sha256·size·rollout 정책을 쓴다. 장치는 url 에서 내려받아 검증·설치한다(--slot-root 로 뜬 장치만).
      --stages 등 명령줄 값을 주면 매니페스트보다 우선한다.
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
import urllib.request
from datetime import datetime, timezone

import paho.mqtt.client as mqtt

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "common"))
import mqtt_conn  # noqa: E402  (TLS·인증: 환경변수 FLEET_TLS_CA / FLEET_USER / FLEET_PASS)


def load_manifest(path_or_url):
    """manifest.json 을 읽고 url 을 절대 주소로 만든다 (상대 경로면 매니페스트와 같은 폴더 기준)"""
    src = path_or_url
    if src.startswith("http://") or src.startswith("https://"):
        with urllib.request.urlopen(src, timeout=30) as resp:
            m = json.loads(resp.read().decode("utf-8"))
        base = src.rsplit("/", 1)[0]
    else:
        if src.startswith("file://"):
            src = src[len("file://"):]
        with open(src, encoding="utf-8") as f:
            m = json.load(f)
        base = "file://" + os.path.dirname(os.path.abspath(src))
    def absolute(url):
        if url and not (url.startswith("http://") or url.startswith("https://") or url.startswith("file://") or url.startswith("/")):
            return base + "/" + url
        return url
    m["url"] = absolute(m.get("url", ""))
    for arch, entry in (m.get("arch") or {}).items():
        entry["url"] = absolute(entry.get("url", ""))
    m["manifest_source"] = path_or_url
    return m


class FleetWatcher:
    """텔레메트리를 듣고 장치별 최신 (fw_version, state) 를 기억한다. 명령도 여기서 보낸다."""

    def __init__(self, broker, port):
        self.lock = threading.Lock()
        self.latest = {}  # device_id -> {"fw": ..., "state": ..., "t": monotonic}
        self.client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, client_id="ota-rollout", protocol=mqtt.MQTTv311)
        self.client.on_connect = self.on_connect
        self.client.on_message = self.on_message
        mqtt_conn.apply_security(self.client)
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
            self.latest[device_id] = {"fw": d.get("fw_version"), "state": d.get("state"), "kind": d.get("kind", "virtual"),
                                      "ota_stage": d.get("ota_stage"), "ota_error": d.get("ota_error"), "t": time.monotonic()}

    def online_devices(self, within_s=5.0):
        """최근 within_s 초 안에 텔레메트리를 보낸 장치 목록 — 가상 먼저(이름순), 실물(kind=real)은 맨 뒤.
        실물을 뒤로 두는 이유: 단계 배포의 앞 단계(5%)는 가상 장치가 맡고, 실물은 그 단계들이 통과한 뒤에만 받게 하려고"""
        now = time.monotonic()
        with self.lock:
            result = []
            for device_id in self.latest:
                info = self.latest[device_id]
                if now - info["t"] < within_s:
                    result.append((1 if info.get("kind") == "real" else 0, device_id))
        result.sort()
        return [device_id for _, device_id in result]

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
    def __init__(self, watcher, version, stages_pct, apply_s, health_wait_s, max_fail, bad, db_log, manifest=None,
                 apply_timeout_s=None):
        self.w = watcher
        self.version = version
        self.stages_pct = stages_pct
        self.apply_s = apply_s
        self.health_wait_s = health_wait_s
        self.max_fail = max_fail
        self.bad = bad
        self.manifest = manifest      # None 이면 흉내 배포(버전 문자열만), 있으면 url/sha256/size 를 같이 보낸다
        if apply_timeout_s is None:
            apply_timeout_s = apply_s + 15.0
        self.apply_timeout_s = apply_timeout_s
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
        real_count = sum(1 for d in batch if self.w.snapshot([d]).get(d, {}).get("kind") == "real")
        self.mark(f"단계 {pct}%: {len(batch)}대에 ota 전송" + (f" (실물 {real_count}대 포함)" if real_count else ""))
        for device_id in batch:
            cmd = {"cmd": "ota", "version": self.version, "apply_s": self.apply_s, "bad": self.bad}
            if self.manifest is not None:
                cmd["url"] = self.manifest["url"]
                cmd["sha256"] = self.manifest.get("sha256", "")
                cmd["size"] = self.manifest.get("size")
                if self.manifest.get("arch"):
                    cmd["arch"] = self.manifest["arch"]   # 장치가 자기 아키텍처(x86_64 / aarch64) 항목을 고른다
            self.w.send(device_id, cmd)
        self.updated.extend(batch)

        took, failed = self.wait_apply(batch)
        if failed:
            snap = self.w.snapshot(failed)
            reasons = sorted(set(str(snap.get(d, {}).get("ota_error") or snap.get(d, {}).get("ota_stage") or "?") for d in failed))
            self.mark(f"단계 {pct}%: 설치 실패 {len(failed)}대 {sorted(failed)[:5]} — 사유 {reasons[:3]} → 롤백")
            self.rollback()
            return False
        if took is None:
            snap = self.w.snapshot(batch)
            pending = sorted(d for d in batch if snap.get(d, {}).get("fw") != self.version)
            stages_seen = sorted(set(str(snap.get(d, {}).get("ota_stage") or "?") for d in pending))
            self.mark(f"단계 {pct}%: 적용 시간 초과 ({self.apply_timeout_s:.0f}초) — 미적용 {len(pending)}대 {pending[:5]}, 단계 {stages_seen[:3]} → 롤백")
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
            errors = sorted(set(str(snap.get(d, {}).get("ota_error")) for d in unhealthy if snap.get(d, {}).get("ota_error")))
            self.mark(f"비정상 장치: {shown}{more}" + (f" 사유 {errors[:3]}" if errors else "") + " → 롤백 결정")
            self.rollback()
            return False
        return True

    def wait_apply(self, batch):
        """batch 전부가 새 버전을 보고할 때까지 기다린다. 설치에 실패한 장치(state=fault + ota_error)가 보이면 바로 멈춘다.
        돌려주는 것: (걸린 초 또는 None(시간 초과), 실패 장치 목록)"""
        start = time.monotonic()
        while True:
            snap = self.w.snapshot(batch)
            failed = [d for d in batch if snap.get(d, {}).get("state") == "fault" and snap.get(d, {}).get("ota_error")]
            if failed:
                return None, failed
            if all(snap.get(d, {}).get("fw") == self.version for d in batch):
                return time.monotonic() - start, []
            if time.monotonic() - start >= self.apply_timeout_s:
                return None, []
            time.sleep(0.2)

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


# wait_until 에 넘길 "조건 함수"를 만들어 주는 함수 (람다 대신 이름 있는 함수로 — 읽기 쉽게)
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


def run_rollout(version, stages, apply_s, health_wait, max_fail, bad, discover_s, broker, port, db, out,
                manifest=None, apply_timeout_s=None):
    """배포 한 번. 결과 dict 를 돌려준다 (장애 주입 스크립트도 이 함수를 부른다). 장치가 없으면 None
    manifest 가 있으면 진짜 산출물 배포(url/sha256/size 를 장치에 보낸다), 없으면 버전 문자열만 바꾸는 흉내 배포"""
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
    r = Rollout(w, version, stages, apply_s, health_wait, max_fail, bad, db_log, manifest=manifest,
                apply_timeout_s=apply_timeout_s)
    kinds = w.snapshot(devices)
    real = [d for d in devices if kinds.get(d, {}).get("kind") == "real"]
    if manifest is not None:
        # 아키텍처가 둘 이상이면 전부 적는다 — 병합 매니페스트의 최상위 url 은 글롭 순서상 aarch64 라서, 그것만 찍으면
        # x86_64 가상 장치에 aarch64 파일을 보내는 것처럼 읽힌다 (장치는 arch 맵에서 자기 것을 고른다)
        arch_map = manifest.get("arch") or {}
        if arch_map:
            for arch in sorted(arch_map):
                e = arch_map[arch]
                r.mark(f"산출물 [{arch}] {e.get('url')} (sha256 {str(e.get('sha256', ''))[:12]}…, {e.get('size')} bytes)")
        else:
            r.mark(f"산출물 {manifest['url']} (sha256 {str(manifest.get('sha256', ''))[:12]}…, {manifest.get('size')} bytes)")
    if real:
        r.mark(f"실물 장치 {len(real)}대는 마지막 순서: {real}")
    success = r.run(devices)
    finished_at = datetime.now(timezone.utc)
    w.close()

    result = {
        "version": version, "bad": bad, "stages_pct": stages, "devices": len(devices),
        "updated_devices": len(r.updated), "success": success, "rollback_s": r.rollback_s,
        "apply_s": apply_s, "health_wait_s": health_wait, "timeline": r.timeline,
        "started_at": started_at.isoformat(), "finished_at": finished_at.isoformat(),
        "mode": "artifact" if manifest is not None else "simulated",
        "real_devices": real,
        "total_s": round((finished_at - started_at).total_seconds(), 2),
    }
    if manifest is not None:
        result["manifest"] = {"source": manifest.get("manifest_source"), "url": manifest.get("url"),
                              "sha256": manifest.get("sha256"), "size": manifest.get("size"), "commit": manifest.get("commit"),
                              "arch": manifest.get("arch") or {}}
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
    ap.add_argument("--version", default="", help="흉내 배포의 버전 문자열. --manifest 가 있으면 매니페스트의 version 을 쓴다")
    ap.add_argument("--manifest", default="", help="manifest.json 경로 또는 URL — 진짜 산출물 배포")
    ap.add_argument("--stages", default="", help="누적 퍼센트, 쉼표 구분 (기본: 매니페스트 또는 5,50,100)")
    ap.add_argument("--apply-s", type=float, default=2.0, help="장치가 적용에 쓰는 시간(초, 흉내 배포에서만)")
    ap.add_argument("--health-wait", type=float, default=None, help="단계마다 헬스를 지켜보는 시간(초, 기본 매니페스트 또는 5)")
    ap.add_argument("--max-fail", type=int, default=None, help="허용하는 비정상 장치 수 (기본 매니페스트 또는 0)")
    ap.add_argument("--apply-timeout", type=float, default=None, help="단계 적용 대기 상한(초, 기본 매니페스트 또는 apply_s+15)")
    ap.add_argument("--bad", action="store_true", help="나쁜 펌웨어 흉내 (적용 뒤 fault). 진짜 배포에서는 --manifest 에 -bad 패키지를 준다")
    ap.add_argument("--discover-s", type=float, default=3.0)
    ap.add_argument("--broker", default=None, help="기본: 환경변수 FLEET_BROKER 또는 localhost")
    ap.add_argument("--port", type=int, default=None, help="기본: 환경변수 FLEET_PORT, TLS 면 8883, 아니면 1883")
    ap.add_argument("--db", default=os.environ.get("DB_DSN", "postgresql://fleet:fleet@localhost:5432/fleet"))
    ap.add_argument("--out", default="", help="결과 JSON 경로 (기본 docs/measurements/ota_<version>.json)")
    a = ap.parse_args()

    a.broker, a.port = mqtt_conn.broker_defaults(a.broker, a.port)
    manifest = None
    policy = {}
    version = a.version
    if a.manifest:
        manifest = load_manifest(a.manifest)
        policy = manifest.get("rollout", {})
        if not version:
            version = str(manifest["version"])
    if not version:
        ap.error("--version 또는 --manifest 가 필요합니다")
    stages = [int(x) for x in a.stages.split(",")] if a.stages else list(policy.get("stages_pct", [5, 50, 100]))
    health_wait = a.health_wait if a.health_wait is not None else float(policy.get("health_wait_s", 5.0))
    max_fail = a.max_fail if a.max_fail is not None else int(policy.get("max_fail", 0))
    apply_timeout = a.apply_timeout if a.apply_timeout is not None else policy.get("apply_timeout_s")
    out = a.out
    if out == "":
        out = f"docs/measurements/ota_{version}.json"
    result = run_rollout(version, stages, a.apply_s, health_wait, max_fail, a.bad,
                         a.discover_s, a.broker, a.port, a.db, out, manifest=manifest, apply_timeout_s=apply_timeout)
    if result is None:
        return 2
    if result["success"]:
        return 0
    return 1


if __name__ == "__main__":
    sys.exit(main())
