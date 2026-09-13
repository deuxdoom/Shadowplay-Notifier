"""실제 자동 전환 캔버스의 해상도별 배치와 전체화면 복원을 확인합니다."""

import os
import sys
import tempfile
import tkinter as tk
from unittest.mock import patch

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from component import display, fonts, theme
from component.app import MonitorApp
from component.nowplaying import Track
from component.scan import DEFAULT_PATTERNS
from component.weather import Weather


class Provider:
    def __init__(self, *args, **kwargs):
        self.version = 1
        self.track = Track("Artist", "Track", "Album")
        self.current = Weather(ok=True, temp=18, code=0, is_day=False)
        self.levels = [0.0] * 12
        self.stopped = False

    def start(self):
        pass

    def stop(self):
        self.stopped = True

    def is_alive(self):
        return False


def check_items(view, items):
    for item in items:
        box = view.canvas.bbox(item)
        assert box is not None, item
        assert box[0] >= 0 and box[1] >= 0, (item, box)
        assert box[2] <= view.width and box[3] <= view.height, (item, box)


def check_layout(root, app, width, height):
    root.update()
    view = app.wallpaper
    assert (root.winfo_width(), root.winfo_height()) == (width, height)
    assert (view.width, view.height) == (width, height)
    assert root.pack_slaves() == [view.canvas]
    assert view.canvas.winfo_ismapped()
    check_items(view, (view.control_items["close"],))
    if app.recording:
        assert view.mode == "rec"
        check_items(view, (view.rec_dot, view.rec_word, view.rec_folder,
                           view.rec_time, view.rec_size, view.rec_unit,
                           view.rec_rate, view.rec_grow, view.rec_file,
                           view.badge_word, view.status_item, view.status_ver))
    else:
        assert view.mode == "wall"
        check_items(view, (view.phase_item, view.date_item, view.clock_item,
                           view.sec_item, view.wicon_item, view.temp_item,
                           view.desc_item, view.meta_item, view.meta2_item,
                           view.title_item, view.album_item))


def main():
    display.enable_dpi_awareness()
    fonts.load()
    root = tk.Tk()
    root.configure(bg=theme.C_BG)
    root.geometry("960x640+0+0")
    root.maxsize(8000, 8000)
    root.overrideredirect(True)
    root.tk.call("tk", "scaling", 96 / 72)
    errors = []
    root.report_callback_exception = lambda *error: errors.append(error)
    watch_dir = tempfile.gettempdir()
    settings = dict(dirs=[watch_dir], outdirs=[], patterns=DEFAULT_PATTERNS,
                    interval=0.5, stall=8, min_size=1024, min_growth=1024,
                    recursive=True, beep=False, topmost=False, borderless=True,
                    monitor=0, latitude=37.5665, longitude=126.978)

    with patch("component.app.AudioLevels", Provider), \
            patch("component.app.NowPlaying", Provider), \
            patch("component.app.WeatherWatch", Provider):
        app = MonitorApp(root, settings)
        app.attach_close(lambda _event=None: root.destroy())
        try:
            root.update()
            base_fonts = {key: font.cget("size")
                          for key, (font, _size) in app.wallpaper._fonts.items()}
            for width, height in ((960, 640), (800, 600), (1024, 768),
                                  (1280, 720), (1366, 768), (1920, 1080),
                                  (1920, 1200), (2560, 1440), (3440, 1440),
                                  (3840, 2160), (1080, 1920)):
                app._set_window_rect(0, 0, width, height)
                app._apply_state(dict(active=False))
                check_layout(root, app, width, height)
                app._apply_state(dict(
                    active=True,
                    path=os.path.join(watch_dir, "Modern Warfare 4 - Beta", "video.mp4"),
                    elapsed=1462, size=3.7 * 1024 ** 3, mbps=71.4,
                    since_growth=0.2, stall=8))
                check_layout(root, app, width, height)
                print("PASS %dx%d: wallpaper and recording" % (width, height))

            app._apply_state(dict(active=False))
            for rect in ((0, 0, 3840, 2160), (3840, 1520, 960, 640)):
                app._set_window_rect(rect[0], rect[1], 960, 640)
                with patch("component.app.monitor_for_point", return_value=rect):
                    app.toggle_fullscreen()
                    check_layout(root, app, rect[2], rect[3])
                    app.toggle_fullscreen()
                check_layout(root, app, 960, 640)
                assert not app.fullscreen
                assert (root.winfo_x(), root.winfo_y()) == rect[:2]
                assert {key: font.cget("size")
                        for key, (font, _size) in app.wallpaper._fonts.items()} == base_fonts
            assert not errors, errors
            print("PASS automatic modes, fullscreen restore, fonts and Tk callbacks")
        finally:
            app.stop_wallpaper()
            root.destroy()
            fonts.unload()


if __name__ == "__main__":
    main()
