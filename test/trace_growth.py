"""실제 녹화 파일의 크기가 디스크에 반영되는 시점을 0.1초 단위로 기록합니다.

감지 지연이 폴링 주기 때문인지, 아니면 윈도우가 기록 중인 파일의 크기를 늦게
갱신하기 때문인지 가려내려고 만든 진단 도구입니다. 앱을 실행하지 않고 단독으로
돌리며, 녹화 폴더를 읽기만 합니다.

  python test\\trace_growth.py
  python test\\trace_growth.py --dir "E:\\shadowplay record" --seconds 120

이 콘솔을 띄워 둔 채로 Alt+F9 를 누르고, 곧바로 스페이스를 눌러 표시를 남기십시오.
녹화를 중단할 때에도 똑같이 하면, 사람이 누른 시각과 파일에 반영된 시각을 나란히
놓고 견줄 수 있습니다.
"""

import argparse
import ctypes
import json
import os
import sys
import time
from ctypes import wintypes

try:
    import msvcrt
except ImportError:
    msvcrt = None

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from component.scan import DEFAULT_PATTERNS, human  # noqa: E402

GENERIC_READ = 0x80000000
FILE_SHARE_READ = 0x00000001
FILE_SHARE_WRITE = 0x00000002
FILE_SHARE_DELETE = 0x00000004
FILE_SHARE_ALL = FILE_SHARE_READ | FILE_SHARE_WRITE | FILE_SHARE_DELETE
OPEN_EXISTING = 3
FILE_ATTRIBUTE_NORMAL = 0x80
ERROR_SHARING_VIOLATION = 32
INVALID_HANDLE = ctypes.c_void_p(-1).value

kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
kernel32.CreateFileW.restype = wintypes.HANDLE
kernel32.CreateFileW.argtypes = [wintypes.LPCWSTR, wintypes.DWORD, wintypes.DWORD,
                                 ctypes.c_void_p, wintypes.DWORD, wintypes.DWORD,
                                 wintypes.HANDLE]
kernel32.GetFileSizeEx.restype = wintypes.BOOL
kernel32.GetFileSizeEx.argtypes = [wintypes.HANDLE,
                                   ctypes.POINTER(ctypes.c_longlong)]
kernel32.CloseHandle.argtypes = [wintypes.HANDLE]


def handle_size(path):
    """열려 있는 파일의 실제 끝 위치를 핸들로 직접 물어봅니다.

    디렉터리 항목에 적힌 크기는 갱신이 늦어질 수 있으므로, 그 값과 견주기
    위해 따로 잽니다. 파일을 열지 못하면 None 을 돌려줍니다.
    """
    h = kernel32.CreateFileW(path, GENERIC_READ, FILE_SHARE_ALL, None,
                             OPEN_EXISTING, FILE_ATTRIBUTE_NORMAL, None)
    if not h or h == INVALID_HANDLE:
        return None
    try:
        size = ctypes.c_longlong(0)
        if not kernel32.GetFileSizeEx(h, ctypes.byref(size)):
            return None
        return size.value
    finally:
        kernel32.CloseHandle(h)


def is_being_written(path):
    """다른 프로세스가 이 파일을 쓰기 위해 열어 두고 있는지 알아봅니다.

    읽기 권한만 요구하되 공유는 읽기까지만 허용해서 엽니다. 그러면 이미
    쓰기로 열려 있는 파일에서는 공유 위반이 나므로, 우리가 파일을 건드리지
    않고도 기록 중인지 가려낼 수 있습니다. 판단이 서지 않으면 None 입니다.
    """
    h = kernel32.CreateFileW(path, GENERIC_READ, FILE_SHARE_READ, None,
                             OPEN_EXISTING, FILE_ATTRIBUTE_NORMAL, None)
    if h and h != INVALID_HANDLE:
        kernel32.CloseHandle(h)
        return False
    return True if ctypes.get_last_error() == ERROR_SHARING_VIOLATION else None


def sweep(dirs, patterns):
    """앱의 scan() 과 같은 방식으로 훑되, 크기 하한을 두지 않습니다."""
    found = {}
    for root_dir in dirs:
        if not os.path.isdir(root_dir):
            continue
        for cur, _subdirs, files in os.walk(root_dir):
            for name in files:
                if not any(name.lower().endswith(p) for p in patterns):
                    continue
                path = os.path.join(cur, name)
                try:
                    stat_size = os.path.getsize(path)
                except OSError:
                    continue
                found[path] = (stat_size, handle_size(path),
                               is_being_written(path))
    return found


def simulate(samples, interval, min_size, min_growth, stall):
    """기록해 둔 표본을 재생해서 앱이 언제 판정했을지 계산합니다.

    watcher.tick() 의 판정 순서를 그대로 옮겨 놓았습니다. 실제 코드를 고치지
    않고도 설정값을 달리했을 때의 반응 시각을 미리 확인할 수 있습니다.
    """
    if not samples:
        return None, None
    begin, end = samples[0][0], samples[-1][0]
    sizes, active, peak, last_growth = {}, "", 0, 0.0
    started_at, stopped_at = None, None
    idx = 0
    tick_at = begin
    while tick_at <= end:
        while idx + 1 < len(samples) and samples[idx + 1][0] <= tick_at:
            idx += 1
        current = {p: rec[0] for p, rec in samples[idx][1].items()
                   if rec[0] >= min_size}
        if active:
            size = current.get(active)
            if size is None:
                stopped_at = tick_at
                break
            if size > peak:
                peak, last_growth = size, tick_at
            elif tick_at - last_growth >= stall:
                stopped_at = tick_at
                break
        else:
            for path, size in current.items():
                prev = sizes.get(path)
                if prev is not None and size - prev >= min_growth:
                    active, peak, last_growth = path, size, tick_at
                    started_at = tick_at
                    break
        sizes = current
        tick_at += interval
    return started_at, stopped_at


def simulate_lock(samples, interval, min_size):
    """잠금 신호만으로 판정했을 때의 시작과 중단 시각을 계산합니다.

    기록 중인 파일은 쓰기로 열려 있으므로, 그런 파일이 처음 나타난 순간이
    시작이고 그 파일이 닫힌 순간이 중단입니다. 크기 증가를 기다릴 필요가
    없어서 폴링 주기 한 번 안에 판정이 끝납니다.
    """
    if not samples:
        return None, None
    begin, end = samples[0][0], samples[-1][0]
    active, started_at, stopped_at = "", None, None
    idx = 0
    tick_at = begin
    while tick_at <= end:
        while idx + 1 < len(samples) and samples[idx + 1][0] <= tick_at:
            idx += 1
        snapshot = samples[idx][1]
        if active:
            record = snapshot.get(active)
            if record is None or record[2] is not True:
                stopped_at = tick_at
                break
        else:
            for path, record in snapshot.items():
                if record[2] is True and record[0] >= min_size:
                    active, started_at = path, tick_at
                    break
        tick_at += interval
    return started_at, stopped_at


def resolve_dirs(given):
    """인자로 받은 폴더가 없으면 config.json 에 적힌 폴더를 씁니다."""
    dirs = list(given or [])
    if not dirs:
        root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        try:
            with open(os.path.join(root, "config.json"), "r", encoding="utf-8") as fp:
                dirs = [json.load(fp).get("dir", "")]
        except (OSError, ValueError):
            dirs = []
    return [os.path.abspath(d) for d in dirs if d]


def report(samples, changes, marks):
    """모아 둔 기록을 사람이 읽을 수 있는 요약으로 바꿔 출력합니다."""
    print("\n===== 요약 =====")
    if not changes:
        print("크기가 변한 파일이 없습니다. 폴더 경로를 확인하십시오.")
        return 1

    growth = [c for c in changes if c[2] is not None and c[3] is not None]
    if len(growth) >= 2:
        gaps = [b[0] - a[0] for a, b in zip(growth, growth[1:])]
        print("크기 갱신 간격: 최소 %.2f초 / 중앙값 %.2f초 / 최대 %.2f초 (%d회 관측)"
              % (min(gaps), sorted(gaps)[len(gaps) // 2], max(gaps), len(gaps)))
        print("-> 최대 간격보다 stall 을 작게 잡으면 녹화 도중에 중단으로 잘못 판정합니다.")
    for i, mark in enumerate(marks, 1):
        print("표시 %d: %.2f초" % (i, mark))

    print("\n설정값을 달리했을 때의 판정 시각 (기록을 시작한 순간이 0초입니다)")
    print("%-36s %10s %10s" % ("주기 / 하한 / 증가폭 / stall", "시작", "중단"))
    combos = [
        (1.0, 1024 * 1024, 256 * 1024, 8.0),
        (0.5, 1024 * 1024, 256 * 1024, 8.0),
        (0.5, 64 * 1024, 64 * 1024, 6.0),
        (0.3, 64 * 1024, 32 * 1024, 5.0),
        (0.3, 1024, 1024, 4.0),
    ]
    base = samples[0][0]
    for interval, min_size, min_growth, stall in combos:
        started, stopped = simulate(samples, interval, min_size, min_growth, stall)
        label = "%.1f초 / %s / %s / %.0f초" % (
            interval, human(min_size), human(min_growth), stall)
        print("%-36s %10s %10s" % (
            label,
            "%.2f초" % (started - base) if started else "없음",
            "%.2f초" % (stopped - base) if stopped else "없음"))

    print("\n잠금 신호로 판정했을 때")
    for interval in (0.5, 0.25):
        started, stopped = simulate_lock(samples, interval, 1024)
        print("%-36s %10s %10s" % (
            "주기 %.2f초" % interval,
            "%.2f초" % (started - base) if started else "없음",
            "%.2f초" % (stopped - base) if stopped else "없음"))
    return 0


def main(argv):
    ap = argparse.ArgumentParser(description="녹화 파일 크기 반영 시점 추적")
    ap.add_argument("--dir", action="append", default=None)
    ap.add_argument("--seconds", type=float, default=120.0)
    ap.add_argument("--sample", type=float, default=0.1)
    args = ap.parse_args(argv)

    dirs = resolve_dirs(args.dir)
    if not dirs:
        print("감시할 폴더를 찾지 못했습니다. --dir 로 지정하십시오.")
        return 2

    print("감시 폴더: %s" % ", ".join(dirs))
    print("표본 주기: %.2f초 / 최대 %.0f초 동안 기록합니다." % (args.sample, args.seconds))
    print("Alt+F9 를 누른 직후에 스페이스를 눌러 표시를 남기고, 중단할 때에도 같게 하십시오.")
    print("Q 를 누르면 기록을 끝냅니다.\n")

    begin = time.time()
    samples, marks, changes = [], [], []
    previous = {}
    while time.time() - begin < args.seconds:
        now = time.time()
        snapshot = sweep(dirs, DEFAULT_PATTERNS)
        samples.append((now, snapshot))
        for path, (stat_size, hnd_size, locked) in snapshot.items():
            was = previous.get(path)
            before = was[0] if was else None
            if before != stat_size:
                changes.append((now - begin, path, before, stat_size, hnd_size))
                print("%7.2f초  %-38s %12s  (%s)%s" % (
                    now - begin, os.path.basename(path)[-38:], human(stat_size),
                    "+" + human(stat_size - before) if before is not None else "새 파일",
                    "" if hnd_size in (None, stat_size)
                    else "  핸들로 잰 값 %s" % human(hnd_size)))
            if was is None or was[2] != locked:
                state = {True: "쓰기로 열림", False: "닫혀 있음"}.get(locked, "알 수 없음")
                print("%7.2f초  %-38s 잠금 상태 -> %s"
                      % (now - begin, os.path.basename(path)[-38:], state))
        for path in previous:
            if path not in snapshot:
                changes.append((now - begin, path, previous[path][0], None, None))
                print("%7.2f초  %-38s 사라졌습니다"
                      % (now - begin, os.path.basename(path)[-38:]))
        previous = snapshot

        if msvcrt is not None and msvcrt.kbhit():
            key = msvcrt.getch()
            if key in (b"q", b"Q"):
                break
            marks.append(now - begin)
            print("%7.2f초  <-- 표시 %d (사용자가 누른 시각)" % (now - begin, len(marks)))
        time.sleep(max(0.0, args.sample - (time.time() - now)))

    return report(samples, changes, marks)


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
