"""Windows 작업 표시줄과 같은 현재 현지 시각을 읽습니다.

CRT의 localtime은 프로세스가 물려받은 TZ 환경변수와 시간대 캐시를 쓰므로
Windows 설정과 다른 시각을 돌려줄 수 있습니다. 표시용 시각은 매번 Windows에
직접 묻고, 경과 시간 측정은 기존 monotonic/perf_counter를 그대로 씁니다.
"""

import ctypes
from ctypes import wintypes as w
from datetime import datetime


class _SYSTEMTIME(ctypes.Structure):
    _fields_ = [(name, w.WORD) for name in (
        "year", "month", "weekday", "day", "hour", "minute", "second", "millisecond")]


_kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
_get_local_time = _kernel32.GetLocalTime
_get_local_time.argtypes = [ctypes.POINTER(_SYSTEMTIME)]
_get_local_time.restype = None


def now():
    """환경변수나 앱 시작 시각에 관계없이 현재 Windows 현지 시각을 반환합니다."""
    value = _SYSTEMTIME()
    _get_local_time(ctypes.byref(value))
    return datetime(value.year, value.month, value.day,
                    value.hour, value.minute, value.second, value.millisecond * 1000)


def localtime():
    """날짜·요일·계절 표시에서 쓰는 struct_time입니다."""
    return now().timetuple()


def strftime(pattern):
    """시각을 다시 현지 시간으로 변환하지 않고 표시용 문자열을 만듭니다."""
    return now().strftime(pattern)
