"""Chrome profile/session management for AI Video provider automation."""

from __future__ import annotations

import json
import os
import platform
import re
import shutil
import socket
import subprocess
import threading
import time
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

from sqlalchemy.orm import Session

from ..database import VideoProviderSession as DBVideoProviderSession
from . import chrome_cdp, video_provider_storage, video_storage

DEFAULT_PROVIDER = "veo"
DEFAULT_PROVIDER_TOOL = "veo3_flow"
DEFAULT_CONNECTION_LABEL = "Veo3 Flow"
DEFAULT_FLOW_URL = "https://labs.google/fx/tools/flow"
FLOW_ORIGIN = "https://labs.google"
ENV_CHROME_PATHS = ("VOICEBOX_VEO_CHROME_PATH", "VOICEBOX_CHROME_PATH", "CHROME_PATH")
ENV_FLOW_URL = "VOICEBOX_VEO_FLOW_URL"

READY_STATUSES = {"ready"}
LOGIN_STATUSES = {"not_configured", "needs_login", "invalid"}
IDENTITY_BLOCKING_STATUSES = {"unknown", "mismatch", "needs_user_action"}

_EMAIL_RE = re.compile(r"(?i)\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b")
_LOGIN_URL_MARKERS = ("accounts.google.", "/signin", "ServiceLogin", "challenge")
_LOGIN_TEXT_MARKERS = (
    "sign in",
    "signin",
    "đăng nhập",
    "chon tai khoan",
    "chọn tài khoản",
    "verify it's you",
    "xác minh",
    "create with google flow",
    "try in google flow",
)
_CHROME_LOCK_NAMES = ("SingletonLock", "SingletonSocket", "SingletonCookie")
_FLOW_ENTRYPOINT_TEXTS = ("Create with Google Flow", "Try in Google Flow")
_FLOW_APPLICATION_ERROR_MARKERS = (
    "application error:",
    "client-side exception has occurred",
    "while loading labs.google",
)
_CHROME_TRANSLATE_DISABLED_ARGS = ("--disable-translate", "--disable-features=Translate,TranslateUI")
_FLOW_RECOVERY_STORAGE_TYPES = "appcache,cache_storage,file_systems,indexeddb,local_storage,service_workers,websql"

class VideoProviderSessionError(ValueError):
    """Raised when a Chrome/Veo provider session cannot continue."""

    def __init__(self, message: str, *, error_code: str = "VIDEO_PROVIDER_SESSION_ERROR"):
        super().__init__(message)
        self.error_code = error_code

@dataclass
class ChromeRuntime:
    provider: str
    process: subprocess.Popen | None
    port: int
    profile_dir: Path

_runtime_lock = threading.Lock()
_runtime_by_provider: dict[str, ChromeRuntime] = {}

def flow_url() -> str:
    return os.environ.get(ENV_FLOW_URL, DEFAULT_FLOW_URL).strip() or DEFAULT_FLOW_URL

def _now() -> datetime:
    return datetime.utcnow()

def mask_account_hint(value: str | None) -> str | None:
    if not value:
        return None
    text = value.strip()
    match = _EMAIL_RE.search(text)
    email = match.group(0) if match else text
    if "@" not in email:
        return video_storage.sanitize_download_filename(email, fallback="account", max_length=80)
    name, domain = email.split("@", 1)
    name_hint = f"{name[:1]}***" if name else "***"
    return f"{name_hint}@{domain.lower()}"

def account_identifier_hash(value: str | None) -> str | None:
    if not value:
        return None
    normalized = value.strip().lower()
    if not normalized:
        return None
    return chrome_cdp.sha256_short(normalized, length=32)

def _extract_email_hint(text: str | None) -> tuple[str | None, str | None]:
    if not text:
        return None, None
    match = _EMAIL_RE.search(text)
    if not match:
        return None, None
    email = match.group(0)
    return mask_account_hint(email), account_identifier_hash(email)

def _chrome_candidates() -> list[str]:
    configured = [os.environ.get(name) for name in ENV_CHROME_PATHS if os.environ.get(name)]
    system = platform.system().lower()
    candidates: list[str] = [value for value in configured if value]
    if system == "darwin":
        candidates.extend(
            [
                "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
                str(Path.home() / "Applications/Google Chrome.app/Contents/MacOS/Google Chrome"),
                "/Applications/Google Chrome Canary.app/Contents/MacOS/Google Chrome Canary",
            ]
        )
    elif system == "windows":
        program_files = [os.environ.get("PROGRAMFILES"), os.environ.get("PROGRAMFILES(X86)"), os.environ.get("LOCALAPPDATA")]
        for root in [value for value in program_files if value]:
            candidates.extend(
                [
                    str(Path(root) / "Google/Chrome/Application/chrome.exe"),
                    str(Path(root) / "Google/Chrome SxS/Application/chrome.exe"),
                ]
            )
    else:
        candidates.extend(["google-chrome", "google-chrome-stable", "chromium", "chromium-browser"])
    return candidates

def detect_chrome_executable() -> str:
    for candidate in _chrome_candidates():
        resolved = shutil.which(candidate) if os.path.sep not in candidate else candidate
        if resolved and Path(resolved).expanduser().exists():
            return str(Path(resolved).expanduser())
    raise VideoProviderSessionError(
        "Chưa tìm thấy Google Chrome. Hãy cài Chrome hoặc cấu hình VOICEBOX_CHROME_PATH.",
        error_code="VIDEO_PROVIDER_CHROME_MISSING",
    )

def _find_free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])

def _profile_lock_reason(profile_dir: Path) -> str | None:
    locks = [profile_dir / name for name in _CHROME_LOCK_NAMES if (profile_dir / name).exists() or (profile_dir / name).is_symlink()]
    if not locks:
        return None
    if _profile_has_live_process(profile_dir):
        return (
            "Chrome profile Veo của Voicebox đang được một cửa sổ Chrome khác dùng. "
            "Hãy đóng cửa sổ đó rồi thử lại."
        )
    _clear_stale_profile_locks(locks)
    return None

def _profile_has_live_process(profile_dir: Path) -> bool:
    profile_text = str(profile_dir)
    if platform.system().lower() == "windows":
        return _singleton_lock_pid_uses_profile(profile_dir)
    try:
        result = subprocess.run(
            ["ps", "axo", "pid=,command="],
            capture_output=True,
            text=True,
            timeout=3.0,
            check=False,
        )
    except Exception:
        return _singleton_lock_pid_uses_profile(profile_dir)
    if result.returncode != 0:
        return _singleton_lock_pid_uses_profile(profile_dir)
    return any(profile_text in line for line in result.stdout.splitlines())

def _singleton_lock_pid_uses_profile(profile_dir: Path) -> bool:
    lock_path = profile_dir / "SingletonLock"
    try:
        target = os.readlink(lock_path)
    except OSError:
        return False
    match = re.search(r"-(\d+)$", target)
    if not match:
        return False
    pid = int(match.group(1))
    if pid <= 0:
        return False
    try:
        result = subprocess.run(
            ["ps", "-p", str(pid), "-o", "command="],
            capture_output=True,
            text=True,
            timeout=2.0,
            check=False,
        )
    except Exception:
        try:
            os.kill(pid, 0)
        except OSError:
            return False
        return True
    return result.returncode == 0 and str(profile_dir) in result.stdout

def _clear_stale_profile_locks(locks: list[Path]) -> None:
    for path in locks:
        try:
            path.unlink()
        except FileNotFoundError:
            continue
        except OSError:
            continue

def _write_download_preferences(profile_dir: Path, download_dir: Path) -> None:
    default_dir = profile_dir / "Default"
    default_dir.mkdir(parents=True, exist_ok=True)
    prefs_path = default_dir / "Preferences"
    prefs: dict[str, Any] = {}
    if prefs_path.exists():
        try:
            prefs = json.loads(prefs_path.read_text(encoding="utf-8"))
        except Exception:
            prefs = {}
    prefs.setdefault("download", {})
    prefs["download"].update(
        {
            "default_directory": str(download_dir),
            "directory_upgrade": True,
            "prompt_for_download": False,
        }
    )
    prefs.setdefault("safebrowsing", {})
    prefs["safebrowsing"]["enabled"] = True
    prefs.setdefault("translate", {})
    prefs["translate"]["enabled"] = False
    prefs["translate_site_blacklist"] = sorted(set([*(prefs.get("translate_site_blacklist") or []), "labs.google"]))
    prefs_path.write_text(json.dumps(prefs, ensure_ascii=False, indent=2), encoding="utf-8")

def _runtime_alive(runtime: ChromeRuntime) -> bool:
    if runtime.process is not None and runtime.process.poll() is not None:
        return False
    try:
        chrome_cdp.fetch_json(f"http://127.0.0.1:{runtime.port}/json/version", timeout=1.0)
        return True
    except Exception:
        return False

def _close_chrome_runtime(runtime: ChromeRuntime, *, timeout_seconds: float = 5.0) -> None:
    try:
        with chrome_cdp.CDPClient(chrome_cdp.browser_websocket_url(runtime.port)) as client:
            client.command("Browser.close", timeout=2.0)
    except Exception:
        pass
    if runtime.process is not None and runtime.process.poll() is None:
        try:
            runtime.process.terminate()
            runtime.process.wait(timeout=timeout_seconds)
        except Exception:
            try:
                runtime.process.kill()
            except Exception:
                pass
    deadline = time.monotonic() + timeout_seconds
    while time.monotonic() < deadline:
        if not _runtime_alive(runtime):
            return
        time.sleep(0.2)

def launch_chrome(
    *,
    provider: str = DEFAULT_PROVIDER,
    url: str | None = None,
    download_dir: Path | None = None,
    require_new: bool = False,
) -> ChromeRuntime:
    profile_dir = video_provider_storage.get_chrome_profile_dir(provider)
    download_dir = download_dir or video_provider_storage.get_provider_downloads_root() / provider
    download_dir.mkdir(parents=True, exist_ok=True)
    with _runtime_lock:
        current = _runtime_by_provider.get(provider)
        if current and _runtime_alive(current) and not require_new:
            return current
        _runtime_by_provider.pop(provider, None)
        existing = _existing_chrome_runtime(provider, profile_dir)
        if existing and not require_new:
            _runtime_by_provider[provider] = existing
            return existing
        if require_new:
            if current and _runtime_alive(current):
                _close_chrome_runtime(current)
            if existing and _runtime_alive(existing):
                _close_chrome_runtime(existing)
        lock_reason = _profile_lock_reason(profile_dir)
        if lock_reason:
            raise VideoProviderSessionError(lock_reason, error_code="VIDEO_PROVIDER_PROFILE_LOCKED")
        chrome_path = detect_chrome_executable()
        _write_download_preferences(profile_dir, download_dir)
        port = _find_free_port()
        args = [
            chrome_path,
            f"--user-data-dir={profile_dir}",
            f"--remote-debugging-port={port}",
            "--no-first-run",
            "--no-default-browser-check",
            "--disable-background-mode",
            *_CHROME_TRANSLATE_DISABLED_ARGS,
            "--new-window",
            url or flow_url(),
        ]
        try:
            process = subprocess.Popen(args, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        except OSError as exc:
            raise VideoProviderSessionError(
                "Không mở được Chrome cho Veo. Hãy kiểm tra đường dẫn Chrome.",
                error_code="VIDEO_PROVIDER_CHROME_LAUNCH_FAILED",
            ) from exc
        runtime = ChromeRuntime(provider=provider, process=process, port=port, profile_dir=profile_dir)
        try:
            chrome_cdp.wait_for_debug_port(port, timeout_seconds=12.0)
        except Exception as exc:
            _runtime_by_provider.pop(provider, None)
            raise VideoProviderSessionError(
                "Chrome đã mở nhưng Voicebox chưa kết nối được remote debugging.",
                error_code="VIDEO_PROVIDER_CHROME_DEBUG_UNAVAILABLE",
            ) from exc
        _runtime_by_provider[provider] = runtime
        return runtime

def _existing_chrome_runtime(provider: str, profile_dir: Path) -> ChromeRuntime | None:
    profile_text = str(profile_dir)
    try:
        if platform.system().lower() == "windows":
            result = subprocess.run(
                [
                    "powershell",
                    "-NoProfile",
                    "-Command",
                    (
                        "[Console]::OutputEncoding=[System.Text.UTF8Encoding]::new(); "
                        "Get-CimInstance Win32_Process -Filter \"name='chrome.exe'\" "
                        "| ForEach-Object { $_.CommandLine }"
                    ),
                ],
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=5.0,
                check=False,
            )
        else:
            result = subprocess.run(
                ["ps", "axo", "pid=,command="],
                capture_output=True,
                text=True,
                timeout=3.0,
                check=False,
            )
    except Exception:
        return None
    if result.returncode != 0:
        return None
    for line in result.stdout.splitlines():
        if profile_text not in line:
            continue
        match = re.search(r"--remote-debugging-port(?:=|\s+)(\d+)", line)
        if not match:
            continue
        port = int(match.group(1))
        try:
            chrome_cdp.fetch_json(f"http://127.0.0.1:{port}/json/version", timeout=1.0)
        except Exception:
            continue
        return ChromeRuntime(provider=provider, process=None, port=port, profile_dir=profile_dir)
    return None

def get_default_session(db: Session, *, provider: str = DEFAULT_PROVIDER, create: bool = True) -> DBVideoProviderSession | None:
    row = (
        db.query(DBVideoProviderSession)
        .filter(DBVideoProviderSession.provider == provider, DBVideoProviderSession.is_default.is_(True))
        .order_by(DBVideoProviderSession.updated_at.desc(), DBVideoProviderSession.created_at.desc())
        .first()
    )
    if row is not None or not create:
        return row
    now = _now()
    profile_dir = video_provider_storage.get_chrome_profile_dir(provider)
    row = DBVideoProviderSession(
        provider=provider,
        provider_tool=DEFAULT_PROVIDER_TOOL,
        status="not_configured",
        is_default=True,
        chrome_profile_path=video_provider_storage.to_storage_path(profile_dir),
        connection_label=DEFAULT_CONNECTION_LABEL,
        identity_status="unknown",
        created_at=now,
        updated_at=now,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return row

def open_login_session(
    db: Session,
    *,
    provider: str = DEFAULT_PROVIDER,
    change_account: bool = False,
) -> DBVideoProviderSession:
    row = get_default_session(db, provider=provider, create=True)
    if row is None:
        raise VideoProviderSessionError("Không tạo được phiên Veo mặc định.", error_code="VIDEO_PROVIDER_SESSION_CREATE_FAILED")
    now = _now()
    try:
        runtime = launch_chrome(
            provider=provider,
            url=flow_url(),
            download_dir=video_provider_storage.get_provider_downloads_root() / provider,
            require_new=True,
        )
        _advance_flow_entrypoint(runtime)
    except VideoProviderSessionError as exc:
        row.status = "invalid"
        row.failure_reason = str(exc)
        row.updated_at = now
        db.commit()
        raise
    row.status = "needs_login" if row.identity_status in {"unknown", "mismatch"} or change_account else "checking"
    if change_account:
        row.identity_status = "unknown"
        row.account_identifier_hash = None
        row.verified_account_hint = None
    row.failure_reason = None
    row.provider_tool = row.provider_tool or DEFAULT_PROVIDER_TOOL
    row.chrome_profile_path = video_provider_storage.to_storage_path(video_provider_storage.get_chrome_profile_dir(provider))
    row.updated_at = now
    db.commit()
    db.refresh(row)
    return row

def _click_flow_entrypoint_if_present(client: chrome_cdp.CDPClient) -> bool:
    result = client.evaluate(
        """
        (() => {
          const labels = %s;
          const normalize = (value) => String(value || '').replace(/\\s+/g, ' ').trim();
          const visible = (element) => {
            const rect = element.getBoundingClientRect();
            const style = getComputedStyle(element);
            return rect.width > 0 && rect.height > 0 && style.display !== 'none' && style.visibility !== 'hidden';
          };
          const inViewport = (element) => {
            const rect = element.getBoundingClientRect();
            return rect.right > 0 && rect.bottom > 0 && rect.left < innerWidth && rect.top < innerHeight;
          };
          const candidates = Array.from(document.querySelectorAll('button,a,[role="button"]')).filter((element) => {
            if (!visible(element)) return false;
            const text = normalize(element.innerText || element.textContent || element.getAttribute('aria-label'));
            return labels.some((label) => text === label || text.includes(label));
          });
          candidates.sort((left, right) => Number(inViewport(right)) - Number(inViewport(left)));
          const target = candidates[0];
          if (!target) return { clicked: false, url: String(location.href || '') };
          target.scrollIntoView({ block: 'center', inline: 'center' });
          const rect = target.getBoundingClientRect();
          const eventInit = {
            bubbles: true,
            cancelable: true,
            view: window,
            clientX: rect.left + rect.width / 2,
            clientY: rect.top + rect.height / 2
          };
          target.dispatchEvent(new MouseEvent('mouseover', eventInit));
          target.dispatchEvent(new MouseEvent('mousedown', eventInit));
          target.dispatchEvent(new MouseEvent('mouseup', eventInit));
          target.click();
          return {
            clicked: true,
            text: normalize(target.innerText || target.textContent || target.getAttribute('aria-label')),
            url: String(location.href || '')
          };
        })()
        """
        % json.dumps(list(_FLOW_ENTRYPOINT_TEXTS)),
        timeout=8.0,
    )
    return isinstance(result, dict) and bool(result.get("clicked"))

def _read_page_snapshot(client: chrome_cdp.CDPClient, *, text_limit: int = 20000) -> dict[str, str]:
    snapshot = client.evaluate(
        f"""
        (() => ({{
          url: String(location.href || ''),
          title: String(document.title || ''),
          text: String(document.body && document.body.innerText || '').slice(0, {int(text_limit)})
        }}))()
        """,
        timeout=10.0,
    )
    if not isinstance(snapshot, dict):
        return {"url": "", "title": "", "text": ""}
    return {key: str(snapshot.get(key) or "") for key in ("url", "title", "text")}

def _looks_like_flow_application_error(snapshot: dict[str, str]) -> bool:
    url = snapshot.get("url", "").lower()
    text = f"{snapshot.get('title', '')}\n{snapshot.get('text', '')}".lower()
    if "labs.google" not in url and "labs.google" not in text:
        return False
    return any(marker in text for marker in _FLOW_APPLICATION_ERROR_MARKERS)

def _looks_like_flow_project_url(url: str | None) -> bool:
    text = str(url or "").lower()
    return "labs.google" in text and "/tools/flow/project/" in text

def close_flow_project_tabs(
    port: int,
    *,
    keep_target_id: str | None = None,
    application_errors_only: bool = False,
) -> int:
    closed = 0
    for target in chrome_cdp.list_targets(port):
        if target.type != "page" or target.id == keep_target_id:
            continue
        if not _looks_like_flow_project_url(target.url):
            continue
        if application_errors_only:
            snapshot = {"url": target.url or "", "title": target.title or "", "text": target.title or ""}
            if not _looks_like_flow_application_error(snapshot):
                try:
                    with chrome_cdp.CDPClient(target.web_socket_debugger_url) as client:
                        snapshot = _read_page_snapshot(client, text_limit=1000)
                except Exception:
                    snapshot = {"url": target.url or "", "title": target.title or "", "text": target.title or ""}
            if not _looks_like_flow_application_error(snapshot):
                continue
        try:
            if chrome_cdp.close_target(port, target.id):
                closed += 1
        except Exception:
            continue
    if closed:
        time.sleep(0.5)
    return closed

def _recover_flow_application_error(client: chrome_cdp.CDPClient, snapshot: dict[str, str]) -> bool:
    if not _looks_like_flow_application_error(snapshot):
        return False
    try:
        client.evaluate(
            """
            (() => {
              try { localStorage.clear(); } catch {}
              try { sessionStorage.clear(); } catch {}
              try {
                if (window.indexedDB && indexedDB.databases) {
                  indexedDB.databases().then((databases) => databases.forEach((database) => {
                    if (database && database.name) indexedDB.deleteDatabase(database.name);
                  }));
                }
              } catch {}
              return true;
            })()
            """,
            timeout=5.0,
        )
    except Exception:
        pass
    try:
        client.command(
            "Storage.clearDataForOrigin",
            {"origin": FLOW_ORIGIN, "storageTypes": _FLOW_RECOVERY_STORAGE_TYPES},
            timeout=8.0,
        )
    except Exception:
        pass
    client.navigate(flow_url(), timeout=20.0)
    time.sleep(4.0)
    return True

def _advance_flow_entrypoint(runtime: ChromeRuntime, *, timeout_seconds: float = 8.0) -> bool:
    close_flow_project_tabs(runtime.port, application_errors_only=True)
    deadline = time.monotonic() + timeout_seconds
    while time.monotonic() < deadline:
        target = chrome_cdp.find_page_target(runtime.port, "flow") or chrome_cdp.find_page_target(runtime.port)
        if target is None:
            target = chrome_cdp.open_target(runtime.port, flow_url())
        with chrome_cdp.CDPClient(target.web_socket_debugger_url) as client:
            snapshot = _read_page_snapshot(client, text_limit=5000)
            if _recover_flow_application_error(client, snapshot):
                continue
            if _click_flow_entrypoint_if_present(client):
                time.sleep(4.0)
                return True
        time.sleep(0.5)
    return False

def _page_snapshot(runtime: ChromeRuntime) -> dict[str, str]:
    close_flow_project_tabs(runtime.port, application_errors_only=True)
    target = chrome_cdp.find_page_target(runtime.port, "flow") or chrome_cdp.open_target(runtime.port, flow_url())
    with chrome_cdp.CDPClient(target.web_socket_debugger_url) as client:
        client.navigate(flow_url(), timeout=15.0)
        time.sleep(3.0)
        snapshot = _read_page_snapshot(client, text_limit=5000)
        if _recover_flow_application_error(client, snapshot):
            time.sleep(1.0)
        if _click_flow_entrypoint_if_present(client):
            time.sleep(4.0)
        snapshot = _read_page_snapshot(client)
    return snapshot

def _looks_like_login(snapshot: dict[str, str]) -> bool:
    url = snapshot.get("url", "")
    text = f"{snapshot.get('title', '')}\n{snapshot.get('text', '')}".lower()
    if any(marker in url for marker in _LOGIN_URL_MARKERS):
        return True
    return any(marker in text for marker in _LOGIN_TEXT_MARKERS)

def check_session(db: Session, *, provider: str = DEFAULT_PROVIDER) -> DBVideoProviderSession:
    row = get_default_session(db, provider=provider, create=True)
    if row is None:
        raise VideoProviderSessionError("Không tìm thấy phiên Veo mặc định.", error_code="VIDEO_PROVIDER_SESSION_NOT_FOUND")
    now = _now()
    row.status = "checking"
    row.failure_reason = None
    row.updated_at = now
    db.commit()
    try:
        runtime = launch_chrome(
            provider=provider,
            url=flow_url(),
            download_dir=video_provider_storage.get_provider_downloads_root() / provider,
        )
        snapshot = _page_snapshot(runtime)
    except VideoProviderSessionError as exc:
        row.status = "invalid"
        row.failure_reason = str(exc)
        row.last_checked_at = now
        row.updated_at = now
        db.commit()
        raise
    except Exception as exc:
        row.status = "invalid"
        row.failure_reason = "Không kiểm tra được phiên Chrome/Veo. Hãy mở lại Chrome profile Veo rồi thử lại."
        row.last_checked_at = now
        row.updated_at = now
        db.commit()
        raise VideoProviderSessionError(row.failure_reason, error_code="VIDEO_PROVIDER_SESSION_CHECK_FAILED") from exc

    if _looks_like_login(snapshot):
        row.status = "needs_login"
        row.failure_reason = "Veo/Google đang yêu cầu đăng nhập hoặc xác minh lại."
        row.last_checked_at = now
        row.updated_at = now
        db.commit()
        db.refresh(row)
        return row

    hint, identifier_hash = _extract_email_hint(snapshot.get("text"))
    if identifier_hash and row.account_identifier_hash and row.account_identifier_hash != identifier_hash:
        row.identity_status = "mismatch"
        row.verified_account_hint = hint
        row.account_identifier_hash = identifier_hash
    elif identifier_hash:
        row.account_identifier_hash = identifier_hash
        row.verified_account_hint = hint
        if row.identity_status not in {"confirmed", "mismatch"}:
            row.identity_status = "detected"
        row.identity_verified_at = now
    elif row.identity_status not in {"confirmed", "mismatch"}:
        row.identity_status = "unknown"
    if not row.connection_label:
        row.connection_label = f"{DEFAULT_CONNECTION_LABEL} - {row.verified_account_hint}" if row.verified_account_hint else DEFAULT_CONNECTION_LABEL
    row.provider_tool = DEFAULT_PROVIDER_TOOL
    row.status = "ready"
    row.last_checked_at = now
    row.failure_reason = None
    row.updated_at = now
    db.commit()
    db.refresh(row)
    return row

def update_connection_label(session_id: str, label: str, db: Session) -> DBVideoProviderSession | None:
    row = db.query(DBVideoProviderSession).filter(DBVideoProviderSession.id == session_id).first()
    if row is None:
        return None
    clean = video_storage.sanitize_download_filename(label, fallback=DEFAULT_CONNECTION_LABEL, max_length=120)
    row.connection_label = clean
    row.updated_at = _now()
    db.commit()
    db.refresh(row)
    return row

def confirm_identity(session_id: str, db: Session) -> DBVideoProviderSession | None:
    row = db.query(DBVideoProviderSession).filter(DBVideoProviderSession.id == session_id).first()
    if row is None:
        return None
    now = _now()
    row.identity_status = "confirmed"
    row.identity_verified_at = now
    row.status = "ready"
    row.failure_reason = None
    row.updated_at = now
    if not row.connection_label:
        row.connection_label = DEFAULT_CONNECTION_LABEL
    db.commit()
    db.refresh(row)
    return row

def invalidate_session(session_id: str, db: Session, *, reason: str | None = None) -> DBVideoProviderSession | None:
    row = db.query(DBVideoProviderSession).filter(DBVideoProviderSession.id == session_id).first()
    if row is None:
        return None
    row.status = "needs_login"
    row.failure_reason = reason or "Người dùng yêu cầu đăng nhập/kết nối lại Veo."
    row.updated_at = _now()
    db.commit()
    db.refresh(row)
    return row

def session_response_ready(row: DBVideoProviderSession | None) -> bool:
    if row is None:
        return False
    return row.status in READY_STATUSES and row.identity_status not in IDENTITY_BLOCKING_STATUSES

def active_runtime(provider: str = DEFAULT_PROVIDER) -> ChromeRuntime | None:
    runtime = _runtime_by_provider.get(provider)
    if runtime and _runtime_alive(runtime):
        return runtime
    return None
