"""Veo/Flow provider adapter driven through Chrome DevTools Protocol."""

from __future__ import annotations

import json
import mimetypes
import re
import time
import unicodedata
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable
from urllib.request import Request, urlopen

from . import chrome_cdp, video_provider_sessions, video_provider_storage, video_storage

SUPPORTED_VIDEO_SUFFIXES = {".mp4", ".mov", ".m4v", ".webm", ".mkv"}
TEMP_DOWNLOAD_SUFFIXES = {".crdownload", ".tmp", ".download"}
DEFAULT_GENERATION_TIMEOUT_SECONDS = 20 * 60
DEFAULT_DOWNLOAD_TIMEOUT_SECONDS = 10 * 60
DEFAULT_DOWNLOAD_STALLED_SECONDS = 90
NEW_PROJECT_TEXTS = ["Dự án mới", "Tạo dự án mới", "New project", "Create project"]
FLOW_DASHBOARD_SETTLE_SECONDS = 1.0
FLOW_AFTER_NEW_PROJECT_CLICK_SECONDS = 1.0
FLOW_STEP_DELAY_SECONDS = 1.0
FLOW_PROJECT_READY_TIMEOUT_SECONDS = 60.0
FLOW_PROMPT_READY_TIMEOUT_SECONDS = 60.0
FLOW_SUBMIT_VERIFY_TIMEOUT_SECONDS = 6.0
FLOW_GENERATION_RETRY_GRACE_SECONDS = 60.0
StatusCallback = Callable[[str, str | None], None]

class VeoChromeError(ValueError):
    """Raised when the Veo/Flow adapter cannot complete an item."""

    def __init__(self, message: str, *, error_code: str = "VIDEO_PROVIDER_ERROR", details: dict[str, Any] | None = None):
        super().__init__(message)
        self.error_code = error_code
        self.details = details or {}

@dataclass(frozen=True)
class DownloadContext:
    project_id: str
    job_id: str
    item_id: str
    shot_id: str
    shot_order: int
    prompt_id: str | None
    expected_download_dir: Path
    download_correlation_id: str

@dataclass(frozen=True)
class ProviderClipResult:
    downloaded_file_path: Path
    original_filename: str
    download_correlation_id: str
    provider_asset_id: str | None = None
    provider_project_url: str | None = None
    provider_project_ref_hash: str | None = None
    download_url_hash: str | None = None
    provider_duration_seconds: float | None = None
    credit_cost: int | None = None
    metadata: dict[str, Any] | None = None

def make_download_context(
    *,
    project_id: str,
    job_id: str,
    item_id: str,
    shot_id: str,
    shot_order: int,
    prompt_id: str | None,
) -> DownloadContext:
    return DownloadContext(
        project_id=project_id,
        job_id=job_id,
        item_id=item_id,
        shot_id=shot_id,
        shot_order=shot_order,
        prompt_id=prompt_id,
        expected_download_dir=video_provider_storage.get_item_download_dir(
            project_id=project_id,
            job_id=job_id,
            shot_order=shot_order,
            shot_id=shot_id,
            item_id=item_id,
        ),
        download_correlation_id=str(uuid.uuid4()),
    )

def _video_files(path: Path) -> list[Path]:
    if not path.exists():
        return []
    files: list[Path] = []
    for candidate in path.iterdir():
        if not candidate.is_file():
            continue
        if candidate.name.startswith("."):
            continue
        suffixes = {suffix.lower() for suffix in candidate.suffixes}
        if suffixes & TEMP_DOWNLOAD_SUFFIXES:
            continue
        if candidate.suffix.lower() in SUPPORTED_VIDEO_SUFFIXES:
            files.append(candidate)
    return sorted(files, key=lambda item: item.stat().st_mtime)

def _completed_download_files(path: Path) -> list[Path]:
    if not path.exists():
        return []
    files: list[Path] = []
    for candidate in path.iterdir():
        if not candidate.is_file() or candidate.name.startswith("."):
            continue
        suffixes = {suffix.lower() for suffix in candidate.suffixes}
        if suffixes & TEMP_DOWNLOAD_SUFFIXES:
            continue
        files.append(candidate)
    return sorted(files, key=lambda item: item.stat().st_mtime)

def _temporary_download_files(path: Path) -> list[Path]:
    if not path.exists():
        return []
    files: list[Path] = []
    for candidate in path.iterdir():
        if not candidate.is_file() or candidate.name.startswith("."):
            continue
        suffixes = {suffix.lower() for suffix in candidate.suffixes}
        if suffixes & TEMP_DOWNLOAD_SUFFIXES:
            files.append(candidate)
    return sorted(files, key=lambda item: item.stat().st_mtime)

def _download_signature(files: list[Path]) -> tuple[tuple[str, int], ...]:
    signature: list[tuple[str, int]] = []
    for file in files:
        try:
            signature.append((file.name, file.stat().st_size))
        except OSError:
            continue
    return tuple(sorted(signature))

def _stable_file(path: Path, *, checks: int = 2, interval_seconds: float = 1.0) -> bool:
    last_size = -1
    stable_count = 0
    while stable_count < checks:
        if not path.exists() or not path.is_file():
            return False
        size = path.stat().st_size
        if size <= 0:
            stable_count = 0
        elif size == last_size:
            stable_count += 1
        else:
            stable_count = 0
        last_size = size
        time.sleep(interval_seconds)
    return True

def _configure_download_behavior(client: chrome_cdp.CDPClient, download_dir: Path) -> None:
    download_dir.mkdir(parents=True, exist_ok=True)
    errors: list[Exception] = []
    try:
        client.set_download_behavior(str(download_dir))
    except Exception as exc:
        errors.append(exc)
    try:
        client.command(
            "Page.setDownloadBehavior",
            {"behavior": "allow", "downloadPath": str(download_dir)},
            timeout=5.0,
        )
    except Exception as exc:
        errors.append(exc)
    if len(errors) >= 2:
        raise VeoChromeError(
            "Không cấu hình được thư mục tải clip Veo cho tab Chrome hiện tại.",
            error_code="VIDEO_DOWNLOAD_DIRECTORY_UNAVAILABLE",
            details={"download_correlation_id": None},
        ) from errors[-1]

def wait_for_downloaded_video(
    context: DownloadContext,
    *,
    timeout_seconds: int = DEFAULT_DOWNLOAD_TIMEOUT_SECONDS,
    stalled_seconds: int = DEFAULT_DOWNLOAD_STALLED_SECONDS,
) -> Path:
    deadline = time.monotonic() + timeout_seconds
    last_temp_signature: tuple[tuple[str, int], ...] | None = None
    last_temp_change_at = time.monotonic()
    while time.monotonic() < deadline:
        now = time.monotonic()
        files = _video_files(context.expected_download_dir)
        completed_files = _completed_download_files(context.expected_download_dir)
        if completed_files and not files:
            raise VeoChromeError(
                "File tải về từ Veo không phải định dạng video được hỗ trợ.",
                error_code="VIDEO_DOWNLOAD_INVALID_FILE",
                details={
                    "download_correlation_id": context.download_correlation_id,
                    "filename": video_storage.sanitize_download_filename(completed_files[0].name, fallback="download"),
                },
            )
        if len(files) > 1:
            raise VeoChromeError(
                "Download mơ hồ: thư mục item có nhiều file video. Voicebox không import để tránh map nhầm shot.",
                error_code="VIDEO_DOWNLOAD_AMBIGUOUS",
                details={"download_correlation_id": context.download_correlation_id},
            )
        if len(files) == 1 and _stable_file(files[0]):
            return files[0]
        temp_files = _temporary_download_files(context.expected_download_dir)
        temp_signature = _download_signature(temp_files)
        if temp_signature:
            if temp_signature != last_temp_signature:
                last_temp_signature = temp_signature
                last_temp_change_at = now
            elif now - last_temp_change_at >= stalled_seconds:
                filename = video_storage.sanitize_download_filename(temp_files[0].name, fallback="download")
                raise VeoChromeError(
                    "Chrome đã bắt đầu tải clip Veo nhưng file tạm không tăng dung lượng trong thời gian dài.",
                    error_code="VIDEO_DOWNLOAD_STALLED",
                    details={
                        "download_correlation_id": context.download_correlation_id,
                        "filename": filename,
                    },
                )
        else:
            last_temp_signature = None
            last_temp_change_at = now
        time.sleep(1.0)
    raise VeoChromeError(
        "Veo chưa tải clip về thư mục item trong thời gian chờ.",
        error_code="VIDEO_DOWNLOAD_TIMEOUT",
        details={"download_correlation_id": context.download_correlation_id},
    )

def _json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False)

def _normalize_text(value: str | None) -> str:
    text = unicodedata.normalize("NFD", str(value or "").lower())
    return "".join(ch for ch in text if unicodedata.category(ch) != "Mn")

def _normalize_requested_duration(duration_seconds: float | None) -> int | None:
    if not duration_seconds:
        return None
    allowed = [4, 6, 8, 10]
    return min(allowed, key=lambda item: abs(item - float(duration_seconds)))

def _compact_prompt_text(value: str | None) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip()

def _flow_helpers_script() -> str:
    return r"""
    (() => {
      const norm = (value) => String(value || '').toLowerCase().normalize('NFD').replace(/[\u0300-\u036f]/g, '').trim();
      const visible = (el) => {
        const style = window.getComputedStyle(el);
        const rect = el.getBoundingClientRect();
        return style && style.display !== 'none' && style.visibility !== 'hidden' && rect.width > 2 && rect.height > 2;
      };
      const elements = () => Array.from(document.querySelectorAll('button,a,[role="button"],textarea,input,[contenteditable="true"],div[aria-label],span[aria-label]')).filter(visible);
      const textOf = (el) => norm([el.innerText, el.textContent, el.getAttribute('aria-label'), el.getAttribute('title'), el.getAttribute('placeholder')].filter(Boolean).join(' '));
      const enabled = (el) => !el.disabled && el.getAttribute('aria-disabled') !== 'true';
      const clickElement = (el) => {
        el.scrollIntoView({block: 'center', inline: 'center'});
        const rect = el.getBoundingClientRect();
        const init = {
          bubbles: true,
          cancelable: true,
          view: window,
          clientX: rect.left + rect.width / 2,
          clientY: rect.top + rect.height / 2
        };
        el.dispatchEvent(new MouseEvent('mouseover', init));
        el.dispatchEvent(new MouseEvent('mousemove', init));
        el.dispatchEvent(new MouseEvent('mousedown', init));
        el.dispatchEvent(new MouseEvent('mouseup', init));
        el.dispatchEvent(new MouseEvent('click', init));
        el.click();
        return true;
      };
      const clickByText = (texts) => {
        const needles = texts.map(norm);
        for (const el of elements()) {
          const hay = textOf(el);
          if (enabled(el) && needles.some((needle) => hay.includes(needle))) {
            return clickElement(el);
          }
        }
        const fallbackCandidates = Array.from(document.querySelectorAll('button,a,[role="button"],[tabindex],div,span'))
          .filter((el) => {
            if (!visible(el) || !enabled(el) || el.matches('textarea,input,[contenteditable="true"]')) return false;
            const rect = el.getBoundingClientRect();
            if (rect.width > window.innerWidth * 0.8 || rect.height > window.innerHeight * 0.5) return false;
            const hay = textOf(el);
            return needles.some((needle) => hay.includes(needle));
          })
          .map((el) => {
            const rect = el.getBoundingClientRect();
            const hay = textOf(el);
            const exact = needles.some((needle) => hay === needle);
            const starts = needles.some((needle) => hay.startsWith(needle));
            return {el, hay, rect, exact, starts, area: rect.width * rect.height};
          });
        fallbackCandidates.sort((left, right) =>
          Number(right.exact) - Number(left.exact) ||
          Number(right.starts) - Number(left.starts) ||
          left.area - right.area ||
          left.hay.length - right.hay.length
        );
        if (fallbackCandidates[0]) return clickElement(fallbackCandidates[0].el);
        return false;
      };
      const promptInput = () => {
        const preferred = elements().find((el) => {
          const hay = textOf(el);
          return (el.matches('textarea,input,[contenteditable="true"]') && (
            hay.includes('ban muon tao gi') ||
            hay.includes('what do you want') ||
            hay.includes('prompt') ||
            hay.includes('ask')
          ));
        });
        return preferred || elements().find((el) => el.matches('textarea,[contenteditable="true"]')) || null;
      };
      const focusPrompt = () => {
        const el = promptInput();
        if (!el) return {focused: false};
        el.scrollIntoView({block: 'center', inline: 'center'});
        const rect = el.getBoundingClientRect();
        const init = {
          bubbles: true,
          cancelable: true,
          view: window,
          clientX: rect.left + rect.width / 2,
          clientY: rect.top + rect.height / 2
        };
        el.dispatchEvent(new MouseEvent('mouseover', init));
        el.dispatchEvent(new MouseEvent('mousemove', init));
        el.dispatchEvent(new MouseEvent('mousedown', init));
        el.dispatchEvent(new MouseEvent('mouseup', init));
        el.dispatchEvent(new MouseEvent('click', init));
        el.focus();
        return {
          focused: document.activeElement === el || el.contains(document.activeElement),
          tagName: el.tagName,
          contentEditable: String(el.getAttribute('contenteditable') || ''),
          ariaLabel: String(el.getAttribute('aria-label') || ''),
          placeholder: String(el.getAttribute('placeholder') || '')
        };
      };
      const promptText = () => {
        const el = promptInput();
        if (!el) return '';
        if (el.getAttribute('contenteditable') === 'true') {
          return String(el.innerText || el.textContent || '');
        }
        return String(el.value || el.innerText || el.textContent || '');
      };
      const setPrompt = (text) => {
        const el = promptInput();
        if (!el) return false;
        el.scrollIntoView({block: 'center', inline: 'center'});
        el.focus();
        if (el.getAttribute('contenteditable') === 'true') {
          el.textContent = text;
          el.dispatchEvent(new InputEvent('input', {bubbles: true, inputType: 'insertText', data: text}));
        } else {
          const proto = el.tagName === 'TEXTAREA' ? HTMLTextAreaElement.prototype : HTMLInputElement.prototype;
          const setter = Object.getOwnPropertyDescriptor(proto, 'value')?.set;
          if (setter) setter.call(el, text);
          else el.value = text;
          el.dispatchEvent(new Event('input', {bubbles: true}));
          el.dispatchEvent(new Event('change', {bubbles: true}));
        }
        return true;
      };
      const submitPromptTarget = () => {
        const input = promptInput();
        if (!input) return null;
        const inputRect = input.getBoundingClientRect();
        const buttons = Array.from(document.querySelectorAll('button,[role="button"]')).filter((el) => {
          if (!visible(el) || !enabled(el)) return false;
          const rect = el.getBoundingClientRect();
          const nearComposer = rect.left >= inputRect.left - 32 &&
            rect.right <= inputRect.right + 64 &&
            rect.top >= inputRect.top - 64 &&
            rect.bottom <= inputRect.bottom + 96;
          return nearComposer;
        }).map((el) => {
          const rect = el.getBoundingClientRect();
          const hay = textOf(el);
          return {
            el,
            hay,
            rect,
            score:
              (hay.includes('arrow_forward') ? 100 : 0) +
              (hay.includes('send') || hay.includes('gui') || hay.includes('submit') ? 90 : 0) +
              (rect.left > inputRect.left + inputRect.width * 0.65 ? 20 : 0) -
              (hay.includes('add') || hay.includes('close') || hay.includes('tune') || hay.includes('settings') || hay.includes('article') ? 80 : 0)
          };
        }).filter((candidate) => candidate.score > 0);
        buttons.sort((left, right) => right.score - left.score || right.rect.left - left.rect.left);
        if (!buttons[0]) return null;
        const rect = buttons[0].rect;
        return {
          x: rect.left + rect.width / 2,
          y: rect.top + rect.height / 2,
          text: buttons[0].hay
        };
      };
      const submitPrompt = () => {
        const target = submitPromptTarget();
        if (target) {
          const el = document.elementFromPoint(target.x, target.y);
          if (el) return clickElement(el.closest('button,[role="button"]') || el);
        }
        return clickByText(['Gửi', 'Send', 'Submit']);
      };
      const bodyText = () => norm(document.body && document.body.innerText || '');
      const hasPromptInput = () => Boolean(promptInput());
      return {clickByText, setPrompt, submitPrompt, submitPromptTarget, bodyText, textOf, hasPromptInput, focusPrompt, promptText};
    })()
    """

def _eval_flow_action(client: chrome_cdp.CDPClient, expression: str, *, timeout: float = 10.0) -> Any:
    return client.evaluate(
        f"""
        (() => {{
          const helpers = {_flow_helpers_script()};
          return (() => {{ {expression} }})();
        }})()
        """,
        timeout=timeout,
    )

def _click_text(client: chrome_cdp.CDPClient, texts: list[str], *, timeout: float = 10.0) -> bool:
    result = _eval_flow_action(client, f"return helpers.clickByText({_json(texts)});", timeout=timeout)
    return bool(result)

def _wait_click_text(client: chrome_cdp.CDPClient, texts: list[str], *, timeout: float = 10.0) -> bool:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if _click_text(client, texts, timeout=min(2.0, max(0.5, deadline - time.monotonic()))):
            return True
        time.sleep(1.0)
    return False

def _click_action_row_by_text(client: chrome_cdp.CDPClient, texts: list[str], *, timeout: float = 5.0) -> bool:
    try:
        result = client.evaluate(
            f"""
            (() => {{
              const norm = (value) => String(value || '').toLowerCase().normalize('NFD').replace(/[\\u0300-\\u036f]/g, '').replace(/\\s+/g, ' ').trim();
              const needles = {_json(texts)}.map(norm);
              const visible = (el) => {{
                const style = getComputedStyle(el);
                const rect = el.getBoundingClientRect();
                return style.display !== 'none' && style.visibility !== 'hidden' && style.pointerEvents !== 'none' && rect.width > 2 && rect.height > 2;
              }};
              const textOf = (el) => norm([el.innerText, el.textContent, el.getAttribute('aria-label'), el.getAttribute('title')].filter(Boolean).join(' '));
              const enabled = (el) => !el.disabled && el.getAttribute('aria-disabled') !== 'true';
              const clickElement = (el) => {{
                el.scrollIntoView({{block: 'center', inline: 'center'}});
                const rect = el.getBoundingClientRect();
                const init = {{
                  bubbles: true,
                  cancelable: true,
                  view: window,
                  clientX: rect.left + rect.width / 2,
                  clientY: rect.top + rect.height / 2
                }};
                el.dispatchEvent(new MouseEvent('mouseover', init));
                el.dispatchEvent(new MouseEvent('mousemove', init));
                el.dispatchEvent(new MouseEvent('mousedown', init));
                el.dispatchEvent(new MouseEvent('mouseup', init));
                el.dispatchEvent(new MouseEvent('click', init));
                el.click?.();
                return true;
              }};
              const rowFor = (el, needle) => {{
                let current = el;
                let best = el;
                for (let depth = 0; current && depth < 5; depth += 1, current = current.parentElement) {{
                  if (!visible(current) || !enabled(current)) continue;
                  const rect = current.getBoundingClientRect();
                  const text = textOf(current);
                  if (!text.includes(needle)) continue;
                  if (rect.width <= 640 && rect.height <= 96) best = current;
                }}
                return best;
              }};
              const candidates = [];
              for (const el of Array.from(document.querySelectorAll('body *'))) {{
                if (!visible(el) || !enabled(el) || el.matches('textarea,input,[contenteditable="true"]')) continue;
                const text = textOf(el);
                if (!text) continue;
                for (const needle of needles) {{
                  if (text === needle || text.endsWith(' ' + needle) || text.includes(needle)) {{
                    const row = rowFor(el, needle);
                    const rect = row.getBoundingClientRect();
                    if (rect.width <= 640 && rect.height <= 96) {{
                      candidates.push({{
                        el: row,
                        text: textOf(row),
                        exact: Number(textOf(row) === needle),
                        suffix: Number(textOf(row).endsWith(' ' + needle)),
                        area: rect.width * rect.height,
                        y: rect.top
                      }});
                    }}
                  }}
                }}
              }}
              candidates.sort((left, right) =>
                right.exact - left.exact ||
                right.suffix - left.suffix ||
                right.area - left.area ||
                right.y - left.y
              );
              if (!candidates[0]) return null;
              const rect = candidates[0].el.getBoundingClientRect();
              return {{
                x: rect.left + rect.width / 2,
                y: rect.top + rect.height / 2,
                text: candidates[0].text
              }};
            }})()
            """,
            timeout=timeout,
        )
    except Exception:
        return False
    if isinstance(result, dict) and result.get("x") is not None and result.get("y") is not None:
        try:
            _dispatch_mouse_click(client, float(result["x"]), float(result["y"]))
        except Exception:
            return False
        return True
    return bool(result)

def _looks_like_flow_project_workspace(snapshot: dict[str, str]) -> bool:
    url = snapshot.get("url", "").lower()
    text = _normalize_text(snapshot.get("text", ""))
    if "/project/" not in url:
        return False
    return any(
        marker in text
        for marker in (
            "ban muon tao gi",
            "bat dau sang tao",
            "tac nhan",
            "what do you want",
            "start creating",
            "agent",
            "prompt",
        )
    )

def _wait_for_flow_project_ready(client: chrome_cdp.CDPClient, *, timeout: float = FLOW_PROJECT_READY_TIMEOUT_SECONDS) -> dict[str, str]:
    deadline = time.monotonic() + timeout
    last_snapshot: dict[str, str] = {"url": "", "title": "", "text": ""}
    while time.monotonic() < deadline:
        last_snapshot = video_provider_sessions._read_page_snapshot(client, text_limit=5000)
        if video_provider_sessions._looks_like_flow_application_error(last_snapshot):
            return last_snapshot
        if _looks_like_flow_project_workspace(last_snapshot):
            return last_snapshot
        time.sleep(FLOW_STEP_DELAY_SECONDS)
    return last_snapshot

def _open_new_flow_project(client: chrome_cdp.CDPClient) -> dict[str, str]:
    last_snapshot: dict[str, str] = {"url": "", "title": "", "text": ""}
    for attempt in range(2):
        time.sleep(FLOW_DASHBOARD_SETTLE_SECONDS)
        if not _wait_click_text(client, NEW_PROJECT_TEXTS, timeout=12.0):
            raise VeoChromeError(
                "Không tìm thấy nút tạo dự án mới trong Flow.",
                error_code="VIDEO_PROVIDER_UI_CHANGED",
            )
        time.sleep(FLOW_AFTER_NEW_PROJECT_CLICK_SECONDS)
        last_snapshot = _wait_for_flow_project_ready(client)
        if _looks_like_flow_project_workspace(last_snapshot):
            return last_snapshot
        if attempt == 0 and video_provider_sessions._recover_flow_application_error(client, last_snapshot):
            time.sleep(FLOW_DASHBOARD_SETTLE_SECONDS)
            continue
    raise VeoChromeError(
        "Flow bị lỗi giao diện khi mở dự án mới. Voicebox đã thử phục hồi phiên nhưng Flow vẫn trả Application error.",
        error_code="VIDEO_PROVIDER_FLOW_APP_ERROR",
        details={"url_hash": chrome_cdp.sha256_short(last_snapshot.get("url", ""), length=24)},
    )

def _open_existing_flow_project(client: chrome_cdp.CDPClient, provider_project_url: str) -> dict[str, str]:
    client.navigate(provider_project_url, timeout=20.0)
    snapshot = _wait_for_flow_project_ready(client)
    if video_provider_sessions._looks_like_flow_application_error(snapshot):
        if video_provider_sessions._recover_flow_application_error(client, snapshot):
            time.sleep(FLOW_STEP_DELAY_SECONDS)
            client.navigate(provider_project_url, timeout=20.0)
            snapshot = _wait_for_flow_project_ready(client)
    if _looks_like_flow_project_workspace(snapshot):
        return snapshot
    raise VeoChromeError(
        "Không mở lại được Flow project đã gắn với project/job này.",
        error_code="VIDEO_PROVIDER_PROJECT_NOT_READY",
        details={"url_hash": chrome_cdp.sha256_short(provider_project_url, length=24)},
    )

def _body_text(client: chrome_cdp.CDPClient, *, timeout: float = 10.0) -> str:
    result = _eval_flow_action(client, "return helpers.bodyText();", timeout=timeout)
    return str(result or "")

def _wait_for_prompt_input(client: chrome_cdp.CDPClient, *, timeout: float = FLOW_PROMPT_READY_TIMEOUT_SECONDS) -> bool:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        snapshot = video_provider_sessions._read_page_snapshot(client, text_limit=5000)
        if video_provider_sessions._looks_like_flow_application_error(snapshot):
            return False
        try:
            if _eval_flow_action(client, "return helpers.hasPromptInput();", timeout=5.0):
                return True
        except Exception:
            pass
        time.sleep(FLOW_STEP_DELAY_SECONDS)
    return False

def _enter_prompt_text(
    client: chrome_cdp.CDPClient,
    prompt: str,
    *,
    mismatch_error_code: str,
    mismatch_message: str,
) -> None:
    if not _wait_for_prompt_input(client):
        raise VeoChromeError(
            "Flow chưa load xong ô chat 'Bạn muốn tạo gì?', không gửi prompt để tránh làm vỡ phiên.",
            error_code="VIDEO_PROVIDER_UI_CHANGED",
        )
    focus_result = _eval_flow_action(client, "return helpers.focusPrompt();", timeout=10.0)
    if not isinstance(focus_result, dict) or not focus_result.get("focused"):
        raise VeoChromeError(
            "Không tìm thấy ô chat 'Bạn muốn tạo gì?' của Flow.",
            error_code="VIDEO_PROVIDER_UI_CHANGED",
        )
    try:
        client.command("Input.dispatchKeyEvent", {"type": "keyDown", "key": "Meta", "code": "MetaLeft", "windowsVirtualKeyCode": 91, "modifiers": 4})
        client.command("Input.dispatchKeyEvent", {"type": "keyDown", "key": "a", "code": "KeyA", "windowsVirtualKeyCode": 65, "modifiers": 4})
        client.command("Input.dispatchKeyEvent", {"type": "keyUp", "key": "a", "code": "KeyA", "windowsVirtualKeyCode": 65, "modifiers": 4})
        client.command("Input.dispatchKeyEvent", {"type": "keyUp", "key": "Meta", "code": "MetaLeft", "windowsVirtualKeyCode": 91})
        client.command("Input.dispatchKeyEvent", {"type": "keyDown", "key": "Backspace", "code": "Backspace", "windowsVirtualKeyCode": 8})
        client.command("Input.dispatchKeyEvent", {"type": "keyUp", "key": "Backspace", "code": "Backspace", "windowsVirtualKeyCode": 8})
        time.sleep(FLOW_STEP_DELAY_SECONDS)
        client.command("Input.insertText", {"text": prompt}, timeout=30.0)
    except Exception as exc:
        raise VeoChromeError(
            "Không nhập được prompt vào ô chat Flow bằng thao tác Chrome an toàn.",
            error_code="VIDEO_PROVIDER_UI_CHANGED",
        ) from exc
    time.sleep(FLOW_STEP_DELAY_SECONDS)
    actual_prompt = str(_eval_flow_action(client, "return helpers.promptText();", timeout=10.0) or "")
    expected_compact = _compact_prompt_text(prompt)
    actual_compact = _compact_prompt_text(actual_prompt)
    if actual_compact != expected_compact:
        raise VeoChromeError(
            mismatch_message,
            error_code=mismatch_error_code,
            details={
                "expected_length": len(expected_compact),
                "actual_length": len(actual_compact),
                "expected_hash": chrome_cdp.sha256_short(expected_compact, length=16),
                "actual_hash": chrome_cdp.sha256_short(actual_compact, length=16),
            },
        )

def _click_prompt_submit(client: chrome_cdp.CDPClient) -> bool:
    target = _eval_flow_action(client, "return helpers.submitPromptTarget();", timeout=5.0)
    if isinstance(target, dict) and target.get("x") is not None and target.get("y") is not None:
        _dispatch_mouse_click(client, float(target["x"]), float(target["y"]))
        return True
    if _eval_flow_action(client, "return helpers.submitPrompt();", timeout=5.0):
        return True
    client.command("Input.dispatchKeyEvent", {"type": "keyDown", "key": "Enter", "windowsVirtualKeyCode": 13})
    client.command("Input.dispatchKeyEvent", {"type": "keyUp", "key": "Enter", "windowsVirtualKeyCode": 13})
    return False

def _dispatch_mouse_click(client: chrome_cdp.CDPClient, x: float, y: float) -> None:
    client.command("Input.dispatchMouseEvent", {"type": "mouseMoved", "x": x, "y": y})
    client.command(
        "Input.dispatchMouseEvent",
        {"type": "mousePressed", "x": x, "y": y, "button": "left", "buttons": 1, "clickCount": 1},
    )
    client.command(
        "Input.dispatchMouseEvent",
        {"type": "mouseReleased", "x": x, "y": y, "button": "left", "buttons": 0, "clickCount": 1},
    )

def _wait_until_prompt_text_changes(
    client: chrome_cdp.CDPClient,
    submitted_text: str,
    *,
    timeout: float = FLOW_SUBMIT_VERIFY_TIMEOUT_SECONDS,
) -> tuple[bool, str]:
    expected = _compact_prompt_text(submitted_text)
    deadline = time.monotonic() + timeout
    last_actual = ""
    while time.monotonic() < deadline:
        snapshot = video_provider_sessions._read_page_snapshot(client, text_limit=3000)
        if video_provider_sessions._looks_like_flow_application_error(snapshot):
            raise VeoChromeError(
                "Flow bị lỗi giao diện sau khi bấm gửi prompt.",
                error_code="VIDEO_PROVIDER_FLOW_APP_ERROR",
                details={"url_hash": chrome_cdp.sha256_short(snapshot.get("url", ""), length=24)},
            )
        try:
            actual = str(_eval_flow_action(client, "return helpers.promptText();", timeout=5.0) or "")
        except Exception:
            return True, last_actual
        last_actual = _compact_prompt_text(actual)
        if last_actual != expected:
            return True, last_actual
        time.sleep(FLOW_STEP_DELAY_SECONDS)
    return False, last_actual

def _enter_and_submit_prompt_text(
    client: chrome_cdp.CDPClient,
    prompt: str,
    *,
    mismatch_error_code: str,
    mismatch_message: str,
    submit_error_code: str,
    submit_message: str,
) -> None:
    _enter_prompt_text(
        client,
        prompt,
        mismatch_error_code=mismatch_error_code,
        mismatch_message=mismatch_message,
    )
    for attempt in range(2):
        _click_prompt_submit(client)
        changed, actual = _wait_until_prompt_text_changes(client, prompt)
        if changed:
            return
        if attempt == 0:
            _eval_flow_action(client, "return helpers.focusPrompt();", timeout=5.0)
            time.sleep(FLOW_STEP_DELAY_SECONDS)
    compact_prompt = _compact_prompt_text(prompt)
    raise VeoChromeError(
        submit_message,
        error_code=submit_error_code,
        details={
            "expected_length": len(compact_prompt),
            "actual_length": len(actual),
            "expected_hash": chrome_cdp.sha256_short(compact_prompt, length=16),
            "actual_hash": chrome_cdp.sha256_short(actual, length=16),
        },
    )

def _submit_prompt(client: chrome_cdp.CDPClient, prompt: str) -> None:
    _enter_and_submit_prompt_text(
        client,
        prompt,
        mismatch_error_code="VIDEO_PROVIDER_PROMPT_MISMATCH",
        mismatch_message="Prompt trong Flow không khớp prompt của project nên Voicebox không gửi để tránh tạo sai video.",
        submit_error_code="VIDEO_PROVIDER_PROMPT_SUBMIT_FAILED",
        submit_message="Flow vẫn giữ nguyên prompt trong ô chat sau khi bấm gửi, nên Voicebox dừng để tránh tạo sai video.",
    )

def _parse_credit_cost(text: str) -> int | None:
    match = re.search(r"(\d+)\s*(?:tin dung|credit|credits)", _normalize_text(text), flags=re.IGNORECASE)
    return int(match.group(1)) if match else None

def _answer_duration_if_needed(
    client: chrome_cdp.CDPClient,
    *,
    requested_duration_seconds: float | None,
    on_status: StatusCallback | None = None,
) -> float | None:
    text = _normalize_text(_body_text(client))
    duration_question = any(
        marker in text
        for marker in (
            "ban muon video dai bao lau",
            "ban muon video nay dai bao lau",
            "chon thoi luong",
            "thoi luong video",
            "select a duration",
            "choose a duration",
            "how long",
            "video length",
        )
    )
    duration_option_count = sum(
        1
        for value in [4, 6, 8, 10]
        if f"{value} giay" in text or f"{value}s" in text or f"{value} second" in text
    )
    if not duration_question and duration_option_count < 2:
        return None
    if on_status:
        on_status("resolving_followup", "Đang chọn duration Veo phù hợp.")
    requested = _normalize_requested_duration(requested_duration_seconds) or 4
    options = [value for value in [4, 6, 8, 10] if f"{value}" in text and ("giay" in text or "second" in text or "s" in text)]
    selected = requested if requested in options else (options[0] if options else requested)
    answer = f"{selected} giây"
    _enter_and_submit_prompt_text(
        client,
        answer,
        mismatch_error_code="VIDEO_PROVIDER_FOLLOWUP_MISMATCH",
        mismatch_message="Câu trả lời duration trong Flow không khớp lựa chọn của Voicebox nên không gửi để tránh sai cấu hình.",
        submit_error_code="VIDEO_PROVIDER_FOLLOWUP_SUBMIT_FAILED",
        submit_message="Flow vẫn giữ nguyên câu trả lời duration sau khi bấm gửi, nên Voicebox dừng thay vì chờ render ảo.",
    )
    return float(selected)

def _answer_topic_followup_if_needed(
    client: chrome_cdp.CDPClient,
    *,
    prompt: str,
    on_status: StatusCallback | None = None,
) -> bool:
    text = _normalize_text(_body_text(client))
    topic_question = (
        ("toi co the tao" in text or "i can create" in text)
        and any(
            marker in text
            for marker in (
                "ban muon video noi ve chu de gi",
                "ban muon video noi ve chu đe gi",
                "what topic",
                "what subject",
                "what should the video be about",
            )
        )
    )
    if not topic_question:
        return False
    if on_status:
        on_status("resolving_followup", "Flow hỏi lại chủ đề sau khi chọn duration, đang gửi lại prompt video.")
    _enter_and_submit_prompt_text(
        client,
        prompt,
        mismatch_error_code="VIDEO_PROVIDER_TOPIC_FOLLOWUP_MISMATCH",
        mismatch_message="Câu trả lời chủ đề trong Flow không khớp prompt của project nên Voicebox không gửi để tránh tạo sai video.",
        submit_error_code="VIDEO_PROVIDER_TOPIC_FOLLOWUP_SUBMIT_FAILED",
        submit_message="Flow vẫn giữ nguyên prompt chủ đề sau khi bấm gửi, nên Voicebox dừng thay vì chờ render ảo.",
    )
    return True

def _resolve_flow_agent_followups(
    client: chrome_cdp.CDPClient,
    *,
    prompt: str,
    requested_duration_seconds: float | None,
    on_status: StatusCallback | None = None,
) -> float | None:
    provider_duration: float | None = None
    for _attempt in range(4):
        selected = _answer_duration_if_needed(
            client,
            requested_duration_seconds=requested_duration_seconds,
            on_status=on_status,
        )
        if selected is not None:
            provider_duration = selected
            time.sleep(FLOW_STEP_DELAY_SECONDS)
            continue
        if _answer_topic_followup_if_needed(client, prompt=prompt, on_status=on_status):
            time.sleep(FLOW_STEP_DELAY_SECONDS)
            continue
        break
    return provider_duration

def _approve_credit_from_text(
    client: chrome_cdp.CDPClient,
    text: str,
    *,
    credit_approval_policy: str,
    max_credit_per_job: int | None,
    credit_spent_estimate: int,
    on_status: StatusCallback | None = None,
) -> int | None:
    if not any(marker in text for marker in ("tin dung", "credit", "credits")):
        return None
    if on_status:
        on_status("credit_policy_check", "Đang kiểm tra chính sách credit của Flow.")
    credit_cost = _parse_credit_cost(text)
    if credit_cost is not None and max_credit_per_job is not None and credit_spent_estimate + credit_cost > max_credit_per_job:
        raise VeoChromeError(
            "Số credit dự kiến vượt giới hạn của job, cần người dùng phê duyệt thủ công.",
            error_code="VIDEO_PROVIDER_CREDIT_LIMIT_EXCEEDED",
            details={"credit_cost": credit_cost, "max_credit_per_job": max_credit_per_job},
        )
    if credit_approval_policy == "approve_dont_ask_again":
        if on_status:
            on_status("approving_credit", "Đang phê duyệt credit theo policy của job.")
        if _click_action_row_by_text(
            client,
            [
                "Phê duyệt, không hỏi lại",
                "Approve, do not ask again",
                "Approve, don't ask again",
                "Approve and don't ask again",
            ],
        ) or _click_text(
            client,
            [
                "Phê duyệt, không hỏi lại",
                "Approve, do not ask again",
                "Approve, don't ask again",
                "Approve and don't ask again",
            ],
        ):
            return credit_cost
    if credit_approval_policy == "manual_per_item":
        raise VeoChromeError(
            "Flow đang yêu cầu phê duyệt credit cho item này.",
            error_code="VIDEO_PROVIDER_NEEDS_CREDIT_APPROVAL",
            details={"credit_cost": credit_cost},
        )
    if on_status:
        on_status("approving_credit", "Đang phê duyệt credit một lần.")
    if _click_action_row_by_text(client, ["Phê duyệt", "Approve"]) or _click_text(client, ["Phê duyệt", "Approve"]):
        return credit_cost
    raise VeoChromeError(
        "Không tìm thấy nút phê duyệt credit trong Flow.",
        error_code="VIDEO_PROVIDER_UI_CHANGED",
        details={"credit_cost": credit_cost},
    )

def _approve_credit_if_needed(
    client: chrome_cdp.CDPClient,
    *,
    credit_approval_policy: str,
    max_credit_per_job: int | None,
    credit_spent_estimate: int,
    on_status: StatusCallback | None = None,
    wait_seconds: float = 8.0,
) -> int | None:
    deadline = time.monotonic() + wait_seconds
    while True:
        text = _normalize_text(_body_text(client))
        if any(marker in text for marker in ("tin dung", "credit", "credits")):
            return _approve_credit_from_text(
                client,
                text,
                credit_approval_policy=credit_approval_policy,
                max_credit_per_job=max_credit_per_job,
                credit_spent_estimate=credit_spent_estimate,
                on_status=on_status,
            )
        if time.monotonic() >= deadline:
            return None
        time.sleep(1.0)

def _looks_like_flow_generation_error(text: str) -> bool:
    error_markers = (
        "da xay ra loi",
        "hay thu lai",
        "thu lai",
        "khong thanh cong",
        "không thành công",
        "su dung lai cau lenh",
        "sử dụng lại câu lệnh",
        "something went wrong",
        "try again",
        "could not generate",
        "generation failed",
    )
    pending_markers = (
        "scheduled",
        "waiting in the queue",
        "in the queue",
        "check back",
        "da duoc dua vao hang doi",
        "dang trong hang doi",
        "cho trong hang doi",
        "dang doi",
    )
    last_error = max((text.rfind(marker) for marker in error_markers), default=-1)
    if last_error < 0:
        return False
    last_pending = max((text.rfind(marker) for marker in pending_markers), default=-1)
    return last_pending < last_error

def _looks_like_flow_generation_pending(text: str) -> bool:
    return bool(re.search(r"(?<!\d)(?:[1-9]\d?|100)%(?!\d)", text)) or any(
        marker in text
        for marker in (
            "scheduled",
            "waiting in the queue",
            "in the queue",
            "check back",
            "da duoc dua vao hang doi",
            "dang trong hang doi",
            "cho trong hang doi",
            "dang doi",
        )
    )

def _page_text_for_generation_wait(client: chrome_cdp.CDPClient, snapshot: dict[str, str]) -> str:
    snapshot_text = _normalize_text(snapshot.get("text", ""))
    try:
        body_text = _normalize_text(_body_text(client, timeout=2.0))
    except Exception:
        return snapshot_text
    return body_text or snapshot_text

def _click_generation_retry(client: chrome_cdp.CDPClient) -> bool:
    retry_texts = [
        "Thử lại",
        "Sử dụng lại câu lệnh",
        "Try again",
        "Reuse prompt",
        "Use prompt again",
    ]
    try:
        return _click_action_row_by_text(client, retry_texts, timeout=3.0) or _click_text(client, retry_texts, timeout=3.0)
    except Exception:
        return False

def _has_generated_media_preview(client: chrome_cdp.CDPClient) -> bool:
    try:
        result = client.evaluate(
            """
            (() => {
              const visible = (el, minWidth = 2, minHeight = 2) => {
                const style = window.getComputedStyle(el);
                const rect = el.getBoundingClientRect();
                return style.display !== 'none' &&
                  style.visibility !== 'hidden' &&
                  style.pointerEvents !== 'none' &&
                  rect.width >= minWidth &&
                  rect.height >= minHeight;
              };
              if (Array.from(document.querySelectorAll('video,img,canvas')).some((el) => visible(el, 80, 80))) {
                return true;
              }
              return Array.from(document.querySelectorAll('button,[role="button"],section,div')).some((el) => {
                const rect = el.getBoundingClientRect();
                if (!visible(el, 100, 100) || rect.top < 60) return false;
                const text = String(el.innerText || el.textContent || el.getAttribute('aria-label') || '').toLowerCase();
                return text.includes('play_circle') || text.includes('pause_circle') || text.includes('videocam');
              });
            })()
            """,
            timeout=5.0,
        )
    except Exception:
        return False
    return bool(result)

def _generated_media_target_script(*, prefer_more_button: bool = False) -> str:
    return f"""
            (() => {{
              const preferMoreButton = {str(prefer_more_button).lower()};
              const norm = (value) => String(value || '').toLowerCase().normalize('NFD').replace(/[\\u0300-\\u036f]/g, '').replace(/\\s+/g, ' ').trim();
              const visible = (el, minWidth = 2, minHeight = 2) => {{
                const style = window.getComputedStyle(el);
                const rect = el.getBoundingClientRect();
                return style.display !== 'none' &&
                  style.visibility !== 'hidden' &&
                  style.pointerEvents !== 'none' &&
                  rect.width >= minWidth &&
                  rect.height >= minHeight;
              }};
              const textOf = (el) => norm([el.innerText, el.textContent, el.getAttribute('aria-label'), el.getAttribute('title')].filter(Boolean).join(' '));
              const centerOf = (el, kind) => {{
                el.scrollIntoView({{block: 'center', inline: 'center'}});
                const rect = el.getBoundingClientRect();
                return {{x: rect.left + rect.width / 2, y: rect.top + rect.height / 2, kind}};
              }};
              const isPageShell = (el) => el === document.body || el === document.documentElement;
              const mediaElements = Array.from(document.querySelectorAll('video,img,canvas'))
                .filter((el) => visible(el, 80, 80) && el.getBoundingClientRect().top >= 60);
              const iconElements = Array.from(document.querySelectorAll('button,[role="button"],div,span'))
                .filter((el) => {{
                  if (!visible(el, 24, 24)) return false;
                  const rect = el.getBoundingClientRect();
                  if (rect.top < 60) return false;
                  const text = textOf(el);
                  return text.includes('play_circle') || text.includes('pause_circle') || text.includes('videocam');
                }});
              const seeds = [...mediaElements, ...iconElements];
              const cards = [];
              for (const seed of seeds) {{
                const seedRect = seed.getBoundingClientRect();
                let current = seed;
                let best = seed;
                for (let depth = 0; current && depth < 8; depth += 1, current = current.parentElement) {{
                  if (isPageShell(current) || !visible(current)) continue;
                  const rect = current.getBoundingClientRect();
                  if (rect.width < 100 || rect.height < 100 || rect.top < 60) continue;
                  if (rect.width > window.innerWidth * 0.96 || rect.height > window.innerHeight * 0.86) continue;
                  if (
                    rect.left <= seedRect.left + 2 &&
                    rect.right >= seedRect.right - 2 &&
                    rect.top <= seedRect.top + 2 &&
                    rect.bottom >= seedRect.bottom - 2
                  ) {{
                    best = current;
                  }}
                }}
                const rect = best.getBoundingClientRect();
                cards.push({{seed, card: best, rect, area: rect.width * rect.height}});
              }}
              cards.sort((left, right) =>
                left.area - right.area ||
                right.rect.top - left.rect.top ||
                right.rect.right - left.rect.right
              );
              if (preferMoreButton) {{
                for (const candidate of cards) {{
                  const rect = candidate.rect;
                  const moreButtons = Array.from(candidate.card.querySelectorAll('button,[role="button"],[aria-label],[title]'))
                    .filter((button) => {{
                      if (!visible(button, 16, 16)) return false;
                      const buttonRect = button.getBoundingClientRect();
                      if (
                        buttonRect.left < rect.left - 8 ||
                        buttonRect.right > rect.right + 8 ||
                        buttonRect.top < rect.top - 8 ||
                        buttonRect.bottom > rect.bottom + 8
                      ) return false;
                      const text = textOf(button);
                      return /(^| )(more_vert|more_horiz|khac|tuy chon|more options|more)( |$)/.test(text);
                    }})
                    .map((button) => ({{button, rect: button.getBoundingClientRect()}}));
                  moreButtons.sort((left, right) => right.rect.right - left.rect.right || left.rect.top - right.rect.top);
                  if (moreButtons[0]) return centerOf(moreButtons[0].button, 'more');
                }}
                return null;
              }}
              const first = cards[0];
              if (!first) return null;
              const clickable = first.seed.closest('button,[role="button"],a') || first.seed;
              return centerOf(clickable, first.seed.matches('video,img,canvas') ? 'media' : 'icon');
            }})()
            """

def _click_generated_media_target(client: chrome_cdp.CDPClient, *, prefer_more_button: bool = False) -> bool:
    try:
        target = client.evaluate(_generated_media_target_script(prefer_more_button=prefer_more_button), timeout=5.0)
    except Exception:
        return False
    if not isinstance(target, dict) or target.get("x") is None or target.get("y") is None:
        return False
    try:
        _dispatch_mouse_click(client, float(target["x"]), float(target["y"]))
    except Exception:
        return False
    return True

def _generated_media_count(client: chrome_cdp.CDPClient) -> int:
    try:
        result = client.evaluate(
            """
            (() => {
              const visible = (el) => {
                const style = window.getComputedStyle(el);
                const rect = el.getBoundingClientRect();
                return style.display !== 'none' && style.visibility !== 'hidden' && rect.width > 80 && rect.height > 80;
              };
              const mediaCards = new Set();
              for (const el of Array.from(document.querySelectorAll('video,img,canvas,[role="button"],button'))) {
                if (!visible(el)) continue;
                const text = String(el.innerText || el.textContent || el.getAttribute('aria-label') || '').toLowerCase();
                const hasMedia = el.matches('video,img,canvas') || text.includes('play_circle') || text.includes('pause_circle');
                if (!hasMedia) continue;
                let current = el;
                for (let depth = 0; current && depth < 6; depth += 1, current = current.parentElement) {
                  if (!visible(current)) continue;
                  const rect = current.getBoundingClientRect();
                  if (rect.width >= 100 && rect.height >= 100 && rect.width <= window.innerWidth && rect.height <= window.innerHeight) {
                    mediaCards.add(current);
                    break;
                  }
                }
              }
              return mediaCards.size;
            })()
            """,
            timeout=5.0,
        )
    except Exception:
        return 0
    try:
        return int(result or 0)
    except (TypeError, ValueError):
        return 0

def _click_generated_media_download(client: chrome_cdp.CDPClient) -> bool:
    selected = _click_generated_media_target(client)
    if not selected:
        try:
            selected = client.evaluate(
                """
            (() => {
              const norm = (value) => String(value || '').toLowerCase().normalize('NFD').replace(/[\\u0300-\\u036f]/g, '').replace(/\\s+/g, ' ').trim();
              const visible = (el) => {
                const style = window.getComputedStyle(el);
                const rect = el.getBoundingClientRect();
                return style.display !== 'none' && style.visibility !== 'hidden' && style.pointerEvents !== 'none' && rect.width > 2 && rect.height > 2;
              };
              const textOf = (el) => norm([el.innerText, el.textContent, el.getAttribute('aria-label'), el.getAttribute('title')].filter(Boolean).join(' '));
              const clickElement = (el) => {
                el.scrollIntoView({block: 'center', inline: 'center'});
                const rect = el.getBoundingClientRect();
                const init = {
                  bubbles: true,
                  cancelable: true,
                  view: window,
                  clientX: rect.left + rect.width / 2,
                  clientY: rect.top + rect.height / 2
                };
                el.dispatchEvent(new MouseEvent('mouseover', init));
                el.dispatchEvent(new MouseEvent('mousemove', init));
                el.dispatchEvent(new MouseEvent('mousedown', init));
                el.dispatchEvent(new MouseEvent('mouseup', init));
                el.dispatchEvent(new MouseEvent('click', init));
                el.click?.();
                return true;
              };
              const cards = Array.from(document.querySelectorAll('[role="button"],section,div'))
                .filter((el) => {
                  if (!visible(el)) return false;
                  const rect = el.getBoundingClientRect();
                  if (rect.width < 100 || rect.height < 100 || rect.top < 60) return false;
                  const text = textOf(el);
                  return el.querySelector('video,img,canvas') || text.includes('play_circle') || text.includes('pause_circle');
                })
                .map((el) => {
                  const rect = el.getBoundingClientRect();
                  return {el, rect, area: rect.width * rect.height};
                })
                .filter((candidate) => candidate.area > 12000);
              cards.sort((left, right) =>
                right.area - left.area ||
                right.rect.top - left.rect.top ||
                right.rect.right - left.rect.right
              );
              const card = cards[0];
              if (!card) return false;
              return clickElement(card.el);
            })()
            """,
                timeout=5.0,
            )
        except Exception:
            selected = False
    if not selected:
        return False
    time.sleep(FLOW_STEP_DELAY_SECONDS)
    if not _click_action_row_by_text(client, ["Tải xuống", "Download"], timeout=2.0) and not _click_text(
        client,
        ["Tải xuống", "Download"],
        timeout=2.0,
    ):
        try:
            opened = client.evaluate(
                """
                (() => {
                  const norm = (value) => String(value || '').toLowerCase().normalize('NFD').replace(/[\\u0300-\\u036f]/g, '').replace(/\\s+/g, ' ').trim();
                  const visible = (el) => {
                    const style = window.getComputedStyle(el);
                    const rect = el.getBoundingClientRect();
                    return style.display !== 'none' && style.visibility !== 'hidden' && style.pointerEvents !== 'none' && rect.width > 2 && rect.height > 2;
                  };
                  const textOf = (el) => norm([el.innerText, el.textContent, el.getAttribute('aria-label'), el.getAttribute('title')].filter(Boolean).join(' '));
                  const clickElement = (el) => {
                    el.scrollIntoView({block: 'center', inline: 'center'});
                    const rect = el.getBoundingClientRect();
                    const init = {
                      bubbles: true,
                      cancelable: true,
                      view: window,
                      clientX: rect.left + rect.width / 2,
                      clientY: rect.top + rect.height / 2
                    };
                    el.dispatchEvent(new MouseEvent('mouseover', init));
                    el.dispatchEvent(new MouseEvent('mousemove', init));
                    el.dispatchEvent(new MouseEvent('mousedown', init));
                    el.dispatchEvent(new MouseEvent('mouseup', init));
                    el.dispatchEvent(new MouseEvent('click', init));
                    el.click?.();
                    return true;
                  };
                  const cards = Array.from(document.querySelectorAll('[role="button"],section,div'))
                    .filter((el) => {
                      if (!visible(el)) return false;
                      const rect = el.getBoundingClientRect();
                      if (rect.width < 100 || rect.height < 100 || rect.top < 60) return false;
                      const text = textOf(el);
                      return el.querySelector('video,img,canvas') || text.includes('play_circle') || text.includes('pause_circle');
                    })
                    .map((el) => {
                      const rect = el.getBoundingClientRect();
                      const moreButtons = Array.from(el.querySelectorAll('button,[role="button"]'))
                        .filter((button) => visible(button) && /(^| )(more_vert|khac|more options|more)( |$)/.test(textOf(button)))
                        .map((button) => ({button, buttonRect: button.getBoundingClientRect()}))
                        .filter(({buttonRect}) => buttonRect.left >= rect.left && buttonRect.right <= rect.right + 8 && buttonRect.top >= rect.top && buttonRect.bottom <= rect.bottom + 8);
                      return {el, rect, moreButtons, area: rect.width * rect.height};
                    })
                    .filter((candidate) => candidate.moreButtons.length > 0);
                  cards.sort((left, right) => right.area - left.area || right.rect.top - left.rect.top);
                  const card = cards[0];
                  if (!card) return false;
                  card.moreButtons.sort((left, right) => right.buttonRect.right - left.buttonRect.right || left.buttonRect.top - right.buttonRect.top);
                  return clickElement(card.moreButtons[0].button);
                })()
                """,
                timeout=5.0,
            )
        except Exception:
            opened = False
        if not opened and _click_generated_media_target(client, prefer_more_button=True):
            opened = True
        if not opened:
            return False
        time.sleep(FLOW_STEP_DELAY_SECONDS)
        if not (
            _click_action_row_by_text(client, ["Tải xuống", "Download"], timeout=5.0)
            or _click_text(client, ["Tải xuống", "Download"], timeout=5.0)
        ):
            return False
    time.sleep(FLOW_STEP_DELAY_SECONDS)
    quality_clicked = (
        _click_action_row_by_text(
            client,
            [
                "720p Kích thước gốc",
                "720p Kích thước gốc",
                "Original size",
                "Original",
                "720p",
            ],
            timeout=5.0,
        )
        or _click_text(
            client,
            [
                "720p Kích thước gốc",
                "720p Kích thước gốc",
                "Original size",
                "Original",
                "720p",
            ],
            timeout=5.0,
        )
    )
    if quality_clicked:
        return True
    return True

def _generated_media_urls(client: chrome_cdp.CDPClient) -> set[str]:
    try:
        result = client.evaluate(
            """
            (() => {
              const normalizeMediaUrl = (raw) => {
                if (!raw || !String(raw).includes('media.getMediaUrlRedirect')) return null;
                const url = new URL(raw, location.origin);
                url.searchParams.delete('mediaUrlType');
                return url.href;
              };
              const urls = [
                ...Array.from(document.querySelectorAll('video[src], video source[src]')).map((el) => {
                  const raw = el.matches('source') ? el.getAttribute('src') : (el.getAttribute('src') || el.querySelector('source[src]')?.getAttribute('src'));
                  return normalizeMediaUrl(raw);
                }),
                ...Array.from(document.querySelectorAll('img[src*="media.getMediaUrlRedirect"]')).map((el) => normalizeMediaUrl(el.getAttribute('src'))),
              ].filter(Boolean);
              return Array.from(new Set(urls));
            })()
            """,
            timeout=5.0,
        )
    except Exception:
        return set()
    if not isinstance(result, list):
        return set()
    return {str(url) for url in result if str(url or "").strip()}

def _generated_media_download_info(client: chrome_cdp.CDPClient, *, baseline_media_urls: set[str] | None = None) -> dict[str, Any] | None:
    baseline_json = json.dumps(sorted(baseline_media_urls or set()))
    script = """
            (async () => {
              const baseline = new Set(__BASELINE_JSON__);
              const visible = (el) => {
                const style = window.getComputedStyle(el);
                const rect = el.getBoundingClientRect();
                return style.display !== 'none' &&
                  style.visibility !== 'hidden' &&
                  rect.width > 80 &&
                  rect.height > 80 &&
                  rect.top >= 60;
              };
              const mediaUrlFromThumbnail = (raw) => {
                const url = new URL(raw, location.origin);
                url.searchParams.delete('mediaUrlType');
                return url.href;
              };
              const visibleImages = Array.from(document.querySelectorAll('img[src*="media.getMediaUrlRedirect"]'))
                .filter((el) => visible(el))
                .map((el) => {
                  const rect = el.getBoundingClientRect();
                  return {
                    url: mediaUrlFromThumbnail(el.getAttribute('src') || ''),
                    area: rect.width * rect.height,
                    top: rect.top,
                    left: rect.left
                  };
                });
              const videoUrls = Array.from(document.querySelectorAll('video[src], video source[src]'))
                .map((el) => {
                  const raw = el.matches('source') ? el.getAttribute('src') : (el.getAttribute('src') || el.querySelector('source[src]')?.getAttribute('src'));
                  if (!raw || !raw.includes('media.getMediaUrlRedirect')) return null;
                  const media = el.closest('video') || el;
                  const rect = media.getBoundingClientRect();
                  return {
                    url: new URL(raw, location.origin).href,
                    area: visible(media) ? rect.width * rect.height : 1,
                    top: rect.top || Number.MAX_SAFE_INTEGER,
                    left: rect.left || Number.MAX_SAFE_INTEGER
                  };
                })
                .filter(Boolean);
              const candidates = [...visibleImages, ...videoUrls]
                .filter((candidate) => !baseline.has(candidate.url))
                .sort((a, b) => b.area - a.area || a.top - b.top || a.left - b.left);
              const src = candidates[0]?.url || null;
              if (!src) return null;
              try {
                const response = await fetch(src, {method: 'GET', redirect: 'follow'});
                return {
                  ok: response.ok,
                  status: response.status,
                  sourceUrl: src,
                  downloadUrl: response.url || src,
                  contentType: response.headers.get('content-type') || '',
                  contentLength: response.headers.get('content-length') || '',
                };
              } catch (error) {
                return {ok: false, sourceUrl: src, error: String(error && error.message || error)};
              }
            })()
            """.replace("__BASELINE_JSON__", baseline_json)
    try:
        result = client.evaluate(
            script,
            await_promise=True,
            timeout=30.0,
        )
    except Exception:
        return None
    return result if isinstance(result, dict) else None

def _suffix_from_download_info(info: dict[str, Any]) -> str:
    content_type = str(info.get("contentType") or "").split(";", 1)[0].strip().lower()
    suffix = mimetypes.guess_extension(content_type) if content_type else None
    if suffix == ".mp4v":
        suffix = ".mp4"
    if suffix and suffix.lower() in SUPPORTED_VIDEO_SUFFIXES:
        return suffix.lower()
    url = str(info.get("downloadUrl") or info.get("sourceUrl") or "")
    guessed = Path(url.split("?", 1)[0]).suffix.lower()
    return guessed if guessed in SUPPORTED_VIDEO_SUFFIXES else ".mp4"

def _download_generated_media_direct(
    client: chrome_cdp.CDPClient,
    context: DownloadContext,
    *,
    baseline_media_urls: set[str] | None = None,
) -> bool:
    info = _generated_media_download_info(client, baseline_media_urls=baseline_media_urls)
    if not info or not info.get("ok") or not info.get("downloadUrl"):
        return False
    suffix = _suffix_from_download_info(info)
    context.expected_download_dir.mkdir(parents=True, exist_ok=True)
    # Keep this filename short because the per-item download directory already
    # contains project/job/shot/item ids and can approach Windows MAX_PATH.
    target = context.expected_download_dir / f"clip{suffix}"
    temp_target = target.with_name(f"{target.name}.download")
    request = Request(
        str(info["downloadUrl"]),
        headers={
            "User-Agent": "Mozilla/5.0 Voicebox AI Video",
            "Accept": "video/mp4,video/*;q=0.9,*/*;q=0.8",
        },
    )
    try:
        with urlopen(request, timeout=120) as response, temp_target.open("wb") as output:
            while True:
                chunk = response.read(1024 * 1024)
                if not chunk:
                    break
                output.write(chunk)
        if temp_target.stat().st_size <= 0:
            temp_target.unlink(missing_ok=True)
            return False
        temp_target.replace(target)
        return True
    except Exception as exc:
        try:
            temp_target.unlink(missing_ok=True)
        except Exception:
            pass
        raise VeoChromeError(
            "Flow đã tạo video nhưng Voicebox không tải trực tiếp được media URL.",
            error_code="VIDEO_DOWNLOAD_DIRECT_FAILED",
            details={
                "download_correlation_id": context.download_correlation_id,
                "download_url_hash": chrome_cdp.sha256_short(str(info.get("downloadUrl") or ""), length=24),
            },
        ) from exc

def _click_download_when_ready(
    client: chrome_cdp.CDPClient,
    *,
    timeout_seconds: int,
    baseline_media_count: int | None = None,
    credit_approval_policy: str | None = None,
    max_credit_per_job: int | None = None,
    credit_spent_estimate: int = 0,
    on_status: StatusCallback | None = None,
    download_context: DownloadContext | None = None,
    baseline_media_urls: set[str] | None = None,
) -> int | None:
    deadline = time.monotonic() + timeout_seconds
    approved_credit_cost: int | None = None
    credit_approved = False
    saw_generation_pending = False
    generation_retry_clicked = False
    generation_retry_grace_until = 0.0
    while time.monotonic() < deadline:
        snapshot = video_provider_sessions._read_page_snapshot(client, text_limit=5000)
        if video_provider_sessions._looks_like_flow_application_error(snapshot):
            raise VeoChromeError(
                "Flow bị lỗi giao diện sau khi gửi prompt. Voicebox đã dừng chờ download để tránh treo job.",
                error_code="VIDEO_PROVIDER_FLOW_APP_ERROR",
                details={"url_hash": chrome_cdp.sha256_short(snapshot.get("url", ""), length=24)},
            )
        text = _page_text_for_generation_wait(client, snapshot)
        is_generation_pending = _looks_like_flow_generation_pending(text)
        if any(marker in text for marker in ("nguoi noi tieng", "người nổi tiếng", "celebrity", "public figure")):
            raise VeoChromeError(
                "Veo chặn prompt vì có thể liên quan người nổi tiếng/public figure. Hãy dùng mô tả cổ động viên hoặc nhân vật hư cấu, không dùng tên/biểu tượng người nổi tiếng.",
                error_code="VIDEO_PROVIDER_POLICY_PUBLIC_FIGURE",
            )
        if any(marker in text for marker in ("quota", "billing", "policy", "vi pham", "vi phạm")):
            raise VeoChromeError("Veo báo lỗi quota/billing/policy.", error_code="VIDEO_PROVIDER_QUOTA_OR_POLICY")
        if (
            not credit_approved
            and credit_approval_policy is not None
            and any(marker in text for marker in ("tin dung", "credit", "credits"))
        ):
            cost = _approve_credit_from_text(
                client,
                text,
                credit_approval_policy=credit_approval_policy,
                max_credit_per_job=max_credit_per_job,
                credit_spent_estimate=credit_spent_estimate,
                on_status=on_status,
            )
            credit_approved = True
            if cost is not None:
                approved_credit_cost = cost
            time.sleep(FLOW_STEP_DELAY_SECONDS)
            continue
        if _looks_like_flow_generation_error(text):
            if is_generation_pending:
                saw_generation_pending = True
                time.sleep(FLOW_STEP_DELAY_SECONDS)
                continue
            if not generation_retry_clicked and _click_generation_retry(client):
                generation_retry_clicked = True
                generation_retry_grace_until = time.monotonic() + FLOW_GENERATION_RETRY_GRACE_SECONDS
                saw_generation_pending = False
                time.sleep(FLOW_STEP_DELAY_SECONDS)
                continue
            if generation_retry_clicked and time.monotonic() < generation_retry_grace_until:
                time.sleep(FLOW_STEP_DELAY_SECONDS)
                continue
            raise VeoChromeError(
                "Flow báo lỗi khi tạo video và yêu cầu thử lại. Voicebox đã thử bấm Thử lại một lần nhưng chưa tạo được clip.",
                error_code="VIDEO_PROVIDER_GENERATION_FAILED",
            )
        if any(marker in text for marker in ("tai xuong", "tải xuống", "download")) and _click_text(
            client,
            ["Tải xuống", "Download"],
            timeout=5.0,
        ):
            return approved_credit_cost
        media_count = _generated_media_count(client)
        has_new_media = baseline_media_count is None or media_count > baseline_media_count
        has_media_preview = _has_generated_media_preview(client)
        has_new_media_url = baseline_media_urls is None or bool(_generated_media_urls(client) - baseline_media_urls)
        can_download_media = has_media_preview and (has_new_media if baseline_media_urls is None else has_new_media_url)
        if can_download_media and download_context is not None and _download_generated_media_direct(
            client,
            download_context,
            baseline_media_urls=baseline_media_urls,
        ):
            return approved_credit_cost
        if can_download_media and _click_generated_media_download(client):
            return approved_credit_cost
        if is_generation_pending:
            saw_generation_pending = True
            time.sleep(FLOW_STEP_DELAY_SECONDS)
            continue
        can_use_stable_media_count = saw_generation_pending and baseline_media_count is not None and media_count >= baseline_media_count
        can_download_stable_media = has_media_preview and (can_use_stable_media_count if baseline_media_urls is None else has_new_media_url)
        if can_download_stable_media and download_context is not None and _download_generated_media_direct(
            client,
            download_context,
            baseline_media_urls=baseline_media_urls,
        ):
            return approved_credit_cost
        if can_download_stable_media and _click_generated_media_download(client):
            return approved_credit_cost
        if has_media_preview and _click_action_row_by_text(client, ["Phê duyệt", "Approve"]):
            time.sleep(FLOW_STEP_DELAY_SECONDS)
            continue
        time.sleep(FLOW_STEP_DELAY_SECONDS)
    raise VeoChromeError(
        "Veo chưa hiển thị nút tải clip trong thời gian chờ.",
        error_code="VIDEO_PROVIDER_DOWNLOAD_UNAVAILABLE",
    )

def submit_prompt_and_download(
    *,
    prompt: str,
    requested_duration_seconds: float | None,
    download_context: DownloadContext,
    credit_approval_policy: str,
    provider_project_url: str | None = None,
    max_credit_per_job: int | None = None,
    credit_spent_estimate: int = 0,
    generation_timeout_seconds: int = DEFAULT_GENERATION_TIMEOUT_SECONDS,
    on_status: StatusCallback | None = None,
    on_provider_project: Callable[[str, str | None], None] | None = None,
) -> ProviderClipResult:
    def emit(status: str, message: str | None = None) -> None:
        if on_status:
            on_status(status, message)

    if not prompt.strip():
        raise VeoChromeError("Prompt video rỗng, không thể gửi sang Veo.", error_code="VIDEO_PROVIDER_PROMPT_EMPTY")
    emit("opening_provider", "Đang mở Chrome/Veo bằng profile riêng.")
    target_url = provider_project_url or video_provider_sessions.flow_url()
    runtime = video_provider_sessions.launch_chrome(
        provider=video_provider_sessions.DEFAULT_PROVIDER,
        url=target_url,
        download_dir=download_context.expected_download_dir,
    )
    video_provider_sessions.close_flow_project_tabs(runtime.port)
    try:
        with chrome_cdp.CDPClient(chrome_cdp.browser_websocket_url(runtime.port)) as browser_client:
            _configure_download_behavior(browser_client, download_context.expected_download_dir)
    except Exception:
        pass
    target = chrome_cdp.open_target(runtime.port, target_url)
    provider_duration: float | None = None
    credit_cost: int | None = None
    current_project_url: str | None = None
    project_ref_hash: str | None = None
    with chrome_cdp.CDPClient(target.web_socket_debugger_url) as client:
        _configure_download_behavior(client, download_context.expected_download_dir)
        if provider_project_url:
            _open_existing_flow_project(client, provider_project_url)
        else:
            client.navigate(video_provider_sessions.flow_url(), timeout=20.0)
            time.sleep(FLOW_STEP_DELAY_SECONDS)
            try:
                snapshot = video_provider_sessions._read_page_snapshot(client, text_limit=5000)
                if video_provider_sessions._recover_flow_application_error(client, snapshot):
                    time.sleep(FLOW_STEP_DELAY_SECONDS)
            except Exception:
                pass
            _open_new_flow_project(client)
        current_project_url = str(client.evaluate("location.href", timeout=5.0) or "")
        project_ref_hash = chrome_cdp.sha256_short(current_project_url, length=24)
        if on_provider_project and current_project_url:
            on_provider_project(current_project_url, project_ref_hash)
        _configure_download_behavior(client, download_context.expected_download_dir)
        baseline_media_count = _generated_media_count(client)
        baseline_media_urls = _generated_media_urls(client)
        time.sleep(FLOW_STEP_DELAY_SECONDS)
        emit("submitting_prompt", "Đang gửi prompt vào agent chat của Flow.")
        _submit_prompt(client, prompt)
        time.sleep(FLOW_AFTER_NEW_PROJECT_CLICK_SECONDS)
        provider_duration = _resolve_flow_agent_followups(
            client,
            prompt=prompt,
            requested_duration_seconds=requested_duration_seconds,
            on_status=on_status,
        )
        time.sleep(FLOW_STEP_DELAY_SECONDS)
        credit_cost = _approve_credit_if_needed(
            client,
            credit_approval_policy=credit_approval_policy,
            max_credit_per_job=max_credit_per_job,
            credit_spent_estimate=credit_spent_estimate,
            on_status=on_status,
        )
        emit("waiting_generation", "Đang chờ Veo tạo clip.")
        _configure_download_behavior(client, download_context.expected_download_dir)
        delayed_credit_cost = _click_download_when_ready(
            client,
            timeout_seconds=generation_timeout_seconds,
            baseline_media_count=baseline_media_count,
            credit_approval_policy=credit_approval_policy,
            max_credit_per_job=max_credit_per_job,
            credit_spent_estimate=credit_spent_estimate,
            on_status=on_status,
            download_context=download_context,
            baseline_media_urls=baseline_media_urls,
        )
        if delayed_credit_cost is not None:
            credit_cost = delayed_credit_cost
    emit("downloading", "Đang chờ file tải về đúng thư mục item.")
    path = wait_for_downloaded_video(download_context)
    filename = video_storage.sanitize_download_filename(path.name, fallback=f"veo-{download_context.shot_order:03d}{path.suffix}")
    guessed_type, _ = mimetypes.guess_type(filename)
    return ProviderClipResult(
        downloaded_file_path=path,
        original_filename=filename,
        download_correlation_id=download_context.download_correlation_id,
        provider_project_url=current_project_url,
        provider_project_ref_hash=project_ref_hash,
        provider_duration_seconds=provider_duration,
        credit_cost=credit_cost,
        metadata={
            "download_context": {
                "project_id": download_context.project_id,
                "job_id": download_context.job_id,
                "item_id": download_context.item_id,
                "shot_id": download_context.shot_id,
                "shot_order": download_context.shot_order,
                "prompt_id": download_context.prompt_id,
                "download_correlation_id": download_context.download_correlation_id,
            },
            "mime_type": guessed_type,
        },
    )
