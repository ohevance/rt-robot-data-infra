#!/usr/bin/env python3
"""fleet 논리 단위 테스트 — 브로커·DB 없이 돈다 (paho 를 fake_mqtt 로 바꿔 끼움).

확인하는 것
  1) parse_telemetry: 정상 JSON → 행 + 전달 지연, 깨진 JSON → None
  2) DeviceAgent 의 store-and-forward: 끊긴 동안 tick() 은 버퍼에 쌓고, 재접속(on_connect) 때 QoS 1 로 전부 재전송
  3) DeviceAgent 의 명령: ping · health · ota(정상/나쁜 펌웨어) · ota_rollback
  4) Collector.flush_once(dry-run): 메시지 수·온라인 수·지연 통계가 맞게 나온다
  5) 유언(LWT): 에이전트가 갑자기 죽으면 브로커가 offline 을 발행하고 수집기가 그것을 이벤트로 받는다
  6) 보관(retained) 상태는 이벤트가 아니다 · 수집기 단일 인스턴스 잠금
  9) Nagle 모형(fleet/tools/nagle_model.py): 간격이 왕복보다 길면 왕복 그대로, 짧으면 2~3배, 양쪽 NODELAY 면 다시 왕복 그대로
  8) pi_agent 는 SIGTERM(systemd stop·재부팅) 에 "정상 종료" 길로 끝난다 — offline 을 스스로 남긴다 (별도 프로세스로 확인)
  7) 왕복 시간 도구(fleet/tools/mqtt_rtt.py): 보낸 것이 전부 되돌아오고 번호로 짝이 맞는다, 통계가 맞다, 수집기가 구독하는 토픽을 건드리지 않는다

실행:  python3 fleet/tests/test_fleet_logic.py
"""
import json
import os
import signal
import socket
import subprocess
import sys
import tempfile
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import fake_mqtt  # noqa: E402

fake_mqtt.install()
BROKER = fake_mqtt.BROKER

sys.path.insert(0, os.path.join(HERE, "..", "agent"))
sys.path.insert(0, os.path.join(HERE, "..", "collector"))
sys.path.insert(0, os.path.join(HERE, "..", "tools"))
from device_agent import DeviceAgent  # noqa: E402
from collector import Collector, parse_telemetry, acquire_single_instance_lock  # noqa: E402
import mqtt_rtt  # noqa: E402
import nagle_model  # noqa: E402

fail_count = 0


def check(condition, message):
    global fail_count
    if not condition:
        print("FAIL:", message)
        fail_count += 1


def metrics_fixed():
    return {"cpu_pct": 1.0, "temp_c": 2.0, "mem_pct": 3.0, "rssi": -50, "loop_hz": None, "wake_p99_us": None}


def send_cmd(agent, cmd_dict):
    """브로커를 거쳐 에이전트에 명령을 넣고, 에이전트가 보낸 마지막 답(cmd_reply)을 돌려준다"""
    BROKER.publish(agent.topic_cmd, json.dumps(cmd_dict).encode("utf-8"), 1, False)
    last = agent.client.published[-1]
    check(last[0] == agent.topic_cmd_reply, "명령마다 cmd_reply 가 나간다")
    return json.loads(last[1])


def wait_ota_done(agent, timeout_s=2.0):
    """OTA 적용 스레드가 끝날 때까지 기다린다"""
    deadline = time.monotonic() + timeout_s
    while agent.ota_thread is not None and time.monotonic() < deadline:
        time.sleep(0.01)


# ---------------------------------------------------------------------------
def test_parse():
    ts = time.time_ns() - 5_000_000  # 5 ms 전에 측정
    good = json.dumps({"device_id": "d1", "seq": 3, "ts_ns": ts, "cpu_pct": 10.0, "temp_c": 40.0,
                       "mem_pct": 20.0, "rssi": -60, "fw_version": "1.0.0", "state": "ok"}).encode()
    parsed = parse_telemetry(good, time.time_ns())
    check(parsed is not None, "정상 JSON 은 파싱된다")
    row, latency_ms = parsed
    check(row[1] == "d1" and row[2] == 3, "device_id, seq 가 행에 들어간다")
    check(4.0 < latency_ms < 500.0, "전달 지연이 ms 단위로 계산된다 (약 5 ms)")
    check(parse_telemetry(b"{not json", time.time_ns()) is None, "깨진 JSON 은 None")
    check(parse_telemetry(json.dumps({"seq": 1}).encode(), time.time_ns()) is None, "필수 키 없으면 None")


def test_store_and_forward():
    BROKER.reset()
    agent = DeviceAgent("d1", "localhost", 1883, 1.0, metrics_fixed)
    client = agent.client
    check(client.will is not None and client.will[1] == "offline", "유언(LWT) 이 offline 으로 설정된다")

    # 아직 접속 전(끊긴 상태)에서 3번 tick → 버퍼 3, 발행 0
    check(client.is_connected() is False, "start 전에는 끊긴 상태")
    agent.tick()
    agent.tick()
    agent.tick()
    check(len(agent.buffer) == 3 and agent.buffered_total == 3, "끊긴 동안은 버퍼에 쌓인다")
    check(len(client.published) == 0, "끊긴 동안은 발행하지 않는다")

    # 접속 → online 발행 + 구독 + 버퍼 3개를 QoS 1 로 재전송
    client.finish_connect()
    topics = [p[0] for p in client.published]
    check(topics[0] == "fleet/d1/status" and client.published[0][1] == "online", "접속하면 online 을 먼저 발행")
    resent = [p for p in client.published if p[0] == "fleet/d1/telemetry"]
    check(len(resent) == 3 and all(p[2] == 1 for p in resent), "버퍼 3개가 QoS 1 로 재전송된다")
    check(agent.flushed_total == 3 and len(agent.buffer) == 0, "재전송 뒤 버퍼는 비고 카운터는 3")
    check(client.wants("fleet/d1/cmd"), "명령 토픽을 구독한다")

    # 붙은 상태에서 tick → 바로 발행 (QoS 0), seq 는 계속 증가
    agent.tick()
    last = client.published[-1]
    check(last[0] == "fleet/d1/telemetry" and last[2] == 0, "붙어 있으면 바로 발행")
    check(json.loads(last[1])["seq"] == 3, "seq 는 0,1,2 다음 3")

    # 브로커가 죽었다 → on_disconnect → reconnects 1, 그동안 버퍼 → 돌아오면 재전송
    agent.running = True  # start() 를 안 했으므로 "돌고 있다"고 표시해야 재접속으로 센다
    BROKER.disconnect_all()
    agent.tick()
    agent.tick()
    check(agent.reconnects == 1 and len(agent.buffer) == 2, "브로커 끊김: 재접속 1회 예정, 버퍼 2")
    BROKER.reconnect_all()
    check(len(agent.buffer) == 0 and agent.flushed_total == 5, "돌아오면 2개 더 재전송 (누적 5)")


def test_commands_and_ota():
    BROKER.reset()
    agent = DeviceAgent("d2", "localhost", 1883, 1.0, metrics_fixed, fw_version="1.0.0")
    agent.client.finish_connect()

    reply = send_cmd(agent, {"cmd": "ping"})
    check(reply["ok"] is True and "seq" in reply, "ping 에 ok 와 seq 로 답한다")

    reply = send_cmd(agent, {"cmd": "health"})
    check(reply["ok"] is True and reply["fw_version"] == "1.0.0" and reply["state"] == "ok", "health 는 버전·상태를 돌려준다")

    # 정상 OTA: updating → 새 버전, ok
    reply = send_cmd(agent, {"cmd": "ota", "version": "1.1.0", "apply_s": 0.05})
    check(reply["ok"] is True and reply["applying"] == "1.1.0", "ota 는 즉시 '적용 중' 으로 답한다")
    time.sleep(0.01)
    check(agent.state == "updating", "적용 중에는 state=updating (텔레메트리로 보인다)")
    wait_ota_done(agent)
    check(agent.fw_version == "1.1.0" and agent.state == "ok", "적용 뒤 새 버전, state=ok")
    check(agent.prev_fw_version == "1.0.0", "직전 버전을 롤백용으로 기억한다")

    # 적용 중에 또 ota 가 오면 거절
    send_cmd(agent, {"cmd": "ota", "version": "1.1.1", "apply_s": 0.2})
    reply = send_cmd(agent, {"cmd": "ota", "version": "1.1.2", "apply_s": 0.05})
    check(reply["ok"] is False, "적용 중 겹치는 ota 는 거절(ok=false)")
    wait_ota_done(agent)
    check(agent.fw_version == "1.1.1", "먼저 온 것만 적용된다")

    # 나쁜 펌웨어: 적용 뒤 fault → 롤백 → 직전 버전·ok
    send_cmd(agent, {"cmd": "ota", "version": "2.0.0-bad", "apply_s": 0.05, "bad": True})
    wait_ota_done(agent)
    check(agent.fw_version == "2.0.0-bad" and agent.state == "fault", "나쁜 펌웨어는 켜지자마자 fault")
    reply = send_cmd(agent, {"cmd": "ota_rollback"})
    check(reply["ok"] is True and reply["fw_version"] == "1.1.1", "롤백은 직전 버전으로")
    check(agent.fw_version == "1.1.1" and agent.state == "ok" and agent.prev_fw_version is None, "롤백 뒤 ok, 되돌릴 것 없음")
    reply = send_cmd(agent, {"cmd": "ota_rollback"})
    check(reply["ok"] is False, "되돌릴 버전이 없으면 롤백 거절")


def test_collector_dry_run():
    BROKER.reset()
    c = Collector("localhost", 1883, "postgresql://x", dry_run=True)
    check(c.client.wants("fleet/abc/telemetry") and c.client.wants("fleet/abc/status"), "수집기는 telemetry·status 를 구독")
    now = time.time_ns()
    for i in range(3):
        for seq in range(2):
            payload = json.dumps({"device_id": f"v{i}", "seq": seq, "ts_ns": now - 2_000_000,
                                  "cpu_pct": 1, "temp_c": 2, "mem_pct": 3, "rssi": -1,
                                  "fw_version": "1.0.0", "state": "ok"}).encode()
            BROKER.publish(f"fleet/v{i}/telemetry", payload, 0, False)
    BROKER.publish("fleet/v9/status", b"offline", 1, True)
    BROKER.publish("fleet/v0/telemetry", b"garbage", 0, False)
    s = c.flush_once()
    check(s["msgs"] == 6, "6개 메시지가 묶였다")
    check(s["online"] == 3, "3대가 온라인")
    check(s["bad"] == 1, "깨진 메시지 1개는 버려지고 세어진다")
    check(s["lat_p50"] is not None and 1.0 < s["lat_p50"] < 500.0, "전달 지연 통계가 ms 로 나온다")
    s2 = c.flush_once()
    check(s2["msgs"] == 0 and s2["online"] == 3, "비운 뒤에는 0 메시지, 온라인은 5초 동안 유지")


def test_lwt_reaches_collector():
    BROKER.reset()
    c = Collector("localhost", 1883, "postgresql://x", dry_run=True)
    agent = DeviceAgent("d3", "localhost", 1883, 1.0, metrics_fixed)
    agent.client.finish_connect()
    check(len(c.pending_status) == 1 and c.pending_status[0][1] == "online", "접속 online 이 수집기에 이벤트로 도착")
    BROKER.crash(agent.client)   # 갑자기 죽음 → 브로커가 유언을 발행
    check(len(c.pending_status) == 2 and c.pending_status[1][1] == "offline", "비정상 종료 → 브로커의 유언 offline 이 도착")


def test_retained_status_and_lock():
    BROKER.reset()
    BROKER.publish("fleet/old/status", b"offline", 1, True)   # 과거에 남은 보관 값
    c = Collector("localhost", 1883, "postgresql://x", dry_run=True)   # 구독하면 보관 값이 retain=1 로 내려온다
    check(c.retained_status_skipped == 1 and len(c.pending_status) == 0, "구독 때 내려온 보관 상태는 이벤트로 적지 않는다")
    BROKER.publish("fleet/old/status", b"online", 1, True)    # 지금 일어난 변화 (전달은 retain=0)
    check(len(c.pending_status) == 1 and c.pending_status[0][1] == "online", "살아 있는 상태 변화는 이벤트로 적는다")

    first = acquire_single_instance_lock()
    check(first is not None, "첫 수집기는 잠금을 잡는다")
    second = acquire_single_instance_lock()
    check(second is None, "두 번째 수집기는 잠금을 못 잡고 물러난다 (같은 client_id 충돌 방지)")
    first.close()


def test_mqtt_rtt_probe():
    BROKER.reset()
    c = Collector("localhost", 1883, "postgresql://x", dry_run=True)   # 수집기가 같이 붙어 있는 상황
    probe = mqtt_rtt.RttProbe("localhost", 1883, qos=0)
    probe.start(timeout_s=2.0)
    check(probe.topic.startswith("rtt/") and not probe.topic.startswith("fleet/"), f"왕복 토픽은 fleet/ 아래가 아니다: {probe.topic}")
    check(probe.wait_ready(timeout_s=2.0) is True, "탐침이 되돌아와 구독이 확인된다")
    probe.run(count=20, interval_s=0.0, payload_bytes=200, settle_s=0.5)
    values = probe.results(20)
    probe.stop()
    check(len(values) == 20 and all(v >= 0.0 for v in values), f"20개를 보내 20개가 되돌아왔다 (got {len(values)})")
    check(-1 in probe.rtt_ms and len(probe.rtt_ms) == 21, f"탐침(음수 번호)은 따로 적히고 결과 20개에 섞이지 않는다 (기록 {len(probe.rtt_ms)}개)")
    check(len(c.pending_rows) == 0 and c.dropped_bad == 0, "수집기는 왕복 메시지를 받지 않는다 (텔레메트리가 아니다)")
    stats = mqtt_rtt.summarize([5.0, 1.0, 3.0, 2.0, 4.0], 6)
    check(stats["sent"] == 6 and stats["received"] == 5 and stats["lost"] == 1, f"보낸 수·받은 수·잃은 수: {stats}")
    check(stats["min"] == 1.0 and stats["p50"] == 3.0 and stats["max"] == 5.0 and stats["mean"] == 3.0, f"최소·중앙값·최대·평균: {stats}")
    empty = mqtt_rtt.summarize([], 3)
    check(empty["received"] == 0 and empty["lost"] == 3 and empty["p50"] is None, "하나도 못 받으면 숫자는 None")
    values_100 = sorted(float(i) for i in range(1, 101))
    check(mqtt_rtt.percentile(values_100, 95) == 95.0 and mqtt_rtt.percentile(values_100, 99) == 99.0, "백분위수는 가장 가까운 순위")

    text = mqtt_rtt.to_json_text({"from": "시험", "rtt_ms": {"p50": 1.0}, "samples_ms": [1.0, 2.5, 3.0]})
    back = json.loads(text)
    check(back["samples_ms"] == [1.0, 2.5, 3.0] and back["from"] == "시험" and text.count("\n") < 10,
          f"결과 JSON 은 다시 읽히고, 개별 값은 한 줄에 적힌다 (줄 수 {text.count(chr(10))})")

    # --nodelay: 소켓이 열릴 때 TCP_NODELAY 를 건다 (가짜 브로커에는 소켓이 없으므로 콜백을 직접 불러 본다)
    class FakeSock:
        def __init__(self):
            self.options = []

        def setsockopt(self, level, name, value):
            self.options.append((level, name, value))
    plain = mqtt_rtt.RttProbe("localhost", 1883)
    check(getattr(plain.client, "on_socket_open", None) is None, "옵션이 없으면 소켓을 건드리지 않는다")
    fast = mqtt_rtt.RttProbe("localhost", 1883, nodelay=True)
    sock = FakeSock()
    fast.client.on_socket_open(fast.client, None, sock)
    check(sock.options == [(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)], f"--nodelay 는 TCP_NODELAY 를 건다: {sock.options}")


def test_nagle_model():
    """모형이 하는 말 셋 — 숫자가 아니라 '모양'을 확인한다 (왕복 285 ms 가정)"""
    one_way = 0.1425
    slow = nagle_model.simulate(one_way, 1.0, 50)                       # 간격 > 왕복
    check(all(abs(v - 285.0) < 0.01 for v in slow), f"간격이 왕복보다 길면 전부 왕복 그대로: {min(slow):.0f}~{max(slow):.0f}")
    fast = nagle_model.simulate(one_way, 0.2, 300)                      # 간격 < 왕복, Nagle 양쪽
    check(abs(min(fast) - 285.0) < 0.01, f"첫 메시지는 왕복 그대로: {min(fast):.0f}")
    p50 = nagle_model.quantile(fast, 50)
    check(2 * 285.0 <= p50 <= 3 * 285.0 and max(fast) <= 3 * 285.0 + 10.0, f"간격이 짧으면 중앙값이 왕복의 2~3배: p50 {p50:.0f}, max {max(fast):.0f}")
    both = nagle_model.simulate(one_way, 0.2, 300, nagle_client=False, nagle_broker=False)
    check(all(abs(v - 285.0) < 0.01 for v in both), "양쪽 NODELAY 면 간격이 짧아도 왕복 그대로")
    half = nagle_model.simulate(one_way, 0.2, 300, nagle_client=False, nagle_broker=True)
    check(285.0 < nagle_model.quantile(half, 50) < p50, f"클라이언트만 NODELAY 면 그 사이: p50 {nagle_model.quantile(half, 50):.0f}")


def test_pi_agent_sigterm():
    """pi_agent 를 별도 프로세스로 띄우고(가짜 브로커) SIGTERM 을 보낸다 — systemd 가 서비스를 멈출 때와 같다.
    기대: 종료 코드 0, "정상 종료" 줄이 찍힌다(= finally 의 agent.stop() 이 돌았다). 핸들러가 없으면 종료 코드가 -15 다."""
    agent_dir = os.path.join(HERE, "..", "agent")
    slot_dir = tempfile.mkdtemp(prefix="pi-agent-test-")
    code = ("import sys; sys.path.insert(0, %r); import fake_mqtt; fake_mqtt.install(); sys.path.insert(0, %r); import pi_agent; "
            "sys.argv = ['pi_agent.py', '--device-id', 't-pi', '--slot-root', %r, '--rate', '20']; sys.exit(pi_agent.main())"
            % (HERE, agent_dir, slot_dir))
    proc = subprocess.Popen([sys.executable, "-u", "-c", code], stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
    first = proc.stdout.readline()                 # 시작 줄이 찍힐 때까지 기다린다 (핸들러는 그 전에 걸린다)
    check("pi agent: t-pi" in first, f"시작 줄: {first.strip()[:80]}")
    time.sleep(0.3)                                # 몇 번 보내게 둔다
    proc.send_signal(signal.SIGTERM)
    try:
        rest, _ = proc.communicate(timeout=10)
    except subprocess.TimeoutExpired:
        proc.kill()
        rest = "(10초 안에 안 끝남)"
    check(proc.returncode == 0, f"SIGTERM 뒤 종료 코드 0 (got {proc.returncode})")
    check("정상 종료" in rest, f"정상 종료 줄이 찍힌다: {rest.strip()[-80:]}")


if __name__ == "__main__":
    test_parse()
    test_store_and_forward()
    test_commands_and_ota()
    test_collector_dry_run()
    test_lwt_reaches_collector()
    test_retained_status_and_lock()
    test_mqtt_rtt_probe()
    test_nagle_model()
    test_pi_agent_sigterm()
    if fail_count == 0:
        print("OK: fleet logic")
        sys.exit(0)
    print(f"FAILED: {fail_count}")
    sys.exit(1)
