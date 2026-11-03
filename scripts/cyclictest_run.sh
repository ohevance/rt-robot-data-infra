#!/usr/bin/env bash
# ---------------------------------------------------------------------------
# 표① 생성용: cyclictest를 한 조건으로 돌려 히스토그램을 저장한다.
#
# cyclictest 란?  "1 ms마다 깨워 달라"고 커널에 부탁해 놓고, 실제로는 얼마나 늦게
#                깨는지를 수십만 번 재는 표준 측정 도구 (rt-tests 패키지).
#
# 사용법 (root 필요):
#   sudo scripts/cyclictest_run.sh <label> <초> [stress]
#   예) sudo scripts/cyclictest_run.sh generic_idle   600
#       sudo scripts/cyclictest_run.sh generic_stress 600 stress
#       sudo scripts/cyclictest_run.sh rt_idle        3600
#       sudo scripts/cyclictest_run.sh rt_stress      3600 stress
#
# 결과: docs/measurements/cyclictest_<label>.txt (+ .meta: 커널·날짜)
#       → scripts/make_table1.py 가 읽어서 표①(마크다운)을 만든다
# ---------------------------------------------------------------------------
set -euo pipefail

LABEL="${1:-run}"
DUR="${2:-600}"
STRESS="${3:-}"
OUTDIR="docs/measurements"
OUT="${OUTDIR}/cyclictest_${LABEL}.txt"
mkdir -p "${OUTDIR}"

if ! command -v cyclictest >/dev/null; then
  echo "cyclictest 가 없습니다:  sudo apt install rt-tests" >&2; exit 1
fi

{
  echo "label=${LABEL}"
  echo "date=$(date -Iseconds)"
  echo "kernel=$(uname -r)"
  echo "realtime=$(cat /sys/kernel/realtime 2>/dev/null || echo 0)"
  echo "duration_s=${DUR}"
  echo "stress=${STRESS:-none}"
  echo "cpus=$(nproc)"
} > "${OUT}.meta"

SPID=""
if [ "${STRESS}" = "stress" ]; then
  if ! command -v stress-ng >/dev/null; then
    echo "stress-ng 가 없습니다:  sudo apt install stress-ng" >&2; exit 1
  fi
  # CPU·I/O·메모리를 동시에 괴롭힌다 → "부하 중에도 주기를 지키는가"
  stress-ng --cpu "$(nproc)" --io 2 --vm 1 --vm-bytes 512M --timeout "${DUR}s" >/dev/null 2>&1 &
  SPID=$!
  sleep 2
fi

# -m 메모리 잠금  -S 모든 CPU에 스레드 하나씩  -p 90 SCHED_FIFO 우선순위
# -i 1000 주기(us)  -h 1000 히스토그램 상한(us)  -q 조용히  -D 지속시간(초)
cyclictest -m -S -p 90 -i 1000 -h 1000 -q -D "${DUR}" > "${OUT}"

if [ -n "${SPID}" ]; then wait "${SPID}" 2>/dev/null || true; fi

echo "saved: ${OUT}"
grep -E "^# (Min|Avg|Max) Latencies" "${OUT}" || true
