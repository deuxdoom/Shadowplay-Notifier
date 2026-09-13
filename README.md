# 🎬 ShadowPlay Notifier

[![RELEASE](https://img.shields.io/github/release/deuxdoom/Shadowplay-Notifier?style=flat&logo=github&logoColor=white&label=RELEASE&labelColor=2f353a&color=0ea5e9)](https://github.com/deuxdoom/Shadowplay-Notifier/releases/latest)
[![Downloads Latest](https://img.shields.io/github/downloads/deuxdoom/Shadowplay-Notifier/latest/total?logo=github&style=flat&label=DOWNLOADS@LATEST&labelColor=2f353a)](https://github.com/deuxdoom/Shadowplay-Notifier/releases/latest)
[![Downloads Total](https://img.shields.io/github/downloads/deuxdoom/Shadowplay-Notifier/total?logo=github&style=flat&label=DOWNLOADS&labelColor=2f353a)](https://github.com/deuxdoom/Shadowplay-Notifier/releases)
[![LICENSE](https://img.shields.io/badge/LICENSE-MIT-22c55e?style=flat&labelColor=2f353a)](LICENSE)  
[![Platform](https://img.shields.io/badge/PLATFORM-WINDOWS%2010%2F11-0078d4?style=flat&logo=windows&logoColor=white&labelColor=2f353a)](https://github.com/deuxdoom/Shadowplay-Notifier)
[![PYTHON](https://img.shields.io/badge/PYTHON-3.14%2B-3776ab?style=flat&logo=python&logoColor=white&labelColor=2f353a)](https://www.python.org/)
[![TKINTER](https://img.shields.io/badge/GUI-TKINTER-f59e0b?style=flat&logoColor=white&labelColor=2f353a)](https://docs.python.org/3/library/tkinter.html)
[![NVIDIA](https://img.shields.io/badge/FOR-NVIDIA%20SHADOWPLAY-76b900?style=flat&logo=nvidia&logoColor=white&labelColor=2f353a)](https://www.nvidia.com/geforce/nvidia-app/)

<p align="center">
  <img src="main.png" alt="녹화 중인 화면" width="100%">
</p>

<p align="center">
  <img src="wallpaper.png" alt="월페이퍼 화면" width="100%">
</p>

<p align="center">
  <a href="https://deuxdoom.github.io/Shadowplay-Notifier/">
    <img src="https://img.shields.io/badge/WEBSITE-deuxdoom.github.io-ff3b46?style=for-the-badge&logo=github&logoColor=white&labelColor=2f353a" alt="WEBSITE">
  </a>
</p>

---

## 📌 소개

NVIDIA App 의 녹화 상태 아이콘이 영상에 그대로 찍히는 것이 싫어서 표시를 꺼 두면,
정작 녹화가 돌아가고 있는지 알 길이 없어집니다. **ShadowPlay Notifier** 는 그 자리를
대신해 **녹화 상태를 보조 모니터에 크게 표시**해 주는 Windows 앱입니다.

녹화 폴더를 지켜보면서 파일이 커지는지, 파일이 쓰기로 열려 있는지를 보고 판단합니다.
**녹화 프로그램에 끼어들지 않고 폴더를 읽기만 하므로** 어떤 녹화 도구를 쓰든 동작하며,
녹화 결과물에는 손대지 않습니다.

녹화를 기다리는 동안에는 **시계와 날씨, 지금 듣는 음악을 보여 주는 월페이퍼 화면**이
됩니다. 녹화가 시작되면 곧바로 녹화 화면으로 바뀌고, 끝나면 다시 돌아옵니다.

설치 과정이 없고 Python 도 필요하지 않습니다. 실행 파일 하나로 씁니다.

---

## ✨ 주요 기능

**녹화 화면**

- **녹화 상태 표시** — 녹화가 시작되면 붉은 표시등과 큰 경과 시간으로 바뀝니다.
  표시등은 더 밝은 쪽으로 깜박이면서 크기도 함께 커지므로 멀리서도 알아볼 수 있습니다.
- **녹화 정보** — 저장 폴더, 파일 이름, 경과 시간, 용량, 비트레이트, 마지막으로 파일이
  커진 시각을 보여 줍니다.
- **빠른 반응** — 파일이 쓰기로 열려 있는지를 함께 보므로, 녹화를 시작하거나 멈추면
  폴링 주기 한 번 안에 화면에 반영됩니다.
- **이어지는 화면 전환** — 녹화 화면과 월페이퍼가 같은 배경과 골격을 씁니다. 시계가
  있던 자리에 경과 시간이, 기온이 있던 자리에 용량이 들어갑니다.

**월페이퍼 화면**

- **시계와 날씨** — 큰 시계와 날짜, 요일, 기온, 오늘 최고·최저 기온, 습도, 강수 확률을
  보여 줍니다.
- **재생 중인 음악** — Spotify 에서 듣고 있는 곡과 아티스트, 앨범 커버를 보여 줍니다.
  로그인이나 계정 연결이 필요 없습니다.
- **소리에 맞춰 움직이는 파형** — 스피커로 나가는 소리를 무지개색 막대로 그립니다.
  소리를 녹음하거나 저장하지 않고 세기만 잽니다.
- **오늘 달** — 실제 달 사진에 그날의 그늘을 덮어 그리므로 초승달인지 보름달인지
  한눈에 알 수 있습니다.
- **사계절 사진** — 봄(3-5월)은 벚꽃 가지, 여름(6-8월)은 바다, 가을(9-11월)은 코코아와
  책, 겨울(12-2월)은 얼음 구슬입니다. 사진은 실행 파일에 들어 있어 인터넷 연결이
  없어도 나옵니다.
- **시간대마다 달라지는 색** — 새벽의 남색부터 저녁의 어스름한 보랏빛까지, 시각에 따라
  화면 전체의 색조가 달라집니다.
- **잠깐씩 찾아오는 날씨 연출** — 비 오는 날에는 물방울, 눈 오는 날에는 눈송이,
  맑은 밤에는 유성이 나타났다가 사라집니다.
- **어떤 사진 위에서도 읽히는 글자** — 글자와 버튼이 저마다 자기가 놓인 자리의 배경
  밝기를 재어 흰색과 검정 가운데 더 잘 보이는 쪽으로 칠해집니다.

**창과 실행**

- **보조 모니터 지원** — 기본 960×640 화면이며, 같은 해상도의 모니터를 자동으로 찾아
  그 자리에 띄웁니다. 전체화면으로 바꾸면 글자와 정보 영역이 함께 커집니다.
- **트레이에서 계속 실행** — 창을 닫으면 알림 영역으로 들어갑니다. 창을 숨기는 동안에는
  월페이퍼 렌더링과 음악·날씨 조회를 쉬고 녹화 감시만 이어 갑니다.
- **윈도우 시작 시 실행** — 트레이 메뉴에서 켜 두면 다음 로그인부터 자동으로 실행됩니다.

---

## 📦 설치 및 실행

1. [Releases](https://github.com/deuxdoom/Shadowplay-Notifier/releases/latest)에서
   `ShadowPlayNotifier.exe` 를 내려받아 원하는 폴더에 둡니다.
2. 내려받은 파일을 그대로 실행합니다. 압축을 풀 필요도, 설치 과정도 없습니다.
3. 오른쪽 위 **환경설정**에서 NVIDIA App 의 동영상 저장 폴더를 지정하고 저장합니다.

**Windows 10 이상**에서 사용합니다. 설정과 기록은 실행 파일 옆에 `config.json` 과
`monitor.log` 로 남으므로, 쓰기가 되는 폴더에 두십시오.

---

## 🖱️ 기본 조작

| 동작 | 방법 |
| --- | --- |
| 창 이동 | 창의 아무 곳이나 마우스로 끌기 |
| 전체화면 | 오른쪽 위 전체화면 버튼 또는 `F11` |
| 전체화면 해제 | 전체화면에서 `Esc` |
| 트레이로 이동 | 오른쪽 위 `✕` 버튼 또는 일반 창에서 `Esc` |
| 창 복원 | 트레이 아이콘 클릭 |
| 프로그램 종료 | 트레이 우클릭 → 프로그램 종료, 또는 `Ctrl+Q` |

키보드 단축키는 창을 한 번 클릭한 뒤에 씁니다. 타이틀바가 없는 창이라 초점을 자동으로
받지 못하기 때문입니다. 월페이퍼에서 닫기 버튼은 항상 보이고, 마우스를 움직이면
환경설정·전체화면 버튼도 나타납니다.

---

## ⚙️ 설정

환경설정 창에서 바꾼 값은 실행 파일 옆의 `config.json` 에 저장되고 곧바로 적용됩니다.
앱을 껐다 켤 필요가 없습니다.

| 항목 | 설명 |
| --- | --- |
| 녹화 폴더 | 녹화 중에 파일이 커지는 폴더입니다. 하위 폴더까지 함께 봅니다. |
| 폴링 주기 | 폴더를 훑어보는 간격입니다. 기본 0.5초입니다. |
| 중단 판정 시간 | 파일이 커지지 않은 채 이만큼 지나면 녹화가 끝난 것으로 봅니다. |
| 표시할 모니터 | `-1` 이면 창 크기와 같은 해상도의 모니터를 자동으로 고릅니다. |
| 항상 위 · 테두리 없음 · 소리 | 게임 녹화에 소리가 섞이면 안 되므로 알림음은 기본 꺼짐입니다. |
| `latitude` · `longitude` | 날씨를 볼 곳입니다. 기본값은 서울(37.5665, 126.978)입니다. |
| `verbose_log` | 자세한 기록을 남길지 정합니다. 문제를 찾을 때만 `true` 로 켜십시오. |

날씨는 [Open-Meteo](https://open-meteo.com/) 에서 받아 오며 API 키가 필요 없습니다.
네트워크가 없거나 조회에 실패해도 시계와 음악은 그대로 나옵니다.

녹화 기록과 오류는 `monitor.log` 에 남습니다. 녹화가 감지되지 않으면 먼저 녹화 폴더
경로부터 확인하십시오.

---

## 📜 라이선스

이 프로젝트는 **MIT 라이선스**를 따릅니다. 전문은 [LICENSE](LICENSE)에 있습니다.
Copyright (c) 2026 deuxdoom

- 아이콘은 Microsoft 의 [Fluent UI System Icons](https://github.com/microsoft/fluentui-system-icons)
  에서 가져왔습니다(MIT).
- 사계절 사진은 [Unsplash](https://unsplash.com/) 에서 가져왔으며
  [Unsplash License](https://unsplash.com/license)를 따릅니다. 사진을 갈아 끼우는 방법은
  [사진 출처](assets/wallpapers/README.md)에 적어 두었습니다.
- 글꼴은 [Pretendard](https://github.com/orioncactus/pretendard) 이며 SIL Open Font
  License 1.1 을 따릅니다. 프로그램이 돌아가는 동안에만 등록되고 윈도우에
  설치되지 않습니다.
