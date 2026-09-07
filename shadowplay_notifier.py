#!/usr/bin/env python3
"""
shadowplay_notifier.py  (v3)

ShadowPlay(NVIDIA App) 녹화 상태를 감시해 보조 디스플레이용 GUI로 표시합니다.
감지 로직(scan / tick / _start / _stop)은 v2 와 동일하며 출력부만 교체했습니다.
런타임 의존성은 표준 라이브러리와 tkinter 뿐입니다.
"""

import argparse
import ctypes
import json
import math
import os
import queue
import sys
import threading
import time
import traceback
import urllib.error
import urllib.request
from collections import deque
from dataclasses import dataclass, field

import tkinter as tk
from tkinter import font as tkfont

try:
    import winsound
except ImportError:
    winsound = None

DEFAULT_SERVER = "https://ntfy.sh"
DEFAULT_PATTERNS = (".tmp", ".mp4", ".mkv")

WIN_W, WIN_H = 960, 640

# 960x640 안에서 세로로 잘리지 않도록 각 영역의 높이를 실측치 기준으로 고정합니다.
H_BANNER = 140
H_DETAIL = 236
H_LOG = 226
LOG_ROWS = 10

C_BG = "#0d0d0f"
C_PANEL = "#16161a"
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


# ---------------------------------------------------------------- 경로와 로그

def base_dir():
    """PyInstaller onefile 로 묶어도 EXE 가 놓인 폴더를 돌려줍니다."""
    if getattr(sys, "frozen", False):
        return os.path.dirname(sys.executable)
    return os.path.dirname(os.path.abspath(__file__))


BASE_DIR = base_dir()
CONFIG_PATH = os.path.join(BASE_DIR, "config.json")
LOG_PATH = os.path.join(BASE_DIR, "monitor.log")

_log_lock = threading.Lock()


def log(msg):
    line = "%s  %s" % (time.strftime("%Y-%m-%d %H:%M:%S"), msg)
    with _log_lock:
        try:
            with open(LOG_PATH, "a", encoding="utf-8") as fp:
                fp.write(line + "\n")
        except OSError:
            pass


def install_excepthook():
    def hook(exc_type, exc, tb):
        log("[예외] " + "".join(
            traceback.format_exception(exc_type, exc, tb)).rstrip())

    sys.excepthook = hook

    def thread_hook(info):
        log("[스레드 예외] " + "".join(traceback.format_exception(
            info.exc_type, info.exc_value, info.exc_traceback)).rstrip())

    if hasattr(threading, "excepthook"):
        threading.excepthook = thread_hook


# ---------------------------------------------------------------- 설정 파일

DEFAULT_CONFIG = {
    "dir": "E:\\shadowplay record",
    "interval": 1.0,
    "stall": 8.0,
    "min_size": 1048576,
    "beep": True,
    "topmost": False,
    "borderless": False,
    "monitor": 0,
    "ntfy_server": "",
    "ntfy_topic": "",
}


def load_config():
    cfg = dict(DEFAULT_CONFIG)
    if os.path.isfile(CONFIG_PATH):
        try:
            with open(CONFIG_PATH, "r", encoding="utf-8") as fp:
                user = json.load(fp)
            if isinstance(user, dict):
                cfg.update(user)
            else:
                log("[설정] config.json 최상위가 객체가 아니어서 기본값을 사용합니다.")
        except (OSError, ValueError) as exc:
            log("[설정] config.json 을 읽지 못해 기본값을 사용합니다: %s" % exc)
    else:
        try:
            with open(CONFIG_PATH, "w", encoding="utf-8") as fp:
                json.dump(DEFAULT_CONFIG, fp, ensure_ascii=False, indent=2)
                fp.write("\n")
            log("[설정] 기본 config.json 을 생성했습니다: %s" % CONFIG_PATH)
        except OSError as exc:
            log("[설정] config.json 을 생성하지 못했습니다: %s" % exc)
    return cfg


# ---------------------------------------------------------------- 알림 전송

def notify(servers, topic, title, message, priority=3, tags=None, token=""):
    payload = {"topic": topic, "title": title,
               "message": message, "priority": priority}
    if tags:
        payload["tags"] = list(tags)
    data = json.dumps(payload, ensure_ascii=False).encode("utf-8")

    ok_any = False
    for server in servers:
        req = urllib.request.Request(
            server.rstrip("/"), data=data,
            headers={"Content-Type": "application/json; charset=utf-8"},
            method="POST",
        )
        if token:
            req.add_header("Authorization", f"Bearer {token}")
        try:
            with urllib.request.urlopen(req, timeout=10) as resp:
                ok_any = ok_any or (200 <= resp.status < 300)
        except (urllib.error.URLError, urllib.error.HTTPError, OSError) as exc:
            log("[알림 실패] %s: %s" % (server, exc))
    return ok_any


# ---------------------------------------------------------------- 파일 관찰

def scan(dirs, patterns, min_size, recursive=True):
    found = {}
    for root_dir in dirs:
        if not os.path.isdir(root_dir):
            continue
        if recursive:
            walker = os.walk(root_dir)
        else:
            walker = [(root_dir, [], os.listdir(root_dir))]
        for cur, _subdirs, files in walker:
            for name in files:
                low = name.lower()
                if patterns and not any(low.endswith(p) for p in patterns):
                    continue
                path = os.path.join(cur, name)
                try:
                    size = os.path.getsize(path)
                except OSError:
                    continue
                if size >= min_size:
                    found[path] = size
    return found


def human(n):
    n = float(n)
    for unit in ("B", "KB", "MB", "GB"):
        if n < 1024 or unit == "GB":
            return f"{int(n)} B" if unit == "B" else f"{n:.1f} {unit}"
        n /= 1024
    return f"{n:.1f} GB"


def hms(seconds):
    s = int(seconds)
    return f"{s // 3600:d}:{(s % 3600) // 60:02d}:{s % 60:02d}"


def sound(kind, enabled):
    if not enabled or winsound is None:
        return
    try:
        if kind == "start":
            winsound.Beep(880, 120)
        else:
            winsound.Beep(523, 180)
    except Exception:
        pass


# ---------------------------------------------------------------- 상태 기계

@dataclass
class Watcher:
    dirs: list
    outdirs: list
    patterns: tuple
    servers: list
    topic: str
    token: str = ""
    interval: float = 1.0
    min_growth: int = 256 * 1024
    stall: float = 8.0
    heartbeat: float = 0.0
    min_size: int = 1024 * 1024
    recursive: bool = True
    beep: bool = True
    sink: object = None

    _sizes: dict = field(default_factory=dict)
    _outfiles: set = field(default_factory=set)
    _active: str = ""
    _started_at: float = 0.0
    _last_growth: float = 0.0
    _last_beat: float = 0.0
    _peak: int = 0
    _start_size: int = 0

    def emit(self, **event):
        if self.sink is not None:
            self.sink(event)

    def _push(self, title, message, priority, tags):
        if not self.topic:
            return
        notify(self.servers, self.topic, title, message,
               priority=priority, tags=tags, token=self.token)

    def _start(self, path, size):
        self._active = path
        now = time.time()
        self._started_at = now
        self._last_growth = now
        self._last_beat = now
        self._peak = size
        self._start_size = size
        log("녹화 시작 감지 -> %s" % path)
        self.emit(kind="start", path=path, size=size, at=now)
        sound("start", self.beep)
        self._push("녹화 시작", os.path.basename(path), 3, ["red_circle"])

    def _stop(self, reason, final_name=""):
        dur = time.time() - self._started_at
        path = self._active
        peak = self._peak
        body = f"경과 {hms(dur)} / 용량 {human(peak)}"
        if final_name:
            body += f"\n{final_name}"
        log("녹화 종료 감지 (%s)  %s" % (reason, body.splitlines()[0]))
        self.emit(kind="stop", path=path, reason=reason, final=final_name,
                  dur=dur, peak=peak, at=time.time())
        sound("stop", self.beep)
        self._push("녹화 중지", body, 3, ["black_square_for_stop"])
        self._active = ""
        self._peak = 0

    def _beat(self):
        dur = time.time() - self._started_at
        self._push("녹화중", f"경과 {hms(dur)} / 용량 {human(self._peak)}",
                   2, ["hourglass_flowing_sand"])
        self._last_beat = time.time()

    def snapshot(self):
        """현재 상태를 UI 가 그대로 표시할 수 있는 형태로 만듭니다."""
        now = time.time()
        if not self._active:
            return {"kind": "state", "active": False}
        elapsed = now - self._started_at
        grown = max(0, self._peak - self._start_size)
        mbps = None
        if elapsed >= 2.0 and grown > 0:
            mbps = grown * 8.0 / elapsed / 1000000.0
        return {"kind": "state", "active": True, "path": self._active,
                "elapsed": elapsed, "size": self._peak, "mbps": mbps,
                "since_growth": now - self._last_growth, "stall": self.stall}

    def tick(self):
        now = time.time()
        current = scan(self.dirs, self.patterns, self.min_size, self.recursive)
        outnow = set(scan(self.outdirs, self.patterns,
                          self.min_size, self.recursive)) if self.outdirs else set()
        new_out = outnow - self._outfiles - {self._active}

        if self._active:
            size = current.get(self._active)
            if new_out:
                self._stop("완료 파일 생성", os.path.basename(sorted(new_out)[0]))
            elif size is None:
                self._stop("임시 파일 사라짐")
            else:
                if size > self._peak:
                    self._peak = size
                    self._last_growth = now
                elif now - self._last_growth >= self.stall:
                    self._stop("증가 멈춤")
                if self._active and self.heartbeat > 0 \
                        and now - self._last_beat >= self.heartbeat:
                    self._beat()
        else:
            for path, size in current.items():
                prev = self._sizes.get(path)
                if prev is not None and size - prev >= self.min_growth:
                    self._start(path, size)
                    break

        self._sizes = current
        self._outfiles = outnow
        self.emit(**self.snapshot())

    def prime(self):
        """감시를 시작하기 직전의 파일 목록을 기준선으로 잡습니다."""
        self._sizes = scan(self.dirs, self.patterns, self.min_size, self.recursive)
        self._outfiles = set(scan(self.outdirs, self.patterns,
                                  self.min_size, self.recursive)) if self.outdirs else set()


class WatchThread(threading.Thread):
    """폴링을 UI 스레드에서 분리해 창이 멈추지 않도록 합니다."""

    def __init__(self, watcher, stop_event):
        super().__init__(name="watcher", daemon=True)
        self.watcher = watcher
        self.stop_event = stop_event

    def run(self):
        w = self.watcher
        try:
            w.prime()
        except Exception as exc:
            log("[오류] 초기 스캔에 실패했습니다: %s" % exc)
            w.emit(kind="error", message="초기 스캔 실패: %s" % exc)
        while not self.stop_event.is_set():
            w.emit(kind="health",
                   missing=[d for d in w.dirs if not os.path.isdir(d)])
            try:
                w.tick()
            except Exception as exc:
                log("[오류] %s\n%s" % (exc, traceback.format_exc().rstrip()))
                w.emit(kind="error", message=str(exc))
            self.stop_event.wait(w.interval)


# ---------------------------------------------------------------- 표시 보조

def mix(color_a, color_b, t):
    """두 색을 t(0~1) 비율로 섞습니다. 배너 밝기 펄스에 사용합니다."""
    t = max(0.0, min(1.0, t))
    a = (int(color_a[1:3], 16), int(color_a[3:5], 16), int(color_a[5:7], 16))
    b = (int(color_b[1:3], 16), int(color_b[3:5], 16), int(color_b[5:7], 16))
    return "#%02x%02x%02x" % tuple(
        int(round(a[i] + (b[i] - a[i]) * t)) for i in range(3))


def ellipsize(text, limit):
    """긴 문자열의 가운데를 줄입니다."""
    if len(text) <= limit:
        return text
    head = (limit - 1) // 2
    tail = limit - 1 - head
    return text[:head] + "…" + text[-tail:]


def folder_label(path, roots):
    """감시 폴더를 기준으로 저장 폴더 이름(예: OnimushaWotS)을 뽑아냅니다."""
    parent = os.path.dirname(path)
    for root in roots:
        try:
            rel = os.path.relpath(parent, root)
        except ValueError:
            continue
        if rel == os.curdir:
            return os.path.basename(root.rstrip("\\/")) or root
        if not rel.startswith(".."):
            return rel.split(os.sep)[0]
    return os.path.basename(parent) or parent


def relative_path(path, roots):
    for root in roots:
        try:
            rel = os.path.relpath(path, root)
        except ValueError:
            continue
        if not rel.startswith(".."):
            return rel
    return path


def growth_color(seconds, stall):
    if seconds >= max(3.0, stall * 0.75):
        return C_REC_TEXT
    if seconds > 3.0:
        return C_WARN
    return C_FG


def enable_dpi_awareness():
    """배율 설정에서 창이 흐리게 늘어나지 않도록 DPI 인식을 켭니다."""
    if not sys.platform.startswith("win"):
        return
    for awareness in (2, 1):
        try:
            ctypes.windll.shcore.SetProcessDpiAwareness(awareness)
            return
        except Exception:
            continue
    try:
        ctypes.windll.user32.SetProcessDPIAware()
    except Exception:
        pass


class _RECT(ctypes.Structure):
    _fields_ = [("left", ctypes.c_long), ("top", ctypes.c_long),
                ("right", ctypes.c_long), ("bottom", ctypes.c_long)]


def monitor_rects():
    """연결된 모니터의 물리 좌표를 (좌, 상, 너비, 높이) 목록으로 돌려줍니다."""
    if not sys.platform.startswith("win"):
        return []
    rects = []
    try:
        proc = ctypes.WINFUNCTYPE(ctypes.c_int, ctypes.c_void_p,
                                  ctypes.c_void_p, ctypes.POINTER(_RECT),
                                  ctypes.c_ssize_t)

        def collect(_monitor, _hdc, lprect, _data):
            r = lprect.contents
            rects.append((r.left, r.top, r.right - r.left, r.bottom - r.top))
            return 1

        ctypes.windll.user32.EnumDisplayMonitors(0, 0, proc(collect), 0)
    except Exception as exc:
        log("[표시] 모니터 목록을 읽지 못했습니다: %s" % exc)
        return []
    rects.sort(key=lambda item: (item[0], item[1]))
    return rects


def window_position(index):
    """지정한 모니터의 한가운데 좌표를 구합니다. 실패하면 None 을 돌려줍니다."""
    rects = monitor_rects()
    if not (0 <= index < len(rects)):
        if index:
            log("[표시] %d번 모니터를 찾지 못해 주 모니터에 표시합니다." % index)
        return None
    left, top, width, height = rects[index]
    return (left + max(0, (width - WIN_W) // 2),
            top + max(0, (height - WIN_H) // 2))


# ---------------------------------------------------------------- GUI

class MonitorApp:
    def __init__(self, root, dirs, interval, borderless):
        self.root = root
        self.dirs = dirs
        self.interval = interval
        self.queue = queue.Queue()
        self.stop_event = threading.Event()

        self.recording = False
        self.session_count = 0
        self.last_summary = "직전 녹화 기록이 없습니다."
        self.last_update = "--:--:--"
        self.warning = ""
        self.log_rows = deque(maxlen=10)

        self._init_fonts()
        self._build_banner()
        self._build_detail()
        self._build_log()
        self._build_status()
        self._show_idle()
        self._refresh_status()

        if borderless:
            self._enable_drag()
        self.root.after(50, self._pulse)
        self.root.after(100, self._drain)

    # ------------------------------------------------------------ 구성

    def _font(self, families, size, weight="normal"):
        available = set(tkfont.families(self.root))
        for name in families:
            if name in available:
                return tkfont.Font(family=name, size=size, weight=weight)
        return tkfont.Font(family=families[-1], size=size, weight=weight)

    def _init_fonts(self):
        self.f_banner = self._font(UI_FAMILIES, 48, "bold")
        self.f_banner_sub = self._font(MONO_FAMILIES, 30, "bold")
        self.f_folder = self._font(UI_FAMILIES, 26, "bold")
        self.f_value = self._font(UI_FAMILIES, 22)
        self.f_value_mono = self._font(MONO_FAMILIES, 22)
        self.f_label = self._font(UI_FAMILIES, 13)
        self.f_mono = self._font(MONO_FAMILIES, 12)
        self.f_status = self._font(UI_FAMILIES, 11)

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

    def _cell(self, parent, row, col, title, value_font, color=C_FG):
        pad = (24, 12) if col == 0 else (12, 24)
        holder = tk.Frame(parent, bg=C_BG, bd=0, highlightthickness=0)
        holder.grid(row=row, column=col, sticky="we", padx=pad, pady=(6, 0))
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
        self.v_rate = self._cell(body, 2, 0, "비트레이트", self.f_value_mono)
        self.v_growth = self._cell(body, 2, 1, "마지막 증가", self.f_value_mono)

        self.v_summary = self._label(body, "", self.f_label, C_BG, C_MUTED)
        self.v_summary.grid(row=3, column=0, columnspan=2, sticky="we",
                            padx=24, pady=(6, 0))

    def _build_log(self):
        frame = tk.Frame(self.root, bg=C_PANEL, height=H_LOG, bd=0,
                         highlightthickness=0)
        frame.pack(side="top", fill="x", padx=16, pady=(4, 0))
        frame.pack_propagate(False)
        self._label(frame, "이벤트 로그", self.f_label, C_PANEL, C_MUTED).pack(
            fill="x", padx=12, pady=(6, 2))
        self.log_labels = []
        for _ in range(LOG_ROWS):
            row = self._label(frame, "", self.f_mono, C_PANEL, C_MUTED)
            row.pack(fill="x", padx=12)
            self.log_labels.append(row)

    def _build_status(self):
        self.status = self._label(self.root, "", self.f_status, C_BG, C_MUTED)
        self.status.pack(side="bottom", fill="x", padx=18, pady=(3, 5))

    def _enable_drag(self):
        def press(event):
            self._drag_x = event.x_root - self.root.winfo_x()
            self._drag_y = event.y_root - self.root.winfo_y()

        def move(event):
            self.root.geometry("+%d+%d" % (event.x_root - self._drag_x,
                                           event.y_root - self._drag_y))

        self._drag_x = self._drag_y = 0
        self.root.bind("<Button-1>", press)
        self.root.bind("<B1-Motion>", move)

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

    def _show_idle(self):
        self.v_folder.config(text="대기 중", fg=C_MUTED)
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
        self.v_folder.config(text=ellipsize(folder_label(path, self.dirs), 22),
                             fg=C_FG)
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
        shown = ellipsize(" · ".join(self.dirs) or "(감시 폴더 없음)", 64)
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


# ---------------------------------------------------------------- 진입점

def parse_args(argv):
    ap = argparse.ArgumentParser(description="ShadowPlay 녹화 상태 모니터 (GUI)")
    ap.add_argument("--dir", action="append", default=None)
    ap.add_argument("--outdir", action="append", default=None)
    ap.add_argument("--pattern", action="append", default=None)
    ap.add_argument("--interval", type=float, default=None)
    ap.add_argument("--stall", type=float, default=None)
    ap.add_argument("--min-size", type=int, default=None)
    ap.add_argument("--min-growth", type=int, default=None)
    ap.add_argument("--heartbeat", type=float, default=None)
    ap.add_argument("--monitor", type=int, default=None)
    ap.add_argument("--ntfy-server", default=None)
    ap.add_argument("--ntfy-topic", default=None)
    ap.add_argument("--ntfy-token", default=None)
    ap.add_argument("--no-recursive", action="store_true")
    ap.add_argument("--beep", dest="beep", action="store_true", default=None)
    ap.add_argument("--no-beep", dest="beep", action="store_false")
    ap.add_argument("--topmost", dest="topmost", action="store_true",
                    default=None)
    ap.add_argument("--no-topmost", dest="topmost", action="store_false")
    ap.add_argument("--borderless", dest="borderless", action="store_true",
                    default=None)
    ap.add_argument("--no-borderless", dest="borderless", action="store_false")
    try:
        return ap.parse_args(argv)
    except SystemExit:
        # --noconsole 로 빌드하면 오류 문구가 보이지 않으므로 로그로 남깁니다.
        log("[인자] 명령줄 인자를 해석하지 못해 config.json 값만 사용합니다: %s"
            % " ".join(argv))
        return ap.parse_args([])


def as_list(value):
    if not value:
        return []
    if isinstance(value, str):
        return [value]
    return list(value)


def normalize(paths):
    return [os.path.abspath(os.path.expandvars(os.path.expanduser(p)))
            for p in paths if p]


def build_settings(cfg, args):
    """config.json 위에 명령줄 인자를 덮어써서 최종 설정을 만듭니다."""
    def pick(arg_value, key, fallback):
        if arg_value is not None:
            return arg_value
        value = cfg.get(key, fallback)
        return fallback if value is None else value

    dirs = normalize(args.dir or as_list(cfg.get("dir")))
    outdirs = normalize(args.outdir or as_list(cfg.get("outdir")))
    patterns = tuple(p.lower() for p in (args.pattern
                                         or as_list(cfg.get("patterns"))) if p)
    server = pick(args.ntfy_server, "ntfy_server", "") or DEFAULT_SERVER
    return {
        "dirs": dirs,
        "outdirs": outdirs,
        "patterns": patterns or DEFAULT_PATTERNS,
        "interval": max(0.2, float(pick(args.interval, "interval", 1.0))),
        "stall": float(pick(args.stall, "stall", 8.0)),
        "min_size": int(pick(args.min_size, "min_size", 1024 * 1024)),
        "min_growth": int(pick(args.min_growth, "min_growth", 256 * 1024)),
        "heartbeat": float(pick(args.heartbeat, "heartbeat", 0.0)),
        "recursive": bool(cfg.get("recursive", True)) and not args.no_recursive,
        "beep": bool(pick(args.beep, "beep", True)),
        "topmost": bool(pick(args.topmost, "topmost", False)),
        "borderless": bool(pick(args.borderless, "borderless", False)),
        "monitor": int(pick(args.monitor, "monitor", 0)),
        "servers": [server],
        "topic": pick(args.ntfy_topic, "ntfy_topic", ""),
        "token": pick(args.ntfy_token, "ntfy_token", ""),
    }


def main(argv=None):
    install_excepthook()
    argv = sys.argv[1:] if argv is None else argv
    settings = build_settings(load_config(), parse_args(argv))

    enable_dpi_awareness()
    root = tk.Tk()
    root.title("ShadowPlay Notifier")
    root.configure(bg=C_BG)
    root.resizable(False, False)
    # 배율에 상관없이 960x640 안에서 같은 레이아웃이 나오도록 고정합니다.
    root.tk.call("tk", "scaling", 96.0 / 72.0)

    spot = window_position(settings["monitor"])
    if spot is None:
        spot = (max(0, (root.winfo_screenwidth() - WIN_W) // 2),
                max(0, (root.winfo_screenheight() - WIN_H) // 2))
    root.geometry("%dx%d+%d+%d" % (WIN_W, WIN_H, spot[0], spot[1]))
    if settings["topmost"]:
        root.attributes("-topmost", True)
    if settings["borderless"]:
        root.overrideredirect(True)

    def tk_error(exc, value, tb):
        log("[UI 예외] " + "".join(
            traceback.format_exception(exc, value, tb)).rstrip())

    root.report_callback_exception = tk_error

    app = MonitorApp(root, settings["dirs"], settings["interval"],
                     settings["borderless"])
    watcher = Watcher(
        dirs=settings["dirs"], outdirs=settings["outdirs"],
        patterns=settings["patterns"], servers=settings["servers"],
        topic=settings["topic"], token=settings["token"],
        interval=settings["interval"], stall=settings["stall"],
        heartbeat=settings["heartbeat"], min_size=settings["min_size"],
        min_growth=settings["min_growth"], recursive=settings["recursive"],
        beep=settings["beep"], sink=app.queue.put,
    )

    def close(_event=None):
        app.stop_event.set()
        try:
            root.destroy()
        except tk.TclError:
            pass

    root.protocol("WM_DELETE_WINDOW", close)
    root.bind("<Escape>", close)

    WatchThread(watcher, app.stop_event).start()
    app.add_log("[시작] 감시를 시작했습니다.", C_MUTED)
    log("앱 시작: dirs=%s interval=%.1f stall=%.1f" % (
        settings["dirs"], settings["interval"], settings["stall"]))
    try:
        root.mainloop()
    finally:
        app.stop_event.set()
        log("앱 종료")


if __name__ == "__main__":
    main()
