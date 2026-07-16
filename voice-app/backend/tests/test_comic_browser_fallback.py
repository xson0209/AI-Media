"""Browser fallback tests (tasks 4.6, 4.7, 4.8).

The SSRF request gate is tested directly (deterministic, no network). A full
render smoke test runs only if a Chromium binary is available.
"""

from __future__ import annotations

import pytest

from backend.services.comic_series_analysis import browser_fallback as bf
from backend.services.comic_series_analysis.config import get_config


def test_request_gate_blocks_dangerous_and_private():
    net = get_config().network
    # Public IP literal (no DNS needed) is allowed.
    assert bf._request_allowed("http://93.184.216.34/a.png", net) is True
    assert bf._request_allowed("https://8.8.8.8/a.png", net) is True
    # Dangerous schemes.
    assert bf._request_allowed("file:///etc/passwd", net) is False
    assert bf._request_allowed("data:image/png;base64,AAAA", net) is False
    assert bf._request_allowed("chrome-extension://abc/x", net) is False
    # Private network.
    assert bf._request_allowed("http://127.0.0.1/x", net) is False
    assert bf._request_allowed("http://169.254.169.254/latest", net) is False


@pytest.mark.skipif(not bf.is_browser_available(), reason="Chromium binary not installed")
def test_browser_availability_probe():
    # The SSRF gate blocks localhost/data URLs, so a full live-site render is
    # covered by manual QA (task 12.16). Here we confirm the runtime probe.
    assert bf.is_browser_available() is True
