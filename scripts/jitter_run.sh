#!/usr/bin/env bash
# ---------------------------------------------------------------------------
# 표① 생성용: 우리 측정기(jitter_bench)를 한 조건으로 돌린다 — 부하·CPU 고정·온도 기록까지 한 줄로.
#
# 왜 따로 두나: 11/04 Pi 실측에서 조건 하나마다 명령 3줄(부하 시작 → sleep → jitter_bench → wait)을
#   손으로 쳤다. 줄이 길면 라벨·파일 이름이 어긋나기 쉽고, 온도 확인을 빼먹는다.
#   이 스크립트는 cyclictest_run.sh 와 같은 모양(label, 초, stress)으로 jitter_bench 를 돌리고
#   docs/measurements/jitter_<label>.json 옆에 .meta(온도 전·후, 스로틀)를 남긴다.
#
# 사용법 (RT 우선순위가 필요하므로 root):
#   sudo scripts/jitter_run.sh <label> <초> [stress|idle] [cpu]
#   예) sudo scripts/jitter_run.sh pi4_rt_idle       60
#       sudo scripts/jitter_run.sh pi4_rt_stress     60 stress
#       sudo scripts/jitter_run.sh pi4_rt_stress_pin 60 stress 3      # RT 스레드를 CPU 3 에 고정
#   환경 변수로 바꾸는 것: JITTER_PRIO(기본 80) · JITTER_WORK_US(기본 50; 0 이면 깨기만) · STRESS_VM_BYTES(기본 256M)
#       예) JITTER_WORK_US=0 sudo -E scripts/jitter_run.sh pi4_rt_stress_pin_work0 60 stress 2
#
# 읽는 순서: 인자 → 빌드 확인 → (부하 시작) → jitter_bench → 메타 기록 → 요약
# ---------------------------------------------------------------------------
set -euo pipefail

LABEL="${1:-run}"
DUR="${2:-60}"
STRESS="${3:-idle}"
CPU="${4:-}"
OUTDIR="docs/measurements"
JSON="${OUTDIR}/jitter_${LABEL}.json"
BENCH="build/rt_core/jitter_bench"
PRIO="${JITTER_PRIO:-80}"   # SCHED_FIFO 우선순위. 11/05 확인: 80 과 90 은 결과가 같다(E19-d B)
WORK_US="${JITTER_WORK_US:-50}"   # 매 주기 바쁘게 일하는 시간. 0 으로 두면 cyclictest 처럼 "깨기만" 한다(E19-d A)
STRESS_HEADROOM_S=15        # 부하는 측정보다 이만큼 길게 (측정 끝까지 부하가 유지되도록)
mkdir -p "${OUTDIR}"

# shellcheck source=scripts/lib_thermal.sh
source "$(dirname "$0")/lib_thermal.sh"
# shellcheck source=scripts/lib_stress.sh
source "$(dirname "$0")/lib_stress.sh"
VM_BYTES="${STRESS_VM_BYTES:-256M}"     # 이 스크립트가 11/04~05 에 쓴 값. cyclictest_run.sh 는 512M — 비교할 때 .meta 를 본다

if [ ! -x "${BENCH}" ]; then
  echo "${BENCH} 가 없습니다. 먼저 빌드:  cmake -S rt_control/rt_core -B build/rt_core -DCMAKE_BUILD_TYPE=Release && cmake --build build/rt_core -j4" >&2
  exit 1
fi

CPU_ARGS=()
if [ -n "${CPU}" ]; then
  CPU_ARGS=(--cpu "${CPU}")
fi

TEMP_BEFORE="$(read_temp_mc)"

if [ "${STRESS}" = "stress" ]; then
  # 부하 정의는 lib_stress.sh 한 곳 (11/04 일반 커널 기준값과 같은 256M 이 기본)
  start_stress "$((DUR + STRESS_HEADROOM_S))" "${VM_BYTES}" || exit 1
fi

"${BENCH}" --prio "${PRIO}" --seconds "${DUR}" --work-us "${WORK_US}" --label "${LABEL}" --json "${JSON}" "${CPU_ARGS[@]}"

stop_stress

{
  echo "label=${LABEL}"
  echo "date=$(date -Iseconds)"
  echo "kernel=$(uname -r)"
  echo "realtime=$(cat /sys/kernel/realtime 2>/dev/null || echo 0)"
  echo "duration_s=${DUR}"
  echo "stress=${STRESS}"
  echo "stress_vm_bytes=${VM_BYTES}"
  echo "cpu=${CPU:-none}"
  echo "prio=${PRIO}"
  echo "work_us=${WORK_US}"
  thermal_meta_lines "${TEMP_BEFORE}"
} > "${JSON}.meta"

echo "saved: ${JSON} (+ .meta)"
thermal_summary "${TEMP_BEFORE}"
