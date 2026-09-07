# ShadowPlay Notifier 작업 지침

ShadowPlay 녹화 상태를 감시해 보조 디스플레이에 상시 표시하는 tkinter 앱입니다.
전체 구조와 설정 항목은 [../README.md](../README.md), 변경 내역은
[../CHANGELOG.md](../CHANGELOG.md) 에 정리되어 있습니다.

## 지켜야 할 제약

- **감지 알고리즘을 바꾸지 않습니다.** `component/watcher.py` 의 `Watcher.tick()` 은
  폴링 + 크기 증가 + stall 판정 구조로 검증이 끝난 코드입니다. 화면에 필요한 값은
  `Watcher.snapshot()` 으로 뽑아 쓰고, 판정부는 건드리지 않습니다. 완료본 폴더
  (`outdir`) 판정 경로도 지금 환경에서 안 쓸 뿐이므로 지우지 마십시오.
- **런타임 의존성은 표준 라이브러리와 tkinter 뿐입니다.** requests, watchdog,
  pystray, Pillow 같은 외부 패키지를 넣지 않습니다. PyInstaller 는 빌드 도구,
  Pillow 는 아이콘을 구울 때만 쓰는 작성 시점 도구이므로 예외입니다.
- **녹화 결과물을 건드리지 않습니다.** 파일을 지우거나 옮기는 기능을 넣지 않습니다.
- `--noconsole` 로 빌드하므로 `print` 를 쓰지 않고 `paths.log()` 로 남깁니다.
- 설정과 로그 경로는 반드시 `paths.base_dir()` 을 거칩니다. onefile 로 묶으면
  `__file__` 이 임시 추출 폴더를 가리키기 때문입니다.
- 알림음 기본값은 꺼짐입니다. 게임 녹화에 소리가 섞이면 안 됩니다.

## 구성

한 파일이 1000줄을 넘어 읽기 어려워져서 `component/` 아래로 나누었습니다.
새 기능은 역할에 맞는 모듈에 넣고, 진입점 `ShadowPlayNotifier.py` 는 조립만 맡습니다.
모듈별 역할은 `component/__init__.py` 의 설명을 보십시오.

빌드 설정은 `ShadowPlayNotifier.spec` 한 곳에 모아 두었습니다. `pyinstaller --clean
ShadowPlayNotifier.spec` 으로 만들며, `--clean` 을 빠뜨리면 바뀐 아이콘이 무시됩니다.

**빌드하거나 검증 도구를 돌리기 전에 앱이 실행 중인지 반드시 확인하고 닫으십시오.**
PyInstaller 는 실행 중인 EXE 를 덮어쓰지 못해 조용히 실패하고, 창이 둘 뜨면 검증
결과도 어긋납니다. 사용자는 EXE 를 저장소가 아니라 아래 폴더에 두고 씁니다.

```
Get-Process -Name ShadowPlayNotifier -ErrorAction SilentlyContinue
Get-CimInstance Win32_Process -Filter "Name = 'pythonw.exe'" |
    Where-Object { $_.CommandLine -like "*ShadowPlayNotifier*" }
```

배포 위치는 `%USERPROFILE%\Downloads\Apps\ShadowPlayNotifier\` 입니다. 빌드한 뒤에는
`dist` 뿐 아니라 이 폴더의 EXE 도 갈아 주어야 사용자가 새 코드로 시험합니다.
같은 폴더의 `config.json` 과 `monitor.log` 는 사용자 파일이므로 덮지 마십시오.

## 창 조작

타이틀바를 쓰지 않는 것이 기본입니다(`borderless` 기본값 `true`). 배너 오른쪽 위에
환경설정·전체화면·닫기 버튼을 직접 그리고, 창은 어디를 잡아도 끌립니다. 창 아이콘은
설정하지 않습니다. 이유는 [tkinter·PyInstaller 함정](memory/tk-and-pyinstaller-gotchas.md)
에 정리해 두었습니다.

아이콘은 Fluent UI System Icons 의 SVG 를 PNG 로 구워 `component/icons.py` 에 base64
로 넣었습니다. 원본은 `F:\backup\fluentui system icons` 에 있고, 굽는 스크립트는
작성 시점에만 쓰므로 저장소에 두지 않았습니다. 아이콘을 바꾸려면 Edge 를 headless 로
돌려 투명 배경 PNG 를 만들고 같은 형식으로 다시 넣으면 됩니다.

## 레이아웃을 고칠 때

창 크기 960x640 은 고정입니다. 세로 배분은 `H_BANNER`(140) + `H_DETAIL`(319) +
`H_LOG`(133) + 상태 표시줄로 실측치에 맞춰 잡혀 있고 여유가 5px 뿐입니다.
글꼴 크기나 여백을 바꾸면 `test\preview.ps1` 로 "잘린 요소: 없음" 을 반드시 확인하십시오.

보조 디스플레이가 물리적으로 아주 작기 때문에(사용자 책상 위의 소형 패널) 글자 크기가
가독성을 좌우합니다. 로그를 5줄로 줄이고 남은 자리를 녹화 정보에 몰아준 배분이며,
이 균형을 되돌리지 마십시오. 저장 폴더 값은 길이에 따라 42~24pt 중에서 골라 씁니다.

상세 정보 프레임은 자식이 `grid` 로 배치되므로 `grid_propagate(False)` 여야 높이가 고정됩니다.
(`pack_propagate` 로는 고정되지 않아 로그와 상태 표시줄이 밀려 잘립니다.)
`pack` 으로 쌓을 때는 `expand=True` 를 쓰는 칸을 마지막에 붙여야 합니다. 먼저 붙이면
남는 자리를 모두 가져가서 뒤에 오는 줄이 잘립니다.

## 버전

`component/version.py` 한 곳에서 관리합니다. 기능을 바꾸면 CHANGELOG.md 에 새 기능,
변경, 수정, 삭제로 나누어 적고 유의적 버전 규칙에 따라 번호를 올립니다.

CHANGELOG 는 앱을 쓰는 사람이 읽는 문서입니다. 그러므로 빌드 방법, 모듈 분리,
검증 도구처럼 사용자가 마주치지 않는 것은 적지 않습니다. 개발 도중에 고친 점도
배포한 뒤에 생긴 문제가 아니라면 적지 않습니다. 아직 배포한 적이 없으므로
1.0.0 항목에는 새 기능만 있고 변경·수정·삭제 절을 두지 않으며, 커밋해서 실제로
배포하기 전까지 버전 번호도 1.0.0 에서 올리지 않습니다.

## 기억

- **[작업 상태와 다음 할 일](memory/project-status.md) — 먼저 읽으십시오. 태그와
  배포본은 사용자가 직접 올린다는 점이 특히 중요합니다.**
- [메모리 저장 위치](memory/memory-location.md)
- [보조 디스플레이 좌표](memory/secondary-display.md)
- [윈도우 GUI 검증 함정](memory/windows-gui-test-gotchas.md)
- [ShadowPlay 는 mp4 에 직접 기록](memory/shadowplay-writes-mp4-directly.md)
- [tkinter·PyInstaller 함정](memory/tk-and-pyinstaller-gotchas.md)
