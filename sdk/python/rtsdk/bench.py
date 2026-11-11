"""ZeroMQ 경로의 시간을 잰다 — 무엇을 재는지가 숫자보다 먼저다.

    python3 -m rtsdk.bench --n 1000 --rate 100 --json out.json [--host 127.0.0.1] [--same-host]

세 가지 (전부 클라이언트 쪽 시계 하나로 잰다 — 1번·2번은 다른 PC 의 노드여도 맞다)
  1) ping 왕복            : PING → 노드의 명령 스레드 → PONG.  소켓 + 명령 스레드의 깨어남만 들어 있다 (RT 루프 없음)
  2) 명령 → 상태 반영     : TARGET(seq=k) 을 보낸 순간 → cmd_seq ≥ k 인 STATE 를 받은 순간.
                            = 소켓 → 명령 스레드 → 명령 우편함 → RT 루프가 다음 주기에 꺼냄 → 상태 벨트 → 발행 스레드(pub_poll_us 마다)
                              → PUB → 나.  로봇 제어에서 "내 명령이 실시간 루프에 들어가 결과가 보이기까지"
  3) 상태 흐름            : 받은 STATE 수, 빈 번호(노드가 버림), RT 주기(iter)의 빈 칸
  (--same-host) 4) RT → 나 한 방향 : STATE 의 rt_stamp_ns(RT 루프가 읽은 시각) → 받은 시각. 같은 PC 일 때만 의미가 있다.
                            명령의 반영을 기다리는 동안 받은 상태들에서 잰다 (흐름 측정 구간의 상태는 최신 것만 보므로 빼고)

결과 JSON 에 주소를 적지 않는다 (E23 과 같은 규칙) — same_host 여부만.
"""
import argparse
import json
import platform
import time

from .client import RobotClient


def pct(values, p):
    if not values:
        return None
    s = sorted(values)
    return s[min(len(s) - 1, int(len(s) * p / 100))]


def summary_ms(values_ns):
    ms = [v / 1e6 for v in values_ns]
    if not ms:
        return {"n": 0}
    return {"n": len(ms), "p50": round(pct(ms, 50), 3), "p95": round(pct(ms, 95), 3), "p99": round(pct(ms, 99), 3),
            "max": round(max(ms), 3), "min": round(min(ms), 3)}


def run(host, n, rate_hz, same_host):
    out = {"tool": "rtsdk.bench", "n": n, "rate_hz": rate_hz, "same_host": same_host,
           "client": {"python": platform.python_version(), "machine": platform.machine()}}
    with RobotClient(host, timeout_s=2.0) as robot:
        out["node"] = robot.info()
        dof = out["node"]["dof"]
        robot.wait_state(2.0)  # 구독이 붙을 때까지 (PUB/SUB 는 붙기 전의 메시지를 받지 못한다)

        # 1) ping
        rtt = []
        for _ in range(n):
            rtt.append(int(robot.ping() * 1e9))
            time.sleep(1.0 / rate_hz)
        out["ping_rtt_ms"] = summary_ms(rtt)

        # 2) 명령 → 상태 반영 (+ 3, 4)
        robot.latest_state()  # 쌓인 것 비우기
        missed0 = robot.states_missed
        received0 = robot.states_received
        t_phase = time.monotonic()
        cmd_to_state, one_way = [], []
        ack_counts = {}
        period = 1.0 / rate_hz
        seqs = []
        for i in range(n):
            target = [0.05 * ((i % 20) - 10) / 10.0] * dof
            t_send = time.monotonic_ns()
            seq = robot.send_target(target, wait_ack=False)
            got = None
            deadline = time.monotonic() + 1.0
            while time.monotonic() < deadline:
                try:
                    s = robot.wait_state(1.0)
                except TimeoutError:
                    break
                if same_host:
                    one_way.append(time.monotonic_ns() - s.rt_stamp_ns)
                if s.cmd_seq >= seq:
                    got = time.monotonic_ns()
                    break
            if got is not None:
                cmd_to_state.append(got - t_send)
            seqs.append(seq)
            # 다음 명령까지 남은 시간 동안 상태를 받아 둔다 (흐름 측정)
            until = t_send + int(period * 1e9)
            while time.monotonic_ns() < until:
                robot.latest_state()  # 받기만 한다 — 개수와 빈 번호는 client 가 센다
                time.sleep(0.0005)
        out["cmd_to_state_ms"] = summary_ms(cmd_to_state)
        out["cmd_lost"] = n - len(cmd_to_state)
        time.sleep(0.05)
        for seq in seqs:  # 흘려보낸 명령의 답(ACK)을 상태별로 센다 — 전부 ok 여야 한다
            st = robot.ack_status(seq) or "no_reply"
            ack_counts[st] = ack_counts.get(st, 0) + 1
        out["acks"] = ack_counts
        out["states_received"] = robot.states_received - received0
        out["states_seconds"] = round(time.monotonic() - t_phase, 3)
        out["states_missed"] = robot.states_missed - missed0
        if same_host:
            out["rt_to_client_ms"] = summary_ms(one_way)
    return out


def main():
    ap = argparse.ArgumentParser(description="ZeroMQ 경로 시간 측정 (rt_zmq_node)")
    ap.add_argument("--host", default="127.0.0.1")
    ap.add_argument("--n", type=int, default=1000)
    ap.add_argument("--rate", type=float, default=100.0, help="명령·ping 을 보내는 빠르기 (Hz)")
    ap.add_argument("--same-host", action="store_true", help="노드와 같은 PC — RT → 나 한 방향 지연도 잰다")
    ap.add_argument("--json", default="", help="결과 파일")
    a = ap.parse_args()
    out = run(a.host, a.n, a.rate, a.same_host)
    text = json.dumps(out, ensure_ascii=False, indent=1)
    print(text)
    if a.json:
        with open(a.json, "w", encoding="utf-8") as f:
            f.write(text + "\n")


if __name__ == "__main__":
    main()
