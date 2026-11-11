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
1. **가입과 리전 — 완료(11/10)**: 새 가입 방식(AWS Builder ID)으로 가입했다. 무료 플랜에 자동 등록되고(크레딧은 가입 때 120달러였고 콘솔의 안내 활동 5개 중 4개를 마친 뒤 **180달러**, 2027-05-10 만료 — 11/10 콘솔에서 확인) 루트 사용자가 없으며, **리전이 아시아 태평양(시드니) ap-southeast-2 로 고정**된다(콘솔에 리전 선택 메뉴가 없다 — 한국 연락처가 시드니에 배정됨). 서울(ap-northeast-2)은 고를 수 없다. 무료(시드니)로 시작하고, 필요하면 유료 전환 뒤 서울로 옮긴다(새 VM 에서 `setup.sh` 를 다시 돌리면 된다). 운영이라면 서울에 둔다(DECISIONS 11/10).
   - **MFA — 완료**: 루트 사용자가 없으므로 루트 MFA 단계는 없다. Builder ID 에 MFA(TOTP)와 복구 이메일을 등록했다.
2. **예산 알림 — 완료(11/10)**: 예산 둘 — **제로 지출 예산**(1센트라도 나가면 알림)과 **monthly-100**(월 100달러, 실제 비용의 30·50·100 % 에서 알림 = 30·50·100달러). 알림 이메일 확인함.
   - 예산 콘솔은 검색에 나오지 않았다 → `https://console.aws.amazon.com/cost-management/` 로 들어간다.
   - monthly-100 은 **크레딧을 제외**했다. 켜 두면 크레딧이 비용을 상쇄해 0 으로 보여 알림이 울리지 않는다. 설정 위치(예전의 체크박스가 아니다): 범위 옵션 → "특정 AWS 비용의 차원 필터링" → 차원 "요금 유형" → Excludes → Credit.
3. **EC2 → 인스턴스 시작**
   - 이름 `rt-fleet` · AMI **Ubuntu Server 24.04 LTS (64-bit x86)** · 유형 **t3.small**
   - AMI 를 바꾸면 "현재 설정 중 일부가 변경되거나 제거됩니다" 확인 창이 뜨고 **스토리지·보안 그룹 설정이 초기화**된다 → AMI 를 먼저 정하고 나머지를 채운다. 요약 패널의 AMI 가 24.04 인지 본다(기본값은 더 새 버전일 수 있다).
   - 키 페어: 새로 만들기 → `rt-fleet` (RSA, .pem 내려받아 보관. 다시 받을 수 없다. 저장소에 넣지 않는다)
   - 네트워크: "보안 그룹 생성". 시작 화면에서는 **SSH 를 "내 IP"로** 만 정하고(HTTP/HTTPS 는 체크하지 않는다), 나머지 둘은 인스턴스가 뜬 뒤 인스턴스 → 보안 탭 → 보안 그룹 → "인바운드 규칙 편집"에서 더한다. 소스 유형에서 "내 IP"를 고르면 주소가 자동으로 들어간다. 최종 규칙 셋
     | 유형 | 포트 | 소스 | 왜 |
     |---|---|---|---|
     | SSH | 22 | **내 IP** | 설치·관리 |
     | 사용자 지정 TCP | 8883 | 0.0.0.0/0 | 장치(MQTT TLS). 집 IP 가 바뀌어도 붙어야 한다 — TLS·비밀번호가 문지기 |
     | 사용자 지정 TCP | 3000 | **내 IP** | Grafana |
   - 스토리지 20 GiB gp3 → 시작. (집 인터넷의 공인 IP 가 바뀌면 SSH·Grafana 가 갑자기 안 된다 → 22·3000 규칙의 소스를 다시 "내 IP"로 저장. 8883 은 영향 없다)
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
`setup.sh` 가 하는 일: Docker 설치 → 저장소 받기 → 자체 CA·서버 인증서(SAN 에 이 VM 의 DNS·IP) → 브로커 비밀번호 → Grafana 비밀번호 → compose 올리기 → 보존 정책. 다시 돌려도 안전하다(비밀번호·CA 재사용). 3~4분 걸린다(11/10 첫 실행).

확인 (서버 안에서):
```bash
cd ~/rt-robot-data-infra
sudo docker compose -f fleet/docker-compose.yml -f fleet/docker-compose.prod.yml ps     # 4개 Up, 밖으로 열린 포트는 8883·3000 뿐
sudo docker logs --tail 5 fleet_collector                                              # msgs/s=0 online=0 … db_err=0 (장치를 붙이기 전)
```
- 브로커 로그의 `per_listener_settings … deprecated` 경고 두 줄은 동작에 영향이 없다(이미지 `eclipse-mosquitto:2` 가 2.1 계열로 올라가며 생긴 안내). 새 문법으로 옮기는 일은 브로커를 띄워 인증이 그대로인지 확인할 수 있을 때 한다 — 잠긴 문의 설정을 확인 없이 바꾸지 않는다.
- 11/10 첫 실행에서 8단계(보존 정책)가 실패했다 — DB 초기화가 끝나기 전에 명령을 보냈다(같은 날 고침: 확장과 표가 생길 때까지 기다린다). 그런 일이 다시 생기면 스크립트를 한 번 더 돌리면 된다.

## 4. 장치를 붙이기
```bash
# [WSL 창] CA 파일을 서버에서 받아 Pi 로  (H = 퍼블릭 DNS. ssh·scp 에서만 앞에 ubuntu@ 를 붙인다)
H=<퍼블릭 DNS>
scp -i ~/rt-fleet.pem ubuntu@$H:~/rt-robot-data-infra/fleet/mosquitto/certs/ca.crt ~/fleet-ca.crt
scp ~/fleet-ca.crt <Pi>:~/fleet-ca.crt
# [Pi 창]
cd ~/rt-robot-data-infra && git pull
bash deploy/pi/install.sh                  # 처음엔 ~/.config/rt-fleet/fleet.env 를 만들고 멈춘다
F=~/.config/rt-fleet/fleet.env             # 값 넷을 채운다 — 편집기 대신 명령으로 (비밀번호가 화면·명령 기록에 남지 않는다)
sed -i "s|^FLEET_TLS_CA=.*|FLEET_TLS_CA=$HOME/fleet-ca.crt|" $F
sed -i "s|^MANIFEST_URL=.*|MANIFEST_URL=https://github.com/<owner>/<repo>/releases/latest/download/manifest.json|" $F
read -p "서버 주소: " H                     # ← 이 줄만 실행하고 주소를 붙여 넣는다 (여러 줄을 한꺼번에 붙이면 입력을 건너뛴다)
sed -i "s|^FLEET_BROKER=.*|FLEET_BROKER=$H|" $F
read -s -p "FLEET_PASS: " P                # ← 이 줄만 실행하고 비밀번호를 붙여 넣는다 (화면에 안 보인다)
echo; sed -i "s|^FLEET_PASS=.*|FLEET_PASS=$P|" $F; unset P
awk -F= '/^FLEET_PASS=/{print "FLEET_PASS=(" length($2) "자)"; next} /^[A-Z]/{print}' $F     # 확인 — 비밀번호는 글자 수만
bash deploy/pi/install.sh                  # paho-mqtt 2.x 가 없으면 받아 오고, 값이 비었으면 멈추고, 서비스 등록·시작
journalctl --user -u rt-pi-agent -n 20 --no-pager
```
- `git pull` 이 "untracked working tree files would be overwritten" 으로 멈추면: Pi 에서 잰 측정 파일이 Pi 에 그대로 남아 있고 같은 파일이 WSL 을 거쳐 저장소에 올라간 것이다. 지우지 말고 옮긴 뒤 다시 받는다 — `mkdir -p ~/pi-measure-backup && git ls-files --others --exclude-standard docs/measurements | xargs -I{} mv {} ~/pi-measure-backup/ && git pull`.
- **Pi 의 자동 보안 업데이트(unattended-upgrade)**: 오래 꺼 두었다 켜면 수십 개 패키지를 30분 넘게 올리고 그동안 `apt` 가 잠긴다(끊지 않는다 — 기다리거나 apt 가 필요 없는 길로 간다). 목록에 일반 커널(`linux-image-raspi`)이 들어 있을 수 있다. **재부팅 전에** 다음 부팅 커널이 RT 인지 본다 — Pi 가 부팅 때 읽는 것은 `/boot/firmware/` 의 `vmlinuz`·`initrd.img` 이므로 그 둘이 RT 커널의 파일과 같은지 해시로 비교한다:
  ```bash
  sudo -v                                    # 비밀번호를 먼저 (여러 줄을 붙여 넣을 때 입력을 건너뛰지 않게)
  K=$(uname -r)                              # 지금 도는 커널 (…-raspi-realtime 이어야 한다)
  for f in vmlinuz initrd.img; do
    a=$(sudo sha256sum /boot/$f-$K | cut -c1-16); b=$(sudo sha256sum /boot/firmware/$f | cut -c1-16)
    [ "$a" = "$b" ] && echo "$f 일치 → 다음 부팅도 $K" || echo "$f 불일치 (boot=$a firmware=$b) — 재부팅하지 말 것"
  done
  loginctl show-user "$USER" -p Linger       # Linger=yes 여야 재부팅 뒤 로그인 없이 에이전트가 뜬다
  ```
  **`ls -l /boot/vmlinuz` 로 판단하지 않는다**(11/11 에 고친 안내): 그 링크는 "마지막에 설치된 커널 패키지"를 가리킬 뿐이다. 11/10 의 자동 업데이트 뒤 링크는 일반 커널(`6.8.0-1065-raspi`)을 가리켰지만 `/boot/firmware` 의 파일은 RT 커널(`6.8.0-2054-raspi-realtime`)과 해시가 같았다. 커널을 부팅 영역에 복사하는 도구(flash-kernel)가 설치된 것 중 **버전이 가장 높은 것**을 고르기 때문이다(업데이트 로그: `A higher version (6.8.0-2054-raspi-realtime) is still installed, no reflashing required`). 반대로 말하면 일반 커널의 번호가 RT 보다 높아지는 날에는 일반 커널로 뜬다 — 그래서 재부팅 전에 해시를 본다.
```bash
# [WSL 창] 같은 브로커로 가상 장치·배포기를 붙여 보기 (시연)
export FLEET_BROKER=<퍼블릭 DNS> FLEET_TLS_CA=~/fleet-ca.crt FLEET_USER=fleet FLEET_PASS=<비밀번호>
python3 fleet/agent/virtual_fleet.py --count 10 --slot-root build/devices
python3 fleet/ota/rollout.py --manifest https://github.com/<owner>/<repo>/releases/download/<태그>/manifest.json --db ""
```
확인: 서버에서 `sudo docker logs --tail 5 fleet_collector` 가 `msgs/s=1 online=1`, 브라우저에서 `http://<퍼블릭 DNS>:3000` → Dashboards → Fleet Overview 의 장치 목록에 `pi-rt`(state ok), 온도 그래프에 보드의 실제 온도.
- Grafana 로그인은 **아이디 `admin`** + `fleet-server-info.txt` 의 `GRAFANA=` 줄 괄호 안 비밀번호다. AWS 계정·이메일과 무관하다(브라우저가 저장된 이메일을 자동으로 채우면 지우고 넣는다). `https://` 가 아니라 `http://`.
- 비밀번호를 환경변수로 넣을 때는 `read -s -p "FLEET_PASS: " FLEET_PASS` **한 줄만** 실행하고 붙여 넣은 뒤 `export FLEET_PASS; echo ${#FLEET_PASS}` 로 글자 수(20)를 본다. 0 이면 빈 비밀번호로 접속을 시도하고 서버가 거부한다(클라이언트 화면만으로는 구분이 안 된다 — 서버의 수집기 로그로 확인).

## 4b. 서버가 시드니에 있다는 것 — 숫자를 읽을 때
- 한국(Pi·WSL) ↔ 시드니는 왕복 지연이 서울 리전보다 크다. 재기 전에는 130~160 ms 로 **어림**했는데 틀렸다 — 11/11 첫 측정에서 집(Wi-Fi)의 Pi → 이 서버의 MQTT 왕복은 **최소 285 ms**(편도 약 142 ms)로 보인다(확정 전: `docs/experiments/E23.md`). 그래서 **서버 왕복이 들어가는 숫자**(텔레메트리 전달 지연, 장애 감지·복구 시간, 단계 배포의 적용·롤백 시간, 재접속 시간)를 이 서버로 잰 것에는 반드시 **"서버: 시드니"** 라고 적는다. WSL·러너에서 잰 기존 표③ 숫자와 섞어 비교하지 않는다.
- 지연과 무관한 것: 유실 0 여부, Pi 의 RT 지터(보드 안에서 잰다), 자율 업데이트(GitHub 에서 받는다).
- 왕복 지연은 **MQTT 왕복**으로 잰다 — `fleet/tools/mqtt_rtt.py`: 한 클라이언트가 보내고 브로커를 거쳐 자기가 다시 받는 시간을 시계 하나로 잰다(TLS·비밀번호·브로커를 장치와 같은 길로 지난다. `ping` 은 보안 그룹이 막고 브로커를 지나지 않는다).
  ```bash
  # [Pi 창] 서비스와 같은 설정으로. 에이전트는 그대로 돈다 (client id 가 달라 서로 건드리지 않는다)
  set -a; . ~/.config/rt-fleet/fleet.env; set +a
  python3 fleet/tools/mqtt_rtt.py --from-label "Pi 4 (집, Wi-Fi)" --out ~/rtt_pi_sydney.json     # 1초 간격 × 100 = 100초. 결과 파일에 서버 주소는 없다
  ```
  **보내는 간격은 왕복보다 길게.** 0.2초 간격으로 재면 왕복(0.285초)보다 짧아 TCP 의 Nagle 이 메시지를 붙잡고, 값이 최소 285 / 중앙 707 / 최대 854 ms 로 커진다 — 망이 아니라 재는 방법이 만든 값이다(E23). 그래서 기본 간격이 1초다.
- 밤샘·며칠 기록은 **세어서** 본다 — `deploy/ec2/soak_report.sh`(서버 안에서): 장치의 일련번호로 보냈어야 할 수·받은 수·빠진 수, 에이전트 재시작 횟수와 그때의 공백, 가장 긴 간격을 JSON 으로 낸다. 그래프는 "끊긴 것처럼 안 보인다"까지만 말해 준다.
  ```bash
  # [EC2 안]
  cd ~/rt-robot-data-infra && git pull && bash deploy/ec2/soak_report.sh pi-rt          # → ~/soak_pi-rt_<UTC시각>.json
  # [WSL 창] 저장소로 가져오기 (비밀값 없음)
  scp -i ~/rt-fleet.pem "ubuntu@$H:~/soak_pi-rt_*.json" docs/measurements/
  ```
  첫 밤(11/10 18:37 ~ 11/11 09:23, 14.77 시간): **53,167건 중 유실 0**, 중복 0, 재시작 0, 장치 쪽 가장 긴 간격 1.0초, 서버가 못 받은 가장 긴 시간 1.6초, offline 이벤트 0 — 그 사이 수집기 재시작 1회 포함(`docs/measurements/soak_pi-rt_20261111T0023Z.json`, 스크립트의 첫 실행. 아침에 손으로 센 `soak_pi_sydney_20261111_0843.json` 과 같은 결론).
- **전달 지연(`transit`)에는 두 시계의 차이가 섞여 있다.** 장치가 찍은 시각과 서버가 받은 시각을 빼기 때문이다. 11/10 첫 관찰: WSL 의 가상 장치 3대 p50 184 / p95 200 ms, Pi p95 151 ms 안팎 — 같은 서버인데 보내는 쪽에 따라 30~50 ms 다르다는 것 자체가 시계 차이가 섞였다는 표시다. 이 값은 왕복 시간과 맞춰 보기 전에는 "지연"으로 인용하지 않는다. 11/11 에 맞춰 본 결과(E23, 확정 전): Pi 의 전달 지연 p50 146.5 ms 는 왕복 최소값의 절반(142.6 ms)과 4 ms 차이 — **Pi 의 값은 거의 그대로 편도 지연**이고 시계 차이는 수 ms 다. WSL 의 184 ms 가 40 ms 큰 것이 시계 차이일 것이다(WSL 에서의 왕복 측정으로 확인할 것).

## 5. 비용과 끄는 법
- t3.small 24시간 ≈ 월 19~20달러 + 디스크 2달러 + 공인 IPv4 3.6달러 ≈ **월 25달러 안팎**(추정 — 시드니 단가는 서울과 조금 다를 수 있으니 콘솔의 요금으로 확인). 시드니의 t3.small Linux 단가는 시간당 0.0264달러(11/10 인스턴스 시작 화면에서 확인) = 월 19.3달러. 이 계정의 크레딧은 **180달러(2027-05-10 만료)** 라서 24시간 켜 두어도 **약 7개월**분(180 ÷ 25) — 무료 플랜 기간 6개월을 덮는다. 제로 지출 예산이 크레딧 소진을 바로 알려 준다.
- 무료 플랜은 6개월 또는 크레딧 소진 때 계정이 닫힌다 → 그 전에 `docs/measurements/` 로 숫자를 옮기고 DB 덤프를 내려받는다.
- 안 쓸 때: 인스턴스 **중지**(디스크·IP 요금은 남는다) 또는 **종료**(전부 삭제) + **탄력적 IP 릴리스**(안 하면 IP 요금이 계속 나간다). 종료 전 `~/fleet-server-info.txt` 와 `ca.key` 는 필요하면 보관.

## 6. 파일
| 파일 | 역할 |
|---|---|
| `deploy/ec2/setup.sh` · `make_certs.sh` | 서버 설치 · 자체 CA/서버 인증서 |
| `fleet/docker-compose.prod.yml` · `fleet/mosquitto/mosquitto-prod.conf` | 운영 덮어쓰기(8883 TLS + 비밀번호, DB 비공개, Grafana 로그인, 수집기 상시) |
| `fleet/common/mqtt_conn.py` | 모든 MQTT 클라이언트의 TLS·인증(환경변수) |
| `deploy/pi/install.sh` · `rt-pi-agent.service` · `fleet.env.example` | Pi 서비스 등록 |
