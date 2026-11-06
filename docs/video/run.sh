#!/usr/bin/env bash
# ---------------------------------------------------------------------------
# 리허설용 자동 진행기 — 환경이 전부 떠 있는지 한 번에 확인:   bash docs/video/run.sh all
#   (녹화에는 쓰지 않는다. 데모는 사람이 직접 치는 모습이어야 하므로 녹화는 docs/video/CHEATSHEET.md 순서대로 타이핑한다.)
#
# 장면마다: 자막 상자(cue.sh) → 명령을 화면에 "$ 명령" 으로 보여 주고 실제로 실행 → 출력 → 몇 초 멈춤.
# 브라우저로 넘어가는 장면(1·4·6)에서는 "지금 Alt+Tab" 안내와 카운트다운을 띄운다(그동안 브라우저를 찍고 돌아온다).
# 한 장면만:  bash docs/video/run.sh 3      (리허설·재촬영용)
#
# 전제: docs/VIDEO_SCRIPT.md 의 체크리스트대로 수집기·가상 장치·노드·50 Hz 명령이 떠 있고, Pi 는 켜져 있거나(ssh 생중계) 꺼져 있어도 됨(건너뜀).
#       ssh 는 ~/.ssh/config 의 별칭 pi-rt 를 쓴다(CHEATSHEET.md). 비밀번호를 묻지 않게 하려면 미리 한 번:  ssh-copy-id pi-rt
#       다른 주소를 쓰려면:  PI=사용자@IP bash docs/video/run.sh all
# 읽는 순서: 도우미(typed·hold·browser) → scene0~6 → main
# ---------------------------------------------------------------------------
set -u
cd "$(dirname "$0")/../.."

PI="${PI:-pi-rt}"
GREEN=$'\e[1;32m'; YELLOW=$'\e[1;33m'; DIM=$'\e[2m'; RESET=$'\e[0m'

# 명령을 "친 것처럼" 보여 준다 (실제 실행은 호출한 쪽에서)
typed() {
  echo
  printf '%s$ %s%s\n' "${GREEN}" "$*" "${RESET}"
}

# n 초 멈춤 (출력을 읽을 시간)
hold() {
  sleep "$1"
}

# 브라우저 장면 안내 + 카운트다운. 인자: 안내문, 초
browser() {
  local text="$1" secs="$2"
  echo
  printf '%s▶ 지금 Alt+Tab → %s  (%d초 뒤 이 창으로 돌아오세요)%s\n' "${YELLOW}" "${text}" "${secs}" "${RESET}"
  local i
  for ((i = secs; i > 0; i--)); do
    printf '\r%s   %2d %s' "${DIM}" "${i}" "${RESET}"
    sleep 1
  done
  printf '\r      \r'
}

scene0() {
  bash docs/video/cue.sh 0
  hold 8
}

scene1() {
  bash docs/video/cue.sh 1
  browser "브라우저 README 탭: 위 표 → 아래 '숫자 한눈에' 까지 천천히 스크롤 → 초록 배지" 12
}

scene2() {
  bash docs/video/cue.sh 2
  hold 6
  typed "ssh ${PI} 'uname -r; cat /sys/kernel/realtime; cat /sys/devices/system/cpu/isolated'"
  ssh -o ConnectTimeout=3 "${PI}" 'uname -r; echo realtime=$(cat /sys/kernel/realtime); echo isolated=$(cat /sys/devices/system/cpu/isolated)' \
    || echo "(Pi 에 접속 못 함 — 꺼져 있으면 건너뜀)"
  hold 4
  typed "grep 'pi4_(generic|rt)_stress' docs/measurements/table1_pi4.md    # 조건 | 도구 | RT | 부하 | p99 | p99.9 | max"
  grep -E '^\| (pi4_generic_stress|pi4_rt_stress|pi4_rt_stress_isol) ' docs/measurements/table1_pi4.md | cut -d'|' -f2,3,5,6,10,11,12
  hold 6
  typed "./build/rt_core/jitter_bench --no-rt --seconds 3    # WSL 참고값"
  ./build/rt_core/jitter_bench --no-rt --seconds 3
  hold 4
}

scene3() {
  bash docs/video/cue.sh 3
  hold 5
  typed "ros2 topic echo /rt_status --once"
  ros2 topic echo /rt_status std_msgs/msg/String --full-length --once
  hold 4
  typed "ros2 topic echo /joint_states --once --field position    # 2번째 = 어깨, 목표 -0.200"
  ros2 topic echo /joint_states --once --field position
  hold 4
  typed "cat docs/measurements/record_summary_wsl_20261105.md    # rosbag2 30초 → CSV → 요약"
  cat docs/measurements/record_summary_wsl_20261105.md
  hold 6
}

scene4() {
  bash docs/video/cue.sh 4
  browser "Grafana 'Fleet Overview' 전체 화면" 5
  typed "python3 fleet/ota/rollout.py --version 1.2.0-bad --bad --apply-s 1 --health-wait 3"
  python3 fleet/ota/rollout.py --version 1.2.0-bad --bad --apply-s 1 --health-wait 3 || true
  hold 3
  browser "Grafana '펌웨어 버전별 장치 수' 패널 — 3대가 튀었다 돌아온 것" 5
}

scene5() {
  bash docs/video/cue.sh 5
  hold 4
  typed "python3 fleet/chaos/inject.py --fault broker --duration 5 --settle 5"
  python3 fleet/chaos/inject.py --fault broker --duration 5 --settle 5 --label video || true
  hold 2
  typed "결과 요약"
  python3 -c "import json;d=json.load(open('docs/measurements/fault_broker_video.json'));print('전 장치 복귀', d['recover_all_devices_s'], '초 / 유실', d['loss']['lost'], '/', d['loss']['expected'])"
  hold 5
}

scene6() {
  bash docs/video/cue.sh 6
  browser "브라우저 Actions 탭: 초록 3잡" 5
  typed "gh run list -L 3"
  gh run list -L 3 || true
  hold 6
}

main() {
  local which="${1:-all}"
  if [ "${which}" = "all" ]; then
    scene0; scene1; scene2; scene3; scene4; scene5; scene6
    echo; printf '%s끝. 녹화를 정지하세요.%s\n' "${YELLOW}" "${RESET}"
    return 0
  fi
  case "${which}" in
    0|1|2|3|4|5|6) "scene${which}" ;;
    *) echo "사용: bash docs/video/run.sh all   또는   bash docs/video/run.sh <0~6>"; return 1 ;;
  esac
}

main "$@"
