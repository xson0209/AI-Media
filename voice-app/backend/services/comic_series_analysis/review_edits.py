"""Review-edit operations for Comic Series Analysis (§7.7, §7.8, §7.11).

Every mutation here creates a new *immutable* analysis revision (bumping
``job.analysis_revision``) and invalidates any active approval manifest, so
an approved revision is never edited in place (§7.11). Edits use an
``expected_revision`` optimistic check to detect concurrent overwrites
(§7.7). Character merge/split rewrites all evidence references in one
transaction (§7.8).
"""

from __future__ import annotations

from sqlalchemy.orm import Session

from ...database import (
    ComicAnalysisJob as DBJob,
    ComicApprovalManifest as DBManifest,
    ComicDetectedCharacter as DBCharacter,
    ComicPanel as DBPanel,
    ComicSpeechBubble as DBBubble,
)
from .contracts import ComicAnalysisError


def _job(db: Session, job_id: str) -> DBJob:
    job = db.query(DBJob).filter(DBJob.id == job_id).first()
    if job is None:
        raise ComicAnalysisError("COMIC_ANALYSIS_NOT_FOUND", status_code=404)
    return job


def _check_revision(job: DBJob, expected_revision: int | None) -> None:
    if expected_revision is not None and expected_revision != job.analysis_revision:
        raise ComicAnalysisError("COMIC_REVISION_CONFLICT", status_code=409)


def _bump_revision_and_invalidate(db: Session, job: DBJob) -> int:
    """Create a new analysis revision and invalidate active approval (§7.11)."""
    job.analysis_revision = (job.analysis_revision or 0) + 1
    active = (
        db.query(DBManifest)
        .filter(DBManifest.job_id == job.id, DBManifest.active == True)  # noqa: E712
        .all()
    )
    for manifest in active:
        manifest.active = False
    if job.run_status == "approved":
        job.run_status = "ready_for_review"
    return job.analysis_revision


def edit_bubble(
    db: Session,
    job_id: str,
    bubble_id: str,
    *,
    expected_revision: int | None = None,
    approved_text: str | None = None,
    bubble_type: str | None = None,
    speaker_character_id: str | None = None,
) -> int:
    """Edit OCR/dialogue text, bubble type or speaker (§7.7).

    Keeps raw + AI text intact, sets the approved/user-edited layer.
    Returns the new analysis revision.
    """
    job = _job(db, job_id)
    _check_revision(job, expected_revision)
    bubble = db.query(DBBubble).filter(DBBubble.id == bubble_id, DBBubble.job_id == job_id).first()
    if bubble is None:
        raise ComicAnalysisError("COMIC_ANALYSIS_NOT_FOUND", "Không tìm thấy bong bóng thoại.", status_code=404)

    if approved_text is not None:
        bubble.approved_text = approved_text
        bubble.edit_source = "user_edited"
    if bubble_type is not None:
        bubble.bubble_type = bubble_type
        bubble.edit_source = "user_edited"
    if speaker_character_id is not None:
        bubble.speaker_character_id = speaker_character_id
        bubble.edit_source = "user_edited"

    revision = _bump_revision_and_invalidate(db, job)
    db.commit()
    return revision


def reorder_panels(
    db: Session,
    job_id: str,
    ordered_panel_ids: list[str],
    *,
    expected_revision: int | None = None,
) -> int:
    """Set explicit reading order for panels (§7.7)."""
    job = _job(db, job_id)
    _check_revision(job, expected_revision)
    panels = {
        p.id: p
        for p in db.query(DBPanel).filter(DBPanel.job_id == job_id).all()
    }
    for order, panel_id in enumerate(ordered_panel_ids):
        panel = panels.get(panel_id)
        if panel is None:
            raise ComicAnalysisError("COMIC_ANALYSIS_NOT_FOUND", f"Không tìm thấy panel {panel_id}.", status_code=404)
        panel.reading_order = order
        panel.edit_source = "user_edited"
    revision = _bump_revision_and_invalidate(db, job)
    db.commit()
    return revision


def merge_characters(
    db: Session,
    job_id: str,
    *,
    source_ids: list[str],
    target_id: str,
    expected_revision: int | None = None,
) -> int:
    """Merge characters into a target, rewriting evidence references (§7.8).

    All bubble speaker references pointing at a merged id are repointed to the
    target in the same transaction, then the merged rows are removed.
    """
    job = _job(db, job_id)
    _check_revision(job, expected_revision)
    target = db.query(DBCharacter).filter(DBCharacter.id == target_id, DBCharacter.job_id == job_id).first()
    if target is None:
        raise ComicAnalysisError("COMIC_ANALYSIS_NOT_FOUND", "Không tìm thấy nhân vật đích.", status_code=404)

    merged_ids = [cid for cid in source_ids if cid != target_id]
    # Repoint speaker references.
    bubbles = (
        db.query(DBBubble)
        .filter(DBBubble.job_id == job_id, DBBubble.speaker_character_id.in_(merged_ids))
        .all()
    )
    for bubble in bubbles:
        bubble.speaker_character_id = target_id

    # Fold aliases/evidence into the target.
    for cid in merged_ids:
        src = db.query(DBCharacter).filter(DBCharacter.id == cid, DBCharacter.job_id == job_id).first()
        if src is None:
            continue
        aliases = list(target.aliases_json or [])
        if src.display_name and src.display_name not in aliases:
            aliases.append(src.display_name)
        aliases.extend(a for a in (src.aliases_json or []) if a not in aliases)
        target.aliases_json = aliases
        evidence = list(target.evidence_ids_json or [])
        evidence.extend(e for e in (src.evidence_ids_json or []) if e not in evidence)
        target.evidence_ids_json = evidence
        db.delete(src)

    target.edit_source = "user_edited"
    revision = _bump_revision_and_invalidate(db, job)
    db.commit()
    return revision


def split_character(
    db: Session,
    job_id: str,
    character_id: str,
    *,
    new_name: str,
    moved_evidence_ids: list[str],
    expected_revision: int | None = None,
) -> tuple[int, str]:
    """Split a cluster into a new character carrying the moved evidence (§7.8)."""
    job = _job(db, job_id)
    _check_revision(job, expected_revision)
    src = db.query(DBCharacter).filter(DBCharacter.id == character_id, DBCharacter.job_id == job_id).first()
    if src is None:
        raise ComicAnalysisError("COMIC_ANALYSIS_NOT_FOUND", "Không tìm thấy nhân vật.", status_code=404)

    moved = set(moved_evidence_ids)
    src_evidence = [e for e in (src.evidence_ids_json or []) if e not in moved]
    src.evidence_ids_json = src_evidence
    src.edit_source = "user_edited"

    new_char = DBCharacter(
        job_id=job_id,
        analysis_revision=job.analysis_revision + 1,
        display_name=new_name,
        evidence_ids_json=list(moved),
        edit_source="user_edited",
    )
    db.add(new_char)
    db.flush()
    revision = _bump_revision_and_invalidate(db, job)
    db.commit()
    return revision, new_char.id


__all__ = [
    "edit_bubble",
    "merge_characters",
    "reorder_panels",
    "split_character",
]
