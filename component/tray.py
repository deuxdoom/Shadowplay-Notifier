"""Windows 알림 영역. 별도 패키지·스레드 없이 Tk의 메시지 루프를 씁니다.

트레이 전용 숨은 HWND를 두어 Tk가 전체화면 전환 중 창을 다시 만들어도
아이콘이 유지됩니다. 네이티브 콜백에서는 이벤트만 큐에 넣습니다.
"""

import ctypes
import os
from collections import deque
from ctypes import wintypes as w

from .i18n import tr
from .paths import RESOURCE_DIR, log

WINDOW_CLASS = "ShadowPlayNotifier.Tray"
RESTORE_MESSAGE = 0x8002
CALLBACK_MESSAGE = 0x8001
user32 = ctypes.WinDLL("user32", use_last_error=True)
shell32 = ctypes.WinDLL("shell32", use_last_error=True)
kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
LRESULT = ctypes.c_ssize_t
WNDPROC = ctypes.WINFUNCTYPE(LRESULT, w.HWND, w.UINT, w.WPARAM, w.LPARAM)


class WNDCLASS(ctypes.Structure):
    _fields_ = [("style", w.UINT), ("lpfnWndProc", WNDPROC), ("cbClsExtra", ctypes.c_int),
                ("cbWndExtra", ctypes.c_int), ("hInstance", w.HINSTANCE), ("hIcon", w.HICON),
                ("hCursor", w.HANDLE), ("hbrBackground", w.HBRUSH),
                ("lpszMenuName", w.LPCWSTR), ("lpszClassName", w.LPCWSTR)]


class GUID(ctypes.Structure):
    _fields_ = [("Data1", w.DWORD), ("Data2", w.WORD), ("Data3", w.WORD),
                ("Data4", ctypes.c_ubyte * 8)]


class NOTIFYICONDATA(ctypes.Structure):
    _fields_ = [("cbSize", w.DWORD), ("hWnd", w.HWND), ("uID", w.UINT),
                ("uFlags", w.UINT), ("uCallbackMessage", w.UINT), ("hIcon", w.HICON),
                ("szTip", w.WCHAR * 128), ("dwState", w.DWORD), ("dwStateMask", w.DWORD),
                ("szInfo", w.WCHAR * 256), ("uVersion", w.UINT),
                ("szInfoTitle", w.WCHAR * 64), ("dwInfoFlags", w.DWORD),
                ("guidItem", GUID), ("hBalloonIcon", w.HICON)]


def _api(dll, name, arguments, result):
    fn = getattr(dll, name)
    fn.argtypes, fn.restype = arguments, result
    return fn


_api(kernel32, "GetModuleHandleW", [w.LPCWSTR], w.HMODULE)
_api(user32, "RegisterClassW", [ctypes.POINTER(WNDCLASS)], w.ATOM)
_api(user32, "UnregisterClassW", [w.LPCWSTR, w.HINSTANCE], w.BOOL)
_api(user32, "CreateWindowExW", [w.DWORD, w.LPCWSTR, w.LPCWSTR, w.DWORD,
     ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_int, w.HWND, w.HMENU,
     w.HINSTANCE, w.LPVOID], w.HWND)
_api(user32, "DefWindowProcW", [w.HWND, w.UINT, w.WPARAM, w.LPARAM], LRESULT)
_api(user32, "DestroyWindow", [w.HWND], w.BOOL)
_api(user32, "RegisterWindowMessageW", [w.LPCWSTR], w.UINT)
_api(user32, "LoadImageW", [w.HINSTANCE, w.LPCWSTR, w.UINT,
                           ctypes.c_int, ctypes.c_int, w.UINT], w.HANDLE)
_api(user32, "DestroyIcon", [w.HICON], w.BOOL)
_api(user32, "LoadIconW", [w.HINSTANCE, ctypes.c_void_p], w.HICON)
_api(user32, "CreatePopupMenu", [], w.HMENU)
_api(user32, "AppendMenuW", [w.HMENU, w.UINT, ctypes.c_size_t, w.LPCWSTR], w.BOOL)
_api(user32, "DestroyMenu", [w.HMENU], w.BOOL)
_api(user32, "TrackPopupMenu", [w.HMENU, w.UINT, ctypes.c_int, ctypes.c_int,
                              ctypes.c_int, w.HWND, ctypes.c_void_p], w.UINT)
_api(user32, "GetCursorPos", [ctypes.POINTER(w.POINT)], w.BOOL)
_api(user32, "SetForegroundWindow", [w.HWND], w.BOOL)
_api(user32, "PostMessageW", [w.HWND, w.UINT, w.WPARAM, w.LPARAM], w.BOOL)
_api(shell32, "Shell_NotifyIconW", [w.DWORD, ctypes.POINTER(NOTIFYICONDATA)], w.BOOL)


class TrayIcon:
    COMMANDS = {1: "show", 5: "settings", 8: "startup", 9: "update", 6: "github", 7: "quit"}

    def __init__(self, root, actions, state, startup_state=None):
        self.root, self.actions, self.state = root, actions, state
        self.startup_state = startup_state or (lambda: False)
        self._events = deque(maxlen=32)
        self._after_id = None
        self._closed, self.available = False, False
        self.hwnd = self._icon = None
        self._owns_icon = False
        self._tip = ""
        self._module = kernel32.GetModuleHandleW(None)
        self._taskbar_created = user32.RegisterWindowMessageW("TaskbarCreated")
        self._callback = WNDPROC(self._window_proc)
        self._class = WNDCLASS()
        self._class.lpfnWndProc, self._class.hInstance = self._callback, self._module
        self._class.lpszClassName = WINDOW_CLASS
        self._registered = bool(user32.RegisterClassW(ctypes.byref(self._class)))
        try:
            if not self._registered:
                raise ctypes.WinError(ctypes.get_last_error())
            self.hwnd = user32.CreateWindowExW(0, WINDOW_CLASS, WINDOW_CLASS, 0,
                                              0, 0, 0, 0, None, None, self._module, None)
            if not self.hwnd:
                raise ctypes.WinError(ctypes.get_last_error())
            path = os.path.join(RESOURCE_DIR, "appicon.ico")
            self._icon = user32.LoadImageW(None, path, 1, 32, 32, 0x10)
            self._owns_icon = bool(self._icon)
            if not self._icon:
                self._icon = user32.LoadIconW(None, ctypes.c_void_p(32512))
            self._data = NOTIFYICONDATA()
            self._data.cbSize = ctypes.sizeof(self._data)
            self._data.hWnd, self._data.uID = self.hwnd, 1
            self._data.uFlags = 1 | 2 | 4 | 0x80  # message, icon, tip, showtip
            self._data.uCallbackMessage, self._data.hIcon = CALLBACK_MESSAGE, self._icon
            self._data.szTip = "ShadowPlay Notifier"
            self._add()
            self._after_id = root.after(100, self._drain)
        except Exception as exc:
            log("[트레이] 초기화하지 못했습니다: %s" % exc)
            self.close()

    def _add(self):
        self.available = bool(shell32.Shell_NotifyIconW(0, ctypes.byref(self._data)))
        if self.available:
            self._data.uVersion = 4
            shell32.Shell_NotifyIconW(4, ctypes.byref(self._data))
        else:
            log("[트레이] 알림 영역에 아이콘을 넣지 못했습니다.")

    def _window_proc(self, hwnd, message, wparam, lparam):
        if message == self._taskbar_created:
            self._events.append("recreate")
            return 0
        if message == RESTORE_MESSAGE:
            self._events.append("show")
            return 0
        if message == CALLBACK_MESSAGE:
            event = lparam & 0xffff
            if event in (0x203, 0x400, 0x401):  # double click, NIN_SELECT, NIN_KEYSELECT
                self._events.append("show")
            elif event == 0x7b:  # WM_CONTEXTMENU (version 4)
                self._events.append("menu")
            return 0
        if message == 0x111 and (wparam & 0xffff) in self.COMMANDS:  # WM_COMMAND
            self._events.append(self.COMMANDS[wparam & 0xffff])
            return 0
        return user32.DefWindowProcW(hwnd, message, wparam, lparam)

    def _drain(self):
        self._after_id = None
        while self._events and not self._closed:
            event = self._events.popleft()
            if event == "recreate":
                self._add()
                if not self.available:
                    self.actions["show"]()  # 숨은 창으로 사용자를 가두지 않습니다.
            elif event == "menu":
                self._show_menu()
            else:
                self.dispatch(event)
        if not self._closed:
            self._update_tip()
            self._after_id = self.root.after(100, self._drain)

    def dispatch(self, action):
        callback = self.actions.get(action)
        if callback:
            try:
                callback()
            except Exception as exc:
                log("[트레이] %s 실행 실패: %s" % (action, exc))

    def menu_entries(self):
        return [(0, "ShadowPlay Notifier", 2), (0, "", 0x800),
                (1, tr("창 열기"), 0),
                (5, tr("환경설정"), 0),
                (8, tr("윈도우 시작 시 실행"), 8 if self.startup_state() else 0),
                (9, tr("최신 버전 확인"), 0),
                (6, tr("GitHub 프로젝트"), 0),
                (0, "", 0x800), (7, tr("프로그램 종료"), 0)]

    def _show_menu(self):
        menu = user32.CreatePopupMenu()
        if not menu:
            return
        try:
            for command, label, flags in self.menu_entries():
                user32.AppendMenuW(menu, flags, command, label)
            point = w.POINT()
            user32.GetCursorPos(ctypes.byref(point))
            user32.SetForegroundWindow(self.hwnd)
            command = user32.TrackPopupMenu(menu, 0x102, point.x, point.y, 0, self.hwnd, None)
            user32.PostMessageW(self.hwnd, 0, 0, 0)
        finally:
            user32.DestroyMenu(menu)
        if command in self.COMMANDS:
            self.dispatch(self.COMMANDS[command])

    def _update_tip(self):
        state = self.state()
        tip = "ShadowPlay Notifier · " + tr(
            "녹화 중" if state.get("recording") else "녹화 대기")
        if tip != self._tip:
            self._tip = tip
            self._data.szTip = tip
            if self.available:
                shell32.Shell_NotifyIconW(1, ctypes.byref(self._data))

    def close(self):
        if self._closed:
            return
        self._closed = True
        if self._after_id is not None:
            self.root.after_cancel(self._after_id)
            self._after_id = None
        if self.available:
            shell32.Shell_NotifyIconW(2, ctypes.byref(self._data))
            self.available = False
        if self.hwnd:
            user32.DestroyWindow(self.hwnd)
            self.hwnd = None
        if self._icon and self._owns_icon:
            user32.DestroyIcon(self._icon)
        self._icon = None
        if self._registered:
            user32.UnregisterClassW(WINDOW_CLASS, self._module)
            self._registered = False
