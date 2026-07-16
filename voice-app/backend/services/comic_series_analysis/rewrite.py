"""Generate the optimized story script shown between analysis and handoff."""

from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace
from typing import Any

from sqlalchemy.orm import Session

from ...database import ComicAnalysisJob as DBJob, ComicSourcePage as DBPage
from .. import ai_planning, settings as settings_service
from .contracts import ComicAnalysisError


OPTIMIZED_SCRIPT_SCHEMA = {
    "type": "object",
    "properties": {
        "title": {"type": "string"},
        "synopsis": {"type": "string"},
        "hook": {"type": "string"},
        "full_story": {"type": "string"},
        "plot_beats": {"type": "array", "items": {"type": "string"}},
        "character_arcs": {"type": "array", "items": {"type": "string"}},
        "scene_outline": {"type": "array", "items": {"type": "string"}},
    },
    "required": [
        "title",
        "synopsis",
        "hook",
        "full_story",
        "plot_beats",
        "character_arcs",
        "scene_outline",
    ],
    "additionalProperties": False,
}

MAX_SOURCE_TEXT_CHARS = 1_500
MAX_PANEL_COUNT = 18
MAX_DIALOGUE_COUNT = 24
MAX_CHARACTER_COUNT = 12
MAX_LOCATION_COUNT = 10
MAX_PLOT_BEAT_COUNT = 12
MAX_RELATIONSHIP_COUNT = 8
MAX_UNCERTAINTY_COUNT = 8
MAX_PROMPT_CHARS = 11_500


def rewrite_optimized_script(db: Session, job_id: str) -> DBJob:
    job = db.query(DBJob).filter(DBJob.id == job_id).first()
    if job is None:
        raise ComicAnalysisError("COMIC_ANALYSIS_NOT_FOUND", status_code=404)

    package = dict(job.analysis_package_json or {})
    if int(job.analysis_revision or 0) <= 0 or not package:
        raise ComicAnalysisError(
            "COMIC_ANALYSIS_INVALID_STATE",
            "Cần phân tích truyện trước khi viết kịch bản tối ưu.",
            status_code=409,
        )

    source_text = "\n\n".join(
        page.extracted_text
        for page in (
            db.query(DBPage)
            .filter(DBPage.document_id == job.current_source_document_id)
            .order_by(DBPage.page_order)
            .all()
        )
        if page.extracted_text
    )
    analysis_input = _build_compact_rewrite_input(job, package, source_text)
    prompt = _build_prompt(analysis_input)
    settings = settings_service.get_ai_planning_settings(db)
    rewrite_settings = _settings_for_rewrite(settings)
    project_root = Path(__file__).resolve().parents[3]

    try:
        raw = ai_planning.run_codex_exec(
            rewrite_settings,
            prompt,
            output_schema=OPTIMIZED_SCRIPT_SCHEMA,
            timeout_seconds=180,
            cwd=project_root,
        )
        optimized = json.loads(raw)
    except ai_planning.AIPlanningError as exc:
        optimized = _fallback_optimized_script(job, analysis_input, exc)
    except (TypeError, ValueError, json.JSONDecodeError) as exc:
        raise ComicAnalysisError(
            "COMIC_AI_OUTPUT_INVALID",
            "AI không trả về kịch bản đúng cấu trúc.",
            status_code=502,
        ) from exc

    if not str(optimized.get("full_story") or "").strip():
        raise ComicAnalysisError(
            "COMIC_AI_OUTPUT_INVALID",
            "Kịch bản tối ưu không có nội dung truyện.",
            status_code=502,
        )

    package["optimized_script"] = optimized
    package["optimized_script_source"] = optimized.pop("_source", "codex")
    job.analysis_package_json = package
    db.flush()
    return job


def _settings_for_rewrite(settings) -> SimpleNamespace:
    """Use a cheaper rewrite profile without mutating persisted settings."""

    return SimpleNamespace(
        provider=settings.provider,
        codex_path=settings.codex_path,
        model=settings.model,
        model_reasoning_effort="high",
        timeout_seconds=settings.timeout_seconds,
    )


def _build_compact_rewrite_input(job: DBJob, package: dict, source_text: str) -> dict[str, Any]:
    panels_raw = _as_list(package.get("panels"))
    dialogues_raw = _as_list(package.get("dialogues"))
    characters_raw = _as_list(package.get("characters"))
    locations_raw = _as_list(package.get("locations"))
    plot = package.get("plot") if isinstance(package.get("plot"), dict) else {}

    panels = _compact_panels(panels_raw, MAX_PANEL_COUNT)
    dialogues = _compact_dialogues(dialogues_raw, MAX_DIALOGUE_COUNT)
    characters = _compact_characters(characters_raw, MAX_CHARACTER_COUNT)
    locations = _compact_locations(locations_raw, MAX_LOCATION_COUNT)

    return {
        "title": _trim(job.title, 180) or "Tập truyện",
        "development_mode": _trim(job.development_mode, 80),
        "counts": {
            "panels_total": len(panels_raw),
            "dialogues_total": len(dialogues_raw),
            "characters_total": len(characters_raw),
            "locations_total": len(locations_raw),
            "selected_panels": len(panels),
            "selected_dialogues": len(dialogues),
        },
        "source_text_excerpt": _trim(source_text, MAX_SOURCE_TEXT_CHARS),
        "plot": {
            "synopsis": _trim(plot.get("synopsis"), 1_000),
            "plot_beats": [_trim(item, 220) for item in _as_list(plot.get("plot_beats"))[:MAX_PLOT_BEAT_COUNT]],
            "relationships": _compact_generic_items(_as_list(plot.get("relationships")), MAX_RELATIONSHIP_COUNT, 260),
            "end_state": _compact_value(plot.get("end_state"), 600),
            "canon_candidates": [_trim(item, 180) for item in _as_list(plot.get("canon_candidates"))[:8]],
            "uncertainties": _compact_generic_items(_as_list(plot.get("uncertainties")), MAX_UNCERTAINTY_COUNT, 180),
            "limitations": _compact_generic_items(_as_list(plot.get("limitations")), MAX_UNCERTAINTY_COUNT, 180),
        },
        "characters": characters,
        "locations": locations,
        "panels": panels,
        "dialogues": dialogues,
        "instruction": (
            "Viết bằng tiếng Việt, giữ đúng bằng chứng quan sát được. "
            "Nếu dữ liệu thiếu, ghi rõ điểm chưa chắc thay vì bịa thêm."
        ),
    }


def _build_prompt(analysis_input: dict[str, Any]) -> str:
    prefix = (
        "Dựa trên package phân tích truyện tranh đã được rút gọn dưới đây, "
        "hãy viết một kịch bản truyện tối ưu bằng tiếng Việt. "
        "Giữ nhất quán nhân vật, bối cảnh, quan hệ và thứ tự diễn biến đã quan sát; "
        "không bịa chi tiết trái bằng chứng. "
        "Kịch bản phải đủ rõ để Story Studio tạo ba candidate tiếp theo.\n\n"
    )
    prompt = prefix + json.dumps(analysis_input, ensure_ascii=False, separators=(",", ":"))
    if len(prompt) <= MAX_PROMPT_CHARS:
        return prompt

    trimmed = dict(analysis_input)
    trimmed["source_text_excerpt"] = _trim(trimmed.get("source_text_excerpt"), 600)
    trimmed["panels"] = _compact_panels(_as_list(trimmed.get("panels")), 12)
    trimmed["dialogues"] = _compact_dialogues(_as_list(trimmed.get("dialogues")), 16)
    trimmed["characters"] = _compact_characters(_as_list(trimmed.get("characters")), 8)
    trimmed["locations"] = _compact_locations(_as_list(trimmed.get("locations")), 6)
    prompt = prefix + json.dumps(trimmed, ensure_ascii=False, separators=(",", ":"))
    return prompt[:MAX_PROMPT_CHARS]


def _compact_panels(items: list[Any], limit: int) -> list[dict[str, Any]]:
    selected = _select_ordered(items, limit)
    return [
        {
            "order": item.get("reading_order") or item.get("order"),
            "asset_id": item.get("asset_id"),
            "visual": _trim(item.get("visual_description") or item.get("visual"), 180),
            "confidence": item.get("confidence"),
            "evidence_ids": _limit_list(item.get("evidence_ids"), 3),
            "needs_review": item.get("needs_review"),
        }
        for item in selected
        if isinstance(item, dict)
    ]


def _compact_dialogues(items: list[Any], limit: int) -> list[dict[str, Any]]:
    selected = _select_ordered(items, limit)
    return [
        {
            "order": item.get("reading_order") or item.get("order"),
            "type": _trim(item.get("bubble_type") or item.get("type"), 40),
            "text": _trim(item.get("text"), 140),
            "speaker_id": item.get("speaker_character_id") or item.get("speaker_id"),
            "confidence": item.get("confidence"),
            "evidence_ids": _limit_list(item.get("evidence_ids"), 3),
        }
        for item in selected
        if isinstance(item, dict) and _trim(item.get("text"), 140)
    ]


def _compact_characters(items: list[Any], limit: int) -> list[dict[str, Any]]:
    compact: list[dict[str, Any]] = []
    for item in items[:limit]:
        if not isinstance(item, dict):
            continue
        compact.append(
            {
                "id": item.get("id"),
                "name": _trim(item.get("name"), 80),
                "role": _trim(item.get("role"), 80),
                "visual": _join_nonempty(
                    [
                        _trim(item.get("face_description"), 80),
                        _trim(item.get("hair_description"), 80),
                        _trim(item.get("body_description"), 80),
                        _trim(item.get("outfit_description"), 100),
                    ],
                    260,
                ),
                "personality": _trim(item.get("personality"), 160),
                "speech_style": _trim(item.get("speech_style"), 120),
                "confidence": item.get("confidence"),
                "evidence_ids": _limit_list(item.get("evidence_ids"), 3),
            }
        )
    return compact


def _compact_locations(items: list[Any], limit: int) -> list[dict[str, Any]]:
    compact: list[dict[str, Any]] = []
    for item in items[:limit]:
        if not isinstance(item, dict):
            continue
        compact.append(
            {
                "id": item.get("id"),
                "name": _trim(item.get("name"), 90),
                "description": _trim(item.get("description"), 180),
                "world_rules": _trim(item.get("world_rules"), 160),
                "confidence": item.get("confidence"),
                "evidence_ids": _limit_list(item.get("evidence_ids"), 3),
            }
        )
    return compact


def _fallback_optimized_script(
    job: DBJob,
    analysis_input: dict[str, Any],
    exc: ai_planning.AIPlanningError,
) -> dict[str, Any]:
    plot = analysis_input.get("plot") if isinstance(analysis_input.get("plot"), dict) else {}
    title = _trim(analysis_input.get("title"), 180) or _trim(job.title, 180) or "Tập truyện"
    synopsis = _trim(plot.get("synopsis"), 1_200) or _derive_synopsis(analysis_input)
    plot_beats = _fallback_plot_beats(analysis_input)
    scene_outline = _fallback_scene_outline(analysis_input, plot_beats)
    character_arcs = _fallback_character_arcs(analysis_input)
    hook = _fallback_hook(synopsis, plot_beats, analysis_input)
    full_story = _fallback_full_story(
        title=title,
        synopsis=synopsis,
        hook=hook,
        plot_beats=plot_beats,
        character_arcs=character_arcs,
        scene_outline=scene_outline,
        analysis_input=analysis_input,
        reason=getattr(exc, "error_code", None) or str(exc),
    )
    return {
        "title": f"Kịch bản tối ưu: {title}",
        "synopsis": synopsis,
        "hook": hook,
        "full_story": full_story,
        "plot_beats": plot_beats,
        "character_arcs": character_arcs,
        "scene_outline": scene_outline,
        "_source": "local_fallback",
    }


def _derive_synopsis(analysis_input: dict[str, Any]) -> str:
    panels = _as_list(analysis_input.get("panels"))
    dialogues = _as_list(analysis_input.get("dialogues"))
    panel_text = next(
        (_trim(item.get("visual"), 240) for item in panels if isinstance(item, dict) and item.get("visual")),
        None,
    )
    dialogue_text = next(
        (_trim(item.get("text"), 180) for item in dialogues if isinstance(item, dict) and item.get("text")),
        None,
    )
    if panel_text and dialogue_text:
        return f"Chương truyện mở ra qua hình ảnh: {panel_text}. Một đoạn thoại then chốt được ghi nhận: “{dialogue_text}”."
    if panel_text:
        return f"Chương truyện được dựng từ các khung hình đã quan sát, bắt đầu với chi tiết: {panel_text}."
    if dialogue_text:
        return f"Chương truyện được dựng từ thoại đã trích xuất, nổi bật với câu: “{dialogue_text}”."
    return "Chương truyện đã có package phân tích nhưng còn thiếu mô tả chi tiết; kịch bản dưới đây chỉ bám theo bằng chứng hiện có."


def _fallback_plot_beats(analysis_input: dict[str, Any]) -> list[str]:
    plot = analysis_input.get("plot") if isinstance(analysis_input.get("plot"), dict) else {}
    beats = [_trim(item, 220) for item in _as_list(plot.get("plot_beats")) if _trim(item, 220)]
    if beats:
        return beats[:MAX_PLOT_BEAT_COUNT]

    panels = _as_list(analysis_input.get("panels"))
    derived = [
        f"Khung {item.get('order')}: {_trim(item.get('visual'), 180)}"
        for item in panels
        if isinstance(item, dict) and _trim(item.get("visual"), 180)
    ]
    if derived:
        return derived[:MAX_PLOT_BEAT_COUNT]
    return ["Thiết lập bối cảnh và nhân vật dựa trên package phân tích đã có."]


def _fallback_scene_outline(analysis_input: dict[str, Any], plot_beats: list[str]) -> list[str]:
    panels = _as_list(analysis_input.get("panels"))
    scenes = [
        f"Cảnh {index + 1}: {_trim(item.get('visual'), 200)}"
        for index, item in enumerate(panels[:8])
        if isinstance(item, dict) and _trim(item.get("visual"), 200)
    ]
    if scenes:
        return scenes
    return [f"Cảnh {index + 1}: {beat}" for index, beat in enumerate(plot_beats[:6])]


def _fallback_character_arcs(analysis_input: dict[str, Any]) -> list[str]:
    characters = _as_list(analysis_input.get("characters"))
    arcs: list[str] = []
    for item in characters:
        if not isinstance(item, dict):
            continue
        name = _trim(item.get("name"), 80) or "Nhân vật chưa định danh"
        role = _trim(item.get("role"), 80)
        personality = _trim(item.get("personality"), 120)
        speech = _trim(item.get("speech_style"), 100)
        details = _join_nonempty([role, personality, speech], 260)
        arcs.append(f"{name}: {details or 'giữ đúng vai trò và hành vi đã quan sát trong package.'}")
    return arcs or ["Giữ nhất quán các nhân vật theo evidence trong panel và thoại đã trích xuất."]


def _fallback_hook(synopsis: str, plot_beats: list[str], analysis_input: dict[str, Any]) -> str:
    dialogues = _as_list(analysis_input.get("dialogues"))
    first_dialogue = next(
        (_trim(item.get("text"), 140) for item in dialogues if isinstance(item, dict) and item.get("text")),
        None,
    )
    if first_dialogue:
        return f"Một câu thoại được quan sát mở khóa xung đột: “{first_dialogue}”."
    if plot_beats:
        return _trim(plot_beats[0], 180) or "Một biến chuyển đầu chương kéo người xem vào mạch truyện."
    return _trim(synopsis, 180) or "Một biến chuyển đầu chương kéo người xem vào mạch truyện."


def _fallback_full_story(
    *,
    title: str,
    synopsis: str,
    hook: str,
    plot_beats: list[str],
    character_arcs: list[str],
    scene_outline: list[str],
    analysis_input: dict[str, Any],
    reason: str,
) -> str:
    locations = _as_list(analysis_input.get("locations"))
    dialogues = _as_list(analysis_input.get("dialogues"))
    location_lines = [
        f"- {_trim(item.get('name'), 80) or 'Bối cảnh'}: {_trim(item.get('description'), 180) or _trim(item.get('world_rules'), 180) or 'giữ theo package.'}"
        for item in locations[:6]
        if isinstance(item, dict)
    ]
    dialogue_lines = [
        f"- Khung {item.get('order')}: “{_trim(item.get('text'), 140)}”"
        for item in dialogues[:10]
        if isinstance(item, dict) and _trim(item.get("text"), 140)
    ]
    sections = [
        f"# {title}",
        "",
        f"Hook: {hook}",
        "",
        f"Tóm tắt: {synopsis}",
        "",
        "Nhịp truyện:",
        *_numbered(plot_beats),
        "",
        "Nhân vật và hướng diễn:",
        *_bullets(character_arcs),
        "",
        "Bối cảnh:",
        *(location_lines or ["- Giữ bối cảnh theo mô tả hình ảnh và evidence trong package."]),
        "",
        "Outline cảnh cho Story Studio:",
        *_numbered(scene_outline),
        "",
        "Thoại/evidence tiêu biểu:",
        *(dialogue_lines or ["- Chưa có thoại chắc chắn; ưu tiên narration bám theo visual evidence."]),
        "",
        f"Ghi chú kỹ thuật: Codex rewrite không hoàn tất ({reason}), nên backend tạo bản fallback từ analysis_package_json. Bản này cố ý chỉ dùng dữ liệu đã quan sát để luồng handoff không bị chặn.",
    ]
    return "\n".join(sections).strip()


def _select_ordered(items: list[Any], limit: int) -> list[dict[str, Any]]:
    dict_items = [item for item in items if isinstance(item, dict)]
    sorted_items = sorted(dict_items, key=lambda item: item.get("reading_order") or item.get("order") or 0)
    if len(sorted_items) <= limit:
        return sorted_items
    if limit <= 2:
        return sorted_items[:limit]

    first = sorted_items[: max(2, limit // 3)]
    last = sorted_items[-2:]
    remaining_slots = limit - len(first) - len(last)
    middle_pool = sorted_items[len(first) : -len(last)]
    middle: list[dict[str, Any]] = []
    if middle_pool and remaining_slots > 0:
        step = max(1, len(middle_pool) // remaining_slots)
        middle = middle_pool[::step][:remaining_slots]
    selected = first + middle + last
    return selected[:limit]


def _compact_generic_items(items: list[Any], limit: int, max_chars: int) -> list[Any]:
    compact: list[Any] = []
    for item in items[:limit]:
        compact.append(_compact_value(item, max_chars))
    return compact


def _compact_value(value: Any, max_chars: int) -> Any:
    if isinstance(value, dict):
        return {
            str(key): _compact_value(inner, max(80, max_chars // 2))
            for key, inner in list(value.items())[:8]
            if inner not in (None, "", [], {})
        }
    if isinstance(value, list):
        return [_compact_value(item, max_chars) for item in value[:6]]
    return _trim(value, max_chars)


def _as_list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def _limit_list(value: Any, limit: int) -> list[Any]:
    return _as_list(value)[:limit]


def _trim(value: Any, max_chars: int) -> str | None:
    text = str(value or "").strip()
    if not text:
        return None
    text = " ".join(text.split())
    if len(text) <= max_chars:
        return text
    return text[: max(0, max_chars - 1)].rstrip() + "…"


def _join_nonempty(values: list[str | None], max_chars: int) -> str | None:
    text = "; ".join(value for value in values if value)
    return _trim(text, max_chars)


def _numbered(values: list[str]) -> list[str]:
    return [f"{index + 1}. {value}" for index, value in enumerate(values)]


def _bullets(values: list[str]) -> list[str]:
    return [f"- {value}" for value in values]


__all__ = ["OPTIMIZED_SCRIPT_SCHEMA", "rewrite_optimized_script"]
