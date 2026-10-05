"""Project-level publishing metadata generation for AI Video."""

from __future__ import annotations

import hashlib
import json
import re
import time
import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any

from pydantic import ValidationError
from sqlalchemy.orm import Session
from sqlalchemy.orm.attributes import flag_modified

from .. import models
from ..database import (
    VideoProject as DBVideoProject,
    VideoPublishingMetadata as DBVideoPublishingMetadata,
    VideoShot as DBVideoShot,
    VideoShotPrompt as DBVideoShotPrompt,
    VideoSourceBlock as DBVideoSourceBlock,
)
from . import (
    ai_planning,
    settings as settings_service,
    video_language,
    video_observability,
    video_phase2,
)
from .video_planning import VideoPlanningValidationError

PLATFORM_YOUTUBE = "youtube"
PLATFORM_TIKTOK = "tiktok"
PLATFORM_FACEBOOK = "facebook"
PLATFORM_ALL = "all"
PLATFORM_KEYS = (PLATFORM_YOUTUBE, PLATFORM_TIKTOK, PLATFORM_FACEBOOK)
STATUS_MISSING = "missing"
STATUS_GENERATING = "generating"
STATUS_COMPLETED = "completed"
STATUS_FAILED = "failed"
STATUS_STALE = "stale"
MAPPING_RETRIES = 3
GENERATION_STALE_AFTER = timedelta(minutes=30)
MAX_CONTEXT_CHARS = 24000


@dataclass(frozen=True)
class PlatformProfile:
    key: str
    label: str
    title_max: int
    description_max: int
    hashtag_min: int
    hashtag_max: int
    thumbnail_prompt_max: int
    thumbnail_ratio: str
    guidance: str


PLATFORM_PROFILES: dict[str, PlatformProfile] = {
    PLATFORM_YOUTUBE: PlatformProfile(
        key=PLATFORM_YOUTUBE,
        label="YouTube",
        title_max=100,
        description_max=5000,
        hashtag_min=3,
        hashtag_max=15,
        thumbnail_prompt_max=4000,
        thumbnail_ratio="16:9",
        guidance=(
            "Title: search-friendly hook without false claims. Description: context, useful keywords, CTA, "
            "and no invented links. Thumbnail: 16:9 composition, strong subject, safe title area."
        ),
    ),
    PLATFORM_TIKTOK: PlatformProfile(
        key=PLATFORM_TIKTOK,
        label="TikTok",
        title_max=120,
        description_max=2200,
        hashtag_min=3,
        hashtag_max=12,
        thumbnail_prompt_max=3600,
        thumbnail_ratio="9:16",
        guidance=(
            "Title/caption: short social hook with curiosity. Description: fast context and CTA. "
            "Thumbnail/cover: 9:16, readable center subject, mobile safe area."
        ),
    ),
    PLATFORM_FACEBOOK: PlatformProfile(
        key=PLATFORM_FACEBOOK,
        label="Facebook",
        title_max=125,
        description_max=5000,
        hashtag_min=2,
        hashtag_max=12,
        thumbnail_prompt_max=4000,
        thumbnail_ratio="1:1 or 16:9",
        guidance=(
            "Title: conversational and shareable. Description: natural context, discussion-friendly CTA, "
            "no fabricated accounts or promises. Thumbnail: feed-safe composition."
        ),
    ),
}

_HASHTAG_PATTERN = re.compile(r"^#[^\s#]+$", re.UNICODE)
_UNSUPPORTED_PLATFORM_KEYS = {"messenger", "instagram", "threads", "x", "twitter", "linkedin", "shorts", "reels"}


class VideoPublishingMetadataError(ValueError):
    """Raised when publishing metadata cannot be generated or mapped."""

    def __init__(
        self,
        message: str,
        *,
        error_code: str = "VIDEO_PUBLISHING_METADATA_ERROR",
        status_code: int = 400,
    ):
        super().__init__(message)
        self.error_code = error_code
        self.status_code = status_code


def _hash_text(value: str | None) -> str:
    return hashlib.sha256((value or "").encode("utf-8")).hexdigest()


def _hash_json(value: Any) -> str:
    encoded = json.dumps(value, ensure_ascii=False, sort_keys=True, default=str, separators=(",", ":"))
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def _truncate(value: str | None, limit: int) -> str:
    text = (value or "").strip()
    if len(text) <= limit:
        return text
    return text[:limit].rstrip(" ,.;:\n\t") + "...[truncated]"


def _ordered_shots(project_id: str, db: Session) -> list[DBVideoShot]:
    return (
        db.query(DBVideoShot)
        .filter(DBVideoShot.project_id == project_id)
        .order_by(DBVideoShot.shot_order.asc(), DBVideoShot.created_at.asc())
        .all()
    )


def _latest_prompt(project_id: str, shot_id: str, db: Session) -> DBVideoShotPrompt | None:
    return (
        db.query(DBVideoShotPrompt)
        .filter(DBVideoShotPrompt.project_id == project_id, DBVideoShotPrompt.shot_id == shot_id)
        .order_by(DBVideoShotPrompt.version.desc(), DBVideoShotPrompt.created_at.desc())
        .first()
    )


def _source_fingerprint(project: DBVideoProject, db: Session) -> list[dict[str, Any]]:
    rows = (
        db.query(DBVideoSourceBlock)
        .filter(DBVideoSourceBlock.project_id == project.id)
        .order_by(DBVideoSourceBlock.sort_order.asc(), DBVideoSourceBlock.created_at.asc())
        .all()
    )
    return [
        {
            "id": row.id,
            "sort_order": int(row.sort_order or 0),
            "block_type": row.block_type,
            "content_hash": _hash_text(row.content),
            "updated_at": row.updated_at.isoformat() if row.updated_at else None,
        }
        for row in rows
    ]


def _dependency_payload(project: DBVideoProject, db: Session) -> dict[str, Any]:
    shots = _ordered_shots(project.id, db)
    prompt_payload: list[dict[str, Any]] = []
    for shot in shots:
        prompt = _latest_prompt(project.id, shot.id, db)
        prompt_payload.append(
            {
                "shot_id": shot.id,
                "shot_order": shot.shot_order,
                "shot_revision": int(getattr(shot, "revision", 1) or 1),
                "duration_seconds": shot.duration_seconds,
                "narration_hash": _hash_text(shot.english_narration),
                "visual_hash": _hash_json(
                    {
                        "vietnamese_description": shot.vietnamese_description,
                        "primary_action": shot.primary_action,
                        "purpose": shot.purpose,
                        "shot_type": shot.shot_type,
                        "camera_angle": shot.camera_angle,
                        "framing": shot.framing,
                        "composition": shot.composition,
                        "camera_motion": shot.camera_motion,
                        "subject_motion": shot.subject_motion,
                        "environment_motion": shot.environment_motion,
                        "transition_to_next": shot.transition_to_next,
                        "retention_json": shot.retention_json,
                        "transition_json": shot.transition_json,
                        "sound_design_json": shot.sound_design_json,
                        "micro_scenes_json": shot.micro_scenes_json,
                    }
                ),
                "prompt_id": prompt.id if prompt else None,
                "prompt_version": int(prompt.version or 1) if prompt else None,
                "prompt_hash": _hash_text(prompt.prompt if prompt else None),
                "prompt_explanation_hash": _hash_text(prompt.prompt_explanation_vi if prompt else None),
                "prompt_quality_status": prompt.quality_status if prompt else None,
                "prompt_status": shot.prompt_status,
            }
        )
    return {
        "project": {
            "id": project.id,
            "topic_hash": _hash_text(project.topic),
            "target_language": video_language.normalize_video_language(project.target_language),
            "video_purpose": project.video_purpose,
            "dialogue_mode": project.dialogue_mode,
            "narration_density": project.narration_density,
            "call_to_action_style": project.call_to_action_style,
            "cta_action": getattr(project, "cta_action", None),
            "aspect_ratio": project.aspect_ratio,
            "visual_style_hash": _hash_text(project.visual_style),
            "continuity_hash": _hash_text(project.continuity_bible),
            "story_hash": _hash_text(project.story_strategy),
            "script_hash": _hash_text(project.detailed_script or project.script_text),
            "retention_hash": _hash_json(project.retention_plan_json or {}),
            "sound_design_hash": _hash_json(project.sound_design_plan_json or {}),
            "series_id": project.series_id,
            "episode_number": project.episode_number,
            "episode_title": project.episode_title,
        },
        "source_blocks": _source_fingerprint(project, db),
        "shots": prompt_payload,
    }


def input_fingerprint(project: DBVideoProject, db: Session) -> str:
    """Return the current content fingerprint for publishing metadata."""
    return _hash_json(_dependency_payload(project, db))


def _platform_schema() -> dict[str, Any]:
    return {
        "type": "object",
        "additionalProperties": False,
        "properties": {
            "title": {"type": "string"},
            "description": {"type": "string"},
            "hashtags": {"type": "array", "items": {"type": "string"}},
            "thumbnail_prompt": {"type": "string"},
        },
        "required": ["title", "description", "hashtags", "thumbnail_prompt"],
    }


def _all_platform_schema() -> dict[str, Any]:
    return {
        "type": "object",
        "additionalProperties": False,
        "properties": {
            "target_language": {"type": "string"},
            "platforms": {
                "type": "object",
                "additionalProperties": False,
                "properties": {key: _platform_schema() for key in PLATFORM_KEYS},
                "required": list(PLATFORM_KEYS),
            },
        },
        "required": ["target_language", "platforms"],
    }


def _single_platform_schema(platform: str) -> dict[str, Any]:
    return {
        "type": "object",
        "additionalProperties": False,
        "properties": {
            "target_language": {"type": "string"},
            platform: _platform_schema(),
        },
        "required": ["target_language", platform],
    }


def _latest_prompt_summaries(project: DBVideoProject, db: Session) -> list[dict[str, Any]]:
    summaries: list[dict[str, Any]] = []
    for shot in _ordered_shots(project.id, db):
        prompt = _latest_prompt(project.id, shot.id, db)
        if prompt is None:
            continue
        summaries.append(
            {
                "shot_order": shot.shot_order,
                "duration_seconds": shot.duration_seconds,
                "narration": _truncate(shot.english_narration, 800),
                "visual_summary_vi": _truncate(shot.vietnamese_description, 900),
                "retention": _truncate(json.dumps(shot.retention_json or {}, ensure_ascii=False), 900),
                "prompt": _truncate(prompt.prompt, 1800),
                "prompt_explanation_vi": _truncate(prompt.prompt_explanation_vi, 900),
                "negative_prompt": _truncate(prompt.negative_prompt, 700),
                "thumbnail_relevant_notes": _truncate(
                    "\n".join(
                        part
                        for part in [
                            prompt.continuity_notes,
                            prompt.retention_notes,
                            prompt.transition_notes,
                            prompt.sound_design_notes,
                        ]
                        if part
                    ),
                    1200,
                ),
            }
        )
    return summaries


def _codex_context(project: DBVideoProject, db: Session) -> dict[str, Any]:
    base = video_phase2.normalize_phase2_codex_context(project, db)
    context = {
        "project": {
            "title_for_internal_context_only": project.title,
            "topic": _truncate(project.topic, 3000),
            "target_language": video_language.normalize_video_language(project.target_language),
            "target_language_label": base.get("target_language_label"),
            "viewer_language_instruction": base.get("viewer_language_instruction"),
            "video_purpose": base.get("video_purpose"),
            "dialogue_mode": base.get("dialogue_mode"),
            "narration_density": base.get("narration_density"),
            "call_to_action_style": base.get("call_to_action_style"),
            "cta_action": base.get("cta_action"),
            "aspect_ratio": project.aspect_ratio,
            "visual_style": _truncate(project.visual_style, 1600),
            "continuity_bible": _truncate(project.continuity_bible, 2500),
        },
        "source_context": _truncate(str(base.get("source_context") or ""), 5000),
        "story_strategy": _truncate(project.story_strategy, 3500),
        "detailed_script_or_narration": _truncate(project.detailed_script or project.script_text, 6000),
        "retention_plan": project.retention_plan_json or {},
        "sound_design_plan": project.sound_design_plan_json or {},
        "shot_prompts": _latest_prompt_summaries(project, db),
        "platform_profiles": {
            key: {
                "label": profile.label,
                "title_max": profile.title_max,
                "description_max": profile.description_max,
                "hashtag_min": profile.hashtag_min,
                "hashtag_max": profile.hashtag_max,
                "thumbnail_prompt_max": profile.thumbnail_prompt_max,
                "thumbnail_ratio": profile.thumbnail_ratio,
                "guidance": profile.guidance,
            }
            for key, profile in PLATFORM_PROFILES.items()
        },
    }
    encoded = json.dumps(context, ensure_ascii=False, default=str)
    if len(encoded) <= MAX_CONTEXT_CHARS:
        return context
    context["source_context"] = _truncate(str(context["source_context"]), 2500)
    context["story_strategy"] = _truncate(str(context["story_strategy"]), 2000)
    context["detailed_script_or_narration"] = _truncate(str(context["detailed_script_or_narration"]), 3500)
    context["shot_prompts"] = context["shot_prompts"][:12]
    return context


def _generation_prompt(project: DBVideoProject, db: Session, *, platform: str) -> str:
    context = _codex_context(project, db)
    language = video_language.normalize_video_language(project.target_language)
    if platform == PLATFORM_ALL:
        platform_instruction = "Tạo đủ đúng ba platform canonical: youtube, tiktok, facebook."
        output_instruction = "Trả JSON gồm target_language và platforms.youtube/tiktok/facebook."
    else:
        profile = PLATFORM_PROFILES[platform]
        platform_instruction = f"Chỉ tạo lại platform canonical `{platform}` ({profile.label}). Không tạo Messenger hoặc platform khác."
        output_instruction = f"Trả JSON gồm target_language và key `{platform}`."
    return f"""
Bạn là chuyên gia đóng gói nội dung đăng video đa nền tảng. Hãy tạo nội dung đăng video bám sát source, story, narration và prompt video đã duyệt.

Context đã giới hạn:
{json.dumps(context, ensure_ascii=False, default=str)}

Yêu cầu bắt buộc:
- target_language của output phải đúng "{language}".
- Title, description và hashtag hướng tới người xem phải dùng ngôn ngữ video target_language.
- Nếu thumbnail_prompt đề xuất chữ hiển thị trên ảnh bìa, chữ đó cũng phải cùng target_language; có thể dùng thuật ngữ camera/lighting/composition tiếng Anh nếu hữu ích cho công cụ tạo ảnh.
- {platform_instruction}
- Mỗi platform bắt buộc có: title, description, hashtags, thumbnail_prompt.
- Không thay thế Facebook bằng Messenger, Instagram, Reels hoặc nền tảng khác.
- Không tự bịa link, tài khoản, sản phẩm, số liệu, cam kết thứ hạng, lượt xem hoặc CTR.
- Không cam kết viral/top SEO. Chỉ tối ưu theo hồ sơ nền tảng.
- Hashtag là array string, không phải chuỗi ghép; hashtag không có khoảng trắng và không trùng nhau trong cùng platform.
- thumbnail_prompt là prompt văn bản để tạo ảnh bìa, không nói ảnh đã render xong.
- thumbnail_prompt phải mô tả subject thật của video, hook thị giác, cảm xúc, bố cục, ánh sáng, tỉ lệ/safe area, continuity, và tránh watermark, logo không có source, random text, lỗi mặt/tay.
- Mỗi nền tảng phải có biến thể riêng, không copy nguyên văn title/description/thumbnail prompt giữa các nền tảng.
- Không dùng tool/command, không đọc file trong project, không thêm markdown hoặc giải thích ngoài JSON.
- {output_instruction}
""".strip()


def _raw_platform_payload(payload: dict[str, Any], *, requested_platform: str) -> dict[str, Any]:
    if not isinstance(payload, dict):
        raise VideoPublishingMetadataError(
            "Codex trả về dữ liệu không phải JSON object.",
            error_code="VIDEO_PUBLISHING_METADATA_INVALID_SCHEMA",
            status_code=422,
        )
    platforms = payload.get("platforms")
    if isinstance(platforms, dict):
        return platforms
    if requested_platform == PLATFORM_ALL:
        return {str(key): value for key, value in payload.items() if key != "target_language"}
    if requested_platform in payload:
        return {requested_platform: payload.get(requested_platform)}
    # Some model outputs put a single platform object under "platform".
    single = payload.get("platform")
    if isinstance(single, dict):
        return {requested_platform: single}
    return {}


def _validate_target_language(payload: dict[str, Any], project: DBVideoProject) -> None:
    expected = video_language.normalize_video_language(project.target_language)
    actual = payload.get("target_language")
    if not isinstance(actual, str) or video_language.normalize_video_language(actual) != expected:
        raise VideoPublishingMetadataError(
            "Codex trả về target_language không khớp ngôn ngữ video.",
            error_code="VIDEO_PUBLISHING_METADATA_LANGUAGE_MISMATCH",
            status_code=422,
        )


def _validate_platform_keys(raw_platforms: dict[str, Any], *, requested_platform: str) -> list[str]:
    keys = set(raw_platforms)
    lowered = {str(key).strip().lower() for key in keys}
    unsupported = sorted(lowered & _UNSUPPORTED_PLATFORM_KEYS)
    if unsupported:
        raise VideoPublishingMetadataError(
            "Codex trả về platform ngoài phạm vi YouTube, TikTok, Facebook.",
            error_code="VIDEO_PUBLISHING_METADATA_UNSUPPORTED_PLATFORM",
            status_code=422,
        )
    if requested_platform == PLATFORM_ALL:
        expected = set(PLATFORM_KEYS)
        if lowered != expected:
            missing = sorted(expected - lowered)
            extra = sorted(lowered - expected)
            raise VideoPublishingMetadataError(
                "Codex trả về thiếu hoặc thừa platform.",
                error_code="VIDEO_PUBLISHING_METADATA_PLATFORM_KEYS_INVALID",
                status_code=422,
            ) from ValueError(f"missing={missing}; extra={extra}")
        return list(PLATFORM_KEYS)
    if requested_platform not in lowered:
        raise VideoPublishingMetadataError(
            f"Codex không trả về platform cần tạo lại: {requested_platform}.",
            error_code="VIDEO_PUBLISHING_METADATA_PLATFORM_MISSING",
            status_code=422,
        )
    if lowered - set(PLATFORM_KEYS):
        raise VideoPublishingMetadataError(
            "Codex trả về platform ngoài schema canonical.",
            error_code="VIDEO_PUBLISHING_METADATA_PLATFORM_KEYS_INVALID",
            status_code=422,
        )
    return [requested_platform]


def _platform_value(raw_platforms: dict[str, Any], platform: str) -> Any:
    for key, value in raw_platforms.items():
        if str(key).strip().lower() == platform:
            return value
    return None


def _required_text(item: dict[str, Any], field: str, *, platform: str, max_length: int) -> str:
    value = item.get(field)
    if not isinstance(value, str):
        raise VideoPublishingMetadataError(
            f"{platform}.{field} không đúng kiểu dữ liệu.",
            error_code="VIDEO_PUBLISHING_METADATA_FIELD_TYPE_INVALID",
            status_code=422,
        )
    text = value.strip()
    if not text:
        raise VideoPublishingMetadataError(
            f"{platform}.{field} đang rỗng.",
            error_code="VIDEO_PUBLISHING_METADATA_REQUIRED_FIELD_EMPTY",
            status_code=422,
        )
    if len(text) > max_length:
        raise VideoPublishingMetadataError(
            f"{platform}.{field} vượt giới hạn {max_length} ký tự.",
            error_code="VIDEO_PUBLISHING_METADATA_FIELD_TOO_LONG",
            status_code=422,
        )
    return text


def _normalize_hashtags(item: dict[str, Any], *, platform: str, profile: PlatformProfile) -> list[str]:
    raw = item.get("hashtags")
    if not isinstance(raw, list) or any(not isinstance(tag, str) for tag in raw):
        raise VideoPublishingMetadataError(
            f"{platform}.hashtags phải là danh sách chuỗi.",
            error_code="VIDEO_PUBLISHING_METADATA_HASHTAGS_INVALID",
            status_code=422,
        )
    normalized: list[str] = []
    seen: set[str] = set()
    for raw_tag in raw:
        tag = raw_tag.strip()
        if not tag:
            continue
        if not tag.startswith("#"):
            tag = "#" + tag
        if not _HASHTAG_PATTERN.match(tag):
            raise VideoPublishingMetadataError(
                f"{platform}.hashtags chứa hashtag không hợp lệ.",
                error_code="VIDEO_PUBLISHING_METADATA_HASHTAG_INVALID",
                status_code=422,
            )
        dedupe_key = tag.casefold()
        if dedupe_key in seen:
            continue
        seen.add(dedupe_key)
        normalized.append(tag)
    if len(normalized) < profile.hashtag_min:
        raise VideoPublishingMetadataError(
            f"{platform}.hashtags cần tối thiểu {profile.hashtag_min} hashtag.",
            error_code="VIDEO_PUBLISHING_METADATA_HASHTAGS_TOO_FEW",
            status_code=422,
        )
    if len(normalized) > profile.hashtag_max:
        raise VideoPublishingMetadataError(
            f"{platform}.hashtags vượt giới hạn {profile.hashtag_max} hashtag.",
            error_code="VIDEO_PUBLISHING_METADATA_HASHTAGS_TOO_MANY",
            status_code=422,
        )
    return normalized


def _map_platform(item: Any, *, platform: str, fingerprint: str) -> dict[str, Any]:
    if not isinstance(item, dict):
        raise VideoPublishingMetadataError(
            f"{platform} không phải object.",
            error_code="VIDEO_PUBLISHING_METADATA_PLATFORM_SCHEMA_INVALID",
            status_code=422,
        )
    profile = PLATFORM_PROFILES[platform]
    return {
        "title": _required_text(item, "title", platform=platform, max_length=profile.title_max),
        "description": _required_text(item, "description", platform=platform, max_length=profile.description_max),
        "hashtags": _normalize_hashtags(item, platform=platform, profile=profile),
        "thumbnail_prompt": _required_text(
            item,
            "thumbnail_prompt",
            platform=platform,
            max_length=profile.thumbnail_prompt_max,
        ),
        "status": STATUS_COMPLETED,
        "input_fingerprint": fingerprint,
        "revision": 1,
    }


def _normalized_comparison_text(value: str) -> str:
    return re.sub(r"\s+", " ", value.strip()).casefold()

def _validate_platform_variation(mapped: dict[str, dict[str, Any]], *, requested_platform: str) -> None:
    if requested_platform != PLATFORM_ALL:
        return
    for field in ("title", "description", "thumbnail_prompt"):
        values = {
            _normalized_comparison_text(str(mapped[platform].get(field) or ""))
            for platform in PLATFORM_KEYS
            if platform in mapped
        }
        if len(values) == 1:
            raise VideoPublishingMetadataError(
                "Codex sao chép cùng một nội dung cho mọi nền tảng thay vì tạo biến thể riêng.",
                error_code="VIDEO_PUBLISHING_METADATA_PLATFORM_VARIANTS_DUPLICATED",
                status_code=422,
            )
    hashtag_sets = {
        tuple(tag.casefold() for tag in mapped[platform].get("hashtags", []))
        for platform in PLATFORM_KEYS
        if platform in mapped
    }
    if len(hashtag_sets) == 1:
        raise VideoPublishingMetadataError(
            "Codex sao chép cùng một bộ hashtag cho mọi nền tảng.",
            error_code="VIDEO_PUBLISHING_METADATA_PLATFORM_VARIANTS_DUPLICATED",
            status_code=422,
        )

def map_codex_payload(
    payload: dict[str, Any],
    *,
    project: DBVideoProject,
    requested_platform: str,
    fingerprint: str,
) -> dict[str, dict[str, Any]]:
    _validate_target_language(payload, project)
    raw_platforms = _raw_platform_payload(payload, requested_platform=requested_platform)
    platforms = _validate_platform_keys(raw_platforms, requested_platform=requested_platform)
    mapped = {
        platform: _map_platform(_platform_value(raw_platforms, platform), platform=platform, fingerprint=fingerprint)
        for platform in platforms
    }
    _validate_platform_variation(mapped, requested_platform=requested_platform)
    return mapped


def _project_for_response(project_id: str, db: Session) -> DBVideoProject | None:
    return db.query(DBVideoProject).filter(DBVideoProject.id == project_id).first()


def _row_response(row: DBVideoPublishingMetadata | None, project: DBVideoProject) -> models.VideoPublishingMetadataResponse:
    if row is None:
        return models.VideoPublishingMetadataResponse(
            project_id=project.id,
            target_language=video_language.normalize_video_language(project.target_language),
        )
    platforms: dict[str, models.VideoPublishingPlatformContent] = {}
    if isinstance(row.platforms_json, dict):
        for key, value in row.platforms_json.items():
            if key not in PLATFORM_KEYS or not isinstance(value, dict):
                continue
            try:
                platforms[key] = models.VideoPublishingPlatformContent.model_validate(value)
            except ValidationError:
                platforms[key] = models.VideoPublishingPlatformContent(status=STATUS_FAILED)
    return models.VideoPublishingMetadataResponse(
        id=row.id,
        project_id=row.project_id,
        status=row.status,
        target_language=row.target_language,
        platforms=platforms,
        input_fingerprint=row.input_fingerprint,
        revision=int(row.revision or 0),
        stale=bool(row.stale),
        failure_reason=row.failure_reason,
        error_code=row.error_code,
        request_id=row.request_id,
        created_at=row.created_at,
        updated_at=row.updated_at,
    )


def _sync_fingerprint_stale(
    row: DBVideoPublishingMetadata,
    *,
    current_fingerprint: str,
    db: Session,
    commit: bool = False,
) -> bool:
    if row.status == STATUS_COMPLETED and not row.stale and row.input_fingerprint != current_fingerprint:
        row.status = STATUS_STALE
        row.stale = True
        row.updated_at = datetime.utcnow()
        if commit:
            db.commit()
        return True
    return False


def get_publishing_metadata(project_id: str, db: Session) -> models.VideoPublishingMetadataResponse | None:
    project = _project_for_response(project_id, db)
    if project is None:
        return None
    row = db.query(DBVideoPublishingMetadata).filter(DBVideoPublishingMetadata.project_id == project_id).first()
    if row is not None:
        _sync_fingerprint_stale(row, current_fingerprint=input_fingerprint(project, db), db=db, commit=True)
        db.refresh(row)
    return _row_response(row, project)


def _platforms_ready_count(row: DBVideoPublishingMetadata | None, current_fingerprint: str) -> int:
    if row is None or not isinstance(row.platforms_json, dict):
        return 0
    count = 0
    for key in PLATFORM_KEYS:
        value = row.platforms_json.get(key)
        if not isinstance(value, dict):
            continue
        if value.get("status") == STATUS_COMPLETED and value.get("input_fingerprint") == current_fingerprint:
            count += 1
    return count


def metadata_status_summary(project_id: str, db: Session) -> dict[str, Any]:
    project = _project_for_response(project_id, db)
    if project is None:
        return {
            "status": STATUS_MISSING,
            "ready": False,
            "stale": False,
            "revision": None,
            "platforms_ready": 0,
        }
    current_fingerprint = input_fingerprint(project, db)
    row = db.query(DBVideoPublishingMetadata).filter(DBVideoPublishingMetadata.project_id == project_id).first()
    if row is None:
        return {
            "status": STATUS_MISSING,
            "ready": False,
            "stale": False,
            "revision": None,
            "platforms_ready": 0,
        }
    if _sync_fingerprint_stale(row, current_fingerprint=current_fingerprint, db=db, commit=True):
        db.refresh(row)
    platforms_ready = _platforms_ready_count(row, current_fingerprint)
    ready = row.status == STATUS_COMPLETED and not row.stale and platforms_ready == len(PLATFORM_KEYS)
    return {
        "status": row.status,
        "ready": ready,
        "stale": bool(row.stale),
        "revision": int(row.revision or 0),
        "platforms_ready": platforms_ready,
    }


def _validate_generation_inputs(project: DBVideoProject, db: Session) -> None:
    if getattr(project, "phase", "phase1") != "phase2":
        raise VideoPublishingMetadataError(
            "Chỉ project AI Video phase 2 mới hỗ trợ tạo nội dung đăng video.",
            error_code="VIDEO_PUBLISHING_METADATA_PHASE_REQUIRED",
            status_code=422,
        )
    # Publishing metadata is an early draft artifact. Incomplete or missing
    # shot prompts lower its accuracy/readiness, but must not block generation.
    return


def _create_or_get_row(project: DBVideoProject, db: Session, *, request_id: str) -> DBVideoPublishingMetadata:
    now = datetime.utcnow()
    row = db.query(DBVideoPublishingMetadata).filter(DBVideoPublishingMetadata.project_id == project.id).first()
    if row is None:
        row = DBVideoPublishingMetadata(
            id=str(uuid.uuid4()),
            project_id=project.id,
            status=STATUS_MISSING,
            target_language=video_language.normalize_video_language(project.target_language),
            platforms_json={},
            revision=0,
            stale=False,
            request_id=request_id,
            created_at=now,
            updated_at=now,
        )
        db.add(row)
        db.flush()
    return row


def _generation_is_recent(row: DBVideoPublishingMetadata) -> bool:
    if row.status != STATUS_GENERATING:
        return False
    if row.updated_at is None:
        return True
    return datetime.utcnow() - row.updated_at < GENERATION_STALE_AFTER


def _mark_generating(row: DBVideoPublishingMetadata, project: DBVideoProject, *, request_id: str, db: Session) -> None:
    if _generation_is_recent(row):
        raise VideoPublishingMetadataError(
            "Dự án đang tạo nội dung đăng video. Hãy chờ request hiện tại hoàn tất.",
            error_code="VIDEO_PUBLISHING_METADATA_GENERATION_ACTIVE",
            status_code=409,
        )
    row.status = STATUS_GENERATING
    row.target_language = video_language.normalize_video_language(project.target_language)
    row.request_id = request_id
    row.failure_reason = None
    row.error_code = None
    row.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(row)


def _record_failure(
    row: DBVideoPublishingMetadata,
    *,
    exc: BaseException,
    request_id: str,
    db: Session,
) -> None:
    row.status = STATUS_FAILED
    row.failure_reason = str(exc)
    row.error_code = getattr(exc, "error_code", "VIDEO_PUBLISHING_METADATA_FAILED")
    row.request_id = request_id
    row.updated_at = datetime.utcnow()
    db.commit()


def _write_success(
    row: DBVideoPublishingMetadata,
    *,
    project: DBVideoProject,
    requested_platform: str,
    mapped: dict[str, dict[str, Any]],
    current_fingerprint: str,
    request_id: str,
    db: Session,
) -> None:
    existing = dict(row.platforms_json or {})
    if requested_platform == PLATFORM_ALL:
        next_platforms = {}
        for key in PLATFORM_KEYS:
            item = dict(mapped[key])
            item["revision"] = int(existing.get(key, {}).get("revision", 0) or 0) + 1 if isinstance(existing.get(key), dict) else 1
            next_platforms[key] = item
    else:
        if not all(isinstance(existing.get(key), dict) for key in PLATFORM_KEYS):
            raise VideoPublishingMetadataError(
                "Cần tạo đủ ba nền tảng trước khi tạo lại riêng một nền tảng.",
                error_code="VIDEO_PUBLISHING_METADATA_FULL_ARTIFACT_REQUIRED",
                status_code=422,
            )
        next_platforms = {key: dict(value) for key, value in existing.items() if key in PLATFORM_KEYS and isinstance(value, dict)}
        item = dict(mapped[requested_platform])
        item["revision"] = int(next_platforms.get(requested_platform, {}).get("revision", 0) or 0) + 1
        next_platforms[requested_platform] = item

    platforms_ready = sum(
        1
        for key in PLATFORM_KEYS
        if isinstance(next_platforms.get(key), dict)
        and next_platforms[key].get("status") == STATUS_COMPLETED
        and next_platforms[key].get("input_fingerprint") == current_fingerprint
    )
    stale = platforms_ready != len(PLATFORM_KEYS)
    row.platforms_json = next_platforms
    flag_modified(row, "platforms_json")
    row.status = STATUS_STALE if stale else STATUS_COMPLETED
    row.target_language = video_language.normalize_video_language(project.target_language)
    row.input_fingerprint = current_fingerprint
    row.revision = int(row.revision or 0) + 1
    row.stale = stale
    row.failure_reason = None
    row.error_code = None
    row.request_id = request_id
    row.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(row)


def _schema_for_request(platform: str) -> dict[str, Any]:
    return _all_platform_schema() if platform == PLATFORM_ALL else _single_platform_schema(platform)


def _step_name_for_request(platform: str) -> str:
    return "publishing_metadata_generation" if platform == PLATFORM_ALL else f"publishing_metadata_generation_{platform}"


def generate_publishing_metadata(
    project_id: str,
    data: models.VideoPublishingMetadataGenerateRequest,
    db: Session,
) -> models.VideoPublishingMetadataResponse | None:
    project = db.query(DBVideoProject).filter(DBVideoProject.id == project_id).first()
    if project is None:
        return None
    platform = data.platform
    if platform not in {PLATFORM_ALL, *PLATFORM_KEYS}:
        raise VideoPublishingMetadataError(
            "Platform không hợp lệ.",
            error_code="VIDEO_PUBLISHING_METADATA_PLATFORM_INVALID",
            status_code=422,
        )
    _validate_generation_inputs(project, db)
    current_fingerprint = input_fingerprint(project, db)
    request_id = str(uuid.uuid4())
    row = _create_or_get_row(project, db, request_id=request_id)
    _sync_fingerprint_stale(row, current_fingerprint=current_fingerprint, db=db, commit=False)

    if not data.force:
        ready_summary = metadata_status_summary(project_id, db)
        if platform == PLATFORM_ALL and ready_summary["ready"]:
            db.refresh(row)
            return _row_response(row, project)
        if (
            platform in PLATFORM_KEYS
            and row.status == STATUS_COMPLETED
            and not row.stale
            and isinstance(row.platforms_json, dict)
            and isinstance(row.platforms_json.get(platform), dict)
            and row.platforms_json[platform].get("input_fingerprint") == current_fingerprint
        ):
            return _row_response(row, project)

    _mark_generating(row, project, request_id=request_id, db=db)
    prompt = _generation_prompt(project, db, platform=platform)
    schema = _schema_for_request(platform)
    settings = settings_service.get_ai_planning_settings(db)
    log_details = {
        "request_id": request_id,
        "platform": platform,
        "prompt_chars": len(prompt),
        "schema_keys": sorted((schema.get("properties") or {}).keys()),
        "fingerprint": current_fingerprint[:16],
    }
    last_error: BaseException | None = None
    try:
        for attempt in range(1, MAPPING_RETRIES + 1):
            started = time.perf_counter()
            try:
                raw = video_phase2._run_structured_codex(
                    db,
                    project,
                    prompt,
                    schema,
                    step_name=_step_name_for_request(platform),
                )
                mapped = map_codex_payload(
                    raw,
                    project=project,
                    requested_platform=platform,
                    fingerprint=current_fingerprint,
                )
                _write_success(
                    row,
                    project=project,
                    requested_platform=platform,
                    mapped=mapped,
                    current_fingerprint=current_fingerprint,
                    request_id=request_id,
                    db=db,
                )
                video_observability.log_event(
                    db,
                    step_name="publishing_metadata_mapping",
                    status="success",
                    project_id=project.id,
                    provider=settings.provider,
                    model=settings.model,
                    duration_ms=round((time.perf_counter() - started) * 1000, 2),
                    retry_count=attempt - 1,
                    message="Đã tạo bộ nội dung đăng video.",
                    technical_details={
                        **log_details,
                        "attempt": attempt,
                        "mapped_platforms": sorted(mapped.keys()),
                        "field_lengths": {
                            key: {
                                "title": len(value["title"]),
                                "description": len(value["description"]),
                                "hashtags": len(value["hashtags"]),
                                "thumbnail_prompt": len(value["thumbnail_prompt"]),
                            }
                            for key, value in mapped.items()
                        },
                    },
                )
                return _row_response(row, project)
            except (VideoPublishingMetadataError, VideoPlanningValidationError, ValidationError) as exc:
                last_error = exc
                retry = attempt < MAPPING_RETRIES
                video_observability.log_event(
                    db,
                    step_name="publishing_metadata_mapping",
                    status="warning" if retry else "failure",
                    project_id=project.id,
                    provider=settings.provider,
                    model=settings.model,
                    duration_ms=round((time.perf_counter() - started) * 1000, 2),
                    retry_count=attempt,
                    error_code=getattr(exc, "error_code", "VIDEO_PUBLISHING_METADATA_INVALID_OUTPUT"),
                    exc=exc,
                    message=str(exc),
                    technical_details={**log_details, "attempt": attempt, "will_retry": retry},
                )
                if not retry:
                    raise
        raise VideoPublishingMetadataError(
            "AI trả về bộ nội dung đăng không đúng cấu trúc.",
            error_code="VIDEO_PUBLISHING_METADATA_INVALID_OUTPUT",
            status_code=422,
        ) from last_error
    except (ai_planning.AIPlanningError, VideoPublishingMetadataError, VideoPlanningValidationError, ValidationError) as exc:
        _record_failure(row, exc=exc, request_id=request_id, db=db)
        if isinstance(exc, VideoPublishingMetadataError):
            raise
        raise VideoPublishingMetadataError(
            str(exc),
            error_code=getattr(exc, "error_code", "VIDEO_PUBLISHING_METADATA_FAILED"),
            status_code=502 if isinstance(exc, ai_planning.AIPlanningError) else 422,
        ) from exc


def mark_publishing_metadata_stale(
    project_id: str,
    db: Session,
    *,
    reason: str | None = None,
    commit: bool = False,
) -> bool:
    row = db.query(DBVideoPublishingMetadata).filter(DBVideoPublishingMetadata.project_id == project_id).first()
    if row is None:
        return False
    if row.status == STATUS_MISSING:
        return False
    row.stale = True
    if row.status == STATUS_COMPLETED:
        row.status = STATUS_STALE
    if reason:
        row.failure_reason = reason[:500]
    row.updated_at = datetime.utcnow()
    if commit:
        db.commit()
    return True
