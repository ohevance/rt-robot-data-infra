#!/usr/bin/env python3
"""DDS 왕복 지연·손실률 측정기 (rclpy)

두 프로그램이 한 쌍이다.
  pong : /dds_bench/ping 을 받으면 그대로 /dds_bench/pong 으로 되돌려 준다 (메아리)
  ping : 번호와 보낸 시각을 넣은 메시지를 정해진 속도로 보내고, 되돌아온 것으로 왕복 시간(RTT)과 손실을 센다

왜 왕복(RTT)인가
  "보낸 시각"을 메시지에 넣어 받는 쪽에서 빼면 한 방향 지연이 되지만, 두 컴퓨터의 시계가 다르면 틀린다.
  왕복은 같은 시계로 재므로 시계 맞춤이 필요 없다. 한 방향 지연 ≈ RTT / 2 로 본다.

사용 (터미널 두 개, 또는 run_matrix.sh)
  python3 dds_bench/rtt_bench.py --role pong --reliability reliable --depth 10
  python3 dds_bench/rtt_bench.py --role ping --reliability reliable --depth 10 --payload 1024 --rate 100 --count 500 \
          --label fast_reliable_1k --json docs/measurements/dds_fast_reliable_1k.json
DDS 구현체는 환경변수로 고른다:  RMW_IMPLEMENTATION=rmw_fastrtps_cpp | rmw_cyclonedds_cpp
"""
import argparse
import json
import os
import struct
import sys
import time

import rclpy
from rclpy.node import Node
from rclpy.qos import HistoryPolicy, QoSProfile, ReliabilityPolicy
from std_msgs.msg import UInt8MultiArray

HEADER_BYTES = 16  # [0:8] 순번(seq), [8:16] 보낸 시각(ns)


def now_ns():
    return time.monotonic_ns()


def make_qos(reliability, depth):
    """reliable = 등기(분실 시 재전송), best_effort = 일반 우편(빠름, 분실 가능)"""
    if reliability == "reliable":
        rel = ReliabilityPolicy.RELIABLE
    else:
        rel = ReliabilityPolicy.BEST_EFFORT
    return QoSProfile(reliability=rel, history=HistoryPolicy.KEEP_LAST, depth=depth)


class Pong(Node):
    """메아리. 받은 것을 그대로 되돌려 준다."""

    def __init__(self, qos):
        super().__init__("dds_bench_pong")
        self.pub = self.create_publisher(UInt8MultiArray, "/dds_bench/pong", qos)
        self.sub = self.create_subscription(UInt8MultiArray, "/dds_bench/ping", self.on_ping, qos)
        self.count = 0

    def on_ping(self, msg):
        self.pub.publish(msg)
        self.count += 1


class Ping(Node):
    """보내고, 되돌아온 것을 세고, 끝나면 통계를 낸다."""

    def __init__(self, qos, payload, rate, count):
        super().__init__("dds_bench_ping")
        self.pub = self.create_publisher(UInt8MultiArray, "/dds_bench/ping", qos)
        self.sub = self.create_subscription(UInt8MultiArray, "/dds_bench/pong", self.on_pong, qos)
        self.payload = payload
        self.count = count
        self.sent = 0
        self.rtt_by_seq = {}          # seq -> 왕복 시간(ns). 같은 seq 가 두 번 오면 첫 번째만
        self.padding = bytes(max(0, payload - HEADER_BYTES))
        self.timer = self.create_timer(1.0 / rate, self.send_one)
        self.done_sending_at = None

    def send_one(self):
        if self.sent >= self.count:
            if self.done_sending_at is None:
                self.done_sending_at = now_ns()
            return
        header = struct.pack("<qq", self.sent, now_ns())
        msg = UInt8MultiArray()
        msg.data = header + self.padding
        self.pub.publish(msg)
        self.sent += 1

    def on_pong(self, msg):
        data = bytes(msg.data)
        if len(data) < HEADER_BYTES:
            return
        seq, send_ns = struct.unpack("<qq", data[:HEADER_BYTES])
        if seq in self.rtt_by_seq:
            return
        self.rtt_by_seq[seq] = now_ns() - send_ns


def percentile(sorted_values, p):
    """정렬된 리스트에서 p 백분위수 (p99.9 = 1,000개 중 999개는 이 값 이내)"""
    n = len(sorted_values)
    index = int(-(-p / 100.0 * n // 1))  # ceil
    if index < 1:
        index = 1
    if index > n:
        index = n
    return sorted_values[index - 1]


def run_ping(args):
    qos = make_qos(args.reliability, args.depth)
    node = Ping(qos, args.payload, args.rate, args.count)
    # 상대(pong)가 토픽을 찾을 시간을 준다 (DDS 디스커버리)
    time.sleep(args.warmup)

    # 보내는 동안 + 마지막 메아리가 돌아올 여유(grace) 동안 spin
    while rclpy.ok():
        rclpy.spin_once(node, timeout_sec=0.05)
        if node.done_sending_at is not None and now_ns() - node.done_sending_at > args.grace * 1e9:
            break

    rtts_us = sorted(v / 1000.0 for v in node.rtt_by_seq.values())
    received = len(rtts_us)
    sent = node.sent
    loss_pct = 100.0 * (sent - received) / sent if sent else 0.0
    result = {
        "label": args.label,
        "rmw": os.environ.get("RMW_IMPLEMENTATION", "rmw_fastrtps_cpp(default)"),
        "reliability": args.reliability,
        "depth": args.depth,
        "payload_bytes": args.payload,
        "rate_hz": args.rate,
        "sent": sent,
        "received": received,
        "loss_pct": round(loss_pct, 3),
        "rtt_us": {},
    }
    if rtts_us:
        result["rtt_us"] = {
            "min": round(rtts_us[0], 1),
            "p50": round(percentile(rtts_us, 50), 1),
            "p99": round(percentile(rtts_us, 99), 1),
            "p999": round(percentile(rtts_us, 99.9), 1),
            "max": round(rtts_us[-1], 1),
        }
    print(json.dumps(result, ensure_ascii=False))
    if args.json:
        os.makedirs(os.path.dirname(args.json) or ".", exist_ok=True)
        with open(args.json, "w", encoding="utf-8") as f:
            json.dump(result, f, ensure_ascii=False, indent=2)
    node.destroy_node()
    return 0


def run_pong(args):
    qos = make_qos(args.reliability, args.depth)
    node = Pong(qos)
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    node.destroy_node()
    return 0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--role", choices=["ping", "pong"], required=True)
    ap.add_argument("--reliability", choices=["reliable", "best_effort"], default="reliable")
    ap.add_argument("--depth", type=int, default=10, help="KEEP_LAST 큐 깊이")
    ap.add_argument("--payload", type=int, default=1024, help="메시지 크기(바이트)")
    ap.add_argument("--rate", type=float, default=100.0, help="초당 메시지 수")
    ap.add_argument("--count", type=int, default=500, help="보낼 개수")
    ap.add_argument("--warmup", type=float, default=1.5, help="보내기 전 대기(초): 디스커버리")
    ap.add_argument("--grace", type=float, default=1.0, help="다 보낸 뒤 메아리를 기다리는 시간(초)")
    ap.add_argument("--label", default="run")
    ap.add_argument("--json", default="")
    args = ap.parse_args()

    rclpy.init()
    try:
        if args.role == "ping":
            return run_ping(args)
        return run_pong(args)
    finally:
        if rclpy.ok():
            rclpy.shutdown()


if __name__ == "__main__":
    sys.exit(main())
