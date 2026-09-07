# ShadowPlay Notifier 작업 지침

ShadowPlay 녹화 상태를 감시해 보조 디스플레이에 상시 표시하는 tkinter 앱입니다.
전체 구조와 설정 항목은 [../README.md](../README.md) 에 정리되어 있습니다.

## 지켜야 할 제약

- **감지 알고리즘을 바꾸지 않습니다.** `Watcher.tick()` 의 폴링 + 크기 증가 +
  stall 판정 구조와 `scan` / `_start` / `_stop` 은 검증이 끝난 코드입니다.
  표시를 위해 필요한 값은 `Watcher.snapshot()` 으로 뽑아 쓰고, 판정부는 건드리지 않습니다.
- **런타임 의존성은 표준 라이브러리와 tkinter 뿐입니다.** requests, watchdog, pystray
  같은 외부 패키지를 넣지 않습니다. PyInstaller 는 빌드 도구이므로 예외입니다.
- **녹화 결과물을 건드리지 않습니다.** 파일을 지우거나 옮기는 기능을 넣지 않습니다.
- `--noconsole` 로 빌드하므로 `print` 를 쓰지 않고 `log()` 로 `monitor.log` 에 남깁니다.
- 설정과 로그 경로는 반드시 `base_dir()` 을 거칩니다. onefile 로 묶으면 `__file__` 이
  임시 추출 폴더를 가리키기 때문입니다.

## 레이아웃을 고칠 때

창 크기 960x640 은 고정입니다. 세로 배분은 `H_BANNER`(140) + `H_DETAIL`(236) +
`H_LOG`(226) + 상태 표시줄로 실측치에 맞춰 잡혀 있고 여유가 5px 뿐입니다.
글꼴 크기나 여백을 바꾸면 `test\preview.ps1` 로 "잘린 요소: 없음" 을 반드시 확인하십시오.
상세 정보 프레임은 자식이 `grid` 로 배치되므로 `grid_propagate(False)` 여야 높이가 고정됩니다.
(`pack_propagate` 로는 고정되지 않아 로그와 상태 표시줄이 밀려 잘립니다.)

## 기억

- [메모리 저장 위치](memory/memory-location.md)
- [보조 디스플레이 좌표](memory/secondary-display.md)
- [윈도우 GUI 검증 함정](memory/windows-gui-test-gotchas.md)
