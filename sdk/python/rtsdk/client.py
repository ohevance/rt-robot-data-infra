"""로봇(rt_zmq_node)과 이야기하는 Python 클라이언트.

    from rtsdk import RobotClient
    with RobotClient("127.0.0.1") as robot:
        print(robot.info())                    # 관절 수·주기·백엔드·RT 여부
        robot.send_target([0.1] * 6)           # 목표 위치 (rad). 노드가 거절하면 CommandRejected
        s = robot.wait_state()                 # 다음 상태 한 장 (위치·속도·상태 머신·워치독)
        print(s.robot_state, s.position)

소켓 두 개 (ZeroMQ)
    SUB    ← 노드의 PUB (state_port, 기본 5555): STATE 를 받기만 한다. 느리게 읽어도 노드는 기다리지 않는다
           (노드 쪽 높은 물 표시 1,000개를 넘으면 노드가 버린다 → State.seq 의 빈 번호로 보인다)
    DEALER ↔ 노드의 ROUTER (cmd_port, 기본 5556): TARGET·PING·GET_INFO 를 보내고 ACK·PONG·INFO 를 받는다.
           REQ 가 아니라 DEALER 인 이유: REQ 는 "보내고 받기"를 번갈아야 해서 답 하나를 잃으면 소켓이 멈춘다.
           DEALER 는 명령을 연달아 보내고 답은 번호(seq)로 맞춘다 — 100 Hz 로 목표를 흘려보내는 쓰임에 맞다.

시간
    time.monotonic_ns() 는 리눅스의 CLOCK_MONOTONIC — 노드(C++ now_ns)와 같은 시계다. 그래서 같은 PC 에서는
    노드가 찍은 시각과 내 시각을 바로 뺄 수 있다. 다른 PC 면 뺄 수 없다 (두 시계의 차이가 섞인다 — E23 과 같은 이유).
    왕복(ping)과 "명령 → 상태에 반영" 은 내 시계 하나로 재므로 어디서나 맞다.
"""
import time

import zmq

from . import wire


class CommandRejected(RuntimeError):
    """노드가 명령을 받지 않았다. status: bad_dof · ring_full · bad_packet · unknown_type · bad_value"""

    def __init__(self, seq, status):
        super().__init__(f"명령 {seq} 거절: {status}")
        self.seq = seq
        self.status = status


class RobotClient:
    def __init__(self, host="127.0.0.1", state_port=5555, cmd_port=5556, timeout_s=1.0, conflate=False, context=None):
        """conflate=True 면 SUB 가 최신 한 장만 들고 있다 (UI 처럼 "지금 값"만 필요할 때). 기본은 전부 받는다."""
        self.timeout_ms = int(timeout_s * 1000)
        self._own_ctx = context is None
        self.ctx = context or zmq.Context()
        self.sub = self.ctx.socket(zmq.SUB)
        if conflate:
            self.sub.setsockopt(zmq.CONFLATE, 1)  # SUBSCRIBE 보다 먼저 정해야 한다
        self.sub.setsockopt(zmq.RCVHWM, 10000)
        self.sub.setsockopt(zmq.SUBSCRIBE, b"")
        self.sub.connect(f"tcp://{host}:{state_port}")
        self.cmd = self.ctx.socket(zmq.DEALER)
        self.cmd.setsockopt(zmq.LINGER, 0)
        self.cmd.connect(f"tcp://{host}:{cmd_port}")
        self._seq = 0
        self._acks = {}  # 내 seq → status (답을 기다리지 않고 보낸 명령의 답이 여기 모인다)
        self.bad_packets = 0  # 형식이 틀려 버린 패킷 수
        self.last_state_seq = None
        self.states_missed = 0  # 노드의 STATE 번호에 빈 칸이 생긴 수 (느리게 읽어 노드가 버렸다)
        self.states_received = 0  # 형식이 맞아 받아들인 STATE 수 (latest_state 가 건너뛴 것도 센다)

    # ---------------------------------------------------------------- 공통
    def _next_seq(self):
        self._seq = (self._seq + 1) & 0xFFFFFFFF
        return self._seq

    def _recv_cmd(self, timeout_ms):
        if not self.cmd.poll(timeout_ms):
            return None
        return self.cmd.recv()

    def _wait_reply(self, want_type, seq, timeout_ms=None):
        """want_type 의 답 중 seq 가 맞는 것을 기다린다. 도중에 온 ACK 는 _acks 에 적어 둔다."""
        deadline = time.monotonic() + (self.timeout_ms if timeout_ms is None else timeout_ms) / 1000.0
        while True:
            left = int((deadline - time.monotonic()) * 1000)
            if left < 0:
                raise TimeoutError(f"type {want_type} seq {seq} 의 답이 시간 안에 오지 않음 — 노드가 떠 있나?")
            data = self._recv_cmd(left)
            if data is None:
                continue
            try:
                h = wire.decode_header(data)
            except wire.WireError:
                self.bad_packets += 1
                continue
            if h.type == wire.ACK:
                _, acked, status = wire.decode_ack(data)
                self._acks[acked] = status
                if want_type == wire.ACK and acked == seq:
                    return data
            elif h.type == want_type and h.seq == seq:
                return data

    def _drain_acks(self):
        while True:
            data = self._recv_cmd(0)
            if data is None:
                return
            try:
                _, acked, status = wire.decode_ack(data)
                self._acks[acked] = status
            except wire.WireError:
                self.bad_packets += 1

    # ---------------------------------------------------------------- 명령
    def send_target(self, position, wait_ack=True):
        """목표 위치(rad)를 보낸다. 내 seq 를 돌려준다.
        wait_ack=True: 노드가 받았는지(ACK)까지 기다리고, 거절이면 CommandRejected.
        wait_ack=False: 보내기만 한다 (흘려보내기용). 답은 나중에 ack_status(seq) 로 본다."""
        wire.check_finite(position)
        seq = self._next_seq()
        self.cmd.send(wire.encode_target(seq, time.monotonic_ns(), position))
        if not wait_ack:
            self._drain_acks()
            return seq
        self._wait_reply(wire.ACK, seq)
        status = self._acks.pop(seq)
        if status != "ok":
            raise CommandRejected(seq, status)
        return seq

    def ack_status(self, seq):
        """흘려보낸 명령의 답. 아직 안 왔으면 None"""
        self._drain_acks()
        return self._acks.get(seq)

    def send_raw(self, data):
        """시험용: 아무 바이트나 보낸다 (형식 오류를 노드가 어떻게 다루는지 볼 때). ACK 를 돌려준다."""
        self.cmd.send(data)
        deadline = time.monotonic() + self.timeout_ms / 1000.0
        while time.monotonic() < deadline:
            reply = self._recv_cmd(max(1, int((deadline - time.monotonic()) * 1000)))
            if reply is not None:
                return wire.decode_ack(reply)
        raise TimeoutError("send_raw 의 답이 오지 않음")

    def ping(self):
        """왕복 시간(초). 내 시계 하나로 잰다 — 다른 PC 의 노드여도 맞다."""
        seq = self._next_seq()
        t0 = time.monotonic_ns()
        self.cmd.send(wire.encode(wire.PING, seq, t0))
        data = self._wait_reply(wire.PONG, seq)
        t1 = time.monotonic_ns()
        h = wire.decode_header(data)
        if h.stamp_ns != t0:
            raise wire.WireError("pong 의 stamp 가 보낸 것과 다름")
        return (t1 - t0) / 1e9

    def info(self):
        seq = self._next_seq()
        self.cmd.send(wire.encode(wire.GET_INFO, seq, time.monotonic_ns()))
        return wire.decode_info(self._wait_reply(wire.INFO, seq))

    # ---------------------------------------------------------------- 상태
    def _take_state(self, data):
        try:
            s = wire.decode_state(data)
        except wire.WireError:
            self.bad_packets += 1
            return None
        if self.last_state_seq is not None:
            gap = (s.seq - self.last_state_seq - 1) & 0xFFFFFFFF
            if gap < 0x80000000:  # 노드가 다시 시작해 번호가 처음으로 돌아간 경우는 빼고
                self.states_missed += gap
        self.last_state_seq = s.seq
        self.states_received += 1
        return s

    def wait_state(self, timeout_s=None):
        """다음 상태 한 장. 시간 안에 안 오면 TimeoutError"""
        timeout_ms = self.timeout_ms if timeout_s is None else int(timeout_s * 1000)
        deadline = time.monotonic() + timeout_ms / 1000.0
        while True:
            left = int((deadline - time.monotonic()) * 1000)
            if left < 0 or not self.sub.poll(max(left, 0)):
                if time.monotonic() >= deadline:
                    raise TimeoutError("상태가 오지 않음 — 노드가 떠 있나, 포트가 맞나?")
                continue
            s = self._take_state(self.sub.recv())
            if s is not None:
                return s

    def latest_state(self):
        """쌓여 있는 상태를 전부 읽고 가장 최신 한 장을 돌려준다 (없으면 None). 기다리지 않는다."""
        latest = None
        while self.sub.poll(0):
            s = self._take_state(self.sub.recv())
            if s is not None:
                latest = s
        return latest

    def wait_until(self, predicate, timeout_s=2.0):
        """predicate(state) 가 참이 되는 첫 상태를 돌려준다. 예: robot.wait_until(lambda s: s.robot_state == "FAULT")"""
        deadline = time.monotonic() + timeout_s
        while time.monotonic() < deadline:
            try:
                s = self.wait_state(max(0.01, deadline - time.monotonic()))
            except TimeoutError:
                break
            if predicate(s):
                return s
        raise TimeoutError("조건을 만족하는 상태가 시간 안에 오지 않음")

    # ---------------------------------------------------------------- 정리
    def close(self):
        self.sub.close(linger=0)
        self.cmd.close(linger=0)
        if self._own_ctx:
            self.ctx.term()

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.close()
