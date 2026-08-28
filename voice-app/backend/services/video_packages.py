"""Premiere-ready material package export for AI Video Assistant."""

from __future__ import annotations

import csv
import io
import json
import mimetypes
import uuid
import zipfile
from datetime import datetime
from pathlib import Path, PurePosixPath

from sqlalchemy.orm import Session

from .. import config, models
from ..database import (
    VideoPackageExport as DBVideoPackageExport,
    VideoProject as DBVideoProject,
    VideoScene as DBVideoScene,
    VideoSceneAsset as DBVideoSceneAsset,
    VideoScenePrompt as DBVideoScenePrompt,
    VideoShot as DBVideoShot,
    VideoShotPrompt as DBVideoShotPrompt,
    VideoSubtitle as DBVideoSubtitle,
)
from . import video_assets, video_errors, video_language, video_purpose, video_rendering, video_speech, video_storage

DEFAULT_PROMPT_SEGMENT_SECONDS = 8
DEFAULT_MICRO_SCENES_PER_PROMPT = 4


class VideoPackageError(ValueError):
    """Raised when a package export cannot be created."""

    def __init__(self, message: str, *, error_code: str = "VIDEO_PACKAGE_ERROR"):
        super().__init__(message)
        self.error_code = error_code


def _ordered_scenes(project_id: str, db: Session) -> list[DBVideoScene]:
    return (
        db.query(DBVideoScene)
        .filter(DBVideoScene.project_id == project_id)
        .order_by(DBVideoScene.scene_order.asc())
        .all()
    )


def _approved_scenes(project_id: str, db: Session) -> list[DBVideoScene]:
    return [scene for scene in _ordered_scenes(project_id, db) if scene.approved]

def _project_prompt_duration(project: DBVideoProject) -> int:
    return int(getattr(project, "prompt_segment_duration_seconds", None) or DEFAULT_PROMPT_SEGMENT_SECONDS)

def _project_micro_scenes_per_prompt(project: DBVideoProject) -> int:
    return int(getattr(project, "micro_scenes_per_prompt", None) or DEFAULT_MICRO_SCENES_PER_PROMPT)

def _micro_scene_text(micro_scenes) -> str:
    if not isinstance(micro_scenes, list) or not micro_scenes:
        return ""
    lines: list[str] = []
    for item in micro_scenes:
        if not isinstance(item, dict):
            continue
        start = item.get("start_seconds", "")
        end = item.get("end_seconds", "")
        label = f"{start}-{end}s" if start != "" and end != "" else ""
        description = item.get("description_vi") or item.get("visual_action") or ""
        camera = item.get("camera_note") or ""
        lines.append(" | ".join(part for part in [label, description, camera] if part))
    return "\n".join(lines)


def _requires_narration(scene: DBVideoScene) -> bool:
    return bool((scene.dialogue or "").strip()) and not bool(scene.no_narration)


def _latest_prompt(project_id: str, scene_id: str, db: Session) -> DBVideoScenePrompt | None:
    return (
        db.query(DBVideoScenePrompt)
        .filter(DBVideoScenePrompt.project_id == project_id, DBVideoScenePrompt.scene_id == scene_id)
        .order_by(DBVideoScenePrompt.version.desc(), DBVideoScenePrompt.created_at.desc())
        .first()
    )

def _ordered_shots(project_id: str, db: Session) -> list[DBVideoShot]:
    return (
        db.query(DBVideoShot)
        .filter(DBVideoShot.project_id == project_id)
        .order_by(DBVideoShot.shot_order.asc(), DBVideoShot.created_at.asc())
        .all()
    )

def _sync_busy_voice_statuses(project_id: str, db: Session) -> None:
    from . import video_voice

    busy_states = {"generating", "loading_model", "queued"}
    scene_ids = [
        row[0]
        for row in db.query(DBVideoScene.id)
        .filter(
            DBVideoScene.project_id == project_id,
            DBVideoScene.generation_id.isnot(None),
            DBVideoScene.voice_status.in_(busy_states),
        )
        .all()
    ]
    for scene_id in scene_ids:
        video_voice.sync_scene_voice_status(project_id, scene_id, db)

    shot_ids = [
        row[0]
        for row in db.query(DBVideoShot.id)
        .filter(
            DBVideoShot.project_id == project_id,
            DBVideoShot.generation_id.isnot(None),
            DBVideoShot.voice_status.in_(busy_states),
        )
        .all()
    ]
    for shot_id in shot_ids:
        video_voice.sync_shot_voice_status(project_id, shot_id, db)

def _latest_shot_prompt(project_id: str, shot_id: str, db: Session) -> DBVideoShotPrompt | None:
    return (
        db.query(DBVideoShotPrompt)
        .filter(DBVideoShotPrompt.project_id == project_id, DBVideoShotPrompt.shot_id == shot_id)
        .order_by(DBVideoShotPrompt.version.desc(), DBVideoShotPrompt.created_at.desc())
        .first()
    )


def _completed_subtitle(project_id: str, db: Session) -> DBVideoSubtitle | None:
    return (
        db.query(DBVideoSubtitle)
        .filter(DBVideoSubtitle.project_id == project_id, DBVideoSubtitle.status == "completed")
        .first()
    )


def _safe_zip_part(value: str, *, fallback: str) -> str:
    part = video_storage.sanitize_download_filename(value, fallback=fallback, max_length=100)
    part = part.replace("/", " ").replace("\\", " ").strip(" .")
    if part in {"", ".", ".."}:
        return fallback
    return part


def _zip_name(*parts: str) -> str:
    safe_parts = [_safe_zip_part(part, fallback="file") for part in parts]
    path = PurePosixPath(*safe_parts)
    if path.is_absolute() or ".." in path.parts:
        raise VideoPackageError("Tên file trong ZIP không an toàn.", error_code="VIDEO_PACKAGE_UNSAFE_PATH")
    return str(path)


def _audio_path(scene: DBVideoScene) -> Path | None:
    path = config.resolve_storage_path(scene.audio_path)
    if path is None or not path.exists() or not path.is_file():
        return None
    return path


def _audio_filename(scene: DBVideoScene) -> str | None:
    path = _audio_path(scene)
    if path is None:
        return None
    return video_storage.voice_filename(scene.scene_order, path.suffix or ".wav")

def _requires_shot_narration(shot: DBVideoShot) -> bool:
    return bool((shot.english_narration or "").strip())

def _shot_audio_path(shot: DBVideoShot) -> Path | None:
    path = config.resolve_storage_path(shot.audio_path)
    if path is None or not path.exists() or not path.is_file():
        return None
    return path

def _shot_audio_filename(shot: DBVideoShot, scenes_by_id: dict[str, DBVideoScene]) -> str | None:
    path = _shot_audio_path(shot)
    if path is None:
        return None
    scene = scenes_by_id.get(shot.scene_id or "")
    return video_storage.shot_voice_filename(scene.scene_order if scene else None, shot.shot_order, path.suffix or ".wav")


def _preview_filename(scene: DBVideoScene, asset: DBVideoSceneAsset | None) -> str | None:
    if asset is None:
        return None
    path = video_storage.resolve_artifact_storage_path(asset.file_path)
    if path is None:
        return None
    suffix = path.suffix or mimetypes.guess_extension(asset.mime_type or "") or ".png"
    return video_storage.sanitize_download_filename(
        f"Ảnh preview - {video_storage.scene_number(scene.scene_order)}{suffix}",
        fallback=f"Anh preview - Canh {scene.scene_order:02d}{suffix}",
    )


def get_package_readiness(project_id: str, db: Session) -> models.VideoPackageReadinessResponse | None:
    project = db.query(DBVideoProject).filter(DBVideoProject.id == project_id).first()
    if project is None:
        return None
    _sync_busy_voice_statuses(project_id, db)

    scenes = _approved_scenes(project_id, db)
    shots = _ordered_shots(project_id, db)
    prompt_scene_ids = {
        row[0]
        for row in db.query(DBVideoScenePrompt.scene_id)
        .filter(DBVideoScenePrompt.project_id == project_id)
        .all()
    }
    missing_video_prompt_shots = [
        shot.id
        for shot in shots
        if _latest_shot_prompt(project_id, shot.id, db) is None or shot.prompt_status != "completed"
    ]
    missing_prompt = [] if shots else [scene.id for scene in scenes if scene.id not in prompt_scene_ids]
    if shots:
        missing_voice = []
        if video_speech.uses_veo_native_speech(project):
            clips = video_rendering.active_clips_for_project(project_id, db)
            missing_voice_shots = []
            for shot in shots:
                if not _requires_shot_narration(shot):
                    continue
                clip = clips.get(shot.id)
                clip_path = video_storage.resolve_artifact_storage_path(clip.file_path) if clip else None
                if (
                    clip is None
                    or clip.status != "ready"
                    or not clip.has_audio
                    or not clip.duration_seconds
                    or clip_path is None
                    or not clip_path.exists()
                ):
                    missing_voice_shots.append(shot.id)
        else:
            missing_voice_shots = [
                shot.id
                for shot in shots
                if _requires_shot_narration(shot)
                and (shot.voice_status != "completed" or not shot.audio_path or not shot.audio_duration or _shot_audio_path(shot) is None)
            ]
    else:
        missing_voice = [
            scene.id
            for scene in scenes
            if _requires_narration(scene)
            and (scene.voice_status != "completed" or not scene.audio_path or not scene.audio_duration or _audio_path(scene) is None)
        ]
        missing_voice_shots = []
    subtitle = _completed_subtitle(project_id, db)
    subtitle_path = video_storage.resolve_artifact_storage_path(subtitle.subtitle_path) if subtitle else None
    missing_subtitle = subtitle is None or subtitle_path is None or not subtitle_path.exists()

    reasons: list[str] = []
    if not scenes and not shots:
        reasons.append("Chưa có scene hoặc shot nào được duyệt.")
    if missing_prompt:
        labels = [video_storage.scene_number(scene.scene_order) for scene in scenes if scene.id in missing_prompt]
        reasons.append("Thiếu prompt ảnh: " + ", ".join(labels))
    if missing_video_prompt_shots:
        labels = [video_storage.shot_number(shot.shot_order) for shot in shots if shot.id in missing_video_prompt_shots]
        reasons.append("Thiếu prompt video đạt chất lượng: " + ", ".join(labels))
    if missing_voice:
        labels = [video_storage.scene_number(scene.scene_order) for scene in scenes if scene.id in missing_voice]
        reasons.append("Thiếu giọng đọc: " + ", ".join(labels))
    if missing_voice_shots:
        labels = [video_storage.shot_number(shot.shot_order) for shot in shots if shot.id in missing_voice_shots]
        reasons.append(
            ("Clip Veo thiếu audio lời thoại tiếng Việt: " if video_speech.uses_veo_native_speech(project) else "Thiếu giọng đọc: ")
            + ", ".join(labels)
        )
    if missing_subtitle:
        reasons.append("Chưa có file phụ đề .srt hoàn tất.")

    return models.VideoPackageReadinessResponse(
        project_id=project_id,
        language=video_language.normalize_video_language(getattr(project, "target_language", None)),
        speech_source=(
            video_speech.effective_speech_source(project)
            if getattr(project, "phase", "phase1") == "phase2"
            else video_speech.SPEECH_SOURCE_PROJECT_AUDIO
        ),
        video_purpose=video_purpose.normalize_video_purpose(getattr(project, "video_purpose", None)),
        dialogue_mode=video_purpose.normalize_dialogue_mode(getattr(project, "dialogue_mode", None), purpose=getattr(project, "video_purpose", None)),
        narration_density=video_purpose.normalize_narration_density(getattr(project, "narration_density", None), purpose=getattr(project, "video_purpose", None)),
        ready=bool(scenes or shots)
        and not missing_prompt
        and not missing_video_prompt_shots
        and not missing_voice
        and not missing_voice_shots
        and not missing_subtitle,
        missing_prompt_scene_ids=missing_prompt,
        missing_video_prompt_shot_ids=missing_video_prompt_shots,
        missing_voice_scene_ids=missing_voice,
        missing_voice_shot_ids=missing_voice_shots,
        missing_subtitle=missing_subtitle,
        missing_reasons=reasons,
    )


def _manifest(project: DBVideoProject, scenes: list[DBVideoScene], db: Session) -> models.VideoPackageManifestResponse:
    manifest_scenes: list[models.VideoPackageManifestScene] = []
    for scene in scenes:
        prompt_filename = video_storage.prompt_filename(scene.scene_order) if _latest_prompt(project.id, scene.id, db) else None
        audio_filename = _audio_filename(scene) if _requires_narration(scene) else None
        preview_asset = video_assets.get_active_preview_asset(project.id, scene.id, db)
        manifest_scenes.append(
            models.VideoPackageManifestScene(
                scene_id=scene.id,
                scene_order=scene.scene_order,
                title=scene.title,
                prompt_filename=prompt_filename,
                audio_filename=audio_filename,
                preview_image_filename=_preview_filename(scene, preview_asset),
                no_narration=bool(scene.no_narration),
            )
        )
    return models.VideoPackageManifestResponse(
        project_id=project.id,
        project_title=project.title,
        language=video_language.normalize_video_language(getattr(project, "target_language", None)),
        speech_source=(
            video_speech.effective_speech_source(project)
            if getattr(project, "phase", "phase1") == "phase2"
            else video_speech.SPEECH_SOURCE_PROJECT_AUDIO
        ),
        video_purpose=video_purpose.normalize_video_purpose(getattr(project, "video_purpose", None)),
        dialogue_mode=video_purpose.normalize_dialogue_mode(getattr(project, "dialogue_mode", None), purpose=getattr(project, "video_purpose", None)),
        narration_density=video_purpose.normalize_narration_density(getattr(project, "narration_density", None), purpose=getattr(project, "video_purpose", None)),
        call_to_action_style=getattr(project, "call_to_action_style", None),
        aspect_ratio=project.aspect_ratio,
        subtitle_filename=video_storage.subtitle_filename(project.title),
        scenes=manifest_scenes,
    )


def _guide_text(project: DBVideoProject) -> str:
    if getattr(project, "phase", "phase1") == "phase2":
        language_label = video_language.video_language_label(getattr(project, "target_language", None))
        prompt_duration = _project_prompt_duration(project)
        micro_count = _project_micro_scenes_per_prompt(project)
        native_speech = video_speech.uses_veo_native_speech(project)
        audio_guide = (
            "3. Video tieng Viet dung loi thoai/audio render truc tiep trong tung clip Veo 3; goi nay khong tao thu muc voice TTS rieng.\n"
            "4. Thu muc '04 - Phu de' chua file .srt tieng Viet, timing theo do dai clip Veo.\n\n"
            if native_speech
            else f"3. Thu muc '03 - Giong doc' chua file voice {language_label} da tao bang Voicebox.\n"
            f"4. Thu muc '04 - Phu de' chua file .srt {language_label} khop timing voice.\n\n"
        )
        return (
            f"Bo nguyen lieu prompt video - {project.title}\n\n"
            f"Video language: {language_label}.\n\n"
            f"Purpose: {video_purpose.normalize_video_purpose(getattr(project, 'video_purpose', None))}.\n"
            f"Dialogue mode: {video_purpose.normalize_dialogue_mode(getattr(project, 'dialogue_mode', None), purpose=getattr(project, 'video_purpose', None))}.\n"
            f"Narration density: {video_purpose.normalize_narration_density(getattr(project, 'narration_density', None), purpose=getattr(project, 'video_purpose', None))}.\n\n"
            f"1. Thu muc '01 - Kich ban' chua kich ban {language_label}, mo ta tieng Viet, continuity bible va segment list CSV.\n"
            f"2. Thu muc '02 - Prompt video' chua prompt goc cho tung segment {prompt_duration} giay, moi segment co {micro_count} canh nho, retention notes, chuyen canh va am thanh/SFX de ban dung khi dung video. Copy prompt goc sang cong cu tao video ben ngoai.\n"
            f"{audio_guide}"
            "Ban giai thich tieng Viet trong goi nay chi de doc hieu va duyet noi dung; no khong phai file phu de .srt cua video cuoi.\n"
            "Cac cue SFX/BGM trong goi nay la chi dan dung neu chua co audio asset that duoc mix vao MP4.\n"
            "Voicebox khong render MP4 trong goi ZIP nay. Ban dung prompt video, voice va subtitle trong tool dung video ben ngoai.\n"
        )
    return (
        f"Bo nguyen lieu cho Premiere - {project.title}\n\n"
        "1. Thu muc '01 - Prompt anh' chua prompt cho tung canh. Hay copy prompt sang cong cu tao anh ban dang dung.\n"
        "2. Thu muc '02 - Giong doc' chua file voice da tao theo tung canh. Keo cac file nay vao timeline Premiere theo dung thu tu.\n"
        "3. Thu muc '03 - Phu de' chua file .srt. Trong Premiere, import file nay de co subtitle khop timing voice.\n"
        "4. Thu muc '04 - Anh preview' chi la anh tham khao neu ban da upload vao Voicebox.\n\n"
        "Voicebox khong render video MP4 trong goi nay. Ban dung Premiere de ghep anh, voice, subtitle, nhac nen va hieu ung.\n"
    )

def _shot_list_csv(project: DBVideoProject, shots: list[DBVideoShot], db: Session) -> str:
    narration_header = f"narration_{video_language.normalize_video_language(getattr(project, 'target_language', None))}"
    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow([
        "scene_order",
        "segment_order",
        "duration",
        "vietnamese_description",
        narration_header,
        "speech_source",
        "speech_cues",
        "shot_type",
        "camera_angle",
        "framing",
        "camera_motion",
        "transition",
        "retention_role",
        "visual_surprise",
        "cut_reason",
        "transition_pack",
        "sound_design",
        "micro_scenes",
        "retainability_quality",
    ])
    scenes = {scene.id: scene for scene in _ordered_scenes(project.id, db)}
    for shot in shots:
        scene = scenes.get(shot.scene_id)
        writer.writerow([
            scene.scene_order if scene else "",
            shot.shot_order,
            shot.duration_seconds or "",
            shot.vietnamese_description or "",
            shot.english_narration or "",
            video_speech.effective_speech_source(project, shot),
            json.dumps(shot.speech_cues_json or [], ensure_ascii=False),
            shot.shot_type or "",
            shot.camera_angle or "",
            shot.framing or "",
            shot.camera_motion or "",
            shot.transition_to_next or "",
            (shot.retention_json or {}).get("retention_role", "") if isinstance(shot.retention_json, dict) else "",
            (shot.retention_json or {}).get("visual_surprise", "") if isinstance(shot.retention_json, dict) else "",
            (shot.retention_json or {}).get("cut_reason", "") if isinstance(shot.retention_json, dict) else "",
            json.dumps(shot.transition_json or {}, ensure_ascii=False),
            json.dumps(shot.sound_design_json or {}, ensure_ascii=False),
            json.dumps(shot.micro_scenes_json or [], ensure_ascii=False),
            json.dumps(shot.retainability_quality_check or {}, ensure_ascii=False),
        ])
    return buffer.getvalue()

def _phase2_story_text(project: DBVideoProject) -> str:
    language_label = video_language.video_language_label(getattr(project, "target_language", None))
    return "\n\n".join(
        part
        for part in [
            "# Story strategy\n" + (project.story_strategy or ""),
            f"# Detailed script ({language_label})\n" + (project.detailed_script or project.script_text or ""),
        ]
        if part.strip()
    ).strip() + "\n"

def _phase2_script_filename(project: DBVideoProject) -> str:
    language = video_language.normalize_video_language(getattr(project, "target_language", None))
    return "Kich ban tieng Viet.txt" if language == "vi" else "Kich ban tieng Anh.txt"

def _phase2_vietnamese_description(project: DBVideoProject, shots: list[DBVideoShot]) -> str:
    lines = [f"Mo ta tieng Viet - {project.title}", ""]
    for shot in shots:
        lines.append(f"Segment {shot.shot_order:02d}: {shot.vietnamese_description or ''}")
        micro_scenes = _micro_scene_text(shot.micro_scenes_json or [])
        if micro_scenes:
            lines.extend(["Canh nho:", micro_scenes, ""])
    return "\n".join(lines).strip() + "\n"

def _phase2_creative_direction_text(project: DBVideoProject, shots: list[DBVideoShot]) -> str:
    lines = [f"Creative direction - {project.title}", ""]
    if project.retention_plan_json:
        lines.extend(["# Retention map", json.dumps(project.retention_plan_json, ensure_ascii=False, indent=2), ""])
    else:
        lines.extend(["# Retention map", "Chua co retention map rieng. Hay tao lai story neu can chi dan giu chan chi tiet.", ""])
    if project.sound_design_plan_json:
        lines.extend(["# Sound design plan", json.dumps(project.sound_design_plan_json, ensure_ascii=False, indent=2), ""])
    else:
        lines.extend(["# Sound design plan", "Chua co sound design plan rieng. SFX/BGM neu co trong prompt chi la chi dan dung.", ""])
    lines.append("# Shot creative notes")
    for shot in shots:
        lines.extend(
            [
                f"Segment {shot.shot_order:02d}",
                "Retention: " + json.dumps(shot.retention_json or {}, ensure_ascii=False),
                "Transition: " + json.dumps(shot.transition_json or {}, ensure_ascii=False),
                "Sound/SFX: " + json.dumps(shot.sound_design_json or {}, ensure_ascii=False),
                "Quality: " + json.dumps(shot.retainability_quality_check or {}, ensure_ascii=False),
                "",
            ]
        )
    lines.append("Ghi chu: SFX/BGM la chi dan dung neu chua co audio asset that duoc mix vao MP4.")
    return "\n".join(lines).strip() + "\n"

def _phase2_prompt_text(project: DBVideoProject, shot: DBVideoShot, prompt: DBVideoShotPrompt) -> str:
    parts = [
        "# Prompt goc de copy sang cong cu tao video",
        "",
        (prompt.prompt or "").strip(),
        "",
        f"Video language: {video_language.video_language_english_name(getattr(project, 'target_language', None))}",
        f"Aspect ratio: {prompt.aspect_ratio or project.aspect_ratio}",
        f"Duration: {prompt.duration_seconds or shot.duration_seconds or ''} seconds",
        f"Micro-scenes:\n{_micro_scene_text(shot.micro_scenes_json or [])}",
        f"Camera movement: {prompt.camera_motion or shot.camera_motion or ''}",
        f"Subject motion: {prompt.subject_motion or shot.subject_motion or ''}",
        f"Environment motion: {prompt.environment_motion or shot.environment_motion or ''}",
        f"Start frame: {prompt.start_frame or ''}",
        f"End frame: {prompt.end_frame or ''}",
        f"Lighting: {prompt.lighting or ''}",
        f"Mood: {prompt.mood or ''}",
        f"Continuity notes: {prompt.continuity_notes or ''}",
    ]
    if prompt.negative_prompt:
        parts.extend(["", "Negative prompt:", prompt.negative_prompt.strip()])
    if prompt.retention_notes:
        parts.extend(["", "Retention:", prompt.retention_notes.strip()])
    if prompt.transition_notes:
        parts.extend(["", "Chuyen canh:", prompt.transition_notes.strip()])
    if prompt.sound_design_notes:
        parts.extend(["", "Am thanh/SFX:", prompt.sound_design_notes.strip(), "Ghi chu: day la chi dan dung neu chua co audio asset SFX/BGM that."])
    parts.extend([
        "",
        "Bản giải thích tiếng Việt:",
        (prompt.prompt_explanation_vi or "").strip() or "Chua co ban giai thich tieng Viet rieng. Hay tao lai prompt video neu can ban giai thich day du.",
    ])
    return "\n".join(part for part in parts if part is not None).strip() + "\n"


def _stored_prompt_download_text(project: DBVideoProject, shot: DBVideoShot, prompt: DBVideoShotPrompt) -> str:  # type: ignore[no-redef]  # noqa: F811
    is_english = video_language.normalize_video_language(getattr(project, "target_language", None)) == "en"
    transition_label = "Transition notes:" if is_english else "Chuyen canh:"
    sound_label = "Sound design notes:" if is_english else "Am thanh/SFX:"
    explanation_label = "Prompt explanation:" if is_english else "Ban giai thich tieng Viet:"
    sound_note = (
        "Note: this is a directing guide only if you have not yet mixed real SFX/BGM into the MP4."
        if is_english
        else "Ghi chu: day la chi dan dung neu chua co audio asset SFX/BGM that."
    )
    missing_explanation = (
        "No separate prompt explanation is available for this prompt. Regenerate the video prompt if you need a full explanation."
        if is_english
        else "Chua co ban giai thich tieng Viet rieng. Hay tao lai prompt video neu can ban giai thich day du."
    )
    parts = [
        (prompt.prompt or "").strip(),
        "",
        f"Video language: {video_language.video_language_english_name(getattr(project, 'target_language', None))}",
        f"Aspect ratio: {prompt.aspect_ratio or project.aspect_ratio}",
        f"Duration: {prompt.duration_seconds or shot.duration_seconds or ''} seconds",
        f"Micro-scenes:\n{_micro_scene_text(shot.micro_scenes_json or [])}",
        f"Camera movement: {prompt.camera_motion or shot.camera_motion or ''}",
        f"Subject motion: {prompt.subject_motion or shot.subject_motion or ''}",
        f"Environment motion: {prompt.environment_motion or shot.environment_motion or ''}",
        f"Start frame: {prompt.start_frame or ''}",
        f"End frame: {prompt.end_frame or ''}",
        f"Lighting: {prompt.lighting or ''}",
        f"Mood: {prompt.mood or ''}",
        f"Continuity notes: {prompt.continuity_notes or ''}",
    ]
    if prompt.negative_prompt:
        parts.extend(["", "Negative prompt:", prompt.negative_prompt.strip()])
    if prompt.retention_notes:
        parts.extend(["", "Retention:", prompt.retention_notes.strip()])
    if prompt.transition_notes:
        parts.extend(["", transition_label, prompt.transition_notes.strip()])
    if prompt.sound_design_notes:
        parts.extend(["", sound_label, prompt.sound_design_notes.strip(), sound_note])
    parts.extend([
        "",
        explanation_label,
        (prompt.prompt_explanation_vi or "").strip() or missing_explanation,
    ])
    return "\n".join(part for part in parts if part is not None).strip() + "\n"

def _write_package_zip(
    *,
    project: DBVideoProject,
    scenes: list[DBVideoScene],
    subtitle: DBVideoSubtitle,
    manifest: models.VideoPackageManifestResponse,
    zip_path: Path,
    manifest_path: Path,
    db: Session,
) -> None:
    root = _safe_zip_part(f"AI Video - {project.title}", fallback="AI Video")
    manifest_path.write_text(manifest.model_dump_json(indent=2), encoding="utf-8")
    subtitle_path = video_storage.resolve_artifact_storage_path(subtitle.subtitle_path)
    if subtitle_path is None or not subtitle_path.exists():
        raise VideoPackageError("Không tìm thấy file phụ đề để đóng gói.", error_code="VIDEO_PACKAGE_SUBTITLE_MISSING")

    with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        archive.writestr(_zip_name(root, "00 - Huong dan.txt"), _guide_text(project))
        archive.write(manifest_path, _zip_name(root, f"Manifest - {project.title}.json"))

        if getattr(project, "phase", "phase1") == "phase2":
            shots = _ordered_shots(project.id, db)
            archive.writestr(_zip_name(root, "01 - Kich ban", _phase2_script_filename(project)), _phase2_story_text(project))
            archive.writestr(_zip_name(root, "01 - Kich ban", "Mo ta tieng Viet.txt"), _phase2_vietnamese_description(project, shots))
            archive.writestr(_zip_name(root, "01 - Kich ban", "Continuity bible.txt"), (project.continuity_bible or project.style_bible or "").strip() + "\n")
            archive.writestr(_zip_name(root, "01 - Kich ban", "Creative direction - Retention va am thanh.txt"), _phase2_creative_direction_text(project, shots))
            archive.writestr(_zip_name(root, "01 - Kich ban", video_storage.shot_list_filename(project.title)), _shot_list_csv(project, shots, db))
            scenes_by_id = {scene.id: scene for scene in _ordered_scenes(project.id, db)}
            for shot in shots:
                prompt = _latest_shot_prompt(project.id, shot.id, db)
                if prompt is None:
                    continue
                scene = scenes_by_id.get(shot.scene_id)
                archive.writestr(
                    _zip_name(root, "02 - Prompt video", video_storage.video_prompt_filename(scene.scene_order if scene else None, shot.shot_order)),
                    _phase2_prompt_text(project, shot, prompt),
                )
            if not video_speech.uses_veo_native_speech(project):
                for shot in shots:
                    if _requires_shot_narration(shot):
                        path = _shot_audio_path(shot)
                        filename = _shot_audio_filename(shot, scenes_by_id)
                        if path is not None and filename is not None:
                            archive.write(path, _zip_name(root, "03 - Giong doc", filename))
            archive.write(subtitle_path, _zip_name(root, "04 - Phu de", video_storage.subtitle_filename(project.title)))
            return

        archive.write(subtitle_path, _zip_name(root, "03 - Phu de", video_storage.subtitle_filename(project.title)))

        for scene in scenes:
            prompt = _latest_prompt(project.id, scene.id, db)
            if prompt is not None:
                prompt_path = video_storage.resolve_artifact_storage_path(prompt.prompt_path)
                if prompt_path is not None and prompt_path.exists():
                    archive.write(prompt_path, _zip_name(root, "01 - Prompt anh", video_storage.prompt_filename(scene.scene_order)))

            if _requires_narration(scene):
                path = _audio_path(scene)
                filename = _audio_filename(scene)
                if path is not None and filename is not None:
                    archive.write(path, _zip_name(root, "02 - Giong doc", filename))

            preview_asset = video_assets.get_active_preview_asset(project.id, scene.id, db)
            preview_name = _preview_filename(scene, preview_asset)
            preview_path = video_storage.resolve_artifact_storage_path(preview_asset.file_path) if preview_asset else None
            if preview_path is not None and preview_path.exists() and preview_name:
                archive.write(preview_path, _zip_name(root, "04 - Anh preview", preview_name))


def create_package(project_id: str, db: Session) -> models.VideoPackageExportResponse | None:
    project = db.query(DBVideoProject).filter(DBVideoProject.id == project_id).first()
    if project is None:
        return None

    readiness = get_package_readiness(project_id, db)
    if readiness is None or not readiness.ready:
        reason = "; ".join(readiness.missing_reasons if readiness else []) or "Dự án chưa đủ nguyên liệu để tải ZIP."
        video_errors.log_error(
            "Package export blocked by readiness validation",
            project_id=project_id,
            missing_reasons=reason,
            step_name="package_readiness",
        )
        raise VideoPackageError(reason, error_code="VIDEO_PACKAGE_NOT_READY")

    scenes = _approved_scenes(project_id, db)
    subtitle = _completed_subtitle(project_id, db)
    if subtitle is None:
        raise VideoPackageError("Chưa có phụ đề hoàn tất.", error_code="VIDEO_PACKAGE_SUBTITLE_MISSING")

    now = datetime.utcnow()
    db.query(DBVideoPackageExport).filter(DBVideoPackageExport.project_id == project_id).update(
        {"stale": True},
        synchronize_session=False,
    )
    row = DBVideoPackageExport(
        id=str(uuid.uuid4()),
        project_id=project_id,
        status="running",
        stale=False,
        created_at=now,
        updated_at=now,
    )
    db.add(row)
    db.commit()
    db.refresh(row)

    export_dir = video_storage.get_project_subdir(project_id, "exports")
    manifest_dir = video_storage.get_project_subdir(project_id, "manifests")
    zip_path = export_dir / f"package-{row.id}.zip"
    manifest_path = manifest_dir / f"manifest-{row.id}.json"
    try:
        manifest = _manifest(project, scenes, db)
        _write_package_zip(
            project=project,
            scenes=scenes,
            subtitle=subtitle,
            manifest=manifest,
            zip_path=zip_path,
            manifest_path=manifest_path,
            db=db,
        )
    except Exception as exc:
        row.status = "failed"
        row.failure_reason = str(exc)
        row.updated_at = datetime.utcnow()
        db.commit()
        video_errors.log_error(
            "Package export failed",
            exc=exc,
            project_id=project_id,
            package_export_id=row.id,
            file_path=video_storage.to_artifact_storage_path(zip_path),
            step_name="package_export",
        )
        if isinstance(exc, VideoPackageError):
            raise
        raise VideoPackageError("Không tạo được file ZIP nguyên liệu.", error_code="VIDEO_PACKAGE_CREATE_FAILED") from exc

    row.status = "completed"
    row.manifest_path = video_storage.to_artifact_storage_path(manifest_path)
    row.zip_path = video_storage.to_artifact_storage_path(zip_path)
    row.updated_at = datetime.utcnow()
    project.package_stale = False
    project.updated_at = row.updated_at
    db.commit()
    db.refresh(row)
    video_errors.log_step(
        "Package export completed",
        project_id=project_id,
        package_export_id=row.id,
        manifest_path=row.manifest_path,
        zip_path=row.zip_path,
        step_name="package_export",
    )
    return models.VideoPackageExportResponse.model_validate(row)


def get_latest_package(project_id: str, db: Session) -> models.VideoPackageExportResponse | None:
    row = (
        db.query(DBVideoPackageExport)
        .filter(DBVideoPackageExport.project_id == project_id)
        .order_by(DBVideoPackageExport.created_at.desc())
        .first()
    )
    if row is None:
        return None
    return models.VideoPackageExportResponse.model_validate(row)


def get_package_download(project_id: str, db: Session) -> tuple[str, Path] | None:
    project = db.query(DBVideoProject).filter(DBVideoProject.id == project_id).first()
    row = (
        db.query(DBVideoPackageExport)
        .filter(
            DBVideoPackageExport.project_id == project_id,
            DBVideoPackageExport.status == "completed",
            DBVideoPackageExport.stale.is_(False),
        )
        .order_by(DBVideoPackageExport.created_at.desc())
        .first()
    )
    if project is None or row is None or not row.zip_path:
        return None
    path = video_storage.resolve_artifact_storage_path(row.zip_path)
    if path is None or not path.exists():
        return None
    return video_storage.package_filename(project.title), path
