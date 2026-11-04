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
PRIO=80                     # SCHED_FIFO 우선순위. cyclictest(90)보다 낮게 두어 둘을 같이 돌려도 cyclictest 가 기준
STRESS_HEADROOM_S=15        # 부하는 측정보다 이만큼 길게 (측정 끝까지 부하가 유지되도록)
mkdir -p "${OUTDIR}"

# shellcheck source=scripts/lib_thermal.sh
source "$(dirname "$0")/lib_thermal.sh"

if [ ! -x "${BENCH}" ]; then
  echo "${BENCH} 가 없습니다. 먼저 빌드:  cmake -S rt_control/rt_core -B build/rt_core -DCMAKE_BUILD_TYPE=Release && cmake --build build/rt_core -j4" >&2
  exit 1
fi

CPU_ARGS=()
if [ -n "${CPU}" ]; then
  CPU_ARGS=(--cpu "${CPU}")
fi

TEMP_BEFORE="$(read_temp_mc)"

SPID=""
if [ "${STRESS}" = "stress" ]; then
  if ! command -v stress-ng >/dev/null; then
    echo "stress-ng 가 없습니다:  sudo apt install stress-ng" >&2; exit 1
  fi
  # 11/04 일반 커널 기준값을 손으로 돌릴 때 쓴 것과 같은 부하(CPU 전부 + I/O 2 + 메모리 256M) — RT 결과와 비교가 되도록 바꾸지 않는다
  stress-ng --cpu "$(nproc)" --io 2 --vm 1 --vm-bytes 256M --timeout "$((DUR + STRESS_HEADROOM_S))s" >/dev/null 2>&1 &
  SPID=$!
  sleep 3
fi

"${BENCH}" --prio "${PRIO}" --seconds "${DUR}" --label "${LABEL}" --json "${JSON}" "${CPU_ARGS[@]}"

if [ -n "${SPID}" ]; then wait "${SPID}" 2>/dev/null || true; fi

{
  echo "label=${LABEL}"
  echo "date=$(date -Iseconds)"
  echo "kernel=$(uname -r)"
  echo "realtime=$(cat /sys/kernel/realtime 2>/dev/null || echo 0)"
  echo "duration_s=${DUR}"
  echo "stress=${STRESS}"
  echo "cpu=${CPU:-none}"
  thermal_meta_lines "${TEMP_BEFORE}"
} > "${JSON}.meta"

echo "saved: ${JSON} (+ .meta)"
thermal_summary "${TEMP_BEFORE}"
