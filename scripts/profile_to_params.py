#!/usr/bin/env python3
"""로봇 프로필(robots/*.yaml) → ROS 2 파라미터 파일(rt_control/ros2_adapter/config/*.params.yaml)

로봇 설정의 "원본"은 robots/*.yaml 하나다. ROS 2 노드는 ROS 파라미터 형식만 읽을 수 있으므로
이 스크립트가 변환한다. 손으로 두 파일을 따로 고치지 않기 위한 장치.

백엔드
  --backend profile (기본) : 프로필의 backend.<mode> 를 쓴다 (so101 의 sim 은 mujoco)
  --backend sim_lag        : MuJoCo 없이 1차 지연 모델로 (오늘 WSL 기본)
  --backend mujoco         : MuJoCo (빌드에 -DRT_CORE_WITH_MUJOCO=ON 필요)
  출력 파일 이름에 백엔드가 붙는다: so101.params.yaml (sim_lag), so101_mujoco.params.yaml (mujoco)

사용:  python3 scripts/profile_to_params.py robots/so101.yaml --backend sim_lag
       python3 scripts/profile_to_params.py robots/so101.yaml --backend mujoco
"""
import argparse
import os
import sys

import yaml  # python3-yaml (ROS 2 설치 시 함께 들어온다)


def build_params(p, a, loop_hz, backend):
    """프로필 + 명령행 옵션 → ROS 파라미터 dict"""
    safety = p.get("safety", {})
    joints = p.get("joints") or []
    mujoco = p.get("mujoco", {}) or {}
    sim_lag = p.get("sim_lag", {}) or {}
    params = {
        "joint_names": [str(j) for j in joints],
        "loop_hz": loop_hz,
        "prio": a.prio,
        "cpu": a.cpu,
        "watchdog_ms": int(safety.get("watchdog_ms", 50)),
        "max_step_rad": float(safety.get("max_step_rad", 0.05)),
        "publish_hz": a.publish_hz,
        "backend": backend,
        "sim_time_constant_s": float(sim_lag.get("time_constant_s", 0.05)),
        "mujoco_model": str(mujoco.get("model", "")),
    }
    mujoco_joints = [str(j) for j in (mujoco.get("joints") or [])]
    if len(mujoco_joints) > 0:
        # 비어 있으면 키 자체를 빼는 이유: ROS 2 파라미터 파서는 빈 배열([])의 타입을 정하지 못해 노드 시작이 실패한다
        params["mujoco_joints"] = mujoco_joints
    return params


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("profile", help="robots/so101.yaml 같은 로봇 프로필")
    ap.add_argument("--mode", choices=["sim", "real"], default="sim")
    ap.add_argument("--backend", choices=["profile", "sim_lag", "mujoco"], default="profile")
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

    backend = a.backend
    if backend == "profile":
        backend = str(p.get("backend", {}).get(a.mode, "sim_lag"))
    if backend not in ("sim_lag", "mujoco"):
        print(f"이 노드가 아직 지원하지 않는 백엔드: {backend} (sim_lag | mujoco). --backend 로 지정하세요", file=sys.stderr)
        return 2

    params = build_params(p, a, loop_hz, backend)
    doc = {"rt_control_node": {"ros__parameters": params}}

    suffix = ""
    if backend != "sim_lag":
        suffix = "_" + backend
    os.makedirs(a.out_dir, exist_ok=True)
    out = os.path.join(a.out_dir, f"{p.get('name', 'robot')}{suffix}.params.yaml")
    with open(out, "w", encoding="utf-8") as f:
        f.write(f"# 자동 생성: {a.profile} 에서 (scripts/profile_to_params.py --backend {a.backend}). 손으로 고치지 말 것.\n")
        yaml.safe_dump(doc, f, sort_keys=False, allow_unicode=True)
    print(f"wrote {out}  (dof={len(joints)}, loop_hz={loop_hz}, backend={backend}, prio={a.prio})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
