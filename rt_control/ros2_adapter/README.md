# ros2_adapter — rt_core 를 감싸는 얇은 ROS 2 노드 (패키지 이름 `rt_control_ros2`)

```
 ros2 topic pub /joint_command ──▶ [ROS 2 실행기 스레드] ──cmd_ring──▶ [RT 스레드 1 kHz: ControlStep → SimLag 백엔드]
                                        ▲                                      │
                      /joint_states ◀───┘ (100 Hz)        ◀──state_ring────────┘
                      /rt_status    ◀───┘ (1 Hz, JSON: 지연 p50/p99/max, 드롭, 워치독)
```

## 빌드 (WSL, 한 번)
```bash
cd ~/rt-robot-data-infra
source /opt/ros/jazzy/setup.bash
colcon build --packages-select rt_control_ros2 --cmake-args -DCMAKE_BUILD_TYPE=Release
source install/setup.bash
```

## 실행 — 터미널 1 (노드)
WSL·일반 사용자는 SCHED_FIFO 권한이 없다. 터미널마다 한 번 아래 한 줄로 한도를 올리면 `sudo` 없이 실시간 우선순위를 쓸 수 있다.
```bash
sudo prlimit --pid $$ --rtprio=99 --memlock=unlimited
source /opt/ros/jazzy/setup.bash && source ~/rt-robot-data-infra/install/setup.bash
ros2 run rt_control_ros2 rt_control_node --ros-args --params-file ~/rt-robot-data-infra/rt_control/ros2_adapter/config/so101.params.yaml
```
**종료는 그 터미널에서 Ctrl+C.** 스크립트로 띄우고 `kill` 할 때는 `ros2 run` 껍데기가 아니라 노드 자체를 죽여야 한다:
```bash
~/rt-robot-data-infra/install/rt_control_ros2/lib/rt_control_ros2/rt_control_node --ros-args --params-file ... &   # 바이너리 직접 실행 → kill $! 이 노드를 죽인다
pkill -f rt_control_node    # 또는 이름으로
```
(권한 올리기를 생략하면 `rt_status` 의 `sched_fifo` 가 `false` 로 나온다. 동작은 하지만 일반 우선순위다.)

## 실행 — 터미널 2 (관찰)
```bash
source /opt/ros/jazzy/setup.bash && source ~/rt-robot-data-infra/install/setup.bash
ros2 topic echo /rt_status            # 1초마다 JSON 한 줄. watchdog: "tripped" (아직 명령이 없으니 정상)
ros2 topic hz /joint_states           # average rate: 100.0 근처
```

## 실행 — 터미널 3 (명령 보내기)
```bash
source /opt/ros/jazzy/setup.bash && source ~/rt-robot-data-infra/install/setup.bash
# 50 Hz 로 목표 위치를 계속 보낸다 → rt_status 의 watchdog 이 "ok" 로, joint_states 의 position 이 목표로 움직인다
ros2 topic pub -r 50 /joint_command sensor_msgs/msg/JointState "{position: [0.3, -0.2, 0.1, 0.0, 0.0, 0.5]}"
# Ctrl+C 로 끊으면 50 ms 뒤 watchdog 이 "tripped" 로 돌아가고 watchdog_trips 가 1 오른다 (안전 정지)
```

## 관찰할 숫자 (표③·면접용)
| 어디서 | 무엇 | 뜻 |
|---|---|---|
| `/rt_status` `wake_us` | p50 / p99 / max | ROS 2 노드 안에서도 RT 루프의 깨어남 지연이 측정기와 같은 수준인가 |
| `/rt_status` `timing_drops`, `state_drops` | 0 이어야 함 | 발행 스레드가 RT 를 따라가고 있는가 |
| `/rt_status` `watchdog`, `watchdog_trips` | 명령 끊으면 tripped, 다시 주면 ok | 안전 정지 동작 |
| `/rt_status` `step_limited` | 큰 목표를 처음 줄 때 증가 | 급변 명령 차단 동작 |
| `ros2 topic hz /joint_states` | 100 Hz | 발행 주기 |

## 파라미터 파일
`config/so101.params.yaml` 은 `robots/so101.yaml` 에서 `scripts/profile_to_params.py` 로 만든다. 손으로 고치지 않는다.
다른 로봇 = 다른 프로필 파일 → 같은 노드, 같은 명령.
