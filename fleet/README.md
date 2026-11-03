# fleet — 관제: 장치 N대 → MQTT → 수집기 → TimescaleDB → Grafana (공고 ②③)

```
 [가상 장치 x50: virtual_fleet.py] ──┐
 [RT 노드 다리: ros_status_bridge.py] ─┼─MQTT (fleet/<id>/telemetry, 1 Hz)──▶ [Mosquitto] ──▶ [collector.py: 1초 묶음 COPY] ──▶ [TimescaleDB] ──▶ [Grafana :3000]
 [실물 Pi (나중에)]                   ┘                                                               └─ collector_stats (초당 메시지·적재 시간·수집 지연)
```

| 파일 | 역할 |
|---|---|
| `docker-compose.yml` | 브로커·DB·Grafana 컨테이너 3개 |
| `db/init.sql` | 스키마: devices · telemetry(하이퍼테이블) · events · collector_stats |
| `agent/device_agent.py` | 장치 한 대: 텔레메트리 발행, 끊기면 버퍼 → 재접속 시 재전송, 유언(LWT), 명령 수신 |
| `agent/virtual_fleet.py` | 가상 장치 N대 |
| `agent/ros_status_bridge.py` | `/rt_status` → 장치 `rt-node-1` 로 (RT 노드가 51번째 장치) |
| `collector/collector.py` | 구독 → 파싱 → 1초 묶음 적재 + 통계 |
| `grafana/` | 데이터 소스·대시보드 자동 등록 (`make_dashboard.py` 가 JSON 생성) |
| `tests/test_fleet_logic.py` | 브로커·DB 없이 도는 단위 테스트 |

## 1. 한 번만: 파이썬 의존성
```bash
cd ~/rt-robot-data-infra
python3 -m venv .venv && source .venv/bin/activate
pip install -r fleet/requirements.txt
python3 fleet/tests/test_fleet_logic.py      # "OK: fleet logic"
```

## 2. 서버 올리기 (터미널 1)
```bash
cd ~/rt-robot-data-infra
docker compose -f fleet/docker-compose.yml up -d
docker compose -f fleet/docker-compose.yml ps        # 3개 모두 running 이면 됨 (db 는 처음 20초쯤 걸림)
```
Grafana: 브라우저에서 http://localhost:3000 → 대시보드 "Fleet Overview" (로그인 없이 보임. 편집은 admin/admin)

## 3. 수집기 (터미널 2)
```bash
cd ~/rt-robot-data-infra && source .venv/bin/activate
python3 fleet/collector/collector.py
```
1초마다 한 줄: `msgs/s=  50  online=  50  insert=   12.3 ms  ingest_latency ms p50=510 p95=980 max=1010  bad=0`

## 4. 가상 장치 50대 (터미널 3)
```bash
cd ~/rt-robot-data-infra && source .venv/bin/activate
python3 fleet/agent/virtual_fleet.py --count 50 --rate 1.0
```
Grafana 에 50대가 올라오고 초당 메시지 50 이 보이면 성공. 300대도 같은 명령(`--count 300`).

## 5. 끊김·재전송 시험 (터미널 4)
```bash
docker compose -f fleet/docker-compose.yml stop mqtt     # 브로커를 10초쯤 죽인다
sleep 10
docker compose -f fleet/docker-compose.yml start mqtt
```
→ 수집기 msgs/s 가 0 으로 떨어졌다가, 브로커가 돌아오면 밀린 메시지가 몰려 들어오고(버퍼 재전송) 다시 50 으로. 가상 장치 종료 시 `buffered=... flushed=...` 가 같은 수.

## 6. 표③ 만들기
```bash
python3 scripts/make_table3.py --minutes 5 --label "가상 50대 1 Hz" --out docs/measurements/table3.md
cat docs/measurements/table3.md
```

## 7. RT 노드를 51번째 장치로 (ROS 2 환경 터미널)
```bash
source /opt/ros/jazzy/setup.bash && source install/setup.bash && source .venv/bin/activate
python3 fleet/agent/ros_status_bridge.py --device-id rt-node-1     # rt_control_node 가 떠 있어야 함
```

## 끄기
```bash
docker compose -f fleet/docker-compose.yml down        # 데이터 유지
docker compose -f fleet/docker-compose.yml down -v     # 데이터까지 삭제
```
