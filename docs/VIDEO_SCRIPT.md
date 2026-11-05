# 2분 영상 대본 (v2, 2026-11-05) — 화면 + 터미널 자막 상자 + 합성 음성(TTS)

목적: 공고 4항목을 **돌아가는 화면과 숫자**로 2분 안에. 얼굴·육성 없음. 내레이션은 Clipchamp 의 "텍스트 음성 변환"(한국어 음성)으로 아래 문장을 그대로 붙여 넣어 만든다.
자막은 편집기에서 얹지 않는다 — 장면마다 터미널에서 `bash docs/video/cue.sh <N>` 을 치면 **자막 상자**(제목 + 핵심 숫자)가 뜬다. 치는 명령은 `docs/video/cues.sh`(history 로 불러 씀).
총 2:00, 장면 6개 + 제목 카드. 내레이션 전체 약 620자(공백 포함) — TTS 1.0 배속에서 약 1분 50초. 길면 1.1 배속.

## 녹화 전 체크리스트 (15분) — 창을 이렇게 띄운다
| 창 | 명령 | 확인 |
|---|---|---|
| [WSL A] 관제 | `docker compose -f fleet/docker-compose.yml up -d` → `python3 fleet/collector/collector.py --qos 1` | 1초마다 `online=50 backlog=0 db_err=0` (가상 장치를 띄운 뒤) |
| [WSL B] 가상 장치 | `python3 fleet/agent/virtual_fleet.py --count 50 --rate 1 --telemetry-qos 1 --keepalive 30` | 조용히 돈다 |
| [WSL C] 노드 | `pkill -f rt_control_node; ros2 daemon stop; ./install/rt_control_ros2/lib/rt_control_ros2/rt_control_node --ros-args --params-file rt_control/ros2_adapter/config/so101_mujoco.params.yaml` | `backend=mujoco dof=6 loop=1000 Hz` |
| [WSL D] 명령 50 Hz | `ros2 topic pub -r 50 /joint_command sensor_msgs/msg/JointState "{position: [0.3, -0.2, 0.1, 0.0, 0.0, 0.5]}"` | 조용히 돈다 |
| **[WSL E] 녹화 창** | 글꼴 20pt, 창 크기 1600×900 쯤, 어두운 배경. `history -r docs/video/cues.sh` | ↑ 로 명령이 나온다 |
| 브라우저 탭 1 | `http://localhost:3000` Grafana "Fleet Overview", Last 5 minutes, 자동 새로고침 5 s | 초당 메시지 ≈ 50, 온라인 50 |
| 브라우저 탭 2 | `https://github.com/ohevance/rt-robot-data-infra` README (숫자 한눈에 표가 보이게) | 배지 초록 |
| 브라우저 탭 3 | 같은 저장소 → Actions | 마지막 run ✓ |
| Pi (선택) | 전원 켜 두기 → [WSL E] 에서 `ssh mgoh@192.168.45.250 true` 로 비밀번호 한 번 입력해 두기(녹화 중 또 묻지 않게 하려면 `ssh-copy-id mgoh@192.168.45.250`) | `uname -r` 에 realtime |
| 녹화 도구 | Windows 캡처 도구(Win+Shift+S → 동영상) 영역을 녹화 창에 맞춤, 또는 OBS 전체 화면 | 시험 녹화 5초 |

장면 하나당 파일 하나로 찍는다(`scene2.mp4` …). 실수하면 그 장면만 다시. 명령 출력이 길면 스크롤하지 말고 그 자리에서 잠깐(3초) 멈춘다 — 편집 때 자르기 쉽다.

## 장면 0 — 0:00~0:08 — 제목 카드
화면: [WSL E] `bash docs/video/cue.sh 0` (상자만 8초).
TTS: "휴머노이드 로봇 회사의 실시간 제어, 데이터 인프라 직무를 겨냥해 2주 동안 만든 저장소입니다. 공고 네 항목마다 코드와 측정 숫자, 그리고 푸시마다 다시 증명하는 CI 가 있습니다."

## 장면 1 — 0:08~0:18 — README 한 장
화면: 브라우저 탭 2 — "직무 요구 ↔ 산출물 ↔ 수치" 표 → 아래로 "숫자 한눈에" 표까지 천천히 스크롤 → 초록 배지.
TTS: "숫자 옆에는 항상 어디서 쟀는지를 붙입니다. 가상 머신 참고값과 라즈베리파이 실측을 섞지 않습니다."

## 장면 2 — 0:18~0:48 — 표① 실시간 루프 (영상의 핵심 숫자)
화면: [WSL E] `bash docs/video/cue.sh 2` (상자 5초) → (Pi 켜 두었으면) `ssh … 'uname -r; …'` 로 `6.8.0-2054-raspi-realtime / realtime=1 / isolated=3` → `grep … table1_pi4.md` 로 다섯 줄(695→132, 781→301→189) → `./build/rt_core/jitter_bench --no-rt --seconds 3` 로 WSL 에서 표가 찍히는 모습 3초.
TTS: "1 킬로헤르츠 제어 루프입니다. 핵심은 평균이 아니라 최댓값입니다. 라즈베리파이 4 에 부하를 걸면 일반 커널의 최댓값은 781 마이크로초, 실시간 커널로 바꾸면 301, CPU 하나를 격리하면 189 입니다. 우선순위는 평균을 좋게 하지만, 꼬리를 자르는 것은 커널입니다."

## 장면 3 — 0:48~1:10 — ROS 2 노드 + MuJoCo 물리 + 로봇 안 기록
화면: [WSL E] `bash docs/video/cue.sh 3` → `ros2 topic echo /rt_status --full-length --once` (JSON 의 `backend: mujoco`, `work_us`, `state: RUNNING` 에 마우스) → `ros2 topic echo /joint_states --once --field position` (두 번째 값 **−0.18** 에 마우스) → `cat docs/measurements/record_summary_wsl_20261105.md` (추종 오차 표의 shoulder_lift 0.0191 에 마우스).
TTS: "제어 코드는 ROS 2 와 무관한 C++ 이고, 백엔드만 MuJoCo 로 바꿨습니다. 물리가 들어오자 어깨 관절이 목표보다 1.1도 처집니다. 중력입니다. 로봇 안의 100 헤르츠 데이터는 rosbag2 로 기록하고 검증 요약까지 자동으로 만듭니다. 틈 0, 그리고 같은 처짐이 요약표에 그대로 나옵니다."

## 장면 4 — 1:10~1:35 — 관제 50대 + OTA 단계 배포
화면: 브라우저 탭 1 Grafana 전체(3초) → [WSL E] `bash docs/video/cue.sh 4` → `python3 fleet/ota/rollout.py --version 1.2.0-bad --bad --apply-s 1 --health-wait 3` 실행(약 12초: "단계 5%: 3대" → "비정상 3/3 → 롤백" → "롤백 완료 1.0초") → Grafana "펌웨어 버전별 장치 수" 패널로 돌아와 3대가 튀었다 돌아온 것.
TTS: "가상 장치 50대가 MQTT 로 보고하고, 수집기가 1초 묶음으로 DB 에 넣습니다. 나쁜 펌웨어를 단계 배포하면 5 퍼센트, 세 대에서 헬스 게이트가 잡아 1초 만에 롤백하고, 나머지 47대는 건드리지 않습니다."

## 장면 5 — 1:35~1:52 — 장애 주입: 유실 0 의 증거
화면: [WSL E] `bash docs/video/cue.sh 5` → `python3 fleet/chaos/inject.py --fault broker --duration 5 --settle 5 --label video` (약 20초 — 편집에서 2배속) → Grafana 초당 메시지가 0 으로 떨어졌다 폭주 → 마지막 한 줄 명령으로 `전 장치 복귀 n 초 / 유실 0 / N` 출력.
TTS: "브로커를 죽이면 장치가 버퍼에 모았다가 재전송하고, 전 장치가 3초 안에 돌아오며 유실은 0 입니다. 처음엔 0 이 아니었습니다. 측정의 맹점을 고치자 53개가 나왔고, 원인 셋을 추적해 0 으로 만들었습니다."

## 장면 6 — 1:52~2:00 — CI 와 마무리
화면: 브라우저 탭 3 Actions 초록 3잡 → [WSL E] `bash docs/video/cue.sh 6` 상자(저장소 주소)로 끝.
TTS: "푸시할 때마다 러너가 루프와 물리, 장애 주입과 롤백을 다시 돌립니다. 코드와 숫자는 저장소에 있습니다."

## 편집 (Clipchamp, 30분)
1. 새 프로젝트 1080p → `scene0.mp4` ~ `scene6.mp4` 를 순서대로 타임라인에.
2. 각 클립 앞뒤 자르기. 장면 5 의 20초 대기는 **속도 2배**(클립 선택 → 속도).
3. **텍스트 음성 변환**: 왼쪽 "녹음 및 만들기" → 텍스트 음성 변환 → 한국어 → 음성 선택 → 위 TTS 문장을 장면별로 붙여 넣기 → 생성 → 해당 장면 시작에 맞춰 놓기. 속도 1.0, 피치 기본.
4. 자막은 터미널 상자가 이미 있으므로 넣지 않는다(브라우저 장면 1·4·6 에만 숫자 자막 한 줄 허용: "유실 0 / 1400", "롤백 1.0초 · 3/50").
5. 내보내기 1080p → YouTube **미등록(unlisted)** 업로드 → 링크를 README 맨 위와 이력서에.

## 왜 이렇게 만드나 (기록)
- 육성 대신 TTS: 녹음 장비·재녹음 부담 없이 문장 품질에 집중. 본인 설명은 면접에서. README "작성 방식"과 함께 보면 오해 소지 없음.
- 자막을 터미널이 띄우는 이유: 편집 작업 최소화 + 숫자가 코드와 같은 화면에 있어 "붙인 글자"가 아니라 "출력"으로 읽힌다.
- 장면 2 가 가장 길고 가운데 있는 이유: 공고 1번 항목이고 Pi 실측이 저장소에서 유일한 "진짜 실시간" 숫자.
