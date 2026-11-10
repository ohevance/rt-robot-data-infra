#!/usr/bin/env python3
"""MQTT 접속 보안 한 곳 — TLS(자체 CA) + 아이디/비밀번호를 환경변수로 받아 paho 클라이언트에 건다.

왜 이 파일이 있나 (11/10)
  관제 서버를 같은 PC(WSL) 밖, 클라우드 VM 에 올리면 브로커가 인터넷에 열린다. 그때는 암호화(TLS)와 인증(비밀번호) 없이는 안 된다.
  장치 에이전트·수집기·배포기·장애 주입기가 전부 브로커에 붙으므로, 접속 설정을 한 곳에 두고 모두 같은 환경변수를 읽게 한다.
  개발(같은 PC, 1883, 인증 없음)에서는 아무것도 설정하지 않으면 전과 똑같이 돈다.

환경변수 (설정 파일·저장소에 비밀값을 넣지 않기 위해 환경변수다 — Pi 는 systemd 의 EnvironmentFile, 서버는 .env)
  FLEET_BROKER   브로커 호스트 (기본 localhost)
  FLEET_PORT     포트 (기본: TLS 면 8883, 아니면 1883)
  FLEET_TLS_CA   우리 CA 인증서 파일(ca.crt) 경로. 주면 TLS 로 붙고 서버 인증서를 이 CA 로 검증한다
  FLEET_USER / FLEET_PASS   브로커 아이디·비밀번호 (mosquitto password_file)
  FLEET_TLS_INSECURE=1      서버 이름 검증을 끈다 (인증서의 SAN 에 없는 주소로 붙을 때만, 임시)

쓰는 법:
  from mqtt_conn import apply_security, broker_defaults
  host, port = broker_defaults()           # 환경변수 → (host, port)
  client = mqtt.Client(...)
  apply_security(client)                   # 환경변수대로 tls_set / username_pw_set. 설정 없으면 아무것도 안 한다
"""
import os


def broker_defaults(host=None, port=None):
    """명령줄 값이 있으면 그것, 없으면 환경변수, 그것도 없으면 localhost / (TLS 면 8883, 아니면 1883)"""
    if host is None:
        host = os.environ.get("FLEET_BROKER", "localhost")
    if port is None:
        env_port = os.environ.get("FLEET_PORT", "")
        if env_port:
            port = int(env_port)
        elif os.environ.get("FLEET_TLS_CA"):
            port = 8883
        else:
            port = 1883
    return host, int(port)


def security_settings():
    """환경변수에서 보안 설정을 읽어 dict 로. 전부 비어 있으면 {} (개발 모드)"""
    s = {}
    ca = os.environ.get("FLEET_TLS_CA", "")
    if ca:
        s["tls_ca"] = os.path.expanduser(ca)
        s["tls_insecure"] = os.environ.get("FLEET_TLS_INSECURE", "") == "1"
    user = os.environ.get("FLEET_USER", "")
    if user:
        s["username"] = user
        s["password"] = os.environ.get("FLEET_PASS", "")
    return s


def apply_security(client, settings=None):
    """paho 클라이언트에 TLS·인증을 건다. 돌려주는 것: 적용한 항목 이름 목록 (로그용)"""
    if settings is None:
        settings = security_settings()
    applied = []
    if settings.get("tls_ca"):
        if not os.path.isfile(settings["tls_ca"]):
            raise FileNotFoundError(f"FLEET_TLS_CA 파일이 없습니다: {settings['tls_ca']}")
        client.tls_set(ca_certs=settings["tls_ca"])
        if settings.get("tls_insecure"):
            client.tls_insecure_set(True)
            applied.append("tls(이름 검증 끔)")
        else:
            applied.append("tls")
    if settings.get("username"):
        client.username_pw_set(settings["username"], settings.get("password", ""))
        applied.append("auth")
    return applied


def describe():
    """사람이 읽는 한 줄 — 어디에 어떻게 붙는지 (비밀번호는 안 적는다)"""
    host, port = broker_defaults()
    s = security_settings()
    parts = [f"{host}:{port}"]
    if s.get("tls_ca"):
        parts.append("TLS")
    if s.get("username"):
        parts.append(f"user={s['username']}")
    if len(parts) == 1:
        parts.append("평문, 인증 없음(개발 모드)")
    return " ".join(parts)
