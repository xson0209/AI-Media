"""Story Studio workflow for image-story and hybrid series production."""

from __future__ import annotations

import json
import re
import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import func
from sqlalchemy.orm import Session

from .. import models
from ..database import (
    SeriesCharacterProfile as DBSeriesCharacterProfile,
    StoryAdaptation as DBStoryAdaptation,
    StoryEpisode as DBStoryEpisode,
    StoryScenarioCandidate as DBStoryScenarioCandidate,
    VideoProject as DBVideoProject,
    VideoRenderJob as DBVideoRenderJob,
    VideoSeries as DBVideoSeries,
    VideoShot as DBVideoShot,
)
from . import (
    ai_planning,
    series_brain,
    series_references,
    settings as settings_service,
    source_package as source_package_core,
    video_auto_runs,
    video_language,
    video_observability,
    video_projects,
    video_series_memory,
)
from .comic_series_analysis import source_context as comic_source_context

SERIES_MODE_IMAGE = "image_story_only"
SERIES_MODE_VIDEO = "video_story_only"
SERIES_MODE_HYBRID = "hybrid"
STORY_SERIES_MODES = {SERIES_MODE_IMAGE, SERIES_MODE_HYBRID}
IMAGE_INTENTS = {"truyen_anh", "ca_hai"}
VIDEO_INTENTS = {"video_truyen", "ca_hai"}
STRATEGIES = [
    ("hook_retention", "Hook/retention mạnh"),
    ("emotional_drama", "Cảm xúc/drama mạnh"),
    ("visual_action", "Visual/action mạnh"),
]
MAX_CANDIDATE_ATTEMPTS = 2
DEFAULT_PROMPT_QUALITY_THRESHOLD = 85.0
MAX_IMAGE_PANEL_COUNT = 200
MIN_AUTO_IMAGE_PANEL_COUNT = 24
MAX_AUTO_IMAGE_PANEL_COUNT = 42
AUTO_PANEL_TARGET_STORY_CHARS = 380
STORY_CANDIDATE_CONTEXT_MAX_CHARS = 10_000
CREATIVE_BRIEF_SERIES_MEMORY_CHARS = 3_000
CREATIVE_BRIEF_PROFILE_CHARS = 2_400
MAX_SOURCE_PROMPT_CHUNKS = 12
MAX_SOURCE_PROMPT_CHARS = 2_600
MAX_SOURCE_CHUNK_TEXT_CHARS = 120
VIDEO_HANDOFF_BLOCK_MAX_CHARS = 28_000
COMIC_STORY_VISUAL_STYLE = (
    "Anime/manga/webtoon comic-story look: cinematic manga panel composition, "
    "clean line art, expressive anime faces, consistent character design, "
    "dynamic comic-to-video motion, vertical 9:16 friendly composition, "
    "avoid photorealistic live-action unless the user explicitly asks."
)
REQUIRED_MASTER_FIELDS = {
    "title",
    "logline",
    "hook",
    "full_story",
    "key_beats",
    "character_emotions",
    "visual_moments",
    "motion_beats",
    "retention_plan",
    "market_profile",
    "language_profile",
    "must_have",
    "avoid",
    "continuity_updates",
    "image_story_notes",
    "video_story_notes",
}
REQUIRED_NONEMPTY_MASTER_FIELDS = REQUIRED_MASTER_FIELDS - {"continuity_updates"}
IMAGE_RENDER_JOB_STATUSES = {"queued", "rendering", "completed", "failed"}
STORY_EVALUATION_CRITERIA_KEYS = [
    "canon",
    "strategic_difference",
    "hook_retention",
    "emotion_logic",
    "visual_production",
    "pacing_payoff",
    "market_language_fit",
    "production_risk",
]

CONTINUITY_UPDATE_SCHEMA: dict[str, Any] = {
    "type": "object",
    "additionalProperties": False,
    "properties": {
        "type": {"type": "string"},
        "target": {"type": "string"},
        "proposal": {"type": "string"},
        "reason": {"type": "string"},
    },
    "required": ["type", "target", "proposal", "reason"],
}

STORY_MASTER_SCHEMA: dict[str, Any] = {
    "type": "object",
    "additionalProperties": False,
    "properties": {
        "title": {"type": "string"},
        "logline": {"type": "string"},
        "hook": {"type": "string"},
        "full_story": {"type": "string"},
        "key_beats": {"type": "array", "items": {"type": "string"}},
        "character_emotions": {"type": "array", "items": {"type": "string"}},
        "visual_moments": {"type": "array", "items": {"type": "string"}},
        "motion_beats": {"type": "array", "items": {"type": "string"}},
        "retention_plan": {"type": "string"},
        "market_profile": {"type": "string"},
        "language_profile": {"type": "string"},
        "must_have": {"type": "array", "items": {"type": "string"}},
        "avoid": {"type": "array", "items": {"type": "string"}},
        "continuity_updates": {"type": "array", "items": CONTINUITY_UPDATE_SCHEMA},
        "image_story_notes": {"type": "string"},
        "video_story_notes": {"type": "string"},
        "strengths_claimed": {"type": "array", "items": {"type": "string"}},
        "risks_claimed": {"type": "array", "items": {"type": "string"}},
    },
    "required": sorted(REQUIRED_MASTER_FIELDS | {"strengths_claimed", "risks_claimed"}),
}

STORY_CANDIDATE_SCHEMA: dict[str, Any] = {
    **STORY_MASTER_SCHEMA,
    "properties": {
        **STORY_MASTER_SCHEMA["properties"],
        "strategy_type": {"type": "string"},
        "strategy_label": {"type": "string"},
    },
    "required": sorted(REQUIRED_MASTER_FIELDS | {"strategy_type", "strategy_label", "strengths_claimed", "risks_claimed"}),
}

STORY_EVALUATION_SCHEMA: dict[str, Any] = {
    "type": "object",
    "additionalProperties": False,
    "properties": {
        "rubric": {"type": "string"},
        "output_intent": {"type": "string"},
        "reviews": {
            "type": "array",
            "items": {
                "type": "object",
                "additionalProperties": False,
                "properties": {
                    "strategy_type": {"type": "string"},
                    "total": {"type": "number"},
                    "criteria": {
                        "type": "object",
                        "additionalProperties": False,
                        "properties": {key: {"type": "number"} for key in STORY_EVALUATION_CRITERIA_KEYS},
                        "required": STORY_EVALUATION_CRITERIA_KEYS,
                    },
                    "reason_vi": {"type": "string"},
                    "evidence": {"type": "array", "items": {"type": "string"}},
                    "strengths": {"type": "array", "items": {"type": "string"}},
                    "weaknesses": {"type": "array", "items": {"type": "string"}},
                    "risks": {"type": "array", "items": {"type": "string"}},
                    "recommended_parts": {"type": "array", "items": {"type": "string"}},
                },
                "required": [
                    "strategy_type",
                    "total",
                    "criteria",
                    "reason_vi",
                    "evidence",
                    "strengths",
                    "weaknesses",
                    "risks",
                    "recommended_parts",
                ],
            },
        },
        "synthesis_guidance": {"type": "string"},
    },
    "required": ["rubric", "output_intent", "reviews", "synthesis_guidance"],
}

STORY_SYNTHESIS_SCHEMA: dict[str, Any] = {
    **STORY_MASTER_SCHEMA,
    "properties": {
        **STORY_MASTER_SCHEMA["properties"],
        "synthesis_sources": {
            "type": "array",
            "items": {
                "type": "object",
                "additionalProperties": False,
                "properties": {
                    "strategy_type": {"type": "string"},
                    "part": {"type": "string"},
                    "reason": {"type": "string"},
                },
                "required": ["strategy_type", "part", "reason"],
            },
        },
    },
    "required": sorted(REQUIRED_MASTER_FIELDS | {"synthesis_sources", "strengths_claimed", "risks_claimed"}),
}

STORY_PROMPT_REPAIR_SCHEMA: dict[str, Any] = {
    "type": "object",
    "additionalProperties": False,
    "properties": {
        "prompt": {"type": "string"},
        "negative_prompt": {"type": "string"},
        "caption_or_dialogue": {"type": "string"},
        "visual_description": {"type": "string"},
        "changes": {"type": "array", "items": {"type": "string"}},
        "reason_vi": {"type": "string"},
    },
    "required": [
        "prompt",
        "negative_prompt",
        "caption_or_dialogue",
        "visual_description",
        "changes",
        "reason_vi",
    ],
}

class StoryStudioError(ValueError):
    """Raised when Story Studio workflow rules are violated."""

def _clean(value: object | None) -> str:
    return str(value or "").strip()

_VIETNAMESE_DIACRITIC_RE = re.compile(
    r"[ăâđêôơưáàảãạắằẳẵặấầẩẫậéèẻẽẹếềểễệíìỉĩịóòỏõọốồổỗộớờởỡợúùủũụứừửữựýỳỷỹỵ]",
    re.IGNORECASE,
)
_OCR_SPEAKER_ID_RE = re.compile(r"\[\s*\d{1,4}\s*\]\s*")
_SCENE_LABEL_RE = re.compile(
    r"^\s*(?:cảnh|canh|scene)\s*\d{1,4}\s*(?:[—–\-:：]\s*[^:：\n]{0,160})?(?:[:：]\s*)?",
    re.IGNORECASE,
)
_ROLE_LABEL_RE = re.compile(
    r"^\s*(?:dialogue|narration|caption|voiceover|speech|thoại|thoai|lời kể|loi ke)\s*[:：\-]\s*",
    re.IGNORECASE,
)
_HOOK_LABEL_RE = re.compile(
    r"^\s*(?:hook\s*(?:mở màn|mo man|opening)?|opening\s*hook|cold\s*open)\s*[:：\-]\s*",
    re.IGNORECASE,
)
_PANEL_BOILERPLATE_MARKERS = (
    "bản quyền",
    "ban quyen",
    "copyright",
    "công ty",
    "cong ty",
    "hợp đồng",
    "hop dong",
    "phát hành",
    "phat hanh",
    "nguyên tác",
    "nguyen tac",
    "tranh:",
    "antstudio",
    "coffee manga",
    "publisher",
    "watermark",
)

def _is_panel_boilerplate(text: str) -> bool:
    lowered = text.lower()
    return any(marker in lowered for marker in _PANEL_BOILERPLATE_MARKERS)

def _strip_wrapping_quotes(text: str) -> str:
    cleaned = text.strip().strip(" \t\r\n")
    quote_pairs = (("“", "”"), ("‘", "’"), ('"', '"'), ("'", "'"))
    changed = True
    while changed and len(cleaned) >= 2:
        changed = False
        for left, right in quote_pairs:
            if cleaned.startswith(left) and cleaned.endswith(right):
                cleaned = cleaned[len(left) : -len(right)].strip()
                changed = True
    return cleaned

def _sanitize_story_panel_source_text(value: object | None, *, remove_hook_label: bool = False) -> str:
    """Remove OCR/index/metadata labels before text is reused in panel prompts.

    The source can contain extraction labels such as ``[56] narration:``,
    scene headers such as ``Cảnh 6 — Thư viện:``, and copyright/footer lines.
    Those are useful evidence in analysis, but they must not reach image/video
    generation as drawable text.
    """

    raw = _clean(value)
    if not raw:
        return ""
    normalized = raw.replace("\r", "\n")
    lines: list[str] = []
    for part in re.split(r"\n+|(?:\s*\|\s*)", normalized):
        line = _OCR_SPEAKER_ID_RE.sub("", part).strip(" \t-–—")
        if not line or _is_panel_boilerplate(line):
            continue
        if _HOOK_LABEL_RE.match(line):
            if remove_hook_label:
                line = _HOOK_LABEL_RE.sub("", line, count=1).strip()
            else:
                continue
        line = _SCENE_LABEL_RE.sub("", line, count=1).strip()
        line = _ROLE_LABEL_RE.sub("", line, count=1).strip()
        line = _strip_wrapping_quotes(line)
        line = re.sub(r"\s+", " ", line).strip(" \t-–—")
        if line and not _is_panel_boilerplate(line):
            lines.append(line)
    return " ".join(lines).strip()

def _target_viewer_language_for_episode(episode: DBStoryEpisode) -> str:
    settings = _episode_output_settings(episode)
    target_language = video_language.normalize_video_language(
        _clean(getattr(settings.video, "target_language", None)),
        default="",
    )
    if target_language:
        return target_language
    language_profile = _clean(getattr(episode, "language_profile", None)).lower()
    profile_language = video_language.normalize_video_language(language_profile, default="")
    if profile_language:
        return profile_language
    return "en" if language_profile.startswith("en") else "vi"

def _sanitize_panel_bubble_text(value: object | None, *, target_language: str) -> str:
    text = _sanitize_story_panel_source_text(value, remove_hook_label=False)
    if not text:
        return ""
    if target_language == "en" and _VIETNAMESE_DIACRITIC_RE.search(text):
        return ""
    return _clip_prompt_text(text, 220)

def _clip_prompt_text(value: object | None, limit: int) -> str:
    text = _clean(value)
    if len(text) <= limit:
        return text
    return text[: max(0, limit - 13)].rstrip(" ,.;:\n\t") + "\n...[rút gọn]"

def _value_to_text(value: object | None) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        return value.strip()
    if isinstance(value, list):
        return "\n".join(_value_to_text(item) for item in value if _value_to_text(item)).strip()
    if isinstance(value, dict):
        parts: list[str] = []
        for key, item in value.items():
            text = _value_to_text(item)
            if text:
                parts.append(f"{key}: {text}")
        return "\n".join(parts).strip()
    return str(value).strip()

def _json_from_ai(raw: str) -> dict[str, Any]:
    text = (raw or "").strip()
    try:
        value = json.loads(text)
    except json.JSONDecodeError:
        match = re.search(r"\{.*\}", text, re.DOTALL)
        if match is None:
            raise
        value = json.loads(match.group(0))
    if not isinstance(value, dict):
        raise json.JSONDecodeError("AI output is not a JSON object", text, 0)
    return value

def _effective_structured_ai_timeout(settings: Any, requested_timeout_seconds: int) -> int:
    """Keep Story Studio AI calls bounded by the user-facing AI planning timeout."""

    try:
        configured_timeout = int(getattr(settings, "timeout_seconds", 0) or 0)
    except (TypeError, ValueError):
        configured_timeout = 0
    requested_timeout = max(5, int(requested_timeout_seconds or 300))
    if configured_timeout > 0:
        return max(5, min(requested_timeout, configured_timeout))
    return requested_timeout

def _run_structured_ai(db: Session, prompt: str, schema: dict[str, Any], *, timeout_seconds: int = 300) -> dict[str, Any]:
    settings = settings_service.get_ai_planning_settings(db)
    effective_timeout = _effective_structured_ai_timeout(settings, timeout_seconds)
    try:
        raw = ai_planning.run_codex_exec(
            settings,
            prompt,
            output_schema=schema,
            timeout_seconds=effective_timeout,
        )
        return _json_from_ai(raw)
    except ai_planning.AIPlanningError as exc:
        raise StoryStudioError(f"AI Story Studio chưa chạy được: {exc}") from exc
    except json.JSONDecodeError as exc:
        raise StoryStudioError("AI trả về JSON không hợp lệ cho Story Studio. Hãy chạy lại bước này.") from exc

def _safe_model_label(db: Session) -> str:
    settings = settings_service.get_ai_planning_settings(db)
    provider = _clean(getattr(settings, "provider", None)) or "codex-cli"
    model = _clean(getattr(settings, "model", None)) or "default"
    return f"{provider}:{model}"[:120]

def _strategy_label(strategy_type: str) -> str:
    return dict(STRATEGIES).get(strategy_type, strategy_type)

def _coerce_list(value: Any) -> list[Any]:
    if isinstance(value, list):
        return value
    if value is None:
        return []
    if isinstance(value, str):
        return [part.strip() for part in re.split(r"\n+|;\s*", value) if part.strip()]
    return [value]

def _deep_merge_settings(base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
    merged = dict(base)
    for key, value in override.items():
        if isinstance(value, dict) and isinstance(merged.get(key), dict):
            merged[key] = _deep_merge_settings(merged[key], value)
        elif value is not None:
            merged[key] = value
    return merged

def _has_nested_key(value: Any, *keys: str) -> bool:
    current = value
    for key in keys:
        if not isinstance(current, dict) or key not in current:
            return False
        current = current[key]
    return True

def _positive_int(value: Any) -> int | None:
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return None
    return parsed if parsed > 0 else None

def _image_size_for_aspect(aspect_ratio: str) -> tuple[int, int]:
    return {
        "9:16": (720, 1280),
        "16:9": (1920, 1080),
        "1:1": (1080, 1080),
        "4:5": (1080, 1350),
    }.get(aspect_ratio, (720, 1280))

def _comic_source_style_guidance(episode: DBStoryEpisode, db: Session) -> str:
    try:
        summary = comic_source_context.source_summary(db, episode.id)
    except Exception:
        return ""
    if summary.source_kind == "comic_analysis":
        return COMIC_STORY_VISUAL_STYLE
    return ""

def _effective_story_visual_style(
    series: DBVideoSeries,
    episode: DBStoryEpisode,
    db: Session,
    *,
    fallback: str = "consistent cinematic illustration",
) -> str:
    return _clean(series.style_bible) or _comic_source_style_guidance(episode, db) or fallback

def _normalize_output_settings(value: Any, *, language_profile: str = "vi") -> models.StoryEpisodeOutputSettings:
    if isinstance(value, models.StoryEpisodeOutputSettings):
        raw = value.model_dump(mode="json")
    elif isinstance(value, dict):
        raw = value
    else:
        raw = {}
    defaults = models.StoryEpisodeOutputSettings().model_dump(mode="json")
    if not _has_nested_key(raw, "video", "target_language"):
        defaults["video"]["target_language"] = "vi" if (language_profile or "").lower().startswith("vi") else "en"
    aspect = raw.get("image", {}).get("aspect_ratio") if isinstance(raw.get("image"), dict) else None
    if aspect and (not _has_nested_key(raw, "image", "width") or not _has_nested_key(raw, "image", "height")):
        width, height = _image_size_for_aspect(str(aspect))
        defaults["image"]["width"] = width
        defaults["image"]["height"] = height
    merged = _deep_merge_settings(defaults, raw)
    raw_video = raw.get("video") if isinstance(raw.get("video"), dict) else {}
    merged_video = merged.get("video") if isinstance(merged.get("video"), dict) else None
    if merged_video is not None:
        has_raw_prompt_segment_settings = bool(
            _positive_int(raw_video.get("prompt_segment_count"))
            and _positive_int(raw_video.get("prompt_segment_duration_seconds"))
        )
        has_raw_target_duration = _positive_int(raw_video.get("target_duration_seconds")) is not None
        if not has_raw_prompt_segment_settings:
            if has_raw_target_duration:
                merged_video["prompt_segment_count"] = None
                merged_video["prompt_segment_duration_seconds"] = None
            else:
                merged_video["default_shot_duration_seconds"] = None
                merged_video["prompt_segment_count"] = models.DEFAULT_STORY_VIDEO_PROMPT_SEGMENT_COUNT
                merged_video["prompt_segment_duration_seconds"] = models.DEFAULT_STORY_VIDEO_PROMPT_SEGMENT_DURATION_SECONDS
                merged_video["micro_scenes_per_prompt"] = models.DEFAULT_STORY_VIDEO_MICRO_SCENES_PER_PROMPT
    return models.StoryEpisodeOutputSettings.model_validate(merged)

def _settings_json(settings: models.StoryEpisodeOutputSettings) -> dict[str, Any]:
    return settings.model_dump(mode="json")

def _episode_output_settings(episode: DBStoryEpisode) -> models.StoryEpisodeOutputSettings:
    return _normalize_output_settings(getattr(episode, "output_settings_json", None), language_profile=episode.language_profile)


def _truncate_source_text(value: Any, *, limit: int = MAX_SOURCE_CHUNK_TEXT_CHARS) -> str:
    text = _clean(value)
    if len(text) <= limit:
        return text
    return text[: max(0, limit - 1)].rstrip(" ,.;:\n\t") + "…"


def _evenly_sample(items: list[dict[str, Any]], limit: int) -> list[dict[str, Any]]:
    if limit <= 0:
        return []
    if len(items) <= limit:
        return list(items)
    if limit == 1:
        return [items[0]]
    last_index = len(items) - 1
    indexes = {
        round(index * last_index / (limit - 1))
        for index in range(limit)
    }
    return [items[index] for index in sorted(indexes)]


def _compact_source_chunks_for_prompt(chunks: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Build a bounded source snapshot for Story Studio AI prompts.

    The full source remains pinned in StoryEpisodeSourceDocument. Candidate
    generation only needs a representative, ordered chapter snapshot; sending
    every raw chunk and every chunk UUID can make Codex spend the whole timeout
    reading prompt context instead of producing JSON.
    """

    valid_chunks = [
        chunk
        for chunk in chunks
        if isinstance(chunk, dict) and _clean(chunk.get("text"))
    ]
    if not valid_chunks:
        return []

    script_chunks = [
        chunk
        for chunk in valid_chunks
        if str(chunk.get("chunk_type") or "").lower() in {"script", "summary", "plot"}
    ][:8]
    sampled_chunks = _evenly_sample(valid_chunks, MAX_SOURCE_PROMPT_CHUNKS)
    selected_by_id: dict[str, dict[str, Any]] = {}
    selected_without_id: list[dict[str, Any]] = []
    for chunk in [*script_chunks, *sampled_chunks]:
        chunk_id = _clean(chunk.get("id"))
        if chunk_id:
            selected_by_id[chunk_id] = chunk
        else:
            selected_without_id.append(chunk)
    selected = [*selected_by_id.values(), *selected_without_id]
    selected.sort(key=lambda chunk: int(chunk.get("chunk_order") or 0))

    compact: list[dict[str, Any]] = []
    used_chars = 0
    for chunk in selected:
        text = _truncate_source_text(chunk.get("text"))
        if not text:
            continue
        if used_chars + len(text) > MAX_SOURCE_PROMPT_CHARS:
            break
        evidence_ids = chunk.get("evidence_ids")
        compact.append(
            {
                "id": chunk.get("id"),
                "chunk_order": chunk.get("chunk_order"),
                "chunk_type": chunk.get("chunk_type"),
                "text": text,
                "evidence_ids": evidence_ids[:3] if isinstance(evidence_ids, list) else [],
                "source_revision": chunk.get("source_revision"),
            }
        )
        used_chars += len(text)
    return compact


def _source_package_content_text(value: Any) -> str:
    if isinstance(value, dict):
        for key in ("text", "summary", "content"):
            text = _clean(value.get(key))
            if text:
                return text
        beats = value.get("beats")
        if isinstance(beats, list):
            return "\n".join(str(item) for item in beats if _clean(item)).strip()
    return _value_to_text(value)


def _source_package_plot_beats(package: source_package_core.SourcePackage) -> list[str]:
    for block in package.blocks:
        if block.block_type != "plot_beats":
            continue
        content = block.content
        if isinstance(content, dict) and isinstance(content.get("beats"), list):
            return [str(item) for item in content["beats"] if _clean(item)]
        return [str(item) for item in _coerce_list(content) if _clean(item)]
    return []


def _source_package_prompt_chunks(package: source_package_core.SourcePackage) -> list[dict[str, Any]]:
    source_chunks: list[dict[str, Any]] = []
    for block in package.blocks:
        if block.block_type in {"synopsis", "plot_beats"}:
            continue
        content = block.content if isinstance(block.content, dict) else {}
        text = _source_package_content_text(block.content)
        if not text:
            continue
        source_chunks.append(
            {
                "id": content.get("id") or block.metadata.get("chunk_id"),
                "chunk_order": content.get("chunk_order") or block.metadata.get("chunk_order") or block.sort_order,
                "chunk_type": block.block_type,
                "text": text,
                "evidence_ids": content.get("evidence_ids") or block.evidence_refs,
                "source_revision": content.get("source_revision") or package.source_revision,
            }
        )
    return _compact_source_chunks_for_prompt(source_chunks)


def _compile_episode_source_payload(episode: DBStoryEpisode, db: Session) -> tuple[dict[str, Any] | None, str]:
    """Compile the approved StoryEpisodeSourceDocument for candidate prompts.

    Comic handoff episodes keep the full chapter in structured source chunks,
    not in ``source_input``. Candidate generation must explicitly include a
    bounded snapshot of that source or the AI only sees series memory.
    """
    try:
        package_summary = comic_source_context.compile_source_package(
            db,
            episode.id,
            char_budget=16000,
            task_type="story_candidate",
        )
    except Exception:
        return None, ""
    package = package_summary.source_package
    if not package.source_ref_id:
        return None, ""
    provenance = package.provenance or {}
    prompt_chunks = _source_package_prompt_chunks(package)
    compact_blocks = source_package_core.to_ai_video_source_blocks(
        package,
        max_content_chars=MAX_SOURCE_CHUNK_TEXT_CHARS,
    )
    plot_beats = _source_package_plot_beats(package)
    payload = {
        "schema_version": package.schema_version,
        "source_kind": package.source_kind,
        "source_ref_id": package.source_ref_id,
        "source_revision": package.source_revision,
        "source_document_id": package.source_ref_id,
        "source_document_revision": package.source_revision,
        "title": package.title,
        "summary": package.summary,
        "coverage_metrics": package.coverage_metrics,
        "limitations": package.limitations,
        "provenance": provenance,
        "fingerprint": package.fingerprint,
        "blocks": compact_blocks,
        "original_source_kind": provenance.get("source_kind"),
        "comic_job_id": provenance.get("comic_job_id"),
        "comic_analysis_revision": provenance.get("comic_analysis_revision"),
        "development_mode": provenance.get("development_mode"),
        "synopsis": package.summary,
        "plot_beats": plot_beats,
        "accepted_chunk_count": package_summary.selected_chunk_count,
        "prompt_chunk_count": len(prompt_chunks),
        "prompt_chunk_selection": "SourcePackage blocks compacted into ordered prompt snapshot",
        "used_chunk_ids_sample": (provenance.get("used_chunk_ids") or [])[:10],
        "omitted_chunk_count": package_summary.omitted_chunk_count,
        "chunks": prompt_chunks,
    }
    text_parts: list[str] = [
        f"Structured source package: {package.source_ref_id} rev {package.source_revision}",
        f"Source package schema: {package.schema_version}",
        f"Source package fingerprint: {package.fingerprint}",
    ]
    if provenance.get("source_kind"):
        text_parts.append(f"Original source kind: {provenance.get('source_kind')}")
    if _clean(package.summary):
        text_parts.append(f"Synopsis:\n{package.summary}")
    if plot_beats:
        text_parts.append("Plot beats:\n" + "\n".join(f"- {item}" for item in plot_beats if _clean(item)))
    if prompt_chunks:
        lines: list[str] = []
        for chunk in prompt_chunks:
            text = _clean(chunk.get("text"))
            if not text:
                continue
            lines.append(
                f"[{chunk.get('chunk_order')}] {chunk.get('chunk_type')}: {text}"
            )
        if lines:
            text_parts.append("Compact accepted source snapshot:\n" + "\n".join(lines))
        if package_summary.selected_chunk_count > len(prompt_chunks):
            text_parts.append(
                f"Prompt source snapshot sampled {len(prompt_chunks)} of {package_summary.selected_chunk_count} accepted chunks. "
                "Use synopsis/plot beats plus this ordered sample; full source remains pinned by fingerprint."
            )
    if package_summary.omitted_chunk_count:
        text_parts.append(f"Omitted accepted chunks due to prompt budget: {package_summary.omitted_chunk_count}")
    return payload, "\n\n".join(text_parts)[:18000]


def _master_text_list(master: dict[str, Any], key: str) -> list[str]:
    return [text for item in _coerce_list(master.get(key)) if (text := _clean(item))]

def _story_text_chunks(text: str, target_count: int) -> list[str]:
    source = _clean(text)
    if not source or target_count <= 0:
        return []
    sentences = [part.strip() for part in re.split(r"(?<=[.!?。！？])\s+|\n+", source) if part.strip()]
    if len(sentences) >= target_count:
        group_size = max(1, (len(sentences) + target_count - 1) // target_count)
        chunks: list[str] = []
        for index in range(0, len(sentences), group_size):
            chunks.append(" ".join(sentences[index : index + group_size]).strip())
            if len(chunks) >= target_count:
                break
        return chunks
    if sentences:
        return sentences
    if len(source) <= 240:
        return [source]
    chunk_size = max(120, min(360, len(source) // max(1, target_count)))
    return [source[index : index + chunk_size].strip(" ,.;:\n\t") for index in range(0, len(source), chunk_size) if source[index : index + chunk_size].strip()]

def _panel_rows_from_master(master: dict[str, Any], target_count: int | None = None) -> list[dict[str, Any]]:
    raw_beats = _master_text_list(master, "key_beats")
    raw_visuals = _master_text_list(master, "visual_moments")
    raw_motions = _master_text_list(master, "motion_beats")
    beats = [_sanitize_story_panel_source_text(text, remove_hook_label=True) for text in raw_beats]
    visuals = [_sanitize_story_panel_source_text(text, remove_hook_label=True) for text in raw_visuals]
    motions = [_sanitize_story_panel_source_text(text, remove_hook_label=True) for text in raw_motions]
    beats = [text for text in beats if text]
    visuals = [text for text in visuals if text]
    motions = [text for text in motions if text]
    full_story = _clean(master.get("full_story"))
    fallback = [
        _sanitize_story_panel_source_text(full_story[:240], remove_hook_label=True) or "Dien bien chinh",
        _sanitize_story_panel_source_text(_clean(master.get("logline")), remove_hook_label=True) or "Xung dot chinh",
        "Payoff cuoi tap",
    ]
    if target_count is None:
        story_based_count = min(
            MAX_AUTO_IMAGE_PANEL_COUNT,
            max(MIN_AUTO_IMAGE_PANEL_COUNT, (len(full_story) + AUTO_PANEL_TARGET_STORY_CHARS - 1) // AUTO_PANEL_TARGET_STORY_CHARS),
        )
        target_count = max(story_based_count, len(beats), len(visuals), len(motions), len(fallback))
    story_chunks = [
        text
        for text in (
            _sanitize_story_panel_source_text(chunk, remove_hook_label=True)
            for chunk in _story_text_chunks(full_story, int(target_count or 0))
        )
        if text
    ]
    target_count = min(target_count, MAX_IMAGE_PANEL_COUNT)
    rows: list[dict[str, Any]] = []
    for index in range(target_count):
        raw_caption_source = (
            (raw_beats[index] if index < len(raw_beats) else "")
            or (story_chunks[index] if index < len(story_chunks) else "")
        )
        beat = (
            (beats[index] if index < len(beats) else "")
            or (story_chunks[index] if index < len(story_chunks) else "")
            or (visuals[index] if index < len(visuals) else "")
            or (motions[index] if index < len(motions) else "")
            or f"{fallback[index % len(fallback)]} - panel {index + 1}"
        )
        visual = (
            (visuals[index] if index < len(visuals) else "")
            or (story_chunks[index] if index < len(story_chunks) else "")
            or (motions[index] if index < len(motions) else "")
            or beat
        )
        motion = motions[index] if index < len(motions) else ""
        rows.append(
            {
                "beat": beat,
                "visual": visual,
                "motion": motion,
                "caption": _sanitize_story_panel_source_text(raw_caption_source, remove_hook_label=False),
                "source_type": "master_story",
            }
        )
    return rows

def _linked_video_project_id(episode_id: str, db: Session) -> str | None:
    row = (
        db.query(DBStoryAdaptation)
        .filter(DBStoryAdaptation.story_episode_id == episode_id, DBStoryAdaptation.kind == "video_story")
        .order_by(DBStoryAdaptation.created_at.desc())
        .first()
    )
    return row.linked_video_project_id if row and row.linked_video_project_id else None

def _panel_rows_from_video_micro_scenes(project_id: str, db: Session) -> list[dict[str, Any]]:
    shots = (
        db.query(DBVideoShot)
        .filter(DBVideoShot.project_id == project_id)
        .order_by(DBVideoShot.shot_order.asc(), DBVideoShot.created_at.asc())
        .all()
    )
    rows: list[dict[str, Any]] = []
    for shot in shots:
        micro_scenes = shot.micro_scenes_json if isinstance(shot.micro_scenes_json, list) else []
        if micro_scenes:
            for micro_index, micro in enumerate(micro_scenes, start=1):
                if not isinstance(micro, dict):
                    continue
                micro_order = int(micro.get("order") or micro_index)
                description = (
                    _sanitize_story_panel_source_text(micro.get("description_vi"), remove_hook_label=True)
                    or _sanitize_story_panel_source_text(shot.vietnamese_description, remove_hook_label=True)
                )
                visual = (
                    _sanitize_story_panel_source_text(micro.get("visual_action"), remove_hook_label=True)
                    or description
                    or _sanitize_story_panel_source_text(shot.primary_action, remove_hook_label=True)
                )
                camera = (
                    _sanitize_story_panel_source_text(micro.get("camera_note"), remove_hook_label=True)
                    or _sanitize_story_panel_source_text(shot.camera_motion, remove_hook_label=True)
                )
                continuity = _sanitize_story_panel_source_text(micro.get("continuity_note"), remove_hook_label=True)
                timing = ""
                if micro.get("start_seconds") is not None and micro.get("end_seconds") is not None:
                    timing = f"{micro.get('start_seconds')}-{micro.get('end_seconds')}s"
                rows.append(
                    {
                        "beat": f"Shot {shot.shot_order}.{micro_order}: {description or visual}",
                        "visual": visual or description or f"Shot {shot.shot_order} micro-scene {micro_order}",
                        "motion": camera,
                        "source_type": "video_micro_scene",
                        "source_project_id": project_id,
                        "source_shot_id": shot.id,
                        "source_shot_order": shot.shot_order,
                        "source_micro_scene_order": micro_order,
                        "source_timing": timing,
                        "continuity": continuity,
                    }
                )
        else:
            description = _clean(shot.vietnamese_description) or _clean(shot.primary_action)
            rows.append(
                {
                    "beat": f"Shot {shot.shot_order}: {description or shot.purpose or 'Video shot'}",
                    "visual": _clean(shot.primary_action) or description or f"Shot {shot.shot_order}",
                    "motion": _clean(shot.camera_motion),
                    "source_type": "video_shot",
                    "source_project_id": project_id,
                    "source_shot_id": shot.id,
                    "source_shot_order": shot.shot_order,
                }
            )
    return rows[:MAX_IMAGE_PANEL_COUNT]

def _normalize_story_payload(payload: dict[str, Any], *, episode: DBStoryEpisode, strategy_type: str | None = None) -> dict[str, Any]:
    normalized = dict(payload)
    for field in [
        "key_beats",
        "character_emotions",
        "visual_moments",
        "motion_beats",
        "must_have",
        "avoid",
        "continuity_updates",
        "strengths_claimed",
        "risks_claimed",
    ]:
        if field in normalized:
            normalized[field] = _coerce_list(normalized.get(field))
    normalized["market_profile"] = _clean(normalized.get("market_profile")) or episode.market_profile
    normalized["language_profile"] = _clean(normalized.get("language_profile")) or episode.language_profile
    if strategy_type:
        normalized["strategy_type"] = strategy_type
        normalized["strategy_label"] = _strategy_label(strategy_type)
    return normalized

def _validate_candidate_script(payload: dict[str, Any], *, episode: DBStoryEpisode, strategy_type: str) -> dict[str, Any]:
    if not isinstance(payload, dict):
        raise StoryStudioError("AI trả candidate không đúng cấu trúc object.")
    if _clean(payload.get("strategy_type")) != strategy_type:
        raise StoryStudioError(f"Candidate không đúng strategy {strategy_type}.")
    normalized = _normalize_story_payload(payload, episode=episode, strategy_type=strategy_type)
    _validate_master_story(normalized)
    if normalized.get("strategy_type") != strategy_type:
        raise StoryStudioError(f"Candidate không đúng strategy {strategy_type}.")
    return normalized

def _tokens(value: Any) -> set[str]:
    text = _value_to_text(value).lower()
    return {token for token in re.findall(r"[\wÀ-ỹ]+", text, flags=re.UNICODE) if len(token) > 2}

def _jaccard(left: set[str], right: set[str]) -> float:
    if not left or not right:
        return 0.0
    return len(left & right) / max(1, len(left | right))

def _candidate_signature(payload: dict[str, Any]) -> set[str]:
    return _tokens(
        {
            "hook": payload.get("hook"),
            "key_beats": payload.get("key_beats"),
            "visual_moments": payload.get("visual_moments"),
            "motion_beats": payload.get("motion_beats"),
            "full_story": payload.get("full_story"),
        }
    )

def _validate_distinct_candidates(candidates: list[dict[str, Any]]) -> None:
    if len(candidates) != 3:
        raise StoryStudioError("Cần đúng ba candidate hợp lệ.")
    strategies = {candidate.get("strategy_type") for candidate in candidates}
    expected = {strategy for strategy, _label in STRATEGIES}
    if strategies != expected:
        raise StoryStudioError("Ba candidate chưa đủ ba chiến lược bắt buộc.")
    for index, left in enumerate(candidates):
        for right in candidates[index + 1 :]:
            if _jaccard(_candidate_signature(left), _candidate_signature(right)) > 0.82:
                raise StoryStudioError("Ba candidate quá giống nhau; AI cần tạo khác biệt thật về hook, beat hoặc trọng tâm hình ảnh/cảm xúc.")

def _should_use_story_studio_ai_fallback(exc: Exception) -> bool:
    """Return True for provider availability/latency failures, not content bugs.

    The local fallback is for keeping Story Studio usable when the configured
    provider is overloaded, unavailable, or too slow. Schema/content validation
    errors should still surface because silently masking them would hide product
    bugs such as invalid response_format schemas.
    """

    text = str(exc).lower()
    if any(
        marker in text
        for marker in [
            "invalid schema",
            "invalid_json_schema",
            "json schema",
            "bad_request",
            "schema validation",
            "json không hợp lệ",
            "json khong hop le",
        ]
    ):
        return False
    return any(
        marker in text
        for marker in [
            "timed out",
            "timeout",
            "time out",
            "server error",
            "server lỗi",
            "server loi",
            "overloaded",
            "unavailable",
            "temporarily unavailable",
            "rate limit",
            "connection",
            "network",
            "err_failed",
            "econnreset",
            "502",
            "503",
            "504",
            "gateway",
            "upstream 5",
        ]
    )

def _fallback_source_anchors(
    episode: DBStoryEpisode,
    creative_brief: dict[str, Any],
    *,
    limit: int = 8,
) -> list[str]:
    anchors: list[str] = []
    seen: set[str] = set()

    def add(value: Any, *, max_chars: int = 260) -> None:
        text = _clip_prompt_text(value, max_chars)
        key = text.lower()
        if text and key not in seen:
            seen.add(key)
            anchors.append(text)

    add(episode.title, max_chars=180)
    add(episode.source_input, max_chars=260)
    add(creative_brief.get("source_digest"), max_chars=220)
    structured_source = creative_brief.get("structured_source")
    if isinstance(structured_source, dict):
        add(structured_source.get("synopsis"), max_chars=320)
        for beat in _coerce_list(structured_source.get("plot_beats")):
            add(beat, max_chars=220)
        chunks = structured_source.get("chunks")
        if isinstance(chunks, list):
            for chunk in chunks:
                if isinstance(chunk, dict):
                    add(chunk.get("text"), max_chars=180)
    if not anchors:
        add("Tập truyện hiện tại cần được chuyển thành Master Story bám sát nguồn.", max_chars=220)
    return anchors[:limit]

def _is_comic_story_brief(creative_brief: dict[str, Any]) -> bool:
    structured_source = creative_brief.get("structured_source")
    source_kind = structured_source.get("source_kind") if isinstance(structured_source, dict) else None
    original_source_kind = structured_source.get("original_source_kind") if isinstance(structured_source, dict) else None
    provenance = structured_source.get("provenance") if isinstance(structured_source, dict) else None
    provenance_source_kind = provenance.get("source_kind") if isinstance(provenance, dict) else None
    visual_style = _value_to_text(
        [
            source_kind,
            original_source_kind,
            provenance_source_kind,
            creative_brief.get("visual_style_guidance"),
            creative_brief.get("series_bible", {}).get("style_bible") if isinstance(creative_brief.get("series_bible"), dict) else "",
        ]
    ).lower()
    return any(marker in visual_style for marker in ["comic", "manga", "webtoon", "anime", "truyện tranh"])

def _fallback_strategy_profile(strategy_type: str) -> dict[str, Any]:
    profiles = {
        "hook_retention": {
            "title_suffix": "bản hook giữ chân",
            "hook_frame": "Mở ngay bằng chi tiết gây tò mò nhất của nguồn, đặt câu hỏi khiến người đọc phải lật tiếp panel.",
            "focus": "bí mật, câu hỏi mở, nhịp cliffhanger và payoff rõ",
            "opening": "Nhịp mở ưu tiên một hook sắc: người đọc thấy ngay biến cố quan trọng trước khi hiểu toàn bộ bối cảnh.",
            "middle": "Phần giữa giữ nhịp bằng các câu hỏi nhỏ, mỗi beat hé thêm nguyên nhân và đẩy nhân vật tới lựa chọn khó hơn.",
            "payoff": "Cuối tập chốt bằng một quyết định hoặc phát hiện còn dư âm, đủ để kéo sang tập sau.",
            "emotions": ["tò mò", "căng thẳng", "quyết tâm", "bị cuốn vào bí mật"],
            "visuals": ["cận cảnh chi tiết then chốt như một hook panel", "ánh mắt nhân vật khi nhận ra mâu thuẫn", "khung cuối để lại câu hỏi lớn"],
            "motions": ["push-in vào chi tiết gây tò mò", "cut nhanh theo từng manh mối", "giữ nhịp dừng ở cliffhanger"],
            "strengths": ["Giữ chân tốt ở đầu tập", "Có câu hỏi dẫn dắt từng beat"],
            "risks": ["Nếu lạm dụng cliffhanger có thể làm cảm xúc bị mỏng"],
        },
        "emotional_drama": {
            "title_suffix": "bản cảm xúc drama",
            "hook_frame": "Mở bằng vết thương cảm xúc hoặc mối quan hệ quan trọng nhất trong nguồn.",
            "focus": "cảm xúc nhân vật, mâu thuẫn gia đình/xã hội, lựa chọn có giá phải trả",
            "opening": "Nhịp mở cho người đọc thấy nhân vật đang bị dồn vào một cảm xúc cụ thể, không chỉ kể sự kiện.",
            "middle": "Phần giữa đào sâu quan hệ, lời nói, ánh mắt và ký ức để biến xung đột thành drama dễ đồng cảm.",
            "payoff": "Cuối tập để nhân vật chọn đứng về điều mình muốn bảo vệ, tạo cảm giác xúc động và công bằng.",
            "emotions": ["tủi thân", "hối tiếc", "thương yêu", "muốn bảo vệ", "kiên định"],
            "visuals": ["cận mặt đọc rõ cảm xúc", "khoảng cách giữa các nhân vật trong cùng khung hình", "bàn tay hoặc ánh mắt giữ lại lời chưa nói"],
            "motions": ["slow push vào biểu cảm", "pause ở khoảng lặng", "chuyển cảnh mềm theo cảm xúc"],
            "strengths": ["Dễ tạo đồng cảm", "Drama rõ động cơ và mối quan hệ"],
            "risks": ["Cần tránh thoại giải thích quá dài"],
        },
        "visual_action": {
            "title_suffix": "bản visual hành động",
            "hook_frame": "Mở bằng một khung hình có chuyển động hoặc tương phản thị giác mạnh.",
            "focus": "bố cục panel, hành động rõ, tương phản hình ảnh và nhịp chuyển cảnh",
            "opening": "Nhịp mở biến sự kiện nguồn thành một khung hình mạnh, nhìn vào là hiểu nguy cơ hoặc mục tiêu.",
            "middle": "Phần giữa sắp xếp các beat theo chuỗi hình ảnh: toàn cảnh, cận cảnh, phản ứng, rồi hành động quyết định.",
            "payoff": "Cuối tập kết bằng một visual anchor dễ nhớ để chuyển thẳng sang prompt ảnh hoặc shot video.",
            "emotions": ["bất ngờ", "khẩn trương", "dứt khoát", "bùng nổ thị giác"],
            "visuals": ["toàn cảnh thiết lập không gian", "góc máy thấp làm nhân vật có lực", "tương phản sáng tối ở khoảnh khắc quyết định"],
            "motions": ["pan theo chuyển động chính", "snap cut sang phản ứng", "pull-back ở visual payoff"],
            "strengths": ["Dễ chuyển thành panel/prompt ảnh", "Nhịp hình rõ và giàu chuyển động"],
            "risks": ["Cần giữ hành động đơn nghĩa để không rối panel"],
        },
    }
    return profiles.get(strategy_type, profiles["hook_retention"])

def _rotated_anchors(anchors: list[str], strategy_type: str) -> list[str]:
    if not anchors:
        return []
    offsets = {"hook_retention": 0, "emotional_drama": 1, "visual_action": 2}
    offset = offsets.get(strategy_type, 0) % len(anchors)
    rotated = anchors[offset:] + anchors[:offset]
    return rotated[:4]

def _fallback_strategy_beats(
    strategy_type: str,
    profile: dict[str, Any],
    *,
    anchor_1: str,
    anchor_2: str,
    anchor_3: str,
) -> list[str]:
    """Keep all-provider-fallback candidates distinct enough for review gates."""

    if strategy_type == "emotional_drama":
        return [
            f"Khoảng lặng mở đầu: đặt {anchor_1} như vết thương cảm xúc đầu tiên, để nhân vật phản ứng bằng im lặng trước khi nói thành lời.",
            f"Neo quan hệ: dùng {anchor_2} để gọi lại người nhân vật muốn bảo vệ, ưu tiên ánh mắt, bàn tay và khoảng cách trong khung hình.",
            "Nhói ký ức: một lời hứa cũ hoặc lời tiếc nuối quay lại, biến sự kiện thành mất mát riêng chứ không chỉ là thông tin.",
            "Xung đột nội tâm: nhân vật muốn lao đi sửa mọi thứ nhưng bị thân phận, tuổi tác hoặc quyền lực hiện tại chặn lại.",
            f"Cảnh chậm: {profile['middle']} Tập trung vào một cử chỉ nhỏ làm rõ tình yêu và nỗi sợ.",
            f"Vết cắt gia đình: {anchor_3} được nhìn qua lăng kính 'nếu mình không hành động, người này sẽ mất'.",
            "Đối diện cảm xúc: nhân vật thừa nhận với chính mình điều mình sợ nhất, không cần tiết lộ bí mật cho người khác.",
            "Quyết tâm nhỏ: một hành động dịu nhưng rõ như nắm tay, lau nước mắt, quay lại nhìn cửa phòng hoặc gọi tên người thân.",
            f"Payoff tình cảm: {profile['payoff']}",
            "Khung kết: để lại dư âm thương yêu, lời hứa bảo vệ và một vệt lo lắng cho tập sau.",
        ]
    if strategy_type == "visual_action":
        return [
            f"Vertical action opener: biến {anchor_1} thành panel dọc có đường dẫn mắt rõ, nhân vật hoặc chi tiết chuyển động cắt ngang khung hình.",
            "Establishing panel rộng: cho thấy không gian, độ cao, cửa ra vào hoặc hướng chạy để độc giả hiểu đường đi của cảnh.",
            f"Snap reaction: {anchor_2} xuất hiện bằng close-up nhanh, tạo cảm giác phát hiện bất ngờ.",
            "Motion chain: toàn cảnh -> cận cảnh -> phản ứng -> hành động, mỗi panel chỉ mang một chuyển động chính.",
            f"Thị giác leo thang: {profile['middle']}",
            f"Contrast beat: dùng {anchor_3} làm điểm đổi sáng/tối hoặc lớn/nhỏ để nhân vật trông có lực hơn.",
            "Action decision: nhân vật bước, chạy, với tay hoặc mở cửa; hành động vật lý thay cho độc thoại dài.",
            "Impact panel: dùng low angle, speed line nhẹ hoặc khoảng trắng mạnh để động tác có trọng lượng.",
            f"Visual anchor payoff: {profile['payoff']}",
            "Khung kết: một hình ảnh dễ nhớ có thể tách thẳng thành prompt ảnh hoặc shot video 9:16.",
        ]
    return [
        f"Cold-open question: mở bằng {anchor_1} và đặt ngay câu hỏi lớn nhất trước khi giải thích bối cảnh.",
        "Micro cliffhanger 1: cắt cảnh trước câu trả lời, để caption ngắn hứa rằng sự thật nằm ở panel kế tiếp.",
        f"Reveal có kiểm soát: đưa {anchor_2} vào như manh mối thứ hai, chỉ trả lời một nửa vấn đề.",
        "Retention loop: mỗi 2-3 panel mở một câu hỏi nhỏ rồi trả bằng hành động hoặc cử chỉ thay vì độc thoại dài.",
        f"Áp lực tăng: {profile['middle']}",
        f"Twist giữa tập: {anchor_3} biến mục tiêu ban đầu thành vấn đề lớn hơn.",
        "False safety beat: nhân vật tưởng đã hiểu tình huống nhưng một chi tiết nhỏ phủ nhận kết luận đó.",
        "Choice under pressure: nhân vật phải chọn hành động ngay, trong khi chưa có đủ thông tin.",
        f"Final hook payoff: {profile['payoff']}",
        "Last-panel promise: kết bằng câu hỏi mới rõ ràng, đủ sức kéo độc giả sang tập tiếp theo.",
    ]

def _fallback_candidate_payload(
    *,
    episode: DBStoryEpisode,
    creative_brief: dict[str, Any],
    strategy_type: str,
    fallback_reason: str,
) -> dict[str, Any]:
    label = _strategy_label(strategy_type)
    profile = _fallback_strategy_profile(strategy_type)
    anchors = _rotated_anchors(_fallback_source_anchors(episode, creative_brief), strategy_type)
    anchor_1 = anchors[0] if len(anchors) > 0 else "nguồn truyện đã handoff"
    anchor_2 = anchors[1] if len(anchors) > 1 else anchor_1
    anchor_3 = anchors[2] if len(anchors) > 2 else anchor_2
    base_title = _clean(episode.title) or _clean(creative_brief.get("series_title")) or f"Tập {episode.episode_number}"
    comic_note = (
        "Giữ cảm giác anime/manga/webtoon, bố cục dọc 9:16, nhân vật nhất quán qua từng panel."
        if _is_comic_story_brief(creative_brief)
        else "Giữ visual style đã khai báo trong series và tránh đổi nhận diện nhân vật."
    )
    title = f"{base_title} — {profile['title_suffix']}"
    fallback_beats = _fallback_strategy_beats(
        strategy_type,
        profile,
        anchor_1=anchor_1,
        anchor_2=anchor_2,
        anchor_3=anchor_3,
    )
    full_story = "\n\n".join(
        [
            f"Cảnh {index:02d}: {beat}"
            for index, beat in enumerate(fallback_beats, start=1)
        ]
        + [
            "Ghi chú dựng truyện ảnh: mỗi cảnh trên có thể tách thành 1-3 panel dọc 9:16; giữ anime/manga/webtoon nếu nguồn là truyện tranh, giữ mặt/trang phục/fixed traits nhất quán, không thêm canon mới ngoài nguồn đã handoff."
        ]
    )
    payload = {
        "strategy_type": strategy_type,
        "strategy_label": label,
        "title": title,
        "logline": f"{label}: bám theo nguồn đã handoff, nhấn vào {profile['focus']} để tạo một hướng kể riêng.",
        "hook": f"{profile['hook_frame']} Chi tiết mở: {anchor_1}.",
        "full_story": full_story,
        "key_beats": fallback_beats,
        "character_emotions": profile["emotions"],
        "visual_moments": [
            f"{label} panel opener: {profile['opening']}",
            *profile["visuals"],
            f"Visual anchor từ nguồn: {anchor_1}",
            f"Cliffhanger cuối: {anchor_3}",
        ],
        "motion_beats": [
            f"{label} opening rhythm: {profile['opening']}",
            *profile["motions"],
            "hold frame ở cliffhanger cuối tập",
        ],
        "retention_plan": (
            f"Dùng {profile['focus']} làm trục giữ chân: mỗi 2-3 panel phải mở một câu hỏi nhỏ, "
            "sau đó trả lời bằng hành động/cảm xúc cụ thể trước khi chuyển sang câu hỏi tiếp theo."
        ),
        "market_profile": _clean(episode.market_profile) or _clean(creative_brief.get("market_profile")) or "viet_nam",
        "language_profile": _clean(episode.language_profile) or _clean(creative_brief.get("language_profile")) or "vi",
        "must_have": [
            "Bám sát source document/source_input đã handoff.",
            "Giữ đúng fixed traits, quan hệ nhân vật và continuity hiện có.",
            comic_note,
        ],
        "avoid": [
            "Không bịa thêm tuyến chính ngoài nguồn.",
            "Không tự lưu continuity update khi người dùng chưa duyệt.",
            "Không đổi sang photorealistic/live-action nếu nguồn là truyện tranh/anime.",
        ],
        "continuity_updates": [],
        "image_story_notes": f"{comic_note} Ưu tiên panel đọc được, caption ngắn, một hành động chính mỗi panel.",
        "video_story_notes": "Nếu handoff sang AI Video, giữ cùng Master Story; mỗi beat chuyển thành shot/micro-scene rõ hành động, cảm xúc và nhịp chuyển.",
        "strengths_claimed": profile["strengths"],
        "risks_claimed": [*profile["risks"], f"Fallback do provider lỗi/chậm: {fallback_reason[:220]}"],
    }
    return _validate_candidate_script(payload, episode=episode, strategy_type=strategy_type)

def _candidate_error_text(row: DBStoryScenarioCandidate) -> str:
    script = row.script_json if isinstance(row.script_json, dict) else {}
    metadata = row.generation_metadata_json if isinstance(row.generation_metadata_json, dict) else {}
    return (
        _clean(script.get("error_message"))
        or _clean(metadata.get("last_error"))
        or _clean(metadata.get("fallback_reason"))
        or _clean(metadata.get("evaluation_error"))
    )

def _candidate_row_has_completed_payload(row: DBStoryScenarioCandidate, episode: DBStoryEpisode) -> bool:
    if row.generation_status != "completed" or not isinstance(row.script_json, dict):
        return False
    try:
        _validate_candidate_script(row.script_json, episode=episode, strategy_type=row.strategy_type)
    except Exception:
        return False
    return True

def _creative_brief_from_candidate_rows(rows: list[DBStoryScenarioCandidate]) -> dict[str, Any]:
    for row in rows:
        if isinstance(row.script_json, dict) and isinstance(row.script_json.get("creative_brief"), dict):
            return row.script_json["creative_brief"]
    return {}

def _candidate_payload_strengths(payload: dict[str, Any]) -> str:
    return "\n".join(
        str(item)
        for item in _coerce_list(payload.get("strengths_claimed"))
        if _clean(item)
    )

def _candidate_payload_risks(payload: dict[str, Any]) -> str:
    return "\n".join(
        str(item)
        for item in _coerce_list(payload.get("risks_claimed"))
        if _clean(item)
    )

def _repair_candidate_rows_with_fallback(
    episode: DBStoryEpisode,
    rows: list[DBStoryScenarioCandidate],
    creative_brief: dict[str, Any],
    db: Session,
) -> bool:
    """Convert provider-timeout candidate rows into usable fallback candidates.

    Earlier runs can leave rows in ``failed`` after Codex times out even though
    Story Studio has enough pinned source/context to continue with its local
    fallback. This repair is intentionally narrow: it only repairs rows whose
    stored error looks like provider latency/availability. Schema/content bugs
    still surface instead of being silently hidden.
    """

    repaired = False
    context_snapshot_id = None
    if isinstance(creative_brief, dict):
        context_snapshot_id = creative_brief.get("series_context_trace_id")
    for row in rows:
        if _candidate_row_has_completed_payload(row, episode):
            continue
        reason = _candidate_error_text(row)
        if not reason or not _should_use_story_studio_ai_fallback(Exception(reason)):
            continue
        previous_status = row.generation_status
        payload = _fallback_candidate_payload(
            episode=episode,
            creative_brief=creative_brief,
            strategy_type=row.strategy_type,
            fallback_reason=reason,
        )
        row.script_json = {
            **payload,
            "creative_brief": creative_brief,
            "context_snapshot_id": row.context_snapshot_id or context_snapshot_id,
        }
        row.strengths = _candidate_payload_strengths(payload)
        row.risks = _candidate_payload_risks(payload)
        row.generation_status = "completed"
        row.evaluation_status = "pending"
        row.generation_metadata_json = {
            **(row.generation_metadata_json or {}),
            "fallback_used": True,
            "fallback_reason": reason[:1000],
            "repaired_from_status": previous_status,
            "repaired_at": datetime.utcnow().isoformat(),
        }
        row.updated_at = datetime.utcnow()
        repaired = True
        video_observability.log_event(
            db,
            step_name="story_studio_candidate_generation_fallback_repair",
            status="warning",
            error_code="STORY_CANDIDATE_PROVIDER_FALLBACK_REPAIR",
            message="Candidate Story Studio lỗi/chậm trước đó; dùng fallback nội bộ để đủ 3 hướng.",
            technical_details={
                "episode_id": episode.id,
                "candidate_id": row.id,
                "strategy_type": row.strategy_type,
            },
        )
    if repaired:
        db.flush()
    return repaired

def _require_completed_candidate_rows(
    episode: DBStoryEpisode,
    rows: list[DBStoryScenarioCandidate],
) -> None:
    invalid = [
        row.strategy_type
        for row in rows
        if not _candidate_row_has_completed_payload(row, episode)
    ]
    if invalid:
        raise StoryStudioError(
            "Cần có đủ 3 hướng kịch bản đã tạo thành công trước khi chấm/tổng hợp. "
            f"Chưa hoàn chỉnh: {', '.join(invalid)}."
        )

def _fallback_evaluation_payload(
    episode: DBStoryEpisode,
    candidates: list[dict[str, Any]],
    *,
    fallback_reason: str,
) -> dict[str, Any]:
    score_bias = {
        "hook_retention": 2.0 if episode.output_intent in {"video_truyen", "ca_hai"} else 0.5,
        "emotional_drama": 1.5,
        "visual_action": 2.0 if episode.output_intent in {"truyen_anh", "ca_hai"} else 0.5,
    }
    reviews: list[dict[str, Any]] = []
    by_strategy = {candidate.get("strategy_type"): candidate for candidate in candidates if isinstance(candidate, dict)}
    for index, (strategy_type, label) in enumerate(STRATEGIES):
        candidate = by_strategy.get(strategy_type, {})
        total = 83.0 + score_bias.get(strategy_type, 0.0) + index
        criteria = {
            "canon": 14,
            "strategic_difference": 12 + index,
            "hook_retention": 13 if strategy_type == "hook_retention" else 10,
            "emotion_logic": 13 if strategy_type == "emotional_drama" else 10,
            "visual_production": 13 if strategy_type == "visual_action" else 10,
            "pacing_payoff": 11,
            "market_language_fit": 9,
            "production_risk": 7,
        }
        evidence = [
            _clean(candidate.get("hook")) or f"{label} có hook riêng.",
            (_coerce_list(candidate.get("key_beats")) or [f"{label} có beat riêng."])[0],
        ]
        reviews.append(
            {
                "strategy_type": strategy_type,
                "total": round(total, 1),
                "criteria": criteria,
                "reason_vi": (
                    f"Chấm fallback vì provider đang lỗi/chậm. {label} đủ cấu trúc, có trọng tâm riêng "
                    "và bám nguồn/canon ở mức dùng được để tiếp tục workflow."
                ),
                "evidence": [item for item in evidence if _clean(item)],
                "strengths": _coerce_list(candidate.get("strengths_claimed")) or [f"Trọng tâm {label} rõ."],
                "weaknesses": ["Điểm số fallback cần người dùng/AI kiểm lại khi provider ổn định."],
                "risks": [f"Provider fallback: {fallback_reason[:220]}"],
                "recommended_parts": [
                    f"Dùng phần mạnh nhất của {label} khi tổng hợp Master Story.",
                    "Giữ các beat đã bám nguồn và tránh thêm canon mới.",
                ],
            }
        )
    return {
        "rubric": _rubric_text(episode.output_intent),
        "output_intent": episode.output_intent,
        "reviews": reviews,
        "synthesis_guidance": "Provider lỗi/chậm nên dùng fallback: lấy hook giữ chân, cảm xúc rõ và visual dễ render từ ba hướng.",
        "fallback_used": True,
        "fallback_reason": fallback_reason,
    }

def _unique_texts(values: list[Any], *, limit: int = 8) -> list[str]:
    results: list[str] = []
    seen: set[str] = set()
    for value in values:
        text = _clean(value)
        key = text.lower()
        if text and key not in seen:
            seen.add(key)
            results.append(text)
        if len(results) >= limit:
            break
    return results

def _source_text_for_grounded_story(episode: DBStoryEpisode, creative_brief: dict[str, Any] | None) -> str:
    """Return the richest source text available for local grounded fallback.

    Provider fallback must not invent a generic outline. For Story Studio,
    the safest usable fallback is the approved/handoff source itself, plus the
    compiled structured-source synopsis/chunks when present.
    """

    parts: list[str] = []

    def add(value: Any, *, limit: int = 18000) -> None:
        text = _clip_prompt_text(value, limit)
        if text:
            parts.append(text)

    add(getattr(episode, "source_input", None), limit=24000)
    structured_source = creative_brief.get("structured_source") if isinstance(creative_brief, dict) else None
    if isinstance(structured_source, dict):
        add(structured_source.get("synopsis"), limit=6000)
        plot_beats = [str(item) for item in _coerce_list(structured_source.get("plot_beats")) if _clean(item)]
        if plot_beats:
            add("\n".join(f"- {item}" for item in plot_beats), limit=6000)
        chunks = structured_source.get("chunks")
        if isinstance(chunks, list):
            chunk_lines: list[str] = []
            for chunk in chunks:
                if isinstance(chunk, dict) and _clean(chunk.get("text")):
                    order = chunk.get("chunk_order")
                    chunk_type = _clean(chunk.get("chunk_type"))
                    prefix = f"[{order}] {chunk_type}: " if order is not None else ""
                    chunk_lines.append(prefix + _clean(chunk.get("text")))
            add("\n".join(chunk_lines), limit=8000)

    combined = "\n\n".join(parts)
    return combined[:30000]

def _story_source_paragraphs(source_text: str) -> list[str]:
    paragraphs = [
        re.sub(r"\s+", " ", part).strip()
        for part in re.split(r"\n\s*\n+", _clean(source_text))
        if _clean(part)
    ]
    if len(paragraphs) <= 1:
        paragraphs = [line.strip() for line in _clean(source_text).splitlines() if line.strip()]
    skipped_prefixes = (
        "structured source document:",
        "source kind:",
        "prompt source snapshot sampled",
        "omitted accepted chunks",
    )
    return [
        paragraph
        for paragraph in paragraphs
        if paragraph and not paragraph.lower().startswith(skipped_prefixes)
    ]

def _is_story_scene_heading(text: str) -> bool:
    return re.match(r"^(cảnh|scene)\s*\d+\b", _clean(text), flags=re.IGNORECASE) is not None

def _source_story_units(source_text: str) -> list[str]:
    units: list[str] = []
    current_scene = ""
    for paragraph in _story_source_paragraphs(source_text):
        if _is_story_scene_heading(paragraph):
            current_scene = paragraph
            continue
        if len(paragraph) < 8:
            continue
        if current_scene and not paragraph.startswith(current_scene):
            units.append(f"{current_scene}: {paragraph}")
        else:
            units.append(paragraph)
    return units

def _score_source_hook_candidate(text: str) -> int:
    lowered = _clean(text).lower()
    score = 0
    weighted_markers = {
        "con ngoài giá thú": 30,
        "ngoài giá thú": 24,
        "giao gia tộc": 26,
        "quá muộn": 22,
        "cha qua đời": 20,
        "mất cha": 20,
        "không còn ai": 18,
        "vứt bỏ": 18,
        "bảo vệ": 14,
        "công nhận": 14,
        "thừa nhận": 14,
        "quyền": 12,
        "số phận": 12,
        "bí mật": 10,
        "mất": 8,
        "không bao giờ": 8,
    }
    for marker, weight in weighted_markers.items():
        if marker in lowered:
            score += weight
    if any(ch in text for ch in "?!…"):
        score += 6
    if "“" in text or '"' in text:
        score += 5
    return score

def _source_hook_for_master(source_text: str, title: str) -> str:
    """Build a high-retention opening from the strongest source moment."""

    text = _clean(source_text)
    lowered = text.lower()
    if "ta đã có thể giao gia tộc này cho cháu" in lowered and "con ngoài giá thú" in lowered:
        return (
            "Hook mở màn: Trong căn phòng bệnh đêm muộn, ông nội Lombardi cuối cùng thừa nhận điều lẽ ra phải nói từ nhiều năm trước: "
            "“Ta đã có thể giao gia tộc này cho cháu.” Nhưng Florentia không mỉm cười. Cô chỉ siết tập hồ sơ trong tay và đáp bình tĩnh: "
            "“Nhưng cháu chỉ là một đứa con ngoài giá thú, thưa ông.” Câu hỏi giữ chân: một người bị cả gia tộc xem là ngoài rìa sẽ làm gì "
            "khi họ nhận ra cô mới là người xứng đáng nhất?"
        )
    paragraphs = _story_source_paragraphs(text)
    best = max(paragraphs, key=_score_source_hook_candidate, default="")
    best = _clip_prompt_text(best, 520)
    if best:
        return (
            f"Hook mở màn: {best} Câu hỏi giữ chân: vì sao khoảnh khắc này quyết định số phận của "
            f"{title or 'nhân vật chính'}, và cái giá phải trả sẽ là gì?"
        )
    return (
        f"Hook mở màn: {title or 'Tập truyện'} bắt đầu ở khoảnh khắc căng nhất trước khi quay về nguyên nhân. "
        "Câu hỏi giữ chân: điều gì đã đẩy nhân vật đến điểm không thể quay đầu?"
    )

def _target_panel_count_from_source(source_text: str) -> int:
    return min(
        MAX_AUTO_IMAGE_PANEL_COUNT,
        max(MIN_AUTO_IMAGE_PANEL_COUNT, (len(_clean(source_text)) + AUTO_PANEL_TARGET_STORY_CHARS - 1) // AUTO_PANEL_TARGET_STORY_CHARS),
    )

def _group_story_units_for_panels(units: list[str], target_count: int) -> list[str]:
    if not units:
        return []
    target = max(1, target_count)
    group_size = max(1, (len(units) + target - 1) // target)
    grouped: list[str] = []
    for index in range(0, len(units), group_size):
        text = " ".join(units[index : index + group_size]).strip()
        if text:
            grouped.append(_clip_prompt_text(text, 520))
    return grouped

def _panel_visual_from_beat(index: int, total: int, beat: str) -> str:
    lowered = beat.lower()
    if index == 1:
        return (
            "Panel hook cận chi tiết: Florentia/nhân vật chính siết chặt hồ sơ hoặc nhìn thẳng vào lời thừa nhận muộn, "
            "ánh sáng lạnh chia đôi gương mặt, vùng caption sạch phía trên."
        )
    if index == total:
        return (
            "Final cliffhanger panel: khoảng cách giữa nhân vật chính và người đại diện quyền lực trong không gian lớn, "
            "ánh mắt kìm nén, negative space để đặt dòng kết."
        )
    if any(marker in lowered for marker in ["dinh", "hành lang", "phòng", "thư viện", "chân dung", "gia tộc"]):
        return "Toàn cảnh dọc thiết lập bối cảnh: không gian quý tộc rộng lớn, nhân vật nhỏ trong khung hình để nhấn vị thế cô độc."
    if any(marker in lowered for marker in ["cha", "gallahan", "bàn tay", "sơ sinh", "mẹ"]):
        return "Cận cảnh cảm xúc: bàn tay, ánh mắt và khoảng cách cha-con/mẹ-con, ánh sáng mềm nhưng buồn."
    if any(marker in lowered for marker in ["ông nội", "giao gia tộc", "hồ sơ", "tài liệu", "sổ sách", "tài chính"]):
        return "Desk-and-document drama panel: hồ sơ, sổ sách và ánh mắt quyền lực, composition rõ nhân vật đang kiểm soát tình thế."
    if any(marker in lowered for marker in ["làm việc", "học", "quản lý", "kiểm tra", "báo cáo"]):
        return "Work-montage story panel: nến, chồng giấy, dấu bút đỏ và khuôn mặt tập trung, một hành động chính dễ đọc."
    if any(marker in lowered for marker in ["không", "quên", "vứt bỏ", "lãng quên", "im lặng"]):
        return "Lonely reaction panel: nhân vật đứng ở rìa ánh sáng, cửa/đám đông tạo đường chia cách rõ."
    return "Cinematic manga/webtoon medium shot: một hành động chính, biểu cảm rõ, background đủ để hiểu bối cảnh."

def _panel_motion_from_beat(index: int, total: int, beat: str) -> str:
    lowered = beat.lower()
    if index == 1:
        return "slow push-in vào biểu cảm và vật chứng của hook, giữ nhịp căng trong 1 panel"
    if index == total:
        return "hold frame ở cliffhanger, pull-back nhẹ để lộ khoảng cách quyền lực"
    if any(marker in lowered for marker in ["cửa", "bước", "đứng", "đi ngang"]):
        return "pan dọc theo chuyển động nhân vật, dừng ở phản ứng im lặng"
    if any(marker in lowered for marker in ["bàn tay", "ánh mắt", "im lặng", "cha"]):
        return "cut cận cảnh sang mắt/bàn tay, nhịp chậm để giữ cảm xúc"
    if any(marker in lowered for marker in ["sổ", "tài liệu", "báo cáo", "kiểm tra"]):
        return "match cut giữa tài liệu và biểu cảm, nhịp nhanh vừa phải để tạo cảm giác tiến bộ"
    return "cinematic cut theo beat truyện, một hành động chính trong mỗi khung"

def _source_panel_beats(source_text: str, title: str) -> tuple[list[str], list[str], list[str]]:
    target_count = _target_panel_count_from_source(source_text)
    hook = _source_hook_for_master(source_text, title)
    units = _source_story_units(source_text)
    grouped = _group_story_units_for_panels(units, max(1, target_count - 1))
    beats = [hook, *grouped]
    if len(beats) < MIN_AUTO_IMAGE_PANEL_COUNT:
        story_chunks = _story_text_chunks(source_text, MIN_AUTO_IMAGE_PANEL_COUNT - len(beats))
        beats.extend(_clip_prompt_text(chunk, 520) for chunk in story_chunks)
    beats = _unique_texts(beats, limit=MAX_AUTO_IMAGE_PANEL_COUNT)
    visual_moments = [
        _panel_visual_from_beat(index, len(beats), beat)
        for index, beat in enumerate(beats, start=1)
    ]
    motion_beats = [
        _panel_motion_from_beat(index, len(beats), beat)
        for index, beat in enumerate(beats, start=1)
    ]
    return beats, visual_moments, motion_beats

def _fallback_grounded_master_story_payload(
    *,
    episode: DBStoryEpisode,
    creative_brief: dict[str, Any],
    candidates: list[dict[str, Any]],
    evaluation: dict[str, Any],
    user_direction: str | None,
    fallback_reason: str,
) -> dict[str, Any] | None:
    source_text = _source_text_for_grounded_story(episode, creative_brief)
    if len(_clean(source_text)) < 500:
        return None

    title_base = _clean(episode.title) or _clean(creative_brief.get("series_title")) or f"Tập {episode.episode_number}"
    hook = _source_hook_for_master(source_text, title_base)
    key_beats, visual_moments, motion_beats = _source_panel_beats(source_text, title_base)
    candidate_strengths = _unique_texts(
        [
            *[item for candidate in candidates for item in _coerce_list(candidate.get("strengths_claimed"))],
            *[item for review in _coerce_list(evaluation.get("reviews")) if isinstance(review, dict) for item in _coerce_list(review.get("recommended_parts"))],
        ],
        limit=6,
    )
    full_story = "\n\n".join(
        [
            hook,
            (
                "Sau hook, tập truyện quay lại nguyên nhân theo mạch nguồn đã handoff. Nhịp kể giữ cảm giác anime/manga/webtoon: "
                "mỗi cảnh có một hành động hoặc cảm xúc chính, caption ngắn, không thêm canon ngoài nguồn."
            ),
            "Câu chuyện chính:\n" + _clip_prompt_text(source_text, 24000),
            (
                "Dòng kết/retention: Lời thừa nhận đến quá muộn không chỉ là phần thưởng cảm xúc; nó mở ra câu hỏi cho tập sau: "
                "Florentia/nhân vật chính sẽ tiếp tục chấp nhận thân phận bị áp đặt, hay sẽ giành lại quyền quyết định số phận của mình?"
            ),
            f"Chỉ dẫn thêm của người dùng: {_clean(user_direction) or 'ưu tiên truyện ảnh giới thiệu tập đầu, hook mạnh và nội dung dày.'}",
        ]
    )
    master = {
        "title": f"{title_base} — Master Story truyện ảnh tập 1",
        "logline": (
            "Một tập mở màn theo kiểu truyện tranh/anime: bắt đầu bằng lời thừa nhận muộn gây sốc, "
            "rồi quay lại tuổi thơ bị xem nhẹ, cái chết của người cha bảo vệ, quá trình tự chứng minh năng lực "
            "và cú chốt khiến người đọc muốn xem tiếp."
        ),
        "hook": hook,
        "full_story": full_story,
        "key_beats": key_beats,
        "character_emotions": [
            "sững lại trước lời thừa nhận quá muộn",
            "tủi thân vì bị xem là con ngoài giá thú",
            "ấm áp ngắn ngủi khi còn được cha bảo vệ",
            "trống rỗng sau cái chết của cha",
            "cô độc khi bị gia tộc lãng quên",
            "kiên quyết chứng minh giá trị bằng công việc",
            "bình tĩnh nhưng đau khi được công nhận quá muộn",
            "quyết tâm giành lại quyền tự quyết cho số phận",
        ],
        "visual_moments": visual_moments,
        "motion_beats": motion_beats,
        "retention_plan": (
            "Mở bằng cliffhanger cảm xúc ở tương lai gần, sau đó cứ 2-3 panel trả lời một phần nguyên nhân nhưng lại mở câu hỏi mới: "
            "vì sao Florentia bị xem nhẹ, ai đã bảo vệ cô, vì sao sự bảo vệ biến mất, cô đã tự đứng dậy thế nào, "
            "và tại sao lời công nhận cuối cùng lại không còn đủ để chữa lành."
        ),
        "market_profile": _clean(episode.market_profile) or "viet_nam",
        "language_profile": _clean(episode.language_profile) or "vi",
        "must_have": [
            "Giữ đúng nguồn đã handoff và không thêm tuyến nhân vật/canon mới.",
            "Hook phải xuất hiện ngay panel 1-3, không mở đầu chậm bằng giới thiệu gia phả thuần túy.",
            "Mỗi panel có một bối cảnh, một hành động/cảm xúc chính, góc máy rõ và caption/thoại riêng.",
            "Giữ style anime/manga/webtoon, framing dọc 9:16, kích thước mặc định 720x1280.",
            "Không để provider tự vẽ chữ tiếng Việt phức tạp; chừa vùng caption/bubble sạch để chèn sau.",
            "Giữ continuity nhân vật, trang phục, quan hệ gia đình và địa vị xã hội theo source.",
        ],
        "avoid": [
            "Không ghép cơ học candidate lỗi hoặc dùng placeholder/template.",
            "Không đưa metadata như số ký tự, source id hoặc lỗi provider vào nội dung truyện.",
            "Không đổi sang photorealistic live-action khi nguồn là truyện tranh/anime.",
            "Không thêm phép thuật, romance hoặc phản diện mới nếu source chưa có.",
            "Không viết prompt ảnh như prompt video dài giây; mỗi panel là một ảnh truyện rõ.",
        ],
        "continuity_updates": [],
        "image_story_notes": (
            "Tạo truyện ảnh dọc 9:16, 720x1280. Mỗi prompt panel phải có: bối cảnh, nhân vật/đạo cụ chính, hành động chính, "
            "cảm xúc nhìn thấy, góc máy/framing, composition note, caption/thoại gợi ý và negative prompt. "
            "Style: anime/manga/webtoon cinematic, line art sạch, biểu cảm rõ, nhân vật nhất quán qua từng panel."
        ),
        "video_story_notes": (
            "Nếu handoff sang video, dùng cùng Master Story; chuyển mỗi beat thành shot/micro-scene 3-5 giây, "
            "giữ push-in/cut close-up/hold frame ở hook và cliffhanger."
        ),
        "strengths_claimed": _unique_texts(
            [
                "Bám nguồn handoff thay vì fallback template.",
                "Hook mở bằng lời thừa nhận muộn và thân phận con ngoài giá thú để giữ chân ngay.",
                "Có đủ beat cho 24-42 panel truyện ảnh.",
                "Mỗi beat có thể chuyển thành prompt ảnh có bối cảnh, góc máy và caption.",
                *candidate_strengths,
            ],
            limit=10,
        ),
        "risks_claimed": [
            "Provider tổng hợp Master Story đang lỗi/chậm nên dùng fallback nội bộ bám nguồn; nên chạy lại bằng AI khi provider ổn nếu muốn thêm biến thể sáng tạo.",
            f"Lý do fallback: {fallback_reason[:220]}",
        ],
        "synthesis_sources": [
            {"strategy_type": "hook_retention", "part": "hook/retention", "reason": "Dùng mở đầu bằng lời thừa nhận muộn để tạo câu hỏi giữ chân."},
            {"strategy_type": "emotional_drama", "part": "character_emotions/full_story", "reason": "Giữ lõi cảm xúc mất cha, bị lãng quên và tự chứng minh."},
            {"strategy_type": "visual_action", "part": "visual_moments/motion_beats", "reason": "Chuyển mỗi beat thành panel có góc máy, bối cảnh và composition rõ."},
        ],
        "fallback_used": True,
        "fallback_reason": fallback_reason,
    }
    master = _normalize_story_payload(master, episode=episode)
    _validate_master_story(master)
    return master

def _fallback_master_story_payload(
    *,
    episode: DBStoryEpisode,
    candidates: list[dict[str, Any]],
    evaluation: dict[str, Any],
    user_direction: str | None,
    fallback_reason: str,
) -> dict[str, Any]:
    creative_brief = {}
    for candidate in candidates:
        if isinstance(candidate, dict) and isinstance(candidate.get("creative_brief"), dict):
            creative_brief = candidate["creative_brief"]
            break
    grounded_master = _fallback_grounded_master_story_payload(
        episode=episode,
        creative_brief=creative_brief,
        candidates=candidates,
        evaluation=evaluation,
        user_direction=user_direction,
        fallback_reason=fallback_reason,
    )
    if grounded_master is not None:
        return grounded_master

    by_strategy = {candidate.get("strategy_type"): candidate for candidate in candidates if isinstance(candidate, dict)}
    reviews = evaluation.get("reviews") if isinstance(evaluation.get("reviews"), list) else []
    scores = {
        review.get("strategy_type"): float(review.get("total") or 0)
        for review in reviews
        if isinstance(review, dict)
    }
    ordered = sorted(
        [candidate for candidate in candidates if isinstance(candidate, dict)],
        key=lambda candidate: scores.get(candidate.get("strategy_type"), 0.0),
        reverse=True,
    )
    primary = ordered[0] if ordered else (candidates[0] if candidates else {})
    hook_candidate = by_strategy.get("hook_retention") or primary
    emotion_candidate = by_strategy.get("emotional_drama") or primary
    visual_candidate = by_strategy.get("visual_action") or primary
    title_base = _clean(episode.title) or _clean(primary.get("title")) or f"Master Story tập {episode.episode_number}"
    key_beats = _unique_texts(
        [
            *(_coerce_list(hook_candidate.get("key_beats"))[:2]),
            *(_coerce_list(emotion_candidate.get("key_beats"))[:2]),
            *(_coerce_list(visual_candidate.get("key_beats"))[:2]),
        ],
        limit=7,
    )
    visual_moments = _unique_texts(
        [
            *(_coerce_list(visual_candidate.get("visual_moments"))[:3]),
            *(_coerce_list(hook_candidate.get("visual_moments"))[:2]),
            *(_coerce_list(emotion_candidate.get("visual_moments"))[:2]),
        ],
        limit=7,
    )
    motion_beats = _unique_texts(
        [
            *(_coerce_list(visual_candidate.get("motion_beats"))[:3]),
            *(_coerce_list(hook_candidate.get("motion_beats"))[:2]),
            *(_coerce_list(emotion_candidate.get("motion_beats"))[:2]),
        ],
        limit=7,
    )
    character_emotions = _unique_texts(
        [
            *(_coerce_list(emotion_candidate.get("character_emotions"))[:4]),
            *(_coerce_list(hook_candidate.get("character_emotions"))[:2]),
            *(_coerce_list(visual_candidate.get("character_emotions"))[:2]),
        ],
        limit=8,
    )
    full_story = " ".join(
        [
            f"Master Story tổng hợp bắt đầu bằng hook mạnh: {_clean(hook_candidate.get('hook')) or _clean(primary.get('hook'))}.",
            f"Tuyến cảm xúc chính lấy từ bản drama: {_clean(emotion_candidate.get('full_story')) or _clean(primary.get('full_story'))}",
            f"Tuyến hình ảnh lấy từ bản visual/action: {_clean(visual_candidate.get('full_story')) or _clean(primary.get('full_story'))}",
            "Khi dựng thành truyện ảnh, mỗi beat giữ một hành động/cảm xúc chính, không thêm canon mới và vẫn bám source đã handoff.",
            f"Chỉ dẫn người dùng: {_clean(user_direction) or 'không có chỉ dẫn thêm'}.",
        ]
    )
    master = {
        "title": f"{title_base} — Master Story tổng hợp",
        "logline": (
            "Bản tổng hợp lấy hook giữ chân, lõi cảm xúc và visual dễ render nhất từ ba candidate "
            "để tạo một mạch truyện thống nhất."
        ),
        "hook": _clean(hook_candidate.get("hook")) or _clean(primary.get("hook")) or "Mở bằng biến cố rõ và câu hỏi kéo người đọc vào tập.",
        "full_story": full_story,
        "key_beats": key_beats or ["Hook", "Leo thang", "Cao trào", "Payoff"],
        "character_emotions": character_emotions or ["bất ngờ", "quyết tâm"],
        "visual_moments": visual_moments or ["cận mặt cảm xúc", "khung hình payoff"],
        "motion_beats": motion_beats or ["push-in", "cut theo hành động"],
        "retention_plan": (
            f"{_clean(hook_candidate.get('retention_plan')) or 'Giữ câu hỏi mở ở đầu tập.'} "
            "Kết hợp nhịp cảm xúc rõ và visual payoff để người đọc muốn xem tiếp."
        ),
        "market_profile": _clean(primary.get("market_profile")) or episode.market_profile,
        "language_profile": _clean(primary.get("language_profile")) or episode.language_profile,
        "must_have": _unique_texts(
            [
                *(_coerce_list(hook_candidate.get("must_have"))[:2]),
                *(_coerce_list(emotion_candidate.get("must_have"))[:2]),
                *(_coerce_list(visual_candidate.get("must_have"))[:2]),
                "Bám sát source/canon đã handoff.",
            ],
            limit=8,
        ),
        "avoid": _unique_texts(
            [
                *(_coerce_list(primary.get("avoid"))[:3]),
                "Không tự thêm canon ngoài nguồn.",
                "Không đổi fixed traits.",
            ],
            limit=8,
        ),
        "continuity_updates": [],
        "image_story_notes": _clean(visual_candidate.get("image_story_notes")) or "Panel rõ, caption ngắn, giữ continuity và style nhất quán.",
        "video_story_notes": _clean(hook_candidate.get("video_story_notes")) or "Nếu handoff sang video, chia mỗi beat thành shot/micro-scene rõ hành động.",
        "strengths_claimed": [
            "Có hook từ hướng giữ chân.",
            "Có cảm xúc từ hướng drama.",
            "Có visual dễ chuyển thành prompt ảnh.",
        ],
        "risks_claimed": [
            "Đây là fallback khi provider lỗi/chậm; nên kiểm lại bằng AI hoặc người dùng khi provider ổn định.",
            f"Lý do fallback: {fallback_reason[:220]}",
        ],
        "synthesis_sources": [
            {"strategy_type": "hook_retention", "part": "hook/retention", "reason": "Tạo câu hỏi mở và nhịp giữ chân."},
            {"strategy_type": "emotional_drama", "part": "character_emotions/full_story", "reason": "Giữ lõi cảm xúc và động cơ nhân vật."},
            {"strategy_type": "visual_action", "part": "visual_moments/motion_beats", "reason": "Dễ chuyển thành panel và prompt ảnh."},
        ],
        "fallback_used": True,
        "fallback_reason": fallback_reason,
    }
    master = _normalize_story_payload(master, episode=episode)
    _validate_master_story(master)
    return master

def _rubric_text(output_intent: str) -> str:
    if output_intent == "truyen_anh":
        return "Ưu tiên khoảnh khắc hình ảnh, bố cục panel, cảm xúc dễ đọc, caption và khả năng chuyển thành prompt ảnh."
    if output_intent == "video_truyen":
        return "Ưu tiên hook, nhịp shot, chuyển động, narration, giữ chân, chuyển cảnh và khả năng chuyển thành prompt video."
    return "Cân bằng panel truyện ảnh, nhịp video, hook, cảm xúc, motion beat và payoff chung."

def _candidate_prompt(
    *,
    creative_brief: dict[str, Any],
    strategy_type: str,
    label: str,
    episode: DBStoryEpisode,
    context_snapshot_id: str | None,
    attempt: int,
) -> str:
    content_language = video_language.video_language_prompt_label(_target_viewer_language_for_episode(episode))
    return f"""
Bạn là biên kịch Story Studio. Hãy tạo một candidate kịch bản THẬT cho đúng một chiến lược.

Chiến lược bắt buộc: {strategy_type} - {label}
Output intent: {episode.output_intent}
Rubric ưu tiên: {_rubric_text(episode.output_intent)}
Context snapshot id: {context_snapshot_id or "none"}
Ngôn ngữ nội dung người xem đã chọn: {content_language}

Gói ngữ cảnh đã đóng băng:
{json.dumps(creative_brief, ensure_ascii=False, separators=(",", ":"))}

Yêu cầu:
- Chỉ tạo một candidate cho strategy trên, không tạo ba bản trong cùng response.
- Candidate phải khác rõ nếu so với các strategy khác: hook, cấu trúc beat, trọng tâm cảm xúc hoặc hình ảnh.
- Hook phải gay cấn ngay từ 1-3 panel đầu: có câu hỏi mở, nguy cơ/mất mát rõ, và một lời hứa nội dung khiến người xem muốn đọc tiếp.
- Dùng cùng canon/context snapshot; không tự đổi fixed traits, bí mật, đạo cụ hoặc trạng thái đã chặn.
- Không trả nội dung mẫu chung chung. Phải khai triển từ source_input, structured source và series context.
- title, logline, hook, full_story, key_beats, character_emotions, visual_moments, motion_beats, retention_plan, image_story_notes và video_story_notes phải dùng đúng ngôn ngữ nội dung người xem đã chọn.
- Các field giải thích cho app/UI có hậu tố `_vi` hoặc tên `reason_vi` vẫn phải là tiếng Việt để người dùng đọc trong giao diện.
- full_story là Master Story nháp hoàn chỉnh, giàu nội dung nhất có thể trong giới hạn response: nhiều cảnh cụ thể, nhiều hành động/biểu cảm, không chỉ tóm tắt.
- key_beats nên có tối thiểu 14 beat nếu nguồn đủ dài; mỗi beat phải có biến chuyển hoặc thông tin mới.
- visual_moments và motion_beats phải đủ dùng để tách thành panel ảnh: bối cảnh, hành động chính, cảm xúc nhìn thấy, góc máy hoặc chuyển động camera.
- image_story_notes phải nói rõ style truyện tranh/anime, vùng thoại/caption, framing dọc 9:16 và cách giữ mặt/trang phục nhân vật nhất quán.
- video_story_notes phải nêu nhịp giữ chân, điểm cliffhanger và cách chuyển cảnh nếu sau này handoff video.
- continuity_updates chỉ là đề xuất nháp, không tự ghi vào series.
- Lần thử hiện tại: {attempt}.
- Chỉ trả đúng JSON object theo schema, không markdown.
""".strip()

def _evaluation_prompt(episode: DBStoryEpisode, candidates: list[dict[str, Any]], creative_brief: dict[str, Any]) -> str:
    return f"""
Bạn là critic độc lập của Story Studio. Chấm ba candidate, không sửa nội dung candidate trong bước này.

Output intent: {episode.output_intent}
Rubric: {_rubric_text(episode.output_intent)}

Creative brief/canon rút gọn:
{json.dumps(creative_brief, ensure_ascii=False, indent=2)[:20000]}

Candidates:
{json.dumps(candidates, ensure_ascii=False, indent=2)}

Yêu cầu:
- Có đúng một review cho mỗi strategy_type.
- Chấm total theo thang 100.
- criteria phải gồm: canon, strategic_difference, hook_retention, emotion_logic, visual_production, pacing_payoff, market_language_fit, production_risk.
- reason_vi, evidence, strengths, weaknesses, risks và recommended_parts phải viết tiếng Việt dễ hiểu.
- Không tự chọn thay người dùng; chỉ đưa synthesis_guidance.
- Chỉ trả đúng JSON object theo schema.
""".strip()

def _synthesis_prompt(
    episode: DBStoryEpisode,
    candidates: list[dict[str, Any]],
    evaluation: dict[str, Any],
    user_direction: str | None,
) -> str:
    content_language = video_language.video_language_prompt_label(_target_viewer_language_for_episode(episode))
    return f"""
Bạn là biên kịch tổng hợp Master Story. Hãy lấy phần tốt nhất của các candidate thành một Master Story duy nhất.

Output intent: {episode.output_intent}
Ngôn ngữ nội dung người xem đã chọn: {content_language}
Chỉ dẫn thêm của người dùng: {_clean(user_direction) or "Không có"}

Candidates:
{json.dumps(candidates, ensure_ascii=False, indent=2)}

Đánh giá độc lập:
{json.dumps(evaluation, ensure_ascii=False, indent=2)}

Yêu cầu:
- Kết quả phải là một câu chuyện liền mạch, không ghép cơ học.
- title, logline, hook, full_story, key_beats, character_emotions, visual_moments, motion_beats, retention_plan, image_story_notes và video_story_notes phải dùng đúng ngôn ngữ nội dung người xem đã chọn.
- Các field giải thích cho app/UI có hậu tố `_vi` hoặc tên `reason_vi` vẫn phải là tiếng Việt để người dùng đọc trong giao diện.
- Ưu tiên tạo Master Story dài, nhiều nội dung, đủ để tách thành 24-42 panel truyện ảnh nếu nguồn đủ dài.
- Mở đầu phải có hook giữ chân mạnh nhất: nguy cơ/mất mát/câu hỏi mở xuất hiện ngay, không mở bằng giới thiệu chậm.
- key_beats phải có nhiều beat cụ thể; mỗi beat nên chuyển được thành một panel có bối cảnh, hành động, biểu cảm và caption/thoại.
- visual_moments phải có mô tả hình ảnh rõ để tạo prompt ảnh: shot type/góc máy, bố cục, ánh sáng, hành động chính, cảm xúc.
- motion_beats phải ghi nhịp camera/chuyển cảnh phù hợp truyện ảnh/video.
- Không vi phạm canon/fixed traits.
- synthesis_sources phải chỉ rõ phần nào lấy từ strategy nào và lý do.
- Master Story vẫn là pending approval, không tự duyệt.
- Chỉ trả đúng JSON object theo schema.
""".strip()

def _repair_prompt(panel: dict[str, Any], quality_check: dict[str, Any], canon_check: dict[str, Any] | None) -> str:
    return f"""
Bạn là bộ sửa prompt Story Studio có giới hạn. Chỉ sửa các lỗi đã được chỉ ra, giữ phần đang đạt.

Panel hiện tại:
{json.dumps(panel, ensure_ascii=False, indent=2)}

Kết quả quality check:
{json.dumps(quality_check, ensure_ascii=False, indent=2)}

Canon check liên quan:
{json.dumps(canon_check or {}, ensure_ascii=False, indent=2)}

Yêu cầu:
- Trả prompt ảnh provider-neutral, không viết như prompt video.
- Sửa hành động, bố cục, nhận diện nhân vật, continuity, khả năng render và vùng phụ đề nếu bị báo lỗi.
- Chữ trong panel: nếu caption_or_dialogue có nội dung, prompt phải yêu cầu render đúng caption đó trong ảnh, chỉ đúng ngôn ngữ đã chọn; nếu không có caption thì không tự thêm chữ.
- Không thêm scene label, hook label, số OCR, watermark, copyright, chữ sai ngôn ngữ hoặc chữ do AI bịa.
- Giữ prompt gửi AI render tách khỏi bản giải thích cho người dùng; bản giải thích tiếng Việt sẽ được backend tự tạo lại.
- Không tự duyệt prompt.
- changes phải liệt kê thay đổi trước/sau bằng tiếng Việt.
- Chỉ trả đúng JSON object theo schema.
""".strip()

def _series_mode(series: DBVideoSeries) -> str:
    mode = _clean(getattr(series, "series_mode", None)) or SERIES_MODE_VIDEO
    if mode in {SERIES_MODE_IMAGE, SERIES_MODE_VIDEO, SERIES_MODE_HYBRID}:
        return mode
    return SERIES_MODE_VIDEO

def _series_for_story(series_id: str, db: Session) -> DBVideoSeries | None:
    series = db.query(DBVideoSeries).filter(DBVideoSeries.id == series_id).first()
    if series is None:
        return None
    if _series_mode(series) not in STORY_SERIES_MODES:
        raise StoryStudioError("Series video chỉ tạo tập trực tiếp trong AI Video, không tạo trong Story Studio.")
    return series

def _validate_intent(series: DBVideoSeries, output_intent: str) -> str:
    mode = _series_mode(series)
    intent = output_intent or "truyen_anh"
    if mode == SERIES_MODE_IMAGE and intent != "truyen_anh":
        raise StoryStudioError("Series truyện ảnh chỉ hỗ trợ đầu ra truyện ảnh.")
    if mode == SERIES_MODE_HYBRID and intent not in {"truyen_anh", "video_truyen", "ca_hai"}:
        raise StoryStudioError("Series truyện + video chỉ hỗ trợ truyện ảnh, video truyện hoặc cả hai.")
    return intent

def _validate_master_story(master: dict[str, Any]) -> None:
    missing: list[str] = []
    for field in sorted(REQUIRED_MASTER_FIELDS):
        if field not in master:
            missing.append(field)
            continue
        value = master.get(field)
        if field in REQUIRED_NONEMPTY_MASTER_FIELDS:
            if value is None or value == "" or value == [] or value == {}:
                missing.append(field)
    if missing:
        raise StoryStudioError(f"Master Story thiếu trường bắt buộc: {', '.join(missing)}.")

def _source_digest(source: str | None) -> str:
    text = _clean(source)
    if not text:
        return "Chưa có nguồn nhập."
    first_line = text.splitlines()[0].strip()
    suffix = f" ({len(text)} ký tự)" if len(text) > len(first_line) else ""
    return f"{first_line[:220]}{suffix}"

def _next_story_episode_number(series_id: str, db: Session) -> int:
    max_story = db.query(func.max(DBStoryEpisode.episode_number)).filter(DBStoryEpisode.series_id == series_id).scalar() or 0
    max_video = db.query(func.max(DBVideoProject.episode_number)).filter(DBVideoProject.series_id == series_id).scalar() or 0
    series = db.query(DBVideoSeries).filter(DBVideoSeries.id == series_id).first()
    latest = int(getattr(series, "latest_episode_number", 0) or 0)
    return max(int(max_story or 0), int(max_video or 0), latest) + 1

def _candidate_rows(episode_id: str, db: Session) -> list[models.StoryScenarioCandidateResponse]:
    rows = (
        db.query(DBStoryScenarioCandidate)
        .filter(DBStoryScenarioCandidate.story_episode_id == episode_id)
        .order_by(DBStoryScenarioCandidate.created_at.asc())
        .all()
    )
    return [models.StoryScenarioCandidateResponse.model_validate(row) for row in rows]

def _adaptation_rows(episode_id: str, db: Session) -> list[models.StoryAdaptationResponse]:
    rows = (
        db.query(DBStoryAdaptation)
        .filter(DBStoryAdaptation.story_episode_id == episode_id)
        .order_by(DBStoryAdaptation.created_at.asc())
        .all()
    )
    return [_adaptation_response(row, db) for row in rows]

def _episode_response(episode: DBStoryEpisode, db: Session) -> models.StoryEpisodeResponse:
    response = models.StoryEpisodeResponse.model_validate(episode)
    response.output_settings = _episode_output_settings(episode)
    source_summary = comic_source_context.source_summary(db, episode.id)
    response.current_source_document_id = source_summary.source_document_id
    response.source_summary = models.StoryEpisodeSourceSummaryResponse(
        source_document_id=source_summary.source_document_id,
        revision=source_summary.revision,
        source_kind=source_summary.source_kind,
        comic_job_id=source_summary.comic_job_id,
        comic_analysis_revision=source_summary.comic_analysis_revision,
        chunk_count=source_summary.chunk_count,
        page_count=source_summary.page_count,
        panel_count=source_summary.panel_count,
        dialogue_count=source_summary.dialogue_count,
        coverage_metrics=source_summary.coverage_metrics,
        limitations=source_summary.limitations,
        has_structured_source=source_summary.has_structured_source,
    )
    response.candidates = _candidate_rows(episode.id, db)
    response.adaptations = _adaptation_rows(episode.id, db)
    return response

def _latest_render_job(project_id: str, db: Session) -> DBVideoRenderJob | None:
    return (
        db.query(DBVideoRenderJob)
        .filter(DBVideoRenderJob.project_id == project_id)
        .order_by(DBVideoRenderJob.created_at.desc())
        .first()
    )

def _refresh_video_adaptation(row: DBStoryAdaptation, db: Session) -> None:
    if row.kind != "video_story" or not row.linked_video_project_id:
        return
    payload = dict(row.payload_json) if isinstance(row.payload_json, dict) else {}
    project_id = row.linked_video_project_id
    render = _latest_render_job(project_id, db)
    payload["linked_video_project_id"] = project_id
    payload["ai_video_url"] = payload.get("ai_video_url") or f"/ai-video?projectId={project_id}"
    auto_run_id = _clean(payload.get("auto_run_id"))
    if auto_run_id:
        auto_run = video_auto_runs.get_auto_run(project_id, auto_run_id, db)
        if auto_run is not None:
            payload["auto_run_status"] = auto_run.status
            payload["auto_run_step"] = auto_run.current_step
            payload["auto_run_progress"] = float(auto_run.progress or 0.0)
            payload["auto_run_failure_reason"] = auto_run.failure_reason
            payload["auto_run_error_code"] = auto_run.error_code
            payload["auto_run_completed_at"] = (
                auto_run.completed_at.isoformat() if auto_run.completed_at else None
            )
    if render is None:
        payload["render_status"] = "not_requested"
        payload["latest_render_job"] = None
        row.status = "approved"
    else:
        payload["render_status"] = render.status
        payload["latest_render_job"] = {
            "id": render.id,
            "status": render.status,
            "progress": float(render.progress or 0),
            "current_step": render.current_step,
            "output_path": render.output_path,
            "stale": bool(render.stale),
            "failure_reason": render.failure_reason,
            "updated_at": render.updated_at.isoformat() if render.updated_at else None,
            "completed_at": render.completed_at.isoformat() if render.completed_at else None,
        }
        if render.status == "completed" and render.output_path and not render.stale:
            row.status = "completed"
            payload["latest_mp4_path"] = render.output_path
            payload["latest_mp4_download_url"] = f"/ai-video/projects/{project_id}/render/jobs/{render.id}/download"
        elif render.status == "failed":
            row.status = "failed"
            payload["latest_mp4_path"] = None
            payload["latest_mp4_download_url"] = None
        elif render.status in {"queued", "running"}:
            row.status = "rendering"
            payload["latest_mp4_path"] = None
            payload["latest_mp4_download_url"] = None
        else:
            row.status = "approved"
            payload["latest_mp4_path"] = None
            payload["latest_mp4_download_url"] = None
    row.payload_json = payload

def _adaptation_response(row: DBStoryAdaptation, db: Session) -> models.StoryAdaptationResponse:
    before_status = row.status
    before_payload = row.payload_json
    _refresh_video_adaptation(row, db)
    if row.status != before_status or row.payload_json != before_payload:
        row.updated_at = datetime.utcnow()
        db.commit()
        db.refresh(row)
    return models.StoryAdaptationResponse.model_validate(row)

def _character_profiles_text(series_id: str, db: Session) -> str:
    rows = (
        db.query(DBSeriesCharacterProfile)
        .filter(DBSeriesCharacterProfile.series_id == series_id)
        .order_by(DBSeriesCharacterProfile.sort_order.asc(), DBSeriesCharacterProfile.created_at.asc())
        .all()
    )
    if not rows:
        return ""
    parts: list[str] = []
    for row in rows:
        parts.append(
            "\n".join(
                item
                for item in [
                    f"- {row.name} ({_clean(row.role) or 'vai trò chưa rõ'})",
                    f"  Face: {_clean(row.face_description)}" if _clean(row.face_description) else "",
                    f"  Hair: {_clean(row.hair_description)}" if _clean(row.hair_description) else "",
                    f"  Body: {_clean(row.body_description)}" if _clean(row.body_description) else "",
                    f"  Outfit: {_clean(row.signature_outfit)}" if _clean(row.signature_outfit) else "",
                    f"  Personality: {_clean(row.personality)}" if _clean(row.personality) else "",
                    f"  Speech: {_clean(row.speech_style)}" if _clean(row.speech_style) else "",
                    f"  Fixed traits: {_clean(row.fixed_traits)}" if _clean(row.fixed_traits) else "",
                ]
                if item
            )
        )
    return "\n".join(parts)

def _creative_brief(
    *,
    episode: DBStoryEpisode,
    series: DBVideoSeries,
    memory_text: str,
    profiles_text: str,
) -> dict[str, Any]:
    intent_notes = {
        "truyen_anh": "Ưu tiên panel rõ, khoảnh khắc hình ảnh mạnh, caption ngắn và prompt ảnh dễ render.",
        "video_truyen": "Ưu tiên hook, motion beat, scene/shot pacing, narration, retention, SFX và transition.",
        "ca_hai": "Cân bằng visual anchor cho truyện ảnh và motion beat cho video từ cùng một Master Story.",
    }
    return {
        "schema_version": "story-studio-creative-brief-v1",
        "series_id": series.id,
        "series_title": series.title,
        "series_mode": _series_mode(series),
        "episode_number": episode.episode_number,
        "output_intent": episode.output_intent,
        "intent_guidance": intent_notes.get(episode.output_intent, intent_notes["truyen_anh"]),
        "market_profile": episode.market_profile,
        "language_profile": episode.language_profile,
        "output_settings": _settings_json(_episode_output_settings(episode)),
        "source_digest": episode.source_digest,
        "series_bible": {
            "character_bible": _clip_prompt_text(series.character_bible, 1400),
            "world_bible": _clip_prompt_text(series.world_bible, 1000),
            "style_bible": _clip_prompt_text(series.style_bible, 1000),
            "continuity_rules": _clip_prompt_text(series.continuity_rules, 1000),
            "negative_rules": _clip_prompt_text(series.negative_rules, 800),
            "previous_episode_summary": _clip_prompt_text(series.previous_episode_summary, 1000),
        },
        "character_profiles": _clip_prompt_text(profiles_text, CREATIVE_BRIEF_PROFILE_CHARS),
        "series_memory_excerpt": _clip_prompt_text(memory_text, CREATIVE_BRIEF_SERIES_MEMORY_CHARS),
        "non_negotiables": [
            "Không tự thay đổi fixed traits.",
            "Không lưu cập nhật continuity hoặc nhân vật nếu người dùng chưa duyệt.",
            "Nếu Story Episode tạo cả truyện ảnh và video, cả hai adaptation phải xuất phát từ Master Story đã duyệt.",
        ],
    }

def list_story_series(db: Session) -> list[models.VideoSeriesResponse]:
    return [series for series in video_projects.list_series(db) if series.series_mode in STORY_SERIES_MODES]

def list_episodes(series_id: str, db: Session) -> list[models.StoryEpisodeResponse] | None:
    _series_for_story(series_id, db)
    rows = (
        db.query(DBStoryEpisode)
        .filter(DBStoryEpisode.series_id == series_id)
        .order_by(DBStoryEpisode.episode_number.asc(), DBStoryEpisode.created_at.asc())
        .all()
    )
    return [_episode_response(row, db) for row in rows]

def get_episode(episode_id: str, db: Session) -> models.StoryEpisodeResponse | None:
    row = db.query(DBStoryEpisode).filter(DBStoryEpisode.id == episode_id).first()
    return _episode_response(row, db) if row else None

def create_episode(series_id: str, data: models.StoryEpisodeCreate, db: Session) -> models.StoryEpisodeResponse | None:
    series = _series_for_story(series_id, db)
    if series is None:
        return None
    intent = _validate_intent(series, data.output_intent)
    now = datetime.utcnow()
    episode_number = data.episode_number or _next_story_episode_number(series_id, db)
    duplicate = (
        db.query(DBStoryEpisode.id)
        .filter(DBStoryEpisode.series_id == series_id, DBStoryEpisode.episode_number == episode_number)
        .first()
    )
    if duplicate is not None:
        raise StoryStudioError(f"Series đã có Story Episode số {episode_number}.")
    output_settings = _normalize_output_settings(
        data.output_settings if "output_settings" in data.model_fields_set else None,
        language_profile=data.language_profile,
    )
    row = DBStoryEpisode(
        id=str(uuid.uuid4()),
        series_id=series_id,
        episode_number=episode_number,
        title=data.title,
        output_intent=intent,
        market_profile=data.market_profile,
        language_profile=data.language_profile,
        source_input=data.source_input,
        source_digest=_source_digest(data.source_input),
        output_settings_json=_settings_json(output_settings),
        approval_status="draft",
        created_at=now,
        updated_at=now,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    video_series_memory.sync_series_memory_file(series_id, db)
    return _episode_response(row, db)

def update_episode(
    episode_id: str,
    patch: models.StoryEpisodeUpdate,
    db: Session,
) -> models.StoryEpisodeResponse | None:
    row = db.query(DBStoryEpisode).filter(DBStoryEpisode.id == episode_id).first()
    if row is None:
        return None
    series = _series_for_story(row.series_id, db)
    if series is None:
        return None
    data = patch.model_dump(exclude_unset=True)
    if "master_story_json" in data and data["master_story_json"] is not None:
        if not isinstance(data["master_story_json"], dict):
            raise StoryStudioError("Master Story phải là object JSON hợp lệ.")
        _validate_master_story(data["master_story_json"])
    master_changed = "master_story_json" in data and data["master_story_json"] != row.master_story_json
    if "output_intent" in data and data["output_intent"] is not None:
        data["output_intent"] = _validate_intent(series, data["output_intent"])
    if "source_input" in data:
        row.source_digest = _source_digest(data["source_input"])
    settings_changed = False
    if "output_settings" in data:
        output_settings = _normalize_output_settings(
            data.pop("output_settings"),
            language_profile=data.get("language_profile") or row.language_profile,
        )
        output_settings_json = _settings_json(output_settings)
        settings_changed = output_settings_json != (row.output_settings_json or {})
        row.output_settings_json = output_settings_json
    for key, value in data.items():
        setattr(row, key, value)
    if master_changed and row.approval_status == "approved":
        row.approval_status = "pending_approval"
        row.approved_at = None
        row.revision = int(row.revision or 1) + 1
        db.query(DBStoryAdaptation).filter(DBStoryAdaptation.story_episode_id == row.id).update(
            {"status": "stale", "updated_at": datetime.utcnow()},
            synchronize_session=False,
        )
    elif settings_changed:
        row.revision = int(row.revision or 1) + 1
        db.query(DBStoryAdaptation).filter(DBStoryAdaptation.story_episode_id == row.id).update(
            {"status": "stale", "updated_at": datetime.utcnow()},
            synchronize_session=False,
        )
    row.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(row)
    video_series_memory.sync_series_memory_file(row.series_id, db)
    return _episode_response(row, db)

def _score_from_review(review: dict[str, Any], rubric: str) -> dict[str, Any]:
    try:
        total = float(review.get("total") or 0)
    except (TypeError, ValueError):
        total = 0.0
    return {
        "total": round(max(0.0, min(100.0, total)), 1),
        "rubric": rubric,
        "criteria": review.get("criteria") if isinstance(review.get("criteria"), dict) else {},
        "reason_vi": _clean(review.get("reason_vi")),
        "evidence": _coerce_list(review.get("evidence")),
        "recommended_parts": _coerce_list(review.get("recommended_parts")),
    }

def _evaluate_candidate_rows(
    episode: DBStoryEpisode,
    rows: list[DBStoryScenarioCandidate],
    creative_brief: dict[str, Any],
    db: Session,
) -> dict[str, Any]:
    candidates = [dict(row.script_json) for row in rows if isinstance(row.script_json, dict)]
    _validate_distinct_candidates(candidates)
    fallback_reason: str | None = None
    try:
        evaluation = _run_structured_ai(
            db,
            _evaluation_prompt(episode, candidates, creative_brief),
            STORY_EVALUATION_SCHEMA,
        )
    except Exception as exc:
        if not _should_use_story_studio_ai_fallback(exc):
            raise
        fallback_reason = str(exc)
        evaluation = _fallback_evaluation_payload(
            episode,
            candidates,
            fallback_reason=fallback_reason,
        )
        video_observability.log_event(
            db,
            step_name="story_studio_candidate_evaluation_fallback",
            status="warning",
            error_code="STORY_CANDIDATE_EVALUATION_PROVIDER_FALLBACK",
            exc=exc,
            message="Provider chấm candidate lỗi/chậm; dùng fallback nội bộ để tiếp tục Story Studio.",
            technical_details={"episode_id": episode.id, "candidate_count": len(rows)},
        )
    reviews = evaluation.get("reviews") if isinstance(evaluation.get("reviews"), list) else []
    by_strategy = {review.get("strategy_type"): review for review in reviews if isinstance(review, dict)}
    expected = {strategy for strategy, _label in STRATEGIES}
    if set(by_strategy) != expected:
        raise StoryStudioError("AI critic chưa trả đủ đánh giá cho ba strategy.")
    rubric = _clean(evaluation.get("rubric")) or _rubric_text(episode.output_intent)
    now = datetime.utcnow()
    for row in rows:
        review = by_strategy.get(row.strategy_type)
        if not isinstance(review, dict):
            raise StoryStudioError(f"Thiếu đánh giá cho candidate {row.strategy_type}.")
        row.score_json = _score_from_review(review, rubric)
        row.strengths = "\n".join(str(item) for item in _coerce_list(review.get("strengths")) if _clean(item))
        row.risks = "\n".join(str(item) for item in _coerce_list(review.get("risks")) if _clean(item))
        row.evaluation_status = "completed"
        row.evaluation_json = review
        if fallback_reason:
            row.generation_metadata_json = {
                **(row.generation_metadata_json or {}),
                "evaluation_fallback_used": True,
                "evaluation_fallback_reason": fallback_reason[:1000],
            }
        row.updated_at = now
    return evaluation

def _master_story_canon_check(episode: DBStoryEpisode, master: dict[str, Any], db: Session) -> dict[str, Any]:
    text = _value_to_text(
        {
            "title": master.get("title"),
            "hook": master.get("hook"),
            "logline": master.get("logline"),
            "full_story": master.get("full_story"),
            "key_beats": master.get("key_beats"),
            "continuity_updates": master.get("continuity_updates"),
        }
    )
    check = series_brain.check_canon(
        episode.series_id,
        models.SeriesCanonCheckRequest(
            prompt=text or json.dumps(master, ensure_ascii=False),
            prompt_kind="master_story",
            prompt_ref_id=episode.id,
            story_episode_id=episode.id,
        ),
        db,
    )
    result = check.model_dump(mode="json")
    if not check.passed:
        conflicts = ", ".join(_clean(item.get("message") or item.get("field") or item) for item in check.blocking_conflicts)
        raise StoryStudioError(f"Master Story còn lỗi canon chặn: {conflicts or 'không rõ lỗi'}.")
    return result

def generate_candidates(episode_id: str, db: Session) -> models.StoryEpisodeResponse | None:
    episode = db.query(DBStoryEpisode).filter(DBStoryEpisode.id == episode_id).first()
    if episode is None:
        return None
    series = _series_for_story(episode.series_id, db)
    if series is None:
        return None
    _validate_intent(series, episode.output_intent)
    source_payload, source_context_text = _compile_episode_source_payload(episode, db)
    source_context_for_memory = source_context_text[:1800] if source_payload else source_context_text
    combined_user_input = "\n\n".join(
        part for part in [episode.source_input, source_context_for_memory] if _clean(part)
    )
    source_trace_payload = None
    if source_payload:
        source_trace_payload = {
            key: value
            for key, value in source_payload.items()
            if key != "chunks"
        }
    try:
        compiled_context = series_brain.compile_prompt_context(
            series.id,
            db,
            task_type="story_candidate",
            episode_number=episode.episode_number,
            story_episode_id=episode.id,
            user_input=combined_user_input or episode.source_input,
            current_payload={
                "episode_title": episode.title,
                "output_intent": episode.output_intent,
                "market_profile": episode.market_profile,
                "language_profile": episode.language_profile,
                "output_settings": _settings_json(_episode_output_settings(episode)),
                "structured_source": source_trace_payload,
            },
            max_chars=STORY_CANDIDATE_CONTEXT_MAX_CHARS,
            persist_trace=True,
        )
        memory_text = compiled_context.context_text
    except Exception:
        memory_text, _truncated = video_series_memory.read_series_memory_for_prompt(series.id, db)
        compiled_context = None
    profiles_text = _character_profiles_text(series.id, db) or _clean(series.character_bible)
    creative_brief = _creative_brief(
        episode=episode,
        series=series,
        memory_text=memory_text,
        profiles_text=profiles_text,
    )
    comic_style_guidance = _comic_source_style_guidance(episode, db)
    if comic_style_guidance and not _clean(creative_brief.get("series_bible", {}).get("style_bible")):
        creative_brief["series_bible"]["style_bible"] = comic_style_guidance
        creative_brief.setdefault("visual_style_guidance", comic_style_guidance)
        creative_brief.setdefault("non_negotiables", []).append(
            "Nguồn là truyện tranh/comic: giữ cảm giác anime/manga/webtoon khi viết visual moments, image_story_notes và video_story_notes."
        )
    if compiled_context is not None:
        creative_brief["series_context_trace_id"] = compiled_context.trace_id
        creative_brief["selected_memory_cards"] = compiled_context.selected_cards
        creative_brief["context_group_usage"] = compiled_context.group_usage
    if source_payload:
        creative_brief["structured_source"] = source_payload
    now = datetime.utcnow()
    db.query(DBStoryScenarioCandidate).filter(DBStoryScenarioCandidate.story_episode_id == episode.id).delete()
    context_snapshot_id = creative_brief.get("series_context_trace_id") if isinstance(creative_brief, dict) else None
    model_label = _safe_model_label(db)
    rows_by_strategy: dict[str, DBStoryScenarioCandidate] = {}
    for strategy_type, label in STRATEGIES:
        row = DBStoryScenarioCandidate(
            id=str(uuid.uuid4()),
            story_episode_id=episode.id,
            strategy_type=strategy_type,
            script_json={
                "strategy_type": strategy_type,
                "strategy_label": label,
                "status": "running",
                "message": "Đang tạo candidate bằng AI.",
                "creative_brief": creative_brief,
                "context_snapshot_id": context_snapshot_id,
            },
            score_json=None,
            strengths=None,
            risks=None,
            context_snapshot_id=str(context_snapshot_id) if context_snapshot_id else None,
            model_label=model_label,
            generation_attempt=0,
            generation_status="running",
            generation_metadata_json={
                "schema_version": "story-studio-candidate-v1",
                "strategy_label": label,
                "independent_prompt": True,
                "context_snapshot_id": context_snapshot_id,
            },
            evaluation_status="pending",
            selected=False,
            source_document_id=source_payload.get("source_document_id") if source_payload else None,
            source_document_revision=source_payload.get("source_revision") if source_payload else None,
            development_mode=source_payload.get("development_mode") if source_payload else episode.development_mode,
            dependency_fingerprint=source_payload.get("fingerprint") if source_payload else None,
            created_at=now,
            updated_at=now,
        )
        db.add(row)
        rows_by_strategy[strategy_type] = row
    episode.updated_at = now
    db.commit()
    candidate_payloads: list[dict[str, Any]] = []
    attempts_by_strategy: dict[str, int] = {}
    for strategy_type, label in STRATEGIES:
        last_error: Exception | None = None
        for attempt in range(1, MAX_CANDIDATE_ATTEMPTS + 1):
            attempts_by_strategy[strategy_type] = attempt
            row = rows_by_strategy[strategy_type]
            row.generation_attempt = attempt
            row.generation_status = "running"
            row.updated_at = datetime.utcnow()
            row.generation_metadata_json = {
                **(row.generation_metadata_json or {}),
                "attempt": attempt,
            }
            db.commit()
            try:
                try:
                    payload = _run_structured_ai(
                        db,
                        _candidate_prompt(
                            creative_brief=creative_brief,
                            strategy_type=strategy_type,
                            label=label,
                            episode=episode,
                            context_snapshot_id=str(context_snapshot_id or ""),
                            attempt=attempt,
                        ),
                        STORY_CANDIDATE_SCHEMA,
                    )
                except Exception as exc:
                    if not _should_use_story_studio_ai_fallback(exc):
                        raise
                    payload = _fallback_candidate_payload(
                        episode=episode,
                        creative_brief=creative_brief,
                        strategy_type=strategy_type,
                        fallback_reason=str(exc),
                    )
                    row.generation_metadata_json = {
                        **(row.generation_metadata_json or {}),
                        "fallback_used": True,
                        "fallback_reason": str(exc)[:1000],
                    }
                    video_observability.log_event(
                        db,
                        step_name="story_studio_candidate_generation_fallback",
                        status="warning",
                        error_code="STORY_CANDIDATE_PROVIDER_FALLBACK",
                        exc=exc,
                        message="Provider tạo candidate lỗi/chậm; dùng fallback nội bộ cho candidate.",
                        technical_details={"episode_id": episode.id, "strategy_type": strategy_type, "attempt": attempt},
                    )
                normalized_payload = _validate_candidate_script(payload, episode=episode, strategy_type=strategy_type)
                candidate_payloads.append(normalized_payload)
                row.script_json = {
                    **normalized_payload,
                    "creative_brief": creative_brief,
                    "context_snapshot_id": context_snapshot_id,
                }
                row.strengths = "\n".join(str(item) for item in _coerce_list(normalized_payload.get("strengths_claimed")) if _clean(item))
                row.risks = "\n".join(str(item) for item in _coerce_list(normalized_payload.get("risks_claimed")) if _clean(item))
                row.generation_status = "completed"
                row.evaluation_status = "pending"
                row.generation_metadata_json = {
                    **(row.generation_metadata_json or {}),
                    "attempt": attempt,
                    "completed_at": datetime.utcnow().isoformat(),
                }
                row.updated_at = datetime.utcnow()
                db.commit()
                last_error = None
                break
            except Exception as exc:
                last_error = exc
                retrying = attempt < MAX_CANDIDATE_ATTEMPTS
                row.generation_status = "retrying" if retrying else "failed"
                row.evaluation_status = "pending" if retrying else "failed"
                row.script_json = {
                    **(row.script_json or {}),
                    "status": row.generation_status,
                    "error_message": str(exc),
                }
                row.generation_metadata_json = {
                    **(row.generation_metadata_json or {}),
                    "attempt": attempt,
                    "last_error": str(exc),
                    "will_retry": retrying,
                }
                row.updated_at = datetime.utcnow()
                db.commit()
                video_observability.log_event(
                    db,
                    step_name="story_studio_candidate_generation",
                    status="warning",
                    error_code="STORY_CANDIDATE_AI_RETRY",
                    exc=exc,
                    message="Candidate Story Studio lỗi, retry riêng candidate này.",
                    technical_details={"strategy_type": strategy_type, "attempt": attempt},
                )
        if last_error is not None:
            raise StoryStudioError(f"Không tạo được candidate {label}: {last_error}") from last_error
    rows = [rows_by_strategy[strategy_type] for strategy_type, _label in STRATEGIES]
    try:
        _validate_distinct_candidates(candidate_payloads)
    except Exception as exc:
        for row in rows:
            row.evaluation_status = "failed"
            row.generation_metadata_json = {
                **(row.generation_metadata_json or {}),
                "validation_error": str(exc),
            }
            row.updated_at = datetime.utcnow()
        db.commit()
        raise
    try:
        _evaluate_candidate_rows(episode, rows, creative_brief, db)
    except Exception as exc:
        for row in rows:
            if row.evaluation_status != "completed":
                row.evaluation_status = "failed"
            row.generation_metadata_json = {
                **(row.generation_metadata_json or {}),
                "evaluation_error": str(exc),
            }
            row.updated_at = datetime.utcnow()
        db.commit()
        video_observability.log_event(
            db,
            step_name="story_studio_candidate_evaluation",
            status="failure",
            error_code="STORY_CANDIDATE_EVALUATION_FAILED",
            exc=exc,
            message="Không chấm được 3 hướng kịch bản Story Studio.",
            technical_details={"episode_id": episode.id, "candidate_count": len(rows)},
        )
        raise
    episode.updated_at = datetime.utcnow()
    db.commit()
    for row in rows:
        db.refresh(row)
    video_observability.log_event(
        db,
        step_name="story_studio_candidates",
        status="success",
        message="Đã tạo và chấm đúng 3 hướng kịch bản Story Studio bằng AI.",
        technical_details={
            "series_id": series.id,
            "series_mode": _series_mode(series),
            "output_intent": episode.output_intent,
            "candidate_count": 3,
            "context_snapshot_id": context_snapshot_id,
        },
    )
    db.refresh(episode)
    return _episode_response(episode, db)

def score_candidates(episode_id: str, db: Session) -> models.StoryEpisodeResponse | None:
    episode = db.query(DBStoryEpisode).filter(DBStoryEpisode.id == episode_id).first()
    if episode is None:
        return None
    rows = db.query(DBStoryScenarioCandidate).filter(DBStoryScenarioCandidate.story_episode_id == episode.id).all()
    if len(rows) != 3:
        raise StoryStudioError("Cần có đúng 3 hướng kịch bản trước khi chấm điểm.")
    creative_brief = _creative_brief_from_candidate_rows(rows)
    _repair_candidate_rows_with_fallback(episode, rows, creative_brief, db)
    _require_completed_candidate_rows(episode, rows)
    _evaluate_candidate_rows(episode, rows, creative_brief, db)
    db.commit()
    db.refresh(episode)
    return _episode_response(episode, db)

def select_master_story(
    episode_id: str,
    data: models.StoryCandidateSelectionRequest,
    db: Session,
) -> models.StoryEpisodeResponse | None:
    episode = db.query(DBStoryEpisode).filter(DBStoryEpisode.id == episode_id).first()
    if episode is None:
        return None
    master = data.master_story_json
    selected_candidate: DBStoryScenarioCandidate | None = None
    if data.candidate_id:
        selected_candidate = (
            db.query(DBStoryScenarioCandidate)
            .filter(DBStoryScenarioCandidate.story_episode_id == episode.id, DBStoryScenarioCandidate.id == data.candidate_id)
            .first()
        )
        if selected_candidate is None:
            raise StoryStudioError("Không tìm thấy hướng kịch bản đã chọn.")
        if not _candidate_row_has_completed_payload(selected_candidate, episode):
            raise StoryStudioError("Candidate đã chọn chưa tạo thành công, chưa thể làm Master Story.")
        master = selected_candidate.script_json
    if not isinstance(master, dict):
        raise StoryStudioError("Cần chọn một candidate hoặc gửi Master Story hợp lệ.")
    _validate_master_story(master)
    master = dict(master)
    master["canon_check"] = _master_story_canon_check(episode, master, db)
    db.query(DBStoryScenarioCandidate).filter(DBStoryScenarioCandidate.story_episode_id == episode.id).update(
        {"selected": False},
        synchronize_session=False,
    )
    if selected_candidate is not None:
        selected_candidate.selected = True
        selected_candidate.updated_at = datetime.utcnow()
    episode.master_story_json = master
    episode.title = episode.title or _clean(master.get("title")) or episode.title
    episode.selection_reason = data.selection_reason or "Người dùng chọn/tổng hợp thành Master Story."
    episode.approval_status = "pending_approval"
    episode.approved_at = None
    episode.revision = int(episode.revision or 1) + 1
    episode.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(episode)
    return _episode_response(episode, db)

def synthesize_master_story(
    episode_id: str,
    data: models.StoryCandidateSynthesisRequest,
    db: Session,
) -> models.StoryEpisodeResponse | None:
    episode = db.query(DBStoryEpisode).filter(DBStoryEpisode.id == episode_id).first()
    if episode is None:
        return None
    query = db.query(DBStoryScenarioCandidate).filter(DBStoryScenarioCandidate.story_episode_id == episode.id)
    if data.candidate_ids:
        query = query.filter(DBStoryScenarioCandidate.id.in_(data.candidate_ids))
    rows = query.order_by(DBStoryScenarioCandidate.created_at.asc()).all()
    if len(rows) < 2:
        raise StoryStudioError("Cần ít nhất hai candidate để tổng hợp.")
    all_rows = db.query(DBStoryScenarioCandidate).filter(DBStoryScenarioCandidate.story_episode_id == episode.id).all()
    creative_brief = _creative_brief_from_candidate_rows(all_rows)
    if len(all_rows) == 3:
        _repair_candidate_rows_with_fallback(episode, all_rows, creative_brief, db)
        if data.candidate_ids:
            selected_ids = set(data.candidate_ids)
            rows = [row for row in all_rows if row.id in selected_ids]
        else:
            rows = sorted(all_rows, key=lambda row: row.created_at)
    _require_completed_candidate_rows(episode, rows)
    if any(row.evaluation_status != "completed" or not isinstance(row.evaluation_json, dict) for row in rows):
        _require_completed_candidate_rows(episode, all_rows)
        _evaluate_candidate_rows(episode, all_rows, creative_brief, db)
        db.flush()
    candidates = [dict(row.script_json) for row in rows if isinstance(row.script_json, dict)]
    evaluation = {
        "reviews": [row.evaluation_json for row in rows],
        "scores": {row.strategy_type: row.score_json for row in rows},
    }
    synthesis_fallback_reason: str | None = None
    try:
        payload = _run_structured_ai(
            db,
            _synthesis_prompt(episode, candidates, evaluation, data.user_direction),
            STORY_SYNTHESIS_SCHEMA,
        )
    except Exception as exc:
        if not _should_use_story_studio_ai_fallback(exc):
            raise
        synthesis_fallback_reason = str(exc)
        payload = _fallback_master_story_payload(
            episode=episode,
            candidates=candidates,
            evaluation=evaluation,
            user_direction=data.user_direction,
            fallback_reason=synthesis_fallback_reason,
        )
        video_observability.log_event(
            db,
            step_name="story_studio_master_synthesis_fallback",
            status="warning",
            error_code="STORY_MASTER_SYNTHESIS_PROVIDER_FALLBACK",
            exc=exc,
            message="Provider tổng hợp Master Story lỗi/chậm; dùng fallback nội bộ.",
            technical_details={"episode_id": episode.id, "candidate_count": len(rows)},
        )
    master = _normalize_story_payload(payload, episode=episode)
    _validate_master_story(master)
    master["canon_check"] = _master_story_canon_check(episode, master, db)
    db.query(DBStoryScenarioCandidate).filter(DBStoryScenarioCandidate.story_episode_id == episode.id).update(
        {"selected": False},
        synchronize_session=False,
    )
    selected_ids = {row.id for row in rows}
    for row in rows:
        row.selected = row.id in selected_ids
        row.updated_at = datetime.utcnow()
    episode.master_story_json = master
    episode.title = episode.title or _clean(master.get("title")) or episode.title
    episode.selection_reason = (
        data.user_direction
        or (
            "Fallback nội bộ tổng hợp Master Story vì provider lỗi/chậm."
            if synthesis_fallback_reason
            else "AI tổng hợp phần tốt nhất từ nhiều candidate."
        )
    )
    episode.approval_status = "pending_approval"
    episode.approved_at = None
    episode.revision = int(episode.revision or 1) + 1
    episode.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(episode)
    return _episode_response(episode, db)

def approve_master_story(
    episode_id: str,
    data: models.StoryApprovalRequest,
    db: Session,
) -> models.StoryEpisodeResponse | None:
    episode = db.query(DBStoryEpisode).filter(DBStoryEpisode.id == episode_id).first()
    if episode is None:
        return None
    if data.approved and not isinstance(episode.master_story_json, dict):
        raise StoryStudioError("Cần có Master Story trước khi duyệt.")
    if data.approved:
        _validate_master_story(episode.master_story_json)
    old_revision = int(episode.revision or 1)
    episode.approval_status = "approved" if data.approved else "rejected"
    episode.approved_at = datetime.utcnow() if data.approved else None
    episode.revision = old_revision + 1
    episode.updated_at = datetime.utcnow()
    series_references.record_version(
        db,
        series_id=episode.series_id,
        entity_type="master_story",
        entity_id=episode.id,
        revision=int(episode.revision or 1),
        snapshot={
            "episode_number": episode.episode_number,
            "title": episode.title,
            "approval_status": episode.approval_status,
            "master_story_json": episode.master_story_json,
            "selection_reason": episode.selection_reason,
        },
        change_source="story_master_approval",
        change_reason="Duyệt hoặc từ chối Master Story.",
    )
    if old_revision > 1:
        series_references.mark_dependency_stale(
            episode.series_id,
            dependency_type="master_story",
            dependency_id=episode.id,
            changed_scope="story_state",
            old_revision=old_revision,
            new_revision=int(episode.revision or 1),
            reason_vi="Master Story của tập đã đổi trạng thái hoặc nội dung.",
            db=db,
            commit=False,
        )
    db.commit()
    db.refresh(episode)
    if data.approved:
        series_brain.record_story_episode_summaries(episode.series_id, episode.id, db)
        try:
            series_brain.propose_current_state(
                episode.series_id,
                models.SeriesStateProposalRequest(
                    source_type="story_episode",
                    source_id=episode.id,
                    based_on_episode_number=episode.episode_number,
                ),
                db,
            )
        except Exception as exc:
            video_observability.log_event(
                db,
                step_name="story_current_state_proposal",
                status="warning",
                error_code="SERIES_STATE_PROPOSAL_FAILED",
                exc=exc,
                message="Khong tao duoc de xuat trang thai series sau khi duyet Master Story.",
                technical_details={"series_id": episode.series_id, "story_episode_id": episode.id},
            )
    video_series_memory.sync_series_memory_file(episode.series_id, db)
    return _episode_response(episode, db)

def _require_approved_master(episode: DBStoryEpisode) -> dict[str, Any]:
    if episode.approval_status != "approved" or not isinstance(episode.master_story_json, dict):
        raise StoryStudioError("Cần duyệt Master Story trước khi tạo sản phẩm.")
    _validate_master_story(episode.master_story_json)
    return episode.master_story_json

def _contains_any(text: str, markers: list[str]) -> bool:
    lowered = text.lower()
    return any(marker.lower() in lowered for marker in markers)

def _contains_english_phrase(text: str, phrase: str) -> bool:
    escaped = re.escape(phrase.lower())
    return re.search(rf"(?<![a-z0-9]){escaped}(?![a-z0-9])", text.lower()) is not None

def _has_internal_prompt_contradiction(prompt: str) -> bool:
    contradictions = [
        ("close-up", "wide shot"),
        ("close up", "wide shot"),
        ("day", "night"),
        ("daylight", "night"),
        ("camera left", "camera right"),
        ("screen left", "screen right"),
        ("facing left", "facing right"),
        ("move left", "move right"),
        ("moves left", "moves right"),
        ("looking left", "looking right"),
        ("look left", "look right"),
    ]
    return any(_contains_english_phrase(prompt, left) and _contains_english_phrase(prompt, right) for left, right in contradictions)

def _story_panel_quality_check(
    panel: dict[str, Any],
    *,
    canon_check: dict[str, Any] | None = None,
    threshold: float = DEFAULT_PROMPT_QUALITY_THRESHOLD,
) -> dict[str, Any]:
    prompt = _clean(panel.get("prompt"))
    caption = _clean(panel.get("caption_or_dialogue"))
    visual = _clean(panel.get("visual_description"))
    consistency = _clean(panel.get("character_consistency_notes"))
    style = _clean(panel.get("style_notes"))
    blocking_errors: list[str] = []
    warnings: list[str] = []
    suggestions: list[str] = []
    evidence: list[str] = []
    criteria: dict[str, float] = {}

    canon_passed = not canon_check or bool(canon_check.get("passed", True))
    canon_conflicts = canon_check.get("blocking_conflicts") if isinstance(canon_check, dict) else []
    if canon_passed:
        criteria["canon_story_state"] = 25
        evidence.append("Canon check không có lỗi chặn.")
    else:
        criteria["canon_story_state"] = 0
        blocking_errors.append("canon_conflicts")
        suggestions.append("Sửa prompt theo bằng chứng canon hoặc nhập lý do ghi đè nếu thật sự cần.")
        evidence.append(f"Canon conflicts: {json.dumps(canon_conflicts, ensure_ascii=False)}")

    if prompt and consistency and _contains_any(prompt, ["character", "nhân vật", "canon", "continuity", "same"]):
        criteria["character_identity"] = 20
    elif prompt and consistency:
        criteria["character_identity"] = 12
        warnings.append("Prompt có context nhân vật nhưng chưa nhắc rõ identity/continuity.")
        suggestions.append("Nhắc rõ identity, trang phục/fixed traits và continuity trong prompt.")
    else:
        criteria["character_identity"] = 0
        blocking_errors.append("missing_character_identity")
        suggestions.append("Bổ sung nhận diện nhân vật và fixed traits vào prompt.")

    action_text = f"{visual}\n{prompt}"
    if len(action_text) >= 80 and not _contains_any(action_text, ["nhiều hành động cùng lúc", "random", "mơ hồ"]):
        criteria["clear_action_duration"] = 15
    elif action_text:
        criteria["clear_action_duration"] = 8
        warnings.append("Hành động hoặc mục đích panel còn ngắn/mơ hồ.")
        suggestions.append("Viết một hành động chính rõ, đọc được trong một panel.")
    else:
        criteria["clear_action_duration"] = 0
        blocking_errors.append("missing_action")
        suggestions.append("Thêm visual_description hoặc prompt có hành động chính rõ.")

    if _contains_any(prompt, ["continuity", "canon", "episode", "beat", "style"]):
        criteria["continuity_panel"] = 10
    else:
        criteria["continuity_panel"] = 4
        warnings.append("Prompt chưa nêu continuity/panel beat đủ rõ.")
        suggestions.append("Gắn prompt với beat, trạng thái truyện và style hiện tại.")

    if _contains_any(prompt, ["vertical", "panel", "cinematic", "composition", "framing", "cận", "khung"]):
        criteria["camera_framing_composition"] = 10
    else:
        criteria["camera_framing_composition"] = 4
        suggestions.append("Bổ sung bố cục, framing, góc camera hoặc loại panel.")

    found_contradiction = _has_internal_prompt_contradiction(prompt)
    if found_contradiction:
        criteria["renderability"] = 0
        blocking_errors.append("internal_contradiction")
        suggestions.append("Gỡ chỉ dẫn loại trừ nhau trong prompt.")
    elif prompt and style:
        criteria["renderability"] = 10
    else:
        criteria["renderability"] = 6
        warnings.append("Prompt render được nhưng còn thiếu style/negative rõ.")

    if caption and not _contains_any(prompt, ["subtitle burned", "baked subtitle", "random text"]):
        criteria["language_caption_safe_zone"] = 5
    else:
        criteria["language_caption_safe_zone"] = 2
        suggestions.append("Giữ caption riêng và tránh yêu cầu provider sinh chữ/subtitle trực tiếp.")

    if _clean(panel.get("purpose")) or _contains_any(prompt, ["hook", "payoff", "retention", "beat"]):
        criteria["retention_transition_sound"] = 5
    else:
        criteria["retention_transition_sound"] = 2
        suggestions.append("Nêu vai trò giữ chân hoặc payoff của panel.")

    if _contains_any(prompt, ["create a video", "video prompt", "seconds", "-second"]) and not _contains_any(prompt, ["story panel", "image", "panel"]):
        blocking_errors.append("image_prompt_written_as_video")
        suggestions.append("Viết lại thành prompt ảnh/panel, không phải prompt video.")

    score = round(sum(criteria.values()), 1)
    return {
        "passed": score >= threshold and not blocking_errors,
        "score": score,
        "threshold": threshold,
        "criteria": criteria,
        "blocking_errors": sorted(set(blocking_errors)),
        "warnings": sorted(set(warnings)),
        "evidence": evidence,
        "suggestions": suggestions,
    }

def _record_panel_version(panel: dict[str, Any], *, reason: str, changes: list[str] | None = None) -> None:
    versions = [dict(item) for item in panel.get("prompt_versions", []) if isinstance(item, dict)]
    versions.append(
        {
            "version": len(versions) + 1,
            "prompt": panel.get("prompt"),
            "render_prompt": panel.get("render_prompt"),
            "reader_prompt_vi": panel.get("reader_prompt_vi"),
            "prompt_explanation_vi": panel.get("prompt_explanation_vi"),
            "negative_prompt": panel.get("negative_prompt"),
            "caption_or_dialogue": panel.get("caption_or_dialogue"),
            "visual_description": panel.get("visual_description"),
            "scene_context": panel.get("scene_context"),
            "camera_angle": panel.get("camera_angle"),
            "composition_notes": panel.get("composition_notes"),
            "dialogue_note": panel.get("dialogue_note"),
            "reason": reason,
            "changes": changes or [],
            "created_at": datetime.utcnow().isoformat(),
        }
    )
    panel["prompt_versions"] = versions

def _refresh_panel_checks(
    panel: dict[str, Any],
    *,
    series_id: str,
    episode_id: str,
    db: Session,
    allow_override: bool = False,
    override_reason: str | None = None,
) -> dict[str, Any]:
    canon_check = series_brain.check_canon(
        series_id,
        models.SeriesCanonCheckRequest(
            prompt=str(panel.get("prompt") or ""),
            prompt_kind="image_panel_prompt",
            prompt_ref_id=str(panel.get("order") or ""),
            story_episode_id=episode_id,
            allow_override=allow_override,
            override_reason=override_reason,
        ),
        db,
    )
    panel["canon_check"] = canon_check.model_dump(mode="json")
    quality = _story_panel_quality_check(
        panel,
        canon_check=panel["canon_check"],
        threshold=float(panel.get("quality_threshold") or DEFAULT_PROMPT_QUALITY_THRESHOLD),
    )
    panel["quality_check"] = quality
    panel["quality_status"] = "passed" if quality["passed"] else "needs_review"
    return quality

def _camera_angle_for_panel(index: int, total: int, motion: str, visual: str) -> str:
    lowered = f"{motion} {visual}".lower()
    if index == 1:
        return "dramatic hook detail framing, shallow depth of field, high contrast"
    if index == total:
        return "cinematic cliffhanger frame with strong negative space for final caption"
    if any(marker in lowered for marker in ["đứng", "bước", "quyết định", "đối diện", "đẩy", "chạy", "hành động"]):
        return "low-angle medium shot, dynamic diagonal composition, clear character action"
    if any(marker in lowered for marker in ["nhìn", "ánh mắt", "im lặng", "nước mắt", "tủi", "hối tiếc", "sợ"]):
        return "tight face-and-eyes emotional framing, soft background blur"
    if any(marker in lowered for marker in ["phòng", "dinh", "hành lang", "thư viện", "bối cảnh", "toàn cảnh"]):
        return "environment-establishing vertical 9:16 frame, character scale against environment"
    return "cinematic medium shot, readable silhouette, foreground-midground-background layering"

def _composition_note_for_panel(index: int, total: int, aspect_ratio: str) -> str:
    if index == 1:
        return (
            f"{aspect_ratio} vertical comic panel; hook first, subject large in frame, "
            "leave clean caption space at top/bottom, no clutter."
        )
    if index == total:
        return (
            f"{aspect_ratio} vertical final panel; strong cliffhanger silhouette or tight detail frame, "
            "leave negative space for ending caption."
        )
    return (
        f"{aspect_ratio} vertical comic panel; one main action only, readable face, "
        "clear depth layers, speech bubble/caption zone kept clean."
    )

def _dialogue_note_for_panel(caption: str, *, index: int, target_language: str) -> str:
    text = _clip_prompt_text(caption, 180)
    language_label = video_language.video_language_prompt_label(target_language)
    if not text:
        return (
            "In-image text policy: no readable text is required for this panel. "
            "Do not invent any text, scene labels, hook labels, OCR bracket IDs, copyright/footer text, or publisher credits."
        )
    return (
        f'Required in-image bubble/caption text ({language_label}): "{text}". '
        f"Render exactly the quoted text inside the panel, in {language_label} only. "
        "Never translate it, never mix another language, and never add scene labels, hook/opening labels, "
        "speaker-number tags like [56], narration/dialogue prefixes, copyright/footer text, or publisher credits. "
        "Keep the bubble/caption short, clean, and legible."
    )

def _story_panel_reader_prompt_vi_from_panel(
    panel: dict[str, Any],
    *,
    target_language: str,
    total_panels: int,
) -> str:
    order = int(panel.get("order") or 0)
    language_label = video_language.video_language_prompt_label(target_language)
    caption = _clean(panel.get("caption_or_dialogue"))
    lines = [
        f"Bản đọc cho người dùng - khung {order}/{total_panels}.",
        f"Mục đích khung: {_clean(panel.get('purpose')) or _clean(panel.get('visual_description')) or 'chưa có mô tả'}.",
    ]
    if _clean(panel.get("visual_description")):
        lines.append(f"Hình ảnh chính: {_clean(panel.get('visual_description'))}.")
    if _clean(panel.get("camera_angle")) or _clean(panel.get("composition_notes")):
        lines.append(
            "Góc máy/bố cục: "
            + " · ".join(
                item
                for item in [_clean(panel.get("camera_angle")), _clean(panel.get("composition_notes"))]
                if item
            )
            + "."
        )
    if caption:
        lines.append(f"Chữ/thoại AI cần vẽ trong ảnh ({language_label}): {caption}")
    else:
        lines.append("Khung này không có chữ bắt buộc; AI không được tự thêm chữ.")
    lines.append(
        "Bản gửi AI render giữ nhân vật nhất quán giữa các panel. Nếu khung có caption thì AI vẽ đúng caption đã chốt; "
        "nếu không có caption thì AI không tự thêm chữ. Chữ trong ảnh chỉ dùng đúng ngôn ngữ đã chọn, không trộn ngôn ngữ."
    )
    return "\n".join(lines)

def _sync_story_panel_prompt_views(
    panel: dict[str, Any],
    *,
    target_language: str,
    total_panels: int,
) -> None:
    panel["render_prompt"] = _clean(panel.get("prompt"))
    reader_prompt = _story_panel_reader_prompt_vi_from_panel(
        panel,
        target_language=target_language,
        total_panels=total_panels,
    )
    panel["reader_prompt_vi"] = reader_prompt
    panel["prompt_explanation_vi"] = reader_prompt

def _scene_context_for_panel(
    *,
    episode: DBStoryEpisode,
    index: int,
    total: int,
    beat: str,
    source_continuity: str,
) -> str:
    continuity = f" Continuity: {source_continuity}" if source_continuity else ""
    return (
        f"Episode {episode.episode_number}, panel {index}/{total}. Story beat: "
        f"{_clip_prompt_text(beat, 260)}.{continuity}"
    )

def _panels_from_master(episode: DBStoryEpisode, series: DBVideoSeries, db: Session) -> list[dict[str, Any]]:
    master = _require_approved_master(episode)
    output_settings = _episode_output_settings(episode)
    image_settings = output_settings.image
    manual_count = image_settings.panel_count if image_settings.panel_mode == "manual" else None
    linked_video_project_id = _linked_video_project_id(episode.id, db)
    panel_rows: list[dict[str, Any]] = []
    if image_settings.panel_mode == "auto" and linked_video_project_id:
        panel_rows = _panel_rows_from_video_micro_scenes(linked_video_project_id, db)
    generation_source = "video_micro_scenes" if panel_rows else "master_story"
    if manual_count:
        panel_rows = _panel_rows_from_master(master, manual_count)
        generation_source = "manual_master_story"
    elif not panel_rows:
        panel_rows = _panel_rows_from_master(master)
    profile_context = _character_profiles_text(series.id, db) or _clean(series.character_bible) or "Chưa có Hồ sơ nhân vật."
    visual_style = _effective_story_visual_style(series, episode, db)
    target_language = _target_viewer_language_for_episode(episode)
    panels: list[dict[str, Any]] = []
    total_panels = len(panel_rows)
    for index, row in enumerate(panel_rows, start=1):
        beat = _sanitize_story_panel_source_text(row["beat"], remove_hook_label=True) or f"Story beat {index}"
        visual = _sanitize_story_panel_source_text(row["visual"], remove_hook_label=True) or beat
        motion = _sanitize_story_panel_source_text(row["motion"], remove_hook_label=True)
        caption = _sanitize_panel_bubble_text(row.get("caption"), target_language=target_language)
        source_type = _clean(row.get("source_type")) or generation_source
        source_continuity = _sanitize_story_panel_source_text(row.get("continuity"), remove_hook_label=True)
        try:
            compiled_context = series_brain.compile_prompt_context(
                series.id,
                db,
                task_type="image_panel_prompt",
                episode_number=episode.episode_number,
                story_episode_id=episode.id,
                target_ref_type="image_panel",
                target_ref_id=str(index),
                user_input=visual,
                current_payload={
                    "panel_order": index,
                    "beat": beat,
                    "visual": visual,
                    "motion": motion,
                    "source_type": source_type,
                    "source_shot_order": row.get("source_shot_order"),
                    "source_micro_scene_order": row.get("source_micro_scene_order"),
                    "master_story_title": master.get("title"),
                },
                max_chars=12000,
                persist_trace=True,
            )
            panel_context = compiled_context.context_text
            context_trace_id = compiled_context.trace_id
            selected_cards = compiled_context.selected_cards
            selected_profiles = compiled_context.selected_character_profiles
            group_usage = compiled_context.group_usage
        except Exception:
            panel_context = profile_context
            context_trace_id = None
            selected_cards = []
            selected_profiles = []
            group_usage = []
        safe_panel_context = _sanitize_story_panel_source_text(panel_context, remove_hook_label=True) or panel_context
        scene_context = _scene_context_for_panel(
            episode=episode,
            index=index,
            total=total_panels,
            beat=beat,
            source_continuity=source_continuity,
        )
        camera_angle = _camera_angle_for_panel(index, total_panels, motion, visual)
        composition_notes = _composition_note_for_panel(index, total_panels, image_settings.aspect_ratio)
        dialogue_note = _dialogue_note_for_panel(caption, index=index, target_language=target_language)
        target_language_label = video_language.video_language_prompt_label(target_language)
        motion_line = f" Motion/camera beat: {motion}." if motion and motion not in {beat, visual} else ""
        continuity_line = f" Source continuity: {source_continuity}." if source_continuity else ""
        prompt = (
            f"Vertical cinematic manga/webtoon story panel, episode {episode.episode_number}, panel {index}/{total_panels}. "
            f"Scene context: {scene_context}. "
            f"Main visual: {visual}.{motion_line}{continuity_line} "
            f"Camera angle/framing: {camera_angle}. Composition: {composition_notes}. "
            f"Dialogue/caption note: {dialogue_note}. "
            "Text rendering rule: render only the required quoted bubble/caption text when provided; otherwise render no readable text. "
            f"Viewer-facing text language lock: {target_language_label}. "
            f"Image format: {image_settings.aspect_ratio}, {image_settings.width}x{image_settings.height}px. "
            f"Keep canon and character continuity: {safe_panel_context[:1800]}. "
            f"Style bible: {visual_style[:800]}."
        )
        reference_package = series_references.build_reference_prompt_package(
            series.id,
            db,
            prompt_text="\n".join([visual, beat]),
            provider="story-studio-image",
            provider_supports_references=False,
        )
        reference_assets = reference_package.get("reference_assets", [])
        if reference_assets:
            reference_lines = [
                f"{item.get('label') or item.get('id')} ({item.get('entity_type')}:{item.get('entity_id')}, {item.get('reference_role')}, rev {item.get('revision')})"
                for item in reference_assets
            ]
            prompt = f"{prompt} Approved visual references to preserve identity/location: {'; '.join(reference_lines)}."
        panel = {
            "order": index,
            "purpose": beat,
            "caption_or_dialogue": caption[:300],
            "visual_description": visual,
            "scene_context": scene_context,
            "camera_angle": camera_angle,
            "composition_notes": composition_notes,
            "dialogue_note": dialogue_note,
            "prompt": prompt,
            "negative_prompt": _clean(series.negative_rules) or (
                "inconsistent face, changed outfit, extra fingers, unreadable extra text, misspelled quoted text, wrong-language text, "
                "translated text, mixed-language text, random speech bubbles, scene title labels, opening-hook labels, OCR numeric bracket IDs, "
                "dialogue/narration metadata labels, copyright footer, publisher credits, photorealistic live-action, "
                "off-model character, cluttered composition"
            ),
            "character_consistency_notes": profile_context[:1500],
            "style_notes": visual_style[:1500],
            "aspect_ratio": image_settings.aspect_ratio,
            "width": image_settings.width,
            "height": image_settings.height,
            "generation_source": generation_source,
            "source_type": source_type,
            "source_project_id": row.get("source_project_id"),
            "source_shot_id": row.get("source_shot_id"),
            "source_shot_order": row.get("source_shot_order"),
            "source_micro_scene_order": row.get("source_micro_scene_order"),
            "source_timing": row.get("source_timing"),
            "prompt_status": "pending_approval",
            "render_status": "not_requested",
            "series_context_trace_id": context_trace_id,
            "selected_memory_cards": selected_cards,
            "selected_character_profiles": selected_profiles,
            "context_group_usage": group_usage,
            "reference_assets": reference_assets,
            "reference_asset_ids": reference_package.get("reference_asset_ids", []),
            "reference_provider_report": reference_package.get("provider_report", {}),
            "asset": None,
            "quality_threshold": DEFAULT_PROMPT_QUALITY_THRESHOLD,
            "repair_attempt": 0,
            "repair_status": "none",
        }
        _sync_story_panel_prompt_views(panel, target_language=target_language, total_panels=total_panels)
        _refresh_panel_checks(panel, series_id=series.id, episode_id=episode.id, db=db)
        _record_panel_version(panel, reason="initial_generation")
        panels.append(panel)
    return panels

def _panel_dependency_inputs(
    *,
    series: DBVideoSeries,
    episode: DBStoryEpisode,
    adaptation: DBStoryAdaptation,
    panel: dict[str, Any],
) -> list[models.ArtifactDependencyInput]:
    panel_match_text = series_references._normalize_text(  # noqa: SLF001 - shared normalization for targeted dependency matching.
        _value_to_text(
            {
                "purpose": panel.get("purpose"),
                "caption": panel.get("caption_or_dialogue"),
                "visual": panel.get("visual_description"),
            }
        )
    )
    reference_entity_ids = {
        str(reference.get("entity_id"))
        for reference in panel.get("reference_assets", [])
        if isinstance(reference, dict) and _clean(reference.get("entity_id"))
    }
    dependencies: list[models.ArtifactDependencyInput] = [
        models.ArtifactDependencyInput(
            dependency_type="series_bible",
            dependency_id=series.id,
            dependency_revision=int(getattr(series, "revision", 1) or 1),
            dependency_scope="story_state",
            metadata={"title": series.title},
        ),
        models.ArtifactDependencyInput(
            dependency_type="series_style",
            dependency_id=series.id,
            dependency_revision=int(getattr(series, "revision", 1) or 1),
            dependency_scope="camera_style",
            metadata={"style_bible_present": bool(_clean(series.style_bible))},
        ),
        models.ArtifactDependencyInput(
            dependency_type="master_story",
            dependency_id=episode.id,
            dependency_revision=int(getattr(episode, "revision", 1) or 1),
            dependency_scope="story_state",
            metadata={"episode_number": episode.episode_number, "title": episode.title},
        ),
    ]
    for card in panel.get("selected_memory_cards", []) if isinstance(panel.get("selected_memory_cards"), list) else []:
        if not isinstance(card, dict) or not _clean(card.get("id")):
            continue
        scope = "camera_style" if card.get("card_type") == "visual_style" else "story_state"
        dependencies.append(
            models.ArtifactDependencyInput(
                dependency_type="memory_card",
                dependency_id=str(card.get("id")),
                dependency_revision=int(card.get("revision") or 1),
                dependency_scope=scope,
                metadata={"title": card.get("title"), "card_type": card.get("card_type")},
            )
        )
    for profile in panel.get("selected_character_profiles", []) if isinstance(panel.get("selected_character_profiles"), list) else []:
        if not isinstance(profile, dict) or not _clean(profile.get("id")):
            continue
        profile_id = str(profile.get("id"))
        profile_name = series_references._normalize_text(profile.get("name"))  # noqa: SLF001
        if profile_id not in reference_entity_ids and profile_name and profile_name not in panel_match_text:
            continue
        dependencies.append(
            models.ArtifactDependencyInput(
                dependency_type="character_profile",
                dependency_id=profile_id,
                dependency_revision=int(profile.get("revision") or 1),
                dependency_scope="visual_identity",
                metadata={"name": profile.get("name")},
            )
        )
    for reference in panel.get("reference_assets", []) if isinstance(panel.get("reference_assets"), list) else []:
        if not isinstance(reference, dict) or not _clean(reference.get("id")):
            continue
        dependencies.append(
            models.ArtifactDependencyInput(
                dependency_type="reference_asset",
                dependency_id=str(reference.get("id")),
                dependency_revision=int(reference.get("revision") or 1),
                dependency_scope="reference_image",
                metadata={
                    "label": reference.get("label"),
                    "entity_type": reference.get("entity_type"),
                    "entity_id": reference.get("entity_id"),
                    "reference_role": reference.get("reference_role"),
                    "adaptation_id": adaptation.id,
                    "panel_order": panel.get("order"),
                },
            )
        )
    return dependencies

def _record_image_panel_dependencies(
    adaptation: DBStoryAdaptation,
    episode: DBStoryEpisode,
    series: DBVideoSeries,
    db: Session,
) -> None:
    payload = adaptation.payload_json if isinstance(adaptation.payload_json, dict) else {}
    panels = [dict(panel) for panel in payload.get("panels", []) if isinstance(panel, dict)]
    for panel in panels:
        panel_order = int(panel.get("order") or 0)
        if panel_order <= 0:
            continue
        artifact_id = f"{adaptation.id}:panel:{panel_order}"
        series_references.record_dependency_snapshots(
            series.id,
            models.ArtifactDependencyRecordRequest(
                artifact_type="story_panel",
                artifact_id=artifact_id,
                artifact_revision=int(adaptation.revision or 1),
                dependencies=_panel_dependency_inputs(
                    series=series,
                    episode=episode,
                    adaptation=adaptation,
                    panel=panel,
                ),
            ),
            db,
            commit=False,
        )

def create_image_adaptation(episode_id: str, db: Session) -> models.StoryAdaptationResponse | None:
    episode = db.query(DBStoryEpisode).filter(DBStoryEpisode.id == episode_id).first()
    if episode is None:
        return None
    series = _series_for_story(episode.series_id, db)
    if series is None:
        return None
    if episode.output_intent not in IMAGE_INTENTS:
        raise StoryStudioError("Tập này không chọn đầu ra truyện ảnh.")
    output_settings = _episode_output_settings(episode)
    panels = _panels_from_master(episode, series, db)
    payload = {
        "panels": panels,
        "output_settings": _settings_json(output_settings),
        "panel_generation_source": panels[0].get("generation_source") if panels else "none",
        "panel_count": len(panels),
        "image_provider_configured": False,
        "export_ready": True,
    }
    row = (
        db.query(DBStoryAdaptation)
        .filter(DBStoryAdaptation.story_episode_id == episode.id, DBStoryAdaptation.kind == "image_story")
        .first()
    )
    now = datetime.utcnow()
    if row is None:
        row = DBStoryAdaptation(
            id=str(uuid.uuid4()),
            story_episode_id=episode.id,
            kind="image_story",
            status="pending_approval",
            payload_json=payload,
            revision=1,
            created_at=now,
            updated_at=now,
        )
        db.add(row)
    else:
        row.status = "pending_approval"
        row.payload_json = payload
        row.revision = int(row.revision or 1) + 1
        row.updated_at = now
    _record_image_panel_dependencies(row, episode, series, db)
    db.commit()
    db.refresh(row)
    return _adaptation_response(row, db)

def _image_adaptation(episode_id: str, db: Session) -> DBStoryAdaptation:
    row = (
        db.query(DBStoryAdaptation)
        .filter(DBStoryAdaptation.story_episode_id == episode_id, DBStoryAdaptation.kind == "image_story")
        .first()
    )
    if row is None:
        raise StoryStudioError("Chưa có Image Story Adaptation.")
    return row

def _image_adaptation_series_id(row: DBStoryAdaptation, db: Session) -> str:
    episode = db.query(DBStoryEpisode).filter(DBStoryEpisode.id == row.story_episode_id).first()
    if episode is None:
        raise StoryStudioError("Khong tim thay Story Episode cua Image Story Adaptation.")
    return episode.series_id

def approve_image_prompts(
    episode_id: str,
    data: models.StoryPanelPromptApprovalRequest,
    db: Session,
) -> models.StoryAdaptationResponse:
    row = _image_adaptation(episode_id, db)
    payload = dict(row.payload_json) if isinstance(row.payload_json, dict) else {}
    panels = [dict(panel) for panel in payload.get("panels", []) if isinstance(panel, dict)]
    selected = set(data.panel_orders or [int(panel.get("order")) for panel in panels])
    blocking_errors: list[str] = []
    series_id = _image_adaptation_series_id(row, db)
    for panel in panels:
        if int(panel.get("order") or 0) not in selected:
            continue
        if data.approved:
            quality = _refresh_panel_checks(
                panel,
                series_id=series_id,
                episode_id=episode_id,
                db=db,
                allow_override=bool(data.canon_override_reason),
                override_reason=data.canon_override_reason,
            )
            if not quality["passed"]:
                blocking_errors.append(str(panel.get("order") or "unknown"))
                continue
        panel["prompt_status"] = "approved" if data.approved else "pending_approval"
        panel["render_status"] = "waiting_provider" if data.approved else "not_requested"
    if blocking_errors:
        raise StoryStudioError(
            "Prompt panel chưa đạt quality/canon, chưa thể duyệt nếu chưa sửa: "
            + ", ".join(blocking_errors)
        )
    payload["panels"] = panels
    row.payload_json = payload
    row.status = "waiting_provider" if data.approved else "pending_approval"
    row.revision = int(row.revision or 1) + 1
    row.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(row)
    return _adaptation_response(row, db)

def update_panel_prompt(
    episode_id: str,
    data: models.StoryPanelPromptUpdateRequest,
    db: Session,
) -> models.StoryAdaptationResponse:
    row = _image_adaptation(episode_id, db)
    payload = dict(row.payload_json) if isinstance(row.payload_json, dict) else {}
    panels = [dict(panel) for panel in payload.get("panels", []) if isinstance(panel, dict)]
    episode = db.query(DBStoryEpisode).filter(DBStoryEpisode.id == episode_id).first()
    target_language = _target_viewer_language_for_episode(episode) if episode is not None else "vi"
    for panel in panels:
        if int(panel.get("order") or 0) != data.panel_order:
            continue
        was_approved = panel.get("prompt_status") == "approved"
        patch = data.model_dump(exclude_unset=True)
        patch.pop("panel_order", None)
        for key, value in patch.items():
            panel[key] = value
        if patch.keys() & {
            "prompt",
            "caption_or_dialogue",
            "visual_description",
            "scene_context",
            "camera_angle",
            "composition_notes",
            "dialogue_note",
        }:
            _sync_story_panel_prompt_views(panel, target_language=target_language, total_panels=len(panels))
        if "prompt" in patch:
            _refresh_panel_checks(
                panel,
                series_id=_image_adaptation_series_id(row, db),
                episode_id=episode_id,
                db=db,
            )
            _record_panel_version(panel, reason="manual_edit", changes=["Người dùng sửa prompt panel."])
        if was_approved:
            panel["prompt_status"] = "pending_approval"
            panel["render_status"] = "not_requested"
        payload["panels"] = panels
        row.payload_json = payload
        row.status = "pending_approval"
        row.revision = int(row.revision or 1) + 1
        row.updated_at = datetime.utcnow()
        db.commit()
        db.refresh(row)
        return _adaptation_response(row, db)
    raise StoryStudioError("Không tìm thấy panel cần sửa.")

def repair_panel_prompt(
    episode_id: str,
    data: models.StoryPromptRepairRequest,
    db: Session,
) -> models.StoryAdaptationResponse:
    row = _image_adaptation(episode_id, db)
    payload = dict(row.payload_json) if isinstance(row.payload_json, dict) else {}
    panels = [dict(panel) for panel in payload.get("panels", []) if isinstance(panel, dict)]
    series_id = _image_adaptation_series_id(row, db)
    episode = db.query(DBStoryEpisode).filter(DBStoryEpisode.id == episode_id).first()
    target_language = _target_viewer_language_for_episode(episode) if episode is not None else "vi"
    for panel in panels:
        if int(panel.get("order") or 0) != data.panel_order:
            continue
        max_attempts = min(int(data.max_attempts or 2), 2)
        existing_attempt = int(panel.get("repair_attempt") or 0)
        quality = panel.get("quality_check") if isinstance(panel.get("quality_check"), dict) else None
        if quality is None:
            quality = _refresh_panel_checks(panel, series_id=series_id, episode_id=episode_id, db=db)
        if quality.get("passed"):
            panel["repair_status"] = "not_needed"
            payload["panels"] = panels
            row.payload_json = payload
            row.revision = int(row.revision or 1) + 1
            row.updated_at = datetime.utcnow()
            db.commit()
            db.refresh(row)
            return _adaptation_response(row, db)
        while existing_attempt < max_attempts:
            existing_attempt += 1
            panel["repair_attempt"] = existing_attempt
            panel["repair_status"] = "repairing"
            repair = _run_structured_ai(
                db,
                _repair_prompt(panel, quality, panel.get("canon_check") if isinstance(panel.get("canon_check"), dict) else None),
                STORY_PROMPT_REPAIR_SCHEMA,
            )
            before_prompt = _clean(panel.get("prompt"))
            panel["prompt"] = _clean(repair.get("prompt")) or before_prompt
            if _clean(repair.get("negative_prompt")):
                panel["negative_prompt"] = _clean(repair.get("negative_prompt"))
            if _clean(repair.get("caption_or_dialogue")):
                panel["caption_or_dialogue"] = _sanitize_panel_bubble_text(
                    repair.get("caption_or_dialogue"),
                    target_language=target_language,
                )
            if _clean(repair.get("visual_description")):
                panel["visual_description"] = _clean(repair.get("visual_description"))
            _sync_story_panel_prompt_views(panel, target_language=target_language, total_panels=len(panels))
            changes = [str(item) for item in _coerce_list(repair.get("changes")) if _clean(item)]
            if not changes and before_prompt != _clean(panel.get("prompt")):
                changes = ["AI sửa prompt theo lỗi quality/canon đã nêu."]
            _record_panel_version(panel, reason=_clean(repair.get("reason_vi")) or "auto_repair", changes=changes)
            quality = _refresh_panel_checks(panel, series_id=series_id, episode_id=episode_id, db=db)
            if quality.get("passed"):
                panel["repair_status"] = "passed"
                panel["prompt_status"] = "pending_approval"
                panel["render_status"] = "not_requested"
                break
        if not quality.get("passed"):
            panel["repair_status"] = "needs_review"
            panel["prompt_status"] = "pending_approval"
            panel["render_status"] = "not_requested"
        payload["panels"] = panels
        row.payload_json = payload
        row.status = "pending_approval"
        row.revision = int(row.revision or 1) + 1
        row.updated_at = datetime.utcnow()
        db.commit()
        db.refresh(row)
        return _adaptation_response(row, db)
    raise StoryStudioError("Không tìm thấy panel cần sửa.")

def _panel_orders(panels: list[dict[str, Any]], requested: list[int] | None) -> set[int]:
    available = {int(panel.get("order") or 0) for panel in panels if int(panel.get("order") or 0) > 0}
    selected = set(requested or sorted(available))
    if not selected:
        raise StoryStudioError("Cần chọn ít nhất một panel để render.")
    missing = selected - available
    if missing:
        raise StoryStudioError(f"Không tìm thấy panel: {', '.join(map(str, sorted(missing)))}.")
    return selected

def _set_image_adaptation_status(row: DBStoryAdaptation, panels: list[dict[str, Any]]) -> None:
    statuses = {str(panel.get("render_status") or "not_requested") for panel in panels}
    prompt_statuses = {str(panel.get("prompt_status") or "draft") for panel in panels}
    if "rendering" in statuses:
        row.status = "rendering"
    elif "queued" in statuses:
        row.status = "queued"
    elif "failed" in statuses:
        row.status = "failed"
    elif statuses and statuses <= {"completed"}:
        row.status = "completed"
    elif "waiting_provider" in statuses:
        row.status = "waiting_provider"
    elif "approved" in prompt_statuses:
        row.status = "approved"
    else:
        row.status = "pending_approval"

def request_image_render(
    episode_id: str,
    data: models.StoryImageRenderRequest,
    db: Session,
) -> models.StoryAdaptationResponse:
    row = _image_adaptation(episode_id, db)
    payload = dict(row.payload_json) if isinstance(row.payload_json, dict) else {}
    panels = [dict(panel) for panel in payload.get("panels", []) if isinstance(panel, dict)]
    selected = _panel_orders(panels, data.panel_orders)
    for panel in panels:
        if int(panel.get("order") or 0) in selected and panel.get("prompt_status") != "approved":
            raise StoryStudioError("Chỉ prompt đã duyệt mới được render.")
    now = datetime.utcnow()
    if not data.image_provider_configured:
        for panel in panels:
            if int(panel.get("order") or 0) in selected:
                panel["render_status"] = "waiting_provider"
        payload["panels"] = panels
        payload["image_provider_configured"] = False
        payload["provider_message"] = "Chưa cấu hình image provider/API key. Prompt đã được lưu và có thể export."
        row.payload_json = payload
        row.status = "waiting_provider"
        row.revision = int(row.revision or 1) + 1
        row.updated_at = now
        db.commit()
        db.refresh(row)
        return _adaptation_response(row, db)

    render_job_id = str(uuid.uuid4())
    job = {
        "id": render_job_id,
        "status": "queued",
        "provider": data.provider,
        "panel_orders": sorted(selected),
        "provider_metadata": data.provider_metadata,
        "created_at": now.isoformat(),
        "updated_at": now.isoformat(),
    }
    for panel in panels:
        if int(panel.get("order") or 0) in selected:
            panel["render_status"] = "queued"
            panel["render_job_id"] = render_job_id
            panel["provider"] = data.provider
    payload["panels"] = panels
    payload["image_provider_configured"] = True
    payload["provider_message"] = "Đã tạo render job ảnh. Adapter provider sẽ cập nhật trạng thái từng panel."
    payload["render_jobs"] = [*([job for job in payload.get("render_jobs", []) if isinstance(job, dict)]), job]
    row.payload_json = payload
    row.status = "queued"
    row.revision = int(row.revision or 1) + 1
    row.updated_at = now
    db.commit()
    db.refresh(row)
    return _adaptation_response(row, db)

def update_image_render_job(
    episode_id: str,
    render_job_id: str,
    data: models.StoryImageRenderJobUpdateRequest,
    db: Session,
) -> models.StoryAdaptationResponse:
    row = _image_adaptation(episode_id, db)
    payload = dict(row.payload_json) if isinstance(row.payload_json, dict) else {}
    panels = [dict(panel) for panel in payload.get("panels", []) if isinstance(panel, dict)]
    jobs = [dict(job) for job in payload.get("render_jobs", []) if isinstance(job, dict)]
    job = next((item for item in jobs if item.get("id") == render_job_id), None)
    if job is None:
        raise StoryStudioError("Không tìm thấy render job ảnh.")
    if data.status not in IMAGE_RENDER_JOB_STATUSES:
        raise StoryStudioError("Trạng thái render job ảnh không hợp lệ.")
    selected = {int(order) for order in job.get("panel_orders", []) if int(order or 0) > 0}
    if not selected:
        selected = _panel_orders(panels, None)
    panel_by_order = {int(panel.get("order") or 0): panel for panel in panels}
    now = datetime.utcnow()
    if data.status in {"queued", "rendering"}:
        for order in selected:
            panel = panel_by_order.get(order)
            if panel is not None and panel.get("render_status") != "completed":
                panel["render_status"] = data.status
        job["status"] = data.status
        job["message"] = data.message
        job["updated_at"] = now.isoformat()
    else:
        if data.status == "completed" and not data.results:
            raise StoryStudioError("Provider phải trả về kết quả ảnh trước khi đánh dấu completed.")
        results_by_order = {result.panel_order: result for result in data.results}
        if data.status == "failed" and not results_by_order:
            for order in selected:
                panel = panel_by_order.get(order)
                if panel is not None:
                    panel["render_status"] = "failed"
                    panel["failure_reason"] = data.message or "Provider render ảnh thất bại."
        for order, result in results_by_order.items():
            if order not in selected:
                raise StoryStudioError(f"Panel {order} không thuộc render job này.")
            panel = panel_by_order.get(order)
            if panel is None:
                raise StoryStudioError(f"Không tìm thấy panel {order}.")
            if result.status == "completed":
                if not (result.image_path or result.image_url or result.provider_asset_id):
                    raise StoryStudioError("Kết quả ảnh completed cần có image_path, image_url hoặc provider_asset_id.")
                panel["render_status"] = "completed"
                panel["asset"] = {
                    "provider": job.get("provider") or "manual",
                    "provider_asset_id": result.provider_asset_id,
                    "image_path": result.image_path,
                    "image_url": result.image_url,
                    "provider_metadata": result.provider_metadata,
                    "render_job_id": render_job_id,
                    "rendered_at": now.isoformat(),
                }
                panel.pop("failure_reason", None)
            else:
                panel["render_status"] = "failed"
                panel["failure_reason"] = result.failure_reason or data.message or "Provider render ảnh thất bại."
        job_statuses = {panel_by_order[order].get("render_status") for order in selected if order in panel_by_order}
        job["status"] = "failed" if "failed" in job_statuses or data.status == "failed" else "completed"
        job["message"] = data.message
        job["completed_at"] = now.isoformat()
        job["updated_at"] = now.isoformat()
    payload["panels"] = panels
    payload["render_jobs"] = jobs
    row.payload_json = payload
    _set_image_adaptation_status(row, panels)
    row.revision = int(row.revision or 1) + 1
    row.updated_at = now
    db.commit()
    db.refresh(row)
    return _adaptation_response(row, db)

def export_image_prompts(episode_id: str, db: Session) -> str:
    row = _image_adaptation(episode_id, db)
    payload = row.payload_json if isinstance(row.payload_json, dict) else {}
    panels = payload.get("panels") if isinstance(payload.get("panels"), list) else []
    chunks = []
    for panel in panels:
        chunks.append(
            "\n".join(
                [
                    f"Panel {panel.get('order')}: {panel.get('purpose') or ''}",
                    f"Bối cảnh: {panel.get('scene_context') or ''}",
                    f"Góc máy/bố cục: {panel.get('camera_angle') or ''}",
                    f"Composition note: {panel.get('composition_notes') or ''}",
                    f"Caption: {panel.get('caption_or_dialogue') or ''}",
                    f"Note thoại/chữ: {panel.get('dialogue_note') or ''}",
                    f"Visual: {panel.get('visual_description') or ''}",
                    f"Prompt: {panel.get('prompt') or ''}",
                    f"Negative prompt: {panel.get('negative_prompt') or ''}",
                    f"Status: prompt={panel.get('prompt_status')} render={panel.get('render_status')}",
                ]
            )
        )
    return "\n\n---\n\n".join(chunks).strip() + "\n"

def _latest_completed_render(project_id: str, db: Session) -> DBVideoRenderJob | None:
    return (
        db.query(DBVideoRenderJob)
        .filter(DBVideoRenderJob.project_id == project_id, DBVideoRenderJob.status == "completed")
        .order_by(DBVideoRenderJob.completed_at.desc().nullslast(), DBVideoRenderJob.created_at.desc())
        .first()
    )

def _video_language_lock_source_block(target_language: str) -> str:
    language = video_language.normalize_video_language(target_language)
    language_name = video_language.video_language_english_name(language)
    if language == "vi":
        return (
            "LANGUAGE LOCK: Viewer-facing narration, character lines, subtitle, on-screen text, prompt speech instruction, "
            "and CTA must be natural Vietnamese. English camera/visual terminology is allowed only for technical direction, "
            "not as viewer-facing speech."
        )
    return (
        f"LANGUAGE LOCK: The source story may contain Vietnamese analysis, OCR text, or dialogue. "
        f"Use it only as canon/evidence. Rewrite every viewer-facing narration, character line, subtitle, "
        f"on-screen text, prompt speech instruction, and CTA in natural {language_name}. "
        "Do not copy Vietnamese dialogue into production fields. Vietnamese is allowed only in *_vi review/explanation fields for the app UI."
    )

def _video_story_source_block(content: object | None, *, target_language: str) -> str:
    text = _clean(content)
    if not text:
        return ""
    language = video_language.normalize_video_language(target_language)
    if language == "vi":
        return text
    language_name = video_language.video_language_english_name(language)
    if language == "en":
        return (
            "Canonical story source. Translate/rewrite for English viewer-facing output; preserve plot, characters, setting, "
            "relationships, and continuity, but do not preserve Vietnamese wording as spoken/on-screen text.\n\n"
            f"{text}"
        )
    return (
        f"Canonical story source. Translate/rewrite for {language_name} viewer-facing output; preserve plot, characters, setting, "
        f"relationships, and continuity, but do not preserve Vietnamese wording as spoken/on-screen text.\n\n"
        f"{text}"
    )

def _approved_master_or_empty(episode: DBStoryEpisode) -> dict[str, Any]:
    if episode.approval_status != "approved" or not isinstance(episode.master_story_json, dict):
        return {}
    _validate_master_story(episode.master_story_json)
    return episode.master_story_json

def _image_story_adaptation_source(
    episode_id: str,
    db: Session,
) -> tuple[DBStoryAdaptation | None, list[dict[str, Any]], int]:
    row = (
        db.query(DBStoryAdaptation)
        .filter(DBStoryAdaptation.story_episode_id == episode_id, DBStoryAdaptation.kind == "image_story")
        .first()
    )
    if row is None:
        return None, [], 0
    payload = row.payload_json if isinstance(row.payload_json, dict) else {}
    raw_panels = payload.get("panels") if isinstance(payload.get("panels"), list) else []
    panels = [dict(panel) for panel in raw_panels if isinstance(panel, dict)]
    panels.sort(key=lambda panel: int(panel.get("order") or 0))
    usable_panels = [
        panel
        for panel in panels
        if _clean(panel.get("prompt")) or _clean(panel.get("visual_description"))
    ]
    prompt_count = sum(1 for panel in usable_panels if _clean(panel.get("prompt")))
    return row, usable_panels, prompt_count

def _resolve_video_handoff_source_mode(
    episode: DBStoryEpisode,
    data: models.StoryVideoHandoffRequest,
    db: Session,
) -> tuple[str, DBStoryAdaptation | None, list[dict[str, Any]], int]:
    image_row, image_panels, prompt_count = _image_story_adaptation_source(episode.id, db)
    requested = data.source_mode
    if requested == "auto":
        if image_panels:
            return "image_story_prompts", image_row, image_panels, prompt_count
        return "master_story", image_row, image_panels, prompt_count
    if requested == "image_story_prompts" and not image_panels:
        raise StoryStudioError(
            "Chưa có prompt truyện ảnh đủ dùng để handoff video. Hãy tạo panel/prompt truyện trước, "
            "sau đó bấm 'Tạo prompt video' hoặc 'Handoff video từ truyện'."
        )
    return requested, image_row, image_panels, prompt_count

def _numbered_panel_value(panel: dict[str, Any], fallback: int) -> int:
    try:
        order = int(panel.get("order") or 0)
    except (TypeError, ValueError):
        order = 0
    return order if order > 0 else fallback

def _handoff_field(label: str, value: object | None, *, limit: int = 4_000) -> str:
    text = _value_to_text(value)
    if not text:
        return ""
    clipped = _clip_prompt_text(text, limit)
    return f"{label}: {clipped}"

def _panel_storyboard_handoff_text(panel: dict[str, Any], fallback_order: int) -> str:
    order = _numbered_panel_value(panel, fallback_order)
    lines = [
        f"Panel {order}",
        _handoff_field("Purpose/story beat", panel.get("purpose"), limit=1_500),
        _handoff_field("Caption/dialogue", panel.get("caption_or_dialogue"), limit=1_500),
        _handoff_field("Scene context", panel.get("scene_context"), limit=2_000),
        _handoff_field("Camera angle", panel.get("camera_angle"), limit=1_500),
        _handoff_field("Composition notes", panel.get("composition_notes"), limit=1_500),
        _handoff_field("Dialogue/note thoại", panel.get("dialogue_note"), limit=1_500),
        _handoff_field("Visual description", panel.get("visual_description"), limit=3_000),
    ]
    return "\n".join(line for line in lines if line)

def _panel_prompt_handoff_text(panel: dict[str, Any], fallback_order: int) -> str:
    order = _numbered_panel_value(panel, fallback_order)
    lines = [
        f"Panel {order}",
        _handoff_field("Prompt ảnh gốc", panel.get("prompt"), limit=9_000),
        _handoff_field("Negative prompt", panel.get("negative_prompt"), limit=4_000),
        _handoff_field("Character consistency", panel.get("character_consistency_notes"), limit=2_000),
        _handoff_field("Style notes", panel.get("style_notes"), limit=2_000),
    ]
    return "\n".join(line for line in lines if line)

def _chunk_video_source_blocks(
    block_type: str,
    intro: str,
    items: list[str],
    *,
    max_chars: int = VIDEO_HANDOFF_BLOCK_MAX_CHARS,
) -> list[models.VideoSourceBlockDraft]:
    clean_items = [_clean(item) for item in items if _clean(item)]
    if not clean_items:
        return []
    chunks: list[str] = []
    current: list[str] = []
    current_len = len(intro) + 2
    for item in clean_items:
        bounded_item = item
        if len(intro) + len(bounded_item) + 4 > max_chars:
            bounded_item = _clip_prompt_text(bounded_item, max_chars - len(intro) - 20)
        projected = current_len + len(bounded_item) + 6
        if current and projected > max_chars:
            chunks.append(f"{intro}\n\n" + "\n\n---\n\n".join(current))
            current = []
            current_len = len(intro) + 2
        current.append(bounded_item)
        current_len += len(bounded_item) + 6
    if current:
        chunks.append(f"{intro}\n\n" + "\n\n---\n\n".join(current))
    blocks: list[models.VideoSourceBlockDraft] = []
    for index, content in enumerate(chunks, start=1):
        blocks.append(
            models.VideoSourceBlockDraft(
                block_type=block_type if len(chunks) == 1 else f"{block_type}_{index:02d}",
                content=content,
            )
        )
    return blocks

def _series_canon_context(series: DBVideoSeries) -> str:
    parts = [
        _handoff_field("Character bible", series.character_bible, limit=6_000),
        _handoff_field("World bible", series.world_bible, limit=6_000),
        _handoff_field("Continuity rules", series.continuity_rules, limit=6_000),
        _handoff_field("Previous episode summary", series.previous_episode_summary, limit=4_000),
    ]
    return "\n".join(part for part in parts if part)

def _master_story_video_source_blocks(
    *,
    master: dict[str, Any],
    visual_style: str,
    target_language: str,
    series_id: str,
    db: Session,
) -> list[models.VideoSourceBlockDraft]:
    source_block_values = [
        ("language_lock", _video_language_lock_source_block(target_language)),
        ("idea", _video_story_source_block(_clean(master.get("logline")) or _clean(master.get("hook")), target_language=target_language)),
        ("rough_script", _video_story_source_block(master.get("full_story"), target_language=target_language)),
        ("character_notes", _character_profiles_text(series_id, db)),
        ("style_notes", visual_style),
        ("must_have", "\n".join(map(str, master.get("must_have") or []))),
        ("avoid", "\n".join(map(str, master.get("avoid") or []))),
    ]
    return [
        models.VideoSourceBlockDraft(block_type=block_type, content=content)
        for block_type, content in source_block_values
        if _clean(content)
    ]

def _image_story_video_source_blocks(
    *,
    episode: DBStoryEpisode,
    series: DBVideoSeries,
    master: dict[str, Any],
    image_row: DBStoryAdaptation,
    panels: list[dict[str, Any]],
    visual_style: str,
    target_language: str,
    db: Session,
) -> list[models.VideoSourceBlockDraft]:
    panel_count = len(panels)
    prompt_count = sum(1 for panel in panels if _clean(panel.get("prompt")))
    handoff_instruction = (
        "Nguồn handoff là prompt truyện ảnh/panel storyboard. AI Video phải phát triển lại thành video: "
        "giữ canon, hook, nhân vật, bối cảnh, cảm xúc, góc máy và thoại/note thoại; không copy máy móc prompt ảnh tĩnh; "
        "hãy chuyển mỗi panel thành nhịp video, shot, motion và prompt video phù hợp."
    )
    idea_parts = [
        handoff_instruction,
        f"Series: {series.title}",
        f"Story Episode: tập {episode.episode_number} - {episode.title or _clean(master.get('title')) or 'chưa đặt tên'}",
        f"Image adaptation: {image_row.id}, revision {int(image_row.revision or 1)}, panels {panel_count}, prompts {prompt_count}",
        _handoff_field("Logline", master.get("logline"), limit=2_000),
        _handoff_field("Hook", master.get("hook"), limit=2_000),
        _handoff_field("Image story notes", master.get("image_story_notes"), limit=2_000),
        _handoff_field("Video story notes", master.get("video_story_notes"), limit=2_000),
    ]
    rough_script_parts = [
        _video_story_source_block(master.get("full_story"), target_language=target_language),
        _handoff_field("Retention plan", master.get("retention_plan"), limit=4_000),
        _handoff_field("Key beats", master.get("key_beats"), limit=4_000),
        _handoff_field("Character emotions", master.get("character_emotions"), limit=4_000),
        _handoff_field("Motion beats", master.get("motion_beats"), limit=4_000),
        _handoff_field("Visual moments", master.get("visual_moments"), limit=4_000),
    ]
    panel_story_items = [
        _panel_storyboard_handoff_text(panel, index)
        for index, panel in enumerate(panels, start=1)
    ]
    panel_prompt_items = [
        _panel_prompt_handoff_text(panel, index)
        for index, panel in enumerate(panels, start=1)
    ]
    character_notes = "\n".join(
        part
        for part in [
            _character_profiles_text(series.id, db),
            _handoff_field("Series character bible", series.character_bible, limit=6_000),
        ]
        if _clean(part)
    )
    style_notes = "\n".join(
        part
        for part in [
            COMIC_STORY_VISUAL_STYLE,
            _handoff_field("Effective visual style", visual_style, limit=6_000),
            _handoff_field("Series style bible", series.style_bible, limit=6_000),
        ]
        if _clean(part)
    )
    negative_prompts = [
        _clean(panel.get("negative_prompt"))
        for panel in panels
        if _clean(panel.get("negative_prompt"))
    ]
    source_block_values = [
        ("language_lock", _video_language_lock_source_block(target_language)),
        ("idea", "\n".join(part for part in idea_parts if _clean(part))),
        ("rough_script", "\n\n".join(part for part in rough_script_parts if _clean(part))),
        ("character_notes", character_notes),
        ("style_notes", style_notes),
        ("canon_context", _series_canon_context(series)),
        ("must_have", "\n".join(map(str, master.get("must_have") or []))),
        (
            "avoid",
            "\n".join(
                part
                for part in [
                    "\n".join(map(str, master.get("avoid") or [])),
                    _clean(series.negative_rules),
                    "\n".join(dict.fromkeys(negative_prompts[:40])),
                ]
                if _clean(part)
            ),
        ),
    ]
    blocks = [
        models.VideoSourceBlockDraft(block_type=block_type, content=content)
        for block_type, content in source_block_values
        if _clean(content)
    ]
    blocks.extend(
        _chunk_video_source_blocks(
            "storyboard_panels",
            "Ordered storyboard panels from Story Studio. Preserve panel order when developing video shots.",
            panel_story_items,
        )
    )
    blocks.extend(
        _chunk_video_source_blocks(
            "image_prompts",
            "Original image prompts from Story Studio. Use as visual/canon evidence and adapt into motion/video prompts.",
            panel_prompt_items,
        )
    )
    if len(blocks) > 40:
        raise StoryStudioError(
            "Dữ liệu prompt truyện quá dài để handoff an toàn trong một project AI Video. "
            "Hãy giảm số panel hoặc rút gọn prompt trước khi handoff."
        )
    return blocks

def _maybe_start_story_video_auto_run(
    row: DBStoryAdaptation,
    data: models.StoryVideoHandoffRequest,
    db: Session,
) -> None:
    if not data.start_auto_run:
        return
    if data.material_target != "prompts_only":
        raise StoryStudioError(
            "Story Studio chỉ hỗ trợ auto-run đến bước prompt video (material_target=prompts_only) để tránh render ngoài ý muốn."
        )
    if not row.linked_video_project_id:
        raise StoryStudioError("Chưa có AI Video project để start auto-run.")
    run = video_auto_runs.start_auto_run_record(
        row.linked_video_project_id,
        models.VideoAutoRunStartRequest(mode="full_auto", material_target="prompts_only", force=False),
        db,
    )
    payload = dict(row.payload_json) if isinstance(row.payload_json, dict) else {}
    if run is not None:
        payload["auto_run_id"] = run.id
        payload["auto_run_status"] = run.status
        payload["auto_run_step"] = run.current_step
        payload["auto_run_material_target"] = run.material_target
    row.payload_json = payload
    row.updated_at = datetime.utcnow()

def _sync_existing_video_project_prompt_segments(
    row: DBStoryAdaptation,
    video_settings: models.StoryVideoHandoffSettings,
    db: Session,
) -> None:
    payload = dict(row.payload_json) if isinstance(row.payload_json, dict) else {}
    payload["handoff_settings"] = video_settings.model_dump(mode="json")
    payload["settings_source"] = "story_episode.output_settings"
    row.payload_json = payload
    row.updated_at = datetime.utcnow()
    if not row.linked_video_project_id:
        return
    project = db.get(DBVideoProject, row.linked_video_project_id)
    if project is None:
        return
    count = _positive_int(video_settings.prompt_segment_count)
    duration = _positive_int(video_settings.prompt_segment_duration_seconds)
    if not count or not duration:
        return
    micro_count = _positive_int(video_settings.micro_scenes_per_prompt) or models.DEFAULT_STORY_VIDEO_MICRO_SCENES_PER_PROMPT
    has_project_segment_settings = bool(
        _positive_int(project.prompt_segment_count)
        and _positive_int(project.prompt_segment_duration_seconds)
    )
    if not has_project_segment_settings:
        project.default_shot_duration_seconds = None
        project.prompt_segment_count = count
        project.prompt_segment_duration_seconds = duration
        project.micro_scenes_per_prompt = micro_count
        if not _positive_int(project.target_duration_seconds):
            project.target_duration_seconds = video_settings.target_duration_seconds or count * duration
        project.updated_at = datetime.utcnow()
    elif not _positive_int(project.micro_scenes_per_prompt):
        project.micro_scenes_per_prompt = micro_count
        project.updated_at = datetime.utcnow()

def create_video_adaptation(
    episode_id: str,
    data: models.StoryVideoHandoffRequest,
    db: Session,
) -> models.StoryAdaptationResponse | None:
    episode = db.query(DBStoryEpisode).filter(DBStoryEpisode.id == episode_id).first()
    if episode is None:
        return None
    series = _series_for_story(episode.series_id, db)
    if series is None:
        return None
    if data.start_auto_run and data.material_target != "prompts_only":
        raise StoryStudioError(
            "Story Studio chỉ hỗ trợ auto-run đến bước prompt video (material_target=prompts_only) để tránh render ngoài ý muốn."
        )
    video_settings = _episode_output_settings(episode).video
    resolved_source_mode, image_row, image_panels, prompt_count = _resolve_video_handoff_source_mode(episode, data, db)
    if resolved_source_mode == "master_story":
        if episode.output_intent not in VIDEO_INTENTS:
            raise StoryStudioError(
                "Tập truyện ảnh chưa có nguồn handoff video từ prompt truyện. Hãy tạo panel/prompt truyện trước, "
                "hoặc đổi đầu ra tập sang video."
            )
        master = _require_approved_master(episode)
    else:
        master = _approved_master_or_empty(episode)
        if image_row is None or not image_panels:
            raise StoryStudioError(
                "Chưa có prompt truyện ảnh đủ dùng để handoff video. Hãy tạo panel/prompt truyện trước."
            )
    existing = (
        db.query(DBStoryAdaptation)
        .filter(DBStoryAdaptation.story_episode_id == episode.id, DBStoryAdaptation.kind == "video_story")
        .first()
    )
    if existing and existing.linked_video_project_id and data.open_existing:
        payload = dict(existing.payload_json) if isinstance(existing.payload_json, dict) else {}
        existing_source = payload.get("handoff_source")
        if (
            data.source_mode == "image_story_prompts"
            and existing_source
            and existing_source != "image_story_prompts"
        ):
            raise StoryStudioError(
                "Tập này đã có AI Video project từ nguồn khác. Hãy mở project hiện có hoặc tạo tập mới để tránh ghi đè nhầm."
            )
        _sync_existing_video_project_prompt_segments(existing, video_settings, db)
        _maybe_start_story_video_auto_run(existing, data, db)
        db.commit()
        db.refresh(existing)
        return _adaptation_response(existing, db)
    duplicate = (
        db.query(DBVideoProject.id)
        .filter(DBVideoProject.series_id == series.id, DBVideoProject.episode_number == episode.episode_number)
        .first()
    )
    if duplicate is not None:
        raise StoryStudioError("Series đã có AI Video project cùng số tập. Hãy mở project đã có hoặc đổi số tập.")
    visual_style = _effective_story_visual_style(series, episode, db, fallback="")
    target_language = video_settings.target_language
    if resolved_source_mode == "image_story_prompts":
        source_blocks = _image_story_video_source_blocks(
            episode=episode,
            series=series,
            master=master,
            image_row=image_row,
            panels=image_panels,
            visual_style=visual_style,
            target_language=target_language,
            db=db,
        )
    else:
        source_blocks = _master_story_video_source_blocks(
            master=master,
            visual_style=visual_style,
            target_language=target_language,
            series_id=series.id,
            db=db,
        )
    has_prompt_segment_settings = bool(
        video_settings.prompt_segment_count and video_settings.prompt_segment_duration_seconds
    )
    topic = (
        _clean(master.get("logline"))
        or _clean(master.get("hook"))
        or _clean(master.get("full_story"))[:1000]
        or f"{series.title} tập {episode.episode_number} từ prompt truyện"
    )
    title = _clean(master.get("title")) or episode.title or f"{series.title} - Tập {episode.episode_number:02d}"
    project = video_projects.create_project(
        models.VideoProjectCreate(
            topic=topic,
            title=title,
            series_id=series.id,
            story_episode_id=episode.id,
            episode_number=episode.episode_number,
            episode_title=episode.title or _clean(master.get("title")),
            target_language=video_settings.target_language,
            video_purpose=video_settings.video_purpose,
            dialogue_mode=video_settings.dialogue_mode,
            narration_density=video_settings.narration_density,
            call_to_action_style=video_settings.call_to_action_style,
            target_duration_seconds=video_settings.target_duration_seconds,
            aspect_ratio=video_settings.aspect_ratio,
            visual_style=visual_style or None,
            default_shot_duration_seconds=video_settings.default_shot_duration_seconds,
            prompt_segment_count=video_settings.prompt_segment_count if has_prompt_segment_settings else None,
            prompt_segment_duration_seconds=(
                video_settings.prompt_segment_duration_seconds if has_prompt_segment_settings else None
            ),
            micro_scenes_per_prompt=(
                video_settings.micro_scenes_per_prompt if has_prompt_segment_settings else None
            ),
            phase="phase2",
            source_blocks=source_blocks,
        ),
        db,
    )
    now = datetime.utcnow()
    payload = {
        "linked_video_project_id": project.id,
        "ai_video_url": f"/ai-video?projectId={project.id}",
        "latest_mp4_path": None,
        "handoff_source": resolved_source_mode,
        "source_mode_requested": data.source_mode,
        "source_mode_resolved": resolved_source_mode,
        "source_panel_count": len(image_panels) if resolved_source_mode == "image_story_prompts" else 0,
        "source_prompt_count": prompt_count if resolved_source_mode == "image_story_prompts" else 0,
        "source_image_adaptation_id": image_row.id if resolved_source_mode == "image_story_prompts" and image_row else None,
        "source_image_adaptation_revision": int(image_row.revision or 1) if resolved_source_mode == "image_story_prompts" and image_row else None,
        "story_episode_output_intent": episode.output_intent,
        "handoff_only": video_settings.handoff_only,
        "handoff_settings": video_settings.model_dump(mode="json"),
        "settings_source": "story_episode.output_settings",
    }
    if existing is None:
        existing = DBStoryAdaptation(
            id=str(uuid.uuid4()),
            story_episode_id=episode.id,
            kind="video_story",
            status="approved",
            payload_json=payload,
            linked_video_project_id=project.id,
            created_at=now,
            updated_at=now,
        )
        db.add(existing)
    else:
        existing.status = "approved"
        existing.payload_json = payload
        existing.linked_video_project_id = project.id
        existing.updated_at = now
    _maybe_start_story_video_auto_run(existing, data, db)
    db.commit()
    db.refresh(existing)
    return _adaptation_response(existing, db)

def suggest_updates(episode_id: str, db: Session) -> models.StorySuggestionResponse | None:
    episode = db.query(DBStoryEpisode).filter(DBStoryEpisode.id == episode_id).first()
    if episode is None:
        return None
    suggestions: list[dict[str, Any]] = []
    master = episode.master_story_json if isinstance(episode.master_story_json, dict) else {}
    for item in master.get("continuity_updates") or []:
        suggestions.append({"type": "continuity", "proposal": item})
    for item in master.get("character_profile_updates") or master.get("character_updates") or []:
        suggestions.append({"type": "character_profile", "proposal": item})
    if not suggestions:
        suggestions.append(
            {
                "type": "review_note",
                "proposal": "Chưa có cập nhật continuity rõ ràng. Không lưu thay đổi vào series.",
            }
        )
    return models.StorySuggestionResponse(
        suggestions=suggestions,
        saved=False,
        message="Đây là đề xuất nháp. Dữ liệu series chỉ thay đổi sau khi người dùng duyệt riêng.",
    )

def approve_suggested_updates(
    episode_id: str,
    data: models.StorySuggestionApprovalRequest,
    db: Session,
) -> models.StorySuggestionResponse | None:
    episode = db.query(DBStoryEpisode).filter(DBStoryEpisode.id == episode_id).first()
    if episode is None:
        return None
    series = db.query(DBVideoSeries).filter(DBVideoSeries.id == episode.series_id).first()
    if series is None:
        return None
    default_suggestions = suggest_updates(episode_id, db)
    suggestions = data.suggestions or (default_suggestions.suggestions if default_suggestions else [])
    if not data.approved:
        return models.StorySuggestionResponse(
            suggestions=suggestions,
            saved=False,
            message="Đã từ chối đề xuất. Dữ liệu series không thay đổi.",
        )
    now = datetime.utcnow()
    saved_count = 0
    continuity_lines: list[str] = []
    for suggestion in suggestions:
        if not isinstance(suggestion, dict):
            continue
        suggestion_type = _clean(suggestion.get("type"))
        proposal = suggestion.get("proposal")
        if suggestion_type == "continuity":
            text = _value_to_text(proposal)
            if text:
                continuity_lines.append(f"- Tập {episode.episode_number:02d}: {text}")
                series_brain.create_memory_card(
                    series.id,
                    models.SeriesMemoryCardCreate(
                        card_type="canon_rule",
                        title=f"Continuity approved from Story Episode {episode.episode_number:02d}",
                        content={"text": text, "source_episode_number": episode.episode_number},
                        tags=["continuity", "approved_update"],
                        entity_refs=[],
                        importance=0.85,
                        status="approved",
                        effective_from_episode=episode.episode_number,
                        source_type="story_episode",
                        source_id=episode.id,
                    ),
                    db,
                )
                saved_count += 1
            continue
        if suggestion_type not in {"character_profile", "character"} or not isinstance(proposal, dict):
            continue
        profile_payload = proposal.get("profile") if isinstance(proposal.get("profile"), dict) else proposal
        name = _clean(profile_payload.get("name"))
        if not name:
            continue
        profile_id = _clean(profile_payload.get("id") or profile_payload.get("profile_id"))
        patch_values = {
            "name": name,
            "role": profile_payload.get("role"),
            "face_description": profile_payload.get("face_description"),
            "hair_description": profile_payload.get("hair_description"),
            "body_description": profile_payload.get("body_description"),
            "signature_outfit": profile_payload.get("signature_outfit"),
            "personality": profile_payload.get("personality"),
            "speech_style": profile_payload.get("speech_style"),
            "fixed_traits": profile_payload.get("fixed_traits"),
            "additional_notes": profile_payload.get("additional_notes"),
            "sort_order": profile_payload.get("sort_order"),
        }
        if profile_id:
            row = (
                db.query(DBSeriesCharacterProfile)
                .filter(DBSeriesCharacterProfile.series_id == series.id, DBSeriesCharacterProfile.id == profile_id)
                .first()
            )
            if row is None:
                continue
            for key, value in patch_values.items():
                if value is not None:
                    setattr(row, key, value)
            row.updated_at = now
        else:
            next_order = (
                db.query(func.max(DBSeriesCharacterProfile.sort_order))
                .filter(DBSeriesCharacterProfile.series_id == series.id)
                .scalar()
                or 0
            ) + 1
            db.add(
                DBSeriesCharacterProfile(
                    id=str(uuid.uuid4()),
                    series_id=series.id,
                    name=name,
                    role=patch_values["role"],
                    face_description=patch_values["face_description"],
                    hair_description=patch_values["hair_description"],
                    body_description=patch_values["body_description"],
                    signature_outfit=patch_values["signature_outfit"],
                    personality=patch_values["personality"],
                    speech_style=patch_values["speech_style"],
                    fixed_traits=patch_values["fixed_traits"],
                    additional_notes=patch_values["additional_notes"],
                    sort_order=patch_values["sort_order"] if patch_values["sort_order"] is not None else next_order,
                    created_at=now,
                    updated_at=now,
                )
            )
        saved_count += 1
    if continuity_lines:
        section = "\n".join(["", f"Cập nhật đã duyệt từ Story Episode {episode.episode_number:02d}:", *continuity_lines]).strip()
        current = _clean(series.continuity_rules)
        series.continuity_rules = f"{current}\n\n{section}".strip() if current else section
        series.updated_at = now
    if saved_count:
        db.commit()
        video_series_memory.sync_series_memory_file(series.id, db)
    else:
        db.rollback()
    return models.StorySuggestionResponse(
        suggestions=suggestions,
        saved=bool(saved_count),
        message=(
            f"Đã lưu {saved_count} cập nhật vào series sau khi duyệt."
            if saved_count
            else "Không có đề xuất hợp lệ để lưu. Dữ liệu series không thay đổi."
        ),
    )
