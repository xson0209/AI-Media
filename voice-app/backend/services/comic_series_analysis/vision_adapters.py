"""OCR/vision adapter contracts for Comic Series Analysis (§6).

The critical rule (spec: "AI vision phải nhận ảnh thật"): an adapter only
counts as having *seen* an image if it attaches real image bytes / multipart
/ provider-file to the model's image-input field. Passing a local file path
inside prompt *text* is explicitly NOT vision (task 6.1).

Adapters expose a capability check. When no vision-capable adapter is
available, the pipeline marks the visual step ``vision_unavailable`` /
``partial`` and must not fabricate pixel descriptions (task 6.2).

A request builds an :class:`AttachmentManifest` mapping every attachment to
its ``asset_id`` / ``tile_id`` / page order / source coordinates so evidence
never loses its link to the source (spec scenario "Phân tích nhiều ảnh").
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
import json
from types import SimpleNamespace
from typing import Protocol, TYPE_CHECKING

from .config import VisionPolicy, get_config
from .contracts import ComicAnalysisError

if TYPE_CHECKING:
    from sqlalchemy.orm import Session


_STRING_ARRAY = {"type": "array", "items": {"type": "string"}}

VISION_OUTPUT_SCHEMA = {
    "type": "object",
    "properties": {
        "panels": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "asset_id": {"type": "string"},
                    "reading_order": {"type": "integer"},
                    "visual_description": {"type": "string"},
                    "confidence": {"type": "number"},
                    "evidence_ids": _STRING_ARRAY,
                },
                "required": ["asset_id", "reading_order", "visual_description", "confidence", "evidence_ids"],
                "additionalProperties": False,
            },
        },
        "dialogues": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "reading_order": {"type": "integer"},
                    "bubble_type": {"type": "string", "enum": ["dialogue", "narration", "sfx", "unknown"]},
                    "raw_text": {"type": "string"},
                    "text": {"type": "string"},
                    "speaker": {"type": "string"},
                    "language": {"type": "string"},
                    "confidence": {"type": "number"},
                    "speaker_confidence": {"type": "number"},
                    "evidence_ids": _STRING_ARRAY,
                },
                "required": [
                    "reading_order", "bubble_type", "raw_text", "text", "speaker", "language",
                    "confidence", "speaker_confidence", "evidence_ids",
                ],
                "additionalProperties": False,
            },
        },
        "characters": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "name": {"type": "string"},
                    "aliases": _STRING_ARRAY,
                    "role": {"type": "string"},
                    "face_description": {"type": "string"},
                    "hair_description": {"type": "string"},
                    "body_description": {"type": "string"},
                    "outfit_description": {"type": "string"},
                    "personality": {"type": "string"},
                    "speech_style": {"type": "string"},
                    "evidence_ids": _STRING_ARRAY,
                    "reference_asset_ids": _STRING_ARRAY,
                    "confidence": {"type": "number"},
                },
                "required": [
                    "name", "aliases", "role", "face_description", "hair_description", "body_description",
                    "outfit_description", "personality", "speech_style", "evidence_ids",
                    "reference_asset_ids", "confidence",
                ],
                "additionalProperties": False,
            },
        },
        "locations": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "name": {"type": "string"},
                    "description": {"type": "string"},
                    "world_rules": {"type": "string"},
                    "evidence_ids": _STRING_ARRAY,
                    "confidence": {"type": "number"},
                },
                "required": ["name", "description", "world_rules", "evidence_ids", "confidence"],
                "additionalProperties": False,
            },
        },
        "plot": {
            "type": "object",
            "properties": {
                "synopsis": {"type": "string"},
                "plot_beats": _STRING_ARRAY,
                "relationships": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "from": {"type": "string"},
                            "to": {"type": "string"},
                            "type": {"type": "string"},
                        },
                        "required": ["from", "to", "type"],
                        "additionalProperties": False,
                    },
                },
                "end_state_summary": {"type": "string"},
                "canon_candidates": _STRING_ARRAY,
                "development_options": _STRING_ARRAY,
                "uncertainties": _STRING_ARRAY,
                "limitations": _STRING_ARRAY,
                "evidence_ids": _STRING_ARRAY,
            },
            "required": [
                "synopsis", "plot_beats", "relationships", "end_state_summary", "canon_candidates",
                "development_options", "uncertainties", "limitations", "evidence_ids",
            ],
            "additionalProperties": False,
        },
    },
    "required": ["panels", "dialogues", "characters", "locations", "plot"],
    "additionalProperties": False,
}


@dataclass(frozen=True)
class Attachment:
    """One image/tile attached to a vision request."""

    attachment_index: int
    asset_id: str
    path: str
    tile_id: str | None = None
    page_order: int | None = None
    source_box: dict | None = None  # {x, y, w, h} in source coords


@dataclass
class AttachmentManifest:
    """Ordered attachments for one vision batch, with a stable hash."""

    batch_id: str
    attachments: list[Attachment] = field(default_factory=list)

    def manifest_keys(self) -> list[dict]:
        return [
            {
                "attachment_index": a.attachment_index,
                "asset_id": a.asset_id,
                "tile_id": a.tile_id,
                "page_order": a.page_order,
            }
            for a in self.attachments
        ]


@dataclass
class VisionResult:
    """Result of a vision batch."""

    batch_id: str
    completed: bool
    payload: dict | None = None
    status: str = "completed"  # completed | vision_unavailable | partial | invalid_output
    error_code: str | None = None


class ComicVisionAdapter(Protocol):
    """A vision-capable analysis adapter."""

    def supports_vision(self) -> bool: ...

    def analyze_batch(self, manifest: AttachmentManifest, instruction: str) -> VisionResult: ...


class ComicOcrAdapter(Protocol):
    """A text-region OCR adapter."""

    def supports_ocr(self) -> bool: ...

    def ocr_image(self, path: str) -> dict: ...


class NullVisionAdapter:
    """Adapter for providers with no real vision input.

    ``supports_vision`` returns False. Calling ``analyze_batch`` never
    fabricates a description — it returns ``vision_unavailable`` so the
    pipeline records the limitation honestly (task 6.2).
    """

    def supports_vision(self) -> bool:
        return False

    def analyze_batch(self, manifest: AttachmentManifest, instruction: str) -> VisionResult:
        return VisionResult(
            batch_id=manifest.batch_id,
            completed=False,
            status="vision_unavailable",
            error_code="COMIC_VISION_UNAVAILABLE",
        )


class CodexVisionAdapter:
    """Attach real comic images to the configured Codex planning provider."""

    def __init__(self, db: "Session"):
        from .. import ai_planning, settings as settings_service

        self._ai_planning = ai_planning
        settings = settings_service.get_ai_planning_settings(db)
        self._settings = SimpleNamespace(
            provider=settings.provider,
            codex_path=settings.codex_path,
            model=settings.model,
            model_reasoning_effort="high",
            timeout_seconds=settings.timeout_seconds,
        )
        # Extraction is latency-sensitive and deterministic enough at high;
        # reserve ultra for creative rewrite/master-story work.

    def supports_vision(self) -> bool:
        return bool(self._ai_planning.resolve_codex_path(self._settings))

    def analyze_batch(self, manifest: AttachmentManifest, instruction: str) -> VisionResult:
        mapping = manifest.manifest_keys()
        prompt = (
            "Bạn là hệ thống phân tích truyện tranh đa phương thức. Hãy đọc trực tiếp các ảnh đính kèm, "
            "không suy đoán từ tên file. Trả về JSON tiếng Việt gồm panels, dialogues/OCR, characters, "
            "locations và plot. Mỗi kết luận phải dùng evidence_ids là asset_id có trong manifest, "
            "confidence từ 0 đến 1, và reading_order theo thứ tự đọc. Mọi trường trong schema đều bắt buộc; "
            "nếu không quan sát được hãy dùng chuỗi rỗng hoặc mảng rỗng, không bỏ trường.\n\n"
            f"Yêu cầu: {instruction}\n"
            f"Attachment manifest: {json.dumps(mapping, ensure_ascii=False)}"
        )
        try:
            raw = self._ai_planning.run_codex_exec(
                self._settings,
                prompt,
                output_schema=VISION_OUTPUT_SCHEMA,
                image_paths=[item.path for item in manifest.attachments],
                timeout_seconds=240,
            )
            payload = json.loads(raw)
        except self._ai_planning.AIPlanningError as exc:
            return VisionResult(
                batch_id=manifest.batch_id,
                completed=False,
                status="vision_unavailable",
                error_code=exc.error_code,
            )
        except (TypeError, ValueError, json.JSONDecodeError):
            return VisionResult(
                batch_id=manifest.batch_id,
                completed=False,
                status="invalid_output",
                error_code="COMIC_AI_OUTPUT_INVALID",
            )
        return VisionResult(batch_id=manifest.batch_id, completed=True, payload=payload)


def validate_attachments(manifest: AttachmentManifest) -> None:
    """Ensure every attachment references a real, readable file (task 6.1).

    This is what makes "the model saw the image" verifiable: the bytes must
    exist and be attachable. Raises ``COMIC_VISION_ATTACH_FAILED`` otherwise.
    """
    if not manifest.attachments:
        raise ComicAnalysisError("COMIC_VISION_ATTACH_FAILED", "Batch không có attachment.")
    for att in manifest.attachments:
        path = Path(att.path)
        if not path.exists() or path.stat().st_size == 0:
            raise ComicAnalysisError(
                "COMIC_VISION_ATTACH_FAILED", f"Không đọc được attachment {att.asset_id}."
            )


def batch_attachments(
    attachments: list[Attachment], *, policy: VisionPolicy | None = None
) -> list[AttachmentManifest]:
    """Split attachments into ordered batches within the per-request limit."""
    policy = policy or get_config().vision
    limit = policy.max_attachments_per_request
    batches: list[AttachmentManifest] = []
    for start in range(0, len(attachments), limit):
        chunk = attachments[start : start + limit]
        batches.append(
            AttachmentManifest(batch_id=f"batch-{start // limit}", attachments=chunk)
        )
    return batches


_ACTIVE_VISION_ADAPTER: ComicVisionAdapter | None = None


def get_vision_adapter(db: "Session | None" = None) -> ComicVisionAdapter:
    """Return a test override or the configured Codex vision adapter."""
    if _ACTIVE_VISION_ADAPTER is not None:
        return _ACTIVE_VISION_ADAPTER
    if db is not None:
        adapter = CodexVisionAdapter(db)
        if adapter.supports_vision():
            return adapter
    return NullVisionAdapter()


def set_vision_adapter(adapter: ComicVisionAdapter) -> None:
    """Register a vision adapter (used by tests and future provider wiring)."""
    global _ACTIVE_VISION_ADAPTER
    _ACTIVE_VISION_ADAPTER = adapter


__all__ = [
    "Attachment",
    "AttachmentManifest",
    "ComicOcrAdapter",
    "ComicVisionAdapter",
    "CodexVisionAdapter",
    "NullVisionAdapter",
    "VisionResult",
    "VISION_OUTPUT_SCHEMA",
    "batch_attachments",
    "get_vision_adapter",
    "set_vision_adapter",
    "validate_attachments",
]
