"""오프라인 월페이퍼 미리보기. ←/→: 장면, Space: 음악, F11: 크기, Esc: 종료.

python test/wallpaper_preview.py --seconds 180 --scene 0
실제 Spotify·날씨·녹화 폴더에는 연결하지 않습니다.
"""

import argparse
import ctypes
import gc
import json
import math
import sys
import time
from pathlib import Path
from types import SimpleNamespace
from collections import deque
import threading

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import tkinter as tk
from component import display, fonts, wallpaper
from component.nowplaying import Track
from component.weather import Weather

SCENES = ((6, 0, "dawn"), (13.5, 0, "day"), (17.5, 0, "sunset"),
          (23, 0, "night"), (22, 63, "rain"), (9, 45, "fog"),
          (16, 73, "snow"), (2, 95, "storm"), (12, 3, "cloudy"))


def demo_cover(root):
    svg = '''<svg xmlns="http://www.w3.org/2000/svg" width="160" height="160">
    <defs><linearGradient id="a" x2=".7" y2="1"><stop stop-color="#8cafb0"/>
    <stop offset="1" stop-color="#18374d"/></linearGradient></defs>
    <rect width="160" height="160" fill="#173344"/>
    <circle cx="112" cy="52" r="78" fill="url(#a)"/>
    <path d="M0 78 Q75 138 160 92 V160 H0Z" fill="#385b63"/>
    <path d="M0 111 Q60 78 160 144 V160 H0Z" fill="#0b2430"/>
    <circle cx="52" cy="39" r="15" fill="#e5d8b4"/></svg>'''
    photo = tk.PhotoImage(master=root, data=svg, format="svg")
    result = root.tk.call(str(photo), "data", "-format", "png")
    root.tk.call("image", "delete", str(photo))
    return result


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--seconds", type=float, default=180)
    parser.add_argument("--scene", type=int, default=0)
    parser.add_argument("--size", default="960x640")
    parser.add_argument("--empty", action="store_true")
    parser.add_argument("--profile", action="store_true")
    parser.add_argument("--cycle", action="store_true")
    parser.add_argument("--controls", action="store_true")
    args = parser.parse_args()
    display.enable_dpi_awareness()
    fonts.load()
    root = tk.Tk()
    root.title("Wallpaper Design Preview")
    root.overrideredirect(True)
    spot = display.window_position(1) or (40, 40)
    width, height = (int(value) for value in args.size.split("x"))
    if width > 960 or height > 640:
        spot = (100, 100)
    root.geometry("%dx%d+%d+%d" % (width, height, *spot))
    root.attributes("-topmost", True)
    track = SimpleNamespace(version=0, track=Track(
        "Tycho", "A Walk", "Dive · 2011", demo_cover(root), (108, 165, 177)))
    weather = SimpleNamespace(version=0, current=Weather())
    audio = SimpleNamespace(levels=[0.] * 12)
    state = {"scene": args.scene, "playing": True, "large": False}
    started, cpu_started = time.perf_counter(), time.process_time()
    samples, frame_times = [], deque(maxlen=20000)

    def report():
        elapsed = time.perf_counter() - started
        times = sorted(frame_times)
        output = {"seconds": round(elapsed, 2),
                  "cpu_core_percent": round((time.process_time() - cpu_started) / elapsed * 100, 2),
                  "frames": len(times),
                  "frame_ms_p50": round(times[len(times) // 2], 3) if times else 0,
                  "frame_ms_p99": round(times[int(len(times) * .99)], 3) if times else 0,
                  "samples": samples}
        folder = Path(__file__).resolve().parents[1] / ".Codex"
        folder.mkdir(exist_ok=True)
        (folder / "wallpaper-soak.json").write_text(json.dumps(output, indent=2), encoding="utf-8")

    def close():
        if args.profile:
            report()
        view.destroy()
        root.destroy()

    def fullscreen():
        state["large"] = not state["large"]
        root.geometry("1920x1080+100+100" if state["large"] else "960x640+%d+%d" % spot)

    view = wallpaper.WallpaperView(root, {}, actions={"close": close, "full": fullscreen})
    if args.profile:
        original_tick = view._tick

        def timed_tick():
            begin = time.perf_counter()
            original_tick()
            frame_times.append((time.perf_counter() - begin) * 1000)

        view._tick = timed_tick

    class Counters(ctypes.Structure):
        _fields_ = [("cb", ctypes.c_ulong), ("faults", ctypes.c_ulong)] + [
            (name, ctypes.c_size_t) for name in ("peak_ws", "ws", "peak_paged", "paged",
                                                "peak_nonpaged", "nonpaged", "pagefile",
                                                "peak_pagefile", "private")]

    def sample():
        gc.collect()
        kernel = ctypes.windll.kernel32
        kernel.GetCurrentProcess.restype = ctypes.c_void_p
        process = kernel.GetCurrentProcess()
        memory = Counters()
        memory.cb = ctypes.sizeof(memory)
        ctypes.windll.psapi.GetProcessMemoryInfo(ctypes.c_void_p(process), ctypes.byref(memory), memory.cb)
        handles = ctypes.c_ulong()
        kernel.GetProcessHandleCount(ctypes.c_void_p(process), ctypes.byref(handles))
        samples.append({"second": round(time.perf_counter() - started),
                        "private_mb": round(memory.private / 1048576, 2),
                        "working_mb": round(memory.ws / 1048576, 2),
                        "handles": handles.value,
                        "gdi": ctypes.windll.user32.GetGuiResources(ctypes.c_void_p(process), 0),
                        "user": ctypes.windll.user32.GetGuiResources(ctypes.c_void_p(process), 1),
                        "canvas_items": len(view.canvas.find_all()),
                        "tk_images": len(root.tk.call("image", "names")),
                        "python_objects": len(gc.get_objects()),
                        "threads": len(threading.enumerate())})
        report()
        root.after(15000, sample)

    def cycle():
        scenario(1)
        music()
        view.stop()
        view.start(audio, track, weather)
        root.after(25000, cycle)

    def clock():
        hour = SCENES[state["scene"]][0]
        text = "%02d:%02d" % (int(hour), round((hour % 1) * 60))
        for item in (view.clock_item, view.clock_shadow):
            view.canvas.itemconfigure(item, text=text)
        view.canvas.itemconfigure(view.date_item, text="2026년 9월 13일   일요일")
        view.canvas.itemconfigure(view.sec_item, text="%02d" % (int(time.time()) % 60))
        view._position_seconds()

    view._update_clock = clock
    wallpaper._now_hour = lambda: SCENES[state["scene"]][0]

    def scenario(step=0):
        state["scene"] = (state["scene"] + step) % len(SCENES)
        hour, code, name = SCENES[state["scene"]]
        weather.version += 1
        weather.current = Weather(ok=True, temp=18 if hour < 8 or hour > 18 else 24,
                                  code=code, tmax=25, tmin=17, humidity=64,
                                  precip=85 if code == 63 else 10, is_day=7 < hour < 19)
        view._apply_weather(force=True)
        view._bake_sky(force=True)

    def music(_event=None):
        state["playing"] = not state["playing"]
        track.version += 1
        track.track = (Track("米津玄師", "夜鷹 - Yodaka", "Yodaka - Single",
                             demo_cover(root), (197, 128, 93)) if state["playing"] else Track())

    def resize(event):
        if event.widget is root:
            view.resize(event.width, event.height)

    def animate():
        t = time.perf_counter()
        audio.levels = [(.23 + .30 * (.5 + .5 * math.sin(t * (1.8 + i * .13) + i)))
                        if state["playing"] else 0 for i in range(12)]
        root.after(33, animate)

    scenario()
    if args.empty:
        music()
    view.start(audio=audio, nowplaying=track, weather=weather)
    root.bind("<Configure>", resize)
    root.bind("<Right>", lambda _e: scenario(1))
    root.bind("<Left>", lambda _e: scenario(-1))
    root.bind("<space>", music)
    root.bind("<F11>", lambda _e: fullscreen())
    root.bind("<Escape>", lambda _e: close())
    root.after(max(1000, round(args.seconds * 1000)), close)
    root.after(100, animate)
    if args.profile:
        root.after(3000, sample)
    if args.cycle:
        root.after(25000, cycle)
    if args.controls:
        root.after(1000, lambda: view._motion(SimpleNamespace(
            x=view.width - 60 * view.scale_x - 88 * view.scale,
            y=53 * view.scale_y)))
    root.mainloop()
    fonts.unload()


if __name__ == "__main__":
    main()
