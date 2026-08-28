"""Independent Research AI attempts, cancellation and deterministic merging."""

from __future__ import annotations

import threading
import time
from concurrent.futures import Future, ThreadPoolExecutor, wait
from dataclasses import dataclass, field
from typing import Any, Callable, Iterable


class AttemptExecutionError(RuntimeError):
    def __init__(
        self,
        message: str,
        *,
        error_code: str = "RESEARCH_ATTEMPT_FAILED",
        metadata: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(message)
        self.error_code = error_code
        self.metadata = dict(metadata or {})


@dataclass
class AttemptResult:
    mode: str
    status: str
    output: dict[str, Any] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)
    error_code: str | None = None
    error_message: str | None = None
    duration_ms: int = 0

    def as_dict(self) -> dict[str, Any]:
        value: dict[str, Any] = {
            "mode": self.mode,
            "status": self.status,
            "output": self.output,
            "duration_ms": self.duration_ms,
        }
        if self.error_code:
            value["error_code"] = self.error_code
        if self.error_message:
            value["error_message"] = self.error_message
        return value


_cancel_lock = threading.Lock()
_cancel_events: dict[str, threading.Event] = {}


def register_run(run_id: str) -> threading.Event:
    event = threading.Event()
    with _cancel_lock:
        _cancel_events[run_id] = event
    return event


def request_cancel(run_id: str) -> bool:
    with _cancel_lock:
        event = _cancel_events.get(run_id)
    if event is None:
        return False
    event.set()
    return True


def clear_run(run_id: str) -> None:
    with _cancel_lock:
        _cancel_events.pop(run_id, None)


def _execute_attempt(
    mode: str,
    runner: Callable[[str], tuple[dict[str, Any], dict[str, Any]]],
    cancel_event: threading.Event,
) -> AttemptResult:
    started = time.monotonic()
    if cancel_event.is_set():
        return AttemptResult(mode=mode, status="cancelled", error_code="RESEARCH_RUN_CANCELLED")
    try:
        output, metadata = runner(mode)
        status = "cancelled" if cancel_event.is_set() else "completed"
        return AttemptResult(
            mode=mode,
            status=status,
            output=output if status == "completed" else {},
            metadata=dict(metadata or {}),
            error_code="RESEARCH_RUN_CANCELLED" if status == "cancelled" else None,
            duration_ms=int((time.monotonic() - started) * 1000),
        )
    except AttemptExecutionError as exc:
        return AttemptResult(
            mode=mode,
            status="failed",
            metadata=dict(exc.metadata or {}),
            error_code=exc.error_code,
            error_message=str(exc)[:2000],
            duration_ms=int((time.monotonic() - started) * 1000),
        )
    except Exception as exc:  # defensive isolation between provider attempts
        return AttemptResult(
            mode=mode,
            status="failed",
            error_code="RESEARCH_ATTEMPT_FAILED",
            error_message=str(exc)[:2000],
            duration_ms=int((time.monotonic() - started) * 1000),
        )


def run_independent_attempts(
    modes: Iterable[str],
    runner: Callable[[str], tuple[dict[str, Any], dict[str, Any]]],
    *,
    timeout_seconds: int,
    cancel_event: threading.Event,
) -> dict[str, AttemptResult]:
    """Run provider attempts concurrently and keep each result isolated."""

    selected = list(dict.fromkeys(modes))
    if not selected:
        return {}
    executor = ThreadPoolExecutor(max_workers=len(selected), thread_name_prefix="research-ai")
    futures: dict[Future[AttemptResult], str] = {
        executor.submit(_execute_attempt, mode, runner, cancel_event): mode for mode in selected
    }
    done, pending = wait(futures, timeout=max(5, int(timeout_seconds) + 5))
    results: dict[str, AttemptResult] = {}
    for future in done:
        mode = futures[future]
        results[mode] = future.result()
    for future in pending:
        mode = futures[future]
        future.cancel()
        results[mode] = AttemptResult(
            mode=mode,
            status="cancelled" if cancel_event.is_set() else "failed",
            error_code="RESEARCH_RUN_CANCELLED" if cancel_event.is_set() else "RESEARCH_ATTEMPT_TIMEOUT",
            error_message=None if cancel_event.is_set() else "Attempt vượt quá thời gian chờ cho phép.",
            duration_ms=max(5, int(timeout_seconds)) * 1000,
        )
    executor.shutdown(wait=False, cancel_futures=True)
    return {mode: results[mode] for mode in selected}


def _as_options(attempt: AttemptResult | None) -> list[dict[str, Any]]:
    if attempt is None or attempt.status != "completed":
        return []
    options = attempt.output.get("options")
    if not isinstance(options, list):
        return []
    return [dict(option) for option in options[:5] if isinstance(option, dict)]


def _list(value: Any) -> list[Any]:
    return list(value) if isinstance(value, list) else []


def _dedupe(values: Iterable[Any], *, limit: int = 100) -> list[Any]:
    result: list[Any] = []
    seen: set[str] = set()
    for value in values:
        key = repr(value)
        if key in seen:
            continue
        seen.add(key)
        result.append(value)
        if len(result) >= limit:
            break
    return result


def _number(option: dict[str, Any], key: str) -> float:
    try:
        return float(option.get(key) or 0)
    except (TypeError, ValueError):
        return 0.0


def merge_attempts(
    attempts: dict[str, AttemptResult],
    *,
    fallback_options: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Merge research evidence and creative structure without hiding conflicts."""

    research_options = _as_options(attempts.get("research"))
    creative_options = _as_options(attempts.get("creative"))
    single_options = research_options or creative_options
    pair_count = max(len(research_options), len(creative_options))
    merged: list[dict[str, Any]] = []
    all_disagreements: list[dict[str, Any]] = []

    for index in range(pair_count):
        research_option = research_options[index] if index < len(research_options) else None
        creative_option = creative_options[index] if index < len(creative_options) else None
        primary = creative_option or research_option or {}
        secondary = research_option if creative_option is not None else None
        contributions: list[dict[str, Any]] = []
        for mode, option in (("research", research_option), ("creative", creative_option)):
            if option is not None:
                contributions.append(
                    {
                        "mode": mode,
                        "title": option.get("title"),
                        "summary": option.get("summary"),
                    }
                )
        disagreements: list[dict[str, Any]] = []
        if research_option and creative_option:
            for field_name in ("title", "summary", "hook", "conflict", "payoff"):
                research_value = research_option.get(field_name)
                creative_value = creative_option.get(field_name)
                if research_value and creative_value and str(research_value).strip() != str(creative_value).strip():
                    disagreement = {
                        "field": field_name,
                        "research": research_value,
                        "creative": creative_value,
                    }
                    disagreements.append(disagreement)
                    all_disagreements.append({"option_index": index + 1, **disagreement})
        evidence_refs = _dedupe(
            _list((research_option or {}).get("evidence_refs"))
            + _list((creative_option or {}).get("evidence_refs"))
        )
        limitations = _dedupe(
            _list((research_option or {}).get("limitations"))
            + _list((creative_option or {}).get("limitations"))
        )
        merged.append(
            {
                **dict(secondary or {}),
                **dict(primary),
                "title": primary.get("title") or (secondary or {}).get("title") or f"Phương án {index + 1}",
                "summary": primary.get("summary") or (secondary or {}).get("summary") or "",
                "hook": primary.get("hook") or (secondary or {}).get("hook") or "",
                "conflict": primary.get("conflict") or (secondary or {}).get("conflict") or "",
                "payoff": primary.get("payoff") or (secondary or {}).get("payoff") or "",
                "evidence_refs": evidence_refs,
                "limitations": limitations,
                "contributions": contributions,
                "disagreements": disagreements,
                "source_provider": "merged" if len(contributions) > 1 else contributions[0]["mode"],
            }
        )

    if not merged:
        merged = [dict(option) for option in single_options[:5]]
    for fallback in fallback_options or []:
        if len(merged) >= 3:
            break
        candidate = dict(fallback)
        candidate.setdefault("source_provider", "fallback")
        candidate.setdefault("limitations", [])
        candidate["limitations"] = _dedupe(
            _list(candidate.get("limitations"))
            + ["Phương án dự phòng được dựng từ brief vì kết quả AI có ít hơn ba lựa chọn."]
        )
        merged.append(candidate)
    merged = merged[:5]

    candidate_index = None
    best_value = float("-inf")
    for index, option in enumerate(merged):
        value = _number(option, "originality") + _number(option, "feasibility") + min(2.0, len(_list(option.get("evidence_refs"))) * 0.25)
        option["merge_score"] = round(value, 2)
        if value > best_value:
            best_value = value
            candidate_index = index
    if candidate_index is not None:
        merged[candidate_index]["recommendation_candidate"] = True

    successful_modes = [mode for mode, attempt in attempts.items() if attempt.status == "completed"]
    failed_modes = [mode for mode, attempt in attempts.items() if attempt.status == "failed"]
    cancelled_modes = [mode for mode, attempt in attempts.items() if attempt.status == "cancelled"]
    status = "completed" if len(successful_modes) == len(attempts) else "partial" if successful_modes else "failed"
    return {
        "status": status,
        "source_modes": list(attempts),
        "successful_modes": successful_modes,
        "failed_modes": failed_modes,
        "cancelled_modes": cancelled_modes,
        "disagreements": all_disagreements[:50],
        "limitations": [
            f"Attempt {mode} không hoàn tất và không được dùng làm canon."
            for mode in failed_modes + cancelled_modes
        ],
        "options": merged,
    }


__all__ = [
    "AttemptExecutionError",
    "AttemptResult",
    "clear_run",
    "merge_attempts",
    "register_run",
    "request_cancel",
    "run_independent_attempts",
]
