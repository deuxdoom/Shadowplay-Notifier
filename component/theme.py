"""창 크기와 색, 글꼴을 한곳에 모아 둡니다.

월페이퍼 화면과 녹화 화면이 함께 쓰는 값만 여기에 둡니다. 한쪽 화면에서만
쓰는 자리와 색은 그 화면을 맡은 모듈이 직접 들고 있습니다.
"""

from tkinter import font as tkfont

WIN_W, WIN_H = 960, 640

# 캔버스 위에 얹는 글자의 기본 밝기입니다. 녹화 화면의 값과 파일 이름처럼
# 흰색보다 한 단계씩 가라앉혀야 하는 자리에 씁니다. 월페이퍼 화면의 글자는
# 어느 시간대에나 흰색이며, 그 값은 ``component/wallpaper.py`` 에 있습니다.
INK, INK_2, INK_3 = "#f1f2f3", "#bdc5ce", "#c6d0dc"

C_BG = "#0d0d0f"
C_PANEL = "#16161a"
C_FIELD = "#1e1e24"
C_LINE = "#33333a"
C_FG = "#f2f2f5"
C_DIM = "#d6d6dc"
C_MUTED = "#8a8a93"
C_REC_TEXT = "#ff6b6b"
C_SKY = "#74c0fc"

UI_FAMILIES = ("맑은 고딕", "Malgun Gothic", "Segoe UI", "Consolas")
MONO_FAMILIES = ("Consolas", "D2Coding", "Courier New")

# 캔버스 화면에 쓰는 글꼴입니다. ``component/fonts.py`` 가 함께 묶어 온
# 파일을 이 프로그램에서만 쓰도록 등록하며, 없으면 뒤의 것으로 넘어갑니다.
# Pretendard JP 는 한글과 일본어를 한 벌로 담고 있습니다.
WALL_UI_FAMILIES = ("Pretendard JP", "맑은 고딕", "Malgun Gothic", "Segoe UI")

# 글자 사이가 고르게 보여야 하는 자리에만 쓰는 글꼴입니다. 시간대 이름(DAWN,
# MORNING), NOW PLAYING, 도시 이름, 오른쪽 아래 버전이 여기에 해당합니다.
# 나머지 글은 WALL_UI_FAMILIES 를 그대로 씁니다.
WALL_MONO_FAMILIES = ("JetBrains Mono", "Consolas", "Segoe UI")


def pick_font(root, families, size, weight="normal"):
    """설치된 글꼴 중 앞에 있는 것을 씁니다. 없으면 마지막 것으로 넘어갑니다."""
    available = set(tkfont.families(root))
    for name in families:
        if name in available:
            return tkfont.Font(family=name, size=size, weight=weight)
    return tkfont.Font(family=families[-1], size=size, weight=weight)


def pick_family(root, families=UI_FAMILIES):
    """설치된 글꼴의 이름만 골라 돌려줍니다.

    ``("맑은 고딕", -14)`` 처럼 튜플로 글꼴을 넘기는 자리에 씁니다. 튜플은
    :class:`tkinter.font.Font` 객체와 달리 참조를 붙들어 둘 필요가 없어서,
    잠깐 떴다 사라지는 팝업에서 다루기 쉽습니다. 이름을 코드에 그대로 적으면
    그 글꼴이 없는 윈도우에서 Tk 가 말없이 다른 글꼴로 바꿔 그립니다.
    """
    available = set(tkfont.families(root))
    for name in families:
        if name in available:
            return name
    return families[-1]


def round_rect(x, y, width, height, radius):
    """모서리가 둥근 사각형의 꼭짓점입니다. 앨범 커버 받침과 녹화 표시등에 씁니다.

    폭과 높이에서 1 을 빼는 것이 중요합니다. 캔버스의 좌표는 픽셀의 인덱스라서
    ``x`` 에서 ``x + width`` 까지를 주면 실제로 칠해지는 것은 ``x`` 부터
    ``x + width - 1`` 까지입니다. 그대로 두면 오른쪽과 아래의 제어점만 마지막
    픽셀보다 하나 바깥에 놓여 그쪽 모서리가 덜 깎입니다. 실제로 재 보니 왼쪽
    위는 4px, 오른쪽 아래는 2px 만 깎여서 같은 사각형인데도 왼쪽이 더 둥글어
    보였습니다. 1 을 빼면 네 귀퉁이가 똑같아집니다.
    """
    r = radius
    width, height = width - 1, height - 1
    return (x + r, y, x + width - r, y, x + width, y, x + width, y + r,
            x + width, y + height - r, x + width, y + height,
            x + width - r, y + height, x + r, y + height, x, y + height,
            x, y + height - r, x, y + r, x, y)
