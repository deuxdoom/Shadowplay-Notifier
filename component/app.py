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
from .display import monitor_for_point, window_position
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


class MonitorApp:
    def __init__(self, root, settings):
        self.root = root
        self.settings = dict(settings)
        self.dirs = settings["dirs"]
        self.interval = settings["interval"]
        self.borderless = settings["borderless"]

        self.close_callback = None
        self.settings_callback = None
        self.fullscreen = False
        self.saved_rect = (0, 0, WIN_W, WIN_H)
        self.queue = queue.Queue()
        self.stop_event = threading.Event()

        self.recording = False
        self.session_count = 0
        self.last_summary = "직전 녹화 기록이 없습니다."
        self.last_update = "--:--:--"
        self.warning = ""
        self.log_rows = deque(maxlen=LOG_ROWS)

        self._init_fonts()
        self._build_banner()
        self._build_detail()
        self._build_log()
        self._build_status()
        self._show_idle()
        self._refresh_status()
        self._enable_drag()

        self.root.after(50, self._pulse)
        self.root.after(100, self._drain)

    # ------------------------------------------------------------ 구성

    def _init_fonts(self):
        self.f_banner = pick_font(self.root, UI_FAMILIES, 48, "bold")
        self.f_banner_sub = pick_font(self.root, MONO_FAMILIES, 38, "bold")
        # 폴더 이름 길이에 맞춰 골라 쓰는 크기들입니다. 첫 번째가 기본입니다.
        self.f_folder_sizes = [pick_font(self.root, UI_FAMILIES, size, "bold")
                               for size in (42, 36, 30, 24)]
        self.f_folder = self.f_folder_sizes[0]
        self.f_value = pick_font(self.root, UI_FAMILIES, 22)
        self.f_value_mono = pick_font(self.root, MONO_FAMILIES, 38)
        self.f_sub_mono = pick_font(self.root, MONO_FAMILIES, 28)
        self.f_label = pick_font(self.root, UI_FAMILIES, 13)
        self.f_summary = pick_font(self.root, UI_FAMILIES, 15)
        self.f_mono = pick_font(self.root, MONO_FAMILIES, 12)
        self.f_status = pick_font(self.root, UI_FAMILIES, 11)
        self.f_version = pick_font(self.root, UI_FAMILIES, 10)

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
        for index, name in enumerate(BUTTON_ORDER):
            self.banner.coords(self.buttons[name],
                               self._banner_width - 12 - index * BUTTON_W, 12)
        self.banner.coords(self.banner_sub, self._banner_width - 36, 70)

    def _corner_hit(self, x, y):
        if y > BUTTON_ZONE_H:
            return None
        for index, name in enumerate(BUTTON_ORDER):
            right = self._banner_width - 4 - index * BUTTON_W
            if right - BUTTON_W <= x < right:
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
        self._label(holder, title, self.f_label, C_BG, C_MUTED).pack(fill="x")
        value = self._label(holder, "—", value_font, C_BG, color)
        value.pack(fill="x")
        return value

    def _build_detail(self):
        body = tk.Frame(self.root, bg=C_BG, height=H_DETAIL, bd=0,
                        highlightthickness=0)
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
        # 전체화면으로 넓어지면 로그 칸이 남는 공간을 가져가도록 둡니다.
        frame.pack(side="top", fill="both", expand=True, padx=16, pady=(4, 0))
        frame.pack_propagate(False)
        self._label(frame, "이벤트 로그", self.f_label, C_PANEL, C_MUTED).pack(
            fill="x", padx=12, pady=(6, 2))
        self.log_labels = []
        for _ in range(LOG_ROWS):
            row = self._label(frame, "", self.f_mono, C_PANEL, C_MUTED)
            row.pack(fill="x", padx=12)
            self.log_labels.append(row)

    def _build_status(self):
        row = tk.Frame(self.root, bg=C_BG, bd=0, highlightthickness=0)
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

    # ------------------------------------------------------------ 갱신

    def _pulse(self):
        if self.recording:
            phase = (time.time() % 1.0) * 2.0 * math.pi
            k = 0.5 - 0.5 * math.cos(phase)
            self.banner.configure(bg=mix(C_REC_DIM, C_REC, k))
            self.banner.itemconfigure(self.dot, fill=mix("#ff8787", "#ffffff", k))
        self.root.after(50, self._pulse)

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
            self._show_idle()

    def _show_folder(self, text, color):
        """폴더 이름이 길면 자르지 않고 글자 크기를 줄여서 끝까지 보여 줍니다."""
        chosen = self.f_folder_sizes[-1]
        for font in self.f_folder_sizes:
            if font.measure(text) <= FOLDER_MAX_PX:
                chosen = font
                break
        self.v_folder.config(text=ellipsize(text, 30), font=chosen, fg=color)

    def _show_idle(self):
        self._show_folder("대기 중", C_MUTED)
        self.v_file.config(text="—", fg=C_MUTED)
        self.v_elapsed.config(text="—", fg=C_MUTED)
        self.v_size.config(text="—", fg=C_MUTED)
        self.v_rate.config(text="—", fg=C_MUTED)
        self.v_growth.config(text="—", fg=C_MUTED)
        self.v_summary.config(
            text="%s   |   세션 누적 %d회" % (self.last_summary,
                                              self.session_count))

    def _apply_state(self, event):
        self._set_recording(bool(event.get("active")))
        if not event.get("active"):
            self._show_idle()
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

    def add_log(self, text, color):
        self.log_rows.appendleft((time.strftime("%H:%M:%S") + " " + text, color))
        for label, row in zip(self.log_labels, self.log_rows):
            label.config(text=ellipsize(row[0], 78), fg=row[1])

    def _refresh_status(self):
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
            self.add_log("[시작] " + relative_path(event["path"], self.dirs),
                         C_REC_TEXT)
        elif kind == "stop":
            self.session_count += 1
            name = event.get("final") or os.path.basename(event.get("path", ""))
            self.last_summary = "직전 녹화: %s · %s · %s" % (
                ellipsize(name, 30), hms(event["dur"]), human(event["peak"]))
            self.add_log("[중단] %s (%s, %s, %s)" % (
                relative_path(event.get("path", ""), self.dirs),
                event.get("reason", ""), hms(event["dur"]),
                human(event["peak"])), C_SKY)
            self._set_recording(False)
            self._show_idle()
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
