from __future__ import annotations

from backend.services import video_phase2


class _Settings:
    timeout_seconds = 20


def test_phase2_codex_timeout_keeps_production_floor_when_env_is_too_low(monkeypatch):
    monkeypatch.setenv("VOICEBOX_PHASE2_CODEX_TIMEOUT", "20")

    assert video_phase2._phase2_codex_timeout(_Settings()) == video_phase2.PHASE2_DEFAULT_CODEX_TIMEOUT_SECONDS
