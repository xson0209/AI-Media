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


__all__ = ["ResearchCLIError", "ResearchCLIResult", "run_research"]
