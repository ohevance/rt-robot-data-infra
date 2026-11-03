#!/usr/bin/env bash
# ---------------------------------------------------------------------------
# MuJoCo 바이너리(C 라이브러리) + MuJoCo Menagerie 의 SO-ARM100 모델을 third_party/ 에 받는다.
#
#   third_party/mujoco/{include/mujoco/mujoco.h, lib/libmujoco.so}   ← GitHub 릴리스 타르볼
#   third_party/mujoco_menagerie/trs_so_arm100/{so_arm100.xml, scene.xml, assets/}   ← git sparse checkout (전체 저장소 수백 MB 를 피함)
#
# 사용:  bash scripts/get_mujoco.sh            # 기본 버전
#        bash scripts/get_mujoco.sh 3.3.2      # 버전 지정 (CI 의 env MUJOCO_VERSION 과 같은 값으로)
# x86_64(노트북·WSL)와 aarch64(라즈베리파이) 모두 지원. 이미 받아져 있으면 건너뛴다.
# ---------------------------------------------------------------------------
set -euo pipefail
VERSION="${1:-3.3.2}"
cd "$(dirname "$0")/.."
mkdir -p third_party

ARCH="$(uname -m)"
case "$ARCH" in
  x86_64)  MJ_ARCH=x86_64 ;;
  aarch64) MJ_ARCH=aarch64 ;;
  *) echo "지원하지 않는 CPU: $ARCH"; exit 1 ;;
esac

# 1) MuJoCo 라이브러리
if [ -f third_party/mujoco/lib/libmujoco.so ]; then
  echo "mujoco: 이미 있음 (third_party/mujoco)"
else
  TARBALL="mujoco-${VERSION}-linux-${MJ_ARCH}.tar.gz"
  URL="https://github.com/google-deepmind/mujoco/releases/download/${VERSION}/${TARBALL}"
  echo "mujoco: 내려받기 $URL"
  curl -L --fail --retry 3 -o "third_party/${TARBALL}" "$URL"
  tar -xzf "third_party/${TARBALL}" -C third_party
  rm -rf third_party/mujoco
  mv "third_party/mujoco-${VERSION}" third_party/mujoco
  rm -f "third_party/${TARBALL}"
fi
ls third_party/mujoco/lib/libmujoco.so* third_party/mujoco/include/mujoco/mujoco.h

# 2) Menagerie 모델 (필요한 폴더만)
if [ -d third_party/mujoco_menagerie/trs_so_arm100 ]; then
  echo "menagerie: 이미 있음 (third_party/mujoco_menagerie/trs_so_arm100)"
else
  echo "menagerie: sparse checkout"
  rm -rf third_party/mujoco_menagerie
  git clone --depth 1 --filter=blob:none --sparse https://github.com/google-deepmind/mujoco_menagerie.git third_party/mujoco_menagerie
  (cd third_party/mujoco_menagerie && git sparse-checkout set trs_so_arm100)
  # SO-101 전용 폴더가 올라와 있다면 같이 받는다 (없어도 조용히 넘어간다 — 그러면 SO-ARM100 모델을 쓴다. 관절 구성은 같다: 5축 + 그리퍼)
  (cd third_party/mujoco_menagerie && git sparse-checkout add trs_so_arm101 >/dev/null 2>&1 || true)
fi
ls third_party/mujoco_menagerie/trs_so_arm100/*.xml
if [ -d third_party/mujoco_menagerie/trs_so_arm101 ]; then
  echo "SO-101 전용 모델도 있음: third_party/mujoco_menagerie/trs_so_arm101  (robots/so101.yaml 의 mujoco.model 을 바꿔도 됨)"
fi
echo "done. 다음:  cmake -S rt_control/rt_core -B build/rt_core_mj -DRT_CORE_WITH_MUJOCO=ON -DMUJOCO_DIR=\$PWD/third_party/mujoco"
