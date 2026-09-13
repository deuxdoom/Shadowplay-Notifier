"""모니터 배율과 좌표를 다루고, 창을 놓을 자리를 정합니다."""

import ctypes
import sys

from .paths import detail, log
from .theme import WIN_H, WIN_W


def enable_dpi_awareness():
    """배율 설정에서 창이 흐리게 늘어나지 않도록 DPI 인식을 켭니다.

    모니터마다 배율이 다를 수 있으므로 모니터별 인식(2)을 먼저 시도합니다.
    """
    if not sys.platform.startswith("win"):
        return
    for awareness in (2, 1):
        try:
            ctypes.windll.shcore.SetProcessDpiAwareness(awareness)
            return
        except Exception:
            continue
    try:
        ctypes.windll.user32.SetProcessDPIAware()
    except Exception:
        pass


class _RECT(ctypes.Structure):
    _fields_ = [("left", ctypes.c_long), ("top", ctypes.c_long),
                ("right", ctypes.c_long), ("bottom", ctypes.c_long)]


def monitor_rects():
    """연결된 모니터의 물리 좌표를 (좌, 상, 너비, 높이) 목록으로 돌려줍니다."""
    if not sys.platform.startswith("win"):
        return []
    rects = []
    try:
        proc = ctypes.WINFUNCTYPE(ctypes.c_int, ctypes.c_void_p,
                                  ctypes.c_void_p, ctypes.POINTER(_RECT),
                                  ctypes.c_ssize_t)

        def collect(_monitor, _hdc, lprect, _data):
            r = lprect.contents
            rects.append((r.left, r.top, r.right - r.left, r.bottom - r.top))
            return 1

        ctypes.windll.user32.EnumDisplayMonitors(0, 0, proc(collect), 0)
    except Exception as exc:
        detail("[표시] 모니터 목록을 읽지 못했습니다: %s" % exc)
        return []
    rects.sort(key=lambda item: (item[0], item[1]))
    return rects


def monitor_for_point(x, y):
    """주어진 좌표를 품고 있는 모니터의 (좌, 상, 너비, 높이) 를 돌려줍니다."""
    for left, top, width, height in monitor_rects():
        if left <= x < left + width and top <= y < top + height:
            return (left, top, width, height)
    return None


def center_in(rect):
    left, top, width, height = rect
    return (left + max(0, (width - WIN_W) // 2),
            top + max(0, (height - WIN_H) // 2))


def window_position(index):
    """창을 놓을 좌표를 정합니다. 모니터를 못 읽으면 None 을 돌려줍니다.

    index 가 0 이상이면 그 모니터를 쓰되, 없거나 창보다 작으면 물러섭니다.
    음수(자동)이면 창 크기와 정확히 같은 모니터를 먼저 찾고, 그런 모니터가
    없으면 주 모니터 한가운데에 놓습니다. 보조 모니터가 없거나 해상도가 다른
    환경에서도 창이 화면 밖으로 나가지 않게 하기 위해서입니다.
    """
    rects = monitor_rects()
    if not rects:
        return None
    if 0 <= index < len(rects):
        chosen = rects[index]
        if chosen[2] >= WIN_W and chosen[3] >= WIN_H:
            return center_in(chosen)
        detail("[표시] %d번 모니터(%dx%d)가 창보다 작아 자동 선택으로 넘어갑니다."
            % (index, chosen[2], chosen[3]))
    elif index >= 0:
        detail("[표시] %d번 모니터가 없어 자동 선택으로 넘어갑니다. (연결된 모니터 %d개)"
            % (index, len(rects)))

    for rect in rects:
        if rect[2] == WIN_W and rect[3] == WIN_H:
            detail("[표시] 창 크기와 같은 모니터를 찾았습니다: %s" % (rect,))
            return center_in(rect)

    primary = monitor_for_point(0, 0) or rects[0]
    detail("[표시] 주 모니터 한가운데에 표시합니다: %s" % (primary,))
    return center_in(primary)
