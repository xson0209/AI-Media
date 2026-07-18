"""SSRF and URL-redaction tests for Comic Series Analysis (tasks 3.11, 12.2, 12.17a)."""

from __future__ import annotations

import ipaddress

import pytest

from backend.services.comic_series_analysis import url_security as us
from backend.services.comic_series_analysis.contracts import ComicAnalysisError


@pytest.mark.parametrize(
    "url,code",
    [
        ("ftp://example.com/x", "COMIC_URL_INVALID"),
        ("file:///etc/passwd", "COMIC_URL_INVALID"),
        ("javascript:alert(1)", "COMIC_URL_INVALID"),
        ("http://user:pass@example.com/", "COMIC_URL_HAS_USERINFO"),
        ("http://example.com:22/", "COMIC_URL_PORT_BLOCKED"),
        ("http://example.com:3306/", "COMIC_URL_PORT_BLOCKED"),
    ],
)
def test_structural_rejections(url, code):
    with pytest.raises(ComicAnalysisError) as exc:
        us.validate_url(url)
    assert exc.value.error_code == code


@pytest.mark.parametrize(
    "url",
    [
        "http://127.0.0.1/",
        "http://10.0.0.5/",
        "http://192.168.1.1/",
        "http://169.254.169.254/latest/meta-data/",
        "http://[::1]/",
        "http://[fe80::1]/",
        "http://100.64.0.1/",  # carrier-grade NAT
        "http://0.0.0.0/",
    ],
)
def test_ip_literal_blocked(url):
    with pytest.raises(ComicAnalysisError) as exc:
        us.validate_url(url)
    assert exc.value.error_code in {"COMIC_URL_BLOCKED", "COMIC_URL_INVALID"}


def test_public_ip_allowed():
    v = us.validate_url("https://93.184.216.34/")  # example.com's historical IP
    assert v.is_ip_literal
    assert v.port == 443


def test_is_blocked_address_matrix():
    blocked = [
        "127.0.0.1", "10.1.2.3", "192.168.0.1", "172.16.0.1",
        "169.254.169.254", "100.64.0.1", "::1", "fe80::1", "0.0.0.0",
        "224.0.0.1",  # multicast
        "::ffff:127.0.0.1",  # IPv4-mapped loopback
    ]
    for ip in blocked:
        assert us.is_blocked_address(ipaddress.ip_address(ip)), ip
    allowed = ["8.8.8.8", "1.1.1.1", "93.184.216.34", "2606:2800:220:1::1"]
    for ip in allowed:
        assert not us.is_blocked_address(ipaddress.ip_address(ip)), ip


def test_check_resolved_addresses_blocks_private():
    with pytest.raises(ComicAnalysisError) as exc:
        us.check_resolved_addresses([ipaddress.ip_address("10.0.0.1")])
    assert exc.value.error_code == "COMIC_URL_BLOCKED"
    # A mix with one private address is still rejected.
    with pytest.raises(ComicAnalysisError):
        us.check_resolved_addresses(
            [ipaddress.ip_address("8.8.8.8"), ipaddress.ip_address("127.0.0.1")]
        )


def test_assert_peer_allowed_dns_rebinding():
    us.assert_peer_allowed("8.8.8.8")  # ok
    with pytest.raises(ComicAnalysisError) as exc:
        us.assert_peer_allowed("127.0.0.1")
    assert exc.value.error_code == "COMIC_URL_BLOCKED"


def test_redact_url_strips_userinfo_and_tokens():
    redacted = us.redact_url("https://user:secret@site.com/a?token=abc123&page=2#frag")
    assert "user" not in redacted
    assert "secret" not in redacted
    assert "abc123" not in redacted
    assert "token=<redacted>" in redacted
    assert "page=2" in redacted
    assert "#frag" not in redacted


def test_redact_url_keeps_host_and_path():
    redacted = us.redact_url("http://comics.example.com/series/ch-1")
    assert redacted == "http://comics.example.com/series/ch-1"
