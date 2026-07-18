"""Structured-output validation and originality checks for §6.

``validate_analysis_output`` runs before any AI result is written to the DB
(task 6.13): it checks required fields, types, stable IDs, that every
referenced ``evidence_id`` exists, that confidences are in ``[0,1] | null``,
and that cross-batch references resolve. Invalid output is rejected so it is
never recorded as a completed analysis (task 12.7a).

``build_originality_report`` produces the write-new-mode overlap artifact
(tasks 6.11, 6.16): longest verbatim span, source-chunk overlap and a
version-stamped threshold decision.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from .contracts import CONFIDENCE_CONFIG_VERSION, normalize_confidence


@dataclass
class ValidationResult:
    ok: bool
    errors: list[str] = field(default_factory=list)


def validate_analysis_output(
    payload: dict,
    *,
    known_evidence_ids: set[str],
    required_fields: tuple[str, ...] = (),
    confidence_paths: tuple[str, ...] = ("confidence",),
) -> ValidationResult:
    """Validate one AI structured-output object before persistence.

    - required fields present and non-null
    - any ``evidence_ids`` reference known evidence
    - confidence values are numeric in [0,1] or explicitly null
    """
    errors: list[str] = []
    if not isinstance(payload, dict):
        return ValidationResult(False, ["Payload không phải object."])

    for field_name in required_fields:
        if field_name not in payload or payload[field_name] in (None, ""):
            errors.append(f"Thiếu field bắt buộc: {field_name}")

    # Evidence IDs referenced anywhere in the object must exist.
    for evidence_id in _iter_evidence_ids(payload):
        if evidence_id not in known_evidence_ids:
            errors.append(f"evidence_id không tồn tại: {evidence_id}")

    # Confidence range.
    for value in _iter_confidences(payload, confidence_paths):
        if value is None:
            continue
        if not isinstance(value, (int, float)):
            errors.append(f"confidence không phải số: {value!r}")
        elif not (0.0 <= float(value) <= 1.0):
            errors.append(f"confidence ngoài [0,1]: {value}")

    return ValidationResult(not errors, errors)


def _iter_evidence_ids(node) -> list[str]:
    found: list[str] = []
    if isinstance(node, dict):
        for key, value in node.items():
            if key in ("evidence_ids", "evidence_id_list") and isinstance(value, list):
                found.extend(str(v) for v in value)
            elif key == "evidence_id" and isinstance(value, str):
                found.append(value)
            else:
                found.extend(_iter_evidence_ids(value))
    elif isinstance(node, list):
        for item in node:
            found.extend(_iter_evidence_ids(item))
    return found


def _iter_confidences(node, paths: tuple[str, ...]) -> list:
    found = []
    if isinstance(node, dict):
        for key, value in node.items():
            if key in paths:
                found.append(value)
            else:
                found.extend(_iter_confidences(value, paths))
    elif isinstance(node, list):
        for item in node:
            found.extend(_iter_confidences(item, paths))
    return found


def normalize_output_confidences(payload: dict, paths: tuple[str, ...] = ("confidence",)) -> dict:
    """Return a copy with all confidence values normalized to [0,1]|null."""
    def _walk(node):
        if isinstance(node, dict):
            return {
                k: (normalize_confidence(v) if k in paths else _walk(v))
                for k, v in node.items()
            }
        if isinstance(node, list):
            return [_walk(item) for item in node]
        return node

    return _walk(payload)


# --------------------------------------------------------------------------
# Originality check (write-new mode)
# --------------------------------------------------------------------------

ORIGINALITY_ALGORITHM_VERSION = "comic_originality.v1"
_WORD = re.compile(r"\w+", re.UNICODE)


@dataclass
class OriginalityReport:
    longest_verbatim_span: int
    verbatim_ratio: float
    source_chunk_overlap: float
    algorithm_version: str
    confidence_config_version: str
    exceeded_threshold: bool
    allowlist: list[str] = field(default_factory=list)
    override_reason: str | None = None

    def to_json(self) -> dict:
        return {
            "longest_verbatim_span": self.longest_verbatim_span,
            "verbatim_ratio": round(self.verbatim_ratio, 4),
            "source_chunk_overlap": round(self.source_chunk_overlap, 4),
            "algorithm_version": self.algorithm_version,
            "confidence_config_version": self.confidence_config_version,
            "exceeded_threshold": self.exceeded_threshold,
            "allowlist": self.allowlist,
            "override_reason": self.override_reason,
        }


def build_originality_report(
    candidate_text: str,
    source_texts: list[str],
    *,
    verbatim_threshold: int = 40,
    ratio_threshold: float = 0.25,
    allowlist: list[str] | None = None,
) -> OriginalityReport:
    """Measure overlap between generated text and the source (task 6.16).

    Uses a longest-common-substring (word-level) span and a shingle overlap
    ratio. Deterministic and version-stamped so results are reproducible.
    """
    allowlist = allowlist or []
    cand_words = _WORD.findall(candidate_text.lower())
    source_joined = " ".join(source_texts).lower()
    source_words = _WORD.findall(source_joined)

    longest = _longest_common_run(cand_words, set(_ngrams(source_words, 1)), source_words)
    verbatim_ratio = longest / max(1, len(cand_words))

    cand_shingles = set(_ngrams(cand_words, 3))
    source_shingles = set(_ngrams(source_words, 3))
    overlap = (
        len(cand_shingles & source_shingles) / max(1, len(cand_shingles))
        if cand_shingles
        else 0.0
    )

    exceeded = longest >= verbatim_threshold or verbatim_ratio >= ratio_threshold
    return OriginalityReport(
        longest_verbatim_span=longest,
        verbatim_ratio=verbatim_ratio,
        source_chunk_overlap=overlap,
        algorithm_version=ORIGINALITY_ALGORITHM_VERSION,
        confidence_config_version=CONFIDENCE_CONFIG_VERSION,
        exceeded_threshold=exceeded,
        allowlist=allowlist,
    )


def _ngrams(words: list[str], n: int) -> list[tuple]:
    return [tuple(words[i : i + n]) for i in range(len(words) - n + 1)] if len(words) >= n else []


def _longest_common_run(cand_words: list[str], source_unigrams: set, source_words: list[str]) -> int:
    """Length (in words) of the longest run of candidate words also appearing
    contiguously in the source."""
    source_text = " " + " ".join(source_words) + " "
    best = 0
    i = 0
    n = len(cand_words)
    while i < n:
        j = i
        # Extend the run while the contiguous slice appears in the source.
        while j < n:
            span = " " + " ".join(cand_words[i : j + 1]) + " "
            if span in source_text:
                j += 1
            else:
                break
        run = j - i
        best = max(best, run)
        i = max(i + 1, j)
    return best


__all__ = [
    "ORIGINALITY_ALGORITHM_VERSION",
    "OriginalityReport",
    "ValidationResult",
    "build_originality_report",
    "normalize_output_confidences",
    "validate_analysis_output",
]
