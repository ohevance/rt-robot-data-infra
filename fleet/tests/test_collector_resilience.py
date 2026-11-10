#!/usr/bin/env python3
"""수집기 내성 테스트 — 가짜 브로커 + 가짜 DB 위에서 "DB 가 죽었다 살았다"를 흉내 낸다.

확인하는 것
  1) 평소: 1초 묶음이 telemetry 에 들어가고 backlog 는 0
  2) DB 죽음: 쓰기가 실패하면 묶음이 backlog 에 남고 db_errors 가 센다. 데이터는 버리지 않는다
  3) DB 복귀: 다음 flush 에서 오래된 묶음부터 전부 들어간다 (순서 유지), backlog 0
  4) 상한: MAX_BACKLOG_ROWS 를 넘으면 가장 오래된 묶음을 버리고 backlog_dropped 로 센다
  5) --qos 1 이면 지속 세션(clean_session=False)으로 붙고 telemetry 를 QoS 1 로 구독한다
  6) 옛 스키마(003 미적용)면 check_schema 가 False 를 돌려준다 (안내 후 종료용)
  7) 종료(SIGTERM/Ctrl+C) 때 아직 묶지 않은 pending 행을 마지막으로 적재한다 (11/04 실측에서 잃었던 "마지막 1초")
  9) 꺼진 장치의 devices.last_seen 은 새로워지지 않는다 (11/10 EC2 첫 운영: 실제 1대인데 대시보드가 4대로 셌다)
  8) main() 한 바퀴 스모크: 인자 → 잠금 → 시그널 핸들러 등록 → 루프 → shutdown 까지 실제 진입점이 깨지지 않았는가
     (11/05 CI 에서 request_stop 누락 NameError 가 통합 테스트에서만 드러났다 — 진입점은 단위 테스트가 한 번은 타야 한다)

실행:  python3 fleet/tests/test_collector_resilience.py
"""
import json
import os
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import fake_mqtt  # noqa: E402
import fake_psycopg  # noqa: E402

fake_mqtt.install()
fake_psycopg.install()
BROKER = fake_mqtt.BROKER

sys.path.insert(0, os.path.join(HERE, "..", "collector"))
import collector  # noqa: E402
from collector import Collector  # noqa: E402

fail_count = 0


def check(condition, message):
    global fail_count
    if not condition:
        print("FAIL:", message)
        fail_count += 1


def publish_telemetry(device_id, seq):
    payload = json.dumps({"device_id": device_id, "seq": seq, "ts_ns": time.time_ns() - 1_000_000,
                          "cpu_pct": 1, "temp_c": 2, "mem_pct": 3, "rssi": -1, "fw_version": "1.0.0", "state": "ok"})
    BROKER.publish(f"fleet/{device_id}/telemetry", payload.encode("utf-8"), 0, False)


def seqs_in_store():
    return [row[2] for row in fake_psycopg.STORE["telemetry"]]


def test_db_outage_and_recovery():
    BROKER.reset()
    fake_psycopg.reset()
    c = Collector("localhost", 1883, "postgresql://fake", dry_run=False)
    check(c.check_schema() is True, "새 스키마면 check_schema True")

    # 1) 평소
    for seq in range(3):
        publish_telemetry("a", seq)
    s = c.flush_once()
    check(s["msgs"] == 3 and s["backlog_rows"] == 0 and s["db_errors"] == 0, "평소: 3행 적재, backlog 0")
    check(len(fake_psycopg.STORE["telemetry"]) == 3, "telemetry 에 3행")
    check(len(fake_psycopg.STORE["collector_stats"]) == 1, "통계 한 줄")
    check(fake_psycopg.STORE["collector_stats"][0][8] == 0, "통계에 backlog_rows=0 이 들어간다")

    # 2) DB 죽음
    fake_psycopg.FAIL["write"] = True
    for seq in range(3, 5):
        publish_telemetry("a", seq)
    s = c.flush_once()
    check(s["backlog_rows"] == 2 and s["db_errors"] == 1, "DB 죽음: 2행이 backlog, 오류 1")
    check(c.conn is None, "실패하면 연결을 버리고 다음에 새로 붙는다")
    for seq in range(5, 7):
        publish_telemetry("a", seq)
    s = c.flush_once()
    check(s["backlog_rows"] == 4 and s["db_errors"] == 2, "계속 죽어 있음: backlog 4, 오류 2")
    check(len(fake_psycopg.STORE["telemetry"]) == 3, "죽은 동안 DB 에는 아무것도 안 들어갔다")
    check(len(fake_psycopg.STORE["collector_stats"]) == 1, "죽은 동안 통계도 못 쓴다 (연결 없음)")

    # 3) DB 복귀
    fake_psycopg.FAIL["write"] = False
    publish_telemetry("a", 7)
    s = c.flush_once()
    check(s["backlog_rows"] == 0, "복귀: backlog 가 0 으로")
    check(seqs_in_store() == [0, 1, 2, 3, 4, 5, 6, 7], "오래된 것부터 순서대로 전부 들어갔다 (유실 0)")
    check(c.backlog_dropped == 0, "버린 행 없음")
    check(len(fake_psycopg.STORE["collector_stats"]) == 2, "복귀 뒤 통계가 다시 써진다")


def test_backlog_limit():
    BROKER.reset()
    fake_psycopg.reset()
    c = Collector("localhost", 1883, "postgresql://fake", dry_run=False)
    original_limit = collector.MAX_BACKLOG_ROWS
    collector.MAX_BACKLOG_ROWS = 5
    fake_psycopg.FAIL["write"] = True
    for batch_index in range(3):
        for k in range(3):
            publish_telemetry("b", batch_index * 3 + k)
        c.flush_once()
    check(c.backlog_rows == 3 and c.backlog_dropped == 6, "상한 5: 묶음 3개(9행) 중 오래된 2개(6행)를 버리고 3행만 남김")
    fake_psycopg.FAIL["write"] = False
    c.flush_once()
    check(seqs_in_store() == [6, 7, 8], "복귀하면 남아 있던 마지막 묶음만 들어간다")
    collector.MAX_BACKLOG_ROWS = original_limit


def test_persistent_session_option():
    BROKER.reset()
    fake_psycopg.reset()
    c0 = Collector("localhost", 1883, "postgresql://fake", dry_run=True, qos=0)
    check(c0.client.clean_session is True, "qos 0: 보통 세션")
    check(("fleet/+/telemetry", 0) in c0.client.subscriptions, "qos 0 으로 구독")
    c1 = Collector("localhost", 1883, "postgresql://fake", dry_run=True, qos=1)
    check(c1.client.clean_session is False and c1.client.client_id == "collector", "qos 1: 지속 세션 + 고정 client_id")
    check(("fleet/+/telemetry", 1) in c1.client.subscriptions, "qos 1 로 구독")


def test_shutdown_flushes_pending():
    BROKER.reset()
    fake_psycopg.reset()
    c = Collector("localhost", 1883, "postgresql://fake", dry_run=False)
    c.check_schema()
    publish_telemetry("z", 0)
    publish_telemetry("z", 1)
    check(len(fake_psycopg.STORE["telemetry"]) == 0, "아직 flush 전: DB 에 0행 (pending 에 2행)")
    collector.shutdown(c)
    check(seqs_in_store() == [0, 1], "shutdown 이 pending 2행을 마지막으로 적재한다")
    check(c.client.connected is False, "shutdown 뒤 브로커 연결은 끊겨 있다 (지속 세션이면 그 뒤는 브로커가 보관)")


def test_old_schema_detected():
    BROKER.reset()
    fake_psycopg.reset()
    fake_psycopg.FAIL["schema_old"] = True
    c = Collector("localhost", 1883, "postgresql://fake", dry_run=False)
    check(c.check_schema() is False, "003 미적용 스키마면 False (migrate.py 안내)")


def test_stale_device_last_seen_not_refreshed():
    """장치 old 는 한 번 보내고 조용해지고, 장치 live 는 계속 보낸다. 5초가 지난 뒤(시계를 직접 민다) flush 하면
    devices 표에서 live 의 last_seen 만 새로워지고 old 의 것은 처음 값 그대로여야 한다."""
    BROKER.reset()
    fake_psycopg.reset()
    c = Collector("localhost", 1883, "postgresql://fake", dry_run=False)
    publish_telemetry("old", 0)
    publish_telemetry("live", 0)
    s = c.flush_once()
    check(s["online"] == 2, f"처음엔 둘 다 온라인 (got {s['online']})")
    old_first = fake_psycopg.STORE["devices"]["old"][2]
    live_first = fake_psycopg.STORE["devices"]["live"][2]
    c.last_seen["old"] -= 6.0                      # old 가 6초 전에 마지막으로 보냈다고 치고
    time.sleep(0.01)
    publish_telemetry("live", 1)
    s = c.flush_once()
    check(s["online"] == 1, f"6초 조용한 장치는 온라인 수에서 빠진다 (got {s['online']})")
    check(fake_psycopg.STORE["devices"]["old"][2] == old_first, "꺼진 장치의 last_seen 은 그대로다")
    check(fake_psycopg.STORE["devices"]["live"][2] > live_first, "살아 있는 장치의 last_seen 은 새로워진다")


def test_main_entry_smoke():
    """main() 을 끝까지 한 번 통과시킨다. STOP 플래그를 미리 세워 두면 while 이 바로 끝나 shutdown 까지 간다.
    시그널 핸들러도 직접 불러 본다(request_stop 이 없으면 여기서 NameError)."""
    BROKER.reset()
    fake_psycopg.reset()
    collector.single_instance.LOCK_DIR = os.path.join(HERE, "..", "logs", "test_lock")   # 진짜 수집기의 잠금과 겹치지 않게
    saved_argv = sys.argv
    sys.argv = ["collector.py", "--broker", "localhost", "--db", "postgresql://fake", "--interval", "0.01"]
    try:
        collector.STOP["requested"] = False
        collector.request_stop(15, None)                       # SIGTERM 핸들러: 플래그만 세운다
        check(collector.STOP["requested"] is True, "request_stop 이 STOP 플래그를 세운다")
        rc = collector.main()                                  # 플래그가 이미 True → 루프 0바퀴 → shutdown → 0
        check(rc == 0, f"main() 이 0 으로 끝난다 (실제 {rc})")
    finally:
        sys.argv = saved_argv
        collector.STOP["requested"] = False


if __name__ == "__main__":
    test_db_outage_and_recovery()
    test_backlog_limit()
    test_persistent_session_option()
    test_shutdown_flushes_pending()
    test_old_schema_detected()
    test_stale_device_last_seen_not_refreshed()
    test_main_entry_smoke()
    if fail_count == 0:
        print("OK: collector resilience")
        sys.exit(0)
    print(f"FAILED: {fail_count}")
    sys.exit(1)
