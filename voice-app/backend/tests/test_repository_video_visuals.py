from __future__ import annotations

from backend.services import video_phase2, video_source_visuals


def test_preserve_source_prompt_bypasses_3d_and_keeps_text_rule():
    prompt = video_phase2._render_safe_video_prompt_text("Zoom into the README command", preserve_source=True)
    assert video_source_visuals.PROMPT_RULE in prompt
    assert "stylized 3D" not in prompt
    negative = video_phase2._render_safe_video_negative_prompt_text("", preserve_source=True)
    assert "no AI redrawing" in negative

