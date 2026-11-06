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
| `mujoco_backend_allex_wsl_1khz.json` | 같은 것, ALLEX 48 자유도(1 kHz 첫 측정, E21) | `test_mujoco_backend` 출력에서 전사 | WSL2 Ubuntu 24.04 |
| `mujoco_backend_allex_wsl_500hz.json` | 같은 것, ALLEX 500 Hz(프로필 기본, 1,000주기) | `test_mujoco_backend` 가 쓴 JSON | WSL2 Ubuntu 24.04 |
| `mujoco_backend_allex_ci_1khz_run42172730308.json` | 같은 것, ALLEX 1 kHz | CI run 42172730308 아티팩트 `mujoco-ci` 복사(경로만 줄임) | ubuntu-24.04 러너 |
| `mujoco_backend_allex_ci_500hz_run42175845461.json` | 같은 것, ALLEX 500 Hz(CI 게이트 첫 run) | CI run 42175845461 아티팩트 그대로 | ubuntu-24.04 러너 |
| `jitter_pi4_generic_{idle,stress}.json` (+`.meta`) | 1 kHz 루프 지연, 일반 커널 기준값 | `jitter_bench --prio 80 --seconds 60` (11/04 은 손으로, 이후는 `scripts/jitter_run.sh`) | **Pi 4B**, Ubuntu 24.04 `6.8.0-1064-raspi`, RT 아님 |
| `cyclictest_pi4_generic_{idle,stress}.txt` (+`.meta`) | 표준 도구 지연 히스토그램, 일반 커널 기준값 | `scripts/cyclictest_run.sh <label> 300` / `120 stress` | Pi 4B, 일반 커널. `.meta` 에 온도·스로틀 |
| `table1_pi4.md` | 표① Pi 4 (일반 → RT 비교표) | `scripts/make_table1.py --cyclictest 'docs/measurements/cyclictest_pi4_*.txt' --jitter 'docs/measurements/jitter_pi4_*.json'` | — |
| `jitter_pi4_rt_{idle,stress,stress_pin,stress_isol}.json` (+`.meta`) | PREEMPT_RT 실측: 한가 · 부하 · 부하+CPU 3 고정 · 부하+isolcpus=3 | `scripts/jitter_run.sh <label> 60 [stress] [3]` | **Pi 4B, `6.8.0-2054-raspi-realtime`**, `/sys/kernel/realtime` = 1, 스로틀 0 |
| `cyclictest_pi4_rt_{idle,stress}.txt` (+`.meta`) | 표준 도구, RT 커널 한가 300 s / 부하 120 s | `scripts/cyclictest_run.sh` | Pi 4B, RT 커널 |
| `jitter_pi4_rt_stress_pin_work0.json` | 도구 불일치 검증(E19-d): 일 없이(`--work-us 0`) CPU 2 고정, 부하 | `jitter_bench --prio 80 --cpu 2 --work-us 0` (손으로) | Pi 4B, RT 커널 + isolcpus 상태 |

| `record_summary_wsl_20261105.md`, `record_rt_status_wsl_20261105.csv` | 기록 파이프라인 첫 실행: 토픽별 Hz·틈, rt_status 29초, 추종 오차 | `data_pipeline/record.sh 30` → `bag_to_csv.py` (MCAP 원본 1.07 MB 는 `build/bags/`, 저장소 제외) | WSL2, MuJoCo 백엔드, 일반 스케줄링 |

규칙: 숫자를 문서에 적을 때는 반드시 이 폴더의 파일 이름을 옆에 적는다. 환경(가상/러너/RT 커널)을 빼고 숫자만 말하지 않는다.
규칙 2(11/04 추가): Pi 측정은 `.meta` 의 `throttled_after` 가 0 인 것만 표에 올린다. 0 이 아니면 클럭 저하가 섞인 값이라 다시 잰다.
