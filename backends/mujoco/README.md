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

## 6. ALLEX — 위로보틱스 공개 모델(48 자유도)을 같은 노드로 (E21)
회사가 2026-06-29 공개한 상체 휴머노이드 모델(`github.com/wirobotics-rih/allex_model`, BSD-3). 액추에이터 48개가 전부 position 서보라
SO-101 과 똑같은 방식으로 붙는다. 바뀌는 것은 프로필(`robots/allex.yaml`)뿐 — 제어 코드·백엔드·노드는 그대로다.

```bash
# [WSL 창] 1) 모델 받기 (약 250 MB, 고정 커밋 5e12052) — third_party/allex_model (gitignore)
bash scripts/get_allex.sh
#    출력 끝에  position actuators : 48  이 보이면 프로필(dof 48)과 맞는 것

# [WSL 창] 2) rt_core 테스트 (ROS 2 없이). 빌드는 §2 의 build/rt_core_mj 를 그대로 쓴다 (테스트 코드가 바뀌었으니 한 번 더 빌드)
cmake --build build/rt_core_mj -j
#    주기는 프로필과 같은 500 Hz(RT_MUJOCO_PERIOD_US=2000). 1 kHz 로 재려면 1000 (E21 1차)
RT_MUJOCO_MODEL=$PWD/third_party/allex_model/mjcf/scene.xml RT_MUJOCO_DOF=48 RT_MUJOCO_PERIOD_US=2000 \
RT_MUJOCO_JOINTS="$(python3 scripts/profile_joints.py robots/allex.yaml)" RT_MUJOCO_OUT=mujoco_backend_allex_wsl_500hz.json \
LD_LIBRARY_PATH=$PWD/third_party/mujoco/lib ./build/rt_core_mj/test_mujoco_backend
#    기대: "관절 0 (R_Shoulder_Pitch_Joint): 시작 … → 2초 뒤 … (움직임 0.29x)" 와 "한 주기 비용 (mj_step x 1 + read, 48 관절): p50 … p99 … max …  (주기 2000 us)" 그리고 OK: mujoco_backend
#    E21 실측(WSL): 1 kHz 336 / 622 / 1,785 → 500 Hz 327 / 1,000 / 1,589 us. p50 은 같고 p99 는 더 컸다(2 ms 의 50%) — 이유 후보와 반복 계획은 E21 4절
#    결과 JSON 은 현재 폴더 → docs/measurements/ 로 옮겨 커밋 (E21.md 3절 표에 숫자 기입). JSON 의 모델 경로는 third_party/ 부터만 적힌다(개인 경로 안 남김)

# [WSL 창] 3) ROS 2 노드에서 (§3 과 같은 빌드, 파라미터 파일만 ALLEX 로)
source install/setup.bash
./install/rt_control_ros2/lib/rt_control_ros2/rt_control_node --ros-args --params-file rt_control/ros2_adapter/config/allex_mujoco.params.yaml
#    노드는 프로필대로 500 Hz 로 돈다(allex_mujoco.params.yaml 의 loop_hz 500) — rt_status 의 work_us 는 2 ms 예산 기준으로 읽는다
#    다른 터미널: 48개 값 명령 (첫 관절 R_Shoulder_Pitch 만 0.3 rad, 나머지 0) 을 50 Hz 로
ros2 topic pub -r 50 /joint_command sensor_msgs/msg/JointState "{position: [0.3, $(python3 -c 'print(", ".join(["0.0"]*47))')]}"
#    또 다른 터미널: rt_status 의 work_us(제어 + 48 자유도 물리) 와 state 를 본다
ros2 topic echo /rt_status
```
관절 이름이 틀리면 §4 와 같은 메시지가 나오고 모델의 관절 이름 전체가 출력된다 — `robots/allex.yaml` 의 `mujoco.joints` 를 그 이름으로 맞춘다.
모델 timestep 2 ms = 프로필의 500 Hz 주기 — `mj_step` 1번이 모델 기본 걸음 그대로다. 1 kHz 로 돌리면 백엔드가 걸음을 1 ms 로 줄인다(올림 규칙, `tune_timestep`) — E21 1차에서 p99 622 us(예산의 62 %)·max 1 ms 초과였고, 그래서 500 Hz 가 기본이다(DECISIONS 11/06). 기록 파이프라인(E20)도 `data_pipeline/record.sh` 그대로 — 관절 48개 CSV 가 나온다.
