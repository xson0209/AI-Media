"""Contract tests for News Video speech modes.

These tests intentionally exercise the pure prompt composer so they do not
need a configured database or provider credentials.
"""

from backend.services.video_speech import build_provider_prompt, word_budget_warning


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
