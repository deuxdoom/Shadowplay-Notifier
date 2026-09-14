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


# **글자는 어느 시간대에나 흰색입니다.** 보조 디스플레이가 작아서 검은 글자는
# 대비를 충분히 확보해도 읽기 어렵고 보기에도 좋지 않았습니다. 그래서 시간대의
# 색을 모두 어둡게 내리고, 그 대신 덮는 정도(``veil``)를 절반 안팎까지 낮춰
# 계절 사진이 어느 시간대에나 비치도록 했습니다. 예전처럼 밝은 색을 짙게
# 덮으면 사진이 사라지고 흰 글자도 묻히므로 그 방식으로 되돌리지 마십시오.
#
# 한 시간대의 값을 고칠 때는 :func:`_needed_veil` 의 기준을 함께 보십시오.
# 덮은 뒤 화면에서 가장 밝은 곳의 휘도가 0.155 이하라야 흰 글자가 4.5:1 로
# 읽힙니다. ``light`` 를 올리려면 그만큼 ``veil`` 도 올려야 합니다.
#
# 시간대는 밝기가 아니라 색조로 나뉩니다. 여명과 노을은 따뜻한 갈색, 낮은
# 하늘의 청회색, 오전과 오후는 금빛, 밤은 남색과 보랏빛입니다. 밤이 낮보다
# 어두운 것은 ``light`` 를 한도보다 낮춰 두었기 때문입니다.
#
# 낮은 12시부터 15시 30분까지 같은 값을 유지하다가 16시 30분을 지나며 노을로
# 넘어갑니다. 그래서 낮 항목이 두 번 나옵니다.
TIMES = (
    Palette("심야", "MIDNIGHT", 0, .40, "#0a1228", .56, 30),
    Palette("새벽", "DAWN", 5, .46, "#232c46", .54, 10),
    Palette("여명", "FIRST LIGHT", 7, .60, "#4a3226", .50, 2),
    Palette("오전", "MORNING", 9, .59, "#46402f", .48, 0),
    Palette("낮", "DAYLIGHT", 12, .59, "#2e404f", .46, 0),
    Palette("낮", "DAYLIGHT", 15.5, .59, "#2e404f", .46, 0),
    Palette("오후", "AFTERNOON", 17.5, .60, "#4a3c2b", .48, 0),
    Palette("노을", "SUNSET", 19, .64, "#4a2e26", .50, 2),
    Palette("저녁", "EVENING", 20, .50, "#2f2234", .55, 8),
)

# 화면에 적는 이름입니다. 낮이 두 번 나오므로 시각으로 따로 고릅니다.
SLOTS = (("심야", "MIDNIGHT"), ("새벽", "DAWN"), ("오전", "MORNING"),
         ("낮", "DAYLIGHT"), ("오후", "AFTERNOON"), ("저녁", "EVENING"))

# 녹화 화면입니다. 붉은 표시가 사진에 묻히지 않도록 가장 어둡게 깔아 둡니다.
REC_GRADE = (.26, (11, 17, 30), .66)

# 화면에서 가장 밝은 곳이 넘어서는 안 되는 휘도입니다. 월페이퍼 글자 가운데
# 가장 어두운 흰색(:data:`component.wallpaper.WALL_INK_3`)이 이 값 위에서
# 4.5:1 로 읽힙니다. 글자를 더 어둡게 만들려면 이 값도 함께 내려야 합니다.
INK_LIMIT = .158

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


@lru_cache(maxsize=512)
def _needed_veil(light, tint):
    """흰 글자가 읽히도록 화면을 덮어야 하는 최소한의 정도입니다.

    사진 한 장에는 새까만 곳과 새하얀 곳이 함께 있습니다. 글자를 언제나 흰색
    으로 쓰기로 했으므로, 사진에서 가장 밝은 곳까지 충분히 어두워져야 합니다.
    휘도 :data:`INK_LIMIT` 는 화면에 쓰는 가장 어두운 흰색이 4.5:1 로 읽히는
    자리입니다.

    :data:`TIMES` 의 값은 이 조건을 이미 만족하므로 평소에는 이 함수가 값을
    올리지 않습니다. 사진을 밝은 것으로 갈아 끼웠을 때를 위한 안전장치입니다.

    예전에는 검은 글자로 바꾸는 길도 열어 두어 밝은 시간대에는 오히려 화면을
    밝히는 쪽을 골랐습니다. 그 방식은 되살리지 마십시오.
    """
    span = 255 * light
    for step in range(0, 96, 2):
        veil = step / 100
        bright = luminance(tuple(min(255., span * (1 - veil) + c * veil) for c in tint))
        if bright <= INK_LIMIT:
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
            g = t * t * (3 - 2 * t)
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


def contrast(pixels, box, ink, width, height):
    """글자 자리에서 가장 낮은 대비를 돌려줍니다. 검사에 씁니다.

    화면에 쓰는 색은 이 값을 보고 고르지 않습니다. 글자는 언제나 흰색이며,
    읽히게 만드는 몫은 시간대의 색과 :func:`_needed_veil` 이 맡습니다.
    """
    if not box or not pixels:
        return 21.0
    light = luminance(ink)
    worst = 21.0
    for y in range(box[1], box[3] + 1, max(1, (box[3] - box[1]) // 4)):
        for x in range(box[0], box[2] + 1, max(1, (box[2] - box[0]) // 12)):
            ground = luminance(sample(pixels, x / width, y / height))
            worst = min(worst, (max(light, ground) + .05) / (min(light, ground) + .05))
    return worst


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
