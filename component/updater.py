"""GitHub 정식 릴리스 확인·검증·교체. 네트워크와 파일 작업은 UI 밖에서 합니다."""

import hashlib
import json
import os
import re
import shutil
import struct
import sys
import tempfile
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import asdict, dataclass
from pathlib import Path

from . import update_windows as win
from .i18n import tr
from .version import VERSION

REPOSITORY = "deuxdoom/Shadowplay-Notifier"
API_URL = "https://api.github.com/repos/" + REPOSITORY + "/releases/latest"
ASSET_NAME = "ShadowPlayNotifier.exe"
JOBS = Path(tempfile.gettempdir()) / "ShadowPlayNotifier-updates"
MAX_EXE_SIZE = 512 * 1024 * 1024


class UpdateError(Exception):
    pass


class Cancelled(UpdateError):
    pass


def version_tuple(tag):
    match = re.fullmatch(r"[vV]?(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)(?:\+[0-9A-Za-z.-]+)?", str(tag))
    if not match:
        raise UpdateError(tr("정식 버전 번호를 읽을 수 없습니다: %s") % tag)
    return tuple(map(int, match.groups()))


@dataclass(frozen=True)
class Release:
    tag: str
    url: str
    size: int
    sha256: str
    page: str


def parse_release(data):
    if not isinstance(data, dict) or data.get("draft") or data.get("prerelease"):
        raise UpdateError(tr("공개된 정식 릴리스가 아닙니다."))
    tag = data.get("tag_name", "")
    version_tuple(tag)
    assets = [item for item in data.get("assets", [])
              if item.get("name") == ASSET_NAME and item.get("state") == "uploaded"]
    if len(assets) != 1:
        raise UpdateError(tr("최신 릴리스에 %s 파일이 아직 준비되지 않았습니다.") % ASSET_NAME)
    asset = assets[0]
    url = asset.get("browser_download_url", "")
    expected = "https://github.com/%s/releases/download/%s/%s" % (
        REPOSITORY, urllib.parse.quote(tag, safe=""), ASSET_NAME)
    if url != expected:
        raise UpdateError(tr("공식 저장소의 다운로드 주소가 아닙니다."))
    digest = asset.get("digest") or ""
    if not re.fullmatch(r"sha256:[0-9a-fA-F]{64}", digest):
        raise UpdateError(tr("릴리스 파일의 SHA-256 확인 정보가 아직 준비되지 않았습니다."))
    size = asset.get("size")
    if not isinstance(size, int) or not 1024 <= size <= MAX_EXE_SIZE:
        raise UpdateError(tr("릴리스 파일의 크기 정보가 올바르지 않습니다."))
    return Release(tag, url, size, digest[7:].lower(),
                   "https://github.com/%s/releases/tag/%s" % (REPOSITORY, urllib.parse.quote(tag, safe="")))


class HTTPSRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        if urllib.parse.urlsplit(newurl).scheme != "https":
            raise UpdateError(tr("보안 연결이 아닌 다운로드 주소를 거부했습니다."))
        return super().redirect_request(req, fp, code, msg, headers, newurl)


def open_url(url, accept):
    request = urllib.request.Request(url, headers={
        "User-Agent": "ShadowPlayNotifier/" + VERSION,
        "Accept": accept, "X-GitHub-Api-Version": "2022-11-28",
        "Cache-Control": "no-cache"})
    return urllib.request.build_opener(HTTPSRedirect()).open(request, timeout=20)


def error_text(exc):
    if isinstance(exc, urllib.error.HTTPError):
        if exc.code in (403, 429):
            return tr("GitHub 요청 한도에 도달했거나 접근이 제한되었습니다. 잠시 후 다시 확인해 주세요.")
        if exc.code == 404:
            return tr("공개된 릴리스 또는 다운로드 파일을 찾지 못했습니다. 잠시 후 다시 확인해 주세요.")
        return tr("GitHub에 연결하지 못했습니다 (HTTP %d). 다시 시도해 주세요.") % exc.code
    if isinstance(exc, (urllib.error.URLError, TimeoutError, ConnectionError)):
        return tr("연결이 끊겼거나 응답이 없습니다. 인터넷 연결을 확인하고 다시 시도해 주세요.")
    if isinstance(exc, PermissionError):
        return tr("설치 폴더에 쓰거나 파일을 교체할 수 없습니다. 폴더 권한과 실행 파일 차단 여부를 확인해 주세요.")
    return str(exc)


def check_latest(current=VERSION):
    with open_url(API_URL, "application/vnd.github+json") as response:
        raw = response.read(2 * 1024 * 1024 + 1)
    if len(raw) > 2 * 1024 * 1024:
        raise UpdateError(tr("GitHub 응답이 너무 큽니다."))
    data = json.loads(raw)
    # 이전 버전은 자산 유무에 상관없이 설치하지 않습니다.
    if not isinstance(data, dict) or data.get("draft") or data.get("prerelease"):
        raise UpdateError(tr("공개된 정식 릴리스가 아닙니다."))
    remote = version_tuple(data.get("tag_name", ""))
    if remote <= version_tuple(current):
        return None, data["tag_name"]
    return parse_release(data), data["tag_name"]


def file_hash(path):
    with open(path, "rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def verify_exe(path, size, digest):
    if path.stat().st_size != size or file_hash(path) != digest.lower():
        raise UpdateError(tr("다운로드 파일의 크기 또는 SHA-256이 일치하지 않습니다. 다시 시도해 주세요."))
    with path.open("rb") as stream:
        header = stream.read(64)
        if len(header) != 64 or header[:2] != b"MZ":
            raise UpdateError(tr("올바른 Windows 실행 파일이 아닙니다."))
        offset = struct.unpack_from("<I", header, 60)[0]
        if not 64 <= offset <= size - 96:
            raise UpdateError(tr("실행 파일의 헤더가 손상되었습니다."))
        stream.seek(offset)
        pe = stream.read(96)
        if pe[:4] != b"PE\0\0" or struct.unpack_from("<H", pe, 92)[0] != 2:
            raise UpdateError(tr("콘솔 없는 Windows 앱 파일이 아닙니다."))


def download(release, destination, report, cancel):
    received = 0
    try:
        with open_url(release.url, "application/octet-stream") as response, destination.open("xb") as output:
            length = response.headers.get("Content-Length")
            if length and int(length) != release.size:
                raise UpdateError(tr("서버의 파일 크기가 릴리스 정보와 다릅니다."))
            while True:
                if cancel.is_set():
                    raise Cancelled("업데이트를 취소했습니다.")
                chunk = response.read(128 * 1024)
                if not chunk:
                    break
                received += len(chunk)
                if received > release.size:
                    raise UpdateError(tr("다운로드 크기가 릴리스 정보보다 큽니다."))
                output.write(chunk)
                report("download", received / release.size * 75,
                       "%.1f / %.1f MB" % (received / 1048576, release.size / 1048576))
            output.flush()
            os.fsync(output.fileno())
        report("verify", 78, "파일 크기와 SHA-256을 확인하고 있습니다.")
        verify_exe(destination, release.size, release.sha256)
    except BaseException:
        destination.unlink(missing_ok=True)
        raise


def replace_retry(source, target, timeout=8):
    deadline = time.monotonic() + timeout
    while True:
        try:
            os.replace(source, target)
            return
        except PermissionError:
            if time.monotonic() >= deadline:
                raise
            time.sleep(.2)


def install(release, target, arguments, report, cancel):
    """다운로드 실패는 앱을 건드리지 않고, 교체/시작 실패는 백업으로 복원합니다."""
    target = Path(target).resolve(strict=True)
    if target.suffix.lower() != ".exe" or win.canonical(target) == win.canonical(sys.executable):
        raise UpdateError(tr("업데이트 도우미는 별도 위치에서 실행해야 합니다."))
    if shutil.disk_usage(target.parent).free < release.size * 2 + target.stat().st_size + 10485760:
        raise UpdateError(tr("업데이트와 복구 파일을 저장할 디스크 공간이 부족합니다."))
    stage = Path(tempfile.mkdtemp(prefix=".spn-update-", dir=target.parent))
    payload, backup = stage / "download.exe", stage / "previous.exe"
    preserve_backup = False
    stopped = False
    replaced = False
    try:
        download(release, payload, report, cancel)
        if cancel.is_set():
            raise Cancelled("업데이트를 취소했습니다.")
        shutil.copy2(target, backup)
        original_hash = file_hash(backup)
        if original_hash != file_hash(target):
            raise UpdateError(tr("업데이트 준비 중 기존 실행 파일이 변경되었습니다."))
        report("stop", 82, "실행 중인 프로그램을 종료하고 있습니다.")
        stopped = True
        win.stop_target(target)
        if original_hash != file_hash(target):
            raise UpdateError(tr("기존 실행 파일이 변경되어 업데이트를 중단했습니다."))
        report("replace", 88, "원래 폴더의 실행 파일을 교체하고 있습니다.")
        replace_retry(payload, target)
        replaced = True
        verify_exe(target, release.size, release.sha256)
        report("restart", 94, "새 버전을 실행하고 응답을 확인하고 있습니다.")
        pid = win.restart(target, arguments)
        report("done", 100, "업데이트가 완료되어 프로그램을 다시 실행했습니다.")
        return pid
    except Exception as exc:
        if stopped:
            report("rollback", 90, "업데이트를 마치지 못해 이전 프로그램을 복구하고 있습니다.")
            try:
                win.stop_target(target)
                if replaced:
                    replace_retry(backup, target)
                win.restart(target, arguments)
            except Exception as recovery:
                preserve_backup = backup.exists()
                raise UpdateError(tr("%s\n복구 후 실행을 확인하지 못했습니다: %s\n기존 파일: %s") % (
                    error_text(exc), error_text(recovery), backup if preserve_backup else target)) from exc
            raise UpdateError(tr("%s\n이전 프로그램을 다시 실행했습니다.") % error_text(exc)) from exc
        raise
    finally:
        if not preserve_backup:
            shutil.rmtree(stage, ignore_errors=True)


def write_json(path, data):
    temp = path.with_suffix(".tmp")
    temp.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
    os.replace(temp, path)


def launch_helper(release, target, arguments, center):
    if not getattr(sys, "frozen", False):
        raise UpdateError(tr("자동 업데이트는 배포된 EXE에서 사용할 수 있습니다."))
    JOBS.mkdir(exist_ok=True)
    job = Path(tempfile.mkdtemp(prefix="job-", dir=JOBS))
    try:
        helper = job / "updater.exe"
        shutil.copy2(sys.executable, helper)
        plan = {"release": asdict(release), "target": str(Path(target).resolve()),
                "arguments": list(arguments), "center": list(center)}
        write_json(job / "plan.json", plan)
        process = win.launch([str(helper), "--apply-update", str(job / "plan.json")], str(job))
        return process, job
    except Exception:
        shutil.rmtree(job, ignore_errors=True)
        raise


def cleanup_jobs():
    """완료된 도우미가 종료된 뒤 자체 임시 폴더만 정리합니다."""
    if not JOBS.is_dir() or JOBS.is_symlink():
        return
    for job in JOBS.glob("job-*"):
        if not job.is_dir() or job.is_symlink():
            continue
        try:
            status_file = job / "status.json"
            finished = status_file.exists() and json.loads(status_file.read_text(encoding="utf-8")).get("phase") in ("done", "error", "cancelled")
            stale = time.time() - job.stat().st_mtime > 86400
            if (finished or stale) and not win.process_ids(job / "updater.exe"):
                shutil.rmtree(job)
        except (OSError, ValueError):
            pass


def schedule_cleanup():
    timer = threading.Timer(8, cleanup_jobs)
    timer.daemon = True
    timer.start()
