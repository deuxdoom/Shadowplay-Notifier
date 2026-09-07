---
name: tk-and-pyinstaller-gotchas
description: 창 위치·전체화면·프로세스 종료에서 조용히 어긋나는 tkinter 와 PyInstaller 동작 네 가지.
metadata:
  type: project
---

2026년 9월 7일에 실제로 증상을 재현하고 원인까지 확인한 것들입니다.

1. **`root.iconbitmap()` 은 창을 다시 만들면서 지정한 위치를 날립니다.** 창 아이콘을
   넣었더니 `geometry("960x640+3840+1520")` 요청은 로그에 그대로 남는데 창은 주 모니터
   구석에 떴습니다. 아이콘은 PyInstaller 의 `--icon` 으로 EXE 에만 넣고, 창 아이콘은
   설정하지 않습니다.
2. **tkinter 의 `attributes("-fullscreen", True)` 는 주 모니터를 채웁니다.** 보조
   디스플레이에 있던 창이 4K 주 모니터를 덮어 버렸습니다. 그래서 창 중심이 속한
   모니터의 좌표를 `monitor_for_point()` 로 구해서 `overrideredirect` 와 `geometry` 로
   직접 맞춥니다. 이때 `resizable(False, False)` 가 크기를 고정하므로 잠시 풀어야 합니다.
3. **타이틀바 없는 창(`overrideredirect`)은 초점을 자동으로 받지 못합니다.**
   `FindWindow` 로도 잡히지 않아서 Esc 나 F11 이 닿지 않습니다. 눌렀을 때
   `focus_force()` 를 부르고, 닫기는 화면에 보이는 ✕ 버튼으로 제공해야 합니다.
4. **PyInstaller onefile 은 부모(부트로더)와 자식 두 프로세스로 돕니다.** 부모만
   종료하면 자식이 계속 살아서 창이 남습니다. 종료나 정리는 이름으로 전체를 잡아야
   합니다. 또한 `--clean` 없이 다시 빌드하면 캐시된 EXE 를 재사용해서 바뀐 아이콘이
   반영되지 않습니다.

**Why:** 네 가지 모두 오류를 내지 않고 조용히 다르게 동작해서, 앱이 고장 난 것처럼
보입니다. 실제로 2번과 4번 때문에 검증 중에 잘못된 결론에 이를 뻔했습니다.

**How to apply:** 창 배치나 전체화면 코드를 건드렸다면 `test\preview.ps1` 로 좌표를
확인하고, EXE 를 다시 만들었다면 실행 중인 인스턴스를 모두 정리한 뒤에 시험하십시오.
검증 도구 쪽 함정은 [[windows-gui-test-gotchas]] 에 따로 정리했습니다.
