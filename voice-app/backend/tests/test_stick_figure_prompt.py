"""Prompt contracts for true (non-anatomical) stick-figure characters."""

from types import SimpleNamespace

from backend.services import video_phase2


def test_stick_figure_prompt_gets_anatomy_lock_without_rewriting_requested_3d_style():
    prompt = "A 3D stick figure wearing a brown hat walks through an ancient temple."

    rendered = video_phase2._render_safe_video_prompt_text(prompt)

    assert "Strict stick-figure anatomy lock" in rendered
    assert "simple round head" in rendered
    assert "uniform thin rod arms and legs" in rendered
    assert "no human hands" in rendered
    # The normal render contract still applies: 3D describes rendering, not
    # permission to add human anatomy.
    assert "high-quality stylized 3D cinematic animation" in rendered


def test_vietnamese_stick_figure_request_gets_negative_anatomy_constraints():
    prompt = "Người que đội mũ nâu đeo ba lô chạy qua cánh cổng phát sáng."

    rendered = video_phase2._render_safe_video_prompt_text(prompt)
    negative = video_phase2._render_safe_video_negative_prompt_text("", prompt)

    assert "Strict stick-figure anatomy lock" in rendered
    assert "no human anatomy" in negative
    assert "no hands" in negative
    assert "no fingers" in negative
    assert "no feet" in negative
    assert "no toes" in negative


def test_ordinary_character_prompt_does_not_receive_stick_figure_lock():
    prompt = "A stylized 3D explorer with human hands opens a map."

    rendered = video_phase2._render_safe_video_prompt_text(prompt)
    negative = video_phase2._render_safe_video_negative_prompt_text("", prompt)

    assert "Strict stick-figure anatomy lock" not in rendered
    assert "no human anatomy" not in negative


def test_stick_figure_constraints_are_idempotent_when_provider_already_includes_them():
    prompt = (
        "A stickman stands still. Strict stick-figure anatomy lock: the character must remain a true "
        "non-anatomical stick figure in every frame."
    )
    negative = video_phase2._STICK_FIGURE_NEGATIVE_RULE

    rendered = video_phase2._render_safe_video_prompt_text(prompt)
    rendered_negative = video_phase2._render_safe_video_negative_prompt_text(negative, prompt)

    assert rendered.count("Strict stick-figure anatomy lock") == 1
    assert video_phase2._STICK_FIGURE_PROMPT_RULE in rendered
    assert video_phase2._render_safe_video_prompt_text(rendered) == rendered
    assert rendered_negative.count("no human anatomy") == 1


def test_project_style_requests_are_available_to_segment_prefix():
    project = SimpleNamespace(
        visual_style="Minimal 3D animation",
        style_bible="Người que đầu tròn, tay chân là que mảnh; không giải phẫu người.",
        continuity_bible="",
        topic="Phiêu lưu trong đền cổ",
    )

    assert video_phase2._project_requests_stick_figure(project) is True


def test_project_lock_survives_when_provider_omits_stick_figure_wording():
    project = SimpleNamespace(
        title="Stickman temple adventure",
        visual_style="Cinematic 3D animation",
        style_bible="",
        continuity_bible="",
        topic="Ancient mystery",
    )
    payload = {
        "prompts": [
            {
                "shot_order": 1,
                "prompt": "A simple dark character opens an ancient map.",
            }
        ]
    }

    normalized = video_phase2._normalize_video_prompt_pack_payload(payload, project)
    item = normalized["prompts"][0]

    assert "Strict stick-figure anatomy lock" in item["prompt"]
    assert "no human anatomy" in item["negative_prompt"]


def test_unaccented_vietnamese_and_stick_person_terms_are_detected():
    assert video_phase2._stick_figure_requested("Hoat hinh nguoi que 3D") is True
    assert video_phase2._stick_figure_requested("A stick person explores a cave") is True
