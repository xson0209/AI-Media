"""Shared state helpers for AI Video Assistant."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy.orm import Session

from ..database import VideoPackageExport as DBVideoPackageExport, VideoProject as DBVideoProject


def mark_package_stale(project: DBVideoProject, db: Session) -> None:
    """Mark current and previous package exports stale after source artifacts change."""
    project.package_stale = True
    project.updated_at = datetime.utcnow()
    db.query(DBVideoPackageExport).filter(DBVideoPackageExport.project_id == project.id).update(
        {"stale": True},
        synchronize_session=False,
    )
