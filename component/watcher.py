"""녹화 시작과 중단을 판정하는 상태 기계와, 그것을 돌리는 감시 스레드입니다.

판정 구조는 검증이 끝난 코드입니다. 폴링으로 파일 크기를 재고, 크기가 늘면 시작,
늘지 않은 채 stall 초가 지나면 중단으로 봅니다. 이 구조를 바꾸지 마십시오.
화면에 필요한 값은 :meth:`Watcher.snapshot` 으로 뽑아 씁니다.
"""

import os
import threading
import time
import traceback
from dataclasses import dataclass, field

from .paths import log
from .scan import being_written, human, hms, scan, sound


@dataclass
class Watcher:
    dirs: list
    outdirs: list
    patterns: tuple
    interval: float = 1.0
    min_growth: int = 256 * 1024
    stall: float = 8.0
    min_size: int = 1024 * 1024
    recursive: bool = True
    beep: bool = True
    fast_detect: bool = True
    sink: object = None

    _sizes: dict = field(default_factory=dict)
    _outfiles: set = field(default_factory=set)
    _active: str = ""
    _started_at: float = 0.0
    _last_growth: float = 0.0
    _peak: int = 0
    _start_size: int = 0

    def emit(self, **event):
        if self.sink is not None:
            self.sink(event)

    def _start(self, path, size):
        self._active = path
        now = time.time()
        self._started_at = now
        self._last_growth = now
        self._peak = size
        self._start_size = size
        log("녹화 시작 감지 -> %s" % path)
        self.emit(kind="start", path=path, size=size, at=now)
        sound("start", self.beep)

    def _stop(self, reason, final_name=""):
        dur = time.time() - self._started_at
        path = self._active
        peak = self._peak
        log("녹화 종료 감지 (%s)  경과 %s / 용량 %s"
            % (reason, hms(dur), human(peak)))
        self.emit(kind="stop", path=path, reason=reason, final=final_name,
                  dur=dur, peak=peak, at=time.time())
        sound("stop", self.beep)
        self._active = ""
        self._peak = 0

    def snapshot(self):
        """현재 상태를 화면이 그대로 표시할 수 있는 형태로 만듭니다."""
        now = time.time()
        if not self._active:
            return {"kind": "state", "active": False}
        elapsed = now - self._started_at
        grown = max(0, self._peak - self._start_size)
        mbps = None
        if elapsed >= 2.0 and grown > 0:
            mbps = grown * 8.0 / elapsed / 1000000.0
        return {"kind": "state", "active": True, "path": self._active,
                "elapsed": elapsed, "size": self._peak, "mbps": mbps,
                "since_growth": now - self._last_growth, "stall": self.stall}

    def tick(self):
        now = time.time()
        current = scan(self.dirs, self.patterns, self.min_size, self.recursive)
        outnow = set(scan(self.outdirs, self.patterns,
                          self.min_size, self.recursive)) if self.outdirs else set()
        new_out = outnow - self._outfiles - {self._active}

        if self._active:
            size = current.get(self._active)
            if new_out:
                self._stop("완료 파일 생성", os.path.basename(sorted(new_out)[0]))
            elif size is None:
                self._stop("임시 파일 사라짐")
            elif size > self._peak:
                self._peak = size
                self._last_growth = now
            # 크기가 늘지 않은 틱에서만 잠금 상태를 확인합니다. 녹화 중에는
            # 거의 매 틱 크기가 늘기 때문에, 이 확인은 실제로 멈춘 뒤에만
            # 일어나고 오판할 여지도 그만큼 줄어듭니다.
            elif self.fast_detect and being_written(self._active) is False:
                self._stop("파일 닫힘")
            elif now - self._last_growth >= self.stall:
                self._stop("증가 멈춤")
        else:
            for path, size in current.items():
                prev = self._sizes.get(path)
                # 이번 틱에 처음 보인 파일이 쓰기로 열려 있다면 바로 시작으로
                # 봅니다. 크기가 한 번 더 늘기를 기다리지 않아도 됩니다.
                if prev is None:
                    if self.fast_detect and being_written(path) is True:
                        self._start(path, size)
                        break
                elif size - prev >= self.min_growth:
                    self._start(path, size)
                    break

        self._sizes = current
        self._outfiles = outnow
        self.emit(**self.snapshot())

    def prime(self):
        """감시를 시작하기 직전의 파일 목록을 기준선으로 잡습니다."""
        self._sizes = scan(self.dirs, self.patterns, self.min_size, self.recursive)
        self._outfiles = set(scan(self.outdirs, self.patterns,
                                  self.min_size, self.recursive)) if self.outdirs else set()


class WatchThread(threading.Thread):
    """폴링을 화면 스레드에서 분리해 창이 멈추지 않도록 합니다."""

    def __init__(self, watcher, stop_event):
        super().__init__(name="watcher", daemon=True)
        self.watcher = watcher
        self.stop_event = stop_event

    def run(self):
        w = self.watcher
        try:
            w.prime()
        except Exception as exc:
            log("[오류] 초기 스캔에 실패했습니다: %s" % exc)
            w.emit(kind="error", message="초기 스캔 실패: %s" % exc)
        while not self.stop_event.is_set():
            w.emit(kind="health",
                   missing=[d for d in w.dirs if not os.path.isdir(d)])
            try:
                w.tick()
            except Exception as exc:
                log("[오류] %s\n%s" % (exc, traceback.format_exc().rstrip()))
                w.emit(kind="error", message=str(exc))
            self.stop_event.wait(w.interval)


def make_watcher(settings, sink):
    return Watcher(
        dirs=settings["dirs"], outdirs=settings["outdirs"],
        patterns=settings["patterns"], interval=settings["interval"],
        stall=settings["stall"], min_size=settings["min_size"],
        min_growth=settings["min_growth"], recursive=settings["recursive"],
        beep=settings["beep"], fast_detect=settings["fast_detect"], sink=sink,
    )


class WatchSupervisor:
    """감시 스레드를 하나만 유지합니다. 환경설정을 바꾸면 새로 시작합니다."""

    def __init__(self, sink):
        self.sink = sink
        self.thread = None
        self.stop_event = None

    def start(self, settings):
        self.stop()
        self.stop_event = threading.Event()
        self.thread = WatchThread(make_watcher(settings, self.sink),
                                  self.stop_event)
        self.thread.start()

    def stop(self):
        if self.stop_event is not None:
            self.stop_event.set()
        self.stop_event = None
        self.thread = None
