# 인수인계 요약 — 2026-11-05 13:00 (D7 — 표① Pi 4 PREEMPT_RT 실측 완료, 기록 파이프라인 첫 실행, 실험 상세 페이지 21장)

새 대화 첫 메시지에 이 파일을 첨부하세요. 저장소는 GitHub 에 있으므로 zip 은 더 이상 필요 없습니다:
**https://github.com/ohevance/rt-robot-data-infra** (public, main, CI 초록)

## 1. 목표 (변경 없음)
- "휴머노이드 로봇 SW 엔지니어(실시간 제어 및 데이터 인프라)" 직무 지원용 포트폴리오.
- **2주 계획: 11/04 ~ 11/17, 11/17(화) 지원.** 수치 표 3개(①RT 지연 ②DDS ③관제·장애·OTA), CI 배지, 2분 영상, 이력서 문장.

## 2. 작업 방식 (사용자 요구 — 바뀐 것 포함)
- Claude 가 코드를 만들고 사용자가 WSL 에서 실행 → 출력 붙여 줌. **도형 보고서·모의 면접 생략.** 설명 틀: (1) 공고 ↔ 코드 ↔ 숫자 표 (2) 면접 한 문장 (3) 칠 명령.
- 코드 규칙: 한 함수 40줄, 람다·매크로·삼항 중첩 금지, 파일 머리 "역할/읽는 순서", 숫자에 단위, 주석은 "왜". 결정 `docs/DECISIONS.md`, 깨진 것 `docs/LOG.md`.
- **git 으로 전환(11/04).** 전달: Claude 가 `C:\Users\<사용자>\Downloads\patch-NN.bundle` 을 넣음 → 사용자 `git pull --no-rebase --no-edit /mnt/c/Users/<사용자>/Downloads/patch-NN.bundle main` → **push 는 사용자가.** (`--rebase` 는 push 된 이력을 다시 써서 충돌을 냈으므로 금지.) Claude 는 공개 저장소를 **읽기 전용으로 fetch** 해 사용자 main 에 기준을 맞춘다(11/04 밤부터; bundle 을 받을 필요 없음). GitHub 를 Claude 에 연결하지 않기로 함(사용자 결정). 측정 결과는 사용자가 WSL 에서 직접 커밋·push(예: b4c6f3b).
- 안내문에는 창을 표시한다: **[Pi 창]** / **[WSL 창]** (11/04 창을 헷갈려 실패한 적 있음).
- **(11/05 규칙) "왜 하는가"와 "결과를 보고 어떻게 판단했는가"는 반드시 저장소 문서에 남긴다** — 개념은 GLOSSARY, 질문·결과는 EXPERIMENTS, 판단(읽기)은 LOG, 결정은 DECISIONS. 채팅에서 설명한 것은 같은 날 문서로 옮긴다(READING_GUIDE §4).
- 커밋 끝에 `Co-Authored-By: Claude …` 줄이 있음(README "작성 방식"과 일치). 작성자는 오문규 <ohevance@gmail.com>.

## 3. 환경 (확인됨) — 전체 지도와 판단 기준은 `docs/ENVIRONMENT.md`
- WSL2 Ubuntu 24.04, 12 CPU, Docker, ROS 2 Jazzy(ros-base) + Cyclone + Fast DDS(기본 RMW 는 fastrtps), `gh` 설치·로그인(ohevance).
- `~/rt-robot-data-infra`: venv 는 **`--system-site-packages`** 로 생성(rclpy 가 쓰는 yaml·numpy 때문). `.bashrc` 가 터미널마다 저장소 이동 + venv + ROS 2 + `install/setup.bash` + `RT_REPO_ROOT` 자동 설정.
- `third_party/mujoco`(3.3.2), `third_party/mujoco_menagerie/trs_so_arm100` 설치됨(gitignore). `build/rt_core_mj`, `install/`(MuJoCo 옵션 colcon) 있음.
- 관제 컨테이너 3개 떠 있음(mqtt persistence true + 볼륨, db, grafana). 수집기는 터미널에서 `--qos 1` 로 띄움(한 번에 하나, `fleet/logs/collector.lock`).
- **Raspberry Pi 4 Model B 4 GB** (11/04 세팅 완료): Samsung PRO Plus 512 GB 에 Ubuntu Server 24.04.5 64-bit, hostname `pi-rt`, **Wi-Fi**(IP 는 바뀔 수 있음 — 안 되면 공유기에서 `pi-rt` 찾기), SSH 비밀번호. 도구(git·cmake·rt-tests·stress-ng) 설치, 저장소 clone·빌드·ctest 4/4. 커널 `6.8.0-1064-raspi`(일반). 방열판 없음 → 부하 측정 120초. 기존 카드(Raspberry Pi OS 12)는 보관.
- Ubuntu One 계정 있음(11/05 아침 가입 성공, 전날 밤은 Launchpad time out). Ubuntu Pro 개인 토큰으로 Pi attach 완료 → **커널 `6.8.0-2054-raspi-realtime`, `/sys/kernel/realtime` = 1, `isolcpus=3 nohz_full=3 rcu_nocbs=3` 적용 상태**(되돌리기: `/boot/firmware/cmdline.txt.bak`). 토큰은 채팅 캡처에 한 번 노출됨 — 영상·문서에 넣지 말 것.

## 4. 저장소 상태 (main c71a5f2 + patch-12)
- rt_core: SPSC 링 · RtLoop · ControlStep(최신 명령·워치독·변화량 제한·상태 머신) · RobotStateMachine(표 기반) · SimLagBackend · **MujocoBackend** · jitter_bench · 테스트 4 + MuJoCo 1. ros2_adapter: `backend: sim_lag|mujoco`, rt_status 에 wake_us·work_us·state·backend·rmw.
- fleet: 에이전트(버퍼·재전송·유언·OTA 적용/롤백·keepalive/QoS 옵션), 수집기(1초 묶음 COPY·DB backlog·지속 세션·곱게 종료·단일 인스턴스 잠금·보관 상태 이벤트 제외), rollout.py(5→50→100% 헬스 게이트·롤백), chaos/inject.py(4종, 장애 직전 seq 기준 유실), assert_results.py, tools/diag.py(A 군집·B 홍수 제외·C seq 틈), db/migrate.py(--wait), 대시보드 14패널, 가짜 브로커·DB 테스트 3개, integration.sh.
- CI 3잡 초록: rt_core 1m13s · mujoco 25s · fleet_integration 1m52s. checkout/upload-artifact 는 v5 로 올림(58d22cf) — 그 뒤 실행 결과는 `gh run list -L 3` 로 확인할 것.
- 측정 스크립트(11/04 밤): `scripts/lib_thermal.sh`(온도·스로틀), `cyclictest_run.sh`(.meta 에 온도 기록), 새 `jitter_run.sh`(라벨·초·stress·cpu 한 줄), `make_table1.py` 가 .meta 를 읽어 비고에 온도/스로틀 표시. `docs/measurements/table1_pi4.md`(일반 커널 4줄).
- docs: README "숫자 한눈에"(환경 표기, Pi 일반 커널 2줄 포함), measurements/README.md 색인, LOG 11/03~11/04 밤까지, DECISIONS 14건+, GLOSSARY, READING_GUIDE 26항목, **EXPERIMENTS.md**(실험 19건 + 사고 9건 한 표), VIDEO_SCRIPT, RESUME_LINES, SETUP_RT_MEASURE(1~4단계 검증 완료 표시).
- **발표 장표(11/05 오후)**: `docs/deck/rt-robot-data-infra.pptx` 138장(순서도 논리: 로봇을 움직이는 과정 먼저, 핵심 소스 코드 파일:줄, 시험·검증은 3부에 번호로, 도형 그림 9장·순서도 30장) + 장표마다 설명 문서 `docs/deck/notes/NNN.docx`(원본 `notes_md/`). 생성 코드 `docs/deck/build/`(`./build.sh` 로 다시 만든다, 코드 장표 줄 번호는 `content_*.py`). 읽는 법·발표하는 법은 `docs/deck/README.md`.

## 5. 측정값 요약 (환경 표기 필수)
- RT 루프(WSL 참고값): 1 kHz 드롭 0, 노드 wake p99 278~352 / max 679~2026 us, SCHED_FIFO 는 p50 92→37 us(꼬리 그대로).
- **Pi 4 일반 커널 6.8.0-1064-raspi(11/04)**: jitter_bench 60 s max 24.9(한가) / 781.2 us(부하, work time max 134.9) · cyclictest max 376(한가 300 s) / 695 us(부하 120 s), p99.9 57 / 118. 온도 45→75 °C, 스로틀 0. → RT 커널의 "후" 와 비교할 "전".
- **Pi 4 PREEMPT_RT 6.8.0-2054-raspi-realtime(11/05)**: cyclictest max 한가 **37** / 부하 **132**(일반 376 / 695). jitter 부하 max **781 → 301**(RT) → 311(CPU 3 고정) → **189**(isolcpus=3), work max 135 → 53. 비용: 부하 p99 146 → 185. 도구 불일치(132 vs 301) 검증: 같은 설정이면 274 vs 270(측정기 맞음); 차이는 -S 스레드 배치(~60)와 부하 정의 512M vs 256M(~80, 추정). 전 14줄 `table1_pi4.md`, 전부 스로틀 0.
- MuJoCo 한 주기: 러너 6.4/8.5/29.4 us, WSL 단독 4.9/6.3/20.8 us, 노드 안 work_us 41/145/247 us. 어깨 Pitch 중력 처짐 1.1°.
- DDS 1 MB: Fast DDS best_effort 99.8% 손실 vs Cyclone 0%.
- 관제 50대 1 Hz(WSL): 전달 지연 p50 0.9 / p95 1.8 ms. 장애: broker 10초 → 2.9초 복귀, 유실 0/1400 · db 10초 → backlog 0 까지 1.4초, 0/1341 · collector(qos1) 10초 → 1.6초, 0/1311 · 나쁜 펌웨어 3/50 에서 롤백 1.0초. 러너(10대 2 Hz)도 같은 모양(0·0·0, 롤백 0.4초).
- 유실의 역사(면접 소재): 처음 "0"은 측정 맹점 → 고치자 53 → 원인 셋(브로커 재시작 경쟁 4~5대×12 / 수집기 종료 순간 1개·장치 / 큐 상한 2,450개) → persistence true·곱게 종료로 0. 오프라인 이벤트 20 = 브로커 종료 시 일괄 유언.

## 6. 다음 할 일
- (완료) 소실험 2개 — keepalive 박자 확정(30 s: 0회 / 10 s: 10.0 s 간격), QoS 0 유실 508/1312.
- (완료 11/05) 표① Pi 4 RT 실측 전부. 선택 과제로 남김: 512M 로 cyclictest -S 한 번 더(부하 정의 vs 격리 전후 가르기), 방열판 달고 300 s 부하.
- **문서 규칙(11/05)**: 채팅에서 한 설명·판단은 같은 날 GLOSSARY/EXPERIMENTS/LOG/DECISIONS 로. 실험이 늘면 `docs/experiments/E##.md` 한 장 + 순서도 상자·마름모 하나.
- 남은 큰 일: 2분 영상 녹화(대본 `docs/VIDEO_SCRIPT.md` 에 Pi 숫자 반영 필요), 이력서 문장(경력 숫자 5개 미수령), 사용자의 코드 분석 기간(**장표 `docs/deck/` 138장 + 설명 문서로** — READING_GUIDE 26 + experiments 20장은 보조), D9 재직자 접촉 문구. 분석 중 막히는 장표는 `notes_md/NNN.md` 를 고치고 `build/make_notes.sh` 로 docx 재생성.
- (완료 11/05) 기록 파이프라인 첫 실행(E20). 남은 WSL 잔일: 수집기 `--qos 1`, 가상 장치 `--telemetry-qos 1` 로 되돌리기(다시 관제를 띄울 때) · CI 초록 확인(`gh run list -L 1`).
- 문서·마무리: actions v5, README 최종, 2분 영상 대본, 이력서 문장(사용자 경력 숫자 5개 아직 미수령: 시스템 규모·초당 처리량·소켓 프로토콜·관제 주기·DB 일 처리량), D9 재직자 접촉 문구.
- 보류(면접에서 "다음 단계"로): 수동 ACK(DB 적재 뒤 PUBACK), 중력 보상, ALLEX 프로필, 실물 SO-101.
- 잔일(11/05 장표 작업 중 발견): `docs/measurements/table3.md` 표③-1(최근 60분 집계)이 장애 실험 구간을 포함해 '초당 메시지 최대 20000 · 전달 지연 max 5,603,338 ms · 유실 −130%' 처럼 깨진 값이다 — 관제를 깨끗이 10분 돌린 뒤 `python3 scripts/make_table3.py --minutes 10` 으로 다시 만들 것(장표는 p50/p95 1/2 ms 만 인용). LOG 11/05 의 '단위 테스트 7개' 는 5개(스모크 추가 전)로 정정.
