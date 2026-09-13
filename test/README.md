# 검증 도구

`trace_growth.py` 를 뺀 나머지는 모두 임시 폴더에 가짜 파일을 만들어 확인하며,
실제 녹화 결과물에는 손대지 않습니다. `trace_growth.py` 는 실제 녹화 폴더를 보지만
읽기만 합니다. GUI 확인 도구는 보조 디스플레이(기본값 1번 모니터)에 창을 강제로 띄웁니다.

## 월페이퍼 디자인 검증

`python test/test_wallpaper.py`는 실제 Tk와 GDI+로 11개 해상도, 긴 한글·일본어 제목,
36개 시간대·날씨 조합의 글자 대비, 커버 교체와 반복 전환의 이미지·도형·예약
콜백 수, 간헐적 효과와 녹화/전체화면 전환을 검사합니다. 네트워크는 사용하지 않습니다.

`python test/wallpaper_preview.py --seconds 180`은 보조 디스플레이에 디자인
미리보기를 띄웁니다. 방향키는 시간·날씨 전환, Space는 음악 유무, F11은 확대,
Esc는 종료입니다. `--scene 0`부터 `8`까지 여명·한낮·노을·밤·비·안개·눈·뇌우·흐림을
고를 수 있으며 `--size 1920x1080`, `--empty`도 지원합니다. 미리보기 곡과 날씨는
검증용 가상 데이터입니다.

`python test/wallpaper_preview.py --seconds 300 --profile --cycle`은 장면과 음악,
화면의 정지·재개를 반복하며 CPU, 메모리, Windows 손잡이, GDI, Tk 이미지와 도형 수를
`.Codex/wallpaper-soak.json`에 기록합니다. 24시간 검증은 `--seconds 86400`으로
별도로 실행할 수 있습니다. 실행 중인 본 앱을 먼저 닫으십시오.

`python test/test_tray.py`는 실제 트레이 등록·제거, 숨은 창 복원 메시지, 메뉴 명령과
체크 표시, Explorer 재시작 알림에 따른 재등록, 반복 종료와 자원 해제를 검사합니다.
`python test/build_icon.py`는 `assets/appicon.svg`에서 EXE·트레이용 ICO와 환경설정
아이콘을 함께 만듭니다. Pillow는 이 작성 도구에만 필요합니다.

## test_detection.py

폴링 상태 기계가 녹화 시작과 중단을 제대로 판정하는지 확인합니다. 창을 띄우지 않습니다.

```
python test\test_detection.py
```

첫 스캔에서 시작으로 오판하지 않는지, 크기 증가를 시작으로 잡는지, 증가가 멈추면
stall 시간 뒤에 중단으로 넘어가는지, 임시 파일이 사라지는 경로와 폴더가 없는 상황까지
확인합니다. 8~10번은 `fast_detect` 경로를 따로 확인합니다. 파일을 열어 둔 채로 두면
곧바로 시작으로 잡는지, 크기가 늘지 않아도 열려 있는 동안에는 녹화 상태를 지키는지,
파일을 닫으면 stall 을 기다리지 않고 중단으로 넘어가는지 봅니다.

1~7번은 `fast_detect` 를 꺼 두었습니다. 가짜 파일은 쓰자마자 닫히기 때문에, 켜 두면
빠른 중단 경로가 먼저 걸려서 stall 경로를 확인할 수 없기 때문입니다.

## test_single_instance.py

중복 실행 방지가 동작하는지 확인합니다. 창을 띄우지 않습니다.

```
python test\test_single_instance.py
```

별도 프로세스에 뮤텍스를 잡게 하고 그 동안 자리를 잡지 못하는지, 그 프로세스가
끝나면 자리가 풀리는지까지 봅니다. 검사에는 실제 앱과 다른 이름을 쓰므로, 앱이
떠 있어도 서로 방해하지 않습니다.

## trace_growth.py

실제 녹화 파일의 크기와 잠금 상태가 디스크에 반영되는 시점을 0.1초 단위로 기록합니다.
감지가 늦다고 느껴질 때, 그 원인이 폴링 주기인지 아니면 NVIDIA App 이 파일을 늦게
만들기 때문인지 가려내는 도구입니다. 앱을 실행하지 않고 단독으로 돌립니다.

```
python test\trace_growth.py
python test\trace_growth.py --dir "E:\shadowplay record" --seconds 120
```

콘솔을 띄워 둔 채 Alt+F9 를 누르고 곧바로 스페이스를 눌러 표시를 남기십시오. 중단할
때에도 같게 하면 사람이 누른 시각과 파일에 반영된 시각을 견줄 수 있습니다. Q 를 누르면
기록을 끝냅니다. 끝나면 크기 갱신 간격의 최소·중앙값·최대와, 설정값을 달리했을 때
판정이 언제 났을지를 함께 계산해서 보여 줍니다.

## test_placement.py

디스플레이 구성이 바뀌어도 창이 화면 밖으로 나가지 않는지 확인합니다. 모니터 목록을
가짜로 바꿔치기하므로 창을 띄우지 않고, 보조 모니터가 없는 환경이나 해상도가 다른
환경까지 이 PC 에서 그대로 검사할 수 있습니다.

```
python test\test_placement.py
```

## test_layout.py

실제 Tk 위젯으로 960×640, FHD, QHD, 4K, 울트라와이드, 세로 화면 등 11개
해상도의 영역 비율과 글자 잘림을 검사합니다. 대기·녹화·긴 폴더 이름을 확인하고,
F11 과 확대된 전체화면 버튼으로 전환을 반복해 원래 위치·글꼴·로그 배치 복원도 봅니다.
실행 중인 앱을 닫은 뒤 `python test/test_layout.py` 로 실행하십시오.

## preview.ps1 / preview_gui.py

가짜 상태를 채운 창을 보조 디스플레이에 띄우고 그 화면을 그대로 캡처합니다.
960x640 안에서 잘리는 요소가 없는지 확인할 때 씁니다.

```
powershell -ExecutionPolicy Bypass -File test\preview.ps1 -Mode rec -Borderless
powershell -ExecutionPolicy Bypass -File test\preview.ps1 -Mode idle -Monitor 1
```

- `-Mode rec` 는 녹화중 화면, `-Mode idle` 은 대기중 화면, `-Mode long` 은 폴더
  이름이 길어서 글자 크기가 자동으로 줄어드는 경우입니다.
- `-Borderless` 를 주면 타이틀바 없는 상태를 확인합니다.
- `-Fullscreen -Monitor 0` 을 함께 주면 주 모니터 전체화면을 확인합니다.
  캡처는 실제 창 해상도를 보존하므로 화면비와 글자 크기도 비교할 수 있습니다.
- 결과는 `test\shot_<모드>.png` 와 `test\layout_<모드>.txt` 로 남습니다.
- 화면 캡처는 배율과 무관한 물리 좌표로 동작하므로, DPI 인식을 켠 파이썬 쪽이
  `monitor_rect.txt` 에 좌표를 적어 주고 PowerShell 이 그 값을 씁니다.

## live_check.ps1

실제 앱을 띄운 뒤 임시 폴더에서 파일을 실제로 키워, 화면 전환에 걸리는 시간을 봅니다.

```
powershell -ExecutionPolicy Bypass -File test\live_check.ps1 -Interval 0.5 -Stall 4
```

대기 → 녹화중 → 대기로 돌아오는 세 시점을 `test\live_1_idle.png`,
`live_2_recording.png`, `live_3_back_to_idle.png` 로 남기고, 마지막에 `monitor.log` 의
끝부분을 출력합니다. 파일이 커지기 시작한 시각과 로그의 감지 시각을 견주어 보면
반응 속도를 알 수 있습니다.

## where.py

지정한 모니터에 창을 놓을 물리 좌표를 출력합니다. 캡처 도구가 내부적으로 씁니다.

```
python test\where.py 1
```
