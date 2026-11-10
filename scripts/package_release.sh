#!/usr/bin/env bash
# ---------------------------------------------------------------------------
# 릴리스 패키지 — 빌드 산출물을 장치가 받아 설치할 수 있는 한 덩어리(tar.gz)로 묶고, sha256 과 manifest.json 을 만든다.
#
#   무엇이 들어가나 : bin/jitter_bench (rt_core 의 1 kHz 루프 실행 파일) · robots/*.yaml (로봇 프로필)
#                     · config/*.params.yaml (ROS 2 파라미터) · VERSION · COMMIT · selftest.sh (자가 점검)
#   자가 점검        : 장치가 새 슬롯을 켜기 전에 selftest.sh 를 돌린다 — jitter_bench 를 0.5초 돌려 드롭 0 이면 통과.
#                     --bad 는 selftest 가 일부러 실패하는 패키지(롤백 검증용)를 만든다 (버전에 -bad 가 붙는다)
#   manifest.json    : 버전 · 파일 이름(url, 매니페스트와 같은 폴더 기준 상대 경로) · sha256 · 크기 · 커밋 · 배포 정책
#                     rollout.py --manifest 와 장치의 --auto-update 가 이 파일을 읽는다
#
# 사용:  bash scripts/package_release.sh <버전> [--build-dir build/rt_core] [--out build/release] [--arch x86_64|aarch64] [--bad]
#        예) bash scripts/package_release.sh v1.2.0          → build/release/rt-robot-data-infra-1.2.0-x86_64.tar.gz + manifest.x86_64.json
#            bash scripts/package_release.sh v1.2.0 --bad    → …-1.2.0-bad-x86_64.tar.gz + manifest-bad.x86_64.json
#        아키텍처가 둘(러너 x86_64, Pi aarch64)이면 scripts/merge_manifests.py 가 manifest.<arch>.json 들을 manifest.json 하나로 합친다
#        (장치는 자기 uname -m 에 맞는 항목을 고른다). 하나뿐이면 그대로 복사해도 된다.
# 전제:  cmake --build <build-dir> 가 끝나 jitter_bench 가 있을 것 (CI 의 rt_core 잡, 또는 WSL 의 build/rt_core)
# 왜 jitter_bench 인가: ROS 2 없이도 어디서나 실행되는 유일한 "로봇 쪽" 바이너리라, 러너·가상 장치·Pi 가 같은 파일을 켜 볼 수 있다.
#   rt_control_node 자체를 재시작하는 훅(post_switch.sh)은 자리만 있다 — docs/RELEASE.md 6절.
# ---------------------------------------------------------------------------
set -euo pipefail
cd "$(dirname "$0")/.."

VERSION="${1:?버전을 주세요 (예: v1.2.0 또는 1.2.0)}"
shift
BUILD_DIR=build/rt_core
OUT=build/release
BAD=0
ARCH="$(uname -m)"
while [ $# -gt 0 ]; do
  case "$1" in
    --build-dir) BUILD_DIR="$2"; shift 2 ;;
    --out) OUT="$2"; shift 2 ;;
    --arch) ARCH="$2"; shift 2 ;;
    --bad) BAD=1; shift ;;
    *) echo "모르는 옵션: $1"; exit 2 ;;
  esac
done
VERSION="${VERSION#v}"            # 태그 v1.2.0 → 1.2.0
if [ "$BAD" = 1 ]; then VERSION="${VERSION}-bad"; fi
NAME="rt-robot-data-infra-${VERSION}-${ARCH}"

if [ ! -x "$BUILD_DIR/jitter_bench" ]; then
  echo "jitter_bench 가 없습니다: $BUILD_DIR/jitter_bench — 먼저 cmake -S rt_control/rt_core -B $BUILD_DIR && cmake --build $BUILD_DIR -j"
  exit 2
fi

STAGE="$(mktemp -d)"
PKG="$STAGE/$NAME"
mkdir -p "$PKG/bin" "$PKG/robots" "$PKG/config"
cp "$BUILD_DIR/jitter_bench" "$PKG/bin/"
cp robots/*.yaml "$PKG/robots/"
cp rt_control/ros2_adapter/config/*.params.yaml "$PKG/config/" 2>/dev/null || true
echo "$VERSION" > "$PKG/VERSION"
COMMIT="$(git rev-parse HEAD 2>/dev/null || echo unknown)"
echo "$COMMIT" > "$PKG/COMMIT"

if [ "$BAD" = 1 ]; then
  cat > "$PKG/selftest.sh" <<'EOS'
#!/usr/bin/env bash
# 고의로 깨진 빌드 — 장치의 자가 점검이 이것을 잡아 설치를 거부하고, 배포기의 헬스 게이트가 롤백을 결정해야 한다.
echo "selftest: 고의로 깨진 빌드 (롤백 검증용)"
exit 1
EOS
else
  cat > "$PKG/selftest.sh" <<'EOS'
#!/usr/bin/env bash
# 자가 점검 — 새 슬롯이 "켜지는가": 이 장치에서 바이너리가 실행되고(아키텍처·라이브러리가 맞고), 1 kHz 루프 0.5초가 돈다.
# 드롭은 10% 넘으면 실패. 0 을 요구하지 않는 이유: 카나리에서는 가상 장치 25대가 한 러너에서 동시에 이 점검을 돌린다 —
# 그때의 드롭은 새 빌드의 문제가 아니라 공유 CPU 의 문제다. "켜지는가"를 묻는 점검이지 RT 성능 측정이 아니다(그건 E05·E19).
set -euo pipefail
cd "$(dirname "$0")"
./bin/jitter_bench --no-rt --seconds 0.5 --period-us 1000 --label selftest --json selftest.json > /dev/null
python3 - <<'PY'
import json
d = json.load(open("selftest.json"))
it = max(1, int(d["iterations"]))
pct = 100.0 * d["drops"] / it
if d["iterations"] < 100 or pct > 10.0:
    raise SystemExit(f"selftest: iterations={d['iterations']} drops={d['drops']} ({pct:.1f}%) — 켜지지 않거나 너무 끊긴다")
print(f"selftest ok: {d['iterations']} cycles, drops {d['drops']} ({pct:.1f}%), wake p99 {d['wake_us']['p99']} us")
PY
EOS
fi
cat > "$PKG/post_switch.sh" <<'EOS'
#!/usr/bin/env bash
# current 링크가 새 슬롯으로 바뀐 뒤 장치가 부르는 훅 (자리만). 실물에서 rt_control_node 를 새 바이너리로 재시작하려면
# 여기에 systemctl --user restart rt_control 같은 한 줄을 둔다 — 서비스 등록은 다음 단계 (docs/RELEASE.md 6절).
exit 0
EOS
chmod +x "$PKG/selftest.sh" "$PKG/post_switch.sh" "$PKG/bin/jitter_bench"

mkdir -p "$OUT"
tar -C "$STAGE" -czf "$OUT/$NAME.tar.gz" "$NAME"
rm -rf "$STAGE"
SHA="$(sha256sum "$OUT/$NAME.tar.gz" | cut -d' ' -f1)"
SIZE="$(stat -c %s "$OUT/$NAME.tar.gz")"
MANIFEST="$OUT/manifest.${ARCH}.json"
if [ "$BAD" = 1 ]; then MANIFEST="$OUT/manifest-bad.${ARCH}.json"; fi
cat > "$MANIFEST" <<EOF
{
  "version": "$VERSION",
  "arch": {"$ARCH": {"url": "$NAME.tar.gz", "sha256": "$SHA", "size": $SIZE}},
  "url": "$NAME.tar.gz",
  "sha256": "$SHA",
  "size": $SIZE,
  "commit": "$COMMIT",
  "built_at": "$(date -u +%Y-%m-%dT%H:%M:%SZ)",
  "rollout": {"stages_pct": [5, 50, 100], "health_wait_s": 5, "max_fail": 0, "apply_timeout_s": 60}
}
EOF
echo "package : $OUT/$NAME.tar.gz ($SIZE bytes)"
echo "sha256  : $SHA"
echo "manifest: $MANIFEST"
