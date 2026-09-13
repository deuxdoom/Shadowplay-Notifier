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

![월페이퍼 화면](wallpaper.png)

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
- 녹화를 기다리는 동안에는 **시계와 날씨, 지금 듣는 음악을 보여 주는 월페이퍼
  화면**이 됩니다. 녹화가 시작되면 곧바로 녹화 화면으로 바뀌고, 끝나면 다시
  돌아옵니다. 보조 모니터를 늘 켜 두어도 화면이 비어 있지 않습니다.
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
- 🕒 **월페이퍼 화면** — 녹화를 기다리는 동안 큰 시계와 날짜, 요일, 날씨를
  보여 줍니다. 기온과 날씨 아이콘, 오늘 최고·최저 기온, 습도, 강수 확률이
  함께 나옵니다. 960×640에서도 잘 읽히도록 날짜와 날씨를 크게 표시하고,
  날씨 아이콘에는 느린 움직임을 더했습니다.
- 🎵 **재생 중인 음악** — Spotify 에서 듣고 있는 곡과 아티스트, 앨범 커버를
  보여 줍니다. 로그인이나 계정 연결이 필요 없습니다.
- 📈 **소리에 맞춰 움직이는 파형** — 스피커로 나가는 소리를 12개 주파수 대역으로
  나누어 지평선 아래 64개의 가는 막대와 옅은 반사로 그립니다. 소리를 녹음하거나
  저장하지 않고 세기만 잽니다. 소리가 멈추면 파형도 조용히 가라앉습니다.
- 🌤️ **시간과 날씨를 따라가는 배경** — 심야부터 밤까지 하늘빛이 천천히 바뀌고,
  구름과 안개가 지평선을 감쌉니다. 비 오는 날에는 유리 위를 미끄러지는 물방울,
  눈 오는 날에는 느린 눈송이, 맑은 밤에는 유성이 잠깐씩 나타납니다. 앨범 커버에서
  뽑은 색은 부드럽게 배경으로 번집니다. 음악이 없을 때는 레코드 문양과
  ‘고요한 순간’ 화면으로 쉬어 갑니다.
- 🔆 **트레이에서 계속 실행** — X를 누르면 알림 영역으로 이동합니다. 트레이에서
  창을 다시 열거나 월페이퍼·녹화 감시 화면·자동 전환을 선택하고, 환경설정과
  GitHub 페이지를 열거나 프로그램을 종료할 수 있습니다. 창을 숨기면 월페이퍼
  렌더링과 음악·날씨 조회를 쉬고 녹화 감시는 계속합니다.

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
| 전체화면 해제 | 전체화면에서 `Esc` |
| 트레이로 이동 | 오른쪽 위 `✕` 버튼 또는 일반 창에서 `Esc` |
| 창 복원 | 트레이 아이콘 클릭 또는 프로그램 다시 실행 |
| 화면 선택 | 트레이 우클릭 → 월페이퍼 화면 / 녹화 감시 화면 / 자동 전환 |
| 프로그램 종료 | 트레이 우클릭 → 프로그램 종료, 또는 `Ctrl+Q` |

키보드 단축키는 창을 한 번 클릭한 뒤에 씁니다. 타이틀바가 없는 창이라 초점을
자동으로 받지 못하기 때문입니다.
월페이퍼의 X 버튼은 항상 보입니다. 마우스를 움직이면 환경설정·전체화면 버튼도
나타납니다. 수동으로 선택한 화면은 녹화 여부와 관계없이 유지되며, 트레이에서
‘녹화 상태에 따라 자동 전환’을 선택하면 기존 자동 전환으로 돌아갑니다.
화면 선택은 현재 실행에만 적용되고, 다음 실행은 설정 파일의 기본 모드로 시작합니다.

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
| `wallpaper` | 월페이퍼 화면을 쓸지 정합니다. `false` 로 두면 예전처럼 대기 화면만 나옵니다. |
| `latitude` · `longitude` | 날씨를 볼 곳입니다. 기본값은 서울(37.5665, 126.978)입니다. |

날씨는 [Open-Meteo](https://open-meteo.com/) 에서 받아 오며 API 키가 필요 없습니다.
네트워크가 없거나 조회에 실패해도 시계와 음악은 그대로 나옵니다.

동작 기록과 오류는 `monitor.log`에 남습니다. 녹화가 감지되지 않으면 먼저 녹화
폴더 경로부터 확인하십시오.

---

## 📜 라이선스

이 프로젝트는 **MIT 라이선스**를 따릅니다. 전문은 [LICENSE](LICENSE)에 있습니다.

```
Copyright (c) 2026 deuxdoom
```

배너와 날씨에 쓰는 아이콘은 Microsoft 의
[Fluent UI System Icons](https://github.com/microsoft/fluentui-system-icons)에서
가져왔으며, 이 역시 MIT 라이선스입니다.

화면에 쓰는 글꼴은 [Pretendard](https://github.com/orioncactus/pretendard) 와
[JetBrains Mono](https://github.com/JetBrains/JetBrainsMono) 이며, 둘 다
SIL Open Font License 1.1 을 따릅니다. 글꼴은 이 프로그램이 돌아가는 동안에만
등록되고 윈도우에 설치되지 않습니다.
