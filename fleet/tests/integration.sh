#!/usr/bin/env bash
# ---------------------------------------------------------------------------
# 통합 테스트 (CI 2단계 = 이 스크립트). 진짜 Mosquitto·TimescaleDB 컨테이너 위에서:
#   수집기(--qos 1) + 가상 장치 N대(QoS 1) → 장애 주입 3종(broker·db·collector) + 나쁜 펌웨어 롤백 + 정상 OTA
#   + (11/10) 진짜 산출물 OTA: 릴리스 패키지(tar.gz)를 로컬 HTTP 로 서빙 → 장치가 내려받아 sha256·A/B 슬롯·자가 점검 → 전환,
#     그리고 자가 점검이 실패하는 패키지로 롤백
#   → fleet/chaos/assert_results.py 로 "유실 0 · 복구됨 · 롤백됨" 판정 → 표③-2/3 생성
#
# WSL 에서:   bash fleet/tests/integration.sh            (약 3~4분. docker 가 떠 있어야 한다)
# 끝나면 컨테이너는 그대로 둔다 (KEEP=0 bash fleet/tests/integration.sh 이면 내린다)
# 결과: build/integration/*.json, build/integration/table3_ci.md, 로그 build/integration/*.log
# ---------------------------------------------------------------------------
set -euo pipefail
cd "$(dirname "$0")/../.."
COUNT=${COUNT:-10}
RATE=${RATE:-2}
OUT=build/integration
mkdir -p "$OUT"
COMPOSE="docker compose -f fleet/docker-compose.yml"

cleanup() {
  echo "--- 정리"
  pkill -INT -f agent/virtual_fleet.py || true
  sleep 1
  pkill -TERM -f collector/collector.py || true
  if [ -n "${HTTP_PID:-}" ]; then kill "$HTTP_PID" 2>/dev/null || true; fi
  if [ "${KEEP:-1}" = "0" ]; then $COMPOSE down -v; fi
}
trap cleanup EXIT

echo "--- 0) 릴리스 패키지 (산출물 OTA 용). 없으면 jitter_bench 를 빌드해 만든다"
PKG_DIR=${PKG_DIR:-build/release}
if [ ! -f "$PKG_DIR/manifest.json" ]; then
  if [ ! -x build/rt_core/jitter_bench ]; then
    cmake -S rt_control/rt_core -B build/rt_core -DCMAKE_BUILD_TYPE=Release > /dev/null
    cmake --build build/rt_core -j --target jitter_bench > /dev/null
  fi
  bash scripts/package_release.sh 0.0.0-ci --out "$PKG_DIR"
  bash scripts/package_release.sh 0.0.0-ci --out "$PKG_DIR" --bad
  python3 scripts/merge_manifests.py --out "$PKG_DIR/manifest.json" "$PKG_DIR"/manifest.*.json
  python3 scripts/merge_manifests.py --out "$PKG_DIR/manifest-bad.json" "$PKG_DIR"/manifest-bad.*.json
fi
HTTP_PORT=${HTTP_PORT:-8089}
python3 -m http.server "$HTTP_PORT" --bind 127.0.0.1 --directory "$PKG_DIR" > "$OUT/http.log" 2>&1 &
HTTP_PID=$!

echo "--- 1) 브로커·DB 올리기"
$COMPOSE up -d mqtt db
# DB 준비 확인은 밖에서 실제로 붙어 보는 migrate.py --wait 로 (컨테이너 안 pg_isready 는 init 중 임시 서버에도 "accepting" 이라고 답한다)
python3 fleet/db/migrate.py --wait 120

echo "--- 2) 수집기(지속 세션) + 가상 장치 ${COUNT}대 @ ${RATE} Hz (QoS 1)"
pkill -TERM -f collector/collector.py || true
python3 fleet/collector/collector.py --qos 1 > "$OUT/collector.log" 2>&1 &
python3 fleet/agent/virtual_fleet.py --count "$COUNT" --rate "$RATE" --telemetry-qos 1 --prefix ci --slot-root "$OUT/devices" > "$OUT/fleet.log" 2>&1 &
sleep 8
tail -n 2 "$OUT/collector.log"

echo "--- 3) 장애 주입"
python3 fleet/chaos/inject.py --fault broker    --duration 5 --settle 8 --out "$OUT/fault_broker.json"
python3 fleet/chaos/inject.py --fault db        --duration 5 --settle 8 --out "$OUT/fault_db.json"
python3 fleet/chaos/inject.py --fault collector --duration 5 --settle 8 --label qos1 --out "$OUT/fault_collector_qos1.json"
python3 fleet/chaos/inject.py --fault bad_firmware --out "$OUT/fault_bad_firmware.json" || true   # 롤백이면 종료 코드 1 이 정상

echo "--- 4) 정상 OTA (흉내: 버전 문자열)"
python3 fleet/ota/rollout.py --version 1.1.0 --apply-s 1 --health-wait 2 --out "$OUT/ota_1.1.0.json"

echo "--- 4b) 산출물 OTA: 진짜 패키지 내려받기 → sha256 → A/B 슬롯 → 자가 점검 → 전환"
python3 fleet/ota/rollout.py --manifest "http://127.0.0.1:$HTTP_PORT/manifest.json" --health-wait 2 --out "$OUT/ota_artifact_good.json"
echo "--- 4c) 산출물 OTA: 자가 점검이 실패하는 패키지 → 첫 단계에서 거부·롤백 (종료 코드 1 이 정상)"
python3 fleet/ota/rollout.py --manifest "http://127.0.0.1:$HTTP_PORT/manifest-bad.json" --health-wait 2 --out "$OUT/ota_artifact_bad.json" || true

echo "--- 5) 판정"
python3 fleet/chaos/assert_results.py "$OUT/fault_broker.json" "$OUT/fault_db.json" "$OUT/fault_collector_qos1.json" \
    "$OUT/fault_bad_firmware.json" "$OUT/ota_1.1.0.json" "$OUT/ota_artifact_good.json" "$OUT/ota_artifact_bad.json"
python3 scripts/make_table3.py --minutes 10 --label "integration ${COUNT}대 ${RATE} Hz" --measurements "$OUT" --out "$OUT/table3_ci.md"
cat "$OUT/table3_ci.md"
