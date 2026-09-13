"""상시 표시를 위한 월페이퍼: 큰 시계와 날씨, 지평선과 음악.

장면 계산은 단일 작업 스레드에서, Tk 접근은 UI 스레드에서만 합니다.
도형·예약 콜백 수는 고정이며 커버 및 배경 프레임은 누적하지 않습니다.
"""

import math
import time
import tkinter as tk
from concurrent.futures import ThreadPoolExecutor

from . import imaging, sky, weather_icons
from .atmosphere import Atmosphere
from .audio import BARS
from .paths import log
from .text import fit_text
from .theme import WALL_UI_FAMILIES, WALL_MONO_FAMILIES, pick_font

BASE_W, BASE_H = 960, 640
COVER_SIZE = 112
WICON_SIZE = 128
SPECTRUM_BARS = 64
INK, INK_2, INK_3 = "#f1f2f3", "#bdc5ce", "#b2bdcb"
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
        self._track_text = ("고요한 순간", "음악을 재생하면 이곳에 표시됩니다", "")
        self._track_fade = None
        self._has_track = False
        self._controls_at, self._controls_visible, self._hovered = 0, False, None
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
        self.date_item = self._text(self._font("date", -32), INK_2)
        self.phase_item = self._text(self._font("phase", -12), INK_3, anchor="e")
        self.day_line = c.create_line(0, 0, 0, 0, fill="#566272", width=1)
        self.phase_dot = c.create_oval(0, 0, 0, 0, outline="", fill="#c7b7aa")
        f_clock = self._font("clock", -158, CLOCK_FAMILIES)
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
        # 커버를 못 받아도 음악 영역의 균형을 유지하는 레코드 문양.
        self.cover_mat = c.create_polygon(0, 0, 0, 0, fill="#121b25", outline="#2d3a48",
                                          smooth=True, splinesteps=24)
        self.record_items = [c.create_oval(0, 0, 0, 0, outline="#34414e")
                             for _ in range(5)]
        self.record_center = c.create_oval(0, 0, 0, 0, fill="#a7bcc8", outline="")
        self.cover_item = c.create_image(0, 0, anchor="nw")
        self.play_label = self._text(self._font("label", -12), INK_3,
                                     "S O U N D   A T   R E S T")
        f_title = self._font("title", -38, weight="bold")
        f_artist = self._font("artist", -25)
        self.title_shadow = self._text(f_title, "#080b12")
        self.title_item = self._text(f_title)
        self.artist_shadow = self._text(f_artist, "#080b12")
        self.artist_item = self._text(f_artist, INK_2)
        self.album_item = self._text(self._font("album", -17), INK_3)
        self.play_dots = [c.create_line(0, 0, 0, 0, fill=INK_3, capstyle="round")
                          for _ in range(3)]
        # 44px 클릭 영역. 아이콘과 안내는 포인터를 움직일 때만 나타납니다.
        self.control_items = {}
        f_control = self._font("control", -22, ("Segoe UI Symbol", "Segoe UI"))
        for key, glyph in (("settings", "⚙"), ("full", "⛶"), ("close", "×")):
            item = self._text(f_control, INK_2, glyph, anchor="center", tag="controls")
            self.control_items[key] = item
        self.tooltip = self._text(self._font("tooltip", -13), INK_2,
                                  anchor="e", tag="controls")
        c.itemconfigure("controls", state="hidden")
        c.itemconfigure(self.control_items["close"], state="normal")
        c.bind("<Motion>", self._motion)
        c.bind("<Leave>", lambda _e: self._show_controls(False))
        c.bind("<Button-1>", self._click)
        c.bind("<B1-Motion>", self._control_drag)
        self._pressed_control = False

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
        c.coords(self.date_item, x, 56 * sy)
        c.coords(self.phase_item, x, 359 * sy)
        c.itemconfigure(self.phase_item, anchor="w")
        c.coords(self.day_line, x, 100 * sy, x + 28 * s, 100 * sy)
        c.coords(self.phase_dot, x, 388 * sy, x + 5 * s, 388 * sy + 5 * s)
        # 기준선 대신 시각적 중심으로 놓아 Windows 글꼴 여백을 흡수합니다.
        c.coords(self.clock_item, x - 8 * s, 227 * sy)
        c.coords(self.clock_shadow, x - 8 * s + s, 227 * sy + 2 * s)
        self._weather_center = (right - 250 * s, 212 * sy)
        c.coords(self.wicon_item, *self._weather_center)
        c.coords(self.temp_item, right, 212 * sy)
        c.coords(self.desc_item, right, 294 * sy)
        c.coords(self.meta_item, right, 348 * sy)
        c.coords(self.meta2_item, right, 390 * sy)
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
        c.coords(self.play_label, self._track_x, cy + 4 * s)
        for front, shadow, dy in ((self.title_item, self.title_shadow, 40),
                                   (self.artist_item, self.artist_shadow, 79)):
            c.coords(front, self._track_x, cy + dy * s)
            c.coords(shadow, self._track_x + s, cy + dy * s + s)
        c.coords(self.album_item, self._track_x, cy + 108 * s)
        for i, key in enumerate(("settings", "full", "close")):
            c.coords(self.control_items[key], right - (88 - 44 * i) * s, 53 * sy)
        c.coords(self.tooltip, right, 85 * sy)
        self._fit_track()
        self._position_seconds()

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
        for photo in (self._bg_image, self._cover_image, self._wicon_image):
            _drop_image(self.parent, photo)
        self._bg_image = self._cover_image = self._wicon_image = None
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
                self.canvas.itemconfigure(self.phase_dot, fill=sky.to_hex(palette["glow"]))
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
        self.canvas.itemconfigure(self.sec_item, text="%02d" % now.tm_sec)
        self._position_seconds()

    def _position_seconds(self):
        box = self.canvas.bbox(self.clock_item)
        if box:
            self.canvas.coords(self.sec_item, box[2] + 12 * self.scale,
                               272 * self.scale_y)

    def _fit_track(self):
        for key, raw, items in (
                ("title", self._track_text[0], (self.title_item, self.title_shadow)),
                ("artist", self._track_text[1], (self.artist_item, self.artist_shadow)),
                ("album", self._track_text[2], (self.album_item,))):
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
        text = ((track.title, track.artist, track.album or "") if playing else
                ("고요한 순간", "음악을 재생하면 이곳에 표시됩니다", ""))
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
        for item, color in ((self.title_item, INK), (self.artist_item, INK_2),
                            (self.album_item, INK_3)):
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
        self._set_weather_icon(current)
        if current.sky != self._sky_key:
            self._sky_key = current.sky
            self._bake_sky()

    def _set_weather_icon(self, current):
        size = max(1, round(WICON_SIZE * self.scale))
        key = (size, current.icon, current.is_day)
        if key == self._weather_icon_key:
            return
        self._weather_icon_key = key
        self._weather_motion = current.sky if current.is_day else (
            "moon" if current.sky == "clear" else current.sky)
        color = "#edc68e" if current.is_day and current.sky == "clear" else "#c2d3e6"
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


def _now_hour():
    now = time.localtime()
    return now.tm_hour + now.tm_min / 60


def _drop_image(parent, image):
    if image is not None:
        try:
            parent.tk.call("image", "delete", str(image))
        except tk.TclError:
            pass

