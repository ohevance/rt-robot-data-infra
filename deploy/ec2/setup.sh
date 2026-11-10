#!/usr/bin/env bash
# ---------------------------------------------------------------------------
# 관제 서버 설치 — 클라우드 VM(EC2 Ubuntu 24.04, t3.small 권장) 안에서 한 번 실행한다. 끝나면 24시간 도는 운영 층이 생긴다:
#   Mosquitto(8883 TLS + 비밀번호) · TimescaleDB(밖으로 안 엶) · 수집기(QoS 1) · Grafana(:3000, 로그인 필요)
#
# 하는 일 (순서대로, 다시 돌려도 안전)
#   1) Docker 설치 (없으면)                       2) 이 저장소 받기/갱신 (~/rt-robot-data-infra)
#   3) 이 VM 의 공개 DNS·IP 를 메타데이터에서 읽기  4) 자체 CA + 서버 인증서 (deploy/ec2/make_certs.sh)
#   5) 브로커 비밀번호 파일 (사용자 fleet, 무작위 비밀번호)   6) Grafana 관리자 비밀번호 (무작위) → fleet/.env
#   7) docker compose (기본 + prod 덮어쓰기) 올리기    8) DB 보존 정책 14일 (telemetry·events·collector_stats)
#   9) 접속 정보를 ~/fleet-server-info.txt (600) 에 저장하고 화면에 출력 — 이 값들을 Pi·WSL 의 환경변수로 옮긴다
#
# 사용 (VM 에 SSH 로 들어가서):
#   curl -fsSL https://raw.githubusercontent.com/<owner>/<repo>/main/deploy/ec2/setup.sh | REPO_URL=https://github.com/<owner>/<repo>.git bash
#   또는 git clone 뒤:  bash deploy/ec2/setup.sh
# 전제: 보안 그룹에서 22(내 IP), 8883(0.0.0.0/0), 3000(내 IP) 이 열려 있을 것 — deploy/ec2/README.md 2절
# 비밀값은 VM 의 fleet/.env · fleet/mosquitto/passwd · certs 에만 있다. 저장소에 없다(.gitignore).
# ---------------------------------------------------------------------------
set -euo pipefail
REPO_URL="${REPO_URL:-https://github.com/ohevance/rt-robot-data-infra.git}"
BRANCH="${BRANCH:-main}"
DIR="${DIR:-$HOME/rt-robot-data-infra}"
RETENTION_DAYS="${RETENTION_DAYS:-14}"

echo "--- 1) Docker"
if ! command -v docker > /dev/null 2>&1; then
  curl -fsSL https://get.docker.com | sudo sh
  sudo usermod -aG docker "$USER" || true
fi
DOCKER="sudo docker"
$DOCKER compose version

echo "--- 2) 저장소"
if [ -d "$DIR/.git" ]; then
  git -C "$DIR" pull --ff-only
else
  git clone --branch "$BRANCH" "$REPO_URL" "$DIR"
fi
cd "$DIR"

echo "--- 3) 이 VM 의 공개 주소 (IMDSv2)"
TOKEN="$(curl -s -X PUT "http://169.254.169.254/latest/api/token" -H "X-aws-ec2-metadata-token-ttl-seconds: 60" || true)"
PUB_DNS="$(curl -s -H "X-aws-ec2-metadata-token: $TOKEN" http://169.254.169.254/latest/meta-data/public-hostname || true)"
PUB_IP="$(curl -s -H "X-aws-ec2-metadata-token: $TOKEN" http://169.254.169.254/latest/meta-data/public-ipv4 || true)"
if [ -z "$PUB_IP" ]; then
  echo "메타데이터에서 공개 IP 를 못 읽었습니다 (EC2 가 아닌가요?). HOST_NAMES='이름 IP' 로 직접 주세요."
  PUB_DNS="${HOST_NAMES:-}"
fi
NAMES="${HOST_NAMES:-$PUB_DNS $PUB_IP}"
echo "    이름/IP: $NAMES"

echo "--- 4) 인증서 (자체 CA)"
bash deploy/ec2/make_certs.sh fleet/mosquitto/certs $NAMES

echo "--- 5) 브로커 비밀번호"
if [ -f fleet/.env ] && grep -q '^FLEET_PASS=' fleet/.env; then
  FLEET_PASS="$(grep '^FLEET_PASS=' fleet/.env | cut -d= -f2-)"
  echo "    기존 비밀번호 재사용"
else
  FLEET_PASS="$(openssl rand -base64 18 | tr -d '/+=' | cut -c1-20)"
fi
rm -f fleet/mosquitto/passwd
$DOCKER run --rm -v "$DIR/fleet/mosquitto:/w" eclipse-mosquitto:2 mosquitto_passwd -b -c /w/passwd fleet "$FLEET_PASS"
sudo chown 1883:1883 fleet/mosquitto/passwd 2>/dev/null || true
sudo chmod 640 fleet/mosquitto/passwd 2>/dev/null || true

echo "--- 6) Grafana 비밀번호 → fleet/.env"
if [ -f fleet/.env ] && grep -q '^GRAFANA_ADMIN_PASSWORD=' fleet/.env; then
  GRAFANA_ADMIN_PASSWORD="$(grep '^GRAFANA_ADMIN_PASSWORD=' fleet/.env | cut -d= -f2-)"
else
  GRAFANA_ADMIN_PASSWORD="$(openssl rand -base64 18 | tr -d '/+=' | cut -c1-20)"
fi
cat > fleet/.env <<EOF
# deploy/ec2/setup.sh 가 만든 비밀값 — 커밋 금지 (.gitignore)
GRAFANA_ADMIN_PASSWORD=$GRAFANA_ADMIN_PASSWORD
FLEET_USER=fleet
FLEET_PASS=$FLEET_PASS
EOF
chmod 600 fleet/.env

echo "--- 7) 컨테이너 올리기"
$DOCKER compose -f fleet/docker-compose.yml -f fleet/docker-compose.prod.yml up -d --build
sudo systemctl enable docker > /dev/null 2>&1 || true

echo "--- 8) DB 보존 정책 (${RETENTION_DAYS}일) — 디스크 20 GB 가 차지 않게"
# "DB 가 응답한다"가 아니라 "확장과 표 셋이 생겼다"를 기다린다.
# 11/10 첫 실행: DB 컨테이너는 처음 켜질 때 초기화용 임시 서버를 먼저 띄운다. pg_isready 는 그 임시 서버에도 "준비됨"이라
#   답해서, init.sql(확장·표 생성)이 끝나기 전에 보존 정책을 걸다 "function add_retention_policy does not exist" 로 실패했다.
READY_SQL="SELECT (SELECT count(*) FROM pg_extension WHERE extname = 'timescaledb') + (SELECT count(*) FROM information_schema.tables WHERE table_schema = 'public' AND table_name IN ('telemetry', 'events', 'collector_stats'))"
DB_READY=0
for i in $(seq 1 90); do
  n="$($DOCKER exec fleet_db psql -U fleet -d fleet -tAc "$READY_SQL" 2> /dev/null || true)"
  if [ "$n" = "4" ]; then DB_READY=1; break; fi
  sleep 2
done
if [ "$DB_READY" != "1" ]; then echo "    DB 초기화가 3분 안에 끝나지 않았습니다 — 잠시 뒤 이 스크립트를 다시 실행하세요 (다시 돌려도 안전)"; fi
for table in telemetry events collector_stats; do
  $DOCKER exec fleet_db psql -U fleet -d fleet -q -c \
    "SELECT add_retention_policy('$table', INTERVAL '${RETENTION_DAYS} days', if_not_exists => TRUE);" > /dev/null && echo "    $table: ${RETENTION_DAYS}일" || echo "    (보존 정책 $table 실패 — 이 스크립트를 다시 실행하세요)"
done

echo "--- 9) 접속 정보"
INFO="$HOME/fleet-server-info.txt"
cat > "$INFO" <<EOF
# 관제 서버 접속 정보 — $(date -u +%Y-%m-%dT%H:%M:%SZ). 이 파일은 비밀값을 담고 있다. 공유 금지.
FLEET_BROKER=${PUB_DNS:-$PUB_IP}
FLEET_PORT=8883
FLEET_USER=fleet
FLEET_PASS=$FLEET_PASS
FLEET_TLS_CA=<ca.crt 를 복사한 경로>     # 서버의 $DIR/fleet/mosquitto/certs/ca.crt 를 Pi·WSL 로 scp
GRAFANA=http://${PUB_DNS:-$PUB_IP}:3000  (admin / $GRAFANA_ADMIN_PASSWORD)
EOF
chmod 600 "$INFO"
echo
echo "설치 끝. 접속 정보는 $INFO 에 (600). 요약:"
echo "  브로커   : ${PUB_DNS:-$PUB_IP}:8883  TLS, 사용자 fleet"
echo "  Grafana  : http://${PUB_DNS:-$PUB_IP}:3000  (admin)"
echo "  CA 파일  : $DIR/fleet/mosquitto/certs/ca.crt  → 장치로 복사:  scp ubuntu@<이 서버>:$DIR/fleet/mosquitto/certs/ca.crt ~/fleet-ca.crt"
echo "  확인     : $DOCKER compose -f fleet/docker-compose.yml -f fleet/docker-compose.prod.yml ps"
