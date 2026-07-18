"""SSRF-safe URL validation for Comic Series Analysis (tasks 3.1-3.3, 3.6, 3.11).

Every outbound fetch — the user URL, every redirect, every image/subresource
URL, and every request a browser fallback generates — must pass through
:func:`validate_url` and, once DNS resolves, :func:`check_resolved_addresses`.
Peer verification after connect (:func:`assert_peer_allowed`) closes the
DNS-rebinding window.

The policy is deliberately explicit and testable: ports, carrier-grade NAT,
userinfo and URL redaction each have their own function so tests assert
concrete behavior rather than a vague "transport phù hợp".
"""

from __future__ import annotations

import ipaddress
import socket
from dataclasses import dataclass
from urllib.parse import urlsplit, urlunsplit

from .config import NetworkPolicy, get_config
from .contracts import ComicAnalysisError

# Carrier-grade NAT range (RFC 6598) — not covered by is_private.
_CGN_V4 = ipaddress.ip_network("100.64.0.0/10")
# Cloud metadata endpoints (link-local already blocked, but be explicit).
_CLOUD_METADATA = {
    ipaddress.ip_address("169.254.169.254"),
    ipaddress.ip_address("fd00:ec2::254"),
}
# Sensitive query parameter names to redact when storing/logging URLs.
_SENSITIVE_QUERY_KEYS = {
    "token",
    "access_token",
    "auth",
    "authorization",
    "key",
    "api_key",
    "apikey",
    "signature",
    "sig",
    "password",
    "pwd",
    "secret",
    "session",
    "sessionid",
}


@dataclass(frozen=True)
class ValidatedUrl:
    """A URL that passed structural validation, ready for DNS resolution."""

    url: str
    scheme: str
    host: str
    port: int
    is_ip_literal: bool


def _blocked(error_code: str, detail: str) -> ComicAnalysisError:
    return ComicAnalysisError(error_code, detail, status_code=400)


def is_blocked_address(ip: ipaddress._BaseAddress) -> bool:
    """Return True if an IP must never be connected to (SSRF guard)."""
    if ip in _CLOUD_METADATA:
        return True
    if ip.version == 4 and ip in _CGN_V4:
        return True
    if (
        ip.is_private
        or ip.is_loopback
        or ip.is_link_local
        or ip.is_multicast
        or ip.is_unspecified
        or ip.is_reserved
    ):
        return True
    # IPv4-mapped IPv6 (e.g. ::ffff:127.0.0.1) — unwrap and re-check.
    if ip.version == 6:
        mapped = getattr(ip, "ipv4_mapped", None)
        if mapped is not None and is_blocked_address(mapped):
            return True
    return False


def _port_allowed(port: int, policy: NetworkPolicy) -> bool:
    return port in policy.allowed_ports


def validate_url(raw_url: str, *, policy: NetworkPolicy | None = None) -> ValidatedUrl:
    """Validate a URL's structure before any network activity (task 3.1).

    Rejects non-http(s) schemes, userinfo, disallowed ports, and IP literals
    that point at non-public addresses. Does not resolve DNS — call
    :func:`check_resolved_addresses` after resolution for hostnames.
    """
    policy = policy or get_config().network
    try:
        parts = urlsplit(raw_url.strip())
    except ValueError as exc:  # malformed
        raise _blocked("COMIC_URL_INVALID", f"URL không phân tích được: {exc}") from exc

    scheme = parts.scheme.lower()
    if scheme not in policy.allowed_schemes:
        raise _blocked("COMIC_URL_INVALID", f"Scheme {scheme!r} không được phép.")

    if parts.username or parts.password:
        raise _blocked("COMIC_URL_HAS_USERINFO", "URL chứa thông tin đăng nhập.")

    host = parts.hostname
    if not host:
        raise _blocked("COMIC_URL_INVALID", "URL thiếu host.")

    port = parts.port if parts.port is not None else (443 if scheme == "https" else 80)
    if not _port_allowed(port, policy):
        raise _blocked("COMIC_URL_PORT_BLOCKED", f"Cổng {port} không được phép.")

    is_ip_literal = False
    try:
        ip = ipaddress.ip_address(host)
        is_ip_literal = True
        if is_blocked_address(ip):
            raise _blocked("COMIC_URL_BLOCKED", "Địa chỉ IP không công khai.")
    except ValueError:
        # It's a hostname; DNS resolution is checked separately.
        pass

    return ValidatedUrl(
        url=raw_url.strip(),
        scheme=scheme,
        host=host,
        port=port,
        is_ip_literal=is_ip_literal,
    )


def resolve_host(host: str, port: int) -> list[ipaddress._BaseAddress]:
    """Resolve a hostname to all its IPv4/IPv6 addresses."""
    try:
        infos = socket.getaddrinfo(host, port, proto=socket.IPPROTO_TCP)
    except socket.gaierror as exc:
        raise _blocked("COMIC_URL_INVALID", f"Không phân giải được host: {host}") from exc
    addresses: list[ipaddress._BaseAddress] = []
    for info in infos:
        sockaddr = info[4]
        addresses.append(ipaddress.ip_address(sockaddr[0]))
    return addresses


def check_resolved_addresses(addresses: list[ipaddress._BaseAddress]) -> None:
    """Ensure every resolved address is public (task 3.2).

    A hostname that resolves to *any* blocked address is rejected — this
    prevents a public name from smuggling in a private A/AAAA record.
    """
    if not addresses:
        raise _blocked("COMIC_URL_INVALID", "Host không có địa chỉ IP.")
    for ip in addresses:
        if is_blocked_address(ip):
            raise _blocked("COMIC_URL_BLOCKED", "Host trỏ tới địa chỉ không công khai.")


def assert_peer_allowed(peer_ip: str) -> None:
    """Verify the actual connected peer address (task 3.3, DNS rebinding).

    Called after the socket connects. Even if DNS passed the earlier check,
    the address we actually connected to must still be public.
    """
    ip = ipaddress.ip_address(peer_ip)
    if is_blocked_address(ip):
        raise _blocked("COMIC_URL_BLOCKED", "Peer thực tế trỏ tới địa chỉ không công khai.")


def validate_and_resolve(raw_url: str, *, policy: NetworkPolicy | None = None) -> ValidatedUrl:
    """Structural validation + DNS resolution check in one call."""
    validated = validate_url(raw_url, policy=policy)
    if not validated.is_ip_literal:
        addresses = resolve_host(validated.host, validated.port)
        check_resolved_addresses(addresses)
    return validated


def redact_url(raw_url: str) -> str:
    """Strip userinfo and sensitive query params for storage/logging (task 3.6).

    Keeps host, path and non-sensitive query so provenance stays useful, but
    never persists credentials or tokens.
    """
    try:
        parts = urlsplit(raw_url)
    except ValueError:
        return "<invalid-url>"

    # Rebuild netloc without userinfo.
    netloc = parts.hostname or ""
    if parts.port:
        netloc = f"{netloc}:{parts.port}"

    query = parts.query
    if query:
        kept = []
        for pair in query.split("&"):
            key = pair.split("=", 1)[0]
            if key.lower() in _SENSITIVE_QUERY_KEYS:
                kept.append(f"{key}=<redacted>")
            else:
                kept.append(pair)
        query = "&".join(kept)

    return urlunsplit((parts.scheme, netloc, parts.path, query, ""))  # drop fragment


__all__ = [
    "ValidatedUrl",
    "assert_peer_allowed",
    "check_resolved_addresses",
    "is_blocked_address",
    "redact_url",
    "resolve_host",
    "validate_and_resolve",
    "validate_url",
]
