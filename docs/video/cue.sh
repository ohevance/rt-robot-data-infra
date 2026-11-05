#!/usr/bin/env bash
# ---------------------------------------------------------------------------
# 영상용 자막 상자 — 녹화 중 터미널에 장면 제목과 핵심 숫자를 크게 띄운다.
#   편집 프로그램에서 글자를 얹지 않아도 되게, 자막을 터미널이 직접 보여 준다.
#
# 사용:  bash docs/video/cue.sh <장면 번호 0~6>      (0 = 제목 카드)
#        예) bash docs/video/cue.sh 2  → 화면을 지우고 "표①" 자막 상자를 띄움 → 이어서 명령을 친다
#
# 내레이션(TTS 에 붙여 넣을 문장)은 docs/VIDEO_SCRIPT.md. 장면별 명령은 docs/video/cues.sh.
# 읽는 순서: box → 장면별 case 문
# ---------------------------------------------------------------------------
set -u

BOLD=$'\e[1m'; CYAN=$'\e[36m'; YELLOW=$'\e[33m'; GREEN=$'\e[32m'; RESET=$'\e[0m'
WIDTH=78

# 한 줄을 상자 안에 왼쪽 정렬로 (한글은 폭 2 로 계산)
pad_line() {
  local text="$1"
  local width
  # 색 코드(ESC[..m)는 폭 0, 한글·전각은 폭 2, 나머지 1
  width=$(printf '%s' "${text}" | python3 -c "import sys,re,unicodedata; s=re.sub(r'\x1b\[[0-9;]*m','',sys.stdin.read()); print(sum(2 if unicodedata.east_asian_width(c) in 'WF' else 1 for c in s))")
  local spaces=$((WIDTH - 4 - width))
  if [ "${spaces}" -lt 0 ]; then spaces=0; fi
  printf '│ %s%*s │\n' "${text}" "${spaces}" ""
}

# 상자: 제목 + 본문 줄들
box() {
  local title="$1"; shift
  clear
  echo
  printf '┌%s┐\n' "$(printf '─%.0s' $(seq 1 $((WIDTH - 2))))"
  pad_line "${BOLD}${CYAN}${title}${RESET}"
  printf '├%s┤\n' "$(printf '─%.0s' $(seq 1 $((WIDTH - 2))))"
  for line in "$@"; do
    pad_line "${line}"
  done
  printf '└%s┘\n' "$(printf '─%.0s' $(seq 1 $((WIDTH - 2))))"
  echo
}

case "${1:-0}" in
  0) box "rt-robot-data-infra — 실시간 제어 · 데이터 인프라 포트폴리오 (2분)" \
         "공고 4항목마다  코드 → 측정 숫자 → push 마다 다시 증명하는 CI" \
         "" \
         "① 1 kHz 실시간 루프 — Raspberry Pi 4, PREEMPT_RT 실측" \
         "② ROS 2 노드 + MuJoCo 물리 + 로봇 안 기록 파이프라인" \
         "③ 가상 장치 50대 관제 · OTA 단계 배포 · 장애 주입 → 유실 0" \
         "④ CI 3잡 (단위 → 진짜 컨테이너 통합 · MuJoCo 헤드리스)" ;;
  1) box "장면 1 — README 한 장: 직무 요구 ↔ 산출물 ↔ 수치" \
         "숫자 옆에는 항상  어디서 쟀는지(WSL 참고값 / Pi 실측 / CI 러너)" ;;
  2) box "장면 2 — 표① 1 kHz 루프의 지연 꼬리: 평균이 아니라 max" \
         "Raspberry Pi 4, 부하(stress-ng) 중 max  (us, 전부 스로틀 0)" \
         "" \
         "  일반 커널            jitter_bench 781   cyclictest 695" \
         "  + PREEMPT_RT         jitter_bench 301   cyclictest 132" \
         "  + CPU 3 고정         jitter_bench 311   (변화 없음)" \
         "  + isolcpus=3         jitter_bench 189   work max 135 → 53" \
         "" \
         "${YELLOW}우선순위(SCHED_FIFO)는 p50 만 좋게 한다 — 꼬리를 자르는 것은 커널${RESET}" ;;
  3) box "장면 3 — ROS 2 노드 + MuJoCo 물리 + 로봇 안 기록" \
         "제어 코드는 ROS 2 와 무관한 C++ — 백엔드만 SimLag → MuJoCo 로 교체" \
         "물리가 들어오자 어깨 관절이 목표보다 0.019 rad(1.1°) 처진다 = 중력" \
         "rosbag2 MCAP 30초 → CSV → 요약: 100.0 Hz · 틈 0 · 처짐 자동 검출" ;;
  4) box "장면 4 — 가상 장치 50대 관제 + OTA 단계 배포(5% → 50% → 100%)" \
         "나쁜 펌웨어: 5%(3대)에서 헬스 게이트가 잡아 1.0초에 롤백, 47대는 무사" ;;
  5) box "장면 5 — 장애 주입: 브로커를 죽여도 유실 0 의 증거" \
         "장치 버퍼 → 재전송, 전 장치 복귀 2.9초, 유실 0 / 1400" \
         "${YELLOW}처음엔 0 이 아니었다 — 측정 맹점을 고치자 53, 원인 셋을 추적해 0 으로${RESET}" ;;
  6) box "장면 6 — CI: push 마다 GitHub 러너가 다시 증명" \
         "rt_core: 빌드 · 단위 테스트 17건 · 1 kHz 연기(드롭 0)" \
         "→ fleet_integration: 진짜 컨테이너 · 장애 3종 · 롤백 · OTA" \
         "→ mujoco: MuJoCo 내려받아 빌드 · SO-ARM100 2,000주기 헤드리스" \
         "" \
         "${GREEN}코드와 숫자는 저장소에 — github.com/ohevance/rt-robot-data-infra${RESET}" ;;
  *) echo "장면 번호 0~6"; exit 1 ;;
esac
