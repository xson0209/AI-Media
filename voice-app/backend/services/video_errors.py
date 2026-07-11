"""Scoped error and logging helpers for AI Video Assistant APIs."""

from __future__ import annotations

import contextvars
import logging
import time
import uuid
from collections.abc import Awaitable, Callable
from typing import Any

from fastapi import HTTPException, Request, Response
from fastapi.exceptions import RequestValidationError
from fastapi.routing import APIRoute

logger = logging.getLogger(__name__)

_REQUEST_ID: contextvars.ContextVar[str | None] = contextvars.ContextVar(
    "ai_video_request_id",
    default=None,
)
_MAX_CONTEXT_CHARS = 1200


def current_request_id() -> str:
    """Return the current AI Video request id, creating one if needed."""
    request_id = _REQUEST_ID.get()
    if request_id:
        return request_id
    request_id = str(uuid.uuid4())
    _REQUEST_ID.set(request_id)
    return request_id


def _new_request_id(request: Request) -> str:
    header_value = (request.headers.get("X-Request-ID") or "").strip()
    if header_value and len(header_value) <= 128:
        return header_value
    return str(uuid.uuid4())


def _trim(value: Any) -> Any:
    if value is None:
        return None
    if isinstance(value, (int, float, bool)):
        return value
    text = str(value)
    if len(text) <= _MAX_CONTEXT_CHARS:
        return text
    return f"{text[:_MAX_CONTEXT_CHARS]}..."


def _context_text(context: dict[str, Any]) -> str:
    safe = {key: _trim(value) for key, value in context.items() if value is not None}
    if not safe:
        return ""
    return " " + " ".join(f"{key}={value!r}" for key, value in sorted(safe.items()))


def error_detail(message: str, error_code: str, *, request_id: str | None = None) -> dict[str, str]:
    """Build the user-facing error shape used by AI Video endpoints."""
    return {
        "message": message,
        "error_code": error_code,
        "request_id": request_id or current_request_id(),
    }


def api_error(
    status_code: int,
    message: str,
    error_code: str,
    *,
    exc: BaseException | None = None,
    **context: Any,
) -> HTTPException:
    """Create and log a friendly AI Video HTTP error."""
    request_id = current_request_id()
    log_context = {"request_id": request_id, "error_code": error_code, **context}
    log_message = f"AI Video API error: {message}{_context_text(log_context)}"
    if exc is not None or status_code >= 500:
        logger.exception(log_message, exc_info=exc)
    else:
        logger.warning(log_message)
    return HTTPException(
        status_code=status_code,
        detail=error_detail(message, error_code, request_id=request_id),
    )


def log_step(message: str, *, level: int = logging.INFO, **context: Any) -> None:
    """Log a structured AI Video step with the active request id."""
    logger.log(level, "AI Video: %s%s", message, _context_text({"request_id": current_request_id(), **context}))


def log_error(message: str, *, exc: BaseException | None = None, **context: Any) -> None:
    """Log a server-side AI Video failure with safe context."""
    logger.exception(
        "AI Video failure: %s%s",
        message,
        _context_text({"request_id": current_request_id(), **context}),
        exc_info=exc,
    )


class AIVideoRoute(APIRoute):
    """Attach request IDs and scoped error handling to AI Video endpoints."""

    def get_route_handler(self) -> Callable[[Request], Awaitable[Response]]:
        original_route_handler = super().get_route_handler()

        async def custom_route_handler(request: Request) -> Response:
            request_id = _new_request_id(request)
            request.state.ai_video_request_id = request_id
            token = _REQUEST_ID.set(request_id)
            started = time.perf_counter()
            context = {
                "request_id": request_id,
                "endpoint": request.url.path,
                "method": request.method,
            }
            try:
                response = await original_route_handler(request)
            except RequestValidationError as exc:
                log_error("Request validation failed", exc=exc, **context)
                raise HTTPException(
                    status_code=422,
                    detail=error_detail(
                        "Dữ liệu gửi lên chưa đúng. Hãy kiểm tra lại thông tin trong form.",
                        "AI_VIDEO_VALIDATION_ERROR",
                        request_id=request_id,
                    ),
                ) from exc
            except HTTPException as exc:
                detail = exc.detail
                if not isinstance(detail, dict) or "request_id" not in detail:
                    message = detail if isinstance(detail, str) else "Yêu cầu AI Video không thực hiện được."
                    exc.detail = error_detail(str(message), "AI_VIDEO_HTTP_ERROR", request_id=request_id)
                logger.warning(
                    "AI Video HTTP error%s",
                    _context_text({**context, "status_code": exc.status_code}),
                )
                raise
            except Exception as exc:
                log_error("Unhandled endpoint exception", exc=exc, **context)
                raise HTTPException(
                    status_code=500,
                    detail=error_detail(
                        "Có lỗi hệ thống khi xử lý AI Video. Hãy gửi request ID này cho developer.",
                        "AI_VIDEO_INTERNAL_ERROR",
                        request_id=request_id,
                    ),
                ) from exc
            finally:
                elapsed_ms = round((time.perf_counter() - started) * 1000, 2)
                logger.info("AI Video request finished%s", _context_text({**context, "elapsed_ms": elapsed_ms}))
                _REQUEST_ID.reset(token)

            response.headers["X-Request-ID"] = request_id
            return response

        return custom_route_handler
