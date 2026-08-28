"""AI planning provider integration for AI Video Assistant."""

from __future__ import annotations

import json
import logging
import os
import re
import shutil
import subprocess
import tempfile
import time
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .. import models
from ..database import AIPlanningSettings as DBAIPlanningSettings
from . import video_errors

logger = logging.getLogger(__name__)

CODEX_PROVIDER = "codex-cli"
DEFAULT_CODEX_MODEL = "gpt-5.6-sol"
DEFAULT_CODEX_REASONING_EFFORT = "ultra"
DEFAULT_CODEX_TIMEOUT_SECONDS = 600
CODEX_REASONING_EFFORTS = {"low", "medium", "high", "xhigh", "max", "ultra"}
MODEL_SOURCE_DEFAULT = "voicebox_default"
MODEL_SOURCE_SETTINGS = "app_settings_override"
MODEL_SOURCE_ENV = "voicebox_env"
MODEL_SOURCE_USER_CONNECTED = "user_connected_codex_config"
USER_CONNECTED_CODEX_CONFIG_LABEL = "Cấu hình Codex hiện tại của người dùng"
_MAX_LOG_CHARS = 4000
_MAX_PROVIDER_DETAIL_CHARS = 2000
_STATUS_PATTERN = re.compile(r"(?i)(?:unexpected\s+)?status\s+(\d{3})")
_SECRET_PATTERN = re.compile(
    r"(?i)(api[_-]?key|secret|token|bearer|authorization|password)\s*[:=]\s*([^\s,;]+)"
)
_BEARER_PATTERN = re.compile(r"(?i)bearer\s+[^\s,;]+")
_TRANSIENT_PROVIDER_MARKERS = (
    "currently experiencing high demand",
    "high demand",
    "reconnecting",
    "temporar",
    "rate limit",
    "rate_limit",
    "try again",
)
_CODEX_EXEC_TIMEOUT_MARKERS = (
    "codex exec timed out",
    "exec timed out",
    "timed out after",
)
_MODEL_CONFIG_FALLBACK_MARKERS = (
    "model does not exist",
    "unknown model",
    "model not found",
    "model is not supported",
    "unsupported model",
    "no access to model",
    "not available for this model",
    "model_reasoning_effort",
    "reasoning effort",
    "unsupported config",
    "invalid config",
    "invalid value for",
    "--config",
)

@dataclass(frozen=True)
class CodexModelPolicy:
    requested_model: str
    requested_reasoning_effort: str
    model_source: str

@dataclass(frozen=True)
class CodexCommandProfile:
    name: str
    model: str | None
    reasoning_effort: str | None
    model_source: str
    force_app_model_config: bool
    label: str
    fallback_reason: str | None = None

@dataclass
class CodexAttemptResult:
    success: bool
    output: str | None = None
    profile: CodexCommandProfile | None = None
    error_code: str | None = None
    message: str | None = None
    provider_text: str | None = None
    provider_detail: str | None = None
    exit_code: int | None = None
    elapsed_ms: float = 0.0
    schema_fallback_used: bool = False

@dataclass
class CodexExecResult:
    output: str
    metadata: dict[str, Any]

class AIPlanningError(RuntimeError):
    """Raised when an AI planning provider cannot complete a request."""

    def __init__(
        self,
        message: str,
        *,
        error_code: str = "AI_PLANNING_ERROR",
        provider_detail: str | None = None,
        metadata: dict[str, Any] | None = None,
    ):
        super().__init__(message)
        self.error_code = error_code
        self.provider_detail = provider_detail
        self.metadata = metadata or {}

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
    if len(text) <= _MAX_PROVIDER_DETAIL_CHARS:
        return text
    separator = "\n...[provider output truncated]...\n"
    head_chars = max(300, _MAX_PROVIDER_DETAIL_CHARS // 3)
    tail_chars = max(300, _MAX_PROVIDER_DETAIL_CHARS - head_chars - len(separator))
    return f"{text[:head_chars]}{separator}{text[-tail_chars:]}"

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

def _looks_like_transient_provider_failure(value: str | None) -> bool:
    if not value:
        return False
    lowered = value.lower()
    status_code = _provider_status_code(value)
    if status_code in {408, 409, 425, 429, 500, 502, 503, 504, 529}:
        return True
    return any(marker in lowered for marker in _TRANSIENT_PROVIDER_MARKERS)

def _looks_like_codex_exec_timeout(value: str | None) -> bool:
    if not value:
        return False
    lowered = value.lower()
    return any(marker in lowered for marker in _CODEX_EXEC_TIMEOUT_MARKERS)

def _provider_failure_text(result: subprocess.CompletedProcess[str]) -> str:
    return "\n".join(part for part in (result.stderr, result.stdout) if part).strip()

def _nonzero_error_code(provider_text: str | None) -> str:
    status_code = _provider_status_code(provider_text)
    if _looks_like_codex_exec_timeout(provider_text):
        return "CODEX_EXEC_TIMEOUT"
    if _looks_like_transient_provider_failure(provider_text):
        return "CODEX_PROVIDER_TEMPORARY_UNAVAILABLE"
    if status_code in {400, 401, 403, 404}:
        return "CODEX_PROVIDER_REJECTED"
    return "CODEX_EXEC_NONZERO"

def _nonzero_error_message(provider_text: str | None) -> str:
    status_code = _provider_status_code(provider_text)
    detail = _redact_provider_text(provider_text)
    if _looks_like_codex_exec_timeout(provider_text):
        return (
            "AI xu ly qua lau khi tao noi dung. Hay thu lai; neu van loi, "
            "hay rut ngan nguon noi dung hoac tang timeout trong Settings."
            + (f" Chi tiet: {detail}" if detail else "")
        )
    if _looks_like_transient_provider_failure(provider_text):
        return (
            "Codex provider dang qua tai hoac tam thoi khong on dinh khi tao noi dung. "
            "Voicebox da thu fallback schema neu co the; hay chay lai sau it phut neu loi con lap."
            + (f" Chi tiet: {detail}" if detail else "")
        )
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
    if _looks_like_transient_provider_failure(provider_text):
        return True
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

def _normalize_model(value: str | None) -> str | None:
    text = (value or "").strip()
    return text or None

def _normalize_reasoning_effort(value: str | None) -> str | None:
    text = (value or "").strip().lower()
    return text if text in CODEX_REASONING_EFFORTS else None

def resolve_codex_model_policy(settings: DBAIPlanningSettings) -> CodexModelPolicy:
    env_model = _normalize_model(os.environ.get("VOICEBOX_CODEX_MODEL"))
    env_effort = _normalize_reasoning_effort(os.environ.get("VOICEBOX_CODEX_REASONING_EFFORT"))
    settings_model = _normalize_model(getattr(settings, "model", None))
    settings_effort = _normalize_reasoning_effort(getattr(settings, "model_reasoning_effort", None))
    if settings_model or settings_effort:
        return CodexModelPolicy(
            requested_model=settings_model or env_model or DEFAULT_CODEX_MODEL,
            requested_reasoning_effort=settings_effort or env_effort or DEFAULT_CODEX_REASONING_EFFORT,
            model_source=MODEL_SOURCE_SETTINGS,
        )
    if env_model or env_effort:
        return CodexModelPolicy(
            requested_model=env_model or DEFAULT_CODEX_MODEL,
            requested_reasoning_effort=env_effort or DEFAULT_CODEX_REASONING_EFFORT,
            model_source=MODEL_SOURCE_ENV,
        )
    return CodexModelPolicy(
        requested_model=DEFAULT_CODEX_MODEL,
        requested_reasoning_effort=DEFAULT_CODEX_REASONING_EFFORT,
        model_source=MODEL_SOURCE_DEFAULT,
    )

def _primary_profile(settings: DBAIPlanningSettings) -> CodexCommandProfile:
    policy = resolve_codex_model_policy(settings)
    return CodexCommandProfile(
        name="preferred",
        model=policy.requested_model,
        reasoning_effort=policy.requested_reasoning_effort,
        model_source=policy.model_source,
        force_app_model_config=True,
        label=f"{policy.requested_model} · {policy.requested_reasoning_effort}",
    )

def _fallback_profile(reason: str | None) -> CodexCommandProfile:
    return CodexCommandProfile(
        name="user_connected_fallback",
        model=USER_CONNECTED_CODEX_CONFIG_LABEL,
        reasoning_effort=None,
        model_source=MODEL_SOURCE_USER_CONNECTED,
        force_app_model_config=False,
        label=USER_CONNECTED_CODEX_CONFIG_LABEL,
        fallback_reason=reason,
    )

def _profile_metadata(
    policy: CodexModelPolicy,
    *,
    effective_profile: CodexCommandProfile | None = None,
    model_verified: bool = False,
    fallback_used: bool = False,
    fallback_reason: str | None = None,
    fallback_error_code: str | None = None,
) -> dict[str, Any]:
    effective_model = None
    effective_reasoning_effort = None
    model_source = policy.model_source
    if effective_profile is not None:
        effective_model = effective_profile.model or effective_profile.label
        effective_reasoning_effort = effective_profile.reasoning_effort
        model_source = effective_profile.model_source
    return {
        "requested_model": policy.requested_model,
        "requested_reasoning_effort": policy.requested_reasoning_effort,
        "effective_model": effective_model,
        "effective_reasoning_effort": effective_reasoning_effort,
        "model_source": model_source,
        "model_verified": model_verified,
        "fallback_used": fallback_used,
        "fallback_reason": fallback_reason,
        "fallback_error_code": fallback_error_code,
    }

def _metadata_response_kwargs(metadata: dict[str, Any]) -> dict[str, Any]:
    return {
        "requested_model": metadata.get("requested_model"),
        "requested_reasoning_effort": metadata.get("requested_reasoning_effort"),
        "effective_model": metadata.get("effective_model"),
        "effective_reasoning_effort": metadata.get("effective_reasoning_effort"),
        "model_source": metadata.get("model_source"),
        "model_verified": bool(metadata.get("model_verified")),
        "fallback_used": bool(metadata.get("fallback_used")),
        "fallback_reason": metadata.get("fallback_reason"),
        "fallback_error_code": metadata.get("fallback_error_code"),
    }

def _looks_like_model_config_failure(provider_text: str | None, error_code: str | None = None) -> bool:
    if error_code == "CODEX_EXEC_TIMEOUT":
        return True
    if not provider_text:
        return False
    if _looks_like_auth_failure(provider_text):
        return False
    lowered = provider_text.lower()
    status_code = _provider_status_code(provider_text)
    if status_code in {400, 403, 404, 408, 409, 425, 429, 500, 502, 503, 504, 529}:
        return True
    if _looks_like_transient_provider_failure(provider_text):
        return True
    return any(marker in lowered for marker in _MODEL_CONFIG_FALLBACK_MARKERS)

def _should_retry_user_connected_config(attempt: CodexAttemptResult) -> bool:
    if attempt.error_code in {"CODEX_CLI_NOT_FOUND", "CODEX_PATH_INVALID", "CODEX_EXEC_FAILED"}:
        return False
    if _looks_like_auth_failure(attempt.provider_text):
        return False
    return _looks_like_model_config_failure(attempt.provider_text, attempt.error_code)

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

def _strict_response_format_schema(schema: dict[str, Any]) -> dict[str, Any]:
    """Return a provider-safe JSON schema for structured responses.

    OpenAI-compatible structured output rejects object schemas that do not
    explicitly set ``additionalProperties: false``. Some generated schemas also
    use JSON Schema type unions such as ``["object", "null"]``; the provider
    reports those union branches as nested ``type.0`` contexts and still
    requires strict object metadata there. Normalize before passing the schema
    to ``codex exec --output-schema`` and before embedding it in fallback
    prompts.
    """

    def clone(value: Any) -> Any:
        if isinstance(value, dict):
            return normalize_object(dict(value))
        if isinstance(value, list):
            return [clone(item) for item in value]
        return value

    def normalize_type_union(node: dict[str, Any], type_values: list[Any]) -> dict[str, Any]:
        shared = {key: value for key, value in node.items() if key != "type"}
        variants: list[dict[str, Any]] = []
        for type_value in type_values:
            if type_value == "null":
                variants.append({"type": "null"})
                continue
            variant = clone(shared)
            if not isinstance(variant, dict):
                variant = {}
            variant["type"] = type_value
            variants.append(normalize_object(variant))
        return {"anyOf": variants}

    def normalize_object(node: dict[str, Any]) -> dict[str, Any]:
        type_value = node.get("type")
        if isinstance(type_value, list):
            return normalize_type_union(node, type_value)

        properties = node.get("properties")
        if isinstance(properties, dict):
            node["properties"] = {key: clone(value) for key, value in properties.items()}
            node.setdefault("type", "object")

        if node.get("type") == "object":
            if "properties" not in node:
                raise ValueError(
                    "Strict response schema contains a free-form object without properties; "
                    "define a structured model before sending it to the provider."
                )
            node["additionalProperties"] = False
            if isinstance(node.get("properties"), dict):
                # Codex/OpenAI structured outputs require every property to be
                # present in ``required``.  Pydantic's JSON schema preserves
                # optional fields by leaving them out of ``required``; for the
                # response format those fields must instead be required and
                # represented as nullable in their property schema.
                node["required"] = list(node["properties"].keys())

        items = node.get("items")
        if isinstance(items, dict):
            node["items"] = clone(items)
        elif isinstance(items, list):
            node["items"] = [clone(item) for item in items]

        for key in ("anyOf", "oneOf", "allOf"):
            values = node.get(key)
            if isinstance(values, list):
                node[key] = [clone(value) for value in values]

        for key in ("$defs", "definitions", "dependentSchemas", "patternProperties"):
            values = node.get(key)
            if isinstance(values, dict):
                node[key] = {name: clone(value) for name, value in values.items()}

        additional = node.get("additionalProperties")
        if isinstance(additional, dict):
            node["additionalProperties"] = False

        return node

    return clone(schema)

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
    creationflags = subprocess.CREATE_NEW_PROCESS_GROUP if os.name == "nt" else 0
    process = subprocess.Popen(
        command,
        cwd=str(cwd) if cwd else None,
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        encoding="utf-8",
        errors="replace",
        creationflags=creationflags,
    )
    try:
        stdout, stderr = process.communicate(input=input_text, timeout=timeout_seconds)
    except subprocess.TimeoutExpired as exc:
        if os.name == "nt":
            subprocess.run(
                ["taskkill.exe", "/pid", str(process.pid), "/t", "/f"],
                capture_output=True,
                check=False,
            )
        else:
            process.kill()
        try:
            stdout, stderr = process.communicate(timeout=5)
        except subprocess.TimeoutExpired:
            process.kill()
            stdout, stderr = process.communicate()
        exc.output = stdout
        exc.stderr = stderr
        raise
    return subprocess.CompletedProcess(command, process.returncode, stdout, stderr)

def check_provider(
    settings: DBAIPlanningSettings,
    *,
    check_exec: bool = False,
    cwd: str | Path | None = None,
) -> models.AIPlanningProviderCheckResponse:
    """Check whether the configured planning provider is ready."""
    request_id = _request_id()
    provider = settings.provider or CODEX_PROVIDER
    policy = resolve_codex_model_policy(settings)
    planned_metadata = _metadata_response_kwargs(_profile_metadata(policy))

    if provider != CODEX_PROVIDER:
        return models.AIPlanningProviderCheckResponse(
            ready=False,
            provider=provider,
            message="Provider AI planning này chưa được hỗ trợ trong bản hiện tại.",
            request_id=request_id,
            error_code="AI_PROVIDER_NOT_IMPLEMENTED",
            **planned_metadata,
        )

    codex_path = resolve_codex_path(settings)
    if not codex_path:
        return models.AIPlanningProviderCheckResponse(
            ready=False,
            provider=provider,
            message="Chưa tìm thấy Codex CLI. Hãy kiểm tra đường dẫn Codex trong Settings.",
            request_id=request_id,
            error_code="CODEX_CLI_NOT_FOUND",
            **planned_metadata,
        )

    if not Path(codex_path).exists() and shutil.which(codex_path) is None:
        return models.AIPlanningProviderCheckResponse(
            ready=False,
            provider=provider,
            codex_path=codex_path,
            message="Đường dẫn Codex CLI không tồn tại. Hãy cập nhật lại Settings.",
            request_id=request_id,
            error_code="CODEX_PATH_INVALID",
            **planned_metadata,
        )

    timeout = max(5, min(settings.timeout_seconds or DEFAULT_CODEX_TIMEOUT_SECONDS, DEFAULT_CODEX_TIMEOUT_SECONDS))
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
            **planned_metadata,
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
            **planned_metadata,
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
            **planned_metadata,
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
            exec_result = run_codex_exec(
                settings,
                "Trả lời đúng một chữ: OK",
                timeout_seconds=min(timeout, 30),
                cwd=cwd,
                return_metadata=True,
            )
            if isinstance(exec_result, CodexExecResult):
                planned_metadata = _metadata_response_kwargs(exec_result.metadata)
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
                **_metadata_response_kwargs(exc.metadata or _profile_metadata(policy)),
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
        **planned_metadata,
    )

def test_provider_prompt(
    settings: DBAIPlanningSettings,
    *,
    prompt: str = "xin chào",
    cwd: str | Path | None = None,
) -> models.AIPlanningTestResponse:
    """Run a small live Codex prompt to prove the saved model config works."""

    provider = settings.provider or CODEX_PROVIDER
    policy = resolve_codex_model_policy(settings)
    planned_metadata = _metadata_response_kwargs(_profile_metadata(policy))
    timeout = max(5, min(settings.timeout_seconds or DEFAULT_CODEX_TIMEOUT_SECONDS, DEFAULT_CODEX_TIMEOUT_SECONDS))
    try:
        result = run_codex_exec(
            settings,
            prompt,
            timeout_seconds=timeout,
            cwd=cwd,
            return_metadata=True,
        )
    except AIPlanningError as exc:
        metadata = _metadata_response_kwargs(exc.metadata or _profile_metadata(policy))
        return models.AIPlanningTestResponse(
            ready=False,
            provider=provider,
            prompt=prompt,
            message=str(exc) or "Codex chưa phản hồi được với cấu hình hiện tại.",
            request_id=(exc.metadata or {}).get("request_id"),
            error_code=exc.error_code,
            **metadata,
        )

    if isinstance(result, CodexExecResult):
        output_text = (result.output or "").strip()
        metadata = _metadata_response_kwargs(result.metadata)
        request_id = result.metadata.get("request_id")
    else:
        output_text = str(result or "").strip()
        metadata = planned_metadata
        request_id = None

    return models.AIPlanningTestResponse(
        ready=bool(output_text),
        provider=provider,
        prompt=prompt,
        output_text=output_text or None,
        message=(
            "Codex đã phản hồi text với cấu hình vừa lưu."
            if output_text
            else "Codex chạy xong nhưng không trả về text."
        ),
        request_id=request_id,
        error_code=None if output_text else "CODEX_EMPTY_OUTPUT",
        **metadata,
    )

def run_codex_exec(
    settings: DBAIPlanningSettings,
    prompt: str,
    *,
    output_schema: dict[str, Any] | None = None,
    timeout_seconds: int | None = None,
    cwd: str | Path | None = None,
    image_paths: list[str | Path] | None = None,
    return_metadata: bool = False,
) -> str | CodexExecResult:
    """Run `codex exec` and return the final assistant message."""
    provider = settings.provider or CODEX_PROVIDER
    request_id = video_errors.current_request_id()
    policy = resolve_codex_model_policy(settings)
    if provider != CODEX_PROVIDER:
        raise AIPlanningError(
            "Provider AI planning này chưa được hỗ trợ.",
            error_code="AI_PROVIDER_NOT_IMPLEMENTED",
            metadata={**_profile_metadata(policy), "request_id": request_id},
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
        raise AIPlanningError(
            "Chưa tìm thấy Codex CLI.",
            error_code="CODEX_CLI_NOT_FOUND",
            metadata={**_profile_metadata(policy), "request_id": request_id},
        )

    timeout = max(5, min(timeout_seconds or settings.timeout_seconds or DEFAULT_CODEX_TIMEOUT_SECONDS, DEFAULT_CODEX_TIMEOUT_SECONDS))
    resolved_image_paths = [str(Path(path).expanduser().resolve()) for path in (image_paths or [])]
    for image_path in resolved_image_paths:
        if not Path(image_path).is_file():
            raise AIPlanningError(
                f"Không đọc được ảnh đính kèm: {image_path}",
                error_code="CODEX_IMAGE_NOT_FOUND",
                metadata={**_profile_metadata(policy), "request_id": request_id},
            )
    strict_output_schema = _strict_response_format_schema(output_schema) if output_schema else None
    with tempfile.TemporaryDirectory(prefix="voicebox-codex-") as tmpdir:
        output_path = Path(tmpdir) / "last-message.txt"
        schema_path: Path | None = None
        if strict_output_schema:
            schema_path = Path(tmpdir) / "output-schema.json"
            schema_path.write_text(json.dumps(strict_output_schema), encoding="utf-8")

        def build_command(profile: CodexCommandProfile, *, use_output_schema: bool) -> list[str]:
            command = [
                codex_path,
                "exec",
                "--skip-git-repo-check",
                "--ephemeral",
                "--output-last-message",
                str(output_path),
            ]
            if profile.force_app_model_config:
                if profile.model:
                    command.extend(["--model", profile.model])
                if profile.reasoning_effort:
                    command.extend(["--config", f'model_reasoning_effort="{profile.reasoning_effort}"'])
            if use_output_schema and schema_path is not None:
                command.extend(["--output-schema", str(schema_path)])
            if resolved_image_paths:
                command.extend(["--image", *resolved_image_paths])
            command.append("-")
            return command

        schema_keys = []
        if isinstance(strict_output_schema, dict):
            properties = strict_output_schema.get("properties")
            if isinstance(properties, dict):
                schema_keys = sorted(str(key) for key in properties)[:20]

        def read_output(result: subprocess.CompletedProcess[str]) -> str:
            if output_path.exists():
                return output_path.read_text(encoding="utf-8").strip()
            return (result.stdout or "").strip()

        def run_profile(profile: CodexCommandProfile, *, fallback_used: bool) -> CodexAttemptResult:
            started = time.perf_counter()
            output_path.unlink(missing_ok=True)
            command = build_command(profile, use_output_schema=bool(strict_output_schema))
            step_name = "codex_exec_model_fallback" if fallback_used else "codex_exec"
            video_errors.log_step(
                "Running Codex CLI planning" if not fallback_used else "Running Codex CLI planning with user Codex config fallback",
                provider=provider,
                requested_model=policy.requested_model,
                requested_reasoning_effort=policy.requested_reasoning_effort,
                effective_model=profile.model,
                effective_reasoning_effort=profile.reasoning_effort,
                model_source=profile.model_source,
                fallback_used=fallback_used,
                fallback_reason=profile.fallback_reason,
                command_path=codex_path,
                timeout_seconds=timeout,
                prompt_chars=len(prompt),
                image_count=len(resolved_image_paths),
                schema_keys=",".join(schema_keys) if schema_keys else None,
                output_schema=bool(strict_output_schema),
                step_name=step_name,
            )
            try:
                result = _run_command(command, timeout_seconds=timeout, cwd=cwd, input_text=prompt)
            except subprocess.TimeoutExpired as exc:
                elapsed_ms = round((time.perf_counter() - started) * 1000, 2)
                stdout = _process_text(exc.output)
                stderr = _process_text(exc.stderr)
                provider_text = "\n".join(
                    part
                    for part in (
                        f"Codex exec timed out after {timeout} seconds.",
                        stdout,
                        stderr,
                    )
                    if part
                )
                video_errors.log_error(
                    "Codex CLI planning timed out",
                    exc=exc,
                    provider=provider,
                    requested_model=policy.requested_model,
                    requested_reasoning_effort=policy.requested_reasoning_effort,
                    effective_model=profile.model,
                    effective_reasoning_effort=profile.reasoning_effort,
                    model_source=profile.model_source,
                    fallback_used=fallback_used,
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
                    step_name=step_name,
                )
                return CodexAttemptResult(
                    success=False,
                    profile=profile,
                    error_code="CODEX_EXEC_TIMEOUT",
                    message=(
                        "AI xử lý quá lâu khi tạo nội dung. Hãy thử lại; nếu vẫn lỗi, "
                        "hãy rút ngắn nguồn nội dung hoặc tăng timeout trong Settings."
                    ),
                    provider_text=provider_text,
                    provider_detail=_redact_provider_text(provider_text),
                    elapsed_ms=elapsed_ms,
                )
            except OSError as exc:
                metadata = {**_profile_metadata(policy), "request_id": request_id}
                video_errors.log_error(
                    "Codex CLI planning failed to start",
                    exc=exc,
                    provider=provider,
                    requested_model=policy.requested_model,
                    requested_reasoning_effort=policy.requested_reasoning_effort,
                    effective_model=profile.model,
                    effective_reasoning_effort=profile.reasoning_effort,
                    model_source=profile.model_source,
                    fallback_used=fallback_used,
                    command_path=codex_path,
                    timeout_seconds=timeout,
                    elapsed_ms=round((time.perf_counter() - started) * 1000, 2),
                    prompt_chars=len(prompt),
                    request_id=request_id,
                    step_name=step_name,
                )
                raise AIPlanningError(
                    "Không chạy được Codex CLI.",
                    error_code="CODEX_EXEC_FAILED",
                    metadata=metadata,
                ) from exc

            provider_text = _provider_failure_text(result) if result.returncode != 0 else None
            schema_fallback_used = False
            if result.returncode != 0 and strict_output_schema and _should_retry_without_output_schema(provider_text):
                schema_fallback_used = True
                initial_provider_text = provider_text or ""
                video_errors.log_step(
                    "Codex output_schema request failed; retrying with inline JSON schema",
                    provider=provider,
                    requested_model=policy.requested_model,
                    requested_reasoning_effort=policy.requested_reasoning_effort,
                    effective_model=profile.model,
                    effective_reasoning_effort=profile.reasoning_effort,
                    model_source=profile.model_source,
                    fallback_used=fallback_used,
                    command_path=codex_path,
                    timeout_seconds=timeout,
                    elapsed_ms=round((time.perf_counter() - started) * 1000, 2),
                    prompt_chars=len(prompt),
                    inline_prompt_chars=len(_prompt_with_inline_schema(prompt, strict_output_schema)),
                    exit_code=result.returncode,
                    provider_status_code=_provider_status_code(initial_provider_text),
                    stderr=_redact_provider_text(initial_provider_text),
                    request_id=request_id,
                    step_name="codex_exec_schema_fallback",
                )
                try:
                    output_path.unlink(missing_ok=True)
                    fallback_prompt = _prompt_with_inline_schema(prompt, strict_output_schema)
                    result = _run_command(
                        build_command(profile, use_output_schema=False),
                        timeout_seconds=timeout,
                        cwd=cwd,
                        input_text=fallback_prompt,
                    )
                    if result.returncode == 0:
                        video_errors.log_step(
                            "Codex CLI planning completed with inline JSON schema fallback",
                            provider=provider,
                            requested_model=policy.requested_model,
                            requested_reasoning_effort=policy.requested_reasoning_effort,
                            effective_model=profile.model,
                            effective_reasoning_effort=profile.reasoning_effort,
                            model_source=profile.model_source,
                            fallback_used=fallback_used,
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
                        provider_text = (
                            f"Structured output error:\n{initial_provider_text}\n\n"
                            f"Inline schema fallback error:\n{fallback_provider_text}"
                        ).strip()
                except subprocess.TimeoutExpired as exc:
                    stdout = _process_text(exc.output)
                    stderr = _process_text(exc.stderr)
                    fallback_timeout_text = "\n".join(
                        part
                        for part in (
                            f"Codex inline schema fallback timed out after {timeout} seconds.",
                            stdout,
                            stderr,
                        )
                        if part
                    )
                    provider_text = (
                        f"Structured output error:\n{initial_provider_text}\n\n"
                        f"Inline schema fallback error:\n{fallback_timeout_text}"
                    ).strip()
                    video_errors.log_error(
                        "Codex CLI inline schema fallback timed out",
                        exc=exc,
                        provider=provider,
                        requested_model=policy.requested_model,
                        requested_reasoning_effort=policy.requested_reasoning_effort,
                        effective_model=profile.model,
                        effective_reasoning_effort=profile.reasoning_effort,
                        model_source=profile.model_source,
                        fallback_used=fallback_used,
                        command_path=codex_path,
                        timeout_seconds=timeout,
                        elapsed_ms=round((time.perf_counter() - started) * 1000, 2),
                        prompt_chars=len(prompt),
                        stdout_chars=len(stdout or ""),
                        stderr_chars=len(stderr or ""),
                        stdout_tail=_trim(stdout[-_MAX_LOG_CHARS:] if stdout else None),
                        stderr_tail=_trim(stderr[-_MAX_LOG_CHARS:] if stderr else None),
                        initial_provider_status_code=_provider_status_code(initial_provider_text),
                        initial_provider_error=_redact_provider_text(initial_provider_text),
                        **_output_file_details(output_path),
                        request_id=request_id,
                        step_name="codex_exec_schema_fallback",
                    )
                    return CodexAttemptResult(
                        success=False,
                        profile=profile,
                        error_code="CODEX_EXEC_TIMEOUT",
                        message=(
                            "AI xử lý quá lâu khi tạo nội dung bằng fallback schema text. Hãy thử lại; "
                            "nếu vẫn lỗi, hãy rút ngắn nguồn nội dung hoặc tăng timeout trong Settings."
                        ),
                        provider_text=provider_text,
                        provider_detail=_redact_provider_text(provider_text),
                        elapsed_ms=round((time.perf_counter() - started) * 1000, 2),
                        schema_fallback_used=True,
                    )
                except OSError as exc:
                    metadata = {**_profile_metadata(policy), "request_id": request_id}
                    video_errors.log_error(
                        "Codex CLI inline schema fallback failed to start",
                        exc=exc,
                        provider=provider,
                        requested_model=policy.requested_model,
                        requested_reasoning_effort=policy.requested_reasoning_effort,
                        effective_model=profile.model,
                        effective_reasoning_effort=profile.reasoning_effort,
                        model_source=profile.model_source,
                        fallback_used=fallback_used,
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
                        metadata=metadata,
                    ) from exc

            elapsed_ms = round((time.perf_counter() - started) * 1000, 2)
            if result.returncode != 0:
                provider_text = provider_text or _provider_failure_text(result)
                error_code = _nonzero_error_code(provider_text)
                provider_detail = _redact_provider_text(provider_text)
                logger.warning(
                    "Codex exec failed: %s",
                    _trim(provider_text),
                    extra={
                        "request_id": request_id,
                        "provider": provider,
                        "requested_model": policy.requested_model,
                        "requested_reasoning_effort": policy.requested_reasoning_effort,
                        "effective_model": profile.model,
                        "effective_reasoning_effort": profile.reasoning_effort,
                        "model_source": profile.model_source,
                        "fallback_used": fallback_used,
                        "codex_path": codex_path,
                        "timeout_seconds": timeout,
                        "elapsed_ms": elapsed_ms,
                        "prompt_chars": len(prompt),
                        "exit_code": result.returncode,
                        "step_name": step_name,
                    },
                )
                video_errors.log_error(
                    "Codex CLI returned non-zero exit code",
                    provider=provider,
                    requested_model=policy.requested_model,
                    requested_reasoning_effort=policy.requested_reasoning_effort,
                    effective_model=profile.model,
                    effective_reasoning_effort=profile.reasoning_effort,
                    model_source=profile.model_source,
                    fallback_used=fallback_used,
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
                    step_name=step_name,
                )
                return CodexAttemptResult(
                    success=False,
                    profile=profile,
                    error_code=error_code,
                    message=_nonzero_error_message(provider_text),
                    provider_text=provider_text,
                    provider_detail=provider_detail,
                    exit_code=result.returncode,
                    elapsed_ms=elapsed_ms,
                    schema_fallback_used=schema_fallback_used,
                )

            output = read_output(result)
            video_errors.log_step(
                "Codex CLI planning completed",
                provider=provider,
                requested_model=policy.requested_model,
                requested_reasoning_effort=policy.requested_reasoning_effort,
                effective_model=profile.model,
                effective_reasoning_effort=profile.reasoning_effort,
                model_source=profile.model_source,
                fallback_used=fallback_used,
                fallback_reason=profile.fallback_reason,
                command_path=codex_path,
                timeout_seconds=timeout,
                elapsed_ms=elapsed_ms,
                prompt_chars=len(prompt),
                output_chars=len(output),
                stdout_chars=len(result.stdout or ""),
                stderr_chars=len(result.stderr or ""),
                output_file_exists=output_path.exists(),
                schema_fallback_used=schema_fallback_used,
                step_name=step_name,
            )
            return CodexAttemptResult(
                success=True,
                output=output,
                profile=profile,
                elapsed_ms=elapsed_ms,
                schema_fallback_used=schema_fallback_used,
            )

        primary_profile = _primary_profile(settings)
        primary = run_profile(primary_profile, fallback_used=False)
        fallback: CodexAttemptResult | None = None
        fallback_reason = primary.provider_detail or primary.message
        fallback_error_code = primary.error_code

        if primary.success:
            metadata = {
                **_profile_metadata(policy, effective_profile=primary.profile, model_verified=True),
                "request_id": request_id,
            }
            result = CodexExecResult(output=primary.output or "", metadata=metadata)
            return result if return_metadata else result.output

        if _should_retry_user_connected_config(primary):
            reason = _trim(fallback_reason)
            fallback_profile = _fallback_profile(reason)
            video_errors.log_step(
                "Codex preferred model/config failed; retrying with user Codex config",
                provider=provider,
                requested_model=policy.requested_model,
                requested_reasoning_effort=policy.requested_reasoning_effort,
                effective_model=fallback_profile.model,
                model_source=fallback_profile.model_source,
                fallback_used=True,
                fallback_reason=reason,
                fallback_error_code=fallback_error_code,
                command_path=codex_path,
                timeout_seconds=timeout,
                request_id=request_id,
                step_name="codex_exec_model_fallback",
            )
            fallback = run_profile(fallback_profile, fallback_used=True)
            if fallback.success:
                metadata = {
                    **_profile_metadata(
                        policy,
                        effective_profile=fallback.profile,
                        model_verified=True,
                        fallback_used=True,
                        fallback_reason=reason,
                        fallback_error_code=fallback_error_code,
                    ),
                    "request_id": request_id,
                }
                result = CodexExecResult(output=fallback.output or "", metadata=metadata)
                return result if return_metadata else result.output

        if fallback is not None:
            provider_text = (
                f"Preferred profile error:\n{primary.provider_text or primary.message or ''}\n\n"
                f"User Codex config fallback error:\n{fallback.provider_text or fallback.message or ''}"
            ).strip()
            error_code = fallback.error_code or primary.error_code or "CODEX_EXEC_NONZERO"
            metadata = {
                **_profile_metadata(
                    policy,
                    effective_profile=fallback.profile,
                    model_verified=False,
                    fallback_used=True,
                    fallback_reason=_trim(fallback_reason),
                    fallback_error_code=primary.error_code,
                ),
                "request_id": request_id,
            }
        else:
            provider_text = primary.provider_text or primary.message or ""
            error_code = primary.error_code or "CODEX_EXEC_NONZERO"
            metadata = {
                **_profile_metadata(policy, effective_profile=primary.profile, model_verified=False),
                "request_id": request_id,
            }

        provider_detail = _redact_provider_text(provider_text)
        raise AIPlanningError(
            primary.message if fallback is None and primary.message else _nonzero_error_message(provider_text),
            error_code=error_code,
            provider_detail=provider_detail,
            metadata=metadata,
        )
