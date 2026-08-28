"""Contract tests for News Video speech modes.

These tests intentionally exercise the pure prompt composer so they do not
need a configured database or provider credentials.
"""

from types import SimpleNamespace
from backend.services.video_speech import (
    build_provider_prompt, word_budget_warning, speech_mode_for,
    effective_speech_source, audio_policy_for,
)
from backend.services.video_phase2 import speech_prompt_quality


def test_native_modes_include_exact_line():
    cues = [{"speaker_name": "Phóng viên", "text": "Tin mới hôm nay"}]
    for mode in ("veo_narration", "veo_dialogue"):
        result = build_provider_prompt("A newsroom", mode, cues, "blurred text")
        assert "Tin mới hôm nay" in result["provider_prompt"]
        assert "NEGATIVE PROMPT" in result["provider_prompt"]


def test_voicebox_context_forbids_spoken_audio():
    result = build_provider_prompt("A newsroom", "voicebox_co_context", [{"text": "Xin chào"}])
    assert "must be silent" in result["audio_contract"]
    assert "Xin chào" in result["audio_contract"]


def test_silent_modes_do_not_require_lines():
    for mode in ("voicebox_khong_context", "none"):
        result = build_provider_prompt("A newsroom", mode, [{"text": "Không đọc"}])
        assert "No speech" in result["audio_contract"]


def test_word_budget_warns_without_truncating():
    warning = word_budget_warning("một hai ba bốn năm sáu", 1)
    assert warning and "rút ngắn hoặc chia shot" in warning

def test_resolver_precedence_and_legacy_fallback():
    project = SimpleNamespace(speech_source="veo_narration", target_language="en", dialogue_mode="voiceover")
    shot = SimpleNamespace(speech_source_override="none")
    assert speech_mode_for(project, shot) == "none"
    assert effective_speech_source(project, shot) == "project_audio"
    assert speech_mode_for(SimpleNamespace(speech_source=None, target_language="vi"), SimpleNamespace(speech_source_override=None)) is None
    assert effective_speech_source(SimpleNamespace(speech_source=None, target_language="vi")) == "veo_native"

def test_audio_policy_is_derived_from_mode():
    for mode, dialogue, audio, tts in [
        ("veo_narration", "voiceover", "clip_only", False),
        ("veo_dialogue", "visible_character", "clip_only", False),
        ("voicebox_co_context", "voiceover", "voiceover", True),
        ("none", "none", "clip_only", False),
    ]:
        policy = audio_policy_for(SimpleNamespace(speech_source=mode, dialogue_mode="voiceover"))
        assert policy["dialogue_mode"] == dialogue and policy["clip_audio_mode"] == audio and policy["requires_tts"] is tts

def test_speech_gate_blocks_missing_exact_line():
    project = SimpleNamespace(speech_source="veo_narration", target_language="vi")
    shot = SimpleNamespace(speech_source_override=None, speech_cues_json=[{"text": "Câu chính xác"}], english_narration="")
    blocked = speech_prompt_quality(project, shot, "visual only")
    assert blocked["needs_review"] is True
    assert speech_prompt_quality(project, shot, "visual Câu chính xác")["passed"] is True
