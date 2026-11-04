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
| (예정) `jitter_pi_rt_*.json`, `cyclictest_pi_*.txt` | PREEMPT_RT 실측 | `scripts/cyclictest_run.sh`, `jitter_bench --prio 80` | Raspberry Pi, RT 커널 |

규칙: 숫자를 문서에 적을 때는 반드시 이 폴더의 파일 이름을 옆에 적는다. 환경(가상/러너/RT 커널)을 빼고 숫자만 말하지 않는다.
