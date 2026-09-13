"""실제 Tk/GDI+를 사용하는 월페이퍼 회귀 검사. 네트워크·녹화 파일 접근 없음."""

import gc
import math
import sys
import time
import unittest
from unittest.mock import patch
from pathlib import Path
from types import SimpleNamespace
from itertools import product

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import tkinter as tk
from component import display, fonts, sky, wallpaper, imaging
from component.nowplaying import Track
from component.weather import Weather
from component.app import MonitorApp
from component.config import build_settings, parse_args
from wallpaper_preview import demo_cover


def luminance(rgb):
    linear = [(v / 255 / 12.92 if v / 255 <= .04045 else
               ((v / 255 + .055) / 1.055) ** 2.4) for v in rgb]
    return sum(a * b for a, b in zip(linear, (.2126, .7152, .0722)))


class WallpaperTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        display.enable_dpi_awareness()
        fonts.load()

    def setUp(self):
        self.root = tk.Tk()
        self.root.withdraw()
        self.errors = []
        self.root.report_callback_exception = lambda *args: self.errors.append(args)
        self.track = SimpleNamespace(version=1, track=Track(
            "米津玄師", "夜鷹 - Yodaka", "Yodaka - Single", demo_cover(self.root), (170, 120, 90)))
        self.weather = SimpleNamespace(version=1, current=Weather(
            ok=True, temp=18, tmax=25, tmin=17, code=0, humidity=84, precip=10))
        self.audio = SimpleNamespace(levels=[.4] * 12)
        self.default_images = set(self.root.tk.call("image", "names"))
        self.view = wallpaper.WallpaperView(self.root, {})
        self.view.start(self.audio, self.track, self.weather)
        self.settle()

    def tearDown(self):
        self.view.destroy()
        self.root.destroy()
        self.assertEqual(self.errors, [])

    def settle(self):
        deadline = time.perf_counter() + 8
        while time.perf_counter() < deadline:
            self.root.update()
            if self.view._fade_target is not None:
                self.view._fade_at -= 3
                self.view._paint_at = 0
            if self.view._future is None and self.view._fade_target is None:
                return
            time.sleep(.005)
        self.fail("scene did not settle")

    def test_time_palette_continuous_through_day_and_midnight(self):
        # 해 뜰 무렵과 해 질 무렵에는 색이 빠르게 건너갑니다. 그 사이에 머물면
        # 사진이 중간 밝기로 떠서 글자가 묻히기 때문입니다. 가장 빠른 곳은 금빛
        # 노을에서 어스름으로 넘어가는 저녁으로 1분에 7단계입니다. 배경을 30초
        # 마다 다시 구우므로 한 번에 움직이는 폭은 그 절반이고, 1.8초에 걸쳐
        # 겹쳐 넘기므로 이어져 보입니다. 자정을 잘못 넘기면 수백 단계가 한 번에
        # 튀므로 여기서 걸립니다.
        previous = sky.blend_palette(0)
        for minute in range(1, 1441):
            current = sky.blend_palette(minute / 60)
            self.assertLessEqual(max(abs(a - b) for a, b in
                                     zip(previous["glow"], current["glow"])), 9)
            previous = current

    def test_layout_and_square_artwork_at_eleven_sizes(self):
        sizes = ((960, 640), (1920, 1080), (2560, 1440), (3840, 2160),
                 (2560, 1080), (3440, 1440), (1080, 1920), (720, 1280),
                 (640, 480), (1280, 800), (960, 640))
        self.track.track.title = "아주 긴 한국어 제목과 日本語の長い曲名 — A very long title " * 5
        self.track.track.artist = "아티스트 · アーティスト " * 8
        self.track.track.album = "Album " * 30
        self.view._apply_track(force=True)
        for w, h in sizes:
            self.view.resize(w, h)
            self.settle()
            self.view._blink_clock(True)
            c = self.view.canvas
            for item in (self.view.date_item, self.view.clock_item, self.view.colon_item,
                         self.view.minute_item, self.view.sec_item,
                         self.view.temp_item, self.view.desc_item, self.view.meta_item,
                         self.view.meta2_item, self.view.title_item,
                         self.view.album_item, self.view.play_label, self.view.phase_item):
                box = c.bbox(item)
                self.assertIsNotNone(box)
                with self.subTest(size=(w, h), text=c.itemcget(item, "text")):
                    self.assertGreaterEqual(box[0], 0)
                    self.assertGreaterEqual(box[1], 0)
                    self.assertLessEqual(box[2], w)
                    self.assertLessEqual(box[3], h)
            cover = self.view._cover_image
            self.assertEqual(cover.width(), cover.height())
            self.assertEqual(cover.width(), round(112 * self.view.scale))
            self.assertLess(c.bbox(self.view.sec_item)[2], c.bbox(self.view.wicon_item)[0])
            self.assertLess(c.bbox(self.view.title_item)[3], c.bbox(self.view.album_item)[1])

    def test_only_wall_and_recording_modes_exist(self):
        self.assertEqual(self.view.mode, "wall")
        c = self.view.canvas
        version_position = c.coords(self.view.status_ver)
        self.assertIsNotNone(c.bbox(self.view.status_ver))
        self.view.set_mode("idle")
        self.assertEqual(self.view.mode, "wall")
        self.view.set_mode("rec")
        self.assertEqual(self.view.mode, "rec")
        self.assertIsNotNone(c.bbox(self.view.status_ver))
        self.assertEqual(c.coords(self.view.status_ver), version_position)
        self.assertEqual(self.view.canvas.itemcget(self.view.rec_word, "text"),
                         "R E C O R D I N G")
        self.view.set_mode("wall")

    def test_only_colon_blinks_without_moving_digits_or_adding_timers(self):
        view, c = self.view, self.view.canvas
        view._set_clock_time(3, 33)
        items = (view.clock_item, view.colon_item, view.minute_item, view.sec_item)
        positions = [c.coords(item) for item in items]
        count = len(c.find_all())
        timers = len(self.root.tk.call("after", "info"))
        epoch = time.mktime((2026, 9, 13, 3, 33, 10, 0, 0, -1))
        for offset, visible in ((.1, True), (.6, False), (1.1, True), (1.6, False)):
            with patch("component.wallpaper.time.time", return_value=epoch + offset):
                view._update_clock()
            self.assertEqual(c.itemcget(view.clock_item, "text"), "03")
            self.assertEqual(c.itemcget(view.minute_item, "text"), "33")
            self.assertEqual(c.itemcget(view.sec_item, "text"), "%02d" % (10 + int(offset)))
            # 배경을 다시 칠해도 깜빡임의 박자를 바꾸지 않습니다.
            view._paint_foreground()
            for item in view._clock_blink_items:
                self.assertEqual(bool(c.itemcget(item, "fill")), visible)
                if visible:
                    self.assertIsNotNone(c.bbox(item))
            self.assertTrue(c.itemcget(view.clock_item, "fill"))
            self.assertTrue(c.itemcget(view.minute_item, "fill"))
            self.assertTrue(c.itemcget(view.sec_item, "fill"))
            self.assertIsNotNone(c.bbox(view.sec_item))
            self.assertEqual([c.coords(item) for item in items], positions)
        self.assertEqual(len(c.find_all()), count)
        self.assertEqual(len(self.root.tk.call("after", "info")), timers)
        view.set_mode("rec")
        view._blink_clock(True)
        for item in (*items, view.colon_shadow, view.minute_shadow):
            self.assertEqual(c.itemcget(item, "state"), "hidden")
        view.set_mode("wall")

    def test_clock_stays_left_aligned_and_clear_of_weather(self):
        view, c = self.view, self.view.canvas
        for width, height in ((960, 640), (640, 480), (1920, 1080), (1080, 1920)):
            view.resize(width, height)
            self.settle()
            for hour, minute in ((0, 0), (11, 11), (23, 58)):
                view._set_clock_time(hour, minute)
                # 왼쪽 여백 보정은 글꼴 크기에 비례합니다. 고정값으로 두면
                # 시계 크기를 바꿀 때 날짜와의 정렬이 조용히 어긋납니다.
                bearing = -view._fonts["clock"][0].cget("size") * wallpaper.BEARING
                self.assertAlmostEqual(c.coords(view.clock_item)[0] + bearing,
                                       c.coords(view.date_item)[0])
                self.assertLess(c.bbox(view.minute_item)[2], c.bbox(view.wicon_item)[0])
                # 큰 글꼴 bbox의 빈 아래 여백은 글획이 아닙니다. 세로 간격은
                # 실화면에서도 확인하며, 여기서는 파형·달과의 간섭을 검사합니다.
                self.assertLess(c.bbox(view.sec_item)[3], min(c.bbox(i)[1] for i in view.bar_items))
                self.assertLess(c.bbox(view.sec_item)[2], c.bbox(view.moon_item)[0])
        view.resize(960, 640)
        # 시계는 화면에서 가장 큰 요소로 남되, 지나치게 커지면 디센더 자리가
        # 함께 늘어 초가 멀어 보이고 날씨까지의 여백도 빠듯해집니다.
        clock_px = -view._fonts["clock"][0].cget("size")
        self.assertGreater(clock_px, 150)
        self.assertLessEqual(clock_px, 170)
        self.assertGreater(clock_px, -view._fonts["date"][0].cget("size") * 3)

    def test_weather_failure_clears_icon_and_resumes_new_provider(self):
        self.weather.current.code = 63
        self.view._apply_weather(force=True)
        self.assertEqual(self.view._sky_key, "rain")
        self.weather.current = Weather()
        self.weather.version += 1
        self.view._apply_weather()
        self.assertEqual(self.view._sky_key, "clear")
        self.assertIsNone(self.view._wicon_image)
        self.assertEqual(self.view.canvas.itemcget(self.view.meta_item, "text"), "")
        self.view.stop()
        self.track = SimpleNamespace(version=1, track=Track("New artist", "New title"))
        self.view.start(nowplaying=self.track)
        self.assertEqual(self.view.canvas.itemcget(self.view.title_item, "text"),
                         "New artist - New title")
        self.assertIsNone(self.view._cover_image)

    def test_large_weather_and_permanent_close_button(self):
        c = self.view.canvas
        self.view._show_controls(False)
        self.assertEqual(c.itemcget(self.view.control_items["close"], "state"), "normal")
        self.assertGreaterEqual(abs(self.view._fonts["date"][0].cget("size")), 32)
        self.assertGreaterEqual(self.view._wicon_image.width(), 100)
        for temp in (-99, -18, 0, 18, 48):
            self.weather.current.temp = temp
            self.view._apply_weather(force=True)
            self.assertLess(c.bbox(self.view.wicon_item)[2], c.bbox(self.view.temp_item)[0])

    def test_image_item_and_callback_counts_under_replacement(self):
        original_items = len(self.view.canvas.find_all())
        original_images = len(self.root.tk.call("image", "names"))
        original_fonts = len(self.root.tk.call("font", "names"))
        # 기존 커버와 수신 실패를 교대로 160회. 같은 Tk 이미지에 덮어쓰기만
        # 하는 검사가 아니라 실제 JPEG/PNG 변환·할당·삭제 경로를 거칩니다.
        cover = self.track.track.cover
        for i in range(160):
            self.view._set_cover(cover if i % 2 else None)
            self.weather.current.code = (0, 63, 73, 45, 95, 3)[i % 6]
            self.view._apply_weather(force=True)
            self.view.atmosphere.configure(960, 640, sky.blend_palette(i % 24),
                                           self.view._sky_key, self.view._bg_pixels, 0)
            self.view.atmosphere.update(i * 7.5)
            self.assertEqual(len(self.view.canvas.find_all()), original_items)
            self.assertLessEqual(len(self.root.tk.call("image", "names")), original_images)
        self.settle()
        self.assertEqual(len(self.root.tk.call("font", "names")), original_fonts)
        for _ in range(30):
            self.view.stop()
            self.assertEqual(len(self.root.tk.call("after", "info")), 0)
            self.view.start(self.audio, self.track, self.weather)
            self.view.start(self.audio, self.track, self.weather)
            self.assertEqual(len(self.root.tk.call("after", "info")), 1)
        self.settle()
        self.view.destroy()
        gc.collect()
        self.assertEqual(len(self.root.tk.call("after", "info")), 0)
        self.assertEqual(set(self.root.tk.call("image", "names")), self.default_images)

    def test_transient_effects_have_quiet_intervals(self):
        a, c = self.view.atmosphere, self.view.canvas
        for group in ("rain", "snow"):
            a.configure(960, 640, sky.blend_palette(22), group, self.view._bg_pixels, 0)
            a.update(12)
            items = ([item for drop in a.rain_items for item in drop] if group == "rain"
                     else a.snow_items)
            self.assertTrue(any(c.itemcget(item, "state") == "normal" for item in items))
            a.update(50)
            self.assertTrue(all(c.itemcget(item, "state") == "hidden" for item in items))
        a.configure(960, 640, sky.blend_palette(22), "clear", self.view._bg_pixels, 0)
        a.update(12.5)
        self.assertIsNotNone(a._meteor)
        a.update(15)
        self.assertIsNone(a._meteor)
        self.assertTrue(all(c.itemcget(item, "state") == "hidden" for item in a.meteor_items))

    def test_controls_scale_and_stop_drag_propagation(self):
        calls = []
        self.view.actions = {key: lambda key=key: calls.append(key)
                             for key in ("settings", "full", "close")}
        self.view.resize(1920, 1080)
        for key, item in self.view.control_items.items():
            x, y = self.view.canvas.coords(item)
            event = SimpleNamespace(x=x, y=y)
            self.assertEqual(self.view._click(event), "break")
            self.assertEqual(self.view._control_drag(event), "break")
            self.assertEqual(calls[-1], key)
        self.assertIsNone(self.view._click(SimpleNamespace(x=200, y=300)))
        self.assertIsNone(self.view._control_drag(None))

    def test_text_contrast_across_all_palettes_and_weather(self):
        self.view._blink_clock(True)
        minimum = 100
        # 글자 bbox에 포함되는 모든 작은 배경 표본을 검사합니다.
        c = self.view.canvas
        positions = [(c.bbox(item), sky._rgb(color), adaptive) for item, color, adaptive in (
            (self.view.clock_item, wallpaper.INK, True), (self.view.colon_item, wallpaper.INK, True),
            (self.view.minute_item, wallpaper.INK, True), (self.view.sec_item, wallpaper.INK_3, True),
            (self.view.date_item, wallpaper.INK_2, True), (self.view.meta_item, wallpaper.INK_3, True),
            (self.view.temp_item, wallpaper.INK, True), (self.view.desc_item, wallpaper.INK_2, True),
            (self.view.meta2_item, wallpaper.INK_3, True), (self.view.title_item, wallpaper.INK, False),
            (self.view.album_item, wallpaper.INK_3, False),
            (self.view.play_label, wallpaper.INK_3, False), (self.view.phase_item, wallpaper.INK_3, True))]
        times = (*sky.TIMES, SimpleNamespace(hour=7, name="sunrise transition"),
                 SimpleNamespace(hour=17.5, name="sunset transition"))
        for season, palette in product(sky.SEASONS, times):
            for group in ("clear", "storm", "fog"):
                pixels = sky.render(960, 640, sky.blend_palette(palette.hour, season),
                                    (255, 255, 255), group)
                for box, ink, adaptive in positions:
                    if adaptive:
                        ink = sky._rgb(sky.foreground(pixels, box, 960, 640))
                    light = luminance(ink)
                    for y in range(max(0, box[1]), min(640, box[3]) + 1, 4):
                        for x in range(max(0, box[0]), min(960, box[2]) + 1, 4):
                            ground = luminance(sky.sample(pixels, x / 960, y / 640))
                            ratio = (max(light, ground) + .05) / (min(light, ground) + .05)
                            minimum = min(minimum, ratio)
                            self.assertGreaterEqual(ratio, 4.5, (season, palette.name, group, box, ratio))
        print("Minimum text contrast: %.2f:1 (96 seasonal scenes, white album accent)" % minimum)

    def test_season_calendar_and_daylight_are_distinct(self):
        self.assertEqual([sky.season_for_month(m) for m in range(1, 13)],
                         ["winter"] * 2 + ["spring"] * 3 + ["summer"] * 3 +
                         ["autumn"] * 3 + ["winter"])
        for season in sky.SEASONS:
            self.assertGreater(len(set(sky._photo(season, 1.5))), 100)
            day = sky.render(960, 640, sky.blend_palette(12, season))
            night = sky.render(960, 640, sky.blend_palette(0, season))
            self.assertGreater(sky.luminance(sky.sample(day, .5, .25)),
                               sky.luminance(sky.sample(night, .5, .25)) * 4)

    def test_native_blend_and_rgb_upload_preserve_channels(self):
        w, h = 37, 19
        first = bytes((i * 31) % 256 for i in range(w * h * 3))
        second = bytes((i * 43 + 77) % 256 for i in range(w * h * 3))
        ppm = imaging.upscale_rgb(first, w, h, w, h)
        self.assertEqual(ppm.split(b"\n", 3)[3], first)
        for t in (0, .125, .5, .9, 1):
            actual = imaging.blend_rgb(first, second, w, h, t)
            self.assertIsNotNone(actual)
            expected = [round(a + (b - a) * t) for a, b in zip(first, second)]
            self.assertLessEqual(max(abs(a - b) for a, b in zip(actual, expected)), 2)

    def test_spectrum_has_long_rainbow_bars_without_overlap(self):
        self.view._levels = [1.] * 12
        self.audio.levels = [1.] * 12
        self.view._update_bars(0, .033)
        c = self.view.canvas
        middle = c.coords(self.view.bar_items[32])
        self.assertGreater(middle[3] - middle[1], 70)
        colors = {c.itemcget(item, "fill") for item in self.view.bar_items}
        self.assertGreater(len(colors), 50)
        for item in self.view.bar_items:
            box = c.bbox(item)
            self.assertGreater(box[1], c.bbox(self.view.meta2_item)[3])
        for item in self.view.reflection_items:
            self.assertLess(c.bbox(item)[3], self.view._cover_xy[1])


class WallpaperIntegrationTests(unittest.TestCase):
    def test_recording_switch_fullscreen_and_restore(self):
        class Provider:
            def __init__(self, *args, **kwargs):
                self.version = 1
                self.track = Track("Artist", "Track")
                self.current = Weather(ok=True, temp=18, code=0, is_day=False)
                self.levels = [0.] * 12
                self.stopped = False

            def start(self):
                pass

            def stop(self):
                self.stopped = True

        display.enable_dpi_awareness()
        fonts.load()
        root = tk.Tk()
        root.withdraw()
        root.geometry("960x640+3840+1520")
        root.maxsize(8000, 8000)
        root.overrideredirect(True)
        root.tk.call("tk", "scaling", 96 / 72)
        root.deiconify()
        errors = []
        root.report_callback_exception = lambda *args: errors.append(args)
        settings = build_settings({}, parse_args([]))
        with patch("component.app.AudioLevels", Provider), \
                patch("component.app.NowPlaying", Provider), \
                patch("component.app.WeatherWatch", Provider):
            app = MonitorApp(root, settings)
            try:
                root.update()
                view = app.wallpaper
                self.assertTrue(view.running)
                self.assertEqual(root.pack_slaves(), [view.canvas])
                provider = app._wall_audio
                app._set_recording(True)
                root.update()
                self.assertTrue(view.running)
                self.assertEqual(view.mode, "rec")
                self.assertTrue(provider.stopped)
                self.assertIsNotNone(view._after_id)
                self.assertEqual(root.pack_slaves(), [view.canvas])
                original_fonts = [font.cget("size") for font, _, _ in app._base_fonts]
                app._set_recording(False)
                self.assertTrue(view.running)
                self.assertEqual(view.mode, "wall")
                self.assertIsNot(app._wall_audio, provider)
                for rect in ((0, 0, 1920, 1080), (0, 0, 3840, 2160)):
                    with patch("component.app.monitor_for_point", return_value=rect):
                        view.actions["full"]()
                        root.update()
                        self.assertTrue(app.fullscreen)
                        self.assertEqual((view.width, view.height), rect[2:])
                        view.actions["full"]()
                        root.update()
                        self.assertFalse(app.fullscreen)
                        self.assertEqual((view.width, view.height), (960, 640))
                app._set_recording(True)
                root.update()
                self.assertEqual([font.cget("size") for font, _, _ in app._base_fonts], original_fonts)
                app.hide_window()
                self.assertFalse(view.running)
                self.assertIsNone(view.audio)
                self.assertTrue(app.hidden_to_tray)
                app.show_window()
                self.assertTrue(view.running)
                self.assertEqual(view.mode, "rec")
                app._set_recording(False)
                self.assertTrue(view.running)
                self.assertEqual(view.mode, "wall")
                self.assertEqual(errors, [])
            finally:
                app.stop_wallpaper()
                root.destroy()


if __name__ == "__main__":
    unittest.main(verbosity=2)
