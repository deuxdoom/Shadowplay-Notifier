# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller 빌드 정의입니다.

빌드:
    pyinstaller --clean ShadowPlayNotifier.spec

--clean 을 붙이는 이유는, 그것이 없으면 PyInstaller 가 이전에 만든 EXE 를 그대로
재사용해서 바뀐 아이콘이 조용히 무시되기 때문입니다.

appicon.ico 파일이 프로젝트 폴더에 있으면 EXE 아이콘으로 넣고, 없으면 아이콘 없이
빌드합니다. 아이콘 원본은 저장소에 올리지 않습니다.
"""

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
    excludes=["PIL", "numpy", "setuptools", "pip", "pytest"],
    noarchive=False,
    optimize=0,
)

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
