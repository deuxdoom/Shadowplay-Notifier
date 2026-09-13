"""설정과 로그 파일의 위치를 정하고 기록을 남깁니다."""

import os
import sys
import threading
import time
import traceback


def base_dir():
    """PyInstaller onefile 로 묶어도 EXE 가 놓인 폴더를 돌려줍니다.

    onefile 로 실행하면 ``__file__`` 은 임시 추출 폴더를 가리키므로,
    설정과 로그는 반드시 이 함수가 돌려주는 경로 기준으로 다루어야 합니다.
    """
    if getattr(sys, "frozen", False):
        return os.path.dirname(sys.executable)
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def resource_dir():
    """글꼴처럼 함께 묶어 배포하는 자료가 들어 있는 곳입니다.

    ``base_dir`` 과 달리 onefile 로 묶으면 임시 추출 폴더를 가리킵니다.
    설정과 로그는 EXE 옆에, 읽기만 하는 자료는 여기에 있습니다.
    """
    if getattr(sys, "frozen", False):
        return getattr(sys, "_MEIPASS", os.path.dirname(sys.executable))
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


BASE_DIR = base_dir()
RESOURCE_DIR = resource_dir()
CONFIG_PATH = os.path.join(BASE_DIR, "config.json")
LOG_PATH = os.path.join(BASE_DIR, "monitor.log")

_log_lock = threading.Lock()


_verbose = False


def set_verbose(on):
    """자세한 기록을 남길지 정합니다. config.json 의 verbose_log 로 켭니다."""
    global _verbose
    _verbose = bool(on)


def detail(message):
    """평소에는 남기지 않는 기록입니다.

    글꼴 등록이나 곡이 바뀐 일처럼 늘 일어나는 것은 여기로 보냅니다.
    monitor.log 에는 녹화와 오류만 남아야 무엇이 잘못되었는지 눈에 띕니다.
    """
    if _verbose:
        log(message)


def log(message):
    """--noconsole 로 빌드하므로 화면 출력 대신 파일에 남깁니다."""
    line = "%s  %s" % (time.strftime("%Y-%m-%d %H:%M:%S"), message)
    with _log_lock:
        try:
            with open(LOG_PATH, "a", encoding="utf-8") as fp:
                fp.write(line + "\n")
        except OSError:
            pass


def install_excepthook():
    """어디서 터지든 흔적이 monitor.log 에 남도록 합니다."""

    def hook(exc_type, exc, tb):
        log("[예외] " + "".join(
            traceback.format_exception(exc_type, exc, tb)).rstrip())

    sys.excepthook = hook

    def thread_hook(info):
        log("[스레드 예외] " + "".join(traceback.format_exception(
            info.exc_type, info.exc_value, info.exc_traceback)).rstrip())

    if hasattr(threading, "excepthook"):
        threading.excepthook = thread_hook
