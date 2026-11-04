# 인수인계 요약 — 2026-11-04 13:20 (D5 완료·GitHub 공개·CI 3잡 초록)

새 대화 첫 메시지에 이 파일을 첨부하세요. 저장소는 GitHub 에 있으므로 zip 은 더 이상 필요 없습니다:
**https://github.com/ohevance/rt-robot-data-infra** (public, main, CI 초록)

## 1. 목표 (변경 없음)
- 위로보틱스 "휴머노이드 로봇 SW 엔지니어(실시간 제어 및 데이터 인프라)" / 리멤버 "Framework S/W 엔지니어" 지원용 포트폴리오.
- **2주 계획: 11/04 ~ 11/17, 11/17(화) 지원.** 수치 표 3개(①RT 지연 ②DDS ③관제·장애·OTA), CI 배지, 2분 영상, 이력서 문장.
- D9쯤 재직자 접촉(리멤버 커넥트·링크드인, 사내추천 200만원 제도) → 추천 경로 우선.

## 2. 작업 방식 (사용자 요구 — 바뀐 것 포함)
- Claude 가 코드를 만들고 사용자가 WSL 에서 실행 → 출력 붙여 줌. **도형 보고서·모의 면접 생략.** 설명 틀: (1) 공고 ↔ 코드 ↔ 숫자 표 (2) 면접 한 문장 (3) 칠 명령.
- 코드 규칙: 한 함수 40줄, 람다·매크로·삼항 중첩 금지, 파일 머리 "역할/읽는 순서", 숫자에 단위, 주석은 "왜". 결정 `docs/DECISIONS.md`, 깨진 것 `docs/LOG.md`.
- **git 으로 전환(11/04).** 전달: Claude 가 `C:\Users\에반스\Downloads\patch-NN.bundle` 을 넣음 → 사용자 `git pull --no-rebase --no-edit /mnt/c/Users/에반스/Downloads/patch-NN.bundle main` → **push 는 사용자가.** (`--rebase` 는 push 된 이력을 다시 써서 충돌을 냈으므로 금지.) Claude 쪽 기준은 사용자 main 의 `ee269c8`(11/04 13:07)에 맞춰져 있음 — 사용자가 `git bundle create .../user-main.bundle main` 으로 보내 주면 다시 맞춤. GitHub 를 Claude 에 연결하지 않기로 함(사용자 결정).
- 커밋 끝에 `Co-Authored-By: Claude …` 줄이 있음(README "작성 방식"과 일치). 작성자는 오문규 <ohevance@gmail.com>.

## 3. 환경 (확인됨)
- WSL2 Ubuntu 24.04, 12 CPU, Docker, ROS 2 Jazzy(ros-base) + Cyclone + Fast DDS(기본 RMW 는 fastrtps), `gh` 설치·로그인(ohevance).
- `~/rt-robot-data-infra`: venv 는 **`--system-site-packages`** 로 생성(rclpy 가 쓰는 yaml·numpy 때문). `.bashrc` 가 터미널마다 저장소 이동 + venv + ROS 2 + `install/setup.bash` + `RT_REPO_ROOT` 자동 설정.
- `third_party/mujoco`(3.3.2), `third_party/mujoco_menagerie/trs_so_arm100` 설치됨(gitignore). `build/rt_core_mj`, `install/`(MuJoCo 옵션 colcon) 있음.
- 관제 컨테이너 3개 떠 있음(mqtt persistence true + 볼륨, db, grafana). 수집기는 터미널에서 `--qos 1` 로 띄움(한 번에 하나, `fleet/logs/collector.lock`).
- Raspberry Pi: 사용자 보유, **모델·OS·저장장치·네트워크 미확인** — 표① RT 커널 실측(D6~D8)에 필요.

## 4. 저장소 상태 (main ee269c8 + 이후 문서 패치)
- rt_core: SPSC 링 · RtLoop · ControlStep(최신 명령·워치독·변화량 제한·상태 머신) · RobotStateMachine(표 기반) · SimLagBackend · **MujocoBackend** · jitter_bench · 테스트 4 + MuJoCo 1. ros2_adapter: `backend: sim_lag|mujoco`, rt_status 에 wake_us·work_us·state·backend·rmw.
- fleet: 에이전트(버퍼·재전송·유언·OTA 적용/롤백·keepalive/QoS 옵션), 수집기(1초 묶음 COPY·DB backlog·지속 세션·곱게 종료·단일 인스턴스 잠금·보관 상태 이벤트 제외), rollout.py(5→50→100% 헬스 게이트·롤백), chaos/inject.py(4종, 장애 직전 seq 기준 유실), assert_results.py, tools/diag.py(A 군집·B 홍수 제외·C seq 틈), db/migrate.py(--wait), 대시보드 14패널, 가짜 브로커·DB 테스트 3개, integration.sh.
- CI 3잡 초록: rt_core 1m13s · mujoco 25s · fleet_integration 1m52s. Node 20 deprecation 경고만 남음(checkout/upload-artifact v5 로 올리면 해소 — 아직 안 함).
- docs: README "숫자 한눈에"(환경 표기), measurements/README.md 색인, LOG 11/03~11/04 상세, DECISIONS 12건+, GLOSSARY, READING_GUIDE 25항목.

## 5. 측정값 요약 (환경 표기 필수)
- RT 루프(WSL 참고값): 1 kHz 드롭 0, 노드 wake p99 278~352 / max 679~2026 us, SCHED_FIFO 는 p50 92→37 us(꼬리 그대로).
- MuJoCo 한 주기: 러너 6.4/8.5/29.4 us, WSL 단독 4.9/6.3/20.8 us, 노드 안 work_us 41/145/247 us. 어깨 Pitch 중력 처짐 1.1°.
- DDS 1 MB: Fast DDS best_effort 99.8% 손실 vs Cyclone 0%.
- 관제 50대 1 Hz(WSL): 전달 지연 p50 0.9 / p95 1.8 ms. 장애: broker 10초 → 2.9초 복귀, 유실 0/1400 · db 10초 → backlog 0 까지 1.4초, 0/1341 · collector(qos1) 10초 → 1.6초, 0/1311 · 나쁜 펌웨어 3/50 에서 롤백 1.0초. 러너(10대 2 Hz)도 같은 모양(0·0·0, 롤백 0.4초).
- 유실의 역사(면접 소재): 처음 "0"은 측정 맹점 → 고치자 53 → 원인 셋(브로커 재시작 경쟁 4~5대×12 / 수집기 종료 순간 1개·장치 / 큐 상한 2,450개) → persistence true·곱게 종료로 0. 오프라인 이벤트 20 = 브로커 종료 시 일괄 유언.

## 6. 다음 할 일
- 소실험 2개(각 5분): `virtual_fleet.py --keepalive 30` 으로 10초 튐이 30초로 바뀌는지(keepalive 가설 확정) · 수집기/장치 QoS 0 조합으로 `--fault collector --label qos0`(유실 n 줄 추가).
- Pi 표①(D6~D8): Pi 모델·OS 확인 → `docs/SETUP_RT_MEASURE.md` 대로 RT 커널 → cyclictest + jitter_bench --prio 80 → `docs/measurements/jitter_pi_rt_*.json` → 표①.
- 문서·마무리: actions v5, README 최종, 2분 영상 대본, 이력서 문장(사용자 경력 숫자 5개 아직 미수령: 시스템 규모·초당 처리량·소켓 프로토콜·관제 주기·DB 일 처리량), D9 재직자 접촉 문구.
- 보류(면접에서 "다음 단계"로): 수동 ACK(DB 적재 뒤 PUBACK), 중력 보상, ALLEX 프로필, 실물 SO-101.
