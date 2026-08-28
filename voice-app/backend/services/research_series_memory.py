"""Read-only Research adapter for approved AI Video Series memory."""

from __future__ import annotations

import hashlib
import json
from typing import Any

from sqlalchemy.orm import Session

from .. import models
from ..database.models import (
    SeriesCharacterProfile as DBSeriesCharacterProfile,
    SeriesCurrentState as DBSeriesCurrentState,
    SeriesMemoryCard as DBSeriesMemoryCard,
    VideoSeries as DBVideoSeries,
)
from . import series_brain


def _fingerprint(value: Any) -> str:
    payload = json.dumps(value, ensure_ascii=False, sort_keys=True, default=str).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def get_series(series_id: str, db: Session) -> DBVideoSeries | None:
    return db.query(DBVideoSeries).filter(DBVideoSeries.id == series_id).first()


def dependency_fingerprint(
    series_id: str,
    db: Session,
    *,
    episode_number: int | None = None,
    max_chars: int = 40_000,
) -> str | None:
    series = get_series(series_id, db)
    if series is None:
        return None
    cards = (
        db.query(DBSeriesMemoryCard)
        .filter(DBSeriesMemoryCard.series_id == series_id, DBSeriesMemoryCard.status == "approved")
        .order_by(DBSeriesMemoryCard.id.asc())
        .all()
    )
    profiles = (
        db.query(DBSeriesCharacterProfile)
        .filter(DBSeriesCharacterProfile.series_id == series_id)
        .order_by(DBSeriesCharacterProfile.id.asc())
        .all()
    )
    states = (
        db.query(DBSeriesCurrentState)
        .filter(DBSeriesCurrentState.series_id == series_id, DBSeriesCurrentState.approval_status == "approved")
        .order_by(DBSeriesCurrentState.id.asc())
        .all()
    )
    return _fingerprint(
        {
            "series": {
                "id": series.id,
                "revision": int(series.revision or 1),
                "updated_at": series.updated_at,
                "latest_episode_number": int(series.latest_episode_number or 0),
                "character_bible": series.character_bible,
                "world_bible": series.world_bible,
                "style_bible": series.style_bible,
                "continuity_rules": series.continuity_rules,
                "negative_rules": series.negative_rules,
                "previous_episode_summary": series.previous_episode_summary,
            },
            "memory_cards": [
                {
                    "id": row.id,
                    "revision": int(row.revision or 1),
                    "updated_at": row.updated_at,
                    "effective_from_episode": row.effective_from_episode,
                    "effective_to_episode": row.effective_to_episode,
                }
                for row in cards
            ],
            "character_profiles": [
                {"id": row.id, "revision": int(row.revision or 1), "updated_at": row.updated_at}
                for row in profiles
            ],
            "current_states": [
                {"id": row.id, "revision": int(row.revision or 1), "updated_at": row.updated_at}
                for row in states
            ],
            "episode_number": episode_number,
            "max_chars": max_chars,
        }
    )


def compile_package(
    *,
    source_id: str,
    series_id: str,
    research_project_id: str,
    research_brief: str | None,
    source_revision: int,
    episode_number: int | None,
    max_chars: int,
    db: Session,
) -> tuple[dict[str, Any], dict[str, Any], str]:
    series = get_series(series_id, db)
    if series is None:
        raise series_brain.SeriesBrainError("Không tìm thấy Series để liên kết memory.")
    fingerprint = dependency_fingerprint(
        series_id,
        db,
        episode_number=episode_number,
        max_chars=max_chars,
    )
    if fingerprint is None:
        raise series_brain.SeriesBrainError("Không đọc được fingerprint của Series Memory.")
    compiled = series_brain.compile_context(
        series_id,
        models.SeriesContextCompileRequest(
            task_type="video_story_development",
            episode_number=episode_number,
            user_input=(research_brief or "Nghiên cứu và phát triển tiếp nội dung series hiện tại.")[:50_000],
            current_payload={
                "research_project_id": research_project_id,
                "research_source_id": source_id,
                "read_only": True,
            },
            target_ref_type="research_source",
            target_ref_id=source_id,
            max_chars=max_chars,
            persist_trace=False,
        ),
        db,
    )
    limitations: list[str] = []
    if compiled.missing_required:
        limitations.append("Series Memory còn thiếu: " + ", ".join(compiled.missing_required))
    if compiled.truncated_groups:
        limitations.append("Context đã rút gọn các nhóm: " + ", ".join(compiled.truncated_groups))
    summary = (
        f"Đang đọc trực tiếp memory đã duyệt của Series '{series.title}' "
        f"(Series r{int(series.revision or 1)}, {len(compiled.selected_cards)} thẻ memory, "
        f"{len(compiled.selected_character_profiles)} hồ sơ nhân vật)."
    )
    evidence_refs = [
        {"kind": "series_memory_card", "id": item.get("id"), "revision": item.get("revision")}
        for item in compiled.selected_cards
        if item.get("id")
    ]
    evidence_refs.extend(
        {
            "kind": "series_character_profile",
            "id": item.get("id"),
            "revision": item.get("revision"),
        }
        for item in compiled.selected_character_profiles
        if item.get("id")
    )
    package = {
        "schema_version": "research_source_package.v1",
        "source_id": source_id,
        "source_type": "series_memory",
        "revision": source_revision,
        "summary": summary,
        "context_text": compiled.context_text,
        "observations": [{"kind": "series_memory_snapshot", "summary": summary}],
        "content_lessons": [],
        "evidence_refs": evidence_refs[:300],
        "coverage": {
            "analysis_complete": True,
            "read_only": True,
            "series_revision": int(series.revision or 1),
            "selected_card_count": len(compiled.selected_cards),
            "selected_character_profile_count": len(compiled.selected_character_profiles),
            "context_chars": len(compiled.context_text),
            "missing_required": compiled.missing_required,
            "truncated_groups": compiled.truncated_groups,
        },
        "progress": 1.0,
        "limitations": limitations,
        "fingerprint": fingerprint,
    }
    provenance = {
        "source_type": "series_memory",
        "series_id": series.id,
        "series_title": series.title,
        "series_revision": int(series.revision or 1),
        "episode_number": episode_number,
        "max_chars": max_chars,
        "dependency_fingerprint": fingerprint,
        "read_only": True,
        "approved_canon_only": True,
    }
    return package, provenance, fingerprint


__all__ = ["compile_package", "dependency_fingerprint", "get_series"]
