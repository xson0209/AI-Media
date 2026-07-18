import asyncio

from backend.core.asyncio_windows import (
    configure_windows_event_loop_policy,
    install_proactor_connection_reset_suppression,
)


def _new_loop_with_captured_handler():
    loop = asyncio.new_event_loop()
    captured = []

    def previous_handler(_loop, context):
        captured.append(context)

    loop.set_exception_handler(previous_handler)
    return loop, captured


def test_windows_proactor_connection_reset_is_suppressed():
    loop, captured = _new_loop_with_captured_handler()
    try:
        installed = install_proactor_connection_reset_suppression(loop, platform_name="win32")

        assert installed is True
        loop.call_exception_handler(
            {
                "message": "Exception in callback _ProactorBasePipeTransport._call_connection_lost(None)",
                "exception": ConnectionResetError(10054, "An existing connection was forcibly closed"),
            }
        )

        assert captured == []
    finally:
        loop.close()


def test_non_proactor_connection_reset_still_delegates():
    loop, captured = _new_loop_with_captured_handler()
    try:
        install_proactor_connection_reset_suppression(loop, platform_name="win32")
        context = {
            "message": "Exception in callback application_task()",
            "exception": ConnectionResetError(10054, "An existing connection was forcibly closed"),
        }

        loop.call_exception_handler(context)

        assert captured == [context]
    finally:
        loop.close()


def test_non_windows_loop_is_left_unchanged():
    loop, captured = _new_loop_with_captured_handler()
    try:
        original_handler = loop.get_exception_handler()

        installed = install_proactor_connection_reset_suppression(loop, platform_name="linux")

        assert installed is False
        assert loop.get_exception_handler() is original_handler
        assert captured == []
    finally:
        loop.close()

def test_windows_event_loop_policy_uses_selector_when_available():
    policy_factory = getattr(asyncio, "WindowsSelectorEventLoopPolicy", None)
    if policy_factory is None:
        return

    original_policy = asyncio.get_event_loop_policy()
    try:
        installed = configure_windows_event_loop_policy(platform_name="win32")

        assert installed is True
        assert isinstance(asyncio.get_event_loop_policy(), policy_factory)
    finally:
        asyncio.set_event_loop_policy(original_policy)

def test_non_windows_event_loop_policy_is_left_unchanged():
    original_policy = asyncio.get_event_loop_policy()

    installed = configure_windows_event_loop_policy(platform_name="linux")

    assert installed is False
    assert asyncio.get_event_loop_policy() is original_policy
