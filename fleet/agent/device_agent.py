#!/usr/bin/env python3
"""장치 에이전트 — 장치(가상 또는 실물) 한 대가 관제 서버에 자기 상태를 보고하는 프로그램.

하는 일 (매 주기, 기본 1 Hz)
  1) 텔레메트리 JSON 을 fleet/<id>/telemetry 로 발행 (일련번호 seq 포함 → 빠진 번호 = 유실)
  2) 브로커와 끊기면 메시지를 메모리에 모아 두었다가(store-and-forward) 다시 붙으면 QoS 1 로 재전송
  3) 접속 시 fleet/<id>/status 에 "online"(보관 메시지), 끊길 때 브로커가 대신 "offline" 을 남김 (LWT, 유언)
  4) fleet/<id>/cmd 로 오는 명령을 받음: ping · set_state · health · ota · ota_rollback
     - ota (url 있음) : 진짜 설치 — 내려받기 → sha256 → A/B 슬롯 → 자가 점검 → current 전환 (ota_apply.py). 11/10 부터.
                        실패하면 state=fault 와 ota_error 를 텔레메트리에 실어 서버의 헬스 게이트가 보게 한다
     - ota (url 없음) : 옛 흉내 경로 — apply_s 동안 state=updating → fw_version 교체. bad=true 면 fault (단위 테스트·장애 주입용)
     - ota_rollback   : 이전 슬롯(또는 이전 버전 문자열)으로 되돌리고 state=ok
  5) 자율 업데이트(선택, --auto-update): poll_s 마다 매니페스트 URL 을 읽어 새 버전이면 스스로 설치한다.
     지휘소(브로커·rollout.py)가 없어도 되는 경로 — 항상 켜진 서버가 없는 현장용. 점검 시간대와 state==ok 일 때만.

읽는 순서: DeviceAgent.__init__ → start → tick (한 주기) → on_connect (재접속 시 버퍼 비우기) → on_message (명령)
           → apply_ota (흉내) / apply_ota_artifact (진짜) → auto_update_loop

실물 장치(Pi, RT 노드)도 같은 클래스를 쓴다. 다른 것은 metrics_source(어디서 숫자를 가져오나)와 kind("real") 뿐이다.
"""
import json
import os
import platform
import sys
import threading
import time
import urllib.request
from collections import deque

import paho.mqtt.client as mqtt

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "common"))
import ota_apply  # noqa: E402
import mqtt_conn  # noqa: E402  (TLS·인증은 환경변수 FLEET_TLS_CA / FLEET_USER / FLEET_PASS — 없으면 개발 모드)

MAX_BUFFER = 3600  # 끊겼을 때 모아 두는 최대 개수 (1 Hz 기준 1시간). 넘치면 가장 오래된 것을 버린다


class DeviceAgent:
    def __init__(self, device_id, broker_host, broker_port, period_s, metrics_source, fw_version="1.0.0",
                 keepalive_s=10, telemetry_qos=0, slot_root=None, kind="virtual"):
        self.device_id = device_id
        self.kind = kind                      # "virtual" | "real" — 배포기가 실물을 마지막 단계로 보내는 데 쓴다
        self.slot_root = slot_root            # A/B 슬롯 디렉터리. None 이면 ota 는 흉내 경로만 된다
        self.ota_stage = None                 # 마지막 설치가 어디까지 갔나 (텔레메트리에 실린다)
        self.ota_error = None
        self.auto_update = None               # {"url":..., "poll_s":..., "window":(h0,h1) | None}
        self.auto_thread = None
        if slot_root is not None:
            os.makedirs(slot_root, exist_ok=True)
            installed = ota_apply.current_version(slot_root)
            if installed is not None:
                fw_version = installed        # 재시작하면 현재 슬롯의 버전이 곧 내 버전이다
        self.period_s = period_s
        self.keepalive_s = keepalive_s        # 이 시간 동안 아무것도 못 받으면 PINGREQ 를 보낸다 (브로커는 1.5배 안에 못 들으면 끊고 유언 발행)
        self.telemetry_qos = telemetry_qos    # 0: 보내고 잊음(기본, 가장 가벼움) / 1: 브로커가 받았다는 확인까지 (수집기 끊김 때 유실 0 에 필요)
        self.metrics_source = metrics_source  # 호출하면 dict 를 돌려주는 함수 (가상: 난수, 실물: 센서)
        self.fw_version = fw_version
        self.prev_fw_version = None   # 롤백용: 직전 버전
        self.ota_thread = None
        self.seq = 0
        self.buffer = deque()          # 끊겼을 때 쌓아 두는 (topic, payload)
        self.buffered_total = 0        # 지금까지 버퍼에 들어간 수
        self.flushed_total = 0         # 재접속 뒤 재전송한 수
        self.reconnects = 0
        self.state = "ok"
        self.running = False
        self.thread = None
        self.lock = threading.Lock()

        self.topic_telemetry = f"fleet/{device_id}/telemetry"
        self.topic_status = f"fleet/{device_id}/status"
        self.topic_cmd = f"fleet/{device_id}/cmd"
        self.topic_cmd_reply = f"fleet/{device_id}/cmd_reply"

        self.client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, client_id=f"agent-{device_id}",
                                  protocol=mqtt.MQTTv311)
        # 유언(LWT): 이 클라이언트가 비정상 종료되면 브로커가 대신 "offline" 을 발행한다
        self.client.will_set(self.topic_status, payload="offline", qos=1, retain=True)
        self.client.on_connect = self.on_connect
        self.client.on_disconnect = self.on_disconnect
        self.client.on_message = self.on_message
        self.client.reconnect_delay_set(min_delay=1, max_delay=5)  # 끊기면 1~5초 간격으로 자동 재접속
        self.security = mqtt_conn.apply_security(self.client)      # 환경변수에 TLS·인증이 있으면 건다 (클라우드 브로커용)
        self.broker_host = broker_host
        self.broker_port = broker_port

    # ---------- 시작 / 종료 ----------
    def start(self):
        self.running = True
        self.client.connect_async(self.broker_host, self.broker_port, keepalive=self.keepalive_s)
        self.client.loop_start()  # paho 가 네트워크 처리용 스레드를 하나 만든다
        self.thread = threading.Thread(target=self.run_loop, name=f"tick-{self.device_id}", daemon=True)
        self.thread.start()

    def stop(self):
        self.running = False
        if self.thread is not None:
            self.thread.join(timeout=2.0)
        # 정상 종료: 내가 직접 offline 을 남기고 끊는다 (유언은 비정상 종료용)
        self.client.publish(self.topic_status, payload="offline", qos=1, retain=True)
        time.sleep(0.2)
        self.client.loop_stop()
        self.client.disconnect()

    # ---------- 한 주기 ----------
    def run_loop(self):
        next_tick = time.monotonic()
        while self.running:
            self.tick()
            next_tick += self.period_s  # 절대 시각 누적 (RT 루프와 같은 원리, 정밀도만 낮음)
            delay = next_tick - time.monotonic()
            if delay > 0:
                time.sleep(delay)

    def tick(self):
        metrics = self.metrics_source()
        payload = {
            "device_id": self.device_id,
            "seq": self.seq,
            "ts_ns": time.time_ns(),      # 벽시계(UTC). 수집기가 "도착 - 측정" 으로 수집 지연을 계산한다
            "fw_version": self.fw_version,
            "state": self.state,
            "kind": self.kind,
            "ota_stage": self.ota_stage,
            "ota_error": self.ota_error,
            "buffered": self.buffered_total,
            "flushed": self.flushed_total,
            "reconnects": self.reconnects,
        }
        payload.update(metrics)
        self.seq += 1
        self.send_or_buffer(self.topic_telemetry, json.dumps(payload))

    def send_or_buffer(self, topic, payload):
        if self.client.is_connected():
            self.client.publish(topic, payload, qos=self.telemetry_qos)
            return
        with self.lock:
            if len(self.buffer) >= MAX_BUFFER:
                self.buffer.popleft()  # 가장 오래된 것을 버린다
            self.buffer.append((topic, payload))
            self.buffered_total += 1

    # ---------- 브로커 콜백 (paho 네트워크 스레드에서 불린다) ----------
    def on_connect(self, client, userdata, flags, reason_code, properties):
        if reason_code.is_failure:
            return
        client.publish(self.topic_status, payload="online", qos=1, retain=True)
        client.subscribe(self.topic_cmd, qos=1)
        self.flush_buffer()

    def flush_buffer(self):
        """끊긴 동안 모아 둔 것을 QoS 1(최소 한 번 도착 보장)로 재전송"""
        with self.lock:
            items = list(self.buffer)
            self.buffer.clear()
        for topic, payload in items:
            self.client.publish(topic, payload, qos=1)
            self.flushed_total += 1

    def on_disconnect(self, client, userdata, disconnect_flags, reason_code, properties):
        if self.running:
            self.reconnects += 1  # paho 가 자동으로 다시 붙는다 (reconnect_delay_set)

    def on_message(self, client, userdata, msg):
        try:
            cmd = json.loads(msg.payload.decode("utf-8"))
        except ValueError:
            return
        name = cmd.get("cmd", "")
        reply = {"device_id": self.device_id, "cmd": name, "ok": False}
        if name == "ping":
            reply["ok"] = True
            reply["seq"] = self.seq
        elif name == "set_state":
            self.state = str(cmd.get("state", "ok"))
            reply["ok"] = True
        elif name == "health":
            reply["ok"] = (self.state == "ok")
            reply["fw_version"] = self.fw_version
            reply["state"] = self.state
        elif name == "ota":
            version = str(cmd.get("version", ""))
            url = cmd.get("url")
            apply_s = float(cmd.get("apply_s", 2.0))
            bad = bool(cmd.get("bad", False))
            if version and self.ota_thread is None:
                # 적용은 시간이 걸리므로 별도 스레드에서. 그동안 텔레메트리는 state=updating 으로 계속 나간다
                if url and self.slot_root is not None:
                    picked = pick_artifact(cmd)
                    args = (version, picked["url"], picked.get("sha256", ""), picked.get("size"))
                    self.ota_thread = threading.Thread(target=self.apply_ota_artifact, args=args, daemon=True)
                else:
                    self.ota_thread = threading.Thread(target=self.apply_ota, args=(version, apply_s, bad), daemon=True)
                self.ota_thread.start()
                reply["ok"] = True
                reply["applying"] = version
                reply["mode"] = "artifact" if (url and self.slot_root is not None) else "simulated"
        elif name == "ota_rollback":
            # 진짜 설치 경로에서는 슬롯의 state.json 이 "이전 버전"의 기준이다 (버전 문자열 기억은 흉내 경로용)
            # 순서가 중요하다 (11/11 수정): "직전 설치가 실패했는가"를 먼저 본다.
            #   install() 은 실패하면 current 를 건드리지 않았거나(sha 불일치·자가 점검 실패) 스스로 되돌렸다(훅 실패).
            #   그러니 되돌릴 슬롯이 없다 — 상태만 정상으로. 전에는 previous 슬롯이 있는지를 먼저 봐서, 두 번째 릴리스 뒤에
            #   깨진 패키지가 오면 "거부한 장치"가 멀쩡한 현재 버전에서 한 단계 더 옛 버전으로 내려갔다(슬롯이 비어 있던 시험에서는 안 보였다).
            slot_previous = None
            if self.slot_root is not None:
                slot_previous = ota_apply.read_state(self.slot_root).get("previous")
            if self.state == "fault" and self.ota_error is not None:
                self.state = "ok"
                self.ota_stage = "rolled_back"
                reply["ok"] = True
                reply["fw_version"] = self.fw_version
            elif slot_previous is not None:
                # 설치는 성공했는데 배포기가 되돌리기로 한 경우(같은 단계의 다른 장치가 비정상) → 슬롯을 이전 버전으로
                restored = ota_apply.rollback(self.slot_root)
                if restored is not None:
                    self.fw_version = restored
                    self.prev_fw_version = None
                    self.state = "ok"
                    self.ota_stage = "rolled_back"
                    reply["ok"] = True
                    reply["fw_version"] = self.fw_version
            elif self.prev_fw_version is not None:
                self.fw_version = self.prev_fw_version
                self.prev_fw_version = None
                self.state = "ok"
                self.ota_stage = "rolled_back"
                reply["ok"] = True
                reply["fw_version"] = self.fw_version
        client.publish(self.topic_cmd_reply, json.dumps(reply), qos=1)

    # ---------- OTA 적용 흉내 (별도 스레드) ----------
    def apply_ota(self, version, apply_s, bad):
        """apply_s 동안 'updating' → 버전 교체 → 정상이면 ok, 나쁜 펌웨어면 fault"""
        self.state = "updating"
        self.ota_stage = "simulated"
        self.ota_error = None
        time.sleep(apply_s)
        self.prev_fw_version = self.fw_version
        self.fw_version = version
        if bad:
            self.state = "fault"   # 새 펌웨어가 켜지자마자 고장 — 서버의 헬스 게이트가 이것을 잡아야 한다
        else:
            self.state = "ok"
        self.ota_thread = None

    # ---------- OTA 진짜 설치 (별도 스레드) ----------
    def apply_ota_artifact(self, version, url, sha256, size):
        """내려받기 → 검증 → A/B 슬롯 → 자가 점검 → 전환. 성공이면 fw_version 교체·ok, 실패면 fault + ota_error"""
        self.state = "updating"
        self.ota_error = None
        self.ota_stage = "downloading"
        r = ota_apply.install(self.slot_root, version, url, sha256, size)
        self.ota_stage = r.stage
        if r.ok:
            self.prev_fw_version = None   # 이전 버전은 슬롯의 state.json 이 기억한다
            self.fw_version = version
            self.state = "ok"
        else:
            # current 는 그대로(1~4단계 실패) — 그래도 state=fault 로 알려 서버가 "이 빌드는 문제" 라고 판단하게 한다
            self.ota_error = r.error[:200]
            self.state = "fault"
        self.ota_thread = None

    # ---------- 자율 업데이트 (지휘소 없이, 선택) ----------
    def enable_auto_update(self, manifest_url, poll_s=600.0, window=None):
        """poll_s 마다 manifest_url 을 읽어 새 버전이면 스스로 설치. window=(시작시, 끝시) 면 그 시간대에만 (예: (3, 5))"""
        self.auto_update = {"url": manifest_url, "poll_s": float(poll_s), "window": window}
        self.auto_thread = threading.Thread(target=self.auto_update_loop, name=f"auto-{self.device_id}", daemon=True)
        self.auto_thread.start()

    def in_window(self, now=None):
        window = self.auto_update.get("window") if self.auto_update else None
        if window is None:
            return True
        hour = time.localtime(now if now is not None else time.time()).tm_hour
        h0, h1 = window
        if h0 <= h1:
            return h0 <= hour < h1
        return hour >= h0 or hour < h1   # 자정을 넘기는 창 (예: 23~2)

    def auto_update_loop(self):
        while self.running and self.auto_update is not None:
            try:
                self.auto_update_once()
            except Exception as e:  # 매니페스트를 못 읽는 것은 흔한 일(네트워크) — 다음 폴링에 다시
                self.ota_error = f"manifest: {e.__class__.__name__}: {e}"[:200]
            deadline = time.monotonic() + self.auto_update["poll_s"]
            while self.running and time.monotonic() < deadline:
                time.sleep(0.5)

    def auto_update_once(self):
        """매니페스트 한 번 읽고 필요하면 설치. 설치했으면 True"""
        if self.ota_thread is not None or self.state != "ok" or not self.in_window():
            return False
        manifest = fetch_manifest(self.auto_update["url"])
        version = str(manifest.get("version", ""))
        if not version or version == self.fw_version:
            return False
        picked = pick_artifact(manifest)
        url = picked.get("url")
        if not url:
            raise ValueError(f"매니페스트에 이 아키텍처({platform.machine()})용 산출물이 없다")
        if not (url.startswith("http") or url.startswith("file://") or url.startswith("/")):
            # 매니페스트와 같은 폴더의 상대 경로 (Release 자산은 같은 폴더에 놓인다)
            url = self.auto_update["url"].rsplit("/", 1)[0] + "/" + url
        self.apply_ota_artifact(version, url, picked.get("sha256", ""), picked.get("size"))
        return True


def pick_artifact(entry, machine=None):
    """매니페스트(또는 ota 명령)에서 이 장치의 아키텍처 항목을 고른다. arch 맵이 없거나 내 아키텍처가 없으면 최상위 url/sha256/size.
    러너·가상 장치는 x86_64, Pi 는 aarch64 — 같은 매니페스트를 보고 서로 다른 파일을 받는다"""
    if machine is None:
        machine = platform.machine()
    arch_map = entry.get("arch") or {}
    if machine in arch_map:
        return dict(arch_map[machine])
    return {"url": entry.get("url"), "sha256": entry.get("sha256", ""), "size": entry.get("size")}


def fetch_manifest(url, timeout_s=20.0):
    if url.startswith("file://"):
        url = url[len("file://"):]
    if url.startswith("http://") or url.startswith("https://"):
        with urllib.request.urlopen(url, timeout=timeout_s) as resp:
            return json.loads(resp.read().decode("utf-8"))
    with open(url, encoding="utf-8") as f:
        return json.load(f)
