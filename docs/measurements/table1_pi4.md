### 표① 실시간 지연 (wake-up latency, 단위 us)

| 조건 | 도구 | 커널 | RT | 부하 | min | avg | p50 | p99 | p99.9 | max | 드롭/오버플로 | 비고 |
|---|---|---|---|---|---:|---:|---:|---:|---:|---:|---:|---|
| pi4_generic_idle | cyclictest | 6.8.0-1064-raspi | no | none | 15 | 23 | 23 | 31 | 57 | 376 | 0 | 4 CPU, worst-CPU values · vm 512M · 온도 51.6→50.1 °C, 스로틀 0 |
| pi4_generic_stress | cyclictest | 6.8.0-1064-raspi | no | stress | 15 | 27 | 23 | 84 | 118 | 695 | 0 | 4 CPU, worst-CPU values · vm 512M · 온도 50.1→75.0 °C, 스로틀 0 |
| pi4_rt_idle | cyclictest | 6.8.0-2054-raspi-realtime | yes | none | 15 | 17 | 18 | 19 | 21 | 37 | 0 | 4 CPU, worst-CPU values · vm 512M · 온도 56.0→49.7 °C, 스로틀 0 |
| pi4_rt_stress | cyclictest | 6.8.0-2054-raspi-realtime | yes | stress | 16 | 32 | 24 | 116 | 123 | 132 | 0 | 4 CPU, worst-CPU values · vm 512M · 온도 49.7→71.6 °C, 스로틀 0 |
| pi4_rt_stress_S_p80_vm256 | cyclictest | 6.8.0-2054-raspi-realtime | yes | stress | 17 | 27 | 23 | 85 | 121 | 210 | 0 | 3 CPU, worst-CPU values · vm 256M, E19-d C: cyclictest -S -p 80, isolcpus=3 상태(CPU 3 제외), vm 256M |
| pi4_rt_stress_cpu2_p80 | cyclictest | 6.8.0-2054-raspi-realtime | yes | stress | 16 | 27 | 22 | 145 | 221 | 274 | 0 | 1 CPU, worst-CPU values · vm 256M, E19-d A: cyclictest -t 1 -a 2 -p 80, isolcpus=3 상태, vm 256M |
| pi4_generic_idle | jitter_bench | 6.8.0-1064-raspi | no | idle | 15.4 | 17.6 | 17.7 | 18.5 | 18.8 | 24.9 | 0 | SCHED_FIFO=ok mlockall=ok cpu_pin=-1 period=1000us · vm 256M, prio 80, work 50 us |
| pi4_generic_stress | jitter_bench | 6.8.0-1064-raspi | no | stress | 16.7 | 34.6 | 25.1 | 145.7 | 201.9 | 781.2 | 0 | SCHED_FIFO=ok mlockall=ok cpu_pin=-1 period=1000us · vm 256M, prio 80, work 50 us |
| pi4_rt_idle | jitter_bench | 6.8.0-2054-raspi-realtime | yes | idle | 17.0 | 18.8 | 18.8 | 19.2 | 20.5 | 27.8 | 0 | SCHED_FIFO=ok mlockall=ok cpu_pin=-1 period=1000us · vm 256M, prio 80, work 50 us · 온도 42.8→45.3 °C, 스로틀 0 |
| pi4_rt_stress | jitter_bench | 6.8.0-2054-raspi-realtime | yes | stress | 16.3 | 41.9 | 26.1 | 185.2 | 241.5 | 300.6 | 0 | SCHED_FIFO=ok mlockall=ok cpu_pin=-1 period=1000us · vm 256M, prio 80, work 50 us · 온도 45.8→70.1 °C, 스로틀 0 |
| pi4_rt_stress_isol | jitter_bench | 6.8.0-2054-raspi-realtime | yes | stress | 18.5 | 30.7 | 23.5 | 108.3 | 146.2 | 189.3 | 0 | SCHED_FIFO=ok mlockall=ok cpu_pin=3 period=1000us · vm 256M, prio 80, work 50 us · 온도 44.8→64.8 °C, 스로틀 0 |
| pi4_rt_stress_pin | jitter_bench | 6.8.0-2054-raspi-realtime | yes | stress | 17.3 | 39.4 | 26.4 | 169.1 | 216.1 | 311.5 | 0 | SCHED_FIFO=ok mlockall=ok cpu_pin=3 period=1000us · vm 256M, prio 80, work 50 us · 온도 51.1→74.0 °C, 스로틀 0 |
| pi4_rt_stress_pin_work0 | jitter_bench | 6.8.0-2054-raspi-realtime | yes | stress | 16.9 | 26.6 | 22.2 | 116.0 | 195.9 | 270.0 | 0 | SCHED_FIFO=ok mlockall=ok cpu_pin=2 period=1000us · vm 256M, prio 80, work 0 us, E19-d A: --work-us 0, isolcpus=3 상태, vm 256M |
| pi4_rt_stress_pin_work0_p90 | jitter_bench | 6.8.0-2054-raspi-realtime | yes | stress | 17.2 | 27.7 | 22.7 | 124.2 | 211.2 | 289.7 | 0 | SCHED_FIFO=ok mlockall=ok cpu_pin=2 period=1000us · vm 256M, prio 90, work 0 us, E19-d B: prio 90, --work-us 0, isolcpus=3 상태, vm 256M |

- p99.9 = 1,000번 중 999번은 이 값 이내. 제어 루프는 평균이 아니라 이 값과 max로 판단한다.
- cyclictest 는 CPU마다 스레드 하나씩이며 가장 나쁜 CPU 값을 적었다.
- 비고의 온도·스로틀은 측정 스크립트(cyclictest_run.sh · jitter_run.sh)가 남긴 .meta 에서. '⚠ 스로틀' 이 붙은 줄은 클럭 저하가 섞였을 수 있다.
