r"""보조 디스플레이에 창을 강제로 띄워 960x640 레이아웃을 눈으로 확인합니다.

실행: python test\preview_gui.py [rec|idle] [모니터번호] [표시시간초]
  rec  : 녹화중 화면 (기본값)
  idle : 대기중 화면
모니터 번호는 왼쪽 위 좌표 순서이며 기본값은 1(보조 디스플레이)입니다.
레이아웃 수치는 test\layout_<모드>.txt 로 남습니다.
pythonw 로 실행하면 표준 출력이 없으므로 파일 기록만 남습니다.
"""

import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import tkinter as tk  # noqa: E402
import shadowplay_notifier as sn  # noqa: E402

MODE = sys.argv[1] if len(sys.argv) > 1 else "rec"
MONITOR = int(sys.argv[2]) if len(sys.argv) > 2 else 1
SECONDS = float(sys.argv[3]) if len(sys.argv) > 3 else 12.0
# 네 번째 인자로 nb 를 주면 타이틀바 없는 상태를 확인합니다.
BORDERLESS = "nb" in sys.argv[4:]
HERE = os.path.dirname(os.path.abspath(__file__))
WATCH_DIR = r"E:\shadowplay record"

sn.enable_dpi_awareness()
root = tk.Tk()
root.title("ShadowPlay Notifier")
root.configure(bg=sn.C_BG)
root.resizable(False, False)
root.tk.call("tk", "scaling", 96.0 / 72.0)

def say(*parts):
    """pythonw 에서는 표준 출력이 없으므로 있을 때만 출력합니다."""
    if sys.stdout is not None:
        print(*parts)


rects = sn.monitor_rects()
say("모니터 목록:", rects)
spot = sn.window_position(MONITOR) or (40, 40)
say("표시 위치:", spot, "/ 모드:", MODE)

# 캡처 도구가 쓸 물리 좌표를 남깁니다. 화면 캡처는 배율과 무관한
# 물리 좌표를 쓰므로 DPI 인식이 켜진 이쪽에서 알려 주어야 합니다.
with open(os.path.join(HERE, "monitor_rect.txt"), "w", encoding="utf-8") as fp:
    fp.write("%d %d %d %d\n" % (spot[0], spot[1], sn.WIN_W, sn.WIN_H))
root.geometry("%dx%d+%d+%d" % (sn.WIN_W, sn.WIN_H, spot[0], spot[1]))
if BORDERLESS:
    root.overrideredirect(True)

app = sn.MonitorApp(root, [WATCH_DIR], 1.0, BORDERLESS)

path = os.path.join(WATCH_DIR, "OnimushaWotS",
                    "Onimusha Way of the Sword 2026.09.07 - 11.20.33.04.DVR.mp4")

if MODE == "rec":
    app.queue.put({"kind": "start", "path": path, "size": 0, "at": time.time()})
    app.queue.put({"kind": "state", "active": True, "path": path,
                   "elapsed": 1462.0, "size": 3.7 * 1024 ** 3, "mbps": 71.4,
                   "since_growth": 3.4, "stall": 8.0})
else:
    app.session_count = 3
    app.last_summary = ("직전 녹화: Onimusha 2026.09.07 - 10.02.11.DVR.mp4"
                        " · 0:24:22 · 3.7 GB")
    app.queue.put({"kind": "state", "active": False})

app.add_log("[중단] OnimushaWotS\\Onimusha 2026.09.07 - 10.02.11.DVR.mp4 "
            "(증가 멈춤, 0:24:22, 3.7 GB)", sn.C_SKY)
app.add_log("[시작] OnimushaWotS\\Onimusha 2026.09.07 - 10.02.11.DVR.tmp",
            sn.C_REC_TEXT)
app.add_log("[오류] 감시 폴더를 읽는 중 오류가 발생했습니다", sn.C_YELLOW)
app.queue.put({"kind": "health", "missing": []})
root.update()

lines = ["창 크기: %dx%d" % (root.winfo_width(), root.winfo_height())]
for child in root.winfo_children():
    lines.append("  %-8s y=%4d h=%4d w=%4d" % (
        child.winfo_class(), child.winfo_y(), child.winfo_height(),
        child.winfo_width()))
bottom = max(c.winfo_y() + c.winfo_height() for c in root.winfo_children())
lines.append("가장 아래 끝: %d / %d (여유 %d)" % (bottom, sn.WIN_H,
                                                 sn.WIN_H - bottom))
clipped = [c.winfo_class() for c in root.winfo_children()
           if c.winfo_height() <= 1 or c.winfo_y() + c.winfo_height() > sn.WIN_H]
lines.append("잘린 요소: %s" % (", ".join(clipped) or "없음"))
report = "\n".join(lines)
say(report)
with open(os.path.join(HERE, "layout_%s.txt" % MODE), "w",
          encoding="utf-8") as fp:
    fp.write(report + "\n")

root.after(int(SECONDS * 1000), root.destroy)
root.mainloop()
