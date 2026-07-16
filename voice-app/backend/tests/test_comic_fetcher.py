"""Fetcher tests: content classification, redirect SSRF, auth outcomes, budgets."""

from __future__ import annotations

import httpx
import pytest

from backend.services.comic_series_analysis import fetcher
from backend.services.comic_series_analysis.contracts import ComicAnalysisError

PNG_MAGIC = b"\x89PNG\r\n\x1a\n" + b"\x00" * 32


def _client(handler):
    return httpx.Client(transport=httpx.MockTransport(handler), follow_redirects=False)


def test_sniff_image_formats():
    assert fetcher.sniff_image_format(PNG_MAGIC) == "png"
    assert fetcher.sniff_image_format(b"\xff\xd8\xff\xe0") == "jpeg"
    assert fetcher.sniff_image_format(b"RIFF\x00\x00\x00\x00WEBPVP8 ") == "webp"
    assert fetcher.sniff_image_format(b"\x00\x00\x00\x20ftypavif") == "avif"
    assert fetcher.sniff_image_format(b"\x00\x00\x00\x18ftypheic") == "heif"
    assert fetcher.sniff_image_format(b"<svg xmlns=") == "svg"
    assert fetcher.sniff_image_format(b"<!DOCTYPE html>") is None


def test_fetch_html(monkeypatch):
    # Bypass DNS resolution for the public test host.
    monkeypatch.setattr(fetcher.url_security, "validate_and_resolve", lambda u, policy=None: None)

    def handler(request):
        return httpx.Response(200, headers={"content-type": "text/html"}, content=b"<html><body>hi</body></html>")

    result = fetcher.fetch("https://comics.example.com/ch1", client=_client(handler))
    assert result.content_kind == "html"
    assert b"hi" in result.content


def test_fetch_direct_image(monkeypatch):
    monkeypatch.setattr(fetcher.url_security, "validate_and_resolve", lambda u, policy=None: None)

    def handler(request):
        return httpx.Response(200, headers={"content-type": "image/png"}, content=PNG_MAGIC)

    result = fetcher.fetch("https://cdn.example.com/a.png", kind="image", client=_client(handler))
    assert result.content_kind == "image"
    assert result.detected_format == "png"


def test_fetch_unsupported_content(monkeypatch):
    monkeypatch.setattr(fetcher.url_security, "validate_and_resolve", lambda u, policy=None: None)

    def handler(request):
        return httpx.Response(200, headers={"content-type": "application/pdf"}, content=b"%PDF-1.7")

    result = fetcher.fetch("https://example.com/doc.pdf", client=_client(handler))
    assert result.content_kind == "unsupported"


def test_fetch_auth_required_outcome(monkeypatch):
    monkeypatch.setattr(fetcher.url_security, "validate_and_resolve", lambda u, policy=None: None)

    def handler(request):
        return httpx.Response(401, content=b"login")

    result = fetcher.fetch("https://paywall.example.com/ch1", client=_client(handler))
    assert result.outcome_code == "authentication_required"
    assert result.content == b""


def test_fetch_access_denied_outcome(monkeypatch):
    monkeypatch.setattr(fetcher.url_security, "validate_and_resolve", lambda u, policy=None: None)

    def handler(request):
        return httpx.Response(403, content=b"denied")

    result = fetcher.fetch("https://blocked.example.com/ch1", client=_client(handler))
    assert result.outcome_code == "access_denied"


def test_redirect_to_private_blocked():
    # Real validation runs: the redirect target resolves to a private IP.
    def handler(request):
        if request.url.host == "start.example.com":
            return httpx.Response(302, headers={"location": "http://127.0.0.1/secret"})
        return httpx.Response(200, content=b"should not reach")

    import backend.services.comic_series_analysis.url_security as us
    real = us.validate_and_resolve
    calls = {"n": 0}

    def patched(url, policy=None):
        # First hop (public host) passes; the 127.0.0.1 hop is blocked by validate_url.
        return us.validate_url(url, policy=policy)

    us_orig = fetcher.url_security.validate_and_resolve
    fetcher.url_security.validate_and_resolve = patched
    try:
        with pytest.raises(ComicAnalysisError) as exc:
            fetcher.fetch("http://start.example.com/", client=_client(handler))
        assert exc.value.error_code == "COMIC_URL_BLOCKED"
    finally:
        fetcher.url_security.validate_and_resolve = us_orig


def test_too_large_rejected(monkeypatch):
    monkeypatch.setattr(fetcher.url_security, "validate_and_resolve", lambda u, policy=None: None)

    big = b"<html>" + b"x" * (200)

    def handler(request):
        return httpx.Response(200, headers={"content-type": "text/html"}, content=big)

    with pytest.raises(ComicAnalysisError) as exc:
        fetcher.fetch("https://example.com/", max_bytes=50, client=_client(handler))
    assert exc.value.error_code == "COMIC_FETCH_TOO_LARGE"
