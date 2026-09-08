"""환경설정 창입니다.

사람마다 녹화 폴더와 임시 파일 폴더가 다르므로, 파일을 직접 고쳐 쓰지 않고
창에서 골라 저장할 수 있게 했습니다. 저장하면 config.json 에 적고 감시를
새 설정으로 다시 시작합니다.
"""

import os
import tkinter as tk
from tkinter import filedialog

from . import icons
from .config import save_config, settings_to_config
from .display import monitor_for_point
from .paths import log
from .theme import (C_BG, C_DIM, C_FG, C_FIELD, C_LINE, C_MUTED, C_PANEL,
                    C_REC_TEXT, C_SKY, MONO_FAMILIES, UI_FAMILIES, pick_font)

# 960x640 패널 안에 타이틀바까지 들어가야 하므로 넉넉히 잡지 않습니다.
DIALOG_W, DIALOG_H = 660, 430


class SettingsDialog:
    def __init__(self, parent, settings, on_apply):
        self.parent = parent
        self.settings = settings
        self.on_apply = on_apply

        self.top = tk.Toplevel(parent)
        self.top.title("환경설정")
        self.top.configure(bg=C_BG)
        self.top.resizable(False, False)
        self.top.transient(parent)
        # 창 아이콘은 자리를 잡기 전에 달아야 합니다. Tk 가 아이콘을 붙이면서
        # 창을 다시 만드는 일이 있는데, 그러면 뒤따르는 geometry 가 날아갑니다.
        self._set_icon()

        self.f_label = pick_font(self.top, UI_FAMILIES, 12)
        self.f_field = pick_font(self.top, UI_FAMILIES, 13)
        self.f_mono = pick_font(self.top, MONO_FAMILIES, 13)
        self.f_head = pick_font(self.top, UI_FAMILIES, 18, "bold")
        self.f_note = pick_font(self.top, UI_FAMILIES, 11)
        self.folder_icon = tk.PhotoImage(data=icons.FOLDER_LIT)

        self._place()
        self._build()
        self._fill(settings)

        self.top.bind("<Escape>", lambda _event: self.close())
        self.top.protocol("WM_DELETE_WINDOW", self.close)
        self.top.grab_set()
        self.top.focus_force()

    # ------------------------------------------------------------ 구성

    def _set_icon(self):
        """타이틀바에 프로그램 아이콘을 답니다.

        ``iconbitmap`` 은 ico 파일 경로를 받는데, onefile 로 묶으면 그 파일이
        따라가지 않는 데다 창까지 다시 만들어 위치를 잃습니다. 그래서 PNG 를
        담아 둔 ``icons.APP_*`` 로 ``iconphoto`` 를 씁니다. 여러 크기를 함께
        넘기면 윈도우가 타이틀바와 작업 전환 화면에 맞는 것을 골라 씁니다.

        본 창은 타이틀바가 없는 것이 기본이므로 아이콘을 달지 않습니다.
        여기서도 ``default=False`` 로 이 창에만 적용합니다.
        """
        try:
            # PhotoImage 는 참조를 잃으면 지워지므로 창이 살아 있는 동안 붙듭니다.
            self.app_icons = [tk.PhotoImage(data=getattr(icons, "APP_%d" % size))
                              for size in icons.APP_SIZES]
            self.top.iconphoto(False, *self.app_icons)
        except tk.TclError as error:
            self.app_icons = []
            log("[설정] 창 아이콘을 달지 못했습니다: %s" % error)

    def _place(self):
        """본 창 한가운데에 놓되, 그 화면 밖으로 나가지 않게 다듬습니다."""
        self.parent.update_idletasks()
        left = self.parent.winfo_x() + (self.parent.winfo_width() - DIALOG_W) // 2
        top = self.parent.winfo_y() + (self.parent.winfo_height() - DIALOG_H) // 2
        rect = monitor_for_point(self.parent.winfo_x() + 10,
                                 self.parent.winfo_y() + 10)
        if rect:
            m_left, m_top, m_width, m_height = rect
            # 타이틀바와 테두리가 더 붙으므로 그만큼 미리 빼 둡니다.
            left = min(max(left, m_left), m_left + m_width - DIALOG_W)
            top = min(max(top, m_top), m_top + m_height - DIALOG_H - 44)
        self.top.geometry("%dx%d+%d+%d" % (DIALOG_W, DIALOG_H,
                                           max(0, left), max(0, top)))
        if self.parent.attributes("-topmost"):
            self.top.attributes("-topmost", True)

    def _label(self, parent, text, font=None, color=C_MUTED, bg=C_BG,
               wrap=0):
        return tk.Label(parent, text=text, font=font or self.f_label, bg=bg,
                        fg=color, anchor="w", justify="left", bd=0, padx=0,
                        pady=0, highlightthickness=0, wraplength=wrap)

    def _entry(self, parent, width=None, mono=False):
        entry = tk.Entry(parent, font=self.f_mono if mono else self.f_field,
                         bg=C_FIELD, fg=C_FG, insertbackground=C_FG,
                         relief="flat", highlightthickness=1,
                         highlightbackground=C_LINE, highlightcolor=C_SKY,
                         disabledbackground=C_FIELD)
        if width:
            entry.configure(width=width)
        return entry

    def _folder_row(self, parent, row, title, note):
        self._label(parent, title).grid(row=row, column=0, columnspan=3,
                                        sticky="w", pady=(12, 2))
        entry = self._entry(parent)
        entry.grid(row=row + 1, column=0, columnspan=2, sticky="we", ipady=5)
        button = tk.Button(parent, image=self.folder_icon, bg=C_FIELD,
                           activebackground=C_LINE, relief="flat", bd=0,
                           highlightthickness=0, cursor="hand2",
                           command=lambda: self._browse(entry))
        button.grid(row=row + 1, column=2, sticky="we", padx=(6, 0), ipadx=10)
        self._label(parent, note, font=self.f_note, color=C_MUTED,
                    wrap=DIALOG_W - 48).grid(
            row=row + 2, column=0, columnspan=3, sticky="w", pady=(3, 0))
        return entry

    def _number_row(self, parent, row, left_title, right_title):
        self._label(parent, left_title).grid(row=row, column=0, sticky="w",
                                             pady=(12, 2))
        self._label(parent, right_title).grid(row=row, column=1, sticky="w",
                                              padx=(16, 0), pady=(12, 2))
        left = self._entry(parent, mono=True)
        left.grid(row=row + 1, column=0, sticky="we", ipady=5)
        right = self._entry(parent, mono=True)
        right.grid(row=row + 1, column=1, sticky="we", padx=(16, 0), ipady=5)
        return left, right

    def _build(self):
        # 아래쪽 버튼 줄을 먼저 붙여야 합니다. expand 를 쓰는 본문을 먼저 붙이면
        # 본문이 남는 자리를 모두 가져가서 버튼이 잘립니다.
        footer = tk.Frame(self.top, bg=C_PANEL)
        footer.pack(fill="x", side="bottom")
        self._label(footer, "저장하면 config.json 에 적고 감시를 다시 시작합니다.",
                    font=self.f_note, bg=C_PANEL).pack(
            side="left", padx=22, pady=14)
        self._button(footer, "저장", self.save, C_SKY, "#0b0b0d").pack(
            side="right", padx=(8, 22), pady=12)
        self._button(footer, "취소", self.close, C_FIELD, C_DIM).pack(
            side="right", pady=12)

        body = tk.Frame(self.top, bg=C_BG)
        body.pack(fill="both", expand=True, padx=22, pady=(16, 0))
        body.columnconfigure(0, weight=1, uniform="col")
        body.columnconfigure(1, weight=1, uniform="col")
        body.columnconfigure(2, minsize=52)

        self._label(body, "환경설정", font=self.f_head, color=C_FG).grid(
            row=0, column=0, columnspan=3, sticky="w")

        self.e_dir = self._folder_row(
            body, 1, "녹화 폴더",
            "녹화 중에 파일이 커지는 폴더입니다. 하위 폴더까지 함께 봅니다.")

        self.e_interval, self.e_stall = self._number_row(
            body, 4, "폴링 주기 (초)", "중단 판정 시간 (초)")
        self.e_min_size, self.e_min_growth = self._number_row(
            body, 6, "최소 파일 크기 (MB)", "시작 판정 증가량 (KB)")

        self._label(body, "표시할 모니터 번호 (-1 이면 자동)").grid(
            row=8, column=0, columnspan=2, sticky="w", pady=(12, 2))
        self.e_monitor = self._entry(body, mono=True)
        self.e_monitor.grid(row=9, column=0, sticky="we", ipady=5)

        checks = tk.Frame(body, bg=C_BG)
        checks.grid(row=9, column=1, columnspan=2, sticky="w", padx=(16, 0))
        self.v_topmost = tk.BooleanVar()
        self.v_borderless = tk.BooleanVar()
        self.v_beep = tk.BooleanVar()
        for text, var in (("항상 위", self.v_topmost),
                          ("테두리 없음", self.v_borderless),
                          ("소리", self.v_beep)):
            tk.Checkbutton(
                checks, text=text, variable=var, font=self.f_label, bg=C_BG,
                fg=C_DIM, selectcolor=C_FIELD, activebackground=C_BG,
                activeforeground=C_FG, bd=0, highlightthickness=0,
                anchor="w", cursor="hand2").pack(side="left", padx=(0, 14))

        self.message = self._label(body, "", font=self.f_note, color=C_REC_TEXT,
                                   wrap=DIALOG_W - 48)
        self.message.grid(row=10, column=0, columnspan=3, sticky="w",
                          pady=(10, 0))

    def _button(self, parent, text, command, bg, fg):
        return tk.Button(parent, text=text, command=command, font=self.f_field,
                         bg=bg, fg=fg, activebackground=bg, activeforeground=fg,
                         relief="flat", bd=0, highlightthickness=0,
                         cursor="hand2", padx=22, pady=7)

    # ------------------------------------------------------------ 값 다루기

    def _fill(self, settings):
        def put(entry, value):
            entry.delete(0, "end")
            entry.insert(0, str(value))

        put(self.e_dir, settings["dirs"][0] if settings["dirs"] else "")
        put(self.e_interval, "%.1f" % settings["interval"])
        put(self.e_stall, "%.1f" % settings["stall"])
        put(self.e_min_size, "%.0f" % (settings["min_size"] / 1048576.0))
        put(self.e_min_growth, "%.0f" % (settings["min_growth"] / 1024.0))
        put(self.e_monitor, settings["monitor"])
        self.v_topmost.set(settings["topmost"])
        self.v_borderless.set(settings["borderless"])
        self.v_beep.set(settings["beep"])

    def _browse(self, entry):
        current = entry.get().strip()
        start = current if os.path.isdir(current) else None
        chosen = filedialog.askdirectory(parent=self.top, initialdir=start,
                                         title="폴더 선택")
        if chosen:
            entry.delete(0, "end")
            entry.insert(0, os.path.normpath(chosen))

    def _collect(self):
        """입력값을 검사해서 새 설정을 만듭니다. 잘못되면 None 을 돌려줍니다."""
        watch = self.e_dir.get().strip()
        if not watch:
            self.message.config(text="녹화 폴더를 지정하십시오.")
            return None
        try:
            interval = float(self.e_interval.get())
            stall = float(self.e_stall.get())
            min_size = float(self.e_min_size.get())
            min_growth = float(self.e_min_growth.get())
            monitor = int(self.e_monitor.get())
        except ValueError:
            self.message.config(text="숫자 칸에는 숫자만 넣을 수 있습니다.")
            return None
        if interval < 0.2:
            self.message.config(text="폴링 주기는 0.2초 이상이어야 합니다.")
            return None
        if stall < interval * 2:
            self.message.config(
                text="중단 판정 시간은 폴링 주기의 두 배 이상이어야 합니다.")
            return None
        if min_size < 0 or min_growth <= 0:
            self.message.config(text="크기 값은 0보다 커야 합니다.")
            return None

        # 완료본 폴더(outdir)는 창에서 다루지 않습니다. config.json 에 적어 둔
        # 값이 있으면 그대로 지켜 줍니다.
        updated = dict(self.settings)
        updated.update({
            "dirs": [os.path.abspath(os.path.expandvars(watch))],
            "interval": interval,
            "stall": stall,
            "min_size": int(min_size * 1048576),
            "min_growth": int(min_growth * 1024),
            "monitor": monitor,
            "topmost": bool(self.v_topmost.get()),
            "borderless": bool(self.v_borderless.get()),
            "beep": bool(self.v_beep.get()),
        })
        if not os.path.isdir(updated["dirs"][0]):
            self.message.config(
                text="폴더가 없습니다. 경로를 확인하십시오: %s" % updated["dirs"][0])
            return None
        return updated

    def save(self):
        updated = self._collect()
        if updated is None:
            return
        if not save_config(settings_to_config(updated)):
            self.message.config(text="설정 파일을 쓰지 못했습니다. 로그를 보십시오.")
            return
        log("[설정] 환경설정을 저장했습니다: %s" % settings_to_config(updated))
        self.close()
        self.on_apply(updated)

    def close(self):
        try:
            self.top.grab_release()
        except tk.TclError:
            pass
        self.top.destroy()
