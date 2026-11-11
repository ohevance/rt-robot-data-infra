# fleet — 관제: 장치 N대 → MQTT → 수집기 → TimescaleDB → Grafana + OTA + 장애 주입 (공고 ②③)

```
 [가상 장치 x50: virtual_fleet.py] ──┐
 [RT 노드 다리: ros_status_bridge.py] ─┼─MQTT (fleet/<id>/telemetry, 1 Hz)──▶ [Mosquitto] ──▶ [collector.py: 1초 묶음 COPY] ──▶ [TimescaleDB] ──▶ [Grafana :3000]
 [실물 Pi: pi_agent.py]               ┘        ▲                                   │  DB 죽으면 backlog 에 보관        └─ collector_stats (초당 메시지·적재 시간·전달 지연·backlog)
                                 끊기면 버퍼 ──┘ 재접속 시 QoS 1 재전송             │
 [ota/rollout.py] ──fleet/<id>/cmd {ota(+url,sha256) | ota_rollback}──▶ 장치 (5% → 50% → 100%, 헬스 게이트, 자동 롤백; 실물은 마지막)
                                                            장치: 내려받기 → sha256 → A/B 슬롯 → 자가 점검 → current 전환 (agent/ota_apply.py)
 [GitHub Release: manifest.json + tar.gz] ◀── release.yml (태그 → 빌드 → 가상 50대 카나리 → 게시)   Pi: pi_agent.py --auto-update 가 스스로 받는다
 [chaos/inject.py] ── docker stop mqtt / db · 수집기 kill · 나쁜 펌웨어 ──▶ 감지·복구·유실을 숫자로 (표③-2)
```

| 파일 | 역할 |
|---|---|
| `docker-compose.yml` | 브로커·DB·Grafana 컨테이너 3개 (+ 선택: 수집기 컨테이너 `--profile collector`) |
| `docker-compose.prod.yml` · `mosquitto/mosquitto-prod.conf` | 운영용 덮어쓰기(11/10): 밖으로는 8883 TLS + 비밀번호만, DB 비공개, Grafana 로그인, 수집기 상시 — 클라우드 VM 에 올릴 때(`deploy/ec2/README.md`) |
| `common/mqtt_conn.py` | 모든 MQTT 클라이언트의 TLS·인증을 환경변수 한 곳에서(`FLEET_BROKER` · `FLEET_PORT` · `FLEET_TLS_CA` · `FLEET_USER` · `FLEET_PASS`). 아무것도 안 주면 개발 모드(localhost:1883) |
| `db/init.sql` · `db/migrations/` · `db/migrate.py` | 스키마 · 이미 떠 있는 DB 에 새 표/컬럼 추가(002 OTA, 003 수집기 내성) |
| `agent/device_agent.py` | 장치 한 대: 텔레메트리 발행, 끊기면 버퍼 → 재접속 시 재전송, 유언(LWT), 명령 수신(ping·health·ota·ota_rollback) |
| `agent/virtual_fleet.py` | 가상 장치 N대 (`--keepalive`, `--telemetry-qos 0|1`) |
| `agent/ros_status_bridge.py` | `/rt_status` → 장치 `rt-node-1` 로 (RT 노드가 51번째 장치. 상태 머신 이름이 장치 state 로) |
| `agent/ota_apply.py` | 장치의 진짜 설치(11/10): 내려받기 → sha256 → A/B 슬롯 → 자가 점검 → `current` 원자적 전환 → 훅, 롤백 — `docs/RELEASE.md` 3절 |
| `agent/pi_agent.py` | 실물 보드 에이전트(ROS 없이): 보드의 진짜 온도·CPU·메모리를 1 Hz 로, 자율 업데이트(`--auto-update`) |
| `collector/collector.py` | 구독 → 파싱 → 1초 묶음 적재 + 통계. DB 끊기면 backlog, `--qos 1` 이면 지속 세션 |
| `ota/rollout.py` | OTA 단계 배포 + 헬스 게이트 + 자동 롤백, 롤백 시간 측정 |
| `chaos/inject.py` · `chaos/assert_results.py` | 장애 주입 4종(broker·db·collector·bad_firmware) → JSON · 기대대로 복구됐는지 판정 |
| `tools/diag.py` | DB 진단: 오프라인 이벤트 분류, 전달 지연 튐 주기 |
| `tools/mqtt_rtt.py` · `tools/nagle_model.py` | MQTT 왕복 시간: 보내고 브로커를 거쳐 자기가 받는다 — 시계 하나로 잰다(대시보드의 전달 지연은 두 시계의 차이가 섞인다). 결과에 서버 주소를 적지 않는다 · 보내는 간격이 왕복보다 짧을 때 값이 커지는 까닭을 옮긴 모형(E23) |
| `grafana/` | 데이터 소스·대시보드 자동 등록 (`make_dashboard.py` 가 JSON 생성) |
| `tests/` | 브로커·DB 없이 도는 단위 테스트 4파일 26건(가짜 브로커 `fake_mqtt.py`·가짜 DB `fake_psycopg.py`) + 진짜 컨테이너로 도는 `integration.sh`(장애 3종 + OTA + 산출물 OTA) · 릴리스 카나리 `release_canary.sh`(가상 50대, 태그 때) |

## 0. 단위 테스트 (어디서나, 1분)
```bash
python3 fleet/tests/test_fleet_logic.py            # 파싱·버퍼·명령·OTA·유언 → "OK: fleet logic"
python3 fleet/tests/test_ota_rollout.py            # 가상 20대 위에서 정상 배포 / 나쁜 펌웨어 롤백 / 적용 시간 초과 → "OK: ota rollout"
python3 fleet/tests/test_ota_artifact.py           # 진짜 설치(로컬 HTTP + tar.gz): sha 불일치·자가 점검 실패·롤백·함대 20대·자율 업데이트·아키텍처·훅 → "OK: ota artifact"
python3 fleet/tests/test_collector_resilience.py   # DB 죽음→backlog→복귀, 상한, 지속 세션 옵션 → "OK: collector resilience"
```

## 1. 한 번만: 파이썬 의존성
```bash
cd ~/rt-robot-data-infra
python3 -m venv .venv && source .venv/bin/activate
pip install -r fleet/requirements.txt
```

## 2. 서버 올리기 (터미널 1)
```bash
cd ~/rt-robot-data-infra
docker compose -f fleet/docker-compose.yml up -d
docker compose -f fleet/docker-compose.yml ps        # 3개 모두 running 이면 됨 (db 는 처음 20초쯤 걸림)
python3 fleet/db/migrate.py                           # 이미 떠 있던 DB 에 새 표/컬럼 추가 (처음 뜬 DB 는 "skip" 만 나옴)
```
Grafana: 브라우저에서 http://localhost:3000 → 대시보드 "Fleet Overview" (로그인 없이 보임. 편집은 admin/admin)

## 3. 수집기 (터미널 2)
```bash
cd ~/rt-robot-data-infra && source .venv/bin/activate
python3 fleet/collector/collector.py            # 기본 (QoS 0)
python3 fleet/collector/collector.py --qos 1    # 지속 세션: 수집기가 잠깐 죽어도 브로커가 메시지를 들고 있는다 (장치도 --telemetry-qos 1 이어야 함)
```
1초마다 한 줄: `msgs/s=  50  online=  50  insert=   12.3 ms  transit ms p50=510 p95=980 max=1010  bad=0  backlog=0  db_err=0`
- `transit` = 장치 측정 → 수집기 도착 (전달 지연). DB 에 보이기까지는 1초 묶음이 최대 1초 더 걸린다.
- `backlog` = DB 에 못 넣고 들고 있는 행 수. DB 가 죽으면 올라가고 돌아오면 0 으로.

## 4. 가상 장치 50대 (터미널 3)
```bash
cd ~/rt-robot-data-infra && source .venv/bin/activate
python3 fleet/agent/virtual_fleet.py --count 50 --rate 1.0                      # 기본
python3 fleet/agent/virtual_fleet.py --count 50 --rate 1.0 --telemetry-qos 1    # 수집기 --qos 1 과 짝
```
Grafana 에 50대가 올라오고 초당 메시지 50 이 보이면 성공. 300대도 같은 명령(`--count 300`).

## 5. OTA 단계 배포 (터미널 4)
```bash
python3 fleet/ota/rollout.py --version 1.1.0              # 흉내(버전 문자열만): 5% → 50% → 100%, 각 단계 헬스 5초 관찰. 약 30초
python3 fleet/ota/rollout.py --version 1.2.0-bad --bad    # 나쁜 펌웨어 흉내: 5%(3대)에서 fault → 롤백. 롤백 시간이 찍힌다
# 진짜 산출물(11/10 —): 가상 장치를 --slot-root 로 띄웠을 때. 패키지는 scripts/package_release.sh (docs/RELEASE.md 5절)
python3 fleet/ota/rollout.py --manifest build/release/manifest.json          # 로컬 파일. 장치가 내려받기·sha256·A/B 슬롯·자가 점검·전환
python3 fleet/ota/rollout.py --manifest https://github.com/<owner>/<repo>/releases/download/v1.2.0/manifest.json   # 게시된 릴리스
python3 fleet/ota/rollout.py --manifest build/release/manifest-bad.json      # 자가 점검이 실패하는 패키지 → 첫 단계에서 거부·롤백
```
결과 JSON `docs/measurements/ota_<version>.json`, DB `ota_rollouts` 표, 이벤트 `events(kind='ota')`. Grafana 장치 표에서 fw_version 이 바뀌는 것이 보인다.
가상 장치를 진짜 설치 경로로 띄우려면 `python3 fleet/agent/virtual_fleet.py --count 50 --slot-root build/devices`(장치마다 폴더). 실물 Pi 는 `fleet/agent/pi_agent.py`(`docs/RELEASE.md` 5절).

## 6. 장애 주입 4종 (터미널 4) — 표③-2
```bash
python3 fleet/chaos/inject.py --fault broker --duration 10          # 브로커 10초 중단 → 장치 버퍼 → 재전송. 유실 0 기대
python3 fleet/chaos/inject.py --fault db --duration 10              # DB 10초 중단 → 수집기 backlog → 복귀 적재. 유실 0 기대
python3 fleet/chaos/inject.py --fault collector --duration 10 --label qos0   # 수집기 죽임 (QoS 0 이면 그 동안 유실 — 숫자로 남긴다)
python3 fleet/chaos/inject.py --fault collector --duration 10 --label qos1   # 수집기 --qos 1 + 장치 --telemetry-qos 1 로 다시: 유실 0
python3 fleet/chaos/inject.py --fault bad_firmware                  # 나쁜 펌웨어 → 5% 에서 롤백
python3 fleet/chaos/assert_results.py docs/measurements/fault_*.json   # 기대대로였나 판정
```
각 장애마다 기준선(장치 수·msgs/s) → 주입 → 감지 시각 → 복구 시각 → 15초 뒤 유실(장애 직전 seq 기준) 계산 → `docs/measurements/fault_<fault>.json`.
브로커 설정을 바꾼 뒤(persistence 등)에는 `docker compose -f fleet/docker-compose.yml up -d mqtt` 로 컨테이너를 다시 만들어야 적용된다.
`collector` 장애는 수집기가 호스트 프로세스면 SIGTERM 후 같은 명령으로 다시 띄운다(출력 `fleet/logs/collector_restarted.log`). 컨테이너(`--profile collector`)면 docker stop/start.
재시작된 수집기는 터미널이 아니라 배경에서 돈다. 다시 터미널에서 보고 싶으면 `kill -TERM $(cat fleet/logs/collector.lock)` 으로 곱게 끝낸 뒤(마지막 적재 후 종료) 터미널 2 에서 다시 띄운다.
**수집기는 한 번에 하나만** — 둘이 뜨면 같은 client_id 를 서로 밀어내 2초마다 재접속한다. 두 번째는 잠금 파일을 보고 스스로 물러난다.

## 7. 표③ 만들기
```bash
python3 scripts/make_table3.py --minutes 10 --label "가상 50대 1 Hz" --out docs/measurements/table3.md
cat docs/measurements/table3.md     # ③-1 처리량·전달 지연·유실, ③-2 장애 주입, ③-3 OTA
```

## 8. 진단 (D2 에서 본 이상 두 가지)
```bash
python3 fleet/tools/diag.py --minutes 15     # A) offline 이벤트 분류(진짜 끊김/가짜/정상 종료) B) 전달 지연 튐 간격 → keepalive 가설 등
python3 fleet/agent/virtual_fleet.py --count 50 --keepalive 30    # 튐 간격이 10초 → 30초로 바뀌면 keepalive(PINGREQ) 가설 확정
```

## 9. RT 노드를 51번째 장치로 (ROS 2 환경 터미널)
```bash
source /opt/ros/jazzy/setup.bash && source install/setup.bash && source .venv/bin/activate
python3 fleet/agent/ros_status_bridge.py --device-id rt-node-1     # rt_control_node 가 떠 있어야 함. state 에 READY/RUNNING/FAULT 가 올라간다
```

## 10. 통합 테스트 한 번에 (CI 2단계와 같은 스크립트, 약 4분)
```bash
bash fleet/tests/integration.sh      # mqtt·db 컨테이너 → 수집기(qos 1) + 가상 10대 → 장애 3종 + 롤백 + 정상 OTA → 판정 → build/integration/table3_ci.md
```
(기존 수집기·가상 장치가 떠 있으면 먼저 끈다. 컨테이너는 끝나도 그대로 둔다. `KEEP=0` 이면 내린다)

## 끄기
```bash
docker compose -f fleet/docker-compose.yml down        # 데이터 유지
docker compose -f fleet/docker-compose.yml down -v     # 데이터까지 삭제 (init.sql 이 다시 돌아 새 표가 다 생긴다)
```
