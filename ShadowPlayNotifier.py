#!/usr/bin/env python3
"""ShadowPlay Notifier 진입점입니다.

ShadowPlay(NVIDIA App) 녹화 상태를 감시해 보조 디스플레이에 표시합니다.
설정을 읽어 창을 만들고, 감시 스레드와 화면을 이어 붙이는 일만 합니다.
실제 동작은 component 폴더의 모듈들이 나누어 맡습니다.
"""

import os
import sys
import tkinter as tk
import traceback
import webbrowser

from component import dialogs, fonts, i18n, instance, startup, version, updater
from component import update_windows
from component.update_dialog import UpdateController, run_helper
from component.app import MonitorApp
from component.config import build_settings, load_config, parse_args
from component.display import enable_dpi_awareness, window_position
from component.paths import detail, install_excepthook, log, set_verbose
from component.theme import C_BG, WIN_H, WIN_W
from component.watcher import WatchSupervisor
from component.tray import TrayIcon


def place_window(root, settings):
    """설정에 따라 창을 놓을 자리를 정합니다."""
    spot = window_position(settings["monitor"])
    if spot is None:
        spot = (max(0, (root.winfo_screenwidth() - WIN_W) // 2),
                max(0, (root.winfo_screenheight() - WIN_H) // 2))
    root.geometry("%dx%d+%d+%d" % (WIN_W, WIN_H, spot[0], spot[1]))
    detail("창 배치: %dx%d+%d+%d (monitor=%d)"
           % (WIN_W, WIN_H, spot[0], spot[1], settings["monitor"]))


def main(argv=None):
    install_excepthook()
    argv = sys.argv[1:] if argv is None else argv

    if len(argv) == 2 and argv[0] == "--apply-update":
        # 업데이트 진행 창은 본 프로그램과 따로 도는 프로세스이므로, 설정
        # 파일에서 쓰는 말만 읽어 옵니다. 감시와 창은 열지 않습니다.
        i18n.set_language(load_config().get("language", i18n.DEFAULT))
        return run_helper(argv[1])
    restart_target = os.environ.pop("SPN_UPDATE_RESTART", "")
    if update_windows.update_active() and (
            not restart_target or update_windows.canonical(restart_target) !=
            update_windows.canonical(sys.executable)):
        update_windows.focus_update()
        return 0

    # 창이 둘 뜨면 같은 폴더를 두 번 감시하면서 로그와 알림음도 겹칩니다.
    if not instance.claim():
        log("[중복 실행] 이미 실행 중이므로 새 창을 띄우지 않습니다.")
        if not instance.focus_existing(version.title()):
            instance.tell_already_running(version.APP_NAME)
        return 1

    settings = build_settings(load_config(), parse_args(argv))
    # 평소에는 녹화와 오류만 남깁니다. 문제를 찾을 때만 자세한 기록을 켭니다.
    set_verbose(settings.get("verbose_log", False))

    enable_dpi_awareness()
    # 묶어 온 글꼴을 이 프로그램에서만 쓰도록 등록합니다. 창을 만들기 전에
    # 해야 Tk 가 글꼴 목록에 넣습니다.
    fonts.load()
    root = tk.Tk()
    root.title(version.title())
    root.configure(bg=C_BG)
    root.resizable(False, False)
    # 배율에 상관없이 960x640 안에서 같은 배치가 나오도록 고정합니다.
    root.tk.call("tk", "scaling", 96.0 / 72.0)

    place_window(root, settings)
    if settings["topmost"]:
        root.attributes("-topmost", True)
    if settings["borderless"]:
        root.overrideredirect(True)

    def tk_error(exc, value, tb):
        log("[UI 예외] " + "".join(
            traceback.format_exception(exc, value, tb)).rstrip())

    root.report_callback_exception = tk_error

    app = MonitorApp(root, settings)
    supervisor = WatchSupervisor(app.queue.put)
    app.settings_callback = supervisor.start
    tray = None
    closing = False
    updates = UpdateController(root, argv)

    def close(_event=None):
        nonlocal closing
        if closing:
            return
        closing = True
        updates.close()
        if tray is not None:
            tray.close()
        app.stop_event.set()
        supervisor.stop(1.0)
        app.stop_wallpaper()
        try:
            root.destroy()
        except tk.TclError:
            pass

    def hide(_event=None):
        if tray is not None and tray.available:
            app.hide_window()
        else:
            close()

    def settings_from_tray():
        app.show_window()
        app.open_settings()

    def startup_from_tray():
        try:
            startup.set_enabled(not startup.is_enabled())
        except (OSError, ValueError) as exc:
            log("[자동 실행] 설정을 바꾸지 못했습니다: %s" % exc)
            dialogs.show_message("윈도우 시작 시 실행",
                                 "자동 실행 설정을 바꾸지 못했습니다.\n%s" % exc, parent=root)

    tray = TrayIcon(root, {
        "show": app.show_window,
        "settings": settings_from_tray,
        "startup": startup_from_tray,
        "update": updates.show,
        "github": lambda: webbrowser.open("https://github.com/deuxdoom/Shadowplay-Notifier"),
        "quit": close,
    }, lambda: {"recording": app.recording}, startup.is_enabled)
    root.protocol("WM_DELETE_WINDOW", hide)
    app.attach_close(hide)
    root.bind("<Control-q>", close)
    if settings["borderless"]:
        # 타이틀바가 없으면 창이 초점을 받지 못해 Esc 가 닿지 않습니다.
        def grab_focus():
            try:
                root.focus_force()
            except tk.TclError as exc:
                log("[표시] %s" % exc)

        root.after(300, grab_focus)

    supervisor.start(settings)
    updater.schedule_cleanup()
    app.add_log("[시작] 감시를 시작했습니다.", "", "감시를 시작했습니다")
    log("앱 시작 %s  감시: %s" % (version.VERSION,
                                  " · ".join(settings["dirs"]) or "(없음)"))
    try:
        root.mainloop()
    finally:
        updates.close()
        tray.close()
        app.stop_event.set()
        supervisor.stop(1.0)
        app.stop_wallpaper()
        fonts.unload()
        log("앱 종료")
    return 0


if __name__ == "__main__":
    sys.exit(main())
