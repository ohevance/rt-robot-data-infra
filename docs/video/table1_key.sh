#!/usr/bin/env bash
# 영상 장면 2 — 표① 핵심 5줄만 보기 좋게 (전체 표는 docs/measurements/table1_pi4.md, 14줄)
#   사용:  bash docs/video/table1_key.sh
cd "$(dirname "$0")/../.."
printf '\n%-22s %-13s %-4s %-7s %8s %8s %8s\n' "조건(Pi 4, 부하 중)" "도구" "RT" "부하" "p99" "p99.9" "max(us)"
printf '%s\n' "----------------------------------------------------------------------------"
grep -E '^\| (pi4_generic_stress|pi4_rt_stress|pi4_rt_stress_isol) ' docs/measurements/table1_pi4.md \
  | awk -F'|' '{gsub(/^ +| +$/,"",$2); gsub(/^ +| +$/,"",$3); gsub(/^ +| +$/,"",$5); gsub(/^ +| +$/,"",$6);
                 printf "%-22s %-13s %-4s %-7s %8s %8s %8s\n", $2, $3, $5, $6, $10, $11, $12}'
echo
