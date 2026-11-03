#!/usr/bin/env bash
# ---------------------------------------------------------------------------
# 표② 생성용: DDS 구현체 × 신뢰성 × 메시지 크기 조합을 순서대로 돌린다.
#   조합 수 = 2(RMW) × 2(reliable/best_effort) × 4(크기) = 16회, 각 약 8초 → 약 2~3분
#
# 사용 (WSL, 저장소 루트에서):
#   source /opt/ros/jazzy/setup.bash
#   bash dds_bench/run_matrix.sh                # 같은 PC 안 (프로세스 간)
#   bash dds_bench/run_matrix.sh --suffix wifi  # 라벨에 접미사 (다른 기기와 잴 때)
#
# 결과: docs/measurements/dds_<rmw>_<reliability>_<payload><suffix>.json
#       → scripts/make_table2.py 가 읽어서 표②(마크다운)을 만든다
# ---------------------------------------------------------------------------
set -u

SUFFIX=""
if [ "${1:-}" = "--suffix" ]; then SUFFIX="_${2:-}"; fi

OUTDIR="docs/measurements"
mkdir -p "${OUTDIR}"

RMWS="rmw_fastrtps_cpp rmw_cyclonedds_cpp"
RELS="reliable best_effort"
PAYLOADS="64 1024 65536 1048576"      # 64 B, 1 KB, 64 KB, 1 MB
RATE=100
COUNT=500

for RMW in ${RMWS}; do
  for REL in ${RELS}; do
    for PAY in ${PAYLOADS}; do
      LABEL="${RMW#rmw_}_${REL}_${PAY}${SUFFIX}"
      echo "=== ${LABEL} ==="
      # 메아리(pong)를 뒤에서 띄우고
      RMW_IMPLEMENTATION="${RMW}" python3 dds_bench/rtt_bench.py --role pong --reliability "${REL}" --depth 10 &
      PONG_PID=$!
      sleep 1
      # 보내는 쪽(ping)을 앞에서 돌린다
      RMW_IMPLEMENTATION="${RMW}" python3 dds_bench/rtt_bench.py --role ping --reliability "${REL}" --depth 10 \
        --payload "${PAY}" --rate "${RATE}" --count "${COUNT}" \
        --label "${LABEL}" --json "${OUTDIR}/dds_${LABEL}.json"
      kill -INT "${PONG_PID}" 2>/dev/null   # SIGINT: rclpy 가 KeyboardInterrupt 로 조용히 끝난다 (SIGTERM 은 예외 출력)
      wait "${PONG_PID}" 2>/dev/null
    done
  done
done

python3 scripts/make_table2.py --json "${OUTDIR}/dds_*.json" --out "${OUTDIR}/table2.md"
cat "${OUTDIR}/table2.md"
