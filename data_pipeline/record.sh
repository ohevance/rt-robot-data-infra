#!/usr/bin/env bash
# ---------------------------------------------------------------------------
# 로봇 데이터 기록 — rt_control_node 가 내는 토픽 3개를 rosbag2(MCAP 형식)로 N초 동안 받는다.
#
#   /joint_states  (100 Hz, 위치·속도)   /joint_command (50 Hz, 목표)   /rt_status (1 Hz, JSON 통계)
#
# 왜 MCAP 인가: Jazzy 의 기본 저장 형식. 한 파일에 여러 토픽이 시간순으로 들어가고, 파이썬(rosbag2_py)으로 바로 읽힌다.
# 사용:  bash data_pipeline/record.sh 30            # 30초 기록 → build/bags/run_<시각>/
#        (노드가 떠 있어야 한다. 명령도 같이 기록하려면 다른 터미널에서 ros2 topic pub ... 를 돌려 둔다)
# 다음:  python3 data_pipeline/bag_to_csv.py build/bags/run_<시각>
# ---------------------------------------------------------------------------
set -euo pipefail
SECONDS_TO_RECORD="${1:-30}"
cd "$(dirname "$0")/.."
OUT="build/bags/run_$(date +%Y%m%d_%H%M%S)"
mkdir -p build/bags
echo "기록 ${SECONDS_TO_RECORD}초 → ${OUT}  (Ctrl+C 로 일찍 끝내도 파일은 남는다)"
# --max-bag-duration 은 "파일 쪼개기" 옵션이라 시간 제한 용도로는 timeout 을 쓴다. SIGINT 라야 rosbag2 가 파일을 곱게 닫는다.
# --foreground 가 없으면(11/05 실제로 겪음) timeout 이 recorder 를 다른 프로세스 그룹에 두고, recorder 는 키보드(SPACE 일시정지)를
# 읽으려다 터미널에서 SIGTTIN 을 받아 "정지" 된다 → 아무 로그도 안 찍히고 30초 뒤 SIGINT 도 못 받는다.
# 키보드 제어도 꺼서(--disable-keyboard-controls) 터미널을 아예 안 읽게 한다. 토픽은 --topics 로(위치 인자는 Jazzy 에서 폐기 예고).
timeout --foreground -s INT "${SECONDS_TO_RECORD}" \
  ros2 bag record -s mcap -o "${OUT}" --disable-keyboard-controls --topics /joint_states /joint_command /rt_status || true
echo "끝. 파일:"; ls -la "${OUT}"
echo "다음:  python3 data_pipeline/bag_to_csv.py ${OUT}"
