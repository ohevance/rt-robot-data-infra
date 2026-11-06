#!/usr/bin/env python3
# 로봇 프로필(robots/*.yaml)의 MuJoCo 관절 이름을 쉼표로 이어 한 줄로 출력한다.
#   테스트/CI 가 RT_MUJOCO_JOINTS 에 그대로 쓰기 위한 것 — 관절 이름을 두 군데(프로필·CI)에 적지 않는다.
# 사용: python3 scripts/profile_joints.py robots/allex.yaml          → "R_Shoulder_Pitch_Joint,...,Neck_Yaw_Joint"
#      python3 scripts/profile_joints.py robots/allex.yaml --count  → 48
import sys

import yaml


def main():
    if len(sys.argv) < 2:
        print("사용: profile_joints.py robots/<로봇>.yaml [--count]", file=sys.stderr)
        return 2
    profile = yaml.safe_load(open(sys.argv[1], encoding="utf-8"))
    joints = (profile.get("mujoco") or {}).get("joints") or profile.get("joints") or []
    if "--count" in sys.argv:
        print(len(joints))
    else:
        print(",".join(str(j) for j in joints))
    return 0


if __name__ == "__main__":
    sys.exit(main())
