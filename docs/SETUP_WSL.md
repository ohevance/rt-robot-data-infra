# WSL2 (Ubuntu 24.04) 개발 환경 — 한 번만 하면 되는 설치

확인된 상태(2026-11-03): 12 CPU · 15 GB · Python 3.12 · git · g++ · Docker(동작 중). **없는 것: cmake, ROS 2.**

## 1. 기본 도구 (1분)
```bash
sudo apt update
sudo apt install -y cmake build-essential python3-venv python3-pip curl
```

## 2. ROS 2 Jazzy (10분) — docs.ros.org 의 Jazzy 설치 문서 그대로
```bash
sudo apt install -y software-properties-common
sudo add-apt-repository -y universe
sudo apt update && sudo apt install -y curl
export ROS_APT_SOURCE_VERSION=$(curl -s https://api.github.com/repos/ros-infrastructure/ros-apt-source/releases/latest | grep -F "tag_name" | awk -F\" '{print $4}')
curl -L -o /tmp/ros2-apt-source.deb "https://github.com/ros-infrastructure/ros-apt-source/releases/download/${ROS_APT_SOURCE_VERSION}/ros2-apt-source_${ROS_APT_SOURCE_VERSION}.$(. /etc/os-release && echo $VERSION_CODENAME)_all.deb"
sudo dpkg -i /tmp/ros2-apt-source.deb
sudo apt update
sudo apt install -y ros-jazzy-ros-base ros-dev-tools ros-jazzy-rmw-cyclonedds-cpp
echo "source /opt/ros/jazzy/setup.bash" >> ~/.bashrc
source ~/.bashrc
ros2 --help | head -3        # 동작 확인
```
- `ros-base` = GUI 없는 기본 묶음(이 저장소에는 충분). `rmw-cyclonedds-cpp` = DDS 두 번째 구현체(표②에서 Fast DDS와 비교용).

## 3. 저장소 가져오기
GitHub가 연결되면:
```bash
cd ~ && git clone https://github.com/<아이디>/rt-robot-data-infra.git
```
그 전에는 공유 폴더(zip)에서:
```bash
cd ~ && unzip /mnt/c/Users/mgoh/Documents/robot-portfolio/rt-robot-data-infra_D0.zip
```

## 4. 파이썬 가상환경 (이 저장소 전용)
```bash
cd ~/rt-robot-data-infra
python3 -m venv .venv && source .venv/bin/activate
pip install --upgrade pip
pip install mujoco numpy pyyaml paho-mqtt     # D3 이후에 쓰는 것들. 미리 받아 둠
```

## 5. 동작 확인
```bash
cmake -S rt_control/rt_core -B build/rt_core -DCMAKE_BUILD_TYPE=Release
cmake --build build/rt_core -j
ctest --test-dir build/rt_core --output-on-failure      # 2 tests passed
```

## WSL에서 되는 것 / 안 되는 것
- 되는 것: 빌드·테스트, ROS 2, DDS(같은 PC 안), MuJoCo(WSLg로 창도 뜸), Docker 관제 스택, CI 리허설.
- 안 되는 것: **표① 실시간 지연 측정**. WSL 커널은 Windows 위의 가상 커널이라 cyclictest·jitter_bench 수치가 "실시간 커널의 수치"가 아니다. 참고값으로만 쓰고, 실측은 네이티브 Ubuntu(노트북 / 외장 SSD / Pi 5)에서 `docs/SETUP_RT_MEASURE.md` 순서로.
