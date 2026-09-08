# ShadowPlay Notifier

NVIDIA ShadowPlay(NVIDIA App)의 녹화 상태를 보조 모니터에 크게 표시하는 Windows 앱입니다.
녹화 상태 아이콘을 꺼 둔 상태에서도 녹화 여부를 한눈에 확인할 수 있습니다.

![녹화 중인 화면](main.png)

## 주요 기능

- 녹화 시작·중단을 감지해 상태, 경과 시간, 파일 용량과 비트레이트 표시
- 기본 960×640 화면과 모니터 해상도에 맞춰 글자·정보 영역이 함께 확대되는 전체화면 지원
- 감시 폴더, 표시할 모니터, 항상 위에 표시, 알림음 설정

녹화 파일의 크기 변화와 쓰기 상태로 녹화 여부를 판단합니다. 녹화 파일을 수정하거나 삭제하지 않습니다.
빠른 감지를 사용할 수 없으면 파일 크기 증가가 멈춘 뒤 기본 8초 후에 중단으로 표시합니다.

## 사용법

1. [Releases](https://github.com/deuxdoom/Shadowplay-Notifier/releases)에서 배포 파일을 받아 압축을 풉니다.
2. `ShadowPlayNotifier.exe`를 실행합니다.
3. 오른쪽 위 톱니바퀴에서 **녹화 폴더**를 지정하고 저장합니다.

설정은 실행 파일 옆의 `config.json`에 저장되며 바로 적용됩니다. 실행 로그는 `monitor.log`에서 확인할 수 있습니다.

- **창 이동:** 창을 마우스로 드래그
- **전체화면:** 오른쪽 위 전체화면 버튼 또는 `F11`
- **전체화면 해제·종료:** `Esc`

키보드 단축키는 창을 한 번 클릭한 뒤 사용합니다.

## 소스 실행 및 빌드

Python 3.8 이상과 tkinter가 필요합니다. 소스 실행에는 외부 패키지가 필요하지 않습니다.

```powershell
python ShadowPlayNotifier.py
```

EXE 빌드는 앱을 종료한 뒤 실행합니다.

```powershell
python -m pip install pyinstaller
pyinstaller --clean ShadowPlayNotifier.spec
```

결과물: `dist\ShadowPlayNotifier.exe`

변경 이력은 [CHANGELOG.md](CHANGELOG.md), 검증 도구 사용법은 [test/README.md](test/README.md)를 참고하세요.
