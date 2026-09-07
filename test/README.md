# 검증 도구

모두 임시 폴더에 가짜 파일을 만들어 확인하며, 실제 녹화 결과물에는 손대지 않습니다.
GUI 확인 도구는 보조 디스플레이(기본값 1번 모니터)에 창을 강제로 띄웁니다.

## test_detection.py

폴링 상태 기계가 녹화 시작과 중단을 제대로 판정하는지 확인합니다. 창을 띄우지 않습니다.

```
python test\test_detection.py
```

첫 스캔에서 시작으로 오판하지 않는지, 크기 증가를 시작으로 잡는지, 증가가 멈추면
stall 시간 뒤에 중단으로 넘어가는지, 임시 파일이 사라지는 경로와 폴더가 없는 상황까지
확인합니다.

## preview.ps1 / preview_gui.py

가짜 상태를 채운 창을 보조 디스플레이에 띄우고 그 화면을 그대로 캡처합니다.
960x640 안에서 잘리는 요소가 없는지 확인할 때 씁니다.

```
powershell -ExecutionPolicy Bypass -File test\preview.ps1 -Mode rec -Borderless
powershell -ExecutionPolicy Bypass -File test\preview.ps1 -Mode idle -Monitor 1
```

- `-Mode rec` 는 녹화중 화면, `-Mode idle` 은 대기중 화면입니다.
- `-Borderless` 를 주면 타이틀바 없는 상태를 확인합니다.
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
