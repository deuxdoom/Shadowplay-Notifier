"""날씨를 받아 오는 일입니다. Open-Meteo 를 씁니다.

API 키가 필요 없고 표준 라이브러리의 ``urllib`` 만으로 부를 수 있습니다.
기본 위치는 서울이며, ``config.json`` 의 ``latitude`` 와 ``longitude`` 로
바꿀 수 있습니다.

받아 오지 못해도 앱은 그대로 돌아갑니다. 날씨 자리만 비워 둡니다.
녹화 중에는 부르지 않습니다.
"""

import json
import ssl
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass

from .paths import log

API_URL = "https://api.open-meteo.com/v1/forecast"
TIMEOUT = 8.0
USER_AGENT = "ShadowPlayNotifier"

# 기상청과 같은 WMO 코드입니다. 아이콘 이름과 한국어 표현을 함께 둡니다.
WMO = {
    0: ("sunny", "맑음"),
    1: ("sunny", "대체로 맑음"),
    2: ("partly_cloudy", "구름 조금"),
    3: ("cloudy", "흐림"),
    45: ("fog", "안개"),
    48: ("fog", "서리 안개"),
    51: ("drizzle", "약한 이슬비"),
    53: ("drizzle", "이슬비"),
    55: ("drizzle", "짙은 이슬비"),
    56: ("rain_snow", "어는 이슬비"),
    57: ("rain_snow", "짙게 어는 이슬비"),
    61: ("rain", "약한 비"),
    63: ("rain", "비"),
    65: ("rain", "강한 비"),
    66: ("rain_snow", "어는 비"),
    67: ("rain_snow", "강하게 어는 비"),
    71: ("snow", "약한 눈"),
    73: ("snow", "눈"),
    75: ("snow", "강한 눈"),
    77: ("snowflake", "싸락눈"),
    80: ("showers", "약한 소나기"),
    81: ("showers", "소나기"),
    82: ("showers", "강한 소나기"),
    85: ("snow_showers", "소낙눈"),
    86: ("snow_showers", "강한 소낙눈"),
    95: ("thunder", "뇌우"),
    96: ("thunder", "우박 동반 뇌우"),
    99: ("thunder", "강한 우박 뇌우"),
}

# 하늘 그림을 고를 때 쓰는 묶음입니다.
SKY_GROUP = {
    "sunny": "clear", "partly_cloudy": "cloudy", "cloudy": "cloudy",
    "fog": "fog", "drizzle": "rain", "rain": "rain", "showers": "rain",
    "rain_snow": "snow", "snow": "snow", "snowflake": "snow",
    "snow_showers": "snow", "thunder": "storm",
}


@dataclass
class Weather:
    """화면에 그대로 올릴 수 있는 날씨입니다."""

    ok: bool = False
    temp: float = None
    feels: float = None
    humidity: int = None
    code: int = None
    tmax: float = None
    tmin: float = None
    precip: int = None      # 지금 시각의 강수 확률
    precip_max: int = None  # 오늘 가장 높은 강수 확률
    is_day: bool = True
    updated_at: float = 0.0

    @property
    def icon(self):
        return WMO.get(self.code, ("cloudy", ""))[0]

    @property
    def text(self):
        return WMO.get(self.code, ("cloudy", "—"))[1]

    @property
    def sky(self):
        return SKY_GROUP.get(self.icon, "cloudy")


def fetch(latitude, longitude, context=None):
    """지금 날씨를 한 번 받아 옵니다. 실패하면 ``ok`` 가 False 입니다."""
    query = urllib.parse.urlencode({
        "latitude": "%.4f" % latitude,
        "longitude": "%.4f" % longitude,
        "current": "temperature_2m,relative_humidity_2m,apparent_temperature,"
                   "weather_code,is_day",
        # 강수 확률은 시간별 값에만 있어서 지금 한 시간치를 함께 받습니다.
        "hourly": "precipitation_probability",
        "daily": "temperature_2m_max,temperature_2m_min,"
                 "precipitation_probability_max",
        "timezone": "auto",
        "forecast_days": "1",
        "forecast_hours": "1",
    })
    request = urllib.request.Request(API_URL + "?" + query,
                                     headers={"User-Agent": USER_AGENT})
    try:
        with urllib.request.urlopen(request, timeout=TIMEOUT,
                                    context=context) as resp:
            body = json.loads(resp.read().decode("utf-8"))
    except (urllib.error.URLError, ValueError, OSError, TimeoutError) as exc:
        log("[날씨] 받아 오지 못했습니다: %s" % exc)
        return Weather()
    try:
        cur = body["current"]
        daily = body.get("daily") or {}
        hourly = body.get("hourly") or {}
        return Weather(
            ok=True,
            temp=cur.get("temperature_2m"),
            feels=cur.get("apparent_temperature"),
            humidity=cur.get("relative_humidity_2m"),
            code=cur.get("weather_code"),
            tmax=(daily.get("temperature_2m_max") or [None])[0],
            tmin=(daily.get("temperature_2m_min") or [None])[0],
            precip=(hourly.get("precipitation_probability") or [None])[0],
            precip_max=(daily.get("precipitation_probability_max") or [None])[0],
            is_day=bool(cur.get("is_day", 1)),
            updated_at=time.time(),
        )
    except (KeyError, TypeError, IndexError) as exc:
        log("[날씨] 응답을 읽지 못했습니다: %s" % exc)
        return Weather()


class WeatherWatch(threading.Thread):
    """날씨를 주기적으로 받아 두는 스레드입니다.

    화면 쪽에서는 :attr:`current` 와 :attr:`version` 만 읽으면 됩니다.
    """

    def __init__(self, latitude, longitude, interval=600.0):
        super().__init__(name="weather", daemon=True)
        self.latitude = latitude
        self.longitude = longitude
        self.interval = max(120.0, float(interval))
        self.current = Weather()
        self.version = 0
        self.stop_event = threading.Event()
        self._ssl = ssl.create_default_context()

    def run(self):
        fails = 0
        while not self.stop_event.is_set():
            got = fetch(self.latitude, self.longitude, self._ssl)
            if got.ok:
                fails = 0
                self.current = got
                self.version += 1
                log("[날씨] %s %.1f℃ 습도 %s%% 강수 %s%%"
                    % (got.text, got.temp, got.humidity, got.precip))
                wait = self.interval
            else:
                # 실패가 이어지면 간격을 늘려 가며 기다립니다.
                fails = min(fails + 1, 5)
                wait = min(self.interval, 30.0 * (2 ** (fails - 1)))
            self.stop_event.wait(wait)

    def stop(self):
        self.stop_event.set()
