# 표① 실측 — Raspberry Pi 4 Model B (4 GB) + Ubuntu 24.04 + PREEMPT_RT

목표: **실시간 커널에서 재는 표①의 진짜 숫자.** WSL 값은 참고값일 뿐이고, 이 숫자가 포트폴리오의 핵심이다.
실시간 커널이 일반 커널과 무엇이 다른지는 [`GLOSSARY.md` → PREEMPT_RT](GLOSSARY.md#preempt_rt-실시간-커널-패치) 에 표·비유·면접 한 문장으로 적어 두었다.
Pi 4B 4 GB 로 충분하다(64-bit Cortex-A72 4코어). 모니터·키보드는 첫 부팅 확인에만 쓰고 이후는 SSH 로 한다.
**1~8단계 전부 11/04~05 에 실제로 거쳤다.** 결과는 `docs/measurements/table1_pi4.md`(14줄), 해석은 `docs/experiments/E18.md`·`E19a~d.md`. 다시 잴 때(다른 보드, 방열판 뒤)는 같은 순서로.

명령 앞의 **[Pi 창]** 은 `mgoh@pi-rt:~$` 프롬프트(SSH), **[WSL 창]** 은 `(.venv) mgoh@DESKTOP…:~/rt-robot-data-infra$` 프롬프트다.
11/04 에 WSL 용 명령을 Pi 창에 쳐서 복사·커밋이 실패했다 — 창을 먼저 본다.

## 0. 준비물
| 있어야 하는 것 | 메모 |
|---|---|
| Raspberry Pi 4 Model B 4 GB | ✓ |
| microSD 16 GB 이상 + 카드 리더 | ✓ Samsung PRO Plus 512 GB (A2). 기존 카드(다른 곳에서 쓰던 Raspberry Pi OS)는 건드리지 않고 보관 |
| USB-C 전원 **5 V / 3 A** | ✓. 약한 충전기면 저전압 경고 → 클럭이 흔들려 **측정이 오염**된다 |
| 네트워크 | **Wi-Fi 로 충분했다**(SSH·scp 모두). 이더넷은 선택 |
| (선택) 방열판 또는 팬 | **없으면 부하 측정은 120초까지.** 11/04: 부하 75초에 45 → 75 °C. Pi 4 는 80 °C 부터 클럭을 내린다(스로틀) |

## 1. SD 카드 굽기 (Windows, 10분) — 완료
1. **Raspberry Pi Imager** 설치 (raspberrypi.com/software). 카드를 따로 포맷할 필요 없다(Imager 가 지운다).
2. Device: *Raspberry Pi 4* → OS: *Other general-purpose OS → Ubuntu → **Ubuntu Server 24.04 LTS (64-bit)*** → Storage: SD 카드(시스템 드라이브 제외 체크 유지).
3. NEXT → **Edit Settings**: hostname `pi-rt`, 사용자 `mgoh` + 비밀번호, Wi-Fi SSID/비밀번호 + 국가 `KR`(전파 규제 지역 코드), 시간대 Asia/Seoul, 키보드 `us`(한글 키보드도 배열은 us); **Services 탭 → Enable SSH (password authentication)** → Save → Yes → 쓰기.
4. 카드를 Pi 에 꽂고 전원. 첫 부팅 2~3분. 모니터가 있으면 로그인 화면 위의 `wlan0: <IP>` 를 적어 둔다. 없으면 공유기 관리 페이지에서 `pi-rt` 의 IP.

## 2. 접속 (Windows PowerShell) — 완료
```powershell
ssh mgoh@192.168.45.250        # IP 는 1-4 에서 적은 것. 처음엔 yes → 비밀번호
```
첫 접속 직후 몇 분은 자동 업데이트가 apt 를 잡고 있다. "Could not get lock" 이면 3~5분 기다린다.
```bash
# [Pi 창]
sudo apt update && sudo apt install -y git build-essential cmake python3 rt-tests stress-ng
```
(설치 끝에 needrestart 가 서비스 재시작 목록을 보여 준다 — 정상. ssh 가 재시작돼도 지금 세션은 유지된다.)

## 3. 저장소 빌드 (Pi 에서, 3분) — 완료
```bash
# [Pi 창]
git clone https://github.com/ohevance/rt-robot-data-infra.git && cd rt-robot-data-infra
cmake -S rt_control/rt_core -B build/rt_core -DCMAKE_BUILD_TYPE=Release && cmake --build build/rt_core -j4
ctest --test-dir build/rt_core --output-on-failure            # 11/04: 4/4 passed (arm64, GCC 13.3)
```

## 4. 일반 커널 기준값 (RT 켜기 전에) — 완료, `table1_pi4.md`
측정 전 준비(측정 때마다): 클럭 고정 + 온도 50 °C 아래 + 스로틀 이력 확인.
```bash
# [Pi 창]
echo performance | sudo tee /sys/devices/system/cpu/cpu*/cpufreq/scaling_governor >/dev/null   # 주파수 변경 지연 제거
cat /sys/class/thermal/thermal_zone0/temp                       # 밀리도. 50000 아래에서 시작
cat /sys/devices/platform/soc/soc:firmware/get_throttled        # 0 이면 부팅 후 스로틀 없음 (0x80000/0x40000 포함이면 이력 있음)
```
측정(스크립트가 부하·온도·스로틀을 `.meta` 에 같이 남긴다). 측정 중 Pi 창에 아무것도 치지 않는다:
```bash
# [Pi 창]
sudo scripts/jitter_run.sh     pi4_generic_idle   60
sudo scripts/jitter_run.sh     pi4_generic_stress 60  stress
sudo scripts/cyclictest_run.sh pi4_generic_idle   300
sudo scripts/cyclictest_run.sh pi4_generic_stress 120 stress        # 방열판 없으면 120 (300 은 80 °C 를 넘긴다)
```
11/04 결과: jitter max 24.9 / 781.2 us, cyclictest max 376 / 695 us(한가/부하), 스로틀 0.

## 5. 실시간 커널 켜기 (10분 + 재부팅) — 완료 11/05: `6.8.0-2054-raspi-realtime`, `/sys/kernel/realtime` = 1
Ubuntu Pro 개인 구독은 무료(기기 5대). 토큰을 받는 길:
1. PC 브라우저 **시크릿 창**에서 `login.ubuntu.com/+new_account` → Ubuntu One 가입(이메일·영문 이름·소문자 사용자명·비밀번호) → 인증 메일 링크.
2. `ubuntu.com/pro/dashboard` → Sign in → **Free Personal Token** `C1…` 복사. (토큰은 채팅·문서에 적지 않는다.)
- 11/04 함정: 가입이 "Oops" / *"Dry run of setting username(...) in Launchpad failed with (The read operation timed out)"* 로 실패 = Canonical 의 Launchpad 가 응답하지 않은 것. 입력값 문제가 아니다 → 30분~반나절 뒤 재시도. `ubuntu.com/pro` 에서 시작하면 되돌아오는 단계에서 또 깨지므로 `login.ubuntu.com` 에서 직접 가입한다.
```bash
# [Pi 창]
sudo pro attach <토큰>
sudo pro enable realtime-kernel --variant=raspi     # Pi 4/5 용 변종. 묻는 것에 y
sudo reboot
# 1~2분 뒤 PowerShell 에서 다시 ssh
uname -r                     # ...-raspi-realtime (또는 realtime 이 들어간 이름)
cat /sys/kernel/realtime     # 1 이면 PREEMPT_RT
```
`--variant=raspi` 를 모른다고 하면 `sudo pro enable realtime-kernel` 로 시도하고, 그래도 안 되면 `pro status` 출력을 보낸다.
되돌리기(필요하면): `sudo pro disable realtime-kernel && sudo reboot`.
플랜 B(토큰이 끝내 안 되면): WSL 에서 Pi 커널(rpi-6.12.y)을 `CONFIG_PREEMPT_RT=y` 로 크로스 컴파일해 `/boot/firmware` 에 올린다 — 2~3시간, 별도 안내.

## 6. 실시간 커널에서 측정 (약 15분) — 완료 11/05: jitter max 27.8 / 300.6 / 311.5, cyclictest max 37 / 132
4단계와 **같은 명령, 라벨만 `pi4_rt_*`**. 온도 50 °C 아래에서 시작, 조건 사이에 2~3분 식힌다.
```bash
# [Pi 창]
cd ~/rt-robot-data-infra
echo performance | sudo tee /sys/devices/system/cpu/cpu*/cpufreq/scaling_governor >/dev/null
sudo scripts/jitter_run.sh     pi4_rt_idle       60
sudo scripts/jitter_run.sh     pi4_rt_stress     60  stress
sudo scripts/jitter_run.sh     pi4_rt_stress_pin 60  stress 3      # RT 스레드를 CPU 3 에 고정
sudo scripts/cyclictest_run.sh pi4_rt_idle       300
sudo scripts/cyclictest_run.sh pi4_rt_stress     120 stress
```
각 명령 끝의 `temp: a -> b mC | throttled: 0` 에서 **throttled 가 0 이 아니면 그 줄은 버리고 식힌 뒤 다시** 잰다.

## 7. (선택, 가장 큰 개선) CPU 3 을 커널에서 떼어 내기 — isolcpus — 완료 11/05: max 189, work max 53
RT 스레드만 쓰는 CPU 를 하나 비워 두면 max 가 크게 준다. 부팅 인자 한 줄:
```bash
# [Pi 창]
sudo cp /boot/firmware/cmdline.txt /boot/firmware/cmdline.txt.bak
sudo sed -i '1 s/$/ isolcpus=3 nohz_full=3 rcu_nocbs=3/' /boot/firmware/cmdline.txt    # 한 줄 파일의 끝에 덧붙인다
sudo reboot
# 다시 접속 → cat /sys/devices/system/cpu/isolated  → 3
sudo scripts/jitter_run.sh pi4_rt_stress_isol 60 stress 3
```
(부하 생성기 stress-ng 는 격리된 CPU 3 에는 올라가지 않으므로 "부하 3코어 + RT 전용 1코어" 상태가 된다.)

## 8. 표① 만들고 결과 가져오기 — 완료 11/05 (커밋 8f06d39)
```bash
# [Pi 창] — sudo 로 만든 결과가 root 소유라 나중에 git pull 이 막힌다. 내 것으로 바꿔 둔다
sudo chown -R mgoh:mgoh ~/rt-robot-data-infra
python3 scripts/make_table1.py --cyclictest 'docs/measurements/cyclictest_pi4_*.txt' --jitter 'docs/measurements/jitter_pi4_*.json' --out docs/measurements/table1_pi4.md
cat docs/measurements/table1_pi4.md
```
```bash
# [WSL 창] — Pi 의 결과 파일을 저장소로 (Pi 에는 GitHub 로그인이 없다. Pi 는 측정만, 커밋은 WSL 에서)
scp 'mgoh@192.168.45.250:~/rt-robot-data-infra/docs/measurements/*pi4*' docs/measurements/
python3 scripts/make_table1.py --cyclictest 'docs/measurements/cyclictest_pi4_*.txt' --jitter 'docs/measurements/jitter_pi4_*.json' --out docs/measurements/table1_pi4.md
git add docs/measurements && git commit -m "measurements: 표① Pi 4 PREEMPT_RT 실측" && git push
```

## 6-1. 도구 두 개가 다르게 나올 때 (11/05 에 실제로 겪음 — `docs/experiments/E19d.md`)
cyclictest 와 jitter_bench 의 max 가 2배 넘게 다르면 측정기를 의심하기 전에 **설정을 같게** 맞춰 본다:
```bash
# [Pi 창] 같은 설정 = 스레드 1개, 같은 CPU, 같은 우선순위, 일 0, 같은 부하
STRESS_VM_BYTES=256M JITTER_WORK_US=0 sudo -E scripts/jitter_run.sh chk_jitter 60 stress 2
stress-ng --cpu 4 --io 2 --vm 1 --vm-bytes 256M --timeout 75s >/dev/null 2>&1 &
sleep 3; sudo cyclictest -m -p 80 -a 2 -t 1 -i 1000 -h 1000 -q -D 60 > docs/measurements/cyclictest_chk.txt; wait
```
11/05 결과 274 vs 270 — 같았다. 차이는 cyclictest `-S`(CPU 마다 스레드)와 부하의 `--vm-bytes` 에서 왔다. **두 도구를 직접 비교하는 줄은 `STRESS_VM_BYTES` 를 같게 준다.**

## 읽는 법 (무엇이 나와야 "정상"인가)
| 조건 | 11/04 실측(일반 커널) | RT 커널 기대(추정) | 뜻 |
|---|---|---|---|
| 한가 | cyclictest 5분 max **376** us (jitter 60 s 는 24.9) | max 수십 us → **실측 37** (jitter 27.8) ✓ | 일반 커널은 한가해도 분 단위로 수백 us 를 뺏긴다. RT 는 그 작업들도 선점된다 |
| 부하 | cyclictest max **695**, jitter max **781** us, `work time` 이 134.9 까지 밀림 | max 100~200 us → **실측 cyclictest 132 ✓, jitter 301**(p99 는 146 → 185 로 비용) | Pi 4 의 알려진 수준. 1 ms 주기 안에 **항상** 들어오면 통과 |
| 부하 + CPU 3 고정 | — | 부하와 비슷하거나 약간 개선 → **실측 311** (변화 없음) ✓ | 고정만으로는 커널 작업을 못 막는다 |
| 부하 + isolcpus | — | max 가 부하의 절반 이하 → **실측 189, work max 53** ✓ | CPU 를 떼어 낸 효과. 잔여 189 는 격리된 CPU 에도 오는 것(타이머·IPI) |
표에서 보는 것은 평균이 아니라 **p99.9 와 max**. 이 줄들이 "우선순위가 아니라 커널이 꼬리를 자른다"는 D0 의 주장을 증명한다.

## 보내 주실 것
각 명령 끝의 표와 `temp/throttled` 줄, `uname -r` 과 `/sys/kernel/realtime`, 안 된 명령과 오류 그대로.

---
(노트북 네이티브 Ubuntu 로 할 때도 같은 순서. `--variant=raspi` 만 빼고, NVIDIA 드라이버가 RT 커널과 충돌하면 GRUB 에서 일반 커널로 부팅해 쓴다.)
