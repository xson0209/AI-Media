"""AI planning provider integration for AI Video Assistant."""

from __future__ import annotations

import json
import logging
import re
import shutil
import subprocess
import tempfile
import time
import uuid
from pathlib import Path
from typing import Any

from .. import models
from ..database import AIPlanningSettings as DBAIPlanningSettings
from . import video_errors

logger = logging.getLogger(__name__)

CODEX_PROVIDER = "codex-cli"
_MAX_LOG_CHARS = 4000
_MAX_PROVIDER_DETAIL_CHARS = 900
_STATUS_PATTERN = re.compile(r"(?i)(?:unexpected\s+)?status\s+(\d{3})")
_SECRET_PATTERN = re.compile(
    r"(?i)(api[_-]?key|secret|token|bearer|authorization|password)\s*[:=]\s*([^\s,;]+)"
)
_BEARER_PATTERN = re.compile(r"(?i)bearer\s+[^\s,;]+")

class AIPlanningError(RuntimeError):
    """Raised when an AI planning provider cannot complete a request."""

    def __init__(
        self,
        message: str,
        *,
        error_code: str = "AI_PLANNING_ERROR",
        provider_detail: str | None = None,
    ):
        super().__init__(message)
        self.error_code = error_code
        self.provider_detail = provider_detail

def _request_id() -> str:
    return str(uuid.uuid4())

def _trim(value: str | None) -> str | None:
    if value is None:
        return None
    return value[:_MAX_LOG_CHARS]

def _redact_provider_text(value: str | None) -> str | None:
    if not value:
        return None
    text = _SECRET_PATTERN.sub(lambda match: f"{match.group(1)}=[redacted]", value)
    text = _BEARER_PATTERN.sub("bearer [redacted]", text)
    return text[:_MAX_PROVIDER_DETAIL_CHARS]

def _provider_status_code(value: str | None) -> int | None:
    if not value:
        return None
    match = _STATUS_PATTERN.search(value)
    if not match:
        return None
    try:
        return int(match.group(1))
    except ValueError:
        return None

def _provider_failure_text(result: subprocess.CompletedProcess[str]) -> str:
    return "\n".join(part for part in (result.stderr, result.stdout) if part).strip()

def _nonzero_error_code(provider_text: str | None) -> str:
    status_code = _provider_status_code(provider_text)
    if status_code in {400, 401, 403, 404}:
        return "CODEX_PROVIDER_REJECTED"
    return "CODEX_EXEC_NONZERO"

def _nonzero_error_message(provider_text: str | None) -> str:
    status_code = _provider_status_code(provider_text)
    detail = _redact_provider_text(provider_text)
    if status_code == 400:
        return (
            "Codex provider từ chối request (HTTP 400). Thường là model/provider không hỗ trợ "
            "structured output hoặc schema quá phức tạp cho request này."
            + (f" Chi tiết: {detail}" if detail else "")
        )
    if status_code in {401, 403}:
        return (
            f"Codex provider từ chối quyền truy cập model/API (HTTP {status_code}). "
            "Hãy đổi model trong Settings AI planning hoặc kiểm tra API key."
            + (f" Chi tiết: {detail}" if detail else "")
        )
    if status_code == 404:
        return (
            "Codex provider không tìm thấy model hoặc endpoint cho request này (HTTP 404). "
            "Hãy đổi model trong Settings AI planning."
            + (f" Chi tiết: {detail}" if detail else "")
        )
    return "Codex CLI trả lỗi khi tạo nội dung." + (f" Chi tiết: {detail}" if detail else "")

def _should_retry_without_output_schema(provider_text: str | None) -> bool:
    if not provider_text:
        return False
    lowered = provider_text.lower()
    status_code = _provider_status_code(provider_text)
    if status_code == 400:
        return True
    return "response_format" in lowered or "output_schema" in lowered or "json schema" in lowered

def _looks_like_auth_failure(provider_text: str | None) -> bool:
    if not provider_text:
        return False
    lowered = provider_text.lower()
    return any(
        marker in lowered
        for marker in (
            "not logged in",
            "login",
            "log in",
            "auth",
            "authentication",
            "unauthorized",
            "invalid api key",
        )
    )

def _login_status_not_logged_in(result: subprocess.CompletedProcess[str]) -> bool:
    if result.returncode == 0:
        return False
    return _looks_like_auth_failure(_provider_failure_text(result))

def _prompt_with_inline_schema(prompt: str, output_schema: dict[str, Any]) -> str:
    schema_text = json.dumps(output_schema, ensure_ascii=False, separators=(",", ":"))
    return (
        f"{prompt}\n\n"
        "Nếu provider không hỗ trợ structured output kỹ thuật, vẫn phải trả về đúng một JSON object "
        "khớp JSON Schema dưới đây. Không thêm markdown, không thêm giải thích ngoài JSON.\n"
        f"JSON Schema:\n{schema_text}"
    )

def _process_text(value: str | bytes | None) -> str | None:
    if value is None:
        return None
    if isinstance(value, bytes):
        return value.decode("utf-8", errors="replace")
    return value

def _output_file_details(output_path: Path) -> dict[str, Any]:
    if not output_path.exists():
        return {"output_file_exists": False}
    try:
        content = output_path.read_text(encoding="utf-8")
    except OSError as exc:
        return {
            "output_file_exists": True,
            "output_file_read_error": exc.__class__.__name__,
        }
    return {
        "output_file_exists": True,
        "output_file_chars": len(content),
        "output_file_tail": _trim(content[-_MAX_LOG_CHARS:]),
    }

def resolve_codex_path(settings: DBAIPlanningSettings) -> str | None:
    if settings.codex_path:
        return settings.codex_path
    return shutil.which("codex")

def _run_command(
    command: list[str],
    *,
    timeout_seconds: int,
    cwd: str | Path | None = None,
    input_text: str | None = None,
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        command,
        cwd=str(cwd) if cwd else None,
        input=input_text,
        text=True,
        encoding="utf-8",
        errors="replace",
        capture_output=True,
        timeout=timeout_seconds,
        check=False,
    )

def check_provider(
    settings: DBAIPlanningSettings,
    *,
    check_exec: bool = False,
    cwd: str | Path | None = None,
) -> models.AIPlanningProviderCheckResponse:
    """Check whether the configured planning provider is ready."""
    request_id = _request_id()
    provider = settings.provider or CODEX_PROVIDER

    if provider != CODEX_PROVIDER:
        return models.AIPlanningProviderCheckResponse(
            ready=False,
            provider=provider,
            message="Provider AI planning này chưa được hỗ trợ trong bản hiện tại.",
            request_id=request_id,
            error_code="AI_PROVIDER_NOT_IMPLEMENTED",
        )

    codex_path = resolve_codex_path(settings)
    if not codex_path:
        return models.AIPlanningProviderCheckResponse(
            ready=False,
            provider=provider,
            message="Chưa tìm thấy Codex CLI. Hãy kiểm tra đường dẫn Codex trong Settings.",
            request_id=request_id,
            error_code="CODEX_CLI_NOT_FOUND",
        )

    if not Path(codex_path).exists() and shutil.which(codex_path) is None:
        return models.AIPlanningProviderCheckResponse(
            ready=False,
            provider=provider,
            codex_path=codex_path,
            message="Đường dẫn Codex CLI không tồn tại. Hãy cập nhật lại Settings.",
            request_id=request_id,
            error_code="CODEX_PATH_INVALID",
        )

    timeout = max(5, min(settings.timeout_seconds or 60, 600))
    try:
        version_result = _run_command([codex_path, "--version"], timeout_seconds=min(timeout, 15), cwd=cwd)
        login_result = _run_command([codex_path, "login", "status"], timeout_seconds=min(timeout, 15), cwd=cwd)
    except subprocess.TimeoutExpired:
        logger.warning(
            "Codex CLI check timed out",
            extra={"request_id": request_id, "provider": provider, "codex_path": codex_path},
        )
        return models.AIPlanningProviderCheckResponse(
            ready=False,
            provider=provider,
            codex_path=codex_path,
            message="Kiểm tra Codex CLI bị timeout. Hãy thử lại hoặc tăng timeout trong Settings.",
            request_id=request_id,
            error_code="CODEX_CHECK_TIMEOUT",
        )
    except OSError:
        logger.exception(
            "Codex CLI check failed to start",
            extra={"request_id": request_id, "provider": provider, "codex_path": codex_path},
        )
        return models.AIPlanningProviderCheckResponse(
            ready=False,
            provider=provider,
            codex_path=codex_path,
            message="Không chạy được Codex CLI. Hãy kiểm tra lại quyền chạy và đường dẫn.",
            request_id=request_id,
            error_code="CODEX_CHECK_FAILED",
        )

    version = (version_result.stdout or version_result.stderr or "").strip() or None
    if version_result.returncode != 0:
        logger.warning(
            "Codex CLI version check failed: %s",
            _trim(version_result.stderr),
            extra={"request_id": request_id, "provider": provider, "codex_path": codex_path},
        )
        return models.AIPlanningProviderCheckResponse(
            ready=False,
            provider=provider,
            codex_path=codex_path,
            version=version,
            message="Codex CLI có trong máy nhưng không chạy được lệnh version.",
            request_id=request_id,
            error_code="CODEX_VERSION_FAILED",
        )

    should_check_exec = check_exec
    login_check_failed = login_result.returncode != 0
    login_status_not_logged_in = _login_status_not_logged_in(login_result)
    if login_check_failed:
        logger.warning(
            "Codex CLI login check failed: %s",
            _trim(login_result.stderr or login_result.stdout),
            extra={"request_id": request_id, "provider": provider, "codex_path": codex_path},
        )
        should_check_exec = True

    if should_check_exec:
        try:
            run_codex_exec(
                settings,
                "Trả lời đúng một chữ: OK",
                timeout_seconds=min(timeout, 30),
                cwd=cwd,
            )
        except AIPlanningError as exc:
            logger.warning(
                "Codex exec readiness failed: %s",
                exc,
                extra={"request_id": request_id, "provider": provider, "codex_path": codex_path},
            )
            if login_status_not_logged_in and exc.error_code == "CODEX_EXEC_TIMEOUT":
                message = "Codex CLI chưa đăng nhập hoặc phiên đăng nhập không hợp lệ."
                error_code = "CODEX_NOT_LOGGED_IN"
            elif login_check_failed and _looks_like_auth_failure(exc.provider_detail):
                message = "Codex CLI chưa đăng nhập hoặc phiên đăng nhập không hợp lệ."
                error_code = "CODEX_NOT_LOGGED_IN"
            elif login_check_failed:
                message = "Codex CLI login status không có phiên OpenAI và codex exec chưa chạy được."
                error_code = exc.error_code
            else:
                message = "Codex CLI đăng nhập rồi nhưng chưa chạy được codex exec."
                error_code = exc.error_code
            return models.AIPlanningProviderCheckResponse(
                ready=False,
                provider=provider,
                codex_path=codex_path,
                version=version,
                message=message,
                request_id=request_id,
                error_code=error_code,
            )

    return models.AIPlanningProviderCheckResponse(
        ready=True,
        provider=provider,
        codex_path=codex_path,
        version=version,
        message=(
            "Codex CLI đã sẵn sàng để tạo kịch bản và prompt."
            if not login_check_failed
            else "Codex CLI login status không có phiên OpenAI, nhưng codex exec chạy được với cấu hình hiện tại."
        ),
        request_id=request_id,
    )

def run_codex_exec(
    settings: DBAIPlanningSettings,
    prompt: str,
    *,
    output_schema: dict[str, Any] | None = None,
    timeout_seconds: int | None = None,
    cwd: str | Path | None = None,
) -> str:
    """Run `codex exec` and return the final assistant message."""
    provider = settings.provider or CODEX_PROVIDER
    request_id = video_errors.current_request_id()
    if provider != CODEX_PROVIDER:
        raise AIPlanningError(
            "Provider AI planning này chưa được hỗ trợ.",
            error_code="AI_PROVIDER_NOT_IMPLEMENTED",
        )

    codex_path = resolve_codex_path(settings)
    if not codex_path:
        video_errors.log_error(
            "Codex CLI path not resolved",
            provider=provider,
            model=settings.model,
            timeout_seconds=settings.timeout_seconds,
            step_name="codex_exec",
        )
        raise AIPlanningError("Chưa tìm thấy Codex CLI.", error_code="CODEX_CLI_NOT_FOUND")

    timeout = max(5, min(timeout_seconds or settings.timeout_seconds or 60, 600))
    with tempfile.TemporaryDirectory(prefix="voicebox-codex-") as tmpdir:
        output_path = Path(tmpdir) / "last-message.txt"
        schema_path: Path | None = None
        if output_schema:
            schema_path = Path(tmpdir) / "output-schema.json"
            schema_path.write_text(json.dumps(output_schema), encoding="utf-8")

        def build_command(*, use_output_schema: bool) -> list[str]:
            command = [
                codex_path,
                "exec",
                "--skip-git-repo-check",
                "--ephemeral",
                "--output-last-message",
                str(output_path),
            ]
            if settings.model:
                command.extend(["--model", settings.model])
            if use_output_schema and schema_path is not None:
                command.extend(["--output-schema", str(schema_path)])
            command.append("-")
            return command

        command = build_command(use_output_schema=bool(output_schema))
        schema_keys = []
        if isinstance(output_schema, dict):
            properties = output_schema.get("properties")
            if isinstance(properties, dict):
                schema_keys = sorted(str(key) for key in properties)[:20]

        started = time.perf_counter()
        try:
            video_errors.log_step(
                "Running Codex CLI planning",
                provider=provider,
                model=settings.model,
                command_path=codex_path,
                timeout_seconds=timeout,
                prompt_chars=len(prompt),
                schema_keys=",".join(schema_keys) if schema_keys else None,
                output_schema=bool(output_schema),
                step_name="codex_exec",
            )
            result = _run_command(command, timeout_seconds=timeout, cwd=cwd, input_text=prompt)
        except subprocess.TimeoutExpired as exc:
            elapsed_ms = round((time.perf_counter() - started) * 1000, 2)
            stdout = _process_text(exc.output)
            stderr = _process_text(exc.stderr)
            video_errors.log_error(
                "Codex CLI planning timed out",
                exc=exc,
                provider=provider,
                model=settings.model,
                command_path=codex_path,
                timeout_seconds=timeout,
                elapsed_ms=elapsed_ms,
                prompt_chars=len(prompt),
                stdout_chars=len(stdout or ""),
                stderr_chars=len(stderr or ""),
                stdout_tail=_trim(stdout[-_MAX_LOG_CHARS:] if stdout else None),
                stderr_tail=_trim(stderr[-_MAX_LOG_CHARS:] if stderr else None),
                **_output_file_details(output_path),
                request_id=request_id,
                step_name="codex_exec",
            )
            raise AIPlanningError(
                "AI xử lý quá lâu khi tạo nội dung. Hãy thử lại; nếu vẫn lỗi, hãy rút ngắn nguồn nội dung hoặc tăng timeout trong Settings.",
                error_code="CODEX_EXEC_TIMEOUT",
            ) from exc
        except OSError as exc:
            video_errors.log_error(
                "Codex CLI planning failed to start",
                exc=exc,
                provider=provider,
                model=settings.model,
                command_path=codex_path,
                timeout_seconds=timeout,
                elapsed_ms=round((time.perf_counter() - started) * 1000, 2),
                prompt_chars=len(prompt),
                request_id=request_id,
                step_name="codex_exec",
            )
            raise AIPlanningError(
                "Không chạy được Codex CLI.",
                error_code="CODEX_EXEC_FAILED",
            ) from exc

        if result.returncode != 0:
            elapsed_ms = round((time.perf_counter() - started) * 1000, 2)
            initial_provider_text = _provider_failure_text(result)
            initial_stderr = _redact_provider_text(initial_provider_text)
            if output_schema and _should_retry_without_output_schema(initial_provider_text):
                video_errors.log_step(
                    "Codex provider rejected output_schema; retrying with inline JSON schema",
                    provider=provider,
                    model=settings.model,
                    command_path=codex_path,
                    timeout_seconds=timeout,
                    elapsed_ms=elapsed_ms,
                    prompt_chars=len(prompt),
                    inline_prompt_chars=len(_prompt_with_inline_schema(prompt, output_schema)),
                    exit_code=result.returncode,
                    provider_status_code=_provider_status_code(initial_provider_text),
                    stderr=initial_stderr,
                    request_id=request_id,
                    step_name="codex_exec_schema_fallback",
                )
                try:
                    output_path.unlink(missing_ok=True)
                    fallback_prompt = _prompt_with_inline_schema(prompt, output_schema)
                    result = _run_command(
                        build_command(use_output_schema=False),
                        timeout_seconds=timeout,
                        cwd=cwd,
                        input_text=fallback_prompt,
                    )
                    if result.returncode == 0:
                        video_errors.log_step(
                            "Codex CLI planning completed with inline JSON schema fallback",
                            provider=provider,
                            model=settings.model,
                            command_path=codex_path,
                            timeout_seconds=timeout,
                            elapsed_ms=round((time.perf_counter() - started) * 1000, 2),
                            prompt_chars=len(prompt),
                            inline_prompt_chars=len(fallback_prompt),
                            stdout_chars=len(result.stdout or ""),
                            stderr_chars=len(result.stderr or ""),
                            output_file_exists=output_path.exists(),
                            request_id=request_id,
                            step_name="codex_exec_schema_fallback",
                        )
                    else:
                        fallback_provider_text = _provider_failure_text(result)
                        initial_provider_text = (
                            f"Structured output error:\n{initial_provider_text}\n\n"
                            f"Inline schema fallback error:\n{fallback_provider_text}"
                        ).strip()
                except subprocess.TimeoutExpired as exc:
                    stdout = _process_text(exc.output)
                    stderr = _process_text(exc.stderr)
                    video_errors.log_error(
                        "Codex CLI inline schema fallback timed out",
                        exc=exc,
                        provider=provider,
                        model=settings.model,
                        command_path=codex_path,
                        timeout_seconds=timeout,
                        elapsed_ms=round((time.perf_counter() - started) * 1000, 2),
                        prompt_chars=len(prompt),
                        stdout_chars=len(stdout or ""),
                        stderr_chars=len(stderr or ""),
                        stdout_tail=_trim(stdout[-_MAX_LOG_CHARS:] if stdout else None),
                        stderr_tail=_trim(stderr[-_MAX_LOG_CHARS:] if stderr else None),
                        **_output_file_details(output_path),
                        request_id=request_id,
                        step_name="codex_exec_schema_fallback",
                    )
                    raise AIPlanningError(
                        "AI xử lý quá lâu khi tạo nội dung bằng fallback schema text. Hãy thử lại; nếu vẫn lỗi, hãy rút ngắn nguồn nội dung hoặc tăng timeout trong Settings.",
                        error_code="CODEX_EXEC_TIMEOUT",
                    ) from exc
                except OSError as exc:
                    video_errors.log_error(
                        "Codex CLI inline schema fallback failed to start",
                        exc=exc,
                        provider=provider,
                        model=settings.model,
                        command_path=codex_path,
                        timeout_seconds=timeout,
                        elapsed_ms=round((time.perf_counter() - started) * 1000, 2),
                        prompt_chars=len(prompt),
                        request_id=request_id,
                        step_name="codex_exec_schema_fallback",
                    )
                    raise AIPlanningError(
                        "Không chạy được Codex CLI khi retry schema text.",
                        error_code="CODEX_EXEC_FAILED",
                    ) from exc

        if result.returncode != 0:
            elapsed_ms = round((time.perf_counter() - started) * 1000, 2)
            provider_text = initial_provider_text if "initial_provider_text" in locals() else _provider_failure_text(result)
            error_code = _nonzero_error_code(provider_text)
            provider_detail = _redact_provider_text(provider_text)
            logger.warning(
                "Codex exec failed: %s",
                _trim(provider_text),
                extra={
                    "request_id": request_id,
                    "provider": provider,
                    "model": settings.model,
                    "codex_path": codex_path,
                    "timeout_seconds": timeout,
                    "elapsed_ms": elapsed_ms,
                    "prompt_chars": len(prompt),
                    "exit_code": result.returncode,
                    "step_name": "codex_exec",
                },
            )
            video_errors.log_error(
                "Codex CLI returned non-zero exit code",
                provider=provider,
                model=settings.model,
                command_path=codex_path,
                timeout_seconds=timeout,
                elapsed_ms=elapsed_ms,
                prompt_chars=len(prompt),
                exit_code=result.returncode,
                provider_status_code=_provider_status_code(provider_text),
                stdout_chars=len(result.stdout or ""),
                stderr_chars=len(result.stderr or ""),
                stderr=_trim(provider_detail),
                **_output_file_details(output_path),
                request_id=request_id,
                step_name="codex_exec",
            )
            raise AIPlanningError(
                _nonzero_error_message(provider_text),
                error_code=error_code,
                provider_detail=provider_detail,
            )

        if output_path.exists():
            output = output_path.read_text(encoding="utf-8").strip()
        else:
            output = (result.stdout or "").strip()
        video_errors.log_step(
            "Codex CLI planning completed",
            provider=provider,
            model=settings.model,
            command_path=codex_path,
            timeout_seconds=timeout,
            elapsed_ms=round((time.perf_counter() - started) * 1000, 2),
            prompt_chars=len(prompt),
            output_chars=len(output),
            stdout_chars=len(result.stdout or ""),
            stderr_chars=len(result.stderr or ""),
            output_file_exists=output_path.exists(),
            step_name="codex_exec",
        )
        return output
