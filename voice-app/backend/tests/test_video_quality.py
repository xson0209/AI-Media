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
    PlatformRetentionDataset as DBPlatformRetentionDataset,
    VideoClipGenerationItem as DBVideoClipGenerationItem,
    VideoInspirationHandoff as DBVideoInspirationHandoff,
    VideoInspirationJob as DBVideoInspirationJob,
    VideoProject as DBVideoProject,
    VideoProjectContextSnapshot as DBVideoProjectContextSnapshot,
    VideoProjectMemoryCard as DBVideoProjectMemoryCard,
    VideoProjectTargetTimelineBeat as DBVideoProjectTargetTimelineBeat,
    VideoQualityReport as DBVideoQualityReport,
    VideoShot as DBVideoShot,
    VideoShotClip as DBVideoShotClip,
    VideoShotPrompt as DBVideoShotPrompt,
    VideoSubtitle as DBVideoSubtitle,
    session as database_session,
)
from backend.services import video_quality

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

def _seed_quality_project(db, *, bad_prompt: bool = False, copy_source: bool = False) -> DBVideoProject:
    now = datetime.utcnow()
    source_phrase = "the locked door opens only when the promise is broken by the child"
    target_narration_1 = (
        source_phrase if copy_source else "A new courier hears a locked elevator answer with a promise."
    )
    target_narration_2 = "She realizes the promise protects a neighbor, then chooses to keep it."
    project = DBVideoProject(
        id="quality-project",
        title="Quality Project",
        topic="A new promise mystery for short-form retention.",
        language="vi",
        target_language="en",
        target_duration_seconds=20,
        aspect_ratio="9:16",
        voice_profile_id="voice-1",
        status="draft",
        phase="phase2",
        video_purpose="custom",
        dialogue_mode="voiceover",
        narration_density="balanced",
        script_approved=True,
        story_approved=True,
        detailed_script=f"{target_narration_1} {target_narration_2}",
        prompt_segment_count=2,
        prompt_segment_duration_seconds=10,
        micro_scenes_per_prompt=3,
        planning_status="completed",
        package_stale=False,
        created_at=now,
        updated_at=now,
    )
    db.add(project)

    job = DBVideoInspirationJob(
        id="quality-job",
        source_type="upload",
        source_platform="upload",
        original_filename="source.mp4",
        status="rewritten",
        current_step="completed",
        progress=1.0,
        target_language="en",
        transcript_text=source_phrase,
        transcript_status="completed",
        analysis_schema_version="video_analysis_package.v1",
        analysis_mode="high_quality",
        analysis_package_json={
            "schema_version": "video_analysis_package.v1",
            "shots": [{"id": "source-shot-1", "start_seconds": 0, "end_seconds": 6}],
            "transcript_segments": [{"id": "source-seg-1", "start_seconds": 0, "end_seconds": 6, "text": source_phrase}],
            "content_retention_beats": [
                {"order": 1, "role": "hook", "new_information": "A promise is hidden.", "micro_payoff": "The door answers."},
                {"order": 2, "role": "payoff", "new_information": "The promise protects someone.", "micro_payoff": "She keeps it."},
            ],
            "coverage_metrics": {"retention_beat_coverage_ratio": 1.0},
            "limitations": ["Retention is predicted from content."],
            "originality_boundaries": ["Learn the promise mechanic, do not copy characters or dialogue."],
        },
        coverage_metrics_json={"retention_beat_coverage_ratio": 1.0},
        limitations_json=["Retention is predicted from content."],
        retention_source="predicted_from_content",
        analysis_completeness="full",
        analysis_json={
            "rewrite_candidates": [
                {"title": "Elevator Promise", "hook": "An elevator answers first.", "script": target_narration_1},
                {"title": "Mailbox Promise", "hook": "A mailbox blinks back.", "script": "Different setting and emotional choice."},
                {"title": "Station Promise", "hook": "A train sign changes.", "script": "Different structure with public stakes."},
            ],
            "rewrite_review": {"critic": "independent", "best": "Elevator Promise"},
            "rewrite": {
                "title": "Quality Project",
                "big_idea": "A promise mystery becomes a choice.",
                "hook_3_5s": "A locked elevator answers before anyone speaks.",
            },
        },
        rewritten_script=f"{target_narration_1} {target_narration_2}",
        script_title="Quality Project",
        big_idea="A promise mystery becomes a choice.",
        hook="A locked elevator answers before anyone speaks.",
        created_video_project_id=project.id,
        created_at=now,
        updated_at=now,
    )
    db.add(job)

    handoff = DBVideoInspirationHandoff(
        id="quality-handoff",
        job_id=job.id,
        analysis_package_revision="video_analysis_package.v1",
        schema_version="video_inspiration_handoff.v1",
        status="consumed",
        target_language="en",
        approved_script_revision=1,
        payload_json={
            "source_observations": {
                "transcript_segments": [{"text": source_phrase}],
                "shots": [{"id": "source-shot-1"}],
            },
            "learnable_lessons": {
                "content_spine": "Promise mechanic",
                "retention_map": [
                    {"order": 1, "role": "hook", "new_information": "A promise appears.", "micro_payoff": "A response."},
                    {"order": 2, "role": "payoff", "new_information": "A choice matters.", "micro_payoff": "Protection."},
                ],
            },
            "target_content": {
                "target_audience": "Short mystery viewers",
                "video_goal": "Keep curiosity until a moral choice.",
                "content_spine": "A promise mystery becomes a choice.",
                "hook_contract": {"hook": "Elevator answers", "payoff": "She keeps the promise."},
                "approved_script": {"script": f"{target_narration_1} {target_narration_2}", "revision": 1},
            },
            "originality_boundaries": ["Learn mechanism only."],
        },
        source_blocks_json=[],
        created_project_id=project.id,
        revision=1,
        created_at=now,
        updated_at=now,
        approved_at=now,
    )
    db.add(handoff)

    for card_type, title, content in [
        ("project_identity", "Project", {"title": project.title}),
        ("video_goal", "Goal", {"value": "Keep curiosity until a moral choice."}),
        ("content_spine", "Spine", {"value": "A promise mystery becomes a choice."}),
        ("hook_and_payoff", "Hook and payoff", {"hook": "Elevator answers", "payoff": "She keeps the promise."}),
        ("approved_decision", "Approved", {"script": f"{target_narration_1} {target_narration_2}"}),
        ("source_evidence", "Evidence", {"source": "analysis package"}),
    ]:
        db.add(
            DBVideoProjectMemoryCard(
                id=f"memory-{card_type}",
                project_id=project.id,
                card_type=card_type,
                title=title,
                content_json=content,
                status="approved",
                source_type="handoff",
                source_ref_id=handoff.id,
                revision=1,
                created_at=now,
                updated_at=now,
                approved_at=now,
            )
        )

    beats = [
        ("beat-1", 1, 0.0, 10.0, "hook", "A new courier hears a locked elevator answer.", "Who is inside?", "The elevator speaks first.", "The voice asks for a promise."),
        ("beat-2", 2, 10.0, 20.0, "payoff", "She learns the promise protects a neighbor.", "Will she keep it?", "The promise is protective, not scary.", "She keeps the promise."),
    ]
    for beat_id, order, start, end, role, content, question, info, payoff in beats:
        db.add(
            DBVideoProjectTargetTimelineBeat(
                id=beat_id,
                project_id=project.id,
                handoff_id=handoff.id,
                beat_order=order,
                start_seconds=start,
                end_seconds=end,
                duration_seconds=end - start,
                role=role,
                content=content,
                viewer_question=question,
                new_information=info,
                micro_payoff=payoff,
                visual_direction="Show the elevator panel reacting to narration.",
                audio_direction="Use a soft mechanical chime under the promise.",
                evidence_refs_json=[],
                source_lesson_refs_json=[],
                revision=1,
                created_at=now,
                updated_at=now,
            )
        )

    shots = [
        ("shot-1", 1, target_narration_1, "Courier faces an elevator panel that answers."),
        ("shot-2", 2, target_narration_2, "Courier chooses to keep the neighbor promise."),
    ]
    for shot_id, order, narration, description in shots:
        db.add(
            DBVideoShot(
                id=shot_id,
                project_id=project.id,
                shot_order=order,
                duration_seconds=10.0,
                vietnamese_description=description,
                english_narration=narration,
                primary_action=description,
                purpose="Advance the promise mystery.",
                composition="Subject and object clearly separated.",
                transition_to_next="Cut on the chime.",
                micro_scenes_json=[{"order": 1, "description_vi": description}],
                status="completed",
                prompt_status="completed",
                voice_status="completed",
                subtitle_status="completed",
                audio_path=f"voice/{shot_id}.wav",
                audio_duration=8.5,
                revision=1,
                created_at=now,
                updated_at=now,
            )
        )
        prompt_text = (
            "Cinematic 4k dolly shot, beautiful lighting, shallow depth of field, dramatic camera move."
            if bad_prompt
            else f"{description} The prompt shows the new information and micro payoff from beat {order}: {narration}"
        )
        db.add(
            DBVideoShotPrompt(
                id=f"prompt-{shot_id}",
                project_id=project.id,
                shot_id=shot_id,
                version=1,
                prompt=prompt_text,
                prompt_explanation_vi=f"Prompt bám nội dung beat {order}.",
                duration_seconds=10.0,
                retention_notes="Matches target beat.",
                quality_status="passed",
                quality_check={"passed": True},
                created_at=now,
            )
        )

    db.add(
        DBVideoSubtitle(
            id="subtitle-1",
            project_id=project.id,
            status="completed",
            subtitle_path="subtitles/subtitle.srt",
            format="srt",
            cues_json=json.dumps(
                [
                    {"index": 1, "shot_id": "shot-1", "shot_order": 1, "start_seconds": 0.0, "end_seconds": 8.5, "text": target_narration_1},
                    {"index": 2, "shot_id": "shot-2", "shot_order": 2, "start_seconds": 8.5, "end_seconds": 17.0, "text": target_narration_2},
                ]
            ),
            revision=1,
            created_at=now,
            updated_at=now,
        )
    )
    db.add(
        DBVideoProjectContextSnapshot(
            id="context-1",
            project_id=project.id,
            task_type="story",
            context_json={"candidate_context": True},
            source_refs_json=[],
            created_at=now,
        )
    )
    db.commit()
    return project

def test_quality_tables_are_created(db):
    tables = set(inspect(database_session.engine).get_table_names())

    assert "video_quality_reports" in tables
    assert "platform_retention_datasets" in tables

def test_quality_report_blocks_camera_prompt_without_content_and_does_not_create_provider_records(db):
    project = _seed_quality_project(db, bad_prompt=True)
    clip_items_before = db.query(DBVideoClipGenerationItem).count()
    clips_before = db.query(DBVideoShotClip).count()

    report = video_quality.run_project_quality_report(
        project.id,
        models.VideoQualityRunRequest(),
        db,
    )

    assert report is not None
    assert report.overall_status == "blocked"
    assert report.rubric_json["content_weight"] == 0.75
    assert report.rubric_json["presentation_weight"] == 0.25
    assert report.sections_json["prompt_quality"]["status"] == "blocked"
    assert any(
        "prompt_missing_beat_content" in json.dumps(item, ensure_ascii=False)
        for item in report.blocking_errors_json or []
    )
    assert db.query(DBVideoClipGenerationItem).count() == clip_items_before
    assert db.query(DBVideoShotClip).count() == clips_before

def test_quality_report_becomes_stale_when_input_revision_changes(db):
    project = _seed_quality_project(db)
    report = video_quality.run_project_quality_report(project.id, models.VideoQualityRunRequest(), db)
    assert report is not None
    assert report.overall_status in {"passed", "needs_review"}

    shot = db.query(DBVideoShot).filter(DBVideoShot.id == "shot-1").one()
    shot.revision += 1
    shot.english_narration = "A changed narration requires quality to run again."
    shot.updated_at = datetime.utcnow()
    db.commit()

    latest = video_quality.get_latest_project_report(project.id, db)

    assert latest is not None
    assert latest.overall_status == "stale"
    assert any("stale" in json.dumps(item, ensure_ascii=False) for item in latest.warnings_json or [])

def test_retention_dataset_normalizes_and_uses_correlation_language(db):
    project = _seed_quality_project(db)

    dataset = video_quality.create_project_retention_dataset(
        project.id,
        models.PlatformRetentionDatasetCreateRequest(
            platform="youtube",
            video_duration_seconds=20,
            source_type="manual",
            data_points=[
                models.PlatformRetentionDataPoint(timestamp_seconds=0, retention_percent=100),
                models.PlatformRetentionDataPoint(duration_percent=50, retention_percent=82),
                models.PlatformRetentionDataPoint(duration_percent=75, retention_percent=58, rewatch_rate=9),
            ],
        ),
        db,
    )

    assert dataset is not None
    assert dataset.normalized_points_json[1]["timestamp_seconds"] == 10.0
    assert dataset.normalized_points_json[2]["duration_percent"] == 75.0
    assert dataset.linked_findings_json
    finding_text = json.dumps(dataset.linked_findings_json, ensure_ascii=False)
    assert "có khả năng liên quan" in finding_text
    assert "không khẳng định" in finding_text

def test_originality_blocks_near_source_copy(db):
    project = _seed_quality_project(db, copy_source=True)

    report = video_quality.run_project_quality_report(project.id, models.VideoQualityRunRequest(), db)

    assert report is not None
    assert report.overall_status == "blocked"
    assert report.sections_json["originality_quality"]["status"] == "blocked"
    assert any(
        "originality_copy_risk" in json.dumps(item, ensure_ascii=False)
        for item in report.blocking_errors_json or []
    )

def test_quality_override_preserves_blocking_history(db):
    project = _seed_quality_project(db, bad_prompt=True)
    report = video_quality.run_project_quality_report(project.id, models.VideoQualityRunRequest(), db)
    assert report is not None
    assert report.blocking_errors_json

    overridden = video_quality.override_report(
        report.id,
        models.VideoQualityOverrideRequest(
            status="needs_review",
            reason="Người dùng đã kiểm tra thủ công và muốn tiếp tục thử nghiệm nội bộ.",
            overridden_by="tester",
        ),
        db,
    )

    assert overridden is not None
    assert overridden.overall_status == "needs_review"
    assert overridden.blocking_errors_json == report.blocking_errors_json
    assert overridden.override_history_json
    assert overridden.override_history_json[0]["blocking_errors_preserved"]

def test_content_weight_below_sixty_requires_special_confirmation(db):
    project = _seed_quality_project(db)

    with pytest.raises(ValueError):
        models.VideoQualityRunRequest(
            rubric=models.VideoQualityRubricConfig(content_weight=0.55, presentation_weight=0.45)
        )

    report = video_quality.run_project_quality_report(
        project.id,
        models.VideoQualityRunRequest(
            rubric=models.VideoQualityRubricConfig(
                content_weight=0.55,
                presentation_weight=0.45,
                special_content_weight_confirmed=True,
            )
        ),
        db,
    )
    assert report is not None
    assert report.rubric_json["content_weight"] == 0.55
