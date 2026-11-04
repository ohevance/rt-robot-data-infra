#!/usr/bin/env python3
"""기록(MCAP) → 표(CSV) + 검증 요약 — "로깅·전처리 자동화"의 최소 한 벌.

하는 일
  1) rosbag2 폴더를 열어 세 토픽을 읽는다 (rosbag2_py + 메시지 역직렬화)
  2) /joint_states 를 joint_states.csv 로 (시각, 관절별 위치·속도), /joint_command 를 joint_command.csv 로,
     /rt_status 의 JSON 을 rt_status.csv 로 (wake/work p99 등 숫자 열만)
  3) 검증 요약 summary.md:
     - 토픽별 메시지 수·기간·실제 주기(Hz) ← 발행 주기가 설계값(100/50/1 Hz)과 맞는가
     - 시간 틈(설계 주기의 3배 넘게 벌어진 곳) ← 기록이 끊긴 구간
     - 관절별 추종 오차: 같은 시각의 목표(/joint_command) 대비 위치(/joint_states) 의 |차이| 평균·최대 ← 중력 처짐 같은 것이 여기 나온다
     - rt_status: wake_us·work_us p99 의 최대, 드롭 합계

읽는 순서: open_bag → read_messages → write_joint_csv → write_status_csv → tracking_error → write_summary → main
사용:  python3 data_pipeline/bag_to_csv.py build/bags/run_20261104_140000           # 결과는 같은 폴더의 csv/ 아래
전제: ROS 2 환경 (rosbag2_py, sensor_msgs 가 보이는 터미널)
"""
import csv
import json
import os
import sys

import rosbag2_py
from rclpy.serialization import deserialize_message
from rosidl_runtime_py.utilities import get_message

EXPECTED_HZ = {"/joint_states": 100.0, "/joint_command": 50.0, "/rt_status": 1.0}
GAP_FACTOR = 3.0   # 설계 주기의 몇 배가 벌어지면 "틈"으로 보나


def open_bag(bag_dir):
    """rosbag2 폴더를 연다. 저장 형식(mcap/sqlite3)은 metadata 에서 자동으로 고른다"""
    storage = rosbag2_py.StorageOptions(uri=bag_dir, storage_id="")
    converter = rosbag2_py.ConverterOptions(input_serialization_format="cdr", output_serialization_format="cdr")
    reader = rosbag2_py.SequentialReader()
    reader.open(storage, converter)
    type_of = {}
    for topic in reader.get_all_topics_and_types():
        type_of[topic.name] = get_message(topic.type)
    return reader, type_of


def read_messages(reader, type_of):
    """토픽 이름 -> [(초, 메시지), ...]. 시각은 기록된 수신 시각(ns) 을 초로"""
    messages = {}
    while reader.has_next():
        topic, raw, t_ns = reader.read_next()
        if topic not in type_of:
            continue
        msg = deserialize_message(raw, type_of[topic])
        if topic not in messages:
            messages[topic] = []
        messages[topic].append((t_ns / 1e9, msg))
    return messages


def write_joint_csv(path, rows, with_velocity):
    """JointState 목록 → CSV. 열: t, j0..jN (위치) [, v0..vN (속도)]"""
    if len(rows) == 0:
        return 0
    dof = len(rows[0][1].position)
    header = ["t_s"]
    for j in range(dof):
        header.append(f"pos_{j}")
    if with_velocity:
        for j in range(dof):
            header.append(f"vel_{j}")
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(header)
        for t, msg in rows:
            line = [f"{t:.6f}"]
            for value in msg.position:
                line.append(f"{value:.6f}")
            if with_velocity:
                for value in msg.velocity:
                    line.append(f"{value:.6f}")
            w.writerow(line)
    return len(rows)


def write_status_csv(path, rows):
    """/rt_status 의 JSON 에서 숫자 열만 뽑아 CSV. 반환: (행 수, wake_p99 최대, work_p99 최대, 드롭 합)"""
    header = ["t_s", "iter", "wake_p50", "wake_p99", "wake_max", "work_p50", "work_p99", "work_max",
              "timing_drops", "state_drops", "state", "watchdog", "backend"]
    wake_p99_max = 0.0
    work_p99_max = 0.0
    drops = 0
    count = 0
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(header)
        for t, msg in rows:
            try:
                d = json.loads(msg.data)
            except ValueError:
                continue
            wake = d.get("wake_us", {})
            work = d.get("work_us", {})
            w.writerow([f"{t:.3f}", d.get("iter"), wake.get("p50"), wake.get("p99"), wake.get("max"),
                        work.get("p50"), work.get("p99"), work.get("max"), d.get("timing_drops"), d.get("state_drops"),
                        d.get("state"), d.get("watchdog"), d.get("backend")])
            wake_p99_max = max(wake_p99_max, float(wake.get("p99") or 0.0))
            work_p99_max = max(work_p99_max, float(work.get("p99") or 0.0))
            drops = int(d.get("timing_drops") or 0) + int(d.get("state_drops") or 0)   # 누적값이므로 마지막 것이 합계
            count += 1
    return count, wake_p99_max, work_p99_max, drops


def rate_and_gaps(rows, expected_hz):
    """메시지 시각 목록으로 (기간 초, 실제 Hz, 틈 목록[(시작, 길이)]) 를 낸다"""
    if len(rows) < 2:
        return 0.0, 0.0, []
    t_first = rows[0][0]
    t_last = rows[-1][0]
    duration = t_last - t_first
    hz = (len(rows) - 1) / duration if duration > 0 else 0.0
    gap_limit = GAP_FACTOR / expected_hz
    gaps = []
    for i in range(1, len(rows)):
        dt = rows[i][0] - rows[i - 1][0]
        if dt > gap_limit:
            gaps.append((rows[i - 1][0] - t_first, dt))
    return duration, hz, gaps


def tracking_error(states, commands):
    """관절별 |목표 − 위치| 의 평균·최대. 각 상태 시각에 대해 '가장 최근 목표' 를 쓴다 (목표는 50 Hz, 상태는 100 Hz)"""
    if len(states) == 0 or len(commands) == 0:
        return []
    dof = len(states[0][1].position)
    sums = [0.0] * dof
    maxes = [0.0] * dof
    used = 0
    ci = 0
    for t, st in states:
        while ci + 1 < len(commands) and commands[ci + 1][0] <= t:
            ci += 1
        if commands[ci][0] > t:
            continue   # 아직 첫 목표가 오기 전
        target = commands[ci][1].position
        if len(target) != dof:
            continue
        for j in range(dof):
            err = abs(target[j] - st.position[j])
            sums[j] += err
            if err > maxes[j]:
                maxes[j] = err
        used += 1
    result = []
    for j in range(dof):
        mean = sums[j] / used if used > 0 else 0.0
        result.append((j, mean, maxes[j]))
    return result


def write_summary(path, bag_dir, messages, status_stats, errors, joint_names):
    lines = [f"# 기록 검증 요약 — `{bag_dir}`", ""]
    lines.append("## 토픽별 메시지 수·주기·틈")
    lines.append("")
    lines.append("| 토픽 | 메시지 | 기간(초) | 실제 Hz | 설계 Hz | 틈(>3주기) |")
    lines.append("|---|---:|---:|---:|---:|---:|")
    for topic, expected in EXPECTED_HZ.items():
        rows = messages.get(topic, [])
        duration, hz, gaps = rate_and_gaps(rows, expected)
        lines.append(f"| `{topic}` | {len(rows)} | {duration:.1f} | {hz:.1f} | {expected:.0f} | {len(gaps)} |")
        for start, length in gaps[:5]:
            lines.append(f"|  ↳ 틈 | | {start:.2f}초 지점 | {length * 1000:.0f} ms | | |")
    lines.append("")
    count, wake_p99_max, work_p99_max, drops = status_stats
    lines.append("## RT 상태 (rt_status)")
    lines.append("")
    lines.append(f"- 통계 줄 {count}개 · wake_us p99 최대 {wake_p99_max:.1f} us · work_us p99 최대 {work_p99_max:.1f} us · 드롭 합계 {drops}")
    lines.append("")
    if len(errors) > 0:
        lines.append("## 추종 오차 |목표 − 위치| (rad)")
        lines.append("")
        lines.append("| 관절 | 평균 | 최대 |")
        lines.append("|---|---:|---:|")
        for j, mean, mx in errors:
            name = joint_names[j] if j < len(joint_names) else str(j)
            lines.append(f"| {name} | {mean:.4f} | {mx:.4f} |")
        lines.append("")
        lines.append("- 평균 오차가 한 관절만 유독 크면(예: 어깨 Pitch) 중력 처짐을 의심한다. 최대 오차는 목표가 뛸 때(변화량 제한 0.05 rad/주기로 따라가는 동안) 커진다.")
    with open(path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")


def main():
    if len(sys.argv) < 2:
        print("사용: python3 data_pipeline/bag_to_csv.py <bag 폴더>")
        return 2
    bag_dir = sys.argv[1].rstrip("/")
    out_dir = os.path.join(bag_dir, "csv")
    os.makedirs(out_dir, exist_ok=True)

    reader, type_of = open_bag(bag_dir)
    messages = read_messages(reader, type_of)
    states = messages.get("/joint_states", [])
    commands = messages.get("/joint_command", [])
    statuses = messages.get("/rt_status", [])

    n_states = write_joint_csv(os.path.join(out_dir, "joint_states.csv"), states, with_velocity=True)
    n_commands = write_joint_csv(os.path.join(out_dir, "joint_command.csv"), commands, with_velocity=False)
    status_stats = write_status_csv(os.path.join(out_dir, "rt_status.csv"), statuses)
    errors = tracking_error(states, commands)
    joint_names = []
    if len(states) > 0:
        joint_names = list(states[0][1].name)
    write_summary(os.path.join(out_dir, "summary.md"), bag_dir, messages, status_stats, errors, joint_names)

    print(f"joint_states {n_states}행, joint_command {n_commands}행, rt_status {status_stats[0]}행 → {out_dir}/")
    with open(os.path.join(out_dir, "summary.md"), encoding="utf-8") as f:
        print(f.read())
    return 0


if __name__ == "__main__":
    sys.exit(main())
