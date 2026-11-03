#!/usr/bin/env python3
"""가짜 paho-mqtt — 네트워크 없이 "브로커 한 대"를 프로세스 안에서 흉내 낸다 (테스트 전용).

왜 필요한가
  진짜 Mosquitto 없이도 장치 에이전트 ↔ OTA 배포기 ↔ 수집기가 서로 메시지를 주고받는 흐름을 단위 테스트하려고.
  CI 의 첫 단계와 샌드박스(브로커 설치 불가)에서 돈다. 진짜 브로커로 하는 검증은 fleet/tests/integration.sh.

흉내 내는 것 (paho 2.x 의 우리가 쓰는 부분만)
  - Client(...): connect / connect_async + loop_start → on_connect 가 즉시 불린다
  - publish → 같은 FakeBroker 에 붙은 모든 구독자의 on_message 를 "그 자리에서(동기)" 부른다
  - subscribe: 토픽 와일드카드 + / # 지원, retain 된 메시지는 구독 즉시 전달
  - will_set: crash(client) 로 "비정상 종료"를 흉내 내면 브로커가 유언을 발행한다
  - 끊김 흉내: broker.disconnect_all() / broker.reconnect_all() (store-and-forward 테스트용)

쓰는 법 (테스트 파일 맨 위에서, device_agent 등을 import 하기 **전에**):
    import fake_mqtt
    fake_mqtt.install()        # sys.modules["paho.mqtt.client"] 를 이 모듈로 바꿔 끼운다
    broker = fake_mqtt.BROKER  # 모든 FakeClient 가 붙는 브로커 하나
"""
import sys
import threading
import types


def topic_matches(pattern, topic):
    """MQTT 토픽 와일드카드: + 는 한 단계, # 은 나머지 전부"""
    p = pattern.split("/")
    t = topic.split("/")
    for i in range(len(p)):
        if p[i] == "#":
            return True
        if i >= len(t):
            return False
        if p[i] != "+" and p[i] != t[i]:
            return False
    return len(p) == len(t)


class FakeMessage:
    def __init__(self, topic, payload, qos, retain):
        self.topic = topic
        self.payload = payload      # bytes (paho 와 같게)
        self.qos = qos
        self.retain = retain


class FakeReasonCode:
    is_failure = False


class FakeBroker:
    def __init__(self):
        self.lock = threading.Lock()
        self.clients = []           # 붙어 있는 FakeClient
        self.retained = {}          # topic -> payload bytes
        self.delivered = 0          # 전달한 메시지 수 (테스트 확인용)

    def reset(self):
        with self.lock:
            self.clients = []
            self.retained = {}
            self.delivered = 0

    def attach(self, client):
        with self.lock:
            if client not in self.clients:
                self.clients.append(client)

    def detach(self, client):
        with self.lock:
            if client in self.clients:
                self.clients.remove(client)

    def publish(self, topic, payload, qos, retain):
        if retain:
            with self.lock:
                self.retained[topic] = payload
        # 전달은 lock 밖에서 (구독자의 on_message 가 다시 publish 를 부를 수 있으므로 교착을 피한다)
        with self.lock:
            targets = list(self.clients)
        for client in targets:
            if client.connected and client.wants(topic):
                self.delivered += 1
                client.deliver(FakeMessage(topic, payload, qos, False))

    def send_retained(self, client, pattern):
        with self.lock:
            items = list(self.retained.items())
        for topic, payload in items:
            if topic_matches(pattern, topic):
                client.deliver(FakeMessage(topic, payload, 1, True))

    # ---- 장애 흉내 ----
    def crash(self, client):
        """클라이언트가 갑자기 죽음 → 브로커가 유언(LWT)을 발행"""
        client.connected = False
        self.detach(client)
        if client.will is not None:
            topic, payload, qos, retain = client.will
            self.publish(topic, to_bytes(payload), qos, retain)

    def disconnect_all(self):
        """브로커가 죽은 상황: 모두 끊긴 것으로 표시하고 on_disconnect 를 부른다"""
        with self.lock:
            targets = list(self.clients)
        for client in targets:
            client.connected = False
            if client.on_disconnect is not None:
                client.on_disconnect(client, None, None, FakeReasonCode(), None)

    def reconnect_all(self):
        """브로커가 돌아온 상황: 모두 다시 붙이고 on_connect 를 부른다 (paho 의 자동 재접속에 해당)"""
        with self.lock:
            targets = list(self.clients)
        for client in targets:
            client.finish_connect()


def to_bytes(payload):
    if payload is None:
        return b""
    if isinstance(payload, bytes):
        return payload
    return str(payload).encode("utf-8")


BROKER = FakeBroker()


class FakeClient:
    def __init__(self, api_version=None, client_id=None, protocol=None, clean_session=True, **kwargs):
        self.client_id = client_id
        self.clean_session = clean_session
        self.connected = False
        self.pending_connect = False
        self.subscriptions = []      # (pattern, qos)
        self.published = []          # (topic, payload, qos, retain) — 보낸 것 기록 (테스트 확인용)
        self.will = None
        self.on_connect = None
        self.on_disconnect = None
        self.on_message = None
        BROKER.attach(self)

    # ---- paho 와 같은 이름의 메서드 ----
    def will_set(self, topic, payload=None, qos=0, retain=False):
        self.will = (topic, payload, qos, retain)

    def reconnect_delay_set(self, min_delay=1, max_delay=5):
        pass

    def connect(self, host, port=1883, keepalive=60):
        self.finish_connect()

    def connect_async(self, host, port=1883, keepalive=60):
        self.pending_connect = True

    def loop_start(self):
        if self.pending_connect:
            self.pending_connect = False
            self.finish_connect()

    def loop_stop(self):
        pass

    def disconnect(self):
        self.connected = False
        BROKER.detach(self)

    def is_connected(self):
        return self.connected

    def publish(self, topic, payload=None, qos=0, retain=False):
        self.published.append((topic, payload, qos, retain))
        if self.connected:
            BROKER.publish(topic, to_bytes(payload), qos, retain)

    def subscribe(self, topic, qos=0):
        self.subscriptions.append((topic, qos))
        BROKER.send_retained(self, topic)

    # ---- 브로커가 부르는 것 ----
    def finish_connect(self):
        BROKER.attach(self)
        self.connected = True
        if self.on_connect is not None:
            self.on_connect(self, None, None, FakeReasonCode(), None)

    def wants(self, topic):
        for pattern, qos in self.subscriptions:
            if topic_matches(pattern, topic):
                return True
        return False

    def deliver(self, message):
        if self.on_message is not None:
            self.on_message(self, None, message)


def install():
    """sys.modules 에 가짜 paho 를 끼운다. 실제 paho 가 설치돼 있어도 테스트는 이것을 쓴다."""
    module = types.ModuleType("paho.mqtt.client")
    module.Client = FakeClient
    module.CallbackAPIVersion = types.SimpleNamespace(VERSION2=2)
    module.MQTTv311 = 4
    module.MQTTv5 = 5
    sys.modules["paho"] = types.ModuleType("paho")
    sys.modules["paho.mqtt"] = types.ModuleType("paho.mqtt")
    sys.modules["paho.mqtt.client"] = module
    return module
