#!/usr/bin/env bash
# ---------------------------------------------------------------------------
# Pi 에 에이전트를 사용자 서비스로 등록한다 (재부팅 뒤에도 돈다, root 불필요).
#   1) ~/.config/rt-fleet/fleet.env 가 없으면 예시를 복사하고 멈춘다 → 값을 채우고 다시 실행
#   2) 서비스 파일 복사 → daemon-reload → enable --now
#   3) 로그아웃 뒤에도 돌게 linger 켜기 (한 번)
# 사용 [Pi 창]:  cd ~/rt-robot-data-infra && bash deploy/pi/install.sh
# 전제: pip install paho-mqtt (python3-paho-mqtt), 저장소가 ~/rt-robot-data-infra 에 있을 것
# ---------------------------------------------------------------------------
set -euo pipefail
cd "$(dirname "$0")/../.."
ENV_DIR="$HOME/.config/rt-fleet"
ENV_FILE="$ENV_DIR/fleet.env"
mkdir -p "$ENV_DIR" "$HOME/.config/systemd/user" "$HOME/rt-slots"
if [ ! -f "$ENV_FILE" ]; then
  cp deploy/pi/fleet.env.example "$ENV_FILE"
  chmod 600 "$ENV_FILE"
  echo "설정 파일을 만들었습니다: $ENV_FILE"
  echo "  FLEET_BROKER / FLEET_PASS / FLEET_TLS_CA / MANIFEST_URL 을 채운 뒤 이 스크립트를 다시 실행하세요."
  echo "  (ca.crt 는 서버에서:  scp ubuntu@<서버>:~/rt-robot-data-infra/fleet/mosquitto/certs/ca.crt ~/fleet-ca.crt)"
  exit 0
fi
# paho-mqtt 는 2.0 이상이어야 한다(CallbackAPIVersion). Ubuntu 24.04 의 apt 패키지는 1.6 이라 맞지 않는다.
# 없으면 deploy/pi/get_paho.py 로 받는다 — pip·apt 없이 PyPI 에서 받아 sha256 을 확인하고 이 사용자의 site-packages 에 푼다.
# 11/10 첫 설치: paho 가 없었고, pip 을 apt 로 깔려니 자동 보안 업데이트(unattended-upgrade)가 잠금을 30분 넘게 쥐고 있었다.
if ! python3 -c "import paho.mqtt.client as m; assert hasattr(m, 'CallbackAPIVersion')" 2> /dev/null; then
  echo "paho-mqtt 2.x 가 없습니다 → deploy/pi/get_paho.py 로 설치합니다"
  python3 deploy/pi/get_paho.py || { echo "설치 실패. 직접:  python3 -m pip install --user 'paho-mqtt>=2.0'"; exit 2; }
fi
# 설정 파일에 자리표시나 빈 값이 남아 있으면 서비스가 조용히 실패한다 → 여기서 멈춘다 (비밀번호 값은 찍지 않는다)
for key in FLEET_BROKER FLEET_PASS FLEET_TLS_CA MANIFEST_URL; do
  value="$(grep "^$key=" "$ENV_FILE" | cut -d= -f2- || true)"
  case "$value" in
    ""|*"<"*|*" "*) echo "$ENV_FILE 의 $key 가 비었거나 자리표시(<…>)·공백이 들어 있습니다. 고친 뒤 다시 실행하세요."; exit 2 ;;
  esac
done
CA_PATH="$(grep '^FLEET_TLS_CA=' "$ENV_FILE" | cut -d= -f2-)"
[ -f "$CA_PATH" ] || { echo "CA 파일이 없습니다: $CA_PATH  (서버의 ca.crt 를 이 경로로 복사)"; exit 2; }
cp deploy/pi/rt-pi-agent.service "$HOME/.config/systemd/user/rt-pi-agent.service"
systemctl --user daemon-reload
systemctl --user enable --now rt-pi-agent
loginctl enable-linger "$USER" 2>/dev/null || sudo loginctl enable-linger "$USER" || true
sleep 2
systemctl --user --no-pager status rt-pi-agent | head -n 12
echo
echo "로그:  journalctl --user -u rt-pi-agent -f"
echo "슬롯:  ls ~/rt-slots/slots && cat ~/rt-slots/state.json"
