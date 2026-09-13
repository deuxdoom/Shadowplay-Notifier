"""상시 표시를 위한 월페이퍼: 큰 시계와 날씨, 지평선과 음악.

장면 계산은 단일 작업 스레드에서, Tk 접근은 UI 스레드에서만 합니다.
도형·예약 콜백 수는 고정이며 커버 및 배경 프레임은 누적하지 않습니다.
"""

import math
import time
import tkinter as tk
from concurrent.futures import ThreadPoolExecutor

from . import imaging, sky, weather, weather_icons
from .atmosphere import Atmosphere
from .audio import BARS
from .paths import log
from .text import fit_text
from .theme import WALL_UI_FAMILIES, WALL_MONO_FAMILIES, pick_font

BASE_W, BASE_H = 960, 640
COVER_SIZE = 112
WICON_SIZE = 128
SPECTRUM_BARS = 64
# 보조 정보 왼쪽에 놓는 달의 지름입니다.
MOON_SIZE = 70
INK, INK_2, INK_3 = "#f1f2f3", "#bdc5ce", "#b2bdcb"

# 녹화·대기 화면. 월페이퍼와 같은 골격을 쓰되 내용만 갈아 끼웁니다.
# 큰 숫자는 시계와 같은 높이에 두어 전환이 이어져 보이게 합니다.
REC_LABEL_Y, REC_FOLDER_Y, REC_BIG_Y = 58, 116, 248
REC_RATE_Y, REC_GROW_Y, REC_FILE_Y = 318, 358, 392
REC_BOTTOM_Y, BADGE_SIZE, LOG_GAP = 452, 112, 36
STATUS_Y = 602
# 녹화 표시는 흐려지면 안 되므로 밝기를 낮추는 대신 더 밝은 쪽으로 흔듭니다.
REC_RED, REC_RED_LIT = "#ff4d4d", "#ff9090"
REC_TIME_INK = "#ff6b6b"
REC_BADGE_BG, REC_BADGE_EDGE = "#bf2a2a", "#ff9b9b"
IDLE_INK, IDLE_BADGE_BG, IDLE_BADGE_EDGE = "#7e8aa2", "#222b38", "#3d4858"
LOG_TIME_INK, STATUS_INK = "#8a94a6", "#77839a"
LOG_START_INK, LOG_STOP_INK = "#ff8080", "#7cc4f7"
CLOCK_FAMILIES = ("Segoe UI Light", "Segoe UI", "Pretendard JP", "Arial")
DOW = ("월요일", "화요일", "수요일", "목요일", "금요일", "토요일", "일요일")


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
        self._fonts = {}
        self._cover_data = None
        self._cover_render_key = None
        self._track_text = ("고요한 순간", "음악을 재생하면 이곳에 표시됩니다")
        self._track_fade = None
        self._has_track = False
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
        self.bar_items = [c.create_line(0, 0, 0, 0, capstyle="round", fill=INK_3)
                          for _ in range(SPECTRUM_BARS)]
        self.reflection_items = [c.create_line(0, 0, 0, 0, capstyle="round", fill=INK_3)
                                 for _ in range(SPECTRUM_BARS)]
        # 시간대 이름은 시계 위, 날짜보다 앞줄에 둡니다. 시계 아래에 두었을
        # 때는 작고 멀어서 읽히지 않았습니다.
        self.phase_item = self._text(self._font("phase", -20), INK_3)
        self.date_item = self._text(self._font("date", -36), INK_2)
        f_clock = self._font("clock", -182, CLOCK_FAMILIES)
        self.clock_shadow = self._text(f_clock, "#080b12")
        self.clock_item = self._text(f_clock)
        self.sec_item = self._text(self._font("sec", -24, WALL_MONO_FAMILIES), INK_3)
        self.wicon_item = c.create_image(0, 0, anchor="center")
        self.temp_item = self._text(self._font("temp", -94, CLOCK_FAMILIES), text="—°", anchor="e")
        self.desc_item = self._text(self._font("desc", -29), INK_2, "날씨 연결 중", anchor="e")
        self.meta_item = self._text(self._font("meta", -24), INK_3, anchor="e")
        self.meta2_item = self._text(self._fonts["meta"][0], INK_3, anchor="e")
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
        self.play_label = self._text(self._font("label", -14), INK_3,
                                     "S O U N D   A T   R E S T")
        f_title = self._font("title", -46, weight="bold")
        self.title_shadow = self._text(f_title, "#080b12")
        self.title_item = self._text(f_title)
        self.album_item = self._text(self._font("album", -24), INK_3)
        self.play_dots = [c.create_line(0, 0, 0, 0, fill=INK_3, capstyle="round")
                          for _ in range(3)]
        # 44px 클릭 영역. 아이콘과 안내는 포인터를 움직일 때만 나타납니다.
        self.control_items = {}
        f_control = self._font("control", -22, ("Segoe UI Symbol", "Segoe UI"))
        for key, glyph in (("settings", "⚙"), ("full", "⛶"), ("close", "×")):
            item = self._text(f_control, INK_2, glyph, anchor="center", tag="controls")
            self.control_items[key] = item
        self._build_recording()
        self.tooltip = self._text(self._font("tooltip", -13), INK_2,
                                  anchor="e", tag="controls")
        c.itemconfigure("controls", state="hidden")
        c.itemconfigure(self.control_items["close"], state="normal")
        c.bind("<Motion>", self._motion)
        c.bind("<Leave>", lambda _e: self._show_controls(False))
        c.bind("<Button-1>", self._click)
        c.bind("<B1-Motion>", self._control_drag)
        self._pressed_control = False

    def _build_recording(self):
        """녹화와 대기 화면에 쓰는 도형입니다. 만들어 두고 숨겨 놓습니다."""
        c = self.canvas
        self.rec_dot = c.create_oval(0, 0, 0, 0, outline="", fill=REC_RED,
                                     tags="reconly")
        self.rec_word = self._text(self._font("recword", -26, weight="bold"),
                                   REC_RED, tag="reconly")
        self.rec_folder = self._text(self._font("recfolder", -40), INK,
                                     tag="reconly")
        f_time = self._font("rectime", -148, CLOCK_FAMILIES)
        self.rec_time_shadow = self._text(f_time, "#080b12", tag="reconly")
        self.rec_time = self._text(f_time, REC_TIME_INK, tag="reconly")
        self.rec_size = self._text(self._font("recsize", -88, CLOCK_FAMILIES),
                                   INK, anchor="e", tag="reconly")
        self.rec_unit = self._text(self._font("recunit", -34), INK_3,
                                   anchor="e", tag="reconly")
        self.rec_rate = self._text(self._font("recrate", -30), INK_2,
                                   anchor="e", tag="reconly")
        self.rec_grow = self._text(self._font("recgrow", -22), INK_3,
                                   anchor="e", tag="reconly")
        self.rec_file = self._text(self._font("recfile", -19), "#7d879a",
                                   anchor="e", tag="reconly")

        # 왼쪽 아래 표시등. 앨범 커버가 있던 자리를 그대로 씁니다.
        self.badge_mat = c.create_polygon(0, 0, 0, 0, fill=REC_BADGE_BG,
                                          outline=REC_BADGE_EDGE, smooth=True,
                                          splinesteps=24, tags="reconly")
        self.badge_ring = c.create_oval(0, 0, 0, 0, outline="", fill="#ffffff",
                                        tags="reconly")
        self.badge_word = self._text(self._font("badge", -15, weight="bold"),
                                     "#ffffff", anchor="center", tag="reconly")

        self.log_label = self._text(self._font("loglabel", -14), INK_3,
                                    "E V E N T   L O G", tag="reconly")
        f_log = self._font("logrow", -20)
        self.log_items = [self._text(f_log, INK_2, tag="reconly")
                          for _ in range(3)]
        self.status_item = self._text(self._font("status", -18), STATUS_INK,
                                      tag="reconly")
        self.status_ver = self._text(self._font("statusver", -16), "#5a6478",
                                     anchor="e", tag="reconly")
        c.itemconfigure("reconly", state="hidden")

        # 월페이퍼에서만 보이는 것들을 한데 묶어 둡니다.
        for item in (self.phase_item, self.date_item, self.clock_item,
                     self.clock_shadow, self.sec_item, self.wicon_item,
                     self.temp_item, self.desc_item, self.meta_item,
                     self.meta2_item, self.moon_item, self.cover_mat,
                     self.record_center, self.cover_item, self.play_label,
                     self.title_item, self.title_shadow, self.album_item):
            c.addtag_withtag("wallonly", item)
        for group in (self.bar_items, self.reflection_items, self.record_items,
                      self.play_dots, self.weather_sparks):
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
        self._bar_y, self._bar_height = 449 * sy, 27 * s
        # 구분선을 빼고 사이 간격만으로 나눕니다. 선이 차지하던 자리를
        # 시계가 가져갑니다.
        c.coords(self.phase_item, x, 52 * sy)
        c.coords(self.date_item, x, 96 * sy)
        # 기준선 대신 시각적 중심으로 놓아 Windows 글꼴 여백을 흡수합니다.
        c.coords(self.clock_item, x - 8 * s, 248 * sy)
        c.coords(self.clock_shadow, x - 8 * s + s, 248 * sy + 2 * s)
        self._weather_center = (right - 268 * s, 206 * sy)
        c.coords(self.wicon_item, *self._weather_center)
        c.coords(self.temp_item, right, 206 * sy)
        c.coords(self.desc_item, right, 288 * sy)
        c.coords(self.meta_item, right, 344 * sy)
        c.coords(self.meta2_item, right, 388 * sy)
        cx, cy = self._cover_xy
        side = COVER_SIZE * s
        c.coords(self.cover_mat, *_round_rect(cx, cy, side, side, 15 * s))
        c.coords(self.cover_item, cx, cy)
        for i, item in enumerate(self.record_items):
            r = (39 - i * 6) * s
            c.coords(item, cx + side / 2 - r, cy + side / 2 - r,
                     cx + side / 2 + r, cy + side / 2 + r)
        c.coords(self.record_center, cx + side / 2 - 4 * s, cy + side / 2 - 4 * s,
                 cx + side / 2 + 4 * s, cy + side / 2 + 4 * s)
        c.coords(self.play_label, self._track_x, cy + 6 * s)
        c.coords(self.title_item, self._track_x, cy + 50 * s)
        c.coords(self.title_shadow, self._track_x + s, cy + 50 * s + s)
        c.coords(self.album_item, self._track_x, cy + 96 * s)
        for i, key in enumerate(("settings", "full", "close")):
            c.coords(self.control_items[key], right - (88 - 44 * i) * s, 53 * sy)
        c.coords(self.tooltip, right, 85 * sy)
        self._place_moon()
        self._place_recording()
        self._fit_track()
        self._position_seconds()

    def _place_recording(self):
        """녹화·대기 화면의 자리입니다. 월페이퍼와 같은 여백을 씁니다."""
        c, sx, sy, s = self.canvas, self.scale_x, self.scale_y, self.scale
        x, right = 60 * sx, self.width - 60 * sx
        radius = 11 * s
        cy = REC_LABEL_Y * sy
        c.coords(self.rec_dot, x + radius - radius, cy - radius,
                 x + radius * 2, cy + radius)
        c.coords(self.rec_word, x + 36 * s, cy)
        c.coords(self.rec_folder, x, REC_FOLDER_Y * sy)
        c.coords(self.rec_time, x - 8 * s, REC_BIG_Y * sy)
        c.coords(self.rec_time_shadow, x - 8 * s + s, REC_BIG_Y * sy + 2 * s)
        c.coords(self.rec_unit, right, (REC_BIG_Y + 22) * sy)
        c.coords(self.rec_rate, right, REC_RATE_Y * sy)
        c.coords(self.rec_grow, right, REC_GROW_Y * sy)
        c.coords(self.rec_file, right, REC_FILE_Y * sy)
        self._place_size_value()

        side = BADGE_SIZE * s
        top = REC_BOTTOM_Y * sy
        c.coords(self.badge_mat, *_round_rect(x, top, side, side, 15 * s))
        ring = 17 * s
        c.coords(self.badge_ring, x + side / 2 - ring, top + side / 2 - ring - 8 * s,
                 x + side / 2 + ring, top + side / 2 + ring - 8 * s)
        c.coords(self.badge_word, x + side / 2, top + side / 2 + 30 * s)

        log_x = x + (BADGE_SIZE + 30) * s
        c.coords(self.log_label, log_x, (REC_BOTTOM_Y + 10) * sy)
        for i, item in enumerate(self.log_items):
            c.coords(item, log_x, (REC_BOTTOM_Y + 44 + i * LOG_GAP) * sy)
        c.coords(self.status_item, x, STATUS_Y * sy)
        c.coords(self.status_ver, right, STATUS_Y * sy)

    def _place_size_value(self):
        """용량 숫자를 단위 왼쪽에 붙여 놓습니다."""
        right = self.width - 60 * self.scale_x
        try:
            box = self.canvas.bbox(self.rec_unit)
        except tk.TclError:
            box = None
        gap = 10 * self.scale
        edge = (box[0] - gap) if box else (right - 60 * self.scale)
        self.canvas.coords(self.rec_size, edge, REC_BIG_Y * self.scale_y)


    # ------------------------------------------------------------ 화면 갈아 끼우기

    @property
    def mode(self):
        return self._mode

    def set_mode(self, mode):
        """``wall``, ``rec``, ``idle`` 가운데 하나로 바꿉니다.

        배경과 지평선은 그대로 두고 그 위의 내용만 갈아 끼웁니다. 캔버스를
        떠나지 않으므로 하늘을 다시 굽지 않고 전환이 이어집니다.
        """
        if mode not in ("wall", "rec", "idle") or mode == self._mode:
            return
        self._mode = mode
        c = self.canvas
        wall = (mode == "wall")
        c.itemconfigure("wallonly", state="normal" if wall else "hidden")
        c.itemconfigure("reconly", state="hidden" if wall else "normal")
        # 별·비·눈은 월페이퍼에서만 움직입니다. 녹화 중에는 쉬게 둡니다.
        c.itemconfigure("atmosphere", state="hidden")
        if wall:
            if self._bg_pixels is not None:
                self.atmosphere.configure(self.width, self.height, self._palette,
                                          self._sky_key, self._bg_pixels,
                                          time.perf_counter())
        else:
            self._paint_mode(mode)

    def _paint_mode(self, mode):
        """녹화와 대기의 색을 나누어 칠합니다."""
        c = self.canvas
        recording = (mode == "rec")
        c.itemconfigure(self.rec_word,
                        text="R E C O R D I N G" if recording else "S T A N D B Y",
                        fill=REC_RED if recording else IDLE_INK)
        c.itemconfigure(self.rec_dot, fill=REC_RED if recording else IDLE_INK)
        c.itemconfigure(self.rec_time, fill=REC_TIME_INK if recording else IDLE_INK)
        c.itemconfigure(self.badge_mat,
                        fill=REC_BADGE_BG if recording else IDLE_BADGE_BG,
                        outline=REC_BADGE_EDGE if recording else IDLE_BADGE_EDGE)
        c.itemconfigure(self.badge_ring, fill="#ffffff" if recording else "#59647a")
        c.itemconfigure(self.badge_word, text="R E C" if recording else "I D L E",
                        fill="#ffffff" if recording else IDLE_INK)
        c.itemconfigure(self.rec_size, fill=INK if recording else "#8b97a9")
        c.itemconfigure(self.rec_rate, fill=INK_2 if recording else "#79839a")

    def show_recording(self, folder, elapsed, size, rate, growth, filename):
        """녹화 중일 때 채웁니다. 값은 이미 다듬은 문자열입니다."""
        c = self.canvas
        c.itemconfigure(self.rec_folder,
                        text=fit_text(folder, self._fonts["recfolder"][0],
                                      int(self.width * 0.42)))
        for item in (self.rec_time, self.rec_time_shadow):
            c.itemconfigure(item, text=elapsed)
        number, _, unit = size.partition(" ")
        c.itemconfigure(self.rec_unit, text=unit)
        c.itemconfigure(self.rec_size, text=number)
        self._place_size_value()
        c.itemconfigure(self.rec_rate, text=rate)
        c.itemconfigure(self.rec_grow, text=growth)
        c.itemconfigure(self.rec_file,
                        text=fit_text(filename, self._fonts["recfile"][0],
                                      int(self.width * 0.46)))

    def show_idle(self, watch_path, size, note, detail, filename):
        """녹화를 기다릴 때 채웁니다."""
        c = self.canvas
        c.itemconfigure(self.rec_folder,
                        text=fit_text(watch_path, self._fonts["recfolder"][0],
                                      int(self.width * 0.46)))
        for item in (self.rec_time, self.rec_time_shadow):
            c.itemconfigure(item, text="0:00:00")
        number, _, unit = size.partition(" ")
        c.itemconfigure(self.rec_unit, text=unit)
        c.itemconfigure(self.rec_size, text=number)
        self._place_size_value()
        c.itemconfigure(self.rec_rate, text=note)
        c.itemconfigure(self.rec_grow, text=detail)
        c.itemconfigure(self.rec_file,
                        text=fit_text(filename, self._fonts["recfile"][0],
                                      int(self.width * 0.46)))

    def set_log(self, rows):
        """이벤트 로그를 세 줄까지 적습니다. rows 는 (시각, 종류, 내용) 입니다."""
        font = self._fonts["logrow"][0]
        room = int(self.width - (60 + BADGE_SIZE + 30) * self.scale
                   - 60 * self.scale_x)
        for i, item in enumerate(self.log_items):
            if i >= len(rows):
                self.canvas.itemconfigure(item, text="")
                continue
            stamp, kind, text = rows[i]
            color = (LOG_START_INK if kind == "시작" else
                     LOG_STOP_INK if kind == "중단" else INK_3)
            line = "%s   %s   %s" % (stamp, kind, text) if kind else \
                   "%s   %s" % (stamp, text)
            self.canvas.itemconfigure(item, text=fit_text(line, font, room),
                                      fill=color if kind else INK_3)

    def set_status(self, text, version=""):
        """맨 아래 한 줄입니다. 감시 폴더와 주기, 갱신 시각, 세션 누적을 적습니다."""
        font = self._fonts["status"][0]
        room = int(self.width - 120 * self.scale_x - 90 * self.scale)
        self.canvas.itemconfigure(self.status_item, text=fit_text(text, font, room))
        self.canvas.itemconfigure(self.status_ver, text=version)

    def _pulse_recording(self, now):
        """녹화 표시의 맥박입니다.

        흐려지면 안 되므로 어두워지는 대신 더 밝은 쪽으로만 흔듭니다.
        크기도 함께 키워서 멀리서도 켜져 있는 것이 보입니다.
        """
        k = 0.5 - 0.5 * math.cos(now * 2 * math.pi)
        color = sky.to_hex(sky.mix(sky._rgb(REC_RED), sky._rgb(REC_RED_LIT), k))
        self.canvas.itemconfigure(self.rec_dot, fill=color)
        s, sx, sy = self.scale, self.scale_x, self.scale_y
        x = 60 * sx
        radius = (11 + 1.4 * k) * s
        cy = REC_LABEL_Y * sy
        self.canvas.coords(self.rec_dot, x, cy - radius, x + radius * 2, cy + radius)
        ring = (17 + 2.2 * k) * s
        cx = x + BADGE_SIZE * s / 2
        top = REC_BOTTOM_Y * sy + BADGE_SIZE * s / 2 - 8 * s
        self.canvas.coords(self.badge_ring, cx - ring, top - ring,
                           cx + ring, top + ring)

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
        phase = int(now / 30) if self._sky_key != "clear" else 0
        key = (self.width, self.height, tuple(palette["sky"]), palette["glow"],
               self._sky_key, self._accent, phase)
        self._baked_at = now
        if not force and key == self._bake_key:
            return
        self._bake_key = key
        self._wanted = (key, palette, phase * .12)
        self._submit_sky()

    def _submit_sky(self):
        if self._future is not None or self._wanted is None:
            return
        key, palette, phase = self._wanted
        self._future = (key, palette, self._executor.submit(
            sky.render, key[0], key[1], palette, key[5], key[4], phase))

    def _poll_sky(self, now):
        if self._future is not None and self._future[2].done():
            key, palette, future = self._future
            self._future = None
            try:
                pixels = future.result()
            except Exception as exc:
                log("[월페이퍼] 배경을 만들지 못했습니다: %s" % exc)
                pixels = None
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
        tint = sky.mix(self._palette["glow"], self._accent or (194, 213, 225), .38)
        for i, (bar, reflection) in enumerate(zip(self.bar_items, self.reflection_items)):
            x = self._bar_left + (self._bar_right - self._bar_left) * i / (SPECTRUM_BARS - 1)
            ground = sky.sample(self._bg_pixels, x / self.width, self._bar_y / self.height)
            self.canvas.itemconfigure(bar, fill=sky.to_hex(sky.mix(ground, tint, .56)))
            self.canvas.itemconfigure(reflection, fill=sky.to_hex(sky.mix(ground, tint, .13)))

    def _update_bars(self, now, dt):
        levels = self.audio.levels if self.audio else (0.,) * BARS
        for i in range(BARS):
            target = max(0, min(1, levels[i]))
            speed = 21 if target > self._levels[i] else 6
            self._levels[i] += (target - self._levels[i]) * (1 - math.exp(-speed * dt))
        c, s = self.canvas, self.scale
        for j, (bar, reflection) in enumerate(zip(self.bar_items, self.reflection_items)):
            pos = j * (BARS - 1) / (SPECTRUM_BARS - 1)
            i, f = min(BARS - 2, int(pos)), pos - min(BARS - 2, int(pos))
            level = self._levels[i] * (1 - f) + self._levels[i + 1] * f
            edge = math.sin(math.pi * (j + 1) / (SPECTRUM_BARS + 1)) ** .45
            height = level * self._bar_height * edge
            x = self._bar_left + (self._bar_right - self._bar_left) * j / (SPECTRUM_BARS - 1)
            if height < .3:
                c.coords(bar, -10, -10, -10, -10)
                c.coords(reflection, -10, -10, -10, -10)
                continue
            c.coords(bar, x, self._bar_y - height, x, self._bar_y)
            c.coords(reflection, x, self._bar_y + 5 * s, x, self._bar_y + 5 * s + height * .3)
            c.itemconfigure(bar, width=max(1, 2 * s))
            c.itemconfigure(reflection, width=max(1, 2 * s))
        for i, item in enumerate(self.play_dots):
            x = self._bar_right - (12 - i * 6) * s
            y = self._cover_xy[1] + 4 * s
            height = (2 + self._levels[i * 3] * 9) * s if self._has_track else 0
            c.coords(item, x, y - height, x, y + height)
            c.itemconfigure(item, state="normal" if self._has_track else "hidden", width=max(1, 2 * s))

    def _tick(self):
        self._after_id = None
        if not self.running:
            return
        now = time.perf_counter()
        dt = min(.15, max(.001, now - self._last_frame))
        self._last_frame = now
        try:
            if self._mode != "wall":
                # 녹화·대기 화면에서는 표시등 맥박과 시각만 돌립니다.
                self._pulse_recording(now)
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
            if self._controls_visible and now - self._controls_at > 2.8 and self._hovered is None:
                self._show_controls(False)
        except Exception as exc:
            log("[월페이퍼] 그리다가 걸렸습니다: %s" % exc)
        elapsed = (time.perf_counter() - now) * 1000
        self._after_id = self.parent.after(max(1, self.period - round(elapsed)), self._tick)

    def _update_clock(self):
        now = time.localtime()
        stamp = (now.tm_year, now.tm_yday, now.tm_hour, now.tm_min, now.tm_sec)
        if stamp == self._last_second:
            return
        minute_changed = self._last_second is None or stamp[:-1] != self._last_second[:-1]
        self._last_second = stamp
        if minute_changed:
            text = time.strftime("%H:%M", now)
            for item in (self.clock_item, self.clock_shadow):
                self.canvas.itemconfigure(item, text=text)
            self.canvas.itemconfigure(self.date_item, text="%d년 %d월 %d일   %s" %
                                      (now.tm_year, now.tm_mon, now.tm_mday, DOW[now.tm_wday]))
            # 자정이나 정오를 지났으면 달을 다시 그립니다.
            slot = _moon_slot(now)
            if slot != self._moon_slot:
                self._moon_slot = slot
                self._place_moon()
        self.canvas.itemconfigure(self.sec_item, text="%02d" % now.tm_sec)
        self._position_seconds()

    def _position_seconds(self):
        box = self.canvas.bbox(self.clock_item)
        if box:
            self.canvas.coords(self.sec_item, box[2] + 14 * self.scale,
                               298 * self.scale_y)

    def _fit_track(self):
        for key, raw, items in (
                ("title", self._track_text[0], (self.title_item, self.title_shadow)),
                ("album", self._track_text[1], (self.album_item,))):
            text = fit_text(raw, self._fonts[key][0], int(self._track_width))
            for item in items:
                self.canvas.itemconfigure(item, text=text)

    def _apply_track(self, force=False):
        provider = self.nowplaying
        version = provider.version if provider else 0
        if not force and version == self._track_version:
            return
        first = self._track_version == -1
        self._track_version = version
        track = provider.track if provider else None
        playing = bool(track and track.is_playing())
        # 아티스트와 곡을 한 줄로 붙여 오른쪽 빈자리를 줄입니다.
        if playing:
            head = ("%s - %s" % (track.artist, track.title)
                    if track.artist else track.title)
            text = (head, track.album or "")
        else:
            text = ("고요한 순간", "음악을 재생하면 이곳에 표시됩니다")
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
        for item, color in ((self.title_item, INK), (self.album_item, INK_3)):
            self.canvas.itemconfigure(item, fill=sky.to_hex(
                sky.mix((81, 94, 108), sky._rgb(color), .25 + .75 * t)))
        if t >= 1:
            self._track_fade = None

    def _set_cover(self, data):
        side = max(1, round(COVER_SIZE * self.scale))
        # 같은 곡에서 날씨·창 위치만 바뀌면 JPEG를 다시 풀지 않습니다.
        key = (id(data), side)
        if key == self._cover_render_key:
            return
        self._cover_render_key, self._cover_data = key, data
        png = imaging.rounded_cover_png(data, side, round(14 * self.scale)) if data else None
        new = tk.PhotoImage(master=self.parent, data=png, format="png") if png else None
        old, self._cover_image = self._cover_image, new
        self.canvas.itemconfigure(self.cover_item, image=new or "")
        _drop_image(self.parent, old)

    def _apply_weather(self, force=False):
        provider = self.weather
        version = provider.version if provider else 0
        if not force and version == self._weather_version:
            return
        self._weather_version = version
        current = provider.current if provider else None
        if current is None or not current.ok or current.temp is None:
            self.canvas.itemconfigure(self.temp_item, text="—°")
            self.canvas.itemconfigure(self.desc_item, text="날씨 연결 중" if version == 0 else "날씨 정보 없음")
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
        self.canvas.itemconfigure(self.temp_item, text="%d°" % round(current.temp))
        # 영하 세 자리 등 폭이 긴 기온도 큰 아이콘과 겹치지 않게 맞춥니다.
        temp_font = self._fonts["temp"][0]
        size = round(94 * self.scale)
        temp_font.configure(size=-max(8, size))
        while size > 50 * self.scale and temp_font.measure("%d°" % round(current.temp)) > 162 * self.scale:
            size -= 1
            temp_font.configure(size=-max(8, size))
        self.canvas.itemconfigure(self.desc_item, text=current.text)
        high = []
        if current.tmax is not None:
            high.append("최고 %d°" % round(current.tmax))
        if current.tmin is not None:
            high.append("최저 %d°" % round(current.tmin))
        low = []
        if current.humidity is not None:
            low.append("습도 %d%%" % current.humidity)
        chance = current.precip if current.precip is not None else current.precip_max
        if chance is not None:
            low.append("강수 %d%%" % chance)
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
        c.coords(self.moon_item, cx, 366 * sy)

    def _set_weather_icon(self, current):
        size = max(1, round(WICON_SIZE * self.scale))
        key = (size, current.icon, current.is_day)
        if key == self._weather_icon_key:
            return
        self._weather_icon_key = key
        self._weather_motion = current.sky if current.is_day else (
            "moon" if current.sky == "clear" else current.sky)
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

    def _show_controls(self, visible):
        self._controls_visible = visible
        self.canvas.itemconfigure("controls", state="normal" if visible else "hidden")
        self.canvas.itemconfigure(self.control_items["close"], state="normal")
        if not visible:
            self._hovered = None
            self.canvas.configure(cursor="")

    def _motion(self, event):
        self._controls_at = time.perf_counter()
        self._show_controls(True)
        self._hovered = self._hit_control(event.x, event.y)
        labels = {"settings": "환경설정", "full": "전체화면 · F11", "close": "트레이로 이동"}
        self.canvas.itemconfigure(self.tooltip, text=labels.get(self._hovered, ""))
        self.canvas.configure(cursor="hand2" if self._hovered else "")
        for key, item in self.control_items.items():
            self.canvas.itemconfigure(item, fill=INK if key == self._hovered else INK_3)

    def _click(self, event):
        hit = self._hit_control(event.x, event.y)
        self._pressed_control = hit is not None
        if hit:
            action = self.actions.get(hit)
            if action:
                action()
            return "break"
        return None

    def _control_drag(self, _event):
        # 버튼을 누른 채 움직여도 본 창의 드래그 바인딩에 전파하지 않습니다.
        return "break" if self._pressed_control else None


def _round_rect(x, y, width, height, radius):
    r = radius
    return (x + r, y, x + width - r, y, x + width, y, x + width, y + r,
            x + width, y + height - r, x + width, y + height,
            x + width - r, y + height, x + r, y + height, x, y + height,
            x, y + height - r, x, y + r, x, y)


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

