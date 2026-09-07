"""폴더를 훑어 파일 크기를 모으고, 사람이 읽기 좋은 단위로 바꿉니다."""

import ctypes
import os
import sys

try:
    import winsound
except ImportError:
    winsound = None

DEFAULT_PATTERNS = (".tmp", ".mp4", ".mkv")

# 녹화 중인 파일이 열려 있는지 확인할 때 쓰는 윈도우 상수들입니다.
_GENERIC_READ = 0x80000000
_FILE_SHARE_READ = 0x00000001
_OPEN_EXISTING = 3
_FILE_ATTRIBUTE_NORMAL = 0x80
_ERROR_SHARING_VIOLATION = 32
_INVALID_HANDLE = ctypes.c_void_p(-1).value

if sys.platform.startswith("win"):
    from ctypes import wintypes

    _kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    _kernel32.CreateFileW.restype = wintypes.HANDLE
    _kernel32.CreateFileW.argtypes = [
        wintypes.LPCWSTR, wintypes.DWORD, wintypes.DWORD, ctypes.c_void_p,
        wintypes.DWORD, wintypes.DWORD, wintypes.HANDLE]
    _kernel32.CloseHandle.argtypes = [wintypes.HANDLE]
else:
    _kernel32 = None


def scan(dirs, patterns, min_size, recursive=True):
    """조건에 맞는 파일의 경로와 크기를 모읍니다.

    폴더가 없거나 파일을 읽지 못해도 예외를 내지 않고 건너뜁니다.
    감지의 기준이 되는 함수이므로 동작을 바꾸지 마십시오.
    """
    found = {}
    for root_dir in dirs:
        if not os.path.isdir(root_dir):
            continue
        if recursive:
            walker = os.walk(root_dir)
        else:
            walker = [(root_dir, [], os.listdir(root_dir))]
        for cur, _subdirs, files in walker:
            for name in files:
                low = name.lower()
                if patterns and not any(low.endswith(p) for p in patterns):
                    continue
                path = os.path.join(cur, name)
                try:
                    size = os.path.getsize(path)
                except OSError:
                    continue
                if size >= min_size:
                    found[path] = size
    return found


def being_written(path):
    """다른 프로세스가 이 파일을 쓰기 위해 열어 두고 있는지 알아봅니다.

    ShadowPlay 는 녹화하는 동안 mp4 파일을 계속 열어 두고, 중단하는 순간
    닫습니다. 그래서 이 값이 True 에서 False 로 바뀌는 시점이 곧 녹화가
    끝난 시점입니다. 크기가 늘기를 기다리지 않아도 되므로 훨씬 빠릅니다.

    읽기 권한만 요구하고 공유는 읽기까지만 허용해서 여는 방식이라, 파일을
    고치지 않고 잠그지도 않습니다. 열리면 아무도 쓰고 있지 않다는 뜻이므로
    False 를, 공유 위반이면 True 를 돌려줍니다. 파일이 없거나 권한이 없어
    판단할 수 없으면 None 을 돌려주며, 부르는 쪽은 이때 기존 판정을 씁니다.
    """
    if _kernel32 is None:
        return None
    handle = _kernel32.CreateFileW(path, _GENERIC_READ, _FILE_SHARE_READ, None,
                                   _OPEN_EXISTING, _FILE_ATTRIBUTE_NORMAL, None)
    if handle and handle != _INVALID_HANDLE:
        _kernel32.CloseHandle(handle)
        return False
    if ctypes.get_last_error() == _ERROR_SHARING_VIOLATION:
        return True
    return None


def human(n):
    n = float(n)
    for unit in ("B", "KB", "MB", "GB"):
        if n < 1024 or unit == "GB":
            return "%d B" % int(n) if unit == "B" else "%.1f %s" % (n, unit)
        n /= 1024
    return "%.1f GB" % n


def hms(seconds):
    s = int(seconds)
    return "%d:%02d:%02d" % (s // 3600, (s % 3600) // 60, s % 60)


def sound(kind, enabled):
    """시작과 중단을 소리로도 알립니다. 실패해도 무시합니다."""
    if not enabled or winsound is None or not sys.platform.startswith("win"):
        return
    try:
        if kind == "start":
            winsound.Beep(880, 120)
        else:
            winsound.Beep(523, 180)
    except Exception:
        pass
