"""함께 묶어 온 글꼴을 이 프로그램에서만 쓰도록 등록합니다.

``AddFontResourceExW`` 를 ``FR_PRIVATE`` 로 부르면 시스템에 설치하지 않고
이 프로세스 안에서만 글꼴을 쓸 수 있습니다. 프로그램을 닫으면 함께 사라지며
사용자의 글꼴 목록을 건드리지 않습니다.

Pretendard JP 는 한글과 일본어를 한 벌로 담고 있어서, 일본 노래 제목이
네모 상자나 어울리지 않는 글꼴로 나오는 일을 막아 줍니다. 큰 시계에는
윈도우의 Segoe UI Light를, 초 표시에는 JetBrains Mono를 씁니다.
초는 글자 폭이 고르기 때문에 바뀔 때 자리가 흔들리지 않습니다.

글꼴 파일이 없으면 조용히 넘어가고 윈도우에 있는 글꼴로 그립니다.
"""

import ctypes
import os

from .paths import RESOURCE_DIR, detail, log

FONT_DIR = os.path.join(RESOURCE_DIR, "assets", "fonts")

# (파일 이름, 화면에 나오는 이름) 입니다.
BUNDLED = (
    ("PretendardJP-Regular.ttf", "Pretendard JP"),
    ("PretendardJP-Bold.ttf", "Pretendard JP"),
    ("JetBrainsMono-Regular.ttf", "JetBrains Mono"),
    ("JetBrainsMono-Bold.ttf", "JetBrains Mono"),
)

FR_PRIVATE = 0x10

_loaded = []
_done = False


def load():
    """묶어 온 글꼴을 등록합니다. 등록된 이름 목록을 돌려줍니다."""
    global _done
    if _done:
        return list(_loaded)
    _done = True
    if not os.path.isdir(FONT_DIR):
        detail("[글꼴] 글꼴 폴더가 없어 윈도우 글꼴을 씁니다: %s" % FONT_DIR)
        return []
    gdi32 = ctypes.windll.gdi32
    gdi32.AddFontResourceExW.argtypes = [ctypes.c_wchar_p, ctypes.c_uint,
                                         ctypes.c_void_p]
    gdi32.AddFontResourceExW.restype = ctypes.c_int
    names = []
    for filename, family in BUNDLED:
        path = os.path.join(FONT_DIR, filename)
        if not os.path.isfile(path):
            detail("[글꼴] 파일이 없습니다: %s" % filename)
            continue
        added = gdi32.AddFontResourceExW(path, FR_PRIVATE, None)
        if added:
            _loaded.append(path)
            if family not in names:
                names.append(family)
        else:
            log("[글꼴] 등록하지 못했습니다: %s" % filename)
    if names:
        detail("[글꼴] %s 를 이 프로그램에서만 쓰도록 등록했습니다." % ", ".join(names))
    return names


def unload():
    """등록을 되돌립니다. 프로그램을 닫을 때 부르면 됩니다."""
    if not _loaded:
        return
    gdi32 = ctypes.windll.gdi32
    gdi32.RemoveFontResourceExW.argtypes = [ctypes.c_wchar_p, ctypes.c_uint,
                                            ctypes.c_void_p]
    for path in _loaded:
        try:
            gdi32.RemoveFontResourceExW(path, FR_PRIVATE, None)
        except Exception:
            pass
    _loaded.clear()
