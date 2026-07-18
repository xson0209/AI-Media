from __future__ import annotations

import sys
import types
from datetime import datetime

import pytest
from sqlalchemy import inspect

if "torch" not in sys.modules:
    torch_stub = types.ModuleType("torch")

    class _Tensor:
        def element_size(self):
            return 0

        def nelement(self):
            return 0

    torch_stub.Tensor = _Tensor
    torch_stub.load = lambda *args, **kwargs: None
    torch_stub.save = lambda *args, **kwargs: None
    sys.modules["torch"] = torch_stub

from backend import config, database, models
from backend.database import (
    Generation as DBGeneration,
    VideoProject as DBVideoProject,
    VideoPublishingMetadata as DBVideoPublishingMetadata,
    VideoShot as DBVideoShot,
    VideoShotPrompt as DBVideoShotPrompt,
    VideoSourceBlock as DBVideoSourceBlock,
    VideoSubtitle as DBVideoSubtitle,
    session as database_session,
)
from backend.services import (
    video_planning_pool,
    video_projects,
    video_publishing_metadata,
    video_storage,
    video_subtitles,
    video_voice,
)


@pytest.fixture
def db(tmp_path):
    config.set_data_dir(tmp_path)
    database.init_db()
    video_planning_pool.reset_for_tests()
    session = database_session.SessionLocal()
    try:
        yield session
    finally:
        session.close()
        video_planning_pool.reset_for_tests()
        database_session.engine.dispose()


def _platform_payload(label: str, *, title: str | None = None) -> dict:
    return {
        "title": title or f"{label} hook rieng",
        "description": f"{label} description bam sat cau chuyen, co ngu canh va CTA phu hop.",
        "hashtags": [f"#{label.lower()}", "#AIVideo", "#Story"],
        "thumbnail_prompt": (
            f"{label} thumbnail prompt: real subject from the video, clear emotion, high contrast, "
            "safe area for optional text, no watermark, no random letters, no unprovided logos."
        ),
    }


def _all_payload(*, target_language: str = "vi") -> dict:
    return {
        "target_language": target_language,
        "platforms": {
            "youtube": _platform_payload("YouTube"),
            "tiktok": _platform_payload("TikTok"),
            "facebook": _platform_payload("Facebook"),
        },
    }


def _seed_phase2_project(db, *, project_id: str = "project-publishing", target_language: str = "vi"):
    project = DBVideoProject(
        id=project_id,
        title="Ten quan ly noi bo",
        topic="Cau chuyen ve mot cau thu nho lap nguoc tran dau trong mua.",
        language="vi",
        target_language=target_language,
        phase="phase2",
        status="draft",
        planning_status="completed",
        story_approved=True,
        aspect_ratio="9:16",
        video_purpose="education",
        call_to_action_style="follow",
        story_strategy="Mo bang ty so cang thang, giu cu sut quyet dinh toi cuoi.",
        detailed_script="Cau thu nho binh tinh buoc toi cham phat den va ghi ban quyet dinh.",
        retention_plan_json={"hook": "bang ty so 0-1 trong mua", "payoff": "cu sut quyet dinh"},
        visual_style="cinematic rain stadium, warm highlight, expressive stickman",
        continuity_bible="Nhan vat cau thu nho mac ao do, giu dong nhat moi segment.",
    )
    db.add(project)
    db.flush()
    db.add(
        DBVideoSourceBlock(
            project_id=project.id,
            block_type="idea",
            sort_order=1,
            content="Mot cau thu nho vuot qua ap luc trong tran chung ket duoi mua.",
        )
    )
    shot = DBVideoShot(
        project_id=project.id,
        shot_order=1,
        duration_seconds=4.0,
        vietnamese_description="Cau thu nho nhin bang ty so trong mua lon.",
        english_narration="The small player breathes slowly, then steps forward for one final shot.",
        primary_action="The player prepares a decisive kick.",
        purpose="hook",
        status="ready",
        prompt_status="completed",
        voice_status="missing",
        retention_json={"hook": "rain scoreboard", "viewer_question": "Can he score?"},
    )
    db.add(shot)
    db.flush()
    db.add(
        DBVideoShotPrompt(
            project_id=project.id,
            shot_id=shot.id,
            version=1,
            prompt="Vertical cinematic sports scene, small red-shirt player, rain, scoreboard pressure.",
            prompt_explanation_vi="Prompt bam sat hook va continuity.",
            negative_prompt="no watermark, no random text",
            duration_seconds=4.0,
            aspect_ratio="9:16",
            quality_status="passed",
            continuity_notes="Keep the red shirt and rainy stadium.",
            retention_notes="Hold the scoreboard tension.",
            transition_notes="Cut on the player stepping forward.",
            sound_design_notes="Rain ambience under narration.",
        )
    )
    db.commit()
    db.refresh(project)
    db.refresh(shot)
    return project, shot


def test_video_publishing_metadata_table_and_missing_response(db):
    tables = set(inspect(database_session.engine).get_table_names())
    assert "video_publishing_metadata" in tables

    project, _shot = _seed_phase2_project(db)

    response = video_publishing_metadata.get_publishing_metadata(project.id, db)

    assert response is not None
    assert response.status == "missing"
    assert response.project_id == project.id
    assert response.target_language == "vi"
    assert response.platforms == {}


def test_map_codex_payload_accepts_three_platforms_and_normalizes_hashtags():
    project = DBVideoProject(title="Internal", topic="Topic", target_language="vi")
    payload = _all_payload()
    payload["platforms"]["youtube"]["hashtags"] = ["bongda", "#AI", "#ai", "story"]

    mapped = video_publishing_metadata.map_codex_payload(
        payload,
        project=project,
        requested_platform="all",
        fingerprint="fingerprint-1",
    )

    assert set(mapped) == {"youtube", "tiktok", "facebook"}
    assert mapped["youtube"]["hashtags"] == ["#bongda", "#AI", "#story"]
    assert mapped["youtube"]["input_fingerprint"] == "fingerprint-1"
    assert mapped["tiktok"]["title"] != mapped["youtube"]["title"]


def test_map_codex_payload_rejects_unsupported_platform_and_invalid_types():
    project = DBVideoProject(title="Internal", topic="Topic", target_language="vi")
    unsupported = {
        "target_language": "vi",
        "youtube": _platform_payload("YouTube"),
        "tiktok": _platform_payload("TikTok"),
        "messenger": _platform_payload("Messenger"),
    }

    with pytest.raises(video_publishing_metadata.VideoPublishingMetadataError) as unsupported_error:
        video_publishing_metadata.map_codex_payload(
            unsupported,
            project=project,
            requested_platform="all",
            fingerprint="fingerprint-1",
        )

    assert unsupported_error.value.error_code == "VIDEO_PUBLISHING_METADATA_UNSUPPORTED_PLATFORM"

    invalid = _all_payload()
    invalid["platforms"]["youtube"]["title"] = {"text": "not a string"}

    with pytest.raises(video_publishing_metadata.VideoPublishingMetadataError) as invalid_error:
        video_publishing_metadata.map_codex_payload(
            invalid,
            project=project,
            requested_platform="all",
            fingerprint="fingerprint-1",
        )

    assert invalid_error.value.error_code == "VIDEO_PUBLISHING_METADATA_FIELD_TYPE_INVALID"

def test_map_codex_payload_rejects_copied_platform_variants():
    project = DBVideoProject(title="Internal", topic="Topic", target_language="vi")
    copied = {
        "target_language": "vi",
        "platforms": {
            "youtube": _platform_payload("Same"),
            "tiktok": _platform_payload("Same"),
            "facebook": _platform_payload("Same"),
        },
    }

    with pytest.raises(video_publishing_metadata.VideoPublishingMetadataError) as exc_info:
        video_publishing_metadata.map_codex_payload(
            copied,
            project=project,
            requested_platform="all",
            fingerprint="fingerprint-1",
        )

    assert exc_info.value.error_code == "VIDEO_PUBLISHING_METADATA_PLATFORM_VARIANTS_DUPLICATED"


def test_generate_single_platform_preserves_other_platform_payloads(db, monkeypatch):
    project, _shot = _seed_phase2_project(db)
    responses = iter(
        [
            _all_payload(),
            {
                "target_language": "vi",
                "youtube": _platform_payload("YouTubeUpdated", title="YouTube hook da tao lai"),
            },
        ]
    )
    calls: list[str] = []

    def fake_structured_codex(_db, _project, _prompt, _schema, *, step_name):
        calls.append(step_name)
        return next(responses)

    monkeypatch.setattr(video_publishing_metadata.video_phase2, "_run_structured_codex", fake_structured_codex)

    first = video_publishing_metadata.generate_publishing_metadata(
        project.id,
        models.VideoPublishingMetadataGenerateRequest(platform="all", force=True),
        db,
    )
    second = video_publishing_metadata.generate_publishing_metadata(
        project.id,
        models.VideoPublishingMetadataGenerateRequest(platform="youtube", force=True),
        db,
    )

    row = db.query(DBVideoPublishingMetadata).filter(DBVideoPublishingMetadata.project_id == project.id).one()
    assert calls == ["publishing_metadata_generation", "publishing_metadata_generation_youtube"]
    assert first is not None
    assert second is not None
    assert row.status == "completed"
    assert row.revision == 2
    assert row.platforms_json["youtube"]["title"] == "YouTube hook da tao lai"
    assert row.platforms_json["youtube"]["revision"] == 2
    assert row.platforms_json["tiktok"]["title"] == "TikTok hook rieng"
    assert row.platforms_json["facebook"]["title"] == "Facebook hook rieng"


def test_generation_failure_keeps_previous_payload_and_records_failed_status(db, monkeypatch):
    project, _shot = _seed_phase2_project(db)
    responses = iter(
        [
            _all_payload(),
            {"target_language": "vi", "youtube": {"title": {"text": "bad"}}},
            {"target_language": "vi", "youtube": {"title": {"text": "still bad"}}},
            {"target_language": "vi", "youtube": {"title": {"text": "bad again"}}},
        ]
    )

    def fake_structured_codex(_db, _project, _prompt, _schema, *, step_name):
        return next(responses)

    monkeypatch.setattr(video_publishing_metadata.video_phase2, "_run_structured_codex", fake_structured_codex)
    video_publishing_metadata.generate_publishing_metadata(
        project.id,
        models.VideoPublishingMetadataGenerateRequest(platform="all", force=True),
        db,
    )
    old_payload = dict(
        db.query(DBVideoPublishingMetadata)
        .filter(DBVideoPublishingMetadata.project_id == project.id)
        .one()
        .platforms_json
    )
    old_revision = (
        db.query(DBVideoPublishingMetadata)
        .filter(DBVideoPublishingMetadata.project_id == project.id)
        .one()
        .revision
    )

    with pytest.raises(video_publishing_metadata.VideoPublishingMetadataError):
        video_publishing_metadata.generate_publishing_metadata(
            project.id,
            models.VideoPublishingMetadataGenerateRequest(platform="youtube", force=True),
            db,
        )

    row = db.query(DBVideoPublishingMetadata).filter(DBVideoPublishingMetadata.project_id == project.id).one()
    assert row.status == "failed"
    assert row.error_code == "VIDEO_PUBLISHING_METADATA_FIELD_TYPE_INVALID"
    assert row.revision == old_revision
    assert row.platforms_json == old_payload


def test_metadata_status_marks_fingerprint_mismatch_stale(db, monkeypatch):
    project, _shot = _seed_phase2_project(db)
    monkeypatch.setattr(
        video_publishing_metadata.video_phase2,
        "_run_structured_codex",
        lambda _db, _project, _prompt, _schema, *, step_name: _all_payload(),
    )
    video_publishing_metadata.generate_publishing_metadata(
        project.id,
        models.VideoPublishingMetadataGenerateRequest(platform="all", force=True),
        db,
    )

    project.topic = "Nguon noi dung da doi nen metadata cu khong con khop."
    project.updated_at = datetime.utcnow()
    db.commit()

    summary = video_publishing_metadata.metadata_status_summary(project.id, db)
    row = db.query(DBVideoPublishingMetadata).filter(DBVideoPublishingMetadata.project_id == project.id).one()

    assert summary["status"] == "stale"
    assert summary["ready"] is False
    assert row.status == "stale"
    assert row.stale is True


def test_voice_profile_change_does_not_stale_publishing_metadata(db, monkeypatch):
    project, _shot = _seed_phase2_project(db)
    monkeypatch.setattr(
        video_publishing_metadata.video_phase2,
        "_run_structured_codex",
        lambda _db, _project, _prompt, _schema, *, step_name: _all_payload(),
    )
    video_publishing_metadata.generate_publishing_metadata(
        project.id,
        models.VideoPublishingMetadataGenerateRequest(platform="all", force=True),
        db,
    )

    project.voice_profile_id = "voice-profile-only-change"
    project.updated_at = datetime.utcnow()
    db.commit()

    summary = video_publishing_metadata.metadata_status_summary(project.id, db)
    row = db.query(DBVideoPublishingMetadata).filter(DBVideoPublishingMetadata.project_id == project.id).one()

    assert summary["status"] == "completed"
    assert summary["ready"] is True
    assert row.stale is False


def test_reset_generated_data_deletes_publishing_metadata(db, monkeypatch):
    project, _shot = _seed_phase2_project(db)
    monkeypatch.setattr(
        video_publishing_metadata.video_phase2,
        "_run_structured_codex",
        lambda _db, _project, _prompt, _schema, *, step_name: _all_payload(),
    )
    video_publishing_metadata.generate_publishing_metadata(
        project.id,
        models.VideoPublishingMetadataGenerateRequest(platform="all", force=True),
        db,
    )

    response = video_projects.reset_generated_data(project.id, db)

    assert response is not None
    assert response.deleted_counts["publishing_metadata"] == 1
    assert db.query(DBVideoPublishingMetadata).filter(DBVideoPublishingMetadata.project_id == project.id).count() == 0


def test_subtitle_timeline_advances_through_silent_shots(db):
    project = DBVideoProject(
        id="project-subtitle-timeline",
        title="Subtitle timeline",
        topic="Timeline",
        phase="phase2",
        target_language="en",
        aspect_ratio="9:16",
    )
    db.add(project)
    silent = DBVideoShot(
        project_id=project.id,
        shot_order=1,
        duration_seconds=2.5,
        english_narration="",
        status="ready",
        prompt_status="completed",
    )
    narrated = DBVideoShot(
        project_id=project.id,
        shot_order=2,
        duration_seconds=3.0,
        english_narration="The player finally takes the shot.",
        status="ready",
        prompt_status="completed",
        voice_status="completed",
        audio_path="artifacts/projects/project-subtitle-timeline/voice/shot-2.wav",
        audio_duration=3.0,
    )
    db.add_all([silent, narrated])
    db.commit()

    response = video_subtitles.generate_subtitle(project.id, db)

    assert response.status == "completed"
    assert len(response.cues) == 1
    assert response.cues[0].shot_id == narrated.id
    assert response.cues[0].start_seconds == 2.5
    assert response.cues[0].end_seconds == 5.5


def test_sync_shot_voice_status_marks_project_subtitle_stale_when_audio_changes(db):
    project = DBVideoProject(
        id="project-voice-sync",
        title="Voice sync",
        topic="Voice sync",
        phase="phase2",
        target_language="en",
        aspect_ratio="9:16",
    )
    shot = DBVideoShot(
        id="shot-voice-sync",
        project_id=project.id,
        shot_order=1,
        duration_seconds=3.0,
        english_narration="A line that already had audio.",
        status="ready",
        prompt_status="completed",
        voice_status="completed",
        subtitle_status="completed",
        generation_id="generation-voice-sync",
        audio_path="old.wav",
        audio_duration=1.0,
    )
    subtitle_path = video_storage.get_project_subdir(project.id, "subtitles") / "subtitle.srt"
    subtitle_path.write_text("1\n00:00:00,000 --> 00:00:01,000\nOld line\n", encoding="utf-8")
    subtitle = DBVideoSubtitle(
        project_id=project.id,
        status="completed",
        subtitle_path=video_storage.to_artifact_storage_path(subtitle_path),
        cues_json="[]",
    )
    generation = DBGeneration(
        id="generation-voice-sync",
        profile_id="profile-sync",
        text="A line that already had audio.",
        language="en",
        status="completed",
        audio_path="new.wav",
        duration=2.0,
        source="ai_video_shot",
    )
    db.add_all([project, shot, subtitle, generation])
    db.commit()

    response = video_voice.sync_shot_voice_status(project.id, shot.id, db)

    db.refresh(shot)
    db.refresh(subtitle)
    assert response is not None
    assert response.voice_status == "completed"
    assert shot.subtitle_status == "stale"
    assert subtitle.status == "stale"
    assert video_subtitles.get_subtitle_download(project.id, db) is None
