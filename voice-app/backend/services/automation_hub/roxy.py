"""RoxyBrowser Desktop Local API adapter."""

from __future__ import annotations

from typing import Any
from urllib.parse import urlparse

import httpx

from .config import get_config


class RoxyApiError(RuntimeError):
    def __init__(self, message: str, error_code: str = "ROXY_API_ERROR"):
        super().__init__(message)
        self.error_code = error_code


class RoxyLocalApiClient:
    def __init__(
        self,
        *,
        api_key: str,
        api_host: str | None = None,
        transport: httpx.AsyncBaseTransport | None = None,
    ):
        if not api_key.strip():
            raise RoxyApiError("Thiếu RoxyBrowser API key.", "ROXY_API_KEY_REQUIRED")
        cfg = get_config()
        self.api_key = api_key
        self.api_host = (api_host or cfg.roxy_api_host).rstrip("/")
        parsed = urlparse(self.api_host)
        if parsed.scheme not in {"http", "https"} or parsed.hostname not in {"127.0.0.1", "localhost", "::1"}:
            raise RoxyApiError("Roxy Local API chỉ được phép dùng địa chỉ loopback.", "ROXY_API_HOST_UNSAFE")
        self.timeout = httpx.Timeout(cfg.roxy_timeout_seconds)
        self.transport = transport

    async def _request(self, method: str, path: str, **kwargs) -> Any:
        try:
            async with httpx.AsyncClient(timeout=self.timeout, transport=self.transport) as client:
                response = await client.request(
                    method,
                    f"{self.api_host}{path}",
                    headers={"token": self.api_key, "Content-Type": "application/json"},
                    **kwargs,
                )
                response.raise_for_status()
                payload = response.json()
        except (httpx.ConnectError, httpx.ConnectTimeout) as exc:
            raise RoxyApiError(
                "Không kết nối được RoxyBrowser. Hãy mở RoxyBrowser Desktop và bật Local API.",
                "ROXY_DESKTOP_UNAVAILABLE",
            ) from exc
        except httpx.HTTPStatusError as exc:
            if exc.response.status_code in {401, 403}:
                raise RoxyApiError(
                    "RoxyBrowser từ chối API key. Hãy tạo key mới và cấu hình lại.",
                    "ROXY_API_KEY_INVALID",
                ) from exc
            raise RoxyApiError(
                f"RoxyBrowser Local API trả lỗi HTTP {exc.response.status_code}.",
                "ROXY_API_REQUEST_FAILED",
            ) from exc
        except (httpx.HTTPError, ValueError) as exc:
            raise RoxyApiError(
                "RoxyBrowser Local API trả lỗi. Hãy kiểm tra API key, port và trạng thái API.",
                "ROXY_API_REQUEST_FAILED",
            ) from exc
        if not isinstance(payload, dict):
            raise RoxyApiError(
                "RoxyBrowser trả response không đúng định dạng.",
                "ROXY_API_RESPONSE_INVALID",
            )
        try:
            code = int(payload.get("code", -1))
        except (TypeError, ValueError) as exc:
            raise RoxyApiError(
                "RoxyBrowser trả response không đúng định dạng.",
                "ROXY_API_RESPONSE_INVALID",
            ) from exc
        if code != 0:
            raise RoxyApiError(
                "RoxyBrowser từ chối request. Hãy kiểm tra API key và dữ liệu profile.",
                "ROXY_API_REJECTED",
            )
        return payload.get("data")

    async def health(self) -> dict[str, Any]:
        data = await self._request("GET", "/health")
        return {"ok": True, "data": data if isinstance(data, dict) else {}}

    async def workspaces(self, page_index: int = 1, page_size: int = 100) -> dict[str, Any]:
        data = await self._request(
            "GET",
            "/browser/workspace",
            params={"page_index": page_index, "page_size": page_size},
        )
        return data if isinstance(data, dict) else {"rows": [], "total": 0}

    async def profiles(
        self,
        workspace_id: int,
        *,
        project_ids: str | None = None,
        page_index: int = 1,
        page_size: int = 100,
    ) -> dict[str, Any]:
        params: dict[str, Any] = {
            "workspaceId": workspace_id,
            "page_index": page_index,
            "page_size": page_size,
        }
        if project_ids:
            params["projectIds"] = project_ids
        data = await self._request("GET", "/browser/list_v3", params=params)
        return data if isinstance(data, dict) else {"rows": [], "total": 0}

    async def open_profile(
        self,
        workspace_id: int,
        dir_id: str,
        *,
        force_open: bool = True,
        args: list[str] | None = None,
    ) -> dict[str, Any]:
        data = await self._request(
            "POST",
            "/browser/open",
            json={
                "workspaceId": workspace_id,
                "dirId": dir_id,
                "forceOpen": force_open,
                "args": list(args or []),
            },
        )
        return _safe_connection(data)

    async def close_profiles(self, dir_ids: list[str]) -> dict[str, Any]:
        results = []
        for dir_id in dir_ids:
            await self._request("POST", "/browser/close", json={"dirId": dir_id})
            results.append({"dir_id": dir_id, "closed": True})
        return {"results": results}

    async def connection_info(self, dir_ids: list[str] | None = None) -> list[dict[str, Any]]:
        params = {"dirIds": ",".join(dir_ids)} if dir_ids else None
        data = await self._request("GET", "/browser/connection_info", params=params)
        rows = data if isinstance(data, list) else []
        return [_safe_connection(row) for row in rows if isinstance(row, dict)]


def _safe_connection(data: Any) -> dict[str, Any]:
    row = data if isinstance(data, dict) else {}
    return {
        "dir_id": row.get("dirId"),
        "window_name": row.get("windowName"),
        "pid": row.get("pid"),
        "ws": row.get("ws"),
        "http": row.get("http"),
        "core_version": row.get("coreVersion"),
        "core_type": row.get("coreType"),
        "driver": row.get("driver"),
    }
