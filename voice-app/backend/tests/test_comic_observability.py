"""Log redaction tests (task 11.5, 12.17a)."""

from __future__ import annotations

from backend.services.comic_series_analysis import observability as obs


def test_safe_event_redacts_url():
    payload = obs.safe_event("fetch", source_url="https://u:p@site.com/x?token=abc&page=2")
    assert "abc" not in payload["source_url"]
    assert "u" not in payload["source_url"].split("//")[1].split("/")[0]  # no userinfo
    assert "token=<redacted>" in payload["source_url"]


def test_safe_event_drops_secrets():
    payload = obs.safe_event("call", cookie="secret", authorization="Bearer x", prompt="long prompt")
    assert "cookie" not in payload
    assert "authorization" not in payload
    assert "prompt" not in payload


def test_safe_event_summarizes_text_and_bytes():
    payload = obs.safe_event("extract", text="x" * 5000, content=b"\x00" * 100)
    assert "len=5000" in payload["text"]
    assert "x" * 5000 not in str(payload["text"])
    assert payload["content"] == "bytes=100"


def test_short_checksum():
    payload = obs.safe_event("store", checksum="a" * 64)
    assert payload["checksum"] == "a" * 12


def test_normal_fields_pass_through():
    payload = obs.safe_event("progress", step="fetch_html", count=5, duration=1.2)
    assert payload["step"] == "fetch_html"
    assert payload["count"] == 5
    assert payload["duration"] == 1.2
