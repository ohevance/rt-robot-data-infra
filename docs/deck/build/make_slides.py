# 장표 조립 — content_a/b/c/d + gates + diagrams_front → slides.json
# 역할: (1) 1부·2부 장표에 '지금 어디'(crumb) 와 '다음 ▶'(next) 를 붙인다
#       (2) 단계마다 들머리(gate) 장표와 '그림 한 장' 장표를 끼운다
#       (3) "verify": True 인 시험·검증 장표를 1·2부에서 꺼내 3부(검증)로 옮긴다 (사용자 요구: 과정은 앞에, 시험은 뒤에 번호만)
#       (4) 목차 표의 범위 {{range:N}} 와 본문의 {{first:글자}}(그 글자로 시작하는 첫 장표 번호)를 채운다
# 읽는 순서: 섹션 이름 → crumb 도우미 → NAV_B/NAV_C(장표별 crumb·next, 제목으로 자리 찾기) → EXTRA(끼울 그림) → VERIFY_NAV → main
# 실행: python3 make_slides.py  → slides.json   (RT_REPO_ROOT 를 주면 그 저장소에서 코드를 읽는다)
import json
import sys

import content_a, content_b, content_c, content_d
import diagrams_front as DF
from gates import GATES_B, GATES_C

SEC1 = content_b.SEC3          # "1. 로봇을 움직이는 길 — …"
SEC2 = content_c.SEC4          # "2. 데이터의 길 — …"
SECV = "3. 검증 — 각 단계의 기준을 정말 넘었나"

STAGE_B = {1: "명령이 생긴다", 2: "DDS 전달", 3: "우편함", 4: "RT 1 ms 루프", 5: "제어 단계(안전)",
           6: "백엔드", 7: "로봇이 움직인다", 8: "상태 발행", 9: "기록", 10: "관제로"}
STAGE_C = {1: "① 장치 에이전트", 2: "② 브로커", 3: "③ 수집기", 4: "④⑤ DB·Grafana", 5: "⑥ OTA", 6: "⑦⑧ 장애·판정·진단"}


def crumb_b(stage, step):
    return f"1부 로봇을 움직이는 길 · 단계 {stage}/10 {STAGE_B[stage]} · {step}"


def crumb_c(stage, step):
    return f"2부 데이터의 길 · {STAGE_C[stage]} · {step}"


# 장표별 길잡이: (제목에 들어 있어야 하는 글자, 단계, 걸음 표시, 다음 ▶ 글). 순서대로 훑으며 제목으로 찾는다(번호를 안 쓰므로 장표를 끼워도 안 깨진다)
# 단계 0 = 단계 밖 — 이때 걸음 표시가 crumb 전체. "verify": True 장표는 여기 없고 VERIFY_NAV 에서 다룬다
NAV_B = [
    ("바탕 지식", 0, "1부 로봇을 움직이는 길 · 바탕 지식 여섯 가지", None),
    ("한 장 그림", 0, "1부 로봇을 움직이는 길 · 한 장 그림 — 10단계", None),
    ("같은 길을 구조도로", 0, "1부 로봇을 움직이는 길 · 구조도(실시간 · 관제 · 측정)", None),
    ("소스 코드 지도", 0, "1부 로봇을 움직이는 길 · 소스 코드 지도(단계 ↔ 파일:줄)", None),
    ("노드 안의 '두 세계'", 0, "1부 로봇을 움직이는 길 · 두 세계(일반 스레드 ↔ RT 스레드)", None),
    ("단계 1 — 명령이 생긴다", 1, "② 무엇·누가·얼마나 자주", "단계 2 — 명령은 50 Hz 로 만들어졌다. 다른 프로세스의 노드까지 어떻게, 얼마나 믿을 만하게 가나? (ROS 2 / DDS)"),
    ("단계 2 — ROS 2 / DDS 가 전달한다", 2, "② 미들웨어가 하는 일 · QoS", "단계 3 — 관절 명령(수십 B)은 어느 조합이든 손실 0 (검증은 3부 장표 {{first:단계 2 검증 — 측정기}}~{{first:단계 2 검증 — E04}}). 도착한 명령을 일반 스레드에서 RT 스레드로 어떻게 넘기나? (우편함)"),
    ("단계 3 — 노드가 받아", 3, "② 코드 — on_command()", None),
    ("단계 3 — 우편함의 정체", 3, "② 코드 — SPSC 링 push/pop", None),
    ("단계 3 — 왜 락", 3, "④ 판단 — 왜 락이 아니라 링인가", "단계 4 — 우편함에 명령이 있다. 누가 1 ms 마다 '정확히' 깨서 꺼내나? (RT 루프)"),
    ("단계 4 — RT 스레드가 1 ms 마다 깬다 — 준비", 4, "② 코드 — 준비 5단계", None),
    ("단계 4 — 루프 본체 (1/2)", 4, "② 코드 — 루프 본체 1/2", None),
    ("단계 4 — 루프 본체 (2/2)", 4, "② 코드 — 루프 본체 2/2", "단계 5 — 이 루프는 Pi 4 RT+격리에서 max 189 us, 1 ms 안에 항상 깬다(검증은 3부 장표 {{first:단계 4 검증 — 측정기}}~{{first:단계 4 검증의 결론}}). 깨서 꺼낸 명령을 그대로 쓰면 위험하다 — 끊김·튐·불법 전이를 어떻게 막나? (제어 단계)"),
    ("단계 5 — 제어 단계 — 한 주기에", 5, "② 코드 — step() 다섯 가지", None),
    ("단계 5 — ① 최신 명령만", 5, "② 코드 — 최신 명령만", None),
    ("단계 5 — ② 워치독", 5, "② 코드 — 워치독", None),
    ("단계 5 — ③ 변화량 제한", 5, "② 코드 — 변화량 제한", None),
    ("단계 5 — 상태 머신 — 로봇이", 5, "② 구조 — 상태 머신 그림", None),
    ("단계 5 — 상태 머신 코드 (1/2)", 5, "② 코드 — 전이표", None),
    ("단계 5 — 상태 머신 코드 (2/2)", 5, "② 코드 — handle()", None),
    ("단계 5 — rt_status 에 올라가는 카운터", 5, "④ 판단 — rt_status 카운터", "단계 6 — 안전해진 목표(applied_)가 생겼다. 로봇이 셋(SimLag·MuJoCo·실물)인데 제어 코드는 그대로 두고 어떻게 쓰나? (백엔드)"),
    ("단계 6 — 백엔드가 로봇에 쓴다", 6, "② 코드 — Backend 인터페이스", None),
    ("단계 6 — 백엔드 A", 6, "② 코드 — 백엔드 A SimLag", None),
    ("단계 6 — 백엔드 B — MuJoCo: 목표를", 6, "② 코드 — 백엔드 B MuJoCo 쓰기/읽기", None),
    ("단계 6 — 백엔드 B — 시뮬레이션 걸음", 6, "② 코드 — 백엔드 B 걸음 맞추기", None),
    ("단계 6 — 모델과 관절의 연결", 6, "② 설정 — 로봇 프로필 YAML", "단계 7 — 목표가 MuJoCo 액추에이터에 들어갔다. 물리는 목표를 따라갔나, 어디까지? (실측 숫자)"),
    ("단계 7 — 로봇이 이렇게 움직인다", 7, "③ 결과 — 실측 숫자", None),
    ("단계 8 — 상태를 읽어 올린다", 8, "② 코드 — publish_state 100 Hz", None),
    ("단계 8 — rt_status", 8, "② 코드 — rt_status 1 Hz JSON", "단계 9 — 상태가 토픽으로 나온다. 사고 분석·튜닝용 원본을 어디에 남기고, 남긴 것이 맞는지 누가 보나? (기록, E20)"),
    ("단계 9 — 기록한다", 9, "③ 흐름과 결과 — E20", None),
    ("단계 9 — 기록(rosbag2)과 관제", 9, "④ 판단 — 기록 vs 관제, 왜 둘인가", "단계 10 — 원본은 로봇 안에 남겼다. 수십 대를 한 화면에서 보려면 요약을 서버로 — 어떤 길로? (다리)"),
    ("단계 10 — 관제로 올린다", 10, "② 코드 — 다리 ros_status_bridge", "가로지르기 — 10단계는 정상일 때의 길이었다. 명령이 끊기면 무슨 일이 일어나나? (안전 경로)"),
    ("안전 경로", 0, "1부 로봇을 움직이는 길 · 가로지르기 — 안전 경로(명령이 끊기면)", "마무리 — 가상 로봇(MuJoCo)에서 끝까지 갔다. 실물 SO-101 로 가면 무엇이 바뀌고 무엇이 그대로인가?"),
    ("실물 로봇", 0, "1부 로봇을 움직이는 길 · 마무리 — 실물 로봇으로 가면", "2부 데이터의 길 — 로봇 안은 끝. 다리를 건너온 숫자가 서버에서 유실 없이 저장·표시되고, 장애와 업데이트를 견디는지 따라간다 (시험·검증은 3부)"),
]
# 들머리를 끼울 자리: (단계, 이 글자로 시작하는 첫 장표 '앞'에)
GATE_BEFORE_B = [(1, "단계 1 —"), (2, "단계 2 —"), (3, "단계 3 —"), (4, "단계 4 —"), (5, "단계 5 —"),
                 (6, "단계 6 —"), (7, "단계 7 —"), (8, "단계 8 —"), (9, "단계 9 —"), (10, "단계 10 —")]
# 그림 한 장을 끼울 자리: (이 글자로 시작하는 첫 장표 '뒤'에, 장표, crumb, next)
EXTRA_B = [
    ("단계 1 들머리", DF.stage1(), crumb_b(1, "② 그림 — 누가 무엇을 어디로"), None),
    ("단계 2 들머리", DF.stage2(), crumb_b(2, "② 그림 — 두 프로세스 사이"), None),
    ("단계 3 들머리", DF.stage3(), crumb_b(3, "② 그림 — 링 버퍼 우편함"), None),
    ("단계 4 들머리", DF.stage4(), crumb_b(4, "② 그림 — 목표 시각과 깨어남 지연"), None),
    ("단계 5 들머리", DF.stage5(), crumb_b(5, "② 그림 — 한 주기의 다섯 가지"), None),
    ("단계 6 들머리", DF.stage6(), crumb_b(6, "② 그림 — 인터페이스와 세 구현"), None),
    ("단계 7 — 로봇이 이렇게 움직인다", DF.stage7_chart(), crumb_b(7, "③ 그래프 — 관절별 추종 오차"), "단계 8 — 로봇이 움직였다(어깨 1.1° 처짐 포함). 그 사실을 1 kHz RT 스레드 밖으로 어떻게 내보내나? (상태 100 Hz · rt_status 1 Hz)"),
    ("단계 8 들머리", DF.stage8(), crumb_b(8, "② 그림 — 벨트와 발행 스레드"), None),
    ("단계 10 들머리", DF.stage10(), crumb_b(10, "② 그림 — 로봇에서 화면까지"), None),
]

NAV_C = [
    ("한 장 그림", 0, "2부 데이터의 길 · 한 장 그림 — 8단계", None),
    ("같은 길을 토픽", 0, "2부 데이터의 길 · 구조도(토픽·설정)", None),
    ("① 장치 에이전트 — 1 Hz tick", 1, "② 코드 — tick · send_or_buffer", None),
    ("① 장치 에이전트 — 재접속하면", 1, "② 코드 — on_connect · flush_buffer · 유언", None),
    ("① 장치 에이전트 — 한 주기의 흐름", 1, "② 그림 — 한 주기", None),
    ("① 가상 장치 50대", 1, "② 가상 장치 50대 · 단일 인스턴스 잠금", "② 브로커 — 장치는 끊겨도 모았다가 보낸다(654 = 654, 3부 장표 {{first:2부 ⑦⑧ 검증 — 표③ 실험 사슬 (1/3)}}). 받는 쪽 브로커는 수집기가 없는 동안 대신 들고 있나, 재시작하면? (설정 세 줄)"),
    ("② 브로커", 2, "② 설정 — mosquitto.conf", "③ 수집기 — 브로커가 잃지 않게 됐다. 초당 50개를 DB 에 빠르게, 그러나 DB 가 죽어도·내가 죽어도 잃지 않게 적재하려면?"),
    ("③ 수집기 — 받는 쪽", 3, "② 코드 — on_message", None),
    ("③ 수집기 — 1초마다 (1/2)", 3, "② 코드 — flush_once · 상한", None),
    ("③ 수집기 — 1초마다 (2/2)", 3, "② 코드 — drain_backlog", None),
    ("③ 수집기 — 종료할 때", 3, "④ 판단 — 종료 때 마지막 1초", "④⑤ DB · Grafana — 1초 묶음이 DB 로 들어간다. 시간 데이터를 어떻게 쌓고 사람에게 보이나?"),
    ("④ TimescaleDB", 4, "② 구조 — 표 5개 · 패널 14개", "⑥ OTA — 올라오는 길은 됐다. 반대 방향(서버 → 장치)으로 펌웨어를 안전하게 내리려면? 나쁜 펌웨어면?"),
    ("⑥ OTA 배포기 — 한 단계 (1/2)", 5, "② 코드 — run_stage 1/2 보내기·적용 대기", None),
    ("⑥ OTA 배포기 — 한 단계 (2/2)", 5, "② 코드 — run_stage 2/2 헬스 게이트", None),
    ("⑥ OTA 배포기 — 롤백", 5, "② 코드 — rollback", "⑦⑧ 장애 주입·판정·진단 — 정상 동작은 확인됐다. 각 부품을 일부러 죽여 얼마나 잃고 얼마나 빨리 돌아오는지 재는 도구들 (실험 결과는 3부)"),
    ("⑦ 장애 주입", 6, "② 코드 — 유실 SQL", None),
    ("⑦ 장애 4종", 6, "③ 표 — 장애 4종(주입·재는 것·기대)", None),
    ("⑦ 판정", 6, "② 도구 — 판정 · 진단", "3부 검증 — 1·2부에서 '확인 → 장표 N' 으로 미뤄 둔 시험을 단계 순서대로 본다: 표② DDS → 표① 1 ms 루프 → 물리 → 표③ 관제"),
]
GATE_BEFORE_C = [(1, "① 장치 에이전트"), (2, "② 브로커"), (3, "③ 수집기"), (4, "④ TimescaleDB"), (5, "⑥ OTA 배포기"), (6, "⑦ 장애 주입")]
EXTRA_C = [
    ("③ 들머리", DF.collector_flow(), crumb_c(3, "② 그림 — 두 스레드와 1초 묶음"), None),
    ("⑥ 들머리", DF.ota_image(), crumb_c(5, "② 그림 — 나쁜 펌웨어 한 번의 흐름"), None),
]

# 3부 검증 장표: (제목에 들어 있는 글자, crumb, next) — 1·2부에서 꺼내 온 순서대로
VERIFY_NAV = [
    ("단계 2 검증 — 측정기", "3부 검증 · 단계 2 DDS 전달 · 측정기 ping/pong", None),
    ("단계 2 검증 — E04", "3부 검증 · 단계 2 DDS 전달 · E04 판단 사슬", "단계 4 검증 — 전달은 우리 크기에서 손실 0. 다음 미뤄 둔 것: 1 ms 루프의 깨어남 지연(표①) — 측정기 → 백분위수 → 실험 사슬 3장 → 표 → 결론"),
    ("단계 4 검증 — 측정기", "3부 검증 · 단계 4 RT 1 ms 루프 · 측정기 jitter_bench", None),
    ("단계 4 검증 — 백분위수", "3부 검증 · 단계 4 RT 1 ms 루프 · 백분위수", None),
    ("단계 4 검증 — 표① 실험 사슬 (1/3)", "3부 검증 · 단계 4 RT 1 ms 루프 · 실험 사슬 1/3 (WSL)", None),
    ("단계 4 검증 — 표① 실험 사슬 (2/3)", "3부 검증 · 단계 4 RT 1 ms 루프 · 실험 사슬 2/3 (Pi 4)", None),
    ("단계 4 검증 — 표① 실험 사슬 (3/3)", "3부 검증 · 단계 4 RT 1 ms 루프 · 실험 사슬 3/3 (측정기 검증)", None),
    ("단계 4 검증 — 표① Pi 4", "3부 검증 · 단계 4 RT 1 ms 루프 · 표① 핵심 8줄", None),
    ("단계 4 검증의 결론", "3부 검증 · 단계 4 RT 1 ms 루프 · 결론 일반 vs RT", "단계 7 검증 — 루프는 1 ms 안에 항상 깬다(189 us). 다음 미뤄 둔 것: 물리는 싸고(E15), 새 사실을 보여 준다(E16)"),
    ("단계 7 검증", "3부 검증 · 단계 7 로봇이 움직인다 · E15 → E16", "2부 ⑦⑧ 검증 — 로봇 안의 검증은 끝. 다음 미뤄 둔 것: 관제의 '유실 0' 은 진짜였나 (표③ 사슬 3장 + 표)"),
    ("2부 ⑦⑧ 검증 — 표③ 실험 사슬 (1/3)", "3부 검증 · 2부 ⑦⑧ 관제 · 표③ 사슬 1/3 ('0' 이 가짜)", None),
    ("2부 ⑦⑧ 검증 — 표③ 실험 사슬 (2/3)", "3부 검증 · 2부 ⑦⑧ 관제 · 표③ 사슬 2/3 (0, CI 도 0)", None),
    ("2부 ⑦⑧ 검증 — 표③ 실험 사슬 (3/3)", "3부 검증 · 2부 ⑦⑧ 관제 · 표③ 사슬 3/3 (곁가지 넷)", None),
    ("2부 ⑦⑧ 검증 — 표③-2", "3부 검증 · 2부 ⑦⑧ 관제 · 표③-2 · ③-3", "4부 — 길과 검증을 다 봤다. 이 길과 숫자가 공고(Framework S/W)의 주요 업무를 덮나? 무엇을 숫자로 증명했나?"),
]

VERIFY_SECTION = {"kind": "section", "section": SECV, "num": "03", "title": "검증 — 미뤄 둔 시험: 각 단계의 기준을 정말 넘었나",
                  "subtitle": "들머리마다 '확인 → 장표 N' 으로 가리켜 둔 실험들을 단계 순서대로 본다. 기준(마름모)을 못 넘은 곳마다 '왜 못 넘었나'가 다음 실험을 낳았다",
                  "flow": {"from": "1부(로봇을 움직이는 길)와 2부(데이터의 길)의 들머리에 적힌 '결과' 한 줄과 '확인 → 장표 N'",
                           "question": "각 단계의 기준을 정말 넘었나? 그 숫자는 어떻게 나왔고, 못 넘었을 때 무엇을 바꿨나?",
                           "answer": "단계 순서대로 — 표② DDS(단계 2: 측정기 · E04 사슬) → 표① 1 ms 루프(단계 4: 측정기 · 백분위수 · 실험 사슬 E01→E19d 3장 · 표 · 결론) → 물리(단계 7: E15→E16) → 표③ 관제(2부 ⑦⑧: E05→E13 '유실 0' 이 가짜였다 → 53 → 0, CI 에서도 0 · 표③-2·③-3)"},
                  "agenda": ["단계 2 검증 2장 → 단계 4 검증 7장 → 단계 7 검증 1장 → 2부 ⑦⑧ 검증 4장", "그림 약속 그대로: 사각형 = 실험, 마름모 = 기준, 화살표 글 = 실제 값, 진한 상자 = 결론, 붉은 상자 = 실패·원인", "→ 다음: 길과 검증을 다 봤다. 이 길과 숫자가 공고(Framework S/W)의 주요 업무를 덮나? (4부)"]}


def find_from(slides, pos, must, startswith=False):
    for i in range(pos, len(slides)):
        t = slides[i]["title"]
        if (t.startswith(must) if startswith else must in t):
            return i
    return None


def annotate(slides, nav, crumb_fn, gate_before, gates, extras):
    pos = 0
    for must, stage, step, nxt in nav:
        found = find_from(slides, pos, must)
        if found is None:
            sys.exit(f"길잡이 자리 못 찾음: '{must}' (이전 자리 {pos})")
        s = slides[found]
        s["crumb"] = crumb_fn(stage, step) if stage else step
        if nxt:
            s["next"] = nxt
        pos = found + 1
    for i, s in enumerate(slides):
        if s["kind"] != "section" and not s.get("verify") and "crumb" not in s:
            sys.exit(f"crumb 없는 장표: {i} {s['title']}")
    # 들머리 끼우기 — 뒤에서부터
    for stage, prefix in reversed(gate_before):
        idx = find_from(slides, 0, prefix, startswith=True)
        if idx is None:
            sys.exit(f"들머리 자리 못 찾음: {prefix}")
        slides.insert(idx, gates[stage])
    # 그림 한 장 끼우기 — 해당 장표 '뒤'에
    for anchor, extra, crumb, nxt in extras:
        idx = find_from(slides, 0, anchor, startswith=True)
        if idx is None:
            sys.exit(f"그림 자리 못 찾음: {anchor}")
        extra["crumb"] = crumb
        if nxt:
            extra["next"] = nxt
            slides[idx].pop("next", None)       # 그래프 장표가 다음 ▶ 를 이어받는다
        slides.insert(idx + 1, extra)
    return slides


def split_verify(slides):
    main, ver = [], []
    for s in slides:
        (ver if s.get("verify") else main).append(s)
    return main, ver


def annotate_verify(ver):
    pos = 0
    for must, crumb, nxt in VERIFY_NAV:
        found = find_from(ver, pos, must)
        if found is None:
            sys.exit(f"검증 길잡이 자리 못 찾음: '{must}'")
        s = ver[found]
        s["section"] = SECV
        s["crumb"] = crumb
        s.pop("next", None)
        if nxt:
            s["next"] = nxt
        pos = found + 1
    for s in ver:
        if "crumb" not in s:
            sys.exit(f"검증 장표에 crumb 없음: {s['title']}")
    return ver


def part_of(section):
    # "3. 검증 — …" → 3, "끝" → 8
    if section.startswith("끝"):
        return 8
    try:
        return int(section.split(".")[0])
    except ValueError:
        return 0


def fill_placeholders(slides):
    """{{range:N}} → 'a–b', {{first:글자}} → 그 글자로 시작하는 첫 장표 번호 (문자열이 든 모든 자리에서)"""
    first, last = {}, {}
    for i, s in enumerate(slides, start=1):
        p = part_of(s["section"])
        if p:
            first.setdefault(p, i)
            last[p] = i
    titles = [s["title"] for s in slides]

    def first_slide(prefix):
        for i, t in enumerate(titles, start=1):
            if t.startswith(prefix):
                return i
        sys.exit(f"{{{{first:{prefix}}}}} 에 맞는 장표가 없다")

    def fix(v):
        if isinstance(v, str):
            while "{{range:" in v:
                a = v.index("{{range:"); b = v.index("}}", a)
                p = int(v[a + 8:b]); v = v[:a] + f"{first[p]}–{last[p]}" + v[b + 2:]
            while "{{first:" in v:
                a = v.index("{{first:"); b = v.index("}}", a)
                v = v[:a] + str(first_slide(v[a + 8:b])) + v[b + 2:]
            return v
        if isinstance(v, list):
            return [fix(x) for x in v]
        if isinstance(v, dict):
            return {k: fix(x) for k, x in v.items()}
        return v
    return [fix(s) for s in slides], first, last


def main():
    cover, start, where = content_a.cover(), content_a.start(), content_a.where()
    b = annotate(content_b.slides(), NAV_B, crumb_b, GATE_BEFORE_B, GATES_B, EXTRA_B)
    c = annotate(content_c.slides(), NAV_C, crumb_c, GATE_BEFORE_C, GATES_C, EXTRA_C)
    b_main, b_ver = split_verify(b)
    c_main, c_ver = split_verify(c)
    ver = annotate_verify(b_ver + c_ver)
    d = content_d.slides()
    slides = cover + b_main + c_main + [VERIFY_SECTION] + ver + start + where + d
    slides, first, last = fill_placeholders(slides)
    with open("slides.json", "w", encoding="utf-8") as f:
        json.dump(slides, f, ensure_ascii=False, indent=1)
    print(f"slides: {len(slides)}  (표지 {len(cover)}, 1부 {len(b_main)}, 2부 {len(c_main)}, 3부 {1 + len(ver)}, 4부 {len(start)}, 5부 {len(where)}, 6·7부·끝 {len(d)})")
    for p in sorted(first):
        print(f"  부 {p}: {first[p]}–{last[p]}")


if __name__ == "__main__":
    main()
