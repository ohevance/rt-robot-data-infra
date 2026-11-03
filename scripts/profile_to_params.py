#!/usr/bin/env python3
"""로봇 프로필(robots/*.yaml) → ROS 2 파라미터 파일(rt_control/ros2_adapter/config/*.params.yaml)

로봇 설정의 "원본"은 robots/*.yaml 하나다. ROS 2 노드는 ROS 파라미터 형식만 읽을 수 있으므로
이 스크립트가 변환한다. 손으로 두 파일을 따로 고치지 않기 위한 장치.

사용:  python3 scripts/profile_to_params.py robots/so101.yaml [--mode sim|real] [--prio 80] [--cpu -1]
출력:  rt_control/ros2_adapter/config/<name>.params.yaml
"""
import argparse
import os
import sys

import yaml  # python3-yaml (ROS 2 설치 시 함께 들어온다)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("profile", help="robots/so101.yaml 같은 로봇 프로필")
    ap.add_argument("--mode", choices=["sim", "real"], default="sim")
    ap.add_argument("--prio", type=int, default=80, help="SCHED_FIFO 우선순위 (0 = 일반 스케줄링)")
    ap.add_argument("--cpu", type=int, default=-1, help="고정할 CPU (-1 = 안 함)")
    ap.add_argument("--publish-hz", type=int, default=100)
    ap.add_argument("--out-dir", default="rt_control/ros2_adapter/config")
    a = ap.parse_args()

    with open(a.profile, encoding="utf-8") as f:
        p = yaml.safe_load(f)

    joints = p.get("joints") or []
    if not joints:
        print("프로필에 joints 가 없습니다", file=sys.stderr)
        return 2
    loop_hz = int(p.get("loop_hz", {}).get(a.mode, 1000))
    safety = p.get("safety", {})

    params = {
        "rt_control_node": {
            "ros__parameters": {
                "joint_names": [str(j) for j in joints],
                "loop_hz": loop_hz,
                "prio": a.prio,
                "cpu": a.cpu,
                "watchdog_ms": int(safety.get("watchdog_ms", 50)),
                "max_step_rad": float(safety.get("max_step_rad", 0.05)),
                "publish_hz": a.publish_hz,
                "sim_time_constant_s": 0.05,
            }
        }
    }

    os.makedirs(a.out_dir, exist_ok=True)
    out = os.path.join(a.out_dir, f"{p.get('name', 'robot')}.params.yaml")
    with open(out, "w", encoding="utf-8") as f:
        f.write(f"# 자동 생성: {a.profile} 에서 (scripts/profile_to_params.py). 손으로 고치지 말 것.\n")
        yaml.safe_dump(params, f, sort_keys=False, allow_unicode=True)
    print(f"wrote {out}  (dof={len(joints)}, loop_hz={loop_hz}, prio={a.prio})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
