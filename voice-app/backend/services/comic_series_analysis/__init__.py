"""Comic Series Analysis — an independent feature module.

This package ingests comic sources (public web links or uploaded images),
performs multimodal analysis (OCR/vision, panels, dialogue, characters,
locations, plot, canon) and hands the approved result off to Series /
Story Studio as a Story Episode with a full ``StoryEpisodeSourceDocument``.

Boundary rules (see ``openspec`` change 13):
  - No import of ``video_inspiration`` / ``video_inspiration_runs`` or any
    AI Video handoff. This module only intersects with the Series and Story
    Studio domain.
  - No foreign key to ``video_inspiration_jobs``.
  - No endpoint or action that hands off directly to AI Video.

Only neutral infrastructure is reused: the DB session, artifact storage,
the shared planning concurrency pool, background task creation,
observability and versioning/stale primitives.
"""

from __future__ import annotations

from . import contracts, config  # noqa: F401

__all__ = ["contracts", "config"]
