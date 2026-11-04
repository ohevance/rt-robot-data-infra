# ---------------------------------------------------------------------------
# 측정 스크립트 공용 — 온도·스로틀 읽기 (cyclictest_run.sh, jitter_run.sh 가 source 한다)
#
# 왜 필요한가: Raspberry Pi 4 는 80 °C 를 넘으면 펌웨어가 클럭을 내린다(스로틀).
#   그 상태에서 잰 지연 값은 "커널 때문"인지 "클럭 때문"인지 가를 수 없다.
#   그래서 측정 전·후 온도와 "부팅 후 스로틀이 있었나" 플래그를 결과 옆에 같이 적는다.
#   (11/04 실측: 부하 75초에 45 → 75 °C. 방열판 없는 Pi 4 는 부하 측정을 120초로 제한한다)
#
# 읽는 순서: read_temp_mc → read_throttled → thermal_meta_lines
# 값이 없는 환경(WSL·CI 러너·노트북)에서는 "na" 를 적는다. 스크립트가 죽지 않게 하는 것이 우선.
# ---------------------------------------------------------------------------

TEMP_FILE="/sys/class/thermal/thermal_zone0/temp"                      # 밀리도(°C × 1000)
THROTTLE_FILE="/sys/devices/platform/soc/soc:firmware/get_throttled"   # Pi 펌웨어 플래그(16진수)

# 온도를 밀리도 정수로. 없으면 na
read_temp_mc() {
  if [ -r "${TEMP_FILE}" ]; then
    cat "${TEMP_FILE}"
  else
    echo "na"
  fi
}

# 스로틀 플래그. 0 이면 부팅 후 한 번도 없었음. 비트 뜻(Pi 4):
#   0x4 지금 스로틀 중 · 0x8 지금 온도 제한 중 · 0x40000 스로틀 이력 · 0x80000 온도 제한 이력
read_throttled() {
  if [ -r "${THROTTLE_FILE}" ]; then
    cat "${THROTTLE_FILE}"
  else
    echo "na"
  fi
}

# .meta 에 덧붙일 줄들 (key=value). 인자: 측정 전 온도(밀리도)
thermal_meta_lines() {
  local before_mc="$1"
  echo "temp_before_mC=${before_mc}"
  echo "temp_after_mC=$(read_temp_mc)"
  echo "throttled_after=$(read_throttled)"
}

# 사람이 보는 한 줄. 인자: 측정 전 온도(밀리도)
thermal_summary() {
  local before_mc="$1"
  echo "temp: ${before_mc} -> $(read_temp_mc) mC | throttled: $(read_throttled)  (0 이면 깨끗한 측정)"
}
