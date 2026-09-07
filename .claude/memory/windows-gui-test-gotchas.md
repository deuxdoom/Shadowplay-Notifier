---
name: windows-gui-test-gotchas
description: 이 환경에서 윈도우 GUI 앱을 만들고 검증할 때 반복해서 걸린 함정 네 가지.
metadata:
  type: project
---

2026년 9월 7일 작업에서 실제로 시간을 쓴 문제들입니다.

1. **배치 파일에 한글을 쓰면 cmd.exe 파서가 깨집니다.** 콘솔 코드페이지와 파일
   인코딩이 어긋나면 한글 바이트를 명령으로 해석해 버립니다. `build.bat` 의 안내
   문구는 ASCII 로 두고 설명은 README 에 적습니다.
2. **`pythonw` 에는 표준 출력이 없어 `print` 가 예외를 냅니다.** `sys.stdout` 이
   `None` 이므로, 창을 띄우는 스크립트는 출력을 파일로 남기거나 `sys.stdout` 을
   확인한 뒤 출력해야 합니다.
3. **`Start-Process` 의 인자에 공백이 든 경로는 직접 따옴표로 묶어야 합니다.**
   예전 저장소 경로에 공백이 있어서(`F:\ShadowPlay Notifier`) 그냥 넘기면 파이썬이
   `F:\ShadowPlay` 를 스크립트로 받고 조용히 실패했습니다. 2026년 9월 7일에
   사용자가 폴더 이름에서 공백을 빼 `F:\ShadowPlayNotifier` 로 바꾸었으므로 지금은
   걸리지 않지만, 감시 대상인 `E:\shadowplay record` 에는 여전히 공백이 있습니다.
   덧붙여 제품 이름 `ShadowPlay Notifier` 는 공백을 그대로 두는 것이 맞습니다.
   폴더 이름과 제품 이름은 다른 값이므로 함께 바꾸지 마십시오.
4. **화면 캡처는 물리 좌표로 동작합니다.** PowerShell 은 주 모니터 배율(150%)로
   확대된 좌표를 보고하므로, 그 값으로 `CopyFromScreen` 을 부르면 화면 밖을 읽어
   흰 이미지가 나옵니다. DPI 인식을 켠 파이썬 쪽에서 물리 좌표를 받아 써야 합니다.

또한 이 환경의 Bash 도구는 긴 히어독을 처리하지 못하므로, 파일 작성은 Write 도구를
씁니다.

**Why:** 네 가지 모두 오류 메시지가 남지 않거나 엉뚱한 곳을 가리켜서, 원인을 다시
찾으려면 같은 시간을 또 써야 합니다.

**How to apply:** 검증 도구는 [[secondary-display]] 의 좌표를 쓰는
`test\preview.ps1`, `test\live_check.ps1` 에 이미 반영해 두었으니 그것을 재사용합니다.
