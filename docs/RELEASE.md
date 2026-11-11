# 릴리스 → 배포 — 태그 하나로 빌드·검증·게시까지, 로봇에 닿는 마지막 한 걸음은 설계로 정한다

> 한 줄 요약: `git tag v1.2.0 && git push origin v1.2.0` 을 올리면 GitHub Actions 가 **두 아키텍처(x86_64·aarch64)로 빌드 → 테스트 → 패키지 → 가상 함대 50대에 단계 배포(카나리) → 깨진 패키지 롤백 확인 → GitHub Release 게시**까지 한다. 장치는 게시된 `manifest.json` 을 보고 **내려받기 → sha256 → A/B 슬롯 → 자가 점검 → 원자적 전환**으로 설치하고, 실패하면 이전 슬롯으로 되돌린다. 실물(Pi)은 지휘소가 없어도 스스로 받는다. (2026-11-10, 공고의 "업데이트 시스템 구축" + "CI/CD 활용"에 대한 답)

11/05 까지의 OTA 는 **버전 문자열을 바꾸고 몇 초 자는 흉내**였다(`device_agent.apply_ota`). 단계 배포·헬스 게이트·롤백의 논리는 있었지만 설치되는 "것"이 없었다. 이 문서는 그 빈칸을 채운 뒤의 그림이다. 흉내 경로는 단위 테스트·장애 주입용으로 그대로 남아 있다.

## 1. 전체 그림 — 어디서 무엇이 도는가

```
[노트북/WSL]  코드 → git push ──▶ [GitHub Actions: ci.yml]  빌드 · 테스트 20건 · 컨테이너 통합(산출물 OTA 포함) · MuJoCo 2모델
              git tag v1.2.0 ─▶ [GitHub Actions: release.yml]
                                   package(x86_64)  ┐  빌드 → ctest → tar.gz + sha256 + manifest.<arch>.json (+ 깨진 패키지)
                                   package(aarch64) ┘
                                   canary           → Mosquitto 컨테이너 + 가상 50대(A/B 슬롯) + 로컬 HTTP
                                                       정상 패키지 5% → 50% → 100% / 깨진 패키지는 첫 단계 3대에서 거부·롤백 / 판정
                                   publish          → GitHub Release: tar.gz 2개 + manifest.json + 카나리 JSON + 보고서
                                                       │
                      ┌────────────────────────────────┘  HTTPS (누구나 내려받기, 밖으로 나가는 연결만)
                      ▼
[LAN]  (지휘소 모드) WSL: rollout.py --manifest <Release URL> ── 브로커 ──▶ 가상 장치들 → … → 실물(마지막 단계)
       (자율 모드)   Pi: pi_agent.py --auto-update <latest/manifest.json>  10분마다 확인 → 새 버전이면 스스로 설치
```

| 층 | 어디 | 켜져 있어야 하나 | 하는 일 |
|---|---|---|---|
| 빌드·검증·게시 | GitHub (클라우드) | 아니오 — push·태그 때만 | 빌드, 테스트, 패키지, 가상 50대 카나리, Release |
| 보관 | GitHub Release | 항상(GitHub 가) | `manifest.json` + tar.gz. 장치의 "배포 서버" |
| 지휘소(운영 층) | WSL (회사라면 실험실 서버 1대, 또는 클라우드 VM) | 있을 때만 더 보인다 | 브로커·수집기·DB·Grafana·단계 배포 지휘 |
| 장치 | Pi · 가상 장치 | Pi 는 항상 | 내려받기·검증·설치·자가 점검·롤백. 지휘소 없이도 자율 업데이트 |

**노트북은 항상 켜 둘 수 없다**는 조건이 이 그림을 정했다(DECISIONS 11/10). 그래서 "항상 켜져 있어야 하는 것"은 GitHub 와 Pi 뿐이고, WSL 은 켜져 있을 때 지휘소가 된다. 운영 층을 24시간 두고 싶으면 `fleet/docker-compose.yml` 을 클라우드 VM 한 대에 올리면 된다(설정만 바뀐다 — `FLEET_BROKER`, `FLEET_PORT`).

## 2. 산출물과 매니페스트

패키지(`scripts/package_release.sh`): `rt-robot-data-infra-<버전>-<아키텍처>.tar.gz`
```
rt-robot-data-infra-1.2.0-aarch64/
  bin/jitter_bench        rt_core 의 1 kHz 루프 실행 파일 — ROS 2 없이 어디서나 켜 볼 수 있는 유일한 "로봇 쪽" 바이너리
  robots/*.yaml           로봇 프로필 (so101, allex)
  config/*.params.yaml    ROS 2 파라미터 (프로필에서 생성)
  VERSION  COMMIT         무엇을 어디서 만들었나
  selftest.sh             자가 점검: jitter_bench 를 0.5초 돌려 "켜지는가"(실행·주기 100회 이상·드롭 10% 이하)
  post_switch.sh          전환 뒤 훅 (자리만 — 실물에서 노드 재시작을 넣을 곳)
```
`manifest.json` (아키텍처별 항목을 하나로 합친 것, `scripts/merge_manifests.py`):
```json
{ "version": "1.2.0",
  "arch": { "x86_64":  {"url": "rt-robot-data-infra-1.2.0-x86_64.tar.gz",  "sha256": "…", "size": 20966},
            "aarch64": {"url": "rt-robot-data-infra-1.2.0-aarch64.tar.gz", "sha256": "…", "size": 20410} },
  "url": "…x86_64.tar.gz", "sha256": "…", "size": 20966,          ← 호환용 기본값(첫 아키텍처)
  "commit": "43105e0…", "built_at": "2026-11-10T01:00:55Z",
  "rollout": {"stages_pct": [5, 50, 100], "health_wait_s": 5, "max_fail": 0, "apply_timeout_s": 60} }
```
- `url` 이 상대 경로인 이유: Release 자산은 매니페스트와 **같은 폴더**에 놓인다. `releases/latest/download/manifest.json` 처럼 "최신" 별칭 주소로 읽어도 같은 폴더의 파일을 받게 된다. 읽는 쪽(`rollout.load_manifest`, `device_agent.auto_update_once`)이 절대 주소로 바꾼다.
- 왜 두 아키텍처인가: 러너·가상 장치는 x86_64, Pi 4 는 aarch64. 장치는 `platform.machine()` 으로 자기 항목을 고른다(`pick_artifact`). 하나의 매니페스트, 두 파일.
- 왜 jitter_bench 가 "펌웨어"인가: `rt_control_node` 는 ROS 2 가 있어야 켜진다. 러너·가상 장치·Pi 가 **같은 파일을 같은 방법으로 켜 보는 것**이 자가 점검의 뜻이라, ROS 2 없이 도는 rt_core 바이너리를 넣었다. 노드까지 바꾸는 것은 6절.
- 깨진 패키지(`--bad`): `selftest.sh` 가 `exit 1` 인 것 외에는 같다. 카나리에서 "거부 → 롤백"을 매번 확인하기 위한 것이고 Release 에는 게시하지 않는다.

## 3. 장치의 설치 — A/B 슬롯 (`fleet/agent/ota_apply.py`)

```
<slot_root>/                     (Pi: ~/rt-slots, 가상 장치: build/…/devices/<id>)
  slots/1.1.0/   slots/1.2.0/    버전마다 한 폴더 — 둘 다 온전히 남아 있다
  current -> slots/1.2.0         지금 켜는 쪽. 임시 링크를 만들고 os.replace 로 바꿔치기 → 원자적
  state.json                     {"current": "1.2.0", "previous": "1.1.0", "switched_at": …}
  .download/                     내려받는 중인 tar (끝나면 지운다)
```
한 번의 설치는 이 순서이고, 어느 단계에서 멈추든 `current` 는 **옛 슬롯 아니면 새 슬롯, 둘 중 하나**다:

| 단계 | 하는 일 | 실패하면 |
|---|---|---|
| 1 내려받기 | url → `.download/<ver>.tar.gz`, 200 MB 상한 | 거부(네트워크·크기) |
| 2 검증 | sha256 == 매니페스트, 크기 == 매니페스트 | **거부 — 풀지도 않는다** |
| 3 풀기 | `slots/<ver>/` (경로 탈출 `../`·링크 멤버 거부, 최상위 폴더 한 겹 벗김) | 슬롯 삭제 |
| 4 자가 점검 | `selftest.sh` (시간 제한 60초) | 슬롯 삭제, `current` 그대로 |
| 5 전환 | `current` → 새 슬롯 (원자적), `state.json` | — |
| 6 훅 | `post_switch.sh` 있으면 실행 | **스스로 이전 슬롯으로 복귀** (`post_switch_failed_rolled_back`) |

- 실패는 텔레메트리에 실린다: `state=fault`, `ota_stage=extracted|downloaded|…`, `ota_error="…selftest 실패 (exit 1)…"`. 배포기는 이걸 보고 **헬스 대기 전에** 롤백을 결정한다(`Rollout.wait_apply`).
- 롤백(`ota_rollback` 명령 또는 자율): `current` → `previous`. 내려받을 것이 없어 0.2초 안이다. 설치가 전환 전에 실패한 장치는 되돌릴 것이 없으므로 상태만 `ok` 로. 장치는 `ota_rollback` 을 받으면 **"직전 설치가 실패했는가"를 먼저** 본다 — 11/11 까지는 "이전 슬롯이 있는가"를 먼저 봐서, 두 번째 릴리스 뒤에 깨진 패키지가 오면 그것을 거부한 장치가 멀쩡한 현재 버전에서 한 단계 더 옛 버전으로 내려갔다(슬롯이 비어 있던 시험·카나리에서는 드러나지 않았다. DECISIONS 11/11).
- 전원이 설치 도중 꺼지면: 1~4 단계면 `current` 는 옛 슬롯 그대로(쓰레기 `.download`·반쯤 풀린 슬롯은 다음 설치가 지운다), 5 단계의 `os.replace` 는 파일시스템이 원자성을 보장한다. 6 단계 도중이면 재부팅 뒤 `current` 는 새 슬롯이고 훅은 다시 돌지 않는다 — 이건 한계다(6절).

## 4. 배포의 세 가지 운전 모드 — 같은 설치 코드, 시작 버튼만 다르다

| 모드 | 시작 | 함대 단위 카나리·헬스 게이트·롤백 | 쓰는 때 |
|---|---|---|---|
| **승인** | 사람: [WSL 창] `python3 fleet/ota/rollout.py --manifest <Release 의 manifest.json URL>` | 있음 (5→50→100 %, 실물은 마지막 단계) | 기본. 로봇에 손대는 마지막 걸음은 사람이 |
| **카나리(CI)** | 태그 → `release.yml` 의 canary 잡 | 있음 — 가상 50대, 깨진 패키지 롤백까지 | 매 릴리스, 게시 전 |
| **자율** | 장치: `pi_agent.py --auto-update <latest/manifest.json> --poll-s 600 --window 3-5` | 없음 — 장치 혼자 검증·자가 점검·로컬 롤백 | 지휘소가 꺼져 있는 평소. 실물 1대의 기본 |

- 실물이 마지막인 이유: `FleetWatcher.online_devices` 가 `kind=real` 을 뒤로 정렬한다. 5 % 단계는 가상 장치가 맡고, 실물은 앞 단계가 다 통과한 뒤에만 받는다.
- 자율 모드의 안전장치: (a) `state == ok`(멈춰 있음)일 때만, (b) 시간대(`--window 3-5` = 03~05시), (c) 채널 — `releases/latest` 는 **정식 릴리스만** 가리키고 `v0.9.0-rc1` 같은 pre-release 는 잡히지 않는다. "무엇을 실물에 내보낼지"는 태그를 다는 사람이 정한다.
- 왜 완전 자동(태그 → 실물)이 아닌가: 러너는 LAN 브로커에 닿지 못한다. Pi 나 WSL 을 self-hosted runner 로 등록하면 닿지만 공개 저장소에 self-hosted runner 는 GitHub 도 말리는 보안 위험이다. 그리고 로봇이 태그 하나에 밤중에 스스로 바뀌는 것은 좋은 설계가 아니다 — 자율 모드도 시간대와 채널로 묶어 두는 이유다.

## 5. 해 보기

```bash
# [WSL 창] 로컬 끝-대-끝 (컨테이너 통합 — CI 2단계와 같다, 산출물 OTA 2단계 포함, 약 4분)
bash fleet/tests/integration.sh
# [WSL 창] 릴리스 카나리만 (가상 50대, 패키지는 build/release 에 있어야)
cmake -S rt_control/rt_core -B build/rt_core -DCMAKE_BUILD_TYPE=Release && cmake --build build/rt_core -j --target jitter_bench
bash scripts/package_release.sh v0.0.0-local && bash scripts/package_release.sh v0.0.0-local --bad
python3 scripts/merge_manifests.py --out build/release/manifest.json build/release/manifest.*.json
python3 scripts/merge_manifests.py --out build/release/manifest-bad.json build/release/manifest-bad.*.json
bash fleet/tests/release_canary.sh
# [WSL 창] 진짜 릴리스 — 사람이 하는 유일한 일
git tag v0.9.0-rc1 && git push origin v0.9.0-rc1          # '-' 가 있으면 pre-release. 정식은 v1.0.0
gh run watch                                              # package ×2 → canary → publish
gh release view v0.9.0-rc1                                # 자산: tar.gz 2개, manifest.json, 카나리 JSON 2개
# [WSL 창] 승인 모드로 LAN 함대(가상 + Pi)에 내보내기 — 브로커·가상 장치가 떠 있을 때
python3 fleet/ota/rollout.py --manifest https://github.com/<owner>/<repo>/releases/download/v0.9.0-rc1/manifest.json
```
```bash
# [Pi 창] 자율 모드 — 브로커는 있으면 붙고 없으면 1시간치 버퍼. 처음 한 번은 --once 로 확인
cd ~/rt-robot-data-infra && git pull
python3 fleet/agent/pi_agent.py --device-id pi-rt --slot-root ~/rt-slots \
    --auto-update https://github.com/<owner>/<repo>/releases/latest/download/manifest.json --once
# 상시 (사용자 systemd 서비스; 로그아웃 뒤에도 돌게 loginctl enable-linger $USER 한 번)
mkdir -p ~/.config/systemd/user && cat > ~/.config/systemd/user/rt-pi-agent.service <<'EOF'
[Unit]
Description=rt-robot-data-infra device agent (telemetry + autonomous OTA)
After=network-online.target
[Service]
WorkingDirectory=%h/rt-robot-data-infra
Environment=FLEET_BROKER=<브로커 호스트>
ExecStart=/usr/bin/python3 fleet/agent/pi_agent.py --device-id pi-rt --slot-root %h/rt-slots --auto-update https://github.com/<owner>/<repo>/releases/latest/download/manifest.json --poll-s 600 --window 3-5
Restart=always
RestartSec=10
[Install]
WantedBy=default.target
EOF
systemctl --user daemon-reload && systemctl --user enable --now rt-pi-agent && systemctl --user status rt-pi-agent
```
`<owner>/<repo>` 는 이 저장소의 GitHub 주소. 브로커 호스트는 WSL 의 LAN 주소(문서에는 적지 않는다 — 11/06 규칙).

## 6. 면접관이 물을 것 — 했다 / 안 했다 / 다음

| 질문 | 답 |
|---|---|
| 왜 5 → 50 → 100 %? | 50대면 5 % = 3대. 깨진 빌드가 닿는 장치를 3대로 묶고, 통과하면 절반, 그다음 전부. 비율은 매니페스트 `rollout.stages_pct` 로 릴리스마다 바꿀 수 있다 |
| 헬스를 무엇으로 정의하나? | 지금은 `state == ok` 와 설치 결과(`ota_error` 없음). 실물은 RT 노드의 워치독 상태가 `state` 가 된다(`ros_status_bridge`). **안 한 것**: `wake_p99_us`·드롭 수 같은 RT 지표를 게이트 조건에 넣기 — 다음 |
| 배포 중 오프라인인 장치는? | 대상 목록은 "최근 5초 안에 텔레메트리를 보낸 장치"다. 꺼진 장치는 빠지고, 켜지면 자율 모드가 `latest` 를 보고 따라온다 |
| 업데이트 도중 전원이 꺼지면? | A/B 슬롯 + 원자적 링크 교체. `current` 는 항상 둘 중 하나다(3절). 훅 도중은 한계 |
| 버전이 섞인 함대는? | 텔레메트리에 `fw_version` 이 실려 Grafana 장치 표에 보인다. 섞인 상태 자체를 막지는 않는다 — 단계 배포가 원래 섞인 상태를 지나간다 |
| 산출물 진위는? | **sha256 은 무결성(깨지지 않았나)만** 보장한다. 누가 만들었나(서명)는 **안 했다** — 다음은 ed25519 서명(minisign 꼴)을 매니페스트에 넣고 장치가 공개키로 확인하기 |
| 실물에서 실제로 바뀌는 것은? | 슬롯 폴더·`current` 링크·자가 점검 실행까지. **노드를 새 바이너리로 재시작하는 훅은 자리만**(`post_switch.sh`). 서비스 등록과 함께 다음 |
| 왜 전부 자동이 아닌가? | 4절. 러너는 LAN 에 못 닿고, self-hosted runner 는 공개 저장소에서 위험하며, 로봇은 태그 하나에 스스로 바뀌면 안 된다 |
| 서버가 꺼져 있으면? | 로봇은 혼자 돌고(RT 루프), 혼자 업데이트하고(자율 모드), 텔레메트리는 1시간치를 들고 있다가 재전송한다. 서버는 "더 보고 함대를 지휘하기 위한 것"이지 로봇이 움직이는 데 필요한 것이 아니다 |

## 7. 숫자 (E22)

카나리의 숫자 — 단계별 적용 시간, 전체 시간, 깨진 패키지의 거부·롤백 시간 — 는 `docs/experiments/E22.md` 에 쌓는다.

**첫 태그 `v0.9.0-rc1` (2026-11-11, run 42927560505) — 첫 실행에 게시까지 통과.**

| 무엇 | 값 |
|---|---|
| 태그 push → Release 게시 | **1분 52초** (패키지 x86_64 21 s · aarch64 43 s → 카나리 48 s → 게시 11 s) |
| 정상 패키지, 가상 50대 | 50/50, 단계별 적용 완료 **1.2 → 2.0 → 2.2 s**, 전체 14.41 s (헬스 대기 3 s × 3 포함) |
| 깨진 패키지 | **3/50** 에서 자가 점검이 거부(0.6 s) → 롤백 **1.0 s** |
| 산출물 | aarch64 21,734 B · x86_64 21,450 B, 사전 릴리스(태그에 `-`) — 실물의 자율 업데이트(`latest`)에는 잡히지 않는다 |

적용·롤백 시간에는 "장치의 다음 보고(1 Hz)까지 최대 1초"가 들어 있다(E22 4절).

**실물 Pi 가 같은 Release 를 받아 설치(11/11, 시험용 슬롯, 4회)**: 한 번에 **0.98 ~ 1.62초** — 매니페스트 읽기 0.18~0.48 + 내려받기 0.09~0.43 + 해시 검증 0.001 + 풀기 0.03 + **자가 점검 0.67** + 링크 전환 0.001 미만 + 훅 0.009. 러너(ubuntu-24.04-arm)가 만든 aarch64 바이너리가 Pi 4 의 RT 커널에서 500주기 드롭 0 으로 자가 점검을 통과했다. 돌고 있는 서비스와 연속 기록은 건드리지 않았다(`install_pi4_once_v0.9.0-rc1.json`). 원본은 Release 자산을 그대로 옮긴 `docs/measurements/ota_release_v0.9.0-rc1_{good,bad}.json` · `manifest_v0.9.0-rc1.json`.

## 8. 파일

| 파일 | 역할 |
|---|---|
| `.github/workflows/release.yml` | 태그 → package(x86_64·aarch64) → canary → publish |
| `scripts/package_release.sh` · `scripts/merge_manifests.py` · `scripts/make_release_report.py` | 패키지·매니페스트·보고서 |
| `fleet/agent/ota_apply.py` | 장치 설치 (내려받기·sha256·A/B·자가 점검·전환·훅·롤백) |
| `fleet/agent/device_agent.py` | `ota` 명령의 진짜 설치 경로, 자율 업데이트(`enable_auto_update`), `pick_artifact` |
| `fleet/agent/pi_agent.py` | 실물 보드 에이전트 (ROS 없이, 자율 업데이트) · `ros_status_bridge.py` 도 같은 옵션 |
| `fleet/ota/rollout.py` | `--manifest`, 실물 마지막, 설치 실패 즉시 감지 |
| `fleet/tests/test_ota_artifact.py` | 단위·끝-대-끝 (가짜 브로커 + 진짜 설치, 9가지 확인) · `fleet/tests/release_canary.sh` · `integration.sh` 4b/4c |
| `docs/DECISIONS.md` 2026-11-10 | 왜 이렇게 (버린 대안 포함) |
