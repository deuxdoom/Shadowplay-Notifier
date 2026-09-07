"""지정한 모니터에 창을 놓을 물리 좌표를 출력합니다. 캡처 도구가 사용합니다."""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import shadowplay_notifier as sn  # noqa: E402

sn.enable_dpi_awareness()
index = int(sys.argv[1]) if len(sys.argv) > 1 else 1
spot = sn.window_position(index) or (0, 0)
print("%d %d %d %d" % (spot[0], spot[1], sn.WIN_W, sn.WIN_H))
