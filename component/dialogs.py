"""앱의 팝업은 모두 프레임리스로 만듭니다. 기본 메시지 상자를 쓰지 않습니다."""

import os
import ctypes
import queue
import threading
import tkinter as tk
from pathlib import Path
from tkinter import ttk

from . import display, icons
from .i18n import tr
from .theme import (C_BG, C_DIM, C_FG, C_FIELD, C_LINE, C_MUTED, C_PANEL,
                    C_SKY, pick_family)


def title_bar(window, title, on_close):
    window.overrideredirect(True)
    window.attributes("-topmost", True)
    window.configure(bg=C_LINE, padx=1, pady=1)
    bar = tk.Frame(window, bg=C_PANEL)
    bar.pack(fill="x")
    icon = tk.PhotoImage(data=icons.APP_16, master=window)
    symbol = tk.Label(bar, image=icon, bg=C_PANEL)
    symbol.image = icon
    symbol.pack(side="left", padx=(12, 8), pady=8)
    family = pick_family(window)
    label = tk.Label(bar, text=title, font=(family, -14), bg=C_PANEL, fg=C_FG)
    label.pack(side="left")
    close = tk.Label(bar, text="×", font=(family, -22), bg=C_PANEL,
                     fg=C_DIM, padx=12, cursor="hand2")
    close.pack(side="right")
    close.bind("<Button-1>", lambda _event: on_close())
    close.bind("<Enter>", lambda _event: close.configure(fg=C_FG))
    close.bind("<Leave>", lambda _event: close.configure(fg=C_DIM))
    origin = [0, 0]

    def drag_start(event):
        origin[:] = [event.x_root - window.winfo_x(), event.y_root - window.winfo_y()]

    def drag_move(event):
        window.geometry("+%d+%d" % (event.x_root - origin[0], event.y_root - origin[1]))

    for widget in (bar, symbol, label):
        widget.bind("<Button-1>", drag_start)
        widget.bind("<B1-Motion>", drag_move)
    window.protocol("WM_DELETE_WINDOW", on_close)
    window.bind("<Escape>", lambda _event: on_close())
    window.bind("<Alt-F4>", lambda _event: on_close())
    return close


def place(window, parent, width):
    window.update_idletasks()
    point = parent.winfo_pointerxy()
    if parent.winfo_viewable():
        point = (parent.winfo_rootx() + parent.winfo_width() // 2,
                 parent.winfo_rooty() + parent.winfo_height() // 2)
    rect = display.monitor_for_point(*point) or (0, 0, window.winfo_screenwidth(), window.winfo_screenheight())
    left, top, screen_w, screen_h = rect
    width = min(width, screen_w - 20)
    height = min(window.winfo_reqheight(), screen_h - 20)
    window.geometry("%dx%d+%d+%d" % (width, height, left + (screen_w - width) // 2,
                                    top + (screen_h - height) // 2))
    window.deiconify()
    window.lift()
    window.focus_force()


def button(parent, text, command, primary=False):
    return tk.Button(parent, text=text, command=command,
                     font=(pick_family(parent), -14),
                     bg=C_SKY if primary else C_FIELD, fg=C_BG if primary else C_FG,
                     activebackground=C_SKY, activeforeground=C_BG,
                     relief="flat", padx=16, pady=7, cursor="hand2")


def show_message(title, message, parent=None):
    owns_root = parent is None
    if owns_root:
        display.enable_dpi_awareness()
        parent = tk.Tk()
        parent.withdraw()
    window = tk.Toplevel(parent)
    window.withdraw()
    window.title(title)
    title_bar(window, title, window.destroy)
    body = tk.Frame(window, bg=C_BG, padx=24, pady=20)
    body.pack(fill="both", expand=True)
    tk.Label(body, text=message, font=(pick_family(body), -15), bg=C_BG, fg=C_FG,
             wraplength=430, justify="left").pack(anchor="w")
    button(body, tr("확인"), window.destroy, True).pack(anchor="e", pady=(20, 0))
    previous_grab = parent.grab_current()
    place(window, parent, 480)
    window.grab_set()
    try:
        parent.wait_window(window)
    finally:
        if owns_root:
            parent.destroy()
        elif previous_grab and previous_grab.winfo_exists():
            previous_grab.grab_set()


class FolderDialog:
    """폴더 선택도 같은 프레임리스 창으로 제공합니다. 폴더 내용은 읽기만 합니다."""
    def __init__(self, parent, initialdir=None, title=None):
        self.parent, self.result = parent, ""
        title = title or tr("폴더 선택")
        self.window = tk.Toplevel(parent)
        self.window.withdraw()
        self.window.title(title)
        self.previous_grab = parent.grab_current()
        title_bar(self.window, title, self.close)
        self.body = tk.Frame(self.window, bg=C_BG, padx=18, pady=16)
        self.body.pack(fill="both", expand=True)
        navigation = tk.Frame(self.body, bg=C_BG)
        navigation.pack(fill="x")
        button(navigation, tr("상위 폴더"), self.up).pack(side="left", padx=(0, 8))
        self.path_var = tk.StringVar()
        family = pick_family(self.window)
        self.address = tk.Entry(navigation, textvariable=self.path_var,
                                font=(family, -14), bg=C_FIELD, fg=C_FG,
                                insertbackground=C_FG, relief="flat")
        self.address.pack(side="left", fill="x", expand=True, ipady=8)
        self.address.bind("<Return>", lambda _event: self.navigate(self.path_var.get()))
        button(navigation, tr("이동"), lambda: self.navigate(self.path_var.get())).pack(side="right", padx=(8, 0))
        mask = ctypes.windll.kernel32.GetLogicalDrives()
        drives = ["%s:\\" % chr(65 + bit) for bit in range(26) if mask & (1 << bit)]
        self.drive = ttk.Combobox(self.body, values=drives, state="readonly",
                                  font=(family, -13))
        self.drive.pack(anchor="w", pady=(12, 8))
        self.drive.bind("<<ComboboxSelected>>", lambda _event: self.navigate(self.drive.get()))
        listing = tk.Frame(self.body, bg=C_BG)
        listing.pack(fill="both", expand=True)
        self.listbox = tk.Listbox(listing, height=10, font=(family, -14),
                                  bg=C_FIELD, fg=C_FG, selectbackground=C_SKY,
                                  selectforeground=C_BG, relief="flat", activestyle="none",
                                  exportselection=False, highlightthickness=1,
                                  highlightbackground=C_LINE, highlightcolor=C_SKY)
        scrollbar = tk.Scrollbar(listing, command=self.listbox.yview)
        scrollbar.pack(side="right", fill="y")
        self.listbox.configure(yscrollcommand=scrollbar.set)
        self.listbox.pack(side="left", fill="both", expand=True)
        self.listbox.bind("<Double-Button-1>", self.open_selected)
        self.listbox.bind("<Return>", self.open_selected)
        self.note = tk.Label(self.body, text="", bg=C_BG, fg=C_MUTED,
                             font=(family, -12), wraplength=530, anchor="w")
        self.note.pack(fill="x", pady=(8, 12))
        buttons = tk.Frame(self.body, bg=C_BG)
        buttons.pack(fill="x")
        button(buttons, tr("취소"), self.close).pack(side="right")
        self.choose = button(buttons, tr("폴더 선택"), self.select, True)
        self.choose.pack(side="right", padx=(0, 8))
        self.events = queue.Queue()
        self.generation = 0
        self.current = None
        self.children = []
        self.closed = False
        self.after_id = self.window.after(80, self.poll)
        self.navigate(initialdir or str(Path.home()))
        place(self.window, parent, 600)
        self.window.grab_set()

    def navigate(self, path):
        path = Path(os.path.abspath(os.path.expanduser(path)))
        self.generation += 1
        generation = self.generation
        self.choose.configure(state="disabled")
        self.listbox.delete(0, "end")
        self.children = []
        self.note.configure(text=tr("폴더를 읽고 있습니다…"))
        self.path_var.set(str(path))
        self.drive.set(path.anchor)

        def read():
            try:
                with os.scandir(path) as entries:
                    directories = sorted((Path(entry.path) for entry in entries if entry.is_dir()),
                                         key=lambda item: item.name.casefold())
                self.events.put((generation, path, directories, None))
            except OSError as exc:
                self.events.put((generation, path, [], str(exc)))

        threading.Thread(target=read, name="folder-list", daemon=True).start()

    def poll(self):
        if self.closed:
            return
        while True:
            try:
                generation, path, directories, error = self.events.get_nowait()
            except queue.Empty:
                break
            if generation != self.generation:
                continue
            self.current = None if error else path
            self.children = directories
            self.listbox.delete(0, "end")
            for child in directories:
                self.listbox.insert("end", child.name)
            self.note.configure(text=tr(
                "폴더를 열 수 없습니다. 경로와 접근 권한을 확인해 주세요." if error else
                "두 번 클릭하면 하위 폴더를 엽니다. 주소를 입력해 이동할 수도 있습니다."))
            self.choose.configure(state="disabled" if error else "normal")
        self.after_id = self.window.after(80, self.poll)

    def open_selected(self, _event=None):
        selected = self.listbox.curselection()
        if selected and selected[0] < len(self.children):
            self.navigate(self.children[selected[0]])

    def up(self):
        if self.current:
            self.navigate(self.current.parent)

    def select(self):
        if self.current and str(self.current) == self.path_var.get():
            selected = self.listbox.curselection()
            chosen = self.children[selected[0]] if selected else self.current
            self.result = str(chosen)
            self.close()
        else:
            self.navigate(self.path_var.get())

    def close(self):
        if self.closed:
            return
        self.closed = True
        self.window.after_cancel(self.after_id)
        self.window.destroy()
        if self.previous_grab and self.previous_grab.winfo_exists():
            self.previous_grab.grab_set()


def askdirectory(parent, initialdir=None, title=None):
    dialog = FolderDialog(parent, initialdir, title)
    parent.wait_window(dialog.window)
    return dialog.result
