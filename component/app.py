"""본 창의 화면 구성과 갱신입니다.

감시 스레드가 큐에 넣은 사건을 100ms 마다 꺼내어 화면에 반영합니다.
멀리서 흘끗 보는 용도이므로 상태 배너와 녹화 정보에 자리를 몰아주었습니다.
"""

import math
import os
import queue
import threading
import time
import tkinter as tk
import traceback
from collections import deque

from . import icons, version
from .audio import AudioLevels
from .display import monitor_for_point, window_position
from .nowplaying import NowPlaying
from .wallpaper import WallpaperView
from .weather import WeatherWatch
from .paths import log
from .scan import human, hms
from .settings_dialog import SettingsDialog
from .text import ellipsize, folder_label, relative_path
from .theme import (C_BG, C_DIM, C_FG, C_IDLE, C_IDLE_DOT, C_MUTED, C_PANEL,
                    C_REC, C_REC_DIM, C_REC_TEXT, C_SKY, C_YELLOW,
                    FOLDER_MAX_PX, H_BANNER, H_DETAIL, H_LOG, LOG_ROWS,
                    MONO_FAMILIES, UI_FAMILIES, WIN_H, WIN_W, growth_color,
                    mix, pick_font)

# 배너 오른쪽 위 버튼입니다. 오른쪽에서 왼쪽 차례로 놓습니다.
BUTTON_ORDER = ("close", "full", "settings")
BUTTON_W = 42
BUTTON_ZONE_H = 44


def _short_path(path):
    """경로가 길면 앞을 줄입니다. 뒤쪽 폴더 이름이 더 쓸모 있습니다."""
    parts = path.replace("/", "\\").rstrip("\\").split("\\")
    if len(parts) <= 3:
        return path
    return "…\\" + "\\".join(parts[-2:])


class _FakeConfigure:
    """지금 창 크기로 배치를 다시 잡을 때 쓰는 가짜 Configure 사건입니다."""

    def __init__(self, widget):
        self.widget = widget
        self.width = widget.winfo_width()
        self.height = widget.winfo_height()


class MonitorApp:
    def __init__(self, root, settings):
        self.root = root
        self.settings = dict(settings)
        self.dirs = settings["dirs"]
        self.interval = settings["interval"]
        self.borderless = settings["borderless"]

        self.close_callback = None
        self.hidden_to_tray = False
        self.settings_callback = None
        self.fullscreen = False
        self.saved_rect = (0, 0, WIN_W, WIN_H)
        self.queue = queue.Queue()
        self.stop_event = threading.Event()

        self.recording = False
        self.session_count = 0
        self.last_summary = "직전 녹화 기록이 없습니다."
        # 월페이퍼 화면에 나눠서 적으려면 값 자체가 필요합니다.
        self.last_record = None
        self._wall_log = deque(maxlen=3)
        self.last_update = "--:--:--"
        self.warning = ""
        self.log_rows = deque(maxlen=LOG_ROWS)
        self._folder_text = ""
        self._layout_size = None
        self._scale_x = self._scale_y = 1.0
        self._cell_holders = []

        # 예전 위젯 화면을 구성하는 동안 자리를 미리 비워 둡니다.
        self.wallpaper = None
        self._wall_audio = self._wall_track = self._wall_weather = None
        self._retired_sources = []

        self._init_fonts()
        self._build_banner()
        self._build_detail()
        self._build_log()
        self._build_status()
        self._refresh_status()
        self._enable_drag()
        self.root.bind("<Configure>", self._resize_layout, add="+")

        # 월페이퍼 화면을 켭니다. 녹화가 잡히면 같은 캔버스에서 내용만 바뀝니다.
        # _sync_view 가 화면을 켜고 소리·음악·날씨 스레드까지 함께 시작합니다.
        self._ensure_wallpaper()
        self._sync_view()

        self.root.after(50, self._pulse)
        self.root.after(100, self._drain)

    # ------------------------------------------------------------ 구성

    def _init_fonts(self):
        self._base_fonts = []

        def font(families, size, weight="normal"):
            chosen = pick_font(self.root, families, size, weight)
            self._base_fonts.append((chosen, size, chosen.metrics("linespace")))
            return chosen

        self.f_banner = font(UI_FAMILIES, 48, "bold")
        self.f_banner_sub = font(MONO_FAMILIES, 38, "bold")
        # 폴더 이름 길이에 맞춰 골라 쓰는 크기들입니다. 첫 번째가 기본입니다.
        self.f_folder_sizes = [font(UI_FAMILIES, size, "bold")
                               for size in (42, 36, 30, 24)]
        self.f_folder = self.f_folder_sizes[0]
        self.f_value = font(UI_FAMILIES, 22)
        self.f_value_mono = font(MONO_FAMILIES, 38)
        self.f_sub_mono = font(MONO_FAMILIES, 28)
        self.f_label = font(UI_FAMILIES, 13)
        self.f_summary = font(UI_FAMILIES, 15)
        self.f_mono = font(MONO_FAMILIES, 12)
        self.f_status = font(UI_FAMILIES, 11)
        self.f_version = font(UI_FAMILIES, 10)
        # 각 행의 기준 높이는 96 DPI 글꼴 실측치입니다. 세로 화면에서도 정보가
        # 위쪽에 몰리지 않도록 글자 크기와 별도로 행 간격을 비례 배분합니다.
        label_h = self.f_label.metrics("linespace")
        self._detail_rows = (
            8 + label_h + self.f_folder.metrics("linespace"),
            8 + label_h + self.f_value_mono.metrics("linespace"),
            8 + label_h + self.f_sub_mono.metrics("linespace"),
            6 + self.f_summary.metrics("linespace"),
        )
        self._log_title_h = label_h
        self._log_row_h = self.f_mono.metrics("linespace")
        self._status_h = self.f_status.metrics("linespace")

    def _label(self, parent, text, font, bg, fg):
        """줄 높이를 예측할 수 있도록 여백과 테두리를 모두 없앤 라벨을 만듭니다."""
        return tk.Label(parent, text=text, font=font, bg=bg, fg=fg,
                        anchor="w", bd=0, padx=0, pady=0,
                        highlightthickness=0)

    def _build_banner(self):
        self.banner = tk.Canvas(self.root, width=WIN_W, height=H_BANNER,
                                bg=C_IDLE, highlightthickness=0, bd=0)
        self.banner.pack(side="top", fill="x")
        self.dot = self.banner.create_oval(56, 36, 124, 104,
                                           fill=C_IDLE_DOT, outline="")
        self.banner_text = self.banner.create_text(
            152, 70, text="대기중", anchor="w", fill=C_DIM, font=self.f_banner)
        self.banner_sub = self.banner.create_text(
            WIN_W - 36, 70, text="", anchor="e", fill=C_DIM,
            font=self.f_banner_sub)
        self._build_buttons()

    def _build_buttons(self):
        """타이틀바가 없으므로 환경설정·전체화면·닫기를 배너 안에 그려 넣습니다."""
        self.images = {
            "settings": (tk.PhotoImage(data=icons.SETTINGS_DIM),
                         tk.PhotoImage(data=icons.SETTINGS_LIT)),
            "full": (tk.PhotoImage(data=icons.FULLSCREEN_DIM),
                     tk.PhotoImage(data=icons.FULLSCREEN_LIT)),
            "restore": (tk.PhotoImage(data=icons.RESTORE_DIM),
                        tk.PhotoImage(data=icons.RESTORE_LIT)),
            "close": (tk.PhotoImage(data=icons.CLOSE_DIM),
                      tk.PhotoImage(data=icons.CLOSE_LIT)),
        }
        self._base_images = self.images
        self._icon_size = self.images["close"][0].width()
        self.buttons = {
            name: self.banner.create_image(0, 12, anchor="ne",
                                           image=self.images[name][0])
            for name in BUTTON_ORDER
        }
        self._banner_width = WIN_W
        self._hovered = None
        self._place_banner_items()
        self.banner.bind("<Configure>", self._place_banner_items)
        self.banner.bind("<Button-1>", self._banner_click)
        self.banner.bind("<Motion>", self._banner_hover)
        self.banner.bind("<Leave>", lambda _event: self._banner_hover(None))

    def _place_banner_items(self, _event=None):
        """전체화면으로 넓어져도 버튼이 오른쪽 위에 붙어 있도록 옮깁니다."""
        width = self.banner.winfo_width()
        self._banner_width = width if width > 1 else WIN_W
        sx, sy = self._scale_x, self._scale_y
        radius = 34 * min(sx, sy)
        self.banner.coords(self.dot, 90 * sx - radius, 70 * sy - radius,
                           90 * sx + radius, 70 * sy + radius)
        self.banner.coords(self.banner_text, 152 * sx, 70 * sy)
        for index, name in enumerate(BUTTON_ORDER):
            self.banner.coords(self.buttons[name],
                               self._banner_width - (12 + index * BUTTON_W) * sx,
                               12 * sy)
        self.banner.coords(self.banner_sub, self._banner_width - 36 * sx, 70 * sy)

    def _corner_hit(self, x, y):
        if y < 0 or y > BUTTON_ZONE_H * self._scale_y:
            return None
        for index, name in enumerate(BUTTON_ORDER):
            right = self._banner_width - (4 + index * BUTTON_W) * self._scale_x
            if right - BUTTON_W * self._scale_x <= x < right:
                return name
        return None

    def _icon_for(self, name, lit):
        """전체화면 버튼은 상태에 따라 다른 그림을 씁니다."""
        key = "restore" if (name == "full" and self.fullscreen) else name
        return self.images[key][1 if lit else 0]

    def _banner_hover(self, event):
        hit = self._corner_hit(event.x, event.y) if event else None
        if hit == self._hovered:
            return
        self._hovered = hit
        for name in BUTTON_ORDER:
            self.banner.itemconfigure(self.buttons[name],
                                      image=self._icon_for(name, name == hit))

    def _banner_click(self, event):
        hit = self._corner_hit(event.x, event.y)
        if hit == "close":
            if self.close_callback:
                self.close_callback()
            return "break"
        if hit == "full":
            self.toggle_fullscreen()
            return "break"
        if hit == "settings":
            self.open_settings()
            return "break"
        return None

    def _cell(self, parent, row, col, title, value_font, color=C_FG):
        pad = (24, 12) if col == 0 else (12, 24)
        holder = tk.Frame(parent, bg=C_BG, bd=0, highlightthickness=0)
        holder.grid(row=row, column=col, sticky="we", padx=pad, pady=(8, 0))
        self._cell_holders.append((holder, pad))
        self._label(holder, title, self.f_label, C_BG, C_MUTED).pack(fill="x")
        value = self._label(holder, "—", value_font, C_BG, color)
        value.pack(fill="x")
        return value

    def _build_detail(self):
        body = tk.Frame(self.root, bg=C_BG, height=H_DETAIL, bd=0,
                        highlightthickness=0)
        self.detail = body
        body.pack(side="top", fill="x")
        # 자식이 grid 로 배치되므로 grid_propagate 를 꺼야 높이가 고정됩니다.
        body.grid_propagate(False)
        body.columnconfigure(0, weight=1, uniform="col")
        body.columnconfigure(1, weight=1, uniform="col")

        self.v_folder = self._cell(body, 0, 0, "저장 폴더", self.f_folder)
        self.v_file = self._cell(body, 0, 1, "파일명", self.f_value)
        self.v_elapsed = self._cell(body, 1, 0, "경과 시간", self.f_value_mono)
        self.v_size = self._cell(body, 1, 1, "용량", self.f_value_mono)
        self.v_rate = self._cell(body, 2, 0, "비트레이트", self.f_sub_mono)
        self.v_growth = self._cell(body, 2, 1, "마지막 증가", self.f_sub_mono)

        self.v_summary = self._label(body, "", self.f_summary, C_BG, C_MUTED)
        self.v_summary.grid(row=3, column=0, columnspan=2, sticky="we",
                            padx=24, pady=(6, 0))

    def _build_log(self):
        frame = tk.Frame(self.root, bg=C_PANEL, height=H_LOG, bd=0,
                         highlightthickness=0)
        self.log_frame = frame
        # 전체화면에서는 모든 영역을 함께 확대합니다. 로그만 expand=True 로
        # 남는 공간을 가져가거나 H_LOG 픽셀로 고정하면 전체 화면의 비율이 깨집니다.
        frame.pack(side="top", fill="x", padx=16, pady=(4, 0))
        frame.pack_propagate(False)
        self.log_title = self._label(frame, "이벤트 로그", self.f_label,
                                     C_PANEL, C_MUTED)
        self.log_labels = []
        for _ in range(LOG_ROWS):
            row = self._label(frame, "", self.f_mono, C_PANEL, C_MUTED)
            self.log_labels.append(row)

    def _build_status(self):
        row = tk.Frame(self.root, bg=C_BG, bd=0, highlightthickness=0)
        self.status_row = row
        row.pack(side="bottom", fill="x", padx=18, pady=(3, 5))
        self.status = self._label(row, "", self.f_status, C_BG, C_MUTED)
        self.status.pack(side="left", fill="x", expand=True)
        self.version_label = tk.Label(row, text=version.label(),
                                      font=self.f_version, bg=C_BG,
                                      fg="#5c5c66", anchor="e", bd=0, padx=0,
                                      pady=0, highlightthickness=0)
        self.version_label.pack(side="right")

    def _enable_drag(self):
        """타이틀바가 없을 때 창의 아무 곳이나 잡아 옮길 수 있게 합니다."""

        def press(event):
            # 초점을 주지 않으면 Esc 나 F11 이 창에 닿지 않습니다.
            try:
                self.root.focus_force()
            except tk.TclError:
                pass
            self._drag_x = event.x_root - self.root.winfo_x()
            self._drag_y = event.y_root - self.root.winfo_y()

        def move(event):
            if self.fullscreen or not self.borderless:
                return
            self.root.geometry("+%d+%d" % (event.x_root - self._drag_x,
                                           event.y_root - self._drag_y))

        self._drag_x = self._drag_y = 0
        self.root.bind("<Button-1>", press)
        self.root.bind("<B1-Motion>", move)

    def attach_close(self, callback):
        """배너의 ✕ 말고 키보드로도 닫을 수 있게 연결합니다."""
        self.close_callback = callback
        self.root.bind("<Escape>", self._on_escape)
        self.root.bind("<F11>", self.toggle_fullscreen)
        self.root.bind("<Double-Button-3>", callback)

    def _on_escape(self, _event=None):
        # 전체화면일 때는 먼저 창 크기로 돌아옵니다.
        if self.fullscreen:
            return self.toggle_fullscreen()
        if self.close_callback:
            self.close_callback()
        return "break"

    # ------------------------------------------------------------ 창 상태

    def _resize_layout(self, event):
        """960x640 의 영역 비율을 유지하며 실제 창 크기에 맞춥니다.

        좌우·상하 간격은 각 축의 배율을 쓰고, 글자·원·아이콘은 작은 배율을
        공통으로 써서 화면비가 달라도 찌그러지거나 잘리지 않게 합니다.
        매번 기준값에서 계산해야 전체화면 전환을 반복해도 반올림이 누적되지 않습니다.
        Tk 전체의 scaling 은 환경설정 창까지 바꾸므로 건드리지 않습니다.
        """
        size = (event.width, event.height)
        if event.widget is not self.root or min(size) <= 1 or size == self._layout_size:
            return
        self._layout_size = size
        if self.wallpaper is not None:
            self.wallpaper.resize(event.width, event.height)
            if self.wallpaper.running:
                # 월페이퍼가 떠 있는 동안에는 감지 화면 위젯이 붙어 있지
                # 않으므로 아래 계산을 할 필요가 없습니다.
                return
        sx, sy = event.width / WIN_W, event.height / WIN_H
        self._scale_x, self._scale_y = sx, sy
        scale = min(sx, sy)
        x = lambda value: round(value * sx)
        y = lambda value: round(value * sy)
        for font, points, line_height in self._base_fonts:
            # 음수 크기는 픽셀 단위입니다. 정수 pt 로 반올림하는 오차를 줄입니다.
            if scale == 1:
                font.configure(size=points)
                continue
            pixels = max(1, round(points * (96 / 72) * scale))
            font.configure(size=-pixels)
            # 글꼴의 픽셀 반올림으로 행보다 1~2px 커지는 경우도 보정합니다.
            while pixels > 1 and font.metrics("linespace") > round(line_height * scale):
                pixels -= 1
                font.configure(size=-pixels)

        self.banner.configure(height=y(H_BANNER))
        self.detail.configure(height=y(H_DETAIL))
        for index, height in enumerate(self._detail_rows):
            self.detail.rowconfigure(index, minsize=y(height) if sy != 1 else 0)
        for holder, pad in self._cell_holders:
            holder.grid_configure(padx=tuple(x(p) for p in pad), pady=(y(8), 0))
        self.v_summary.grid_configure(padx=x(24), pady=(y(6), 0))

        self.log_frame.configure(height=y(H_LOG))
        self.log_frame.pack_configure(padx=x(16), pady=(y(4), 0))
        # 행 높이도 확대해야 세로로 긴 모니터에서 로그가 위에 몰리지 않습니다.
        self.log_title.place(x=x(12), y=y(6), relwidth=1, width=-x(24),
                             height=y(self._log_title_h))
        for index, label in enumerate(self.log_labels):
            label.place(x=x(12), y=y(8 + self._log_title_h + index * self._log_row_h),
                        relwidth=1, width=-x(24), height=y(self._log_row_h))
        self.status_row.configure(height=y(self._status_h))
        self.status_row.pack_propagate(False)
        self.status_row.pack_configure(padx=x(18), pady=(y(3), y(5)))

        # PhotoImage 원본을 보존해 확대/복원을 반복해도 화질과 크기가 누적되지 않습니다.
        source_size = self._base_images["close"][0].width()
        icon_size = max(1, round(source_size * scale))
        if icon_size != self._icon_size:
            factor = math.gcd(icon_size, source_size)
            self.images = {
                name: tuple(photo.zoom(icon_size // factor).subsample(source_size // factor)
                            for photo in pair)
                for name, pair in self._base_images.items()
            } if icon_size != source_size else self._base_images
            self._icon_size = icon_size
            for name in BUTTON_ORDER:
                self.banner.itemconfigure(self.buttons[name],
                                          image=self._icon_for(name, name == self._hovered))
        self._show_folder(self._folder_text, self.v_folder.cget("fg"))
        self._place_banner_items()

    def _set_window_rect(self, left, top, width, height):
        # resizable(False) 는 창 크기를 못으로 박아 두므로 잠시 풀고 옮깁니다.
        self.root.resizable(True, True)
        self.root.geometry("%dx%d+%d+%d" % (width, height, left, top))
        self.root.update_idletasks()
        self.root.resizable(False, False)

    def toggle_fullscreen(self, _event=None):
        """창이 놓인 모니터를 가득 채웁니다. 타이틀바에 잘리는 부분이 없어집니다.

        tkinter 의 -fullscreen 속성은 주 모니터를 채워 버리기 때문에 쓰지 않고,
        창이 올라가 있는 모니터의 좌표를 직접 구해서 맞춥니다.
        """
        target = not self.fullscreen
        try:
            if target:
                center_x = self.root.winfo_x() + self.root.winfo_width() // 2
                center_y = self.root.winfo_y() + self.root.winfo_height() // 2
                rect = monitor_for_point(center_x, center_y)
                if rect is None:
                    log("[표시] 창이 놓인 모니터를 찾지 못했습니다.")
                    return "break"
                self.saved_rect = (self.root.winfo_x(), self.root.winfo_y(),
                                   WIN_W, WIN_H)
                self.root.overrideredirect(True)
                self._set_window_rect(*rect)
            else:
                self.root.overrideredirect(self.borderless)
                self._set_window_rect(*self.saved_rect)
        except tk.TclError as exc:
            log("[표시] 전체화면 전환에 실패했습니다: %s" % exc)
            return "break"
        self.fullscreen = target
        self._hovered = None
        self.banner.itemconfigure(self.buttons["full"],
                                  image=self._icon_for("full", False))
        self.root.after(50, self._place_banner_items)
        return "break"

    def open_settings(self):
        SettingsDialog(self.root, self.settings, self._settings_saved)

    def _settings_saved(self, settings):
        previous = self.settings
        self.settings = dict(settings)
        self.dirs = settings["dirs"]
        self.interval = settings["interval"]
        try:
            self.root.attributes("-topmost", settings["topmost"])
            if settings["borderless"] != self.borderless and not self.fullscreen:
                self.root.overrideredirect(settings["borderless"])
            self.borderless = settings["borderless"]
            if settings["monitor"] != previous["monitor"] and not self.fullscreen:
                spot = window_position(settings["monitor"])
                if spot:
                    self._set_window_rect(spot[0], spot[1], WIN_W, WIN_H)
        except tk.TclError as exc:
            log("[표시] 창 설정을 적용하지 못했습니다: %s" % exc)
        self.add_log("[설정] 환경설정을 저장하고 감시를 다시 시작했습니다.", C_SKY)
        self._refresh_status()
        if self.settings_callback:
            self.settings_callback(settings)
        if any(settings.get(key) != previous.get(key) for key in
               ("latitude", "longitude", "wallpaper_fps")):
            self._leave_wallpaper()
            self._sync_view()

    # ------------------------------------------------------------ 갱신

    def _pulse(self):
        if self.recording and not self.hidden_to_tray and self.banner.winfo_ismapped():
            phase = (time.time() % 1.0) * 2.0 * math.pi
            k = 0.5 - 0.5 * math.cos(phase)
            self.banner.configure(bg=mix(C_REC_DIM, C_REC, k))
            self.banner.itemconfigure(self.dot, fill=mix("#ff8787", "#ffffff", k))
        self.root.after(50, self._pulse)

    # ------------------------------------------------------------ 월페이퍼

    def _ensure_wallpaper(self):
        if self.wallpaper is None:
            self.wallpaper = WallpaperView(
                self.root, self.settings,
                self.root.winfo_width() if self.root.winfo_width() > 1 else WIN_W,
                self.root.winfo_height() if self.root.winfo_height() > 1 else WIN_H,
                actions={"settings": self.open_settings,
                         "full": self.toggle_fullscreen,
                         "close": lambda: self.close_callback() if self.close_callback else None})

    def _sync_view(self):
        """지금 보여야 할 화면을 정합니다.

        월페이퍼를 쓰는 동안에는 캔버스 하나가 두 화면을 모두 맡습니다.
        배경을 그대로 둔 채 내용만 갈아 끼우므로 전환이 이어져 보입니다.
        """
        if self.hidden_to_tray:
            return
        self._ensure_wallpaper()
        mode = "rec" if self.recording else "wall"
        self._enter_wallpaper()
        self._sync_sources(mode == "wall")
        self.wallpaper.set_mode(mode)
        if mode == "rec":
            self._refresh_wall_status()

    def _sync_sources(self, want):
        """소리와 음악, 날씨 스레드는 월페이퍼 화면에서만 돌립니다."""
        self._reap_sources()
        if want and self._wall_audio is None:
            self._wall_audio = AudioLevels(
                fps=self.settings.get("wallpaper_fps", 30))
            self._wall_audio.start()
            self._wall_track = NowPlaying(interval=1.0)
            self._wall_track.start()
            self._wall_weather = WeatherWatch(
                self.settings.get("latitude", 37.5665),
                self.settings.get("longitude", 126.9780))
            self._wall_weather.start()
            self.wallpaper.set_sources(self._wall_audio, self._wall_track,
                                       self._wall_weather)
        elif not want and self._wall_audio is not None:
            self._stop_sources()

    def _reap_sources(self):
        """종료 신호 뒤 정리 중인 공급자만 잠시 참조합니다."""
        self._retired_sources = [thread for thread in self._retired_sources
                                 if getattr(thread, "is_alive", lambda: False)()]

    def _stop_sources(self, wait=0.0):
        threads = tuple(thread for thread in
                        (self._wall_audio, self._wall_track, self._wall_weather)
                        if thread is not None)
        for thread in threads:
            thread.stop()
        if wait:
            deadline = time.monotonic() + wait
            for thread in threads:
                join = getattr(thread, "join", None)
                if join and getattr(thread, "is_alive", lambda: False)():
                    join(max(0.0, deadline - time.monotonic()))
        self._retired_sources.extend(
            thread for thread in threads
            if getattr(thread, "is_alive", lambda: False)())
        self._wall_audio = self._wall_track = self._wall_weather = None
        if self.wallpaper is not None:
            self.wallpaper.set_sources(None, None, None)
        self._reap_sources()

    def _refresh_wall_status(self):
        """녹화 화면 맨 아래 줄입니다."""
        if self.wallpaper is None:
            return
        shown = _short_path(self.dirs[0]) if self.dirs else "(감시 폴더 없음)"
        text = "감시 %s   ·   주기 %.1f초   ·   갱신 %s   ·   세션 누적 %d회" % (
            shown, self.interval, self.last_update, self.session_count)
        if self.warning:
            text += "   ·   " + self.warning
        self.wallpaper.set_status(text, version.label())

    def hide_window(self):
        self.hidden_to_tray = True
        self.root.withdraw()
        self._leave_wallpaper()

    def show_window(self):
        self.hidden_to_tray = False
        self.root.deiconify()
        self._sync_view()
        self.root.lift()
        self.root.focus_force()

    def _enter_wallpaper(self):
        """캔버스 화면을 켭니다. 월페이퍼와 녹화 화면을 여기에 그립니다."""
        if self.hidden_to_tray or self.wallpaper is None or self.wallpaper.running:
            return
        for widget in (self.banner, self.detail, self.log_frame, self.status_row):
            widget.pack_forget()
        self.wallpaper.start()

    def _leave_wallpaper(self):
        """캔버스를 걷어내고 예전 위젯 화면으로 되돌립니다.

        월페이퍼를 끄거나 창을 닫을 때만 씁니다. 녹화로 넘어갈 때는 캔버스를
        그대로 둔 채 :meth:`WallpaperView.set_mode` 로 내용만 바꿉니다.
        """
        if self.wallpaper is None or not self.wallpaper.running:
            return
        self.wallpaper.stop()
        self.wallpaper.canvas.pack_forget()
        self._sync_sources(False)
        # 원래 순서대로 다시 쌓습니다. 상태 표시줄만 아래쪽에 붙습니다.
        self.banner.pack(side="top", fill="x")
        self.detail.pack(side="top", fill="x")
        self.log_frame.pack(side="top", fill="x", padx=16, pady=(4, 0))
        self.status_row.pack(side="bottom", fill="x", padx=18, pady=(3, 5))
        self._layout_size = None
        self.root.update_idletasks()
        self._resize_layout(_FakeConfigure(self.root))

    def stop_wallpaper(self):
        """창을 닫을 때 부릅니다."""
        if self.wallpaper is None:
            self._stop_sources(.5)
            return
        if self.wallpaper.running:
            self._leave_wallpaper()
        self._stop_sources(.5)
        self.wallpaper.destroy()
        self.wallpaper = None

    def _set_recording(self, active):
        if active == self.recording:
            return
        self.recording = active
        if active:
            self.banner.itemconfigure(self.banner_text, text="녹화중",
                                      fill="#ffffff")
        else:
            self.banner.configure(bg=C_IDLE)
            self.banner.itemconfigure(self.dot, fill=C_IDLE_DOT)
            self.banner.itemconfigure(self.banner_text, text="대기중",
                                      fill=C_DIM)
            self.banner.itemconfigure(self.banner_sub, text="", fill=C_DIM)
        self._sync_view()

    def _show_folder(self, text, color):
        """폴더 이름이 길면 자르지 않고 글자 크기를 줄여서 끝까지 보여 줍니다."""
        self._folder_text = text
        chosen = self.f_folder_sizes[-1]
        for font in self.f_folder_sizes:
            if font.measure(text) <= FOLDER_MAX_PX * self._scale_x:
                chosen = font
                break
        self.v_folder.config(text=ellipsize(text, 30), font=chosen, fg=color)

    def _apply_state(self, event):
        self._set_recording(bool(event.get("active")))
        if not event.get("active"):
            return
        path = event["path"]
        self._show_folder(folder_label(path, self.dirs), C_FG)
        self.v_file.config(text=ellipsize(os.path.basename(path), 26), fg=C_FG)
        self.v_elapsed.config(text=hms(event["elapsed"]), fg=C_FG)
        self.v_size.config(text=human(event["size"]), fg=C_FG)
        mbps = event.get("mbps")
        self.v_rate.config(text="%.1f Mbps" % mbps if mbps else "측정 중",
                           fg=C_FG if mbps else C_MUTED)
        since = event["since_growth"]
        self.v_growth.config(text="%.1f 초 전" % since,
                             fg=growth_color(since, event["stall"]))
        self.v_summary.config(text="세션 누적 %d회" % self.session_count)
        self.banner.itemconfigure(self.banner_sub, text=hms(event["elapsed"]),
                                  fill="#ffffff")
        if self.wallpaper is not None and self.wallpaper.mode == "rec":
            self.wallpaper.show_recording(
                folder_label(path, self.dirs), hms(event["elapsed"]),
                human(event["size"]),
                "%.1f Mbps" % mbps if mbps else "측정 중",
                "%.1f초 전 증가" % since, os.path.basename(path))
            self._refresh_wall_status()

    def add_log(self, text, color, kind="", detail=""):
        stamp = time.strftime("%H:%M:%S")
        self.log_rows.appendleft((stamp + " " + text, color))
        for label, row in zip(self.log_labels, self.log_rows):
            label.config(text=ellipsize(row[0], 78), fg=row[1])
        # 새 화면은 시각과 종류, 내용을 나누어 색을 달리 칠합니다.
        self._wall_log.appendleft((stamp, kind, detail or text))
        if self.wallpaper is not None:
            self.wallpaper.set_log(list(self._wall_log))

    def _refresh_status(self):
        self._refresh_wall_status()
        shown = ellipsize(" · ".join(self.dirs) or "(감시 폴더 없음)", 58)
        text = "감시: %s     주기: %.1f초     갱신: %s" % (
            shown, self.interval, self.last_update)
        if self.warning:
            self.status.config(text=text + "     경고: " + self.warning,
                               fg=C_YELLOW)
        else:
            self.status.config(text=text, fg=C_MUTED)

    def _handle(self, event):
        kind = event.get("kind")
        if kind == "state":
            self.last_update = time.strftime("%H:%M:%S")
            self._apply_state(event)
            self._refresh_status()
        elif kind == "start":
            self._set_recording(True)
            shown = relative_path(event["path"], self.dirs)
            self.add_log("[시작] " + shown, C_REC_TEXT, "시작", shown)
        elif kind == "stop":
            self.session_count += 1
            name = event.get("final") or os.path.basename(event.get("path", ""))
            self.last_summary = "직전 녹화: %s · %s · %s" % (
                ellipsize(name, 30), hms(event["dur"]), human(event["peak"]))
            self.add_log("[중단] %s (%s, %s, %s)" % (
                relative_path(event.get("path", ""), self.dirs),
                event.get("reason", ""), hms(event["dur"]),
                human(event["peak"])), C_SKY, "중단",
                "%s · %s · %s" % (event.get("reason", ""), hms(event["dur"]),
                                  human(event["peak"])))
            self.last_record = {"name": name, "dur": event["dur"],
                                "peak": event["peak"],
                                "at": time.strftime("%H:%M")}
            self._set_recording(False)
        elif kind == "health":
            missing = event.get("missing") or []
            self.warning = ("폴더에 접근할 수 없습니다: "
                            + ellipsize(", ".join(missing), 48)) if missing else ""
            self._refresh_status()
        elif kind == "error":
            self.add_log("[오류] " + str(event.get("message", "")), C_YELLOW)

    def _drain(self):
        try:
            while True:
                self._handle(self.queue.get_nowait())
        except queue.Empty:
            pass
        except Exception:
            log("[UI 오류] " + traceback.format_exc().rstrip())
        finally:
            self.root.after(100, self._drain)
