"""본 창의 화면 구성과 갱신입니다.

감시 스레드가 큐에 넣은 사건을 100ms 마다 꺼내어 화면에 반영합니다.
화면은 :class:`component.wallpaper.WallpaperView` 캔버스 하나가 모두 맡으며,
녹화를 기다리는 월페이퍼와 녹화 중 화면이 배경을 함께 쓰고 내용만 갈아 끼웁니다.
이 모듈은 창 상태와 설정, 자료를 대는 스레드를 그 캔버스에 이어 붙입니다.
"""

import os
import queue
import threading
import time
import tkinter as tk
import traceback
from collections import deque

from . import i18n, version
from .audio import AudioLevels
from .config import save_config, settings_to_config
from .display import monitor_for_point, window_position
from .i18n import tr
from .nowplaying import NowPlaying
from .recording_view import LOG_ROWS
from .wallpaper import WallpaperView
from .weather import WeatherWatch
from .paths import log
from .scan import human, hms
from .settings_dialog import SettingsDialog
from .text import ellipsize, folder_label, relative_path
from .theme import WIN_H, WIN_W


def _short_path(path):
    """경로가 길면 앞을 줄입니다. 뒤쪽 폴더 이름이 더 쓸모 있습니다."""
    parts = path.replace("/", "\\").rstrip("\\").split("\\")
    if len(parts) <= 3:
        return path
    return "…\\" + "\\".join(parts[-2:])


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
        self.log_rows = deque(maxlen=LOG_ROWS)
        self.last_update = "--:--:--"
        self.warning = ""
        self._layout_size = None

        self.wallpaper = None
        self._wall_audio = self._wall_track = self._wall_weather = None
        self._retired_sources = []

        self._enable_drag()
        self.root.bind("<Configure>", self._resize_layout, add="+")

        # 캔버스를 켭니다. 녹화가 잡히면 같은 캔버스에서 내용만 바뀝니다.
        # _sync_view 가 화면을 켜고 소리·음악·날씨 스레드까지 함께 시작합니다.
        self._ensure_wallpaper()
        self._sync_view()
        self._refresh_status()

        self.root.after(100, self._drain)

    # ------------------------------------------------------------ 창 상태

    def _enable_drag(self):
        """타이틀바가 없으므로 창의 아무 곳이나 잡아 옮길 수 있게 합니다."""

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

    def _resize_layout(self, event):
        """창 크기가 바뀌면 캔버스를 같은 크기로 맞춥니다.

        영역과 글자·아이콘을 실제 창 크기에 맞춰 다시 잡는 일은
        :meth:`component.wallpaper.WallpaperView.resize` 가 맡습니다.
        """
        size = (event.width, event.height)
        if event.widget is not self.root or min(size) <= 1 or size == self._layout_size:
            return
        self._layout_size = size
        if self.wallpaper is not None:
            self.wallpaper.resize(event.width, event.height)

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
        return "break"

    # ------------------------------------------------------------ 환경설정

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
        # 화면에 쓰는 말이 바뀌면 이미 적어 둔 글자까지 새 말로 갈아 끼웁니다.
        # 트레이 메뉴는 열 때마다 새로 만들므로 따로 손대지 않아도 됩니다.
        if settings.get("language") != previous.get("language"):
            i18n.set_language(settings.get("language"))
            if self.wallpaper is not None:
                self.wallpaper.refresh_language()
        # 도시 이름처럼 화면이 들고 있는 값을 새것으로 갈아 끼웁니다. 캔버스를
        # 새로 만들지는 않으므로, 여기에서 알려 주지 않으면 옛 값이 그대로 남습니다.
        if self.wallpaper is not None:
            self.wallpaper.apply_settings(self.settings)
        # 날씨는 좌표를, 소리 막대는 빠르기를 스레드를 세울 때 정합니다.
        # 그 값이 바뀌면 스레드를 다시 세워야 새 값으로 돕니다.
        if any(settings.get(key) != previous.get(key)
               for key in ("latitude", "longitude", "wallpaper_fps")):
            self._restart_sources()
        self.add_log("[설정] 환경설정을 저장하고 감시를 다시 시작했습니다.")
        self._refresh_status()
        if self.settings_callback:
            self.settings_callback(settings)

    # ------------------------------------------------------------ 화면

    def _ensure_wallpaper(self):
        if self.wallpaper is None:
            self.wallpaper = WallpaperView(
                self.root, self.settings,
                self.root.winfo_width() if self.root.winfo_width() > 1 else WIN_W,
                self.root.winfo_height() if self.root.winfo_height() > 1 else WIN_H,
                actions={"settings": self.open_settings,
                         "full": self.toggle_fullscreen,
                         "clock": self._clock_changed,
                         "close": lambda: self.close_callback() if self.close_callback else None})

    def _clock_changed(self, use_24h):
        """시계를 눌러 바꾼 24시간·12시간 표시를 설정 파일에 남깁니다."""
        self.settings["clock_24h"] = bool(use_24h)
        save_config(settings_to_config(self.settings))

    def _sync_view(self):
        """지금 보여야 할 화면을 정합니다.

        캔버스 하나가 두 화면을 모두 맡습니다. 배경을 그대로 둔 채 내용만
        갈아 끼우므로 전환이 이어져 보입니다.
        """
        if self.hidden_to_tray:
            return
        self._ensure_wallpaper()
        mode = "rec" if self.recording else "wall"
        self._start_wallpaper()
        self._sync_sources(mode == "wall")
        self.wallpaper.set_mode(mode)
        if mode == "rec":
            self._refresh_status()

    def _start_wallpaper(self):
        if self.hidden_to_tray or self.wallpaper is None or self.wallpaper.running:
            return
        self.wallpaper.start()

    def _pause_wallpaper(self):
        """창을 감출 때 그리기와 자료 수집을 함께 멈춥니다."""
        if self.wallpaper is not None and self.wallpaper.running:
            self.wallpaper.stop()
        self._sync_sources(False)

    def stop_wallpaper(self):
        """창을 닫을 때 부릅니다."""
        if self.wallpaper is None:
            self._stop_sources(.5)
            return
        self._pause_wallpaper()
        self._stop_sources(.5)
        self.wallpaper.destroy()
        self.wallpaper = None

    def hide_window(self):
        self.hidden_to_tray = True
        self.root.withdraw()
        self._pause_wallpaper()

    def show_window(self):
        self.hidden_to_tray = False
        self.root.deiconify()
        self._sync_view()
        self.root.lift()
        self.root.focus_force()

    # ------------------------------------------------------------ 자료 공급

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

    def _restart_sources(self):
        """좌표나 빠르기가 바뀌면 공급 스레드를 새 값으로 다시 세웁니다."""
        if self._wall_audio is None:
            return
        self._stop_sources()
        self._sync_sources(self.wallpaper is not None
                           and self.wallpaper.mode == "wall")

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

    # ------------------------------------------------------------ 갱신

    def _refresh_status(self):
        """녹화 화면 맨 아래 한 줄입니다."""
        if self.wallpaper is None:
            return
        shown = _short_path(self.dirs[0]) if self.dirs else tr("(감시 폴더 없음)")
        text = tr("감시 %s   ·   주기 %.1f초   ·   갱신 %s   ·   세션 누적 %d회") % (
            shown, self.interval, self.last_update, self.session_count)
        if self.warning:
            text += "   ·   " + self.warning
        self.wallpaper.set_status(text, version.label())

    def add_log(self, text, kind="", detail=""):
        """이벤트 로그에 한 줄 올립니다.

        ``kind`` 는 색을 고르는 데 쓰는 한국어 원문(``시작``·``중단``)이며,
        화면에 적을 때에만 쓰는 말로 옮깁니다. ``detail`` 을 주면 그것을 적고
        없으면 ``text`` 를 그대로 적습니다.
        """
        self.log_rows.appendleft(
            (time.strftime("%H:%M:%S"), kind, detail or text))
        if self.wallpaper is not None:
            self.wallpaper.set_log(list(self.log_rows))

    def _set_recording(self, active):
        if active == self.recording:
            return
        self.recording = active
        self._sync_view()

    def _apply_state(self, event):
        self._set_recording(bool(event.get("active")))
        if not event.get("active"):
            return
        if self.wallpaper is None or self.wallpaper.mode != "rec":
            return
        path = event["path"]
        mbps = event.get("mbps")
        since = event["since_growth"]
        self.wallpaper.show_recording(
            folder_label(path, self.dirs), hms(event["elapsed"]),
            human(event["size"]),
            "%.1f Mbps" % mbps if mbps else tr("측정 중"),
            tr("%.1f초 전 증가") % since, os.path.basename(path))
        self._refresh_status()

    def _handle(self, event):
        kind = event.get("kind")
        if kind == "state":
            self.last_update = time.strftime("%H:%M:%S")
            self._apply_state(event)
            self._refresh_status()
        elif kind == "start":
            self._set_recording(True)
            shown = relative_path(event["path"], self.dirs)
            self.add_log("[시작] " + shown, "시작", shown)
        elif kind == "stop":
            self.session_count += 1
            self.add_log("[중단]", "중단", "%s · %s · %s" % (
                tr(event.get("reason", "")), hms(event["dur"]),
                human(event["peak"])))
            self._set_recording(False)
        elif kind == "health":
            missing = event.get("missing") or []
            self.warning = (tr("폴더에 접근할 수 없습니다: ")
                            + ellipsize(", ".join(missing), 48)) if missing else ""
            self._refresh_status()
        elif kind == "error":
            self.add_log("[오류] " + str(event.get("message", "")))

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
