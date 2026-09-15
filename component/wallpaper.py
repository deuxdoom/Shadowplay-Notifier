"""상시 표시를 위한 월페이퍼: 큰 시계와 날씨, 지평선과 음악.

장면 계산은 단일 작업 스레드에서, Tk 접근은 UI 스레드에서만 합니다.
도형·예약 콜백 수는 고정이며 커버 및 배경 프레임은 누적하지 않습니다.
"""

import math
import time
import tkinter as tk
from concurrent.futures import ThreadPoolExecutor

from . import imaging, sky, version, weather, weather_icons
from .atmosphere import Atmosphere
from .audio import BARS
from .i18n import date_text, tr, weekday, weekday_leads
from .paths import log
from .recording_view import STATUS_Y, RecordingLayer
from .text import fit_text
from .theme import (INK, INK_3, WALL_MONO_FAMILIES, WALL_UI_FAMILIES,
                    pick_font, round_rect)

BASE_W, BASE_H = 960, 640
COVER_SIZE = 112
WICON_SIZE = 128
SPECTRUM_BARS = 64
# 보조 정보 왼쪽에 놓는 달의 지름입니다.
MOON_SIZE = 70
# 월페이퍼 글자입니다. **어느 시간대에나 흰색으로 씁니다.** 보조 디스플레이가
# 작아서 배경이 밝을 때 검은 글자로 바꾸면 대비를 맞추어도 읽기 어려웠습니다.
# 그래서 글자의 위계는 밝기가 아니라 크기와 굵기로만 나타냅니다. 셋 다
# ``sky.INK_LIMIT`` 위에서 4.5:1 로 읽히는 밝기이므로 더 어둡게 만들려면
# 그 한도와 ``sky.TIMES`` 를 함께 손보아야 합니다.
WALL_INK, WALL_INK_2, WALL_INK_3 = "#ffffff", "#f7f9fb", "#f2f5f9"
RAINBOW = tuple(sky._rgb(c) for c in (
    "#ff6f91", "#ffae68", "#ffe78b", "#a4ed9b", "#63dfd7",
    "#6dbdfc", "#a99aff", "#e28fdf"))

# 녹화 화면은 :mod:`component.recording_view` 가 같은 캔버스 위에 그립니다.
# 자리와 색은 그쪽에 모아 두었고, 여기에서는 화면을 갈아 끼우는 일만 맡습니다.
# Pretendard 숫자가 글자 상자 왼쪽에 두는 여백입니다. 글꼴 크기에 대한 비율이며,
# 시계를 날짜와 왼쪽 정렬할 때 이만큼 빼 줍니다.
BEARING = 0.061
# 시계 옆 초, 그리고 기온 옆 날씨 아이콘이 두는 사이 간격입니다. 글획 사이의
# 실제 거리를 뜻하므로 글꼴이 두는 여백(BEARING)을 뺀 자리에 놓습니다.
SEC_GAP, WICON_GAP = 22, 20

# 토요일과 일요일에만 색을 줍니다. 배경이 어느 시간대에나 어두우므로 밝은
# 쪽으로 물들인 값을 씁니다. 채도를 더 올리면 색은 뚜렷해지지만 흰 날짜와
# 나란히 놓았을 때 그 글자만 어두워 보여서 오히려 읽기 나빠집니다.
# 날짜는 36px 짜리 큰 글자이므로 대비 기준은 3:1 이며, 배경이 가장 밝을 때
# (``sky.INK_LIMIT``) 두 색 모두 3.1:1 이 넘습니다.
DOW_SAT, DOW_SUN = "#b0cdff", "#ffb9b9"

# 기온의 도 표시입니다. 영상과 영하를 색으로 가르되, 빨강·파랑처럼 맞세우지
# 않고 흰색에서 살짝 따뜻한 쪽과 찬 쪽으로만 옮깁니다.
DEG_WARM, DEG_COLD = "#ffdcc6", "#cfe2ff"

# 시·분 사이의 콜론입니다. 글꼴의 콜론은 점 지름이 글꼴 크기의 0.125 여서
# 숫자 획(0.083~0.089)보다 1.5배 굵고, 168px 에서는 시·분보다 콜론이 먼저
# 눈에 들어옵니다. 그래서 같은 자리에 점 두 개를 직접 그리고 지름만 획보다
# 가늘게 줄였습니다. 두 값 모두 글꼴 크기에 대한 비율이므로 시계를 키워도
# 가늘어 보이는 인상이 그대로 유지됩니다.
#
# 세로 자리는 글꼴을 따르지 않습니다. 활자에서 콜론은 베이스라인 쪽에 앉아
# 있어서, 168px 짜리 숫자 옆에 그대로 두면 숫자 획의 가운데보다 16px 남짓
# 내려가 한쪽으로 처져 보입니다. 그래서 숫자 획의 실제 가운데에 맞춥니다.
COLON_DOT, COLON_SPREAD = .070, .196

# 긴 곡 이름을 흘려 보내는 규칙입니다. 처음에서 잠깐 멈춰 아티스트와 곡
# 이름을 읽게 하고, 끝까지 흘린 뒤에도 잠깐 멈췄다가 처음으로 돌아갑니다.
MARQUEE_HOLD, MARQUEE_TAIL, MARQUEE_SPEED = 2.4, 1.6, 52.0

# 시계 글자 상자의 위에서 숫자 획의 위끝까지의 거리와, 숫자 획 자체의 높이입니다.
# 글꼴 크기에 대한 비율이며, Pretendard 숫자를 168px 로 그려서 실제로 재 보니
# 상자 높이 201 가운데 위쪽 40px 이 비어 있고 획은 122px 이었습니다. 숫자에는
# 디센더가 없어서 상자 아래쪽에도 39px 이 남습니다.
CLOCK_HEAD, CLOCK_CAP = 40 / 168, 122 / 168
# 오전·오후 글자와 시계 숫자의 머리 사이를 띄우는 거리입니다.
AMPM_GAP = 4

# 960x640 을 기준으로 잰 세로 자리입니다. 시간대 이름과 날짜는 맨 위에
# 고정하고, 그 아래의 시계와 날씨는 날짜 줄과 음악 영역 사이의 빈 자리에서
# 각각 위아래 가운데에 놓습니다. 그래서 시계와 날씨의 값은 :func:`_place`
# 가 실제로 잰 높이로 다시 잡으며, 여기 적은 값은 그 계산의 출발점입니다.
PHASE_Y, DATE_Y = 52, 96
CLOCK_Y, WEATHER_Y = 248, 206
DESC_Y, META_Y, META2_Y, MOON_Y = 288, 326, 358, 342

# 두 묶음에서 실제로 그려지는 부분이 차지하는 세로 범위입니다. 글자 상자가
# 아니라 획의 위아래 끝이며, 셋째 값은 그 위끝에서 기준 좌표(CLOCK_Y,
# WEATHER_Y)까지의 거리입니다. 가운데에 놓아야 하는 것은 상자가 아니라
# 눈에 보이는 부분이므로 이 값으로 자리를 잡습니다.
#
# 시계는 Pretendard 숫자를 168px 로 그려 실측했습니다. 글자 상자 높이는
# 201 이지만 숫자 획은 122(0.726배)뿐이고, 디센더 자리가 비어 있어 획의
# 가운데가 상자 가운데와 거의 같습니다. 초는 베이스라인을 맞추므로 이 범위
# 안에 들어옵니다. 날씨는 기온 위의 도시 이름에서 시작해 달의 아래끝까지입니다.
CLOCK_INK = (187.5, 309.5, 60.5)
WEATHER_INK = (120.5, 377.5, 85.5)

# 날씨 묶음만 빈 자리의 한가운데에서 이만큼 위로 올립니다. 도시 이름부터 달까지
# 아래로 길게 늘어서는 묶음이라, 자로 잰 가운데에 두면 눈에는 살짝 내려앉은
# 것처럼 보입니다. 사용자가 보고 정한 값입니다. 위로는 날짜 줄과의 사이가,
# 아래로는 소리 막대와의 사이가 좁아지므로 더 키우지 마십시오. 5px 일 때 위로
# 8px, 아래로 7.5px 이 남아 양쪽이 거의 균형을 이룹니다. 8px 을 넘기면 도시
# 이름이 날짜 줄과 같은 높이로 올라와 한 줄처럼 보입니다.
WEATHER_LIFT = 5


class WallpaperView:
    def __init__(self, parent, settings, width=BASE_W, height=BASE_H, actions=None):
        self.parent, self.settings = parent, dict(settings)
        self.width, self.height = width, height
        self.actions = actions or {}
        self.fps = max(12, min(40, int(settings.get("wallpaper_fps", 30))))
        self.period = round(1000 / self.fps)
        self.canvas = tk.Canvas(parent, width=width, height=height,
                                highlightthickness=0, bd=0, bg="#080c13")
        self.running, self._after_id, self._destroyed = False, None, False
        self.audio = self.nowplaying = self.weather = None
        self._bg_image = self._cover_image = self._wicon_image = None
        self._moon_image, self._moon_key = None, None
        self._moon_slot = None
        self._weather_icon_key = None
        self._weather_motion = ""
        self._bg_pixels = self._fade_source = self._fade_target = None
        self._fade_at = self._paint_at = 0
        self._palette = sky.blend_palette(_now_hour())
        self._sky_key, self._accent = "clear", None
        self._bake_key, self._wanted, self._future = None, None, None
        self._executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="wall-sky")
        self._baked_at = self._last_frame = self._data_at = 0
        self._levels = [0.] * BARS
        self._track_version = self._weather_version = -1
        self._last_second = None
        self._clock_blink_on = True
        self._clock_blink_ink = {}
        self._fonts = {}
        self._cover_data, self._cover_side = None, None
        self._track_text = (tr("고요한 순간"), tr("음악을 재생하면 이곳에 표시됩니다"))
        self._track_fade = None
        self._has_track = False
        # 긴 곡 이름을 흘려 보낼 때 쓰는 값입니다. ``_title_over`` 가 0 이면
        # 한 줄에 다 들어가므로 흘리지 않고 그대로 둡니다.
        self._title_over, self._title_at, self._title_off = 0.0, 0.0, None
        self._title_y = 0.0
        # 시계와 날씨를 가운데에 놓을 때 쓰는 값입니다. _place() 가 채웁니다.
        self._clock_y = float(CLOCK_Y)
        self._weather_shift = 0.0
        self._clock_box = (0.0, 0.0, 0.0, 0.0)
        self._controls_at, self._controls_visible, self._hovered = 0, False, None
        self._mode = "wall"
        self._rec_since = 0.0
        self._build()
        self._place()

    @property
    def scale_x(self):
        return self.width / BASE_W

    @property
    def scale_y(self):
        return self.height / BASE_H

    @property
    def scale(self):
        return min(self.scale_x, self.scale_y)

    @property
    def clock_24h(self):
        return bool(self.settings.get("clock_24h", True))

    def _font(self, key, size, families=WALL_UI_FAMILIES, weight="normal"):
        font = pick_font(self.parent, families, size, weight)
        self._fonts[key] = (font, size)
        return font

    def _text(self, font, color=INK, text="", anchor="w", tag="content"):
        return self.canvas.create_text(0, 0, anchor=anchor, font=font, fill=color,
                                       text=text, tags=tag)

    def _build(self):
        c = self.canvas
        self.bg_item = c.create_image(0, 0, anchor="nw")
        self.atmosphere = Atmosphere(c)
        self.bar_glows = [c.create_line(0, 0, 0, 0, capstyle="round", fill=INK_3)
                          for _ in range(SPECTRUM_BARS)]
        self.bar_items = [c.create_line(0, 0, 0, 0, capstyle="round", fill=INK_3)
                          for _ in range(SPECTRUM_BARS)]
        self.reflection_items = [c.create_line(0, 0, 0, 0, capstyle="round", fill=INK_3)
                                 for _ in range(SPECTRUM_BARS)]
        # 시간대 이름은 시계 위, 날짜보다 앞줄에 둡니다. 시계 아래에 두었을
        # 때는 작고 멀어서 읽히지 않았습니다. 글자 사이가 고른 글꼴을 써서
        # 기계 장치의 표시처럼 보이게 합니다.
        self.phase_item = self._text(self._font("phase", -20, WALL_MONO_FAMILIES),
                                     WALL_INK_3)
        # 날짜와 요일을 따로 그립니다. 토요일과 일요일에만 색을 주기 때문이고,
        # 년·월·일 사이와 같은 간격으로 요일을 붙일 수 있기 때문이기도 합니다.
        self.date_item = self._text(self._font("date", -36), WALL_INK_2)
        self.dow_item = self._text(self._fonts["date"][0], WALL_INK_2)
        # 12시간으로 볼 때만 나오는 오전·오후 표시입니다. 날짜와 시계 사이에
        # 작게 얹고, 가로로는 시와 분 사이의 콜론 쪽으로 붙입니다.
        self.ampm_item = self._text(self._font("ampm", -20, WALL_MONO_FAMILIES,
                                               weight="bold"),
                                    WALL_INK_2, anchor="sw")
        f_clock = self._font("clock", -168)
        self.clock_shadow = self._text(f_clock, "#080b12")
        self.clock_item = self._text(f_clock, WALL_INK)
        self.minute_shadow = self._text(f_clock, "#080b12")
        self.minute_item = self._text(f_clock, WALL_INK)
        self._clock_parts = ((self.clock_item, self.clock_shadow),
                             (self.minute_item, self.minute_shadow))
        # 콜론은 글꼴 대신 점 두 개로 그립니다. 168px 짜리 숫자 옆에서 글꼴의
        # 콜론은 점이 굵게 보여, 시와 분보다 콜론이 먼저 눈에 들어옵니다.
        self.colon_shadows = [c.create_oval(0, 0, 0, 0, outline="", fill="#080b12")
                              for _ in range(2)]
        self.colon_dots = [c.create_oval(0, 0, 0, 0, outline="", fill=WALL_INK)
                           for _ in range(2)]
        self.sec_item = self._text(self._font("sec", -30), WALL_INK_3)
        self._clock_blink_items = tuple(self.colon_dots) + tuple(self.colon_shadows)
        self._clock_blink_ink = {item: c.itemcget(item, "fill")
                                 for item in self._clock_blink_items}
        self.wicon_item = c.create_image(0, 0, anchor="center")
        # 날씨를 보는 곳입니다. 기온 위에 작게 얹고 오른쪽을 맞춰 둡니다.
        self.city_item = self._text(self._font("city", -22, WALL_MONO_FAMILIES),
                                    WALL_INK_3, anchor="e")
        self._city_text = str(self.settings.get("city") or "")
        # 도 표시는 숫자와 나누어 그립니다. 영상과 영하를 색으로 가르기
        # 위해서입니다. 숫자는 그 왼쪽에 오른쪽 맞춤으로 붙습니다.
        self.deg_item = self._text(self._font("temp", -94), DEG_WARM, "°", anchor="e")
        self.temp_item = self._text(self._fonts["temp"][0], WALL_INK, "—", anchor="e")
        self.desc_item = self._text(self._font("desc", -29), WALL_INK_2,
                                    tr("날씨 연결 중"), anchor="e")
        self.meta_item = self._text(self._font("meta", -24), WALL_INK_3, anchor="e")
        self.meta2_item = self._text(self._fonts["meta"][0], WALL_INK_3, anchor="e")
        self.weather_sparks = [c.create_oval(0, 0, 0, 0, outline="", fill="#adc9df",
                                            state="hidden") for _ in range(5)]
        # 오늘 달입니다. 구의 표면에 빛이 닿는 정도를 픽셀마다 계산해 구운
        # 그림이라 명암 경계가 부드럽고 바다 무늬도 들어 있습니다.
        self.moon_item = c.create_image(0, 0, anchor="center")
        # 커버를 못 받아도 음악 영역의 균형을 유지하는 레코드 문양.
        self.cover_mat = c.create_polygon(0, 0, 0, 0, fill="#121b25", outline="#2d3a48",
                                          smooth=True, splinesteps=24)
        self.record_items = [c.create_oval(0, 0, 0, 0, outline="#34414e")
                             for _ in range(5)]
        self.record_center = c.create_oval(0, 0, 0, 0, fill="#a7bcc8", outline="")
        self.cover_item = c.create_image(0, 0, anchor="nw")
        self.play_label = self._text(self._font("label", -14, WALL_MONO_FAMILIES),
                                     WALL_INK_3, "S O U N D   A T   R E S T")
        f_title = self._font("title", -46, weight="bold")
        self.title_shadow = self._text(f_title, "#080b12")
        self.title_item = self._text(f_title, WALL_INK)
        self.album_item = self._text(self._font("album", -24), WALL_INK_3)
        # 44px 클릭 영역. 아이콘과 안내는 포인터를 움직일 때만 나타납니다.
        self.control_items = {}
        f_control = self._font("control", -22, ("Segoe UI Symbol", "Segoe UI"))
        for key, glyph in (("settings", "⚙"), ("full", "⛶"), ("close", "×")):
            item = self._text(f_control, WALL_INK_2, glyph, anchor="center", tag="controls")
            self.control_items[key] = item
        # 흘러가는 곡 이름은 왼쪽에서 한 글자가 반쯤 걸친 채 사라집니다.
        # 캔버스에는 글자를 잘라 내는 기능이 없으므로, 앨범 커버를 곡 이름보다
        # 위에 올려 그 반 글자를 가리게 합니다.
        for item in (self.cover_mat, *self.record_items, self.record_center,
                     self.cover_item):
            c.tag_raise(item)
        # 녹화 화면은 따로 떼어 둔 켜가 같은 캔버스 위에 그립니다. 월페이퍼
        # 도형을 모두 만든 뒤에 세워야 배경 위, 안내 글 아래에 놓입니다.
        self.recording = RecordingLayer(c, self.parent)
        # 오른쪽 아래 버전은 두 화면에 모두 남으므로 어느 꼬리표도 달지 않습니다.
        self.status_ver = self._text(self._font("statusver", -16,
                                                WALL_MONO_FAMILIES), "#5a6478",
                                     text=version.label(), anchor="e")
        self._tag_wallonly()
        self.tooltip = self._text(self._font("tooltip", -13), WALL_INK_2,
                                  anchor="e", tag="controls")
        c.itemconfigure("controls", state="hidden")
        c.bind("<Motion>", self._motion)
        # 포인터가 창에 들어오거나 창이 앞으로 나오면 버튼을 드러냅니다.
        # ×도 설정·전체화면과 똑같이 다루므로 평소에는 보이지 않습니다.
        c.bind("<Enter>", self._motion)
        c.bind("<Leave>", lambda _e: self._show_controls(False))
        c.bind("<FocusIn>", lambda _e: self._wake_controls())
        self.parent.bind("<FocusIn>", lambda _e: self._wake_controls(), add="+")
        c.bind("<Button-1>", self._click)
        c.bind("<B1-Motion>", self._control_drag)
        c.bind("<ButtonRelease-1>", self._release)
        self._pressed_control = False
        self._pressed_clock = None

    def _tag_wallonly(self):
        """월페이퍼에서만 보이는 것들을 한데 묶어 둡니다."""
        c = self.canvas
        for item in (self.phase_item, self.date_item, self.dow_item,
                     self.ampm_item, self.clock_item,
                     self.clock_shadow,
                     self.minute_item, self.minute_shadow, self.sec_item, self.wicon_item,
                     self.city_item, self.temp_item, self.deg_item,
                     self.desc_item, self.meta_item,
                     self.meta2_item, self.moon_item, self.cover_mat,
                     self.record_center, self.cover_item, self.play_label,
                     self.title_item, self.title_shadow, self.album_item):
            c.addtag_withtag("wallonly", item)
        for group in (self.bar_items, self.bar_glows, self.reflection_items,
                      self.record_items, self.colon_dots, self.colon_shadows,
                      self.weather_sparks):
            for item in group:
                c.addtag_withtag("wallonly", item)

    def _place(self):
        c, sx, sy, s = self.canvas, self.scale_x, self.scale_y, self.scale
        for font, size in self._fonts.values():
            font.configure(size=min(-8, round(size * s)))
        # 가로가 넓어져도 이미지와 글자는 작은 배율을 따라갑니다.
        x, right = 60 * sx, self.width - 60 * sx
        self._cover_xy = (x, self.height - 48 * sy - COVER_SIZE * s)
        self._track_x = x + (COVER_SIZE + 30) * s
        self._track_width = max(1, right - self._track_x)
        self._bar_left, self._bar_right = x, right
        self._bar_y, self._bar_height = 453 * sy, 72 * s
        for group, width in ((self.bar_items, 4), (self.bar_glows, 8),
                             (self.reflection_items, 3)):
            for item in group:
                c.itemconfigure(item, width=max(1, width * s))
        # 구분선을 빼고 사이 간격만으로 나눕니다. 선이 차지하던 자리를
        # 시계가 가져갑니다.
        c.coords(self.phase_item, x, PHASE_Y * sy)
        self._place_date()
        # 시계와 날씨는 날짜 줄과 소리 막대 사이의 빈 자리에서 위아래 가운데에
        # 섭니다. 두 묶음의 가운데가 같은 높이에 놓이도록 각각 옮깁니다.
        band = self._band()
        self._clock_y = self._center_of(band, CLOCK_INK)
        weather_y = self._center_of(band, WEATHER_INK) - WEATHER_LIFT * s
        self._weather_shift = weather_y - WEATHER_Y * sy
        # 시계가 쓸 수 있는 폭은 가장 넓은 기온을 기준으로 고정해 둡니다.
        # 아이콘이 짧은 기온을 따라 오른쪽으로 당겨져도 시계 크기는 그대로입니다.
        self._weather_limit_x = right - 268 * s
        self._weather_center = (self._weather_limit_x, weather_y)
        self._place_clock()
        # 도시 이름의 자리와 폭은 아이콘이 자리를 잡은 뒤에 _fit_city() 가
        # 기온의 실제 크기를 보고 맞춥니다.
        c.coords(self.deg_item, right, weather_y)
        self._place_temp()
        self._place_weather_icon()
        c.coords(self.desc_item, right, DESC_Y * sy + self._weather_shift)
        c.coords(self.meta_item, right, META_Y * sy + self._weather_shift)
        c.coords(self.meta2_item, right, META2_Y * sy + self._weather_shift)
        cx, cy = self._cover_xy
        side = COVER_SIZE * s
        c.coords(self.cover_mat, *round_rect(cx, cy, side, side, 15 * s))
        c.coords(self.cover_item, cx, cy)
        for i, item in enumerate(self.record_items):
            r = (39 - i * 6) * s
            c.coords(item, cx + side / 2 - r, cy + side / 2 - r,
                     cx + side / 2 + r, cy + side / 2 + r)
        c.coords(self.record_center, cx + side / 2 - 4 * s, cy + side / 2 - 4 * s,
                 cx + side / 2 + 4 * s, cy + side / 2 + 4 * s)
        c.coords(self.play_label, self._track_x, cy + 6 * s)
        self._title_y = cy + 50 * s
        c.coords(self.title_item, self._track_x, self._title_y)
        c.coords(self.title_shadow, self._track_x + s, self._title_y + s)
        c.coords(self.album_item, self._track_x, cy + 96 * s)
        for i, key in enumerate(("settings", "full", "close")):
            c.coords(self.control_items[key], right - (88 - 44 * i) * s, 53 * sy)
        c.coords(self.tooltip, right, 85 * sy)
        self._place_moon()
        self._place_recording()
        self._fit_track()

    def _band(self):
        """시계와 날씨가 놓이는 세로 범위입니다.

        위는 날짜 줄의 아래끝, 아래는 소리 막대가 가장 높이 올라갔을 때의
        꼭대기입니다. 막대는 화면 전체 폭에 걸쳐 지평선에서 솟아오르므로,
        이 선 아래로 내려보내면 큰 소리에서 글자와 겹칩니다.
        """
        sy, s = self.scale_y, self.scale
        top = (DATE_Y * sy + self._fonts["date"][0].metrics("linespace") / 2
               + 8 * s)
        bottom = sky.horizon_y(.5) * self.height - self._bar_height - 2 * s
        return top, bottom

    def _center_of(self, band, ink):
        """글자 상자의 가운데 좌표를 돌려줍니다.

        ``ink`` 는 그 묶음에서 실제로 그려지는 부분이 기준 좌표에서 차지하는
        위아래 끝입니다. 숫자에는 디센더가 없고 날씨는 아이콘과 보조 정보가
        아래로 길어서, 글자 상자를 그대로 가운데에 두면 눈에는 한쪽으로
        치우쳐 보입니다. 그래서 그려지는 부분을 가운데에 맞추고, 그 자리에
        상자를 끼워 넣습니다.
        """
        s = self.scale
        top, bottom = band
        # 글자와 아이콘은 가로·세로 배율 가운데 작은 쪽으로 커지므로 묶음의
        # 높이도 그 배율을 따릅니다. 놓는 자리만 창의 실제 높이를 씁니다.
        height = (ink[1] - ink[0]) * s
        room = bottom - top
        # 묶음이 빈 자리보다 크면 가운데를 맞출 수 없습니다. 그때는 아래를
        # 먼저 지킵니다. 위로 넘치는 쪽은 날짜 줄과의 사이 여백이 받아 주지만,
        # 아래로 넘치면 소리 막대가 글자를 지나가기 때문입니다.
        start = (bottom - height if height >= room
                 else top + (room - height) / 2)
        return start + ink[2] * s

    def _place_date(self):
        """날짜와 요일을 나란히 놓습니다.

        사이는 년·월·일 사이와 같은 간격으로 띄웁니다. 예전에는 공백 세 칸을
        넣어 요일 앞만 눈에 띄게 벌어져 있었습니다. 영어는 요일이 날짜 앞에
        오므로 둘의 차례를 바꿉니다.
        """
        c, sy = self.canvas, self.scale_y
        font = self._fonts["date"][0]
        x, y = 60 * self.scale_x, DATE_Y * sy
        gap = font.measure(" ")
        first, second = ((self.dow_item, self.date_item) if weekday_leads()
                         else (self.date_item, self.dow_item))
        c.coords(first, x, y)
        c.coords(second, x + font.measure(c.itemcget(first, "text") or "") + gap, y)

    def _place_temp(self):
        """도 표시 왼쪽에 기온 숫자를 붙입니다.

        영상과 영하를 도 표시의 색으로 가르기 때문에 둘을 따로 그립니다.
        오른쪽 끝은 도 표시가 맡고, 숫자는 그 왼쪽에 오른쪽 맞춤으로 섭니다.
        """
        right = self.width - 60 * self.scale_x
        font = self._fonts["temp"][0]
        deg = self.canvas.itemcget(self.deg_item, "text") or "°"
        self.canvas.coords(self.temp_item, right - font.measure(deg),
                           self._weather_center[1])

    def _temp_width(self):
        """기온 숫자와 도 표시를 합친 폭입니다."""
        font = self._fonts["temp"][0]
        return (font.measure(self.canvas.itemcget(self.temp_item, "text") or "—")
                + font.measure(self.canvas.itemcget(self.deg_item, "text") or "°"))

    def _place_clock(self):
        """시계를 날짜와 왼쪽 정렬하고, 초는 그 오른쪽에 베이스라인을 맞춰 둡니다."""
        c, s = self.canvas, self.scale
        font, base = self._fonts["clock"]
        sec_font = self._fonts["sec"][0]
        size = max(8, round(-base * s))
        # 큰 Pretendard 숫자의 왼쪽 글꼴 여백을 빼 날짜의 글획과 맞춥니다.
        # 이 여백은 글꼴 크기에 비례하므로 고정값으로 두면 시계 크기를 바꿀 때
        # 날짜와의 왼쪽 정렬이 어긋납니다.
        left = 60 * self.scale_x - size * BEARING
        limit = self._weather_limit_x - WICON_SIZE * s / 2 - left - 12 * s
        # 초가 시계 오른쪽에 서므로 그 폭과 사이 간격까지 넣고 줄여야 날씨
        # 아이콘과 부딪히지 않습니다. 시각은 자릿수마다 폭이 다르므로 여기서는
        # 가장 넓은 두 자리를 기준으로 잡아 어떤 시각에도 넘치지 않게 합니다.
        sec_width = max(sec_font.measure("%02d" % n) for n in range(60))
        while True:
            font.configure(size=-size)
            hour_width = max(font.measure("%02d" % n) for n in range(24))
            minute_width = max(font.measure("%02d" % n) for n in range(60))
            colon_width = round(font.measure(":") * .8)
            width = hour_width + colon_width + minute_width
            # 12시간으로 보면 시가 한 자리로 줄기도 하지만, 자리를 그때그때
            # 바꾸면 시각이 넘어갈 때마다 시계가 흔들립니다. 언제나 두 자리의
            # 가장 넓은 폭을 기준으로 잡습니다.
            # 큰 숫자가 글자 상자 오른쪽에 두는 여백만큼 당겨야 눈에 보이는
            # 사이 간격이 SEC_GAP 과 같아집니다.
            sec_gap = SEC_GAP * s - size * BEARING
            if width + sec_gap + sec_width <= limit or size <= 8:
                break
            size -= 1
        self._clock_left, self._clock_colon_width = left, colon_width
        # 초는 위에서 잰 최대 폭이 아니라 실제로 그려진 분의 끝에 붙습니다.
        # 최대 폭에 맞추면 좁은 분(19 등)에서 초만 멀리 떨어져 보입니다.
        self._sec_gap = sec_gap
        # 초의 베이스라인을 시계의 베이스라인과 맞춥니다. 두 글자가 같은 줄에
        # 앉아 보이게 하려면 글자 상자 가운데가 아니라 베이스라인을 맞춰야 합니다.
        baseline = (self._clock_y - font.metrics("linespace") / 2
                    + font.metrics("ascent"))
        self._sec_y = (baseline + sec_font.metrics("linespace") / 2
                       - sec_font.metrics("ascent"))
        c.itemconfigure(self.sec_item, anchor="w")
        # 시계를 눌러 12시간과 24시간을 오갈 수 있게, 글자가 차지하는 자리를
        # 적어 둡니다. 세로는 실제로 그려지는 높이를 그대로 씁니다.
        self._clock_box = (left, self._clock_y - font.metrics("linespace") / 2,
                           left + width, self._clock_y + font.metrics("linespace") / 2)
        self._position_clock()

    def _position_clock(self):
        c, s = self.canvas, self.scale
        font = self._fonts["clock"][0]
        left, colon_width = self._clock_left, self._clock_colon_width
        size = abs(font.cget("size"))
        y = self._clock_y
        hour_width = font.measure(c.itemcget(self.clock_item, "text") or "00")
        hour_end = left + hour_width
        for (item, shadow), x in zip(self._clock_parts,
                                     (left, hour_end + colon_width)):
            c.coords(item, x, y)
            c.coords(shadow, x + s, y + 2 * s)
        # 점 두 개를 숫자 높이의 시각적 가운데에 세로로 나란히 찍습니다.
        # 글꼴의 콜론을 그대로 쓰면 이만한 크기에서 점이 굵게 보입니다.
        radius = max(1.0, size * COLON_DOT / 2)
        # 숫자 획의 위아래 가운데입니다. 글자 상자의 가운데가 아니라 실제로
        # 그려지는 부분을 기준으로 삼아야 두 점이 시·분의 한복판에 섭니다.
        middle = (y - font.metrics("linespace") / 2
                  + size * (CLOCK_HEAD + CLOCK_CAP / 2))
        cx = hour_end + colon_width / 2
        for i, (dot, shadow) in enumerate(zip(self.colon_dots, self.colon_shadows)):
            cy = middle + (i * 2 - 1) * size * COLON_SPREAD
            c.coords(dot, cx - radius, cy - radius, cx + radius, cy + radius)
            c.coords(shadow, cx - radius + s, cy - radius + 2 * s,
                     cx + radius + s, cy + radius + 2 * s)
        minute_end = (hour_end + colon_width
                      + font.measure(c.itemcget(self.minute_item, "text") or "00"))
        c.coords(self.sec_item, minute_end + self._sec_gap, self._sec_y)
        self._place_ampm()

    def _place_ampm(self):
        """오전·오후를 시계의 머리 바로 위에 왼쪽을 맞춰 붙입니다.

        시각을 읽는 눈이 거의 움직이지 않도록, 시 숫자의 왼쪽 획과 세로줄을
        맞추고 숫자의 꼭대기 가까이에 둡니다. 12시간으로 볼 때만 보입니다.
        """
        c, s = self.canvas, self.scale
        font = self._fonts["clock"][0]
        # 시계 숫자 획의 위끝입니다. 글자 상자 위에서 CLOCK_HEAD 만큼 내려온
        # 자리이며, Pretendard 숫자를 실제로 그려서 잰 비율입니다.
        head = (self._clock_y - font.metrics("linespace") / 2
                + abs(font.cget("size")) * CLOCK_HEAD)
        c.coords(self.ampm_item, 60 * self.scale_x, head - AMPM_GAP * s)

    def _set_ampm(self, hour):
        """12시간으로 볼 때만 오전·오후를 적습니다."""
        text = "" if self.clock_24h else ("AM" if hour < 12 else "PM")
        self.canvas.itemconfigure(self.ampm_item, text=text)

    def _place_weather_icon(self):
        """기온 글자 폭을 재서 날씨 아이콘을 그 왼쪽에 붙입니다.

        기온은 자릿수와 부호에 따라 폭이 크게 달라지므로 아이콘을 고정 좌표에
        두면 짧은 기온에서 사이가 벌어집니다. 달이 보조 정보 두 줄을 실제로
        재서 따라붙는 것과 같은 방식입니다. 왼쪽으로는 ``_weather_limit_x``
        보다 더 가지 않으므로 시계와 부딪히지 않습니다.
        """
        s = self.scale
        right = self.width - 60 * self.scale_x
        font = self._fonts["temp"][0]
        # 기온 숫자가 글자 상자 왼쪽에 두는 여백만큼 더 당겨야 글획 사이가
        # 눈으로 보는 간격과 같아집니다.
        gap = WICON_GAP * s - abs(font.cget("size")) * BEARING
        x = right - self._temp_width() - gap - WICON_SIZE * s / 2
        self._weather_center = (max(self._weather_limit_x, x),
                                self._weather_center[1])
        self.canvas.coords(self.wicon_item, *self._weather_center)
        self._fit_city()

    def _fit_city(self):
        """도시 이름을 아이콘 오른쪽에서 기온 끝까지의 폭에 맞춥니다.

        아이콘은 기온 폭을 따라 좌우로 움직이므로 도시 이름의 자리도 그에
        맞춰 달라집니다. 이렇게 해야 이름이 길어도 아이콘 위로 넘어가지
        않고, 기온과 오른쪽이 가지런히 맞습니다.
        """
        s = self.scale
        right = self.width - 60 * self.scale_x
        room = right - (self._weather_center[0] + WICON_SIZE * s / 2) - 8 * s
        font = self._fonts["city"][0]
        self.canvas.itemconfigure(self.city_item, text=fit_text(
            self._city_text, font, int(max(40 * s, room))))
        # 기온은 글자가 길면 스스로 작아지므로 그 실제 높이를 재서 바로 위에
        # 붙입니다. 고정 좌표로 두면 기온에 따라 간격이 들쭉날쭉해집니다.
        top = (self._weather_center[1]
               - self._fonts["temp"][0].metrics("linespace") / 2)
        self.canvas.coords(self.city_item, right,
                           top - 6 * s - font.metrics("linespace") / 2)

    def _place_recording(self):
        """녹화 켜에 지금 창 크기를 알려 주고, 두 화면이 함께 쓰는 것만 놓습니다."""
        self.recording.place(self.width, self.scale_x, self.scale_y, self.scale)
        self.canvas.coords(self.status_ver, self.width - 60 * self.scale_x,
                           STATUS_Y * self.scale_y)

    # ------------------------------------------------------------ 화면 갈아 끼우기

    @property
    def mode(self):
        return self._mode

    def set_mode(self, mode):
        """``wall``과 ``rec`` 가운데 하나로 바꿉니다.

        배경과 지평선은 그대로 두고 그 위의 내용만 갈아 끼웁니다. 캔버스를
        떠나지 않으므로 하늘을 다시 굽지 않고 전환이 이어집니다.
        """
        if mode not in ("wall", "rec") or mode == self._mode:
            return
        self._mode = mode
        c = self.canvas
        wall = (mode == "wall")
        c.itemconfigure("wallonly", state="normal" if wall else "hidden")
        c.itemconfigure("reconly", state="hidden" if wall else "normal")
        # 별·비·눈은 월페이퍼에서만 움직입니다. 녹화 중에는 쉬게 둡니다.
        c.itemconfigure("atmosphere", state="hidden")
        if wall:
            # ``wallonly`` 가 방금 모두 되살렸으므로, 커버가 있을 때 감춰 두던
            # 받침을 다시 감춥니다.
            self._show_cover_backdrop()
            if self._bg_pixels is not None:
                self.atmosphere.configure(self.width, self.height, self._palette,
                                          self._sky_key, self._bg_pixels,
                                          time.perf_counter())
        else:
            self.recording.paint()
        self._bake_sky()

    def show_recording(self, folder, elapsed, size, rate, growth, filename):
        """녹화 중일 때 채웁니다. 값은 이미 다듬은 문자열입니다."""
        self.recording.show(folder, elapsed, size, rate, growth, filename)

    def set_log(self, rows):
        """이벤트 로그입니다. rows 는 (시각, 종류, 내용) 입니다."""
        self.recording.set_log(rows)

    def set_status(self, text, label=""):
        """맨 아래 한 줄입니다.

        ``label`` 은 오른쪽 끝에 적는 버전 문구이며 두 화면에 모두 남습니다.
        이름을 ``version`` 으로 두면 모듈 :mod:`component.version` 을 가리므로
        쓰지 않습니다.
        """
        self.recording.set_status(text)
        self.canvas.itemconfigure(self.status_ver, text=label)

    def set_sources(self, audio=None, nowplaying=None, weather=None):
        """자료를 대는 스레드를 갈아 끼웁니다.

        녹화 중에는 소리와 음악, 날씨 조회를 멈추므로 모두 None 이 들어옵니다.
        새 스레드로 바뀌면 판을 다시 읽도록 버전을 되돌립니다.
        """
        self.audio, self.nowplaying, self.weather = audio, nowplaying, weather
        self._track_version = self._weather_version = -1
        self._data_at = 0
        if audio is None:
            self._levels = [0.] * BARS

    def start(self, audio=None, nowplaying=None, weather=None):
        if self._destroyed:
            return
        if self.running:
            return
        self.audio, self.nowplaying, self.weather = audio, nowplaying, weather
        # 제공자 인스턴스가 녹화 전환마다 바뀌므로 버전도 다시 읽습니다.
        self._track_version = self._weather_version = -1
        self._levels = [0.] * BARS
        self._last_second = None
        self._data_at = 0
        self.running = True
        self.canvas.pack(fill="both", expand=True)
        self._last_frame = time.perf_counter()
        self._apply_track(force=True)
        self._apply_weather(force=True)
        self._bake_sky()
        self._tick()

    def stop(self):
        self.running = False
        if self._after_id is not None:
            try:
                self.parent.after_cancel(self._after_id)
            except tk.TclError:
                pass
            self._after_id = None
        self._show_controls(False)
        self.canvas.pack_forget()
        self.audio = self.nowplaying = self.weather = None

    def destroy(self):
        if self._destroyed:
            return
        self.stop()
        self._destroyed = True
        self._executor.shutdown(wait=False, cancel_futures=True)
        for photo in (self._bg_image, self._cover_image, self._wicon_image,
                      self._moon_image):
            _drop_image(self.parent, photo)
        self._bg_image = self._cover_image = self._wicon_image = None
        self._moon_image, self._moon_key = None, None
        self._moon_slot = None
        self._bg_pixels = self._fade_source = self._fade_target = None
        self._cover_data = self._wanted = self._future = None
        self._cover_side = None
        self.canvas.destroy()

    def resize(self, width, height):
        width, height = max(1, int(width)), max(1, int(height))
        if (width, height) == (self.width, self.height):
            return
        self.width, self.height = width, height
        self.canvas.configure(width=width, height=height)
        self._place()
        if self.running:
            self._set_cover(self._cover_data)
            self._apply_weather(force=True)
            self._bake_sky(force=True)

    def _bake_sky(self, force=False):
        if not self.running:
            return
        now = time.perf_counter()
        palette = sky.blend_palette(_now_hour())
        palette["recording"] = self._mode == "rec"
        key = (self.width, self.height, tuple(palette["sky"]), palette["glow"],
               self._sky_key, self._accent, palette["season"],
               round(palette["light"], 4), round(palette["veil"], 4), self._mode)
        self._baked_at = now
        if not force and key == self._bake_key:
            return
        self._bake_key = key
        self._wanted = (key, palette, self.width, self.height,
                        self._accent, self._sky_key)
        self._submit_sky()

    def _submit_sky(self):
        if self._future is not None or self._wanted is None:
            return
        key, palette, width, height, accent, group = self._wanted
        self._future = (key, palette, self._executor.submit(
            sky.render, width, height, palette, accent, group))

    def _poll_sky(self, now):
        if self._future is not None and self._future[2].done():
            key, palette, future = self._future
            self._future = None
            try:
                pixels = future.result()
            except Exception as exc:
                log("[월페이퍼] 배경을 만들지 못했습니다: %s" % exc)
                pixels = None
                # 열쇠를 비워 두어야 같은 장면이라도 다음 차례에 다시 굽습니다.
                # 그대로 두면 _bake_sky() 가 같은 열쇠에서 일찍 물러납니다.
                self._bake_key = None
            if key == self._bake_key and pixels is not None:
                self._palette = palette
                self.canvas.itemconfigure(self.phase_item, text=palette["label"])
                self._fade_source, self._fade_target = self._bg_pixels, pixels
                self._fade_at, self._paint_at = now, 0
                self.atmosphere.configure(self.width, self.height, palette,
                                          self._sky_key, pixels, now)
            elif key != self._bake_key:
                self._submit_sky()
        if self._fade_target is None:
            return
        # 대형 화면에서는 전체 화면 이미지 교체 빈도를 줄입니다.
        interval = .14 if self.width * self.height <= 2200000 else .32
        if now - self._paint_at < interval:
            return
        self._paint_at = now
        t = min(1, (now - self._fade_at) / 1.8) if self._fade_source else 1
        eased = t * t * (3 - 2 * t)
        pixels = (sky.interpolate(self._fade_source, self._fade_target, eased)
                  if t < 1 else self._fade_target)
        ppm = imaging.upscale_rgb(pixels, sky.SMALL_W, sky.SMALL_H,
                                  self.width, self.height)
        if ppm is not None:
            new = tk.PhotoImage(master=self.parent, data=ppm, format="ppm")
            old, self._bg_image = self._bg_image, new
            self.canvas.itemconfigure(self.bg_item, image=new)
            _drop_image(self.parent, old)
            self._bg_pixels = pixels
            self.atmosphere.pixels = pixels
            self._paint_spectrum()
        if t >= 1:
            self._fade_source = self._fade_target = None

    def _paint_spectrum(self):
        for i, (bar, glow, reflection) in enumerate(zip(
                self.bar_items, self.bar_glows, self.reflection_items)):
            x = self._bar_left + (self._bar_right - self._bar_left) * i / (SPECTRUM_BARS - 1)
            ground = sky.sample(self._bg_pixels, x / self.width, sky.horizon_y(x / self.width))
            pos = i / (SPECTRUM_BARS - 1) * (len(RAINBOW) - 1)
            stop = min(len(RAINBOW) - 2, int(pos))
            tint = sky.mix(RAINBOW[stop], RAINBOW[stop + 1], pos - stop)
            self.canvas.itemconfigure(bar, fill=sky.to_hex(tint))
            self.canvas.itemconfigure(glow, fill=sky.to_hex(sky.mix(ground, tint, .22)))
            self.canvas.itemconfigure(reflection, fill=sky.to_hex(sky.mix(ground, tint, .32)))

    def _update_bars(self, now, dt):
        levels = self.audio.levels if self.audio else (0.,) * BARS
        for i in range(BARS):
            target = max(0, min(1, levels[i]))
            speed = 21 if target > self._levels[i] else 6
            self._levels[i] += (target - self._levels[i]) * (1 - math.exp(-speed * dt))
        c, s = self.canvas, self.scale
        for j, (bar, glow, reflection) in enumerate(zip(
                self.bar_items, self.bar_glows, self.reflection_items)):
            pos = j * (BARS - 1) / (SPECTRUM_BARS - 1)
            i, f = min(BARS - 2, int(pos)), pos - min(BARS - 2, int(pos))
            level = self._levels[i] * (1 - f) + self._levels[i + 1] * f
            edge = math.sin(math.pi * (j + 1) / (SPECTRUM_BARS + 1)) ** .45
            height = level ** .72 * self._bar_height * edge
            x = self._bar_left + (self._bar_right - self._bar_left) * j / (SPECTRUM_BARS - 1)
            baseline = sky.horizon_y(x / self.width) * self.height
            if height < .3:
                c.coords(bar, -10, -10, -10, -10)
                c.coords(glow, -10, -10, -10, -10)
                c.coords(reflection, -10, -10, -10, -10)
                continue
            c.coords(bar, x, baseline - height, x, baseline)
            c.coords(glow, x, baseline - height, x, baseline)
            c.coords(reflection, x, baseline + 6 * s, x, baseline + 6 * s + height * .17)

    def _tick(self):
        self._after_id = None
        if not self.running:
            return
        now = time.perf_counter()
        dt = min(.15, max(.001, now - self._last_frame))
        self._last_frame = now
        try:
            if self._mode != "wall":
                # 녹화 화면에서는 표시등 맥박과 하늘만 돌립니다.
                self.recording.pulse(now)
                self._poll_sky(now)
                if now - self._baked_at > 30:
                    self._bake_sky()
                self._after_id = self.parent.after(self.period, self._tick)
                return
            self._update_bars(now, dt)
            self.atmosphere.update(now)
            self._animate_weather(now)
            self._update_clock()
            if now - self._data_at >= .5:
                self._data_at = now
                self._apply_track()
                self._apply_weather()
            if now - self._baked_at > 30:
                self._bake_sky()
            self._poll_sky(now)
            self._animate_track(now)
            self._animate_title(now)
            if self._controls_visible and now - self._controls_at > 2.8 and self._hovered is None:
                self._show_controls(False)
        except Exception as exc:
            log("[월페이퍼] 그리다가 걸렸습니다: %s" % exc)
        elapsed = (time.perf_counter() - now) * 1000
        self._after_id = self.parent.after(max(1, self.period - round(elapsed)), self._tick)

    def _update_clock(self):
        timestamp = time.time()
        now = time.localtime(timestamp)
        self._blink_clock(timestamp % 1 < .5)
        stamp = (now.tm_year, now.tm_yday, now.tm_hour, now.tm_min, now.tm_sec)
        if stamp == self._last_second:
            return
        minute_changed = self._last_second is None or stamp[:-1] != self._last_second[:-1]
        self._last_second = stamp
        if minute_changed:
            self._set_clock_time(now.tm_hour, now.tm_min)
            self._set_date(now)
            # 자정이나 정오를 지났으면 달을 다시 그립니다.
            slot = _moon_slot(now)
            if slot != self._moon_slot:
                self._moon_slot = slot
                self._place_moon()
        self.canvas.itemconfigure(self.sec_item, text="%02d" % now.tm_sec)

    def apply_settings(self, settings):
        """환경설정에서 바뀐 값을 켜 둔 채로 갈아 끼웁니다.

        예전에는 이 자리가 없어서, 도시를 바꾸면 좌표를 따라간 기온만 새 도시
        것으로 바뀌고 화면에 적히는 이름은 옛 도시가 그대로 남았습니다. 본 창이
        같은 인스턴스를 껐다 켤 뿐 새로 만들지는 않기 때문입니다.
        """
        self.settings = dict(settings)
        self.fps = max(12, min(40, int(settings.get("wallpaper_fps", 30))))
        self.period = round(1000 / self.fps)
        city = str(settings.get("city") or "")
        if city != self._city_text:
            self._city_text = city
            self._fit_city()
        # 24시간·12시간 표시도 설정에 들어 있으므로 그 자리에서 다시 적습니다.
        now = time.localtime()
        self._set_clock_time(now.tm_hour, now.tm_min)

    def refresh_language(self):
        """환경설정에서 쓰는 말을 바꾸면 적어 둔 글자를 새 말로 갈아 끼웁니다.

        시각과 날씨, 곡은 다음 갱신을 기다리지 않고 곧바로 다시 적습니다.
        기다리게 두면 날씨는 한 시간 뒤에야 바뀌기 때문입니다.
        """
        self._last_second = None
        self._track_version = self._weather_version = -1
        self._update_clock()
        self._apply_track(force=True)
        self._apply_weather(force=True)
        self.canvas.itemconfigure(self.tooltip, text="")

    def _set_date(self, now):
        """날짜와 요일을 적습니다. 토요일과 일요일에만 색을 줍니다."""
        c = self.canvas
        c.itemconfigure(self.date_item, text=date_text(now))
        ink = (DOW_SAT if now.tm_wday == 5 else
               DOW_SUN if now.tm_wday == 6 else WALL_INK_2)
        c.itemconfigure(self.dow_item, text=weekday(now.tm_wday), fill=ink)
        self._place_date()

    def _set_clock_time(self, hour, minute):
        shown = hour if self.clock_24h else (hour % 12 or 12)
        for items, text in ((self._clock_parts[0], "%02d" % shown),
                            (self._clock_parts[1], "%02d" % minute)):
            for item in items:
                self.canvas.itemconfigure(item, text=text)
        self._set_ampm(hour)
        self._position_clock()

    def toggle_clock(self):
        """시계를 누르면 24시간과 12시간을 오갑니다.

        고른 값은 ``config.json`` 에 남습니다. 저장은 본 창이 맡습니다.
        """
        self.settings["clock_24h"] = not self.clock_24h
        now = time.localtime()
        self._set_clock_time(now.tm_hour, now.tm_min)
        action = self.actions.get("clock")
        if action:
            action(self.clock_24h)

    def _blink_clock(self, visible, force=False):
        if not force and visible == self._clock_blink_on:
            return
        self._clock_blink_on = visible
        # fill만 비우면 좌표와 wall/rec 표시 상태가 그대로 유지됩니다.
        for item in self._clock_blink_items:
            self.canvas.itemconfigure(item, fill=self._clock_blink_ink[item] if visible else "")

    def _fit_track(self):
        """곡 이름과 앨범을 자리에 맞춥니다.

        앨범은 길면 뒤를 줄입니다. 아티스트와 곡 이름은 줄이지 않고 흘려
        보냅니다. 말줄임표로 자르면 어느 곡인지 끝내 알 수 없기 때문입니다.
        """
        self.canvas.itemconfigure(self.album_item, text=fit_text(
            self._track_text[1], self._fonts["album"][0], int(self._track_width)))
        font = self._fonts["title"][0]
        raw = self._track_text[0]
        self._title_over = max(0, font.measure(raw) - int(self._track_width))
        self._title_at, self._title_off = time.perf_counter(), None
        self._draw_title(0)

    def _draw_title(self, off):
        """곡 이름을 왼쪽으로 ``off`` 픽셀만큼 민 모습으로 그립니다.

        캔버스에는 글자를 잘라 내는 기능이 없으므로, 왼쪽으로 벗어나는 글자를
        문자열에서 덜어 내고 남은 어긋남만큼만 좌표를 당깁니다. 그래서 글자
        단위로 덜컹거리지 않고 픽셀 단위로 흘러갑니다.
        """
        if off == self._title_off:
            return
        self._title_off = off
        c, font = self.canvas, self._fonts["title"][0]
        raw = self._track_text[0]
        width = int(self._track_width)
        if self._title_over <= 0:
            text, shift = raw, 0
        else:
            eaten = _cut_to(raw, font, off)
            shift = off - font.measure(raw[:eaten])
            rest = raw[eaten:]
            # 오른쪽 끝에서 반쯤 걸친 글자도 그려야 흘러가는 것으로 보입니다.
            # 그만큼 넘치는 자리는 화면 오른쪽 여백이 받아 줍니다.
            text = rest[:_cut_to(rest, font, width + shift) + 1]
        x = self._track_x - shift
        s = self.scale
        for item, dx, dy in ((self.title_shadow, s, s), (self.title_item, 0, 0)):
            c.itemconfigure(item, text=text)
            c.coords(item, x + dx, self._title_y + dy)

    def _animate_title(self, now):
        """긴 곡 이름을 처음에 잠깐 멈췄다가 끝까지 흘리고 되돌립니다."""
        span = self._title_over
        if span <= 0:
            return
        cycle = MARQUEE_HOLD + span / MARQUEE_SPEED + MARQUEE_TAIL
        t = (now - self._title_at) % cycle
        if t < MARQUEE_HOLD:
            off = 0
        elif t < cycle - MARQUEE_TAIL:
            off = round((t - MARQUEE_HOLD) * MARQUEE_SPEED)
        else:
            off = span
        self._draw_title(min(span, off))

    def _apply_track(self, force=False):
        provider = self.nowplaying
        # 이름을 ``version`` 으로 두면 모듈 :mod:`component.version` 을 가립니다.
        revision = provider.version if provider else 0
        if not force and revision == self._track_version:
            return
        first = self._track_version == -1
        self._track_version = revision
        track = provider.track if provider else None
        playing = bool(track and track.is_playing())
        # 아티스트와 곡을 한 줄로 붙여 오른쪽 빈자리를 줄입니다.
        if playing:
            head = ("%s - %s" % (track.artist, track.title)
                    if track.artist else track.title)
            text = (head, track.album or "")
        else:
            text = (tr("고요한 순간"), tr("음악을 재생하면 이곳에 표시됩니다"))
        changed = text != self._track_text
        self._track_text, self._has_track = text, playing
        self._fit_track()
        self.canvas.itemconfigure(self.play_label,
                                  text="N O W   P L A Y I N G" if playing else "S O U N D   A T   R E S T")
        self._set_cover(track.cover if playing else None)
        accent = track.accent if playing else None
        if accent != self._accent:
            self._accent = accent
            self._bake_sky()
        if changed and not first and not force:
            self._track_fade = time.perf_counter()

    def _animate_track(self, now):
        if self._track_fade is None:
            return
        t = min(1, (now - self._track_fade) / .7)
        for item, color in ((self.title_item, WALL_INK), (self.album_item, WALL_INK_3)):
            self.canvas.itemconfigure(item, fill=sky.to_hex(
                sky.mix((81, 94, 108), sky._rgb(color), .25 + .75 * t)))
        if t >= 1:
            self._track_fade = None

    def _set_cover(self, data):
        side = max(1, round(COVER_SIZE * self.scale))
        # 같은 곡에서 날씨·창 위치만 바뀌면 JPEG를 다시 풀지 않습니다.
        # 주소(``id``)가 아니라 그림 객체 자체를 붙들고 견줍니다. 주소는 파이썬이
        # 버린 자리를 다시 쓰면 다른 그림에도 같은 값이 나올 수 있습니다.
        if data is self._cover_data and side == self._cover_side:
            return
        self._cover_data, self._cover_side = data, side
        png = imaging.rounded_cover_png(data, side, round(14 * self.scale)) if data else None
        new = tk.PhotoImage(master=self.parent, data=png, format="png") if png else None
        old, self._cover_image = self._cover_image, new
        self.canvas.itemconfigure(self.cover_item, image=new or "")
        _drop_image(self.parent, old)
        self._show_cover_backdrop()

    def _show_cover_backdrop(self):
        """커버가 없을 때만 받침과 레코드 문양을 보여 줍니다.

        받침은 커버를 받지 못했을 때 음악 자리가 비어 보이지 않게 하는 것인데,
        커버가 올라오면 그 둥근 모서리 바깥으로 받침의 어두운 색이 비쳐 네
        귀퉁이에 커버와 어울리지 않는 검은 자국이 남습니다. 커버 그림은 이미
        제 모서리를 둥글게 굽고 있으므로 뒤를 받쳐 줄 이유가 없습니다.
        """
        # 녹화 화면에서는 ``wallonly`` 가 이미 모두 감추고 있으므로 건드리지
        # 않습니다. 월페이퍼로 돌아올 때 set_mode() 가 다시 불러 줍니다.
        if self._mode != "wall":
            return
        state = "hidden" if self._cover_image is not None else "normal"
        for item in (self.cover_mat, self.record_center, *self.record_items):
            self.canvas.itemconfigure(item, state=state)

    def _apply_weather(self, force=False):
        provider = self.weather
        # 이름을 ``version`` 으로 두면 모듈 :mod:`component.version` 을 가립니다.
        revision = provider.version if provider else 0
        if not force and revision == self._weather_version:
            return
        self._weather_version = revision
        current = provider.current if provider else None
        if current is None or not current.ok or current.temp is None:
            self.canvas.itemconfigure(self.temp_item, text="—")
            self.canvas.itemconfigure(self.deg_item, fill=DEG_WARM)
            self._place_temp()
            self._place_weather_icon()
            self.canvas.itemconfigure(self.desc_item, text=tr(
                "날씨 연결 중" if revision == 0 else "날씨 정보 없음"))
            self.canvas.itemconfigure(self.meta_item, text="")
            self.canvas.itemconfigure(self.meta2_item, text="")
            self.canvas.itemconfigure(self.wicon_item, image="")
            _drop_image(self.parent, self._wicon_image)
            self._wicon_image = None
            self._weather_icon_key = None
            self._weather_motion = ""
            self.canvas.itemconfigure(self.moon_item, state="hidden")
            if self._sky_key != "clear":
                self._sky_key = "clear"
                self._bake_sky()
            return
        # 영하 세 자리 등 폭이 긴 기온도 큰 아이콘과 겹치지 않게 맞춥니다.
        # 글꼴 크기를 먼저 정한 뒤에 글자를 넣습니다. 순서를 뒤집으면 Tk 가
        # 들고 있던 예전 크기의 bbox 가 한 프레임 남아, 그 값으로 자리를
        # 잡는 아이콘이 기온과 겹쳐 보입니다.
        value = "%d" % round(current.temp)
        temp_font = self._fonts["temp"][0]
        size = round(94 * self.scale)
        temp_font.configure(size=-max(8, size))
        while (size > 50 * self.scale
               and temp_font.measure(value + "°") > 162 * self.scale):
            size -= 1
            temp_font.configure(size=-max(8, size))
        self.canvas.itemconfigure(self.temp_item, text=value)
        # 도 표시만 색을 달리해 영상과 영하를 가릅니다. 빨강·파랑으로 맞세우면
        # 기온보다 이 작은 글자가 먼저 눈에 들어옵니다.
        self.canvas.itemconfigure(
            self.deg_item, fill=DEG_COLD if round(current.temp) < 0 else DEG_WARM)
        self._place_temp()
        self._place_weather_icon()
        self.canvas.itemconfigure(self.desc_item, text=tr(current.text))
        high = []
        if current.tmax is not None:
            high.append(tr("최고 %d°") % round(current.tmax))
        if current.tmin is not None:
            high.append(tr("최저 %d°") % round(current.tmin))
        low = []
        if current.humidity is not None:
            low.append(tr("습도 %d%%") % current.humidity)
        chance = current.precip if current.precip is not None else current.precip_max
        if chance is not None:
            low.append(tr("강수 %d%%") % chance)
        self.canvas.itemconfigure(self.meta_item, text="   ·   ".join(high))
        self.canvas.itemconfigure(self.meta2_item, text="   ·   ".join(low))
        self.canvas.itemconfigure(self.moon_item, state="normal")
        self._place_moon()
        self._set_weather_icon(current)
        if current.sky != self._sky_key:
            self._sky_key = current.sky
            self._bake_sky()

    def _place_moon(self):
        """보조 정보 두 줄 왼쪽에 오늘 달을 놓습니다.

        글자 길이에 따라 두 줄의 왼쪽 끝이 달라지므로 실제로 재서 맞춥니다.
        그림 자체는 자정과 정오가 지날 때만 다시 굽습니다.
        """
        c, s, sy = self.canvas, self.scale, self.scale_y
        boxes = [b for b in (c.bbox(self.meta_item), c.bbox(self.meta2_item)) if b]
        if not boxes:
            return
        size = max(12, round(MOON_SIZE * s))
        phase = weather.moon_phase()
        # 달은 하루에 두 번, 자정과 정오가 지나면 다시 굽습니다. 위상이 하루에
        # 3% 남짓 움직이므로 그보다 자주 그릴 이유가 없습니다.
        key = (size, _moon_slot())
        if key != self._moon_key:
            self._moon_key = key
            old = self._moon_image
            try:
                data = imaging.moon_png(size, phase)
                self._moon_image = tk.PhotoImage(master=self.parent, data=data,
                                                 format="png")
                c.itemconfigure(self.moon_item, image=self._moon_image)
            except (tk.TclError, ValueError) as exc:
                log("[월페이퍼] 달을 그리지 못했습니다: %s" % exc)
                self._moon_image = None
                c.itemconfigure(self.moon_item, image="")
            _drop_image(self.parent, old)
        cx = min(b[0] for b in boxes) - 26 * s - size / 2
        c.coords(self.moon_item, cx, MOON_Y * sy + self._weather_shift)

    def _set_weather_icon(self, current):
        size = max(1, round(WICON_SIZE * self.scale))
        key = (size, current.icon, current.is_day)
        if key == self._weather_icon_key:
            return
        self._weather_icon_key = key
        self._weather_motion = current.sky if current.is_day else (
            "moon" if current.sky == "clear" else current.sky)
        # 배경이 어느 시간대에나 어두우므로 밝은 아이콘 한 벌만 씁니다.
        color = weather_icons.color(current.icon, not current.is_day)
        svg = weather_icons.svg(current.icon, color, not current.is_day)
        old = self._wicon_image
        try:
            new = tk.PhotoImage(master=self.parent, data=svg,
                                format="svg -scaletowidth %d" % size)
        except tk.TclError as exc:
            log("[월페이퍼] 날씨 아이콘을 그리지 못했습니다: %s" % exc)
            new = None
        self._wicon_image = new
        self.canvas.itemconfigure(self.wicon_item, image=new or "")
        _drop_image(self.parent, old)

    def _animate_weather(self, now):
        """날씨 아이콘은 천천히 떠 있고 비·눈·별 장식은 짧게 움직입니다."""
        c, s = self.canvas, self.scale
        x, y = self._weather_center
        kind = self._weather_motion
        drift = math.sin(now * .55) * 3 * s if kind else 0
        c.coords(self.wicon_item, x + math.sin(now * .22) * 2 * s, y + drift)
        for i, item in enumerate(self.weather_sparks):
            if not kind or now % 24 > 7:
                c.itemconfigure(item, state="hidden")
                continue
            if kind in ("rain", "storm", "snow"):
                t = (now * .65 + i / 5) % 1
                px, py = x + (i - 2) * 12 * s, y + (29 + t * 32) * s
                r, ry = (1.4 * s, 3 * s) if kind != "snow" else (2 * s, 2 * s)
                color = "#9fbacf"
            elif kind in ("clear", "moon"):
                angle = now * .10 + i * math.tau / 5
                px, py = x + math.cos(angle) * 60 * s, y + math.sin(angle) * 59 * s
                r = ry = (.7 + .8 * (.5 + .5 * math.sin(now + i))) * s
                color = "#c5b597" if kind == "clear" else "#a2b7d1"
            else:
                c.itemconfigure(item, state="hidden")
                continue
            c.coords(item, px - r, py - ry, px + r, py + ry)
            c.itemconfigure(item, state="normal", fill=color)

    def _hit_control(self, x, y):
        if abs(y - 53 * self.scale_y) > 22 * self.scale:
            return None
        right = self.width - 60 * self.scale_x
        for i, name in enumerate(("settings", "full", "close")):
            if abs(x - (right - (88 - i * 44) * self.scale)) <= 22 * self.scale:
                return name
        return None

    def _hit_clock(self, x, y):
        left, top, right, bottom = self._clock_box
        return left <= x <= right and top <= y <= bottom

    def _show_controls(self, visible):
        self._controls_visible = visible
        self.canvas.itemconfigure("controls", state="normal" if visible else "hidden")
        if not visible:
            self._hovered = None
            self.canvas.configure(cursor="")

    def _wake_controls(self):
        """창이 앞으로 나왔을 때도 잠깐 버튼을 보여 줍니다."""
        self._controls_at = time.perf_counter()
        self._show_controls(True)

    def _motion(self, event):
        self._controls_at = time.perf_counter()
        self._show_controls(True)
        self._hovered = self._hit_control(event.x, event.y)
        labels = {"settings": tr("환경설정"), "full": tr("전체화면 · F11"),
                  "close": tr("트레이로 이동")}
        self.canvas.itemconfigure(self.tooltip, text=labels.get(self._hovered, ""))
        over = self._hovered or self._hit_clock(event.x, event.y)
        self.canvas.configure(cursor="hand2" if over else "")

    def _click(self, event):
        hit = self._hit_control(event.x, event.y)
        self._pressed_control = hit is not None
        if hit:
            action = self.actions.get(hit)
            if action:
                action()
            return "break"
        # 시계는 눌렀다 뗄 때 처리합니다. 여기에서 곧바로 받으면 창을 옮기려고
        # 시계를 잡아끄는 것과 구별되지 않습니다.
        self._pressed_clock = ((event.x, event.y)
                               if self._hit_clock(event.x, event.y) else None)
        return None

    def _release(self, event):
        pressed, self._pressed_clock = self._pressed_clock, None
        if pressed is None or self._pressed_control:
            return None
        if (abs(event.x - pressed[0]) > 4 or abs(event.y - pressed[1]) > 4
                or not self._hit_clock(event.x, event.y)):
            return None
        self.toggle_clock()
        return "break"

    def _control_drag(self, _event):
        # 버튼을 누른 채 움직여도 본 창의 드래그 바인딩에 전파하지 않습니다.
        return "break" if self._pressed_control else None


def _cut_to(text, font, room):
    """``room`` 픽셀 안에 들어가는 글자 수를 셉니다. 이분법으로 찾습니다."""
    if room <= 0:
        return 0
    low, high = 0, len(text)
    while low < high:
        mid = (low + high + 1) // 2
        if font.measure(text[:mid]) <= room:
            low = mid
        else:
            high = mid - 1
    return low


def _moon_slot(now=None):
    """달을 다시 그릴 때를 나타냅니다. 하루를 자정과 정오로 나눕니다."""
    now = time.localtime() if now is None else now
    return (now.tm_year, now.tm_yday, 0 if now.tm_hour < 12 else 1)


def _now_hour():
    now = time.localtime()
    return now.tm_hour + now.tm_min / 60


def _drop_image(parent, image):
    if image is not None:
        try:
            parent.tk.call("image", "delete", str(image))
        except tk.TclError:
            pass

