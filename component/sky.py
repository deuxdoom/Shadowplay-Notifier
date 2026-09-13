"""사계절 풍경에 시간대의 빛과 앨범 색을 합성하는 오프라인 배경입니다."""

import colorsys
import math
import time
from functools import lru_cache
from pathlib import Path
from array import array

from . import imaging
from .paths import RESOURCE_DIR, detail

SMALL_W, SMALL_H = 480, 320
SEASONS = {
    "spring": ("봄", "S P R I N G", (255, 218, 229)),
    "summer": ("여름", "S U M M E R", (173, 233, 243)),
    "autumn": ("가을", "A U T U M N", (255, 221, 182)),
    "winter": ("겨울", "W I N T E R", (220, 235, 250)),
}


def _rgb(color):
    return tuple(int(color[i:i + 2], 16) for i in (1, 3, 5))


class Palette:
    """한 시간대의 색 규칙입니다.

    ``light`` 는 사진의 밝기를 얼마나 살릴지, ``tint`` 는 그 위에 입히는 색,
    ``veil`` 은 그 색의 불투명도입니다. 셋 다 화면 전체에 똑같이 적용합니다.
    자리마다 다르게 덧칠하면 얼룩이 져서 지저분해 보입니다.
    """

    def __init__(self, name, label, hour, light, tint, veil, stars):
        self.name, self.label, self.hour = name, label, hour
        self.light, self.glow, self.veil, self.stars = light, _rgb(tint), veil, stars


# 심야와 저녁만 색을 뚜렷하게 씁니다. 나머지 시간대는 채도를 낮춘 색을 옅게
# 덮어 사진 본래의 색이 비치도록 합니다. 짙은 색을 덮으면 사진이 물들어 버립니다.
#
# **밝은 시간대의 veil 을 0.50 아래로 내리지 마십시오.** 사진의 어두운 부분
# 위에 검은 글자가 얹히면 읽을 수 없게 됩니다. 낮에 색을 아예 빼는 방안을
# 검토했지만 바로 이 문제로 접었습니다.
#
# 낮은 12시부터 15시 30분까지 같은 값을 유지하다가 16시 30분을 지나며 노을로
# 넘어갑니다. 그래서 낮 항목이 두 번 나옵니다.
# 7시와 19시 항목은 밤과 낮이 뒤바뀌는 순간입니다. 이때는 배경이 중간 밝기라
# 글자를 읽으려면 많이 덮어야 하므로, 잿빛 대신 여명과 노을의 따뜻한 색을
# 지나가게 했습니다. 밝은 색일수록 덜 덮어도 되어 사진도 더 남습니다.
TIMES = (
    Palette("심야", "MIDNIGHT", 0, .26, "#0a1228", .72, 30),
    Palette("새벽", "DAWN", 5, .42, "#232c46", .60, 10),
    Palette("여명", "FIRST LIGHT", 7, .80, "#f2c9a6", .54, 2),
    Palette("오전", "MORNING", 9, .98, "#ffe3bd", .54, 0),
    Palette("낮", "DAYLIGHT", 12, 1.12, "#eff9ff", .49, 0),
    Palette("낮", "DAYLIGHT", 15.5, 1.12, "#eff9ff", .49, 0),
    Palette("오후", "AFTERNOON", 17.5, 1.00, "#ffdda8", .55, 0),
    Palette("노을", "SUNSET", 19, .76, "#f6c6a6", .54, 2),
    Palette("저녁", "EVENING", 20, .50, "#402e46", .64, 8),
)

# 화면에 적는 이름입니다. 낮이 두 번 나오므로 시각으로 따로 고릅니다.
SLOTS = (("심야", "MIDNIGHT"), ("새벽", "DAWN"), ("오전", "MORNING"),
         ("낮", "DAYLIGHT"), ("오후", "AFTERNOON"), ("저녁", "EVENING"))

# 녹화 화면입니다. 붉은 표시가 사진에 묻히지 않도록 가장 어둡게 깔아 둡니다.
REC_GRADE = (.26, (11, 17, 30), .66)

SKIES = {
    "clear": {"fog": 0, "dim": 0, "star_mul": 1},
    "cloudy": {"fog": .10, "dim": .06, "star_mul": .2},
    "rain": {"fog": .14, "dim": .12, "star_mul": 0},
    "snow": {"fog": .19, "dim": .03, "star_mul": 0},
    "storm": {"fog": .16, "dim": .18, "star_mul": 0},
    "fog": {"fog": .32, "dim": .06, "star_mul": .05},
}


def season_for_month(month):
    return ("winter", "spring", "summer", "autumn")[(month % 12) // 3]


def _flips(first, second):
    """밤과 낮이 뒤바뀌는 구간인지 봅니다. 글자 색이 반대로 바뀌는 자리입니다."""
    return (luminance(first.glow) < .19) != (luminance(second.glow) < .19)


@lru_cache(maxsize=512)
def _needed_veil(light, tint):
    """글자가 읽히도록 화면을 덮어야 하는 최소한의 정도입니다.

    사진 한 장에는 새까만 곳과 새하얀 곳이 함께 있습니다. 흰 글자를 쓰려면
    가장 밝은 곳까지 충분히 어두워야 하고, 검은 글자를 쓰려면 가장 어두운
    곳까지 충분히 밝아야 합니다. 둘 중 먼저 이루어지는 쪽을 따릅니다.

    시간대가 바뀌는 동안에는 색이 중간 밝기를 지나므로 이 값이 잠시 커집니다.
    그 덕분에 색 자체는 서두르지 않고 천천히 물들어 갈 수 있습니다.
    """
    span = 255 * light
    for step in range(0, 96, 2):
        veil = step / 100
        dark = luminance(tuple(c * veil for c in tint))
        bright = luminance(tuple(min(255., span * (1 - veil) + c * veil) for c in tint))
        if bright <= .175 or dark >= .190:
            return veil
    return .96


def blend_palette(hour, season=None):
    """한국의 달력 계절과 여섯 시간대. 자정을 포함해 빛은 연속입니다."""
    season = season or season_for_month(time.localtime().tm_mon)
    hour %= 24
    for i, first in enumerate(TIMES):
        second = TIMES[(i + 1) % len(TIMES)]
        span = (second.hour - first.hour) % 24
        elapsed = (hour - first.hour) % 24
        if elapsed <= span:
            t = elapsed / span
            name, label = SLOTS[0 if hour >= 22 or hour < 4 else
                                1 if hour < 7 else 2 if hour < 11 else
                                3 if hour < 16 else 4 if hour < 19 else 5]
            # 시작과 끝에서 부드럽게 붙는 곡선입니다. 색은 시간대 내내 천천히
            # 옮겨 가고, 글자를 읽을 수 있게 하는 몫은 veil 이 맡습니다.
            # 다만 밤과 낮이 뒤바뀌는 구간만은 가운데를 조금 빠르게 지납니다.
            # 그 중간 밝기에서는 화면을 거의 다 덮어야 글자가 읽히기 때문입니다.
            g = (.5 + .5 * math.tanh((t - .5) * 6) if _flips(first, second)
                 else t * t * (3 - 2 * t))
            light = first.light + (second.light - first.light) * g
            glow = mix(first.glow, second.glow, g)
            veil = first.veil + (second.veil - first.veil) * g
            veil = max(veil, _needed_veil(round(light, 3), glow))
            return {"name": name, "label": label,
                    "season": season, "light": light, "glow": glow, "veil": veil,
                    "sky": (mix((12, 19, 34), glow, light),) * 4,
                    "stars": round(first.stars + (second.stars - first.stars) * t),
                    "night": hour < 7 or hour >= 19}


def mix(a, b, t):
    t = max(0, min(1, t))
    return tuple(round(a[k] + (b[k] - a[k]) * t) for k in range(3))


def to_hex(color):
    return "#%02x%02x%02x" % color


def horizon_y(x):
    return .707 + .016 * ((x - .5) / .5) ** 2


def _photo_path(season):
    """사진을 갈아 끼울 때 확장자를 가리지 않도록 둘 다 찾아봅니다."""
    folder = Path(RESOURCE_DIR) / "assets" / "wallpapers"
    for suffix in (".png", ".jpg", ".jpeg"):
        path = folder / (season + suffix)
        if path.is_file():
            return path
    raise OSError("%s 계절 사진이 없습니다" % season)


@lru_cache(maxsize=4)
def _photo(season, aspect):
    """크기별 프레임을 쌓지 않고 최대 네 장만 보관합니다."""
    try:
        data = _photo_path(season).read_bytes()
        w, h = (round(SMALL_H * aspect), SMALL_H)
        rgb = imaging.photo_rgb(data, w, h)
        if w == SMALL_W:
            return rgb
        ppm = imaging.upscale_rgb(rgb, w, h, SMALL_W, SMALL_H)
        return ppm.split(b"\n", 3)[3]
    except (OSError, ValueError) as exc:
        detail("[월페이퍼] 계절 사진을 읽지 못했습니다: %s" % exc)
        return bytes(SEASONS[season][2]) * (SMALL_W * SMALL_H)


@lru_cache(maxsize=1)
def _masks():
    """자리마다 달라지는 것만 한 번 계산해 둡니다.

    시간대의 색은 화면 전체에 똑같이 입히므로 여기에 들어오지 않습니다.
    남은 것은 음악 자리를 만드는 아래쪽 바닥과 앨범 색 번짐, 지평선 빛입니다.
    """
    masks = tuple(array("f") for _ in range(4))
    for y in range(SMALL_H):
        yr = y / (SMALL_H - 1)
        floor = 1 / (1 + math.exp(-(yr - .704) * 40))
        for x in range(SMALL_W):
            xr = x / (SMALL_W - 1)
            bloom = math.exp(-((xr - .22) / .55) ** 2 - ((yr - .85) / .15) ** 2)
            ribbon = math.exp(-((xr - .62) / .46) ** 2 - ((yr - .93) / .18) ** 2)
            beam = math.exp(-((yr - horizon_y(xr)) / .0035) ** 2) * .08
            for mask, value in zip(masks, (floor, bloom, ribbon, beam)):
                mask.append(value)
    return masks


def render(width, height, palette, accent=None, group="clear", phase=0):
    """사진 위에 시간대의 색을 균일하게 입히고 아래에 음악 자리를 만듭니다.

    시간대의 색과 불투명도는 화면 어디에서나 같습니다. 글자가 놓인 자리만
    따로 밝히면 얼룩이 져서 지저분해 보이므로 그렇게 하지 않습니다.
    """
    spec = SKIES.get(group, SKIES["clear"])
    aspect = round(max(.125, min(8., width / max(1, height))), 4)
    photo = _photo(palette["season"], aspect)
    if palette.get("recording"):
        light, tint, veil = REC_GRADE
    else:
        light, tint, veil = palette["light"], palette["glow"], palette["veil"]
    # 계절의 기운은 밝은 시간대에만 아주 옅게 섞습니다. 많이 섞으면 사진이
    # 그 색으로 물들고, 밤에 섞으면 남색이 흐려집니다.
    tone = (tint[0] * .2126 + tint[1] * .7152 + tint[2] * .0722) / 255
    tint = mix(tint, SEASONS[palette["season"]][2], .07 * tone)
    music = accent or SEASONS[palette["season"]][2]
    h, s, v = colorsys.rgb_to_hsv(*(c / 255 for c in music))
    music = tuple(round(c * 255) for c in colorsys.hsv_to_rgb(h, s, min(.8, max(.48, v))))
    companion = mix(music, tint, .22)
    exposure = light * (1 - spec["dim"])
    # 안개와 비는 같은 색을 조금 더 덮는 것으로 나타냅니다.
    veil = min(.95, veil + spec["fog"] * .45)
    output = bytearray(len(photo))
    for i, (floor, bloom, ribbon, beam) in enumerate(zip(*_masks())):
        for k in range(3):
            base = photo[i * 3 + k] * exposure
            base = base * (1 - veil) + tint[k] * veil
            base = base * (1 - floor * .97) + (9, 14, 22)[k] * floor
            base += music[k] * bloom * floor * .25 + companion[k] * ribbon * floor * .10
            base += tint[k] * beam
            output[i * 3 + k] = min(255, max(0, round(base)))
    return bytes(output)


def luminance(rgb):
    linear = [v / 3294.6 if v <= 10.31475 else ((v / 255 + .055) / 1.055) ** 2.4 for v in rgb]
    return sum(a * b for a, b in zip(linear, (.2126, .7152, .0722)))


def foreground(pixels, box, width, height):
    """실제 글자 자리의 밝기를 읽어 검정/흰색 중 대비가 큰 쪽을 고릅니다."""
    if not box or not pixels:
        return "#f5f4f2"
    shades = [luminance(sample(pixels, x / width, y / height))
              for y in range(box[1], box[3] + 1, max(1, (box[3] - box[1]) // 4))
              for x in range(box[0], box[2] + 1, max(1, (box[2] - box[0]) // 12))]
    dark, white = (min(shades) + .05) / .0515, 1.05 / (max(shades) + .05)
    return "#030508" if dark >= white else "#ffffff"


def sample(pixels, x, y):
    ix = max(0, min(SMALL_W - 1, round(x * (SMALL_W - 1))))
    iy = max(0, min(SMALL_H - 1, round(y * (SMALL_H - 1))))
    i = (iy * SMALL_W + ix) * 3
    return tuple(pixels[i:i + 3]) if pixels else (8, 12, 19)


def interpolate(first, second, fraction):
    native = imaging.blend_rgb(first, second, SMALL_W, SMALL_H, fraction)
    return native if native is not None else bytes(
        round(a + (b - a) * fraction) for a, b in zip(first, second))


def bake(width, height, palette, accent=None, group="clear"):
    return imaging.upscale_rgb(render(width, height, palette, accent, group),
                               SMALL_W, SMALL_H, width, height)
