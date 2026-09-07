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
import shadowplay_notifier as sn  # noqa: E402

root = tempfile.mkdtemp(prefix="spn_test_")
game = os.path.join(root, "OnimushaWotS")
os.makedirs(game)
target = os.path.join(game, "Onimusha 2026.09.07 - 11.20.33.04.DVR.tmp")

events = []
watcher = sn.Watcher(dirs=[root], outdirs=[], patterns=sn.DEFAULT_PATTERNS,
                     servers=[], topic="", interval=0.1, stall=1.5,
                     min_size=1024 * 1024, min_growth=256 * 1024,
                     beep=False, sink=events.append)
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
    print("[통과] 시작 감지, 저장 폴더 =", sn.folder_label(target, [root]))

    # 3) 계속 증가하는 동안에는 녹화 상태가 유지됩니다.
    for step in range(3):
        write(8 + step * 4)
        time.sleep(0.2)
        watcher.tick()
        assert events[-1]["active"], "녹화 중인데 상태가 풀렸습니다"
    print("[통과] 진행 중 상태 유지, 경과 =", sn.hms(events[-1]["elapsed"]))

    # 4) 증가가 멈추면 stall 시간 뒤에 중단으로 판정합니다.
    time.sleep(1.6)
    watcher.tick()
    assert stops(), "stall 판정이 동작하지 않았습니다"
    assert stops()[-1]["reason"] == "증가 멈춤"
    assert not events[-1]["active"]
    print("[통과] stall 중단 판정, 용량 =", sn.human(stops()[-1]["peak"]))

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

    # 6) 폴더가 없어도 예외 없이 대기 상태를 유지합니다.
    ghost = sn.Watcher(dirs=[os.path.join(root, "없는폴더")], outdirs=[],
                       patterns=sn.DEFAULT_PATTERNS, servers=[], topic="",
                       beep=False, sink=lambda event: None)
    ghost.prime()
    ghost.tick()
    print("[통과] 없는 폴더 처리")

    print("[통과] 표시 형식:", sn.human(1536 * 1024 * 1024), sn.hms(3725),
          sn.ellipsize("Onimusha 2026.09.07 - 11.20.33.04.DVR.mp4", 26))
    print("\n모든 검사를 통과했습니다.")
finally:
    shutil.rmtree(root, ignore_errors=True)
