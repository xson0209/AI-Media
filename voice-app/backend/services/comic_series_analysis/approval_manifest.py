"""Immutable approval-manifest service for Comic Series Analysis (§6.15, §1.12).

When a user approves an analysis revision, this builds an immutable manifest
classifying every relevant item as ``accepted`` / ``excluded`` /
``unreviewed``, records the accepted limitations, requested development mode
and rights attestation revision, and computes a stable ``manifest_hash``.

Rules:
  - Only ``accepted`` items may be handed off or used by the context
    compiler; ``unreviewed`` items are never treated as approved source.
  - Editing selection or content after approval creates a *new* revision and
    invalidates the previous manifest (``active=False``).
"""

from __future__ import annotations

import hashlib
import json

from sqlalchemy.orm import Session

from ...database import ComicApprovalManifest as DBComicApprovalManifest
from .contracts import (
    APPROVAL_MANIFEST_SCHEMA_VERSION,
    APPROVAL_ITEM_STATES,
    ComicAnalysisError,
)


def compute_manifest_hash(
    *,
    analysis_revision: int,
    accepted_items: list[dict],
    excluded_items: list[dict],
    unreviewed_items: list[dict],
    accepted_limitations: list[str],
    development_mode: str,
    rights_attestation_revision: int,
) -> str:
    """Deterministic hash over the manifest's semantically significant fields."""
    canonical = json.dumps(
        {
            "schema": APPROVAL_MANIFEST_SCHEMA_VERSION,
            "analysis_revision": analysis_revision,
            "accepted": sorted(_item_keys(accepted_items)),
            "excluded": sorted(_item_keys(excluded_items)),
            "unreviewed": sorted(_item_keys(unreviewed_items)),
            "limitations": sorted(accepted_limitations),
            "development_mode": development_mode,
            "rights_attestation_revision": rights_attestation_revision,
        },
        ensure_ascii=False,
        sort_keys=True,
    )
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _item_keys(items: list[dict]) -> list[str]:
    keys = []
    for item in items:
        item_type = item.get("item_type", "")
        item_id = item.get("id", "")
        revision = item.get("revision", "")
        keys.append(f"{item_type}:{item_id}:{revision}")
    return keys


def create_manifest(
    db: Session,
    *,
    job_id: str,
    analysis_revision: int,
    accepted_items: list[dict],
    excluded_items: list[dict],
    unreviewed_items: list[dict],
    accepted_limitations: list[str] | None = None,
    development_mode: str,
    rights_attestation_revision: int,
    source_document_revision: int | None = None,
) -> DBComicApprovalManifest:
    """Create an immutable manifest and deactivate any prior active one."""
    accepted_limitations = accepted_limitations or []

    # Invalidate previous active manifests for this job (task 6.15).
    prior = (
        db.query(DBComicApprovalManifest)
        .filter(
            DBComicApprovalManifest.job_id == job_id,
            DBComicApprovalManifest.active == True,  # noqa: E712
        )
        .all()
    )
    for row in prior:
        row.active = False

    manifest_hash = compute_manifest_hash(
        analysis_revision=analysis_revision,
        accepted_items=accepted_items,
        excluded_items=excluded_items,
        unreviewed_items=unreviewed_items,
        accepted_limitations=accepted_limitations,
        development_mode=development_mode,
        rights_attestation_revision=rights_attestation_revision,
    )

    manifest = DBComicApprovalManifest(
        job_id=job_id,
        analysis_revision=analysis_revision,
        schema_version=APPROVAL_MANIFEST_SCHEMA_VERSION,
        manifest_hash=manifest_hash,
        accepted_items_json=accepted_items,
        excluded_items_json=excluded_items,
        unreviewed_items_json=unreviewed_items,
        accepted_limitations_json=accepted_limitations,
        requested_development_mode=development_mode,
        rights_attestation_revision=rights_attestation_revision,
        source_document_revision=source_document_revision,
        active=True,
    )
    db.add(manifest)
    db.flush()
    return manifest


def get_active_manifest(db: Session, job_id: str) -> DBComicApprovalManifest | None:
    """Return the currently active approval manifest for a job, if any."""
    return (
        db.query(DBComicApprovalManifest)
        .filter(
            DBComicApprovalManifest.job_id == job_id,
            DBComicApprovalManifest.active == True,  # noqa: E712
        )
        .order_by(DBComicApprovalManifest.created_at.desc())
        .first()
    )


def accepted_item_ids(manifest: DBComicApprovalManifest) -> set[str]:
    """Set of accepted item ids — the only items eligible for handoff."""
    return {item.get("id", "") for item in (manifest.accepted_items_json or [])}


def assert_item_accepted(manifest: DBComicApprovalManifest, item_id: str) -> None:
    """Raise if an item is not in the accepted set (handoff guard)."""
    if item_id not in accepted_item_ids(manifest):
        raise ComicAnalysisError(
            "COMIC_ITEM_UNREVIEWED", f"Item {item_id} chưa được duyệt để handoff."
        )


def validate_classification(items: list[dict]) -> None:
    """Ensure every item carries a valid state (defensive)."""
    for item in items:
        state = item.get("state")
        if state not in APPROVAL_ITEM_STATES:
            raise ComicAnalysisError(
                "COMIC_ANALYSIS_INVALID_STATE", f"Trạng thái item không hợp lệ: {state!r}"
            )


__all__ = [
    "accepted_item_ids",
    "assert_item_accepted",
    "compute_manifest_hash",
    "create_manifest",
    "get_active_manifest",
    "validate_classification",
]
