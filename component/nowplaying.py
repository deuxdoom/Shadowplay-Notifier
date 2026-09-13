"""지금 재생 중인 곡을 알아내는 일입니다.

Spotify 창 제목에서 "아티스트 - 곡" 을 읽습니다. 로그인도 토큰도 필요 없고,
창이 트레이에 내려가 있어도 제목은 남아 있어서 그대로 읽힙니다.

앨범 커버는 세 곳을 차례로 찾습니다. 모두 인증이 필요 없습니다.

1. iTunes 공개 검색 (기본 창고, 안 나오면 일본 창고)
2. Deezer 공개 검색
3. Spotify 가 재생하려고 이미 받아 둔 그림

갓 나온 곡은 iTunes 와 Deezer 의 검색에 며칠 늦게 오릅니다. 그동안에도 커버가
비지 않도록 마지막에 Spotify 가 받아 둔 그림을 찾아봅니다. 지금 듣고 있는 곡의
커버이므로 가장 정확하지만, 곡이 바뀐 무렵에 새로 받은 것만 알아볼 수 있습니다.

곡이 바뀔 때만 한 번 찾고, 받아 둔 그림은 한 장만 들고 있다가 다음 곡에서
갈아 끼웁니다. 저장하거나 쌓아 두지 않습니다.

네트워크가 없거나 어디에서도 찾지 못하면 곡 이름만 나옵니다.
"""

import ctypes
import difflib
import json
import os
import re
import ssl
import struct
import threading
import time
import unicodedata
import urllib.error
import urllib.parse
import urllib.request
from ctypes import byref, wintypes
from dataclasses import dataclass, field

from . import imaging
from .paths import detail, log

PLAYER_EXE = "spotify.exe"
PLAYER_CLASS = "Chrome_WidgetWin_1"
# 재생 중이 아닐 때 창 제목에 그대로 남는 문구들입니다.
IDLE_TITLES = ("spotify", "spotify premium", "spotify free", "광고")

SEARCH_URL = "https://itunes.apple.com/search"
DEEZER_URL = "https://api.deezer.com/search"
# Spotify 가 재생하려고 받아 둔 그림이 쌓이는 곳입니다.
SPOTIFY_CACHE = os.path.join(os.environ.get("LOCALAPPDATA", ""), "Spotify", "Data")
# 앨범 커버로 볼 가장 작은 크기입니다. 이보다 작으면 목록용 썸네일입니다.
MIN_COVER_PX = 240
# 로컬 캐시에는 곡 식별 정보가 없습니다. 검색으로 확인하지 못한 신곡에 한해,
# 곡 전환 직후 생긴 정사각형 그림이 하나뿐일 때만 마지막 수단으로 씁니다.
CACHE_BEFORE = 5.0
CACHE_WINDOW = 20.0
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
              "media": "music", "entity": "song", "limit": 10}
    if country:
        params["country"] = country
    url = SEARCH_URL + "?" + urllib.parse.urlencode(params)
    body = json.loads(_get(url, context).decode("utf-8"))
    return body.get("results") or []


def _normalized(text):
    """검색 서비스마다 다른 공백·기호·대소문자를 비교 가능한 꼴로 만듭니다."""
    value = unicodedata.normalize("NFKC", str(text or "")).casefold()
    value = re.sub(r"[\(\[（【](?:feat\.?|ft\.?|with)\b.*?[\)\]）】]", "", value)
    return "".join(char for char in value if char.isalnum())


def _similarity(expected, actual):
    left, right = _normalized(expected), _normalized(actual)
    if not left or not right:
        return 0.0
    if left == right:
        return 1.0
    if min(len(left), len(right)) >= 4 and (left in right or right in left):
        return 0.92 * min(len(left), len(right)) / max(len(left), len(right)) + 0.08
    return difflib.SequenceMatcher(None, left, right).ratio()


def _best_result(items, artist, title, artist_value, title_value):
    """곡명과 아티스트가 모두 맞는 결과만 고릅니다."""
    best = None
    for item in items:
        title_score = _similarity(title, title_value(item))
        artist_score = _similarity(artist, artist_value(item))
        score = title_score * 0.72 + artist_score * 0.28
        # 제목이 비슷하다는 이유만으로 다른 아티스트의 동명곡을 쓰지 않습니다.
        if title_score < 0.82 or artist_score < 0.55 or score < 0.80:
            continue
        if best is None or score > best[0]:
            best = (score, item)
    return best[1] if best else None


def lookup_cover(artist, title, context, since=None):
    """검증된 검색 결과를 우선하고 로컬 캐시는 마지막에만 봅니다."""
    album = ""
    # 한 창고가 일시적으로 실패해도 다음 창고와 Deezer까지 계속 확인합니다.
    for country in STORES:
        try:
            results = _search(artist, title, country, context)
        except (urllib.error.URLError, ValueError, OSError, TimeoutError) as exc:
            detail("[음악] iTunes 검색 실패(%s): %s" % (country or "기본", exc))
            continue
        item = _best_result(results, artist, title,
                            lambda value: value.get("artistName"),
                            lambda value: value.get("trackName"))
        if not item:
            continue
        album = item.get("collectionName") or album
        art = item.get("artworkUrl100") or ""
        if art:
            try:
                return album, _get(art.replace("100x100bb", COVER_SIZE), context)
            except (urllib.error.URLError, OSError, TimeoutError) as exc:
                detail("[음악] iTunes 커버를 받지 못했습니다: %s" % exc)

    deezer_album, raw = lookup_deezer(artist, title, context)
    album = album or deezer_album or ""
    if raw:
        return album, raw

    if since is not None:
        raw = cached_cover(since)
        if raw:
            detail("[음악] 곡 전환 직후의 단일 Spotify 캐시를 썼습니다")
            return album, raw
    return album, None


def lookup_deezer(artist, title, context):
    """Deezer 공개 검색입니다. iTunes 가 비었을 때 씁니다."""
    query = urllib.parse.urlencode({"q": "%s %s" % (artist, title), "limit": 10})
    try:
        body = json.loads(_get(DEEZER_URL + "?" + query, context).decode("utf-8"))
    except (urllib.error.URLError, ValueError, OSError, TimeoutError) as exc:
        detail("[음악] Deezer 를 물어보지 못했습니다: %s" % exc)
        return None, None
    items = body.get("data") or []
    item = _best_result(items, artist, title,
                        lambda value: (value.get("artist") or {}).get("name"),
                        lambda value: value.get("title"))
    if not item:
        return None, None
    album = item.get("album") or {}
    art = album.get("cover_xl") or album.get("cover_big") or album.get("cover_medium")
    if not art:
        return album.get("title") or "", None
    try:
        raw = _get(art, context)
    except (urllib.error.URLError, OSError, TimeoutError) as exc:
        detail("[음악] Deezer 커버를 받지 못했습니다: %s" % exc)
        return album.get("title") or "", None
    return album.get("title") or "", raw


def _jpeg_size(path):
    """JPEG 머리만 읽어 크기를 구합니다. 그림 전체를 풀지 않아 빠릅니다."""
    try:
        with open(path, "rb") as fp:
            if fp.read(2) != b"\xff\xd8":
                return None
            while True:
                marker = fp.read(2)
                if len(marker) < 2 or marker[0] != 0xFF:
                    return None
                code = marker[1]
                if code in (0xD8, 0xD9) or 0xD0 <= code <= 0xD7:
                    continue
                head = fp.read(2)
                if len(head) < 2:
                    return None
                length = struct.unpack(">H", head)[0]
                if 0xC0 <= code <= 0xCF and code not in (0xC4, 0xC8, 0xCC):
                    fp.read(1)
                    body = fp.read(4)
                    if len(body) < 4:
                        return None
                    height, width = struct.unpack(">HH", body)
                    return width, height
                fp.seek(length - 2, 1)
    except OSError:
        return None


def cached_cover(since):
    """Spotify 가 방금 받아 둔 앨범 커버를 찾습니다.

    갓 나온 곡은 iTunes 와 Deezer 의 검색에 아직 오르지 않습니다. 그런 곡도
    Spotify 는 재생하려고 커버를 이미 받아 두므로, 곡이 바뀐 무렵에 새로 생긴
    정사각형 그림을 이 곡의 커버로 봅니다.

    ``since`` 는 곡이 바뀐 시각입니다. 그 앞뒤 :data:`CACHE_WINDOW` 초 안에
    받은 것만 봅니다. 예전에 들어 이미 받아 둔 곡은 알아볼 수 없지만, 그런
    곡은 검색으로 찾히므로 여기까지 오지 않습니다.
    """
    if not SPOTIFY_CACHE or not os.path.isdir(SPOTIFY_CACHE):
        return None
    candidates = []
    low, high = since - CACHE_BEFORE, min(time.time(), since + CACHE_WINDOW)
    try:
        for root, _dirs, files in os.walk(SPOTIFY_CACHE):
            for name in files:
                path = os.path.join(root, name)
                try:
                    stat = os.stat(path)
                except OSError:
                    continue
                if stat.st_size < 8192 or stat.st_size > 4_000_000:
                    continue
                if not low <= stat.st_mtime <= high:
                    continue
                size = _jpeg_size(path)
                if not size or size[0] != size[1] or size[0] < MIN_COVER_PX:
                    continue
                candidates.append((abs(stat.st_mtime - since), path))
    except OSError as exc:
        detail("[음악] 받아 둔 그림을 훑지 못했습니다: %s" % exc)
        return None
    # 파일 안에는 곡 ID가 없습니다. 후보가 여러 개면 어느 곡인지 증명할 수
    # 없으므로 빈 커버가 잘못된 커버보다 낫다고 판단해 사용하지 않습니다.
    if len(candidates) != 1:
        if candidates:
            detail("[음악] Spotify 캐시 후보가 %d개라 사용하지 않았습니다"
                   % len(candidates))
        return None
    try:
        with open(candidates[0][1], "rb") as fp:
            return fp.read()
    except OSError:
        return None


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
        changed_at = 0.0
        retry_at = None
        retries = 0
        while not self.stop_event.is_set():
            try:
                artist, title = parse_title(read_title())
                key = (artist, title)
                if key != last_key:
                    last_key = key
                    changed_at = time.time()
                    has_cover = self._update(artist, title, changed_at)
                    retries = 0
                    retry_at = (time.monotonic() + 2.0
                                if title and self.want_cover and not has_cover else None)
                elif retry_at is not None and time.monotonic() >= retry_at:
                    if self._retry_cache(artist, title, changed_at):
                        retry_at = None
                    else:
                        retries += 1
                        retry_at = time.monotonic() + 3.0 if retries < 2 else None
            except Exception as exc:
                log("[음악] 곡 정보를 읽다가 멈췄습니다: %s" % exc)
            self.stop_event.wait(self.interval)

    def _update(self, artist, title, changed_at=None):
        if not title:
            self.track = Track()
            self.version += 1
            return False
        # 이름을 먼저 올리고 커버는 뒤따라 채웁니다. 화면이 곧바로 바뀝니다.
        changed_at = time.time() if changed_at is None else changed_at
        self.track = Track(artist=artist, title=title)
        self.version += 1
        if not self.want_cover:
            return False
        album, raw = lookup_cover(artist, title, self._ssl, changed_at)
        # 커버를 받는 동안 곡이 또 바뀌었으면 지금 것을 버립니다.
        if parse_title(read_title()) != (artist, title):
            return False
        accent = imaging.dominant_color(raw) if raw else None
        self.track = Track(artist=artist, title=title, album=album or "",
                           cover=raw, accent=accent)
        self.version += 1
        detail("[음악] %s - %s%s" % (artist, title, " (커버 있음)" if raw else ""))
        return bool(raw)

    def _retry_cache(self, artist, title, changed_at):
        """검색 뒤 늦게 기록된 단일 캐시를 두 번까지만 다시 확인합니다."""
        raw = cached_cover(changed_at)
        if not raw or parse_title(read_title()) != (artist, title):
            return False
        current = self.track
        accent = imaging.dominant_color(raw)
        self.track = Track(artist=artist, title=title, album=current.album,
                           cover=raw, accent=accent)
        self.version += 1
        detail("[음악] 늦게 받은 Spotify 캐시 커버를 적용했습니다")
        return True

    def stop(self):
        self.stop_event.set()
