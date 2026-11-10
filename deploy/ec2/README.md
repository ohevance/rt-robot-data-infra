# 운영 층을 클라우드 VM 한 대에 — AWS EC2 에 관제 서버 올리기 (24시간, TLS + 인증)

> 한 줄 요약: 노트북은 항상 켜 둘 수 없다. 그래서 브로커·수집기·DB·Grafana(운영 층)를 EC2 한 대에 올려 24시간 돌리고, Pi 는 인터넷 너머로 **TLS(자체 CA) + 비밀번호**로 붙는다. 코드는 바뀌지 않고 환경변수(`FLEET_BROKER` 등)만 바뀐다. 비밀값은 저장소에 없다.

```
[Pi, 집]  pi_agent.py ──8883 TLS + 비밀번호──▶ [EC2: Mosquitto] ─1883(도커 내부)─▶ [수집기 QoS 1] ─▶ [TimescaleDB] ─▶ [Grafana :3000 로그인]
   │  밖으로 나가는 연결만 (공유기 설정 불필요)                                        보존 14일
   └── GitHub Release 의 manifest.json 을 스스로 읽어 업데이트 (서버와 무관)
[WSL]  rollout.py · virtual_fleet.py 도 같은 환경변수로 같은 브로커에 붙을 수 있다 (단계 배포 시연)
```

## 1. 왜 이 구성인가
| 결정 | 이유 | 버린 대안 |
|---|---|---|
| VM 1대 + 기존 `docker compose` | 운영 층이 이미 compose 한 벌이다. 옮기는 데 코드 변경이 없다 | AWS IoT Core·관리형 DB — 직접 만든 수집·배포 로직이 사라지고 시간이 든다 |
| 8883 만 공개, TLS + 비밀번호 | 인터넷에 열린 브로커는 암호화·인증 없이는 누구나 명령(`ota`)을 보낼 수 있다 | 1883 평문 공개 — 안 된다 |
| 자체 CA | 도메인이 없어도 된다. 장치에는 `ca.crt` 하나만 나눠 주면 되고 비용 0 | Let's Encrypt — 도메인 필요. 장치별 클라이언트 인증서(mTLS) — 더 강하지만 발급·폐기 절차가 필요해 다음 단계 |
| 내부 1883 은 도커 네트워크에만 | 수집기는 같은 VM 안에 있다. 밖으로 나가는 문만 잠근다 | 수집기도 TLS — 얻는 것 없이 설정만 는다 |
| DB(5432) 비공개, Grafana 로그인 | DB 는 밖에서 붙을 이유가 없다. 대시보드는 익명 보기를 끈다 | — |
| 보존 14일 | 디스크 20 GB. 가상 50대 1 Hz 를 계속 돌리면 하루 0.9 GB 쯤 쌓인다 | 무제한 — 3주면 찬다 |

한계(정직하게): 비밀번호 하나를 모든 장치가 같이 쓴다(장치별 계정·mTLS 는 다음). Grafana 는 HTTP 다 — 그래서 3000 은 내 IP 에만 연다. 서버 한 대라 서버가 죽으면 운영 층이 멈춘다(로봇은 계속 돌고, 텔레메트리는 1시간 버퍼).

## 2. 콘솔에서 할 일 (한 번, 약 15분)
1. **가입과 리전 — 완료(11/10)**: 새 가입 방식(AWS Builder ID)으로 가입했다. 무료 플랜에 자동 등록되고(크레딧 120달러, 2027-05-10 만료 — 가입 때 확인한 값) 루트 사용자가 없으며, **리전이 아시아 태평양(시드니) ap-southeast-2 로 고정**된다(콘솔에 리전 선택 메뉴가 없다 — 한국 연락처가 시드니에 배정됨). 서울(ap-northeast-2)은 고를 수 없다. 무료(시드니)로 시작하고, 필요하면 유료 전환 뒤 서울로 옮긴다(새 VM 에서 `setup.sh` 를 다시 돌리면 된다). 운영이라면 서울에 둔다(DECISIONS 11/10).
   - **MFA — 완료**: 루트 사용자가 없으므로 루트 MFA 단계는 없다. Builder ID 에 MFA(TOTP)와 복구 이메일을 등록했다.
2. **예산 알림 — 완료(11/10)**: 예산 둘 — **제로 지출 예산**(1센트라도 나가면 알림)과 **monthly-100**(월 100달러, 실제 비용의 30·50·100 % 에서 알림 = 30·50·100달러). 알림 이메일 확인함.
   - 예산 콘솔은 검색에 나오지 않았다 → `https://console.aws.amazon.com/cost-management/` 로 들어간다.
   - monthly-100 은 **크레딧을 제외**했다. 켜 두면 크레딧이 비용을 상쇄해 0 으로 보여 알림이 울리지 않는다. 설정 위치(예전의 체크박스가 아니다): 범위 옵션 → "특정 AWS 비용의 차원 필터링" → 차원 "요금 유형" → Excludes → Credit.
3. **EC2 → 인스턴스 시작**
   - 이름 `rt-fleet` · AMI **Ubuntu Server 24.04 LTS (64-bit x86)** · 유형 **t3.small**
   - 키 페어: 새로 만들기 → `rt-fleet` (.pem 내려받아 보관. 저장소에 넣지 않는다)
   - 네트워크: "보안 그룹 생성", 인바운드 규칙 셋
     | 유형 | 포트 | 소스 | 왜 |
     |---|---|---|---|
     | SSH | 22 | **내 IP** | 설치·관리 |
     | 사용자 지정 TCP | 8883 | 0.0.0.0/0 | 장치(MQTT TLS). 집 IP 가 바뀌어도 붙어야 한다 — TLS·비밀번호가 문지기 |
     | 사용자 지정 TCP | 3000 | **내 IP** | Grafana |
   - 스토리지 20 GiB gp3 → 시작.
4. **탄력적 IP(Elastic IP)를 붙인다 — `setup.sh` 를 돌리기 전에.** EC2 → 탄력적 IP → 주소 할당 → 방금 만든 인스턴스에 연결. 이유: 탄력적 IP 가 없으면 인스턴스를 중지했다 켤 때마다 공개 주소가 바뀌고, 그러면 서버 인증서(SAN 에 주소가 적혀 있다)와 Pi 의 `FLEET_BROKER` 를 다시 맞춰야 한다. 비용은 같다 — 공인 IPv4 는 탄력적이든 아니든 시간당 0.005달러이고, **인스턴스에 붙어 있지 않은 탄력적 IP 도 같은 요금**이 나가므로 인스턴스를 종료할 때는 주소도 "릴리스"한다.
   - 확인: 인스턴스 요약의 "탄력적 IP 주소" 칸에 값이 있고 "퍼블릭 IPv4 주소"와 같다.
5. 인스턴스의 **퍼블릭 IPv4 DNS**(ec2-…ap-southeast-2.compute.amazonaws.com)를 적어 둔다. 주소를 바꾸게 되면 `setup.sh` 를 다시 돌려 인증서를 새 주소로 만든다(`ca.crt` 는 그대로라 장치는 `FLEET_BROKER` 만 고친다).

## 3. 서버 설치 (SSH 한 번)
```bash
# [WSL 창]
chmod 600 ~/rt-fleet.pem
ssh -i ~/rt-fleet.pem ubuntu@<퍼블릭 DNS>
# [EC2 안]
curl -fsSL https://raw.githubusercontent.com/<owner>/<repo>/main/deploy/ec2/setup.sh | bash
cat ~/fleet-server-info.txt        # 브로커 주소·비밀번호·Grafana 비밀번호 (이 파일은 공유 금지)
```
`setup.sh` 가 하는 일: Docker 설치 → 저장소 받기 → 자체 CA·서버 인증서(SAN 에 이 VM 의 DNS·IP) → 브로커 비밀번호 → Grafana 비밀번호 → compose 올리기 → 보존 정책. 다시 돌려도 안전하다(비밀번호·CA 재사용).

## 4. 장치를 붙이기
```bash
# [WSL 창] CA 파일을 서버에서 받아 Pi 로
scp -i ~/rt-fleet.pem ubuntu@<퍼블릭 DNS>:~/rt-robot-data-infra/fleet/mosquitto/certs/ca.crt ~/fleet-ca.crt
scp ~/fleet-ca.crt <Pi>:~/fleet-ca.crt
# [Pi 창]
cd ~/rt-robot-data-infra && git pull
bash deploy/pi/install.sh                  # 처음엔 ~/.config/rt-fleet/fleet.env 를 만들고 멈춘다
nano ~/.config/rt-fleet/fleet.env          # FLEET_BROKER / FLEET_PASS / FLEET_TLS_CA / MANIFEST_URL 채우기
bash deploy/pi/install.sh                  # 서비스 등록·시작
journalctl --user -u rt-pi-agent -f
```
```bash
# [WSL 창] 같은 브로커로 가상 장치·배포기를 붙여 보기 (시연)
export FLEET_BROKER=<퍼블릭 DNS> FLEET_TLS_CA=~/fleet-ca.crt FLEET_USER=fleet FLEET_PASS=<비밀번호>
python3 fleet/agent/virtual_fleet.py --count 10 --slot-root build/devices
python3 fleet/ota/rollout.py --manifest https://github.com/<owner>/<repo>/releases/download/<태그>/manifest.json --db ""
```
확인: 브라우저에서 `http://<퍼블릭 DNS>:3000` (admin / `fleet-server-info.txt` 의 비밀번호) → Fleet Overview 에 `pi-rt` 가 보인다.

## 4b. 서버가 시드니에 있다는 것 — 숫자를 읽을 때
- 한국(Pi·WSL) ↔ 시드니는 왕복 지연이 서울 리전보다 크다(대략 130~160 ms 로 **예상**, 재기 전의 추정). 그래서 **서버 왕복이 들어가는 숫자**(텔레메트리 전달 지연, 장애 감지·복구 시간, 단계 배포의 적용·롤백 시간, 재접속 시간)를 이 서버로 잰 것에는 반드시 **"서버: 시드니"** 라고 적는다. WSL·러너에서 잰 기존 표③ 숫자와 섞어 비교하지 않는다.
- 지연과 무관한 것: 유실 0 여부, Pi 의 RT 지터(보드 안에서 잰다), 자율 업데이트(GitHub 에서 받는다).
- 왕복 지연 자체도 재서 적는다: `ping`/TCP 연결 시간, 그리고 수집기의 전달 지연(`recv − 장치 ts`).

## 5. 비용과 끄는 법
- t3.small 24시간 ≈ 월 19~20달러 + 디스크 2달러 + 공인 IPv4 3.6달러 ≈ **월 25달러 안팎**(추정 — 시드니 단가는 서울과 조금 다를 수 있으니 콘솔의 요금으로 확인). 이 계정의 크레딧은 **120달러(2027-05-10 만료)** 라서 t3.small 을 24시간 켜 두면 **약 4.8개월**분이다(120 ÷ 25). 6개월을 채우려면 중간에 t3.micro 로 내리거나(월 15달러 안팎, 메모리 1 GB 라 스왑 필요) 안 쓰는 기간에 중지한다. 제로 지출 예산이 크레딧 소진을 바로 알려 준다.
- 무료 플랜은 6개월 또는 크레딧 소진 때 계정이 닫힌다 → 그 전에 `docs/measurements/` 로 숫자를 옮기고 DB 덤프를 내려받는다.
- 안 쓸 때: 인스턴스 **중지**(디스크·IP 요금은 남는다) 또는 **종료**(전부 삭제) + **탄력적 IP 릴리스**(안 하면 IP 요금이 계속 나간다). 종료 전 `~/fleet-server-info.txt` 와 `ca.key` 는 필요하면 보관.

## 6. 파일
| 파일 | 역할 |
|---|---|
| `deploy/ec2/setup.sh` · `make_certs.sh` | 서버 설치 · 자체 CA/서버 인증서 |
| `fleet/docker-compose.prod.yml` · `fleet/mosquitto/mosquitto-prod.conf` | 운영 덮어쓰기(8883 TLS + 비밀번호, DB 비공개, Grafana 로그인, 수집기 상시) |
| `fleet/common/mqtt_conn.py` | 모든 MQTT 클라이언트의 TLS·인증(환경변수) |
| `deploy/pi/install.sh` · `rt-pi-agent.service` · `fleet.env.example` | Pi 서비스 등록 |
