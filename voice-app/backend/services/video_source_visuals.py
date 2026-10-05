"""Original screenshots, source selections and deterministic video clips.

The project owns a copy of every image. Model outputs select known asset/region
IDs; they cannot supply file paths or replace text with generated pixels.
"""

from __future__ import annotations

import hashlib
import json
import math
import shutil
import subprocess
import uuid
from pathlib import Path

from .. import config, models
from ..database.models import VideoProject, VideoShot, VideoShotClip, VideoSourceBlock
from . import video_storage

STYLE = "preserve_source: original screenshots and code; crop, gentle zoom and highlight only; preserve readable source text."
PROMPT_RULE = "Original screenshot rule: preserve all existing UI, code, letters and logos exactly as captured; use only crop, gentle zoom and highlight on the original image; do not redraw the screen or invent new text."
NEGATIVE_RULE = "no AI redrawing of the source, no altered code or UI, no invented text, no added captions, no added watermark"


class SourceVisualError(ValueError):
    def __init__(self, message: str, code: str = "VIDEO_SOURCE_VISUAL_INVALID"):
        super().__init__(message)
        self.error_code = code


def preserves_source(project) -> bool:
    return str(getattr(project, "visual_style", "") or "").lower().startswith("preserve_source:")


def copy_assets(assets: list[dict], project_id: str, *, source_root: Path) -> list[dict]:
    """Copy and verify acquired originals into a project-owned directory."""
    originals = {}
    for asset in assets:
        originals.setdefault(asset["id"], asset)
    result = []
    for asset in originals.values():
        original = config.resolve_storage_path(asset.get("file_path"))
        if original is None or not original.resolve().is_relative_to(source_root.resolve()) or not original.is_file():
            raise SourceVisualError("Không còn screenshot gốc trong Research Project.", "VIDEO_SOURCE_VISUAL_MISSING")
        if hashlib.sha256(original.read_bytes()).hexdigest() != asset.get("sha256"):
            raise SourceVisualError("Screenshot gốc đã thay đổi; cần nghiên cứu lại.", "VIDEO_SOURCE_VISUAL_CHANGED")
        destination = video_storage.get_project_subdir(project_id, "source_visuals") / f"{uuid.uuid4()}{original.suffix.lower()}"
        shutil.copy2(original, destination)
        # OCR text belongs to the research evidence; keep the visual manifest small.
        regions = [{key: value for key, value in region.items() if key != "text"} for region in asset.get("regions") or []]
        result.append({**asset, "regions": regions, "file_path": video_storage.to_artifact_storage_path(destination)})
    return result


def list_assets(project_id: str, db) -> list[dict]:
    assets = {}
    for block in db.query(VideoSourceBlock).filter(VideoSourceBlock.project_id == project_id, VideoSourceBlock.block_type == "source_visuals").order_by(VideoSourceBlock.sort_order).all():
        try:
            payload = json.loads(block.content)
        except (ValueError, TypeError):
            continue
        if not isinstance(payload, dict) or payload.get("schema_version") != "source_visuals.v1":
            continue
        for asset in payload.get("assets") or []:
            if isinstance(asset, dict) and asset.get("id"):
                assets[asset["id"]] = asset
    return list(assets.values())


def resolve_asset(project_id: str, asset_id: str, db) -> tuple[dict, Path]:
    asset = next((asset for asset in list_assets(project_id, db) if asset["id"] == asset_id), None)
    path = config.resolve_storage_path(asset.get("file_path")) if asset else None
    root = video_storage.get_project_subdir(project_id, "source_visuals").resolve()
    if asset is None or path is None or not path.resolve().is_relative_to(root) or not path.is_file():
        raise SourceVisualError("Screenshot không thuộc project này hoặc file đã mất.", "VIDEO_SOURCE_VISUAL_MISSING")
    if hashlib.sha256(path.read_bytes()).hexdigest() != asset.get("sha256"):
        raise SourceVisualError("File screenshot không còn khớp ảnh đã nghiên cứu.", "VIDEO_SOURCE_VISUAL_CHANGED")
    return asset, path


def validate_selection(selection: dict, assets: list[dict]) -> dict:
    asset = next((asset for asset in assets if asset["id"] == selection.get("asset_id")), None)
    if asset is None:
        raise SourceVisualError("Shot chọn screenshot chưa có trong project.")
    region_id = selection.get("region_id") or None
    if region_id and not any(region.get("id") == region_id for region in asset.get("regions") or []):
        raise SourceVisualError("Vùng screenshot chưa được đọc hoặc không thuộc ảnh đã chọn.")
    motion = selection.get("motion", "hold")
    if motion not in {"hold", "zoom"}:
        raise SourceVisualError("Chuyển động screenshot chỉ hỗ trợ giữ khung hoặc zoom nhẹ.")
    return {"asset_id": asset["id"], "region_id": region_id, "motion": motion, "highlight": bool(selection.get("highlight", False)) and bool(region_id)}


def build_clip_command(ffmpeg: str, image: Path, output: Path, asset: dict, selection: dict, *, duration: float, resolution: tuple[int, int]) -> list[str]:
    """Build crop/highlight/zoom filters from known normalized source regions."""
    width, height = resolution
    filters = []
    region = next((item for item in asset.get("regions") or [] if item.get("id") == selection.get("region_id")), None)
    if region:
        x, y, w, h = [float(value) for value in region["box"]]
        if not all(math.isfinite(value) for value in [x, y, w, h]) or not (0 <= x < 1 and 0 <= y < 1 and w > 0 and h > 0 and x + w <= 1.001 and y + h <= 1.001):
            raise SourceVisualError("Tọa độ vùng screenshot không hợp lệ.")
        source_w, source_h = int(asset["width"]), int(asset["height"])
        left, top = max(0, int((x - w * .12) * source_w)), max(0, int((y - h * .12) * source_h))
        right, bottom = min(source_w, math.ceil((x + w * 1.12) * source_w)), min(source_h, math.ceil((y + h * 1.12) * source_h))
        filters.append(f"crop={max(2, right - left)}:{max(2, bottom - top)}:{left}:{top}")
        if selection.get("highlight"):
            filters.append(f"drawbox=x={int(x * source_w) - left}:y={int(y * source_h) - top}:w={max(2, int(w * source_w))}:h={max(2, int(h * source_h))}:color=0xFACC15:t=3")
    filters += [f"scale={width}:{height}:force_original_aspect_ratio=decrease", f"pad={width}:{height}:(ow-iw)/2:(oh-ih)/2:color=0x111827", "setsar=1"]
    if selection.get("motion") == "zoom":
        frames = max(2, round(duration * 30))
        filters.append(f"zoompan=z='min(1.06,1+on*0.06/{frames - 1})':x='iw/2-iw/zoom/2':y='ih/2-ih/zoom/2':d=1:s={width}x{height}:fps=30")
    return [ffmpeg, "-y", "-loop", "1", "-framerate", "30", "-i", str(image), "-vf", ",".join(filters), "-t", f"{duration:.3f}", "-an", "-c:v", "libx264", "-preset", "veryfast", "-crf", "18", "-pix_fmt", "yuv420p", "-r", "30", "-movflags", "+faststart", str(output)]


def create_clip(project_id: str, shot_id: str, data: models.VideoScreenshotClipCreate, db) -> models.VideoShotClipResponse:
    from . import video_phase2, video_rendering

    project = db.query(VideoProject).filter(VideoProject.id == project_id).first()
    shot = db.query(VideoShot).filter(VideoShot.project_id == project_id, VideoShot.id == shot_id).first()
    if project is None or shot is None:
        raise SourceVisualError("Không tìm thấy shot video.", "VIDEO_SHOT_NOT_FOUND")
    if project.phase != "phase2":
        raise SourceVisualError("Dựng screenshot cần project AI Video phase 2.")
    selection = validate_selection(data.model_dump(exclude={"resolution"}), list_assets(project_id, db))
    asset, image = resolve_asset(project_id, selection["asset_id"], db)
    duration = float(shot.duration_seconds or 8)
    if not 0.5 <= duration <= 30:
        raise SourceVisualError("Thời lượng shot phải từ 0,5 đến 30 giây.")
    resolution = {"16:9": (1280, 720), "9:16": (720, 1280), "1:1": (720, 720)}.get(project.aspect_ratio, (1280, 720))
    if data.resolution == "1080p":
        resolution = tuple(int(value * 1.5) for value in resolution)
    ffmpeg = video_rendering.detect_tools().ffmpeg
    if not ffmpeg:
        raise SourceVisualError("Cần cài FFmpeg để dựng clip từ screenshot.", "VIDEO_RENDER_FFMPEG_MISSING")
    output = video_storage.get_project_subdir(project_id, "shot_clips") / f"screen-{uuid.uuid4()}.mp4"
    try:
        command = build_clip_command(ffmpeg, image, output, asset, selection, duration=duration, resolution=resolution)
        completed = subprocess.run(command, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=180, creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
        if completed.returncode:
            raise SourceVisualError(f"Không dựng được screenshot: {completed.stderr[-1500:]}", "VIDEO_SCREENSHOT_RENDER_FAILED")
        # Update dependencies through the same interface used by manual shot edits.
        retention = {**(shot.retention_json or {}), "source_visual": selection}
        update = {"retention_json": retention}
        if (shot.speech_source_override or project.speech_source) in {"veo_narration", "veo_dialogue"}:
            update["speech_source_override"] = "voicebox_khong_context"
        video_phase2.update_shot(project_id, shot_id, models.VideoShotUpdate(**update), db)
        clip = video_rendering.import_provider_clip(project_id, shot_id, source_path=output, original_filename=f"screenshot-shot-{shot.shot_order}.mp4", provider="original_screenshot", provider_metadata={"source_visual": selection, "sha256": asset["sha256"], "preserve_source": True}, db=db)
        if clip is None:
            raise SourceVisualError("Shot đã bị xóa khi dựng screenshot.", "VIDEO_SHOT_NOT_FOUND")
        row = db.query(VideoShotClip).filter(VideoShotClip.id == clip.id).one()
        row.source = "screenshot"
        db.commit()
        db.refresh(row)
        return models.VideoShotClipResponse.model_validate(row)
    except subprocess.TimeoutExpired as exc:
        raise SourceVisualError("Dựng screenshot vượt quá thời gian chờ.", "VIDEO_SCREENSHOT_RENDER_TIMEOUT") from exc
    finally:
        output.unlink(missing_ok=True)
