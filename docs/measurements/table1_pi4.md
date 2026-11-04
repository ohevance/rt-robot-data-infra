### 표① 실시간 지연 (wake-up latency, 단위 us)

| 조건 | 도구 | 커널 | RT | 부하 | min | avg | p50 | p99 | p99.9 | max | 드롭/오버플로 | 비고 |
|---|---|---|---|---|---:|---:|---:|---:|---:|---:|---:|---|
| pi4_generic_idle | cyclictest | 6.8.0-1064-raspi | no | none | 15 | 23 | 23 | 31 | 57 | 376 | 0 | 4 CPU, worst-CPU values · 온도 51.6→50.1 °C, 스로틀 0 |
| pi4_generic_stress | cyclictest | 6.8.0-1064-raspi | no | stress | 15 | 27 | 23 | 84 | 118 | 695 | 0 | 4 CPU, worst-CPU values · 온도 50.1→75.0 °C, 스로틀 0 |
| pi4_generic_idle | jitter_bench | 6.8.0-1064-raspi | no | idle | 15.4 | 17.6 | 17.7 | 18.5 | 18.8 | 24.9 | 0 | SCHED_FIFO=ok mlockall=ok cpu_pin=-1 period=1000us |
| pi4_generic_stress | jitter_bench | 6.8.0-1064-raspi | no | stress | 16.7 | 34.6 | 25.1 | 145.7 | 201.9 | 781.2 | 0 | SCHED_FIFO=ok mlockall=ok cpu_pin=-1 period=1000us |

- p99.9 = 1,000번 중 999번은 이 값 이내. 제어 루프는 평균이 아니라 이 값과 max로 판단한다.
- cyclictest 는 CPU마다 스레드 하나씩이며 가장 나쁜 CPU 값을 적었다.
- 비고의 온도·스로틀은 측정 스크립트(cyclictest_run.sh · jitter_run.sh)가 남긴 .meta 에서. '⚠ 스로틀' 이 붙은 줄은 클럭 저하가 섞였을 수 있다.
