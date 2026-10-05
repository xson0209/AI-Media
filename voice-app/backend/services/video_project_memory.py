"""Structured Video Inspiration handoff and project-scope memory."""

from __future__ import annotations

import math
import re
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any

from sqlalchemy import func
from sqlalchemy.orm import Session

from .. import models
from ..database import (
    ArtifactDependencySnapshot as DBArtifactDependencySnapshot,
    VideoInspirationHandoff as DBVideoInspirationHandoff,
    VideoInspirationJob as DBVideoInspirationJob,
    VideoProject as DBVideoProject,
    VideoProjectContextSnapshot as DBVideoProjectContextSnapshot,
    VideoProjectMemoryCard as DBVideoProjectMemoryCard,
    VideoProjectTargetTimelineBeat as DBVideoProjectTargetTimelineBeat,
)
from . import series_references, source_package, video_state

HANDOFF_SCHEMA_VERSION = "video_inspiration_handoff.v1"
TASK_DEPENDENCY_SCOPES = (
    ("video_project", "project", "story_state"),
    ("video_story", "story", "story_state"),
    ("video_shot", "shot", "story_state"),
    ("video_prompt", "prompt", "style"),
    ("scene_voice", "voice", "narration"),
    ("subtitle", "subtitle", "timing"),
    ("package", "package", "narration"),
)
_GENERIC_SOURCE_TITLE_STEMS = {
    "download",
    "source",
    "upload",
    "video",
    "file",
    "output",
    "clip",
    "untitled",
}


class VideoProjectMemoryError(ValueError):
    def __init__(self, message: str, *, error_code: str = "VIDEO_PROJECT_MEMORY_ERROR", status_code: int = 400):
        super().__init__(message)
        self.error_code = error_code
        self.status_code = status_code


def _now() -> datetime:
    return datetime.utcnow()


def _truncate(value: Any, limit: int) -> str:
    return str(value or "").strip()[:limit].rstrip()


def _title_candidate(value: Any, *, filename: bool = False) -> str:
    text = str(value or "").strip()
    if not text:
        return ""
    if filename:
        text = Path(text).stem
    text = re.sub(r"\.(?:aac|avi|flac|m4a|m4v|mkv|mov|mp3|mp4|ogg|opus|wav|webm)$", "", text, flags=re.IGNORECASE)
    text = re.sub(r"[_\-]+", " ", text)
    text = re.sub(r"\s+", " ", text).strip(" .:-_")
    normalized = re.sub(r"\s*\(\d+\)$", "", text.lower()).strip()
    normalized = re.sub(r"\s+(?:aac|avi|flac|m4a|m4v|mkv|mov|mp3|mp4|ogg|opus|wav|webm)$", "", normalized).strip()
    normalized = re.sub(r"\s+\d+$", "", normalized).strip()
    if not text or text.lower() in _GENERIC_SOURCE_TITLE_STEMS or normalized in _GENERIC_SOURCE_TITLE_STEMS:
        return ""
    return _truncate(text, 120)


def _handoff_title(row: DBVideoInspirationJob, rewrite: dict[str, Any]) -> str:
    analysis = _as_dict(row.analysis_json)
    for value in (
        row.script_title,
        rewrite.get("title"),
        row.big_idea,
        rewrite.get("big_idea"),
        row.hook,
        analysis.get("main_idea_vi"),
        analysis.get("hook_vi"),
        row.user_direction,
        row.transcript_text,
    ):
        title = _title_candidate(value)
        if title:
            return title
    title = _title_candidate(row.original_filename, filename=True)
    if title and row.source_type != "url":
        return title
    platform = (row.source_platform or "").strip().lower()
    if platform and platform != "unknown":
        return f"Video cảm hứng từ {platform.title()}"
    return "Video từ cảm hứng"


def _as_dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _as_list(value: Any) -> list[Any]:
    if value is None:
        return []
    return value if isinstance(value, list) else [value]


def _has_meaningful_content(value: Any) -> bool:
    if value is None:
        return False
    if isinstance(value, str):
        return bool(value.strip())
    if isinstance(value, dict):
        return any(_has_meaningful_content(item) for item in value.values())
    if isinstance(value, (list, tuple, set)):
        return any(_has_meaningful_content(item) for item in value)
    return True


def _rewrite_payload(row: DBVideoInspirationJob) -> dict[str, Any]:
    analysis = _as_dict(row.analysis_json)
    return _as_dict(analysis.get("rewrite"))


def _retention_map(row: DBVideoInspirationJob) -> list[dict[str, Any]]:
    package = _as_dict(row.analysis_package_json)
    beats = package.get("content_retention_beats")
    if isinstance(beats, list) and beats:
        return [item for item in beats if isinstance(item, dict)]
    rewrite_retention = _as_dict(_rewrite_payload(row).get("retention_plan"))
    beat_curve = rewrite_retention.get("beat_curve")
    if isinstance(beat_curve, list):
        return [
            {
                "order": index,
                "role": "rewrite_retention",
                "content": str(item),
                "why_continue": str(item),
            }
            for index, item in enumerate(beat_curve, start=1)
        ]
    return []


def _approved_script(row: DBVideoInspirationJob) -> dict[str, Any]:
    rewrite = _rewrite_payload(row)
    return {
        "title": _handoff_title(row, rewrite),
        "big_idea": row.big_idea or rewrite.get("big_idea"),
        "hook": row.hook or rewrite.get("hook_3_5s") or rewrite.get("hook"),
        "script": row.rewritten_script,
        "segments": rewrite.get("segments") if isinstance(rewrite.get("segments"), list) else [],
        "target_language": row.target_language,
        "revision": 1,
    }


def build_handoff_payload(row: DBVideoInspirationJob) -> dict[str, Any]:
    package = _as_dict(row.analysis_package_json)
    analysis = _as_dict(row.analysis_json)
    rewrite = _rewrite_payload(row)
    source_blocks = _as_dict(rewrite.get("ai_video_source_blocks"))
    approved_script = _approved_script(row)
    retention_map = _retention_map(row)
    hook_contract = {
        "hook": approved_script.get("hook") or analysis.get("hook_vi"),
        "viewer_question": rewrite.get("viewer_question") or _as_dict(rewrite.get("retention_plan")).get("viewer_question"),
        "curiosity_gap": rewrite.get("curiosity_gap") or _as_dict(rewrite.get("retention_plan")).get("curiosity_gap"),
        "payoff": _as_dict(rewrite.get("retention_plan")).get("payoff"),
    }
    payload = {
        "source_analysis_ref": {
            "job_id": row.id,
            "schema_version": row.analysis_schema_version,
            "analysis_package_path": row.analysis_package_path,
            "analysis_completeness": row.analysis_completeness,
            "retention_source": row.retention_source,
        },
        "source_observations": {
            "shots": package.get("shots", []),
            "transcript_segments": package.get("transcript_segments", []),
            "audio_events": package.get("audio_events", []),
            "on_screen_text_events": package.get("on_screen_text_events", []),
            "coverage_metrics": package.get("coverage_metrics") or row.coverage_metrics_json or {},
            "limitations": package.get("limitations") or row.limitations_json or [],
        },
        "learnable_lessons": {
            "content_spine": approved_script.get("big_idea") or analysis.get("main_idea_vi"),
            "retention_map": retention_map,
            "visual_grammar_to_learn": package.get("visual_grammar") or analysis.get("visual_rhythm_vi") or row.visual_summary,
            "audio_grammar_to_learn": package.get("audio_grammar") or rewrite.get("audio_direction") or rewrite.get("sound_design_plan"),
            "strengths": analysis.get("strengths_vi") or package.get("strengths") or [],
            "rewrite_opportunities": analysis.get("rewrite_opportunities_vi") or package.get("rewrite_opportunities") or [],
        },
        "target_content": {
            "target_audience": rewrite.get("target_audience") or source_blocks.get("target_audience") or "",
            "video_goal": row.big_idea or rewrite.get("big_idea") or analysis.get("main_idea_vi") or "",
            "platform": "",
            "content_spine": approved_script.get("big_idea") or "",
            "hook_contract": hook_contract,
            "approved_script": approved_script,
            "character_and_setting_state": source_blocks.get("character_notes") or analysis.get("characters_context_vi") or "",
            "visual_direction": source_blocks.get("style_notes") or rewrite.get("visual_suggestions") or row.visual_summary or "",
            "audio_direction": rewrite.get("audio_direction") or rewrite.get("sound_design_plan") or "",
            "voice_and_language": {"target_language": row.target_language, "dialogue_mode": "voiceover"},
            "must_have": source_blocks.get("must_have") or "",
            "avoid": source_blocks.get("avoid") or "",
        },
        "originality_boundaries": package.get("originality_boundaries") or rewrite.get("originality_note") or [],
        "evidence_refs": _collect_evidence_refs(package, retention_map),
        "limitations": package.get("limitations") or row.limitations_json or [],
        "revision": 1,
    }
    return payload


def _collect_evidence_refs(package: dict[str, Any], retention_map: list[dict[str, Any]]) -> list[Any]:
    refs: list[Any] = []
    for beat in retention_map:
        refs.extend(_as_list(beat.get("evidence_refs")))
    for event in _as_list(package.get("on_screen_text_events"))[:8]:
        if isinstance(event, dict):
            refs.append({"type": "on_screen_text", "id": event.get("id"), "time": event.get("start_seconds")})
    return refs[:40]


def source_blocks_from_payload(payload: dict[str, Any]) -> list[models.VideoSourceBlockDraft]:
    package = source_package_from_payload(payload)
    return [
        models.VideoSourceBlockDraft(block_type=str(block["block_type"]), content=str(block["content"]))
        for block in source_package.to_ai_video_source_blocks(package)
    ]

def source_package_from_payload(payload: dict[str, Any]) -> source_package.SourcePackage:
    """Build the canonical Source Package for a Video Inspiration handoff."""
    target = _as_dict(payload.get("target_content"))
    lessons = _as_dict(payload.get("learnable_lessons"))
    source = _as_dict(payload.get("source_observations"))
    script = _as_dict(target.get("approved_script"))
    hook_contract = _as_dict(target.get("hook_contract"))
    source_ref = _as_dict(payload.get("source_analysis_ref"))
    package_blocks = [
        source_package.SourcePackageBlock(
            block_type="idea",
            sort_order=1,
            content={
                "video_goal": target.get("video_goal"),
                "content_spine": target.get("content_spine"),
                "hook_contract": hook_contract,
            },
        ),
        source_package.SourcePackageBlock(
            block_type="rough_script",
            sort_order=2,
            content={
                "approved_target_script": script,
                "source_transcript_is_evidence_only": True,
            },
        ),
        source_package.SourcePackageBlock(
            block_type="character_notes",
            sort_order=3,
            content=target.get("character_and_setting_state"),
        ),
        source_package.SourcePackageBlock(
            block_type="style_notes",
            sort_order=4,
            content={
                "visual_direction": target.get("visual_direction"),
                "visual_grammar_to_learn": lessons.get("visual_grammar_to_learn"),
            },
        ),
        source_package.SourcePackageBlock(
            block_type="must_have",
            sort_order=5,
            content=target.get("must_have"),
        ),
        source_package.SourcePackageBlock(
            block_type="avoid",
            sort_order=6,
            content={
                "avoid": target.get("avoid"),
                "originality_boundaries": payload.get("originality_boundaries"),
            },
        ),
        source_package.SourcePackageBlock(
            block_type="analysis",
            sort_order=7,
            content={
                "source_analysis_ref": payload.get("source_analysis_ref"),
                "retention_map": lessons.get("retention_map"),
                "limitations": payload.get("limitations"),
            },
        ),
        source_package.SourcePackageBlock(
            block_type="transcript",
            sort_order=8,
            content={"source_transcript_for_evidence_only": source.get("transcript_segments", [])[:12]},
        ),
    ]
    return source_package.build_source_package(
        source_kind="video_inspiration_handoff",
        source_ref_id=source_ref.get("job_id"),
        source_revision=payload.get("revision") or source_ref.get("schema_version"),
        title=script.get("title") or target.get("video_goal"),
        summary=target.get("content_spine") or target.get("video_goal"),
        blocks=package_blocks,
        coverage_metrics=_as_dict(source.get("coverage_metrics")),
        limitations=_as_list(payload.get("limitations")),
        provenance={
            "source_analysis_ref": payload.get("source_analysis_ref"),
            "originality_boundaries": payload.get("originality_boundaries"),
            "target_language": script.get("target_language"),
        },
    )


def create_or_update_handoff(
    row: DBVideoInspirationJob,
    db: Session,
    *,
    status: str = "ready_for_review",
) -> DBVideoInspirationHandoff:
    if not row.analysis_package_json:
        raise VideoProjectMemoryError(
            "Cần có gói phân tích VideoAnalysisPackage trước khi tạo handoff.",
            error_code="VIDEO_INSPIRATION_ANALYSIS_PACKAGE_REQUIRED",
        )
    if not (row.rewritten_script or "").strip():
        raise VideoProjectMemoryError(
            "Cần có kịch bản mới đã duyệt trước khi tạo handoff.",
            error_code="VIDEO_INSPIRATION_APPROVED_SCRIPT_REQUIRED",
        )
    payload = build_handoff_payload(row)
    source_blocks = [block.model_dump(mode="json") for block in source_blocks_from_payload(payload)]
    existing = (
        db.query(DBVideoInspirationHandoff)
        .filter(DBVideoInspirationHandoff.job_id == row.id)
        .order_by(DBVideoInspirationHandoff.updated_at.desc())
        .first()
    )
    now = _now()
    if existing is None:
        existing = DBVideoInspirationHandoff(
            id=str(uuid.uuid4()),
            job_id=row.id,
            created_at=now,
        )
        db.add(existing)
    else:
        existing.revision = int(existing.revision or 1) + 1
    existing.analysis_package_path = row.analysis_package_path
    existing.analysis_package_revision = row.analysis_schema_version or "video_analysis_package.v1"
    existing.schema_version = HANDOFF_SCHEMA_VERSION
    existing.status = status
    existing.target_language = row.target_language
    existing.approved_script_revision = int(payload.get("revision") or 1)
    existing.payload_json = payload
    existing.source_blocks_json = source_blocks
    existing.updated_at = now
    existing.approved_at = now if status == "approved" else existing.approved_at
    db.commit()
    db.refresh(existing)
    return existing

def create_handoff_for_job(
    job_id: str,
    db: Session,
    *,
    status: str = "ready_for_review",
) -> models.VideoInspirationStructuredHandoffResponse | None:
    row = db.query(DBVideoInspirationJob).filter(DBVideoInspirationJob.id == job_id).first()
    if row is None:
        return None
    handoff = create_or_update_handoff(row, db, status=status)
    return models.VideoInspirationStructuredHandoffResponse.model_validate(handoff)


def list_handoffs_for_job(job_id: str, db: Session) -> models.VideoInspirationHandoffListResponse:
    rows = (
        db.query(DBVideoInspirationHandoff)
        .filter(DBVideoInspirationHandoff.job_id == job_id)
        .order_by(DBVideoInspirationHandoff.updated_at.desc())
        .all()
    )
    return models.VideoInspirationHandoffListResponse(
        items=[models.VideoInspirationStructuredHandoffResponse.model_validate(row) for row in rows],
        total=len(rows),
    )


def create_project_memory_cards(
    project: DBVideoProject,
    *,
    source_type: str,
    source_ref_id: str,
    items: list[tuple[str, str, Any]],
    db: Session,
    replace: bool = True,
    commit: bool = True,
) -> list[DBVideoProjectMemoryCard]:
    """Materialize approved handoff content into project-scope memory cards."""
    existing = (
        db.query(DBVideoProjectMemoryCard)
        .filter(
            DBVideoProjectMemoryCard.project_id == project.id,
            DBVideoProjectMemoryCard.source_type == source_type,
            DBVideoProjectMemoryCard.source_ref_id == source_ref_id,
        )
        .order_by(DBVideoProjectMemoryCard.card_type.asc(), DBVideoProjectMemoryCard.created_at.asc())
        .all()
    )
    if existing and not replace:
        return existing
    if existing:
        db.query(DBVideoProjectMemoryCard).filter(
            DBVideoProjectMemoryCard.project_id == project.id,
            DBVideoProjectMemoryCard.source_type == source_type,
            DBVideoProjectMemoryCard.source_ref_id == source_ref_id,
        ).delete(synchronize_session=False)

    now = _now()
    rows: list[DBVideoProjectMemoryCard] = []
    for card_type, title, content in items:
        if not _has_meaningful_content(content):
            continue
        if isinstance(content, dict):
            normalized = content
        elif isinstance(content, list):
            normalized = {"items": content}
        else:
            normalized = {"value": content}
        row = DBVideoProjectMemoryCard(
            id=str(uuid.uuid4()),
            project_id=project.id,
            series_id=project.series_id,
            memory_scope="project",
            card_type=card_type,
            title=title,
            content_json=normalized,
            status="approved",
            source_type=source_type,
            source_ref_id=source_ref_id,
            revision=1,
            created_at=now,
            updated_at=now,
            approved_at=now,
        )
        db.add(row)
        rows.append(row)
    if commit:
        db.commit()
    else:
        db.flush()
    return rows


def create_project_memory_from_handoff(project: DBVideoProject, handoff: DBVideoInspirationHandoff, db: Session) -> list[DBVideoProjectMemoryCard]:
    payload = _as_dict(handoff.payload_json)
    target = _as_dict(payload.get("target_content"))
    lessons = _as_dict(payload.get("learnable_lessons"))
    items = [
        ("project_identity", "Nhận diện dự án", {"title": project.title, "topic": project.topic, "target_language": project.target_language}),
        ("target_audience", "Khách hàng mục tiêu", target.get("target_audience")),
        ("video_goal", "Mục tiêu video", target.get("video_goal")),
        ("content_spine", "Trục nội dung", target.get("content_spine") or lessons.get("content_spine")),
        ("hook_and_payoff", "Hook và payoff", target.get("hook_contract")),
        ("retention_map", "Retention map", lessons.get("retention_map")),
        ("character_state", "Nhân vật và bối cảnh", target.get("character_and_setting_state")),
        ("visual_direction", "Định hướng hình ảnh", target.get("visual_direction")),
        ("audio_direction", "Định hướng âm thanh", target.get("audio_direction")),
        ("voice_and_language", "Voice và ngôn ngữ", target.get("voice_and_language")),
        ("approved_decision", "Quyết định đã duyệt", target.get("approved_script")),
        ("must_have", "Điều bắt buộc", target.get("must_have")),
        ("avoid", "Điều cần tránh", {"avoid": target.get("avoid"), "originality_boundaries": payload.get("originality_boundaries")}),
        ("source_evidence", "Bằng chứng nguồn", {"evidence_refs": payload.get("evidence_refs"), "limitations": payload.get("limitations")}),
    ]
    return create_project_memory_cards(
        project,
        source_type="handoff",
        source_ref_id=handoff.id,
        items=items,
        db=db,
    )


def plan_target_timeline(project: DBVideoProject, handoff: DBVideoInspirationHandoff, db: Session) -> list[DBVideoProjectTargetTimelineBeat]:
    payload = _as_dict(handoff.payload_json)
    target = _as_dict(payload.get("target_content"))
    lessons = _as_dict(payload.get("learnable_lessons"))
    source_beats = [item for item in _as_list(lessons.get("retention_map")) if isinstance(item, dict)]
    duration = int(project.target_duration_seconds or 0)
    if duration <= 0:
        duration = max(20, min(180, len(source_beats) * int(project.prompt_segment_duration_seconds or 8) or 45))
    segment_count = int(project.prompt_segment_count or 0) or max(1, len(source_beats) or math.ceil(duration / max(5, int(project.prompt_segment_duration_seconds or 8))))
    segment_count = max(1, min(40, segment_count))
    segment_duration = duration / segment_count
    db.query(DBVideoProjectTargetTimelineBeat).filter(DBVideoProjectTargetTimelineBeat.project_id == project.id).delete(synchronize_session=False)
    rows: list[DBVideoProjectTargetTimelineBeat] = []
    now = _now()
    for index in range(segment_count):
        source = source_beats[index % len(source_beats)] if source_beats else {}
        start = round(index * segment_duration, 3)
        end = round(duration if index == segment_count - 1 else (index + 1) * segment_duration, 3)
        beat = DBVideoProjectTargetTimelineBeat(
            id=str(uuid.uuid4()),
            project_id=project.id,
            handoff_id=handoff.id,
            beat_order=index + 1,
            start_seconds=start,
            end_seconds=end,
            duration_seconds=max(0.0, end - start),
            role=_truncate(source.get("role") or ("hook" if index == 0 else "development"), 80),
            content=_truncate(source.get("why_continue") or source.get("content") or target.get("content_spine"), 8000),
            viewer_question=_truncate(source.get("viewer_question_before") or _as_dict(target.get("hook_contract")).get("viewer_question"), 4000),
            new_information=_truncate(source.get("new_information") or target.get("video_goal"), 4000),
            micro_payoff=_truncate(source.get("micro_payoff") or _as_dict(target.get("hook_contract")).get("payoff"), 4000),
            visual_direction=_truncate(target.get("visual_direction"), 4000),
            audio_direction=_truncate(target.get("audio_direction"), 4000),
            evidence_refs_json=_as_list(source.get("evidence_refs")),
            source_lesson_refs_json=[{"type": "retention_beat", "order": source.get("order") or source.get("beat_order")}],
            revision=1,
            created_at=now,
            updated_at=now,
        )
        db.add(beat)
        rows.append(beat)
    db.commit()
    return rows


def list_project_memory(project_id: str, db: Session) -> models.VideoProjectMemoryListResponse:
    rows = (
        db.query(DBVideoProjectMemoryCard)
        .filter(DBVideoProjectMemoryCard.project_id == project_id)
        .order_by(DBVideoProjectMemoryCard.card_type.asc(), DBVideoProjectMemoryCard.created_at.asc())
        .all()
    )
    return models.VideoProjectMemoryListResponse(items=[models.VideoProjectMemoryCardResponse.model_validate(row) for row in rows], total=len(rows))


def list_target_timeline(project_id: str, db: Session) -> models.VideoProjectTargetTimelineResponse:
    rows = (
        db.query(DBVideoProjectTargetTimelineBeat)
        .filter(DBVideoProjectTargetTimelineBeat.project_id == project_id)
        .order_by(DBVideoProjectTargetTimelineBeat.beat_order.asc())
        .all()
    )
    return models.VideoProjectTargetTimelineResponse(items=[models.VideoProjectTargetTimelineBeatResponse.model_validate(row) for row in rows], total=len(rows))


def compile_context(
    project_id: str,
    data: models.VideoProjectContextCompileRequest,
    db: Session,
) -> models.VideoProjectContextSnapshotResponse:
    project = db.query(DBVideoProject).filter(DBVideoProject.id == project_id).first()
    if project is None:
        raise VideoProjectMemoryError("Không tìm thấy project AI Video.", error_code="VIDEO_PROJECT_NOT_FOUND", status_code=404)
    memory = list_project_memory(project_id, db).items
    timeline = list_target_timeline(project_id, db).items
    pinned_types = {"project_identity", "video_goal", "content_spine", "hook_and_payoff", "approved_decision"}
    if data.task_type in {"voice", "subtitle"}:
        selected_memory = [card for card in memory if card.card_type in {"voice_and_language", "approved_decision", "approved_script_seed", "hook_and_payoff"}]
        selected_timeline = []
    elif data.task_type == "story":
        selected_memory = [
            card
            for card in memory
            if card.card_type
            in pinned_types
            | {
                "target_audience",
                "retention_map",
                "selected_ideas",
                "approved_script_seed",
                "research_findings",
                "must_have",
                "avoid",
                "source_evidence",
            }
        ]
        selected_timeline = timeline[:8]
    else:
        selected_memory = [
            card
            for card in memory
            if card.card_type
            in pinned_types
            | {
                "visual_direction",
                "audio_direction",
                "retention_map",
                "selected_ideas",
                "approved_script_seed",
                "must_have",
                "avoid",
            }
        ]
        selected_timeline = timeline[:12]
    context = {
        "task_type": data.task_type,
        "project": {"id": project.id, "title": project.title, "target_language": project.target_language, "series_id": project.series_id},
        "pinned": [card.model_dump(mode="json") for card in selected_memory if card.card_type in pinned_types],
        "project_memory": [card.model_dump(mode="json") for card in selected_memory],
        "target_timeline": [beat.model_dump(mode="json") for beat in selected_timeline],
        "rules": {
            "source_transcript_is_evidence_only": True,
            "voice_and_subtitle_use_approved_target_narration": True,
            "do_not_copy_source_shot_sequence": True,
        },
    }
    source_refs = [{"type": "project_memory", "id": card.id, "card_type": card.card_type} for card in selected_memory]
    source_refs.extend({"type": "target_timeline", "id": beat.id, "beat_order": beat.beat_order} for beat in selected_timeline)
    row = DBVideoProjectContextSnapshot(
        id=str(uuid.uuid4()),
        project_id=project_id,
        task_type=data.task_type,
        artifact_type=data.artifact_type,
        artifact_id=data.artifact_id,
        context_json=context,
        source_refs_json=source_refs,
        created_at=_now(),
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return models.VideoProjectContextSnapshotResponse.model_validate(row)


def list_context_snapshots(project_id: str, db: Session, *, limit: int = 20) -> models.VideoProjectContextSnapshotListResponse:
    rows = (
        db.query(DBVideoProjectContextSnapshot)
        .filter(DBVideoProjectContextSnapshot.project_id == project_id)
        .order_by(DBVideoProjectContextSnapshot.created_at.desc())
        .limit(limit)
        .all()
    )
    total = db.query(func.count(DBVideoProjectContextSnapshot.id)).filter(DBVideoProjectContextSnapshot.project_id == project_id).scalar() or 0
    return models.VideoProjectContextSnapshotListResponse(items=[models.VideoProjectContextSnapshotResponse.model_validate(row) for row in rows], total=total)


def mark_handoff_consumed(handoff: DBVideoInspirationHandoff, project_id: str, db: Session) -> None:
    handoff.created_project_id = project_id
    handoff.status = "consumed"
    handoff.updated_at = _now()
    db.commit()


def record_project_dependency(project_id: str, dependency_type: str, dependency_id: str, revision: int, db: Session) -> None:
    project = db.query(DBVideoProject).filter(DBVideoProject.id == project_id).first()
    if project is None or not project.series_id:
        return
    artifact_ids = [
        project_id if suffix == "project" else f"{project_id}:{suffix}"
        for _artifact_type, suffix, _scope in TASK_DEPENDENCY_SCOPES
    ]
    db.query(DBArtifactDependencySnapshot).filter(
        DBArtifactDependencySnapshot.series_id == project.series_id,
        DBArtifactDependencySnapshot.dependency_type == dependency_type,
        DBArtifactDependencySnapshot.dependency_id == dependency_id,
        DBArtifactDependencySnapshot.artifact_id.in_(artifact_ids),
    ).delete(synchronize_session=False)
    now = _now()
    for artifact_type, suffix, scope in TASK_DEPENDENCY_SCOPES:
        row = DBArtifactDependencySnapshot(
            id=str(uuid.uuid4()),
            series_id=project.series_id,
            artifact_type=artifact_type,
            artifact_id=project_id if suffix == "project" else f"{project_id}:{suffix}",
            artifact_revision=1,
            dependency_type=dependency_type,
            dependency_id=dependency_id,
            dependency_revision=revision,
            dependency_scope=scope,
            metadata_json={
                "source": "video_inspiration_handoff",
                "project_id": project_id,
                "task": suffix,
                "target_scope": "project",
            },
            created_at=now,
        )
        db.add(row)
    db.commit()

def mark_handoffs_stale_for_job(
    job_id: str,
    db: Session,
    *,
    changed_scope: str,
    reason_vi: str,
    new_revision: int | None = None,
) -> None:
    rows = (
        db.query(DBVideoInspirationHandoff)
        .filter(DBVideoInspirationHandoff.job_id == job_id)
        .all()
    )
    now = _now()
    for handoff in rows:
        old_revision = int(handoff.revision or 1)
        handoff.status = "stale"
        handoff.revision = old_revision + 1
        handoff.updated_at = now
        project_id = handoff.created_project_id
        if not project_id:
            continue
        project = db.query(DBVideoProject).filter(DBVideoProject.id == project_id).first()
        if project is None:
            continue
        project.planning_status = "stale"
        project.planning_error = reason_vi
        project.updated_at = now
        video_state.mark_package_stale(project, db)
        if project.series_id:
            series_references.mark_dependency_stale(
                project.series_id,
                dependency_type="video_inspiration_handoff",
                dependency_id=handoff.id,
                changed_scope=changed_scope,
                db=db,
                old_revision=old_revision,
                new_revision=new_revision or int(handoff.revision or old_revision + 1),
                reason_vi=reason_vi,
                commit=False,
            )
    db.commit()
