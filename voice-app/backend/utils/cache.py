"""
Voice prompt caching utilities.
"""

from __future__ import annotations

import hashlib
import logging
import os
from collections import OrderedDict
from contextlib import suppress
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

import torch

from .. import config

logger = logging.getLogger(__name__)

VOICE_PROMPT_MEMORY_MAX_ENTRIES_ENV = "VOICEBOX_VOICE_PROMPT_MEMORY_MAX_ENTRIES"
VOICE_PROMPT_MEMORY_MAX_MB_ENV = "VOICEBOX_VOICE_PROMPT_MEMORY_MAX_MB"
VOICE_PROMPT_MEMORY_TTL_SECONDS_ENV = "VOICEBOX_VOICE_PROMPT_MEMORY_TTL_SECONDS"


def _get_cache_dir() -> Path:
    """Get cache directory from config."""
    return config.get_cache_dir()


@dataclass
class VoicePromptCacheEntry:
    value: torch.Tensor | dict[str, Any]
    created_at: datetime = field(default_factory=datetime.utcnow)
    last_accessed_at: datetime = field(default_factory=datetime.utcnow)
    estimated_bytes: int = 0


_memory_cache: OrderedDict[str, VoicePromptCacheEntry] = OrderedDict()
_cache_stats = {
    "hits_memory": 0,
    "hits_disk": 0,
    "misses": 0,
    "evictions": 0,
}


def get_cache_key(audio_path: str, reference_text: str) -> str:
    """
    Generate cache key from audio file and reference text.

    Args:
        audio_path: Path to audio file
        reference_text: Reference text

    Returns:
        Cache key (MD5 hash)
    """
    with open(audio_path, "rb") as f:
        audio_bytes = f.read()

    combined = audio_bytes + reference_text.encode("utf-8")
    return hashlib.md5(combined).hexdigest()


def _max_entries() -> int:
    try:
        return max(1, int(os.environ.get(VOICE_PROMPT_MEMORY_MAX_ENTRIES_ENV, "24")))
    except ValueError:
        return 24


def _max_bytes() -> int:
    try:
        mb = max(1, int(os.environ.get(VOICE_PROMPT_MEMORY_MAX_MB_ENV, "256")))
    except ValueError:
        mb = 256
    return mb * 1024 * 1024


def _ttl() -> timedelta:
    try:
        seconds = max(0, int(os.environ.get(VOICE_PROMPT_MEMORY_TTL_SECONDS_ENV, "3600")))
    except ValueError:
        seconds = 3600
    return timedelta(seconds=seconds)


def _estimate_size(value: Any) -> int:
    if isinstance(value, torch.Tensor):
        return int(value.element_size() * value.nelement())
    if isinstance(value, dict):
        return sum(_estimate_size(item) for item in value.values())
    if isinstance(value, (list, tuple)):
        return sum(_estimate_size(item) for item in value)
    if isinstance(value, (bytes, bytearray, str)):
        return len(value)
    if isinstance(value, (int, float, bool)) or value is None:
        return 32
    return 256


def _memory_cache_bytes() -> int:
    return sum(entry.estimated_bytes for entry in _memory_cache.values())


def _is_expired(entry: VoicePromptCacheEntry) -> bool:
    ttl = _ttl()
    if ttl.total_seconds() <= 0:
        return False
    return datetime.utcnow() - entry.created_at > ttl


def _remember_memory(cache_key: str, value: torch.Tensor | dict[str, Any]) -> None:
    _memory_cache[cache_key] = VoicePromptCacheEntry(
        value=value,
        estimated_bytes=_estimate_size(value),
    )
    _memory_cache.move_to_end(cache_key)
    _enforce_memory_limits()


def _enforce_memory_limits() -> None:
    for key in list(_memory_cache.keys()):
        if _is_expired(_memory_cache[key]):
            _memory_cache.pop(key, None)
            _cache_stats["evictions"] += 1

    max_entries = _max_entries()
    max_bytes = _max_bytes()
    while len(_memory_cache) > max_entries or _memory_cache_bytes() > max_bytes:
        if not _memory_cache:
            break
        _memory_cache.popitem(last=False)
        _cache_stats["evictions"] += 1


def get_cached_voice_prompt(
    cache_key: str,
) -> torch.Tensor | dict[str, Any] | None:
    """
    Get cached voice prompt if available.

    Args:
        cache_key: Cache key

    Returns:
        Cached voice prompt (dict or tensor) or None
    """
    entry = _memory_cache.get(cache_key)
    if entry is not None:
        if _is_expired(entry):
            _memory_cache.pop(cache_key, None)
            _cache_stats["evictions"] += 1
        else:
            entry.last_accessed_at = datetime.utcnow()
            _memory_cache.move_to_end(cache_key)
            _cache_stats["hits_memory"] += 1
            return entry.value

    cache_file = _get_cache_dir() / f"{cache_key}.prompt"
    if cache_file.exists():
        try:
            prompt = torch.load(cache_file, weights_only=True)
            _remember_memory(cache_key, prompt)
            _cache_stats["hits_disk"] += 1
            return prompt
        except Exception:
            cache_file.unlink(missing_ok=True)

    _cache_stats["misses"] += 1
    return None


def cache_voice_prompt(
    cache_key: str,
    voice_prompt: torch.Tensor | dict[str, Any],
) -> None:
    """
    Cache voice prompt to memory and disk.

    Args:
        cache_key: Cache key
        voice_prompt: Voice prompt (dict or tensor)
    """
    _remember_memory(cache_key, voice_prompt)

    cache_file = _get_cache_dir() / f"{cache_key}.prompt"
    torch.save(voice_prompt, cache_file)


def clear_voice_prompt_memory_cache() -> dict[str, int]:
    """Clear only in-memory voice prompt cache, preserving disk cache."""
    entries = len(_memory_cache)
    bytes_cleared = _memory_cache_bytes()
    _memory_cache.clear()
    return {"entries_cleared": entries, "bytes_cleared": bytes_cleared}


def get_voice_prompt_cache_stats() -> dict[str, Any]:
    """Return in-memory and disk voice prompt cache metrics."""
    _enforce_memory_limits()
    cache_dir = _get_cache_dir()
    disk_files = list(cache_dir.glob("*.prompt")) if cache_dir.exists() else []
    disk_bytes = 0
    for path in disk_files:
        with suppress(OSError):
            disk_bytes += path.stat().st_size

    memory_bytes = _memory_cache_bytes()
    return {
        "available": True,
        "entries": len(_memory_cache),
        "bytes": memory_bytes,
        "size_mb": round(memory_bytes / 1024 / 1024, 2),
        "disk_files": len(disk_files),
        "disk_bytes": disk_bytes,
        "disk_size_mb": round(disk_bytes / 1024 / 1024, 2),
        "max_entries": _max_entries(),
        "max_mb": round(_max_bytes() / 1024 / 1024, 2),
        "ttl_seconds": int(_ttl().total_seconds()),
        **_cache_stats,
    }


def clear_voice_prompt_cache() -> int:
    """
    Clear all voice prompt caches (memory and disk).

    Returns:
        Number of cache files deleted
    """
    clear_voice_prompt_memory_cache()

    cache_dir = _get_cache_dir()
    deleted_count = 0

    if cache_dir.exists():
        for cache_file in cache_dir.glob("*.prompt"):
            try:
                cache_file.unlink()
                deleted_count += 1
            except Exception as e:
                logger.warning("Failed to delete cache file %s: %s", cache_file, e)

        for audio_file in cache_dir.glob("combined_*.wav"):
            try:
                audio_file.unlink()
                deleted_count += 1
            except Exception as e:
                logger.warning("Failed to delete combined audio file %s: %s", audio_file, e)

    return deleted_count


def clear_profile_cache(profile_id: str) -> int:
    """
    Clear cache files for a specific profile.

    Args:
        profile_id: Profile ID

    Returns:
        Number of cache files deleted
    """
    cache_dir = _get_cache_dir()
    deleted_count = 0

    if cache_dir.exists():
        pattern = f"combined_{profile_id}_*.wav"
        for audio_file in cache_dir.glob(pattern):
            try:
                audio_file.unlink()
                deleted_count += 1
            except Exception as e:
                logger.warning("Failed to delete combined audio file %s: %s", audio_file, e)

    return deleted_count
