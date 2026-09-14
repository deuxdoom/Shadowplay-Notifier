"""업데이트에 필요한 Windows 프로세스·뮤텍스 API. 셸을 실행하지 않습니다."""

import ctypes
import os
import subprocess
import sys
import time
from ctypes import wintypes as w

UPDATE_MUTEX = "ShadowPlayNotifier-deuxdoom-update"
UPDATE_TITLE = "ShadowPlay Notifier 업데이트"
k32 = ctypes.WinDLL("kernel32", use_last_error=True)
u32 = ctypes.WinDLL("user32", use_last_error=True)
psapi = ctypes.WinDLL("psapi", use_last_error=True)


def _api(dll, name, args, result):
    fn = getattr(dll, name)
    fn.argtypes, fn.restype = args, result
    return fn


_api(k32, "OpenProcess", [w.DWORD, w.BOOL, w.DWORD], w.HANDLE)
_api(k32, "CloseHandle", [w.HANDLE], w.BOOL)
_api(k32, "QueryFullProcessImageNameW", [w.HANDLE, w.DWORD, w.LPWSTR,
                                       ctypes.POINTER(w.DWORD)], w.BOOL)
_api(k32, "WaitForSingleObject", [w.HANDLE, w.DWORD], w.DWORD)
_api(k32, "TerminateProcess", [w.HANDLE, w.UINT], w.BOOL)
_api(k32, "CreateMutexW", [w.LPVOID, w.BOOL, w.LPCWSTR], w.HANDLE)
_api(k32, "OpenMutexW", [w.DWORD, w.BOOL, w.LPCWSTR], w.HANDLE)
_api(k32, "SetDllDirectoryW", [w.LPCWSTR], w.BOOL)
_api(psapi, "EnumProcesses", [w.LPVOID, w.DWORD, ctypes.POINTER(w.DWORD)], w.BOOL)
ENUM_WINDOWS = ctypes.WINFUNCTYPE(w.BOOL, w.HWND, w.LPARAM)
_api(u32, "EnumWindows", [ENUM_WINDOWS, w.LPARAM], w.BOOL)
_api(u32, "GetWindowThreadProcessId", [w.HWND, ctypes.POINTER(w.DWORD)], w.DWORD)
_api(u32, "GetClassNameW", [w.HWND, w.LPWSTR, ctypes.c_int], ctypes.c_int)
_api(u32, "PostMessageW", [w.HWND, w.UINT, w.WPARAM, w.LPARAM], w.BOOL)
_api(u32, "FindWindowW", [w.LPCWSTR, w.LPCWSTR], w.HWND)
_api(u32, "SetForegroundWindow", [w.HWND], w.BOOL)
_api(u32, "GetAncestor", [w.HWND, w.UINT], w.HWND)
_api(u32, "GetWindowRect", [w.HWND, ctypes.POINTER(w.RECT)], w.BOOL)
_api(u32, "SetWindowPos", [w.HWND, w.HWND, ctypes.c_int, ctypes.c_int,
                           ctypes.c_int, ctypes.c_int, w.UINT], w.BOOL)
_api(u32, "SendMessageTimeoutW", [w.HWND, w.UINT, w.WPARAM, w.LPARAM,
                                 w.UINT, w.UINT, ctypes.POINTER(ctypes.c_size_t)], w.LPARAM)


def canonical(path):
    return os.path.normcase(os.path.realpath(path))


class UpdateLock:
    def __init__(self):
        self.handle = k32.CreateMutexW(None, False, UPDATE_MUTEX)
        if not self.handle:
            raise ctypes.WinError(ctypes.get_last_error())
        if ctypes.get_last_error() == 183:
            self.close()
            raise RuntimeError("이미 업데이트가 진행 중입니다.")

    def close(self):
        if self.handle:
            k32.CloseHandle(self.handle)
            self.handle = None


def update_active():
    handle = k32.OpenMutexW(0x100000, False, UPDATE_MUTEX)
    if handle:
        k32.CloseHandle(handle)
    return bool(handle)


def focus_update():
    hwnd = u32.FindWindowW(None, UPDATE_TITLE)
    if hwnd:
        u32.SetForegroundWindow(hwnd)


def center_window(window, monitor):
    """DPI 배율에 따른 타이틀바/테두리까지 포함해 모니터 중앙에 놓습니다."""
    window.update_idletasks()
    hwnd = u32.GetAncestor(window.winfo_id(), 2)
    bounds = w.RECT()
    if hwnd and u32.GetWindowRect(hwnd, ctypes.byref(bounds)):
        left, top, width, height = monitor
        x = left + (width - (bounds.right - bounds.left)) // 2
        y = top + (height - (bounds.bottom - bounds.top)) // 2
        u32.SetWindowPos(hwnd, None, x, y, 0, 0, 0x15)


def _image(handle):
    buffer = ctypes.create_unicode_buffer(32768)
    size = w.DWORD(len(buffer))
    if k32.QueryFullProcessImageNameW(handle, 0, buffer, ctypes.byref(size)):
        return canonical(buffer.value)
    return None


def matching_processes(target):
    """이름 대신 전체 경로를 비교합니다. 반환한 핸들은 호출자가 닫습니다."""
    capacity = 2048
    while True:
        pids = (w.DWORD * capacity)()
        used = w.DWORD()
        if not psapi.EnumProcesses(pids, ctypes.sizeof(pids), ctypes.byref(used)):
            raise ctypes.WinError(ctypes.get_last_error())
        if used.value < ctypes.sizeof(pids):
            break
        capacity *= 2
    found = []
    expected = canonical(target)
    for pid in pids[:used.value // ctypes.sizeof(w.DWORD)]:
        if pid == os.getpid():
            continue
        handle = k32.OpenProcess(0x1000 | 0x100000, False, pid)
        if not handle:
            continue
        if _image(handle) == expected:
            found.append((pid, handle))
        else:
            k32.CloseHandle(handle)
    return found


def process_ids(target):
    matches = matching_processes(target)
    try:
        return {pid for pid, _handle in matches}
    finally:
        for _pid, handle in matches:
            k32.CloseHandle(handle)


def tray_windows(target):
    pids = process_ids(target)
    windows = []

    def collect(hwnd, _data):
        pid = w.DWORD()
        u32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
        if pid.value in pids:
            name = ctypes.create_unicode_buffer(256)
            u32.GetClassNameW(hwnd, name, len(name))
            if name.value == "ShadowPlayNotifier.Tray":
                windows.append(hwnd)
        return True

    u32.EnumWindows(ENUM_WINDOWS(collect), 0)
    return windows


def stop_target(target, grace=10.0):
    """정상 종료를 요청하고 기다린 뒤 같은 경로의 잔여 프로세스만 종료합니다."""
    for hwnd in tray_windows(target):
        u32.PostMessageW(hwnd, 0x111, 7, 0)
    deadline = time.monotonic() + grace
    while process_ids(target) and time.monotonic() < deadline:
        time.sleep(.1)
    matches = matching_processes(target)
    try:
        for pid, handle in matches:
            if k32.WaitForSingleObject(handle, 0) == 0:
                continue
            # 종료 권한은 필요할 때만 얻습니다. 새 핸들에서도 경로를 확인합니다.
            killer = k32.OpenProcess(0x1000 | 0x100000 | 1, False, pid)
            if not killer:
                if k32.WaitForSingleObject(handle, 0) == 0:
                    continue
                raise ctypes.WinError(ctypes.get_last_error())
            try:
                if _image(killer) == canonical(target):
                    if not k32.TerminateProcess(killer, 0):
                        raise ctypes.WinError(ctypes.get_last_error())
                    k32.WaitForSingleObject(killer, 5000)
            finally:
                k32.CloseHandle(killer)
    finally:
        for _pid, handle in matches:
            k32.CloseHandle(handle)
    if process_ids(target):
        raise RuntimeError("기존 프로그램을 종료하지 못했습니다. 파일은 교체하지 않았습니다.")


def launch(command, cwd, restart_target=None):
    """onefile 추출 폴더와 콘솔을 물려주지 않는 독립 실행입니다."""
    env = dict(os.environ)
    for key in list(env):
        if key.startswith("_PYI_") or key == "_MEIPASS2":
            env.pop(key)
    env["PYINSTALLER_RESET_ENVIRONMENT"] = "1"
    env.pop("SPN_UPDATE_RESTART", None)
    if restart_target:
        env["SPN_UPDATE_RESTART"] = canonical(restart_target)
    frozen_dir = getattr(sys, "_MEIPASS", None)
    if frozen_dir:
        k32.SetDllDirectoryW(None)
    try:
        return subprocess.Popen(command, cwd=cwd, env=env, close_fds=True,
                                stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                                stderr=subprocess.DEVNULL,
                                creationflags=subprocess.CREATE_NO_WINDOW)
    finally:
        if frozen_dir:
            k32.SetDllDirectoryW(frozen_dir)


def restart(target, arguments, timeout=35.0):
    process = launch([str(target), *arguments], str(target.parent), target)
    deadline = time.monotonic() + timeout
    ready_since = None
    while time.monotonic() < deadline:
        if process.poll() is not None:
            raise RuntimeError("새 프로그램이 시작 중 종료되었습니다.")
        ready = False
        for hwnd in tray_windows(target):
            result = ctypes.c_size_t()
            if u32.SendMessageTimeoutW(hwnd, 0, 0, 0, 2, 500, ctypes.byref(result)):
                ready = True
        if ready:
            ready_since = ready_since or time.monotonic()
            if time.monotonic() - ready_since >= 2:
                return process.pid
        else:
            ready_since = None
        time.sleep(.1)
    raise RuntimeError("새 프로그램의 시작을 확인하지 못했습니다.")
