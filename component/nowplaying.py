"""지금 재생 중인 곡을 알아내는 일입니다.

Spotify 창 제목에서 "아티스트 - 곡" 을 읽습니다. 로그인도 토큰도 필요 없고,
창이 트레이에 내려가 있어도 제목은 남아 있어서 그대로 읽힙니다.

앨범 커버는 iTunes 의 공개 검색으로 주소를 얻어 받아 옵니다. 이것도 인증이
없습니다. 곡이 바뀔 때만 한 번 물어보고, 받아 둔 그림은 한 장만 들고 있다가
다음 곡에서 갈아 끼웁니다. 저장하거나 쌓아 두지 않습니다.

네트워크가 없거나 검색이 빗나가도 곡 이름은 그대로 나옵니다.
"""

import ctypes
import json
import ssl
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from ctypes import byref, wintypes
from dataclasses import dataclass, field

from . import imaging
from .paths import log

PLAYER_EXE = "spotify.exe"
PLAYER_CLASS = "Chrome_WidgetWin_1"
# 재생 중이 아닐 때 창 제목에 그대로 남는 문구들입니다.
IDLE_TITLES = ("spotify", "spotify premium", "spotify free", "광고")

SEARCH_URL = "https://itunes.apple.com/search"
# 찾아볼 창고 차례입니다. None 은 기본(미국) 창고입니다. 한국 창고는
# 음원이 거의 없어서 넣지 않습니다.
STORES = (None, "JP")
COVER_SIZE = "600x600bb"
USER_AGENT = "ShadowPlayNotifier"
TIMEOUT = 6.0

user32 = ctypes.windll.user32
kernel32 = ctypes.windll.kernel32

kernel32.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
kernel32.OpenProcess.restype = wintypes.HANDLE
kernel32.QueryFullProcessImageNameW.argtypes = [
    wintypes.HANDLE, wintypes.DWORD, wintypes.LPWSTR, ctypes.POINTER(wintypes.DWORD)]
kernel32.CloseHandle.argtypes = [wintypes.HANDLE]

PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
WNDENUMPROC = ctypes.WINFUNCTYPE(ctypes.c_bool, wintypes.HWND, wintypes.LPARAM)


@dataclass
class Track:
    """화면에 그대로 올릴 수 있는 곡 정보입니다."""

    artist: str = ""
    title: str = ""
    album: str = ""
    cover: bytes = field(default=None, repr=False)
    accent: tuple = None

    @property
    def key(self):
        return (self.artist, self.title)

    def is_playing(self):
        return bool(self.title)


_exe_cache = {}


def _exe_name(pid):
    """프로세스 실행 파일 이름을 소문자로 돌려줍니다."""
    if pid in _exe_cache:
        return _exe_cache[pid]
    name = ""
    handle = kernel32.OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION, False, pid)
    if handle:
        try:
            size = wintypes.DWORD(260)
            buf = ctypes.create_unicode_buffer(size.value)
            if kernel32.QueryFullProcessImageNameW(handle, 0, buf, byref(size)):
                name = buf.value.rsplit("\\", 1)[-1].lower()
        finally:
            kernel32.CloseHandle(handle)
    if len(_exe_cache) > 256:
        _exe_cache.clear()
    _exe_cache[pid] = name
    return name


def read_title():
    """Spotify 창 제목을 읽습니다. 없으면 빈 문자열입니다."""
    found = []

    def on_window(hwnd, _):
        cls = ctypes.create_unicode_buffer(64)
        user32.GetClassNameW(hwnd, cls, 64)
        if cls.value != PLAYER_CLASS:
            return True
        length = user32.GetWindowTextLengthW(hwnd)
        if not length:
            return True
        buf = ctypes.create_unicode_buffer(length + 1)
        user32.GetWindowTextW(hwnd, buf, length + 1)
        title = buf.value.strip()
        if not title:
            return True
        pid = wintypes.DWORD()
        user32.GetWindowThreadProcessId(hwnd, byref(pid))
        if _exe_name(pid.value) == PLAYER_EXE:
            found.append(title)
            return False
        return True

    try:
        user32.EnumWindows(WNDENUMPROC(on_window), 0)
    except Exception as exc:
        log("[음악] 창 목록을 읽지 못했습니다: %s" % exc)
        return ""
    return found[0] if found else ""


def parse_title(title):
    """"아티스트 - 곡" 을 나눕니다. 재생 중이 아니면 빈 값입니다."""
    if not title or title.strip().lower() in IDLE_TITLES:
        return "", ""
    if " - " not in title:
        return "", ""
    artist, _, name = title.partition(" - ")
    return artist.strip(), name.strip()


def _get(url, context):
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(request, timeout=TIMEOUT, context=context) as resp:
        return resp.read()


def _search(artist, title, country, context):
    params = {"term": "%s %s" % (artist, title),
              "media": "music", "entity": "song", "limit": 1}
    if country:
        params["country"] = country
    url = SEARCH_URL + "?" + urllib.parse.urlencode(params)
    body = json.loads(_get(url, context).decode("utf-8"))
    return body.get("results") or []


def lookup_cover(artist, title, context):
    """앨범 이름과 커버 그림을 찾아 옵니다. 못 찾으면 (None, None) 입니다."""
    results = []
    try:
        # 기본 창고에서 먼저 찾고, 없으면 일본 창고를 봅니다. 일본어로 적힌
        # 아티스트 이름은 기본 창고에서 걸리지 않는 일이 많습니다.
        for country in STORES:
            results = _search(artist, title, country, context)
            if results:
                break
    except (urllib.error.URLError, ValueError, OSError, TimeoutError) as exc:
        log("[음악] 커버를 찾지 못했습니다: %s" % exc)
        return None, None
    if not results:
        return None, None
    item = results[0]
    album = item.get("collectionName") or ""
    art = item.get("artworkUrl100") or ""
    if not art:
        return album, None
    try:
        raw = _get(art.replace("100x100bb", COVER_SIZE), context)
    except (urllib.error.URLError, OSError, TimeoutError) as exc:
        log("[음악] 커버를 받지 못했습니다: %s" % exc)
        return album, None
    return album, raw


class NowPlaying(threading.Thread):
    """곡이 바뀌는지 지켜보고 바뀌면 커버까지 챙겨 놓는 스레드입니다.

    화면 쪽에서는 :attr:`track` 과 :attr:`version` 만 읽으면 됩니다.
    ``version`` 이 달라졌을 때만 화면을 고쳐 그리면 됩니다.
    """

    def __init__(self, interval=1.0, want_cover=True):
        super().__init__(name="now-playing", daemon=True)
        self.interval = max(0.5, float(interval))
        self.want_cover = want_cover
        self.track = Track()
        self.version = 0
        self.stop_event = threading.Event()
        self._ssl = ssl.create_default_context()

    def run(self):
        last_key = None
        while not self.stop_event.is_set():
            try:
                artist, title = parse_title(read_title())
                key = (artist, title)
                if key != last_key:
                    last_key = key
                    self._update(artist, title)
            except Exception as exc:
                log("[음악] 곡 정보를 읽다가 멈췄습니다: %s" % exc)
            self.stop_event.wait(self.interval)

    def _update(self, artist, title):
        if not title:
            self.track = Track()
            self.version += 1
            return
        # 이름을 먼저 올리고 커버는 뒤따라 채웁니다. 화면이 곧바로 바뀝니다.
        self.track = Track(artist=artist, title=title)
        self.version += 1
        if not self.want_cover:
            return
        album, raw = lookup_cover(artist, title, self._ssl)
        # 커버를 받는 동안 곡이 또 바뀌었으면 지금 것을 버립니다.
        if self.track.key != (artist, title):
            return
        accent = imaging.dominant_color(raw) if raw else None
        self.track = Track(artist=artist, title=title, album=album or "",
                           cover=raw, accent=accent)
        self.version += 1
        log("[음악] %s - %s%s" % (artist, title, " (커버 있음)" if raw else ""))

    def stop(self):
        self.stop_event.set()
