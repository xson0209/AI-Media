"""Experimental Vietnamese evaluation support for TADA 3B.

This module intentionally does not declare Vietnamese as official TADA support.
It provides a fixed evaluation corpus, a review-state file, and a gate that
keeps normal API/UI generation hidden until a maintainer accepts the result.
"""

from __future__ import annotations

import json
import os
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

CORPUS_VERSION = "2026-06-30-v1"
EVAL_DIR_ENV = "VOICEBOX_TADA_VIETNAMESE_EVAL_DIR"
LOCAL_TEST_BYPASS_ENV = "VOICEBOX_TADA_VIETNAMESE_TEST_BYPASS"
DEFAULT_EVAL_DIR = Path("output") / "tada-vietnamese-eval"
REVIEW_STATE_FILENAME = "review-state.json"
TADA_1B_SIZE = "1B"
TADA_3B_SIZE = "3B"

TADA_VIETNAMESE_CORPUS: list[dict[str, str]] = [
    {
        "id": "vi-short-01",
        "category": "short",
        "text": "Xin chào, hôm nay trời rất đẹp.",
    },
    {
        "id": "vi-tone-01",
        "category": "tone",
        "text": "Má, mà, mã, mả, mạ là năm thanh khác nhau trong tiếng Việt.",
    },
    {
        "id": "vi-tone-02",
        "category": "tone",
        "text": "Tôi muốn mua bún bò, phở gà, bánh mì và một ly cà phê sữa đá.",
    },
    {
        "id": "vi-long-01",
        "category": "long",
        "text": (
            "Khi phát triển một công cụ giọng nói tiếng Việt, điều quan trọng nhất "
            "là giữ đúng dấu, đúng nhịp câu, và không làm mất cảm xúc tự nhiên của người nói."
        ),
    },
    {
        "id": "vi-number-01",
        "category": "number",
        "text": "Đơn hàng số 2026 có giá 1.250.000 đồng và sẽ giao lúc 8 giờ 30 phút sáng.",
    },
    {
        "id": "vi-acronym-01",
        "category": "acronym",
        "text": "Voicebox dùng API, GPU và mô hình TADA 3B để tạo giọng nói thử nghiệm.",
    },
    {
        "id": "vi-punctuation-01",
        "category": "punctuation",
        "text": "Bạn nghe rõ không? Nếu rõ, hãy trả lời: tôi nghe rất rõ!",
    },
    {
        "id": "vi-dialogue-01",
        "category": "dialogue",
        "text": "Lan nói: 'Mình bắt đầu nhé.' Minh đáp: 'Được, đọc chậm và rõ hơn một chút.'",
    },
]

REVIEW_RUBRIC: list[dict[str, Any]] = [
    {
        "field": "intelligibility",
        "label": "Vietnamese intelligibility",
        "scale": "0-5",
        "passing_score": 4,
    },
    {
        "field": "tone_accuracy",
        "label": "Tone mark and vowel accuracy",
        "scale": "0-5",
        "passing_score": 4,
    },
    {
        "field": "naturalness",
        "label": "Natural Vietnamese rhythm and prosody",
        "scale": "0-5",
        "passing_score": 3,
    },
    {
        "field": "speaker_similarity",
        "label": "Similarity to reference voice",
        "scale": "0-5",
        "passing_score": 3,
    },
    {
        "field": "stability",
        "label": "No dropouts, language switching, or hallucinated trailing speech",
        "scale": "0-5",
        "passing_score": 4,
    },
]

def get_evaluation_root(path: str | Path | None = None) -> Path:
    """Return the gitignored directory used for generated evaluation artifacts."""
    configured = path or os.environ.get(EVAL_DIR_ENV) or DEFAULT_EVAL_DIR
    return Path(configured).resolve()

def get_review_state_path(root: str | Path | None = None) -> Path:
    return get_evaluation_root(root) / REVIEW_STATE_FILENAME

def load_review_state(root: str | Path | None = None) -> dict[str, Any] | None:
    path = get_review_state_path(root)
    if not path.exists():
        return None
    try:
        with path.open("r", encoding="utf-8") as handle:
            state = json.load(handle)
    except (OSError, json.JSONDecodeError):
        return None
    return state if isinstance(state, dict) else None

def is_review_accepted(root: str | Path | None = None) -> bool:
    state = load_review_state(root)
    return bool(state and state.get("status") == "accepted")

def is_local_test_bypass_enabled() -> bool:
    value = os.environ.get(LOCAL_TEST_BYPASS_ENV, "")
    return value.strip().lower() in {"1", "true", "yes", "on"}

def normalize_tada_model_size(
    *,
    engine: str | None,
    language: str | None,
    model_size: str | None,
) -> str | None:
    """Resolve stale/non-TADA size values before TADA validation.

    The web form can carry a previous Qwen size such as ``1.7B`` when a
    Vietnamese profile auto-selects TADA. For Vietnamese we route to the
    only viable TADA model, 3B, unless the caller explicitly picked 1B so the
    normal "TADA 1B is English-only" error remains intact.
    """
    if engine != "tada":
        return model_size
    if language == "vi":
        return TADA_1B_SIZE if model_size == TADA_1B_SIZE else TADA_3B_SIZE
    return model_size if model_size in {TADA_1B_SIZE, TADA_3B_SIZE} else TADA_1B_SIZE

def should_allow_profile_bypass(
    *,
    profile: Any,
    engine: str | None,
    model_size: str | None,
    language: str | None,
) -> bool:
    """Allow a Vietnamese TADA 3B request tied to a Vietnamese voice profile.

    This bypass is deliberately profile-scoped: it does not advertise upstream
    Vietnamese support, does not enable TADA 1B, and does not fallback to
    English or another engine.
    """
    profile_language = (getattr(profile, "language", None) or "").strip().lower()
    return (
        engine == "tada"
        and language == "vi"
        and model_size == TADA_3B_SIZE
        and profile_language == "vi"
    )

def write_review_state(
    *,
    status: str,
    notes: str = "",
    reviewer: str = "",
    run_id: str | None = None,
    root: str | Path | None = None,
) -> Path:
    if status not in {"accepted", "rejected", "pending"}:
        raise ValueError("Review status must be accepted, rejected, or pending")

    evaluation_root = get_evaluation_root(root)
    evaluation_root.mkdir(parents=True, exist_ok=True)
    path = evaluation_root / REVIEW_STATE_FILENAME
    payload = {
        "status": status,
        "notes": notes,
        "reviewer": reviewer,
        "run_id": run_id,
        "corpus_version": CORPUS_VERSION,
        "updated_at": datetime.now(UTC).isoformat(),
    }
    with path.open("w", encoding="utf-8") as handle:
        json.dump(payload, handle, ensure_ascii=False, indent=2)
        handle.write("\n")
    return path

def is_tada_vietnamese_request(engine: str | None, model_size: str | None, language: str | None) -> bool:
    return engine == "tada" and model_size == "3B" and language == "vi"

def ensure_tada_vietnamese_allowed(
    *,
    engine: str | None,
    model_size: str | None,
    language: str | None,
    allow_evaluation: bool = False,
) -> None:
    """Reject normal TADA Vietnamese requests until the evaluation is accepted."""
    if engine != "tada" or language != "vi":
        return
    if model_size != "3B":
        raise ValueError("Vietnamese is not available for TADA 1B; use TADA 3B evaluation instead.")
    if allow_evaluation or is_review_accepted() or is_local_test_bypass_enabled():
        return
    raise ValueError(
        "Vietnamese for TADA 3B is experimental and hidden until a Vietnamese evaluation run is accepted. "
        "Run scripts/evaluate_tada_vietnamese.py with a Vietnamese reference profile first."
    )
