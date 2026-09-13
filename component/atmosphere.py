"""잠깐씩 찾아오는 날씨 연출. 모든 도형은 처음에 만들고 계속 재사용합니다."""

import math
import random

from . import sky


class Atmosphere:
    def __init__(self, canvas):
        self.canvas = canvas
        self.rng = random.Random(831)
        self.stars = [(self.rng.uniform(.54, .97), self.rng.uniform(.12, .57),
                       self.rng.uniform(0, math.tau)) for _ in range(30)]
        self.star_items = [canvas.create_oval(0, 0, 0, 0, outline="", state="hidden",
                                              tags="atmosphere") for _ in self.stars]
        self.drops = [(self.rng.choice((self.rng.uniform(.025, .17),
                                       self.rng.uniform(.60, .97))),
                       self.rng.uniform(-.20, .1), self.rng.uniform(.55, 1.5),
                       self.rng.uniform(0, 7)) for _ in range(12)]
        self.rain_items = []
        for _ in self.drops:
            trail = [canvas.create_line(0, 0, 0, 0, smooth=True, capstyle="round",
                                        state="hidden", tags="atmosphere") for _ in range(3)]
            trail.append(canvas.create_oval(0, 0, 0, 0, state="hidden", tags="atmosphere"))
            self.rain_items.append(trail)
        self.snow = [(self.rng.random(), self.rng.random(), self.rng.uniform(.5, 1.3),
                      self.rng.uniform(0, math.tau)) for _ in range(20)]
        self.snow_items = [canvas.create_oval(0, 0, 0, 0, outline="", state="hidden",
                                              tags="atmosphere") for _ in self.snow]
        self.meteor_items = [canvas.create_line(0, 0, 0, 0, capstyle="round",
                                                 state="hidden", tags="atmosphere") for _ in range(12)]
        self.width, self.height, self.scale = 960, 640, 1
        self.group, self.night = None, False
        self.pixels = None
        self.star_count = 0
        self._start, self._next_meteor = 0, 12
        self._meteor = None
        self._star_at = -1

    def configure(self, width, height, palette, group, pixels, now):
        self.width, self.height = width, height
        self.scale = min(width / 960, height / 640)
        self.pixels = pixels
        self.star_count = round(palette["stars"] * sky.SKIES[group]["star_mul"])
        if (group, palette["night"]) != (self.group, self.night):
            self.group, self.night = group, palette["night"]
            self._start, self._next_meteor = now, now + 12
            self._meteor = None
            self.canvas.itemconfigure("atmosphere", state="hidden")
            self._star_at = -1

    def _color(self, x, y, strength, tint=(180, 207, 225)):
        return sky.to_hex(sky.mix(sky.sample(self.pixels, x / self.width,
                                            y / self.height), tint, strength))

    def update(self, now):
        c, w, h, s = self.canvas, self.width, self.height, self.scale
        # 별은 6fps로 충분합니다. 그 사이에는 Tcl 호출도 없습니다.
        if now - self._star_at > .16:
            self._star_at = now
            for i, (item, (x, y, phase)) in enumerate(zip(self.star_items, self.stars)):
                if i >= self.star_count:
                    c.itemconfigure(item, state="hidden")
                    continue
                x, y = x * w, y * h
                if .6 * w < x and .20 * h < y < .66 * h:
                    c.itemconfigure(item, state="hidden")
                    continue
                r = (.65 if i % 5 else 1.05) * s
                a = .16 + .18 * (.5 + .5 * math.sin(now * .45 + phase))
                c.coords(item, x - r, y - r, x + r, y + r)
                c.itemconfigure(item, state="normal", fill=self._color(x, y, a))
        elapsed = now - self._start
        if self.group in ("rain", "storm"):
            self._rain(elapsed)
        elif self.group == "snow":
            self._snow(elapsed)
        if self.night and self.group == "clear":
            self._shooting_star(now)

    def _rain(self, elapsed):
        # 110초 중 22초만 창에 물방울이 맺힙니다. 가속·멈춤·굴절된 꼬리.
        t = (elapsed - 5) % 110
        c, w, h, s = self.canvas, self.width, self.height, self.scale
        for items, (x, y, speed, delay) in zip(self.rain_items, self.drops):
            age = t - delay
            if not 0 <= age <= 15:
                for item in items:
                    c.itemconfigure(item, state="hidden")
                continue
            fade = min(1, age / 2, (15 - age) / 3)
            py = (y + .035 * age * speed + .0018 * age ** 2) * h
            px = x * w + math.sin(age * .65 + delay) * 3 * s
            length = min(64, 6 + age * 5) * s * speed
            for i, item in enumerate(items[:3]):
                low, high = py - length * (i + 1) / 3, py - length * i / 3
                c.coords(item, px - 2 * s, low, px + s, (low + high) / 2, px, high)
                c.itemconfigure(item, state="normal", width=max(1, (2.2 - i * .5) * s),
                                fill=self._color(px, (low + high) / 2, fade * (.14 - .035 * i)))
            r = (1.9 + .5 * speed) * s
            c.coords(items[3], px - r, py - r * 1.4, px + r, py + r)
            c.itemconfigure(items[3], state="normal", width=max(1, s),
                            fill=self._color(px, py, fade * .09),
                            outline=self._color(px, py, fade * .36))

    def _snow(self, elapsed):
        t = (elapsed - 4) % 75
        c, w, h, s = self.canvas, self.width, self.height, self.scale
        for item, (x, y, speed, phase) in zip(self.snow_items, self.snow):
            if t > 26:
                c.itemconfigure(item, state="hidden")
                continue
            fade = min(1, t / 4, (26 - t) / 5)
            px = x * w + math.sin(t * .35 + phase) * 18 * s
            py = ((y + t * .019 * speed) % 1) * h
            r = (1 + speed) * s
            c.coords(item, px - r, py - r, px + r, py + r)
            c.itemconfigure(item, state="normal", fill=self._color(px, py, fade * .36))

    def _shooting_star(self, now):
        if self._meteor is None and now >= self._next_meteor:
            self._meteor = (now, self.rng.uniform(.58, .83), self.rng.uniform(.09, .19))
            self._next_meteor = now + self.rng.uniform(65, 125)
        if self._meteor is None:
            return
        start, x, y = self._meteor
        age = now - start
        if age > 1.8:
            for item in self.meteor_items:
                self.canvas.itemconfigure(item, state="hidden")
            self._meteor = None
            return
        s = self.scale
        fade = min(1, age / .3, (1.8 - age) / .65)
        px, py = x * self.width - age * 210 * s, y * self.height + age * 88 * s
        for i, item in enumerate(self.meteor_items):
            tail = i * 9 * s
            x0, y0 = px + tail, py - tail * .42
            self.canvas.coords(item, x0, y0, x0 + 10 * s, y0 - 4.2 * s)
            self.canvas.itemconfigure(item, state="normal", width=max(1, 1.5 * s),
                                      fill=self._color(x0, y0, fade * (1 - i / 12) ** 2 * .8))
