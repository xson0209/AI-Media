"""Windows asyncio compatibility helpers."""

from __future__ import annotations

import asyncio
import logging
import sys
from collections.abc import Mapping
from typing import Any

logger = logging.getLogger(__name__)

_HANDLER_MARKER = "_voicebox_proactor_connection_reset_suppression"
_PROACTOR_CONNECTION_LOST_CALLBACK = "_ProactorBasePipeTransport._call_connection_lost"


def configure_windows_event_loop_policy(*, platform_name: str = sys.platform) -> bool:
    """Use the Windows selector loop for the HTTP server when available.

    Python 3.12's default Proactor loop can drop uvicorn's localhost listener
    after some client-side disconnects on Windows. The backend uses synchronous
    subprocess calls for AI planning, so it does not need Proactor-only async
    subprocess support. Configure this before uvicorn creates its event loop.
    """
    if platform_name != "win32":
        return False

    policy_factory = getattr(asyncio, "WindowsSelectorEventLoopPolicy", None)
    if policy_factory is None:
        return False

    current_policy = asyncio.get_event_loop_policy()
    if isinstance(current_policy, policy_factory):
        return True

    asyncio.set_event_loop_policy(policy_factory())
    return True


def _is_proactor_connection_reset(context: Mapping[str, Any], platform_name: str) -> bool:
    if platform_name != "win32":
        return False

    exception = context.get("exception")
    if not isinstance(exception, ConnectionResetError):
        return False

    message = str(context.get("message", ""))
    handle = context.get("handle")
    if handle is not None:
        message = f"{message} {handle!r}"

    return _PROACTOR_CONNECTION_LOST_CALLBACK in message


def install_proactor_connection_reset_suppression(
    loop: asyncio.AbstractEventLoop | None = None,
    *,
    platform_name: str = sys.platform,
) -> bool:
    """Suppress noisy Windows Proactor logs for client-side connection resets.

    Python's Windows Proactor transport can raise ``ConnectionResetError`` while
    closing a socket that the remote peer already closed. The default event-loop
    exception handler logs that as an ERROR even though the request has already
    been handled or abandoned by the browser. Keep the suppression narrow so real
    application exceptions still reach the previous/default handler.
    """
    if platform_name != "win32":
        return False

    loop = loop or asyncio.get_running_loop()
    previous_handler = loop.get_exception_handler()
    if getattr(previous_handler, _HANDLER_MARKER, False):
        return True

    def handler(event_loop: asyncio.AbstractEventLoop, context: dict[str, Any]) -> None:
        if _is_proactor_connection_reset(context, platform_name):
            logger.debug("Suppressed benign Windows Proactor connection reset")
            return

        if previous_handler is not None:
            previous_handler(event_loop, context)
            return

        event_loop.default_exception_handler(context)

    setattr(handler, _HANDLER_MARKER, True)
    loop.set_exception_handler(handler)
    return True
