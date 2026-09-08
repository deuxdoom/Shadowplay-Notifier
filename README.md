# 🎬 ShadowPlay Notifier

[![RELEASE](https://img.shields.io/github/release/deuxdoom/Shadowplay-Notifier?style=flat&logo=github&logoColor=white&label=RELEASE&labelColor=2f353a&color=0ea5e9)](https://github.com/deuxdoom/Shadowplay-Notifier/releases/latest)
[![Downloads Latest](https://img.shields.io/github/downloads/deuxdoom/Shadowplay-Notifier/latest/total?logo=github&style=flat&label=DOWNLOADS@LATEST&labelColor=2f353a)](https://github.com/deuxdoom/Shadowplay-Notifier/releases/latest)
[![Downloads Total](https://img.shields.io/github/downloads/deuxdoom/Shadowplay-Notifier/total?logo=github&style=flat&label=DOWNLOADS&labelColor=2f353a)](https://github.com/deuxdoom/Shadowplay-Notifier/releases)
[![LICENSE](https://img.shields.io/badge/LICENSE-MIT-22c55e?style=flat&labelColor=2f353a)](LICENSE)  
[![Platform](https://img.shields.io/badge/PLATFORM-WINDOWS%2010%2F11-0078d4?style=flat&logo=windows&logoColor=white&labelColor=2f353a)](https://github.com/deuxdoom/Shadowplay-Notifier)
[![PYTHON](https://img.shields.io/badge/PYTHON-3.8%2B-3776ab?style=flat&logo=python&logoColor=white&labelColor=2f353a)](https://www.python.org/)
[![TKINTER](https://img.shields.io/badge/GUI-TKINTER-f59e0b?style=flat&logoColor=white&labelColor=2f353a)](https://docs.python.org/3/library/tkinter.html)
[![NVIDIA](https://img.shields.io/badge/FOR-NVIDIA%20SHADOWPLAY-76b900?style=flat&logo=nvidia&logoColor=white&labelColor=2f353a)](https://www.nvidia.com/geforce/nvidia-app/)

![녹화 중인 화면](main.png)

---

## 📌 간단 소개

- **ShadowPlay Notifier**는 NVIDIA ShadowPlay(NVIDIA App)의 **녹화 상태를 보조
  모니터에 크게 표시**해 주는 Windows 앱입니다.
- NVIDIA App 의 녹화 상태 아이콘이 영상에 그대로 찍히는 것이 싫어서 그 표시를
  꺼 두면, 정작 녹화가 돌아가고 있는지 알 길이 없어집니다. 이 앱은 그 자리를
  대신합니다.
- 녹화 폴더를 지켜보면서 파일이 커지는지, 파일이 쓰기로 열려 있는지를 보고
  판단합니다. **녹화 프로그램에 끼어들지 않고 폴더를 읽기만 하므로** 어떤 녹화
  도구를 쓰든 동작하며, 녹화 결과물에는 손대지 않습니다.
- 별도의 설치 과정이 없고 Python 도 필요하지 않습니다. 실행 파일 하나로 씁니다.

---

## ✨ 주요 기능

- 🔴 **녹화 상태 표시** — 녹화가 시작되면 배너가 빨갛게 바뀌고 원형 표시등이
  1초 주기로 깜박여서, 멀리서도 한눈에 알아볼 수 있습니다.
- 📊 **녹화 정보 확인** — 저장 폴더, 파일 이름, 경과 시간, 용량, 비트레이트,
  마지막으로 파일이 커진 시각을 보여 줍니다. 대기 중에는 직전 녹화 요약과
  세션 누적 횟수가 대신 나옵니다.
- ⚡ **빠른 반응** — 파일이 쓰기로 열려 있는지를 함께 보므로, 녹화를 시작하거나
  멈추면 폴링 주기 한 번 안에 화면에 반영됩니다.
- 🖥️ **보조 모니터 지원** — 기본 960×640 화면이며, 창 크기와 같은 모니터를
  자동으로 찾아 그 자리에 띄웁니다. 전체화면으로 바꾸면 글자와 정보 영역이
  해상도에 맞춰 함께 커집니다.
- ⚙️ **간편 설정** — 감시 폴더, 표시할 모니터, 항상 위에 표시, 알림음을 창에서
  바로 바꿀 수 있습니다.

---

## 📦 설치 및 실행

1. [Releases](https://github.com/deuxdoom/Shadowplay-Notifier/releases/latest)에서
   ZIP 파일을 내려받아 압축을 풉니다.
2. `ShadowPlayNotifier.exe`를 실행합니다.
3. 오른쪽 위 **⚙️ 환경설정**에서 NVIDIA App 의 동영상 저장 폴더를 지정하고
   저장합니다.

**Windows 10 이상**에서 사용하며, Python 을 따로 설치할 필요가 없습니다.

---

## 🖱️ 기본 조작

| 동작 | 방법 |
| --- | --- |
| 창 이동 | 창의 아무 곳이나 마우스로 끌기 |
| 전체화면 | 오른쪽 위 전체화면 버튼 또는 `F11` |
| 전체화면 해제·종료 | `Esc` |
| 닫기 | 오른쪽 위 `✕` 버튼 |

키보드 단축키는 창을 한 번 클릭한 뒤에 씁니다. 타이틀바가 없는 창이라 초점을
자동으로 받지 못하기 때문입니다.

---

## ⚙️ 설정

환경설정 창에서 바꾼 값은 실행 파일 옆의 `config.json`에 저장되고 곧바로
적용됩니다. 앱을 껐다 켤 필요가 없습니다.

| 항목 | 설명 |
| --- | --- |
| 녹화 폴더 | 녹화 중에 파일이 커지는 폴더입니다. 하위 폴더까지 함께 봅니다. |
| 폴링 주기 | 폴더를 훑어보는 간격입니다. 기본 0.5초입니다. |
| 중단 판정 시간 | 파일이 커지지 않은 채 이만큼 지나면 녹화가 끝난 것으로 봅니다. |
| 표시할 모니터 | `-1`이면 창 크기와 같은 해상도의 모니터를 자동으로 고릅니다. |
| 항상 위 · 테두리 없음 · 소리 | 게임 녹화에 소리가 섞이면 안 되므로 알림음은 기본 꺼짐입니다. |

동작 기록과 오류는 `monitor.log`에 남습니다. 녹화가 감지되지 않으면 먼저 녹화
폴더 경로부터 확인하십시오.

---

## 📜 라이선스

이 프로젝트는 **MIT 라이선스**를 따릅니다. 전문은 [LICENSE](LICENSE)에 있습니다.

```
Copyright (c) 2026 deuxdoom
```

배너에 쓰는 아이콘은 Microsoft 의
[Fluent UI System Icons](https://github.com/microsoft/fluentui-system-icons)에서
가져왔으며, 이 역시 MIT 라이선스입니다.
