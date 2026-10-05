"""
Server-side user settings — singleton rows persisted in SQLite so every
client window, API consumer, and headless flow reads the same preferences.

Two domains live here: capture/refine defaults and long-form generation
defaults. Each has a ``get_*`` that lazily creates the row with defaults and
an ``update_*`` that accepts a partial payload.
"""

import os
import shutil
from pathlib import Path
from typing import Any

from sqlalchemy.orm import Session

from ..database import (
    AIPlanningSettings as DBAIPlanningSettings,
    CaptureSettings as DBCaptureSettings,
    GenerationSettings as DBGenerationSettings,
)
from ..utils.capture_chords import (
    default_push_to_talk_chord,
    default_toggle_to_talk_chord,
)

SINGLETON_ID = 1
DEFAULT_CODEX_TIMEOUT_SECONDS = 600
OLD_DEFAULT_CODEX_TIMEOUT_SECONDS = 60
CODEX_REASONING_EFFORTS = {"low", "medium", "high", "xhigh", "max", "ultra"}
CONTENT_PROVIDERS = {"codex", "claude"}
DEFAULT_CONTENT_PROVIDER = "codex"
DEFAULT_CONTENT_MODELS = {
    "codex": "gpt-5.6-sol",
    # Stable Claude CLI aliases follow the user's entitlement and resolve to
    # the newest accessible release. Pinned historical IDs can return 404.
    "claude": "sonnet",
}
LEGACY_CLAUDE_MODEL_ALIASES = {
    "claude-sonnet-4-5": "sonnet",
    "claude-opus-4-1": "opus",
    "claude-haiku-3-5": "haiku",
}


def _get_or_create_capture_row(db: Session) -> DBCaptureSettings:
    row = db.query(DBCaptureSettings).filter(DBCaptureSettings.id == SINGLETON_ID).first()
    if row is None:
        row = DBCaptureSettings(
            id=SINGLETON_ID,
            chord_push_to_talk_keys=default_push_to_talk_chord(),
            chord_toggle_to_talk_keys=default_toggle_to_talk_chord(),
        )
        db.add(row)
        db.commit()
        db.refresh(row)
    return row


def _get_or_create_generation_row(db: Session) -> DBGenerationSettings:
    row = db.query(DBGenerationSettings).filter(DBGenerationSettings.id == SINGLETON_ID).first()
    if row is None:
        row = DBGenerationSettings(id=SINGLETON_ID)
        db.add(row)
        db.commit()
        db.refresh(row)
    return row

def _default_codex_path() -> str | None:
    return os.environ.get("VOICEBOX_CODEX_PATH") or shutil.which("codex")


def _path_exists_or_resolves(path: str | None) -> bool:
    if not path:
        return False
    return Path(path).exists() or shutil.which(path) is not None


def _looks_like_stale_cross_platform_codex_path(path: str | None) -> bool:
    if not path:
        return False
    normalized = path.replace("\\", "/").lower()
    if os.name == "nt":
        return normalized in {
            "/opt/homebrew/bin/codex",
            "/usr/local/bin/codex",
            "/usr/bin/codex",
        }
    return (
        len(path) >= 3
        and path[1] == ":"
        and path[2] in ("\\", "/")
        and normalized.endswith(("/codex.cmd", "/codex.ps1", "/codex.bat"))
    )


def _refresh_codex_path_if_needed(row: DBAIPlanningSettings) -> bool:
    detected = _default_codex_path()
    if not detected:
        return False
    if not row.codex_path:
        row.codex_path = detected
        return True
    # A persisted CLI path can become stale after npm/node is reinstalled or
    # the user switches machines.  Refresh it whenever it no longer resolves,
    # regardless of whether the old path looks cross-platform.
    if not _path_exists_or_resolves(row.codex_path):
        row.codex_path = detected
        return True
    return False


def _default_codex_timeout() -> int:
    try:
        parsed = int(os.environ.get("VOICEBOX_CODEX_TIMEOUT", str(DEFAULT_CODEX_TIMEOUT_SECONDS)))
    except ValueError:
        parsed = DEFAULT_CODEX_TIMEOUT_SECONDS
    return max(5, min(parsed, DEFAULT_CODEX_TIMEOUT_SECONDS))

def _refresh_codex_timeout_if_needed(row: DBAIPlanningSettings) -> bool:
    if int(row.timeout_seconds or 0) != OLD_DEFAULT_CODEX_TIMEOUT_SECONDS:
        return False
    row.timeout_seconds = _default_codex_timeout()
    return True

def _default_codex_reasoning_effort() -> str | None:
    value = (os.environ.get("VOICEBOX_CODEX_REASONING_EFFORT") or "").strip().lower()
    return value if value in CODEX_REASONING_EFFORTS else None

def _get_or_create_ai_planning_row(db: Session) -> DBAIPlanningSettings:
    row = db.query(DBAIPlanningSettings).filter(DBAIPlanningSettings.id == SINGLETON_ID).first()
    if row is None:
        row = DBAIPlanningSettings(
            id=SINGLETON_ID,
            provider="codex-cli",
            codex_path=_default_codex_path(),
            model=os.environ.get("VOICEBOX_CODEX_MODEL"),
            model_reasoning_effort=_default_codex_reasoning_effort(),
            content_provider=(os.environ.get("VOICEBOX_CONTENT_PROVIDER") or DEFAULT_CONTENT_PROVIDER).strip().lower()
            if (os.environ.get("VOICEBOX_CONTENT_PROVIDER") or DEFAULT_CONTENT_PROVIDER).strip().lower() in CONTENT_PROVIDERS
            else DEFAULT_CONTENT_PROVIDER,
            content_model=os.environ.get("VOICEBOX_CONTENT_MODEL") or DEFAULT_CONTENT_MODELS.get(
                (os.environ.get("VOICEBOX_CONTENT_PROVIDER") or DEFAULT_CONTENT_PROVIDER).strip().lower(),
                DEFAULT_CONTENT_MODELS[DEFAULT_CONTENT_PROVIDER],
            ),
            timeout_seconds=_default_codex_timeout(),
        )
        db.add(row)
        db.commit()
        db.refresh(row)
    else:
        changed = _refresh_codex_path_if_needed(row)
        changed = _refresh_codex_timeout_if_needed(row) or changed
        if not getattr(row, "content_provider", None) or row.content_provider not in CONTENT_PROVIDERS:
            row.content_provider = DEFAULT_CONTENT_PROVIDER
            changed = True
        if not getattr(row, "content_model", None):
            row.content_model = DEFAULT_CONTENT_MODELS.get(row.content_provider, DEFAULT_CONTENT_MODELS[DEFAULT_CONTENT_PROVIDER])
            changed = True
        elif row.content_provider == "claude" and row.content_model in LEGACY_CLAUDE_MODEL_ALIASES:
            row.content_model = LEGACY_CLAUDE_MODEL_ALIASES[row.content_model]
            changed = True
        if changed:
            db.commit()
            db.refresh(row)
    return row


def _apply_patch(row: Any, patch: dict[str, Any]) -> None:
    """Apply a partial update to a settings row.

    Values explicitly set to ``None`` are honored only for columns where the
    schema allows it — clearing ``default_playback_voice_id`` works, but a
    ``None`` for a non-nullable field is dropped rather than crashing the
    request. Unknown keys are ignored.
    """
    columns = type(row).__table__.columns
    for key, value in patch.items():
        col = columns.get(key)
        if col is None:
            continue
        if value is None and not col.nullable:
            continue
        setattr(row, key, value)


def get_capture_settings(db: Session) -> DBCaptureSettings:
    """Return the capture settings row, creating it with defaults if missing."""
    return _get_or_create_capture_row(db)


def update_capture_settings(db: Session, patch: dict[str, Any]) -> DBCaptureSettings:
    row = _get_or_create_capture_row(db)
    _apply_patch(row, patch)
    db.commit()
    db.refresh(row)
    return row


def get_generation_settings(db: Session) -> DBGenerationSettings:
    """Return the generation settings row, creating it with defaults if missing."""
    return _get_or_create_generation_row(db)


def update_generation_settings(db: Session, patch: dict[str, Any]) -> DBGenerationSettings:
    row = _get_or_create_generation_row(db)
    _apply_patch(row, patch)
    db.commit()
    db.refresh(row)
    return row

def get_ai_planning_settings(db: Session) -> DBAIPlanningSettings:
    """Return the AI planning settings row, creating it with local Codex defaults."""
    return _get_or_create_ai_planning_row(db)

def update_ai_planning_settings(db: Session, patch: dict[str, Any]) -> DBAIPlanningSettings:
    row = _get_or_create_ai_planning_row(db)
    if "model_reasoning_effort" in patch and isinstance(patch["model_reasoning_effort"], str):
        effort = patch["model_reasoning_effort"].strip().lower()
        if effort and effort not in CODEX_REASONING_EFFORTS:
            raise ValueError("model_reasoning_effort must be one of low, medium, high, xhigh, max, ultra")
        patch["model_reasoning_effort"] = effort if effort else None
    if "content_provider" in patch and isinstance(patch["content_provider"], str):
        provider = patch["content_provider"].strip().lower()
        if provider not in CONTENT_PROVIDERS:
            raise ValueError("content_provider must be one of codex or claude")
        patch["content_provider"] = provider
        if "content_model" not in patch:
            patch["content_model"] = DEFAULT_CONTENT_MODELS[provider]
    if "content_model" in patch and isinstance(patch["content_model"], str):
        model = patch["content_model"].strip()
        patch["content_model"] = LEGACY_CLAUDE_MODEL_ALIASES.get(model, model) or None
    _apply_patch(row, patch)
    db.commit()
    db.refresh(row)
    return row
