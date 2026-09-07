"""창 크기와 색, 글꼴을 한곳에 모아 둡니다."""

from tkinter import font as tkfont

WIN_W, WIN_H = 960, 640

# 960x640 안에서 세로로 잘리지 않도록 각 영역의 높이를 실측치 기준으로 고정합니다.
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
