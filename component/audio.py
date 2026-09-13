"""스피커로 나가는 소리를 받아 주파수 막대로 바꾸는 일입니다.

윈도우의 WASAPI 루프백을 ``ctypes`` 로 직접 열어 출력 샘플을 읽고, 순수
파이썬 FFT 로 12대역 세기를 구합니다. 외부 패키지를 쓰지 않습니다.

소리를 녹음하는 것이 아니라 세기만 재며, 어디에도 저장하지 않습니다.
녹화가 시작되면 :meth:`AudioLevels.stop` 으로 장치를 닫습니다.

대역마다 최근 천장과 바닥을 따라가며 그 사이를 0~1 로 펼칩니다. 고정 범위로
자르면 음악의 저역이 늘 꼭대기에 붙어서 막대가 움직이지 않습니다.
"""

import cmath
import ctypes
import math
import struct
import threading
import time
from ctypes import POINTER, byref, c_uint, c_uint32, c_uint64, c_void_p

from .paths import detail, log

BARS = 12
N_FFT = 1024
LOW_HZ, HIGH_HZ = 40.0, 16000.0
# 음악은 저역 에너지가 크므로 옥타브마다 이만큼 올려 준다
TILT_DB = 4.0
# 대역이 쓰는 구간이 이보다 좁아지면 더 좁히지 않는다
MIN_SPAN_DB = 14.0

ole32 = ctypes.windll.ole32

CLSID_MMDeviceEnumerator = "{BCDE0395-E52F-467C-8E3D-C4579291692E}"
IID_IMMDeviceEnumerator = "{A95664D2-9614-4F35-A746-DE8DB63617E6}"
IID_IAudioClient = "{1CB9AD4C-DBFA-4c32-B178-C2F568A703B2}"
IID_IAudioCaptureClient = "{C8ADBD64-E71E-48a0-A4DE-185C395CD317}"

CLSCTX_ALL = 23
AUDCLNT_SHAREMODE_SHARED = 0
AUDCLNT_STREAMFLAGS_LOOPBACK = 0x00020000
AUDCLNT_BUFFERFLAGS_SILENT = 0x2
BUFFER_100NS = 2000000  # 0.2 초


class GUID(ctypes.Structure):
    _fields_ = [("Data1", ctypes.c_uint32), ("Data2", ctypes.c_uint16),
                ("Data3", ctypes.c_uint16), ("Data4", ctypes.c_ubyte * 8)]

    def __init__(self, text=None):
        super().__init__()
        if text:
            ole32.CLSIDFromString(ctypes.c_wchar_p(text), byref(self))


class WAVEFORMATEX(ctypes.Structure):
    _fields_ = [("wFormatTag", ctypes.c_uint16), ("nChannels", ctypes.c_uint16),
                ("nSamplesPerSec", ctypes.c_uint32),
                ("nAvgBytesPerSec", ctypes.c_uint32),
                ("nBlockAlign", ctypes.c_uint16), ("wBitsPerSample", ctypes.c_uint16),
                ("cbSize", ctypes.c_uint16)]


def _vcall(ptr, index, argtypes, *args):
    """COM 객체의 vtable 에서 index 번째 메서드를 부릅니다."""
    vtable = ctypes.cast(ptr, POINTER(POINTER(c_void_p))).contents
    proto = ctypes.WINFUNCTYPE(ctypes.HRESULT, c_void_p, *argtypes)
    return proto(vtable[index])(ptr, *args)


def _release(ptr):
    if ptr:
        _vcall(ptr, 2, [])  # IUnknown::Release


# FFT 에 쓰는 회전 인자와 창 함수는 한 번만 만들어 둡니다.
_TWIDDLE = [cmath.exp(-2j * math.pi * k / N_FFT) for k in range(N_FFT)]
_WINDOW = [0.5 - 0.5 * math.cos(2 * math.pi * i / (N_FFT - 1)) for i in range(N_FFT)]


def fft(values):
    """반복형 radix-2 FFT 입니다. 길이는 2의 거듭제곱이어야 합니다."""
    n = len(values)
    out = list(values)
    j = 0
    for i in range(1, n):
        bit = n >> 1
        while j & bit:
            j ^= bit
            bit >>= 1
        j |= bit
        if i < j:
            out[i], out[j] = out[j], out[i]
    size = 2
    while size <= n:
        step, half = n // size, size // 2
        for start in range(0, n, size):
            k = 0
            for i in range(start, start + half):
                w = _TWIDDLE[k]
                a = out[i]
                b = out[i + half] * w
                out[i] = a + b
                out[i + half] = a - b
                k += step
        size <<= 1
    return out


def band_edges(rate):
    """40 Hz 부터 16 kHz 까지를 로그 간격으로 12등분해 FFT 칸 번호로 바꿉니다."""
    bin_hz = rate / N_FFT
    hz = [LOW_HZ * (HIGH_HZ / LOW_HZ) ** (i / BARS) for i in range(BARS + 1)]
    edges = [int(round(h / bin_hz)) for h in hz]
    for i in range(1, len(edges)):
        if edges[i] <= edges[i - 1]:
            edges[i] = edges[i - 1] + 1
    centers = [math.sqrt(hz[i] * hz[i + 1]) for i in range(BARS)]
    return hz, edges, centers


class AudioLevels(threading.Thread):
    """출력 소리를 받아 12대역 세기를 계속 갱신하는 스레드입니다.

    화면 쪽에서는 :attr:`levels` 를 그대로 읽어 씁니다. 값은 0~1 입니다.
    장치를 열지 못하면 조용히 물러나고 :attr:`available` 이 False 가 됩니다.
    """

    def __init__(self, fps=30):
        super().__init__(name="audio-levels", daemon=True)
        self.fps = max(10, min(60, int(fps)))
        self.levels = [0.0] * BARS
        self.silent = True
        self.available = False
        self.error = ""
        self.stop_event = threading.Event()
        self._ceil_db = [-10.0] * BARS
        self._floor_db = [-55.0] * BARS

    # ------------------------------------------------------------ 장치

    def _open(self):
        """루프백 캡처를 엽니다. 실패하면 예외를 올립니다."""
        enumerator = c_void_p()
        hr = ole32.CoCreateInstance(byref(GUID(CLSID_MMDeviceEnumerator)), None,
                                    CLSCTX_ALL,
                                    byref(GUID(IID_IMMDeviceEnumerator)),
                                    byref(enumerator))
        if hr:
            raise OSError("오디오 장치 목록을 얻지 못했습니다 (0x%08x)" % (hr & 0xFFFFFFFF))
        device = c_void_p()
        # GetDefaultAudioEndpoint(eRender=0, eConsole=0)
        hr = _vcall(enumerator, 4, [c_uint, c_uint, POINTER(c_void_p)],
                    0, 0, byref(device))
        if hr:
            _release(enumerator)
            raise OSError("기본 출력 장치를 얻지 못했습니다 (0x%08x)" % (hr & 0xFFFFFFFF))
        client = c_void_p()
        hr = _vcall(device, 3, [POINTER(GUID), c_uint32, c_void_p, POINTER(c_void_p)],
                    byref(GUID(IID_IAudioClient)), CLSCTX_ALL, None, byref(client))
        if hr:
            _release(device)
            _release(enumerator)
            raise OSError("오디오 클라이언트를 열지 못했습니다 (0x%08x)" % (hr & 0xFFFFFFFF))

        fmt_ptr = POINTER(WAVEFORMATEX)()
        _vcall(client, 8, [POINTER(POINTER(WAVEFORMATEX))], byref(fmt_ptr))
        fmt = fmt_ptr.contents
        hr = _vcall(client, 3, [c_uint32, c_uint32, c_uint64, c_uint64,
                                POINTER(WAVEFORMATEX), c_void_p],
                    AUDCLNT_SHAREMODE_SHARED, AUDCLNT_STREAMFLAGS_LOOPBACK,
                    BUFFER_100NS, 0, fmt_ptr, None)
        if hr:
            _release(client)
            _release(device)
            _release(enumerator)
            raise OSError("루프백 캡처를 시작하지 못했습니다 (0x%08x)" % (hr & 0xFFFFFFFF))
        capture = c_void_p()
        _vcall(client, 14, [POINTER(GUID), POINTER(c_void_p)],
               byref(GUID(IID_IAudioCaptureClient)), byref(capture))
        _vcall(client, 10, [])  # Start
        return enumerator, device, client, capture, fmt

    # ------------------------------------------------------------ 본체

    def run(self):
        ole32.CoInitializeEx(None, 0)
        try:
            enumerator, device, client, capture, fmt = self._open()
        except Exception as exc:
            self.error = str(exc)
            log("[소리] 시각화를 켜지 못했습니다: %s" % exc)
            return
        self.available = True
        rate = fmt.nSamplesPerSec
        channels = fmt.nChannels
        block = fmt.nBlockAlign
        _, edges, centers = band_edges(rate)
        tilt = [TILT_DB * math.log2(c / 200.0) for c in centers]
        detail("[소리] 시각화를 시작합니다 (%d Hz, %d 채널)" % (rate, channels))

        buf = []
        data_ptr, frames, flags = c_void_p(), c_uint32(), c_uint32()
        pos, qpc = c_uint64(), c_uint64()
        period = 1.0 / self.fps
        next_at = time.perf_counter()

        try:
            while not self.stop_event.is_set():
                self._drain(capture, buf, channels, block,
                            data_ptr, frames, flags, pos, qpc)
                now = time.perf_counter()
                if now >= next_at and len(buf) >= N_FFT:
                    next_at = now + period
                    self._analyze(buf[-N_FFT:], edges, tilt)
                self.stop_event.wait(0.004)
        except Exception as exc:
            self.error = str(exc)
            log("[소리] 시각화가 멈췄습니다: %s" % exc)
        finally:
            try:
                _vcall(client, 11, [])  # Stop
            except Exception:
                pass
            _release(capture)
            _release(client)
            _release(device)
            _release(enumerator)
            self.available = False

    def _drain(self, capture, buf, channels, block,
               data_ptr, frames, flags, pos, qpc):
        """쌓인 패킷을 모두 꺼내 한 채널로 합칩니다."""
        while True:
            hr = _vcall(capture, 3, [POINTER(c_void_p), POINTER(c_uint32),
                                     POINTER(c_uint32), POINTER(c_uint64),
                                     POINTER(c_uint64)],
                        byref(data_ptr), byref(frames), byref(flags),
                        byref(pos), byref(qpc))
            if hr or not frames.value:
                break
            count = frames.value
            if flags.value & AUDCLNT_BUFFERFLAGS_SILENT:
                buf.extend([0.0] * count)
            else:
                vals = struct.unpack("<%df" % (count * channels),
                                     ctypes.string_at(data_ptr, count * block))
                if channels >= 2:
                    buf.extend((vals[i] + vals[i + 1]) * 0.5
                               for i in range(0, len(vals), channels))
                else:
                    buf.extend(vals)
            _vcall(capture, 4, [c_uint32], count)
        # 버퍼가 무한정 자라지 않도록 최근 것만 남깁니다.
        if len(buf) > N_FFT * 6:
            del buf[:len(buf) - N_FFT * 2]

    def _analyze(self, chunk, edges, tilt):
        if max(chunk) < 1e-5 and min(chunk) > -1e-5:
            # 소리가 없으면 FFT 를 돌리지 않고 막대를 천천히 내립니다.
            self.silent = True
            self.levels = [v - 0.06 if v > 0.06 else 0.0 for v in self.levels]
            return
        self.silent = False
        spec = fft([chunk[i] * _WINDOW[i] for i in range(N_FFT)])
        out = []
        for b in range(BARS):
            lo = edges[b]
            hi = min(edges[b + 1], N_FFT // 2)
            if hi <= lo:
                hi = lo + 1
            acc = 0.0
            for k in range(lo, hi):
                c = spec[k]
                acc += c.real * c.real + c.imag * c.imag
            mag = math.sqrt(acc / (hi - lo))
            db = 20 * math.log10(mag + 1e-9) + tilt[b]
            out.append(self._normalize(b, db))
        self.levels = out

    def _normalize(self, b, db):
        """대역이 최근에 쓴 구간을 0~1 로 펼칩니다."""
        ceil_db = self._ceil_db[b]
        floor_db = self._floor_db[b]
        # 천장은 곧바로 따라 올라가고 아주 천천히 내려옵니다.
        ceil_db += (db - ceil_db) * (0.35 if db > ceil_db else 0.005)
        # 바닥은 천천히 내려갑니다. 순간의 저점까지 쫓아가면 기준이 너무
        # 낮아져서 막대가 늘 위쪽에 머뭅니다.
        floor_db += (db - floor_db) * (0.10 if db < floor_db else 0.012)
        self._ceil_db[b] = ceil_db
        self._floor_db[b] = floor_db
        span = ceil_db - floor_db
        if span < MIN_SPAN_DB:
            span = MIN_SPAN_DB
        v = (db - floor_db) / span
        if v <= 0.0:
            return 0.0
        if v >= 1.0:
            return 1.0
        return v ** 1.35

    def stop(self):
        self.stop_event.set()
