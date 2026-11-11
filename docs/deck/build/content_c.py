# 장표 내용 C — 2부 데이터의 길(관제, top → down). 표③ 실험 사슬·표는 "verify": True → make_slides.py 가 3부 검증으로 옮긴다
from cu import code, ref

SEC4 = "2. 데이터의 길 — 장치에서 대시보드까지"
AG = "fleet/agent/device_agent.py"
VF = "fleet/agent/virtual_fleet.py"
COL = "fleet/collector/collector.py"
SI = "fleet/common/single_instance.py"
RO = "fleet/ota/rollout.py"
INJ = "fleet/chaos/inject.py"
AS = "fleet/chaos/assert_results.py"
DG = "fleet/tools/diag.py"
MQC = "fleet/mosquitto/mosquitto.conf"


def slides():
    s = []
    s.append({"kind": "section", "section": SEC4, "num": "02", "title": "데이터의 길 — 장치에서 대시보드까지 (위에서 아래로)",
              "subtitle": "로봇(또는 가상 장치 50대)의 숫자가 MQTT → 수집기 → TimescaleDB → Grafana 로 가고, 서버가 OTA 와 장애를 다루는 길. 목표는 '잃지 않는 것, 잃었으면 세는 것'",
              "flow": {"from": "로봇의 상태가 1 Hz 요약으로 다리를 건너 관제에 올라간다 (1부 단계 10). 가상 장치 50대도 같은 길",
                       "question": "수십 대의 숫자를 잃지 않고 서버까지 가져오고, 장애와 업데이트를 견디나?",
                       "answer": "8단계(6묶음)를 위에서 아래로 — 에이전트 → 브로커 → 수집기 → DB·Grafana → OTA → 장애 주입·판정·진단, 묶음마다 핵심 코드(파일:줄). 기준: 유실 0 · 복구 수초 · 나쁜 펌웨어는 5% 에서 멈춤. 실험(표③, '유실 0' 이 처음엔 가짜였던 이야기)은 3부로"},
              "agenda": ["① 장치 에이전트 → ② 브로커 → ③ 수집기 → ④⑤ DB·Grafana → ⑥ OTA 배포기 → ⑦⑧ 장애 주입·판정·진단",
                         "묶음마다 들머리(들어온 것 → 문제 → 기준 → 확인 → 결과 → 판단) → 핵심 코드. 실험(E05 → E13, 표③)은 번호만 적고 3부로",
                         "→ 다음: 1·2부에서 '확인 → 장표 N' 으로 미뤄 둔 시험들을 단계 순서대로 본다 (3부 검증)"]})
    s.append({"kind": "path", "section": SEC4, "title": "한 장 그림 — 데이터의 길 8단계", "perRow": 4,
              "stages": [
                  {"head": "장치 에이전트", "text": "1 Hz tick: seq·ts_ns·fw·state·센서값 JSON. 끊기면 버퍼(3600개), 붙으면 QoS 1 재전송. 유언(offline)·보관(online)", "ref": "fleet/agent/device_agent.py", "color": "accent5"},
                  {"head": "브로커 Mosquitto", "text": "토픽 fleet/<id>/… 중계. persistence true, 지속 세션 큐 20,000, keepalive 1.5배 안에 못 들으면 유언 발행", "ref": "fleet/mosquitto/mosquitto.conf", "color": "accent5"},
                  {"head": "수집기", "text": "구독 → pending → 1초마다 묶음(COPY) → backlog(DB 죽음) → 통계 한 줄. 곱게 종료, 단일 인스턴스 잠금", "ref": "fleet/collector/collector.py", "color": "accent1"},
                  {"head": "TimescaleDB", "text": "telemetry·events·collector_stats 하이퍼테이블, devices, ota_rollouts. 마이그레이션 001~003", "ref": "fleet/db/init.sql · migrate.py", "color": "accent1"},
                  {"head": "Grafana", "text": "Fleet Overview 14 패널 — 온라인·초당 메시지·전달 지연·backlog·펌웨어 버전·이벤트. JSON 은 생성기로", "ref": "fleet/grafana/make_dashboard.py", "color": "accent2"},
                  {"head": "OTA 배포기", "text": "살아 있는 장치 찾기 → 5%·50%·100% 단계 → 적용 대기 → 헬스 게이트 → 롤백", "ref": "fleet/ota/rollout.py", "color": "accent6"},
                  {"head": "장애 주입·판정", "text": "broker·db·collector 를 죽였다 살리고 감지·복구·유실을 DB 로 잰다. 판정 규칙으로 CI 가 통과/실패", "ref": "fleet/chaos/inject.py · assert_results.py", "color": "accent4"},
                  {"head": "진단", "text": "이상한 숫자를 들여다본다: 오프라인 군집(A) · 지연 튐(B) · seq 틈(C)", "ref": "fleet/tools/diag.py", "color": "accent3"},
              ],
              "bottom": "1부의 단계 ⑩(다리)이 여기 1번 상자로 들어온다. 전부 파이썬이고 실시간 요구가 없다 — 대신 '잃지 않는 것'과 '잃었으면 세는 것'이 요구다"})
    s.append({"kind": "image", "section": SEC4, "title": "같은 길을 토픽·설정과 함께 — fleet 데이터 흐름", "image": "img/fleet_flow.png",
              "caption": "토픽 4종: telemetry(측정값) · status(online/offline, 보관) · cmd(서버 → 장치) · cmd_reply. 장애 주입은 컨테이너를 멈추고(stop) 살리며(start) DB 로 결과를 잰다"})
    # 장치 에이전트
    s.append({"kind": "code", "section": SEC4, "title": "① 장치 에이전트 — 1 Hz tick 과 '끊기면 모았다가, 붙으면 보낸다'", "file": ref(AG, 119, 147),
              "code": code(AG, 119, 147, dedent=4), "codeSize": 10, "pointsSize": 11,
              "points": ["seq(일련번호)가 유실 측정의 열쇠: 빠진 번호 = 잃은 메시지", "ts_ns 는 벽시계(UTC) — 수집기가 '도착 − 측정' 으로 전달 지연을 계산한다. 같은 PC 면 시계가 하나, 다른 기계면 두 시계의 차이가 섞인다 → 왕복으로 확인(7부 덧붙임 장표 {{first:덧붙임 (11/11) — 서버까지}})", "kind · ota_stage · ota_error 는 11/10 에 더한 칸: 배포기가 실물(kind=real)을 마지막 단계로 보내고, 설치가 어디서 왜 멈췄는지를 텔레메트리로 안다", "붙어 있으면 바로 publish(qos=telemetry_qos), 끊겼으면 버퍼(최대 3,600개 = 1 Hz 로 1시간)", "버퍼가 차면 가장 오래된 것을 버린다 — 메모리 보호"]})
    s.append({"kind": "code", "section": SEC4, "title": "① 장치 에이전트 — 재접속하면 버퍼를 QoS 1 로 비운다, 비정상 종료는 유언이 말한다", "file": ref(AG, 149, 167) + " + 유언·보안 설정(:82-87)",
              "code": code(AG, 82, 87, dedent=8) + [""] + code(AG, 149, 167, dedent=4), "codeSize": 10, "pointsSize": 11,
              "points": ["on_connect: status online(보관) 발행 → cmd 구독 → flush_buffer", "flush_buffer: 모아 둔 것을 QoS 1(브로커가 받았다는 확인까지)로 전부 재전송, flushed_total 로 센다", "유언(LWT): 비정상 종료 시 브로커가 대신 status offline 을 발행(보관). 정상 종료는 자기가 offline 을 남기고 끊는다", "apply_security(11/10): 환경변수에 TLS 인증서·계정이 있으면 건다 — 개발(같은 PC, 평문 1883)과 운영(클라우드, 8883 TLS + 비밀번호)이 같은 코드(fleet/common/mqtt_conn.py)", "11/03 D2 실측: 브로커 10초 중단 → 버퍼 654 = 재전송 654 (E05)"]})
    s.append({"kind": "image", "section": SEC4, "title": "① 장치 에이전트 — 한 주기의 흐름 (보내거나, 모으거나, 붙으면 비우거나)", "image": "img/agent_flow_lr.png",
              "bullets": ["3600개 상한, 넘치면 오래된 것부터 버림", "재접속은 paho 가 1~5초 간격으로 자동", "같은 클래스가 가상 장치 50대와 RT 노드 다리에 쓰인다 — 다른 것은 metrics_source 뿐", "OTA 명령(ota/ota_rollback)은 on_message 에서, 별도 스레드로 — 명령에 url 이 없으면 흉내(apply_ota: apply_s 동안 updating → fw 교체 → ok 또는 fault), 있으면 진짜 설치(apply_ota_artifact, 7부 덧붙임)"]})
    s.append({"kind": "bullets", "section": SEC4, "title": "① 가상 장치 50대 (virtual_fleet.py) — 실물 없이 서버에 부하를 주고 흐름을 검증한다",
              "bullets": [
                  "장치마다 DeviceAgent 하나(스레드 2개: 주기 스레드 + paho 네트워크 스레드). 숫자는 난수 걸음(random walk): cpu 20~60%, temp 40~55 °C, mem, rssi — 시드 고정이라 재현된다",
                  "옵션: --count 50 --rate 1 --telemetry-qos {0,1} --keepalive 10 --keepalive-jitter N --prefix · --slot-root(11/10: 장치마다 A/B 슬롯 폴더 — 진짜 설치용)",
                  "keepalive jitter 가 왜 있나(E10): 50대가 동시에 접속하면 keepalive 박자가 맞아 10초마다 PINGREQ 가 몰리고 전달 지연 p95 가 10 ms 로 튄다. 30초로 늘리면 사라지지만 끊김 감지가 45초로 늦어진다 → 장치마다 0~N초를 더해 박자를 흩뜨린다",
                  "같은 --prefix 로는 한 벌만: fleet/logs/fleet_<prefix>.lock (flock). 두 벌이 뜨면 같은 client_id 를 서로 밀어내 2초마다 재접속(11/04 reconnects 1,675 사고)",
                  "Ctrl+C 면 전부 정상 종료(offline 발행)",
              ],
              "callout": {"title": "단일 인스턴스 잠금 (fleet/common/single_instance.py)", "text": "acquire(name): fleet/logs/<name>.lock 을 열고 flock(LOCK_EX|LOCK_NB) — 이미 잠겨 있으면 None.\nother_pid(name): 잠금 파일에 적힌 pid 를 읽어 '누가 잡고 있나'를 안내.\n프로세스가 죽으면 커널이 잠금을 자동 해제한다.\n수집기('collector')와 가상 장치('fleet_<prefix>')가 공용으로 쓴다"}})
    # 브로커
    s.append({"kind": "code", "section": SEC4, "title": "② 브로커 Mosquitto — 설정 세 줄이 유실 0 을 만든다", "file": MQC,
              "code": code(MQC, 1, 20), "codeSize": 10,
              "points": ["persistence true: 세션·보관 메시지를 디스크에(볼륨 fleet_mqtt_data). false 였을 때 브로커 재시작 뒤 수집기의 지속 세션이 사라져 4~5대 × 12개 유실(E07 원인 ①)", "max_queued_messages 20000: 수집기가 없는 동안 브로커가 대신 들고 있는 QoS 1 메시지 상한. 기본 1000 은 300대 × 1 Hz × 10초 = 3,000 을 못 담는다. 넘으면 새 메시지를 버린다(E12: 2,450개)", "인증 없음은 개발용(같은 PC). 운영 설정은 따로 있다(11/10): mosquitto-prod.conf — 밖으로는 8883 TLS + 비밀번호만, 1883 은 컨테이너 안에서만 (7부 덧붙임 장표 {{first:덧붙임 (11/10~11) — 운영 층}})", "keepalive 는 장치 쪽 설정(기본 10초). 1.5배 안에 PINGREQ 가 없으면 브로커가 끊고 유언을 발행한다"]})
    # 수집기
    s.append({"kind": "code", "section": SEC4, "title": "③ 수집기 — 받는 쪽: on_message 는 파싱해서 pending 에 넣기만 한다", "file": ref(COL, 153, 181),
              "code": code(COL, 153, 181, dedent=4), "codeSize": 10, "pointsSize": 11,
              "points": ["paho 콜백 스레드에서 돈다 — DB 를 만지지 않는다(1초 묶음은 메인 스레드)", "status 메시지 중 retain=1(보관 값)은 '지금 상태'이지 사건이 아니다 → events 에 넣지 않는다 (persistence true 뒤 오프라인 이벤트가 두 배로 세졌던 사고)", "parse_telemetry 가 ts_ns 와 도착 시각으로 전달 지연(ms)을 계산", "last_seen(단조 시계)으로 '온라인'(5초 안에 본 장치)을 세고, last_seen_wall(벽시계)은 devices 표에 '그 장치의 마지막 메시지 도착 시각'으로 쓴다 — 11/10 전에는 본 적 있는 장치 전부를 매초 지금 시각으로 덮어써, 꺼진 장치가 온라인으로 보였다(실제 1대, 표시 4대)"]})
    s.append({"kind": "code", "section": SEC4, "title": "③ 수집기 — 1초마다 (1/2): 묶음을 backlog 끝에 붙이고, 상한을 넘으면 오래된 것부터 버린다", "file": ref(COL, 207, 217) + " · " + ref(COL, 234, 240),
              "code": code(COL, 207, 217, dedent=4) + [""] + code(COL, 234, 240, dedent=4), "codeSize": 11,
              "points": ["flush_once 는 1초마다 메인 스레드가 부른다: take_batch 로 pending 을 통째로 꺼내(락 한 번) backlog 끝에 붙이고, drain_backlog 로 DB 에 민다", "왜 1초 묶음 + COPY: 300대 × 1 Hz 를 행마다 INSERT 하면 DB 왕복 300번/초 → 묶으면 1번/초. 대신 DB 에 보이기까지 최대 1초(표③ 비고에 적음)", "enforce_backlog_limit: 상한 MAX_BACKLOG_ROWS(200,000행 = 50대 × 1 Hz × 66분)를 넘으면 가장 오래된 묶음부터 버리고 backlog_dropped 로 센다 — 메모리를 지키되 '잃었다'를 숨기지 않는다(DECISIONS D4)", "받는 쪽(on_message)은 여기를 모른다 — pending 에 넣기만"]})
    s.append({"kind": "code", "section": SEC4, "title": "③ 수집기 — 1초마다 (2/2): backlog 를 오래된 것부터 DB 에, 하나라도 실패하면 거기서 멈추고 다음 초에 (drain_backlog)", "file": ref(COL, 241, 255),
              "code": code(COL, 241, 255, dedent=4), "codeSize": 11,
              "points": ["backlog 의 맨 앞(가장 오래된 묶음)부터 write_db(COPY). 성공하면 pop, 실패하면 db_errors +1 하고 return — 다음 초에 같은 묶음부터 다시", "그래서 순서가 지켜지고(오래된 것 먼저), DB 가 죽은 동안의 묶음은 메모리에 남는다(11/04 db 장애: 10초 뒤 570행이 뒤늦게 적재, 유실 0 / 1341)", "예외를 잡으면 db_errors +1, DB 연결을 끊어 두고(drop_db_connection → 다음 초에 다시 붙는다), 첫 번째와 10번째마다만 로그 — 로그 폭주 방지", "통계 한 줄(write_stats): msgs/s · insert_ms · 전달 지연 p50/p95/max · online · backlog_rows · db_errors → collector_stats 표 + Grafana 'backlog/DB 오류' 패널"]})
    s.append({"kind": "chain", "section": SEC4, "title": "③ 수집기 — 종료할 때 마지막 1초를 잃지 않는 길 (11/04 실측에서 고침)", "perRow": 4,
              "items": [
                  {"text": "SIGTERM / Ctrl+C 도착"},
                  {"text": "request_stop(): STOP 플래그만 세운다\n(핸들러 안에서 DB·소켓 금지)"},
                  {"text": "메인 루프: while not STOP → 0.2초씩 자며 매초 flush_once"},
                  {"text": "루프 탈출 → shutdown(c)"},
                  {"text": "loop_stop → disconnect\n(지속 세션이면 그 뒤 메시지는 브로커가 보관)"},
                  {"text": "마지막 flush_once: pending + backlog 전부 적재"},
                  {"kind": "q", "text": "backlog 가 남았나?", "answer": "0 이면 '마지막 n행까지 적재 완료' / 남으면 'DB 가 죽어 있음' 안내"},
                  {"kind": "end", "text": "종료 코드 0\n(11/04 전: 즉시 종료로 장치당 1행 = 50행 유실 → E07 원인 ②)"},
              ],
              "bottom": "코드: collector.py request_stop(325) · shutdown(343-353) · main(356-394). 11/05 CI 사고: 잠금 공용화 패치에서 request_stop 이 통째로 지워져 NameError → main() 한 바퀴 스모크 테스트 추가 (test_collector_resilience 8번째)"})
    # DB / Grafana
    s.append({"kind": "two_col", "section": SEC4, "title": "④ TimescaleDB — 표 5개와 마이그레이션, ⑤ Grafana — 14 패널",
              "left": {"head": "DB (fleet/db/init.sql, migrations/001~003)", "bullets": ["telemetry(hypertable): time, device_id, seq, cpu_pct, temp_c, mem_pct, rssi, loop_hz, wake_p99_us, fw_version, state, ingest_latency_ms — 인덱스 (device_id, time DESC)", "events(hypertable): kind(online/offline/fault/ota), device_id, detail", "collector_stats(hypertable): msgs, insert_ms, lat_p50/p95/max, online, backlog_rows, db_errors(003)", "devices: 장치별 마지막 상태 · ota_rollouts(002): 배포 요약 한 줄", "migrate.py --wait N: 번호 붙은 SQL 을 순서대로, TCP 로 진짜 붙어 보며 기다린다(CI 의 TimescaleDB 초기화 경쟁 해결)"]},
              "right": {"head": "Grafana Fleet Overview (make_dashboard.py 가 JSON 생성)", "bullets": ["stat: 온라인 장치(5초) · 초당 메시지 · 전달 지연 p95 · DB 적재 ms · 오프라인 이벤트(10분) · 멈춤·고장 장치", "timeseries: 초당 메시지/온라인 · 전달 지연 p50/p95/max · 장치별 온도 · RT 노드 깨어남 지연 p99 · 수집기 backlog/DB 오류 · 펌웨어 버전별 장치 수", "table: 최근 이벤트(장애 주입·OTA·온/오프라인) · 장치 목록", "JSON 을 손으로 안 만지는 이유: 패널 14개의 SQL 을 코드로 두면 리뷰·수정·CI 검사(파싱)가 된다"]},
              "foot": "하이퍼테이블 = 시간으로 자동 분할되는 PostgreSQL 표(TimescaleDB). 출처: fleet/db/init.sql, fleet/grafana/make_dashboard.py, DECISIONS 11/03 (D2) '대시보드 JSON 은 생성기로'"})
    # OTA
    s.append({"kind": "code", "section": SEC4, "title": "⑥ OTA 배포기 — 한 단계 (1/2): 이번 단계 장치에 보내고, 적용될 때까지 기다린다 (run_stage 앞부분)", "file": ref(RO, 183, 198) + " · wait_apply " + ref(RO, 234, 247),
              "code": code(RO, 183, 198, dedent=4) + [""] + code(RO, 234, 247, dedent=4), "codeSize": 10, "pointsSize": 10.5,
              "points": ["단계 = 누적 퍼센트(5 → 50 → 100). 50대의 5% = ceil(2.5) = 3대 — batch 는 '이번 단계에서 새로 받는 장치들'. 실물(kind=real)은 목록 맨 뒤라 마지막 단계에만 든다", "보내기: fleet/<id>/cmd 에 {cmd: ota, version, apply_s, bad}. 매니페스트가 있으면(진짜 설치, 11/10) url · sha256 · size · arch 를 같이 보내고 장치가 자기 아키텍처 항목을 고른다. 없으면 흉내 경로 — bad=true 면 적용 뒤 state=fault", "적용 대기(wait_apply): 그 장치들의 fw_version 이 새 버전으로 바뀔 때까지 0.2초마다 본다. state=fault + ota_error 인 장치가 하나라도 보이면 그 자리에서 멈춘다 — 설치 실패는 헬스 대기를 기다리지 않고 바로 롤백", "시간(apply_timeout_s) 안에 안 바뀌면 시간 초과 → 롤백. 실패·시간 초과의 사유(ota_error · ota_stage)는 타임라인에 남긴다(run_stage 199-211줄)", "updated 에 '지금까지 새 버전을 받은 모든 장치'를 누적한다 — 다음 장의 헬스 게이트와 롤백이 이 목록을 쓴다"]})
    s.append({"kind": "code", "section": SEC4, "title": "⑥ OTA 배포기 — 한 단계 (2/2): 헬스 게이트 — 지켜본 뒤 하나라도 아프면 전부 되돌린다 (run_stage 뒷부분)", "file": ref(RO, 214, 232),
              "code": code(RO, 214, 232, dedent=4), "codeSize": 11,
              "points": ["health_wait 초 동안 지켜본 뒤 '지금까지 새 버전을 받은 모든 장치(updated)'의 state 스냅샷을 본다 — 이번 단계 3대만이 아니라 누적 전부", "ok 가 아닌 장치 수 > max_fail(기본 0) 이면 rollback() → 이 단계에서 멈춘다(장치가 알려 준 사유 ota_error 가 있으면 같이 남긴다). 50% · 100% 단계는 시작도 안 한다(47대는 명령을 받은 적도 없다)", "판단 기준(헬스 게이트·허용 수)이 서버 코드 한 곳에 있다 — 장치는 적용/복원만(DECISIONS 11/03 D3)", "통과하면 True → 다음 단계(50%)로. 세 단계 다 통과 = success"]})
    s.append({"kind": "code", "section": SEC4, "title": "⑥ OTA 배포기 — 롤백: 새 버전을 받은 모든 장치를 이전 버전으로, 걸린 시간을 잰다", "file": ref(RO, 249, 262),
              "code": code(RO, 249, 262, dedent=4), "pointsSize": 11,
              "points": ["ota_rollback 명령 → 장치가 하는 일은 셋 중 하나(device_agent.py on_message): 직전 설치를 거부한 장치는 상태만 ok 로(current 가 안 바뀌었으니 되돌릴 것이 없다) / 설치에 성공한 장치는 current 를 이전 슬롯으로 / 흉내 경로면 prev_fw_version 으로", "전부 돌아올 때까지(30초 제한) 기다려 rollback_s 에 기록 — 11/04: 1.0초, 11/05 리허설: 0.8초", "결과 JSON(ota_<version>.json) + DB events(kind='ota') + ota_rollouts 요약 → 표③-3", "나쁜 펌웨어가 닿은 장치 3/50 — 나머지 47대는 명령을 받은 적도 없다(카나리의 뜻)"]})
    # 장애 주입
    s.append({"kind": "code", "section": SEC4, "title": "⑦ 장애 주입 — 유실을 세는 SQL: 기준점은 '장애 직전의 마지막 seq' (E07 에서 고침)", "file": ref(INJ, 118, 134),
              "code": code(INJ, 118, 134, max_len=150), "codeSize": 10,
              "points": ["장치별로 (창 안 마지막 seq − 창 직전 마지막 seq) = 만들었어야 할 메시지 수, 실제 받은 행 수와의 차 = 유실", "왜 창 안 min(seq) 가 아닌가: 장애 시작 직후 잃은 메시지는 창의 앞 가장자리라 min(seq) 뒤로 숨는다 → 유실 0 으로 보인다(11/04 맹점, 2대 × 12개)", "직전 30초에 데이터가 없는 장치는 min(seq)−1 로", "결과: expected · received · lost · devices → JSON → make_table3 → 표③-2"]})
    s.append({"kind": "table", "section": SEC4, "title": "⑦ 장애 4종 — 무엇을 어떻게 죽이고, 무엇을 재고, 무엇을 기대하나", "fontSize": 11,
              "colW": [1.6, 3.2, 3.6, 3.9],
              "rows": [["장애", "주입 방법", "재는 것", "기대 · 실측(WSL 50대 1 Hz)"],
                       ["broker", "docker compose stop mqtt → N초 → start", "감지(msgs/s=0), 첫 메시지·전 장치 복귀, 유실(seq)", "유실 ≤ 장치 수 → 실측 0 / 1400, 복귀 2.9초, 재전송 폭주 431 msgs/s"],
                       ["db", "docker compose stop db → N초 → start", "DB 프로브 응답, backlog 0 까지, 뒤늦게 적재된 행", "유실 0 → 실측 0 / 1341, 1.4초, 뒤늦게 570행"],
                       ["collector", "호스트 프로세스 SIGTERM → N초 → 같은 명령·같은 venv 로 재시작", "첫 메시지·전 장치, 유실", "QoS 1 지속 세션 0 / 1311 · QoS 0 508 / 1312 (예측 500)"],
                       ["bad_firmware", "rollout.py --bad (5→50→100%)", "닿은 장치 수, 롤백 시간", "3/50, 1.0초"]],
              "note": "재시작 함정(11/04): /proc/<pid>/exe 로 다시 띄우니 venv 를 잃고 바로 죽음 → /proc/<pid>/environ 의 VIRTUAL_ENV·PATH 로 같은 환경. 출처: inject.py HostCollector(253-345), docs/measurements/table3.md ③-2"})
    s.append({"kind": "bullets", "section": SEC4, "title": "⑦ 판정(assert_results.py) 과 ⑧ 진단(diag.py) — 숫자를 통과/실패와 '왜'로 바꾸는 도구",
              "bullets": [
                  {"text": "판정 규칙 (CI 2단계와 integration.sh 의 마지막 단계, 종료 코드 0 = 전부 통과)", "bold": True},
                  {"text": "broker: 유실 ≤ 장치 수(죽는 순간 소켓에 실린 1개/장치는 QoS 0 에서 잃을 수 있다), 전 장치 복귀 시간 있음 · db: 유실 0, backlog 0 복귀 시간 있음", "sub": True},
                  {"text": "collector: label 에 qos1 이면 유실 0 / qos0 이면 유실 > 0 이어야 정상(보호가 없음을 보여 주는 실험) · bad_firmware: success=false, 닿은 장치 = ceil(5%), 롤백 시간 있음 · ota: success=true", "sub": True},
                  {"text": "진단 세 절 — 실측에서 나온 '이상한 것'을 숫자로", "bold": True},
                  {"text": "A 오프라인 이벤트: 첫 이벤트 기준 0.5초 안에 몰린 offline(3개 이상) = 브로커 종료 시 일괄 유언. 50대 중 20개만 찍힌 이유는 소켓을 닫기 전까지 쓴 만큼(E09)", "sub": True},
                  {"text": "B 지연 튐: p95 가 중앙값의 3배를 넘는 초, 단 msgs/s 가 3배 이상인 '홍수'(복구 폭주) 제외 → 간격의 중앙값이 10.0초면 keepalive 박자(E10)", "sub": True},
                  {"text": "C seq 틈: 연속 행에서 seq 가 1 넘게 뛰면 유실, seq 는 연속인데 3초 넘게 벌어지면 '장치 멈춤'(유실 아님). 표③ 유실 계산이 가장자리에서 놓칠 수 있는 것을 여기서 잡는다", "sub": True},
                  "군집 함정(11/04): '이전 이벤트 기준'으로 이어 붙이면 1초마다 오는 이벤트가 209개짜리 거대 군집으로 뭉친다 → '첫 이벤트 기준' 0.5초",
                  {"text": "이 도구들로 한 실험(표③ 사슬 E05 → E13: '유실 0' 이 가짜였다 → 53 → 원인 셋 → 0, CI 에서도 0)과 표③-2·③-3 은 3부 장표 {{first:2부 ⑦⑧ 검증 — 표③ 실험 사슬 (1/3)}}~{{first:2부 ⑦⑧ 검증 — 표③-2}}", "bold": True},
              ],
              "callout": {"title": "소스", "text": "fleet/chaos/assert_results.py (94줄): check · assert_fault · assert_ota(11/10: 산출물 규칙 — 자가 점검이 거부했나 · sha256 이 결과에 남았나)\nfleet/tools/diag.py (316줄): find_cluster_groups(82) · classify_offline_events(109) · section_latency_blips(160) · section_seq_gaps(221)\n실행: python3 fleet/tools/diag.py --minutes 15"}})
    # ---- 표③ 실험 사슬 ----
    s.append({"kind": "chain", "verify": True, "section": SEC4, "title": "2부 ⑦⑧ 검증 — 표③ 실험 사슬 (1/3) — E05 → E06 → E07: '유실 0' 이 다른 증거와 안 맞는다", "perRow": 4,
              "items": [
                  {"text": "E05 가상 50대 1 Hz 기본\n전달 지연 p50 0.9 / p95 1.8 ms"},
                  {"kind": "q", "text": "끊김 동안 데이터가 보존되나?", "answer": "예: 브로커 10초 중단 → 버퍼 654 = 재전송 654 ✓"},
                  {"text": "E06 장애 4종 1차\n복구 2.9 / 1.4 / 1.6 s, 롤백 1.0 s, 유실 '0'"},
                  {"kind": "q", "text": "유실 0 이 다른 증거(diag)와 맞나?", "answer": "아니오: 두 장치에 12초 공백인데 0"},
                  {"text": "E07 유실 기준점 수정\n창 안 min(seq) → 장애 직전 마지막 seq"},
                  {"kind": "q", "text": "다시 재면 0 인가?", "answer": "아니오: 53 / 1434"},
                  {"kind": "fail", "text": "원인 셋: ① 브로커 재시작 경쟁(persistence false, 4~5대 × 12)\n② 수집기 종료 순간 장치당 1개 ③ 큐 상한"},
                  {"kind": "end", "text": "→ E08 고치고 재측정"},
              ],
              "bottom": "측정이 틀리면 '0' 은 가장 위험한 숫자다. 출처: docs/experiments/E05~E07.md, docs/LOG.md 11/04 'D5 실측 1차·2차'"})
    s.append({"kind": "chain", "verify": True, "section": SEC4, "title": "2부 ⑦⑧ 검증 — 표③ 실험 사슬 (2/3) — E08 → E13: 고치자 0, 다른 환경에서도 0", "perRow": 4,
              "items": [
                  {"text": "E08 persistence true + 곱게 종료 뒤 재측정"},
                  {"kind": "q", "text": "유실 0? diag C 틈 없음?", "answer": "예: broker 0 / 1400, collector(QoS 1) 0 / 1311 ✓"},
                  {"text": "같은 실행에서 발견 2건:\n수집기 두 개(client_id 충돌) → flock\n보관 유언 재수신 → events 제외"},
                  {"text": "E13 CI 러너(ubuntu-24.04)\n10대 2 Hz, 진짜 컨테이너"},
                  {"kind": "q", "text": "환경이 달라도 같은 모양?", "answer": "예: 0/318 · 0/286 · 0/280, 롤백 0.4 s ✓"},
                  {"kind": "end", "text": "표③ 통과 — 환경이 아니라 설계가 만든 숫자\n매 push 마다 다시 증명"},
              ],
              "bottom": "CI 1차는 실패했었다: TimescaleDB 첫 기동의 임시 서버에 pg_isready 가 속음 → migrate.py --wait 가 TCP 로 진짜 붙어 보며 기다리게 고침. 출처: docs/experiments/E08.md·E13.md"})
    s.append({"kind": "chain", "verify": True, "section": SEC4, "title": "2부 ⑦⑧ 검증 — 표③ 실험 사슬 (3/3) — 곁가지 E09 · E10 · E11 · E12: 이상한 숫자 넷의 정체", "perRow": 4,
              "items": [
                  {"kind": "q", "text": "오프라인 이벤트 = 장치 수 50?", "answer": "아니오: 20"},
                  {"text": "E09 → 브로커 종료 시 일괄 유언, 1 ms 안 20개\n= 소켓 닫기 전 쓴 만큼. 장치는 멀쩡 ✓"},
                  {"kind": "q", "text": "전달 지연이 평탄한가?", "answer": "아니오: 10초마다 p95 10 ms 튐"},
                  {"text": "E10 keepalive A/B\n30 s → 0회 / 10 s → 정확히 10.0 s 간격\n→ keepalive-jitter 옵션 ✓"},
                  {"kind": "q", "text": "QoS 1 이 아니었다면?", "answer": "E11: 508 / 1312 유실 (예측 500 = 50대 × 10초)"},
                  {"text": "QoS 0 vs 1 을 표③-2 두 줄로 남김\n'보호 없음'의 숫자"},
                  {"kind": "q", "text": "지속 세션은 무한 보관인가?", "answer": "E12: 아니오 — 7.5분 공백 중 2,450개 버림"},
                  {"kind": "end", "text": "= max_queued_messages 20000\n설계 규칙: 상한 = 허용 중단 × 장치 수 × Hz"},
              ],
              "bottom": "출처: docs/experiments/E09~E12.md, fleet/tools/diag.py, docs/DECISIONS.md 11/04 '브로커 persistence true, 곱게 종료, 수동 ACK 보류' · 'keepalive 기본 10초 유지, jitter 는 옵션'"})
    s.append({"kind": "table", "verify": True, "section": SEC4, "title": "2부 ⑦⑧ 검증 — 표③-2 · ③-3 — 장애 주입과 OTA (WSL2, 가상 50대 1 Hz, 2026-11-04)", "fontSize": 10.5,
              "colW": [1.9, 2.6, 1.0, 1.0, 1.6, 1.3, 1.5, 1.4],
              "rows": [["장애", "주입", "멈춤", "감지", "복구(전 장치/backlog 0)", "유실 행", "보호 없었다면", "비고"],
                       ["broker", "stop mqtt", "10초", "1.3초", "2.9초", "0 / 1400", "500", "폭주 431 msgs/s"],
                       ["db", "stop db", "10초", "0.4초", "1.4초", "0 / 1341", "500", "뒤늦게 570행"],
                       ["collector (qos0)", "SIGTERM + 재시작", "10초", "-", "1.6초", "508 / 1312", "500", "보호 없음"],
                       ["collector (qos1)", "SIGTERM + 재시작", "10초", "-", "1.6초", "0 / 1311", "500", "지속 세션"],
                       ["bad_firmware", "rollout --bad", "-", "-", "롤백 1.0초", "닿은 장치 3/50", "50대", "5% 헬스 게이트"],
                       ["CI 러너 (10대 2 Hz)", "같은 4종, 5초", "5초", "-", "3.2 / 1.2 / 1.5초", "0/318 · 0/286 · 0/280", "-", "롤백 0.4초"]],
              "note": "'보호 없었다면' = 초당 메시지 × 멈춘 시간(50 × 10). 전달 지연 p50/p95 ≈ 1 / 2 ms(③-1). 출처: docs/measurements/table3.md, table3_ci.md"})
    return s
