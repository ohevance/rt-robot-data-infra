"""끝-대-끝: 진짜 rt_zmq_node 를 띄우고 SDK 로 이야기한다 (가짜 없음 — 진짜 libzmq·진짜 RT 루프, 권한 없는 곳이라 일반 스케줄링).

  1) info · ping           : 관절 수·주기가 띄운 옵션과 같다, 왕복이 온다
  2) 목표를 따라간다        : 목표 0.3 rad 를 100 Hz 로 보내면 위치가 0.3 에 가까워지고 상태 머신이 RUNNING. 그동안 워치독은 한 번도 안 걸린다
                              (처음엔 20 Hz 로 썼다가 워치독이 9번 걸렸다 — 명령 간격 50 ms = 워치독 50 ms 라 경계에 걸린 것. 명령은 워치독보다 충분히 자주)
  3) 명령 번호가 돌아온다   : STATE 의 cmd_seq 가 마지막으로 보낸 명령 번호에 닿는다 (명령 → 반영 지연을 재는 근거)
  4) 끊기면 멈춘다          : 명령을 멈추면 워치독 50 ms → FAULT, 위치는 그 자리에서 더 움직이지 않는다
  5) 다시 오면 복구          : 명령을 다시 보내면 RECOVERING → (100 ms) → READY/RUNNING
  6) 나쁜 패킷은 거절, 노드는 산다 : 쓰레기 바이트 → bad_packet, 관절 수 다름 → bad_dof, NaN → bad_value (보내기 전 SDK 가 먼저 막는
                              것과 별개로 노드도 막는지 — 날 바이트로 보낸다), 그 뒤에도 ping 이 온다
  7) 공유 메모리            : 같은 PC 의 rt_state_peek 가 소켓 없이 최신 상태를 읽는다
  8) 클라이언트 둘          : 답(ACK)은 보낸 쪽에만 간다 (ROUTER 는 보낸 쪽의 신원으로 돌려보낸다), 상태는 둘 다 받는다
  9) 느린 구독자            : 1초 안 읽으면 wait_state() 는 1초 묵은 상태를 준다 — 버려지는 것이 아니라 늦게 온다.
                              latest_state() 는 최신, conflate 클라이언트는 최신 한 장 + 건너뛴 수를 빈 번호로 센다
                              (11/11 밤에 더함: 이 길은 시험이 없었고, 문서가 "1초 넘으면 노드가 버리고 센다"고 틀리게 말하고 있었다)
 10) 끝날 때 센 값          : SIGTERM 으로 끝내면 status JSON 에 거절 수·워치독·불법 전이 0
 11) 노드가 다시 뜨면        : 같은 SDK 객체가 다시 붙는다(ZeroMQ 가 다시 연결). 번호가 처음으로 돌아간 것을 빈 번호로 세지 않는다
 12) 우편함이 차면          : 10 Hz 노드에 목표 200개를 한꺼번에 → 우편함(64칸)이 차서 ring_full 로 답한다, 그 뒤에도 ping

실행: RT_ZMQ_NODE=<빌드 폴더>/rt_zmq_node python3 sdk/python/tests/test_zmq_node.py
      (rt_state_peek 는 같은 폴더에서 찾는다. pyzmq 가 있어야 한다)
"""
import json
import os
import signal
import socket
import struct
import subprocess
import sys
import tempfile
import time

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
from rtsdk import RobotClient, CommandRejected, wire  # noqa: E402

DOF = 6


def free_port():
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def start_node(binary, state_port, cmd_port, shm, status_json, hz=1000):
    cmd = [binary, "--dof", str(DOF), "--loop-hz", str(hz), "--publish-hz", str(hz), "--prio", "0",
           "--state-ep", f"tcp://127.0.0.1:{state_port}", "--cmd-ep", f"tcp://127.0.0.1:{cmd_port}",
           "--shm", shm, "--status-json", status_json]
    return subprocess.Popen(cmd, stderr=subprocess.PIPE, text=True)


def main():
    binary = os.environ.get("RT_ZMQ_NODE", "build/zmq_adapter/rt_zmq_node")
    if not os.path.exists(binary):
        sys.exit(f"노드 실행 파일이 없음: {binary} (RT_ZMQ_NODE 로 경로를 준다)")
    peek = os.path.join(os.path.dirname(binary), "rt_state_peek")
    sp, cp = free_port(), free_port()
    shm = f"/rt_state_test_{os.getpid()}"
    status_json = os.path.join(tempfile.mkdtemp(), "status.json")
    node = start_node(binary, sp, cp, shm, status_json)
    try:
        with RobotClient("127.0.0.1", sp, cp, timeout_s=2.0) as robot:
            # 1) info · ping
            info = robot.info()
            assert info["dof"] == DOF and info["loop_hz"] == 1000 and info["protocol_version"] == 1, info
            rtt = [robot.ping() for _ in range(20)]
            print(f"  1) info 관절 {info['dof']}, {info['loop_hz']} Hz, zmq {info['zmq']} · ping 중앙 {sorted(rtt)[10] * 1e3:.3f} ms")

            # 2) 목표를 따라간다 (100 Hz 로 0.5초)
            s = robot.wait_state(2.0)
            assert s.robot_state in ("READY", "FAULT"), s.robot_state  # 시작은 명령 없음 → 워치독이 걸려 있다
            last_seq = 0
            for _ in range(50):
                last_seq = robot.send_target([0.3] * DOF)
                t_last = time.monotonic()  # 마지막 명령의 ACK 를 받은 때 (sleep 뒤가 아니라 — 처음엔 sleep 뒤에 재서 40 ms 로 보였다)
                time.sleep(0.01)
            s = robot.wait_until(lambda st: st.robot_state == "RUNNING" and abs(st.position[0] - 0.3) < 0.02, 2.0)
            print(f"  2) 목표 0.3 rad → 위치 {s.position[0]:.4f}, 상태 {s.robot_state}")

            # 3) 명령 번호가 돌아온다
            s = robot.wait_until(lambda st: st.cmd_seq == last_seq, 1.0)
            print(f"  3) STATE 의 cmd_seq = 마지막 명령 번호 {last_seq}")

            # 4) 끊기면 멈춘다 (워치독 50 ms) — 마지막 명령을 보낸 때부터 FAULT 를 본 때까지
            s = robot.wait_until(lambda st: st.robot_state == "FAULT", 1.0)
            waited = (time.monotonic() - t_last) * 1e3
            assert 45 <= waited < 500, waited
            pos = s.position[0]
            time.sleep(0.2)
            s2 = robot.latest_state() or robot.wait_state()
            assert s2.robot_state == "FAULT" and abs(s2.position[0] - pos) < 1e-3, (s2.robot_state, pos, s2.position[0])
            print(f"  4) 마지막 명령 {waited:.0f} ms 뒤 FAULT (워치독 50 ms), 0.2초 뒤에도 위치 그대로 ({pos:.4f})")

            # 5) 다시 오면 복구
            for _ in range(20):
                robot.send_target([0.1] * DOF)
                time.sleep(0.01)
            s = robot.wait_until(lambda st: st.robot_state in ("READY", "RUNNING"), 1.0)
            print(f"  5) 명령을 다시 보내자 {s.robot_state}")

            # 6) 나쁜 패킷 — 노드가 거절하고 살아 있다
            _, acked, status = robot.send_raw(b"garbage-bytes")
            assert status == "bad_packet", status
            try:
                robot.send_target([0.0] * (DOF + 1))
                raise AssertionError("관절 수가 다른 명령을 받아들임")
            except CommandRejected as e:
                assert e.status == "bad_dof"
            nan_body = wire.TARGET_FIXED.pack(DOF, 0) + struct.pack(f"<{DOF}d", *([0.0] * (DOF - 1) + [float("nan")]))
            _, acked, status = robot.send_raw(wire.encode(wire.TARGET, 999, time.monotonic_ns(), nan_body))
            assert (acked, status) == (999, "bad_value"), (acked, status)
            _, _, status = robot.send_raw(wire.encode(42, 1000, 0))
            assert status == "unknown_type", status
            assert robot.ping() < 1.0
            print("  6) 쓰레기 → bad_packet, 관절 수 다름 → bad_dof, NaN → bad_value, 모르는 type → unknown_type, 그 뒤에도 ping 응답")

            # 7) 공유 메모리
            if os.path.exists(peek):
                for _ in range(5):
                    robot.send_target([0.2] * DOF, wait_ack=False)
                    time.sleep(0.02)
                out = subprocess.run([peek, "--shm", shm, "--count", "3", "--interval-ms", "10"], capture_output=True, text=True, timeout=5)
                rows = [json.loads(line) for line in out.stdout.splitlines()]
                assert len(rows) == 3 and all("iter" in r for r in rows), out.stdout + out.stderr
                assert rows[-1]["iter"] > rows[0]["iter"] and rows[-1]["dof"] == DOF
                assert max(r["age_ms"] for r in rows) < 50, rows
                print(f"  7) rt_state_peek: iter {rows[0]['iter']} → {rows[-1]['iter']}, 나이 최대 {max(r['age_ms'] for r in rows):.2f} ms")
            else:
                print("  7) rt_state_peek 이 없어 건너뜀")

            # 8) 클라이언트 둘 — 답은 보낸 쪽에만, 상태는 둘 다
            with RobotClient("127.0.0.1", sp, cp, timeout_s=2.0) as other:
                other.wait_state(2.0)
                seqs = [robot.send_target([0.2] * DOF, wait_ack=False) for _ in range(30)]
                for _ in range(10):
                    other.ping()  # 그사이 other 에 잘못 온 ACK 가 있으면 other 의 답 목록에 쌓인다
                time.sleep(0.05)
                robot.ping()
                got = [robot.ack_status(q) for q in seqs]
                assert got == ["ok"] * len(seqs), got
                stray = [q for q in seqs if other.ack_status(q) is not None]
                assert not stray, f"다른 클라이언트에 답이 갔다: {stray}"
                s1, s2 = robot.latest_state() or robot.wait_state(), other.latest_state() or other.wait_state()
                print(f"  8) 클라이언트 둘: 목표 {len(seqs)}개의 답은 보낸 쪽에 {got.count('ok')}/{len(seqs)}, 다른 쪽 {len(stray)} · "
                      f"상태는 둘 다 (iter {s1.iter}, {s2.iter})")

            # 9) 느린 구독자 — 버려지지 않고 늦게 온다. 최신이 필요하면 latest_state() 또는 conflate
            with RobotClient("127.0.0.1", sp, cp, timeout_s=2.0, conflate=True) as newest:
                newest.wait_state(2.0)
                robot.latest_state()  # 쌓인 것을 비우고 시작
                skipped0 = newest.states_missed
                time.sleep(1.0)  # 1초 동안 아무도 읽지 않는다 (1 kHz → 약 1,000장이 쌓인다)
                old = robot.wait_state()  # 쌓인 것 중 가장 오래된 것
                age_old = (time.monotonic_ns() - old.rt_stamp_ns) / 1e6
                new = robot.latest_state()
                age_new = (time.monotonic_ns() - new.rt_stamp_ns) / 1e6
                n = newest.latest_state()
                skipped = newest.states_missed - skipped0
                assert age_old > 500, age_old  # 1초 전 것이 그대로 남아 있다 — 버려지지 않았다
                assert age_new < 100, age_new
                assert n is not None and skipped > 500, (n, skipped)  # conflate: 사이의 것은 빈 번호로 센다 (셈이 0 이 아닌 경우)
                print(f"  9) 느린 구독자: 1초 안 읽은 뒤 wait_state() 는 {age_old:.0f} ms 묵은 상태, latest_state() 는 {age_new:.1f} ms · "
                      f"conflate 클라이언트는 최신 한 장 + 건너뛴 {skipped}장을 빈 번호로")
            missed = robot.states_missed

            # 10) 끝날 때 센 값
            node.send_signal(signal.SIGTERM)
            node.wait(timeout=5)
            st = json.load(open(status_json))
            assert node.returncode == 0, node.returncode
            assert st["rejected"]["bad_packet"] >= 1 and st["rejected"]["bad_dof"] >= 1 and st["rejected"]["bad_value"] >= 1, st
            assert st["illegal_events"] == 0 and st["watchdog_trips"] >= 1 and st["state_drops"] == 0, st
            print(f" 10) 끝: 패킷 {st['packets']}, 명령 {st['targets_ok']}, 상태 {st['states_sent']} (보내기 실패 {st['states_send_dropped']}), "
                  f"SDK 가 놓친 상태 {missed}, 워치독 {st['watchdog_trips']}, 불법 전이 {st['illegal_events']}")

            # 11) 노드가 다시 뜨면 — 같은 포트, 같은 SDK 객체. 이번 노드는 10 Hz (12 를 위해)
            status2 = os.path.join(os.path.dirname(status_json), "status2.json")
            node = start_node(binary, sp, cp, "", status2, hz=10)
            s = robot.wait_state(5.0)
            while s.seq > 1000:  # 앞 노드의 것이 남아 있으면 넘긴다
                s = robot.wait_state(5.0)
            assert robot.ping() < 1.0 and robot.info()["loop_hz"] == 10
            assert robot.states_missed == missed, (missed, robot.states_missed)  # 번호가 처음으로 돌아간 것은 빈 번호가 아니다
            print(f" 11) 노드를 다시 띄우자 같은 SDK 객체가 다시 붙음: 새 노드의 상태 번호 {s.seq}, 빈 번호 셈 그대로 {robot.states_missed}")

            # 12) 우편함이 차면 — 10 Hz 루프는 100 ms 에 한 번 우편함을 비운다. 그 사이에 200개를 넣으면 넘친다
            seqs = [robot.send_target([0.1] * DOF, wait_ack=False) for _ in range(200)]
            time.sleep(0.3)
            robot.ping()
            got = [robot.ack_status(q) for q in seqs]
            full = got.count("ring_full")
            assert got.count("ok") + full == len(seqs) and full >= 1, {k: got.count(k) for k in set(got)}
            assert robot.ping() < 1.0
            node.send_signal(signal.SIGTERM)
            node.wait(timeout=5)
            st2 = json.load(open(status2))
            assert node.returncode == 0 and st2["rejected"]["ring_full"] == full, (node.returncode, st2)
            print(f" 12) 목표 200개를 한꺼번에: ok {got.count('ok')}, ring_full {full} (64칸 링은 한 칸을 비워 둬서 63개까지) — 노드도 같은 수를 셈, 그 뒤에도 ping")
    finally:
        if node.poll() is None:
            node.kill()
            node.wait()
    print("OK: rt_zmq_node 끝-대-끝 12단계 (info·ping · 추종 · cmd_seq · 워치독 · 복구 · 나쁜 패킷 · 공유 메모리 · 클라이언트 둘 · "
          "느린 구독자 · 종료 · 다시 연결 · 우편함 가득 참)")


if __name__ == "__main__":
    main()
