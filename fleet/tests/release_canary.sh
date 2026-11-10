#!/usr/bin/env bash
# ---------------------------------------------------------------------------
# 릴리스 카나리 — 방금 만든 릴리스 패키지를 "게시하기 전에" 가상 함대 50대에 단계 배포해 본다 (릴리스 워크플로의 2번째 잡).
#
#   진짜 Mosquitto 컨테이너 + 가상 장치 N대(A/B 슬롯 있음) + 패키지 폴더를 로컬 HTTP 로 서빙
#   1) manifest.json      → 5% → 50% → 100% 단계 배포. 장치마다 내려받기·sha256·풀기·자가 점검(jitter_bench 0.5초)·전환
#   2) manifest-bad.json  → 자가 점검이 실패하는 패키지. 첫 단계(5% = 3대)에서 거부되어 롤백해야 한다
#   3) 판정(assert_results.py) → 통과해야 Release 가 게시된다. 숫자(단계별 적용 시간, 전체 시간, 롤백 시간)는 JSON + 보고서로 남긴다
#
# 왜 가상 50대인가: 실물은 1대라 "5% 에서 멈추기"를 실물로는 못 보인다. 함대 차원의 검증은 여기서, 실물은 게시된 Release 를 스스로 받는다.
# 사용:  bash fleet/tests/release_canary.sh            (전제: build/release/manifest.json, manifest-bad.json, docker)
#        COUNT=50 OUT=build/release_canary PKG_DIR=build/release
# ---------------------------------------------------------------------------
set -euo pipefail
cd "$(dirname "$0")/../.."
COUNT=${COUNT:-50}
RATE=${RATE:-1}
OUT=${OUT:-build/release_canary}
PKG_DIR=${PKG_DIR:-build/release}
HTTP_PORT=${HTTP_PORT:-8089}
HEALTH_WAIT=${HEALTH_WAIT:-3}
mkdir -p "$OUT"
COMPOSE="docker compose -f fleet/docker-compose.yml"

cleanup() {
  echo "--- 정리"
  pkill -INT -f agent/virtual_fleet.py || true
  sleep 1
  if [ -n "${HTTP_PID:-}" ]; then kill "$HTTP_PID" 2>/dev/null || true; fi
  if [ "${KEEP:-0}" = "0" ]; then $COMPOSE down -v > /dev/null 2>&1 || true; fi
}
trap cleanup EXIT

test -f "$PKG_DIR/manifest.json" || { echo "manifest.json 이 없습니다: $PKG_DIR (scripts/package_release.sh + merge_manifests.py 먼저)"; exit 2; }
test -f "$PKG_DIR/manifest-bad.json" || { echo "manifest-bad.json 이 없습니다: $PKG_DIR"; exit 2; }

echo "--- 1) 브로커"
$COMPOSE up -d mqtt
python3 - <<'EOF'
import socket, time
deadline = time.time() + 60
while time.time() < deadline:
    try:
        socket.create_connection(("127.0.0.1", 1883), timeout=1).close(); break
    except OSError:
        time.sleep(1)
else:
    raise SystemExit("브로커가 60초 안에 안 열림")
print("broker ready")
EOF

echo "--- 2) 패키지 서빙 + 가상 장치 ${COUNT}대 (A/B 슬롯: $OUT/devices)"
python3 -m http.server "$HTTP_PORT" --bind 127.0.0.1 --directory "$PKG_DIR" > "$OUT/http.log" 2>&1 &
HTTP_PID=$!
python3 fleet/agent/virtual_fleet.py --count "$COUNT" --rate "$RATE" --telemetry-qos 1 --prefix rel --slot-root "$OUT/devices" > "$OUT/fleet.log" 2>&1 &
sleep 6

echo "--- 3) 정상 패키지: 단계 배포"
python3 fleet/ota/rollout.py --manifest "http://127.0.0.1:$HTTP_PORT/manifest.json" --db "" --health-wait "$HEALTH_WAIT" \
    --out "$OUT/ota_release_good.json"

echo "--- 4) 깨진 패키지: 첫 단계에서 거부 → 롤백 (종료 코드 1 이 정상)"
python3 fleet/ota/rollout.py --manifest "http://127.0.0.1:$HTTP_PORT/manifest-bad.json" --db "" --health-wait "$HEALTH_WAIT" \
    --out "$OUT/ota_release_bad.json" || true

echo "--- 5) 판정 + 보고서"
python3 fleet/chaos/assert_results.py "$OUT/ota_release_good.json" "$OUT/ota_release_bad.json"
python3 scripts/make_release_report.py --manifest "$PKG_DIR/manifest.json" --good "$OUT/ota_release_good.json" \
    --bad "$OUT/ota_release_bad.json" --out "$OUT/RELEASE_NOTES.md"
cat "$OUT/RELEASE_NOTES.md"
