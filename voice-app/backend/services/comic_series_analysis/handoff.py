"""Series handoff: preview + atomic idempotent commit (§8).

Two gates (design §14):
  1. Analysis approval (an active approval manifest) — "eligible to handoff".
  2. Handoff preview → commit, with per-item decisions and conflict
     resolution. Only ``accepted`` manifest items reach the target.

Commit is idempotent (``idempotency_key`` + payload → one operation) and
transactional: it builds the full ``StoryEpisodeSourceDocument`` + chunks +
assets and the target Series/Episode as one logical write. The result never
touches AI Video — the response carries no ``video_project_id`` (task 8.13).
"""

from __future__ import annotations

import hashlib
import json
import uuid
from datetime import datetime
from typing import Any

from sqlalchemy.orm import Session

from ... import models as api_models
from ...database import (
    ComicAnalysisJob as DBJob,
    ComicDetectedCharacter as DBCharacter,
    ComicDetectedLocation as DBLocation,
    ComicPanel as DBPanel,
    ComicPlotAnalysis as DBPlot,
    ComicSpeechBubble as DBBubble,
    ComicSeriesHandoff as DBHandoff,
    ComicSeriesHandoffItem as DBHandoffItem,
    ComicSourceAsset as DBAsset,
    ComicSourceDocument as DBDoc,
    ComicSourcePage as DBPage,
    ComicSourceVersionRecord as DBVersionRecord,
    StoryEpisode as DBStoryEpisode,
    StoryEpisodeSourceAsset as DBEpAsset,
    StoryEpisodeSourceChunk as DBEpChunk,
    StoryEpisodeSourceDocument as DBEpDoc,
    SeriesCharacterProfile as DBCharacterProfile,
    VideoSeries as DBVideoSeries,
)
from . import approval_manifest
from .contracts import (
    HANDOFF_MAPPING_SCHEMA_VERSION,
    SOURCE_PACKAGE_SCHEMA_VERSION,
    ComicAnalysisError,
)

_TARGET_SERIES_TITLE_FALLBACK_KEY = "__comic_target_series_title"
_OUTPUT_SETTINGS_FALLBACK_KEY = "__comic_story_output_settings"
_MARKET_PROFILE_FALLBACK_KEY = "__comic_story_market_profile"
_LANGUAGE_PROFILE_FALLBACK_KEY = "__comic_story_language_profile"
_SOURCE_INPUT_FALLBACK_KEY = "__comic_story_source_input"

_DEFAULT_MARKET_PROFILE = "global_short"
_DEFAULT_LANGUAGE_PROFILE = "en"
_STORY_OUTPUT_INTENTS = {"truyen_anh", "video_truyen", "ca_hai"}
_COMIC_STORY_STYLE_BIBLE = (
    "Anime/manga/webtoon comic-story look: cinematic manga panel composition, "
    "clean line art, expressive anime faces, consistent character design, "
    "dynamic comic-to-video motion, vertical 9:16 friendly composition, "
    "avoid photorealistic live-action unless the user explicitly asks."
)


# --------------------------------------------------------------------------
# Fingerprints
# --------------------------------------------------------------------------

def _sha(obj) -> str:
    return hashlib.sha256(
        json.dumps(obj, ensure_ascii=False, sort_keys=True).encode("utf-8")
    ).hexdigest()


def target_dependency_fingerprint(db: Session, series_id: str | None) -> str:
    """Revision vector of the target Series + its episodes/profiles (task 8.4a)."""
    if series_id is None:
        return _sha({"target": "new_series"})
    series = db.query(DBVideoSeries).filter(DBVideoSeries.id == series_id).first()
    if series is None:
        raise ComicAnalysisError("COMIC_HANDOFF_TARGET_INVALID", status_code=404)
    episodes = (
        db.query(DBStoryEpisode.id, DBStoryEpisode.revision, DBStoryEpisode.episode_number)
        .filter(DBStoryEpisode.series_id == series_id)
        .all()
    )
    return _sha(
        {
            "series_id": series_id,
            "series_revision": series.revision,
            "series_mode": series.series_mode,
            "episodes": sorted([[e.id, e.revision, e.episode_number] for e in episodes]),
        }
    )


def _preview_fingerprint(
    *,
    analysis_revision: int,
    manifest_hash: str,
    rights_attestation_revision: int,
    development_mode: str,
    target_fingerprint: str,
    target_series_title: str | None,
    output_intent: str,
    output_settings: dict[str, Any],
    market_profile: str,
    language_profile: str,
    source_input: str | None,
    selected_items: list[str],
    conflict_resolutions: dict,
) -> str:
    return _sha(
        {
            "schema": HANDOFF_MAPPING_SCHEMA_VERSION,
            "analysis_revision": analysis_revision,
            "manifest_hash": manifest_hash,
            "rights_attestation_revision": rights_attestation_revision,
            "development_mode": development_mode,
            "target_fingerprint": target_fingerprint,
            "target_series_title": target_series_title,
            "output_intent": output_intent,
            "output_settings": output_settings,
            "market_profile": market_profile,
            "language_profile": language_profile,
            "source_input": source_input,
            "selected_items": sorted(selected_items),
            "conflict_resolutions": conflict_resolutions,
        }
    )


# --------------------------------------------------------------------------
# Preview
# --------------------------------------------------------------------------

def _require_approved(db: Session, job: DBJob):
    manifest = approval_manifest.get_active_manifest(db, job.id)
    if manifest is None:
        raise ComicAnalysisError("COMIC_REVISION_NOT_APPROVED", status_code=409)
    if manifest.analysis_revision != job.analysis_revision:
        raise ComicAnalysisError("COMIC_APPROVAL_STALE", status_code=409)
    return manifest


def _validate_target_series(db: Session, series_id: str) -> DBVideoSeries:
    series = db.query(DBVideoSeries).filter(DBVideoSeries.id == series_id).first()
    if series is None:
        raise ComicAnalysisError("COMIC_HANDOFF_TARGET_INVALID", status_code=404)
    if series.series_mode == "video_story_only":
        raise ComicAnalysisError("COMIC_HANDOFF_TARGET_VIDEO_ONLY", status_code=409)
    return series


def _clean_optional_title(value: str | None) -> str | None:
    if value is None:
        return None
    cleaned = " ".join(str(value).split())
    return cleaned[:160] or None


def _clean_limited_text(value: Any, *, max_length: int) -> str | None:
    if value is None:
        return None
    cleaned = str(value).strip()
    if not cleaned:
        return None
    return cleaned[:max_length]


def _image_size_for_aspect(aspect_ratio: str) -> tuple[int, int]:
    return {
        "9:16": (720, 1280),
        "16:9": (1920, 1080),
        "1:1": (1080, 1080),
        "4:5": (1080, 1350),
    }.get(aspect_ratio, (720, 1280))


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


def _normalize_output_settings(value: Any, *, language_profile: str) -> dict[str, Any]:
    raw = value if isinstance(value, dict) else {}
    defaults = api_models.StoryEpisodeOutputSettings().model_dump(mode="json")
    if not _has_nested_key(raw, "video", "target_language"):
        defaults["video"]["target_language"] = "vi" if language_profile.lower().startswith("vi") else "en"
    aspect = raw.get("image", {}).get("aspect_ratio") if isinstance(raw.get("image"), dict) else None
    if aspect and (not _has_nested_key(raw, "image", "width") or not _has_nested_key(raw, "image", "height")):
        width, height = _image_size_for_aspect(str(aspect))
        defaults["image"]["width"] = width
        defaults["image"]["height"] = height
    try:
        return api_models.StoryEpisodeOutputSettings.model_validate(
            _deep_merge_settings(defaults, raw)
        ).model_dump(mode="json")
    except Exception as exc:
        raise ComicAnalysisError(
            "COMIC_HANDOFF_TARGET_INVALID",
            f"Cấu hình đầu ra Story Studio không hợp lệ: {exc}",
            status_code=400,
        ) from exc


def _validate_output_intent(target_series_mode: str, output_intent: Any) -> str:
    intent = str(output_intent or "truyen_anh").strip() or "truyen_anh"
    if intent not in _STORY_OUTPUT_INTENTS:
        raise ComicAnalysisError("COMIC_HANDOFF_TARGET_INVALID", "Đầu ra Story Studio không hợp lệ.", status_code=400)
    if target_series_mode == "image_story_only" and intent != "truyen_anh":
        raise ComicAnalysisError(
            "COMIC_HANDOFF_TARGET_INVALID",
            "Series truyện ảnh chỉ nhận đầu ra Truyện ảnh.",
            status_code=400,
        )
    if target_series_mode == "hybrid" and intent not in _STORY_OUTPUT_INTENTS:
        raise ComicAnalysisError("COMIC_HANDOFF_TARGET_INVALID", "Đầu ra Story Studio không hợp lệ.", status_code=400)
    return intent


def _handoff_metadata(handoff: DBHandoff) -> dict[str, Any]:
    value = handoff.conflict_resolutions_json or {}
    return value if isinstance(value, dict) else {}


def target_series_title_for_handoff(handoff: DBHandoff) -> str | None:
    direct_value = getattr(handoff, "target_series_title", None)
    cleaned = _clean_optional_title(direct_value)
    if cleaned:
        return cleaned
    return _clean_optional_title(_handoff_metadata(handoff).get(_TARGET_SERIES_TITLE_FALLBACK_KEY))


def output_settings_for_handoff(handoff: DBHandoff) -> dict[str, Any] | None:
    value = _handoff_metadata(handoff).get(_OUTPUT_SETTINGS_FALLBACK_KEY)
    return value if isinstance(value, dict) else None


def market_profile_for_handoff(handoff: DBHandoff) -> str:
    return _clean_limited_text(_handoff_metadata(handoff).get(_MARKET_PROFILE_FALLBACK_KEY), max_length=80) or _DEFAULT_MARKET_PROFILE


def language_profile_for_handoff(handoff: DBHandoff) -> str:
    settings = output_settings_for_handoff(handoff) or {}
    video = settings.get("video") if isinstance(settings.get("video"), dict) else {}
    return (
        _clean_limited_text(_handoff_metadata(handoff).get(_LANGUAGE_PROFILE_FALLBACK_KEY), max_length=20)
        or _clean_limited_text(video.get("target_language"), max_length=20)
        or _DEFAULT_LANGUAGE_PROFILE
    )


def source_input_for_handoff(handoff: DBHandoff) -> str | None:
    return _clean_limited_text(_handoff_metadata(handoff).get(_SOURCE_INPUT_FALLBACK_KEY), max_length=50000)


def build_preview(
    db: Session,
    job_id: str,
    *,
    target_kind: str = "new_series",
    target_series_id: str | None = None,
    target_series_mode: str = "image_story_only",
    target_series_title: str | None = None,
    episode_number: int | None = None,
    episode_title: str | None = None,
    output_intent: str = "truyen_anh",
    output_settings: dict[str, Any] | None = None,
    market_profile: str | None = None,
    language_profile: str | None = None,
    source_input: str | None = None,
    selected_items: list[str] | None = None,
    conflict_resolutions: dict | None = None,
) -> DBHandoff:
    """Create a deterministic, side-effect-free preview (task 8.2, 8.3).

    Writes only a ``ComicSeriesHandoff`` row with status ``previewed`` and its
    items — never Series/Episode/Memory/Reference (design §14).
    """
    job = db.query(DBJob).filter(DBJob.id == job_id).first()
    if job is None:
        raise ComicAnalysisError("COMIC_ANALYSIS_NOT_FOUND", status_code=404)
    manifest = _require_approved(db, job)
    selected_items = selected_items or list(approval_manifest.accepted_item_ids(manifest))
    conflict_resolutions = conflict_resolutions or {}

    if target_series_mode not in ("image_story_only", "hybrid"):
        raise ComicAnalysisError("COMIC_HANDOFF_TARGET_INVALID", "Series mode không hợp lệ cho luồng truyện.")

    target_series_title = _clean_optional_title(target_series_title)
    series = None
    if target_kind == "existing_series":
        if not target_series_id:
            raise ComicAnalysisError("COMIC_HANDOFF_TARGET_INVALID", "Thiếu Series đích.")
        series = _validate_target_series(db, target_series_id)
        target_series_mode = series.series_mode
        target_series_title = None

    output_intent = _validate_output_intent(target_series_mode, output_intent)
    market_profile = _clean_limited_text(market_profile, max_length=80) or _DEFAULT_MARKET_PROFILE
    language_profile = _clean_limited_text(language_profile, max_length=20) or _DEFAULT_LANGUAGE_PROFILE
    normalized_output_settings = _normalize_output_settings(output_settings, language_profile=language_profile)
    source_input = _clean_limited_text(source_input, max_length=50000)

    target_fp = target_dependency_fingerprint(db, target_series_id)

    if episode_number is None:
        episode_number = _next_episode_number(db, target_series_id)

    # Conflict classification for existing series (task 8.3).
    items = _classify_items(
        db, job, manifest, target_series_id, episode_number, selected_items
    )

    preview_fp = _preview_fingerprint(
        analysis_revision=job.analysis_revision,
        manifest_hash=manifest.manifest_hash,
        rights_attestation_revision=manifest.rights_attestation_revision,
        development_mode=manifest.requested_development_mode,
        target_fingerprint=target_fp,
        target_series_title=target_series_title,
        output_intent=output_intent,
        output_settings=normalized_output_settings,
        market_profile=market_profile,
        language_profile=language_profile,
        source_input=source_input,
        selected_items=selected_items,
        conflict_resolutions=conflict_resolutions,
    )

    stored_conflict_resolutions = dict(conflict_resolutions)
    if target_series_title:
        stored_conflict_resolutions[_TARGET_SERIES_TITLE_FALLBACK_KEY] = target_series_title
    stored_conflict_resolutions[_OUTPUT_SETTINGS_FALLBACK_KEY] = normalized_output_settings
    stored_conflict_resolutions[_MARKET_PROFILE_FALLBACK_KEY] = market_profile
    stored_conflict_resolutions[_LANGUAGE_PROFILE_FALLBACK_KEY] = language_profile
    if source_input:
        stored_conflict_resolutions[_SOURCE_INPUT_FALLBACK_KEY] = source_input

    handoff_kwargs = {
        "job_id": job.id,
        "analysis_revision": job.analysis_revision,
        "approval_manifest_id": manifest.id,
        "approval_manifest_hash": manifest.manifest_hash,
        "rights_attestation_revision": manifest.rights_attestation_revision,
        "development_mode": manifest.requested_development_mode,
        "target_kind": target_kind,
        "target_series_id": target_series_id,
        "target_series_mode": target_series_mode,
        "episode_number": episode_number,
        "episode_title": episode_title or job.title,
        "output_intent": output_intent,
        "target_dependency_fingerprint": target_fp,
        "preview_fingerprint": preview_fp,
        "mapping_schema_version": HANDOFF_MAPPING_SCHEMA_VERSION,
        "item_decisions_json": [i for i in items],
        "conflict_resolutions_json": stored_conflict_resolutions,
        "status": "previewed",
    }
    if hasattr(DBHandoff, "target_series_title"):
        handoff_kwargs["target_series_title"] = target_series_title

    handoff = DBHandoff(**handoff_kwargs)
    db.add(handoff)
    db.flush()
    for item in items:
        db.add(
            DBHandoffItem(
                handoff_id=handoff.id,
                item_type=item["item_type"],
                source_ref_id=item.get("source_ref_id"),
                decision=item["decision"],
                target_ref_type=item.get("target_ref_type"),
                target_ref_id=item.get("target_ref_id"),
                expected_target_revision=item.get("expected_target_revision"),
                match_confidence=item.get("match_confidence"),
                status="previewed",
            )
        )
    db.commit()
    db.refresh(handoff)
    return handoff


def _next_episode_number(db: Session, series_id: str | None) -> int:
    if series_id is None:
        return 1
    highest = (
        db.query(DBStoryEpisode.episode_number)
        .filter(DBStoryEpisode.series_id == series_id)
        .order_by(DBStoryEpisode.episode_number.desc())
        .first()
    )
    return (highest[0] + 1) if highest and highest[0] else 1


def _classify_items(db, job, manifest, target_series_id, episode_number, selected_items) -> list[dict]:
    """Classify each handoff item as create/update/merge/skip/duplicate/conflict."""
    items: list[dict] = []
    # The episode item.
    episode_decision = "create"
    if target_series_id is not None:
        dup = (
            db.query(DBStoryEpisode.id)
            .filter(
                DBStoryEpisode.series_id == target_series_id,
                DBStoryEpisode.episode_number == episode_number,
            )
            .first()
        )
        if dup is not None:
            episode_decision = "conflict"  # duplicate episode number
    items.append(
        {
            "item_type": "episode",
            "source_ref_id": job.id,
            "decision": episode_decision,
            "target_ref_type": "story_episode",
        }
    )
    # Accepted characters → create (existing-series matching left to user).
    for item_id in selected_items:
        # Only expose accepted items (unreviewed/excluded excluded by manifest).
        items.append(
            {
                "item_type": "accepted_item",
                "source_ref_id": item_id,
                "decision": "create",
            }
        )
    return items


# --------------------------------------------------------------------------
# Commit (idempotent, transactional)
# --------------------------------------------------------------------------

def commit_handoff(
    db: Session,
    handoff_id: str,
    *,
    idempotency_key: str,
) -> DBHandoff:
    """Commit a previewed handoff into a Series + full Source Document.

    Idempotent: replaying the same key returns the existing committed result.
    Rejects the same key with a different payload (task 8.11, 8.16).
    """
    handoff = db.query(DBHandoff).filter(DBHandoff.id == handoff_id).first()
    if handoff is None:
        raise ComicAnalysisError("COMIC_ANALYSIS_NOT_FOUND", status_code=404)

    # Idempotency: an existing committed handoff with this key + same preview
    # fingerprint returns its result.
    if handoff.idempotency_key and handoff.idempotency_key != idempotency_key:
        raise ComicAnalysisError("COMIC_HANDOFF_IDEMPOTENCY_CONFLICT", status_code=409)
    if handoff.status == "committed":
        return handoff

    existing = (
        db.query(DBHandoff)
        .filter(
            DBHandoff.idempotency_key == idempotency_key,
            DBHandoff.status == "committed",
        )
        .first()
    )
    if existing is not None:
        if existing.preview_fingerprint != handoff.preview_fingerprint:
            raise ComicAnalysisError("COMIC_HANDOFF_IDEMPOTENCY_CONFLICT", status_code=409)
        return existing

    job = db.query(DBJob).filter(DBJob.id == handoff.job_id).first()
    if job is None:
        raise ComicAnalysisError("COMIC_ANALYSIS_NOT_FOUND", status_code=404)

    # Stale-preview guard: target must not have changed since preview.
    current_target_fp = target_dependency_fingerprint(db, handoff.target_series_id)
    if current_target_fp != handoff.target_dependency_fingerprint:
        raise ComicAnalysisError("COMIC_HANDOFF_PREVIEW_STALE", status_code=409)

    # Conflict must be resolved before commit.
    for item in handoff.item_decisions_json or []:
        if item.get("decision") == "conflict":
            resolution = (handoff.conflict_resolutions_json or {}).get(item.get("source_ref_id"))
            if not resolution:
                raise ComicAnalysisError("COMIC_HANDOFF_CONFLICT_UNRESOLVED", status_code=409)

    handoff.idempotency_key = idempotency_key
    handoff.operation_id = handoff.operation_id or str(uuid.uuid4())
    handoff.status = "committing"
    db.flush()

    try:
        series = _resolve_or_create_series(db, handoff, job)
        episode = _create_episode(db, handoff, job, series)
        source_doc = _create_source_document(db, handoff, job, episode)
        _apply_approved_series_context(db, handoff, job, series)
        episode.current_source_document_id = source_doc.id
        episode.development_mode = handoff.development_mode
        episode.rights_attestation_revision = handoff.rights_attestation_revision

        _record_version(db, handoff, job, series.id, "series", series.id)
        _record_version(db, handoff, job, series.id, "episode", episode.id)

        handoff.created_series_id = series.id
        handoff.created_story_episode_id = episode.id
        handoff.created_source_document_id = source_doc.id
        handoff.status = "committed"
        handoff.result_json = {
            "series_id": series.id,
            "story_episode_id": episode.id,
            "source_document_id": source_doc.id,
            "handoff_id": handoff.id,
            "story_studio_url": f"/story-studio?seriesId={series.id}&episodeId={episode.id}",
        }
        db.commit()
        db.refresh(handoff)
        return handoff
    except ComicAnalysisError:
        db.rollback()
        handoff = db.query(DBHandoff).filter(DBHandoff.id == handoff_id).first()
        if handoff:
            handoff.status = "failed"
            db.commit()
        raise
    except Exception as exc:
        db.rollback()
        handoff = db.query(DBHandoff).filter(DBHandoff.id == handoff_id).first()
        if handoff:
            handoff.status = "failed"
            handoff.failure_reason = str(exc)
            handoff.error_code = "COMIC_HANDOFF_COMMIT_FAILED"
            db.commit()
        raise ComicAnalysisError("COMIC_HANDOFF_COMMIT_FAILED", str(exc), status_code=500) from exc


def _resolve_or_create_series(db, handoff, job) -> DBVideoSeries:
    if handoff.target_kind == "existing_series":
        series = _validate_target_series(db, handoff.target_series_id)
        return series
    series = DBVideoSeries(
        title=target_series_title_for_handoff(handoff) or job.title or "Truyện mới",
        series_mode=handoff.target_series_mode or "image_story_only",
        style_bible=_COMIC_STORY_STYLE_BIBLE,
    )
    db.add(series)
    db.flush()
    return series


def _source_digest(source: str | None) -> str | None:
    text = _clean(source)
    if not text:
        return None
    first_line = text.splitlines()[0].strip()
    suffix = f" ({len(text)} ký tự)" if len(text) > len(first_line) else ""
    return f"{first_line[:220]}{suffix}"


def _analysis_source_input(handoff, job) -> str | None:
    """Compact task payload for Story Studio context selection.

    The full chapter still lives in StoryEpisodeSourceDocument/chunks. This
    field gives Series Brain and the candidate prompt a concise, searchable
    task payload instead of an empty manual source_input.
    """
    optimized = (job.analysis_package_json or {}).get("optimized_script") or {}
    plot = (job.analysis_package_json or {}).get("plot") or {}
    parts: list[str] = []
    user_notes = source_input_for_handoff(handoff)
    if user_notes:
        parts.append(f"Ghi chú cấu hình của người dùng:\n{user_notes}")
    if _clean(optimized.get("title")):
        parts.append(f"Tiêu đề tối ưu: {optimized.get('title')}")
    if _clean(optimized.get("synopsis")):
        parts.append(f"Tóm tắt tối ưu:\n{optimized.get('synopsis')}")
    if _clean(optimized.get("hook")):
        parts.append(f"Hook:\n{optimized.get('hook')}")
    beats = optimized.get("plot_beats") or plot.get("plot_beats") or []
    if isinstance(beats, list) and beats:
        parts.append("Plot beats:\n" + "\n".join(f"- {item}" for item in beats[:24] if _clean(item)))
    if _clean(optimized.get("full_story")):
        parts.append(f"Kịch bản tối ưu từ phân tích web/comic:\n{optimized.get('full_story')}")
    text = "\n\n".join(part for part in parts if _clean(part))
    return text[:50000] if text else None


def _create_episode(db, handoff, job, series) -> DBStoryEpisode:
    language_profile = language_profile_for_handoff(handoff)
    source_input = _analysis_source_input(handoff, job)
    output_settings = _normalize_output_settings(
        output_settings_for_handoff(handoff),
        language_profile=language_profile,
    )
    episode = DBStoryEpisode(
        series_id=series.id,
        episode_number=handoff.episode_number or _next_episode_number(db, series.id),
        title=handoff.episode_title or job.title,
        output_intent=handoff.output_intent or "truyen_anh",
        market_profile=market_profile_for_handoff(handoff),
        language_profile=language_profile,
        source_input=source_input,
        source_digest=_source_digest(source_input),
        output_settings_json=output_settings,
        approval_status="draft",
    )
    db.add(episode)
    db.flush()
    return episode


def _create_source_document(db, handoff, job, episode) -> DBEpDoc:
    """Build the full StoryEpisodeSourceDocument + chunks + assets (task 8.9).

    Carries the entire approved chapter content — never just a synopsis or a
    truncated ``source_input`` (spec: "toàn bộ nội dung chương").
    """
    doc = db.query(DBDoc).filter(DBDoc.id == job.current_source_document_id).first()
    pages = (
        db.query(DBPage)
        .filter(DBPage.document_id == doc.id)
        .order_by(DBPage.page_order)
        .all()
        if doc
        else []
    )
    assets = (
        db.query(DBAsset)
        .filter(DBAsset.document_id == doc.id)
        .order_by(DBAsset.asset_order)
        .all()
        if doc
        else []
    )

    text_pages = [p for p in pages if p.extracted_text]
    full_text = "\n\n".join(p.extracted_text for p in text_pages)
    revision = int(handoff.analysis_revision or job.analysis_revision or 0)
    panels = (
        db.query(DBPanel)
        .filter(DBPanel.job_id == job.id, DBPanel.analysis_revision == revision)
        .order_by(DBPanel.reading_order)
        .all()
    )
    bubbles = (
        db.query(DBBubble)
        .filter(DBBubble.job_id == job.id, DBBubble.analysis_revision == revision)
        .order_by(DBBubble.reading_order)
        .all()
    )
    characters = db.query(DBCharacter).filter_by(job_id=job.id, analysis_revision=revision).all()
    locations = db.query(DBLocation).filter_by(job_id=job.id, analysis_revision=revision).all()
    plot = db.query(DBPlot).filter_by(job_id=job.id, analysis_revision=revision).first()
    optimized = (job.analysis_package_json or {}).get("optimized_script") or {}
    optimized_story = _clean(optimized.get("full_story"))
    structured_text = _structured_analysis_text(panels, bubbles, characters, locations, plot)
    approved_text = optimized_story or full_text or structured_text or None
    normalized_text = optimized_story or structured_text or None
    synopsis = _clean(optimized.get("synopsis")) or (plot.synopsis if plot else None)
    plot_structure = {
        "beats": optimized.get("plot_beats") or (plot.plot_beats_json if plot else []),
        "relationships": plot.relationships_json if plot else [],
        "end_state": plot.end_state_json if plot else None,
        "characters": [_character_payload(item) for item in characters],
        "locations": [_location_payload(item) for item in locations],
        "optimized_script": optimized or None,
    }

    ep_doc = DBEpDoc(
        story_episode_id=episode.id,
        revision=1,
        approval_status="approved",
        schema_version=SOURCE_PACKAGE_SCHEMA_VERSION,
        source_kind="comic_analysis",
        comic_job_id=job.id,
        comic_analysis_revision=job.analysis_revision,
        comic_source_revision=doc.revision if doc else None,
        handoff_id=handoff.id,
        title=job.title,
        synopsis=synopsis,
        plot_structure_json=plot_structure,
        raw_extracted_text=full_text or None,
        ai_normalized_text=normalized_text,
        approved_text=approved_text,
        coverage_metrics_json=doc.coverage_metrics_json if doc else None,
        limitations_json=doc.limitations_json if doc else None,
        provenance_json={
            "source_url": doc.requested_url if doc else None,
            "final_url": doc.final_url if doc else None,
            "content_hash": doc.content_hash if doc else None,
            "fetched_at": doc.fetched_at.isoformat() if doc and doc.fetched_at else None,
            "analysis_revision": job.analysis_revision,
            "handoff_id": handoff.id,
        },
        content_hash=doc.content_hash if doc else None,
    )
    db.add(ep_doc)
    db.flush()

    # Chunks (ordered, evidence-linked). No 50k truncation (task 8.10b).
    chunk_order = 0
    for page in pages:
        db.add(
            DBEpChunk(
                document_id=ep_doc.id,
                story_episode_id=episode.id,
                chunk_order=chunk_order,
                chunk_type="text" if page.extracted_text else "panel",
                approved_text=page.extracted_text,
                raw_text=page.extracted_text,
                page_refs_json=[page.id],
                evidence_ids_json=[page.evidence_id] if page.evidence_id else None,
                source_revision=doc.revision if doc else None,
                approval_state="accepted",
            )
        )
        chunk_order += 1

    for bubble in bubbles:
        text = _clean(bubble.approved_text or bubble.normalized_text or bubble.raw_text)
        if not text:
            continue
        db.add(
            DBEpChunk(
                document_id=ep_doc.id,
                story_episode_id=episode.id,
                chunk_order=chunk_order,
                chunk_type=bubble.bubble_type if bubble.bubble_type in {"dialogue", "narration"} else "dialogue",
                approved_text=text,
                raw_text=bubble.raw_text,
                ai_text=bubble.normalized_text,
                bubble_refs_json=[bubble.id],
                speaker_ref=bubble.speaker_character_id,
                evidence_ids_json=bubble.evidence_ids_json,
                confidence=bubble.ocr_confidence,
                source_revision=doc.revision if doc else None,
                approval_state="accepted",
            )
        )
        chunk_order += 1

    for panel in panels:
        text = _clean(panel.visual_description)
        if not text:
            continue
        db.add(
            DBEpChunk(
                document_id=ep_doc.id,
                story_episode_id=episode.id,
                chunk_order=chunk_order,
                chunk_type="visual",
                approved_text=text,
                ai_text=text,
                panel_refs_json=[panel.id],
                evidence_ids_json=panel.evidence_ids_json,
                confidence=panel.confidence,
                source_revision=doc.revision if doc else None,
                approval_state="accepted",
            )
        )
        chunk_order += 1

    for character in characters:
        text = _character_text(character)
        if text:
            db.add(
                DBEpChunk(
                    document_id=ep_doc.id,
                    story_episode_id=episode.id,
                    chunk_order=chunk_order,
                    chunk_type="character",
                    approved_text=text,
                    ai_text=text,
                    evidence_ids_json=character.evidence_ids_json,
                    confidence=character.confidence,
                    source_revision=doc.revision if doc else None,
                    approval_state="accepted",
                )
            )
            chunk_order += 1

    for location in locations:
        text = _location_text(location)
        if text:
            db.add(
                DBEpChunk(
                    document_id=ep_doc.id,
                    story_episode_id=episode.id,
                    chunk_order=chunk_order,
                    chunk_type="location",
                    approved_text=text,
                    ai_text=text,
                    evidence_ids_json=location.evidence_ids_json,
                    confidence=location.confidence,
                    source_revision=doc.revision if doc else None,
                    approval_state="accepted",
                )
            )
            chunk_order += 1

    if optimized_story:
        db.add(
            DBEpChunk(
                document_id=ep_doc.id,
                story_episode_id=episode.id,
                chunk_order=chunk_order,
                chunk_type="script",
                approved_text=optimized_story,
                ai_text=optimized_story,
                evidence_ids_json=_all_evidence_ids(panels, bubbles, characters, locations),
                source_revision=doc.revision if doc else None,
                approval_state="accepted",
            )
        )

    # Immutable asset links (task 8.9).
    for order, asset in enumerate(assets):
        db.add(
            DBEpAsset(
                document_id=ep_doc.id,
                story_episode_id=episode.id,
                asset_order=order,
                comic_source_asset_id=asset.id,
                original_path=asset.original_path,
                checksum=asset.checksum,
                source_revision=doc.revision if doc else None,
                occurrences_json=asset.occurrences_json,
            )
        )

    # Compatibility projection (task 8.10b, design §15): <= 50k chars.
    from .config import get_config

    limit = get_config().source_input_projection_limit
    if approved_text:
        episode.source_input = approved_text[:limit]

    db.flush()
    return ep_doc


def _apply_approved_series_context(db, handoff, job, series) -> None:
    manifest = approval_manifest.get_active_manifest(db, job.id)
    accepted_ids = approval_manifest.accepted_item_ids(manifest) if manifest else set()
    revision = int(handoff.analysis_revision or job.analysis_revision or 0)
    characters = db.query(DBCharacter).filter_by(job_id=job.id, analysis_revision=revision).all()
    locations = db.query(DBLocation).filter_by(job_id=job.id, analysis_revision=revision).all()

    accepted_characters = [item for item in characters if item.id in accepted_ids]
    accepted_locations = [item for item in locations if item.id in accepted_ids]
    for order, item in enumerate(accepted_characters):
        db.add(
            DBCharacterProfile(
                series_id=series.id,
                name=item.display_name or f"Nhân vật {order + 1}",
                role=item.role,
                face_description=item.face_description,
                hair_description=item.hair_description,
                body_description=item.body_description,
                signature_outfit=item.outfit_description,
                personality=item.personality,
                speech_style=item.speech_style,
                additional_notes=f"Nguồn Comic Analysis revision {revision}",
                sort_order=order,
            )
        )
    if accepted_characters and not series.character_bible:
        series.character_bible = "\n\n".join(_character_text(item) for item in accepted_characters if _character_text(item))
    if accepted_locations and not series.world_bible:
        series.world_bible = "\n\n".join(_location_text(item) for item in accepted_locations if _location_text(item))
    db.flush()


def _structured_analysis_text(panels, bubbles, characters, locations, plot) -> str:
    parts: list[str] = []
    if plot and plot.synopsis:
        parts.append(f"Tóm tắt: {plot.synopsis}")
    for panel in panels:
        if panel.visual_description:
            parts.append(f"Hình ảnh {panel.reading_order + 1}: {panel.visual_description}")
    for bubble in bubbles:
        text = _clean(bubble.approved_text or bubble.normalized_text or bubble.raw_text)
        if text:
            parts.append(f"{bubble.bubble_type}: {text}")
    parts.extend(_character_text(item) for item in characters if _character_text(item))
    parts.extend(_location_text(item) for item in locations if _location_text(item))
    return "\n\n".join(parts)


def _character_payload(item) -> dict:
    return {
        "id": item.id,
        "name": item.display_name,
        "role": item.role,
        "face_description": item.face_description,
        "hair_description": item.hair_description,
        "body_description": item.body_description,
        "outfit_description": item.outfit_description,
        "personality": item.personality,
        "speech_style": item.speech_style,
        "evidence_ids": item.evidence_ids_json,
        "confidence": item.confidence,
    }


def _location_payload(item) -> dict:
    return {
        "id": item.id,
        "name": item.name,
        "description": item.description,
        "world_rules": item.world_rules,
        "evidence_ids": item.evidence_ids_json,
        "confidence": item.confidence,
    }


def _character_text(item) -> str:
    traits = [
        item.role,
        item.face_description,
        item.hair_description,
        item.body_description,
        item.outfit_description,
        item.personality,
        item.speech_style,
    ]
    detail = "; ".join(value for value in traits if value)
    return f"Nhân vật {item.display_name}: {detail}" if item.display_name else detail


def _location_text(item) -> str:
    detail = "; ".join(value for value in (item.description, item.world_rules) if value)
    return f"Bối cảnh {item.name}: {detail}" if item.name else detail


def _all_evidence_ids(panels, bubbles, characters, locations) -> list[str] | None:
    values: list[str] = []
    for item in [*panels, *bubbles, *characters, *locations]:
        for evidence_id in item.evidence_ids_json or []:
            if evidence_id not in values:
                values.append(evidence_id)
    return values or None


def _clean(value) -> str | None:
    text = str(value or "").strip()
    return text or None


def _record_version(db, handoff, job, series_id, target_type, target_id) -> None:
    db.add(
        DBVersionRecord(
            job_id=job.id,
            handoff_id=handoff.id,
            analysis_revision=job.analysis_revision,
            source_document_revision=None,
            target_type=target_type,
            target_id=target_id,
        )
    )


__all__ = [
    "build_preview",
    "commit_handoff",
    "target_dependency_fingerprint",
]
