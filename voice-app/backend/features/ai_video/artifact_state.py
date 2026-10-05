"""Apply AI Video dependency changes to stored artifacts without committing.

Project-task dependencies address a collection, including artifacts created after
the handoff. Concrete dependencies address one stored artifact. Both use the
same state rules here; series event bookkeeping stays with series_references.
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy.orm import Session

from ...database import (
    ArtifactDependencySnapshot,
    VideoPackageExport,
    VideoProject,
    VideoRenderJob,
    VideoScene,
    VideoShot,
    VideoShotPrompt,
    VideoSubtitle,
)

PROJECT_TASKS = {
    "video_project": "project",
    "video_story": "story",
    "video_shot": "shot",
    "video_prompt": "prompt",
    "scene_voice": "voice",
    "subtitle": "subtitle",
    "package": "package",
}


def mark_package_stale(project: VideoProject, db: Session) -> None:
    project.package_stale = True
    project.updated_at = datetime.utcnow()
    db.query(VideoPackageExport).filter(VideoPackageExport.project_id == project.id).update(
        {"stale": True}, synchronize_session="fetch"
    )


def mark_render_outputs_stale(project_id: str, db: Session) -> None:
    db.query(VideoRenderJob).filter(
        VideoRenderJob.project_id == project_id,
        VideoRenderJob.status == "completed",
        VideoRenderJob.stale.is_(False),
    ).update({"stale": True, "updated_at": datetime.utcnow()}, synchronize_session="fetch")


def mark_dialogue_dependents_stale(project: VideoProject, db: Session) -> None:
    """Preserve the existing purpose/dialogue invalidation contract."""
    from ...services import video_publishing_metadata

    db.query(VideoScene).filter(VideoScene.project_id == project.id).update(
        {"prompt_status": "stale", "voice_status": "stale", "subtitle_status": "stale"},
        synchronize_session="fetch",
    )
    for shot in db.query(VideoShot).filter(VideoShot.project_id == project.id).all():
        shot.status = "stale"
        shot.prompt_status = "stale"
        shot.subtitle_status = "stale"
        if (shot.english_narration or "").strip():
            shot.voice_status = "stale"
    db.query(VideoSubtitle).filter(VideoSubtitle.project_id == project.id).update(
        {"status": "stale"}, synchronize_session="fetch"
    )
    mark_render_outputs_stale(project.id, db)
    mark_package_stale(project, db)
    video_publishing_metadata.mark_publishing_metadata_stale(
        project.id, db, reason="Nội dung kịch bản, narration hoặc mục đích video đã thay đổi."
    )


def _touch(row) -> None:
    row.revision = int(row.revision or 1) + 1
    row.updated_at = datetime.utcnow()


def _mark_fields_stale(row, *fields: str) -> None:
    if any(getattr(row, field) != "stale" for field in fields):
        for field in fields:
            setattr(row, field, "stale")
        _touch(row)


def _mark_subtitles_stale(project_id: str, db: Session) -> None:
    for subtitle in db.query(VideoSubtitle).filter(VideoSubtitle.project_id == project_id).all():
        if subtitle.status != "stale":
            subtitle.status = "stale"
            _touch(subtitle)


def _project_target(snapshot: ArtifactDependencySnapshot, db: Session) -> VideoProject | None:
    metadata = snapshot.metadata_json if isinstance(snapshot.metadata_json, dict) else {}
    project_id = metadata.get("project_id")
    task = PROJECT_TASKS.get(snapshot.artifact_type)
    if not project_id or not task or metadata.get("task") != task:
        return None
    expected_id = project_id if task == "project" else f"{project_id}:{task}"
    if snapshot.artifact_id != expected_id:
        return None
    # Legacy handoff snapshots did not declare target_scope. Do not treat an
    # ordinary concrete snapshot containing project_id as a collection target.
    if metadata.get("target_scope") != "project" and metadata.get("source") != "video_inspiration_handoff":
        return None
    project = db.get(VideoProject, project_id)
    return project if project is not None and project.series_id == snapshot.series_id else None


def _apply_project_task(project: VideoProject, artifact_type: str, reason_vi: str, db: Session) -> None:
    from ...services import video_publishing_metadata, video_speech

    if artifact_type in {"video_project", "video_story"}:
        project.planning_status = "stale"
        project.planning_error = reason_vi
        project.story_approved = project.script_approved = False
        retention = project.retention_plan_json or {}
        longform = retention.get("longform")
        if isinstance(longform, dict):
            project.retention_plan_json = {
                **retention,
                "longform": {
                    **longform,
                    "status": "stale",
                    "outline_approved": False,
                    "input_fingerprint": None,
                    "error": reason_vi,
                },
            }
        video_publishing_metadata.mark_publishing_metadata_stale(project.id, db, reason=reason_vi)
    elif artifact_type in {"video_shot", "video_prompt"}:
        for scene in db.query(VideoScene).filter(VideoScene.project_id == project.id).all():
            if artifact_type == "video_shot":
                _mark_fields_stale(scene, "prompt_status", "subtitle_status")
            else:
                _mark_fields_stale(scene, "prompt_status")
        for shot in db.query(VideoShot).filter(VideoShot.project_id == project.id).all():
            if artifact_type == "video_shot":
                _mark_fields_stale(shot, "status", "prompt_status", "subtitle_status")
            else:
                _mark_fields_stale(shot, "prompt_status")
        db.query(VideoShotPrompt).filter(VideoShotPrompt.project_id == project.id).update(
            {"quality_status": "stale"}, synchronize_session="fetch"
        )
        if artifact_type == "video_shot":
            _mark_subtitles_stale(project.id, db)
    elif artifact_type == "scene_voice":
        for scene in db.query(VideoScene).filter(VideoScene.project_id == project.id).all():
            if scene.no_narration or not (scene.dialogue or "").strip():
                continue
            _mark_fields_stale(scene, "voice_status", "subtitle_status")
        for shot in db.query(VideoShot).filter(VideoShot.project_id == project.id).all():
            if video_speech.uses_veo_native_speech(project, shot) or not (shot.english_narration or "").strip():
                continue
            _mark_fields_stale(shot, "voice_status", "subtitle_status")
        _mark_subtitles_stale(project.id, db)
    elif artifact_type == "subtitle":
        _mark_subtitles_stale(project.id, db)
        for scene in db.query(VideoScene).filter(VideoScene.project_id == project.id).all():
            scene.subtitle_status = "stale"
        for shot in db.query(VideoShot).filter(VideoShot.project_id == project.id).all():
            shot.subtitle_status = "stale"
    mark_package_stale(project, db)
    mark_render_outputs_stale(project.id, db)


def apply_dependency_stale(
    snapshot: ArtifactDependencySnapshot, reason_vi: str, db: Session, *, replay: bool = False
) -> None:
    """Invalidate the concrete target or the explicitly addressed project task."""
    project = _project_target(snapshot, db)
    if project is not None:
        _apply_project_task(project, snapshot.artifact_type, reason_vi, db)
        return
    if replay:
        # Legacy collection events could exist without updating real targets.
        # Existing concrete events retain their previous duplicate behavior.
        return
    artifact_type = snapshot.artifact_type
    if artifact_type in {"video_project", "video_story"}:
        project = db.get(VideoProject, snapshot.artifact_id)
        if project is not None and project.series_id == snapshot.series_id:
            _apply_project_task(project, artifact_type, reason_vi, db)
    elif artifact_type == "video_prompt":
        prompt = db.get(VideoShotPrompt, snapshot.artifact_id)
        if prompt is not None:
            prompt.quality_status = "stale"
            shot = db.get(VideoShot, prompt.shot_id)
            if shot is not None:
                shot.prompt_status = "stale"
                _touch(shot)
            if prompt.scene_id:
                scene = db.get(VideoScene, prompt.scene_id)
                if scene is not None:
                    scene.prompt_status = "stale"
                    _touch(scene)
    elif artifact_type in {"scene_voice", "scene_subtitle"}:
        scene = db.get(VideoScene, snapshot.artifact_id)
        if scene is not None:
            if artifact_type == "scene_voice":
                scene.voice_status = "stale"
            scene.subtitle_status = "stale"
            _touch(scene)
    elif artifact_type in {"shot_voice", "shot_subtitle", "video_shot"}:
        shot = db.get(VideoShot, snapshot.artifact_id)
        if shot is not None:
            if artifact_type == "shot_voice":
                shot.voice_status = "stale"
            if artifact_type == "video_shot":
                shot.status = shot.prompt_status = "stale"
            shot.subtitle_status = "stale"
            _touch(shot)
    elif artifact_type == "subtitle":
        subtitle = db.get(VideoSubtitle, snapshot.artifact_id)
        if subtitle is not None:
            subtitle.status = "stale"
            _touch(subtitle)
    elif artifact_type == "package":
        package = db.get(VideoPackageExport, snapshot.artifact_id)
        if package is not None:
            package.stale = True
            _touch(package)
    elif artifact_type == "render":
        render = db.get(VideoRenderJob, snapshot.artifact_id)
        if render is not None:
            render.stale = True
            render.updated_at = datetime.utcnow()
