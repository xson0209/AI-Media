"""Read-only CLI adapter for document/source research.

This adapter is intentionally separate from AI Video planning. It loads the
user's local research-cli settings without mutating them and runs with only
web/document tools enabled, so a research request cannot edit the repository.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import copy
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .. import config

MAX_ERROR_CHARS = 2000


@dataclass(frozen=True)
class ResearchCLIResult:
    output: str
    metadata: dict[str, Any]


class ResearchCLIError(RuntimeError):
    def __init__(self, message: str, *, error_code: str = "RESEARCH_CLI_ERROR", metadata: dict[str, Any] | None = None):
        super().__init__(message)
        self.error_code = error_code
        self.metadata = metadata or {}


def check_provider(*, check_exec: bool = False, timeout_seconds: int = 30, model: str | None = None) -> dict[str, Any]:
    """Return a safe readiness payload for the configured Claude CLI."""
    cli_path = _cli_path()
    settings_path = _settings_path()
    selected_model = model or "sonnet"
    payload: dict[str, Any] = {
        "provider": "claude-cli",
        "ready": bool(cli_path and settings_path),
        "message": "Claude CLI sẵn sàng cho nghiên cứu nội dung." if cli_path and settings_path else "Chưa cấu hình Claude CLI hoặc file settings.",
        "codex_path": cli_path,
        "requested_model": selected_model,
        "effective_model": selected_model,
        "model_source": "content_settings",
        "model_verified": False,
    }
    if not payload["ready"] or not check_exec:
        payload["error_code"] = None if payload["ready"] else "CLAUDE_CLI_NOT_READY"
        return payload
    try:
        result = run_research(
            "Trả lời đúng một chữ: OK",
            timeout_seconds=min(timeout_seconds, 120),
            tools="",
            model=selected_model,
        )
        payload.update({"ready": bool(result.output), "model_verified": bool(result.output), "request_id": None})
        payload["message"] = "Claude CLI đã phản hồi với cấu hình nội dung." if result.output else "Claude CLI chạy nhưng không trả về text."
        if not result.output:
            payload["error_code"] = "CLAUDE_EMPTY_OUTPUT"
    except ResearchCLIError as exc:
        payload.update({"ready": False, "message": str(exc), "error_code": exc.error_code})
    return payload


def _settings_path() -> Path | None:
    configured = os.environ.get("VOICEBOX_RESEARCH_CLI_SETTINGS")
    path = Path(configured).expanduser() if configured else Path.home() / ".claude" / "settings.json"
    return path.resolve() if path.is_file() else None


def _cli_path() -> str | None:
    configured = os.environ.get("VOICEBOX_RESEARCH_CLI_PATH")
    if configured:
        path = Path(configured).expanduser()
        return str(path.resolve()) if path.is_file() else None
    resolved = shutil.which("claude")
    if resolved:
        return resolved
    windows_fallback = Path.home() / ".local" / "bin" / "claude.exe"
    return str(windows_fallback.resolve()) if windows_fallback.is_file() else None


def _safe_metadata(envelope: dict[str, Any]) -> dict[str, Any]:
    allowed = {
        "model",
        "total_cost_usd",
        "duration_ms",
        "duration_api_ms",
        "num_turns",
        "usage",
        "is_error",
    }
    metadata: dict[str, Any] = {key: envelope[key] for key in allowed if key in envelope}
    usage = metadata.get("usage")
    if isinstance(usage, dict):
        metadata["usage"] = {
            str(key): value
            for key, value in usage.items()
            if isinstance(value, (str, int, float, bool)) or value is None
        }
    return metadata


def _error_text(value: str | None) -> str:
    text = (value or "").strip()
    return text[-MAX_ERROR_CHARS:]


def run_research(
    prompt: str,
    *,
    timeout_seconds: int = 180,
    tools: str | None = None,
    effort: str | None = None,
    max_budget_usd: float | None = None,
    model: str | None = None,
) -> ResearchCLIResult:
    """Run the local research CLI in read-only mode using the user's settings."""
    cli_path = _cli_path()
    if not cli_path:
        raise ResearchCLIError("Chưa tìm thấy CLI nghiên cứu tài liệu.", error_code="RESEARCH_CLI_NOT_FOUND")
    settings_path = _settings_path()
    if not settings_path:
        raise ResearchCLIError("Chưa tìm thấy file cấu hình nghiên cứu trong thư mục người dùng.", error_code="RESEARCH_SETTINGS_NOT_FOUND")

    selected_tools = os.environ.get("VOICEBOX_RESEARCH_CLI_TOOLS", "WebSearch,WebFetch") if tools is None else tools
    command = [
        cli_path,
        "-p",
        "--output-format",
        "json",
        "--no-session-persistence",
        "--permission-mode",
        "plan",
        "--tools",
        selected_tools,
        "--settings",
        str(settings_path),
    ]
    if effort in {"low", "medium", "high", "xhigh", "max"}:
        command.extend(["--effort", effort])
    if model:
        command.extend(["--model", model.strip()])
    if max_budget_usd is not None:
        command.extend(["--max-budget-usd", str(max(0.01, min(float(max_budget_usd), 5.0)))])
    command.append("--")
    try:
        completed = subprocess.run(
            command,
            input=prompt,
            cwd=str(config.get_data_dir()),
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=max(5, min(timeout_seconds, 600)),
            check=False,
        )
    except subprocess.TimeoutExpired as exc:
        raise ResearchCLIError("Nghiên cứu tài liệu quá thời gian chờ.", error_code="RESEARCH_CLI_TIMEOUT") from exc
    except OSError as exc:
        raise ResearchCLIError("Không khởi chạy được CLI nghiên cứu tài liệu.", error_code="RESEARCH_CLI_EXEC_FAILED") from exc

    if completed.returncode != 0:
        detail = _error_text(completed.stderr or completed.stdout)
        raise ResearchCLIError(
            f"CLI nghiên cứu tài liệu trả về lỗi: {detail or 'không có chi tiết'}",
            error_code="RESEARCH_CLI_NONZERO",
        )

    raw = (completed.stdout or "").strip()
    try:
        envelope = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise ResearchCLIError("CLI nghiên cứu tài liệu không trả về JSON hợp lệ.", error_code="RESEARCH_CLI_INVALID_OUTPUT") from exc
    if not isinstance(envelope, dict):
        raise ResearchCLIError("CLI nghiên cứu tài liệu trả về dữ liệu không hợp lệ.", error_code="RESEARCH_CLI_INVALID_OUTPUT")

    result = envelope.get("result")
    if isinstance(result, str):
        output = result.strip()
    elif isinstance(result, dict):
        output = json.dumps(result, ensure_ascii=False)
    else:
        output = json.dumps(envelope, ensure_ascii=False)
    if not output:
        raise ResearchCLIError("CLI nghiên cứu tài liệu không trả về nội dung.", error_code="RESEARCH_CLI_EMPTY_OUTPUT")
    return ResearchCLIResult(output=output, metadata=_safe_metadata(envelope))


def run_content(
    prompt: str,
    settings: Any,
    *,
    timeout_seconds: int,
    tools: str | None = None,
    effort: str | None = None,
) -> ResearchCLIResult | Any:
    """Run the provider selected in shared Content settings.

    Research, creative generation, chat, and scoring all use this adapter so
    one Settings choice controls every content flow. The existing Claude CLI
    adapter remains read-only; Codex uses the established planning executor.
    """

    provider = str(getattr(settings, "content_provider", "codex") or "codex").strip().lower()
    default_models = {"codex": "gpt-5.6-sol", "claude": "sonnet"}
    model = str(getattr(settings, "content_model", "") or "").strip() or default_models.get(provider)
    if provider == "claude":
        result = run_research(
            prompt,
            timeout_seconds=timeout_seconds,
            tools=tools,
            effort=effort,
            model=model,
        )
        result.metadata.setdefault("provider", "claude")
        if model:
            result.metadata.setdefault("configured_model", model)
        return result

    # Import lazily to keep this low-level CLI module independent at import
    # time and avoid a circular dependency during backend startup.
    from . import ai_planning

    codex_settings = copy.copy(settings)
    if model:
        # ``content_model`` is the shared content setting; the legacy Codex
        # planning field remains untouched in the persisted settings row.
        codex_settings.model = model
    result = ai_planning.run_codex_exec(
        codex_settings,
        prompt,
        timeout_seconds=timeout_seconds,
        return_metadata=True,
    )
    if isinstance(result, ai_planning.CodexExecResult):
        result.metadata.setdefault("provider", "codex")
        if model:
            result.metadata.setdefault("configured_model", model)
        return result
    return result


__all__ = ["ResearchCLIError", "ResearchCLIResult", "run_content", "run_research"]
