"""Storage helpers for AI Video Assistant artifacts."""

from __future__ import annotations

import re
import shutil
import unicodedata
from pathlib import Path

from .. import config

VIDEO_PROJECT_SUBDIRS = (
    "prompts",
    "video_prompts",
    "shot_clips",
    "render_intermediates",
    "render_cache",
    "render_outputs",
    "render_enhanced",
    "sfx_assets",
    "review_reports",
    "preview_images",
    "source_visuals",
    "subtitles",
    "manifests",
    "exports",
    "logs",
)
VIDEO_SERIES_MEMORY_FILENAME = "series-memory.md"

_UNSAFE_FILENAME_CHARS = re.compile(r"[\\/:*?\"<>|\x00-\x1f]")
_WHITESPACE = re.compile(r"\s+")

def get_video_projects_dir() -> Path:
    path = config.get_data_dir() / "video_projects"
    path.mkdir(parents=True, exist_ok=True)
    return path

def get_video_series_dir() -> Path:
    path = config.get_data_dir() / "video_series"
    path.mkdir(parents=True, exist_ok=True)
    return path

def get_series_dir(series_id: str) -> Path:
    path = get_video_series_dir() / series_id
    path.mkdir(parents=True, exist_ok=True)
    return path

def get_series_memory_path(series_id: str) -> Path:
    return get_series_dir(series_id) / VIDEO_SERIES_MEMORY_FILENAME

def get_project_dir(project_id: str) -> Path:
    path = get_video_projects_dir() / project_id
    path.mkdir(parents=True, exist_ok=True)
    for subdir in VIDEO_PROJECT_SUBDIRS:
        (path / subdir).mkdir(parents=True, exist_ok=True)
    return path

def get_project_subdir(project_id: str, subdir: str) -> Path:
    if subdir not in VIDEO_PROJECT_SUBDIRS:
        raise ValueError(f"Unknown video project artifact folder: {subdir}")
    path = get_project_dir(project_id) / subdir
    path.mkdir(parents=True, exist_ok=True)
    return path

def to_artifact_storage_path(path: str | Path) -> str:
    return config.to_storage_path(path)

def resolve_artifact_storage_path(path: str | Path | None) -> Path | None:
    return config.resolve_storage_path(path)

def sanitize_download_filename(value: str, *, fallback: str = "tai-ve", max_length: int = 140) -> str:
    """Return a filesystem-safe display filename while preserving Vietnamese text."""
    normalized = unicodedata.normalize("NFC", value or "")
    normalized = _UNSAFE_FILENAME_CHARS.sub(" ", normalized)
    normalized = _WHITESPACE.sub(" ", normalized).strip(" .")
    if not normalized:
        normalized = fallback
    return normalized[:max_length].rstrip(" .") or fallback

def scene_number(index: int) -> str:
    return f"Cảnh {index:02d}"

def prompt_filename(scene_index: int) -> str:
    return sanitize_download_filename(f"Prompt ảnh - {scene_number(scene_index)}.txt")

def prompt_pack_filename(project_title: str) -> str:
    title = sanitize_download_filename(project_title, fallback="Du an")
    return sanitize_download_filename(f"Prompt ảnh - {title}.txt")

def shot_number(index: int) -> str:
    return f"Shot {index:02d}"

def segment_number(index: int) -> str:
    return f"Segment {index:02d}"

def video_prompt_filename(scene_index: int | None, shot_index: int) -> str:
    scene_part = f"{scene_number(scene_index)} - " if scene_index else ""
    return sanitize_download_filename(f"Prompt video - {scene_part}{segment_number(shot_index)}.txt")

def video_prompt_pack_filename(project_title: str) -> str:
    title = sanitize_download_filename(project_title, fallback="Du an")
    return sanitize_download_filename(f"Prompt video - {title}.txt")

def shot_list_filename(project_title: str) -> str:
    title = sanitize_download_filename(project_title, fallback="Du an")
    return sanitize_download_filename(f"Segment list - {title}.csv")

def debug_log_filename(project_title: str) -> str:
    title = sanitize_download_filename(project_title, fallback="Du an")
    return sanitize_download_filename(f"Log loi - {title}.jsonl")

def voice_filename(scene_index: int, suffix: str = ".wav") -> str:
    return sanitize_download_filename(f"Giọng đọc - {scene_number(scene_index)}{suffix}")

def shot_voice_filename(scene_index: int | None, shot_index: int, suffix: str = ".wav") -> str:
    scene_part = f"{scene_number(scene_index)} - " if scene_index else ""
    return sanitize_download_filename(f"Giọng đọc - {scene_part}{shot_number(shot_index)}{suffix}")

def shot_clip_filename(scene_index: int | None, shot_index: int, suffix: str = ".mp4") -> str:
    scene_part = f"{scene_number(scene_index)} - " if scene_index else ""
    return sanitize_download_filename(f"Video clip - {scene_part}{shot_number(shot_index)}{suffix}")

def render_output_filename(project_title: str) -> str:
    title = sanitize_download_filename(project_title, fallback="Du an")
    return sanitize_download_filename(f"Video hoàn chỉnh - {title}.mp4")

def render_manifest_filename(project_title: str) -> str:
    title = sanitize_download_filename(project_title, fallback="Du an")
    return sanitize_download_filename(f"Timeline render - {title}.json")

def enhanced_render_artifact_filename(index: int, title: str, suffix: str) -> str:
    return sanitize_download_filename(f"{index}. {title}{suffix}")

def subtitle_filename(project_title: str) -> str:
    title = sanitize_download_filename(project_title, fallback="Du an")
    return sanitize_download_filename(f"Phụ đề - {title}.srt")

def package_filename(project_title: str) -> str:
    title = sanitize_download_filename(project_title, fallback="Du an")
    return sanitize_download_filename(f"Bộ nguyên liệu - {title}.zip")

def series_memory_download_filename(series_title: str) -> str:
    title = sanitize_download_filename(series_title, fallback="Series")
    return sanitize_download_filename(f"Series memory - {title}.md")

def remove_project_artifacts(project_id: str) -> None:
    project_dir = get_video_projects_dir() / project_id
    if project_dir.exists():
        shutil.rmtree(project_dir)

def remove_series_artifacts(series_id: str) -> None:
    series_dir = get_video_series_dir() / series_id
    if series_dir.exists():
        shutil.rmtree(series_dir)

def remove_artifact_file(path: str | Path | None) -> None:
    resolved = resolve_artifact_storage_path(path)
    if resolved and resolved.exists() and resolved.is_file():
        resolved.unlink()
