"""config.json 을 읽고 쓰며, 명령줄 인자와 합쳐 최종 설정을 만듭니다.

명령줄 인자가 config.json 보다 우선합니다.
"""

import argparse
import json
import math
import os

from . import cities, i18n
from .paths import CONFIG_PATH, log
from .scan import DEFAULT_PATTERNS

DEFAULT_CONFIG = {
    "dir": "E:\\shadowplay record",
    # 다른 녹화 프로그램이 저장하는 폴더입니다. 비워 두면 그 프로그램은 보지
    # 않습니다. 어느 폴더든 판정 방식은 ShadowPlay 와 같습니다.
    "avermedia_dir": "",
    "veyra_dir": "",
    "outdir": "",
    "interval": 0.5,
    "stall": 8.0,
    "min_size": 1048576,
    "min_growth": 262144,
    # 파일이 쓰기로 열려 있는지를 함께 보고 시작과 중단을 곧바로 잡습니다.
    # 끄면 크기 증가와 stall 만으로 판정하므로 중단 표시가 stall 초만큼 늦습니다.
    "fast_detect": True,
    # 게임 녹화에 알림음이 섞이면 안 되므로 기본은 꺼 둡니다.
    "beep": False,
    "topmost": False,
    "borderless": True,
    "monitor": -1,
    # 날씨를 볼 곳입니다. 기본값은 서울입니다. 환경설정에서 도시 이름으로
    # 고르며, 고른 곳의 좌표가 함께 적힙니다.
    "city": "Seoul",
    "latitude": 37.5665,
    "longitude": 126.9780,
    # 화면에 쓰는 말입니다. ko / en / ja 가운데 하나이며 기본은 한국어입니다.
    "language": "ko",
    # 시계를 24시간으로 볼지 정합니다. 월페이퍼의 시계를 누르면 바뀌고,
    # 12시간으로 두면 날짜 줄 아래에 AM/PM 이 함께 나옵니다.
    "clock_24h": True,
}

# 월페이퍼 화면을 다시 그리는 빠르기입니다. 기본값으로 충분하므로 설정
# 화면에는 내놓지 않고, 직접 적어 두면 읽어 씁니다.
WALLPAPER_FPS_DEFAULT = 30

# 기본 파일에는 넣지 않지만, 직접 적어 두면 읽어 쓰는 값들입니다.
ADVANCED_KEYS = ("patterns", "recursive", "wallpaper_fps", "verbose_log")

# 녹화 프로그램마다 (설정 안의 폴더 목록 키, config.json 키, 녹화 화면에 적는
# 짧은 이름, 환경설정에 적는 이름) 입니다. ShadowPlay 는 게임마다 하위 폴더를
# 만들므로 녹화 화면에 그 폴더 이름을 적고, 나머지는 한 폴더에 모아 저장하므로
# 프로그램 이름을 적습니다.
SHADOWPLAY = "ShadowPlay"
RECORDERS = (
    ("dirs", "dir", SHADOWPLAY, SHADOWPLAY),
    ("avermedia_dirs", "avermedia_dir", "AVerMedia", "AVerMedia Streaming Center"),
    ("veyra_dirs", "veyra_dir", "Veyra", "Veyra"),
)


def watch_dirs(settings):
    """감시할 폴더를 프로그램 순서대로 모두 모읍니다. 같은 폴더는 한 번만 넣습니다."""
    seen, found = set(), []
    for key, _config_key, _name, _title in RECORDERS:
        for path in settings.get(key) or ():
            folded = os.path.normcase(os.path.normpath(path))
            if folded not in seen:
                seen.add(folded)
                found.append(path)
    return found


def recorder_of(path, settings):
    """파일이 든 녹화 프로그램의 (이름, 감시 폴더) 입니다. 모르면 빈 문자열 둘입니다.

    한 폴더가 다른 폴더 안에 있으면 더 깊은 쪽을 고릅니다. 예를 들어
    ShadowPlay 폴더 안에 Veyra 폴더를 두어도 Veyra 녹화는 Veyra 로 적힙니다.
    """
    best = ("", "")
    for key, _config_key, name, _title in RECORDERS:
        for root in settings.get(key) or ():
            try:
                rel = os.path.relpath(path, root)
            except ValueError:
                continue
            if rel == os.pardir or rel.startswith(os.pardir + os.sep):
                continue
            if len(root) > len(best[1]):
                best = (name, root)
    return best


def load_config():
    """설정 파일을 읽습니다. 없으면 기본값으로 새로 만듭니다."""
    cfg = dict(DEFAULT_CONFIG)
    if os.path.isfile(CONFIG_PATH):
        try:
            with open(CONFIG_PATH, "r", encoding="utf-8") as fp:
                user = json.load(fp)
            if isinstance(user, dict):
                cfg.update(user)
            else:
                log("[설정] config.json 최상위가 객체가 아니어서 기본값을 사용합니다.")
        except (OSError, ValueError) as exc:
            log("[설정] config.json 을 읽지 못해 기본값을 사용합니다: %s" % exc)
    else:
        write_config(DEFAULT_CONFIG)
        log("[설정] 기본 config.json 을 만들었습니다: %s" % CONFIG_PATH)
    return cfg


def write_config(values):
    """설정 파일에 그대로 씁니다. 성공 여부를 돌려줍니다.

    같은 폴더의 임시 파일에 끝까지 쓴 뒤 바꿔 끼웁니다. 시계를 누를 때마다
    쓰는 파일이라, 쓰는 도중 전원이 나가면 반쯤 쓰인 파일이 남아 다음에
    켤 때 설정이 기본값으로 돌아가기 때문입니다.
    """
    tmp_path = "%s.%d.tmp" % (CONFIG_PATH, os.getpid())
    try:
        try:
            with open(tmp_path, "w", encoding="utf-8") as fp:
                json.dump(values, fp, ensure_ascii=False, indent=2)
                fp.write("\n")
                fp.flush()
                os.fsync(fp.fileno())
            os.replace(tmp_path, CONFIG_PATH)
        except BaseException:
            try:
                os.remove(tmp_path)
            except OSError:
                pass
            raise
        return True
    except OSError as exc:
        log("[설정] config.json 을 쓰지 못했습니다: %s" % exc)
        return False


def save_config(values):
    """기존 파일의 값을 살리면서 넘겨받은 값을 덮어씁니다.

    지금 쓰지 않는 키는 함께 지웁니다. 예전 판에서 쓰던 ntfy 관련 값이
    파일에 남아 헷갈리는 일을 막기 위해서입니다.
    """
    merged = dict(DEFAULT_CONFIG)
    if os.path.isfile(CONFIG_PATH):
        try:
            with open(CONFIG_PATH, "r", encoding="utf-8") as fp:
                current = json.load(fp)
            if isinstance(current, dict):
                keep = set(DEFAULT_CONFIG) | set(ADVANCED_KEYS)
                dropped = [k for k in current if k not in keep]
                if dropped:
                    log("[설정] 쓰지 않는 항목을 지웠습니다: %s" % ", ".join(dropped))
                merged.update({k: v for k, v in current.items() if k in keep})
        except (OSError, ValueError):
            pass
    merged.update(values)
    return write_config(merged)


def nearest_city_name(latitude, longitude):
    """좌표에 맞는 도시 이름을 목록에서 찾습니다. 멀면 빈 문자열입니다.

    도시 이름이 없던 때의 ``config.json`` 을 그대로 읽어도 화면에 이름이
    나오게 하려는 것입니다. 0.25도는 대략 25km 안쪽입니다.
    """
    best, gap = "", 0.25
    for name, _korean, _country, lat, lon in cities.CITIES:
        span = abs(lat - latitude) + abs(lon - longitude)
        if span < gap:
            best, gap = name, span
    return best


def as_list(value):
    if not value:
        return []
    if isinstance(value, str):
        return [value]
    return list(value)


def normalize(paths):
    return [os.path.abspath(os.path.expandvars(os.path.expanduser(p)))
            for p in paths if p]


def parse_args(argv):
    ap = argparse.ArgumentParser(description="ShadowPlay 녹화 상태 모니터")
    ap.add_argument("--dir", action="append", default=None)
    ap.add_argument("--outdir", action="append", default=None)
    ap.add_argument("--pattern", action="append", default=None)
    ap.add_argument("--interval", type=float, default=None)
    ap.add_argument("--stall", type=float, default=None)
    ap.add_argument("--min-size", type=int, default=None)
    ap.add_argument("--min-growth", type=int, default=None)
    ap.add_argument("--monitor", type=int, default=None)
    ap.add_argument("--no-recursive", action="store_true")
    ap.add_argument("--beep", dest="beep", action="store_true", default=None)
    ap.add_argument("--no-beep", dest="beep", action="store_false")
    ap.add_argument("--fast-detect", dest="fast_detect", action="store_true",
                    default=None)
    ap.add_argument("--no-fast-detect", dest="fast_detect", action="store_false")
    ap.add_argument("--topmost", dest="topmost", action="store_true",
                    default=None)
    ap.add_argument("--no-topmost", dest="topmost", action="store_false")
    ap.add_argument("--borderless", dest="borderless", action="store_true",
                    default=None, help=argparse.SUPPRESS)
    # 예전 바로가기 인자를 계속 읽되 창은 항상 프레임리스로 표시합니다.
    ap.add_argument("--no-borderless", dest="borderless", action="store_false",
                    help=argparse.SUPPRESS)
    try:
        return ap.parse_args(argv)
    except SystemExit:
        # --noconsole 로 빌드하면 오류 문구가 보이지 않으므로 로그로 남깁니다.
        log("[인자] 명령줄 인자를 해석하지 못해 config.json 값만 사용합니다: %s"
            % " ".join(argv))
        return ap.parse_args([])


def _number(convert, value, key, fallback):
    """값을 숫자로 바꿉니다. 바꿀 수 없으면 기본값을 쓰고 기록을 남깁니다.

    config.json 의 숫자 자리에 글자가 들어 있으면 float()/int() 가 터져
    앱이 창도 띄우지 못하고 끝나기 때문입니다.
    """
    try:
        number = convert(value)
        if isinstance(number, float) and not math.isfinite(number):
            raise ValueError(value)
        return number
    except (TypeError, ValueError, OverflowError):
        log("[설정] %s 값이 올바르지 않아 기본값을 씁니다" % key)
        return fallback


def build_settings(cfg, args):
    """config.json 위에 명령줄 인자를 덮어써서 최종 설정을 만듭니다."""

    def pick(arg_value, key, fallback):
        if arg_value is not None:
            return arg_value
        value = cfg.get(key, fallback)
        return fallback if value is None else value

    def number(convert, arg_value, key, fallback):
        return _number(convert, pick(arg_value, key, fallback), key, fallback)

    # 0.0 도 올바른 좌표이므로 값이 없을 때만 서울 좌표를 씁니다.
    latitude = number(float, None, "latitude", 37.5665)
    longitude = number(float, None, "longitude", 126.9780)

    patterns = tuple(p.lower() for p in (args.pattern
                                         or as_list(cfg.get("patterns"))) if p)
    return {
        "dirs": normalize(args.dir or as_list(cfg.get("dir"))),
        "avermedia_dirs": normalize(as_list(cfg.get("avermedia_dir"))),
        "veyra_dirs": normalize(as_list(cfg.get("veyra_dir"))),
        "outdirs": normalize(args.outdir or as_list(cfg.get("outdir"))),
        "patterns": patterns or DEFAULT_PATTERNS,
        "interval": max(0.2, number(float, args.interval, "interval", 0.5)),
        "stall": max(1.0, number(float, args.stall, "stall", 8.0)),
        "min_size": number(int, args.min_size, "min_size", 1024 * 1024),
        "min_growth": number(int, args.min_growth, "min_growth", 256 * 1024),
        "recursive": bool(cfg.get("recursive", True)) and not args.no_recursive,
        "beep": bool(pick(args.beep, "beep", False)),
        "fast_detect": bool(pick(args.fast_detect, "fast_detect", True)),
        "topmost": bool(pick(args.topmost, "topmost", False)),
        "borderless": True,
        "monitor": number(int, args.monitor, "monitor", -1),
        "latitude": latitude,
        "longitude": longitude,
        # 화면에 쓰는 말입니다. 여기에서 정해 두면 뒤에 만드는 창들이 모두
        # 같은 말로 나옵니다.
        "language": i18n.set_language(cfg.get("language", i18n.DEFAULT)),
        "clock_24h": bool(cfg.get("clock_24h", True)),
        # 화면에 적는 이름입니다. 예전 설정 파일에는 없으므로, 비어 있으면
        # 좌표에 맞는 도시를 목록에서 찾아 채웁니다.
        "city": str(cfg.get("city") or "").strip() or nearest_city_name(
            latitude, longitude),
        # monitor.log 에 자세한 기록까지 남길지 정합니다. 문제를 찾을 때만 켭니다.
        "verbose_log": bool(cfg.get("verbose_log", False)),
        "wallpaper_fps": max(12, min(40, number(
            int, None, "wallpaper_fps", WALLPAPER_FPS_DEFAULT)
            or WALLPAPER_FPS_DEFAULT)),
    }


def settings_to_config(settings):
    """지금 적용 중인 설정을 config.json 에 적을 형태로 바꿉니다."""
    def paths_value(values):
        # 경로 하나는 기존 문자열 형식을 유지하고, 여러 경로는 모두 보존합니다.
        return list(values) if len(values) > 1 else (values[0] if values else "")

    return {
        "dir": paths_value(settings["dirs"]),
        "avermedia_dir": paths_value(settings.get("avermedia_dirs") or []),
        "veyra_dir": paths_value(settings.get("veyra_dirs") or []),
        "outdir": paths_value(settings["outdirs"]),
        "interval": settings["interval"],
        "stall": settings["stall"],
        "min_size": settings["min_size"],
        "min_growth": settings["min_growth"],
        "fast_detect": settings["fast_detect"],
        "beep": settings["beep"],
        "topmost": settings["topmost"],
        "borderless": settings["borderless"],
        "monitor": settings["monitor"],
        "city": settings.get("city", ""),
        "latitude": settings["latitude"],
        "longitude": settings["longitude"],
        "language": settings.get("language", i18n.DEFAULT),
        "clock_24h": bool(settings.get("clock_24h", True)),
    }
