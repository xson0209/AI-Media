"""Regression checks from dependency registration to persisted artifact state."""

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from backend import models
from backend.database import (
    ArtifactDependencySnapshot,
    ArtifactStaleEvent,
    Base,
    VideoPackageExport,
    VideoProject,
    VideoRenderJob,
    VideoScene,
    VideoSeries,
    VideoShot,
    VideoShotPrompt,
    VideoSubtitle,
)
from backend.services import series_references, video_longform_workflow, video_project_memory
from backend.services.video_planning import VideoPlanningValidationError


@pytest.fixture
def db():
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    with Session(engine, autoflush=False) as session:
        yield session
    engine.dispose()


def _artifacts(db, project_id="project"):
    if db.get(VideoSeries, "series") is None:
        db.add(VideoSeries(id="series", title="Series"))
    project = VideoProject(
        id=project_id,
        series_id="series",
        title=project_id,
        topic="Topic",
        phase="phase2",
        target_language="en",
        story_approved=True,
        script_approved=True,
        planning_status="ready",
    )
    scene = VideoScene(
        id=f"{project_id}-scene",
        project_id=project_id,
        dialogue="Scene narration",
        prompt_status="ready",
        voice_status="completed",
        subtitle_status="ready",
        approved=True,
    )
    shot = VideoShot(
        id=f"{project_id}-shot",
        project_id=project_id,
        scene_id=scene.id,
        english_narration="Narration",
        status="ready",
        prompt_status="ready",
        voice_status="completed",
        subtitle_status="ready",
        locked=True,
    )
    prompt = VideoShotPrompt(
        id=f"{project_id}-prompt",
        project_id=project_id,
        scene_id=scene.id,
        shot_id=shot.id,
        prompt="Visual prompt",
        quality_status="ready",
    )
    subtitle = VideoSubtitle(id=f"{project_id}-subtitle", project_id=project_id, status="completed")
    package = VideoPackageExport(id=f"{project_id}-package", project_id=project_id, status="completed")
    render = VideoRenderJob(id=f"{project_id}-render", project_id=project_id, status="completed")
    db.add_all([project, scene, shot, prompt, subtitle, package, render])
    db.commit()
    return project, scene, shot, prompt, subtitle, package, render


def _record_handoff(db, project_id="project"):
    video_project_memory.record_project_dependency(project_id, "video_inspiration_handoff", "handoff", 1, db)
    db.commit()


def _change(db, scope, **kwargs):
    return series_references.mark_dependency_stale(
        "series",
        dependency_type="video_inspiration_handoff",
        dependency_id="handoff",
        changed_scope=scope,
        old_revision=1,
        new_revision=2,
        reason_vi="Nguồn đã đổi",
        db=db,
        **kwargs,
    )


@pytest.mark.parametrize("legacy", [False, True])
def test_story_state_updates_real_artifacts_and_revokes_approval(db, legacy):
    project, scene, shot, prompt, _, package, render = _artifacts(db)
    other = _artifacts(db, "unrelated")
    _record_handoff(db)
    if legacy:
        for snapshot in db.query(ArtifactDependencySnapshot).all():
            snapshot.metadata_json = {
                key: value for key, value in snapshot.metadata_json.items() if key != "target_scope"
            }
        db.commit()

    events = _change(db, "story_state")
    db.expire_all()

    assert events.total == 3
    assert project.planning_status == "stale"
    assert project.story_approved is False
    assert project.script_approved is False
    assert shot.status == shot.prompt_status == shot.subtitle_status == "stale"
    assert scene.prompt_status == prompt.quality_status == "stale"
    assert shot.voice_status == "completed"
    assert shot.locked is True  # Manual content locks are preserved.
    assert project.package_stale is True
    assert package.stale is True
    assert render.stale is True
    assert other[0].planning_status == other[2].status == "ready"
    assert other[5].stale is False
    assert other[6].stale is False


def test_style_change_only_stales_visual_material_and_outputs(db):
    project, scene, shot, prompt, subtitle, package, render = _artifacts(db)
    _record_handoff(db)
    events = _change(db, "style")
    db.expire_all()

    assert events.total == 1
    assert scene.prompt_status == shot.prompt_status == prompt.quality_status == "stale"
    assert scene.voice_status == shot.voice_status == "completed"
    assert shot.subtitle_status == "ready"
    assert subtitle.status == "completed"
    assert project.story_approved is True
    assert project.script_approved is True
    assert package.stale is True
    assert render.stale is True


@pytest.mark.parametrize("scope", ["narration", "dialogue", "timing", "language"])
def test_speech_change_reaches_phase2_shots_without_staling_visuals(db, scope):
    project, scene, shot, prompt, subtitle, package, render = _artifacts(db)
    _record_handoff(db)
    _change(db, scope)
    db.expire_all()

    assert scene.voice_status == shot.voice_status == "stale"
    assert subtitle.status == "stale"
    assert shot.prompt_status == prompt.quality_status == "ready"
    assert project.story_approved is True
    assert package.stale is True
    assert render.stale is True


def test_native_veo_shots_do_not_require_voicebox_regeneration(db):
    project, _, shot, _, subtitle, _, _ = _artifacts(db)
    project.target_language = "vi"
    project.speech_source = "veo_dialogue"
    _record_handoff(db)
    _change(db, "narration")
    db.expire_all()
    assert shot.voice_status == "completed"
    assert shot.subtitle_status == subtitle.status == "stale"


def test_concrete_prompt_dependency_only_updates_its_actual_target(db):
    project, scene, shot, prompt, subtitle, _, _ = _artifacts(db)
    _, _, other_shot, other_prompt, _, _, _ = _artifacts(db, "other")
    series_references.record_dependency_snapshots(
        "series",
        models.ArtifactDependencyRecordRequest(
            artifact_type="video_prompt",
            artifact_id=prompt.id,
            artifact_revision=prompt.version,
            dependencies=[
                models.ArtifactDependencyInput(
                    dependency_type="video_inspiration_handoff",
                    dependency_id="handoff",
                    dependency_revision=1,
                    dependency_scope="style",
                )
            ],
            metadata={"project_id": project.id},
        ),
        db,
    )
    events = _change(db, "style")
    db.expire_all()
    assert events.total == 1
    assert prompt.quality_status == shot.prompt_status == scene.prompt_status == "stale"
    assert other_shot.prompt_status == other_prompt.quality_status == "ready"
    assert shot.voice_status == "completed"
    assert subtitle.status == "completed"


def test_repeated_change_is_idempotent_and_events_match_state(db):
    _, scene, shot, _, _, _, _ = _artifacts(db)
    _record_handoff(db)
    first = _change(db, "story_state")
    revisions = (scene.revision, shot.revision)
    second = _change(db, "story_state")
    assert first.total == 3
    assert second.total == 0
    assert revisions == (scene.revision, shot.revision)
    assert series_references.list_stale_events("series", db).total == 3


def test_event_and_state_changes_share_the_callers_transaction(db):
    project, _, shot, _, _, package, _ = _artifacts(db)
    _record_handoff(db)
    _change(db, "story_state", commit=False)
    assert shot.status == "stale"
    db.rollback()
    assert project.story_approved is True
    assert shot.status == "ready"
    assert package.stale is False
    assert series_references.list_stale_events("series", db).total == 0


def test_registration_replaces_only_the_matching_project_dependency(db):
    _artifacts(db)
    _artifacts(db, "other")
    _record_handoff(db)
    _record_handoff(db, "other")
    video_project_memory.record_project_dependency("project", "video_inspiration_handoff", "handoff", 4, db)
    db.commit()
    snapshots = db.query(ArtifactDependencySnapshot).all()
    assert len(snapshots) == 14
    assert {row.dependency_revision for row in snapshots if row.metadata_json["project_id"] == "project"} == {4}
    assert {row.dependency_revision for row in snapshots if row.metadata_json["project_id"] == "other"} == {1}


def test_project_dependency_also_covers_artifacts_created_after_handoff(db):
    _artifacts(db)
    _record_handoff(db)
    later = VideoShot(project_id="project", shot_order=2, status="ready", prompt_status="ready")
    db.add(later)
    db.commit()
    _change(db, "story_state")
    assert later.status == later.prompt_status == "stale"


def test_stale_story_dependency_revokes_the_persisted_longform_production_gate(db):
    project, _, _, _, _, _, _ = _artifacts(db)
    project.format_profile = "long_form"
    project.retention_plan_json = {
        "longform": {
            "revision": 4,
            "status": "ready",
            "outline_approved": True,
            "editorial_review": {"passed": True},
            "input_fingerprint": video_longform_workflow.fingerprint(project, db),
        }
    }
    db.commit()
    video_longform_workflow.require_ready(project, db)
    _record_handoff(db)
    _change(db, "story_state")
    with pytest.raises(VideoPlanningValidationError):
        video_longform_workflow.require_ready(project, db)


def test_legacy_active_events_repair_actual_artifacts_without_duplicate_events(db):
    _, scene, shot, _, _, _, _ = _artifacts(db)
    _record_handoff(db)
    for snapshot in db.query(ArtifactDependencySnapshot).all():
        snapshot.metadata_json = {key: value for key, value in snapshot.metadata_json.items() if key != "target_scope"}
        if snapshot.dependency_scope == "story_state":
            db.add(
                ArtifactStaleEvent(
                    id=f"legacy-{snapshot.artifact_type}",
                    series_id="series",
                    artifact_type=snapshot.artifact_type,
                    artifact_id=snapshot.artifact_id,
                    artifact_revision=1,
                    dependency_type=snapshot.dependency_type,
                    dependency_id=snapshot.dependency_id,
                    dependency_scope="story_state",
                    changed_scope="story_state",
                    reason_vi="Old change",
                    propagation_rule="story_state->story_state",
                    status="active",
                    metadata_json=snapshot.metadata_json,
                )
            )
    db.commit()
    assert _change(db, "story_state").total == 0
    assert shot.status == "stale"
    revisions = (scene.revision, shot.revision)
    assert _change(db, "story_state").total == 0
    assert revisions == (scene.revision, shot.revision)
    assert series_references.list_stale_events("series", db).total == 3
