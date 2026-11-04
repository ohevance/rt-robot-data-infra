# 표① 실측 — Raspberry Pi 4 Model B (4 GB) + Ubuntu 24.04 + PREEMPT_RT

목표: **실시간 커널에서 재는 표①의 진짜 숫자.** WSL 값은 참고값일 뿐이고, 이 숫자가 포트폴리오의 핵심이다.
Pi 4B 4 GB 로 충분하다(64-bit Cortex-A72 4코어). 모니터·키보드 없이 SSH 로 한다. 손이 가는 시간 약 1시간 + cyclictest 대기 1시간.

## 0. 준비물
| 있어야 하는 것 | 메모 |
|---|---|
| Raspberry Pi 4 Model B 4 GB | ✓ (상자 확인) |
| microSD 16 GB 이상 (A1/A2 등급 권장) + 카드 리더 | 8 GB 도 돌아가지만 업그레이드 여유가 없다 |
| USB-C 전원 **5 V / 3 A** | 상자에 "sold separately". 약한 충전기면 저전압 경고 → 클럭이 흔들려 **측정이 오염**된다 |
| 이더넷 케이블 (공유기 ↔ Pi) | 권장. Wi-Fi 도 되지만 측정 중 Wi-Fi 드라이버가 지연의 원천이 될 수 있다 |
| (선택) 방열판 또는 팬 | cyclictest 30분 + stress 에 80 °C 를 넘으면 자동 감속(throttle) → 수치가 흔들린다. 없으면 측정 시간을 10분으로 줄인다 |

## 1. SD 카드 굽기 (Windows, 10분)
1. **Raspberry Pi Imager** 설치 (raspberrypi.com/software).
2. Device: *Raspberry Pi 4* → OS: *Other general-purpose OS → Ubuntu → **Ubuntu Server 24.04 LTS (64-bit)*** → Storage: SD 카드.
3. NEXT → **Edit Settings**: hostname `pi-rt`, 사용자 `mgoh` + 비밀번호, (Wi-Fi 쓰면 SSID/비밀번호, 국가 KR), 시간대 Asia/Seoul; **Services 탭 → Enable SSH (password authentication)** → Save → Yes → 쓰기.
4. 카드를 Pi 에 꽂고 이더넷·전원 연결. 첫 부팅은 2~3분(자동 설정·확장).

## 2. 접속 (Windows PowerShell 또는 WSL)
```powershell
ssh mgoh@pi-rt.local          # 안 되면 공유기 관리 페이지에서 pi-rt 의 IP 를 찾아  ssh mgoh@<IP>
```
첫 접속 직후 몇 분은 자동 업데이트가 apt 를 잡고 있다. `sudo apt update` 가 "lock" 으로 막히면 3~5분 기다린다.
```bash
sudo apt update && sudo apt install -y git build-essential cmake python3 rt-tests stress-ng
cat /sys/class/thermal/thermal_zone0/temp     # 천 단위 밀리도. 45000 = 45 °C
```

## 3. 저장소 빌드 (Pi 에서, 3분)
```bash
git clone https://github.com/ohevance/rt-robot-data-infra.git && cd rt-robot-data-infra
cmake -S rt_control/rt_core -B build/rt_core -DCMAKE_BUILD_TYPE=Release && cmake --build build/rt_core -j4
ctest --test-dir build/rt_core --output-on-failure            # 4 tests passed (arm64 에서도 그대로)
```

## 4. 먼저 **일반 커널**에서 기준값 (RT 켜기 전에! 10분)
측정 전 준비 두 가지(측정 때마다):
```bash
echo performance | sudo tee /sys/devices/system/cpu/cpu*/cpufreq/scaling_governor >/dev/null   # 클럭 고정 (주파수 변경 지연 제거)
cat /sys/class/thermal/thermal_zone0/temp                                                        # 75000 넘으면 식힌 뒤
```
```bash
sudo ./build/rt_core/jitter_bench --prio 80 --seconds 60 --label pi4_generic_idle   --json docs/measurements/jitter_pi4_generic_idle.json
stress-ng --cpu 4 --io 2 --vm 1 --vm-bytes 256M --timeout 75s >/dev/null 2>&1 &
sleep 3; sudo ./build/rt_core/jitter_bench --prio 80 --seconds 60 --label pi4_generic_stress --json docs/measurements/jitter_pi4_generic_stress.json; wait
sudo scripts/cyclictest_run.sh pi4_generic_stress 300 stress
```

## 5. 실시간 커널 켜기 (10분 + 재부팅)
Ubuntu Pro 개인 구독은 무료(기기 5대): ubuntu.com/pro 에서 토큰 발급.
```bash
sudo pro attach <토큰>
sudo pro enable realtime-kernel --variant=raspi     # Pi 4/5 용 변종. 묻는 것에 y
sudo reboot
# 다시 접속해서
uname -r                     # ...-raspi-realtime (또는 realtime 이 들어간 이름)
cat /sys/kernel/realtime     # 1 이면 PREEMPT_RT
```
`--variant=raspi` 를 모른다고 하면 `sudo pro enable realtime-kernel` 로 시도하고, 그래도 안 되면 `pro status` 출력을 보내 준다.
되돌리기(필요하면): `sudo pro disable realtime-kernel && sudo reboot`.

## 6. 실시간 커널에서 측정 (30분 + cyclictest)
```bash
cd ~/rt-robot-data-infra
echo performance | sudo tee /sys/devices/system/cpu/cpu*/cpufreq/scaling_governor >/dev/null
# B) 한가할 때
sudo ./build/rt_core/jitter_bench --prio 80 --seconds 60 --label pi4_rt_idle --json docs/measurements/jitter_pi4_rt_idle.json
# C) 부하 중
stress-ng --cpu 4 --io 2 --vm 1 --vm-bytes 256M --timeout 75s >/dev/null 2>&1 &
sleep 3; sudo ./build/rt_core/jitter_bench --prio 80 --seconds 60 --label pi4_rt_stress --json docs/measurements/jitter_pi4_rt_stress.json; wait
# D) 부하 중 + RT 스레드를 CPU 3 에 고정
stress-ng --cpu 4 --io 2 --vm 1 --vm-bytes 256M --timeout 75s >/dev/null 2>&1 &
sleep 3; sudo ./build/rt_core/jitter_bench --prio 80 --cpu 3 --seconds 60 --label pi4_rt_stress_pin --json docs/measurements/jitter_pi4_rt_stress_pin.json; wait
# cyclictest (표준 도구) — 한가 / 부하, 각 10분. 방열판이 있으면 1800 으로
sudo scripts/cyclictest_run.sh pi4_rt_idle   600
sudo scripts/cyclictest_run.sh pi4_rt_stress 600 stress
```

## 7. (선택, 가장 큰 개선) CPU 3 을 커널에서 떼어 내기 — isolcpus
RT 스레드만 쓰는 CPU 를 하나 비워 두면 max 가 크게 준다. 부팅 인자 한 줄:
```bash
sudo cp /boot/firmware/cmdline.txt /boot/firmware/cmdline.txt.bak
sudo sed -i '1 s/$/ isolcpus=3 nohz_full=3 rcu_nocbs=3/' /boot/firmware/cmdline.txt    # 한 줄 파일의 끝에 덧붙인다 (줄바꿈 없이)
sudo reboot
# 다시 접속 → cat /sys/devices/system/cpu/isolated  → 3
stress-ng --cpu 3 --io 2 --vm 1 --vm-bytes 256M --timeout 75s >/dev/null 2>&1 &
sleep 3; sudo ./build/rt_core/jitter_bench --prio 80 --cpu 3 --seconds 60 --label pi4_rt_stress_isol --json docs/measurements/jitter_pi4_rt_stress_isol.json; wait
```

## 8. 표① 만들고 결과 가져오기
Pi 에서:
```bash
python3 scripts/make_table1.py --cyclictest 'docs/measurements/cyclictest_pi4_*.txt' --jitter 'docs/measurements/jitter_pi4_*.json' --out docs/measurements/table1_pi4.md
cat docs/measurements/table1_pi4.md
```
WSL 에서 (Pi 의 결과 파일을 저장소로):
```bash
scp 'mgoh@pi-rt.local:~/rt-robot-data-infra/docs/measurements/*pi4*' docs/measurements/      # .local 이 안 되면 IP
python3 scripts/make_table1.py --cyclictest 'docs/measurements/cyclictest_*.txt' --jitter 'docs/measurements/jitter_*.json' --out docs/measurements/table1.md
git add docs/measurements && git commit -m "measurements: 표① Pi 4 PREEMPT_RT 실측" && git push
```

## 읽는 법 (무엇이 나와야 "정상"인가 — 예상 범위, 실측 전 추정)
| 조건 | 기대(추정) | 뜻 |
|---|---|---|
| 일반 커널 + 부하 | max 수 ms | 커널이 선점 불가 구간에서 멈춘다 — WSL 과 같은 모양 |
| RT 커널, 한가 | max 수십 us | 선점형 커널의 바닥 |
| RT 커널 + 부하 | max 100~200 us | Pi 4 의 알려진 수준(Pi 5 보다 높다). 1 ms 주기 안에 **항상** 들어오면 통과 |
| RT + 부하 + isolcpus | max 가 C) 의 절반 이하로 | CPU 를 떼어 낸 효과 |
표에서 보는 것은 평균이 아니라 **p99.9 와 max**. 이 네 줄이 "우선순위가 아니라 커널이 꼬리를 자른다"는 D0 의 주장을 증명한다.

## 보내 주실 것
`table1_pi4.md` 내용, `uname -r` 과 `/sys/kernel/realtime`, 측정 때 온도(`thermal_zone0/temp`) 최고값, 안 된 명령과 오류 그대로.

---
(노트북 네이티브 Ubuntu 로 할 때도 같은 순서. `--variant=raspi` 만 빼고, NVIDIA 드라이버가 RT 커널과 충돌하면 GRUB 에서 일반 커널로 부팅해 쓴다.)
