#!/usr/bin/env python3
"""장애 주입·OTA 결과 JSON 을 읽어 "기대한 대로 복구됐나"를 판정한다 (CI 2단계와 integration.sh 의 마지막 단계).

규칙 (파일의 fault / version 필드로 구분)
  broker        : 유실 ≤ 장치 수 (브로커가 죽는 순간 소켓에 이미 실린 메시지 1개/장치는 QoS 0 에서 잃을 수 있다), 전 장치 복귀 시간 있음
  db            : 유실 0, backlog 0 복귀 시간 있음
  collector     : label 에 qos1 이 있으면 유실 0 / qos0 이면 유실 > 0 이어야 정상 (보호가 없음을 "보여 주는" 실험)
  bad_firmware  : 롤백 성공(success=false), 나쁜 버전이 닿은 장치 = 5% 단계(ceil) 만, 롤백 시간 있음
  ota (성공 배포) : success=true, 전 장치 새 버전

사용:  python3 fleet/chaos/assert_results.py build/fault_broker.json build/fault_db.json ...
종료 코드 0 = 전부 통과
"""
import json
import math
import sys

fail_count = 0


def check(condition, message):
    global fail_count
    mark = "ok  "
    if not condition:
        mark = "FAIL"
        fail_count += 1
    print(f"{mark}  {message}")


def assert_fault(r):
    fault = r["fault"]
    loss = r.get("loss") or {}
    lost = loss.get("lost")
    if fault == "broker":
        check(lost is not None and lost <= r["baseline_devices"], f"broker: 유실 {lost} ≤ 장치 수 {r['baseline_devices']}")
        check(r.get("recover_all_devices_s") is not None, f"broker: 전 장치 복귀 {r.get('recover_all_devices_s')}초")
    elif fault == "db":
        check(lost == 0, f"db: 유실 {lost} == 0")
        check(r.get("recover_backlog_drained_s") is not None, f"db: backlog 0 복귀 {r.get('recover_backlog_drained_s')}초")
        check((r.get("rows_written_late") or 0) > 0, f"db: 뒤늦게 들어간 행 {r.get('rows_written_late')} > 0 (backlog 가 실제로 쓰였다)")
    elif fault == "collector":
        label = r.get("label") or ""
        if "qos1" in label:
            check(lost == 0, f"collector(qos1): 유실 {lost} == 0 (지속 세션)")
        else:
            check(lost is not None and lost > 0, f"collector(qos0): 유실 {lost} > 0 (보호 없음이 숫자로 보인다)")
        check(r.get("recover_first_stats_s") is not None, f"collector: 재시작 뒤 첫 통계 {r.get('recover_first_stats_s')}초")
    elif fault == "bad_firmware":
        canary = int(math.ceil(r["devices_total"] * 0.05))
        check(r.get("success") is False, "bad_firmware: 배포가 롤백으로 끝났다")
        check(r.get("devices_touched") == canary, f"bad_firmware: 닿은 장치 {r.get('devices_touched')} == 5% 단계 {canary}")
        check(r.get("rollback_s") is not None, f"bad_firmware: 롤백 시간 {r.get('rollback_s')}초")
    else:
        check(False, f"모르는 장애 종류: {fault}")


def assert_ota(r):
    check(r.get("success") is True, f"ota {r['version']}: 성공")
    check(r.get("updated_devices") == r.get("devices"), f"ota {r['version']}: {r.get('updated_devices')}/{r.get('devices')} 장치 갱신")


def main(paths):
    for path in paths:
        with open(path, encoding="utf-8") as f:
            r = json.load(f)
        print(f"--- {path}")
        if "fault" in r:
            assert_fault(r)
        elif "version" in r:
            assert_ota(r)
        else:
            check(False, "fault 도 version 도 없는 JSON")
    if fail_count == 0:
        print("OK: all fault/OTA results as expected")
        return 0
    print(f"FAILED: {fail_count}")
    return 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
