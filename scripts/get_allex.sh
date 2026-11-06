#!/usr/bin/env bash
# ---------------------------------------------------------------------------
# ALLEX — 위로보틱스가 공개한 상체 휴머노이드 시뮬레이션 모델을 third_party/allex_model 에 받는다.
#
#   출처   : https://github.com/wirobotics-rih/allex_model  (BSD-3-Clause; 메시는 MESHES-LICENSE 참고)
#   받는 것: mjcf/scene.xml (MuJoCo, 48 position 액추에이터) · urdf · usd · meshes (전체 약 250 MB)
#   고정   : 커밋 5e12052 (2026-07-03, v0.2.0 pre-release) — 다시 재도 같은 모델이 되게 커밋을 고정한다.
#
# 사용:  bash scripts/get_allex.sh            # 이미 있으면 건너뛴다
#        bash scripts/get_allex.sh <커밋>     # 다른 커밋으로 (문서의 숫자와 달라질 수 있다)
# 그 다음: robots/allex.yaml (관절 이름 48개) 로 노드/테스트를 돌린다 — backends/mujoco/README.md §5
# ---------------------------------------------------------------------------
set -euo pipefail
PIN="${1:-5e120529b106902898382fbd3eb9cec3188deaa2}"
cd "$(dirname "$0")/.."
DEST=third_party/allex_model

if [ -f "$DEST/mjcf/scene.xml" ]; then
  echo "allex: 이미 있음 ($DEST, $(git -C "$DEST" rev-parse --short HEAD 2>/dev/null || echo '?'))"
else
  echo "allex: 내려받기 (약 250 MB, 커밋 ${PIN:0:7})"
  mkdir -p "$DEST"
  git -C "$DEST" init -q
  git -C "$DEST" remote add origin https://github.com/wirobotics-rih/allex_model
  git -C "$DEST" fetch -q --depth 1 origin "$PIN"
  git -C "$DEST" checkout -q FETCH_HEAD
fi

# 프로필(robots/allex.yaml)과 맞는지 눈으로 확인할 숫자: 관절 60(수동 12 포함) · position 액추에이터 48
echo "joints : $(grep -c '<joint ' "$DEST/mjcf/ALLEX.xml")  (수동 관절·등식 제약 포함)"
echo "position actuators : $(grep -c '<position ' "$DEST/mjcf/ALLEX.xml")  (= robots/allex.yaml 의 dof)"
echo "timestep : $(grep -o 'timestep="[^"]*"' "$DEST/mjcf/ALLEX.xml")  (제어 주기 1 ms 보다 커서 백엔드가 1 ms 로 맞춘다)"
