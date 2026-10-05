"""Provider independent long-form outline, chapter and editorial contracts."""

from __future__ import annotations

from collections.abc import Callable
from itertools import pairwise
from typing import Any


class LongFormPlanningError(ValueError):
    pass


LONGFORM_OUTLINE_SCHEMA: dict[str, Any] = {
    "type": "object",
    "additionalProperties": False,
    "required": ["central_question", "central_promise", "payoff", "chapters"],
    "properties": {
        "central_question": {"type": "string", "minLength": 1},
        "central_promise": {"type": "string", "minLength": 1},
        "payoff": {"type": "string", "minLength": 1},
        "chapters": {"type": "array", "minItems": 1, "maxItems": 40},
    },
}


def validate_outline(outline: dict[str, Any], target_seconds: int) -> dict[str, Any]:
    if not isinstance(outline, dict) or any(
        not isinstance(outline.get(key), str) or not outline[key].strip()
        for key in ("central_question", "central_promise", "payoff")
    ):
        raise LongFormPlanningError("Dàn ý dài thiếu câu hỏi trung tâm, lời hứa hoặc payoff.")
    chapters = outline.get("chapters")
    if not isinstance(chapters, list) or not chapters or len(chapters) > 40:
        raise LongFormPlanningError("Dàn ý dài phải có từ 1 đến 40 chương.")
    try:
        ordered = sorted((dict(item) for item in chapters), key=lambda item: int(item.get("order", 0)))
    except (TypeError, ValueError) as exc:
        raise LongFormPlanningError("Thứ tự chương không hợp lệ.") from exc
    if [int(item.get("order", 0)) for item in ordered] != list(range(1, len(ordered) + 1)):
        raise LongFormPlanningError("Thứ tự chương phải liên tục từ 1.")
    for chapter in ordered:
        try:
            duration = int(chapter["duration_seconds"])
        except (KeyError, TypeError, ValueError) as exc:
            raise LongFormPlanningError("Thời lượng chương phải là số nguyên dương.") from exc
        required = ("title", "goal", "state_in", "state_out", "bridge")
        if duration <= 0 or any(not isinstance(chapter.get(key), str) or not chapter[key].strip() for key in required):
            raise LongFormPlanningError(f"Chương {chapter.get('order')} thiếu trường bắt buộc.")
        chapter["duration_seconds"] = duration
        for key in required:
            chapter[key] = chapter[key].strip()
    for before, after in pairwise(ordered):
        if before["state_out"].casefold() != after["state_in"].casefold():
            raise LongFormPlanningError(f"Trạng thái chương {before['order']} không nối được chương {after['order']}.")
    total = sum(item["duration_seconds"] for item in ordered)
    tolerance = max(15, int(max(1, target_seconds) * 0.08))
    if target_seconds > 0 and abs(total - target_seconds) > tolerance:
        raise LongFormPlanningError(f"Tổng thời lượng chương ({total}s) lệch mục tiêu ({target_seconds}s).")
    return {**outline, "chapters": ordered, "duration_seconds": total}


def build_outline(
    project_context: str, target_seconds: int, run: Callable[[str, dict, str], dict[str, Any]]
) -> dict[str, Any]:
    return validate_outline(
        run(
            f"Tạo dàn ý video dài {target_seconds} giây. Ngữ cảnh:\n{project_context}",
            LONGFORM_OUTLINE_SCHEMA,
            "longform_outline",
        ),
        target_seconds,
    )


def _chapter_schema(scene_schema: dict[str, Any] | None) -> dict[str, Any]:
    props: dict[str, Any] = {
        "narration": {"type": "string", "minLength": 1},
        "state_out": {"type": "string", "minLength": 1},
        "bridge": {"type": "string", "minLength": 1},
        "review_vi": {"type": "string"},
        "scenes": {"type": "array", "minItems": 1},
    }
    if scene_schema:
        props["scenes"] = {"type": "array", "minItems": 1, "items": scene_schema}
    return {"type": "object", "additionalProperties": False, "required": list(props), "properties": props}


def _similarity(left: str, right: str) -> float:
    a, b = set(left.casefold().split()), set(right.casefold().split())
    return len(a & b) / max(1, len(a | b))


def generate_chapters(
    outline: dict[str, Any],
    project_context: str,
    run: Callable[[str, dict, str], dict[str, Any]],
    *,
    completed_chapters: list[dict[str, Any]] | None = None,
    on_chapter: Callable[[list[dict[str, Any]]], None] | None = None,
    scene_schema: dict[str, Any] | None = None,
) -> dict[str, Any]:
    chapters = [dict(item) for item in (completed_chapters or [])]
    by_order = {int(item.get("order", 0)): item for item in chapters if item.get("order")}
    for chapter in outline["chapters"]:
        order = int(chapter["order"])
        if order in by_order and str(by_order[order].get("narration", "")).strip() and by_order[order].get("scenes"):
            continue
        ledger = "\n".join(
            f"Chương {item.get('order')}: {item.get('state_out')}; {item.get('bridge')}" for item in chapters[-2:]
        )
        prompt = f"Dàn ý: {outline['central_question']} / {outline['central_promise']} / {outline['payoff']}\nNgữ cảnh: {project_context}\nChương {order}: {chapter['title']}\nMục tiêu: {chapter['goal']}\nTrạng thái đầu: {chapter['state_in']}\nBộ nhớ: {ledger}\nViết một chương với narration và scene theo schema, bổ sung thông tin mới, không lặp chương trước."
        result = run(prompt, _chapter_schema(scene_schema), f"longform_chapter_{order}")
        narration = str(result.get("narration", "")).strip()
        if (
            not narration
            or not str(result.get("state_out", "")).strip()
            or not str(result.get("bridge", "")).strip()
            or not isinstance(result.get("scenes"), list)
            or not result["scenes"]
        ):
            raise LongFormPlanningError(f"Chương {order} thiếu narration, state_out, bridge hoặc scene.")
        if any(_similarity(narration, item.get("narration", "")) >= 0.92 for item in chapters):
            raise LongFormPlanningError(f"Chương {order} lặp nội dung.")
        item = {**chapter, **result, "order": order, "duration_seconds": chapter["duration_seconds"]}
        chapters = [old for old in chapters if int(old.get("order", 0)) != order] + [item]
        chapters.sort(key=lambda value: int(value["order"]))
        by_order[order] = item
        if on_chapter:
            on_chapter(chapters)
    return {**outline, "chapters": chapters, "status": "ready_for_editorial_review"}


def editorial_review(
    outline: dict[str, Any],
    chapters: list[dict[str, Any]],
    project_context: str,
    run: Callable[[str, dict, str], dict[str, Any]],
) -> dict[str, Any]:
    if not chapters or len(chapters) != len(outline["chapters"]):
        raise LongFormPlanningError("Chưa viết đủ chương để biên tập toàn bài.")
    local = [
        {
            "code": "continuity_break",
            "chapter": after.get("order"),
            "message": "Trạng thái giữa hai chương không nối được.",
        }
        for before, after in pairwise(chapters)
        if str(before.get("state_out", "")).casefold() != str(after.get("state_in", "")).casefold()
    ]
    if local:
        return {
            "passed": False,
            "blocking_errors": local,
            "warnings": [],
            "recommended_actions": ["Sửa state_in/state_out hoặc viết lại chương chuyển tiếp."],
        }
    schema = {
        "type": "object",
        "additionalProperties": False,
        "required": ["passed", "blocking_errors", "warnings", "recommended_actions"],
        "properties": {
            "passed": {"type": "boolean"},
            "blocking_errors": {"type": "array"},
            "warnings": {"type": "array"},
            "recommended_actions": {"type": "array"},
        },
    }
    result = run(
        f"Kiểm tra biên tập toàn bài về hook, lời hứa, payoff, lặp ý, tiến triển, continuity và thể loại. Outline: {outline}. Chapters: {chapters}. Ngữ cảnh: {project_context}.",
        schema,
        "longform_editorial_review",
    )
    if not isinstance(result, dict) or not isinstance(result.get("passed"), bool):
        raise LongFormPlanningError("Kết quả biên tập không đúng cấu trúc.")
    for key in ("blocking_errors", "warnings", "recommended_actions"):
        result.setdefault(key, [])
    return result
