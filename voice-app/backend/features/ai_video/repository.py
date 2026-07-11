"""Repository helpers for AI Video database access."""

from __future__ import annotations

from sqlalchemy.orm import Session

from ...database import (
    VideoAutoRun,
    VideoPackageExport,
    VideoProject,
    VideoRenderJob,
    VideoScene,
    VideoSceneAsset,
    VideoScenePrompt,
    VideoSeries,
    VideoShot,
    VideoShotClip,
    VideoShotPrompt,
    VideoSourceBlock,
    VideoSubtitle,
)


def get_project(db: Session, project_id: str) -> VideoProject | None:
    """Return one AI Video project by id."""
    return db.query(VideoProject).filter(VideoProject.id == project_id).first()


__all__ = [
    "VideoAutoRun",
    "VideoPackageExport",
    "VideoProject",
    "VideoRenderJob",
    "VideoScene",
    "VideoSceneAsset",
    "VideoScenePrompt",
    "VideoSeries",
    "VideoShot",
    "VideoShotClip",
    "VideoShotPrompt",
    "VideoSourceBlock",
    "VideoSubtitle",
    "get_project",
]
