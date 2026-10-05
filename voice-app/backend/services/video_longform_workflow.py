"""Persisted outline approval and resumable chapter planning for AI Video."""
from __future__ import annotations

import copy
import hashlib
import json
import threading
from contextlib import contextmanager
from datetime import datetime
from typing import Any

from sqlalchemy.orm import Session

from ..database import VideoProject, VideoSourceBlock
from . import video_longform
from .video_planning import VideoPlanningValidationError

_guard = threading.Lock()
_active: set[str] = set()


@contextmanager
def planning(project_id: str):
    with _guard:
        if project_id in _active:
            raise VideoPlanningValidationError("Dàn ý hoặc chương của dự án đang được xử lý. Hãy chờ hoàn tất.")
        _active.add(project_id)
    try:
        yield
    finally:
        with _guard:
            _active.discard(project_id)


def state(project: VideoProject) -> dict[str, Any]:
    value = (project.retention_plan_json or {}).get("longform", {})
    return copy.deepcopy(value) if isinstance(value, dict) else {}


def fingerprint(project: VideoProject, db: Session) -> str:
    fields = (
        "topic", "target_language", "video_purpose", "content_genre", "content_objective",
        "audience_age_band", "format_profile", "narrative_mode", "learning_objective",
        "interaction_mode", "safety_policy", "made_for_kids", "target_duration_seconds",
        "dialogue_mode", "narration_density", "call_to_action_style", "cta_action",
        "visual_style", "aspect_ratio", "series_id", "episode_number", "episode_title",
    )
    payload = {key: getattr(project, key, None) for key in fields}
    payload["sources"] = [
        [row.id, row.block_type, row.content, row.sort_order]
        for row in db.query(VideoSourceBlock).filter(VideoSourceBlock.project_id == project.id)
        .order_by(VideoSourceBlock.sort_order, VideoSourceBlock.id).all()
    ]
    return hashlib.sha256(json.dumps(payload, ensure_ascii=False, sort_keys=True, default=str).encode()).hexdigest()


def save(project: VideoProject, value: dict, db: Session) -> None:
    project.retention_plan_json = {**(project.retention_plan_json or {}), "longform": copy.deepcopy(value)}
    project.updated_at = datetime.utcnow()
    db.commit()


def assert_current(project: VideoProject, db: Session, input_hash: str, revision: int) -> None:
    db.refresh(project)
    if fingerprint(project, db) != input_hash or state(project).get("revision") != revision:
        raise VideoPlanningValidationError("Nội dung hoặc dàn ý đã thay đổi trong khi AI chạy. Mở lại dự án và phát triển bản mới.")


def _require_revision(value: dict, revision: int | None) -> None:
    if revision is None or revision != value.get("revision"):
        raise VideoPlanningValidationError("Dàn ý đã thay đổi. Tải lại dự án trước khi duyệt hoặc sửa.")


def approve_outline(project_id: str, approved: bool, db: Session, *, expected_revision: int | None = None):
    from . import video_projects
    with planning(project_id):
        project = db.get(VideoProject, project_id)
        if project is None:
            return None
        value = state(project)
        _require_revision(value, expected_revision)
        if project.format_profile != "long_form" or not value.get("outline"):
            raise VideoPlanningValidationError("Cần tạo dàn ý video dài trước khi duyệt.")
        if value.get("input_fingerprint") != fingerprint(project, db):
            raise VideoPlanningValidationError("Đầu vào đã thay đổi. Hãy tạo lại dàn ý trước khi duyệt.")
        video_longform.validate_outline(value["outline"], int(project.target_duration_seconds or 0))
        value["outline_approved"] = approved
        value["error"] = None
        if not approved:
            value["status"] = "outline_ready"
            value["editorial_review"] = None
            project.story_approved = project.script_approved = False
            video_projects._stale_dialogue_dependent_artifacts(project, db)
        project.planning_status = "longform_writing" if approved else "outline_ready"
        save(project, value, db)
        return video_projects.get_project(project_id, db)


def update_outline(project_id: str, outline: dict, db: Session, *, expected_revision: int | None = None):
    from . import video_projects
    with planning(project_id):
        project = db.get(VideoProject, project_id)
        if project is None:
            return None
        previous = state(project)
        _require_revision(previous, expected_revision)
        if project.format_profile != "long_form":
            raise VideoPlanningValidationError("Dự án này chưa chọn định dạng video dài.")
        try:
            validated = video_longform.validate_outline(outline, int(project.target_duration_seconds or 0))
        except video_longform.LongFormPlanningError as exc:
            raise VideoPlanningValidationError(str(exc)) from exc
        value = {
            "revision": previous["revision"] + 1, "status": "outline_ready",
            "outline": validated, "outline_approved": False, "chapters": [],
            "editorial_review": None, "error": None, "input_fingerprint": fingerprint(project, db),
        }
        project.story_approved = project.script_approved = False
        project.planning_status = "outline_ready"
        video_projects._stale_dialogue_dependent_artifacts(project, db)
        save(project, value, db)
        return video_projects.get_project(project_id, db)


def require_ready(project: VideoProject, db: Session) -> None:
    if project.format_profile != "long_form":
        return
    value = state(project)
    review = value.get("editorial_review") or {}
    if (value.get("status") != "ready" or not value.get("outline_approved")
            or review.get("passed") is not True or value.get("input_fingerprint") != fingerprint(project, db)):
        raise VideoPlanningValidationError("Video dài cần duyệt dàn ý, hoàn tất các chương và đạt kiểm tra biên tập trước khi sản xuất.")


def develop(project: VideoProject, db: Session, context: str, run, *, force: bool = False) -> dict | None:
    """Return an assembled plan, or None when a new outline awaits approval."""
    from . import video_phase2, video_projects
    value = state(project)
    input_hash = fingerprint(project, db)
    if force or not value.get("outline") or value.get("input_fingerprint") != input_hash:
        revision = int(value.get("revision", 0)) + 1
        value = {"revision": revision, "status": "outline_ready", "outline": None,
                 "outline_approved": False, "chapters": [], "editorial_review": None,
                 "error": None, "input_fingerprint": input_hash}
        project.story_approved = project.script_approved = False
        video_projects._stale_dialogue_dependent_artifacts(project, db)
        save(project, value, db)
        try:
            outline = video_longform.build_outline(context, int(project.target_duration_seconds or 600), run)
            assert_current(project, db, input_hash, revision)
            value["outline"] = outline
            project.planning_status = project.status = "outline_ready"
            save(project, value, db)
            return None
        except Exception as exc:
            _save_failure(project, db, value, input_hash, exc)
            raise
    if not value.get("outline_approved"):
        return None
    revision = value["revision"]
    try:
        value.update(status="writing", error=None, editorial_review=None)
        project.story_approved = project.script_approved = False
        save(project, value, db)

        def checkpoint(chapters):
            assert_current(project, db, input_hash, revision)
            value["chapters"] = copy.deepcopy(chapters)
            save(project, value, db)

        generated = video_longform.generate_chapters(
            value["outline"], context, run, completed_chapters=value.get("chapters", []),
            on_chapter=checkpoint, scene_schema=video_phase2.StoryScenePlan.model_json_schema(),
        )
        value["chapters"] = generated["chapters"]
        value["status"] = "editorial_review"
        assert_current(project, db, input_hash, revision)
        save(project, value, db)
        review = video_longform.editorial_review(value["outline"], value["chapters"], context, run)
        assert_current(project, db, input_hash, revision)
        value["editorial_review"] = review
        if review.get("passed") is not True:
            value["status"] = "blocked"
            save(project, value, db)
            raise VideoPlanningValidationError("Kiểm tra biên tập chưa đạt. Xem nhận xét, sửa dàn ý và viết lại phần nội dung liên quan.")
        value["status"] = "ready"
        save(project, value, db)
        return assemble_plan(value, project)
    except Exception as exc:
        _save_failure(project, db, value, input_hash, exc)
        raise


def _save_failure(project: VideoProject, db: Session, value: dict, input_hash: str, exc: Exception) -> None:
    db.rollback()
    db.refresh(project)
    if state(project).get("revision") == value["revision"] and fingerprint(project, db) == input_hash:
        value.update(status="blocked", error=str(exc)[:2000])
        project.planning_status = "longform_blocked"
        save(project, value, db)


def assemble_plan(value: dict, project: VideoProject) -> dict:
    """Keep chapter narration verbatim when producing the existing scene model."""
    from . import video_phase2
    outline = value["outline"]
    chapters = value["chapters"]
    scenes = [scene for chapter in chapters for scene in chapter["scenes"]]
    script = "\n\n".join(scene["english_narration"] for scene in scenes)
    review_script = "\n\n".join(f"{chapter['title']}\n{chapter.get('review_vi', chapter['goal'])}" for chapter in chapters)
    strategy = f"{outline['central_question']}\n{outline['central_promise']}\nKết quả: {outline['payoff']}"
    continuity = "\n".join(f"{chapter['title']}: {chapter['state_in']} → {chapter['state_out']}. {chapter['bridge']}" for chapter in chapters)
    elapsed = 0
    beats = []
    for chapter in chapters:
        end = elapsed + chapter["duration_seconds"]
        beats.append({"start_seconds": elapsed, "end_seconds": end, "purpose": chapter["goal"],
                      "viewer_reason": chapter["bridge"], "pattern_interrupt": chapter["title"],
                      "visual_surprise": chapter["state_out"]})
        elapsed = end
    sound = video_phase2._default_sound_payload(fallback="Giữ giọng kể rõ, âm thanh theo bối cảnh từng chương.")
    sound["review_vi"] = "Chỉ dẫn âm thanh: giọng kể rõ, nhạc và hiệu ứng nhẹ theo từng chương."
    return {
        "video_purpose": project.video_purpose, "dialogue_mode": project.dialogue_mode,
        "narration_density": project.narration_density, "call_to_action_style": project.call_to_action_style,
        "cta_action": project.cta_action, "input_synthesis": strategy,
        "story_strategy": strategy, "story_strategy_vi": strategy,
        "continuity_bible": continuity, "continuity_bible_vi": continuity,
        "detailed_script": script, "detailed_script_vi": script if project.target_language == "vi" else review_script,
        "retention_plan": {"review_vi": strategy, "hook_0_2s": outline["central_question"],
            "viewer_question": outline["central_question"], "curiosity_gap": outline["central_promise"],
            "beat_curve": beats, "pattern_interrupts": [c["bridge"] for c in chapters],
            "payoff_plan": outline["payoff"], "dropoff_risks": ["Theo dõi nhịp kể tại điểm chuyển chương."]},
        "sound_design_plan": sound, "scenes": scenes,
    }
