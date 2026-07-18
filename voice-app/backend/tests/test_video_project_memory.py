import asyncio
import json
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
    ArtifactDependencySnapshot as DBArtifactDependencySnapshot,
    ArtifactStaleEvent as DBArtifactStaleEvent,
    VideoInspirationHandoff as DBVideoInspirationHandoff,
    VideoInspirationJob as DBVideoInspirationJob,
    VideoProject as DBVideoProject,
    VideoSeries as DBVideoSeries,
    session as database_session,
)
from backend.services import video_inspiration, video_project_memory


@pytest.fixture
def db(tmp_path):
    config.set_data_dir(tmp_path)
    database.init_db()
    session = database_session.SessionLocal()
    try:
        yield session
    finally:
        session.close()
        database_session.engine.dispose()


def _seed_inspiration_job(db, *, analysis_package=True, script=True) -> DBVideoInspirationJob:
    now = datetime.utcnow()
    package = None
    if analysis_package:
        package = {
            "schema_version": "video_analysis_package.v1",
            "content_retention_beats": [
                {
                    "order": 1,
                    "start_seconds": 40.0,
                    "end_seconds": 45.0,
                    "role": "source_hook",
                    "why_continue": "The source creates a question before revealing the answer.",
                    "viewer_question_before": "What is behind the door?",
                    "new_information": "A new target story opens with a locked door.",
                    "micro_payoff": "The door moves but does not open yet.",
                    "evidence_refs": [{"type": "shot", "id": "source-shot-1"}],
                },
                {
                    "order": 2,
                    "start_seconds": 100.0,
                    "end_seconds": 108.0,
                    "role": "development",
                    "why_continue": "Each beat answers one loop and opens another.",
                    "viewer_question_before": "Will the clue matter?",
                    "new_information": "The clue belongs to a different character.",
                    "micro_payoff": "The clue changes ownership.",
                    "evidence_refs": [{"type": "audio_event", "id": "source-audio-1"}],
                },
            ],
            "shots": [
                {"id": "source-shot-1", "start_seconds": 40.0, "end_seconds": 45.0},
            ],
            "transcript_segments": [
                {
                    "id": "source-transcript-1",
                    "start_seconds": 40.0,
                    "end_seconds": 43.0,
                    "text": "Original source transcript that must stay evidence only.",
                }
            ],
            "audio_events": [{"id": "source-audio-1", "start_seconds": 41.0, "event_type": "silence_drop"}],
            "on_screen_text_events": [{"id": "source-text-1", "start_seconds": 42.0, "text": "WAIT"}],
            "coverage_metrics": {"retention_beat_coverage_ratio": 1.0},
            "limitations": ["Retention is predicted from content, not platform analytics."],
            "originality_boundaries": ["Learn pacing, do not copy the source shot sequence."],
            "visual_grammar": {"camera": "tight hook, wider payoff"},
            "audio_grammar": {"sound": "silence drop before a reveal"},
        }
    job = DBVideoInspirationJob(
        id="handoff-job",
        source_type="upload",
        source_platform="upload",
        original_filename="source.mp4",
        status="rewritten",
        current_step="completed",
        progress=1.0,
        target_language="vi",
        transcript_text="Original source transcript that must stay evidence only.",
        visual_summary="Observed source uses a dark door and a silence drop.",
        analysis_schema_version="video_analysis_package.v1",
        analysis_package_json=package,
        analysis_package_path="video_inspiration/handoff-job/package.json" if package else None,
        coverage_metrics_json={"retention_beat_coverage_ratio": 1.0} if package else None,
        limitations_json=["Retention is predicted from content, not platform analytics."] if package else None,
        retention_source="predicted_from_content",
        analysis_completeness="full" if package else "not_started",
        analysis_json={
            "main_idea_vi": "Build a new mystery about a hidden promise.",
            "hook_vi": "A locked door shakes without a hand touching it.",
            "rewrite": {
                "target_audience": "Người xem thích truyện bí ẩn ngắn.",
                "big_idea": "A promise hidden behind a door becomes a choice.",
                "hook_3_5s": "The new story opens on a shaking locked door.",
                "viewer_question": "Who is opening the door from the other side?",
                "curiosity_gap": "The door moves before the character arrives.",
                "retention_plan": {
                    "payoff": "The door was protecting a promise, not hiding a threat.",
                    "beat_curve": ["hook", "clue", "choice"],
                },
                "audio_direction": "Use a silence drop and one wooden knock under narration.",
                "ai_video_source_blocks": {
                    "target_audience": "Người xem thích truyện bí ẩn ngắn.",
                    "character_notes": "New character, new door, no copied dialogue.",
                    "style_notes": "Learn the reveal rhythm, not the source shots.",
                    "must_have": "New hook, new clue, new payoff.",
                    "avoid": "Do not copy the source character or transcript.",
                },
            },
        },
        rewritten_script="Approved target narration for the new AI Video.",
        script_title="The Door Promise",
        big_idea="A promise hidden behind a door becomes a choice.",
        hook="The new story opens on a shaking locked door.",
        created_at=now,
        updated_at=now,
    )
    if not script:
        job.rewritten_script = ""
    db.add(job)
    db.commit()
    db.refresh(job)
    return job


def test_project_memory_tables_are_created(db):
    tables = set(inspect(database_session.engine).get_table_names())

    assert "video_inspiration_handoffs" in tables
    assert "video_project_memory_cards" in tables
    assert "video_project_target_timeline_beats" in tables
    assert "video_project_context_snapshots" in tables


def test_handoff_keeps_structured_payload_and_compatible_source_blocks(db):
    job = _seed_inspiration_job(db)

    handoff = video_project_memory.create_or_update_handoff(job, db, status="ready_for_review")

    assert handoff.status == "ready_for_review"
    assert handoff.schema_version == video_project_memory.HANDOFF_SCHEMA_VERSION
    assert handoff.payload_json["target_content"]["approved_script"]["script"] == (
        "Approved target narration for the new AI Video."
    )
    assert handoff.payload_json["source_observations"]["transcript_segments"][0]["text"] == (
        "Original source transcript that must stay evidence only."
    )
    assert handoff.payload_json["learnable_lessons"]["retention_map"][0]["role"] == "source_hook"

    blocks = video_project_memory.source_blocks_from_payload(handoff.payload_json)
    rough_script = next(block for block in blocks if block.block_type == "rough_script")
    transcript = next(block for block in blocks if block.block_type == "transcript")
    assert "Approved target narration for the new AI Video" in rough_script.content
    assert "source_transcript_is_evidence_only" in rough_script.content
    assert "source_transcript_for_evidence_only" in transcript.content


def test_video_handoff_payload_builds_canonical_source_package(db):
    job = _seed_inspiration_job(db)
    handoff = video_project_memory.create_or_update_handoff(job, db, status="ready_for_review")

    package = video_project_memory.source_package_from_payload(handoff.payload_json)
    block_types = [block.block_type for block in package.blocks]

    assert package.schema_version == "source_package.v1"
    assert package.source_kind == "video_inspiration_handoff"
    assert package.source_ref_id == job.id
    assert package.fingerprint
    assert {"idea", "rough_script", "character_notes", "style_notes", "must_have", "avoid"} <= set(block_types)

def test_handoff_requires_analysis_package_and_approved_script(db):
    missing_package = _seed_inspiration_job(db, analysis_package=False)
    with pytest.raises(video_project_memory.VideoProjectMemoryError) as exc:
        video_project_memory.create_or_update_handoff(missing_package, db)
    assert exc.value.error_code == "VIDEO_INSPIRATION_ANALYSIS_PACKAGE_REQUIRED"

    db.delete(missing_package)
    db.commit()
    missing_script = _seed_inspiration_job(db, script=False)
    with pytest.raises(video_project_memory.VideoProjectMemoryError) as script_exc:
        video_project_memory.create_or_update_handoff(missing_script, db)
    assert script_exc.value.error_code == "VIDEO_INSPIRATION_APPROVED_SCRIPT_REQUIRED"


def test_create_project_from_handoff_builds_memory_timeline_and_manual_project(db, monkeypatch):
    job = _seed_inspiration_job(db)
    auto_run_calls = []

    async def fake_start_auto_run(*args, **kwargs):
        auto_run_calls.append((args, kwargs))
        raise AssertionError("auto-run should not start by default")

    monkeypatch.setattr(video_inspiration.video_auto_runs, "start_auto_run", fake_start_auto_run)

    result = asyncio.run(
        video_inspiration.create_ai_video_project(
            job.id,
            models.VideoInspirationCreateProjectRequest(start_full_materials=False, mode="review_gated"),
            db,
        )
    )

    assert result is not None
    assert result.auto_run is None
    assert auto_run_calls == []

    project = db.query(DBVideoProject).filter(DBVideoProject.id == result.project.id).one()
    assert project.series_id is None

    handoff = db.query(DBVideoInspirationHandoff).filter(DBVideoInspirationHandoff.job_id == job.id).one()
    assert handoff.status == "consumed"
    assert handoff.created_project_id == project.id

    memory = video_project_memory.list_project_memory(project.id, db)
    card_types = {card.card_type for card in memory.items}
    assert "target_audience" in card_types
    assert "approved_decision" in card_types
    assert "source_evidence" in card_types

    timeline = video_project_memory.list_target_timeline(project.id, db)
    assert timeline.total == 2
    assert [beat.start_seconds for beat in timeline.items] == [0.0, 10.0]
    assert timeline.items[0].start_seconds != 40.0
    assert timeline.items[1].start_seconds != 100.0
    assert timeline.items[-1].end_seconds == 20.0

    voice_context = video_project_memory.compile_context(
        project.id,
        models.VideoProjectContextCompileRequest(task_type="voice"),
        db,
    )
    context_text = json.dumps(voice_context.context_json, ensure_ascii=False)
    assert "Approved target narration for the new AI Video" in context_text
    assert "Original source transcript that must stay evidence only" not in context_text
    assert voice_context.context_json["rules"]["voice_and_subtitle_use_approved_target_narration"] is True


def test_series_project_records_task_dependencies_and_stales_target_narration_only(db, monkeypatch):
    series = DBVideoSeries(
        id="series-memory",
        title="Memory Series",
        series_mode="video_story_only",
        character_bible="Fixed character traits stay canonical.",
        style_bible="Minimal mystery style.",
        revision=3,
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow(),
    )
    db.add(series)
    db.commit()
    job = _seed_inspiration_job(db)
    monkeypatch.setattr(video_inspiration.video_auto_runs, "start_auto_run", lambda *args, **kwargs: None)

    result = asyncio.run(
        video_inspiration.create_ai_video_project(
            job.id,
            models.VideoInspirationCreateProjectRequest(
                start_full_materials=False,
                mode="review_gated",
                series_id=series.id,
            ),
            db,
        )
    )
    assert result is not None

    project = db.query(DBVideoProject).filter(DBVideoProject.id == result.project.id).one()
    assert project.series_id == series.id

    handoff = db.query(DBVideoInspirationHandoff).filter(DBVideoInspirationHandoff.job_id == job.id).one()
    snapshots = (
        db.query(DBArtifactDependencySnapshot)
        .filter(
            DBArtifactDependencySnapshot.series_id == series.id,
            DBArtifactDependencySnapshot.dependency_type == "video_inspiration_handoff",
            DBArtifactDependencySnapshot.dependency_id == handoff.id,
        )
        .all()
    )
    artifact_types = {row.artifact_type for row in snapshots}
    assert {
        "video_project",
        "video_story",
        "video_shot",
        "video_prompt",
        "scene_voice",
        "subtitle",
        "package",
    }.issubset(artifact_types)
    assert {row.dependency_scope for row in snapshots if row.artifact_type in {"scene_voice", "subtitle"}} == {
        "narration",
        "timing",
    }

    video_inspiration.update_script(
        job.id,
        models.VideoInspirationScriptUpdate(
            rewritten_script="Approved target narration changed for voice and subtitle.",
            script_title="The Door Promise",
            big_idea="A promise hidden behind a door becomes a choice.",
            hook="The new story opens on a shaking locked door.",
        ),
        db,
    )

    db.refresh(project)
    db.refresh(handoff)
    assert handoff.status == "stale"
    assert project.planning_status == "stale"
    assert project.package_stale is True

    events = (
        db.query(DBArtifactStaleEvent)
        .filter(DBArtifactStaleEvent.series_id == series.id)
        .all()
    )
    event_types = {event.artifact_type for event in events}
    assert {"scene_voice", "subtitle", "package"}.issubset(event_types)
    assert "video_prompt" not in event_types
    assert all("Ká»‹ch báº£n Ä‘Ã­ch" in event.reason_vi for event in events)


def test_source_transcript_edit_does_not_stale_target_voice_or_subtitle(db, monkeypatch):
    series = DBVideoSeries(
        id="series-transcript",
        title="Transcript Series",
        series_mode="video_story_only",
        revision=1,
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow(),
    )
    db.add(series)
    db.commit()
    job = _seed_inspiration_job(db)
    monkeypatch.setattr(video_inspiration.video_auto_runs, "start_auto_run", lambda *args, **kwargs: None)

    result = asyncio.run(
        video_inspiration.create_ai_video_project(
            job.id,
            models.VideoInspirationCreateProjectRequest(
                start_full_materials=False,
                mode="review_gated",
                series_id=series.id,
            ),
            db,
        )
    )
    assert result is not None

    video_inspiration.update_transcript(
        job.id,
        models.VideoInspirationTranscriptUpdate(
            transcript_text="Corrected source transcript for evidence only.",
        ),
        db,
    )

    events = (
        db.query(DBArtifactStaleEvent)
        .filter(DBArtifactStaleEvent.series_id == series.id)
        .all()
    )
    assert events == []
