"""녹화 중 화면입니다. 월페이퍼와 캔버스를 함께 쓰고 내용만 갈아 끼웁니다.

배경과 지평선은 :mod:`component.wallpaper` 가 그대로 맡고, 이 모듈은 그 위에
올라가는 녹화 정보만 맡습니다. 도형은 처음에 모두 만들어 두고 ``reconly``
꼬리표로 함께 보이고 숨깁니다. 월페이퍼로 돌아갈 때 지웠다 다시 만들지
않으므로 전환에 걸리는 시간이 없습니다.

960x640 에서 실측한 자리이며, 창이 커지면 그 비율대로 함께 늘립니다.
"""

import math
import tkinter as tk

from . import sky
from .i18n import tr
from .text import fit_text
from .theme import (INK, INK_2, INK_3, WALL_UI_FAMILIES, pick_font,
                    round_rect)

# 960x640 을 기준으로 잰 세로 자리입니다. 큰 숫자는 월페이퍼 시계와 같은
# 높이에 두어 화면이 바뀔 때 눈이 옮겨 가지 않게 했습니다.
REC_LABEL_Y, REC_FOLDER_Y, REC_BIG_Y = 58, 116, 248
REC_RATE_Y, REC_GROW_Y, REC_FILE_Y = 318, 358, 392
REC_BOTTOM_Y, BADGE_SIZE, LOG_GAP = 452, 112, 36
STATUS_Y = 602

# 이벤트 로그에 남기는 줄 수입니다. 멀리서 흘끗 보는 화면이라 최근 것만
# 남깁니다. 본 창이 들고 있는 기록의 길이도 이 값을 따릅니다.
LOG_ROWS = 3

# 녹화 표시는 흐려지면 안 되므로 밝기를 낮추는 대신 더 밝은 쪽으로 흔듭니다.
REC_RED, REC_RED_LIT = "#ff4d4d", "#ff9090"
REC_TIME_INK = "#ff6b6b"
REC_BADGE_BG, REC_BADGE_EDGE = "#bf2a2a", "#ff9b9b"
STATUS_INK = "#77839a"
LOG_START_INK, LOG_STOP_INK = "#ff8080", "#7cc4f7"
REC_NUMERIC_FAMILIES = ("Segoe UI Light", "Segoe UI", "Pretendard JP", "Arial")


class RecordingLayer:
    """캔버스 위에 녹화 정보를 그리는 켜입니다.

    자리와 글꼴 크기는 :meth:`place` 가 창 크기를 받아 다시 잡습니다.
    월페이퍼 화면이 그 값을 함께 쥐고 있으므로 두 화면의 여백이 어긋나지 않습니다.
    """

    def __init__(self, canvas, parent):
        self.canvas, self.parent = canvas, parent
        self.fonts = {}
        self.width = self.scale = self.scale_x = self.scale_y = 1
        self._build()

    # ------------------------------------------------------------ 구성

    def _font(self, key, size, families=WALL_UI_FAMILIES, weight="normal"):
        font = pick_font(self.parent, families, size, weight)
        self.fonts[key] = (font, size)
        return font

    def _text(self, font, color=INK, text="", anchor="w"):
        return self.canvas.create_text(0, 0, anchor=anchor, font=font, fill=color,
                                       text=text, tags="reconly")

    def _build(self):
        """만들어 두고 숨겨 놓습니다. 화면을 바꿀 때 꼬리표로 함께 드러냅니다."""
        c = self.canvas
        self.rec_dot = c.create_oval(0, 0, 0, 0, outline="", fill=REC_RED,
                                     tags="reconly")
        self.rec_word = self._text(self._font("recword", -26, weight="bold"),
                                   REC_RED)
        self.rec_folder = self._text(self._font("recfolder", -40), INK)
        f_time = self._font("rectime", -148, REC_NUMERIC_FAMILIES)
        self.rec_time_shadow = self._text(f_time, "#080b12")
        self.rec_time = self._text(f_time, REC_TIME_INK)
        self.rec_size = self._text(self._font("recsize", -88, REC_NUMERIC_FAMILIES),
                                   INK, anchor="e")
        self.rec_unit = self._text(self._font("recunit", -34), INK_3, anchor="e")
        self.rec_rate = self._text(self._font("recrate", -30), INK_2, anchor="e")
        self.rec_grow = self._text(self._font("recgrow", -22), INK_3, anchor="e")
        self.rec_file = self._text(self._font("recfile", -19), "#7d879a", anchor="e")

        # 왼쪽 아래 표시등. 앨범 커버가 있던 자리를 그대로 씁니다.
        self.badge_mat = c.create_polygon(0, 0, 0, 0, fill=REC_BADGE_BG,
                                          outline=REC_BADGE_EDGE, smooth=True,
                                          splinesteps=24, tags="reconly")
        self.badge_ring = c.create_oval(0, 0, 0, 0, outline="", fill="#ffffff",
                                        tags="reconly")
        self.badge_word = self._text(self._font("badge", -15, weight="bold"),
                                     "#ffffff", anchor="center")

        self.log_label = self._text(self._font("loglabel", -14), INK_3,
                                    "E V E N T   L O G")
        f_log = self._font("logrow", -20)
        self.log_items = [self._text(f_log, INK_2) for _ in range(LOG_ROWS)]
        self.status_item = self._text(self._font("status", -18), STATUS_INK)
        c.itemconfigure("reconly", state="hidden")

    # ------------------------------------------------------------ 자리

    def place(self, width, scale_x, scale_y, scale):
        """월페이퍼와 같은 여백을 쓰되 세로 자리는 이 모듈의 기준값을 따릅니다."""
        self.width, self.scale_x, self.scale_y, self.scale = (
            width, scale_x, scale_y, scale)
        for font, size in self.fonts.values():
            font.configure(size=min(-8, round(size * scale)))
        c, sx, sy, s = self.canvas, scale_x, scale_y, scale
        x, right = 60 * sx, width - 60 * sx
        radius = 11 * s
        cy = REC_LABEL_Y * sy
        c.coords(self.rec_dot, x, cy - radius, x + radius * 2, cy + radius)
        c.coords(self.rec_word, x + 36 * s, cy)
        c.coords(self.rec_folder, x, REC_FOLDER_Y * sy)
        c.coords(self.rec_time, x - 8 * s, REC_BIG_Y * sy)
        c.coords(self.rec_time_shadow, x - 8 * s + s, REC_BIG_Y * sy + 2 * s)
        c.coords(self.rec_unit, right, (REC_BIG_Y + 22) * sy)
        c.coords(self.rec_rate, right, REC_RATE_Y * sy)
        c.coords(self.rec_grow, right, REC_GROW_Y * sy)
        c.coords(self.rec_file, right, REC_FILE_Y * sy)
        self._place_size_value()

        side = BADGE_SIZE * s
        top = REC_BOTTOM_Y * sy
        c.coords(self.badge_mat, *round_rect(x, top, side, side, 15 * s))
        ring = 17 * s
        c.coords(self.badge_ring, x + side / 2 - ring, top + side / 2 - ring - 8 * s,
                 x + side / 2 + ring, top + side / 2 + ring - 8 * s)
        c.coords(self.badge_word, x + side / 2, top + side / 2 + 30 * s)

        log_x = x + (BADGE_SIZE + 30) * s
        c.coords(self.log_label, log_x, (REC_BOTTOM_Y + 10) * sy)
        for i, item in enumerate(self.log_items):
            c.coords(item, log_x, (REC_BOTTOM_Y + 44 + i * LOG_GAP) * sy)
        c.coords(self.status_item, x, STATUS_Y * sy)

    def _place_size_value(self):
        """용량 숫자를 단위 왼쪽에 붙여 놓습니다."""
        right = self.width - 60 * self.scale_x
        try:
            box = self.canvas.bbox(self.rec_unit)
        except tk.TclError:
            box = None
        gap = 10 * self.scale
        edge = (box[0] - gap) if box else (right - 60 * self.scale)
        self.canvas.coords(self.rec_size, edge, REC_BIG_Y * self.scale_y)

    # ------------------------------------------------------------ 내용

    def paint(self):
        """녹화 화면으로 넘어올 때 고대비 색과 문구를 칠합니다."""
        c = self.canvas
        c.itemconfigure(self.rec_word, text="R E C O R D I N G", fill=REC_RED)
        c.itemconfigure(self.rec_dot, fill=REC_RED)
        c.itemconfigure(self.rec_time, fill=REC_TIME_INK)
        c.itemconfigure(self.badge_mat, fill=REC_BADGE_BG, outline=REC_BADGE_EDGE)
        c.itemconfigure(self.badge_ring, fill="#ffffff")
        c.itemconfigure(self.badge_word, text="R E C", fill="#ffffff")
        c.itemconfigure(self.rec_size, fill=INK)
        c.itemconfigure(self.rec_rate, fill=INK_2)

    def show(self, folder, elapsed, size, rate, growth, filename):
        """녹화 중일 때 채웁니다. 값은 이미 다듬은 문자열입니다."""
        c = self.canvas
        c.itemconfigure(self.rec_folder,
                        text=fit_text(folder, self.fonts["recfolder"][0],
                                      int(self.width * 0.42)))
        for item in (self.rec_time, self.rec_time_shadow):
            c.itemconfigure(item, text=elapsed)
        number, _, unit = size.partition(" ")
        c.itemconfigure(self.rec_unit, text=unit)
        c.itemconfigure(self.rec_size, text=number)
        self._place_size_value()
        c.itemconfigure(self.rec_rate, text=rate)
        c.itemconfigure(self.rec_grow, text=growth)
        c.itemconfigure(self.rec_file,
                        text=fit_text(filename, self.fonts["recfile"][0],
                                      int(self.width * 0.46)))

    def set_log(self, rows):
        """이벤트 로그를 적습니다. rows 는 (시각, 종류, 내용) 입니다."""
        font = self.fonts["logrow"][0]
        room = int(self.width - (60 + BADGE_SIZE + 30) * self.scale
                   - 60 * self.scale_x)
        for i, item in enumerate(self.log_items):
            if i >= len(rows):
                self.canvas.itemconfigure(item, text="")
                continue
            stamp, kind, text = rows[i]
            # ``kind`` 는 색을 고르는 이름이므로 한국어 원문으로 받고, 화면에
            # 적을 때에만 쓰는 말로 옮깁니다.
            color = (LOG_START_INK if kind == "시작" else
                     LOG_STOP_INK if kind == "중단" else INK_3)
            line = "%s   %s   %s" % (stamp, tr(kind), text) if kind else \
                   "%s   %s" % (stamp, text)
            self.canvas.itemconfigure(item, text=fit_text(line, font, room),
                                      fill=color if kind else INK_3)

    def set_status(self, text):
        """맨 아래 한 줄입니다. 감시 폴더와 주기, 갱신 시각, 세션 누적을 적습니다."""
        font = self.fonts["status"][0]
        room = int(self.width - 120 * self.scale_x - 90 * self.scale)
        self.canvas.itemconfigure(self.status_item, text=fit_text(text, font, room))

    def pulse(self, now):
        """녹화 표시의 맥박입니다.

        흐려지면 안 되므로 어두워지는 대신 더 밝은 쪽으로만 흔듭니다.
        크기도 함께 키워서 멀리서도 켜져 있는 것이 보입니다.
        """
        k = 0.5 - 0.5 * math.cos(now * 2 * math.pi)
        color = sky.to_hex(sky.mix(sky._rgb(REC_RED), sky._rgb(REC_RED_LIT), k))
        self.canvas.itemconfigure(self.rec_dot, fill=color)
        s, sx, sy = self.scale, self.scale_x, self.scale_y
        x = 60 * sx
        radius = (11 + 1.4 * k) * s
        cy = REC_LABEL_Y * sy
        self.canvas.coords(self.rec_dot, x, cy - radius, x + radius * 2, cy + radius)
        ring = (17 + 2.2 * k) * s
        cx = x + BADGE_SIZE * s / 2
        top = REC_BOTTOM_Y * sy + BADGE_SIZE * s / 2 - 8 * s
        self.canvas.coords(self.badge_ring, cx - ring, top - ring,
                           cx + ring, top + ring)
