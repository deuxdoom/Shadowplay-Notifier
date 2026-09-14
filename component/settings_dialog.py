"""환경설정 창입니다.

사람마다 녹화 폴더와 임시 파일 폴더가 다르므로, 파일을 직접 고쳐 쓰지 않고
창에서 골라 저장할 수 있게 했습니다. 저장하면 config.json 에 적고 감시를
새 설정으로 다시 시작합니다.
"""

import os
import ssl
import threading
import tkinter as tk

from . import cities, dialogs, i18n, icons, weather
from .config import save_config, settings_to_config
from .display import monitor_for_point
from .paths import detail, log
from .theme import (C_BG, C_DIM, C_FG, C_FIELD, C_LINE, C_MUTED, C_PANEL,
                    C_REC_TEXT, C_SKY, MONO_FAMILIES, UI_FAMILIES, pick_font)

# 960x640 패널 안에 타이틀바까지 들어가야 하므로 넉넉히 잡지 않습니다.
# 높이는 기준값일 뿐이며, 실제로는 내용에 맞춰 늘립니다. 화면 배율이 높으면
# pt 로 지정한 글자가 그만큼 커져서 고정 높이로는 아래쪽이 잘립니다.
DIALOG_W, DIALOG_H = 600, 400
# 도시 후보를 보여 주는 목록의 줄 수와 한 줄 높이입니다.
SUGGEST_ROWS = 7
# 글자를 친 뒤 이만큼 쉬면 인터넷에서도 도시를 찾아봅니다. 글자마다 부르면
# 조회가 밀리기만 하고 후보가 늦게 나옵니다.
SUGGEST_DELAY = 320


class SettingsDialog:
    def __init__(self, parent, settings, on_apply):
        self.parent = parent
        self.settings = settings
        self.on_apply = on_apply

        self.top = tk.Toplevel(parent)
        self.top.title(i18n.tr("환경설정"))
        self.top.configure(bg=C_BG)
        self.top.resizable(False, False)
        self.top.transient(parent)
        # 본 창이 타이틀바를 쓰지 않으므로 이 창도 맞춥니다. 제목과 닫기
        # 버튼은 위쪽 줄에 직접 그리고, 그 줄을 잡으면 창이 끌립니다.
        self.top.overrideredirect(True)
        self._drag_from = None

        # 글꼴은 pt 가 아니라 픽셀(음수)로 잡습니다. pt 로 두면 화면 배율이
        # 200% 인 환경에서 글자가 두 배가 되어, 창이 본 창(960x640)보다 커집니다.
        self.f_label = pick_font(self.top, UI_FAMILIES, -13)
        self.f_field = pick_font(self.top, UI_FAMILIES, -14)
        self.f_mono = pick_font(self.top, MONO_FAMILIES, -14)
        self.f_head = pick_font(self.top, UI_FAMILIES, -20, "bold")
        self.f_note = pick_font(self.top, UI_FAMILIES, -12)
        self.folder_icon = tk.PhotoImage(data=icons.FOLDER_LIT)

        # 도시 후보 상태입니다. 조회는 다른 스레드에서 하고, 화면은 Tk 스레드
        # 에서만 건드립니다. ``_suggest_seq`` 로 늦게 도착한 결과를 버립니다.
        self._city_pick = None
        self._suggestions = []
        self._suggest_seq = 0
        self._suggest_after = None
        self._suggest_poll = None
        self._suggest_lock = threading.Lock()
        self._suggest_ready = None
        self._suggest_window = None
        self._suggest_list = None
        self._ssl = ssl.create_default_context()

        self._build()
        self._fill(settings)
        self._place()

        self.top.bind("<Escape>", lambda _event: self.close())
        self.top.protocol("WM_DELETE_WINDOW", self.close)
        self.top.grab_set()
        self.top.focus_force()

    # ------------------------------------------------------------ 구성

    def _title_bar(self, parent):
        """제목과 닫기 버튼을 직접 그린 위쪽 줄입니다.

        타이틀바가 없으므로 이 줄이 그 몫을 합니다. 아무 데나 잡아 끌면 창이
        따라오고, 오른쪽 끝의 × 로 닫습니다.
        """
        bar = tk.Frame(parent, bg=C_PANEL)
        bar.pack(fill="x", side="top")
        try:
            # PhotoImage 는 참조를 잃으면 지워지므로 창이 사는 동안 붙듭니다.
            self.app_icon = tk.PhotoImage(data=icons.APP_16)
            tk.Label(bar, image=self.app_icon, bg=C_PANEL, bd=0,
                     highlightthickness=0).pack(side="left", padx=(12, 8), pady=8)
        except tk.TclError as error:
            self.app_icon = None
            log("[설정] 창 아이콘을 넣지 못했습니다: %s" % error)
        title = self._label(bar, i18n.tr("환경설정"), font=self.f_field, color=C_FG,
                            bg=C_PANEL)
        title.pack(side="left", pady=8)
        close = tk.Label(bar, text="×", font=self.f_head, bg=C_PANEL, fg=C_DIM,
                         bd=0, padx=12, highlightthickness=0, cursor="hand2")
        close.pack(side="right")
        close.bind("<Button-1>", lambda _e: self.close())
        close.bind("<Enter>", lambda _e: close.configure(fg=C_FG))
        close.bind("<Leave>", lambda _e: close.configure(fg=C_DIM))
        for widget in (bar, title):
            widget.bind("<Button-1>", self._drag_start)
            widget.bind("<B1-Motion>", self._drag_move)
        return bar

    def _drag_start(self, event):
        self._drag_from = (event.x_root - self.top.winfo_x(),
                           event.y_root - self.top.winfo_y())

    def _drag_move(self, event):
        if self._drag_from is None:
            return
        self.top.geometry("+%d+%d" % (event.x_root - self._drag_from[0],
                                      event.y_root - self._drag_from[1]))

    def _place(self):
        """본 창 한가운데에 놓되, 그 화면 밖으로 나가지 않게 다듬습니다.

        높이는 내용이 요구하는 만큼 씁니다. 화면 배율이 높은 환경에서 pt 로
        지정한 글자가 커지는데, 창을 고정 높이로 두면 아래쪽 항목이 통째로
        잘려 보이지 않습니다. 화면보다 커질 때만 화면에 맞춰 줄입니다.
        """
        self.parent.update_idletasks()
        self.top.update_idletasks()
        width = max(DIALOG_W, self.top.winfo_reqwidth())
        height = max(DIALOG_H, self.top.winfo_reqheight())
        rect = monitor_for_point(self.parent.winfo_x() + 10,
                                 self.parent.winfo_y() + 10)
        if rect:
            width = min(width, rect[2] - 16)
            height = min(height, rect[3] - 60)
        left = self.parent.winfo_x() + (self.parent.winfo_width() - width) // 2
        top = self.parent.winfo_y() + (self.parent.winfo_height() - height) // 2
        if rect:
            m_left, m_top, m_width, m_height = rect
            # 타이틀바와 테두리가 더 붙으므로 그만큼 미리 빼 둡니다.
            left = min(max(left, m_left), m_left + m_width - width)
            top = min(max(top, m_top), m_top + m_height - height - 44)
        # 타이틀바가 없는 창은 Z 순서를 스스로 지키지 못해서, 월페이퍼가 다시
        # 그려질 때마다 본 창 뒤로 숨습니다. 잠깐 쓰는 창이므로 맨 위에 둡니다.
        # **자리를 잡기 전에 걸어야 합니다.** 이 속성을 나중에 주면 Tk 가 창을
        # 다시 만들면서 방금 지정한 위치를 0,0 으로 되돌립니다.
        self.top.attributes("-topmost", True)
        self.top.lift()
        self.top.geometry("%dx%d+%d+%d" % (width, height,
                                           max(0, left), max(0, top)))

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
                                        sticky="w", pady=(9, 2))
        entry = self._entry(parent)
        entry.grid(row=row + 1, column=0, columnspan=2, sticky="we", ipady=4)
        button = tk.Button(parent, image=self.folder_icon, bg=C_FIELD,
                           activebackground=C_LINE, relief="flat", bd=0,
                           highlightthickness=0, cursor="hand2",
                           command=lambda: self._browse(entry))
        button.grid(row=row + 1, column=2, sticky="we", padx=(6, 0), ipadx=8)
        self._label(parent, note, font=self.f_note, color=C_MUTED,
                    wrap=DIALOG_W - 48).grid(
            row=row + 2, column=0, columnspan=3, sticky="w", pady=(2, 0))
        return entry

    def _number_row(self, parent, row, left_title, right_title):
        self._label(parent, left_title).grid(row=row, column=0, sticky="w",
                                             pady=(9, 2))
        self._label(parent, right_title).grid(row=row, column=1, sticky="w",
                                              padx=(14, 0), pady=(9, 2))
        left = self._entry(parent, mono=True)
        left.grid(row=row + 1, column=0, sticky="we", ipady=4)
        right = self._entry(parent, mono=True)
        right.grid(row=row + 1, column=1, sticky="we", padx=(14, 0), ipady=4)
        return left, right

    def _build(self):
        # 테두리가 없는 창이라 배경에 묻히지 않도록 한 줄 선을 두릅니다.
        self.top.configure(highlightthickness=1, highlightbackground=C_LINE,
                           highlightcolor=C_LINE)
        self._title_bar(self.top)
        # 아래쪽 버튼 줄을 먼저 붙여야 합니다. expand 를 쓰는 본문을 먼저 붙이면
        # 본문이 남는 자리를 모두 가져가서 버튼이 잘립니다.
        footer = tk.Frame(self.top, bg=C_PANEL)
        footer.pack(fill="x", side="bottom")
        self._label(footer, i18n.tr("저장하면 config.json 에 적고 감시를 다시 시작합니다."),
                    font=self.f_note, bg=C_PANEL).pack(
            side="left", padx=18, pady=11)
        self._button(footer, i18n.tr("저장"), self.save, C_SKY, "#0b0b0d").pack(
            side="right", padx=(6, 18), pady=9)
        self._button(footer, i18n.tr("취소"), self.close, C_FIELD, C_DIM).pack(
            side="right", pady=9)

        body = tk.Frame(self.top, bg=C_BG)
        body.pack(fill="both", expand=True, padx=18, pady=(4, 0))
        body.columnconfigure(0, weight=1, uniform="col")
        body.columnconfigure(1, weight=1, uniform="col")
        body.columnconfigure(2, minsize=44)

        self.e_dir = self._folder_row(
            body, 1, i18n.tr("녹화 폴더"),
            i18n.tr("녹화 중에 파일이 커지는 폴더입니다. 하위 폴더까지 함께 봅니다."))

        self.e_interval, self.e_stall = self._number_row(
            body, 4, i18n.tr("폴링 주기 (초)"), i18n.tr("중단 판정 시간 (초)"))
        self.e_min_size, self.e_min_growth = self._number_row(
            body, 6, i18n.tr("최소 파일 크기 (MB)"), i18n.tr("시작 판정 증가량 (KB)"))

        self._label(body, i18n.tr("표시할 모니터 번호 (-1 이면 자동)")).grid(
            row=8, column=0, sticky="w", pady=(9, 2))
        self._label(body, i18n.tr("날씨를 볼 도시")).grid(
            row=8, column=1, sticky="w", padx=(14, 0), pady=(9, 2))
        self.e_monitor = self._entry(body, mono=True)
        self.e_monitor.grid(row=9, column=0, sticky="we", ipady=4)
        self.e_city = self._entry(body)
        self.e_city.grid(row=9, column=1, sticky="we", padx=(14, 0), ipady=4)
        self.e_city.bind("<KeyRelease>", self._city_typed)
        self.e_city.bind("<Down>", lambda _e: self._move_suggestion(1))
        self.e_city.bind("<Up>", lambda _e: self._move_suggestion(-1))
        self.e_city.bind("<Return>", self._take_suggestion)
        self.e_city.bind("<Escape>", self._city_escape)
        self._label(body, i18n.tr("도시는 Seo 까지만 적어도 Seoul 이 후보로 나옵니다. "
                                  "골라 두면 그 좌표를 함께 저장합니다."),
                    font=self.f_note, color=C_MUTED, wrap=DIALOG_W - 48).grid(
            row=10, column=0, columnspan=3, sticky="w", pady=(3, 0))

        # 화면에 쓰는 말입니다. 고르는 창을 따로 띄우지 않고 한 줄에 늘어놓아,
        # 지금 무엇이 골라져 있는지 열자마자 보이게 했습니다.
        self._label(body, i18n.tr("화면에 쓰는 말")).grid(
            row=11, column=0, columnspan=3, sticky="w", pady=(9, 2))
        languages = tk.Frame(body, bg=C_BG)
        languages.grid(row=12, column=0, columnspan=3, sticky="w")
        self.v_language = tk.StringVar(value=i18n.language())
        for code, label in i18n.LANGUAGES:
            tk.Radiobutton(
                languages, text=label, value=code, variable=self.v_language,
                font=self.f_label, bg=C_BG, fg=C_DIM, selectcolor=C_FIELD,
                activebackground=C_BG, activeforeground=C_FG, bd=0,
                highlightthickness=0, anchor="w",
                cursor="hand2").pack(side="left", padx=(0, 14))

        checks = tk.Frame(body, bg=C_BG)
        checks.grid(row=13, column=0, columnspan=3, sticky="w", pady=(9, 0))
        self.v_topmost = tk.BooleanVar()
        self.v_beep = tk.BooleanVar()
        for text, var in ((i18n.tr("항상 위"), self.v_topmost),
                          (i18n.tr("소리"), self.v_beep)):
            tk.Checkbutton(
                checks, text=text, variable=var, font=self.f_label, bg=C_BG,
                fg=C_DIM, selectcolor=C_FIELD, activebackground=C_BG,
                activeforeground=C_FG, bd=0, highlightthickness=0,
                anchor="w", cursor="hand2").pack(side="left", padx=(0, 12))

        self.message = self._label(body, "", font=self.f_note, color=C_REC_TEXT,
                                   wrap=DIALOG_W - 48)
        self.message.grid(row=14, column=0, columnspan=3, sticky="w",
                          pady=(8, 0))

    def _button(self, parent, text, command, bg, fg):
        return tk.Button(parent, text=text, command=command, font=self.f_field,
                         bg=bg, fg=fg, activebackground=bg, activeforeground=fg,
                         relief="flat", bd=0, highlightthickness=0,
                         cursor="hand2", padx=18, pady=6)

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
        name = str(settings.get("city") or "")
        put(self.e_city, name)
        if name:
            found = cities.find(name)
            self._city_pick = (name, found[2] if found else "",
                               settings.get("latitude"), settings.get("longitude"))
        self.v_topmost.set(settings["topmost"])
        self.v_beep.set(settings["beep"])
        self.v_language.set(settings.get("language", i18n.DEFAULT))

    # ------------------------------------------------------------ 도시 찾기

    def _city_typed(self, event):
        """글자를 칠 때마다 후보를 새로 고칩니다.

        목록에 담아 둔 도시로 먼저 채워 곧바로 보여 주고, 손을 잠깐 멈추면
        인터넷에서도 찾아 목록에 없는 곳을 뒤에 덧붙입니다.
        """
        if event.keysym in ("Up", "Down", "Return", "Escape", "Tab"):
            return
        text = self.e_city.get().strip()
        self._show_suggestions(cities.match(text))
        if self._suggest_after is not None:
            self.top.after_cancel(self._suggest_after)
            self._suggest_after = None
        if len(text) >= 2:
            self._suggest_after = self.top.after(
                SUGGEST_DELAY, lambda: self._ask_online(text))

    def _ask_online(self, text):
        """지오코딩으로 도시를 찾습니다. 조회는 다른 스레드가 맡습니다."""
        self._suggest_after = None
        self._suggest_seq += 1
        seq = self._suggest_seq

        def work():
            found = weather.geocode(text, 8, self._ssl)
            with self._suggest_lock:
                self._suggest_ready = (seq, text, found)

        threading.Thread(target=work, name="geocode", daemon=True).start()
        if self._suggest_poll is None:
            self._suggest_poll = self.top.after(80, self._poll_online)

    def _poll_online(self):
        """조회 결과를 Tk 스레드에서 받습니다. Tk 는 여기에서만 건드립니다."""
        self._suggest_poll = None
        with self._suggest_lock:
            ready, self._suggest_ready = self._suggest_ready, None
        if ready is None:
            self._suggest_poll = self.top.after(80, self._poll_online)
            return
        seq, text, found = ready
        # 늦게 온 결과와 그새 달라진 입력은 버립니다.
        if seq != self._suggest_seq or text != self.e_city.get().strip():
            return
        rows = cities.match(text)
        seen = {cities.fold(row[0]) for row in rows}
        for name, country, lat, lon in found:
            if cities.fold(name) in seen:
                continue
            seen.add(cities.fold(name))
            rows.append((name, "", country, lat, lon))
        self._show_suggestions(rows)

    def _suggest_text(self, row):
        name, korean, country = row[0], row[1], row[2]
        head = "%s (%s)" % (name, korean) if korean and korean != name else name
        return "   " + (("%s, %s" % (head, country)) if country else head)

    def _show_suggestions(self, rows):
        """입력 칸 바로 아래에 후보를 펼칩니다."""
        self._suggestions = list(rows)[:SUGGEST_ROWS]
        if not self._suggestions:
            self._hide_suggestions()
            return
        if self._suggest_window is None:
            self._suggest_window = tk.Toplevel(self.top)
            self._suggest_window.overrideredirect(True)
            self._suggest_window.configure(bg=C_LINE)
            self._suggest_window.attributes("-topmost", True)
            self._suggest_list = tk.Listbox(
                self._suggest_window, font=self.f_field, bg=C_FIELD, fg=C_FG,
                selectbackground=C_SKY, selectforeground="#0b0b0d",
                relief="flat", bd=0, highlightthickness=0, activestyle="none",
                exportselection=False)
            self._suggest_list.pack(fill="both", expand=True, padx=1, pady=1)
            self._suggest_list.bind("<Button-1>", self._click_suggestion)
        self._suggest_list.delete(0, "end")
        for row in self._suggestions:
            self._suggest_list.insert("end", self._suggest_text(row))
        self._suggest_list.configure(height=len(self._suggestions))
        self._suggest_list.selection_clear(0, "end")
        self._suggest_list.selection_set(0)
        self._suggest_window.deiconify()
        self._suggest_window.update_idletasks()
        # 나라 이름까지 들어가면 입력 칸보다 넓으므로 가장 긴 줄에 맞춥니다.
        # 대신 창 오른쪽 끝을 넘지 않게 자릅니다.
        wide = max(self.f_field.measure(self._suggest_text(row))
                   for row in self._suggest_rows())
        left = self.e_city.winfo_rootx()
        room = self.top.winfo_rootx() + self.top.winfo_width() - left
        width = max(self.e_city.winfo_width(), min(room, wide + 24))
        top = self.e_city.winfo_rooty() + self.e_city.winfo_height()
        height = self._suggest_window.winfo_reqheight()
        # 화면 아래로 넘어가면 입력 칸 위쪽으로 펼칩니다.
        if top + height > self.top.winfo_screenheight() - 8:
            top = max(0, self.e_city.winfo_rooty() - height)
        self._suggest_window.geometry("%dx%d+%d+%d" % (width, height, left, top))

    def _suggest_rows(self):
        return self._suggestions

    def _hide_suggestions(self):
        self._suggestions = []
        if self._suggest_window is not None:
            self._suggest_window.withdraw()

    def _move_suggestion(self, step):
        if not self._suggestions:
            return None
        size = self._suggest_list.size()
        picked = self._suggest_list.curselection()
        index = picked[0] + step if picked else (0 if step > 0 else size - 1)
        index = max(0, min(size - 1, index))
        self._suggest_list.selection_clear(0, "end")
        self._suggest_list.selection_set(index)
        self._suggest_list.see(index)
        return "break"

    def _take_suggestion(self, _event=None):
        if not self._suggestions:
            return None
        picked = self._suggest_list.curselection()
        self._choose_city(self._suggestions[picked[0] if picked else 0])
        return "break"

    def _click_suggestion(self, event):
        index = self._suggest_list.nearest(event.y)
        if 0 <= index < len(self._suggestions):
            self._choose_city(self._suggestions[index])
        return "break"

    def _city_escape(self, _event):
        """후보가 펼쳐져 있으면 그것만 접고 창은 그대로 둡니다."""
        if not self._suggestions:
            return None
        self._hide_suggestions()
        return "break"

    def _choose_city(self, row):
        name, _korean, country, latitude, longitude = row
        self._city_pick = (name, country, latitude, longitude)
        self.e_city.delete(0, "end")
        self.e_city.insert(0, name)
        self._hide_suggestions()
        self.e_city.focus_set()
        self.e_city.icursor("end")
        self.message.config(text="")

    def _resolve_city(self):
        """적어 둔 도시를 좌표로 바꿉니다. 못 찾으면 이름이 ``None`` 입니다."""
        text = self.e_city.get().strip()
        if not text:
            self.message.config(text=i18n.tr("날씨를 볼 도시를 적으십시오."))
            return None, 0.0, 0.0
        if self._city_pick and cities.fold(self._city_pick[0]) == cities.fold(text):
            return self._city_pick[0], self._city_pick[2], self._city_pick[3]
        found = cities.find(text)
        if found:
            return found[0], found[3], found[4]
        # 후보를 고르지 않고 그대로 저장할 때만 여기에서 한 번 조회합니다.
        rows = weather.geocode(text, 1, self._ssl)
        if rows:
            detail("[설정] 도시를 찾았습니다: %s" % (rows[0],))
            return rows[0][0], rows[0][2], rows[0][3]
        self.message.config(text=i18n.tr("%s 을(를) 찾지 못했습니다. 후보에서 고르십시오.") % text)
        return None, 0.0, 0.0

    # ------------------------------------------------------------ 값 다루기

    def _browse(self, entry):
        current = entry.get().strip()
        start = current if os.path.isdir(current) else None
        chosen = dialogs.askdirectory(parent=self.top, initialdir=start,
                                         title=i18n.tr("폴더 선택"))
        if chosen:
            entry.delete(0, "end")
            entry.insert(0, os.path.normpath(chosen))

    def _collect(self):
        """입력값을 검사해서 새 설정을 만듭니다. 잘못되면 None 을 돌려줍니다."""
        watch = self.e_dir.get().strip()
        if not watch:
            self.message.config(text=i18n.tr("녹화 폴더를 지정하십시오."))
            return None
        try:
            interval = float(self.e_interval.get())
            stall = float(self.e_stall.get())
            min_size = float(self.e_min_size.get())
            min_growth = float(self.e_min_growth.get())
            monitor = int(self.e_monitor.get())
        except ValueError:
            self.message.config(text=i18n.tr("숫자 칸에는 숫자만 넣을 수 있습니다."))
            return None
        if interval < 0.2:
            self.message.config(text=i18n.tr("폴링 주기는 0.2초 이상이어야 합니다."))
            return None
        if stall < interval * 2:
            self.message.config(
                text=i18n.tr("중단 판정 시간은 폴링 주기의 두 배 이상이어야 합니다."))
            return None
        if min_size < 0 or min_growth <= 0:
            self.message.config(text=i18n.tr("크기 값은 0보다 커야 합니다."))
            return None
        city, latitude, longitude = self._resolve_city()
        if city is None:
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
            "city": city,
            "latitude": latitude,
            "longitude": longitude,
            "topmost": bool(self.v_topmost.get()),
            "borderless": True,
            "beep": bool(self.v_beep.get()),
            "language": self.v_language.get(),
        })
        if not os.path.isdir(updated["dirs"][0]):
            self.message.config(
                text=i18n.tr("폴더가 없습니다. 경로를 확인하십시오: %s") % updated["dirs"][0])
            return None
        return updated

    def save(self):
        updated = self._collect()
        if updated is None:
            return
        if not save_config(settings_to_config(updated)):
            self.message.config(text=i18n.tr("설정 파일을 쓰지 못했습니다. 로그를 보십시오."))
            return
        log("[설정] 환경설정을 저장했습니다: %s" % settings_to_config(updated))
        self.close()
        self.on_apply(updated)

    def close(self):
        for name in ("_suggest_after", "_suggest_poll"):
            token = getattr(self, name, None)
            if token is not None:
                try:
                    self.top.after_cancel(token)
                except tk.TclError:
                    pass
                setattr(self, name, None)
        # 조회 스레드가 남아 있어도 결과를 받을 곳이 없어 그대로 끝납니다.
        self._suggest_seq += 1
        if self._suggest_window is not None:
            self._suggest_window.destroy()
            self._suggest_window = None
        try:
            self.top.grab_release()
        except tk.TclError:
            pass
        self.top.destroy()
