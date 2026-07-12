"""Tiny Chrome DevTools Protocol client using only the Python standard library."""

from __future__ import annotations

import base64
import hashlib
import http.client
import json
import os
import socket
import struct
import time
from dataclasses import dataclass
from typing import Any
from urllib.parse import quote, urlparse
from urllib.request import Request, urlopen

class CDPError(RuntimeError):
    """Raised when Chrome DevTools Protocol communication fails."""

@dataclass(frozen=True)
class ChromeTarget:
    id: str
    type: str
    title: str | None
    url: str | None
    web_socket_debugger_url: str

def fetch_json(url: str, *, timeout: float = 3.0) -> Any:
    try:
        with urlopen(url, timeout=timeout) as response:
            return json.loads(response.read().decode("utf-8"))
    except Exception as exc:
        raise CDPError(f"Không kết nối được Chrome DevTools tại {url}.") from exc

def wait_for_debug_port(port: int, *, timeout_seconds: float = 12.0) -> None:
    deadline = time.monotonic() + timeout_seconds
    last_error: Exception | None = None
    while time.monotonic() < deadline:
        try:
            fetch_json(f"http://127.0.0.1:{port}/json/version", timeout=1.0)
            return
        except Exception as exc:
            last_error = exc
            time.sleep(0.25)
    raise CDPError("Chrome đã mở nhưng remote debugging chưa sẵn sàng.") from last_error

def browser_websocket_url(port: int) -> str:
    payload = fetch_json(f"http://127.0.0.1:{port}/json/version")
    value = payload.get("webSocketDebuggerUrl")
    if not value:
        raise CDPError("Chrome không trả về Browser websocket endpoint.")
    return str(value)

def list_targets(port: int) -> list[ChromeTarget]:
    payload = fetch_json(f"http://127.0.0.1:{port}/json/list")
    targets: list[ChromeTarget] = []
    for item in payload if isinstance(payload, list) else []:
        ws_url = item.get("webSocketDebuggerUrl")
        if not ws_url:
            continue
        targets.append(
            ChromeTarget(
                id=str(item.get("id") or ""),
                type=str(item.get("type") or ""),
                title=item.get("title"),
                url=item.get("url"),
                web_socket_debugger_url=str(ws_url),
            )
        )
    return targets

def open_target(port: int, url: str) -> ChromeTarget:
    last_error: Exception | None = None
    for attempt in range(3):
        try:
            return _open_target_once(port, url)
        except Exception as exc:
            last_error = exc
            if attempt < 2:
                time.sleep(0.75)
    raise CDPError("Không tạo được tab Chrome mới cho provider.") from last_error

def _open_target_once(port: int, url: str) -> ChromeTarget:
    endpoint = f"http://127.0.0.1:{port}/json/new?{quote(url, safe=':/?&=%#')}"
    request = Request(endpoint, method="PUT")
    try:
        with urlopen(request, timeout=5.0) as response:
            item = json.loads(response.read().decode("utf-8"))
    except Exception as exc:
        return _open_target_via_browser_cdp(port, url, exc)
    ws_url = item.get("webSocketDebuggerUrl")
    if not ws_url:
        raise CDPError("Tab Chrome mới không có websocket endpoint.")
    return ChromeTarget(
        id=str(item.get("id") or ""),
        type=str(item.get("type") or "page"),
        title=item.get("title"),
        url=item.get("url"),
        web_socket_debugger_url=str(ws_url),
    )

def _open_target_via_browser_cdp(port: int, url: str, original_exc: Exception) -> ChromeTarget:
    try:
        with CDPClient(browser_websocket_url(port)) as client:
            result = client.command("Target.createTarget", {"url": url}, timeout=8.0)
    except Exception as exc:
        raise CDPError("Không tạo được tab Chrome mới cho provider qua CDP.") from exc

    target_id = str(result.get("targetId") or "")
    if not target_id:
        raise CDPError("Chrome không trả về targetId cho tab provider mới.") from original_exc

    deadline = time.monotonic() + 5.0
    while time.monotonic() < deadline:
        for target in list_targets(port):
            if target.id == target_id:
                return target
        time.sleep(0.2)

    raise CDPError("Tab Chrome provider mới không có websocket endpoint sau khi tạo qua CDP.") from original_exc

def close_target(port: int, target_id: str) -> bool:
    if not target_id:
        return False
    endpoint = f"http://127.0.0.1:{port}/json/close/{quote(target_id, safe='')}"
    try:
        with urlopen(endpoint, timeout=3.0) as response:
            response.read()
            return 200 <= int(response.status) < 300
    except Exception as exc:
        raise CDPError("Không đóng được tab Chrome provider.") from exc

def find_page_target(port: int, url_hint: str | None = None) -> ChromeTarget | None:
    def usable_page(target: ChromeTarget) -> bool:
        url = target.url or ""
        return target.type == "page" and not url.startswith(("devtools://", "chrome://", "chrome-extension://"))

    targets = [target for target in list_targets(port) if usable_page(target)]
    if url_hint:
        hinted = [target for target in targets if url_hint in (target.url or "")]
        if hinted:
            return hinted[0]
    return targets[0] if targets else None

class WebSocket:
    def __init__(self, url: str, *, timeout: float = 15.0):
        self.url = url
        parsed = urlparse(url)
        if parsed.scheme != "ws":
            raise CDPError(f"WebSocket URL không hỗ trợ: {url}")
        self.host = parsed.hostname or "127.0.0.1"
        self.port = int(parsed.port or 80)
        self.path = parsed.path + (f"?{parsed.query}" if parsed.query else "")
        self.timeout = timeout
        self.sock: socket.socket | None = None

    def __enter__(self) -> "WebSocket":
        self.connect()
        return self

    def __exit__(self, *_args) -> None:
        self.close()

    def connect(self) -> None:
        key = base64.b64encode(os.urandom(16)).decode("ascii")
        sock = socket.create_connection((self.host, self.port), timeout=self.timeout)
        request = (
            f"GET {self.path} HTTP/1.1\r\n"
            f"Host: {self.host}:{self.port}\r\n"
            "Upgrade: websocket\r\n"
            "Connection: Upgrade\r\n"
            f"Sec-WebSocket-Key: {key}\r\n"
            "Sec-WebSocket-Version: 13\r\n\r\n"
        ).encode("ascii")
        sock.sendall(request)
        response = b""
        while b"\r\n\r\n" not in response:
            chunk = sock.recv(4096)
            if not chunk:
                break
            response += chunk
        if b" 101 " not in response.split(b"\r\n", 1)[0]:
            sock.close()
            raise CDPError("Chrome DevTools websocket handshake thất bại.")
        self.sock = sock

    def close(self) -> None:
        if self.sock is not None:
            try:
                self.sock.close()
            finally:
                self.sock = None

    def send_text(self, text: str) -> None:
        if self.sock is None:
            raise CDPError("WebSocket chưa mở.")
        payload = text.encode("utf-8")
        header = bytearray([0x81])
        length = len(payload)
        if length < 126:
            header.append(0x80 | length)
        elif length < 65536:
            header.append(0x80 | 126)
            header.extend(struct.pack("!H", length))
        else:
            header.append(0x80 | 127)
            header.extend(struct.pack("!Q", length))
        mask = os.urandom(4)
        header.extend(mask)
        masked = bytes(byte ^ mask[index % 4] for index, byte in enumerate(payload))
        self.sock.sendall(bytes(header) + masked)

    def recv_text(self) -> str:
        while True:
            opcode, payload = self._recv_frame()
            if opcode == 0x1:
                return payload.decode("utf-8")
            if opcode == 0x8:
                raise CDPError("Chrome đã đóng websocket.")
            if opcode == 0x9:
                self._send_pong(payload)

    def _send_pong(self, payload: bytes) -> None:
        if self.sock is None:
            return
        frame = bytearray([0x8A, len(payload)])
        frame.extend(payload)
        self.sock.sendall(bytes(frame))

    def _recv_exact(self, size: int) -> bytes:
        if self.sock is None:
            raise CDPError("WebSocket chưa mở.")
        chunks = bytearray()
        while len(chunks) < size:
            chunk = self.sock.recv(size - len(chunks))
            if not chunk:
                raise CDPError("Chrome DevTools websocket mất kết nối.")
            chunks.extend(chunk)
        return bytes(chunks)

    def _recv_frame(self) -> tuple[int, bytes]:
        first, second = self._recv_exact(2)
        opcode = first & 0x0F
        masked = bool(second & 0x80)
        length = second & 0x7F
        if length == 126:
            length = struct.unpack("!H", self._recv_exact(2))[0]
        elif length == 127:
            length = struct.unpack("!Q", self._recv_exact(8))[0]
        mask = self._recv_exact(4) if masked else b""
        payload = self._recv_exact(length) if length else b""
        if masked:
            payload = bytes(byte ^ mask[index % 4] for index, byte in enumerate(payload))
        return opcode, payload

class CDPClient:
    def __init__(self, websocket_url: str):
        self.websocket_url = websocket_url
        self._next_id = 1
        self._socket = WebSocket(websocket_url)

    def __enter__(self) -> "CDPClient":
        self._socket.connect()
        return self

    def __exit__(self, *_args) -> None:
        self._socket.close()

    def command(self, method: str, params: dict[str, Any] | None = None, *, timeout: float = 15.0) -> dict[str, Any]:
        command_id = self._next_id
        self._next_id += 1
        payload = {"id": command_id, "method": method}
        if params is not None:
            payload["params"] = params
        self._socket.send_text(json.dumps(payload, separators=(",", ":")))
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            message = json.loads(self._socket.recv_text())
            if message.get("id") != command_id:
                continue
            if "error" in message:
                raise CDPError(f"CDP {method} lỗi: {message['error']}")
            return message.get("result") or {}
        raise CDPError(f"CDP {method} quá thời gian chờ.")

    def evaluate(self, expression: str, *, await_promise: bool = False, timeout: float = 15.0) -> Any:
        result = self.command(
            "Runtime.evaluate",
            {
                "expression": expression,
                "awaitPromise": await_promise,
                "returnByValue": True,
                "userGesture": True,
            },
            timeout=timeout,
        )
        remote = result.get("result") or {}
        if "value" in remote:
            return remote["value"]
        if remote.get("type") == "undefined":
            return None
        return remote

    def navigate(self, url: str, *, timeout: float = 30.0) -> None:
        self.command("Page.enable", timeout=timeout)
        self.command("Runtime.enable", timeout=timeout)
        self.command("Page.navigate", {"url": url}, timeout=timeout)

    def set_download_behavior(self, download_dir: str) -> None:
        self.command(
            "Browser.setDownloadBehavior",
            {"behavior": "allow", "downloadPath": download_dir, "eventsEnabled": True},
            timeout=5.0,
        )

def sha256_short(value: str | None, *, length: int = 24) -> str | None:
    if not value:
        return None
    digest = hashlib.sha256(value.encode("utf-8")).hexdigest()
    return digest[:length]

def raw_http_get(host: str, port: int, path: str, *, timeout: float = 3.0) -> tuple[int, str]:
    conn = http.client.HTTPConnection(host, port, timeout=timeout)
    try:
        conn.request("GET", path)
        response = conn.getresponse()
        return response.status, response.read().decode("utf-8", errors="replace")
    finally:
        conn.close()
