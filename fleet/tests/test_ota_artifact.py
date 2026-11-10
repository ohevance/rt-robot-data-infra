#!/usr/bin/env python3
"""산출물 기반 OTA 끝-대-끝 테스트 — 진짜 tar.gz 를 로컬 HTTP 서버로 내려받아 A/B 슬롯에 설치한다 (브로커는 가짜, 설치는 진짜).

확인하는 것
  1) ota_apply.install: 정상 패키지 → 내려받기·sha256·풀기·자가 점검·current 전환, state.json 기록
  2) sha256 이 틀린 매니페스트 → 'downloaded' 단계에서 거부, 디스크에 풀지 않음, current 그대로
  3) 자가 점검이 실패하는 패키지(-bad) → 'extracted' 에서 멈추고 슬롯을 지움, current 그대로
  4) rollback → previous 슬롯으로, state.json 갱신
  5) 함대 20대(가상 19 + 실물 1) + rollout.py --manifest: 정상 → 3단계 전부, 20대 모두 새 버전·current 링크. 실물은 마지막 순서
  6) 같은 함대에 -bad 매니페스트: 1단계(1대)에서 설치 실패를 보고 즉시 롤백, 실물은 닿지 않음, 모두 이전 버전·ok
  7) 자율 업데이트: 매니페스트를 한 번 읽어 새 버전이면 설치, 같은 버전이면 아무것도 안 함, 시간대 밖이면 안 함
  8) 아키텍처 맵: 매니페스트의 arch 에 내 아키텍처가 있으면 그 항목, 없으면 최상위 url (러너 x86_64 / Pi aarch64 가 한 매니페스트를 본다)
  9) post_switch.sh 훅이 실패하면 장치가 스스로 이전 슬롯으로 되돌린다

실행:  python3 fleet/tests/test_ota_artifact.py   (약 5~10초. 네트워크 없음 — 127.0.0.1 만)
"""
import hashlib
import http.server
import io
import json
import math
import os
import shutil
import sys
import tarfile
import tempfile
import threading
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import fake_mqtt  # noqa: E402

fake_mqtt.install()
BROKER = fake_mqtt.BROKER

sys.path.insert(0, os.path.join(HERE, "..", "agent"))
sys.path.insert(0, os.path.join(HERE, "..", "ota"))
from device_agent import DeviceAgent, pick_artifact  # noqa: E402
import ota_apply  # noqa: E402
import rollout  # noqa: E402

fail_count = 0


def check(condition, message):
    global fail_count
    if not condition:
        print("FAIL:", message)
        fail_count += 1


# ---------- 가짜 릴리스 패키지 만들기 (scripts/package_release.sh 와 같은 구조, 바이너리 대신 셸 스크립트) ----------
def make_package(out_dir, version, bad=False, bad_hook=False):
    name = f"rt-robot-data-infra-{version}"
    stage = tempfile.mkdtemp()
    pkg = os.path.join(stage, name)
    os.makedirs(os.path.join(pkg, "bin"))
    if bad_hook:
        with open(os.path.join(pkg, "post_switch.sh"), "w") as f:
            f.write("#!/usr/bin/env bash\necho 'hook: service restart failed'\nexit 3\n")
        os.chmod(os.path.join(pkg, "post_switch.sh"), 0o755)
    with open(os.path.join(pkg, "VERSION"), "w") as f:
        f.write(version + "\n")
    with open(os.path.join(pkg, "bin", "jitter_bench"), "w") as f:
        f.write("#!/usr/bin/env bash\necho fake-binary\n")
    with open(os.path.join(pkg, "selftest.sh"), "w") as f:
        if bad:
            f.write("#!/usr/bin/env bash\necho 'selftest: broken on purpose'\nexit 1\n")
        else:
            f.write("#!/usr/bin/env bash\nset -e\ncd \"$(dirname \"$0\")\"\n./bin/jitter_bench > /dev/null\necho selftest ok\n")
    os.chmod(os.path.join(pkg, "selftest.sh"), 0o755)
    os.chmod(os.path.join(pkg, "bin", "jitter_bench"), 0o755)
    tar_path = os.path.join(out_dir, name + ".tar.gz")
    with tarfile.open(tar_path, "w:gz") as tar:
        tar.add(pkg, arcname=name)
    shutil.rmtree(stage)
    sha = hashlib.sha256(open(tar_path, "rb").read()).hexdigest()
    manifest = {"version": version, "url": name + ".tar.gz", "sha256": sha, "size": os.path.getsize(tar_path),
                "commit": "test", "rollout": {"stages_pct": [5, 50, 100], "health_wait_s": 0.2, "max_fail": 0, "apply_timeout_s": 10}}
    mpath = os.path.join(out_dir, "manifest-bad.json" if bad else ("manifest-badhook.json" if bad_hook else "manifest.json"))
    with open(mpath, "w", encoding="utf-8") as f:
        json.dump(manifest, f)
    return mpath, manifest


class QuietHandler(http.server.SimpleHTTPRequestHandler):
    def log_message(self, fmt, *args):
        pass


def serve(directory):
    """directory 를 127.0.0.1 의 빈 포트로 서빙. (서버, base_url) 을 돌려준다"""
    handler = lambda *a, **kw: QuietHandler(*a, directory=directory, **kw)  # noqa: E731
    server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    return server, f"http://127.0.0.1:{server.server_address[1]}"


# ---------- 0: 상대 경로 슬롯 (11/10 CI 에서 발견) ----------
def test_relative_slot_root(base_url, good, work):
    """슬롯 디렉터리를 상대 경로로 줘도 자가 점검이 돈다.
    통합 테스트(integration.sh)와 릴리스 카나리는 --slot-root build/…/devices 처럼 상대 경로를 준다. 자가 점검은 슬롯 안에서
    (cwd=슬롯) 돌리는데, 스크립트 경로까지 상대 경로면 "슬롯 안에서 본 슬롯 경로"가 되어 못 찾는다(exit 127).
    단위 테스트는 임시 디렉터리(절대 경로)만 써서 이걸 못 잡았다."""
    saved = os.getcwd()
    os.chdir(work)
    try:
        r = ota_apply.install(os.path.join("rel", "dev-1"), good["version"], base_url + "/" + good["url"], good["sha256"], good["size"])
        check(r.ok and r.stage == "switched", f"상대 경로 슬롯에서도 설치된다: ok={r.ok} stage={r.stage} err={r.error}")
        check(ota_apply.current_version(os.path.join("rel", "dev-1")) == good["version"], "상대 경로로 읽어도 current 가 새 버전")
    finally:
        os.chdir(saved)


# ---------- 1~4: ota_apply 단독 ----------
def test_apply_unit(base_url, good, bad, work):
    slot_root = os.path.join(work, "unit-slots")
    r = ota_apply.install(slot_root, good["version"], base_url + "/" + good["url"], good["sha256"], good["size"])
    check(r.ok and r.stage == "switched", f"정상 설치: ok={r.ok} stage={r.stage} err={r.error}")
    check(os.path.islink(os.path.join(slot_root, "current")), "current 링크가 생겼다")
    check(os.readlink(os.path.join(slot_root, "current")) == os.path.join("slots", good["version"]), "current → slots/<version>")
    check(ota_apply.current_version(slot_root) == good["version"], "state.json 의 current 가 새 버전")
    check(set(r.took_s) == {"download", "verify", "extract", "selftest", "switch", "post_switch"}, f"단계별 시간이 다 적힌다: {sorted(r.took_s)}")
    check(not os.path.exists(os.path.join(slot_root, ".download", good["version"] + ".tar.gz")), "내려받은 tar 는 지운다")

    # sha 틀림
    r2 = ota_apply.install(slot_root, "9.9.9", base_url + "/" + good["url"], "00" * 32, good["size"])
    check(not r2.ok and r2.stage == "downloaded" and "sha256" in r2.error, f"sha 불일치는 downloaded 에서 거부: {r2.stage} {r2.error[:40]}")
    check(not os.path.isdir(os.path.join(slot_root, "slots", "9.9.9")), "거부된 패키지는 풀지 않는다")
    check(ota_apply.current_version(slot_root) == good["version"], "current 는 그대로")

    # 자가 점검 실패
    r3 = ota_apply.install(slot_root, bad["version"], base_url + "/" + bad["url"], bad["sha256"], bad["size"])
    check(not r3.ok and r3.stage == "extracted" and "selftest" in r3.error, f"selftest 실패는 extracted 에서 멈춤: {r3.stage} {r3.error[:60]}")
    check(not os.path.isdir(os.path.join(slot_root, "slots", bad["version"])), "실패한 슬롯은 지운다")
    check(ota_apply.current_version(slot_root) == good["version"], "current 는 여전히 정상 버전")

    # 두 번째 정상 버전 → previous 가 생기고 rollback 이 돌아간다
    r4 = ota_apply.install(slot_root, "1.2.0", base_url + "/" + good["url"], good["sha256"], good["size"])
    check(r4.ok, "두 번째 정상 설치")
    st = ota_apply.read_state(slot_root)
    check(st["current"] == "1.2.0" and st["previous"] == good["version"], f"state: current 1.2.0, previous {good['version']}: {st}")
    back = ota_apply.rollback(slot_root)
    check(back == good["version"] and ota_apply.current_version(slot_root) == good["version"], f"rollback → {back}")
    check(os.readlink(os.path.join(slot_root, "current")) == os.path.join("slots", good["version"]), "rollback 뒤 current 링크도 이전 슬롯")


# ---------- 5~6: 함대 + rollout --manifest ----------
def metrics_fixed():
    return {"cpu_pct": 1.0, "temp_c": 2.0, "mem_pct": 3.0, "rssi": -50, "loop_hz": None, "wake_p99_us": None}


def start_fleet(work, count, period_s=0.05):
    agents = []
    for i in range(count):
        device_id = f"a-{i + 1:03d}"
        kind = "virtual"
        if i == 0:
            device_id = "real-pi"   # 이름순이면 맨 앞에 올 이름 — kind=real 이라 맨 뒤로 가야 한다
            kind = "real"
        agent = DeviceAgent(device_id, "localhost", 1883, period_s, metrics_fixed, fw_version="1.0.0",
                            slot_root=os.path.join(work, "fleet-slots", device_id), kind=kind)
        agent.start()
        agents.append(agent)
    return agents


def stop_fleet(agents):
    for agent in agents:
        agent.running = False
    for agent in agents:
        if agent.thread is not None:
            agent.thread.join(timeout=1.0)


def test_fleet_good(agents, manifest_path):
    m = rollout.load_manifest(manifest_path)
    check(m["url"].startswith("http://127.0.0.1"), f"매니페스트의 상대 url 이 절대 주소가 된다: {m['url']}")
    result = rollout.run_rollout(version=m["version"], stages=m["rollout"]["stages_pct"], apply_s=0.0, health_wait=0.2, max_fail=0,
                                 bad=False, discover_s=0.3, broker="localhost", port=1883, db="", out="",
                                 manifest=m, apply_timeout_s=10.0)
    check(result is not None and result["devices"] == 20, "대상 20대")
    check(result["success"] is True and result["updated_devices"] == 20, f"정상 산출물: 성공, 20/20 (got {result['updated_devices']})")
    check(result["mode"] == "artifact" and result["manifest"]["sha256"] == m["sha256"], "결과에 산출물 정보가 남는다")
    check(result["real_devices"] == ["real-pi"], f"실물 장치가 표시된다: {result['real_devices']}")
    # 실물은 마지막 순서: 첫 단계(5% = 1대) 에 실물이 없어야 한다
    first_stage = [e["event"] for e in result["timeline"] if e["event"].startswith("단계 5%: 1대에 ota 전송")]
    check(len(first_stage) == 1 and "실물" not in first_stage[0], f"1단계에 실물 없음: {first_stage}")
    last_stage = [e["event"] for e in result["timeline"] if e["event"].startswith("단계 100%") and "ota 전송" in e["event"]]
    check(len(last_stage) == 1 and "실물 1대 포함" in last_stage[0], f"실물은 마지막 단계: {last_stage}")
    check(all(a.fw_version == m["version"] and a.state == "ok" for a in agents), "20대 모두 새 버전·ok")
    check(all(ota_apply.current_version(a.slot_root) == m["version"] for a in agents), "20대 모두 current 슬롯이 새 버전")
    check(all(a.ota_stage == "switched" for a in agents), "ota_stage 가 switched")
    return m["version"]


def test_fleet_bad(agents, manifest_bad_path, good_version):
    m = rollout.load_manifest(manifest_bad_path)
    result = rollout.run_rollout(version=m["version"], stages=[5, 50, 100], apply_s=0.0, health_wait=0.2, max_fail=0,
                                 bad=False, discover_s=0.3, broker="localhost", port=1883, db="", out="",
                                 manifest=m, apply_timeout_s=10.0)
    canary = int(math.ceil(20 * 5 / 100.0))
    check(result["success"] is False, "나쁜 산출물은 실패로 끝난다")
    check(result["updated_devices"] == canary, f"닿은 장치는 1단계 {canary}대뿐 (got {result['updated_devices']})")
    check(result["rollback_s"] is not None and result["rollback_s"] < 5.0, f"롤백 시간 측정 {result['rollback_s']}")
    check(any("설치 실패" in e["event"] for e in result["timeline"]), "타임라인에 '설치 실패'(자가 점검) 가 남는다")
    check(all(a.fw_version == good_version and a.state == "ok" for a in agents), "모두 이전 버전·ok 로 복귀")
    real = [a for a in agents if a.kind == "real"][0]
    check(real.ota_stage == "switched" and real.ota_error is None, "실물은 나쁜 산출물에 닿지 않았다")
    check(all(ota_apply.current_version(a.slot_root) == good_version for a in agents), "current 슬롯은 전부 이전 정상 버전")


# ---------- 6b: 두 번째 릴리스 뒤에 온 깨진 패키지 (11/11) ----------
def test_rollback_after_rejected_install(base_url, good, bad, work):
    """장치에 정상 버전이 둘(이전 1.1.0, 현재 1.2.0) 깔린 뒤 깨진 패키지가 온다 → 자가 점검이 거부 → 배포기가 ota_rollback 을 보낸다.
    기대: 현재 버전(1.2.0) 그대로. 거부한 패키지는 current 를 건드린 적이 없으므로 되돌릴 슬롯이 없다.
    고치기 전: previous 슬롯이 있다는 이유로 1.1.0 으로 한 단계 더 내려갔다 (슬롯이 비어 있던 기존 시험에서는 안 보였다)."""
    slot_root = os.path.join(work, "rb-slots")
    agent = DeviceAgent("rb-1", "localhost", 1883, 0.05, metrics_fixed, fw_version="1.0.0", slot_root=slot_root)
    agent.start()
    try:
        agent.apply_ota_artifact(good["version"], base_url + "/" + good["url"], good["sha256"], good["size"])
        agent.apply_ota_artifact("1.2.0", base_url + "/" + good["url"], good["sha256"], good["size"])
        st = ota_apply.read_state(slot_root)
        check(agent.fw_version == "1.2.0" and st["current"] == "1.2.0" and st["previous"] == good["version"],
              f"준비: 현재 1.2.0, 이전 {good['version']} (got fw={agent.fw_version} state={st})")
        agent.apply_ota_artifact(bad["version"], base_url + "/" + bad["url"], bad["sha256"], bad["size"])
        check(agent.state == "fault" and agent.ota_error is not None and "selftest" in agent.ota_error, f"깨진 패키지는 거부되고 fault 로 알린다: {agent.state} {agent.ota_error}")
        check(ota_apply.current_version(slot_root) == "1.2.0", "거부 직후에도 current 는 1.2.0")
        BROKER.publish(agent.topic_cmd, json.dumps({"cmd": "ota_rollback"}).encode("utf-8"), 1, False)
        st = ota_apply.read_state(slot_root)
        check(agent.state == "ok" and agent.fw_version == "1.2.0", f"롤백 명령 뒤: 상태 ok, 버전은 그대로 1.2.0 (got {agent.state} {agent.fw_version})")
        check(st["current"] == "1.2.0" and st["previous"] == good["version"], f"슬롯도 그대로: current 1.2.0, previous {good['version']} (got {st})")
        check(os.readlink(os.path.join(slot_root, "current")) == os.path.join("slots", "1.2.0"), "current 링크도 1.2.0")
        # 설치가 '성공'한 뒤의 롤백은 여전히 이전 슬롯으로 간다 (같은 단계의 다른 장치가 비정상이라 배포기가 되돌리는 경우)
        BROKER.publish(agent.topic_cmd, json.dumps({"cmd": "ota_rollback"}).encode("utf-8"), 1, False)
        check(agent.fw_version == good["version"] and ota_apply.current_version(slot_root) == good["version"],
              f"성공한 설치 뒤의 롤백은 이전 버전으로: {agent.fw_version}")
    finally:
        stop_fleet([agent])


# ---------- 7: 자율 업데이트 ----------
def test_auto_update(work, base_url, good_manifest_path):
    slot_root = os.path.join(work, "auto-slots")
    agent = DeviceAgent("auto-1", "localhost", 1883, 0.05, metrics_fixed, fw_version="0.0.0", slot_root=slot_root, kind="real")
    agent.running = True
    agent.auto_update = {"url": base_url + "/manifest.json", "poll_s": 600, "window": None}
    installed = agent.auto_update_once()
    check(installed is True and agent.fw_version == "1.1.0" and agent.state == "ok", f"자율 업데이트 1회: 설치 {installed}, fw {agent.fw_version}")
    check(agent.auto_update_once() is False, "같은 버전이면 아무것도 안 한다")
    agent.auto_update["window"] = (3, 5)
    in_w = agent.in_window(now=time.mktime((2026, 11, 10, 4, 0, 0, 0, 0, -1)))
    out_w = agent.in_window(now=time.mktime((2026, 11, 10, 12, 0, 0, 0, 0, -1)))
    check(in_w is True and out_w is False, f"시간대 판정: 04시 {in_w}, 12시 {out_w}")
    agent.auto_update["window"] = (23, 2)
    check(agent.in_window(now=time.mktime((2026, 11, 10, 0, 30, 0, 0, 0, -1))) is True, "자정을 넘기는 창(23~2)에 00:30 은 안")
    # 파일 경로 매니페스트도 된다 (file://)
    agent2 = DeviceAgent("auto-2", "localhost", 1883, 0.05, metrics_fixed, fw_version="0.0.0",
                         slot_root=os.path.join(work, "auto2-slots"), kind="real")
    agent2.running = True
    agent2.auto_update = {"url": "file://" + good_manifest_path, "poll_s": 600, "window": None}
    check(agent2.auto_update_once() is True and agent2.fw_version == "1.1.0", "file:// 매니페스트로도 설치된다")


def test_arch_and_hook(base_url, good, badhook, work):
    import platform
    me = platform.machine()
    entry = {"url": "top.tar.gz", "sha256": "top", "size": 1,
             "arch": {me: {"url": "mine.tar.gz", "sha256": "mine", "size": 2}, "other-arch": {"url": "other.tar.gz", "sha256": "o", "size": 3}}}
    check(pick_artifact(entry)["url"] == "mine.tar.gz", "내 아키텍처 항목을 고른다")
    check(pick_artifact(entry, machine="nope")["url"] == "top.tar.gz", "없는 아키텍처면 최상위 url")
    check(pick_artifact({"url": "only.tar.gz"})["url"] == "only.tar.gz", "arch 맵이 없으면 최상위 url")
    m = rollout.load_manifest(base_url + "/manifest.json")
    check(all(e["url"].startswith("http://") for e in m.get("arch", {}).values()) or not m.get("arch"), "arch 항목의 상대 url 도 절대 주소가 된다")

    slot_root = os.path.join(work, "hook-slots")
    r1 = ota_apply.install(slot_root, good["version"], base_url + "/" + good["url"], good["sha256"], good["size"])
    check(r1.ok, "훅 테스트 준비: 정상 설치")
    r2 = ota_apply.install(slot_root, badhook["version"], base_url + "/" + badhook["url"], badhook["sha256"], badhook["size"])
    check(not r2.ok and r2.stage == "post_switch_failed_rolled_back" and "post_switch" in r2.error,
          f"훅 실패 → 스스로 되돌림: stage={r2.stage} err={r2.error[:50]}")
    check(ota_apply.current_version(slot_root) == good["version"], "훅 실패 뒤 current 는 이전 정상 버전")
    check(os.readlink(os.path.join(slot_root, "current")) == os.path.join("slots", good["version"]), "링크도 이전 슬롯")


if __name__ == "__main__":
    work = tempfile.mkdtemp(prefix="ota-test-")
    pkg_dir = os.path.join(work, "release")
    os.makedirs(pkg_dir)
    good_path, good = make_package(pkg_dir, "1.1.0")
    bad_path, bad = make_package(pkg_dir, "1.1.0-bad", bad=True)
    badhook_path, badhook = make_package(pkg_dir, "1.1.0-badhook", bad_hook=True)
    server, base_url = serve(pkg_dir)
    BROKER.reset()
    agents = []
    try:
        test_relative_slot_root(base_url, good, work)
        test_apply_unit(base_url, good, bad, work)
        agents = start_fleet(work, 20)
        time.sleep(0.2)
        v = test_fleet_good(agents, base_url + "/manifest.json")
        test_fleet_bad(agents, base_url + "/manifest-bad.json", v)
        test_rollback_after_rejected_install(base_url, good, bad, work)
        test_auto_update(work, base_url, good_path)
        test_arch_and_hook(base_url, good, badhook, work)
    finally:
        stop_fleet(agents)
        server.shutdown()
        shutil.rmtree(work, ignore_errors=True)
    if fail_count == 0:
        print("OK: ota artifact")
        sys.exit(0)
    print(f"FAILED: {fail_count}")
    sys.exit(1)
