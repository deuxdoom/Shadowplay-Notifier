"""그림을 만들고 고치는 일입니다. 윈도우에 이미 있는 GDI+ 를 ``ctypes`` 로 씁니다.

tkinter 의 ``PhotoImage`` 는 JPEG 를 읽지 못합니다. 그래서 앨범 커버는 GDI+ 로
풀어서 Tk 가 읽는 PPM 으로 바꿔 넣습니다. 배경에 까는 그라디언트와 번짐도
작게 계산한 뒤 GDI+ 로 늘리면 부드럽게 나옵니다.

커버는 쌓아 두지 않습니다. 곡이 바뀌면 새로 받아 갈아 끼우고 이전 것은 버립니다.
"""

import colorsys
import ctypes
import math
import os
import struct
import zlib
from ctypes import byref, c_void_p

from .paths import RESOURCE_DIR, detail, log

gdiplus = ctypes.windll.gdiplus

PIXEL_FORMAT_32BPP_ARGB = 0x0026200A
INTERPOLATION_HQ_BICUBIC = 7
WRAP_MODE_TILE_FLIP_XY = 3


class _StartupInput(ctypes.Structure):
    _fields_ = [("GdiplusVersion", ctypes.c_uint32),
                ("DebugEventCallback", c_void_p),
                ("SuppressBackgroundThread", ctypes.c_int),
                ("SuppressExternalCodecs", ctypes.c_int)]


class _Rect(ctypes.Structure):
    _fields_ = [("X", ctypes.c_int), ("Y", ctypes.c_int),
                ("Width", ctypes.c_int), ("Height", ctypes.c_int)]


class _BitmapData(ctypes.Structure):
    _fields_ = [("Width", ctypes.c_uint), ("Height", ctypes.c_uint),
                ("Stride", ctypes.c_int), ("PixelFormat", ctypes.c_int),
                ("Scan0", c_void_p), ("Reserved", c_void_p)]


kernel32 = ctypes.windll.kernel32
ole32 = ctypes.windll.ole32

# 64비트에서 손잡이와 포인터가 잘리지 않도록 형을 분명히 지정합니다.
kernel32.GlobalAlloc.argtypes = [ctypes.c_uint, ctypes.c_size_t]
kernel32.GlobalAlloc.restype = c_void_p
kernel32.GlobalLock.argtypes = [c_void_p]
kernel32.GlobalLock.restype = c_void_p
kernel32.GlobalUnlock.argtypes = [c_void_p]
kernel32.GlobalFree.argtypes = [c_void_p]
kernel32.GlobalFree.restype = c_void_p
ole32.CreateStreamOnHGlobal.argtypes = [c_void_p, ctypes.c_int,
                                        ctypes.POINTER(c_void_p)]
ole32.CreateStreamOnHGlobal.restype = ctypes.HRESULT
gdiplus.GdipCreateBitmapFromStream.argtypes = [c_void_p, ctypes.POINTER(c_void_p)]
gdiplus.GdipCreateBitmapFromStream.restype = ctypes.c_int

_token = ctypes.c_ulong()
_ready = False


def start():
    """GDI+ 를 한 번만 켭니다. 실패해도 앱은 계속 돌아갑니다."""
    global _ready
    if _ready:
        return True
    try:
        si = _StartupInput(1, None, 0, 0)
        status = gdiplus.GdiplusStartup(byref(_token), byref(si), None)
        _ready = (status == 0)
        if not _ready:
            log("[그림] GDI+ 를 켜지 못했습니다 (%d)" % status)
    except Exception as exc:
        log("[그림] GDI+ 를 켜지 못했습니다: %s" % exc)
        _ready = False
    return _ready


def _bitmap_from_bytes(data):
    """메모리에 있는 그림 바이트로 GDI+ 비트맵을 만듭니다.

    스트림에 메모리 소유권을 넘기므로(fDeleteOnRelease), 스트림을 놓아주면
    잡아 둔 메모리도 함께 풀립니다.
    """
    size = len(data)
    handle = kernel32.GlobalAlloc(0x0002, size)  # GMEM_MOVEABLE
    if not handle:
        raise MemoryError("그림을 담을 메모리를 잡지 못했습니다")
    ptr = kernel32.GlobalLock(handle)
    if not ptr:
        kernel32.GlobalFree(handle)
        raise MemoryError("그림 메모리를 잠그지 못했습니다")
    ctypes.memmove(ptr, data, size)
    kernel32.GlobalUnlock(handle)

    stream = c_void_p()
    try:
        ole32.CreateStreamOnHGlobal(handle, 1, byref(stream))
    except OSError as exc:
        kernel32.GlobalFree(handle)
        raise OSError("그림 스트림을 만들지 못했습니다: %s" % exc)

    bitmap = c_void_p()
    status = gdiplus.GdipCreateBitmapFromStream(stream, byref(bitmap))
    # 비트맵이 만들어졌으면 그림 자료를 이미 읽었으므로 스트림은 놓아줍니다.
    _release_com(stream)
    if status:
        raise OSError("그림을 풀지 못했습니다 (%d)" % status)
    return bitmap


def _release_com(ptr):
    if ptr:
        vtable = ctypes.cast(ptr, ctypes.POINTER(ctypes.POINTER(c_void_p))).contents
        ctypes.WINFUNCTYPE(ctypes.c_ulong, c_void_p)(vtable[2])(ptr)


def _new_bitmap(width, height):
    bitmap = c_void_p()
    gdiplus.GdipCreateBitmapFromScan0(width, height, 0,
                                      PIXEL_FORMAT_32BPP_ARGB, None, byref(bitmap))
    return bitmap


def _to_ppm(bitmap, width, height):
    """GDI+ 비트맵을 Tk 가 읽는 PPM 바이트로 바꿉니다."""
    data = _BitmapData()
    rect = _Rect(0, 0, width, height)
    status = gdiplus.GdipBitmapLockBits(bitmap, byref(rect), 1,
                                        PIXEL_FORMAT_32BPP_ARGB, byref(data))
    if status:
        raise OSError("그림 픽셀을 읽지 못했습니다 (%d)" % status)
    raw = ctypes.string_at(data.Scan0, data.Stride * height)
    stride = data.Stride
    gdiplus.GdipBitmapUnlockBits(bitmap, byref(data))

    # 픽셀을 하나씩 도는 대신 채널별로 잘라 넣습니다. 파이썬 반복문이
    # 빠지면서 960x640 한 장이 수십 밀리초에서 몇 밀리초로 줄어듭니다.
    span = width * 3
    out = bytearray(span * height)
    for y in range(height):
        line = raw[y * stride: y * stride + width * 4]
        base = y * span
        out[base:base + span:3] = line[2::4]      # R
        out[base + 1:base + span:3] = line[1::4]  # G
        out[base + 2:base + span:3] = line[0::4]  # B
    header = ("P6\n%d %d\n255\n" % (width, height)).encode("ascii")
    return header + bytes(out)


def _draw_scaled(src, width, height):
    dst = _new_bitmap(width, height)
    graphics = c_void_p()
    gdiplus.GdipGetImageGraphicsContext(dst, byref(graphics))
    gdiplus.GdipSetInterpolationMode(graphics, INTERPOLATION_HQ_BICUBIC)
    # 가장자리에서 바깥 픽셀을 끌어오지 않도록 감싸기 방식을 지정합니다.
    gdiplus.GdipSetPixelOffsetMode(graphics, 2)  # Half
    gdiplus.GdipDrawImageRectI(graphics, src, 0, 0, width, height)
    gdiplus.GdipDeleteGraphics(graphics)
    return dst


def cover_ppm(data, size):
    """앨범 커버 바이트를 정사각 PPM 으로 바꿉니다. 실패하면 None 입니다."""
    if not start():
        return None
    src = None
    dst = None
    try:
        src = _bitmap_from_bytes(data)
        dst = _draw_scaled(src, size, size)
        return _to_ppm(dst, size, size)
    except Exception as exc:
        detail("[그림] 커버를 만들지 못했습니다: %s" % exc)
        return None
    finally:
        if dst:
            gdiplus.GdipDisposeImage(dst)
        if src:
            gdiplus.GdipDisposeImage(src)


def rounded_cover_png(data, size, radius):
    """둥근 커버 한 장. 표준 라이브러리로 PNG 알파를 만들며 캐시하지 않습니다."""
    ppm = cover_ppm(data, size)
    if ppm is None:
        return None
    pixels = ppm.split(b"\n", 3)[3]
    rgba = bytearray(size * size * 4)
    rgba[0::4], rgba[1::4], rgba[2::4] = pixels[0::3], pixels[1::3], pixels[2::3]
    rgba[3::4] = b"\xff" * (size * size)
    radius = max(1, min(radius, size // 2))
    # 모서리만 계산하며 1픽셀의 가장자리에 안티앨리어싱을 적용합니다.
    for y in range(radius):
        for x in range(radius):
            distance = ((radius - x - .5) ** 2 + (radius - y - .5) ** 2) ** .5
            alpha = round(max(0, min(1, radius + .5 - distance)) * 255)
            for px, py in ((x, y), (size - 1 - x, y),
                           (x, size - 1 - y), (size - 1 - x, size - 1 - y)):
                rgba[(py * size + px) * 4 + 3] = alpha

    def chunk(name, body):
        return (struct.pack(">I", len(body)) + name + body +
                struct.pack(">I", zlib.crc32(name + body) & 0xffffffff))

    stride = size * 4
    scanlines = b"".join(b"\0" + rgba[y * stride:(y + 1) * stride]
                         for y in range(size))
    return (b"\x89PNG\r\n\x1a\n" +
            chunk(b"IHDR", struct.pack(">IIBBBBB", size, size, 8, 6, 0, 0, 0)) +
            chunk(b"IDAT", zlib.compress(scanlines, 3)) + chunk(b"IEND", b""))


def dominant_color(data, fallback=(120, 120, 132)):
    """커버에서 배경에 쓸 대표색을 고릅니다.

    아주 작게 줄이면 평균색과 주요 색이 한 번에 나옵니다. 그중 너무 어둡거나
    너무 흐리지 않은 것을 고릅니다.
    """
    if not start():
        return fallback
    src = None
    small = None
    try:
        src = _bitmap_from_bytes(data)
        side = 8
        small = _draw_scaled(src, side, side)
        data_out = _BitmapData()
        rect = _Rect(0, 0, side, side)
        gdiplus.GdipBitmapLockBits(small, byref(rect), 1,
                                   PIXEL_FORMAT_32BPP_ARGB, byref(data_out))
        raw = ctypes.string_at(data_out.Scan0, data_out.Stride * side)
        stride = data_out.Stride
        gdiplus.GdipBitmapUnlockBits(small, byref(data_out))

        best, best_score = fallback, -1.0
        for y in range(side):
            for x in range(side):
                i = y * stride + x * 4
                r, g, b = raw[i + 2], raw[i + 1], raw[i]
                _, s, v = colorsys.rgb_to_hsv(r / 255.0, g / 255.0, b / 255.0)
                # 선명하면서 너무 밝지도 어둡지도 않은 색을 높게 칩니다.
                score = s * min(v, 1.0 - abs(v - 0.62) * 0.8)
                if score > best_score:
                    best_score, best = score, (r, g, b)
        return best
    except Exception as exc:
        detail("[그림] 대표색을 찾지 못했습니다: %s" % exc)
        return fallback
    finally:
        if small:
            gdiplus.GdipDisposeImage(small)
        if src:
            gdiplus.GdipDisposeImage(src)


def upscale_rgb(pixels, small_w, small_h, width, height):
    """작게 계산한 RGB 를 늘려 PPM 으로 만듭니다.

    배경의 번짐을 960x640 에서 곧바로 계산하면 느립니다. 작게 만들어
    늘리면 경계가 부드러워지면서도 빠릅니다.

    ``pixels`` 는 (r, g, b) 를 이어 붙인 bytes 여야 합니다.
    """
    if not start():
        return None
    src = None
    dst = None
    try:
        src = _new_bitmap(small_w, small_h)
        data = _BitmapData()
        rect = _Rect(0, 0, small_w, small_h)
        gdiplus.GdipBitmapLockBits(src, byref(rect), 3,  # ReadWrite
                                   PIXEL_FORMAT_32BPP_ARGB, byref(data))
        stride = data.Stride
        buf = (ctypes.c_ubyte * (stride * small_h)).from_address(data.Scan0)
        for y in range(small_h):
            base = y * stride
            row = y * small_w * 3
            for x in range(small_w):
                i = base + x * 4
                j = row + x * 3
                buf[i] = pixels[j + 2]
                buf[i + 1] = pixels[j + 1]
                buf[i + 2] = pixels[j]
                buf[i + 3] = 255
        gdiplus.GdipBitmapUnlockBits(src, byref(data))
        dst = _draw_scaled(src, width, height)
        return _to_ppm(dst, width, height)
    except Exception as exc:
        log("[그림] 배경을 늘리지 못했습니다: %s" % exc)
        return None
    finally:
        if dst:
            gdiplus.GdipDisposeImage(dst)
        if src:
            gdiplus.GdipDisposeImage(src)


# 실제 달 사진입니다. 배경을 지우고 정사각형에 꽉 차게 맞춰 두었습니다.
MOON_IMAGE = "moon.png"
# 빛이 닿지 않는 면에 덮는 검정의 짙기입니다. 0.9 면 표면이 어렴풋이 남습니다.
MOON_SHADOW = 0.90
_moon_surface = {}


def _moon_source(size):
    """달 사진을 원하는 크기로 줄여 RGBA 로 들고 있습니다.

    사진은 바뀌지 않으므로 크기마다 한 번만 만들어 둡니다. 화면 크기가
    달라지면 이전 것은 버립니다.
    """
    if size in _moon_surface:
        return _moon_surface[size]
    path = os.path.join(RESOURCE_DIR, "assets", MOON_IMAGE)
    try:
        with open(path, "rb") as fp:
            data = fp.read()
    except OSError as exc:
        log("[그림] 달 사진을 읽지 못했습니다: %s" % exc)
        return None
    if not start():
        return None
    src = dst = None
    try:
        src = _bitmap_from_bytes(data)
        dst = _draw_scaled(src, size, size)
        rgba = _to_rgba(dst, size, size)
    except Exception as exc:
        log("[그림] 달 사진을 줄이지 못했습니다: %s" % exc)
        return None
    finally:
        if dst:
            gdiplus.GdipDisposeImage(dst)
        if src:
            gdiplus.GdipDisposeImage(src)
    _moon_surface.clear()
    _moon_surface[size] = rgba
    return rgba


def _to_rgba(bitmap, width, height):
    """알파를 살린 채로 픽셀을 꺼냅니다."""
    data = _BitmapData()
    rect = _Rect(0, 0, width, height)
    status = gdiplus.GdipBitmapLockBits(bitmap, byref(rect), 1,
                                        PIXEL_FORMAT_32BPP_ARGB, byref(data))
    if status:
        raise OSError("그림 픽셀을 읽지 못했습니다 (%d)" % status)
    raw = ctypes.string_at(data.Scan0, data.Stride * height)
    stride = data.Stride
    gdiplus.GdipBitmapUnlockBits(bitmap, byref(data))
    span = width * 4
    out = bytearray(span * height)
    for y in range(height):
        line = raw[y * stride: y * stride + span]
        base = y * span
        out[base:base + span:4] = line[2::4]      # R
        out[base + 1:base + span:4] = line[1::4]  # G
        out[base + 2:base + span:4] = line[0::4]  # B
        out[base + 3:base + span:4] = line[3::4]  # A
    return bytes(out)


def moon_png(size, phase):
    """오늘 달을 한 장 굽습니다. 알파가 있는 PNG 바이트를 돌려줍니다.

    실제 달 사진을 바탕에 깔고, 그 위에 빛이 닿지 않는 면을 계산해 검정을
    덮습니다. 완전히 지우지 않고 90% 만 덮기 때문에 달의 윤곽과 표면 무늬가
    어렴풋이 남아, 어디까지 차올랐는지 함께 보입니다.

    ``phase`` 는 0 이 삭, 0.5 가 보름입니다. 하루에 한 번꼴로만 바뀌므로
    이 함수도 그만큼만 부르면 됩니다.
    """
    n = max(8, int(size))
    source = _moon_source(n)
    if source is None:
        return None
    # 태양은 위상각만큼 돌아간 자리에 있습니다. 삭이면 달 뒤쪽입니다.
    angle = 2.0 * math.pi * (phase % 1.0)
    sun_x, sun_z = math.sin(angle), -math.cos(angle)

    rgba = bytearray(source)
    half = n / 2.0
    for y in range(n):
        ny = (y + 0.5 - half) / half
        row = y * n * 4
        for x in range(n):
            i = row + x * 4
            if not rgba[i + 3]:
                continue
            nx = (x + 0.5 - half) / half
            d2 = nx * nx + ny * ny
            nz = math.sqrt(1.0 - d2) if d2 < 1.0 else 0.0
            light = nx * sun_x + nz * sun_z
            lit = (light ** 0.6) if light > 0.0 else 0.0
            shade = (1.0 - MOON_SHADOW) + MOON_SHADOW * lit
            rgba[i] = round(rgba[i] * shade)
            rgba[i + 1] = round(rgba[i + 1] * shade)
            rgba[i + 2] = round(rgba[i + 2] * shade)

    def chunk(name, body):
        return (struct.pack(">I", len(body)) + name + body +
                struct.pack(">I", zlib.crc32(name + body) & 0xffffffff))

    span = n * 4
    scanlines = b"".join(bytes([0]) + rgba[y * span:(y + 1) * span]
                         for y in range(n))
    return (bytes([137, 80, 78, 71, 13, 10, 26, 10]) +
            chunk(b"IHDR", struct.pack(">IIBBBBB", n, n, 8, 6, 0, 0, 0)) +
            chunk(b"IDAT", zlib.compress(scanlines, 6)) + chunk(b"IEND", b""))
