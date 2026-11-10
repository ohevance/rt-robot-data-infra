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
python3 -c "import paho.mqtt.client" 2>/dev/null || { echo "paho-mqtt 가 없습니다: sudo apt install -y python3-paho-mqtt (또는 pip install paho-mqtt)"; exit 2; }
cp deploy/pi/rt-pi-agent.service "$HOME/.config/systemd/user/rt-pi-agent.service"
systemctl --user daemon-reload
systemctl --user enable --now rt-pi-agent
loginctl enable-linger "$USER" 2>/dev/null || sudo loginctl enable-linger "$USER" || true
sleep 2
systemctl --user --no-pager status rt-pi-agent | head -n 12
echo
echo "로그:  journalctl --user -u rt-pi-agent -f"
echo "슬롯:  ls ~/rt-slots/slots && cat ~/rt-slots/state.json"
