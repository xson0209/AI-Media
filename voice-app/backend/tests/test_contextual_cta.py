from backend.services import video_purpose
from backend.services.video_phase2 import ShotBreakdownPlan, _purpose_generation_instructions


def test_normalize_cta_action_uses_one_canonical_value():
    assert video_purpose.normalize_cta_action("commenting") == "comment"
    assert video_purpose.normalize_cta_action("share_video") == "share"
    assert video_purpose.normalize_cta_action("unknown") == "none"
    assert video_purpose.normalize_cta_action(None) == "none"


def test_purpose_context_includes_contextual_cta_action():
    lines = video_purpose.purpose_context_lines(
        video_purpose="global_short",
        target_language="en",
        dialogue_mode="voiceover",
        narration_density="balanced",
        call_to_action_style="direct",
        cta_action="comment",
    )
    assert any("CTA action: comment" in line for line in lines)


def test_shot_breakdown_schema_carries_cta_action():
    plan = ShotBreakdownPlan.model_validate(
        {
            "cta_action": "like",
            "shots": [
                {
                    "scene_order": 1,
                    "shot_order": 1,
                }
            ],
        }
    )
    assert plan.cta_action == "like"
