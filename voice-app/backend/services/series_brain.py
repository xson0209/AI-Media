"""Structured Series Brain memory, context selection, and canon checks."""

from __future__ import annotations

import re
import uuid
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from sqlalchemy import func
from sqlalchemy.orm import Session

from .. import models
from ..database import (
    SeriesCanonCheck as DBSeriesCanonCheck,
    SeriesCharacterProfile as DBSeriesCharacterProfile,
    SeriesContextTrace as DBSeriesContextTrace,
    SeriesCurrentState as DBSeriesCurrentState,
    SeriesMemoryCard as DBSeriesMemoryCard,
    StoryEpisode as DBStoryEpisode,
    VideoProject as DBVideoProject,
    VideoSeries as DBVideoSeries,
)

APPROVED = "approved"
CARD_CONTEXT_PREVIEW_CHARS = 6000
DEFAULT_CONTEXT_MAX_CHARS = 24000

TASK_TYPE_GROUPS: dict[str, set[str]] = {
    "story_candidate": {"series_identity", "canon_rule", "visual_style", "relationship", "story_thread", "episode_summary", "arc_summary", "series_summary"},
    "master_story": {"series_identity", "canon_rule", "visual_style", "relationship", "location", "prop", "story_thread", "episode_summary", "arc_summary", "series_summary"},
    "image_panel_prompt": {"series_identity", "canon_rule", "visual_style", "relationship", "location", "prop", "story_thread", "episode_summary"},
    "video_story_development": {"series_identity", "canon_rule", "visual_style", "relationship", "location", "prop", "story_thread", "episode_summary", "arc_summary", "series_summary"},
    "shot_breakdown": {"canon_rule", "visual_style", "relationship", "location", "prop", "story_thread", "episode_summary"},
    "video_prompt": {"canon_rule", "visual_style", "relationship", "location", "prop", "story_thread"},
    "voice": {"series_identity", "relationship", "story_thread", "episode_summary", "series_summary"},
    "subtitle": {"series_identity", "relationship", "story_thread", "episode_summary", "series_summary"},
}

GROUP_WEIGHTS: dict[str, float] = {
    "immutable_rules": 0.15,
    "characters_relationships": 0.20,
    "locations_props": 0.10,
    "open_threads": 0.15,
    "current_recent": 0.15,
    "task_payload": 0.20,
    "output_rules": 0.05,
}

TASK_WEIGHT_OVERRIDES: dict[str, dict[str, float]] = {
    "voice": {
        "immutable_rules": 0.10,
        "characters_relationships": 0.20,
        "locations_props": 0.00,
        "open_threads": 0.05,
        "current_recent": 0.10,
        "task_payload": 0.45,
        "output_rules": 0.10,
    },
    "subtitle": {
        "immutable_rules": 0.08,
        "characters_relationships": 0.12,
        "locations_props": 0.00,
        "open_threads": 0.05,
        "current_recent": 0.10,
        "task_payload": 0.55,
        "output_rules": 0.10,
    },
}

CARD_TYPE_LABELS: dict[str, str] = {
    "series_identity": "Danh tinh series",
    "character_context": "Ngu canh nhan vat",
    "relationship": "Quan he",
    "location": "Dia diem",
    "prop": "Dao cu",
    "story_thread": "Mach truyen",
    "canon_rule": "Quy tac canon",
    "visual_style": "Phong cach hinh anh",
    "episode_summary": "Tom tat tap",
    "arc_summary": "Tom tat chang",
    "series_summary": "Tom tat toan series",
    "reviewed_note": "Ghi chu da duyet",
}

NEGATION_WORDS = {
    "khong",
    "khong con",
    "doi",
    "thay doi",
    "mat",
    "bo",
    "remove",
    "without",
    "no longer",
    "changed",
    "different",
}


class SeriesBrainError(ValueError):
    """Raised when a Series Brain operation cannot be completed."""


@dataclass
class GroupDraft:
    key: str
    title: str
    body: str
    mandatory: bool = False


def _clean(value: object | None) -> str:
    return str(value or "").strip()


def _json_dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _json_list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def _json_text(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        return value.strip()
    if isinstance(value, dict):
        parts: list[str] = []
        for key, item in value.items():
            text = _json_text(item)
            if text:
                parts.append(f"{key}: {text}")
        return "\n".join(parts).strip()
    if isinstance(value, list):
        return "\n".join(_json_text(item) for item in value if _json_text(item)).strip()
    return str(value).strip()

def _clip_text(value: object | None, limit: int) -> str:
    text = _json_text(value)
    if len(text) <= limit:
        return text
    return text[:limit].rstrip(" ,.;:\n\t") + "...[rut gon]"


def _normalize_term(value: object | None) -> str:
    text = _clean(value).lower()
    replacements = {
        "á": "a",
        "à": "a",
        "ả": "a",
        "ã": "a",
        "ạ": "a",
        "ă": "a",
        "ắ": "a",
        "ằ": "a",
        "ẳ": "a",
        "ẵ": "a",
        "ặ": "a",
        "â": "a",
        "ấ": "a",
        "ầ": "a",
        "ẩ": "a",
        "ẫ": "a",
        "ậ": "a",
        "đ": "d",
        "é": "e",
        "è": "e",
        "ẻ": "e",
        "ẽ": "e",
        "ẹ": "e",
        "ê": "e",
        "ế": "e",
        "ề": "e",
        "ể": "e",
        "ễ": "e",
        "ệ": "e",
        "í": "i",
        "ì": "i",
        "ỉ": "i",
        "ĩ": "i",
        "ị": "i",
        "ó": "o",
        "ò": "o",
        "ỏ": "o",
        "õ": "o",
        "ọ": "o",
        "ô": "o",
        "ố": "o",
        "ồ": "o",
        "ổ": "o",
        "ỗ": "o",
        "ộ": "o",
        "ơ": "o",
        "ớ": "o",
        "ờ": "o",
        "ở": "o",
        "ỡ": "o",
        "ợ": "o",
        "ú": "u",
        "ù": "u",
        "ủ": "u",
        "ũ": "u",
        "ụ": "u",
        "ư": "u",
        "ứ": "u",
        "ừ": "u",
        "ử": "u",
        "ữ": "u",
        "ự": "u",
        "ý": "y",
        "ỳ": "y",
        "ỷ": "y",
        "ỹ": "y",
        "ỵ": "y",
    }
    for src, dest in replacements.items():
        text = text.replace(src, dest)
    return re.sub(r"\s+", " ", text)


def _contains_term(haystack: str, needle: str) -> bool:
    normalized_haystack = _normalize_term(haystack)
    normalized_needle = _normalize_term(needle)
    return bool(normalized_needle and normalized_needle in normalized_haystack)


def _terms_from_text(text: str) -> set[str]:
    normalized = _normalize_term(text)
    return {part for part in re.split(r"[^a-z0-9_]+", normalized) if len(part) >= 3}


def _require_series(series_id: str, db: Session) -> DBVideoSeries:
    series = db.query(DBVideoSeries).filter(DBVideoSeries.id == series_id).first()
    if series is None:
        raise SeriesBrainError("Khong tim thay series.")
    return series


def _latest_approved_state(series_id: str, db: Session) -> DBSeriesCurrentState | None:
    return (
        db.query(DBSeriesCurrentState)
        .filter(DBSeriesCurrentState.series_id == series_id, DBSeriesCurrentState.approval_status == APPROVED)
        .order_by(DBSeriesCurrentState.revision.desc(), DBSeriesCurrentState.created_at.desc())
        .first()
    )


def _next_card_revision(series_id: str, source_type: str | None, source_id: str | None, db: Session) -> int:
    if not source_type or not source_id:
        return 1
    latest = (
        db.query(func.max(DBSeriesMemoryCard.revision))
        .filter(
            DBSeriesMemoryCard.series_id == series_id,
            DBSeriesMemoryCard.source_type == source_type,
            DBSeriesMemoryCard.source_id == source_id,
        )
        .scalar()
        or 0
    )
    return int(latest) + 1


def _next_state_revision(series_id: str, db: Session) -> int:
    latest = (
        db.query(func.max(DBSeriesCurrentState.revision))
        .filter(DBSeriesCurrentState.series_id == series_id)
        .scalar()
        or 0
    )
    return int(latest) + 1


def _card_response(row: DBSeriesMemoryCard) -> models.SeriesMemoryCardResponse:
    return models.SeriesMemoryCardResponse(
        id=row.id,
        series_id=row.series_id,
        card_type=row.card_type,
        title=row.title,
        content=_json_dict(row.content_json),
        tags=[str(item) for item in _json_list(row.tags_json)],
        entity_refs=[item for item in _json_list(row.entity_refs_json) if isinstance(item, dict)],
        importance=float(row.importance or 0),
        status=row.status,
        effective_from_episode=row.effective_from_episode,
        effective_to_episode=row.effective_to_episode,
        source_type=row.source_type,
        source_id=row.source_id,
        revision=int(row.revision or 1),
        approved_at=row.approved_at,
        created_at=row.created_at,
        updated_at=row.updated_at,
    )


def _state_response(row: DBSeriesCurrentState) -> models.SeriesCurrentStateResponse:
    return models.SeriesCurrentStateResponse(
        id=row.id,
        series_id=row.series_id,
        based_on_episode_number=int(row.based_on_episode_number or 0),
        character_states=_json_dict(row.character_states_json),
        relationship_states=_json_dict(row.relationship_states_json),
        location_states=_json_dict(row.location_states_json),
        prop_states=_json_dict(row.prop_states_json),
        open_threads=[item for item in _json_list(row.open_threads_json) if isinstance(item, dict)],
        unresolved_conflicts=[item for item in _json_list(row.unresolved_conflicts_json) if isinstance(item, dict)],
        approval_status=row.approval_status,
        source_type=row.source_type,
        source_id=row.source_id,
        revision=int(row.revision or 1),
        previous_state_id=row.previous_state_id,
        approved_at=row.approved_at,
        created_at=row.created_at,
        updated_at=row.updated_at,
    )


def _trace_response(row: DBSeriesContextTrace) -> models.SeriesContextTraceResponse:
    return models.SeriesContextTraceResponse(
        id=row.id,
        series_id=row.series_id,
        project_id=row.project_id,
        story_episode_id=row.story_episode_id,
        task_type=row.task_type,
        target_ref_type=row.target_ref_type,
        target_ref_id=row.target_ref_id,
        selected_cards=[item for item in _json_list(row.selected_cards_json) if isinstance(item, dict)],
        selected_character_profiles=[item for item in _json_list(row.selected_character_profiles_json) if isinstance(item, dict)],
        group_budget=[item for item in _json_list(row.group_budget_json) if isinstance(item, dict)],
        missing_required=[str(item) for item in _json_list(row.missing_required_json)],
        truncated_groups=[str(item) for item in _json_list(row.truncated_groups_json)],
        context_stats=_json_dict(row.context_stats_json),
        reasons=[item for item in _json_list(row.reasons_json) if isinstance(item, dict)],
        context_preview=row.context_preview,
        created_at=row.created_at,
    )


def list_memory_cards(
    series_id: str,
    db: Session,
    *,
    card_type: str | None = None,
    status: str | None = None,
    episode_number: int | None = None,
    entity_ref: str | None = None,
    tag: str | None = None,
    min_importance: float | None = None,
) -> models.SeriesMemoryCardListResponse:
    _require_series(series_id, db)
    query = db.query(DBSeriesMemoryCard).filter(DBSeriesMemoryCard.series_id == series_id)
    if card_type:
        query = query.filter(DBSeriesMemoryCard.card_type == card_type)
    if status:
        query = query.filter(DBSeriesMemoryCard.status == status)
    if min_importance is not None:
        query = query.filter(DBSeriesMemoryCard.importance >= min_importance)
    rows = query.order_by(DBSeriesMemoryCard.importance.desc(), DBSeriesMemoryCard.updated_at.desc()).all()
    filtered: list[DBSeriesMemoryCard] = []
    for row in rows:
        if episode_number is not None:
            start = row.effective_from_episode
            end = row.effective_to_episode
            if start is not None and episode_number < int(start):
                continue
            if end is not None and episode_number > int(end):
                continue
        if entity_ref:
            refs = _json_list(row.entity_refs_json)
            ref_text = "\n".join(_json_text(ref) for ref in refs)
            if not _contains_term(ref_text, entity_ref):
                continue
        if tag:
            tags = [str(item) for item in _json_list(row.tags_json)]
            if not any(_contains_term(item, tag) for item in tags):
                continue
        filtered.append(row)
    return models.SeriesMemoryCardListResponse(
        items=[_card_response(row) for row in filtered],
        total=len(filtered),
    )


def create_memory_card(series_id: str, data: models.SeriesMemoryCardCreate, db: Session) -> models.SeriesMemoryCardResponse:
    _require_series(series_id, db)
    now = datetime.utcnow()
    status = data.status or "draft"
    row = DBSeriesMemoryCard(
        id=str(uuid.uuid4()),
        series_id=series_id,
        card_type=data.card_type,
        title=data.title.strip(),
        content_json=data.content or {},
        tags_json=[tag.strip() for tag in data.tags if tag.strip()],
        entity_refs_json=data.entity_refs,
        importance=float(data.importance),
        status=status,
        effective_from_episode=data.effective_from_episode,
        effective_to_episode=data.effective_to_episode,
        source_type=data.source_type,
        source_id=data.source_id,
        revision=_next_card_revision(series_id, data.source_type, data.source_id, db),
        approved_at=now if status == APPROVED else None,
        created_at=now,
        updated_at=now,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return _card_response(row)


def update_memory_card(
    series_id: str,
    card_id: str,
    patch: models.SeriesMemoryCardUpdate,
    db: Session,
) -> models.SeriesMemoryCardResponse | None:
    row = (
        db.query(DBSeriesMemoryCard)
        .filter(DBSeriesMemoryCard.series_id == series_id, DBSeriesMemoryCard.id == card_id)
        .first()
    )
    if row is None:
        return None
    data = patch.model_dump(exclude_unset=True)
    content_changed = False
    field_map = {
        "content": "content_json",
        "tags": "tags_json",
        "entity_refs": "entity_refs_json",
    }
    for key, value in data.items():
        attr = field_map.get(key, key)
        if key == "title" and isinstance(value, str):
            value = value.strip()
        if key == "tags" and isinstance(value, list):
            value = [str(item).strip() for item in value if str(item).strip()]
        if key in {"card_type", "title", "content", "tags", "entity_refs", "effective_from_episode", "effective_to_episode"}:
            content_changed = True
        setattr(row, attr, value)
    if content_changed:
        row.revision = int(row.revision or 1) + 1
        if row.status == APPROVED:
            row.status = "pending_approval"
            row.approved_at = None
    if "status" in data:
        row.approved_at = datetime.utcnow() if row.status == APPROVED else None
    row.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(row)
    return _card_response(row)


def set_memory_card_status(
    series_id: str,
    card_id: str,
    data: models.SeriesMemoryCardStatusRequest,
    db: Session,
) -> models.SeriesMemoryCardResponse | None:
    row = (
        db.query(DBSeriesMemoryCard)
        .filter(DBSeriesMemoryCard.series_id == series_id, DBSeriesMemoryCard.id == card_id)
        .first()
    )
    if row is None:
        return None
    row.status = data.status
    row.approved_at = datetime.utcnow() if data.status == APPROVED else None
    row.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(row)
    return _card_response(row)


def delete_memory_card(series_id: str, card_id: str, db: Session) -> bool:
    row = (
        db.query(DBSeriesMemoryCard)
        .filter(DBSeriesMemoryCard.series_id == series_id, DBSeriesMemoryCard.id == card_id)
        .first()
    )
    if row is None:
        return False
    db.delete(row)
    db.commit()
    return True


def _upsert_memory_card_row(
    *,
    series_id: str,
    card_type: str,
    title: str,
    content: dict[str, Any],
    tags: list[str],
    entity_refs: list[dict[str, Any]] | None = None,
    importance: float,
    status: str,
    effective_from_episode: int | None,
    effective_to_episode: int | None,
    source_type: str,
    source_id: str,
    db: Session,
) -> DBSeriesMemoryCard:
    now = datetime.utcnow()
    row = (
        db.query(DBSeriesMemoryCard)
        .filter(
            DBSeriesMemoryCard.series_id == series_id,
            DBSeriesMemoryCard.card_type == card_type,
            DBSeriesMemoryCard.source_type == source_type,
            DBSeriesMemoryCard.source_id == source_id,
        )
        .first()
    )
    normalized_tags = [tag.strip() for tag in tags if tag.strip()]
    normalized_refs = entity_refs or []
    if row is None:
        row = DBSeriesMemoryCard(
            id=str(uuid.uuid4()),
            series_id=series_id,
            card_type=card_type,
            title=title.strip(),
            content_json=content,
            tags_json=normalized_tags,
            entity_refs_json=normalized_refs,
            importance=importance,
            status=status,
            effective_from_episode=effective_from_episode,
            effective_to_episode=effective_to_episode,
            source_type=source_type,
            source_id=source_id,
            revision=1,
            approved_at=now if status == APPROVED else None,
            created_at=now,
            updated_at=now,
        )
        db.add(row)
        return row

    content_changed = any(
        [
            row.title != title.strip(),
            row.content_json != content,
            (row.tags_json or []) != normalized_tags,
            (row.entity_refs_json or []) != normalized_refs,
            float(row.importance or 0) != float(importance),
            row.effective_from_episode != effective_from_episode,
            row.effective_to_episode != effective_to_episode,
        ]
    )
    row.title = title.strip()
    row.content_json = content
    row.tags_json = normalized_tags
    row.entity_refs_json = normalized_refs
    row.importance = importance
    row.status = status
    row.effective_from_episode = effective_from_episode
    row.effective_to_episode = effective_to_episode
    row.approved_at = row.approved_at or (now if status == APPROVED else None)
    row.updated_at = now
    if content_changed:
        row.revision = int(row.revision or 1) + 1
    return row


def _story_episode_summary_text(episode: DBStoryEpisode, *, full_story_limit: int = 5000) -> str:
    master = episode.master_story_json if isinstance(episode.master_story_json, dict) else {}
    title = _clean(episode.title) or _clean(master.get("title")) or "Chua dat ten"
    parts = [
        f"Episode {int(episode.episode_number or 0):02d}: {title}",
        f"Output intent: {_clean(episode.output_intent)}" if _clean(episode.output_intent) else "",
        f"Hook: {_clip_text(master.get('hook'), 1200)}" if _clean(master.get("hook")) else "",
        f"Logline: {_clip_text(master.get('logline'), 1200)}" if _clean(master.get("logline")) else "",
        f"Key beats:\n{_clip_text(master.get('key_beats'), 2500)}" if _json_text(master.get("key_beats")) else "",
        f"Full story:\n{_clip_text(master.get('full_story'), full_story_limit)}" if _clean(master.get("full_story")) else "",
        f"Continuity updates:\n{_clip_text(master.get('continuity_updates'), 2500)}" if _json_text(master.get("continuity_updates")) else "",
    ]
    return "\n\n".join(part for part in parts if part).strip()


def _approved_story_episodes(series_id: str, db: Session) -> list[DBStoryEpisode]:
    return (
        db.query(DBStoryEpisode)
        .filter(DBStoryEpisode.series_id == series_id, DBStoryEpisode.approval_status == APPROVED)
        .order_by(DBStoryEpisode.episode_number.asc(), DBStoryEpisode.created_at.asc())
        .all()
    )


def record_story_episode_summaries(
    series_id: str,
    episode_id: str,
    db: Session,
) -> list[models.SeriesMemoryCardResponse]:
    """Persist layered Story Studio summaries after a Master Story is approved."""

    series = _require_series(series_id, db)
    episode = (
        db.query(DBStoryEpisode)
        .filter(
            DBStoryEpisode.series_id == series_id,
            DBStoryEpisode.id == episode_id,
            DBStoryEpisode.approval_status == APPROVED,
        )
        .first()
    )
    if episode is None:
        return []

    episode_number = int(episode.episode_number or 0)
    episode_text = _story_episode_summary_text(episode)
    master = episode.master_story_json if isinstance(episode.master_story_json, dict) else {}
    title = _clean(episode.title) or _clean(master.get("title")) or "Chua dat ten"
    rows: list[DBSeriesMemoryCard] = []
    rows.append(
        _upsert_memory_card_row(
            series_id=series_id,
            card_type="episode_summary",
            title=f"Story Episode {episode_number:02d}: {title}",
            content={
                "summary_scope": "episode",
                "episode_number": episode_number,
                "title": title,
                "text": episode_text,
            },
            tags=["story_episode", "episode_summary", "approved_master_story"],
            entity_refs=[],
            importance=0.82,
            status=APPROVED,
            effective_from_episode=episode_number or None,
            effective_to_episode=episode_number or None,
            source_type="story_episode",
            source_id=episode.id,
            db=db,
        )
    )

    arc_start = ((max(episode_number, 1) - 1) // 10) * 10 + 1
    arc_end = arc_start + 9
    arc_episodes = [
        item for item in _approved_story_episodes(series_id, db)
        if arc_start <= int(item.episode_number or 0) <= arc_end
    ]
    arc_text = "\n\n".join(_story_episode_summary_text(item, full_story_limit=1800) for item in arc_episodes).strip()
    if arc_text:
        rows.append(
            _upsert_memory_card_row(
                series_id=series_id,
                card_type="arc_summary",
                title=f"Story arc {arc_start:02d}-{arc_end:02d}",
                content={
                    "summary_scope": "arc",
                    "episode_start": arc_start,
                    "episode_end": arc_end,
                    "episode_count": len(arc_episodes),
                    "text": _clip_text(arc_text, 30000),
                },
                tags=["story_episode", "arc_summary", "approved_master_story"],
                entity_refs=[],
                importance=0.72,
                status=APPROVED,
                effective_from_episode=arc_start,
                effective_to_episode=arc_end,
                source_type="story_arc",
                source_id=f"{series_id}:{arc_start}-{arc_end}",
                db=db,
            )
        )

    approved_episodes = _approved_story_episodes(series_id, db)
    series_text = "\n\n".join(_story_episode_summary_text(item, full_story_limit=1400) for item in approved_episodes).strip()
    if series_text:
        rows.append(
            _upsert_memory_card_row(
                series_id=series_id,
                card_type="series_summary",
                title=f"Series summary: {series.title}",
                content={
                    "summary_scope": "series",
                    "episode_count": len(approved_episodes),
                    "latest_episode_number": max((int(item.episode_number or 0) for item in approved_episodes), default=0),
                    "text": _clip_text(series_text, 50000),
                },
                tags=["story_episode", "series_summary", "approved_master_story"],
                entity_refs=[],
                importance=0.78,
                status=APPROVED,
                effective_from_episode=None,
                effective_to_episode=None,
                source_type="story_series_summary",
                source_id=series.id,
                db=db,
            )
        )

    if episode_text:
        series.previous_episode_summary = _clip_text(episode_text, 50000)
    if episode_number:
        series.latest_episode_number = max(int(getattr(series, "latest_episode_number", 0) or 0), episode_number)
    series.updated_at = datetime.utcnow()
    db.commit()
    for row in rows:
        db.refresh(row)
    return [_card_response(row) for row in rows]


def _legacy_card(
    *,
    card_type: str,
    title: str,
    text: str,
    tags: list[str],
    source_type: str,
    source_id: str | None = None,
    importance: float = 0.5,
) -> models.SeriesMemoryCardCreate | None:
    body = _clean(text)
    if not body:
        return None
    return models.SeriesMemoryCardCreate(
        card_type=card_type,
        title=title,
        content={"text": body},
        tags=tags,
        entity_refs=[],
        importance=importance,
        status="draft",
        source_type=source_type,
        source_id=source_id,
    )


def suggest_memory_cards(
    series_id: str,
    data: models.SeriesMemorySuggestionRequest,
    db: Session,
) -> models.SeriesMemorySuggestionResponse:
    series = _require_series(series_id, db)
    cards: list[models.SeriesMemoryCardCreate] = []
    identity = models.SeriesMemoryCardCreate(
        card_type="series_identity",
        title=f"Danh tinh series: {series.title}",
        content={
            "title": series.title,
            "series_mode": getattr(series, "series_mode", "video_story_only"),
        },
        tags=["identity", "series"],
        entity_refs=[],
        importance=1.0,
        status="draft",
        source_type="video_series",
        source_id=series.id,
    )
    cards.append(identity)
    if data.include_legacy_bible:
        for card in [
            _legacy_card(
                card_type="reviewed_note",
                title="Character Bible cu",
                text=series.character_bible,
                tags=["legacy", "character"],
                source_type="legacy_character_bible",
                source_id=series.id,
                importance=0.55,
            ),
            _legacy_card(
                card_type="location",
                title="World Bible cu",
                text=series.world_bible,
                tags=["legacy", "world"],
                source_type="legacy_world_bible",
                source_id=series.id,
                importance=0.65,
            ),
            _legacy_card(
                card_type="visual_style",
                title="Style Bible cu",
                text=series.style_bible,
                tags=["legacy", "style"],
                source_type="legacy_style_bible",
                source_id=series.id,
                importance=0.85,
            ),
            _legacy_card(
                card_type="canon_rule",
                title="Continuity rules cu",
                text=series.continuity_rules,
                tags=["legacy", "canon", "continuity"],
                source_type="legacy_continuity_rules",
                source_id=series.id,
                importance=0.9,
            ),
            _legacy_card(
                card_type="canon_rule",
                title="Negative rules cu",
                text=series.negative_rules,
                tags=["legacy", "negative", "forbidden"],
                source_type="legacy_negative_rules",
                source_id=series.id,
                importance=0.9,
            ),
        ]:
            if card is not None:
                cards.append(card)
    if data.include_latest_summary:
        card = _legacy_card(
            card_type="episode_summary",
            title="Tom tat tap gan nhat",
            text=series.previous_episode_summary,
            tags=["legacy", "episode_summary"],
            source_type="legacy_previous_episode_summary",
            source_id=series.id,
            importance=0.75,
        )
        if card is not None:
            cards.append(card)
    saved = False
    if data.save_drafts:
        existing_sources = {
            (row.source_type, row.source_id, row.card_type, row.title)
            for row in db.query(DBSeriesMemoryCard)
            .filter(DBSeriesMemoryCard.series_id == series_id)
            .all()
        }
        for card in cards:
            key = (card.source_type, card.source_id, card.card_type, card.title)
            if key in existing_sources:
                continue
            create_memory_card(series_id, card, db)
            saved = True
    return models.SeriesMemorySuggestionResponse(
        cards=cards,
        saved=saved,
        message=(
            "Da luu cac the nho nhap tu Series Bible cu. Chua the nao tro thanh canon neu chua duyet."
            if saved
            else "Da tao goi y the nho nhap tu Series Bible cu. Chua luu thay doi vao series."
        ),
    )


def list_current_states(series_id: str, db: Session) -> models.SeriesCurrentStateListResponse:
    _require_series(series_id, db)
    rows = (
        db.query(DBSeriesCurrentState)
        .filter(DBSeriesCurrentState.series_id == series_id)
        .order_by(DBSeriesCurrentState.revision.desc(), DBSeriesCurrentState.created_at.desc())
        .all()
    )
    return models.SeriesCurrentStateListResponse(items=[_state_response(row) for row in rows], total=len(rows))


def create_current_state(
    series_id: str,
    data: models.SeriesCurrentStateCreate,
    db: Session,
) -> models.SeriesCurrentStateResponse:
    _require_series(series_id, db)
    now = datetime.utcnow()
    previous = _latest_approved_state(series_id, db)
    row = DBSeriesCurrentState(
        id=str(uuid.uuid4()),
        series_id=series_id,
        based_on_episode_number=data.based_on_episode_number,
        character_states_json=data.character_states,
        relationship_states_json=data.relationship_states,
        location_states_json=data.location_states,
        prop_states_json=data.prop_states,
        open_threads_json=data.open_threads,
        unresolved_conflicts_json=data.unresolved_conflicts,
        approval_status=data.approval_status,
        source_type=data.source_type,
        source_id=data.source_id,
        previous_state_id=previous.id if previous is not None else None,
        revision=_next_state_revision(series_id, db),
        approved_at=now if data.approval_status == APPROVED else None,
        created_at=now,
        updated_at=now,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return _state_response(row)


def update_current_state(
    series_id: str,
    state_id: str,
    patch: models.SeriesCurrentStateUpdate,
    db: Session,
) -> models.SeriesCurrentStateResponse | None:
    row = (
        db.query(DBSeriesCurrentState)
        .filter(DBSeriesCurrentState.series_id == series_id, DBSeriesCurrentState.id == state_id)
        .first()
    )
    if row is None:
        return None
    data = patch.model_dump(exclude_unset=True)
    field_map = {
        "character_states": "character_states_json",
        "relationship_states": "relationship_states_json",
        "location_states": "location_states_json",
        "prop_states": "prop_states_json",
        "open_threads": "open_threads_json",
        "unresolved_conflicts": "unresolved_conflicts_json",
    }
    for key, value in data.items():
        setattr(row, field_map.get(key, key), value)
    if "approval_status" in data:
        row.approved_at = datetime.utcnow() if row.approval_status == APPROVED else None
    row.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(row)
    return _state_response(row)


def set_current_state_status(
    series_id: str,
    state_id: str,
    data: models.SeriesCurrentStateStatusRequest,
    db: Session,
) -> models.SeriesCurrentStateResponse | None:
    row = (
        db.query(DBSeriesCurrentState)
        .filter(DBSeriesCurrentState.series_id == series_id, DBSeriesCurrentState.id == state_id)
        .first()
    )
    if row is None:
        return None
    row.approval_status = data.approval_status
    row.approved_at = datetime.utcnow() if data.approval_status == APPROVED else None
    row.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(row)
    return _state_response(row)


def propose_current_state(
    series_id: str,
    data: models.SeriesStateProposalRequest,
    db: Session,
) -> models.SeriesCurrentStateResponse:
    series = _require_series(series_id, db)
    previous = _latest_approved_state(series_id, db)
    base_character = dict(_json_dict(previous.character_states_json)) if previous is not None else {}
    base_relationship = dict(_json_dict(previous.relationship_states_json)) if previous is not None else {}
    base_location = dict(_json_dict(previous.location_states_json)) if previous is not None else {}
    base_prop = dict(_json_dict(previous.prop_states_json)) if previous is not None else {}
    base_threads = [item for item in _json_list(previous.open_threads_json) if isinstance(item, dict)] if previous is not None else []
    conflicts = [item for item in _json_list(previous.unresolved_conflicts_json) if isinstance(item, dict)] if previous is not None else []

    based_on_episode = data.based_on_episode_number
    source_notes = _clean(data.notes)
    if data.source_type == "story_episode" and data.source_id:
        episode = db.query(DBStoryEpisode).filter(DBStoryEpisode.series_id == series_id, DBStoryEpisode.id == data.source_id).first()
        if episode is not None:
            based_on_episode = based_on_episode or int(episode.episode_number or 0)
            master = episode.master_story_json if isinstance(episode.master_story_json, dict) else {}
            for index, item in enumerate(master.get("continuity_updates") or [], start=1):
                item_text = _json_text(item)[:160] or f"Cap nhat tu tap {episode.episode_number}"
                base_threads.append(
                    {
                        "id": f"story-episode-{episode.episode_number}-{index}",
                        "title": item_text,
                        "status": "proposed",
                        "source": episode.id,
                        "previous_value": None,
                        "new_value": item,
                        "change_source": "master_story.continuity_updates",
                    }
                )
            source_notes = source_notes or _json_text(master.get("full_story") or master.get("logline"))
    elif data.source_type == "video_project" and data.source_id:
        project = db.query(DBVideoProject).filter(DBVideoProject.series_id == series_id, DBVideoProject.id == data.source_id).first()
        if project is not None:
            based_on_episode = based_on_episode or int(project.episode_number or 0)
            if _clean(project.continuity_bible):
                base_threads.append(
                    {
                        "id": f"video-project-{project.id}",
                        "title": _clean(project.episode_title or project.title)[:160],
                        "status": "proposed",
                        "source": project.id,
                        "summary": _clean(project.continuity_bible)[:4000],
                        "previous_value": None,
                        "new_value": _clean(project.continuity_bible)[:4000],
                        "change_source": "video_project.continuity_bible",
                    }
                )
            source_notes = source_notes or _clean(project.detailed_script or project.story_strategy or project.topic)

    if source_notes:
        base_threads.append(
            {
                "id": f"manual-{uuid.uuid4()}",
                "title": source_notes[:160],
                "status": "proposed",
                "source": data.source_id or series.id,
                "previous_value": None,
                "new_value": source_notes[:4000],
                "change_source": data.source_type,
            }
        )

    return create_current_state(
        series_id,
        models.SeriesCurrentStateCreate(
            based_on_episode_number=based_on_episode or int(getattr(series, "latest_episode_number", 0) or 0),
            character_states=base_character,
            relationship_states=base_relationship,
            location_states=base_location,
            prop_states=base_prop,
            open_threads=base_threads,
            unresolved_conflicts=conflicts,
            approval_status="pending_approval",
            source_type=data.source_type,
            source_id=data.source_id,
        ),
        db,
    )


def _approved_cards(series_id: str, episode_number: int | None, db: Session) -> list[DBSeriesMemoryCard]:
    rows = (
        db.query(DBSeriesMemoryCard)
        .filter(DBSeriesMemoryCard.series_id == series_id, DBSeriesMemoryCard.status == APPROVED)
        .order_by(DBSeriesMemoryCard.importance.desc(), DBSeriesMemoryCard.updated_at.desc())
        .all()
    )
    selected: list[DBSeriesMemoryCard] = []
    for row in rows:
        if episode_number is not None:
            if row.effective_from_episode is not None and episode_number < int(row.effective_from_episode):
                continue
            if row.effective_to_episode is not None and episode_number > int(row.effective_to_episode):
                continue
        selected.append(row)
    return selected


def _profile_summary(row: DBSeriesCharacterProfile, task_type: str) -> str:
    if task_type in {"voice", "subtitle"}:
        fields = [
            f"- {row.name} ({_clean(row.role) or 'vai tro chua ro'})",
            f"  Speech: {_clean(row.speech_style)}" if _clean(row.speech_style) else "",
            f"  Personality: {_clean(row.personality)}" if _clean(row.personality) else "",
            f"  Fixed traits: {_clean(row.fixed_traits)}" if _clean(row.fixed_traits) else "",
        ]
    else:
        fields = [
            f"- {row.name} ({_clean(row.role) or 'vai tro chua ro'})",
            f"  Face: {_clean(row.face_description)}" if _clean(row.face_description) else "",
            f"  Hair: {_clean(row.hair_description)}" if _clean(row.hair_description) else "",
            f"  Body: {_clean(row.body_description)}" if _clean(row.body_description) else "",
            f"  Outfit: {_clean(row.signature_outfit)}" if _clean(row.signature_outfit) else "",
            f"  Personality: {_clean(row.personality)}" if _clean(row.personality) else "",
            f"  Speech: {_clean(row.speech_style)}" if _clean(row.speech_style) else "",
            f"  Fixed traits: {_clean(row.fixed_traits)}" if _clean(row.fixed_traits) else "",
            f"  Notes: {_clean(row.additional_notes)}" if _clean(row.additional_notes) else "",
        ]
    return "\n".join(field for field in fields if field).strip()


def _profile_trace(row: DBSeriesCharacterProfile) -> dict[str, Any]:
    return {
        "id": row.id,
        "name": row.name,
        "revision": int(getattr(row, "revision", 1) or 1),
        "source": "series_character_profiles",
    }


def _card_summary(row: DBSeriesMemoryCard) -> str:
    label = CARD_TYPE_LABELS.get(row.card_type, row.card_type)
    content = _json_text(row.content_json)
    refs = _json_text(row.entity_refs_json)
    tags = ", ".join(str(item) for item in _json_list(row.tags_json))
    meta = []
    if tags:
        meta.append(f"tags={tags}")
    if refs:
        meta.append(f"refs={refs[:300]}")
    meta_line = f" ({'; '.join(meta)})" if meta else ""
    return f"- [{label}] {row.title}{meta_line}\n  {content}".strip()


def _card_trace(row: DBSeriesMemoryCard, reason: str) -> dict[str, Any]:
    return {
        "id": row.id,
        "card_type": row.card_type,
        "title": row.title,
        "revision": int(row.revision or 1),
        "importance": float(row.importance or 0),
        "reason": reason,
    }


def _score_card(
    row: DBSeriesMemoryCard,
    *,
    task_type: str,
    query_terms: set[str],
    episode_number: int | None,
) -> tuple[float, str]:
    score = float(row.importance or 0)
    reasons: list[str] = []
    if row.card_type in TASK_TYPE_GROUPS.get(task_type, set()):
        score += 0.30
        reasons.append("phu hop loai nhiem vu")
    content_terms = _terms_from_text("\n".join([row.title, _json_text(row.content_json), _json_text(row.tags_json), _json_text(row.entity_refs_json)]))
    overlap = len(query_terms & content_terms)
    if overlap:
        bump = min(0.25, 0.04 * overlap)
        score += bump
        reasons.append("trung nhan/thuc the/tu khoa")
    if episode_number is not None and row.effective_from_episode is not None:
        distance = max(0, episode_number - int(row.effective_from_episode))
        if distance <= 3:
            score += 0.08
            reasons.append("gan tap hien tai")
    if row.card_type in {"canon_rule", "series_identity"}:
        score += 0.10
        reasons.append("du lieu bat buoc")
    return score, ", ".join(reasons) or "muc quan trong cao"


def _state_text(state: DBSeriesCurrentState | None) -> str:
    if state is None:
        return ""
    sections = [
        f"Based on episode: {state.based_on_episode_number}",
        f"Character states:\n{_json_text(state.character_states_json)}" if _json_text(state.character_states_json) else "",
        f"Relationship states:\n{_json_text(state.relationship_states_json)}" if _json_text(state.relationship_states_json) else "",
        f"Location states:\n{_json_text(state.location_states_json)}" if _json_text(state.location_states_json) else "",
        f"Prop states:\n{_json_text(state.prop_states_json)}" if _json_text(state.prop_states_json) else "",
        f"Open threads:\n{_json_text(state.open_threads_json)}" if _json_text(state.open_threads_json) else "",
        f"Unresolved conflicts:\n{_json_text(state.unresolved_conflicts_json)}" if _json_text(state.unresolved_conflicts_json) else "",
    ]
    return "\n".join(part for part in sections if part).strip()


def _task_payload_text(data: models.SeriesContextCompileRequest) -> str:
    parts = []
    if _clean(data.user_input):
        parts.append(f"User input:\n{_clean(data.user_input)}")
    if data.current_payload:
        parts.append(f"Current task payload:\n{_json_text(data.current_payload)}")
    if data.entity_refs:
        parts.append("Explicit entity refs: " + ", ".join(data.entity_refs))
    if data.tags:
        parts.append("Explicit tags: " + ", ".join(data.tags))
    return "\n\n".join(parts).strip()


def _budget_for_task(task_type: str, max_chars: int) -> dict[str, int]:
    weights = TASK_WEIGHT_OVERRIDES.get(task_type, GROUP_WEIGHTS)
    total_weight = sum(weights.values()) or 1
    return {key: max(0, int(max_chars * value / total_weight)) for key, value in weights.items()}


def _apply_group_budgets(groups: list[GroupDraft], budgets: dict[str, int], max_chars: int) -> tuple[str, list[dict[str, Any]], list[str]]:
    raw_by_key = {group.key: group for group in groups}
    used: dict[str, str] = {}
    overflow: list[str] = []
    surplus = 0
    for group in groups:
        body = group.body.strip()
        budget = budgets.get(group.key, 0)
        if not body or budget <= 0:
            used[group.key] = ""
            surplus += max(0, budget)
            continue
        if len(body) <= budget:
            used[group.key] = body
            surplus += budget - len(body)
        else:
            used[group.key] = body[:budget].rstrip(" ,.;:\n\t") + "\n...[rut gon trong nhom]"
            overflow.append(group.key)

    if surplus > 0 and overflow:
        extra_each = max(1, surplus // len(overflow))
        for key in list(overflow):
            raw = raw_by_key[key].body.strip()
            current = used[key]
            if len(raw) <= len(current):
                continue
            new_budget = min(len(raw), len(current) + extra_each)
            used[key] = raw[:new_budget].rstrip(" ,.;:\n\t")
            if new_budget < len(raw):
                used[key] += "\n...[rut gon trong nhom]"
            else:
                overflow.remove(key)

    sections: list[str] = []
    group_usage: list[dict[str, Any]] = []
    for group in groups:
        body = used.get(group.key, "").strip()
        if not body:
            group_usage.append(
                {
                    "group": group.key,
                    "title": group.title,
                    "allocated_chars": budgets.get(group.key, 0),
                    "used_chars": 0,
                    "truncated": False,
                }
            )
            continue
        section = f"## {group.title}\n{body}"
        sections.append(section)
        group_usage.append(
            {
                "group": group.key,
                "title": group.title,
                "allocated_chars": budgets.get(group.key, 0),
                "used_chars": len(body),
                "truncated": group.key in overflow,
            }
        )
    context = "\n\n".join(sections).strip()
    if len(context) > max_chars:
        context = context[:max_chars].rstrip(" ,.;:\n\t") + "\n...[context truncated]"
        if "context" not in overflow:
            overflow.append("context")
    return context, group_usage, overflow


def compile_context(
    series_id: str,
    data: models.SeriesContextCompileRequest,
    db: Session,
) -> models.SeriesContextCompileResponse:
    series = _require_series(series_id, db)
    episode_number = data.episode_number or int(getattr(series, "latest_episode_number", 0) or 0) or None
    cards = _approved_cards(series_id, episode_number, db)
    query_text = "\n".join(
        [
            data.task_type,
            _clean(data.user_input),
            _json_text(data.current_payload),
            " ".join(data.entity_refs),
            " ".join(data.tags),
        ]
    )
    query_terms = _terms_from_text(query_text)
    scored = [
        (score, reason, row)
        for row in cards
        for score, reason in [_score_card(row, task_type=data.task_type, query_terms=query_terms, episode_number=episode_number)]
    ]
    scored.sort(key=lambda item: item[0], reverse=True)
    selected_cards = [row for _score, _reason, row in scored[:80]]
    selected_trace = [_card_trace(row, reason) for _score, reason, row in scored[:80]]

    profiles = (
        db.query(DBSeriesCharacterProfile)
        .filter(DBSeriesCharacterProfile.series_id == series_id)
        .order_by(DBSeriesCharacterProfile.sort_order.asc(), DBSeriesCharacterProfile.created_at.asc())
        .all()
    )
    state = _latest_approved_state(series_id, db)
    card_text_by_type: dict[str, list[str]] = {}
    for card in selected_cards:
        card_text_by_type.setdefault(card.card_type, []).append(_card_summary(card))

    immutable_parts = [
        f"Series title: {series.title}",
        f"Series mode: {getattr(series, 'series_mode', 'video_story_only')}",
        "\n".join(card_text_by_type.get("series_identity", [])),
        "\n".join(card_text_by_type.get("canon_rule", [])),
        "\n".join(card_text_by_type.get("visual_style", [])),
    ]
    if not card_text_by_type.get("canon_rule") and _clean(series.continuity_rules):
        immutable_parts.append("Fallback continuity rules:\n" + _clean(series.continuity_rules))
    if not card_text_by_type.get("visual_style") and _clean(series.style_bible):
        immutable_parts.append("Fallback style bible:\n" + _clean(series.style_bible))

    profile_text = "\n\n".join(_profile_summary(row, data.task_type) for row in profiles if _profile_summary(row, data.task_type))
    relationship_text = "\n".join(card_text_by_type.get("relationship", []))
    character_parts = [profile_text, relationship_text]
    if not profile_text and _clean(series.character_bible):
        character_parts.append("Fallback Character Bible:\n" + _clean(series.character_bible))

    location_prop_parts = [
        "\n".join(card_text_by_type.get("location", [])),
        "\n".join(card_text_by_type.get("prop", [])),
    ]
    if not any(_clean(part) for part in location_prop_parts) and _clean(series.world_bible):
        location_prop_parts.append("Fallback World Bible:\n" + _clean(series.world_bible))

    current_recent_parts = [
        _state_text(state),
        "\n".join(card_text_by_type.get("episode_summary", [])),
        "\n".join(card_text_by_type.get("arc_summary", [])),
        "\n".join(card_text_by_type.get("series_summary", [])),
    ]
    if not any(_clean(part) for part in current_recent_parts) and _clean(series.previous_episode_summary):
        current_recent_parts.append("Fallback previous episode summary:\n" + _clean(series.previous_episode_summary))

    output_rules = [
        "Chi dung the nho da duyet lam canon bat buoc.",
        "Khong tu ghi de trang thai hien tai; moi cap nhat can tao de xuat cho nguoi dung duyet.",
        "Khong ghi token, cookie, provider secret hoac prompt nhay cam vao trace.",
    ]
    if data.task_type in {"voice", "subtitle"}:
        output_rules.append("Voice/subtitle chi can narration, ngon ngu, nguoi noi, cach noi, cam xuc va thoi luong; khong gui toan bo du lieu hinh anh neu khong can.")
    if _clean(series.negative_rules):
        output_rules.append("Negative rules fallback:\n" + _clean(series.negative_rules))

    groups = [
        GroupDraft("immutable_rules", "Quy tac bat bien va danh tinh series", "\n\n".join(_clean(part) for part in immutable_parts if _clean(part)), True),
        GroupDraft("characters_relationships", "Nhan vat va quan he lien quan", "\n\n".join(_clean(part) for part in character_parts if _clean(part)), True),
        GroupDraft("locations_props", "Dia diem va dao cu", "\n\n".join(_clean(part) for part in location_prop_parts if _clean(part))),
        GroupDraft("open_threads", "Mach truyen dang mo", "\n\n".join(card_text_by_type.get("story_thread", []))),
        GroupDraft("current_recent", "Trang thai hien tai va lich su gan", "\n\n".join(_clean(part) for part in current_recent_parts if _clean(part)), True),
        GroupDraft("task_payload", "Noi dung nhiem vu hien tai", _task_payload_text(data), True),
        GroupDraft("output_rules", "Dieu cam va yeu cau dau ra", "\n".join(output_rules), True),
    ]
    budgets = _budget_for_task(data.task_type, data.max_chars or DEFAULT_CONTEXT_MAX_CHARS)
    context_text, group_usage, truncated = _apply_group_budgets(groups, budgets, data.max_chars or DEFAULT_CONTEXT_MAX_CHARS)
    missing_required = []
    if not profile_text and not _clean(series.character_bible):
        missing_required.append("character_profiles_or_character_bible")
    if not _clean(groups[0].body):
        missing_required.append("series_identity_or_canon_rules")
    if data.task_type in {"story_candidate", "master_story", "video_story_development"} and not _clean(groups[5].body):
        missing_required.append("task_payload")

    trace_id: str | None = None
    context_stats = {
        "max_chars": data.max_chars,
        "context_chars": len(context_text),
        "selected_card_count": len(selected_cards),
        "selected_character_profile_count": len(profiles),
        "episode_number": episode_number,
    }
    if data.persist_trace:
        now = datetime.utcnow()
        trace = DBSeriesContextTrace(
            id=str(uuid.uuid4()),
            series_id=series_id,
            project_id=data.project_id,
            story_episode_id=data.story_episode_id,
            task_type=data.task_type,
            target_ref_type=data.target_ref_type,
            target_ref_id=data.target_ref_id,
            selected_cards_json=selected_trace,
            selected_character_profiles_json=[_profile_trace(row) for row in profiles],
            group_budget_json=group_usage,
            missing_required_json=missing_required,
            truncated_groups_json=truncated,
            context_stats_json=context_stats,
            reasons_json=[{"card_id": item["id"], "reason": item["reason"]} for item in selected_trace],
            context_preview=context_text[:CARD_CONTEXT_PREVIEW_CHARS],
            created_at=now,
        )
        db.add(trace)
        db.commit()
        trace_id = trace.id

    return models.SeriesContextCompileResponse(
        trace_id=trace_id,
        series_id=series_id,
        task_type=data.task_type,
        context_text=context_text,
        selected_cards=selected_trace,
        selected_character_profiles=[_profile_trace(row) for row in profiles],
        group_usage=group_usage,
        missing_required=missing_required,
        truncated_groups=truncated,
        context_stats=context_stats,
    )


def compile_prompt_context(
    series_id: str,
    db: Session,
    *,
    task_type: str,
    episode_number: int | None = None,
    project_id: str | None = None,
    story_episode_id: str | None = None,
    user_input: str | None = None,
    current_payload: dict[str, Any] | None = None,
    target_ref_type: str | None = None,
    target_ref_id: str | None = None,
    max_chars: int = DEFAULT_CONTEXT_MAX_CHARS,
    persist_trace: bool = True,
) -> models.SeriesContextCompileResponse:
    return compile_context(
        series_id,
        models.SeriesContextCompileRequest(
            task_type=task_type,
            episode_number=episode_number,
            project_id=project_id,
            story_episode_id=story_episode_id,
            target_ref_type=target_ref_type,
            target_ref_id=target_ref_id,
            user_input=user_input,
            current_payload=current_payload or {},
            max_chars=max_chars,
            persist_trace=persist_trace,
        ),
        db,
    )


def list_context_traces(
    series_id: str,
    db: Session,
    *,
    task_type: str | None = None,
    project_id: str | None = None,
    story_episode_id: str | None = None,
    limit: int = 50,
) -> models.SeriesContextTraceListResponse:
    _require_series(series_id, db)
    query = db.query(DBSeriesContextTrace).filter(DBSeriesContextTrace.series_id == series_id)
    if task_type:
        query = query.filter(DBSeriesContextTrace.task_type == task_type)
    if project_id:
        query = query.filter(DBSeriesContextTrace.project_id == project_id)
    if story_episode_id:
        query = query.filter(DBSeriesContextTrace.story_episode_id == story_episode_id)
    rows = query.order_by(DBSeriesContextTrace.created_at.desc()).limit(limit).all()
    return models.SeriesContextTraceListResponse(items=[_trace_response(row) for row in rows], total=len(rows))


def _rule_terms(content: dict[str, Any], *keys: str) -> list[str]:
    terms: list[str] = []
    for key in keys:
        value = content.get(key)
        if isinstance(value, str):
            terms.append(value)
        elif isinstance(value, list):
            terms.extend(str(item) for item in value if _clean(item))
    return [_clean(term) for term in terms if _clean(term)]


def _check_character_traits(prompt: str, profiles: list[DBSeriesCharacterProfile]) -> list[dict[str, Any]]:
    conflicts: list[dict[str, Any]] = []
    normalized_prompt = _normalize_term(prompt)
    for profile in profiles:
        name_in_prompt = _contains_term(prompt, profile.name)
        fixed_traits = _clean(profile.fixed_traits)
        if not fixed_traits or not name_in_prompt:
            continue
        for trait in re.split(r"[;\n,.]+", fixed_traits):
            trait = trait.strip()
            if len(trait) < 4:
                continue
            trait_norm = _normalize_term(trait)
            for word in NEGATION_WORDS:
                pattern = f"{_normalize_term(word)} {trait_norm}"
                if pattern in normalized_prompt:
                    conflicts.append(
                        {
                            "type": "fixed_trait_changed",
                            "severity": "blocking",
                            "message": f"Prompt co dau hieu thay doi fixed trait cua {profile.name}: {trait}",
                            "evidence_type": "character_profile",
                            "evidence_id": profile.id,
                            "suggestion": f"Giu nguyen fixed trait: {trait}",
                        }
                    )
    return conflicts


def _check_card_rules(prompt: str, cards: list[DBSeriesMemoryCard]) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[str]]:
    conflicts: list[dict[str, Any]] = []
    warnings: list[dict[str, Any]] = []
    evidence_ids: list[str] = []
    for card in cards:
        if card.card_type != "canon_rule":
            continue
        content = _json_dict(card.content_json)
        forbidden_terms = _rule_terms(content, "forbidden", "forbid", "forbidden_terms", "negative", "must_not")
        required_terms = _rule_terms(content, "must", "required", "required_terms", "canon")
        for term in forbidden_terms:
            if _contains_term(prompt, term):
                evidence_ids.append(card.id)
                conflicts.append(
                    {
                        "type": "forbidden_canon_term",
                        "severity": "blocking",
                        "message": f"Prompt dung noi dung bi cam theo the '{card.title}': {term}",
                        "evidence_type": "memory_card",
                        "evidence_id": card.id,
                        "suggestion": f"Loai bo hoac sua phan mau thuan: {term}",
                    }
                )
        for term in required_terms:
            if term and not _contains_term(prompt, term):
                evidence_ids.append(card.id)
                warnings.append(
                    {
                        "type": "missing_required_canon_hint",
                        "severity": "warning",
                        "message": f"Prompt chua nhac ro yeu cau canon tu the '{card.title}': {term}",
                        "evidence_type": "memory_card",
                        "evidence_id": card.id,
                        "suggestion": f"Can nhac them neu phu hop: {term}",
                    }
                )
    return conflicts, warnings, sorted(set(evidence_ids))


def _check_state_rules(prompt: str, state: DBSeriesCurrentState | None) -> tuple[list[dict[str, Any]], list[str]]:
    warnings: list[dict[str, Any]] = []
    evidence_ids: list[str] = []
    if state is None:
        return warnings, evidence_ids
    for prop_name, prop_state in _json_dict(state.prop_states_json).items():
        if not _contains_term(prompt, str(prop_name)):
            continue
        if isinstance(prop_state, dict):
            holder = _clean(prop_state.get("holder") or prop_state.get("owner"))
            if holder and not _contains_term(prompt, holder):
                warnings.append(
                    {
                        "type": "prop_holder_not_mentioned",
                        "severity": "warning",
                        "message": f"Prompt co dao cu '{prop_name}' nhung khong nhac nguoi dang giu hien tai: {holder}",
                        "evidence_type": "current_state",
                        "evidence_id": state.id,
                        "suggestion": f"Kiem tra lai nguoi dang giu {prop_name}: {holder}",
                    }
                )
                evidence_ids.append(state.id)
    return warnings, evidence_ids


def check_canon(
    series_id: str,
    data: models.SeriesCanonCheckRequest,
    db: Session,
) -> models.SeriesCanonCheckResponse:
    _require_series(series_id, db)
    cards = _approved_cards(series_id, None, db)
    profiles = (
        db.query(DBSeriesCharacterProfile)
        .filter(DBSeriesCharacterProfile.series_id == series_id)
        .order_by(DBSeriesCharacterProfile.sort_order.asc(), DBSeriesCharacterProfile.created_at.asc())
        .all()
    )
    conflicts = _check_character_traits(data.prompt, profiles)
    rule_conflicts, rule_warnings, card_evidence_ids = _check_card_rules(data.prompt, cards)
    conflicts.extend(rule_conflicts)
    state_warnings, state_evidence_ids = _check_state_rules(data.prompt, _latest_approved_state(series_id, db))
    warnings = [*rule_warnings, *state_warnings]
    evidence_ids = sorted(
        {
            *card_evidence_ids,
            *state_evidence_ids,
            *[
                str(item.get("evidence_id"))
                for item in conflicts
                if item.get("evidence_id") and item.get("evidence_type") == "memory_card"
            ],
        }
    )
    has_blocking = bool(conflicts)
    override_reason = _clean(data.override_reason)
    passed = not has_blocking or (data.allow_override and bool(override_reason))
    now = datetime.utcnow()
    row = DBSeriesCanonCheck(
        id=str(uuid.uuid4()),
        series_id=series_id,
        project_id=data.project_id,
        story_episode_id=data.story_episode_id,
        prompt_kind=data.prompt_kind,
        prompt_ref_id=data.prompt_ref_id,
        passed=passed,
        blocking_conflicts_json=conflicts,
        warnings_json=warnings,
        evidence_card_ids_json=evidence_ids,
        override_reason=override_reason if data.allow_override and override_reason else None,
        overridden_by="local_user" if data.allow_override and override_reason else None,
        overridden_at=now if data.allow_override and override_reason else None,
        created_at=now,
    )
    db.add(row)
    db.commit()
    return models.SeriesCanonCheckResponse(
        id=row.id,
        series_id=series_id,
        prompt_kind=data.prompt_kind,
        prompt_ref_id=data.prompt_ref_id,
        passed=passed,
        blocking_conflicts=conflicts,
        warnings=warnings,
        evidence_card_ids=evidence_ids,
        suggestions=[str(item.get("suggestion")) for item in [*conflicts, *warnings] if item.get("suggestion")],
        override_reason=row.override_reason,
        created_at=row.created_at,
    )


def latest_canon_checks(
    series_id: str,
    db: Session,
    *,
    project_id: str | None = None,
    story_episode_id: str | None = None,
    limit: int = 50,
) -> list[models.SeriesCanonCheckResponse]:
    _require_series(series_id, db)
    query = db.query(DBSeriesCanonCheck).filter(DBSeriesCanonCheck.series_id == series_id)
    if project_id:
        query = query.filter(DBSeriesCanonCheck.project_id == project_id)
    if story_episode_id:
        query = query.filter(DBSeriesCanonCheck.story_episode_id == story_episode_id)
    rows = query.order_by(DBSeriesCanonCheck.created_at.desc()).limit(limit).all()
    return [
        models.SeriesCanonCheckResponse(
            id=row.id,
            series_id=row.series_id,
            prompt_kind=row.prompt_kind,
            prompt_ref_id=row.prompt_ref_id,
            passed=bool(row.passed),
            blocking_conflicts=[item for item in _json_list(row.blocking_conflicts_json) if isinstance(item, dict)],
            warnings=[item for item in _json_list(row.warnings_json) if isinstance(item, dict)],
            evidence_card_ids=[str(item) for item in _json_list(row.evidence_card_ids_json)],
            suggestions=[
                str(item.get("suggestion"))
                for item in [
                    *[entry for entry in _json_list(row.blocking_conflicts_json) if isinstance(entry, dict)],
                    *[entry for entry in _json_list(row.warnings_json) if isinstance(entry, dict)],
                ]
                if item.get("suggestion")
            ],
            override_reason=row.override_reason,
            created_at=row.created_at,
        )
        for row in rows
    ]
