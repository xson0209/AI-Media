"""Story Episode source access + task-based context compiler (§9).

Full chapter content lives in ``StoryEpisodeSourceDocument`` / chunks — never
in Series Memory or ``series-memory.md`` (§9.9). The compiler retrieves the
synopsis, plot beats and only the *relevant, accepted* chunks within a
character budget instead of stuffing the whole chapter into every prompt
(§9.3, §9.11), and pins the source document revision so the three candidates
share one snapshot (§9.4).

Also provides the atomic ``current_source_document_id`` pointer swap (§9.14)
and the precise stale marking for candidates / Master Story (§9.15, §1.11).
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field

from sqlalchemy.orm import Session

from ...database import (
    StoryEpisode as DBStoryEpisode,
    StoryEpisodeSourceChunk as DBEpChunk,
    StoryEpisodeSourceDocument as DBEpDoc,
    StoryScenarioCandidate as DBCandidate,
)
from .. import source_package as source_package_core
from .contracts import STALE_STATUS


@dataclass
class EpisodeSourceSummary:
    """Lightweight source summary for episode responses (§9.1)."""

    source_document_id: str | None
    revision: int | None
    source_kind: str | None
    comic_job_id: str | None
    comic_analysis_revision: int | None
    chunk_count: int
    page_count: int
    panel_count: int
    dialogue_count: int
    coverage_metrics: dict | None
    limitations: list | None
    has_structured_source: bool


def get_current_document(db: Session, episode_id: str) -> DBEpDoc | None:
    """The episode's current approved source document (never a newer unapproved one)."""
    episode = db.query(DBStoryEpisode).filter(DBStoryEpisode.id == episode_id).first()
    if episode is None or not episode.current_source_document_id:
        return None
    return (
        db.query(DBEpDoc)
        .filter(DBEpDoc.id == episode.current_source_document_id)
        .first()
    )


def source_summary(db: Session, episode_id: str) -> EpisodeSourceSummary:
    """Build the episode source summary (counts only, no long payloads)."""
    doc = get_current_document(db, episode_id)
    if doc is None:
        return EpisodeSourceSummary(
            source_document_id=None, revision=None, source_kind=None,
            comic_job_id=None, comic_analysis_revision=None, chunk_count=0,
            page_count=0, panel_count=0, dialogue_count=0,
            coverage_metrics=None, limitations=None,
            has_structured_source=False,
        )
    chunks = db.query(DBEpChunk).filter(DBEpChunk.document_id == doc.id).all()
    chunk_count = len(chunks)
    page_count = sum(1 for chunk in chunks if chunk.page_refs_json)
    panel_count = sum(
        1
        for chunk in chunks
        if chunk.panel_refs_json or chunk.chunk_type in {"panel", "visual"}
    )
    dialogue_count = sum(
        1
        for chunk in chunks
        if chunk.bubble_refs_json or chunk.chunk_type in {"dialogue", "narration"}
    )
    return EpisodeSourceSummary(
        source_document_id=doc.id,
        revision=doc.revision,
        source_kind=doc.source_kind,
        comic_job_id=doc.comic_job_id,
        comic_analysis_revision=doc.comic_analysis_revision,
        chunk_count=chunk_count,
        page_count=page_count,
        panel_count=panel_count,
        dialogue_count=dialogue_count,
        coverage_metrics=doc.coverage_metrics_json,
        limitations=doc.limitations_json,
        has_structured_source=True,
    )


@dataclass
class CompiledContext:
    """A task-scoped context package pinned to one source revision."""

    source_document_id: str | None
    source_revision: int | None
    synopsis: str | None
    plot_beats: list = field(default_factory=list)
    chunks: list[dict] = field(default_factory=list)
    limitations: list = field(default_factory=list)
    used_chunk_ids: list[str] = field(default_factory=list)
    omitted_chunk_count: int = 0
    fingerprint: str = ""
    development_mode: str | None = None


@dataclass
class SourcePackageSummary:
    """Canonical Source Package for a story episode."""

    source_package: source_package_core.SourcePackage
    selected_chunk_count: int
    omitted_chunk_count: int


def compile_context(
    db: Session,
    episode_id: str,
    *,
    char_budget: int = 24_000,
    task_type: str = "story_candidate",
) -> CompiledContext:
    """Compile task context from the approved source (§9.3, §9.11, §9.12).

    - Only ``accepted`` chunks are used as creative source; ``unreviewed``
      chunks are excluded (§9.11).
    - Relevant chunks are selected within ``char_budget``; the remainder is
      reported as omitted, never silently replaced (§9.3).
    - The fingerprint includes the source revision + development mode so a
      changed source/mode invalidates any cache (§9.12).
    """
    episode = db.query(DBStoryEpisode).filter(DBStoryEpisode.id == episode_id).first()
    doc = get_current_document(db, episode_id)
    if doc is None:
        return CompiledContext(source_document_id=None, source_revision=None, synopsis=None)

    chunks = (
        db.query(DBEpChunk)
        .filter(
            DBEpChunk.document_id == doc.id,
            DBEpChunk.approval_state == "accepted",  # §9.11
        )
        .order_by(DBEpChunk.chunk_order)
        .all()
    )

    selected: list[dict] = []
    used_ids: list[str] = []
    used_chars = 0
    omitted = 0
    for chunk in chunks:
        text = chunk.approved_text or ""
        if used_chars + len(text) <= char_budget:
            selected.append(
                {
                    "id": chunk.id,
                    "chunk_order": chunk.chunk_order,
                    "chunk_type": chunk.chunk_type,
                    "text": text,
                    "evidence_ids": chunk.evidence_ids_json,
                    "source_revision": chunk.source_revision,
                }
            )
            used_ids.append(chunk.id)
            used_chars += len(text)
        else:
            omitted += 1

    development_mode = episode.development_mode if episode else None
    fingerprint = _context_fingerprint(
        source_document_id=doc.id,
        source_revision=doc.revision,
        development_mode=development_mode,
        used_chunk_ids=used_ids,
    )

    return CompiledContext(
        source_document_id=doc.id,
        source_revision=doc.revision,
        synopsis=doc.synopsis,
        plot_beats=(doc.plot_structure_json or {}).get("beats", []) if doc.plot_structure_json else [],
        chunks=selected,
        limitations=doc.limitations_json or [],
        used_chunk_ids=used_ids,
        omitted_chunk_count=omitted,
        fingerprint=fingerprint,
        development_mode=development_mode,
    )


def compile_source_package(
    db: Session,
    episode_id: str,
    *,
    char_budget: int = 24_000,
    task_type: str = "story_candidate",
) -> SourcePackageSummary:
    """Compile the episode's approved source into a canonical Source Package."""

    context = compile_context(db, episode_id, char_budget=char_budget, task_type=task_type)
    doc = get_current_document(db, episode_id)
    if doc is None:
        package = source_package_core.build_source_package(
            source_kind="story_episode_source",
            source_ref_id=None,
            source_revision=None,
            title=None,
            summary=None,
            blocks=[],
        )
        return SourcePackageSummary(source_package=package, selected_chunk_count=0, omitted_chunk_count=0)

    blocks: list[source_package_core.SourcePackageBlock] = []
    if context.synopsis:
        blocks.append(
            source_package_core.SourcePackageBlock(
                block_type="synopsis",
                content=context.synopsis,
                sort_order=1,
                metadata={"episode_id": episode_id, "task_type": task_type},
            )
        )
    if context.plot_beats:
        blocks.append(
            source_package_core.SourcePackageBlock(
                block_type="plot_beats",
                content={"beats": context.plot_beats},
                sort_order=2,
                metadata={"episode_id": episode_id, "task_type": task_type},
            )
        )
    for index, chunk in enumerate(context.chunks, start=3):
        blocks.append(
            source_package_core.SourcePackageBlock(
                block_type=str(chunk.get("chunk_type") or "text"),
                content={
                    "id": chunk.get("id"),
                    "chunk_order": chunk.get("chunk_order"),
                    "text": chunk.get("text"),
                    "evidence_ids": chunk.get("evidence_ids"),
                    "source_revision": chunk.get("source_revision"),
                },
                sort_order=index,
                metadata={
                    "episode_id": episode_id,
                    "chunk_id": chunk.get("id"),
                    "chunk_order": chunk.get("chunk_order"),
                },
            )
        )

    package = source_package_core.build_source_package(
        source_kind="story_episode_source",
        source_ref_id=context.source_document_id,
        source_revision=context.source_revision,
        title=doc.title,
        summary=context.synopsis,
        blocks=blocks,
        coverage_metrics=doc.coverage_metrics_json or {},
        limitations=doc.limitations_json or [],
        provenance={
            "episode_id": episode_id,
            "source_document_id": doc.id,
            "source_kind": doc.source_kind,
            "comic_job_id": doc.comic_job_id,
            "comic_analysis_revision": doc.comic_analysis_revision,
            "used_chunk_ids": context.used_chunk_ids,
            "omitted_chunk_count": context.omitted_chunk_count,
            "development_mode": context.development_mode,
            "fingerprint": context.fingerprint,
        },
    )
    return SourcePackageSummary(
        source_package=package,
        selected_chunk_count=len(context.chunks),
        omitted_chunk_count=context.omitted_chunk_count,
    )


def _context_fingerprint(*, source_document_id, source_revision, development_mode, used_chunk_ids) -> str:
    return hashlib.sha256(
        json.dumps(
            {
                "doc": source_document_id,
                "rev": source_revision,
                "mode": development_mode,
                "chunks": sorted(used_chunk_ids),
            },
            sort_keys=True,
        ).encode("utf-8")
    ).hexdigest()


# --------------------------------------------------------------------------
# Atomic pointer swap + stale propagation (§9.14, §9.15)
# --------------------------------------------------------------------------

def swap_current_source(db: Session, episode_id: str, new_document_id: str) -> None:
    """Atomically point the episode at a new approved source document (§9.14).

    The previous document is marked ``superseded`` but kept for history. The
    API never auto-selects a newer unapproved revision — the caller passes an
    explicitly approved document id.
    """
    episode = db.query(DBStoryEpisode).filter(DBStoryEpisode.id == episode_id).first()
    if episode is None:
        return
    new_doc = db.query(DBEpDoc).filter(DBEpDoc.id == new_document_id).first()
    if new_doc is None or new_doc.approval_status != "approved":
        raise ValueError("New source document must be approved before swap.")
    prev_id = episode.current_source_document_id
    if prev_id and prev_id != new_document_id:
        prev = db.query(DBEpDoc).filter(DBEpDoc.id == prev_id).first()
        if prev is not None:
            prev.approval_status = "superseded"
    episode.current_source_document_id = new_document_id
    db.flush()


def mark_dependent_candidates_stale(db: Session, episode_id: str, *, old_source_revision: int) -> int:
    """Stale candidates that used the old source revision (§9.15, §1.11).

    Candidates: generation_status = evaluation_status = "stale", clear
    selected. Master Story: approval_status = "stale", clear approved_at.
    """
    count = 0
    candidates = (
        db.query(DBCandidate)
        .filter(DBCandidate.story_episode_id == episode_id)
        .all()
    )
    for cand in candidates:
        if cand.source_document_revision == old_source_revision:
            cand.generation_status = STALE_STATUS
            cand.evaluation_status = STALE_STATUS
            cand.selected = False
            count += 1

    episode = db.query(DBStoryEpisode).filter(DBStoryEpisode.id == episode_id).first()
    if episode is not None and episode.master_story_json:
        episode.master_story_approval_status = STALE_STATUS
        episode.master_story_approved_at = None
    db.flush()
    return count


__all__ = [
    "CompiledContext",
    "EpisodeSourceSummary",
    "SourcePackageSummary",
    "compile_context",
    "compile_source_package",
    "get_current_document",
    "mark_dependent_candidates_stale",
    "source_summary",
    "swap_current_source",
]
