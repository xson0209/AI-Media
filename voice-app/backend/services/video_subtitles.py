"""Subtitle generation for AI Video Assistant Premiere exports."""

from __future__ import annotations

import json
import re
import uuid
from datetime import datetime

from sqlalchemy.orm import Session

from .. import models
from ..database import (
    VideoProject as DBVideoProject,
    VideoScene as DBVideoScene,
    VideoShot as DBVideoShot,
    VideoSubtitle as DBVideoSubtitle,
)
from . import series_brain, video_errors, video_observability, video_rendering, video_state, video_storage

_SENTENCE_SPLIT = re.compile(r"(?<=[.!?\u3002\uff01\uff1f])\s+")
_MAX_CHARS_BY_RATIO = {
    "9:16": 34,
    "1:1": 46,
    "16:9": 68,
}
_MIN_CUE_SECONDS = 1.2


class VideoSubtitleError(ValueError):
    """Raised when subtitle generation cannot continue."""

    def __init__(self, message: str, *, error_code: str = "VIDEO_SUBTITLE_ERROR"):
        super().__init__(message)
        self.error_code = error_code


def _ordered_scenes(project_id: str, db: Session) -> list[DBVideoScene]:
    return (
        db.query(DBVideoScene)
        .filter(DBVideoScene.project_id == project_id)
        .order_by(DBVideoScene.scene_order.asc())
        .all()
    )


def _ordered_shots(project_id: str, db: Session) -> list[DBVideoShot]:
    return (
        db.query(DBVideoShot)
        .filter(DBVideoShot.project_id == project_id)
        .order_by(DBVideoShot.shot_order.asc(), DBVideoShot.created_at.asc())
        .all()
    )


def _requires_narration(scene: DBVideoScene) -> bool:
    return bool((scene.dialogue or "").strip()) and not bool(scene.no_narration)


def _requires_shot_narration(shot: DBVideoShot) -> bool:
    return bool((shot.english_narration or "").strip())


def _subtitle_response(row: DBVideoSubtitle) -> models.VideoSubtitleResponse:
    cues: list[models.VideoSubtitleCue] = []
    if row.cues_json:
        try:
            cues = [models.VideoSubtitleCue.model_validate(item) for item in json.loads(row.cues_json)]
        except Exception as exc:
            video_errors.log_error(
                "Stored subtitle cues could not be parsed",
                exc=exc,
                project_id=row.project_id,
                subtitle_id=row.id,
                step_name="subtitle_response",
            )
            cues = []
    return models.VideoSubtitleResponse(
        id=row.id,
        project_id=row.project_id,
        status=row.status,
        subtitle_path=row.subtitle_path,
        format=row.format,
        cues=cues,
        created_at=row.created_at,
        updated_at=row.updated_at,
    )


def _format_srt_timestamp(seconds: float) -> str:
    total_ms = max(0, round(seconds * 1000))
    hours = total_ms // 3_600_000
    total_ms %= 3_600_000
    minutes = total_ms // 60_000
    total_ms %= 60_000
    secs = total_ms // 1000
    millis = total_ms % 1000
    return f"{hours:02d}:{minutes:02d}:{secs:02d},{millis:03d}"


def _split_long_wordsafe(text: str, max_chars: int) -> list[str]:
    words = text.split()
    chunks: list[str] = []
    current: list[str] = []
    current_len = 0
    for word in words:
        extra = len(word) + (1 if current else 0)
        if current and current_len + extra > max_chars:
            chunks.append(" ".join(current))
            current = [word]
            current_len = len(word)
        else:
            current.append(word)
            current_len += extra
    if current:
        chunks.append(" ".join(current))
    return chunks or [text.strip()]


def _merge_caption_chunks_for_duration(chunks: list[str], *, max_chunks: int, max_chars: int) -> list[str]:
    while len(chunks) > max_chunks:
        merged: list[str] = []
        changed = False
        index = 0
        while index < len(chunks):
            if index + 1 < len(chunks):
                candidate = f"{chunks[index]} {chunks[index + 1]}".strip()
                if len(candidate) <= max_chars:
                    merged.append(candidate)
                    index += 2
                    changed = True
                    continue
            merged.append(chunks[index])
            index += 1
        if not changed:
            break
        chunks = merged
    return chunks


def _split_caption_text(text: str, *, aspect_ratio: str, duration: float) -> list[str]:
    max_chars = _MAX_CHARS_BY_RATIO.get(aspect_ratio, 52)
    sentences = [part.strip() for part in _SENTENCE_SPLIT.split(text.strip()) if part.strip()]
    chunks: list[str] = []
    for sentence in sentences or [text.strip()]:
        if len(sentence) <= max_chars:
            chunks.append(sentence)
        else:
            chunks.extend(_split_long_wordsafe(sentence, max_chars))

    max_chunks_for_duration = max(1, int(max(duration, _MIN_CUE_SECONDS) // _MIN_CUE_SECONDS))
    return _merge_caption_chunks_for_duration(chunks, max_chunks=max_chunks_for_duration, max_chars=max_chars)


def _caption_chunk_durations(chunks: list[str], total_duration: float) -> list[float]:
    if not chunks:
        return []
    if len(chunks) == 1:
        return [total_duration]

    # Short captions keep a readable floor; longer phrases get more of the
    # spoken audio so the yellow karaoke highlight drifts less.
    weights = [max(8, len(re.sub(r"\s+", "", chunk))) for chunk in chunks]
    total_weight = sum(weights)
    durations = [total_duration * weight / total_weight for weight in weights]
    durations[-1] += total_duration - sum(durations)
    return durations

def _cue_models(project: DBVideoProject, scenes: list[DBVideoScene]) -> list[models.VideoSubtitleCue]:
    cues: list[models.VideoSubtitleCue] = []
    cursor = 0.0
    cue_index = 1
    for scene in scenes:
        if not _requires_narration(scene):
            continue
        duration = float(scene.audio_duration or 0)
        chunks = _split_caption_text(scene.dialogue, aspect_ratio=project.aspect_ratio, duration=duration)
        chunk_durations = _caption_chunk_durations(chunks, duration)
        for chunk, cue_duration in zip(chunks, chunk_durations, strict=True):
            start = cursor
            end = cursor + cue_duration
            cues.append(
                models.VideoSubtitleCue(
                    index=cue_index,
                    scene_id=scene.id,
                    scene_order=scene.scene_order,
                    start_seconds=round(start, 3),
                    end_seconds=round(end, 3),
                    text=chunk,
                )
            )
            cue_index += 1
            cursor = end
    return cues


def _shot_cue_models(project: DBVideoProject, shots: list[DBVideoShot]) -> list[models.VideoSubtitleCue]:
    cues: list[models.VideoSubtitleCue] = []
    cursor = 0.0
    cue_index = 1
    for shot in shots:
        if not _requires_shot_narration(shot):
            duration = video_rendering.resolve_shot_duration(shot)
            if duration is None:
                raise VideoSubtitleError(
                    f"Segment {video_storage.shot_number(shot.shot_order)} không có narration nhưng thiếu duration timeline hợp lệ.",
                    error_code="VIDEO_SUBTITLE_TIMELINE_DURATION_REQUIRED",
                )
            cursor += float(duration)
            continue
        duration = float(shot.audio_duration or 0)
        chunks = _split_caption_text(shot.english_narration or "", aspect_ratio=project.aspect_ratio, duration=duration)
        chunk_durations = _caption_chunk_durations(chunks, duration)
        for chunk, cue_duration in zip(chunks, chunk_durations, strict=True):
            start = cursor
            end = cursor + cue_duration
            cues.append(
                models.VideoSubtitleCue(
                    index=cue_index,
                    scene_id=shot.scene_id,
                    scene_order=None,
                    shot_id=shot.id,
                    shot_order=shot.shot_order,
                    start_seconds=round(start, 3),
                    end_seconds=round(end, 3),
                    text=chunk,
                )
            )
            cue_index += 1
            cursor = end
    return cues

def mark_subtitle_stale(
    project_id: str,
    db: Session,
    *,
    reason: str | None = None,
    commit: bool = False,
) -> bool:
    row = db.query(DBVideoSubtitle).filter(DBVideoSubtitle.project_id == project_id).first()
    if row is None:
        return False
    row.status = "stale"
    row.updated_at = datetime.utcnow()
    if commit:
        db.commit()
    if reason:
        video_observability.log_event(
            db,
            step_name="subtitle_stale",
            status="info",
            project_id=project_id,
            message=reason,
            technical_details={"subtitle_id": row.id},
        )
    return True


def _srt_content(cues: list[models.VideoSubtitleCue]) -> str:
    blocks = []
    for cue in cues:
        blocks.append(
            "\n".join(
                [
                    str(cue.index),
                    f"{_format_srt_timestamp(cue.start_seconds)} --> {_format_srt_timestamp(cue.end_seconds)}",
                    cue.text.strip(),
                ]
            )
        )
    return "\n\n".join(blocks).strip() + "\n"


def validate_subtitle_inputs(project_id: str, db: Session) -> tuple[DBVideoProject, list[DBVideoScene], list[DBVideoShot]]:
    project = db.query(DBVideoProject).filter(DBVideoProject.id == project_id).first()
    if project is None:
        raise VideoSubtitleError("Không tìm thấy dự án video.", error_code="VIDEO_PROJECT_NOT_FOUND")
    scenes = _ordered_scenes(project_id, db)
    shots = _ordered_shots(project_id, db)

    use_shots = getattr(project, "phase", "phase1") == "phase2" and any(_requires_shot_narration(shot) for shot in shots)
    if use_shots:
        missing_shot_labels: list[str] = []
        for shot in shots:
            if not _requires_shot_narration(shot):
                continue
            if shot.voice_status != "completed" or not shot.audio_path or not shot.audio_duration:
                missing_shot_labels.append(video_storage.shot_number(shot.shot_order))
        if missing_shot_labels:
            message = "Chưa thể tạo phụ đề vì còn shot chưa có giọng đọc hoàn tất: " + ", ".join(missing_shot_labels)
            video_observability.log_event(
                db,
                step_name="subtitle_validation",
                status="failure",
                project_id=project_id,
                error_code="VIDEO_SUBTITLE_MISSING_NARRATION",
                message=message,
                technical_details={"missing_shots": missing_shot_labels, "source": "shots"},
            )
            raise VideoSubtitleError(message, error_code="VIDEO_SUBTITLE_MISSING_NARRATION")
        return project, [], shots

    missing_scene_labels: list[str] = []
    for scene in scenes:
        if not _requires_narration(scene):
            continue
        if scene.voice_status != "completed" or not scene.audio_path or not scene.audio_duration:
            missing_scene_labels.append(video_storage.scene_number(scene.scene_order))
    if missing_scene_labels:
        message = "Chưa thể tạo phụ đề vì còn cảnh chưa có giọng đọc hoàn tất: " + ", ".join(missing_scene_labels)
        video_observability.log_event(
            db,
            step_name="subtitle_validation",
            status="failure",
            project_id=project_id,
            error_code="VIDEO_SUBTITLE_MISSING_NARRATION",
            message=message,
            technical_details={"missing_scenes": missing_scene_labels, "source": "scenes"},
        )
        raise VideoSubtitleError(message, error_code="VIDEO_SUBTITLE_MISSING_NARRATION")
    return project, scenes, []


def generate_subtitle(project_id: str, db: Session) -> models.VideoSubtitleResponse:
    project, scenes, shots = validate_subtitle_inputs(project_id, db)
    cues = _shot_cue_models(project, shots) if shots else _cue_models(project, scenes)
    if not cues:
        video_observability.log_event(
            db,
            step_name="subtitle_generation",
            status="failure",
            project_id=project_id,
            error_code="VIDEO_SUBTITLE_NO_DIALOGUE",
            message="Dự án chưa có lời thoại nào cần tạo phụ đề.",
            technical_details={"scene_count": len(scenes), "shot_count": len(shots)},
        )
        raise VideoSubtitleError(
            "Dự án chưa có lời thoại nào cần tạo phụ đề.",
            error_code="VIDEO_SUBTITLE_NO_DIALOGUE",
        )

    if project.series_id:
        try:
            series_brain.compile_prompt_context(
                project.series_id,
                db,
                task_type="subtitle",
                episode_number=project.episode_number,
                project_id=project_id,
                user_input="\n".join(cue.text for cue in cues),
                current_payload={
                    "cue_count": len(cues),
                    "source": "shots" if shots else "scenes",
                    "cues": [cue.model_dump() for cue in cues],
                },
                persist_trace=True,
            )
        except Exception as exc:
            video_observability.log_event(
                db,
                step_name="subtitle_series_context_trace",
                status="warning",
                project_id=project_id,
                error_code="SERIES_CONTEXT_TRACE_FAILED",
                exc=exc,
                message="Khong luu duoc trace bo nho series cho subtitle.",
            )

    now = datetime.utcnow()
    existing = db.query(DBVideoSubtitle).filter(DBVideoSubtitle.project_id == project_id).first()
    if existing is not None:
        video_storage.remove_artifact_file(existing.subtitle_path)
        row = existing
        row.updated_at = now
    else:
        row = DBVideoSubtitle(id=str(uuid.uuid4()), project_id=project_id, created_at=now, updated_at=now)
        db.add(row)

    subtitle_dir = video_storage.get_project_subdir(project_id, "subtitles")
    subtitle_path = subtitle_dir / f"subtitle-{row.id}.srt"
    subtitle_path.write_text(_srt_content(cues), encoding="utf-8")

    row.status = "completed"
    row.subtitle_path = video_storage.to_artifact_storage_path(subtitle_path)
    row.format = "srt"
    row.cues_json = json.dumps([cue.model_dump() for cue in cues], ensure_ascii=False)
    for scene in scenes:
        if _requires_narration(scene):
            scene.subtitle_status = "completed"
            scene.updated_at = now
    for shot in shots:
        if _requires_shot_narration(shot):
            shot.subtitle_status = "completed"
            shot.updated_at = now
    video_rendering.mark_render_outputs_stale(project_id, db)
    video_state.mark_package_stale(project, db)
    db.commit()
    db.refresh(row)
    video_errors.log_step(
        "Subtitle generated",
        project_id=project_id,
        subtitle_id=row.id,
        cue_count=len(cues),
        file_path=row.subtitle_path,
        step_name="subtitle_generation",
    )
    return _subtitle_response(row)


def get_subtitle(project_id: str, db: Session) -> models.VideoSubtitleResponse | None:
    row = db.query(DBVideoSubtitle).filter(DBVideoSubtitle.project_id == project_id).first()
    if row is None:
        return None
    return _subtitle_response(row)


def get_subtitle_download(project_id: str, db: Session) -> tuple[str, str] | None:
    project = db.query(DBVideoProject).filter(DBVideoProject.id == project_id).first()
    row = db.query(DBVideoSubtitle).filter(DBVideoSubtitle.project_id == project_id).first()
    if project is None or row is None or row.status != "completed" or not row.subtitle_path:
        return None
    path = video_storage.resolve_artifact_storage_path(row.subtitle_path)
    if path is None or not path.exists():
        return None
    return video_storage.subtitle_filename(project.title), path.read_text(encoding="utf-8")
