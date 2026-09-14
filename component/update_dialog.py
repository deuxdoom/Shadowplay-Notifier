"""트레이 업데이트 창과 별도 업데이트 프로세스의 진행 창입니다."""

import json
import queue
import sys
import threading
import time
import tkinter as tk
import webbrowser
from pathlib import Path
from tkinter import ttk

from . import dialogs, display, fonts, updater
from . import update_windows as win
from .i18n import tr
from .paths import log
from .theme import C_BG, C_FIELD, C_FG, C_LINE, C_MUTED, C_SKY
from .version import VERSION

PHASES = {
    "download": "새 버전을 내려받고 있습니다", "verify": "다운로드 파일 확인",
    "stop": "기존 프로그램 종료", "replace": "실행 파일 교체",
    "restart": "새 버전 시작 확인", "rollback": "이전 버전 복구",
    "done": "업데이트 완료", "error": "업데이트를 완료하지 못했습니다",
    "cancelled": "업데이트 취소"}


class UpdateWindow:
    def __init__(self, window, center=None):
        self.window = window
        window.withdraw()
        window.title(win.UPDATE_TITLE)
        window.configure(bg=C_BG)
        window.resizable(False, False)
        window.attributes("-topmost", True)
        self.request_close = lambda: None
        self.title_close = dialogs.title_bar(window, tr("업데이트"), lambda: self.request_close())
        self.box = tk.Frame(window, bg=C_BG, padx=28, pady=24)
        self.box.pack(fill="both", expand=True)
        self._label("SHADOWPLAY NOTIFIER", 12, C_MUTED).pack(anchor="w")
        self.heading = self._label(tr("최신 버전 확인 중"), 24, C_FG, "bold")
        self.heading.pack(anchor="w", pady=(12, 8))
        self.versions = self._label(tr("현재 버전  ") + VERSION, 15, C_SKY)
        self.versions.pack(anchor="w")
        self.message = self._label(tr("GitHub에서 최신 정식 릴리스를 확인하고 있습니다."), 15, C_FG)
        self.message.pack(anchor="w", pady=(20, 14))
        style = ttk.Style(window)
        # 테마 전환은 본 앱의 다른 ttk 위젯에도 영향을 주므로 하지 않습니다.
        # 이 막대의 요소만 clam에서 가져와 Windows 밝은 테마에서도 어둡게 표시합니다.
        if "Update.trough" not in style.element_names():
            style.element_create("Update.trough", "from", "clam", "Horizontal.Progressbar.trough")
            style.element_create("Update.pbar", "from", "clam", "Horizontal.Progressbar.pbar")
        style.layout("Update.Horizontal.TProgressbar", [
            ("Update.trough", {"sticky": "nswe", "children": [
                ("Update.pbar", {"side": "left", "sticky": "ns"})]})])
        style.configure("Update.Horizontal.TProgressbar", troughcolor=C_FIELD,
                        background=C_SKY, bordercolor=C_FIELD, lightcolor=C_SKY,
                        darkcolor=C_SKY, thickness=12)
        self.progress = ttk.Progressbar(self.box, style="Update.Horizontal.TProgressbar",
                                        maximum=100, mode="indeterminate")
        self.progress.pack(fill="x")
        self.detail = self._label(tr("연결 중…"), 13, C_MUTED)
        self.detail.pack(anchor="w", pady=(10, 0))
        self.source = self._label(tr("공식 GitHub 릴리스 · ") + "deuxdoom/Shadowplay-Notifier", 12, C_MUTED)
        self.source.pack(anchor="w", pady=(18, 18))
        self.buttons = tk.Frame(self.box, bg=C_BG)
        self.buttons.pack(fill="x")
        self.close_button = self.button(tr("닫기"), lambda: None)
        self.close_button.pack(side="right")
        self.action = self.button(tr("업데이트"), lambda: None, primary=True)
        self.center = center or window.winfo_pointerxy()
        self.recenter()
        window.deiconify()
        self.recenter()
        window.lift()
        window.focus_force()
        self.progress.start(12)

    def _label(self, text, size, color, weight="normal"):
        return tk.Label(self.box, text=text, font=("Malgun Gothic", -size, weight),
                        fg=color, bg=C_BG, justify="left", anchor="w", wraplength=464)

    def button(self, text, command, primary=False):
        return tk.Button(self.buttons, text=text, command=command,
                         font=("Malgun Gothic", -14, "bold"),
                         bg=C_SKY if primary else C_FIELD,
                         fg=C_BG if primary else C_FG,
                         activebackground=C_SKY, activeforeground=C_BG,
                         relief="flat", bd=0, padx=18, pady=9,
                         highlightthickness=1, highlightbackground=C_LINE, cursor="hand2")

    def recenter(self):
        self.window.update_idletasks()
        rect = display.monitor_for_point(*self.center)
        rect = rect or (0, 0, self.window.winfo_screenwidth(), self.window.winfo_screenheight())
        left, top, width, height = rect
        box_width = min(520, width - 24)
        box_height = min(self.window.winfo_reqheight(), height - 64)
        self.window.geometry("%dx%d+%d+%d" % (
            box_width, box_height, left + (width - box_width) // 2,
            top + (height - box_height) // 2))
        if self.window.winfo_viewable():
            win.center_window(self.window, rect)

    def result(self, heading, message, detail=""):
        self.progress.stop()
        self.progress.configure(mode="determinate", value=0)
        self.heading.configure(text=heading)
        self.message.configure(text=message)
        self.detail.configure(text=detail)
        self.recenter()

    def phase(self, phase, percent, detail):
        self.progress.stop()
        self.progress.configure(mode="determinate", value=percent)
        self.heading.configure(text=tr(PHASES.get(phase, phase)))
        self.message.configure(text=tr("다운로드 → 확인 → 설치 → 재실행"))
        self.detail.configure(text="%d%%  ·  %s" % (percent, detail))


class UpdateController:
    def __init__(self, root, arguments):
        self.root, self.arguments = root, list(arguments)
        self.view = None
        self.events = queue.Queue()
        self.generation = 0
        self.after_id = None
        self.helper = None
        self.release = None

    def show(self):
        if (self.helper and self.helper.poll() is None) or win.update_active():
            win.focus_update()
            return
        if self.view:
            self.view.window.lift()
            self.view.window.focus_force()
            return
        self.helper = None
        self.generation += 1
        generation = self.generation
        self.view = UpdateWindow(tk.Toplevel(self.root))
        self.view.window.protocol("WM_DELETE_WINDOW", self.dismiss)
        self.view.close_button.configure(command=self.dismiss)
        self.view.request_close = self.dismiss
        self.view.action.configure(command=self.begin)
        self.release = None

        def check():
            try:
                result = updater.check_latest()
                self.events.put((generation, "release", result))
            except Exception as exc:
                log("[업데이트 확인] %s" % exc)
                self.events.put((generation, "error", updater.error_text(exc)))

        threading.Thread(target=check, name="update-check", daemon=True).start()
        self.after_id = self.root.after(100, self.poll)

    def poll(self):
        self.after_id = None
        if not self.view:
            return
        while True:
            try:
                generation, kind, data = self.events.get_nowait()
            except queue.Empty:
                break
            if generation != self.generation:
                continue
            if kind == "error":
                self.view.result(tr("확인하지 못했습니다"), data)
                self.view.action.configure(text=tr("다시 확인"), command=self.retry)
                self.view.action.pack(side="right", padx=(0, 10))
            else:
                self.release, tag = data
                if self.release:
                    self.view.versions.configure(text=tr("현재  %s    →    최신  %s") % (VERSION, tag))
                    self.view.result(tr("새 버전이 있습니다"),
                                     tr("업데이트하면 프로그램이 잠시 종료된 뒤 자동으로 다시 실행됩니다."),
                                     tr("설정과 로그는 그대로 유지됩니다."))
                    self.view.action.configure(text=tr("업데이트"), command=self.begin)
                    self.view.action.pack(side="right", padx=(0, 10))
                else:
                    self.view.result(tr("최신 버전입니다"), tr("설치할 새 정식 버전이 없습니다."),
                                     tr("현재 %s  ·  GitHub 최신 %s") % (VERSION, tag))
        if self.view:
            self.after_id = self.root.after(100, self.poll)

    def retry(self):
        self.dismiss()
        self.show()

    def begin(self):
        if not self.release:
            return
        if not getattr(sys, "frozen", False):
            self.view.result(tr("EXE에서 업데이트해 주세요"),
                             tr("소스 실행 중에는 파일을 교체할 수 없습니다. 릴리스에서 EXE를 내려받아 실행해 주세요."))
            self.view.action.configure(text=tr("릴리스 열기"),
                                       command=lambda: webbrowser.open(self.release.page))
            return
        self.view.action.configure(state="disabled")
        self.view.close_button.configure(state="disabled")
        self.view.result(tr("업데이트 준비"), tr("진행 창을 준비하고 있습니다."),
                         tr("잠시만 기다려 주세요."))
        # 20 MB EXE 복사도 Tk 스레드 밖에서 처리합니다.
        center = self.view.center
        release = self.release
        generation = self.generation
        self.launching = True

        def launch():
            try:
                process, job = updater.launch_helper(release, sys.executable, self.arguments, center)
                self.events.put((generation, "helper", (process, job)))
            except Exception as exc:
                self.events.put((generation, "launch_error", updater.error_text(exc)))

        if self.after_id:
            self.root.after_cancel(self.after_id)
        threading.Thread(target=launch, name="update-launch", daemon=True).start()
        self.deadline = time.monotonic() + 45
        self.job = None
        self.after_id = self.root.after(100, self.wait_helper)

    def wait_helper(self):
        self.after_id = None
        if not self.view:
            return
        try:
            _generation, kind, data = self.events.get_nowait()
        except queue.Empty:
            kind, data = None, None
        error = None
        if kind == "helper":
            self.helper, self.job = data
        elif kind == "launch_error":
            error = data
        if self.job and (self.job / "ready").exists():
            self.launching = False
            self.dismiss()
            return
        if self.helper and self.helper.poll() is not None:
            error = tr("업데이트 진행 창을 시작하지 못했습니다. 다시 시도해 주세요.")
        if time.monotonic() >= self.deadline:
            error = tr("업데이트 준비에 시간이 걸리고 있습니다. 잠시 후 다시 확인해 주세요.")
        if error:
            self.launching = False
            self.view.result(tr("업데이트 준비 실패"), error)
            self.view.close_button.configure(state="normal")
            self.view.action.configure(state="normal", text=tr("다시 확인"), command=self.retry)
            return
        self.after_id = self.root.after(100, self.wait_helper)

    def dismiss(self):
        if getattr(self, "launching", False):
            return
        self.generation += 1
        if self.after_id:
            self.root.after_cancel(self.after_id)
            self.after_id = None
        if self.view:
            self.view.progress.stop()
            self.view.window.destroy()
            self.view = None

    def close(self):
        self.launching = False
        self.dismiss()


def run_helper(plan_path):
    """일반 앱 뮤텍스/설정/감시를 열지 않는 전용 진입점입니다."""
    lock = win.UpdateLock()
    root = None
    try:
        plan_path = Path(plan_path).resolve(strict=True)
        job = plan_path.parent
        if job.parent != updater.JOBS.resolve() or not job.name.startswith("job-"):
            raise updater.UpdateError(tr("업데이트 작업 폴더가 올바르지 않습니다."))
        plan = json.loads(plan_path.read_text(encoding="utf-8"))
        release = updater.Release(**plan["release"])
        # 저장된 입력도 공식 릴리스와 같은 규칙으로 검사합니다.
        updater.parse_release({"tag_name": release.tag, "assets": [{
            "name": updater.ASSET_NAME, "state": "uploaded", "size": release.size,
            "digest": "sha256:" + release.sha256, "browser_download_url": release.url}]})
        target = Path(plan["target"]).resolve(strict=True)
        arguments = plan["arguments"]
        if not isinstance(arguments, list) or not all(isinstance(arg, str) for arg in arguments):
            raise updater.UpdateError(tr("재실행 인자가 올바르지 않습니다."))
        display.enable_dpi_awareness()
        fonts.load()
        root = tk.Tk()
        view = UpdateWindow(root, tuple(plan["center"]))
        view.versions.configure(text=tr("새 버전  ") + release.tag)
        view.source.configure(text=tr("공식 GitHub 릴리스 · ") + release.tag)
        events = queue.Queue()
        cancel = threading.Event()
        state = {"phase": "download"}
        can_cancel = {"download", "verify"}

        def close():
            if state["phase"] in can_cancel:
                cancel.set()
                view.close_button.configure(text=tr("취소 중…"), state="disabled")
            elif state["phase"] in ("done", "error", "cancelled"):
                root.destroy()

        root.protocol("WM_DELETE_WINDOW", close)
        view.request_close = close
        view.close_button.configure(text=tr("취소"), command=close)

        def report(phase, percent, detail):
            state["phase"] = phase
            events.put((phase, percent, detail))
            if phase != "download":
                try:
                    updater.write_json(job / "status.json", {"phase": phase, "detail": detail,
                                                             "target": str(target)})
                except OSError as exc:
                    # 상태 기록 실패가 파일 복구를 가로막아서는 안 됩니다.
                    log("[업데이트 상태 기록] %s" % exc)

        def work():
            try:
                updater.install(release, target, arguments, report, cancel)
            except updater.Cancelled as exc:
                report("cancelled", 0, str(exc))
            except Exception as exc:
                log("[업데이트] %s" % exc)
                report("error", 0, updater.error_text(exc))

        def poll():
            latest = None
            while True:
                try:
                    latest = events.get_nowait()
                except queue.Empty:
                    break
            if latest:
                phase, percent, detail = latest
                if phase in ("error", "cancelled"):
                    view.result(tr(PHASES[phase]), detail)
                else:
                    view.phase(phase, percent, detail)
                view.close_button.configure(
                    text=tr("닫기") if phase in ("done", "error", "cancelled") else tr("취소"),
                    state="normal" if phase in can_cancel | {"done", "error", "cancelled"} else "disabled")
                view.title_close.configure(fg=C_FG if phase in can_cancel | {"done", "error", "cancelled"} else C_MUTED)
                if phase == "done":
                    root.after(1400, root.destroy)
                    return
            root.after(80, poll)

        view.phase("download", 0, tr("다운로드를 준비하고 있습니다."))
        updater.write_json(job / "status.json", {"phase": "download", "target": str(target)})
        (job / "ready").write_text(str(root.winfo_id()), encoding="ascii")
        root.after(100, poll)
        threading.Thread(target=work, name="update-install", daemon=True).start()
        root.mainloop()
        return 0
    finally:
        fonts.unload()
        lock.close()
