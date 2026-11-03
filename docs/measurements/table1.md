### 표① 실시간 지연 (wake-up latency, 단위 us)

| 조건 | 도구 | 커널 | RT | 부하 | min | avg | p50 | p99 | p99.9 | max | 드롭/오버플로 | 비고 |
|---|---|---|---|---|---:|---:|---:|---:|---:|---:|---:|---|
| sandbox_generic | jitter_bench | 6.18.44-fc-v230 | no | - | 22.0 | 116.2 | 85.0 | 728.7 | 2892.3 | 3828.8 | 0 | SCHED_FIFO=ok mlockall=ok cpu_pin=-1 period=1000us |
| wsl_fifo | jitter_bench | 6.18.33.2-microsoft-standard-WSL2 | no | - | 5.2 | 48.9 | 37.5 | 273.0 | 664.0 | 936.9 | 0 | SCHED_FIFO=ok mlockall=ok cpu_pin=-1 period=1000us |
| wsl_generic | jitter_bench | 6.18.33.2-microsoft-standard-WSL2 | no | - | 11.0 | 107.7 | 92.4 | 305.0 | 504.3 | 920.9 | 0 | SCHED_FIFO=no mlockall=ok cpu_pin=-1 period=1000us |

- p99.9 = 1,000번 중 999번은 이 값 이내. 제어 루프는 평균이 아니라 이 값과 max로 판단한다.
- cyclictest 는 CPU마다 스레드 하나씩이며 가장 나쁜 CPU 값을 적었다.
