"""실제 Tk 위젯으로 해상도별 비율, 글자 잘림, 전체화면 복원을 확인합니다.

python test/test_layout.py
앱을 닫고 실행하십시오. 가짜 녹화 상태만 표시하며 녹화 파일과 설정은 읽지 않습니다.
"""

import os
import sys
import tempfile
import tkinter as tk
from types import SimpleNamespace
from unittest.mock import patch

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from component import display, theme  # noqa: E402
from component.app import BUTTON_ORDER, MonitorApp  # noqa: E402
from component.scan import DEFAULT_PATTERNS  # noqa: E402


def check_layout(root, app, width, height):
    root.update()
    assert (root.winfo_width(), root.winfo_height()) == (width, height)
    sy = height / theme.WIN_H
    scale = min(width / theme.WIN_W, sy)
    for widget, base in ((app.banner, theme.H_BANNER),
                         (app.detail, theme.H_DETAIL), (app.log_frame, theme.H_LOG)):
        assert abs(widget.winfo_height() - base * sy) <= 1, widget
    # 로그 아래가 화면의 대부분을 차지하던 회귀를 잡습니다.
    gap = app.status_row.winfo_y() - (app.log_frame.winfo_y() + app.log_frame.winfo_height())
    assert 0 <= gap <= height * 0.05, (width, height, gap)

    def check_children(parent):
        for child in parent.winfo_children():
            assert child.winfo_ismapped(), child
            assert child.winfo_width() > 1 and child.winfo_height() > 1, child
            assert child.winfo_x() >= 0 and child.winfo_y() >= 0, child
            assert child.winfo_x() + child.winfo_width() <= parent.winfo_width(), child
            assert child.winfo_y() + child.winfo_height() <= parent.winfo_height(), child
            if isinstance(child, tk.Label):
                assert child.winfo_reqheight() <= child.winfo_height(), (
                    width, height, child, child.winfo_reqheight(), child.winfo_height())
            check_children(child)

    check_children(root)
    dot = app.banner.coords(app.dot)
    assert abs((dot[2] - dot[0]) - (dot[3] - dot[1])) < 0.01
    assert abs((dot[2] - dot[0]) - 68 * scale) < 0.01
    expected_font_h = app._base_fonts[0][2] * scale
    assert abs(app.f_banner.metrics("linespace") - expected_font_h) <= max(3, expected_font_h * 0.02)
    for name in BUTTON_ORDER:
        box = app.banner.bbox(app.buttons[name])
        assert box[0] >= 0 and box[2] <= width
        assert box[1] >= 0 and box[3] <= app.banner.winfo_height()
        assert app._corner_hit((box[0] + box[2]) / 2, (box[1] + box[3]) / 2) == name
    for item in (app.banner_text, app.banner_sub):
        box = app.banner.bbox(item)
        assert box[0] >= 0 and box[2] <= width, box
        assert box[1] >= 0 and box[3] <= app.banner.winfo_height(), box
    assert len(app.log_labels) == 5


def main():
    display.enable_dpi_awareness()
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
                    recursive=True, beep=False, topmost=False, borderless=True, monitor=0,
                    wallpaper=False)
    app = MonitorApp(root, settings)
    app.attach_close(lambda _event=None: root.destroy())
    for index in range(5):
        app.add_log("[test] recording event %d" % index, theme.C_SKY)
    try:
        root.update()
        base_fonts = [font.cget("size") for font, _, _ in app._base_fonts]
        base_rows = [label.winfo_geometry() for label in app.log_labels]
        base_tk_scaling = root.tk.call("tk", "scaling")
        for width, height in ((960, 640), (800, 600), (1024, 768), (1280, 720),
                              (1366, 768), (1920, 1080), (1920, 1200),
                              (2560, 1440), (3440, 1440), (3840, 2160), (1080, 1920)):
            app._set_window_rect(0, 0, width, height)
            for folder in (None, "OnimushaWotS", "Modern Warfare 4 - Beta"):
                app._apply_state(dict(active=folder is not None,
                                      path=os.path.join(watch_dir, folder or "idle", "video.mp4"),
                                      elapsed=1462, size=3.7 * 1024 ** 3, mbps=71.4,
                                      since_growth=0.2, stall=8))
                check_layout(root, app, width, height)
            print("PASS %dx%d: idle, recording, long folder" % (width, height))

        for rect in ((0, 0, 3840, 2160), (3840, 1520, 960, 640)):
            app._set_window_rect(rect[0], rect[1], 960, 640)
            for _ in range(2):
                with patch("component.app.monitor_for_point", return_value=rect):
                    root.focus_force()
                    root.event_generate("<F11>")
                    root.update()
                    assert app.fullscreen
                    check_layout(root, app, rect[2], rect[3])
                if _ == 0:
                    # 배너 버튼의 확대된 좌표로도 복원이 되는지 확인합니다.
                    box = app.banner.bbox(app.buttons["full"])
                    app._banner_click(SimpleNamespace(x=(box[0] + box[2]) / 2,
                                                      y=(box[1] + box[3]) / 2))
                else:
                    root.event_generate("<Escape>")
                check_layout(root, app, 960, 640)
                assert not app.fullscreen
                assert (root.winfo_x(), root.winfo_y()) == rect[:2]
                assert [font.cget("size") for font, _, _ in app._base_fonts] == base_fonts
                assert [label.winfo_geometry() for label in app.log_labels] == base_rows
                assert root.tk.call("tk", "scaling") == base_tk_scaling
        assert not errors, errors
        print("PASS fullscreen controls, original position/fonts/rows, no Tk callback errors")
    finally:
        root.destroy()


if __name__ == "__main__":
    main()
