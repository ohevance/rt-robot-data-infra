# ---------------------------------------------------------------------------
# 측정 스크립트 공용 — 부하(stress-ng) 정의 한 곳 (cyclictest_run.sh, jitter_run.sh 가 source 한다)
#
# 왜 한 곳인가 (2026-11-05 교훈): 두 스크립트가 각자 stress-ng 를 띄우면서 메모리 버퍼 크기가 달랐다
#   (cyclictest_run 512M, jitter_run 256M). 그 상태로 "표준 도구 132 vs 내 측정기 301" 을 비교하다가
#   차이의 일부가 측정기가 아니라 **부하 정의** 에서 온 것을 뒤늦게 알았다(E19-d).
#   도구를 비교하려면 부하까지 같은 함수에서 나와야 하고, 쓴 값은 .meta 에 남아야 한다.
#
# 버퍼 크기가 왜 지연에 영향을 주나(추정): --vm 작업자는 버퍼를 mmap → 채움 → munmap 을 반복한다.
#   버퍼가 작을수록 그 주기가 짧아 munmap 이 잦고, munmap 마다 다른 CPU 로 TLB 동기화 IPI 가 간다.
#   IPI 는 우선순위도 isolcpus 도 막지 못하는 지연 원천이다.
#
# 기본값은 두 스크립트가 지금까지 쓴 값을 그대로 둔다(기존 14줄과의 비교가 깨지지 않게).
#   바꾸고 싶으면 환경 변수:  STRESS_VM_BYTES=512M sudo scripts/jitter_run.sh ...
# 읽는 순서: start_stress → stop_stress
# ---------------------------------------------------------------------------

STRESS_PID=""

# 부하 시작. 인자: 지속 초, vm 버퍼 크기(예 256M). CPU 전부 + I/O 2 + 메모리 1
start_stress() {
  local seconds="$1"
  local vm_bytes="$2"
  if ! command -v stress-ng >/dev/null; then
    echo "stress-ng 가 없습니다:  sudo apt install stress-ng" >&2
    return 1
  fi
  stress-ng --cpu "$(nproc)" --io 2 --vm 1 --vm-bytes "${vm_bytes}" --timeout "${seconds}s" >/dev/null 2>&1 &
  STRESS_PID=$!
  sleep 3     # 작업자들이 다 뜰 때까지 (측정 첫 1~2초가 "아직 한가"로 섞이지 않게)
}

# 부하 끝까지 기다림 (측정이 먼저 끝나도 timeout 까지 돈다)
stop_stress() {
  if [ -n "${STRESS_PID}" ]; then
    wait "${STRESS_PID}" 2>/dev/null || true
    STRESS_PID=""
  fi
}
