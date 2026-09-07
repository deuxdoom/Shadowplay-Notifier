# ShadowPlay Notifier

NVIDIA ShadowPlay(NVIDIA App)의 녹화 상태를 감시해서, 보조 디스플레이에 상시
띄워 놓고 멀리서 흘끗 보아도 녹화 여부를 판단할 수 있게 만든 tkinter GUI 앱입니다.

녹화 폴더를 일정 주기로 훑어보면서 파일 크기가 커지면 녹화 시작으로 판정하고,
크기 증가가 멈춘 채 지정한 시간(stall)이 지나면 녹화 중단으로 판정합니다.
런타임 의존성은 파이썬 표준 라이브러리와 tkinter 뿐이며, 외부 패키지를 쓰지 않습니다.
(PyInstaller 는 빌드할 때만 필요합니다.)

녹화 결과물을 읽기만 하며, 파일을 지우거나 옮기는 기능은 넣지 않았습니다.

## 화면 구성

| 영역 | 내용 |
| --- | --- |
| 상태 배너 (140px) | 녹화 중에는 빨간 배경과 원형 인디케이터가 1초 주기로 밝기 펄스를 그리고 "녹화중"을 48pt 로 표시합니다. 대기 중에는 회색 배경에 펄스가 없습니다. 오른쪽에는 경과 시간을 크게 띄웁니다. |
| 상세 정보 | 저장 폴더(굵게), 파일명(길면 가운데 생략), 경과 시간, 용량, 비트레이트, 마지막 증가 시점을 2열로 보여 줍니다. 마지막 증가가 3초를 넘으면 주황색, stall 임계의 75% 를 넘으면 빨간색으로 바뀝니다. 대기 중에는 직전 녹화 요약과 세션 누적 횟수를 표시합니다. |
| 이벤트 로그 | 최근 10건을 고정폭 글꼴로 남깁니다. 시작은 빨강, 중단은 하늘색, 오류는 노랑입니다. |
| 상태 표시줄 | 감시 폴더, 폴링 주기, 마지막 갱신 시각을 표시하고, 폴더에 접근할 수 없으면 경고를 덧붙입니다. |

폴링은 별도 스레드에서 수행하고 `queue.Queue` 로 결과를 넘기며, UI 스레드는
`after()` 루프로 100ms 마다 큐를 비웁니다. 그래서 폴더를 훑는 동안에도 창이 멈추지
않습니다. 창을 닫으면 종료 플래그가 서고 감시 스레드도 함께 끝납니다.

## 빌드

```
build.bat
```

`dist\ShadowPlayNotifier.exe` 하나만 나옵니다. `app.ico` 파일을 프로젝트 폴더에 두면
자동으로 아이콘이 적용되고, 없으면 아이콘 없이 빌드합니다. PyInstaller 가 없으면
아래 명령으로 먼저 설치하십시오.

```
python -m pip install pyinstaller
```

빌드 스크립트의 안내 문구를 영문으로 둔 이유는, cmd.exe 가 배치 파일을 읽는 코드페이지와
파일 인코딩이 어긋나면 한글 때문에 파서가 깨지기 때문입니다.

`--noconsole` 로 빌드하므로 콘솔 출력이 없습니다. 실행 중에 생긴 일과 예외는 EXE 옆의
`monitor.log` 에 계속 덧붙여 기록됩니다.

## 설정

EXE(또는 스크립트)와 같은 폴더의 `config.json` 을 읽습니다. 파일이 없으면 기본값으로
새로 만듭니다. onefile 로 묶으면 `__file__` 이 임시 폴더를 가리키므로, 설정 경로는
`sys.executable` 기준으로 구합니다.

```json
{
  "dir": "E:\\shadowplay record",
  "interval": 1.0,
  "stall": 8.0,
  "min_size": 1048576,
  "beep": true,
  "topmost": false,
  "borderless": false,
  "monitor": 0,
  "ntfy_server": "",
  "ntfy_topic": ""
}
```

| 항목 | 뜻 |
| --- | --- |
| `dir` | 감시할 녹화 폴더입니다. 하위 폴더까지 훑습니다. |
| `interval` | 폴링 주기(초)입니다. 값이 작을수록 반응이 빠르고 디스크를 자주 읽습니다. |
| `stall` | 파일 크기 증가가 이만큼(초) 멈추면 녹화가 끝난 것으로 판정합니다. |
| `min_size` | 이보다 작은 파일은 후보에서 제외합니다(바이트). |
| `beep` | 시작과 중단에 짧은 소리를 냅니다. |
| `topmost` | 창을 항상 위에 둡니다. |
| `borderless` | 타이틀바를 없앱니다. 창을 끌어서 옮길 수 있고, Esc 로 종료합니다. |
| `monitor` | 창을 띄울 모니터 번호입니다. 왼쪽 위 좌표 순서로 0부터 셉니다. |
| `ntfy_server` | ntfy 서버 주소입니다. 비워 두면 `https://ntfy.sh` 를 씁니다. |
| `ntfy_topic` | ntfy 토픽입니다. **비워 두면 푸시 알림을 보내지 않습니다.** |

### 보조 디스플레이가 정확히 960x640 인 경우

창의 내부 크기가 960x640 이므로, 타이틀바가 있으면 그 높이(약 31px)만큼 화면 아래가
잘립니다. 화면에 딱 맞추려면 `borderless` 를 켜십시오.

```json
{ "monitor": 1, "borderless": true, "topmost": true }
```

주 모니터와 보조 모니터의 배율이 다를 때 창이 흐리게 늘어나지 않도록,
`SetProcessDpiAwareness(2)`(모니터별 DPI 인식)를 켠 뒤 tk 배율을 96DPI 로 고정합니다.

### 고급 항목

기본 파일에는 넣지 않지만, `config.json` 에 직접 적으면 인식하는 값들입니다.

| 항목 | 기본값 | 뜻 |
| --- | --- | --- |
| `min_growth` | `262144` | 한 주기에 이만큼 커져야 녹화 시작으로 봅니다(바이트). |
| `patterns` | `[".tmp", ".mp4", ".mkv"]` | 감시할 확장자 목록입니다. |
| `outdir` | 없음 | 완성본이 따로 떨어지는 폴더입니다. 여기에 새 파일이 생기면 즉시 중단으로 판정합니다. |
| `recursive` | `true` | 하위 폴더까지 훑을지 여부입니다. |
| `heartbeat` | `0` | 녹화 중 이 간격(초)마다 ntfy 로 진행 알림을 보냅니다. 0이면 보내지 않습니다. |
| `ntfy_token` | `""` | ntfy 인증 토큰입니다. |

## 실행 예시

```
# 설정 파일 그대로 실행
ShadowPlayNotifier.exe

# 보조 디스플레이에 테두리 없이 항상 위로 띄우기
ShadowPlayNotifier.exe --monitor 1 --borderless --topmost

# 다른 폴더를 0.5초 주기로 감시하고 소리는 끄기
ShadowPlayNotifier.exe --dir "D:\record" --interval 0.5 --no-beep

# 스크립트로 바로 실행 (파이썬 3.8 이상)
python shadowplay_notifier.py --monitor 1 --borderless
```

명령줄 인자가 `config.json` 보다 우선합니다. `--topmost` 처럼 켜는 인자에는
`--no-topmost`, `--no-borderless`, `--no-beep` 처럼 끄는 짝이 있습니다.

## 검증 도구

`test/` 폴더에 있습니다. 자세한 사용법은 [test/README.md](test/README.md) 를 보십시오.

```
python test\test_detection.py
powershell -ExecutionPolicy Bypass -File test\preview.ps1 -Mode rec -Borderless
powershell -ExecutionPolicy Bypass -File test\live_check.ps1
```
