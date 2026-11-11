#!/usr/bin/env python3
"""Nagle 모형 — "보내는 간격이 왕복 시간보다 짧으면 왕복 측정값이 왜 2~3배가 되는가"를 사건 기반으로 흉내 낸다.

왜 이 파일이 있나 (11/11, docs/experiments/E23.md)
  Pi → 시드니 브로커의 MQTT 왕복을 0.2초 간격으로 쟀더니 최소 285 / 중앙 707 / p95 838 / 최대 854 ms 가 나왔다.
  대시보드의 편도 지연(약 146 ms)과 맞지 않는다. "망이 느린가, 재는 방법이 값을 키웠는가"를 가르려고 가설을 모형으로 옮겼다:
    - 끝점 둘(클라이언트, 브로커)이 모두 Nagle 을 켜고 있다 (paho 는 TCP_NODELAY 를 걸지 않고, Mosquitto 의 set_tcp_nodelay 기본값은 false)
    - Nagle: 보냈지만 아직 수신 확인(ACK)을 못 받은 데이터가 있으면, 작은 쓰기는 보내지 않고 모아 둔다
    - 브로커는 받은 메시지마다 따로 되돌려 쓴다 (write 한 번에 하나) → 한 세그먼트에 둘이 실려 오면 둘째의 되돌림은 첫째의 ACK 를 기다린다
  이 셋만으로 편도 142.5 ms · 0.2초 간격을 돌리면 최소 285 / 중앙 710 / p95 845 / 최대 860 ms — 실측과 거의 같다.
  모형이 실측을 "설명"하는 것만으로는 부족하므로, 재기 전에 다른 조건의 값을 예측해 두고(E23 2절) 그 뒤에 쟀다.

무엇이 단순화인가 (정직하게)
  진짜 TCP 가 아니다. 혼잡 제어·재전송·MSS·TLS 레코드·무선 구간의 흔들림이 없다. 지연 ACK 는 고정 시간(기본 40 ms) 하나다.
  그래서 모형의 값은 "계단 모양"이고 실측은 그 주변에 퍼진다. 문턱(간격 = 왕복)의 위치와 배수(2~3배)를 보는 용도다.

사용:  python3 fleet/tools/nagle_model.py --rtt-ms 285          # 간격·옵션별 표
읽는 순서: simulate(사건 넷: write / seg / delack / ack) → quantile → main
"""
import argparse
import heapq
import statistics
import sys


class Endpoint:
    """TCP 끝점 하나의 상태 (세그먼트 개수로만 센다)"""

    def __init__(self, nagle):
        self.nagle = nagle
        self.buffer = []          # 쓰기는 됐지만 아직 못 보낸 메시지 번호
        self.sent = 0             # 보낸 데이터 세그먼트 누계
        self.acked = 0            # 그중 ACK 받은 것
        self.received = 0         # 받은 데이터 세그먼트 누계
        self.acked_to_peer = 0    # 상대에게 ACK 해 준 것
        self.delack_pending = False


def simulate(one_way_s, interval_s, count, nagle_client=True, nagle_broker=True, delack_s=0.040):
    """클라이언트가 interval 마다 메시지를 쓰고 브로커가 되돌린다. 돌려주는 것: 메시지별 왕복 시간(ms) 리스트"""
    events = []
    order = [0]

    def push(t, kind, *args):
        order[0] += 1
        heapq.heappush(events, (t, order[0], kind, args))

    client = Endpoint(nagle_client)
    broker = Endpoint(nagle_broker)
    peer = {client: broker, broker: client}
    t_write = {}
    t_echo = {}

    def try_send(t, end):
        """버퍼에 있는 것을 세그먼트 하나로 보낸다 — Nagle 이 켜져 있고 미확인 데이터가 있으면 기다린다"""
        if len(end.buffer) == 0:
            return
        if end.nagle and end.sent > end.acked:
            return
        messages = end.buffer
        end.buffer = []
        end.sent += 1
        end.acked_to_peer = end.received      # 데이터 세그먼트는 그때까지 받은 것의 ACK 를 같이 싣는다
        end.delack_pending = False
        push(t + one_way_s, "seg", peer[end], messages, end.sent, end.acked_to_peer)

    def on_ack(t, end, ack_no):
        if ack_no > end.acked:
            end.acked = ack_no
            try_send(t, end)                  # ACK 가 오면 붙잡혀 있던 것이 나간다

    for k in range(count):
        push(k * interval_s, "write", k)

    while len(events) > 0:
        t, _, kind, args = heapq.heappop(events)
        if kind == "write":
            k = args[0]
            t_write[k] = t
            client.buffer.append(k)
            try_send(t, client)
        elif kind == "seg":
            end, messages, seg_no, ack_no = args
            end.received = max(end.received, seg_no)
            on_ack(t, end, ack_no)
            if end is broker:
                for k in messages:            # 브로커는 메시지마다 따로 쓴다 → 둘째부터는 Nagle 이 붙잡는다
                    broker.buffer.append(k)
                    try_send(t, broker)
            else:
                for k in messages:
                    t_echo[k] = t
            if end.acked_to_peer < end.received and not end.delack_pending:
                end.delack_pending = True     # 되돌려 보낼 데이터가 없으면 지연 ACK
                push(t + delack_s, "delack", end)
        elif kind == "delack":
            end = args[0]
            if end.delack_pending and end.acked_to_peer < end.received:
                end.acked_to_peer = end.received
                push(t + one_way_s, "ack", peer[end], end.acked_to_peer)
            end.delack_pending = False
        elif kind == "ack":
            end, ack_no = args
            on_ack(t, end, ack_no)

    return [1000.0 * (t_echo[k] - t_write[k]) for k in range(count) if k in t_echo]


def quantile(values, p):
    """가장 가까운 순위 방식 (mqtt_rtt.percentile 과 같은 정의)"""
    s = sorted(values)
    index = int(-(-p * len(s) // 100))
    index = max(1, min(len(s), index))
    return s[index - 1]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--rtt-ms", type=float, default=285.0, help="망의 왕복 시간 (모형의 편도 = 이 값의 절반)")
    ap.add_argument("--count", type=int, default=300)
    a = ap.parse_args()
    one_way = a.rtt_ms / 2000.0
    rows = [
        ("1.00 s (1 Hz), 옵션 없음", 1.00, True, True),
        ("0.35 s, 옵션 없음", 0.35, True, True),
        ("0.20 s (5 Hz), 옵션 없음", 0.20, True, True),
        ("0.20 s, 클라이언트만 TCP_NODELAY", 0.20, False, True),
        ("0.20 s, 양쪽 TCP_NODELAY", 0.20, False, False),
    ]
    print(f"모형: 왕복 {a.rtt_ms:.0f} ms (편도 {a.rtt_ms / 2:.1f} ms), 메시지 {a.count}개")
    print(f"{'보내는 간격, 옵션':36s} {'min':>6s} {'p50':>6s} {'p95':>6s} {'max':>6s} {'mean':>6s}")
    for label, interval, nagle_c, nagle_b in rows:
        v = simulate(one_way, interval, a.count, nagle_c, nagle_b)
        print(f"{label:36s} {min(v):6.0f} {quantile(v, 50):6.0f} {quantile(v, 95):6.0f} {max(v):6.0f} {statistics.mean(v):6.0f}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
