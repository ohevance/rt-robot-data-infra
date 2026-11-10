#!/usr/bin/env bash
# ---------------------------------------------------------------------------
# 자체 CA + 브로커 서버 인증서 — 도메인 없이 TLS 를 켜기 위해 (Let's Encrypt 는 도메인이 있어야 한다).
#
#   만드는 것 (CERT_DIR 에):
#     ca.key / ca.crt        우리 CA. ca.crt 만 장치(Pi·WSL)에 나눠 준다 — 장치는 이 CA 가 서명한 서버만 믿는다
#     server.key / server.crt 브로커 인증서. SAN 에 이 서버의 공개 DNS 이름·공개 IP·'mqtt'(도커 네트워크)·'localhost'
#   왜 SAN 인가: 클라이언트는 "접속한 주소가 인증서에 적힌 이름과 같은가"를 본다. EC2 의 공개 DNS 와 IP 를 둘 다 넣어 어느 쪽으로 붙어도 된다.
#   유효기간: CA 10년, 서버 825일 (브라우저가 아니라 우리 장치만 보므로 길어도 된다).
#   Elastic IP 를 붙이거나 주소가 바뀌면 이 스크립트를 다시 돌리고 브로커만 재시작하면 된다(ca.crt 는 그대로라 장치는 손댈 것 없음).
#
# 사용:  bash deploy/ec2/make_certs.sh <CERT_DIR> <이름 또는 IP> [<이름 또는 IP> ...]
#   예)  bash deploy/ec2/make_certs.sh fleet/mosquitto/certs ec2-3-xx-xx-xx.ap-northeast-2.compute.amazonaws.com 3.xx.xx.xx
# 비밀키(*.key)는 .gitignore 에 있다. 절대 저장소에 넣지 않는다.
# ---------------------------------------------------------------------------
set -euo pipefail
CERT_DIR="${1:?인증서 디렉터리}"
shift
if [ $# -lt 1 ]; then echo "서버 이름/IP 를 하나 이상 주세요"; exit 2; fi
mkdir -p "$CERT_DIR"
cd "$CERT_DIR"

if [ ! -f ca.key ]; then
  openssl genrsa -out ca.key 4096 2>/dev/null
  openssl req -x509 -new -key ca.key -sha256 -days 3650 -subj "/CN=rt-robot-data-infra fleet CA" -out ca.crt
  echo "CA 생성: $CERT_DIR/ca.crt (장치에 나눠 줄 파일)"
else
  echo "CA 있음: $CERT_DIR/ca.crt (재사용)"
fi

SAN="DNS:mqtt,DNS:localhost,IP:127.0.0.1"
for name in "$@"; do
  if [[ "$name" =~ ^[0-9]+\.[0-9]+\.[0-9]+\.[0-9]+$ ]]; then SAN="$SAN,IP:$name"; else SAN="$SAN,DNS:$name"; fi
done
openssl genrsa -out server.key 2048 2>/dev/null
openssl req -new -key server.key -subj "/CN=$1" -out server.csr
cat > server.ext <<EOF
subjectAltName=$SAN
extendedKeyUsage=serverAuth
EOF
openssl x509 -req -in server.csr -CA ca.crt -CAkey ca.key -CAcreateserial -out server.crt -days 825 -sha256 -extfile server.ext 2>/dev/null
rm -f server.csr server.ext
# mosquitto 컨테이너는 uid 1883 으로 돈다 — 키를 읽을 수 있게
chmod 644 ca.crt server.crt
chmod 640 server.key ca.key
if command -v sudo >/dev/null 2>&1 && [ "$(id -u)" != "0" ]; then sudo chown 1883:1883 server.key 2>/dev/null || chmod 644 server.key; else chown 1883:1883 server.key 2>/dev/null || chmod 644 server.key; fi
echo "서버 인증서: $CERT_DIR/server.crt  SAN=$SAN"
openssl x509 -in server.crt -noout -dates | sed 's/^/  /'
