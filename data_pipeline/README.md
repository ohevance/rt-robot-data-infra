# data_pipeline — 로봇 데이터 기록 → 표 → 검증 (공고 ③ "로깅·전처리 자동화"의 최소 한 벌)

```
 rt_control_node ──/joint_states 100 Hz, /joint_command 50 Hz, /rt_status 1 Hz──▶ [record.sh: rosbag2 MCAP] ──▶ build/bags/run_<시각>/
                                                                                      │
                                                   [bag_to_csv.py] ◀──────────────────┘
                                                      ├─ csv/joint_states.csv · joint_command.csv · rt_status.csv   (표)
                                                      └─ csv/summary.md: 토픽별 주기·틈, RT 통계, 관절별 추종 오차   (검증)
```

| 파일 | 역할 |
|---|---|
| `record.sh N` | 토픽 3개를 N초 동안 MCAP 으로 기록 (`timeout -s INT` 로 곱게 닫는다) |
| `bag_to_csv.py <bag>` | MCAP → CSV 3개 + `summary.md` (주기 검증·틈 찾기·추종 오차) |

관제(fleet)의 1 Hz 텔레메트리가 "장치 → 서버" 로깅이라면, 이것은 "로봇 안" 고주기 데이터의 로깅이다. 둘은 목적이 다르다:
관제는 수백 대의 건강 상태(가볍게, 오래), 기록은 한 대의 제어 데이터(무겁게, 짧게 — 문제 구간 재현·학습 데이터).

## 사용 (ROS 2 환경, 노드가 떠 있을 때)
```bash
# 터미널 A: 노드 (MuJoCo)
./install/rt_control_ros2/lib/rt_control_ros2/rt_control_node --ros-args --params-file rt_control/ros2_adapter/config/so101_mujoco.params.yaml
# 터미널 B: 명령 + 기록 30초 + 표 변환
ros2 topic pub -r 50 /joint_command sensor_msgs/msg/JointState "{position: [0.3, -0.2, 0.1, 0.0, 0.0, 0.5]}" > /dev/null &
bash data_pipeline/record.sh 30
kill %1
python3 data_pipeline/bag_to_csv.py build/bags/run_<시각>      # record.sh 가 마지막 줄에 정확한 명령을 찍어 준다
```
`summary.md` 에서 볼 것: `/joint_states` 실제 Hz 가 100 에 가깝고 틈이 0 인가 · `wake_us p99 최대` · 추종 오차 표에서 어깨(shoulder_lift)만 평균 오차가 큰가(중력 처짐).

## 왜 이 정도만인가 (2주 계획)
- 구간 추출(사건 전후 N초만 잘라내기)·업로드·보존 정책은 넣지 않았다. 면접에서 "다음 단계"로 말한다: MCAP 은 토픽·시간 인덱스가 있어 구간 추출이 싸고, 업로드는 fleet 의 store-and-forward 와 같은 패턴(끊기면 보관, 붙으면 전송)으로 간다.
- CI 러너에는 ROS 2 가 없어 이 폴더는 CI 밖이다. WSL 에서 돌린 `summary.md` 를 `docs/measurements/` 에 넣는 것으로 증거를 남긴다.
