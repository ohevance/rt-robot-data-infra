# 작업 상태 요약 — 2026-11-06 (D8 — 표① Pi 4 PREEMPT_RT 실측 완료, 기록 파이프라인 첫 실행, 발표 장표, 제출 서류)

이 문서는 "지금 어디까지 왔고, 무엇이 남았나"를 한 장으로 적은 것이다. 시간순 기록은 `docs/LOG.md`, 결정의 이유는 `docs/DECISIONS.md`, 실험 하나하나는 `docs/EXPERIMENTS.md`.
저장소: **https://github.com/ohevance/rt-robot-data-infra** (public, main, CI 초록)

## 1. 목표
- "휴머노이드 로봇 SW 엔지니어(실시간 제어 및 데이터 인프라)" 직무 지원용 포트폴리오.
- **2주 계획: 11/04 ~ 11/17.** 수치 표 3개(①RT 지연 ②DDS ③관제·장애·OTA), CI 배지, 2분 영상, 제출 서류(이력서·자기소개서·설계서).

## 2. 작업 규칙
- 코드: 함수는 한 화면 안에 들어오게, 람다·매크로·삼항 중첩 금지, 파일 머리에 "역할/읽는 순서", 숫자에 단위, 주석은 "왜". 규칙 전문은 `docs/READING_GUIDE.md` §4.
- 기록: 결정은 `docs/DECISIONS.md`(결정·이유·버린 대안·검증 방법), 깨진 것과 해결은 `docs/LOG.md`, 실험은 `docs/EXPERIMENTS.md` 한 줄 + `docs/experiments/E##.md` 한 장. 개념은 `docs/GLOSSARY.md`. **"왜 하는가"와 "결과를 보고 어떻게 판단했는가"는 반드시 문서에 남긴다.**
- 숫자: 모든 측정값은 `docs/measurements/` 원본과 환경 표기(WSL2 참고값 / Pi 4 실측 / GitHub 러너)가 있어야 문서에 적는다. 표①②③은 생성기(`scripts/make_table1/2/3.py`)로만 만든다.
- git: Pi 는 측정만 하고 커밋·push 는 WSL 에서. 이미 push 된 이력은 다시 쓰지 않는다(`--rebase` 금지 — 11/04 충돌 경위는 `docs/ENVIRONMENT.md` §2). 커밋 전 `git grep` 으로 사설 IP·계정 이름·토큰이 없는지 본다(11/06 규칙).
- 안내문에는 창을 표시한다: **[Pi 창]** / **[WSL 창]** (11/04 창을 헷갈려 실패한 적 있음).
- 작성 방식 고지는 README "작성 방식" 문단 그대로(설계·검토·측정·해석은 작성자, 코드 초안과 스크립트·설정 템플릿은 AI 도구의 보조).

## 3. 환경 (확인됨) — 전체 지도와 판단 기준은 `docs/ENVIRONMENT.md`
- WSL2 Ubuntu 24.04, 12 CPU, Docker, ROS 2 Jazzy(ros-base) + Cyclone + Fast DDS(기본 RMW 는 fastrtps).
- `~/rt-robot-data-infra`: venv 는 **`--system-site-packages`** 로 생성(rclpy 가 쓰는 yaml·numpy 때문). `.bashrc` 가 터미널마다 저장소 이동 + venv + ROS 2 + `install/setup.bash` + `RT_REPO_ROOT` 자동 설정.
- `third_party/mujoco`(3.3.2), `third_party/mujoco_menagerie/trs_so_arm100`, `third_party/allex_model`(ALLEX, 고정 커밋 5e12052) 설치됨(gitignore). `build/rt_core_mj`, `install/`(MuJoCo 옵션 colcon) 있음.
- 관제 컨테이너 3개(mqtt persistence true + 볼륨, db, grafana). 수집기는 터미널에서 `--qos 1` 로 띄움(한 번에 하나, `fleet/logs/collector.lock`).
- **Raspberry Pi 4 Model B 4 GB**: Ubuntu Server 24.04.5 64-bit, hostname `pi-rt`, Wi-Fi(IP 는 바뀔 수 있음 — 안 되면 공유기에서 `pi-rt` 찾기; ssh 별칭은 `docs/video/CHEATSHEET.md`). 도구(git·cmake·rt-tests·stress-ng) 설치, 저장소 clone·빌드·ctest 4/4. 방열판 없음 → 부하 측정 120초.
- 실시간 커널 적용 완료: **`6.8.0-2054-raspi-realtime`, `/sys/kernel/realtime` = 1, `isolcpus=3 nohz_full=3 rcu_nocbs=3`**(되돌리기: `/boot/firmware/cmdline.txt.bak`). 일반 커널 `6.8.0-1064-raspi` 값은 "전"으로 `table1_pi4.md` 에 있다.

## 4. 저장소 상태
- rt_core: SPSC 링 · RtLoop · ControlStep(최신 명령·워치독·변화량 제한·상태 머신) · RobotStateMachine(표 기반) · SimLagBackend · **MujocoBackend** · jitter_bench · 테스트 4 + MuJoCo 1. ros2_adapter: `backend: sim_lag|mujoco`, rt_status 에 wake_us·work_us·state·backend·rmw.
- fleet: 에이전트(버퍼·재전송·유언·OTA 적용/롤백·keepalive/QoS 옵션), 수집기(1초 묶음 COPY·DB backlog·지속 세션·곱게 종료·단일 인스턴스 잠금·보관 상태 이벤트 제외), rollout.py(5→50→100% 헬스 게이트·롤백), chaos/inject.py(4종, 장애 직전 seq 기준 유실), assert_results.py, tools/diag.py(A 군집·B 홍수 제외·C seq 틈), db/migrate.py(--wait), 대시보드 14패널, 가짜 브로커·DB 테스트 15개, integration.sh.
- CI 3잡 초록: rt_core 1m13s · mujoco 25s · fleet_integration 1m52s (11/04). 11/06 run 42172730308(ALLEX 단계 포함): rt_core 6m42s(apt 느림으로 추정) · mujoco 44s · fleet_integration 1m59s. checkout/upload-artifact 는 v5 로 올림(58d22cf) — 그 뒤 실행 결과는 `gh run list -L 3` 로 확인할 것.
- 측정 스크립트: `scripts/lib_thermal.sh`(온도·스로틀), `lib_stress.sh`(부하 정의 한 곳), `cyclictest_run.sh`·`jitter_run.sh`(.meta 에 온도·스로틀 기록), `make_table1.py` 가 .meta 를 읽어 비고에 표시. `docs/measurements/table1_pi4.md` 14줄.
- docs: README "숫자 한눈에"(환경 표기), measurements/README.md 색인, LOG 11/03~11/06, DECISIONS, GLOSSARY, READING_GUIDE 26항목, EXPERIMENTS.md(실험 21건 + 사고 11건), VIDEO_SCRIPT, RESUME_LINES, SETUP_RT_MEASURE, ENVIRONMENT.
- **발표 장표(11/05, 11/06 덧붙임)**: `docs/deck/rt-robot-data-infra.pptx` 139장(136 = ALLEX 덧붙임)(순서도 논리: 로봇을 움직이는 과정 먼저, 핵심 소스 코드 파일:줄, 시험·검증은 3부에 번호로) + 장표마다 설명 문서 `docs/deck/notes/NNN.docx`(원본 `notes_md/`). 생성 코드 `docs/deck/build/`(`./build.sh`). 읽는 법·발표하는 법은 `docs/deck/README.md`.

## 5. 측정값 요약 (환경 표기 필수)
- RT 루프(WSL 참고값): 1 kHz 드롭 0, 노드 wake p99 278~352 / max 679~2026 us, SCHED_FIFO 는 p50 92→37 us(꼬리 그대로).
- **Pi 4 일반 커널 6.8.0-1064-raspi(11/04)**: jitter_bench 60 s max 24.9(한가) / 781.2 us(부하, work time max 134.9) · cyclictest max 376(한가 300 s) / 695 us(부하 120 s), p99.9 57 / 118. 온도 45→75 °C, 스로틀 0. → RT 커널의 "후" 와 비교할 "전".
- **Pi 4 PREEMPT_RT 6.8.0-2054-raspi-realtime(11/05)**: cyclictest max 한가 **37** / 부하 **132**(일반 376 / 695). jitter 부하 max **781 → 301**(RT) → 311(CPU 3 고정) → **189**(isolcpus=3), work max 135 → 53. 비용: 부하 p99 146 → 185. 도구 불일치(132 vs 301) 검증: 같은 설정이면 274 vs 270(측정기 맞음); 차이는 -S 스레드 배치(~60)와 부하 정의 512M vs 256M(~80, 추정). 전 14줄 `table1_pi4.md`, 전부 스로틀 0.
- MuJoCo 한 주기: 러너 6.4/8.5/29.4 us, WSL 단독 4.9/6.3/20.8 us, 노드 안 work_us 41/145/247 us. 어깨 Pitch 중력 처짐 1.1°. **ALLEX 48 자유도**: 1 kHz WSL 336/622/1,785 · 러너 382/458/609 — 500 Hz WSL 327/1,000/1,589 · 러너 390/510/685 us → 프로필 500 Hz(E21; WSL 500 Hz p99 가 어림 31 % 가 아닌 50 %, 러너는 26 % — 반복 측정 남음).
- DDS 1 MB: Fast DDS best_effort 99.8% 손실 vs Cyclone 0%.
- 관제 50대 1 Hz(WSL): 전달 지연 p50 0.9 / p95 1.8 ms. 장애: broker 10초 → 2.9초 복귀, 유실 0/1400 · db 10초 → backlog 0 까지 1.4초, 0/1341 · collector(qos1) 10초 → 1.6초, 0/1311 · 나쁜 펌웨어 3/50 에서 롤백 1.0초. 러너(10대 2 Hz)도 같은 모양(0·0·0, 롤백 0.4초).
- 유실의 역사(면접 소재): 처음 "0"은 측정 맹점 → 고치자 53 → 원인 셋(브로커 재시작 경쟁 4~5대×12 / 수집기 종료 순간 1개·장치 / 큐 상한 2,450개) → persistence true·곱게 종료로 0. 오프라인 이벤트 20 = 브로커 종료 시 일괄 유언.

## 6. 다음 할 일
- (완료) 소실험 2개 — keepalive 박자 확정(30 s: 0회 / 10 s: 10.0 s 간격), QoS 0 유실 508/1312.
- (완료 11/05) 표① Pi 4 RT 실측 전부. 선택 과제: 512M 로 cyclictest -S 한 번 더(부하 정의 vs 격리 전후 가르기), 방열판 달고 300 s 부하.
- (완료 11/05) 기록 파이프라인 첫 실행(E20). (완료 11/06) 제출 서류 — 이력서·자기소개서, 포트폴리오 설계서(저장소 밖 PDF).
- 남은 큰 일: 2분 영상 녹화(대본 `docs/VIDEO_SCRIPT.md`), 장표(`docs/deck/`)로 직접 설명해 보는 분석 기간 — 막히는 장표는 `notes_md/NNN.md` 를 고치고 `build/make_notes.sh` 로 docx 재생성.
- WSL 잔일: 수집기 `--qos 1`, 가상 장치 `--telemetry-qos 1` 로 되돌리기(다시 관제를 띄울 때) · CI 초록 확인(`gh run list -L 1`).
- (완료 11/06) ALLEX 프로필 + E21(WSL 1 kHz · 500 Hz, 러너 1 kHz) → 500 Hz 기본. 남은 것: 노드 안 `work_us`·drop(500 Hz), 조건별 3회 반복·10초 측정(테스트에 주기 수 옵션).
- (1차 완료 11/10) **릴리스 → 배포 파이프라인**(`docs/RELEASE.md`): OTA 를 진짜 설치로(내려받기·sha256·A/B 슬롯·자가 점검·롤백), `release.yml`(태그 → 패키지 x86_64·aarch64 → 가상 50대 카나리 → Release), Pi 자율 업데이트(`pi_agent.py --auto-update`). **남은 것**: 첫 태그 `v0.9.0-rc1` 올려 러너 카나리 값을 E22 에, Pi 에서 `pi_agent.py --once` 1회 + 서비스 등록, 설계서·장표에 반영. 다음 단계: 헬스 게이트에 RT 지표, ed25519 서명, `post_switch.sh` 노드 재시작, 운영 층을 클라우드 VM(EC2, 신규 계정 6개월 무료)으로 — 면접 전 하루.
- (가동 중, 11/10 18:37 부터) 운영 층이 EC2(시드니, t3.small, 탄력적 IP)에서 돌고 Pi(`rt-pi-agent` 사용자 서비스)가 TLS + 비밀번호로 1 Hz 보고 중 — 노트북과 무관하게 기록이 쌓인다. 첫 실행에서 나온 여섯 가지와 고친 것은 LOG 11/10 저녁. 접속 정보·비밀번호는 서버의 `~/fleet-server-info.txt` 에만. **남은 것**: (1) 서버에 patch-31 반영(`git pull` + `docker compose … up -d --build` — LOG 에 명령), (2) Pi 재부팅 전에 다음 부팅 커널이 RT 인지 확인(자동 업데이트가 일반 커널 패키지를 올렸다), (3) 시계와 무관한 왕복 지연 측정 → "서버: 시드니" 로 기록, (4) 첫 태그로 Pi 자율 업데이트 확인, (5) 브로커 설정의 deprecated 경고(확인 가능한 때), (6) 장표·설계서의 테스트 수(15 → 26)와 운영 층 반영.
- 보류(면접에서 "다음 단계"로): 수동 ACK(DB 적재 뒤 PUBACK), 중력 보상(토크 피드포워드), 실물 SO-101 시리얼 백엔드 + 안전 정지, MCAP 구간 추출·업로드, 기록 요약을 관제로 1 Hz 올리기.
- 잔일: `docs/measurements/table3.md` 표③-1(최근 60분 집계)이 장애 실험 구간을 포함해 '초당 메시지 최대 20000 · 전달 지연 max 5,603,338 ms · 유실 −130%' 처럼 깨진 값이다 — 관제를 깨끗이 10분 돌린 뒤 `python3 scripts/make_table3.py --minutes 10` 으로 다시 만들 것(장표·설계서는 p50/p95 1/2 ms 만 인용). 읽기 가이드의 "한 함수 40줄"을 넘는 함수(`rt_loop.cpp` run, `rt_control_node.cpp` publish_status, `make_dashboard.py` build, `diag.py` 등) 쪼개기.
