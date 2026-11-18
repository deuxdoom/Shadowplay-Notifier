# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller 빌드 정의입니다.

빌드:
    pyinstaller --clean ShadowPlayNotifier.spec

--clean 을 붙이는 이유는, 그것이 없으면 PyInstaller 가 이전에 만든 EXE 를 그대로
재사용해서 바뀐 아이콘이 조용히 무시되기 때문입니다.

완성본은 언제나 dist/ShadowPlayNotifier.exe 한 곳에 생깁니다. 작업 폴더는
--workpath 로 옮길 수 있지만 --distpath 는 받지 않습니다. 다 구운 뒤에는 EXE 에
들어간 번호가 component/version.py 와 같은지 확인하고 크기와 SHA-256 을 알립니다.

appicon.ico 파일이 프로젝트 폴더에 있으면 EXE 아이콘으로 넣고, 없으면 아이콘 없이
빌드합니다.
"""

import hashlib
import os
import re

NAME = "ShadowPlayNotifier"
DESCRIPTION = "ShadowPlay 녹화 상태 모니터"


def read_meta(name, fallback):
    """버전과 작성자는 component/version.py 한 곳에서만 관리합니다."""
    path = os.path.join(SPECPATH, "component", "version.py")
    with open(path, encoding="utf-8") as fp:
        found = re.search(r'^%s\s*=\s*"([^"]+)"' % name, fp.read(), re.M)
    return found.group(1) if found else fallback


def version_resource(version, author):
    """윈도우 파일 속성 창에 보이는 버전 정보를 만듭니다."""
    from PyInstaller.utils.win32.versioninfo import (
        FixedFileInfo, StringFileInfo, StringStruct, StringTable, VarFileInfo,
        VarStruct, VSVersionInfo)

    numbers = tuple(int(part) for part in version.split(".")[:3]) + (0,)
    return VSVersionInfo(
        ffi=FixedFileInfo(filevers=numbers, prodvers=numbers, mask=0x3F,
                          flags=0x0, OS=0x40004, fileType=0x1, subtype=0x0,
                          date=(0, 0)),
        kids=[
            # 041204B0 은 한국어(0x0412) + 유니코드(0x04B0) 조합입니다.
            StringFileInfo([StringTable("041204B0", [
                StringStruct("CompanyName", author),
                StringStruct("FileDescription", DESCRIPTION),
                StringStruct("FileVersion", version),
                StringStruct("InternalName", NAME),
                StringStruct("LegalCopyright", "Copyright (c) 2026 %s" % author),
                StringStruct("OriginalFilename", NAME + ".exe"),
                StringStruct("ProductName", "ShadowPlay Notifier"),
                StringStruct("ProductVersion", version),
            ])]),
            VarFileInfo([VarStruct("Translation", [0x0412, 1200])]),
        ],
    )


VERSION = read_meta("VERSION", "0.0.0")
AUTHOR = read_meta("AUTHOR", "deuxdoom")
ICON = os.path.join(SPECPATH, "appicon.ico")
DIST = os.path.join(SPECPATH, "dist")
TARGET = os.path.join(DIST, NAME + ".exe")


def prepare_dist():
    """완성본은 저장소의 dist 에만 만듭니다.

    2.6.0 은 --distpath 로 임시 폴더에만 구웠고, dist 에 남아 있던 2.5.1 빌드가
    2.6.0 릴리스에 대신 올라갔습니다. 그래서 완성본 자리를 한 곳으로 고정하고,
    빌드가 도중에 실패해도 예전 EXE 가 새것처럼 남지 않도록 먼저 지웁니다.
    """
    if os.path.normcase(os.path.abspath(DISTPATH)) != os.path.normcase(DIST):
        raise SystemExit("완성본은 %s 에만 만듭니다. --distpath 를 빼고 다시 빌드하십시오. "
                         "(받은 값: %s)" % (DIST, DISTPATH))
    try:
        if os.path.isfile(TARGET):
            os.remove(TARGET)
    except PermissionError:
        raise SystemExit("%s 을 지우지 못했습니다. 이 EXE 로 실행 중인 앱을 닫고 "
                         "다시 빌드하십시오." % TARGET)


def built_versions(path):
    """구운 EXE 의 파일 속성 버전과, 그 안에 묶인 version.py 의 VERSION 입니다."""
    from PyInstaller.archive.readers import CArchiveReader, ZlibArchiveReader
    from PyInstaller.utils.win32.versioninfo import read_version_info_from_executable

    info = read_version_info_from_executable(path)
    high, low = info.ffi.fileVersionMS, info.ffi.fileVersionLS
    found = {"숫자 버전": "%d.%d.%d" % (high >> 16, high & 0xFFFF, low >> 16)}
    found.update((item.name, item.val) for table in info.kids[0].kids
                 for item in table.kids if item.name in ("FileVersion", "ProductVersion"))
    archive = CArchiveReader(path)
    # PYZ 는 압축하지 않은 채 EXE 안에 들어 있어서 그 자리에서 바로 읽습니다.
    offset = archive._start_offset + archive.toc["PYZ.pyz"][0]
    names = {}
    exec(ZlibArchiveReader(path, start_offset=offset).extract("component.version"), names)
    found["묶인 VERSION"] = names.get("VERSION")
    return found


def verify_built():
    """구운 EXE 가 version.py 와 같은 번호를 달았는지 보고 크기와 SHA-256 을 알립니다.

    번호가 하나라도 어긋나면 EXE 를 지우고 빌드를 실패로 끝냅니다. 여기서 알린
    크기와 SHA-256 을 릴리스 페이지의 파일 확인 표에 그대로 옮겨 적습니다.
    """
    found = built_versions(TARGET)
    wrong = {key: value for key, value in found.items() if value != VERSION}
    if wrong:
        os.remove(TARGET)
        raise SystemExit("구운 EXE 의 번호가 version.py 의 %s 와 달라 지웠습니다: %s"
                         % (VERSION, wrong))
    with open(TARGET, "rb") as fp:
        digest = hashlib.file_digest(fp, "sha256").hexdigest().upper()
    print("완성본 %s | %s | %s bytes | SHA-256 %s"
          % (TARGET, VERSION, format(os.path.getsize(TARGET), ","), digest))


prepare_dist()


def season_photos():
    """계절 사진 네 장입니다.

    폴더째 넣으면 갈아 끼우고 남은 예전 사진과 출처 문서까지 따라 들어갑니다.
    component/sky.py 와 같은 차례로 확장자를 골라 실제로 읽는 것만 넣습니다.
    """
    folder = os.path.join(SPECPATH, "assets", "wallpapers")
    found = []
    for season in ("spring", "summer", "autumn", "winter"):
        for ext in (".png", ".jpg", ".jpeg"):
            path = os.path.join(folder, season + ext)
            if os.path.isfile(path):
                found.append((path, os.path.join("assets", "wallpapers")))
                break
    return found

a = Analysis(
    [os.path.join(SPECPATH, "ShadowPlayNotifier.py")],
    pathex=[SPECPATH],
    binaries=[],
    # 월페이퍼 화면에 쓰는 글꼴입니다. 설치하지 않고 실행할 때만 등록하므로
    # EXE 안에 함께 넣습니다. component/fonts.py 가 풀린 자리에서 읽습니다.
    datas=[(os.path.join(SPECPATH, "assets", "fonts", family + "-" + weight + ".ttf"),
            os.path.join("assets", "fonts"))
           for family in ("PretendardJP", "JetBrainsMono")
           for weight in ("Regular", "Bold")]
          # 날씨 옆에 띄우는 달 사진입니다.
          + [(os.path.join(SPECPATH, "assets", "moon.png"), "assets")]
          + season_photos() + ([(ICON, ".")] if os.path.isfile(ICON) else []),
    hiddenimports=[],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    # 런타임에 쓰지 않는 것들입니다. Pillow 는 아이콘을 구울 때만 쓰는
    # 작성 시점 도구이므로 EXE 에 들어갈 이유가 없습니다.
    #
    # 둘째 줄부터는 표준 라이브러리가 끌고 오지만 앱이 한 번도 부르지 않는
    # 모듈입니다(2.7.1, 약 1.2MB). 검사 전부와 날씨·도시·업데이트·곡 조회를 실제로
    # 돌려 불러온 모듈을 기록한 뒤, 이 목록을 import 하지 못하게 막고 다시 돌려
    # 모두 통과하는 것을 확인했습니다. shutil 은 bz2·lzma·zstd 가 있는지
    # try/except 로 확인만 하므로 빠져도 됩니다. 쓰는 것은 ThreadPoolExecutor
    # 뿐이라 프로세스 풀과 multiprocessing 도 필요 없습니다. 새 기능에서 이 가운데
    # 하나를 쓰게 되면 여기서 지워야 EXE 가 시작할 때 멈추지 않습니다.
    #
    # zipfile 은 앱이 쓰지 않지만 빼면 안 됩니다. PyInstaller 의 런타임 훅
    # pyi_rth_inspect 가 시작할 때 import 하므로, 빼면 EXE 가 「No module named
    # 'zipfile'」 오류 창을 띄우고 멈춥니다. 런타임 훅은 묶은 EXE 에서만 돌기
    # 때문에 소스로 돌리는 검사에는 걸리지 않습니다. 목록을 고치면 반드시
    # 구운 EXE 를 실제로 띄워 확인하십시오.
    excludes=["PIL", "numpy", "setuptools", "pip", "pytest",
              "multiprocessing", "_multiprocessing", "pickle", "_compat_pickle",
              "concurrent.futures.process", "concurrent.futures.interpreter",
              "concurrent.interpreters",
              "decimal", "_decimal", "_pydecimal", "fractions", "statistics",
              "xml", "xmlrpc", "pyexpat",
              "tarfile", "gzip", "bz2", "_bz2", "lzma", "_lzma",
              "compression.zstd", "_zstd",
              "_pydatetime", "http.cookiejar", "ftplib", "netrc"],
    noarchive=False,
    optimize=0,
)

# 윈도우 10 이상은 시스템 폴더의 유니버설 CRT 를 언제나 먼저 쓰므로 EXE 에 묶을
# 까닭이 없습니다. 그런데 PATH 에 Windows Kits 폴더(Windows Performance Toolkit 등)가
# 들어 있으면 PyInstaller 가 거기 있는 api-ms-win-*.dll 과 ucrtbase.dll 을 찾아 묶어서
# 쓰이지도 않는 파일 41개로 EXE 가 0.9MB 커집니다(2.7.1 빌드에서 발견).
a.binaries = [entry for entry in a.binaries
              if not (entry[0].lower().startswith("api-ms-win-")
                      or entry[0].lower() == "ucrtbase.dll")]

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name=NAME,
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    runtime_tmpdir=None,
    # 콘솔 창을 띄우지 않습니다. 그래서 기록은 monitor.log 로 남깁니다.
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=ICON if os.path.isfile(ICON) else None,
    version=version_resource(VERSION, AUTHOR),
)

verify_built()
