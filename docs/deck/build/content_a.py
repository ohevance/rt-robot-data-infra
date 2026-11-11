# 장표 내용 A — 0 표지·읽는 법·목차(순서도), 4부 출발(공고 ↔ 증명한 숫자), 5부 어디서(환경)
# 각 장표는 dict: kind, section, title, ... (build_deck.js 의 KINDS 참고)
# 순서도 논리(2026-11-05 사용자 요구: 왕초보 입장에서 로봇을 움직이기까지의 과정을 맨 앞에, 시험·검증은 뒤로 빼고 번호만 표시):
#   로봇을 움직이는 길 10단계(1부) → 데이터의 길(2부) → ◇기준을 정말 넘었나? 검증(3부) → ◇공고를 다 덮었나? 숫자(4부)
#   → ◇어디서 만들었나?(5부) → ◇어떻게 믿나?(6부) → ◇왜 이렇게, 무엇이 깨졌나?(7부) → 끝
# {{first:글자}} 는 make_slides.py 가 "그 글자로 시작하는 첫 장표의 번호"로 바꾼다 (장표 번호를 손으로 적지 않는다)

SEC0 = "0. 표지·읽는 법·목차"
SEC4 = "4. 출발 — 공고가 요구한 것, 증명한 숫자"
SEC5 = "5. 어디서 — 전체 환경 지도"

# 목차 표의 장표 번호 범위는 make_slides.py 가 조립한 뒤 채운다 ({{range:부}} 자리)
TOC_ROWS = [
    ["부", "이 장이 답하는 질문", "답(요약)", "장표"],
    ["1부 로봇을 움직이는 길", "명령 하나가 로봇의 움직임이 되기까지 무엇을 거치나? (왕초보 → 핵심 소스 코드)", "10단계, 단계마다 들어온 것 → 문제 → 기준 → 코드(파일:줄) → 결과 → 판단. 시험은 번호만 적고 3부로", "{{range:1}}"],
    ["2부 데이터의 길", "로봇(수십 대)의 숫자를 잃지 않고 서버까지 가져오고, 장애·업데이트를 견디나?", "8단계: 에이전트 → 브로커 → 수집기 → DB·Grafana → OTA → 장애 주입·판정·진단 (코드 포함)", "{{range:2}}"],
    ["3부 검증", "1·2부에서 '확인 → 장표 N' 으로 미뤄 둔 기준들을 정말 넘었나? 숫자는 어떻게 나왔나?", "단계 순서대로: 표② DDS → 표① 1 ms 루프(일반 → RT → 격리) → 물리 → 표③ 관제(유실 53 → 0)", "{{range:3}}"],
    ["4부 출발", "이 길과 숫자가 공고(Framework S/W 엔지니어)의 주요 업무를 덮나? 무엇을 숫자로 증명했나?", "주요 업무 여섯 묶음 + 필수 역량 ↔ 산출물 ↔ 수치 ↔ 상태 한 표 · 숫자 한눈에 ①②", "{{range:4}}"],
    ["5부 어디서", "그 숫자는 어디서, 어떤 조건에서 만들었고 어디까지 믿나?", "네 곳(개발 PC · Pi 4 · GitHub CI · 작업본)과 각 곳의 '정상 신호'", "{{range:5}}"],
    ["6부 믿을 수 있나", "이 숫자들을 누가, 무엇으로, 언제 다시 재나?", "측정 스크립트(온도·부하 기록) · 테스트 37건 · CI 3잡 매 push", "{{range:6}}"],
    ["7부 왜·사고·방식", "왜 이렇게 만들었고(버린 대안), 무엇이 깨졌고, 어떻게 일했나?", "결정 25건 · 사고 11건 · 2주 일정 · AI 와 일한 방식 · 남은 일 · 용어 · 덧붙임 9장(11/06 ALLEX · 11/10~11 릴리스 → 배포 3장 · 클라우드 운영 층 · 사고 · 왕복 290 ms · 11/11 ZeroMQ 2장)", "{{range:7}}"],
    ["끝", "그래서 로봇은 어떻게 움직이나?", "한 장 요약 — 명령 50 Hz 에서 관제 대시보드까지, 숫자와 함께", "{{range:8}}"],
]


def cover():
    s = []
    s.append({"kind": "title", "section": SEC0,
              "title": "rt-robot-data-infra",
              "subtitle": "로봇은 어떻게 움직이나 — 명령 하나가 관절의 움직임이 되기까지 10단계를 핵심 소스 코드(파일:줄)와 함께 따라가고, 그 숫자를 어떻게 증명했는지까지. 2주 포트폴리오",
              "meta": "오문규 · 2026-11-05 (덧붙임 ~11/11) · github.com/ohevance/rt-robot-data-infra\n장표마다 설명 문서(docs/deck/notes/NNN.docx)가 하나씩 있다"})
    s.append({"kind": "bullets", "section": SEC0, "title": "이 장표를 읽는 법 — 로봇이 움직이는 과정을 먼저, 시험·검증은 뒤에 번호로", "crumb": "0 · 읽는 법",
              "bullets": [
                  "목적: 이 저장소를 처음 보는 사람(또는 면접관)에게 '로봇이 어떻게 움직이고, 그 코드가 어디에 있고, 무엇을 쟀고, 왜 그렇게 판단했나'를 처음부터 끝까지 끊김 없이 설명한다",
                  {"text": "순서: 1부 로봇을 움직이는 길(왕초보 바탕 → 한 장 그림 → 소스 코드 지도 → 단계 1~10, 단계마다 핵심 코드와 파일:줄) → 2부 데이터의 길 → 3부 검증(1·2부에서 미뤄 둔 시험) → 4부 공고와 숫자 → 5부 환경 → 6부 테스트·CI → 7부 결정·사고·방식 → 끝", "bold": True},
                  {"text": "1·2부 안에서는 시험·검증을 하지 않는다. 기준을 넘었는지는 들머리의 '결과' 상자에 숫자 한 줄로 적고, 자세한 실험은 '확인 → 장표 N' 으로 번호만 가리킨다. 3부에서 같은 단계 순서로 그 실험을 본다", "bold": True},
                  "모든 장(부)은 같은 꼴로 시작한다: [앞에서 안 것] → ◇[이 장의 질문] → [이 장의 답]. 모든 단계는 같은 꼴로 시작한다(들머리 장표): 들어온 것 → 문제 → ◇기준 → 확인 방법 → 결과 → 판단 → 다음. 그 뒤에 코드 장표가 따라온다",
                  "위 오른쪽 알약 = 지금 어디(부 · 단계 · 코드/확인/판단). 아래 '다음 ▶' 다리 = 왜 다음 장으로 넘어가는지. 이 둘만 따라가도 길을 잃지 않는다",
                  "그림 약속: 회색 상자 = 앞 단계에서 들어온 것, 민트 상자 = 코드/실험, 마름모 = 판단 기준(합격선), 파란 상자 = 확인 방법, 화살표 글 = 그 기준에 대한 답(실제 값), 진한 둥근 상자 = 결론, 붉은 상자 = 실패·원인",
                  "숫자 옆에는 항상 어디서 쟀는지가 붙는다: WSL2(가상 커널, 참고값) · Pi 4(PREEMPT_RT, 실측) · GitHub 러너(돌아간다의 증거). 단위는 us(마이크로초, 100만분의 1초), ms, rad, Hz",
                  "코드는 캡처가 아니라 저장소 파일에서 그대로 읽어 넣었고, 코드 상자 위에 항상 파일 경로와 줄 번호가 있다(2026-11-11 main 기준 — 빌드할 때 저장소 파일에서 읽는다). 장표 하나마다 docs/deck/notes/NNN.docx — 그 장표의 모든 요소를 처음 읽는 사람 기준으로 풀어 쓴 설명(왜 · 용어 · 단위 · 쉬운 예시 · 숫자 출처 · 면접 한 문장)",
              ]})
    s.append({"kind": "chain", "section": SEC0, "title": "목차 = 순서도 — '로봇을 움직이고 싶다'에서 출발해 '결국 로봇은 이렇게 움직인다'로 끝난다", "perRow": 4, "nodeH": 1.3, "crumb": "0 · 목차(순서도)",
              "items": [
                  {"kind": "in", "text": "출발: 로봇을 움직이고 싶다\n관절 6개짜리 팔에 '이 각도로' 를 전하면 실제로 움직이게 하려면?", "fs": 10},
                  {"kind": "do", "text": "1부 로봇을 움직이는 길 10단계\n명령 → DDS → 우편함 → 1 ms 루프 → 안전 검사 → 백엔드 → 움직임 → 상태 → 기록 → 관제. 단계마다 핵심 코드(파일:줄)", "fs": 9.5},
                  {"kind": "do", "text": "2부 데이터의 길 8단계\n로봇 → 에이전트 → 브로커 → 수집기 → DB·Grafana → OTA → 장애 주입·판정 (코드)", "fs": 10},
                  {"kind": "q", "text": "각 단계의 기준을\n정말 넘었나?", "answer": "3부 검증"},
                  {"text": "표② DDS 손실·RTT → 표① 1 ms 루프(일반 → RT → 격리) → 물리 → 표③ 관제(유실 53 → 0)", "fs": 10.5},
                  {"kind": "q", "text": "공고가 요구한 것을\n다 덮었나? 어떤 숫자로?", "answer": "4부"},
                  {"text": "공고 주요 업무 여섯 묶음 ↔ 산출물 ↔ 수치 ↔ 상태 한 표\n숫자 한눈에 ①②", "fs": 10.5},
                  {"kind": "q", "text": "그 숫자는 어디서,\n어떤 조건에서?", "answer": "5부"},
                  {"text": "환경 네 곳 — 개발 PC(WSL2) · Pi 4(RT 커널) · GitHub CI · 작업본 + 각 곳의 '정상 신호'", "fs": 10.5},
                  {"kind": "q", "text": "이 숫자들을\n어떻게 믿나?", "answer": "6부"},
                  {"text": "측정 스크립트(온도·부하·커널 기록) · 테스트 37건 · CI 3잡이 매 push 다시 잰다 → ◇왜 이렇게, 무엇이 깨졌나? → 7부 결정 25 · 사고 11 · 일정 · AI · 용어 · 덧붙임", "fs": 9},
                  {"kind": "end", "text": "끝: 결국 로봇은 이렇게 움직인다\n(한 장 요약, 숫자와 함께)"},
              ],
              "bottom": "읽는 법: 왼쪽 위에서 뱀처럼. 1·2부는 '길' 자체라 질문이 아니라 단계로 내려간다 — 단계 안에서 같은 꼴(들어온 것 → 문제 → 기준 → 코드 → 결과 → 판단)이 반복되고, 시험은 '확인 → 장표 N' 으로 3부를 가리킨다. 마름모(질문)마다 다음 부가 그 답이다"})
    s.append({"kind": "table", "section": SEC0, "title": "목차 — 부마다 '질문 → 답 → 장표 번호'", "fontSize": 11, "crumb": "0 · 목차(표)",
              "colW": [2.0, 4.4, 4.7, 1.2],
              "rows": TOC_ROWS,
              "note": "장표 번호는 오른쪽 아래 숫자와 같다. 장표마다 설명 문서가 같은 번호로 있다: docs/deck/notes/NNN.docx (예: 37번 장표 → notes/037.docx). 1·2부 안의 '확인 → 장표 N' 도 같은 번호"})
    return s


def start():
    s = []
    s.append({"kind": "section", "section": SEC4, "num": "04", "title": "출발 — 공고가 요구한 것, 그래서 증명한 숫자",
              "subtitle": "로봇을 움직이는 길(1부)·데이터의 길(2부)·검증(3부)을 끝까지 왔다. 이제 출발점으로 돌아가 '이 길이 공고가 요구한 것을 다 덮나, 무엇을 숫자로 증명했나'를 한 표로 본다",
              "flow": {"from": "명령에서 움직임까지 10단계(1부)와 데이터의 길 8단계(2부), 그 기준들을 넘었다는 검증(3부)",
                       "question": "이 길과 숫자가 공고(Framework S/W 엔지니어)의 주요 업무를 덮나? 무엇을 숫자로 증명했나?",
                       "answer": "주요 업무 여섯 묶음 중 다섯에 코드 + 숫자 — ① 프레임워크·프로세스·IPC ② 실시간 제어(PREEMPT_RT) ③ 상태 머신 ④ 통신 패킷·SDK(ZeroMQ·ROS 2) ⑥ OTA·로깅. ⑤ EtherCAT 은 하드웨어가 없어 없다(들어갈 자리만). 필수 역량 Git·Docker·CI/CD 는 6부. 숫자 한눈에 ①(실시간) ②(관제·물리)"},
              "agenda": ["공고 주요 업무(여섯 묶음) + 필수 역량 ↔ 산출물(코드) ↔ 수치(표) ↔ 상태 — 한 표 (없는 것도 적는다)", "숫자 한눈에 ① 실시간(Pi 4 실측) · ② 관제·장애·OTA·물리(WSL2 + CI 러너) — 어디서 쟀는지와 함께", "→ 다음 질문: 이 숫자들은 어디서, 어떤 조건에서 만들었고 어디까지 믿나? (5부)"]})
    s.append({"kind": "table", "section": SEC4, "title": "공고(Framework S/W 엔지니어) 주요 업무 ↔ 산출물 ↔ 수치 ↔ 상태 — 여섯 묶음 중 다섯에 코드와 숫자, EtherCAT 은 없다", "fontSize": 9, "crumb": "4부 출발 · 공고 ↔ 산출물 ↔ 숫자",
              "colW": [2.3, 4.6, 3.6, 1.8],
              "rows": [["공고 주요 업무", "산출물(코드)", "수치(표·실험)", "상태"],
                       ["① Linux 로봇 프레임워크 · 프로세스 구조·미들웨어 · 멀티스레드 데이터 흐름 · IPC", "rt_core: RT 스레드 ↔ 일반 스레드를 락 없는 우편함(spsc_ring)으로 · 같은 핵심을 노드 둘이 감쌈(ROS 2 · ZeroMQ) · 같은 PC 는 공유 메모리 seqlock · 백엔드 하나 뒤에 6 자유도 팔과 ALLEX 48 자유도(프로필만 다름) (1부 단계 2~7)", "1 kHz 루프 드롭 0(Pi 4, 14조건) · seqlock 섞인 읽기 0 / 36,692 · ALLEX 500 Hz 물리 p99 510 us(2 ms 의 26 %)", "완료"],
                       ["② 실시간 제어 환경(Xenomai · PREEMPT_RT) · 지연 최적화", "PREEMPT_RT + SCHED_FIFO + mlockall + CPU 고정 + isolcpus(Pi 4), 측정기 jitter_bench 와 cyclictest 교차 확인 (1부 단계 4, 3부 표①)", "부하 중 깨어남 max 781 → 189 us · cyclictest max 695 → 132 us · 측정기 vs cyclictest 270 vs 274 us", "PREEMPT_RT 완료. Xenomai 는 안 함"],
                       ["③ 상태 머신 · 오류 복구 시나리오", "robot_state_machine: INIT → READY → RUNNING → FAULT → RECOVERING, 전이 표 + 불법 전이 카운터 · 워치독 → FAULT(자리 유지) → 명령이 다시 오면 복구 (1부 단계 5)", "명령이 끊기면 51~52 ms 뒤 FAULT(워치독 50 ms) · 불법 전이 0 — 끝-대-끝이 매 push", "완료"],
                       ["④ ZeroMQ · ROS 통신 패킷 · Python/C++ SDK", "wire.hpp(머리 24바이트 + 본문, C++·Python 골든 바이트) · rt_zmq_node(DEALER↔ROUTER 명령, PUB 상태) · Python SDK rtsdk · ROS 2 노드 · dds_bench (7부 덧붙임 ZeroMQ)", "명령 → 반영 → 상태 p50 0.88 / p99 1.81 ms(WSL, 1,000회, 잃음 0) · 상태 1만 개 빈 번호 0 · 표② DDS", "완료(11/11). C++ 소켓 클라이언트·Pi 값은 아직"],
                       ["⑤ EtherCAT 마스터 · 슬레이브 진단 · 오류 복구", "없음 — 하드웨어가 없다. 들어갈 자리는 Backend 인터페이스 하나(SimLag · MuJoCo 가 같은 자리)", "—", "없음(지원 뒤 판단)"],
                       ["⑥ OTA 업데이트 · 로그 수집·분석", "fleet: MQTT → TimescaleDB → Grafana, 장애 주입 4종 · 릴리스: 태그 → 빌드 → 가상 50대 카나리 → 게시 → 장치가 sha256·A/B 슬롯·자가 점검으로 설치 · 로봇 안 기록 rosbag2 → CSV · 클라우드 운영 층 (2부, 7부 덧붙임)", "50대 설치 14.62 s · 깨진 패키지 3/50 에서 거부 → 롤백 1.0 s · 브로커 중단 유실 0 / 1400 · 실물 Pi 53,167건 유실 0", "완료. v0.9.0 게시(11/11)"],
                       ["필수 역량: Git · Docker · CI/CD", "CI 3잡(단위 → 통합 컨테이너 · MuJoCo 헤드리스 × 2 모델) + 릴리스 워크플로(태그 → 4잡) (6부)", "테스트 37건(C++ 7 · Python 30) + 끝-대-끝 셋 · 태그 → 게시 1분 27초", "완료, CI 초록"]],
              "note": "출처: README.md 첫 표(11/11 에 공고를 Framework S/W 엔지니어로 바꿔 다시 나눔 — 산출물은 같다, DECISIONS 11/11). '완료'는 코드가 있고 실제로 돌려 숫자를 얻었다는 뜻이지 '제품 수준'이라는 뜻이 아니다. 필수 역량 중 Linux C/C++ · 멀티스레드·네트워크 · ZeroMQ/DDS/ROS 2 · 상태 머신은 ①~④ 줄에 있다"})
    s.append({"kind": "kpi", "section": SEC4, "title": "숫자 한눈에 ① — 실시간 (Pi 4, PREEMPT_RT 실측) — 표①이 답하는 것", "crumb": "4부 출발 · 숫자 한눈에 ① 실시간",
              "kpis": [{"value": "781 → 189 us", "label": "부하 중 깨어남 지연 max\n일반 커널 → RT + isolcpus=3 (jitter_bench)"},
                       {"value": "695 → 132 us", "label": "표준 도구 cyclictest max\n일반 → RT (4 CPU 중 최악)"},
                       {"value": "270 vs 274", "label": "내 측정기 vs cyclictest\n같은 설정으로 맞췄을 때 (us)"},
                       {"value": "0 드롭", "label": "1 kHz 루프, Pi 4 14조건(60~300 s)\n전부 드롭 0 · 스로틀 0"}],
              "bullets": ["읽는 법: 평균이 아니라 max 로 판단한다 — 1 ms 주기 안에 '항상' 들어와야 로봇이 멈추지 않는다 (p99.9 와 max 가 표①의 주인공)",
                          "우선순위(SCHED_FIFO)는 p50 만 좋게 하고(WSL 92 → 37 us) max 는 못 자른다(921 → 937). 꼬리를 자르는 것은 커널(PREEMPT_RT)이고, 그 CPU 의 다른 일을 치우는 것이 격리(isolcpus)다 — 실험 사슬은 3부 장표 {{first:단계 4 검증 — 표① 실험 사슬 (1/3)}}~{{first:단계 4 검증의 결론}}",
                          "정직한 줄: RT 커널은 공짜가 아니다 — 부하 p99 가 146 → 185 us 로 조금 나빠진다 (상한을 사고 평균을 조금 내준다)"],
              "foot": "원본: docs/measurements/table1_pi4.md (14줄, .meta 에 온도·스로틀), 해석: docs/experiments/E18.md, E19a~d.md. 이 숫자들이 어떻게 나왔는지는 1부 단계 4 와 3부"})
    s.append({"kind": "kpi", "section": SEC4, "title": "숫자 한눈에 ② — 관제·장애·OTA·물리 (WSL2 + CI 러너) — 표③과 물리가 답하는 것", "crumb": "4부 출발 · 숫자 한눈에 ② 관제·물리",
              "kpis": [{"value": "0 / 1400", "label": "브로커 10초 중단 뒤 유실\n(전 장치 복귀 2.9초)"},
                       {"value": "508 / 1312", "label": "같은 장애, QoS 0 이면 유실\n(QoS 1 지속 세션은 0 / 1311)"},
                       {"value": "3 / 50, 1.0초", "label": "나쁜 펌웨어: 닿은 장치 / 롤백 시간\n(5% 단계 헬스 게이트)"},
                       {"value": "0.9% · 46%", "label": "MuJoCo 물리 한 주기 p99 / 1 ms 예산\n6축 8.5 us · ALLEX 48축 458 us (러너)"}],
              "bullets": ["유실 0 은 처음부터 0 이 아니었다 — 측정 맹점을 고치자 53 이 나왔고, 원인 셋(브로커 재시작 경쟁·종료 순간·큐 상한)을 추적해 설정과 종료 처리로 0 을 만들었다 (2부 ⑦⑧, 3부 표③ 사슬 장표 {{first:2부 ⑦⑧ 검증 — 표③ 실험 사슬 (1/3)}}~)",
                          "물리가 들어오자 어깨 관절이 목표보다 0.019 rad(1.1°) 처졌다 = 중력. 기록 파이프라인의 자동 요약에도 같은 숫자가 나온다 (1부 단계 7·9)",
                          "같은 장애 4종을 GitHub 러너(10대 2 Hz)에서 매 push 마다 다시 돌린다: 유실 0·0·0, 롤백 0.4초 (6부)",
                          "회사가 공개한 ALLEX 모델(48 자유도)은 프로필 하나로 붙었고 제어 코드는 안 바뀌었다(11/06). 물리 비용은 6축의 약 70~100배라 제어 주기를 모델 기본 걸음인 500 Hz 로 — 실측 p99 러너 510 us(2 ms 의 26%), WSL 1,000 us(50%) (7부 장표 {{first:덧붙임}})",
                          "11/10~11 보탬 — OTA 가 흉내에서 진짜 설치로: 태그 하나로 러너가 가상 50대에 14초에 깔고, 깨진 빌드는 3 / 50 에서 거부해 1.0초에 되돌린다. 실물 Pi 는 한 번에 약 1초. 운영 층은 시드니 서버에서 24시간 — Pi 14.8시간 53,167건 유실 0, 서버까지 왕복 290 ms (7부 장표 {{first:덧붙임 (11/10) — 릴리스}}~{{first:덧붙임 (11/11) — 서버까지}})"],
              "fontSize": 11,
              "foot": "원본: docs/measurements/table3.md, table3_ci.md, mujoco_backend_ci.json, mujoco_backend_allex_*.json, record_summary_wsl_20261105.md, ota_release_v0.9.0*.json, soak_pi-rt_*.json, rtt_pi_sydney_*.json",
              "next": "5부 — 증명한 숫자는 나왔다. 그 숫자는 어디서, 어떤 조건에서 만들었고 어디까지 믿나? (환경 네 곳과 각 곳의 '정상 신호')"})
    return s


def where():
    s = []
    s.append({"kind": "section", "section": SEC5, "num": "05", "title": "어디서 — 전체 환경 지도",
              "subtitle": "컴퓨터 네 곳에 무엇이 있고, 코드와 숫자가 어느 길로 오가며, 각 곳의 결과를 어떻게 읽나. 이 장이 끝나면 '어느 숫자를 어디까지 믿나'의 규칙이 선다",
              "flow": {"from": "증명한 숫자 셋 — 표① 1 ms 루프 지연 · 표② DDS 전달 · 표③ 관제 유실·복구·OTA (4부)",
                       "question": "그 숫자는 어디서, 어떤 조건에서 만들었고 어디까지 믿나?",
                       "answer": "네 곳: ① 개발 PC WSL2(전부 돈다, 지연 수치는 참고값) ② Raspberry Pi 4(진짜 RT 커널 — 표①은 여기서만) ③ GitHub CI(매 push 재증명, '돌아간다'의 증거) ④ 작업본(초안). 각 곳의 '정상 신호'를 정해 두고 그 신호가 맞을 때의 숫자만 표에 올린다"},
              "agenda": ["한 장 그림 — 네 곳과 그 사이의 길", "왜 한 곳으로는 안 되나 · 코드와 숫자가 오가는 길(트리거·명령·확인)", "① 개발 PC 의 '정상' 신호 · ② Pi 4 측정이 유효하려면(확인 5가지)", "→ 다음: 환경을 알았다. 이 숫자들을 누가, 무엇으로, 언제 다시 재나? (6부)"]})
    s.append({"kind": "image", "section": SEC5, "title": "환경 지도 — 네 곳과 그 사이의 길", "image": "img/env_map.png", "crumb": "5부 어디서 · 한 장 그림",
              "caption": "실선 = 코드와 숫자가 실제로 흐르는 길, 점선 = 참고 관계. GitHub 가 가운데: 네 곳 모두 main 을 기준으로 맞춘다. 11/05 의 그림 — 11/10 에 더한 다섯째 곳(클라우드 서버)은 다음 장표의 비고와 장표 {{first:덧붙임 (11/10~11) — 운영 층}}. 출처: docs/ENVIRONMENT.md §0"})
    s.append({"kind": "table", "section": SEC5, "title": "왜 네 곳인가 — 한 곳으로는 안 되는 이유 (각 곳이 '못 하는 것'이 다음 곳을 만든다)", "fontSize": 11, "crumb": "5부 어디서 · 왜 네 곳",
              "colW": [1.9, 3.6, 3.6, 3.2],
              "rows": [["곳", "하는 일", "왜 여기여야 하나", "못 하는 것"],
                       ["① 개발 PC (WSL2 Ubuntu 24.04)", "모든 코드를 실제로 돌린다 — ROS 2 노드, 관제 컨테이너 3개, 가상 장치 50대, 장애 주입, 기록", "12 CPU · Docker · ROS 2 가 있는 유일한 곳. Grafana 화면도 여기", "실시간 지연 수치 — 가상 커널이라 max 가 1 ms 턱밑(921~2,026 us). 전부 '참고값' → ② 가 필요"],
                       ["② Raspberry Pi 4B 4 GB", "표① 하나만 잰다 — 일반 커널 vs PREEMPT_RT, 고정, 격리", "진짜 하드웨어 + 진짜 RT 커널. 4코어라 격리 실험이 된다", "ROS 2·Docker·MuJoCo 없음. GitHub 로그인 없음 — 측정만, 커밋은 ①"],
                       ["③ GitHub (ohevance/rt-robot-data-infra)", "저장소(이력 전체) + CI(push 마다 자동 검사) + 공개 링크", "어느 PC 에서도 같은 코드를 받는 기준점. 러너는 매번 새 VM", "RT 커널·권한 없음 → 지연 수치 못 잼. '돌아간다'의 증거"],
                       ["④ 작성 보조 작업본 (Claude 샌드박스)", "코드·문서 초안, 컴파일·단위 테스트, git bundle 전달", "작은 패치 단위로 작성자가 검토할 수 있게", "ROS 2·Docker·MuJoCo·네트워크 없음 → 가짜 위에서 논리만. 진짜 첫 실행은 항상 ①"]],
              "note": "비유: ① 작업장, ② 계측실(진동 없는 방), ③ 도면 보관소 겸 검사원, ④ 설계 사무실. 출처: docs/ENVIRONMENT.md §1. 11/10 부터 다섯째 곳이 생겼다 — 클라우드 서버(AWS 시드니): 운영 층(브로커·수집기·DB·Grafana)이 24시간 돌고, Pi 는 에이전트 서비스로 거기에 보고한다 → 7부 덧붙임 장표 {{first:덧붙임 (11/10~11) — 운영 층}}"})
    s.append({"kind": "table", "section": SEC5, "title": "코드와 숫자가 오가는 길 — 언제, 무엇이 움직이나", "fontSize": 10.5, "crumb": "5부 어디서 · 길과 트리거",
              "colW": [2.2, 2.0, 5.3, 2.8],
              "rows": [["길", "트리거", "명령", "결과 확인"],
                       ["④ → ① 패치 전달", "작업본이 커밋을 만들면", "patch-NN.bundle 이 Downloads 에 → [WSL] git pull --no-rebase --no-edit /mnt/c/Users/…/patch-NN.bundle main", "Fast-forward 와 파일 목록 (--rebase 금지: 이력을 다시 써서 충돌, 11/04)"],
                       ["① → ③ 공개", "사람이 결정할 때", "git push (push 는 항상 사람이)", "main -> main, 몇 분 뒤 CI"],
                       ["③ → ④ 기준 맞추기", "패치 만들기 전", "작업본이 git fetch (읽기 전용)", "번들의 기준 커밋 = 사용자의 main"],
                       ["③ → ② Pi 갱신", "측정 스크립트가 바뀌면", "[Pi] git pull", "untracked 결과 파일이 있으면 막힘 → rm 뒤 pull"],
                       ["② → ① → ③ 측정 결과", "측정이 끝나면", "[WSL] scp '<사용자>@<Pi IP>:…/docs/measurements/*pi4*' docs/measurements/ → make_table1.py → commit → push", "table1_pi4.md 줄 수, 각 줄 '스로틀 0'"],
                       ["① 기록 → 저장소", "기록 실험 뒤", "summary.md · rt_status.csv 만 docs/measurements 로 (MCAP 원본 1 MB 는 build/, 제외)", "record_* 파일"]],
              "note": "규칙: 커밋 주체는 ① 하나(Pi 도 작업본도 push 하지 않는다). 숫자는 원본 파일과 함께. 출처: docs/ENVIRONMENT.md §2"})
    s.append({"kind": "table", "section": SEC5, "title": "① 개발 PC — 무엇이 떠 있어야 하고, 무엇을 보고 판단하나", "fontSize": 10.5, "crumb": "5부 어디서 · ① 개발 PC 의 정상 신호",
              "colW": [1.7, 4.2, 3.4, 3.0],
              "rows": [["구성", "띄우는 법", "'정상' 신호", "비정상이면"],
                       ["WSL 터미널", "새 창 (.bashrc 가 venv·ROS 2·RT_REPO_ROOT 자동 설정)", "프롬프트 앞 (.venv), echo $RT_REPO_ROOT 가 저장소 경로", "docs/SETUP_WSL.md 의 .bashrc 블록"],
                       ["관제 컨테이너 3개", "docker compose -f fleet/docker-compose.yml up -d", "docker ps 에 fleet_mqtt·fleet_db·fleet_grafana Up, localhost:3000", "docker compose … logs <이름>"],
                       ["수집기", "python3 fleet/collector/collector.py --qos 1 (한 번에 하나, flock)", "1초마다 msgs/s=50 online=50 … backlog=0 db_err=0", "backlog 증가 = DB 죽음, online 급감 = 브로커/장치, '이미 떠 있습니다' = 중복"],
                       ["가상 장치", "python3 fleet/agent/virtual_fleet.py --count 50 --rate 1 --telemetry-qos 1", "수집기의 online=50", "reconnects 가 계속 늘면 client_id 충돌(두 벌)"],
                       ["ROS 2 노드", "./install/rt_control_ros2/lib/rt_control_ros2/rt_control_node --ros-args --params-file …so101_mujoco.params.yaml", "backend=mujoco dof=6 loop=1000 Hz, rt_status 의 timing_drops: 0, state: RUNNING", "토픽 안 보이면 ros2 daemon stop (RMW 꼬임), 고아는 pkill -f rt_control_node"],
                       ["기록", "bash data_pipeline/record.sh 30 → bag_to_csv.py", "summary.md 에 실제 Hz = 설계 Hz, 틈 0, 드롭 0", "조용히 안 끝나면 정지된 것(SIGTTIN) — pkill -CONT 뒤 -INT"]],
              "note": "WSL 에서 나오는 지연 수치는 전부 참고값(가상 커널). 출처: docs/ENVIRONMENT.md §3"})
    s.append({"kind": "table", "section": SEC5, "title": "② Raspberry Pi 4 — 측정이 유효하려면 (확인 5가지, 하나라도 아니면 그 숫자는 버린다)", "fontSize": 11, "crumb": "5부 어디서 · ② Pi 4 측정 유효 조건",
              "colW": [1.8, 4.6, 2.6, 3.3],
              "rows": [["확인", "명령", "정상", "아니면"],
                       ["RT 커널인가", "uname -r; cat /sys/kernel/realtime", "…-raspi-realtime / 1", "pro enable realtime-kernel --variant=raspi, 재부팅"],
                       ["격리", "cat /sys/devices/system/cpu/isolated", "3", "/boot/firmware/cmdline.txt 끝에 isolcpus=3 nohz_full=3 rcu_nocbs=3"],
                       ["클럭 고정", "cat /sys/devices/system/cpu/cpu0/cpufreq/scaling_governor", "performance", "echo performance | sudo tee …/scaling_governor"],
                       ["열·스로틀", "cat /sys/class/thermal/thermal_zone0/temp; cat /sys/devices/platform/soc/soc:firmware/get_throttled", "시작 50 °C 아래, 플래그 0", "식힌다. 플래그 ≠ 0 이면 그 측정은 버린다"],
                       ["결과 판단", "각 스크립트 끝의 temp: a -> b mC | throttled: 0", "0", "0 아니면 재측정"]],
              "note": "측정하는 동안 Pi 는 측정 외의 일을 하지 않는다(11/10 부터는 에이전트 서비스가 상시 돈다 — 표①을 다시 잴 때는 서비스를 멈추고 잰다). 11/04~05 실측: 부하 75초에 45 → 75 °C(방열판 없음) → 부하 측정 120초 상한. 출처: docs/ENVIRONMENT.md §4, docs/SETUP_RT_MEASURE.md",
              "next": "6부 — 환경과 '정상 신호'를 알았다. 이 숫자들을 누가, 무엇으로, 언제 다시 재나? (측정 스크립트 · 테스트 37건 · CI 3잡)"})
    return s
