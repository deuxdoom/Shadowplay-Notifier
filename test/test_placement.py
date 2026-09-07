"""디스플레이 구성이 달라져도 창이 화면 밖으로 나가지 않는지 확인합니다.

실행: python test\test_placement.py
실제 모니터 목록을 가짜로 바꿔치기해서, 보조 모니터가 없는 환경이나
해상도가 다른 환경까지 창 없이 확인합니다.
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from component import display  # noqa: E402
from component.theme import WIN_H, WIN_W  # noqa: E402

PRIMARY_4K = (0, 0, 3840, 2160)
PANEL_960 = (3840, 1520, 960, 640)
WIDE_SECOND = (3840, 0, 1920, 1080)
TINY_SECOND = (3840, 0, 800, 600)


def with_monitors(rects):
    display.monitor_rects = lambda: list(rects)


def center_of(rect):
    return (rect[0] + (rect[2] - WIN_W) // 2, rect[1] + (rect[3] - WIN_H) // 2)


cases = [
    # (설명, 모니터 목록, 요청한 번호, 기대 위치)
    ("960x640 보조 모니터가 있으면 자동으로 그 화면을 씁니다",
     [PRIMARY_4K, PANEL_960], -1, center_of(PANEL_960)),
    ("보조 모니터가 없으면 주 모니터 한가운데에 놓습니다",
     [PRIMARY_4K], -1, center_of(PRIMARY_4K)),
    ("보조 모니터가 더 크면 주 모니터 한가운데에 놓습니다",
     [PRIMARY_4K, WIDE_SECOND], -1, center_of(PRIMARY_4K)),
    ("번호를 직접 지정하면 그 모니터 한가운데에 놓습니다",
     [PRIMARY_4K, WIDE_SECOND], 1, center_of(WIDE_SECOND)),
    ("지정한 번호의 모니터가 없으면 자동 선택으로 물러섭니다",
     [PRIMARY_4K, PANEL_960], 5, center_of(PANEL_960)),
    ("지정한 모니터가 창보다 작으면 자동 선택으로 물러섭니다",
     [PRIMARY_4K, TINY_SECOND], 1, center_of(PRIMARY_4K)),
    ("주 모니터가 창보다 작아도 화면 밖으로 나가지 않습니다",
     [(0, 0, 800, 600)], -1, (0, 0)),
]

for note, rects, index, expected in cases:
    with_monitors(rects)
    got = display.window_position(index)
    assert got == expected, "%s -> %s (기대 %s)" % (note, got, expected)
    print("[통과] %s: %s" % (note, got))

with_monitors([])
assert display.window_position(-1) is None, "모니터를 못 읽으면 None 이어야 합니다"
print("[통과] 모니터 목록을 못 읽으면 tkinter 기본 중앙 정렬로 넘깁니다")

with_monitors([PRIMARY_4K, PANEL_960])
assert display.monitor_for_point(4000, 1600) == PANEL_960
assert display.monitor_for_point(100, 100) == PRIMARY_4K
assert display.monitor_for_point(-50, -50) is None
print("[통과] 좌표로 모니터 찾기")

print("\n모든 검사를 통과했습니다.")
