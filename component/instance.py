"""프로그램이 한 번에 하나만 돌도록 지킵니다.

이름 붙인 뮤텍스를 하나 잡아 두고, 그 이름이 이미 쓰이고 있으면 다른 창이
떠 있다고 봅니다. 뮤텍스는 프로세스가 끝날 때 운영체제가 알아서 놓아 주므로,
앱이 비정상적으로 죽어도 다음 실행이 막히지 않습니다.

윈도우가 아니거나 확인에 실패하면 실행을 막지 않습니다. 감시를 못 하게 되는
것보다는 창이 둘 뜨는 편이 낫기 때문입니다.
"""

import ctypes
import sys

from .paths import log

# 다른 프로그램과 겹치지 않도록 이름을 길게 잡았습니다. 사용자별 세션 안에서만
# 통하는 이름이라, 계정을 바꿔 로그인하면 각각 하나씩 띄울 수 있습니다.
MUTEX_NAME = "ShadowPlayNotifier-deuxdoom-single-instance"

_ERROR_ALREADY_EXISTS = 183
_SW_RESTORE = 9
_MB_OK = 0x00000000
_MB_ICONINFORMATION = 0x00000040
_MB_SETFOREGROUND = 0x00010000

if sys.platform.startswith("win"):
    from ctypes import wintypes

    _kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    _user32 = ctypes.WinDLL("user32", use_last_error=True)

    _kernel32.CreateMutexW.restype = wintypes.HANDLE
    _kernel32.CreateMutexW.argtypes = [ctypes.c_void_p, wintypes.BOOL,
                                       wintypes.LPCWSTR]
    _kernel32.CloseHandle.argtypes = [wintypes.HANDLE]

    _user32.FindWindowW.restype = wintypes.HWND
    _user32.FindWindowW.argtypes = [wintypes.LPCWSTR, wintypes.LPCWSTR]
    _user32.IsIconic.argtypes = [wintypes.HWND]
    _user32.ShowWindow.argtypes = [wintypes.HWND, ctypes.c_int]
    _user32.SetForegroundWindow.argtypes = [wintypes.HWND]
    _user32.MessageBoxW.argtypes = [wintypes.HWND, wintypes.LPCWSTR,
                                    wintypes.LPCWSTR, wintypes.UINT]
else:
    _kernel32 = None
    _user32 = None

# 잡아 둔 뮤텍스 손잡이입니다. 프로세스가 사는 동안 계속 들고 있어야 하므로
# 모듈 변수에 담아 둡니다. 놓아 버리면 다른 실행본이 곧바로 들어옵니다.
_held = None


def claim(name=MUTEX_NAME):
    """이 프로세스가 유일한 실행본인지 알아보고 자리를 잡습니다.

    처음 실행하는 것이면 True 를, 이미 다른 창이 떠 있으면 False 를 돌려줍니다.
    """
    global _held
    if _kernel32 is None:
        return True
    handle = _kernel32.CreateMutexW(None, False, name)
    if not handle:
        log("[중복 실행] 뮤텍스를 만들지 못했습니다(오류 %d). 그대로 실행합니다."
            % ctypes.get_last_error())
        return True
    if ctypes.get_last_error() == _ERROR_ALREADY_EXISTS:
        _kernel32.CloseHandle(handle)
        return False
    _held = handle
    return True


def release():
    """잡아 둔 뮤텍스를 놓습니다. 검사에서 되풀이해 확인할 때 씁니다."""
    global _held
    if _kernel32 is None or _held is None:
        return
    _kernel32.CloseHandle(_held)
    _held = None


def focus_existing(title):
    """이미 떠 있는 창을 찾아 앞으로 끌어옵니다.

    찾아서 끌어왔으면 True 를 돌려줍니다. 창을 찾지 못하면 False 이며,
    부르는 쪽은 그때 사용자에게 따로 알려 주면 됩니다.
    """
    if _user32 is None:
        return False
    hwnd = _user32.FindWindowW(None, title)
    if not hwnd:
        return False
    if _user32.IsIconic(hwnd):
        _user32.ShowWindow(hwnd, _SW_RESTORE)
    _user32.SetForegroundWindow(hwnd)
    return True


def tell_already_running(title):
    """창을 찾지 못했을 때만 짧은 알림 상자를 띄웁니다.

    ``--noconsole`` 로 빌드하므로 아무 것도 하지 않으면 사용자가 보기에는
    실행이 그냥 무시된 것처럼 보입니다. 그래서 이 경우에만 알립니다.
    """
    if _user32 is None:
        return
    _user32.MessageBoxW(
        None, "이미 실행 중입니다. 보조 디스플레이에 떠 있는 창을 확인하십시오.",
        title, _MB_OK | _MB_ICONINFORMATION | _MB_SETFOREGROUND)
