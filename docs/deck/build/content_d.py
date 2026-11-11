# 장표 내용 D — 6부 믿을 수 있나(측정·테스트·CI), 7부 왜·사고·방식(결정·사고·일정·AI·남은 일·용어), 끝
# 순서도 논리: 1~5부의 숫자 → "어떻게 믿나?"(6부) → "왜 이렇게, 무엇이 깨졌나, 어떻게 일했나?"(7부) → 끝: 결국 로봇은 이렇게 움직인다
from cu import code, ref

SEC5 = "6. 믿을 수 있나 — 측정·테스트·CI"
SEC6 = "7. 왜·사고·방식 — 결정·사고·일정·AI·용어"
SEC7 = "끝"
LT = "scripts/lib_thermal.sh"
LS = "scripts/lib_stress.sh"
JR = "scripts/jitter_run.sh"
MT1 = "scripts/make_table1.py"
TCR = "fleet/tests/test_collector_resilience.py"
OA = "fleet/agent/ota_apply.py"


def slides():
    s = []
    # ---------------- 5 ----------------
    s.append({"kind": "section", "section": SEC5, "num": "06", "title": "믿을 수 있나 — 측정 · 테스트 · CI",
              "subtitle": "숫자를 만드는 스크립트는 조건(커널·부하·온도)을 같이 적고, 테스트와 CI 러너는 push 마다 다시 증명한다",
              "flow": {"from": "로봇을 움직이는 길(1부)·데이터의 길(2부)의 숫자 — 표① 189 us, 표② 손실 0, 표③ 유실 0 / 롤백 1.0초, 물리 0.9% — 와 그 검증(3부), 공고 표(4부), 환경(5부)",
                       "question": "이 숫자들을 어떻게 믿나 — 누가, 무엇으로, 언제 다시 재나?",
                       "answer": "측정 스크립트 5개가 조건(커널·부하 크기·온도·스로틀)을 결과 옆에 적는다 · 테스트 31건(C++ 5 · Python 26)과 통합 스크립트 · CI 3잡이 매 push 마다 1 kHz 루프·물리·장애 3종·롤백·진짜 설치를 다시 돌린다 — 그리고 실제로 세 번 나를 잡았다"},
              "agenda": ["측정: 표① 한 줄이 만들어지는 길(스크립트 5개) · 온도·부하 함수", "테스트: 목록 31건 · 가짜 브로커·DB · 통합 스크립트", "CI: 3잡 · 결과를 보고 무엇을 판단하나 · Jenkins 대응표 (태그 때 도는 릴리스 워크플로는 7부 덧붙임)", "→ 다음 질문: 왜 이렇게 만들었고(버린 대안), 무엇이 깨졌고, 어떻게 일했나? (7부)"]})
    s.append({"kind": "process", "section": SEC5, "title": "표① 한 줄이 만들어지는 길 — 스크립트 다섯 개 (조건을 결과 옆에 적는다)", "crumb": "6부 믿을 수 있나 · 측정 스크립트 5개",
              "steps": [
                  {"head": "jitter_run.sh", "lines": ["<label> <초> [stress] [cpu]", "온도 읽기 → (부하 시작) → jitter_bench → .meta(커널·RT·부하·vm·prio·work·온도 전후·스로틀)", "환경 변수: JITTER_PRIO · JITTER_WORK_US · STRESS_VM_BYTES(256M)"]},
                  {"head": "cyclictest_run.sh", "lines": ["<label> <초> [stress]", "cyclictest -m -S -p 90 -i 1000 -h 1000 -q -D", ".meta 에 같은 항목(vm 512M)", "CPU 마다 스레드 → 가장 나쁜 CPU 값을 표에"]},
                  {"head": "lib_thermal.sh", "lines": ["read_temp_mc: /sys/class/thermal/…/temp (밀리도)", "read_throttled: …/get_throttled (0 = 깨끗)", "thermal_meta_lines · thermal_summary", "없는 환경(WSL·러너)이면 na"]},
                  {"head": "lib_stress.sh", "lines": ["start_stress <초> <vm>: stress-ng --cpu N --io 2 --vm 1 --vm-bytes", "stop_stress: timeout 까지 기다림", "11/05 교훈: 부하 정의는 한 곳, 쓴 값은 .meta 에"]},
                  {"head": "make_table1.py", "lines": ["cyclictest 히스토그램 → p99/p99.9/max(최악 CPU)", "jitter JSON → 그대로", ".meta → 비고에 '온도 a→b °C, 스로틀 0' / '⚠ 스로틀'", "→ docs/measurements/table1_pi4.md"]},
              ],
              "foot": "전부 Pi 에서 sudo 로 돈다(RT 우선순위). 결과는 scp 로 WSL 에 가져와 커밋 — Pi 에는 GitHub 로그인이 없다. 출처: scripts/, docs/SETUP_RT_MEASURE.md"})
    s.append({"kind": "code", "section": SEC5, "title": "lib_thermal.sh — 온도와 스로틀 플래그를 읽어 결과 옆에 적는다", "file": ref(LT, 17, 33), "crumb": "6부 믿을 수 있나 · 측정 — 온도·스로틀 함수",
              "code": code(LT, 17, 33), "codeSize": 11.5,
              "points": ["Pi 4 는 80 °C 부터 클럭을 내린다(스로틀). 그 상태의 지연은 '커널 때문'인지 '클럭 때문'인지 가를 수 없다 → 측정마다 온도 전후와 플래그를 .meta 에", "read_temp_mc: /sys/class/thermal/thermal_zone0/temp 는 밀리도(m°C) — 51608 = 51.6 °C. 없으면 na(WSL·러너)", "read_throttled: /sys/devices/platform/soc/soc:firmware/get_throttled 비트 — 0x4 지금 스로틀, 0x8 지금 온도 제한, 0x40000/0x80000 이력. 0 이어야 표에 올린다", "11/04 실측: 부하 75초에 45 → 75 °C(방열판 없음) → 부하 측정은 120초 상한(DECISIONS 11/04)", "make_table1.py 가 이 값을 비고 칸에 '온도 a→b °C, 스로틀 0' 으로 쓴다"]})
    s.append({"kind": "code", "section": SEC5, "title": "lib_stress.sh — 부하 정의는 한 곳에: start_stress · stop_stress", "file": ref(LS, 21, 38), "crumb": "6부 믿을 수 있나 · 측정 — 부하 함수",
              "code": code(LS, 21, 38), "codeSize": 11.5,
              "points": ["start_stress <초> <vm>: stress-ng --cpu N(코어 수) --io 2 --vm 1 --vm-bytes <vm> --timeout <초> 를 뒤에서 돌리고 PID 를 STRESS_PID 에 둔다. sleep 3 은 작업자가 다 뜰 때까지(측정 첫 1~2초가 '아직 한가'로 섞이지 않게). stop_stress 는 그 PID 를 wait", "--vm-bytes 가 왜 중요한가: 메모리를 건드리는 부하가 클수록 CPU 간 인터럽트(IPI, TLB 비우기)가 잦아져 격리된 CPU 도 맞는다 → 같은 'stress' 라도 vm 크기가 다르면 다른 실험", "부하를 한 함수로 묶은 이유: E19-d 에서 두 스크립트의 vm 크기(cyclictest_run 512M vs jitter_run 256M)가 달라 도구 비교가 흐려졌다 → 쓴 값은 .meta 의 stress_vm_bytes 에(DECISIONS 11/05)", "stress-ng 가 없으면 바로 실패한다 — 조용히 '부하 없이' 재는 일이 없게"],
              "next": "테스트 — 측정은 '조건을 적는다'로 믿게 했다. 코드 논리는 무엇이 지키나? (테스트 31건, 가짜 → 진짜)"})
    s.append({"kind": "table", "section": SEC5, "title": "테스트 목록 — '테스트 케이스 등록'은 따로 없다, 전부 저장소의 코드이고 CI 가 push 마다 돌린다", "fontSize": 10, "crumb": "6부 믿을 수 있나 · 테스트 목록 31건",
              "colW": [2.0, 3.9, 4.9, 1.5],
              "rows": [["묶음", "파일", "케이스", "CI 잡"],
                       ["C++ 단위 (ctest)", "rt_control/rt_core/test/test_spsc_ring.cpp · test_control_step.cpp · test_state_machine.cpp · jitter_smoke", "4 — 링 버퍼(두 스레드, 역전 없음·드롭 허용) · 제어 단계(최신 명령·워치독·변화량 제한) · 상태 머신(전이·불법 거부) · 1 kHz 2초 드롭 0", "rt_core"],
                       ["C++ MuJoCo", "rt_control/rt_core/test/test_mujoco_backend.cpp", "1 (× 2 모델) — SO-ARM100 1 kHz 2,000주기 · ALLEX 48 자유도 500 Hz 1,000주기(같은 바이너리, 환경변수로 관절·주기): 움직임 + 비용 p99 < 주기의 90% → mujoco_backend_ci.json · _allex_ci.json", "mujoco"],
                       ["Python 단위 (가짜 브로커·DB)", "fleet/tests/test_fleet_logic.py · test_ota_rollout.py · test_collector_resilience.py · test_ota_artifact.py(11/10)", "9 + 3 + 7 + 7 = 26 — 에이전트 버퍼·재전송·유언·OTA · 왕복 측정기 · Nagle 모형 · 종료 신호 / 배포 good·bad·timeout / 수집기 DB 중단·복귀 · backlog 상한 · 지속 세션 · 종료 flush · 옛 스키마 · 꺼진 장치의 last_seen · main() 스모크 / 진짜 설치(가짜 브로커 + 진짜 패키지): 상대 경로 슬롯 · 설치 단위 · 함대 정상 · 깨진 패키지 · 거부 뒤 롤백 · 자율 업데이트 · 아키텍처와 훅", "rt_core"],
                       ["통합 (진짜 컨테이너)", "fleet/tests/integration.sh + fleet/chaos/assert_results.py", "장애 3종 + 나쁜 펌웨어 롤백 + 정상 OTA + 산출물 OTA 2종(4b 진짜 패키지 설치 · 4c 깨진 패키지 거부)의 판정 규칙", "fleet_integration"],
                       ["릴리스 카나리 (태그 때만)", "fleet/tests/release_canary.sh + assert_results.py", "진짜 Mosquitto + 가상 50대: 정상 패키지 5 → 50 → 100 % 설치, 깨진 패키지는 첫 단계 3대에서 거부·롤백 — 통과해야 게시된다", "release 워크플로의 canary"],
                       ["연기(CI 단계, ctest 밖)", "jitter_bench --no-rt 2초 → JSON → make_table1.py · 대시보드 JSON 생성 → 파싱", "2 — '돌아간다'의 증거(지연 수치 아님)", "rt_core"]],
              "note": "결과는 Actions 잡 로그의 'OK: …' / '100% tests passed'. 케이스별 표(JUnit 리포트)는 없다(우선순위 낮음). 세는 법: 테스트 함수의 수 — grep -c '^def test_' fleet/tests/test_*.py → 9 · 3 · 7 · 7 (test_ota_artifact 는 함수 7개 안에 확인 11가지). 출처: docs/ENVIRONMENT.md §5-7"})
    s.append({"kind": "two_col", "section": SEC5, "title": "가짜 브로커·가짜 DB — 컨테이너 없이 몇 초 만에 도는 단위 테스트의 바닥", "crumb": "6부 믿을 수 있나 · 테스트 — 가짜 브로커·DB",
              "left": {"head": "fleet/tests/fake_mqtt.py (218줄)", "bullets": ["install(): paho.mqtt.client.Client 를 가짜 클래스로 바꿔치기 — 수집기·에이전트 코드는 자기가 가짜 위에 있는 줄 모른다", "FakeBroker: 토픽 와일드카드(+, #) 구독, 보관(retained) 메시지, publish 즉시 콜백 전달", "crash() / disconnect_all() / reconnect_all(): 브로커 죽음·재접속을 흉내 → 버퍼·재전송·유언 시험", "QoS 와 clean_session 인자를 기록해 '지속 세션으로 붙었나'를 검사할 수 있다"]},
              "right": {"head": "fleet/tests/fake_psycopg.py (120줄)", "bullets": ["connect/cursor/execute/copy 를 흉내. STORE 딕셔너리에 telemetry 행이 쌓인다", "FAIL 스위치: 'write' 를 켜면 COPY 가 예외 → backlog 경로, 'schema_old' 면 003 미적용 스키마 → check_schema False", "test_collector_resilience: DB 죽음 → backlog 에 남음 → 복귀 → 오래된 것부터 전부, 순서 유지 → 상한 넘기면 가장 오래된 묶음 버림", "11/05 추가: main() 한 바퀴 스모크 — 인자 → 잠금 → 시그널 핸들러 등록 → 루프 0바퀴 → shutdown (request_stop 누락을 잡는다)"]},
              "foot": "가짜 위에서 통과한 것은 '논리가 맞다'이지 '진짜 위에서도 된다'가 아니다 — 그래서 CI 2단계(진짜 컨테이너)가 따로 있다. DECISIONS 11/03 (D4) 'CI 는 2단계: 가짜로 빠르게, 진짜로 한 번'"})
    s.append({"kind": "code", "section": SEC5, "title": "통합 테스트 스크립트 (1/2) — 릴리스 패키지를 만들고, 컨테이너를 띄워 DB 가 '진짜' 준비될 때까지, 수집기와 장치 10대 (integration.sh)", "file": "fleet/tests/integration.sh:29-57", "crumb": "6부 믿을 수 있나 · 테스트 — 통합 1/2 (준비)",
              "code": code("fleet/tests/integration.sh", 29, 57, max_len=170), "codeSize": 10, "pointsSize": 10.5,
              "points": ["trap cleanup EXIT: 어떻게 끝나든(실패 포함) 수집기·장치·HTTP 서버를 정리한다. 컨테이너는 KEEP=0 일 때만 내린다(CI) — WSL 에서는 기본 KEEP=1 이라 그대로 둔다", "0) 릴리스 패키지(11/10): 매니페스트가 없으면 jitter_bench 를 빌드해 정상·깨진 패키지를 만들고(package_release.sh, --bad) 아키텍처별 매니페스트를 하나로 합친 뒤 로컬 HTTP(127.0.0.1:8089)로 서빙 — 4b·4c 의 장치가 여기서 내려받는다", "1) docker compose up mqtt db → migrate.py --wait 120: 컨테이너 안 pg_isready 는 init 중 임시 서버에도 '준비됨'이라 한다 → 밖에서 TCP 로 진짜 붙어 보며 기다린다(11/04 CI 1차 실패의 해결)", "2) 수집기(--qos 1) + 가상 장치 10대 2 Hz(--prefix ci, --slot-root: 장치마다 A/B 슬롯 폴더). 로그는 $OUT 에", "sleep 8: 장치가 전부 붙고 첫 묶음이 DB 에 들어갈 시간"]})
    s.append({"kind": "code", "section": SEC5, "title": "통합 테스트 스크립트 (2/2) — 장애 3종 + 나쁜 펌웨어 + 정상 OTA + 산출물 OTA(4b·4c) → 판정 → 표 (integration.sh)", "file": "fleet/tests/integration.sh:59-77", "crumb": "6부 믿을 수 있나 · 테스트 — 통합 2/2 (장애·판정)",
              "code": code("fleet/tests/integration.sh", 59, 77, max_len=170), "codeSize": 10, "pointsSize": 10.5,
              "points": ["3) 장애 3종 각 5초(settle 8): broker · db · collector(qos1). 나쁜 펌웨어 줄의 || true 는 안전장치 — 63줄 주석의 '종료 코드 1' 은 옛 설명이고, 지금 inject.py 는 결과 파일을 쓰면 0 을 낸다(롤백 여부는 5) 판정에서 본다)", "4) 정상 OTA 1.1.0(흉내 — 버전 문자열만): 세 단계(5 → 50 → 100%)를 다 통과해야 success=true", "4b) 산출물 OTA(11/10): 진짜 패키지를 내려받아 sha256 → A/B 슬롯 → 자가 점검 → 전환. 4c) 자가 점검이 실패하는 패키지 → 첫 단계에서 거부·롤백(종료 코드 1 이 정상이라 || true). 11/10 밤 4b 가 상대 경로 슬롯에서 exit 127 — CI 가 잡았다(7부 덧붙임 사고 표)", "5) assert_results.py 가 JSON 7개를 규칙으로 판정 — 하나라도 어긋나면 종료 코드 ≠ 0 → CI 잡 실패", "make_table3.py 가 같은 결과 파일($OUT)과 DB 통계로 table3_ci.md 를 만들어 아티팩트로 — 사람이 읽는 표와 CI 의 판정이 같은 원본. WSL 에서도 같은 스크립트(약 3~4분, E13)"],
              "next": "CI — 테스트는 사람이 돌릴 때만 돈다. 누가 매 push 마다 빠짐없이 돌리나? (GitHub Actions 3잡)"})
    s.append({"kind": "chain", "section": SEC5, "title": "CI 잡 1 — rt_core (1단계, 러너 VM 1, 약 35초): 빌드 → 단위 테스트 → 연기 → 표 생성기 → fleet 단위 26건", "perRow": 4, "crumb": "6부 믿을 수 있나 · CI 잡 1 rt_core",
              "items": [
                  {"kind": "in", "text": "push · pull_request · 수동 실행\n→ GitHub 가 새 VM(ubuntu-24.04)을 켠다. 내 노트북이 아니고 매번 백지"},
                  {"text": "apt: cmake g++ python3\n→ cmake 빌드 rt_core"},
                  {"kind": "q", "text": "ctest 4건 통과?\n링 버퍼 · 제어 단계 · 상태 머신 · 1 kHz 2초 드롭 0", "answer": "예 → 계속 / 아니오 → 잡 실패, 배지 빨강"},
                  {"kind": "do", "text": "jitter_bench --no-rt 2초 → JSON → make_table1\n('돌아간다'의 증거, 지연 수치 아님 — 러너엔 RT 없음)"},
                  {"kind": "q", "text": "fleet 단위 26건 전부 OK?\n(가짜 브로커·DB 위)", "answer": "예 / 아니오 → 로그의 FAIL: 줄"},
                  {"text": "대시보드 JSON 생성 → 파싱 검사\n(make_dashboard.py)"},
                  {"kind": "end", "text": "✓ 아티팩트 jitter-ci(jitter_ci.json · table1_ci.md)\n→ needs: 로 2단계 두 잡이 병렬 시작"},
              ],
              "bottom": "1단계의 뜻: 1분 안에 '논리가 깨지지 않았다'를 확인한다. 여기서 떨어지면 2단계(진짜 컨테이너·물리)는 돌지 않는다 — 싼 검사부터(DECISIONS 11/03 D4). 걸린 시간은 11/11 의 두 실행이 34초 · 37초(11/05 에는 1분 13초 — 러너의 apt 속도에 따라 흔들린다). 출처: .github/workflows/ci.yml 잡 rt_core, docs/ENVIRONMENT.md §5"})
    s.append({"kind": "chain", "section": SEC5, "title": "CI 잡 2 — fleet_integration (2단계, 러너 VM 2, 약 2분 30초): 진짜 컨테이너에서 장애 3종 + 롤백 + OTA + 진짜 산출물 설치", "perRow": 4, "crumb": "6부 믿을 수 있나 · CI 잡 2 fleet_integration",
              "items": [
                  {"kind": "in", "text": "잡 1 통과(needs: rt_core)\n새 VM 에 pip install + cmake(패키지에 넣을 jitter_bench)", "fs": 10},
                  {"text": "릴리스 패키지(정상 · 깨진 것) → 로컬 HTTP\ndocker compose up mqtt db → migrate.py --wait 120", "fs": 10},
                  {"kind": "q", "text": "DB 가 진짜 준비됐나?\n(pg_isready 는 임시 서버에도 '예'라 한다)", "answer": "예 → 계속 / 시간 초과 → 잡 실패 (11/04 1차 실패 자리)"},
                  {"kind": "do", "text": "수집기(QoS 1) + 가상 장치 10대 2 Hz(A/B 슬롯)\n→ 장애 주입 broker · db · collector 5초(settle 8)", "fs": 10},
                  {"kind": "do", "text": "나쁜 펌웨어 inject --fault bad_firmware(롤백돼야 정상)\n→ 정상 OTA 1.1.0 (흉내)", "fs": 10},
                  {"kind": "do", "text": "4b 산출물 OTA: 내려받기 → sha256 → 슬롯 → 자가 점검 → 전환\n4c 깨진 패키지: 첫 단계에서 거부·롤백", "fs": 10},
                  {"kind": "q", "text": "assert_results.py (JSON 7개)\n유실 0 · 복구 · 롤백 · OTA · 거부?", "answer": "예 → ✓ / 아니오 → 실패 줄에 어느 규칙인지", "fs": 9.5},
                  {"kind": "end", "text": "✓ table3_ci.md → 아티팩트 fleet-integration\n(11/05 실측 0/318 · 0/286 · 0/280, 롤백 0.4초)"},
              ],
              "bottom": "2단계의 뜻: 가짜 위에서 맞던 논리가 진짜 브로커·DB 위에서도 맞는지 한 번 더. CI 가 실제로 잡은 3건이 전부 이 잡이다(11/04 TimescaleDB 초기화 경쟁 · 11/05 request_stop 삭제 · 11/10 상대 경로 슬롯에서 자가 점검 exit 127). 걸린 시간은 11/11 의 두 실행이 2분 25초 · 2분 34초. 출처: fleet/tests/integration.sh, docs/experiments/E13.md"})
    s.append({"kind": "chain", "section": SEC5, "title": "CI 잡 3 — mujoco (2단계, 러너 VM 3, 약 45초): 헤드리스 물리 — SO-ARM100 1 kHz, ALLEX 500 Hz, 비용 상한", "perRow": 2, "nodeH": 1.45, "crumb": "6부 믿을 수 있나 · CI 잡 3 mujoco",
              "items": [
                  {"kind": "in", "text": "잡 1 통과(needs: rt_core)\n새 VM"},
                  {"text": "get_mujoco.sh 3.3.2 + menagerie SO-ARM100\n→ cmake -DRT_CORE_WITH_MUJOCO=ON"},
                  {"kind": "q", "text": "ctest mujoco: 2,000주기 동안 관절이 움직이고\n한 주기 비용 p99 < 900 us?", "answer": "예 → ✓ (실측 p99 8.5 us) / 아니오 → 잡 실패"},
                  {"text": "get_allex.sh — 위로보틱스 ALLEX 48 자유도 (고정 커밋)\n같은 테스트 바이너리, 프로필의 관절 이름 48개, 주기 2 ms"},
                  {"kind": "q", "text": "1,000주기 동안 움직이고\np99 < 1,800 us (2 ms 의 90%)?", "answer": "예 → ✓ (러너 p99 510 us) / 아니오 → 잡 실패"},
                  {"kind": "end", "text": "✓ JSON 2개 → 아티팩트 mujoco-ci\n셋 다 ✓ 면 README 배지 초록 (2단계 병렬)"},
              ],
              "bottom": "ALLEX 게이트를 운영점(500 Hz)으로 두는 이유: 1 kHz 는 '어디까지 되나'의 측정(E21)이고 CI 는 '운영점에서 통과하나'의 게이트 — 섞으면 러너 상태에 따라 빨개지는 날이 생긴다. 물리 잡을 따로 둔 이유: MuJoCo 를 빌드 옵션(기본 OFF)으로 두어 MuJoCo 없는 환경(1단계·Pi)에서도 빌드되게 했고, 물리가 있는 환경에서만 '제어 코드 무변경 + 비용 상한'을 다시 확인한다(DECISIONS 11/03 D5). 출처: rt_control/rt_core/test/test_mujoco_backend.cpp"})
    s.append({"kind": "table", "section": SEC5, "title": "CI 결과를 보고 무엇을 판단하나 — 실패 유형별 첫 행동", "fontSize": 11, "crumb": "6부 믿을 수 있나 · CI — 실패 유형별 판단",
              "colW": [3.4, 4.3, 4.6],
              "rows": [["증상", "뜻", "첫 명령"],
                       ["배지 빨강 / gh run list ✗", "마지막 push 가 3잡 중 하나라도 실패. 다른 일보다 먼저 본다 — 포트폴리오 첫 화면", "gh run view <ID> --log-failed | tail -40"],
                       ["rt_core 의 ctest 실패", "코드 논리가 깨짐(WSL 에서도 깨질 것)", "ctest --test-dir build/rt_core --output-on-failure"],
                       ["rt_core 의 fleet 단위 FAIL:", "수집기·OTA·에이전트 논리", "python3 fleet/tests/test_*.py"],
                       ["fleet_integration '장치 0대'", "수집기나 가상 장치가 시작 직후 죽음", "로그에서 traceback (11/05 NameError: request_stop)"],
                       ["fleet_integration 복구 시간 초과", "타이밍·컨테이너 준비(11/04 TimescaleDB 임시 서버)", "migrate.py --wait 가 지났는지, settle 값"],
                       ["mujoco 다운로드 실패", "외부 URL·버전", "get_mujoco.sh 와 ci.yml 의 MUJOCO_VERSION 일치"],
                       ["Unable to resolve action", "uses: 버전이 없음", "checkout@v5, upload-artifact@v5 확인"]],
              "note": "CI 가 실제로 잡은 3건: 11/04 TimescaleDB 초기화 경쟁(WSL 볼륨엔 데이터가 있어 안 보임) · 11/05 request_stop 삭제(단위 테스트가 main() 을 안 탐) · 11/10 상대 경로 슬롯(단위 테스트는 절대 경로만 — 그 빨강을 3시간 못 봤다). 규칙: 문서 커밋이라도 push 뒤 gh run list -L 1"})
    s.append({"kind": "table", "section": SEC5, "title": "Jenkins 에 익숙한 사람을 위한 대응표", "fontSize": 11.5, "crumb": "6부 믿을 수 있나 · CI — Jenkins 대응표",
              "colW": [3.3, 3.6, 5.4],
              "rows": [["Jenkins", "GitHub Actions", "이 저장소"],
                       ["Jenkins 서버(직접 운영)", "GitHub 가 운영", "—"],
                       ["빌드 노드 / agent", "runner", "runs-on: ubuntu-24.04 (매번 새 VM)"],
                       ["Job(파이프라인 하나) / Jenkinsfile", "workflow (yml 파일 하나)", ".github/workflows/ci.yml · release.yml(태그 때, 11/10)"],
                       ["트리거(polling·webhook·수동)", "on:", "ci: push · pull_request · workflow_dispatch / release: 태그 v*"],
                       ["stage", "job (각자 다른 runner)", "ci: rt_core · fleet_integration · mujoco / release: package × 2 · canary · publish"],
                       ["sh 한 줄 / 플러그인", "step (run:) / action (uses:)", "'Configure & build' … / checkout@v5, upload-artifact@v5"],
                       ["upstream/downstream", "needs:", "2단계 둘이 needs: rt_core → 병렬"],
                       ["Build #123 / 콘솔 출력", "run (ID) / job 로그", "gh run list · gh run view <ID> --log-failed"],
                       ["JUnit 리포트 화면", "(없음 — 로그의 OK/FAIL)", "필요하면 JUnit XML + 리포터 액션"]],
              "note": "Jenkins 의 'job' = GitHub 의 'workflow', GitHub 의 'job' = Jenkins 의 'stage' — 이름이 한 칸씩 어긋난다. 출처: docs/ENVIRONMENT.md §5-6",
              "next": "7부 — 코드·숫자·검증이 한 벌이 됐다. 왜 이렇게 만들었고(버린 대안), 무엇이 깨졌고, 어떻게 일했나?"})
    # ---------------- 6 ----------------
    s.append({"kind": "section", "section": SEC6, "num": "07", "title": "왜 · 사고 · 방식 — 결정, 깨진 것, 일정, AI, 용어",
              "subtitle": "왜 이렇게 만들었나(버린 대안 포함), 무엇이 깨졌고 어떻게 풀었나, 2주를 어떻게 썼나, 그리고 처음 읽는 사람을 위한 말",
              "flow": {"from": "코드 · 숫자 · 검증이 한 벌 (1~6부)",
                       "question": "왜 이렇게 만들었고, 무엇이 깨졌고, 어떻게 일했나?",
                       "answer": "결정 중 핵심 25건(이유 + 버린 대안) · 사고 11건(원인 + 고친 것 + 배운 규칙) · 2주 일정과 그 뒤 · AI 와 일한 방식(작성자의 것 / AI 의 것 / 검증) · 남은 일 · 면접 한 문장 12개 · 용어 · 덧붙임 7장(본편 뒤에 한 일)"},
              "agenda": ["결정 기록 3장(실시간 · 관제 · 측정·검증·범위)", "사고와 해결 2장 → 2주 일정 → 작성 방식(AI) → 남은 일 → 면접 한 문장 모음", "부록: 용어 2장", "덧붙임 7장: ALLEX(11/06) → 릴리스 → 배포 3장(그림 · 코드 · 숫자) → 클라우드 운영 층 → 사고와 해결 (3) → 왕복 290 ms(11/10~11)", "→ 끝: 결국 로봇은 이렇게 움직인다 (한 장 요약)"]})
    s.append({"kind": "table", "section": SEC6, "title": "결정 기록 (1/3) — 실시간 쪽: 왜 이렇게 만들었나", "fontSize": 10.5, "crumb": "7부 왜·사고·방식 · 결정 1/3 실시간",
              "colW": [3.0, 5.2, 4.1],
              "rows": [["결정 (날짜)", "이유", "버린 대안"],
                       ["RT 핵심은 ROS 2 와 무관한 순수 C++ (11/03)", "CI 러너(ROS 2 없음)에서도 핵심이 테스트되고, 미들웨어 교체가 어댑터 교체가 된다. '제어 코드가 어디 있나'에 파일 하나로 답한다", "ROS 2 노드 안에 제어를 직접 — 테스트·이식이 ROS 2 에 묶인다"],
                       ["로깅 큐는 꽉 차면 버린다 (11/03)", "RT 스레드가 기다리는 순간 꼬리가 생긴다. 버린 수를 세어 보이면 된다(실측 drops 0)", "블로킹 큐 / 가변 크기 큐(할당)"],
                       ["지연은 p99.9 와 max 로 판단 (11/03)", "평균 18 us 라도 한 번 781 us 면 그 주기를 놓친다", "평균·중앙값 보고"],
                       ["절대 시각 타이머 TIMER_ABSTIME (11/03)", "늦게 깬 만큼이 다음 주기로 쌓이지 않는다(드리프트 0)", "상대 sleep(usleep) — 매 주기 오차 누적"],
                       ["매 주기 할 일을 RtStep 으로 바꿔 끼움 (D1)", "측정기(BusyWork)와 노드(ControlStep)가 같은 루프를 쓴다 — 측정한 루프가 곧 제어 루프", "측정기와 노드가 루프를 따로 가짐"],
                       ["명령은 가장 최신 것만, 우편함을 매 주기 비움 (D1)", "밀렸다 풀린 옛 목표를 따라갈 이유가 없다", "큐에 쌓인 명령을 순서대로 전부 적용"],
                       ["워치독은 '멈춤 = 현재 위치 유지' (D1)", "급정지보다 안전한 기본값(실물은 토크 오프까지)", "0 위치로 복귀 — 더 위험"],
                       ["상태 머신은 if 문이 아니라 전이표 (D3)", "'FAULT 에서 바로 RUNNING 되나?'에 표 한 줄로 답, 표 밖은 전부 거부·카운트", "흩어진 if/else"]],
              "note": "출처: docs/DECISIONS.md 11/03~11/03(D3). 각 항목에 '이유'와 '버린 대안'을 적어 두는 것이 이 저장소의 규칙"})
    s.append({"kind": "table", "section": SEC6, "title": "결정 기록 (2/3) — 관제 쪽", "fontSize": 10.5, "crumb": "7부 왜·사고·방식 · 결정 2/3 관제",
              "colW": [3.0, 5.2, 4.1],
              "rows": [["결정 (날짜)", "이유", "버린 대안"],
                       ["장치 → 서버는 MQTT, 서버 안은 ROS 2 가 아니다 (D2)", "수십~수백 대·끊김·NAT 에는 MQTT(브로커·QoS·유언)가 맞다. ROS 2/DDS 는 로봇 안", "DDS 를 WAN 으로 — 발견·NAT 문제"],
                       ["수집기는 1초 묶음 + COPY (D2)", "300대 × 1 Hz 를 행마다 INSERT 하면 300 왕복/초. 묶으면 1번. 대신 DB 에 보이기까지 ≤1초(표에 적음)", "행마다 INSERT"],
                       ["끊김 처리는 장치 쪽 버퍼(store-and-forward) (D2)", "브로커가 죽어도 데이터는 장치에 남아 있다가 재전송(654 = 654)", "서버 쪽에서만 보관"],
                       ["대시보드 JSON 은 생성기로 (D2)", "패널 14개의 SQL 을 코드로 리뷰·수정·CI 파싱", "Grafana UI 에서 손으로 → export"],
                       ["OTA 롤백 결정은 서버가 (D3)", "장치는 적용/복원만. 판단 기준(헬스 게이트·허용 수)을 한 곳에. 11/10 보탬: 켜 보기 전의 거부(sha256·자가 점검)와 훅 실패 뒤 복귀는 장치가 스스로 — 함대 차원의 결정은 그대로 서버", "장치가 스스로 롤백"],
                       ["수집기 backlog 는 메모리, 상한 두고 버림 (D4)", "단순하고 빠름. 상한 200,000행 = 50대 66분. 버린 수를 센다", "디스크 큐 — 복잡도 대비 2주 밖"],
                       ["텔레메트리 QoS 기본 0, 옵션 1, 차이를 표로 (D4)", "가장 가벼운 기본 + '보호가 없으면 얼마를 잃나'를 숫자로(508 vs 0)", "무조건 QoS 1"],
                       ["브로커 persistence true, 수집기 곱게 종료, 수동 ACK 보류 (11/04)", "유실 53 의 원인 ①②를 막는 최소 변경. 수동 ACK(DB 적재 뒤 PUBACK)는 2주 밖", "paho 자동 ACK 그대로 두고 무시"],
                       ["keepalive 기본 10초 유지, jitter 는 옵션 (11/04)", "끊김 감지 15초를 지키고 박자만 흩뜨린다", "30초로 늘리기 — 감지 45초"]],
              "note": "출처: docs/DECISIONS.md 11/03(D2~D4), 11/04"})
    s.append({"kind": "table", "section": SEC6, "title": "결정 기록 (3/3) — 측정·검증·범위", "fontSize": 10.5, "crumb": "7부 왜·사고·방식 · 결정 3/3 측정·검증·범위",
              "colW": [3.0, 5.2, 4.1],
              "rows": [["결정 (날짜)", "이유", "버린 대안"],
                       ["DDS 지연은 왕복(RTT)으로 (D1)", "두 컴퓨터의 시계 차이와 무관. 한 방향 ≈ RTT/2", "한 방향 지연 — 시계 맞춤 필요"],
                       ["장애 주입은 docker stop/start 와 kill, 측정은 전부 DB 로 (D4)", "재현 가능하고, 숫자는 수집기가 이미 DB 에 남기는 것으로", "네트워크 장애 도구(tc) — 2주 밖"],
                       ["CI 는 2단계: 가짜로 빠르게, 진짜로 한 번 (D4)", "1분 안에 논리, 2분 더에 진짜 컨테이너. 싼 검사부터", "통합만 / 단위만"],
                       ["MuJoCo 는 Backend 의 한 구현, 빌드 옵션 기본 OFF (D5)", "MuJoCo 없는 환경(CI 1단계·Pi)에서도 빌드. 제어 코드 무변경 확인", "MuJoCo 를 필수 의존성으로"],
                       ["부하 측정은 120초, 온도·스로틀 기록, Pi 는 측정만 (11/04)", "80 °C 스로틀이 수치를 오염시킨다. 자격 증명은 WSL 한 곳", "방열판 달고 300초 — 조건이 바뀌면 일반 커널도 다시"],
                       ["표①의 조건은 커널 × 부하 × 고정/격리 × 도구 × 시간 (11/05)", "줄 하나가 반박 하나를 막는다('일반이면?', '한가하면 다 그렇다', '측정기가 틀렸다', '스로틀')", "RT 부하 한 줄만"],
                       ["부하 정의는 lib_stress.sh 한 곳, 쓴 값은 .meta (11/05)", "도구 비교 중 vm 512M vs 256M 차이가 측정기 차이로 보였다", "스크립트마다 따로"],
                       ["6주 계획을 2주로 줄이며 뺀 것 (11/03)", "실물 서보 백엔드·중력 보상·TLS 인증·디스크 큐·수동 ACK — 자리와 문서만 남김(TLS + 비밀번호는 11/10 에 운영 설정으로 넣었다)", "전부 하기 — 기한 안에 아무것도 증명 못 함"]],
              "note": "출처: docs/DECISIONS.md. 파일에는 전체 44건(11/11 기준 — 11/05 까지 28건, 그 뒤 16건은 7부 덧붙임 장표에서), 여기는 11/05 까지에서 면접에서 물을 만한 25건(세 장 8 + 9 + 8 행)",
              "next": "사고와 해결 — 결정대로 만들었지만 전부 처음부터 돌지는 않았다. 무엇이 깨졌고, 왜, 어떻게 고쳤나? (11건)"})
    s.append({"kind": "table", "section": SEC6, "title": "사고와 해결 (1/2) — 깨진 것, 원인, 고친 것", "fontSize": 10.5, "crumb": "7부 왜·사고·방식 · 사고 1/2",
              "colW": [3.3, 4.4, 3.4, 1.2],
              "rows": [["무엇", "원인", "해결", "기록"],
                       ["재시작된 수집기가 바로 죽음", "/proc/<pid>/exe 는 venv 를 잃은 경로", "/proc/<pid>/environ 의 VIRTUAL_ENV·PATH 로 같은 환경 재시작", "11/04"],
                       ["수집기 둘·가상 장치 두 벌이 2초마다 서로 밀어냄(reconnects 1,675)", "같은 MQTT client_id", "fleet/common/single_instance.py flock 잠금", "11/04"],
                       ["persistence true 뒤 오프라인 이벤트 +50", "보관된 유언이 재구독 때 다시 내려옴", "retain=1 상태는 사건이 아님 → events 제외", "11/04"],
                       ["CI fleet_integration 실패(1차)", "TimescaleDB 첫 기동의 임시 서버를 pg_isready 가 '준비됨'이라 함", "migrate.py --wait 가 TCP 로 재시도", "11/04"],
                       ["ros2 topic echo 가 토픽을 못 봄", "다른 RMW 로 떠 있던 ros2 데몬", "ros2 daemon stop / 타입을 직접 적기", "11/04"],
                       ["colcon install 뒤 libmujoco.so 못 찾음", "install 단계에서 rpath 소실", "CMAKE_INSTALL_RPATH_USE_LINK_PATH TRUE", "11/03"]],
              "note": "출처: docs/EXPERIMENTS.md §4 사고·함정, docs/LOG.md 해당 날짜. 사고마다 '배운 것' 한 줄이 LOG 에 있다"})
    s.append({"kind": "table", "section": SEC6, "title": "사고와 해결 (2/2)", "fontSize": 10.5, "crumb": "7부 왜·사고·방식 · 사고 2/2",
              "colW": [3.3, 4.4, 3.4, 1.2],
              "rows": [["무엇", "원인", "해결", "기록"],
                       ["노드가 파라미터 파일로 시작 안 됨", "빈 배열 mujoco_joints: [] 의 타입 미정", "빈 배열이면 키를 뺀다(profile_to_params)", "11/03"],
                       ["Pi 결과 파일 복사·커밋 실패", "WSL 명령을 Pi 창에 침, sudo 가 만든 root 소유 파일", "안내에 [Pi 창]/[WSL 창] 표시, chown -R", "11/04"],
                       ["Ubuntu One 가입 실패(실시간 커널 토큰)", "Launchpad 사용자명 검사 time out(Canonical 쪽)", "기다렸다 재시도(다음 날 아침 성공)", "11/04"],
                       ["CI fleet_integration 빨강(2차, NameError: request_stop)", "잠금 공용화 패치에서 시그널 핸들러 함수가 통째로 삭제. 단위 테스트가 main() 을 안 탐", "함수 복원 + main() 한 바퀴 스모크 테스트", "11/05"],
                       ["record.sh 가 조용히 안 끝남", "timeout 이 recorder 를 뒤 프로세스 그룹에 둠 → 키보드 읽기에서 SIGTTIN 정지", "timeout --foreground + --disable-keyboard-controls", "11/05"]],
              "note": "배운 규칙 둘: 진입점(main)은 단위 테스트가 한 번은 타야 한다 · 문서 커밋이라도 push 뒤 CI 를 본다(빨간 배지는 포트폴리오 첫 화면). 11/10~11 의 9건은 덧붙임 장표 {{first:덧붙임 (11/10~11) — 사고}} 에",
              "next": "2주 일정 — 이 결정과 사고가 언제 일어났나? D0~D8 과 그 뒤를 한 줄로"})
    s.append({"kind": "process", "section": SEC6, "title": "2주 일정 — 무엇을 언제 만들었나 (D0 ~ D8, 그리고 11/10~11)", "crumb": "7부 왜·사고·방식 · 2주 일정",
              "steps": [
                  {"head": "D0\n11/03", "lines": ["rt_core 뼈대: 링 버퍼·RT 루프·측정기", "WSL 일반 vs FIFO 비교 (E01·E02)", "표① 생성기"]},
                  {"head": "D1~D2", "lines": ["ROS 2 노드 + 제어 단계·워치독", "DDS 표② 16조합", "관제: 브로커·수집기·DB·Grafana, 가상 50대"]},
                  {"head": "D3~D4", "lines": ["상태 머신(전이표), OTA 단계 배포·롤백", "수집기 backlog, 장애 주입 4종, 판정", "CI 2단계(가짜 → 진짜 컨테이너)"]},
                  {"head": "D5\n11/04", "lines": ["MuJoCo 백엔드 + SO-ARM100", "장애 실측 1·2차 → 유실 53 → 0", "GitHub 공개, CI 3잡 초록"]},
                  {"head": "D6\n11/04 밤", "lines": ["Pi 4 세팅(Ubuntu 24.04)", "일반 커널 기준값 4줄", "열·스로틀 기록 스크립트"]},
                  {"head": "D7\n11/05", "lines": ["PREEMPT_RT: 커널 → 고정 → 격리", "도구 불일치 검증 4회", "기록 파이프라인 첫 실행, 실험 페이지 21장, 이 장표"]},
                  {"head": "D8\n11/06", "lines": ["제출 서류(이력서·설계서, 저장소 밖)", "공개 문서 점검 — IP·계정·경로 제거", "ALLEX 48 자유도: 프로필 하나로, E21 → 500 Hz"]},
                  {"head": "11/10\n~11/11", "lines": ["릴리스 → 배포: 진짜 설치, 태그 → 카나리 → 게시(E22)", "운영 층을 클라우드(시드니)에, Pi 가 보고 시작", "첫 릴리스 v0.9.0 · 왕복 290 ms(E23)"]},
              ],
              "foot": "D0~D4 는 날짜 표기가 '11/03 (D1)' 처럼 DECISIONS 의 꼬리표를 따른다(하루에 여러 D). 출처: docs/LOG.md, docs/HANDOVER.md",
              "next": "작성 방식 — 2주에 이만큼이 가능했던 이유와, 그래서 생기는 질문('AI 가 다 한 거 아냐?')에 대한 답"})
    s.append({"kind": "two_col", "section": SEC6, "title": "작성 방식 — AI(Claude)와 어떻게 일했나, 무엇이 작성자의 것인가", "crumb": "7부 왜·사고·방식 · AI 와 일한 방식",
              "left": {"head": "작성자(오문규)가 한 것", "bullets": ["무엇을 만들지·범위·일정(6주 → 2주, 뺀 것), git 전환, Pi 구매·세팅 결정", "모든 실행과 측정: WSL 과 Pi 에서 명령을 치고 출력을 읽고 다음 질문을 정함(수십 회)", "판단: '왜 하는지와 결과 해석이 문서에 있어야 한다', '순서도에 기준이 있어야 논리가 선다', '측정 조건이 왜 이 조합인가', '녹화는 직접 치는 모습이어야', '장표도 순서도 논리로'", "검토: 읽기 가이드 28항목과 실험 페이지 24장을 교재로 분석 기간(5회차) + 혼자 하는 과제 3건(Co-Authored-By 없는 커밋)"]},
              "right": {"head": "AI 가 한 것 · 어떻게 검증했나", "bullets": ["코드 초안·문서 초안·장표 초안. AI 가 쓴 커밋에 Co-Authored-By: Claude 표기(숨기지 않는다. 측정 결과·병합 커밋은 작성자 단독)", "AI 의 샌드박스에는 ROS 2·Docker·MuJoCo 가 없어 가짜 위에서 논리만 검증 → 진짜 첫 실행은 항상 작성자의 WSL/Pi/서버 — 그때 깨진 것 11건(11/10~11 에 9건 더)이 LOG 에", "CI 가 매 push 마다 3잡을 다시 돌린다(AI 도 작성자도 아닌 제3의 검사원)", "면접 한 문장: 'AI 를 코드 초안과 문서화에 썼고, 무엇을 만들지·무엇을 재고 어떻게 판단할지·결과가 맞는지는 제가 했습니다. 어느 파일이든 열어서 물어보셔도 됩니다'"]},
              "foot": "README '작성 방식' 문단, docs/HANDOVER.md §2. 회사가 AI 로 검증하면 1분 안에 보이는 것을 먼저 말하는 쪽이 신뢰를 얻는다",
              "next": "남은 일 — 지원(11/17)까지 무엇이 남았고, 면접에서 '다음 단계'로 말할 것은?"})
    s.append({"kind": "bullets", "section": SEC6, "title": "남은 일 — 지원(11/17)까지, 그리고 그 뒤", "crumb": "7부 왜·사고·방식 · 남은 일",
              "bullets": [
                  {"text": "지원 전 (우선순위 순)", "bold": True},
                  {"text": "Pi 의 첫 자율 업데이트(v0.9.0, 새벽 03~05시)와 연속 기록을 다음 날 아침에 세어 확인 → E22 · 이 장표의 숫자 갱신", "sub": True},
                  {"text": "2분 영상 — 대본 v2·자막 상자(cue.sh)·순서표(CHEATSHEET) 준비됨. 원테이크 직접 타이핑 + Clipchamp TTS", "sub": True},
                  {"text": "작성자의 분석 기간 5회차 — 표① 사슬 → 제어·물리 → 관제 → 장애 → OTA·CI·릴리스. 각 회차 끝에 혼자 하는 과제 1건(예: 2 kHz 측정 줄 추가, 테스트 1개, 패널 1개)", "sub": True},
                  {"text": "제출 서류(이력서·설계서)에 11/10~11 의 것(릴리스 → 배포 · 운영 층 · 왕복) 반영", "sub": True},
                  {"text": "선택 (면접에서 '다음 단계'로 말할 것)", "bold": True},
                  {"text": "512M 부하로 cyclictest -S 한 번 더(E19-d 의 부하 정의 vs 격리 전후 가르기) · 방열판 달고 300초 부하", "sub": True},
                  {"text": "수동 ACK(DB 적재 뒤 PUBACK) · 브로커 로그로 천둥 떼 가설 확정 · 기록 요약을 관제로 1 Hz 올리기", "sub": True},
                  {"text": "중력 보상(토크 피드포워드) · 관절 한계 클램프 · 실물 Feetech 시리얼 백엔드 · JUnit 리포트", "sub": True},
                  {"text": "릴리스·운영: 산출물 서명(ed25519) · 헬스 게이트에 RT 지표 · 노드 재시작 훅 · 자율 모드에서 실패한 버전만 건너뛰기 · 장치별 인증서(mTLS) · 양쪽 TCP_NODELAY 측정", "sub": True},
              ],
              "callout": {"title": "지금 상태(11/11)", "text": "코드·측정·문서·CI 가 일관된 상태이고, 첫 정식 릴리스 v0.9.0 이 게시됐다(러너 카나리 50/50, 깨진 빌드 3/50 에서 거부).\n남은 큰 일은 영상 · 분석 기간 · 서류 제출 — 모두 작성자의 손이 필요한 일"},
              "next": "면접 한 문장 모음 — 지금까지의 장표에서 바로 꺼내 쓰는 문장 12개"})
    s.append({"kind": "bullets", "section": SEC6, "title": "면접 한 문장 모음 — 장표에서 바로 꺼내 쓰는 문장 12개", "fontSize": 13.5, "crumb": "7부 왜·사고·방식 · 면접 한 문장 12",
              "bullets": [
                  "표①: '우선순위는 줄을 앞세울 뿐이고 꼬리를 자르는 건 커널이다 — WSL 에서 p50 은 좋아졌지만 max 는 그대로였던 이유. Pi 에서 커널만 바꿔 781 → 301, 격리로 189.'",
                  "비용: 'RT 커널은 상한을 사고 평균을 조금 내준다 — 부하 p99 가 146 → 185 로 나빠진 것도 표에 그대로 적었다.'",
                  "측정기: '표준 도구와 2.3배 달라서 변수를 하나씩 지웠다 — 같은 설정에서 274 대 270 으로 일치했고, 차이는 스레드 배치와 부하 정의였으며, 그 과정에서 내 스크립트 둘의 부하가 달랐던 실수를 찾았다.'",
                  "열: '임베디드 보드의 지연 측정은 열 조건을 같이 기록하지 않으면 재현도 비교도 안 된다 — 표①의 모든 Pi 줄에 온도와 스로틀 여부가 붙어 있는 이유.'",
                  "구조: '제어 코드는 ROS 2 와 로봇에서 떼어 두었다 — 백엔드를 SimLag 에서 MuJoCo 로 바꿨는데 제어 코드는 한 줄도 안 바뀌었다.'",
                  "안전: '명령이 50 ms 끊기면 지금 자리에 멈추고 FAULT, 명령이 다시 와도 100 ms 연속 정상이어야 READY — 전이표 밖의 길은 전부 막혀 있다.'",
                  "물리: '물리가 들어오자 어깨가 1.1° 처졌다 — SimLag 로는 절대 못 보는, 중력 보상이 필요하다는 숫자 근거.'",
                  "관제: '유실 0 은 처음부터 0 이 아니었다 — 측정 맹점을 고치자 53, 원인 셋을 추적해 둘은 설정과 종료 처리로 막고 하나는 큐 상한의 설계 수치로 정리했다.'",
                  "QoS: '보호가 없으면 얼마를 잃는지도 쟀다 — QoS 0 은 508, QoS 1 지속 세션은 0.'",
                  "OTA: '나쁜 펌웨어는 5%, 세 대에서 헬스 게이트가 잡아 1초에 롤백하고 47대는 건드리지도 않는다.'",
                  "기록: '관제는 1 Hz 요약을 서버로, 기록은 100 Hz 원본을 로봇 안에 — 30초 기록에서 100.0 Hz·틈 0·처짐 1.1° 가 사람 손 없이 나온다.'",
                  "CI: '푸시마다 러너가 1 kHz 루프, 물리, 장애 3종과 롤백, 진짜 설치를 다시 돌린다 — 그리고 실제로 세 번 나를 잡았다.'",
              ],
              "next": "부록 용어 2장 → 덧붙임 7장(11/06 ~ 11/11, 장표마다 면접 한 문장이 설명 문서에) → 끝: 결국 로봇은 이렇게 움직인다"})
    s.append({"kind": "cards", "section": SEC6, "title": "부록 · 용어 (1/2) — 실시간 쪽, 처음 읽는 사람을 위한 한 줄씩", "cols": 3, "crumb": "7부 부록 · 용어 1/2 실시간",
              "cards": [
                  {"icon": "RT", "head": "실시간 · PREEMPT_RT", "lines": ["실시간 = 빠른 게 아니라 '정해진 시간 안에 항상'", "PREEMPT_RT = 급한 스레드가 오면 커널이 하던 일을 중단하고 비켜 주는 리눅스 패치. /sys/kernel/realtime = 1"]},
                  {"icon": "us", "head": "us · p99.9 · max · 지터", "lines": ["us = 마이크로초 = 100만분의 1초. 1 ms = 1,000 us", "p99.9 = 1,000번 중 999번은 이 값 이내. max = 가장 나쁜 한 번", "지터 = 주기가 흔들리는 폭"]},
                  {"icon": "SF", "head": "SCHED_FIFO · mlockall", "lines": ["SCHED_FIFO = '더 급한 스레드가 없으면 CPU 를 내놓지 않는다'. 우선순위 1~99", "mlockall = 메모리를 RAM 에 고정(스왑·페이지 폴트 없음)"]},
                  {"icon": "T", "head": "절대 시각 타이머", "lines": ["clock_nanosleep(TIMER_ABSTIME): '지금부터 1 ms' 가 아니라 '그 시각에' 깨워 달라", "늦게 깬 만큼이 쌓이지 않는다(드리프트 0)"]},
                  {"icon": "Q", "head": "SPSC 링 버퍼 · 우편함", "lines": ["넣는 스레드 하나, 꺼내는 스레드 하나 → 락 없음", "꽉 차면 버리고 센다. 우편함 = 명령 링(64), 벨트 = 상태 링(2048)"]},
                  {"icon": "I", "head": "IPI · isolcpus · 스로틀", "lines": ["IPI = CPU 간 인터럽트. 우선순위도 격리도 못 막는다", "isolcpus = 그 CPU 를 일반 스케줄링에서 떼어 둔다", "스로틀 = 80 °C 에서 클럭을 내림 → 측정 오염"]},
              ]})
    s.append({"kind": "cards", "section": SEC6, "title": "부록 · 용어 (2/2) — 관제·미들웨어·물리 쪽", "cols": 3, "crumb": "7부 부록 · 용어 2/2 관제·물리",
              "cards": [
                  {"icon": "R2", "head": "ROS 2 · 토픽 · DDS · RMW · QoS", "lines": ["토픽 = 이름표 붙은 데이터 흐름. DDS 가 발견·전달", "RMW = ROS 가 DDS 를 부르는 층(Fast DDS / Cyclone)", "QoS: reliable(재전송) vs best_effort(잃을 수 있음), depth(큐 깊이)"]},
                  {"icon": "MQ", "head": "MQTT · 브로커 · QoS 0/1 · 지속 세션", "lines": ["브로커 = 우체국. 장치는 발행, 서버는 구독", "QoS 0 보내고 잊음 / 1 받았다는 확인(PUBACK)", "지속 세션(clean_session=False) = 없는 동안 브로커가 대신 보관"]},
                  {"icon": "LWT", "head": "유언 · 보관 메시지 · keepalive", "lines": ["유언(LWT) = 비정상 종료 때 브로커가 대신 발행하는 'offline'", "보관(retained) = 마지막 값을 새 구독자에게 바로 — '지금 상태'", "keepalive = 이 시간 동안 조용하면 PINGREQ, 1.5배 넘으면 끊김"]},
                  {"icon": "DB", "head": "TimescaleDB · 하이퍼테이블 · COPY · backlog", "lines": ["시간으로 자동 분할되는 PostgreSQL 표", "COPY = 묶음 적재(행마다 INSERT 보다 DB 왕복이 훨씬 적다)", "backlog = DB 가 죽은 동안 수집기가 들고 있는 묶음"]},
                  {"icon": "OTA", "head": "OTA · 단계 배포 · 헬스 게이트 · 롤백", "lines": ["OTA = 무선 펌웨어 갱신", "단계 배포(카나리) = 5% → 50% → 100%", "헬스 게이트 = 단계마다 state 를 보고 통과/롤백", "A/B 슬롯 = 버전마다 폴더, current 링크로 전환 · 자가 점검 = 켜 보기 전의 검사"]},
                  {"icon": "MJ", "head": "MuJoCo · Menagerie · 중력 처짐 · 추종 오차", "lines": ["MuJoCo = 물리 엔진(중력·접촉·모터). Menagerie = 검증된 로봇 모델 모음", "ALLEX = 위로보틱스가 공개한 상체 휴머노이드 모델(48 자유도, position 서보) — 프로필 하나로 붙였다", "중력 처짐 = 목표 아래로 쳐지는 정상 상태 오차(어깨 1.1°)", "추종 오차 = |목표 − 실제|, rad(× 57.3 = 도)"]},
              ],
              "next": "덧붙임 — 본편(11/05) 뒤에 한 일 일곱 장: ALLEX → 릴리스 → 배포 → 클라우드 운영 층 → 사고 → 왕복. 그 다음이 끝"})
    # ---------------- 덧붙임 (11/06) — 장표 본편(11/05) 뒤에 한 일. 번호를 흔들지 않으려고 7부 끝에 둔다 ----------------
    s.append({"kind": "kpi", "section": SEC6, "title": "덧붙임 (11/06) — 위로보틱스 공개 모델 ALLEX 48 자유도를 프로필 하나로: 같은 코드, 비용 70~100배, 500 Hz 결정", "crumb": "7부 왜·사고·방식 · 덧붙임 ALLEX (11/06)",
              "kpis": [{"value": "48 / 0줄", "label": "자유도 / 바뀐 제어 코드\nrobots/allex.yaml 하나 (+ 받기 스크립트)"},
                       {"value": "×70~100", "label": "물리 한 주기 비용, 6축 대비\n같은 PC: 4.9/6.3/20.8 → 336/622/1,785 us"},
                       {"value": "458 · 622", "label": "1 kHz 물리 p99 (us), 러너 · WSL\n= 1 ms 예산의 46~62%"},
                       {"value": "500 Hz", "label": "ALLEX 프로필 기본 주기 (모델 걸음 2 ms)\n실측 p99 러너 510 (26%) · WSL 1,000 us (50%)"}],
              "bullets": ["왜 했나: 회사가 2026-06-29 공개한 모델(MJCF, BSD-3)이 이 백엔드가 기대하는 꼴(position 액추에이터 48개, 이름 있는 관절)과 같았다 — '로봇을 바꾸는 일은 설정 파일을 바꾸는 일'이라는 1부 단계 6 의 주장을 회사의 로봇으로 시험했다. 수동 관절 12개(손가락 DIP·IP, 허리 링크)는 등식 제약으로 따라오므로 프로필에 이름 48개를 적어야 한다",
                          "무엇이 나왔나: 제어 코드·백엔드·노드 무변경(git show --stat). 물리는 예상보다 무거웠다 — 손가락 30관절의 접촉과 등식 제약이 제약 풀이를 키운 것으로 본다(추정). 합격선(p99 < 주기의 90%)은 넘었지만 물리만으로 1 ms 의 절반 가까이가 사라져, 모델 기본 걸음인 500 Hz 를 프로필 기본으로 (버린 대안: 1 kHz 유지 · 물리 2주기에 1번 · 물리 스레드 분리)",
                          "정직한 줄: '비용은 같고 예산만 2배라 p99 31%' 라던 어림은 WSL 실측 50% 에 틀렸다. p50 은 같고 꼬리만 나빠졌다 — 러너에선 +11% 뿐이라 환경 꼬리가 주원인으로 보이지만(추정) 조건별 3회·10초 측정으로 가를 일. 결정은 유지, 틀린 어림은 E21·DECISIONS 에 그대로 남겼다"],
              "fontSize": 11.5,
              "foot": "원본: docs/experiments/E21.md, docs/measurements/mujoco_backend_allex_{wsl_1khz, wsl_500hz, ci_1khz_run42172730308, ci_500hz_run42175845461}.json, docs/DECISIONS.md 11/06. 남은 것: 노드 안 work_us(500 Hz)·drop, 반복 측정",
              "next": "덧붙임 (11/10) — ALLEX 는 '로봇을 바꾸는 일'이었다. 다음은 '로봇의 소프트웨어를 바꾸는 일': 태그 하나로 빌드 · 검증 · 게시까지"})
    s.extend(addenda_1110())

    # ---------------- 끝 ----------------
    s.append({"kind": "section", "section": SEC7, "num": "끝", "title": "결국 로봇은 이렇게 움직인다",
              "subtitle": "출발(공고)에서 여기까지 온 길을 한 장으로 접는다 — 어느 상자에서든 멈춰 '이 숫자는 어디서 왔고, 코드는 어디에 있고, 왜 그렇게 했나'를 말할 수 있어야 한다",
              "flow": {"from": "1~7부 — 로봇을 움직이는 10단계 · 데이터의 길 8단계 · 검증 · 공고와 숫자 · 어디서 · 어떻게 믿나 · 왜 이렇게",
                       "question": "그래서 로봇은 어떻게 움직이나?",
                       "answer": "명령 50 Hz → DDS → 우편함 → 1 ms 루프(max 189 us) → 안전 검사 → MuJoCo → 관절이 움직인다(어깨 1.1° 처짐) → 상태 100 Hz → 기록(틈 0) → 관제(유실 0). 한 장표에 숫자와 파일 이름을 같이"},
              "agenda": ["한 장 요약(10 상자, 숫자 + 파일) · 닫는 장"]})
    s.append({"kind": "path", "section": SEC7, "title": "끝 — 결국 로봇은 이렇게 움직인다 (한 장 요약, 숫자와 함께)", "perRow": 5, "crumb": "끝 · 한 장 요약",
              "stages": [
                  {"head": "명령 50 Hz", "text": "목표 [0.3, −0.2, 0.1, 0, 0, 0.5] rad", "ref": "/joint_command", "color": "accent5"},
                  {"head": "DDS 전달", "text": "작은 메시지 손실 0, RTT p50 ≈ 1 ms", "ref": "표②", "color": "accent5"},
                  {"head": "우편함", "text": "락 없는 링 64칸, 꽉 차면 버리고 센다", "ref": "spsc_ring.hpp", "color": "accent1"},
                  {"head": "1 ms 루프", "text": "Pi RT: max 189 us(격리), 드롭 0. WSL: 참고값", "ref": "표① · rt_loop.cpp", "color": "accent1"},
                  {"head": "안전 검사", "text": "최신 명령 · 워치독 50 ms · 0.05 rad/주기 · 상태 머신 RUNNING", "ref": "control_step.cpp", "color": "accent1"},
                  {"head": "백엔드", "text": "MuJoCo ctrl → mj_step, p99 6축 8.5 us · ALLEX 48축 458 us", "ref": "mujoco_backend.cpp", "color": "accent6"},
                  {"head": "로봇이 움직인다", "text": "어깨 −0.181(처짐 1.1°), 팔꿈치 0.109, 나머지 목표 그대로", "ref": "/joint_states", "color": "accent2"},
                  {"head": "상태 100 Hz", "text": "실제 100.0 Hz, rt_status 1 Hz JSON", "ref": "rt_control_node.cpp", "color": "accent1"},
                  {"head": "기록", "text": "MCAP 30초 → CSV → 요약: 틈 0, 처짐 자동 검출", "ref": "data_pipeline/", "color": "accent3"},
                  {"head": "관제", "text": "브로커 → 수집기 → DB → Grafana. 브로커 장애 유실 0 / 1400(가상 50대), 실물 Pi → 시드니 서버 14.8시간 유실 0", "ref": "fleet/ · deploy/", "color": "accent3"},
              ],
              "bottom": "이 한 줄기가 저장소의 전부다. 어느 상자에서든 멈춰 '이 숫자는 어디서 왔고, 코드는 어디에 있고, 왜 그렇게 했나'를 설명할 수 있어야 한다 — 그 답이 docs/experiments/, docs/DECISIONS.md, 그리고 장표마다 붙은 설명 문서에 있다"})
    s.append({"kind": "closing", "section": SEC7, "title": "rt-robot-data-infra — 코드와 숫자는 저장소에 있습니다",
              "bullets": ["github.com/ohevance/rt-robot-data-infra — README 첫 표가 공고 ↔ 산출물 ↔ 숫자, 배지가 CI", "읽는 순서: docs/ENVIRONMENT.md → docs/READING_GUIDE.md(28항목) → docs/EXPERIMENTS.md(순서도) → docs/experiments/(24장) · 릴리스와 운영은 docs/RELEASE.md · deploy/ec2/README.md", "장표 설명 문서: docs/deck/notes/NNN.docx (장표 번호와 같다)", "작성: 오문규 · AI 보조(Claude, AI 가 쓴 커밋에 Co-Authored-By 표기) · 2026-11-03 ~ 11-11"]})
    return s


def addenda_1110():
    """덧붙임 (11/10~11) 여섯 장 — 본편(11/05)과 ALLEX 덧붙임(11/06) 뒤에 한 일. 번호를 흔들지 않으려고 7부 끝(끝 섹션 바로 앞)에 둔다 (DECISIONS 11/06)
    순서도 논리: ALLEX = 로봇을 바꾸는 일 → 릴리스 = 로봇의 소프트웨어를 바꾸는 일(그림 → 코드 → 숫자) → 그 관제는 어디에(운영 층) → 실제 기계에서 나온 것(사고) → 틀린 숫자를 가른 법(왕복)"""
    a = []
    # ---- 1/6 릴리스 → 배포 한 장 그림 ----
    a.append({"kind": "chain", "section": SEC6, "title": "덧붙임 (11/10) — 릴리스 → 배포 한 장 그림: 태그 하나로 빌드 · 가상 50대 카나리 · 게시까지, 로봇에 닿는 마지막 걸음은 사람 또는 장치", "perRow": 4, "nodeH": 1.3,
              "crumb": "7부 왜·사고·방식 · 덧붙임 릴리스 → 배포 1/3 그림 (11/10)",
              "items": [
                  {"kind": "in", "text": "11/05 까지의 OTA 는 '흉내'\n버전 문자열을 바꾸고 apply_s 초 잤다 — 설치되는 '것'이 없었다 (2부 ⑥)", "fs": 9.5},
                  {"kind": "q", "text": "이 커밋을 로봇에\n내보낼지는 누가?", "answer": "사람 — git tag v0.9.0 && git push origin v0.9.0 (push 마다가 아니다)"},
                  {"kind": "do", "text": "package × 2 (release.yml)\nx86_64 러너 · aarch64(arm) 러너: 빌드 → ctest → tar.gz + sha256 + manifest (+ 깨진 패키지)", "fs": 9},
                  {"kind": "do", "text": "canary: 진짜 Mosquitto + 가상 50대(A/B 슬롯)\n정상 패키지를 5 → 50 → 100 % 로 진짜 설치", "fs": 9.5},
                  {"kind": "q", "text": "50대 전부 새 버전,\n헬스 OK?", "answer": "예: 50 / 50, 1.2 → 2.2 → 2.2초 (v0.9.0)"},
                  {"kind": "do", "text": "같은 함대에 깨진 패키지\n(selftest.sh 가 exit 1)", "fs": 9.5},
                  {"kind": "q", "text": "첫 단계 3대에서\n거부·롤백?", "answer": "예: 3 / 50, 롤백 1.0초 / 아니오 → 게시 안 함"},
                  {"kind": "out", "text": "publish: GitHub Release\ntar.gz 2 + manifest.json + 카나리 JSON 2 (태그에 '-' 가 있으면 사전 릴리스)", "fs": 9.5},
                  {"kind": "q", "text": "로봇에 닿는\n마지막 걸음은?", "answer": "둘 중 하나"},
                  {"text": "승인: 사람이 rollout.py --manifest <Release 주소> — 가상 먼저, 실물(kind=real)은 마지막 단계\n자율: Pi 가 latest/manifest.json 을 10분마다 — state=ok · 03~05시 · 정식 릴리스만", "fs": 8.5},
                  {"kind": "end", "text": "장치: 내려받기 → sha256 → 슬롯 → 자가 점검 → current 전환\n(다음 장표)", "fs": 9.5},
              ],
              "bottom": "왜 이렇게: '내보낸다'는 결정은 사람이(태그), 함대 차원의 검증은 가상 50대가 릴리스마다, 실물은 지휘소 없이 스스로 — 노트북은 항상 켜 둘 수 없기 때문이다. 러너가 실물에 직접 배포하지 않는 이유: 러너는 집 안의 브로커에 닿지 못하고, 공개 저장소의 self-hosted runner 는 위험하며, 로봇이 태그 하나에 무인으로 바뀌면 안 된다. 출처: docs/RELEASE.md, .github/workflows/release.yml, DECISIONS 11/10",
              "next": "장치의 설치 — 게시된 파일을 장치는 어떻게 '반쯤 깔린 상태 없이' 설치하나? (ota_apply.install)"})
    # ---- 2/6 장치의 설치 (코드) ----
    a.append({"kind": "code", "section": SEC6, "title": "덧붙임 (11/10) — 장치의 설치: 내려받기 → sha256 → A/B 슬롯 → 자가 점검 → 원자적 전환 (ota_apply.install)", "file": ref(OA, 205, 234) + " (install 의 본체)",
              "crumb": "7부 왜·사고·방식 · 덧붙임 릴리스 → 배포 2/3 코드 (11/10)",
              "code": code(OA, 205, 234, dedent=4), "codeSize": 10, "pointsSize": 10.5,
              "points": ["한 줄이 한 단계: 내려받기 → 크기·sha256 → 풀기 → 자가 점검 → 전환 → 훅. _timed 가 단계마다 걸린 시간을 took_s 에 적고, stage 는 '어디까지 갔나'(텔레메트리의 ota_stage)",
                         "검증이 풀기보다 먼저 — 해시가 다르면 풀지도 않는다. 풀 때는 경로 탈출(../)과 링크 멤버를 거부한다(extract, 116-133줄)",
                         "자가 점검(selftest.sh: jitter_bench 0.5초)이 0 을 돌려줄 때만 전환. 실패하면 그 슬롯을 지우고 current 는 그대로 — 깨진 빌드를 '켜 보기 전에' 거른다",
                         "전환은 switch_current(168-175줄): 임시 링크를 만들고 os.replace 로 바꿔치기 → 어느 순간 전원이 꺼져도 current 는 옛 슬롯 아니면 새 슬롯",
                         "훅(post_switch.sh)이 실패하면 서버를 기다리지 않고 스스로 이전 슬롯으로(rollback, 237-246줄)",
                         "실측(Pi 4, 3회): 한 번에 0.98~1.62초 — 그중 자가 점검 0.67초, 검증 0.001초, 전환 0.001초 미만"],
              "foot": "출처: fleet/agent/ota_apply.py(250줄), docs/RELEASE.md 3절, DECISIONS 11/10. 한계: sha256 은 무결성이지 진위(서명)가 아니다 · 훅 실행 도중의 전원 차단은 복구하지 못한다",
              "next": "릴리스의 숫자 — 이 파이프라인을 실제로 돌리면 몇 초이고, 깨진 빌드는 몇 대에서 멈추나? (러너 2회 · 실물 Pi)"})
    # ---- 3/6 릴리스의 숫자 ----
    a.append({"kind": "kpi", "section": SEC6, "title": "덧붙임 (11/11) — 릴리스의 숫자: 태그에서 게시까지 2분 안, 깨진 빌드는 3 / 50 에서 멈춘다, 실물 Pi 의 설치 한 번은 약 1초",
              "crumb": "7부 왜·사고·방식 · 덧붙임 릴리스 → 배포 3/3 숫자 (11/11)",
              "kpis": [{"value": "1분 27초", "label": "태그 push → Release 게시 (v0.9.0)\nrc1 은 1분 52초 — 둘 다 첫 실행에 통과"},
                       {"value": "50 / 50", "label": "가상 50대에 진짜 설치 (러너)\n1.2 → 2.2 → 2.2초, 전체 14.6초"},
                       {"value": "3 / 50", "label": "깨진 패키지가 닿은 장치\n자가 점검이 거부, 롤백 1.0초"},
                       {"value": "약 1초", "label": "실물 Pi 4 의 설치 한 번 (0.98~1.62초)\n그중 자가 점검 0.67초"}],
              "bullets": ["읽는 법: 러너의 숫자에는 '장치의 다음 보고(1 Hz)까지 최대 1초'가 들어 있다 — 배포기는 장치의 다음 텔레메트리에서야 새 버전과 복귀를 안다. 0.05초마다 보고하는 장치로 잰 값(가짜 브로커, 11/10)은 0.6 → 1.0 → 1.2초, 롤백 0.2초였다. 설치 자체의 비용은 거의 전부 자가 점검(0.5초짜리 1 kHz 루프)이다",
                          "러너 두 번(진짜 Mosquitto, 가상 50대): rc1(11/11 08:59) 1.2 → 2.0 → 2.2초 · 전체 14.41초 · 거부 0.6초 뒤 롤백 1.0초 / v0.9.0(09:48) 1.2 → 2.2 → 2.2초 · 14.62초 · 거부 1.0초 뒤 롤백 1.0초. 전체에는 헬스 대기 3초 × 3 이 들어 있다. 합격선(50대 < 60초 · 첫 단계 3대에서 멈춤 · 롤백 < 5초)은 둘 다 통과",
                          "실물: 러너(ubuntu-24.04-arm)가 만든 aarch64 바이너리가 Pi 4 의 RT 커널에서 자가 점검 500주기 드롭 0 으로 통과했다(깨어남 p99 158 us). 시험용 슬롯에 설치해, 돌고 있는 서비스와 연속 기록은 건드리지 않았다. 정식 v0.9.0 은 Pi 서비스가 새벽 03~05시에 스스로 받는다 — 첫 자율 설치의 결과는 E22 에 적는다",
                          "정직한 줄: 첫 태그 전에 릴리스 경로를 처음부터 다시 읽다가 버그 하나를 찾았다 — 정상 릴리스가 두 번 깔린 장치에 깨진 패키지가 오면, 그것을 거부한 장치가 멀쩡한 현재 버전에서 한 세대 뒤로 내려갔다(롤백 가지의 순서). 시험은 전부 빈 슬롯에서 시작해 보이지 않았다 → 고치고 '정상 2번 → 깨진 것' 테스트를 더했다"],
              "fontSize": 11.5,
              "foot": "원본: docs/experiments/E22.md, docs/measurements/ota_release_v0.9.0_{good,bad}.json · ota_release_v0.9.0-rc1_{good,bad}.json(Release 자산 그대로), install_pi4_once_v0.9.0-rc1.json, selftest_pi4_v0.9.0-rc1.json. 한계: 실물 1대 · 서명 없음 · 노드 재시작 훅은 자리만",
              "next": "운영 층 — 릴리스는 GitHub 에서 받는다. 그러면 관제(브로커 · 수집기 · DB · 대시보드)는 어디에 있어야 하나? 노트북은 항상 켜 둘 수 없다"})
    # ---- 4/6 운영 층을 클라우드에 ----
    a.append({"kind": "kpi", "section": SEC6, "title": "덧붙임 (11/10~11) — 운영 층을 클라우드에: Pi 가 시드니 서버로 보고한 14.8시간, 53,167건 중 유실 0",
              "crumb": "7부 왜·사고·방식 · 덧붙임 클라우드 운영 층 (11/10~11)",
              "kpis": [{"value": "유실 0", "label": "53,167건 중 (Pi → 서버: 시드니)\n14.8시간 · 재시작 0 · 중복 0"},
                       {"value": "VM 1대", "label": "컨테이너 4개(브로커·수집기·DB·Grafana)\ndocker compose — K8s 는 쓰지 않았다"},
                       {"value": "8883", "label": "밖으로 연 MQTT 포트는 이것 하나\nTLS(자체 CA) + 비밀번호"},
                       {"value": "290 ms", "label": "서버까지 MQTT 왕복 (다다음 장표)\n대시보드 전달 지연 146.5 ms ≈ 편도"}],
              "bullets": ["왜 했나: 노트북은 항상 켜 둘 수 없다. 실물 Pi 의 텔레메트리를 쌓아 '돌아가는 주소'를 보이려면 운영 층이 항상 켜진 곳에 있어야 한다. 코드는 그대로 두고 접속 설정만 환경변수(FLEET_BROKER · PORT · TLS_CA · USER · PASS)로 읽게 했고(fleet/common/mqtt_conn.py), compose 에 운영 덮어쓰기 파일을 하나 더했다",
                          "무엇을 열고 닫았나: 인터넷에 열린 브로커는 ota 명령을 받는 문이다 → 암호화와 인증 없이는 열지 않는다. 내부 1883 과 DB 5432 는 컨테이너 네트워크 안에만, 대시보드(3000)와 ssh(22)는 내 IP 에만. 리전이 시드니인 것은 무료 플랜의 조건이고(운영이라면 장치와 가까운 서울) 그 값이 왕복 290 ms — 서버 왕복이 들어가는 숫자에는 '서버: 시드니'를 적는다",
                          "유실 0 을 무엇이 말하나: 대시보드는 '지금 온라인 1, 오류 0'까지만 보여 준다. 밤새 끊김이 없었다는 말은 장치가 붙인 일련번호(seq)를 서버에서 센 숫자가 한다 — 보냈어야 할 53,167 = 받은 53,167, 이웃한 기록의 가장 긴 간격 1.0초, offline 이벤트 0. 그 사이 수집기 재시작 1회와 Pi 의 자동 보안 업데이트(패키지 70개쯤)가 있었다",
                          "K8s 를 쓰지 않은 이유: 노드 1대 · 컨테이너 4개에 필요한 것(죽으면 다시 켜기 · 부팅 때 자동 시작 · 설정을 코드로 · 개발과 같은 구성)은 compose 로 된다. 바꿀 때는 수집기를 여러 대로 늘려야 할 때이고, 그 첫 걸음은 수집기를 상태 없는 복제본으로 만드는 것이다"],
              "fontSize": 11.5,
              "foot": "원본: docs/measurements/soak_pi-rt_20261111T0023Z.json(11/10 18:37 ~ 11/11 09:23), deploy/ec2/(README · setup.sh · soak_report.sh), fleet/docker-compose.prod.yml, mosquitto-prod.conf, DECISIONS 11/10 · 11/11. 한계: 비밀번호 하나를 모든 장치가 공유 · Grafana 는 HTTP · 서버 1대",
              "next": "사고와 해결 (3) — 설치 스크립트는 작업본에서 문법과 인증서까지만 확인했다. 실제 기계에서 처음 돌리자 무엇이 나왔나?"})
    # ---- 5/6 사고와 해결 (3) ----
    a.append({"kind": "table", "section": SEC6, "title": "덧붙임 (11/10~11) — 사고와 해결 (3): 실제 기계에서 처음 돌리자 나온 것, 그리고 같은 실수 두 번", "fontSize": 9.5,
              "crumb": "7부 왜·사고·방식 · 덧붙임 사고 3/3 (11/10~11)",
              "colW": [2.9, 4.5, 3.9, 1.0],
              "rows": [["무엇", "원인", "해결", "기록"],
                       ["서버 설치의 보존 정책 단계 실패(add_retention_policy does not exist)", "DB 컨테이너의 초기화용 임시 서버에 pg_isready 가 '준비됨'이라 답했다 — 11/04 CI 에서 겪은 것과 같은 원인을 새 스크립트에 다시 썼다", "'응답하는가'가 아니라 '확장 1 + 표 3 이 생겼는가'를 기다린다. 새로 쓸 때는 실패 사례 표부터 본다", "11/10"],
                       ["서버가 장치를 거부하는데 장치 화면은 정상 때와 똑같다", "여러 줄을 한꺼번에 붙여 넣어 비밀번호 입력(read -s)이 건너뛰어짐 → 0자", "한 줄씩 + 글자 수 확인. Pi 설치 스크립트가 빈 값·자리표시·공백을 서비스 등록 전에 거부", "11/10"],
                       ["Pi 에서 에이전트가 뜨지 않음", "paho 가 없었고 안내한 apt 패키지는 1.6(필요 2.0 이상) — 틀린 안내였다. pip 설치는 자동 보안 업데이트가 dpkg 잠금을 30분 넘게 쥐어 막혔다", "PyPI 의 순수 파이썬 휠을 받아 sha256 확인 뒤 사용자 폴더에(deploy/pi/get_paho.py)", "11/10"],
                       ["대시보드 '온라인 장치 4' (실제 1대), 지연 패널은 빨강", "수집기가 본 적 있는 장치 전부의 last_seen 을 매초 지금으로 덮어썼다. 패널은 색 기준이 없어 기본값(80)이 걸렸다", "최근 5초 안에 보낸 장치만, 그 장치의 마지막 도착 시각으로 + 테스트. 패널마다 색 기준을 명시", "11/10"],
                       ["CI 가 3시간 빨강 — 산출물 OTA 가 첫 장치에서 exit 127", "통합 테스트는 상대 경로 슬롯, 단위 테스트는 절대 경로만 썼다. 패치 다섯 개를 한꺼번에 push 하고 CI 를 보지 않았다(11/05 에 적은 규칙을 어겼다)", "설치·자가 점검·훅이 경로를 절대 경로로 굳힌다 + 상대 경로 테스트", "11/10"],
                       ["'다음 부팅도 RT 커널인가'의 확인 기준이 다음 날 서로 다른 답을 냈다", "/boot/vmlinuz 링크는 마지막에 설치된 패키지일 뿐, Pi 가 부팅 때 읽는 것은 /boot/firmware 의 파일", "부팅 파일의 sha256 을 RT 커널 파일과 직접 비교 — 기준은 '그 시스템이 실제로 읽는 것'으로", "11/11"],
                       ["깨진 패키지를 거부한 장치가 한 세대 뒤로 내려감 (실행 전에 찾음)", "ota_rollback 이 '이전 슬롯이 있는가'를 먼저 봤다 — 시험은 전부 빈 슬롯에서 시작해 우연히 옳은 가지로 갔다", "'직전 설치가 실패했는가'를 먼저 본다 + '정상 2번 → 깨진 것' 테스트", "11/11"],
                       ["서버까지 왕복 707 ms (같은 구간의 편도는 146 ms)", "보내는 간격 0.2초가 왕복보다 짧아 양쪽의 Nagle 이 붙잡았다 — 재는 방법이 만든 값", "기본 간격을 1초로 → 290 ms. 예측을 먼저 적고 검증(다음 장표)", "11/11"],
                       ["공개한 장표(pptx) 108번에 계정 이름이 남아 있었다", "11/06 의 점검은 git grep — pptx·docx 안(ZIP)은 보지 못한다. 장표 생성 코드 폴더도 .gitignore 의 build/ 에 걸려 저장소에 없었다", "pptx·docx 를 풀어서 보는 점검 스크립트 + 생성 코드를 저장소에", "11/11"]],
              "note": "배운 것: 실제 기계에서만 보이는 것(초기화 순서 · 패키지 버전 · OS 의 백그라운드 작업 · 사람이 붙여 넣는 방식 · 계속 켜 둔 서버)이 있다. 나온 것을 그날 스크립트·테스트·문서에 되돌려 넣는 것이 일이다. 사전 점검의 값: 서버·Pi 설치는 첫 실행에서 일곱 번 걸렸고, 미리 읽고 흉내 낸 릴리스 워크플로는 첫 실행에 통과했다. 출처: docs/LOG.md 11/10~11",
              "next": "왕복 290 ms — 여덟째 줄(707 ms)은 '틀린 숫자'였다. 숫자가 다른 숫자와 다툴 때 어떻게 갈랐나? (예측을 먼저 적고 쟀다)"})
    # ---- 6/6 왕복 290 ms (E23) ----
    a.append({"kind": "chain", "section": SEC6, "title": "덧붙임 (11/11) — 서버까지 왕복 290 ms: 첫 측정 707 ms 는 재는 방법이 만든 값 (예측을 먼저 적고 쟀다 — 넷 중 셋)", "perRow": 4, "nodeH": 1.3,
              "crumb": "7부 왜·사고·방식 · 덧붙임 왕복 290 ms — E23 (11/11)",
              "items": [
                  {"kind": "in", "text": "질문: Pi ↔ 시드니 브로커의 왕복은 몇 ms 인가\n대시보드의 전달 지연(146 ms)에는 두 시계의 차이가 섞인다 → 시계 하나로 재는 도구(mqtt_rtt.py)", "fs": 9},
                  {"text": "첫 측정: 0.2초 간격 × 300\n최소 285 / 중앙 707 / 최대 854 ms", "fs": 10},
                  {"kind": "q", "text": "편도 146 ms 와\n맞나?", "answer": "아니오: 707 이면 편도가 350 쯤이어야 한다"},
                  {"kind": "fail", "text": "가설: 간격(0.2초) < 왕복 → 양쪽의 Nagle 이 작은 쓰기를 붙잡았다\n모형(nagle_model.py) 285 / 710 / 860 — 첫 측정을 재현", "fs": 9},
                  {"kind": "do", "text": "설명만으로는 부족하다 → 다른 조건 넷의 값을 재기 전에 예측해 커밋(09:37)\n측정은 09:41~09:44", "fs": 9},
                  {"kind": "q", "text": "A  1초 간격\n예측 285 평평", "answer": "290 ✓ (60회 중 59회가 287~293)"},
                  {"kind": "q", "text": "D  0.35초 간격\n예측 285", "answer": "288 ✓ (꼬리 504 · 1,163)"},
                  {"kind": "q", "text": "B  0.2초 + NODELAY\n예측 460", "answer": "464 ✓ (네 숫자가 모형과 6 ms 안)"},
                  {"kind": "q", "text": "C  0.2초 재측정\n예측 710", "answer": "548 ✗ — 세 띠(694 → 473 → 597)"},
                  {"kind": "out", "text": "확정: 망의 왕복 290 ms (A·D 는 모형에 기대지 않는 직접 측정)\n대시보드 146.5 − 145.0 = 시계 차이 +1.5 ms", "fs": 9.5},
                  {"kind": "fail", "text": "틀린 것 둘을 그대로 남긴다\n모형의 C 예측(710 → 548) · 재기 전의 어림(왕복 130~160 ms — 두 배 틀림)", "fs": 9},
                  {"kind": "end", "text": "결정: 측정 간격은 왕복보다 길게(기본 1초)\n운영(1 Hz)은 무관 → NODELAY 는 지금 바꾸지 않는다", "fs": 9.5},
              ],
              "bottom": "읽는 법: 숫자가 다른 숫자와 다투면, 숫자를 고르기 전에 재는 방법을 의심한다. 모형이 첫 측정을 한 자리까지 맞혔어도 그것은 '설명'이지 '확인'이 아니다 — 재기 전에 예측을 적어 두니 맞은 것 셋과 틀린 것 하나가 갈렸다. 290 ms 는 모형이 아니라 1초 간격의 측정이 말한다. 출처: docs/experiments/E23.md, docs/measurements/rtt_pi_sydney_*.json(개별 값 포함), DECISIONS 11/11",
              "next": "끝 — 1~7부와 덧붙임을 한 줄기로 접으면: 결국 로봇은 이렇게 움직인다"})
    return a
