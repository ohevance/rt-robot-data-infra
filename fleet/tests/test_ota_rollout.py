#!/usr/bin/env python3
"""OTA 단계 배포 끝-대-끝 테스트 — 가짜 브로커 위에서 가상 장치 20대 ↔ rollout.py 를 실제로 돌린다.

확인하는 것
  1) 정상 펌웨어: 5% → 50% → 100% 세 단계를 모두 통과, 20대 전부 새 버전, 롤백 없음
  2) 나쁜 펌웨어: 1단계(5% = 1대)에서 헬스 게이트가 fault 를 잡아 롤백. 나쁜 버전이 닿은 장치는 1대뿐,
     롤백 뒤 20대 모두 이전 버전·ok. 롤백 시간이 측정된다
  3) 중간에 장치 하나가 적용 실패(시간 초과) → 롤백

실행:  python3 fleet/tests/test_ota_rollout.py   (약 3~5초)
"""
import math
import os
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import fake_mqtt  # noqa: E402

fake_mqtt.install()
BROKER = fake_mqtt.BROKER

sys.path.insert(0, os.path.join(HERE, "..", "agent"))
sys.path.insert(0, os.path.join(HERE, "..", "ota"))
from device_agent import DeviceAgent  # noqa: E402
import rollout  # noqa: E402

fail_count = 0


def check(condition, message):
    global fail_count
    if not condition:
        print("FAIL:", message)
        fail_count += 1


def metrics_fixed():
    return {"cpu_pct": 1.0, "temp_c": 2.0, "mem_pct": 3.0, "rssi": -50, "loop_hz": None, "wake_p99_us": None}


def start_fleet(count, period_s=0.05):
    """가상 장치 count 대를 띄운다 (스레드). period_s 마다 텔레메트리를 보낸다"""
    agents = []
    for i in range(count):
        agent = DeviceAgent(f"t-{i + 1:03d}", "localhost", 1883, period_s, metrics_fixed, fw_version="1.0.0")
        agent.start()
        agents.append(agent)
    return agents


def stop_fleet(agents):
    for agent in agents:
        agent.running = False
    for agent in agents:
        if agent.thread is not None:
            agent.thread.join(timeout=1.0)


def run(version, bad, agents):
    return rollout.run_rollout(version=version, stages=[5, 50, 100], apply_s=0.05, health_wait=0.2, max_fail=0,
                               bad=bad, discover_s=0.3, broker="localhost", port=1883, db="", out="")


def test_good_firmware(agents):
    result = run("1.1.0", False, agents)
    check(result is not None, "장치를 찾았다")
    check(result["devices"] == 20, "대상 20대")
    check(result["success"] is True, "정상 펌웨어는 성공")
    check(result["updated_devices"] == 20, "20대 전부 새 버전을 받았다")
    check(result["rollback_s"] is None, "롤백 없음")
    check(all(a.fw_version == "1.1.0" and a.state == "ok" for a in agents), "모든 장치 fw=1.1.0, ok")
    stage_lines = [e["event"] for e in result["timeline"] if "전원 적용 완료" in e["event"]]
    check(len(stage_lines) == 3, "세 단계 모두 '적용 완료' 기록")


def test_bad_firmware(agents):
    result = run("1.2.0-bad", True, agents)
    check(result["success"] is False, "나쁜 펌웨어는 실패로 끝난다")
    canary = int(math.ceil(20 * 5 / 100.0))
    check(result["updated_devices"] == canary, f"나쁜 버전이 닿은 장치는 1단계 {canary}대뿐")
    check(result["rollback_s"] is not None and result["rollback_s"] < 5.0, "롤백 시간이 측정된다 (5초 미만)")
    check(all(a.fw_version == "1.1.0" and a.state == "ok" for a in agents), "롤백 뒤 20대 모두 1.1.0, ok")
    check(any("롤백 결정" in e["event"] for e in result["timeline"]), "타임라인에 롤백 결정이 남는다")


def test_apply_timeout(agents):
    # 장치 하나를 "ota 를 무시하는" 상태로 만든다 (적용 스레드가 이미 있는 것처럼) → 적용 시간 초과 → 롤백
    victim = agents[0]
    victim.ota_thread = object()
    result = rollout.run_rollout(version="1.3.0", stages=[5, 100], apply_s=0.05, health_wait=0.1, max_fail=0,
                                 bad=False, discover_s=0.3, broker="localhost", port=1883, db="", out="",
                                 apply_timeout_s=1.0)
    victim.ota_thread = None
    check(result["success"] is False, "적용 시간 초과면 실패")
    check(any("적용 시간 초과" in e["event"] for e in result["timeline"]), "타임라인에 시간 초과가 남는다")
    check(all(a.fw_version == "1.1.0" for a in agents), "롤백 뒤 아무도 1.3.0 이 아니다")


if __name__ == "__main__":
    BROKER.reset()
    agents = start_fleet(20)
    time.sleep(0.2)
    try:
        test_good_firmware(agents)
        test_bad_firmware(agents)
        test_apply_timeout(agents)   # 적용 대기 상한을 1초로 줘서 짧게 돈다
    finally:
        stop_fleet(agents)
    if fail_count == 0:
        print("OK: ota rollout")
        sys.exit(0)
    print(f"FAILED: {fail_count}")
    sys.exit(1)
