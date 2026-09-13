"""작성 시점 전용: SVG 원본에서 여러 해상도의 EXE/트레이 ICO를 만듭니다.

Pillow는 ICO 저장에만 사용되며 앱 런타임과 EXE에는 포함되지 않습니다.
python test/build_icon.py
"""

import io
import base64
from pathlib import Path
import tkinter as tk

from PIL import Image

BASE = Path(__file__).resolve().parents[1]
root = tk.Tk()
root.withdraw()
svg = (BASE / "assets" / "appicon.svg").read_text(encoding="utf-8")
photo = tk.PhotoImage(master=root, data=svg, format="svg -scaletowidth 1024")
png = root.tk.call(str(photo), "data", "-format", "png")
with Image.open(io.BytesIO(png)) as source:
    source.save(BASE / "appicon.ico", format="ICO",
                sizes=[(n, n) for n in (16, 20, 24, 32, 40, 48, 64, 128, 256)])
    source.resize((256, 256), Image.Resampling.LANCZOS).save(BASE / "test" / "shot_appicon.png")
    sizes = (16, 24, 32, 48)
    blocks = ["APP_SIZES = " + repr(sizes)]
    for size in sizes:
        output = io.BytesIO()
        source.resize((size, size), Image.Resampling.LANCZOS).save(output, format="PNG")
        encoded = base64.b64encode(output.getvalue()).decode("ascii")
        lines = ['    "' + encoded[i:i + 76] + '"' for i in range(0, len(encoded), 76)]
        blocks.append("APP_%d = (\n%s\n)" % (size, "\n".join(lines)))
    icons_file = BASE / "component" / "icons.py"
    previous = icons_file.read_text(encoding="utf-8")
    prefix = previous[:previous.index("APP_SIZES =")]
    icons_file.write_text(prefix + "\n\n".join(blocks) + "\n", encoding="utf-8")
root.destroy()
