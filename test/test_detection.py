"""감지 상태 기계가 녹화 시작과 중단을 제대로 판정하는지 확인합니다.

실행: python test\test_detection.py
임시 폴더에 가짜 녹화 파일을 만들어 폴링 결과만 확인하며,
실제 녹화 결과물에는 전혀 손대지 않습니다.
"""

import os
import shutil
import sys
import tempfile
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from component.scan import DEFAULT_PATTERNS, human, hms  # noqa: E402
from component.text import ellipsize, folder_label  # noqa: E402
from component.watcher import Watcher  # noqa: E402

root = tempfile.mkdtemp(prefix="spn_test_")
game = os.path.join(root, "OnimushaWotS")
os.makedirs(game)
target = os.path.join(game, "Onimusha 2026.09.07 - 11.20.33.04.DVR.tmp")

events = []
# 1~7번은 크기 증가와 stall 만으로 판정하는 원래 구조를 확인하는 검사입니다.
# 가짜 파일은 쓰자마자 닫히기 때문에, 잠금 신호를 켜 두면 빠른 중단 경로가
# 먼저 걸려 stall 경로를 확인할 수 없습니다. 그래서 여기서만 꺼 둡니다.
watcher = Watcher(dirs=[root], outdirs=[], patterns=DEFAULT_PATTERNS,
                  interval=0.1, stall=1.5, min_size=1024 * 1024,
                  min_growth=256 * 1024, beep=False, fast_detect=False,
                  sink=events.append)
watcher.prime()


def write(megabytes):
    with open(target, "wb") as fp:
        fp.write(b"\0" * (megabytes * 1024 * 1024))


def kinds():
    return [e["kind"] for e in events]


def stops():
    return [e for e in events if e["kind"] == "stop"]


try:
    # 1) 파일이 있어도 증가 이력이 없으면 시작으로 보지 않습니다.
    write(2)
    watcher.tick()
    assert "start" not in kinds(), "첫 스캔에서 시작으로 오판했습니다"

    # 2) 다음 폴링에서 크기 증가를 확인하면 시작으로 판정합니다.
    write(6)
    watcher.tick()
    assert "start" in kinds(), "크기 증가를 감지하지 못했습니다"
    assert events[-1]["active"] and events[-1]["path"] == target
    print("[통과] 시작 감지, 저장 폴더 =", folder_label(target, [root]))

    # 3) 계속 증가하는 동안에는 녹화 상태가 유지됩니다.
    for step in range(3):
        write(8 + step * 4)
        time.sleep(0.2)
        watcher.tick()
        assert events[-1]["active"], "녹화 중인데 상태가 풀렸습니다"
    print("[통과] 진행 중 상태 유지, 경과 =", hms(events[-1]["elapsed"]))

    # 4) 증가가 멈추면 stall 시간 뒤에 중단으로 판정합니다.
    time.sleep(1.6)
    watcher.tick()
    assert stops(), "stall 판정이 동작하지 않았습니다"
    assert stops()[-1]["reason"] == "증가 멈춤"
    assert not events[-1]["active"]
    print("[통과] stall 중단 판정, 용량 =", human(stops()[-1]["peak"]))

    # 5) 임시 파일이 사라지는 경로도 중단으로 판정합니다.
    write(2)
    watcher.tick()
    write(6)
    watcher.tick()
    assert events[-1]["active"], "두 번째 녹화 시작을 놓쳤습니다"
    os.remove(target)
    watcher.tick()
    assert stops()[-1]["reason"] == "임시 파일 사라짐"
    print("[통과] 임시 파일 소멸 경로")

    # 6) 완료본 폴더에 새 파일이 생기면 곧바로 중단으로 판정합니다.
    done = os.path.join(root, "완료본")
    os.makedirs(done, exist_ok=True)
    pair = Watcher(dirs=[game], outdirs=[done], patterns=DEFAULT_PATTERNS,
                   interval=0.1, stall=30, min_size=1024 * 1024,
                   min_growth=256 * 1024, beep=False, fast_detect=False,
                   sink=lambda e: None)
    pair.prime()
    write(2)
    pair.tick()
    write(6)
    pair.tick()
    assert pair._active == target, "완료본 감시 쪽에서 시작을 놓쳤습니다"
    with open(os.path.join(done, "완성본.mp4"), "wb") as fp:
        fp.write(b"\0" * (2 * 1024 * 1024))
    pair.tick()
    assert not pair._active, "완료 파일이 생겼는데 중단으로 넘어가지 않았습니다"
    print("[통과] 완료본 폴더 감지")

    # 7) 폴더가 없어도 예외 없이 대기 상태를 유지합니다.
    ghost = Watcher(dirs=[os.path.join(root, "없는폴더")], outdirs=[],
                    patterns=DEFAULT_PATTERNS, beep=False,
                    sink=lambda event: None)
    ghost.prime()
    ghost.tick()
    print("[통과] 없는 폴더 처리")

    # 8) 잠금 신호를 켜면 파일이 열린 첫 틱에 곧바로 시작으로 판정합니다.
    fast_dir = os.path.join(root, "빠른감지")
    os.makedirs(fast_dir, exist_ok=True)
    live = os.path.join(fast_dir, "Onimusha 2026.09.07 - 12.00.00.04.mp4")
    fast_events = []
    fast = Watcher(dirs=[fast_dir], outdirs=[], patterns=DEFAULT_PATTERNS,
                   interval=0.1, stall=30, min_size=1024 * 1024,
                   min_growth=256 * 1024, beep=False, fast_detect=True,
                   sink=fast_events.append)
    fast.prime()

    handle = open(live, "wb")
    handle.write(b"\0" * (2 * 1024 * 1024))
    handle.flush()
    fast.tick()
    assert fast._active == live, "쓰기로 열린 파일을 시작으로 잡지 못했습니다"
    print("[통과] 잠금 신호로 시작 즉시 판정")

    # 9) 크기가 늘지 않아도 파일이 열려 있는 동안에는 녹화 상태를 지킵니다.
    fast.tick()
    assert fast._active == live, "열려 있는데 중단으로 오판했습니다"

    # 10) 파일을 닫으면 stall 을 기다리지 않고 다음 틱에 중단으로 판정합니다.
    handle.close()
    fast.tick()
    assert not fast._active, "파일이 닫혔는데 중단으로 넘어가지 않았습니다"
    fast_stops = [e for e in fast_events if e["kind"] == "stop"]
    assert fast_stops[-1]["reason"] == "파일 닫힘"
    print("[통과] 잠금 신호로 중단 즉시 판정 (stall 30초를 기다리지 않았습니다)")

    print("[통과] 표시 형식:", human(1536 * 1024 * 1024), hms(3725),
          ellipsize("Onimusha 2026.09.07 - 11.20.33.04.DVR.mp4", 26))
    print("\n모든 검사를 통과했습니다.")
finally:
    shutil.rmtree(root, ignore_errors=True)
