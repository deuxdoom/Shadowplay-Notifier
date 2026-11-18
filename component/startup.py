"""현재 사용자 계정의 로그인 자동 실행. 메뉴에서 선택할 때만 등록을 바꿉니다."""

import subprocess
import sys
import winreg
from pathlib import Path

from .paths import detail, log

RUN_KEY = r"Software\Microsoft\Windows\CurrentVersion\Run"
VALUE_NAME = "ShadowPlayNotifier"


def command():
    """임시 추출 폴더나 현재 작업 폴더가 아닌 실제 실행 경로를 등록합니다."""
    executable = Path(sys.executable).resolve()
    if getattr(sys, "frozen", False):
        args = [str(executable)]
    else:
        pythonw = executable.with_name("pythonw.exe")
        args = [str(pythonw if pythonw.is_file() else executable),
                str(Path(__file__).resolve().parents[1] / "ShadowPlayNotifier.py")]
    return subprocess.list2cmdline(args)


def is_enabled():
    """메뉴를 열 때 실제 등록을 읽습니다. 다른 위치의 오래된 등록은 체크하지 않습니다."""
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, RUN_KEY, 0, winreg.KEY_READ) as key:
            value, kind = winreg.QueryValueEx(key, VALUE_NAME)
        return kind == winreg.REG_SZ and value == command()
    except FileNotFoundError:
        return False
    except OSError as exc:
        log("[자동 실행] 등록 상태를 읽지 못했습니다: %s" % exc)
        return False


def set_enabled(enabled):
    if enabled:
        value = command()
        # Windows Run 키는 명령줄을 260자까지 지원합니다.
        if len(value.encode("utf-16-le")) // 2 > 260:
            raise ValueError("실행 파일 경로가 너무 깁니다. 더 짧은 폴더로 옮긴 뒤 다시 설정해 주세요.")
        with winreg.CreateKeyEx(winreg.HKEY_CURRENT_USER, RUN_KEY, 0,
                               winreg.KEY_SET_VALUE) as key:
            winreg.SetValueEx(key, VALUE_NAME, 0, winreg.REG_SZ, value)
    else:
        try:
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, RUN_KEY, 0,
                                winreg.KEY_SET_VALUE) as key:
                winreg.DeleteValue(key, VALUE_NAME)
        except FileNotFoundError:
            pass
    detail("[자동 실행] 윈도우 시작 시 실행 %s" % ("켜짐" if enabled else "꺼짐"))
