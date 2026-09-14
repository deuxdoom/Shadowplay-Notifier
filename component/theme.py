"""창 크기와 색, 글꼴을 한곳에 모아 둡니다."""

from tkinter import font as tkfont

WIN_W, WIN_H = 960, 640

# 960x640 에서 실측한 기준 높이입니다. 전체화면에서는 app._resize_layout 이
# 창 높이에 비례해 모든 영역을 함께 확대하며, 글자와 아이콘도 같은 기준으로 키웁니다.
# 멀리서 판단하는 화면이므로 녹화 정보에 자리를 몰아주고 로그는 최근 것만 남깁니다.
H_BANNER = 140
H_DETAIL = 319
H_LOG = 133
LOG_ROWS = 5
# 저장 폴더 값이 들어갈 수 있는 가로 폭입니다. 이름이 길면 글자를 줄여서 맞춥니다.
FOLDER_MAX_PX = 436

C_BG = "#0d0d0f"
C_PANEL = "#16161a"
C_FIELD = "#1e1e24"
C_LINE = "#33333a"
C_FG = "#f2f2f5"
C_DIM = "#d6d6dc"
C_MUTED = "#8a8a93"
C_REC = "#e03131"
C_REC_DIM = "#8f1f1f"
C_REC_TEXT = "#ff6b6b"
C_IDLE = "#3a3a3f"
C_IDLE_DOT = "#6a6a72"
C_WARN = "#f59f00"
C_SKY = "#74c0fc"
C_YELLOW = "#ffd43b"

UI_FAMILIES = ("맑은 고딕", "Malgun Gothic", "Segoe UI", "Consolas")
MONO_FAMILIES = ("Consolas", "D2Coding", "Courier New")

# 월페이퍼 화면에만 쓰는 글꼴입니다. ``component/fonts.py`` 가 함께 묶어 온
# 파일을 이 프로그램에서만 쓰도록 등록하며, 없으면 뒤의 것으로 넘어갑니다.
# 녹화 화면은 맑은 고딕으로 실측해 둔 배치를 그대로 지켜야 하므로 건드리지
# 않습니다. Pretendard JP 는 한글과 일본어를 한 벌로 담고 있습니다.
WALL_UI_FAMILIES = ("Pretendard JP", "맑은 고딕", "Malgun Gothic", "Segoe UI")

# 월페이퍼에서 글자 사이가 고르게 보여야 하는 자리에만 쓰는 글꼴입니다.
# 시간대 이름(DAWN, MORNING), NOW PLAYING, 도시 이름, 오른쪽 아래 버전이
# 여기에 해당합니다. 나머지 글은 WALL_UI_FAMILIES 를 그대로 씁니다.
WALL_MONO_FAMILIES = ("JetBrains Mono", "Consolas", "Segoe UI")


def pick_font(root, families, size, weight="normal"):
    """설치된 글꼴 중 앞에 있는 것을 씁니다. 없으면 마지막 것으로 넘어갑니다."""
    available = set(tkfont.families(root))
    for name in families:
        if name in available:
            return tkfont.Font(family=name, size=size, weight=weight)
    return tkfont.Font(family=families[-1], size=size, weight=weight)


def mix(color_a, color_b, t):
    """두 색을 t(0~1) 비율로 섞습니다. 배너 밝기 펄스에 씁니다."""
    t = max(0.0, min(1.0, t))
    a = (int(color_a[1:3], 16), int(color_a[3:5], 16), int(color_a[5:7], 16))
    b = (int(color_b[1:3], 16), int(color_b[3:5], 16), int(color_b[5:7], 16))
    return "#%02x%02x%02x" % tuple(
        int(round(a[i] + (b[i] - a[i]) * t)) for i in range(3))


def growth_color(seconds, stall):
    """마지막 증가가 오래될수록 눈에 띄는 색으로 바꿉니다."""
    if seconds >= max(3.0, stall * 0.75):
        return C_REC_TEXT
    if seconds > 3.0:
        return C_WARN
    return C_FG
