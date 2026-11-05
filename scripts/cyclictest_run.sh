#!/usr/bin/env bash
# ---------------------------------------------------------------------------
# 표① 생성용: cyclictest를 한 조건으로 돌려 히스토그램을 저장한다.
#
# cyclictest 란?  "1 ms마다 깨워 달라"고 커널에 부탁해 놓고, 실제로는 얼마나 늦게
#                깨는지를 수십만 번 재는 표준 측정 도구 (rt-tests 패키지).
#
# 사용법 (root 필요):
#   sudo scripts/cyclictest_run.sh <label> <초> [stress]
#   예) sudo scripts/cyclictest_run.sh pi4_generic_idle   300
#       sudo scripts/cyclictest_run.sh pi4_generic_stress 120 stress     # 방열판 없는 Pi 4 는 부하 120초까지
#       sudo scripts/cyclictest_run.sh pi4_rt_idle        300
#       sudo scripts/cyclictest_run.sh pi4_rt_stress      120 stress
#
# 결과: docs/measurements/cyclictest_<label>.txt (+ .meta: 커널·날짜·온도·스로틀)
#       → scripts/make_table1.py 가 읽어서 표①(마크다운)을 만든다
# 읽는 순서: 메타 기록 → (부하 시작, lib_stress.sh) → cyclictest → 온도·스로틀 덧붙임 → 요약 출력
# ---------------------------------------------------------------------------
set -euo pipefail

LABEL="${1:-run}"
DUR="${2:-600}"
STRESS="${3:-}"
OUTDIR="docs/measurements"
OUT="${OUTDIR}/cyclictest_${LABEL}.txt"
mkdir -p "${OUTDIR}"

# shellcheck source=scripts/lib_thermal.sh
source "$(dirname "$0")/lib_thermal.sh"
# shellcheck source=scripts/lib_stress.sh
source "$(dirname "$0")/lib_stress.sh"
VM_BYTES="${STRESS_VM_BYTES:-512M}"     # 이 스크립트가 11/04~05 에 쓴 값. jitter_run.sh 는 256M — 비교할 때 .meta 의 stress_vm_bytes 를 본다

if ! command -v cyclictest >/dev/null; then
  echo "cyclictest 가 없습니다:  sudo apt install rt-tests" >&2; exit 1
fi

TEMP_BEFORE="$(read_temp_mc)"
{
  echo "label=${LABEL}"
  echo "date=$(date -Iseconds)"
  echo "kernel=$(uname -r)"
  echo "realtime=$(cat /sys/kernel/realtime 2>/dev/null || echo 0)"
  echo "duration_s=${DUR}"
  echo "stress=${STRESS:-none}"
  echo "stress_vm_bytes=${VM_BYTES}"
  echo "cpus=$(nproc)"
} > "${OUT}.meta"

if [ "${STRESS}" = "stress" ]; then
  # CPU·I/O·메모리를 동시에 괴롭힌다 → "부하 중에도 주기를 지키는가" (정의는 lib_stress.sh 한 곳)
  start_stress "${DUR}" "${VM_BYTES}" || exit 1
fi

# -m 메모리 잠금  -S 모든 CPU에 스레드 하나씩  -p 90 SCHED_FIFO 우선순위
# -i 1000 주기(us)  -h 1000 히스토그램 상한(us)  -q 조용히  -D 지속시간(초)
cyclictest -m -S -p 90 -i 1000 -h 1000 -q -D "${DUR}" > "${OUT}"

stop_stress

# 측정 뒤 온도·스로틀을 메타에 덧붙인다 (스로틀 != 0 이면 이 측정은 "오염 가능"으로 표에 표시된다)
thermal_meta_lines "${TEMP_BEFORE}" >> "${OUT}.meta"

echo "saved: ${OUT}"
grep -E "^# (Min|Avg|Max) Latencies" "${OUT}" || true
thermal_summary "${TEMP_BEFORE}"
