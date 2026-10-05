import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from pydantic import ValidationError

from backend.services import content_profile


def test_options_endpoint_returns_registry():
    from backend.routes.ai_video import router as ai_video_router

    app = FastAPI()
    app.include_router(ai_video_router)
    response = TestClient(app).get("/ai-video/content-profile/options")

    assert response.status_code == 200
    payload = response.json()
    assert payload["version"] == content_profile.CONTENT_PROFILE_VERSION
    assert {item["key"] for item in payload["genres"]} >= {"kids_rescue", "kids_stem"}


def test_legacy_educational_purpose_maps_to_educational_genre():
    profile = content_profile.resolve_content_profile(
        video_purpose_value="educational_explainer",
        target_duration_seconds=90,
    )

    assert profile["content_objective"] == "educate"
    assert profile["content_genre"] == "educational_explainer"
    assert profile["format_profile"] == "explainer_90s"


def test_pydantic_rejects_unknown_content_genre():
    from backend import models

    with pytest.raises(ValidationError):
        models.VideoProjectCreate(topic="x", content_genre="not-a-genre")


def test_duration_inference_supports_short_and_long_formats():
    assert content_profile.infer_format_profile(15) == "short_15s"
    assert content_profile.infer_format_profile(30) == "short_30s"
    assert content_profile.infer_format_profile(60) == "short_60s"
    assert content_profile.infer_format_profile(180) == "narrative_3m"
    assert content_profile.infer_format_profile(600) == "long_form"


def test_kids_profile_overrides_unsafe_values_and_has_guidance():
    profile = content_profile.resolve_content_profile(
        content_genre="kids_rescue",
        audience_age_band="adults",
        safety_policy="adult",
        made_for_kids=False,
        target_duration_seconds=120,
    )

    assert profile["made_for_kids"] is True
    assert profile["safety_policy"] == "kids_strict"
    assert profile["audience_age_band"] == "kids_6_9"
    lines = content_profile.profile_context_lines(profile)
    assert any("tối đa hai bước" in line for line in lines)
    assert any("nguy hiểm dễ bắt chước" in line for line in lines)


def test_every_profile_includes_content_first_contract():
    profile = content_profile.resolve_content_profile(
        content_genre="product_ad",
        target_duration_seconds=30,
    )

    lines = content_profile.profile_context_lines(profile)
    text = "\n".join(lines)

    assert "Content-first generation guidance:" in text
    assert "một audience cụ thể" in text
    assert "một CTA chính" in text
    assert "Content-first review checks:" in text
    assert "Claim, ví dụ và asset có nguồn/quyền dùng" in text


def test_options_payload_exposes_four_kids_templates():
    payload = content_profile.options_payload()
    keys = {item["key"] for item in payload["genres"]}
    assert {"kids_educational", "kids_rescue", "kids_stem", "kids_song"} <= keys


def test_phase2_context_includes_resolved_kids_contract(tmp_path):
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker

    from backend.database.models import Base, VideoProject, VideoSourceBlock
    from backend.services import video_phase2

    engine = create_engine(f"sqlite:///{tmp_path / 'content-profile.db'}")
    Base.metadata.create_all(engine)
    db = sessionmaker(bind=engine)()
    project = VideoProject(
        id="kids-project",
        title="Cầu Cầu Vồng bị gãy",
        topic="Đội xe robot sửa cầu an toàn",
        language="vi",
        target_language="vi",
        video_purpose="educational_explainer",
        content_genre="kids_rescue",
        audience_age_band="kids_6_9",
        format_profile="kids_2m",
        distribution_platform="youtube_kids",
        interaction_mode="pause_and_choose",
        safety_policy="kids_strict",
        made_for_kids=True,
        target_duration_seconds=120,
        aspect_ratio="16:9",
        status="draft",
        script_approved=False,
        package_stale=False,
    )
    db.add(project)
    db.add(VideoSourceBlock(id="source-1", project_id=project.id, block_type="idea", sort_order=1, content=project.topic))
    db.commit()

    try:
        context = video_phase2.normalize_phase2_codex_context(project, db)
        text = "\n".join(context["content_profile_context_lines"])
        assert context["content_profile"]["content_genre"] == "kids_rescue"
        assert "0:00–0:10" in text
        assert "Made for kids: yes" in text
    finally:
        db.close()
        engine.dispose()


def test_delete_project_removes_compiled_context_snapshot(tmp_path, monkeypatch):
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker

    from backend import models
    from backend.database.models import Base, VideoProjectContextSnapshot
    from backend.services import video_projects

    engine = create_engine(f"sqlite:///{tmp_path / 'delete-project.db'}")
    Base.metadata.create_all(engine)
    db = sessionmaker(bind=engine)()
    monkeypatch.setattr(video_projects.video_storage, "get_project_dir", lambda _project_id: tmp_path)
    monkeypatch.setattr(video_projects.video_storage, "remove_project_artifacts", lambda _project_id: None)
    monkeypatch.setattr(video_projects.video_provider_storage, "cleanup_project_downloads", lambda _project_id: None)

    try:
        project = video_projects.create_project(
            models.VideoProjectCreate(topic="Delete context regression", phase="phase2"),
            db,
        )
        db.add(
            VideoProjectContextSnapshot(
                id="context-to-delete",
                project_id=project.id,
                task_type="story",
                context_json={"test": True},
            )
        )
        db.commit()

        assert video_projects.delete_project(project.id, db) is True
        assert db.query(VideoProjectContextSnapshot).filter_by(project_id=project.id).count() == 0
    finally:
        db.close()
        engine.dispose()
