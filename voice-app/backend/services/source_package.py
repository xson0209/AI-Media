"""Canonical Source Package primitives shared by analysis and creation flows.

This module intentionally has no dependency on database models, API schemas, or
domain-specific services. Domain adapters should build a ``SourcePackage`` here
and then convert it to the target shape they need.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from typing import Any, Iterable

SOURCE_PACKAGE_SCHEMA_VERSION = "source_package.v1"
DEFAULT_AI_VIDEO_BLOCK_LIMIT = 30_000


@dataclass(frozen=True)
class SourcePackageBlock:
    """One ordered source unit inside a canonical Source Package."""

    block_type: str
    content: Any
    sort_order: int = 0
    title: str | None = None
    evidence_refs: list[Any] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class SourcePackage:
    """A normalized source snapshot that downstream creative flows can read."""

    source_kind: str
    source_ref_id: str | None
    source_revision: int | str | None
    blocks: list[SourcePackageBlock]
    schema_version: str = SOURCE_PACKAGE_SCHEMA_VERSION
    title: str | None = None
    summary: str | None = None
    coverage_metrics: dict[str, Any] = field(default_factory=dict)
    limitations: list[Any] = field(default_factory=list)
    provenance: dict[str, Any] = field(default_factory=dict)
    fingerprint: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "source_kind": self.source_kind,
            "source_ref_id": self.source_ref_id,
            "source_revision": self.source_revision,
            "title": self.title,
            "summary": self.summary,
            "coverage_metrics": self.coverage_metrics,
            "limitations": self.limitations,
            "provenance": self.provenance,
            "fingerprint": self.fingerprint,
            "blocks": [
                {
                    "block_type": block.block_type,
                    "sort_order": block.sort_order,
                    "title": block.title,
                    "content": block.content,
                    "evidence_refs": block.evidence_refs,
                    "metadata": block.metadata,
                }
                for block in self.blocks
            ],
        }


def build_source_package(
    *,
    source_kind: str,
    source_ref_id: str | None = None,
    source_revision: int | str | None = None,
    title: str | None = None,
    summary: str | None = None,
    blocks: Iterable[SourcePackageBlock] = (),
    coverage_metrics: dict[str, Any] | None = None,
    limitations: Iterable[Any] | None = None,
    provenance: dict[str, Any] | None = None,
    schema_version: str = SOURCE_PACKAGE_SCHEMA_VERSION,
) -> SourcePackage:
    """Build a normalized package and compute a stable fingerprint."""

    normalized_blocks = _normalize_blocks(blocks)
    package = SourcePackage(
        schema_version=schema_version,
        source_kind=_clean_token(source_kind) or "unknown",
        source_ref_id=source_ref_id,
        source_revision=source_revision,
        title=_clean_text(title),
        summary=_clean_text(summary),
        blocks=normalized_blocks,
        coverage_metrics=dict(coverage_metrics or {}),
        limitations=list(limitations or []),
        provenance=dict(provenance or {}),
    )
    return SourcePackage(
        schema_version=package.schema_version,
        source_kind=package.source_kind,
        source_ref_id=package.source_ref_id,
        source_revision=package.source_revision,
        title=package.title,
        summary=package.summary,
        blocks=package.blocks,
        coverage_metrics=package.coverage_metrics,
        limitations=package.limitations,
        provenance=package.provenance,
        fingerprint=_fingerprint(package),
    )


def to_ai_video_source_blocks(
    package: SourcePackage,
    *,
    max_content_chars: int = DEFAULT_AI_VIDEO_BLOCK_LIMIT,
) -> list[dict[str, Any]]:
    """Convert a Source Package into AI Video-compatible source blocks.

    The return shape is deliberately plain dictionaries so this module stays
    independent from the API model layer.
    """

    result: list[dict[str, Any]] = []
    for fallback_order, block in enumerate(package.blocks, start=1):
        content = _format_content(block.content)
        if not content:
            continue
        if len(content) > max_content_chars:
            content = content[:max_content_chars].rstrip(" ,.;:\n\t") + "...[truncated]"
        result.append(
            {
                "block_type": block.block_type,
                "content": content,
                "sort_order": block.sort_order or fallback_order,
                "title": block.title,
                "evidence_refs": block.evidence_refs,
                "metadata": block.metadata,
            }
        )
    return sorted(result, key=lambda item: int(item.get("sort_order") or 0))


def _normalize_blocks(blocks: Iterable[SourcePackageBlock]) -> list[SourcePackageBlock]:
    normalized: list[SourcePackageBlock] = []
    for index, block in enumerate(blocks, start=1):
        block_type = _clean_token(block.block_type) or "text"
        content = block.content
        if content is None:
            continue
        if isinstance(content, str) and not content.strip():
            continue
        normalized.append(
            SourcePackageBlock(
                block_type=block_type,
                content=content.strip() if isinstance(content, str) else content,
                sort_order=int(block.sort_order or index),
                title=_clean_text(block.title),
                evidence_refs=list(block.evidence_refs or []),
                metadata=dict(block.metadata or {}),
            )
        )
    return sorted(normalized, key=lambda item: item.sort_order)


def _fingerprint(package: SourcePackage) -> str:
    payload = {
        "schema_version": package.schema_version,
        "source_kind": package.source_kind,
        "source_ref_id": package.source_ref_id,
        "source_revision": package.source_revision,
        "title": package.title,
        "summary": package.summary,
        "coverage_metrics": package.coverage_metrics,
        "limitations": package.limitations,
        "provenance": package.provenance,
        "blocks": [
            {
                "block_type": block.block_type,
                "sort_order": block.sort_order,
                "title": block.title,
                "content": block.content,
                "evidence_refs": block.evidence_refs,
                "metadata": block.metadata,
            }
            for block in package.blocks
        ],
    }
    return hashlib.sha256(
        json.dumps(payload, ensure_ascii=False, sort_keys=True, default=str).encode("utf-8")
    ).hexdigest()


def _format_content(value: Any) -> str:
    if isinstance(value, str):
        return value.strip()
    return json.dumps(value, ensure_ascii=False, indent=2, default=str).strip()


def _clean_token(value: Any) -> str:
    return str(value or "").strip().lower().replace(" ", "_")


def _clean_text(value: Any) -> str | None:
    text = str(value or "").strip()
    return text or None


__all__ = [
    "DEFAULT_AI_VIDEO_BLOCK_LIMIT",
    "SOURCE_PACKAGE_SCHEMA_VERSION",
    "SourcePackage",
    "SourcePackageBlock",
    "build_source_package",
    "to_ai_video_source_blocks",
]
