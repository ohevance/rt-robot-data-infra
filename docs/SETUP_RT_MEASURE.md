# 표① 실측 — 네이티브 Ubuntu 24.04 에서 (노트북 · 외장 SSD · Pi 5 중 하나)

목표: 실시간 커널을 켜고, 이 저장소의 `jitter_bench`와 `cyclictest`를 돌려 **표①의 첫 수치**를 얻는다.
전부 네이티브 부팅에서 해야 한다 (WSL·가상머신에서는 실시간 측정이 의미 없음).

## 1. 기본 도구 (5분)
```bash
sudo apt update
sudo apt install -y git build-essential cmake python3 python3-pip rt-tests stress-ng
```

## 2. 실시간 커널 켜기 (10분 + 재부팅)
```bash
sudo pro attach <Ubuntu Pro 토큰>     # 개인 무료 토큰 (ubuntu.com/pro)
sudo pro enable realtime-kernel        # 묻는 것에 y
sudo reboot
# 재부팅 뒤 확인
uname -r                 # ...-realtime 이 보여야 함
cat /sys/kernel/realtime # 1 이면 PREEMPT_RT 커널
```
NVIDIA 드라이버가 실시간 커널에서 깨지면(화면이 안 나오거나 검은 화면): 부팅 메뉴(GRUB → Advanced)에서 일반 커널로 들어가도 됩니다. 측정할 때만 실시간 커널로 부팅합니다. 해결 방법은 보고서 #2에 정리합니다.

## 3. 저장소 빌드 (2분)
```bash
cd ~/rt-robot-data-infra
cmake -S rt_control/rt_core -B build/rt_core -DCMAKE_BUILD_TYPE=Release
cmake --build build/rt_core -j
./build/rt_core/test_spsc_ring            # "OK: spsc_ring"
```

## 4. jitter_bench — 4가지 조건 (각 60초)
```bash
mkdir -p docs/measurements
# A) 일반 커널로 부팅한 상태에서 (RT 비교용)
sudo ./build/rt_core/jitter_bench --prio 80 --seconds 60 --label generic_idle   --json docs/measurements/jitter_generic_idle.json
# B) 실시간 커널로 부팅한 상태에서
sudo ./build/rt_core/jitter_bench --prio 80 --seconds 60 --label rt_idle        --json docs/measurements/jitter_rt_idle.json
# C) 실시간 커널 + 부하 (다른 터미널에서 먼저: stress-ng --cpu $(nproc) --io 2 --vm 1 --vm-bytes 512M --timeout 90s)
sudo ./build/rt_core/jitter_bench --prio 80 --seconds 60 --label rt_stress      --json docs/measurements/jitter_rt_stress.json
# D) 실시간 커널 + 부하 + CPU 고정 (마지막 CPU 번호 = nproc-1)
sudo ./build/rt_core/jitter_bench --prio 80 --cpu $(( $(nproc) - 1 )) --seconds 60 --label rt_stress_pin --json docs/measurements/jitter_rt_stress_pin.json
```

## 5. cyclictest — 밤새 (각 10분~1시간, 실시간 커널에서)
```bash
sudo scripts/cyclictest_run.sh rt_idle   1800
sudo scripts/cyclictest_run.sh rt_stress 1800 stress
# 일반 커널로 부팅했을 때 한 번 더
sudo scripts/cyclictest_run.sh generic_idle 600
```

## 6. 표① 만들기
```bash
python3 scripts/make_table1.py --cyclictest 'docs/measurements/cyclictest_*.txt' \
                               --jitter     'docs/measurements/jitter_*.json' \
                               --out docs/measurements/table1.md
cat docs/measurements/table1.md
git add docs/measurements && git commit -m "measurements: table1 (RT vs generic, idle vs stress)" && git push
```

## 보내 주실 것
- `docs/measurements/table1.md` 내용 (또는 화면 캡처)
- `uname -r`, `cat /sys/kernel/realtime` 결과
- 안 된 것이 있으면 그 명령과 화면에 나온 오류 그대로
