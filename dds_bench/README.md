# dds_bench — DDS 구현체·QoS·메시지 크기별 왕복 지연과 손실률 (표②)

공고 문장 "ROS 2/DDS 미들웨어" · "DDS QoS" 에 숫자로 답하는 자리.

```
 [ping 노드] ──/dds_bench/ping──▶ [pong 노드]
             ◀──/dds_bench/pong──┘        ping 이 "보낸 시각"을 넣어 보내고, 돌아온 것으로 RTT 와 손실을 센다
```

## 실행 (WSL, 저장소 루트에서, 약 3분)
```bash
source /opt/ros/jazzy/setup.bash
bash dds_bench/run_matrix.sh
```
16개 조합(Fast DDS·Cyclone × reliable·best_effort × 64 B·1 KB·64 KB·1 MB)을 차례로 돌리고 `docs/measurements/table2.md` 를 만든다.

## 한 조합만 손으로
```bash
# 터미널 1
RMW_IMPLEMENTATION=rmw_cyclonedds_cpp python3 dds_bench/rtt_bench.py --role pong --reliability best_effort
# 터미널 2
RMW_IMPLEMENTATION=rmw_cyclonedds_cpp python3 dds_bench/rtt_bench.py --role ping --reliability best_effort --payload 65536 --rate 100 --count 500
```

## 읽는 법
- `reliable` = 등기: 잃으면 재전송 → 손실 0, 대신 p99.9 가 커질 수 있다.
- `best_effort` = 일반 우편: 재전송 없음 → 빠르지만 큰 메시지·높은 속도에서 손실이 생긴다.
- 같은 PC 안에서는 DDS 가 공유 메모리로 전달하므로 "네트워크 수치"가 아니다. 두 기기(PC ↔ Pi) 사이에서 다시 재면 WiFi·유선 행이 생긴다.
