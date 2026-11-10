#!/usr/bin/env python3
"""paho-mqtt 2.x 를 pip·apt 없이 설치한다 — PyPI 에서 휠을 받아 sha256 을 확인하고 이 사용자의 site-packages 에 푼다.

왜 이 파일이 있나 (11/10, Pi 첫 설치에서)
  - 에이전트는 paho-mqtt 2.0 이상이 필요하다(CallbackAPIVersion). Ubuntu 24.04 의 apt 패키지(python3-paho-mqtt)는 1.6 이다.
  - 새 Ubuntu 이미지에는 pip 이 없다. pip 을 apt 로 깔려는데 자동 보안 업데이트(unattended-upgrade)가 dpkg 잠금을
    30분 넘게 쥐고 있어 설치가 멈췄다. 장치를 붙이는 일이 OS 업데이트를 기다리면 안 된다.
  - paho-mqtt 는 순수 파이썬(py3-none-any 휠)이라 압축을 풀기만 하면 된다. 표준 라이브러리만 쓴다.
무결성: PyPI 가 알려 주는 sha256 과 받은 파일의 sha256 을 비교한다. 다르면 풀지 않는다.
  (같은 서버가 알려 준 값이므로 전송 중 손상·잘림을 막는 것이지 공급망 공격을 막는 것은 아니다 — HTTPS 가 그 몫)

사용:  python3 deploy/pi/get_paho.py            (deploy/pi/install.sh 가 필요할 때 부른다)
"""
import hashlib
import io
import json
import os
import site
import sys
import urllib.request
import zipfile

VERSION = "2.1.0"      # 고정 — 장치마다 같은 것을 쓴다


def main():
    meta_url = f"https://pypi.org/pypi/paho-mqtt/{VERSION}/json"
    with urllib.request.urlopen(meta_url, timeout=30) as response:
        meta = json.load(response)
    wheels = [f for f in meta["urls"] if f["filename"].endswith("py3-none-any.whl")]
    if len(wheels) == 0:
        print("순수 파이썬 휠을 찾지 못했습니다")
        return 1
    wheel = wheels[0]
    with urllib.request.urlopen(wheel["url"], timeout=60) as response:
        data = response.read()
    if hashlib.sha256(data).hexdigest() != wheel["digests"]["sha256"]:
        print("sha256 이 다릅니다 — 풀지 않습니다")
        return 1
    target = site.getusersitepackages()
    os.makedirs(target, exist_ok=True)
    with zipfile.ZipFile(io.BytesIO(data)) as archive:
        archive.extractall(target)
    print(f"paho-mqtt {VERSION} → {target}  ({len(data)} bytes, sha256 일치)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
