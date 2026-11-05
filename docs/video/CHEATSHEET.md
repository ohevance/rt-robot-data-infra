# 녹화 순서표 — 휴대폰에 띄우거나 인쇄해서 옆에 둔다 (화면에는 클로드 창을 띄우지 않는다)

녹화 창 [WSL E] 최대화, 글꼴 20pt 이상. `Win + Shift + R` → 전체 화면 → 시작. 아래를 **직접 타이핑**한다(붙여넣기 아님).
명령이 끝나면 **3초 멈춤**(편집 때 자르기 쉽게). 틀리면 그 자리에서 다시 치면 된다 — 편집에서 잘라 낸다.
브라우저로 갈 때는 `Alt+Tab`, 돌아올 때도 `Alt+Tab`.

## 장면 0 (8초)
```
bash docs/video/cue.sh 0
```
## 장면 1 (10초) — 브라우저 README
```
bash docs/video/cue.sh 1
```
→ Alt+Tab → README 위 표에서 "숫자 한눈에" 표까지 천천히 스크롤 → 초록 배지 → Alt+Tab

## 장면 2 (30초) — 표①
```
bash docs/video/cue.sh 2
ssh pi-rt 'uname -r; cat /sys/kernel/realtime'
bash docs/video/table1_key.sh
./build/rt_core/jitter_bench --no-rt --seconds 3
```
(`ssh pi-rt` 는 `~/.ssh/config` 별칭. Pi 가 꺼져 있으면 이 줄은 건너뛴다.)

## 장면 3 (22초) — 노드 · 물리 · 기록
```
bash docs/video/cue.sh 3
ros2 topic echo /rt_status std_msgs/msg/String --full-length --once
ros2 topic echo /joint_states --once --field position
cat docs/measurements/record_summary_wsl_20261105.md
```
(두 번째 position 값 −0.18 과 요약표 shoulder_lift 0.0191 에 마우스를 잠깐 올린다.)

## 장면 4 (25초) — 관제 + OTA
```
bash docs/video/cue.sh 4
```
→ Alt+Tab → Grafana 전체 3초 → Alt+Tab
```
python3 fleet/ota/rollout.py --version 1.2.0-bad --bad --apply-s 1 --health-wait 3
```
→ Alt+Tab → Grafana "펌웨어 버전별 장치 수" 패널 3초 → Alt+Tab

## 장면 5 (20초) — 장애 주입
```
bash docs/video/cue.sh 5
python3 fleet/chaos/inject.py --fault broker --duration 5 --settle 5
```
(마지막 JSON 의 `"lost": 0` 에 마우스. 약 20초 — 편집에서 2배속.)

## 장면 6 (8초) — CI
```
bash docs/video/cue.sh 6
```
→ Alt+Tab → Actions 초록 3잡 3초 → Alt+Tab
```
gh run list -L 3
```
→ 5초 멈춤 → **녹화 정지**

---
준비(녹화 전 한 번): `ssh-copy-id mgoh@192.168.45.250` (비밀번호 안 묻게) 와 `~/.ssh/config` 에
```
Host pi-rt
    HostName 192.168.45.250
    User mgoh
```
리허설만 자동으로 돌려 보려면 `bash docs/video/run.sh all` (녹화에는 쓰지 않는다 — 직접 치는 모습이 데모다).
