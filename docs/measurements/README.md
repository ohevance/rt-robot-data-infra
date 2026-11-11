# measurements — 숫자의 원본 (표①②③은 전부 여기 파일에서 생성된다)

| 파일 | 무엇 | 어떻게 만들었나 | 환경 |
|---|---|---|---|
| `jitter_sandbox_generic.json` | 1 kHz 루프 지연 (D0, 가상 머신) | `jitter_bench --no-rt --seconds 5` | 샌드박스 VM, 참고값 |
| `jitter_wsl_generic.json`, `jitter_wsl_fifo.json` | 1 kHz 루프 지연, 일반 vs SCHED_FIFO | `jitter_bench` | WSL2, 참고값 |
| `table1.md` | 표① | `scripts/make_table1.py --jitter 'docs/measurements/jitter_*.json'` | — |
| `dds_<rmw>_<qos>_<bytes>.json` (16개) | DDS 왕복 지연·손실 | `dds_bench/run_matrix.sh` | WSL2, rclpy |
| `table2.md` | 표② | `scripts/make_table2.py` | — |
| `fault_<장애>[_label].json` | 장애 주입 감지·복구·유실 | `fleet/chaos/inject.py --fault ...` | WSL2, 가상 50대 1 Hz |
| `ota_<version>.json` | OTA 단계 배포 결과 | `fleet/ota/rollout.py` | WSL2 |
| `table3.md` | 표③ (①처리량 ②장애 ③OTA) | `scripts/make_table3.py --minutes N` | — |
| `table3_ci.md` | 표③, GitHub 러너에서 (10대 2 Hz) | CI `fleet_integration` 아티팩트 | ubuntu-24.04 러너 |
| `mujoco_backend_ci.json` | MuJoCo 물리 한 주기 비용 | CI `mujoco` 아티팩트 (`test_mujoco_backend`) | ubuntu-24.04 러너 |
| `mujoco_backend_wsl_20261104.json` | 같은 것, WSL 단독(4.9 / 6.3 / 20.8 us) | `test_mujoco_backend` 가 쓴 JSON. 11/04 에 저장소 뿌리에 `mujoco_backend_ci.json` 이라는 이름으로 커밋돼 있던 것을 11/11 에 이리로 옮기고 이름을 바꿨다(테스트를 뿌리에서 돌리면 그 이름으로 쓴다 — 러너 값과 헷갈린다) | WSL2 Ubuntu 24.04 (참고값) |
| `mujoco_backend_allex_wsl_1khz.json` | 같은 것, ALLEX 48 자유도(1 kHz 첫 측정, E21) | `test_mujoco_backend` 출력에서 전사 | WSL2 Ubuntu 24.04 |
| `mujoco_backend_allex_wsl_500hz.json` | 같은 것, ALLEX 500 Hz(프로필 기본, 1,000주기) | `test_mujoco_backend` 가 쓴 JSON | WSL2 Ubuntu 24.04 |
| `mujoco_backend_allex_ci_1khz_run42172730308.json` | 같은 것, ALLEX 1 kHz | CI run 42172730308 아티팩트 `mujoco-ci` 복사(경로만 줄임) | ubuntu-24.04 러너 |
| `mujoco_backend_allex_ci_500hz_run42175845461.json` | 같은 것, ALLEX 500 Hz(CI 게이트 첫 run) | CI run 42175845461 아티팩트 그대로 | ubuntu-24.04 러너 |
| `ota_release_sandbox_good.json` · `_bad.json` | 진짜 산출물 OTA 50대: 단계별 적용 시간·전체, 깨진 패키지 거부·롤백 (E22 1차) | `rollout.py --manifest` 결과 그대로(경로만 줄임) | 샌드박스, 가짜 브로커 + 진짜 설치 |
| `jitter_pi4_generic_{idle,stress}.json` (+`.meta`) | 1 kHz 루프 지연, 일반 커널 기준값 | `jitter_bench --prio 80 --seconds 60` (11/04 은 손으로, 이후는 `scripts/jitter_run.sh`) | **Pi 4B**, Ubuntu 24.04 `6.8.0-1064-raspi`, RT 아님 |
| `cyclictest_pi4_generic_{idle,stress}.txt` (+`.meta`) | 표준 도구 지연 히스토그램, 일반 커널 기준값 | `scripts/cyclictest_run.sh <label> 300` / `120 stress` | Pi 4B, 일반 커널. `.meta` 에 온도·스로틀 |
| `table1_pi4.md` | 표① Pi 4 (일반 → RT 비교표) | `scripts/make_table1.py --cyclictest 'docs/measurements/cyclictest_pi4_*.txt' --jitter 'docs/measurements/jitter_pi4_*.json'` | — |
| `jitter_pi4_rt_{idle,stress,stress_pin,stress_isol}.json` (+`.meta`) | PREEMPT_RT 실측: 한가 · 부하 · 부하+CPU 3 고정 · 부하+isolcpus=3 | `scripts/jitter_run.sh <label> 60 [stress] [3]` | **Pi 4B, `6.8.0-2054-raspi-realtime`**, `/sys/kernel/realtime` = 1, 스로틀 0 |
| `cyclictest_pi4_rt_{idle,stress}.txt` (+`.meta`) | 표준 도구, RT 커널 한가 300 s / 부하 120 s | `scripts/cyclictest_run.sh` | Pi 4B, RT 커널 |
| `jitter_pi4_rt_stress_pin_work0.json` | 도구 불일치 검증(E19-d): 일 없이(`--work-us 0`) CPU 2 고정, 부하 | `jitter_bench --prio 80 --cpu 2 --work-us 0` (손으로) | Pi 4B, RT 커널 + isolcpus 상태 |

| `record_summary_wsl_20261105.md`, `record_rt_status_wsl_20261105.csv` | 기록 파이프라인 첫 실행: 토픽별 Hz·틈, rt_status 29초, 추종 오차 | `data_pipeline/record.sh 30` → `bag_to_csv.py` (MCAP 원본 1.07 MB 는 `build/bags/`, 저장소 제외) | WSL2, MuJoCo 백엔드, 일반 스케줄링 |
| `ota_release_v0.9.0-rc1_good.json` · `_bad.json` · `manifest_v0.9.0-rc1.json` | 첫 태그의 릴리스 카나리: 가상 50대 단계 배포, 깨진 패키지 거부·롤백, 게시된 매니페스트 (E22) | Release `v0.9.0-rc1` 의 자산 그대로 (`gh release download`, run 42927560505) | ubuntu-24.04 러너, 진짜 Mosquitto |
| `ota_release_v0.9.0_good.json` · `_bad.json` · `manifest_v0.9.0.json` | 정식 태그의 릴리스 카나리 — 같은 시험의 두 번째 값(1.2 / 2.2 / 2.2 s, 전체 14.62 s, 3/50 에서 거부 → 롤백 1.0 s) (E22) | Release `v0.9.0` 의 자산 그대로 (공개 주소 `releases/download/v0.9.0/` 에서 받음, run 42934131689). 이름만 `ota_release_good.json` → `ota_release_v0.9.0_good.json` 꼴로 바꿨다 | ubuntu-24.04 러너, 진짜 Mosquitto |
| `selftest_pi4_v0.9.0-rc1.json` | 실물 Pi 가 Release 의 aarch64 패키지를 설치하며 돌린 자가 점검 (500주기, 드롭 0) + 슬롯 상태 | Pi 의 `~/rt-slots-test/current/selftest.json`·`state.json` 출력에서 전사 | **Pi 4B, RT 커널**, `--no-rt` 0.5초 — 성능 측정이 아니라 "켜지는가" |
| `soak_pi_sydney_20261111_0843.json` | Pi 의 첫 밤 14.09 h: 보낸 수·받은 수·유실 | 서버에서 psql 질의, 출력에서 전사 | Pi 4(집 Wi-Fi) → **서버: 시드니** |
| `soak_pi-rt_<UTC시각>.json` | 같은 것을 스크립트로 (재시작·공백·가장 긴 간격·전달 지연 포함) | 서버에서 `deploy/ec2/soak_report.sh pi-rt` 의 출력 그대로 | Pi 4 → **서버: 시드니** |
| `rtt_pi_sydney_<UTC시각>_[조건_]interval<간격>[_nodelay].json` (5개) | MQTT 왕복 시간 (E23): 첫 측정(0.2 s) + 검증 넷 A(1.00 s) · D(0.35 s) · C(0.20 s) · B(0.20 s, 클라이언트 NODELAY). **망의 왕복으로 인용하는 것은 A 뿐** — 간격이 왕복보다 짧은 것은 Nagle 로 커진 값이다. 검증 넷은 개별 값(`samples_ms`) 포함 | Pi 에서 `fleet/tools/mqtt_rtt.py` 의 출력 그대로 | Pi 4(집 Wi-Fi) → **서버: 시드니**, TLS + 비밀번호 |
| `install_pi4_once_v0.9.0-rc1.json` | 실물 Pi 가 Release 를 받아 설치하는 데 걸린 단계별 시간, 3회 (E22) | `pi_agent.py --once` 의 출력에서 전사 | **Pi 4B, RT 커널**, 집 Wi-Fi, GitHub Release 에서 직접 |

규칙: 숫자를 문서에 적을 때는 반드시 이 폴더의 파일 이름을 옆에 적는다. 환경(가상/러너/RT 커널)을 빼고 숫자만 말하지 않는다.
규칙 2(11/04 추가): Pi 측정은 `.meta` 의 `throttled_after` 가 0 인 것만 표에 올린다. 0 이 아니면 클럭 저하가 섞인 값이라 다시 잰다.
