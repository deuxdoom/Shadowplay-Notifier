"""시간과 날씨에 물드는 어두운 지평선. 작은 RGB 장면만 계산하고 GDI+로 확대합니다.

사진이나 프레임 캐시 없이 시간·날씨·앨범색으로 장면을 만듭니다.
텍스트는 어두운 왼쪽에, 빛은 오른쪽에 모아 상시 표시 화면의 대비를 지킵니다.
"""

import math

from . import imaging

SMALL_W, SMALL_H = 240, 160


def _rgb(color):
    return tuple(int(color[i:i + 2], 16) for i in (1, 3, 5))


class Palette:
    def __init__(self, name, label, hour, sky, glow, stars):
        self.name, self.label, self.hour = name, label, hour
        self.sky = tuple(_rgb(c) for c in sky)
        self.glow, self.stars = _rgb(glow), stars


TIMES = (
    Palette("심야", "M I D N I G H T", 2,
            ("#060a13", "#101828", "#080d15", "#080b10"), "#8eacdf", 30),
    Palette("여명", "F I R S T   L I G H T", 6,
            ("#100e19", "#272235", "#1e1c29", "#0c0d13"), "#edb398", 12),
    Palette("아침", "M O R N I N G", 9,
            ("#08131a", "#18303b", "#111e29", "#080f14"), "#afd8d9", 0),
    Palette("한낮", "D A Y L I G H T", 13.5,
            ("#09121d", "#1b304a", "#111f30", "#080e16"), "#98c4f0", 0),
    Palette("해질녘", "G O L D E N   H O U R", 17.5,
            ("#170f19", "#37232b", "#271c25", "#100c12"), "#f0aa7e", 5),
    Palette("밤", "N I G H T F A L L", 21,
            ("#070c16", "#132437", "#101b29", "#080c13"), "#82bfcf", 26),
)

SKIES = {
    "clear": {"clouds": 0, "fog": 0, "dim": 0, "star_mul": 1},
    "cloudy": {"clouds": .7, "fog": 0, "dim": .12, "star_mul": .2},
    "rain": {"clouds": .8, "fog": .3, "dim": .20, "star_mul": 0},
    "snow": {"clouds": .45, "fog": .2, "dim": .10, "star_mul": 0},
    "storm": {"clouds": 1, "fog": .2, "dim": .28, "star_mul": 0},
    "fog": {"clouds": .2, "fog": 1, "dim": .13, "star_mul": .05},
}


def blend_palette(hour):
    """시간상 이웃한 팔레트를 보간합니다. 자정에서도 연속입니다."""
    hour %= 24
    for i, first in enumerate(TIMES):
        second = TIMES[(i + 1) % len(TIMES)]
        span = (second.hour - first.hour) % 24
        elapsed = (hour - first.hour) % 24
        if elapsed <= span:
            t = elapsed / span
            near = first if t < .5 else second
            return {"name": near.name, "label": near.label,
                    "sky": [mix(a, b, t) for a, b in zip(first.sky, second.sky)],
                    "glow": mix(first.glow, second.glow, t),
                    "stars": round(first.stars + (second.stars - first.stars) * t),
                    "night": hour < 7 or hour >= 19}


def mix(a, b, t):
    t = max(0, min(1, t))
    return tuple(round(a[k] + (b[k] - a[k]) * t) for k in range(3))


def to_hex(color):
    return "#%02x%02x%02x" % color


def gradient_color(palette, y):
    stops = (0, .44, .70, 1)
    for i in range(3):
        if y <= stops[i + 1]:
            return mix(palette["sky"][i], palette["sky"][i + 1],
                       (y - stops[i]) / (stops[i + 1] - stops[i]))
    return palette["sky"][-1]


def render(width, height, palette, accent=None, group="clear", phase=0):
    """대기·얇은 지평선·안개를 합성한 작은 RGB 버퍼입니다.

    phase는 느린 구름 이동에만 사용합니다.
    창의 화면비가 바뀌어도 배경의 상대 위치는 같습니다.
    """
    spec = SKIES.get(group, SKIES["clear"])
    sw, sh = SMALL_W, SMALL_H
    glow = mix(palette["glow"], (143, 170, 186), spec["dim"] * 1.8)
    music = accent or glow
    output = bytearray(sw * sh * 3)
    for y in range(sh):
        yr = y / (sh - 1)
        base = gradient_color(palette, yr)
        for x in range(sw):
            xr = x / (sw - 1)
            # 부드러운 빛은 오른쪽에 모아 왼쪽의 글자 대비를 지킵니다.
            halo = math.exp(-((xr - .77) / .30) ** 2 - ((yr - .39) / .30) ** 2)
            light = .13 * halo * (1 - spec["dim"])
            color = [base[k] + glow[k] * light for k in range(3)]
            # 넓은 번짐과 매우 얇은 빛을 함께 굽습니다.
            horizon = .677 + .065 * ((xr - .75) / .8) ** 2
            distance = yr - horizon
            span = math.exp(-((xr - .76) / .47) ** 2)
            beam = (math.exp(-(distance / .026) ** 2) * .095 +
                    math.exp(-(distance / .005) ** 2) * .14) * span
            music_light = math.exp(-((xr - .31) / .40) ** 2 - ((yr - .89) / .21) ** 2) * .075
            cloud = 0
            if spec["clouds"] or spec["fog"]:
                bend = .035 * math.sin(xr * 8 + phase)
                cloud = math.exp(-((yr - .49 - bend) / .047) ** 2)
                cloud += .5 * math.exp(-((yr - .59 + bend) / .072) ** 2)
                cloud *= spec["clouds"] * .07 * halo
                cloud += spec["fog"] * .105 * math.exp(-((yr - .61 - bend) / .12) ** 2)
            # 결정적이고 1 LSB 미만인 디더. 움직이는 노이즈가 없습니다.
            noise = (((x * 73 + y * 37) % 19) / 19 - .5) * .85
            floor = max(0, min(1, (yr - horizon) / .055))
            for k in range(3):
                value = color[k] * (1 - floor * .30)
                value += glow[k] * (beam + cloud) + music[k] * music_light
                output[(y * sw + x) * 3 + k] = max(0, min(255, round(value + noise)))
    return bytes(output)


def sample(pixels, x, y):
    """캔버스의 알파 대용: 실제 구운 장면의 해당 위치를 표본 추출합니다."""
    ix = max(0, min(SMALL_W - 1, round(x * (SMALL_W - 1))))
    iy = max(0, min(SMALL_H - 1, round(y * (SMALL_H - 1))))
    i = (iy * SMALL_W + ix) * 3
    return tuple(pixels[i:i + 3]) if pixels else (8, 12, 19)


def interpolate(first, second, fraction):
    """한 번의 전환에 버퍼 두 개만 보유하며 중간 프레임은 버립니다."""
    return bytes(round(a + (b - a) * fraction) for a, b in zip(first, second))


def bake(width, height, palette, accent=None, group="clear"):
    return imaging.upscale_rgb(render(width, height, palette, accent, group),
                               SMALL_W, SMALL_H, width, height)

