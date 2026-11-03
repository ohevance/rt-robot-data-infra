# MuJoCo 백엔드 — 같은 제어 코드를 "물리가 있는 로봇" 위에서 돌린다 (D5)

코드는 `rt_control/rt_core/include/rt_core/mujoco_backend.hpp`, `rt_control/rt_core/src/mujoco_backend.cpp` 에 있다.
이 폴더는 설치·실행 안내만.

```
 joint_command ─▶ ControlStep ─write_command(목표)─▶ MujocoBackend: ctrl[액추에이터]=목표 → mj_step ×N ─▶ 물리 모델(SO-ARM100)
                              ◀─read_state(위치·속도)─                qpos / qvel ◀─────────────────────────┘
```

| 구분 | SimLagBackend (D1) | MujocoBackend (D5) |
|---|---|---|
| 무엇 | "목표를 천천히 따라간다" 수식 한 줄 | 관절 한계·중력·접촉·모터(position actuator)가 있는 물리 시뮬레이션 |
| 한 주기 비용 | ~0.1 us | SO-ARM100 6축에서 수십 us (테스트가 p50/p99/max 를 찍는다) |
| 용도 | 노드 전체 흐름 검증 | "1 kHz 안에 물리 한 걸음이 들어오는가", 로봇 모델만 바꿔 다른 로봇(ALLEX 등) |

## 1. 받기 (한 번)
```bash
cd ~/rt-robot-data-infra
bash scripts/get_mujoco.sh              # third_party/mujoco (라이브러리) + third_party/mujoco_menagerie/trs_so_arm100 (모델)
```
third_party/ 는 .gitignore 에 있다 (수백 MB, 저장소에 넣지 않는다).

## 2. rt_core 만 빌드해서 테스트 (ROS 2 없이)
```bash
cmake -S rt_control/rt_core -B build/rt_core_mj -DCMAKE_BUILD_TYPE=Release -DRT_CORE_WITH_MUJOCO=ON -DMUJOCO_DIR=$PWD/third_party/mujoco
cmake --build build/rt_core_mj -j
RT_MUJOCO_MODEL=$PWD/third_party/mujoco_menagerie/trs_so_arm100/scene.xml ctest --test-dir build/rt_core_mj --output-on-failure
```
기대 출력(테스트 `mujoco_backend`):
```
MujocoBackend: '.../scene.xml' nq=6 nu=6, 제어 주기 1.000 ms = mj_step 1번 x 1.000 ms
  관절 0: Rotation (joint 0, qpos[0], actuator 0 'Rotation')
  ...
관절 0: 시작 0.000 → 2초 뒤 0.2xx rad (목표 +0.300, 움직임 0.2xx)
한 주기 비용 (mj_step x 1 + read): p50 xx us, p99 xx us, max xxx us  (주기 1000 us)
OK: mujoco_backend
```
숫자 세 개(p50/p99/max)가 표①에 "물리 포함 한 주기 비용"으로 들어간다. 결과 JSON: `build/rt_core_mj/mujoco_backend_ci.json`.

## 3. ROS 2 노드에서 쓰기
```bash
source /opt/ros/jazzy/setup.bash
colcon build --packages-select rt_control_ros2 --cmake-args -DRT_CORE_WITH_MUJOCO=ON -DMUJOCO_DIR=$PWD/third_party/mujoco
source install/setup.bash
# 파라미터 파일이 백엔드를 고른다 (robots/so101.yaml → scripts/profile_to_params.py 가 생성)
./install/rt_control_ros2/lib/rt_control_ros2/rt_control_node --ros-args --params-file rt_control/ros2_adapter/config/so101_mujoco.params.yaml
```
`rt_status` JSON 에 `"backend": "mujoco"` 가 보이면 물리 위에서 돌고 있는 것. 모델 경로는 저장소 루트 기준 상대 경로이므로
루트에서 실행하거나 `export RT_REPO_ROOT=$HOME/rt-robot-data-infra` 를 둔다.

## 4. 관절 이름이 안 맞을 때
노드/테스트가 이렇게 멈추면:
```
MujocoBackend: 모델에 관절 'Rotation' 가 없음
  모델의 관절 (6개): joint_1 joint_2 ...
  → robots/*.yaml 의 mujoco.joints 를 위 관절 이름으로 맞추세요
```
`robots/so101.yaml` 의 `mujoco.joints` 를 출력된 이름으로 고치고 `profile_to_params.py` 를 다시 돌린다.
`joints: []` 로 비우면 모델의 1축 관절을 앞에서부터 6개 쓴다 (이름이 달라도 돈다).

## 5. 다른 로봇으로 바꾸기 (ALLEX 등)
`robots/<이름>.yaml` 에 `joints`(우리 쪽 이름), `mujoco.model`(xml 경로), `mujoco.joints`(모델 이름)만 적으면 끝.
제어 코드(`rt_core`)는 한 줄도 바뀌지 않는다 — 이것이 Backend 인터페이스를 둔 이유.

## 안 하는 것
- 화면(렌더링) 없음. 눈으로 보고 싶으면 별도로 `python3 -m mujoco.viewer --mjcf third_party/mujoco_menagerie/trs_so_arm100/scene.xml` (pip install mujoco).
- 토크 제어·중력 보상 없음. 모델의 position 액추에이터(kp)에 목표 각만 넣는다.
