# ---------------------------------------------------------------------------
# 영상 녹화용 "치는 명령" 목록 — 녹화 터미널의 history 에 한 번에 넣고 ↑ 로 불러 친다.
#   [WSL 녹화 창]  history -r docs/video/cues.sh      ← 이 파일의 줄들이 history 에 들어간다(주석 포함)
#   그다음 ↑ 를 눌러 아래 줄들을 역순으로 불러 쓴다. ": 장면 N" 줄은 아무것도 안 하는 표지판이다.
#
# 장면 순서와 내레이션은 docs/VIDEO_SCRIPT.md, 자막 상자는 docs/video/cue.sh <N>.
# 이 파일은 실행하는 것이 아니다(source 하지 말 것).
# ---------------------------------------------------------------------------
: ==== 장면 0 제목 카드 ====
bash docs/video/cue.sh 0
: ==== 장면 1 README (브라우저) ====
bash docs/video/cue.sh 1
: ==== 장면 2 표① — Pi 실측 ====
bash docs/video/cue.sh 2
ssh pi-rt 'uname -r; cat /sys/kernel/realtime'
bash docs/video/table1_key.sh
./build/rt_core/jitter_bench --no-rt --seconds 3
: ==== 장면 3 노드 + MuJoCo + 기록 ====
bash docs/video/cue.sh 3
ros2 topic echo /rt_status std_msgs/msg/String --full-length --once
ros2 topic echo /joint_states --once --field position
cat docs/measurements/record_summary_wsl_20261105.md
: ==== 장면 4 관제 + OTA (Grafana 와 번갈아) ====
bash docs/video/cue.sh 4
python3 fleet/ota/rollout.py --version 1.2.0-bad --bad --apply-s 1 --health-wait 3
: ==== 장면 5 장애 주입 ====
bash docs/video/cue.sh 5
python3 fleet/chaos/inject.py --fault broker --duration 5 --settle 5
: ==== 장면 6 CI (브라우저 Actions 탭) ====
bash docs/video/cue.sh 6
gh run list -L 3
