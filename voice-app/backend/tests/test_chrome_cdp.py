from __future__ import annotations

import pytest

from backend.services import chrome_cdp


def test_open_target_falls_back_to_browser_cdp_when_json_new_fails(monkeypatch):
    target = chrome_cdp.ChromeTarget(
        id="target-1",
        type="page",
        title="Flow",
        url="https://labs.google/fx/tools/flow",
        web_socket_debugger_url="ws://127.0.0.1:9222/devtools/page/target-1",
    )
    requests = []
    clients = []

    def fake_urlopen(request, *, timeout):
        requests.append((request.full_url, request.get_method(), timeout))
        raise OSError("404 from /json/new")

    class FakeCDPClient:
        def __init__(self, websocket_url):
            self.websocket_url = websocket_url
            self.commands = []
            clients.append(self)

        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return None

        def command(self, method, params=None, *, timeout=15.0):
            self.commands.append((method, params, timeout))
            return {"targetId": "target-1"}

    monkeypatch.setattr(chrome_cdp, "urlopen", fake_urlopen)
    monkeypatch.setattr(
        chrome_cdp,
        "browser_websocket_url",
        lambda port: f"ws://127.0.0.1:{port}/devtools/browser/browser-1",
    )
    monkeypatch.setattr(chrome_cdp, "CDPClient", FakeCDPClient)
    monkeypatch.setattr(chrome_cdp, "list_targets", lambda port: [target])
    monkeypatch.setattr(chrome_cdp.time, "sleep", lambda _seconds: None)

    result = chrome_cdp.open_target(9222, "https://labs.google/fx/tools/flow")

    assert result == target
    assert requests == [
        ("http://127.0.0.1:9222/json/new?https://labs.google/fx/tools/flow", "PUT", 5.0),
    ]
    assert clients[0].websocket_url == "ws://127.0.0.1:9222/devtools/browser/browser-1"
    assert clients[0].commands == [
        ("Target.createTarget", {"url": "https://labs.google/fx/tools/flow"}, 8.0),
    ]


def test_open_target_raises_cdp_error_when_browser_cdp_fallback_fails(monkeypatch):
    class FailingCDPClient:
        def __init__(self, _websocket_url):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return None

        def command(self, _method, _params=None, *, timeout=15.0):
            raise RuntimeError("browser target creation failed")

    def fake_urlopen(_request, *, timeout):
        raise OSError("404")

    monkeypatch.setattr(chrome_cdp, "urlopen", fake_urlopen)
    monkeypatch.setattr(
        chrome_cdp,
        "browser_websocket_url",
        lambda port: f"ws://127.0.0.1:{port}/devtools/browser/browser-1",
    )
    monkeypatch.setattr(chrome_cdp, "CDPClient", FailingCDPClient)

    with pytest.raises(chrome_cdp.CDPError, match="provider"):
        chrome_cdp.open_target(9222, "https://labs.google/fx/tools/flow")
