"""Content repurposing generators used by the Content Tools workspace.

The service owns the prompt and output contract for the three tools exposed by
the route.  It deliberately returns a reviewable prompt pack instead of
creating an AI Video project implicitly; users can inspect and edit the result
before handing it to the video workspace.
"""

from __future__ import annotations

import json
import re
import uuid
from typing import Any

from .. import models
from . import ai_planning, research_ai

ANGLE_LABELS = {
    "how_to": "Hướng dẫn từng bước",
    "story": "Kể chuyện",
    "comparison": "So sánh",
    "counterpoint": "Phản biện có căn cứ",
    "q_and_a": "Hỏi đáp",
}
DEFAULT_ANGLES = tuple(ANGLE_LABELS)


class ContentToolsError(RuntimeError):
    """A controlled content generation failure with a stable error code."""

    def __init__(self, message: str, *, error_code: str = "CONTENT_TOOLS_ERROR"):
        super().__init__(message)
        self.error_code = error_code


def _source_context(request: models.ContentToolsGenerateRequest) -> str:
    text = (request.source_text or "").strip()
    url = (request.source_url or "").strip()
    parts: list[str] = []
    if text:
        parts.append(f"NỘI DUNG/TRÍCH DẪN NGUỒN:\n{text}")
    if url:
        parts.append(f"URL THAM KHẢO (không tự suy diễn nếu chưa có nội dung):\n{url}")
    return "\n\n".join(parts)


def _mode_rules(request: models.ContentToolsGenerateRequest) -> str:
    if request.mode == "podcast_short":
        return """Chọn một đoạn đáng chú ý từ transcript, nêu lý do chọn và giữ đúng ý người nói.
Tạo hook trong 3-5 giây đầu, script ngắn theo thời lượng mục tiêu, rồi chia thành 4-8 cảnh.
Mỗi cảnh phải có hành động nhìn thấy được, camera, ánh sáng, mood, continuity và video_prompt.
Không bịa dữ kiện ngoài transcript; nếu chỉ có URL thì ghi rõ giới hạn nguồn trong source_summary.
selected_excerpt phải là trích đoạn hoặc tóm tắt có thể kiểm tra lại."""
    if request.mode == "multi_angle":
        selected = request.angles or list(DEFAULT_ANGLES)
        return f"""Viết các phiên bản độc lập nhưng cùng giữ content spine và dữ kiện nguồn.
Chỉ tạo các angle được yêu cầu: {", ".join(selected)}.
Mỗi phiên bản phải có hook, promise, script khác framing; không thêm claim không có trong nguồn.
Mỗi phiên bản có 3-6 cảnh prompt video phù hợp với góc kể."""
    return """Biến bài học thành truyện minh họa có nhân vật, bối cảnh, lựa chọn khó, hậu quả,
hành động đúng và payoff. Người xem phải suy ra bài học từ hành động thay vì nghe một bài giảng.
Giữ learning outcome rõ ràng, phù hợp audience/age band; tạo 4-8 cảnh có continuity và prompt video."""


def build_prompt(request: models.ContentToolsGenerateRequest) -> str:
    # Only the multi-angle tool uses the shared angle vocabulary. The podcast
    # and lesson tools each return one focused result.
    angles = request.angles or list(DEFAULT_ANGLES) if request.mode == "multi_angle" else []
    angle_instruction = ", ".join(angles) or "one focused result"
    schema = {
        "request_id": "uuid string",
        "mode": request.mode,
        "title": "short title",
        "source_summary": "what is supported by the source and any limitations",
        "selected_excerpt": "podcast excerpt or null",
        "angles": [
            {
                "angle": "how_to|story|comparison|counterpoint|q_and_a or mode-specific label",
                "label": "human-readable label",
                "hook": "first 3-5 seconds",
                "promise": "what viewer gets",
                "script": "complete short script",
                "scenes": [
                    {
                        "order": 1,
                        "title": "scene title",
                        "narration": "spoken line",
                        "visual_description": "observable action",
                        "video_prompt": "provider-ready visual prompt",
                        "negative_prompt": "things to avoid",
                        "duration_seconds": 5,
                    }
                ],
            }
        ],
        "next_steps": ["review source claims", "edit script", "handoff to AI Video"],
    }
    return f"""Bạn là biên tập viên nội dung ngắn và đạo diễn prompt video.
Tạo output JSON hợp lệ duy nhất theo schema bên dưới, không markdown fence, không giải thích ngoài JSON.
Ngôn ngữ output: {request.language}. Thời lượng mục tiêu: {request.target_duration_seconds} giây.
Tiêu đề: {request.title or "Tự đặt tiêu đề ngắn, rõ ý"}.
Audience: {request.audience or "người xem phổ thông"}; age band: {request.age_band or "không chỉ định"}.
Visual style: {request.visual_style or "cinematic, clear subject, consistent characters"}.
Lesson outcome (nếu có): {request.lesson_outcome or "suy ra từ nguồn"}.
Mode: {request.mode}. Angles được chọn: {angle_instruction}.

QUY TẮC MODE:
{_mode_rules(request)}

NGUỒN:
{_source_context(request)}

SCHEMA JSON BẮT BUỘC:
{json.dumps(schema, ensure_ascii=False, indent=2)}

Kiểm tra trước khi trả lời: mọi angle có script và ít nhất một scene; prompt mô tả chủ thể,
hành động, camera, ánh sáng và continuity; không biến URL thành dữ kiện chưa đọc được."""


def _extract_json(raw: str) -> dict[str, Any]:
    text = raw.strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*", "", text, flags=re.IGNORECASE)
        text = re.sub(r"\s*```$", "", text)
    try:
        value = json.loads(text)
    except json.JSONDecodeError:
        start, end = text.find("{"), text.rfind("}")
        if start < 0 or end <= start:
            raise ContentToolsError(
                "AI trả về định dạng không hợp lệ; hãy thử lại hoặc rút ngắn nguồn.",
                error_code="CONTENT_TOOLS_INVALID_OUTPUT",
            ) from None
        try:
            value = json.loads(text[start : end + 1])
        except json.JSONDecodeError as exc:
            raise ContentToolsError(
                "AI trả về JSON không hợp lệ; hãy thử lại.",
                error_code="CONTENT_TOOLS_INVALID_OUTPUT",
            ) from exc
    if not isinstance(value, dict):
        raise ContentToolsError("AI không trả về object JSON hợp lệ.", error_code="CONTENT_TOOLS_INVALID_OUTPUT")
    return value


def _provider_metadata(result: Any) -> tuple[str | None, str | None]:
    metadata = getattr(result, "metadata", {}) or {}
    provider = metadata.get("provider") if isinstance(metadata, dict) else None
    model = None
    if isinstance(metadata, dict):
        model = metadata.get("effective_model") or metadata.get("configured_model") or metadata.get("model")
    return (str(provider) if provider else None, str(model) if model else None)


def generate_content_tool(
    request: models.ContentToolsGenerateRequest,
    settings: Any,
) -> models.ContentToolsGenerateResponse:
    """Generate and validate one content-tool result synchronously."""
    prompt = build_prompt(request)
    try:
        result = research_ai.run_content(
            prompt,
            settings,
            timeout_seconds=min(max(int(getattr(settings, "timeout_seconds", 600) or 600), 5), 600),
            tools="",
            effort="high",
        )
    except (research_ai.ResearchCLIError, ai_planning.AIPlanningError):
        raise
    raw = getattr(result, "output", result)
    if not isinstance(raw, str) or not raw.strip():
        raise ContentToolsError("AI không trả về nội dung.", error_code="CONTENT_TOOLS_EMPTY_OUTPUT")

    payload = _extract_json(raw)
    payload.setdefault("request_id", str(uuid.uuid4()))
    payload.setdefault("mode", request.mode)
    payload.setdefault("title", request.title or "Nội dung video mới")
    payload.setdefault("source_summary", "Nguồn đã được dùng để tạo bản nháp; hãy kiểm tra claim trước khi xuất bản.")
    payload.setdefault("selected_excerpt", None)
    payload.setdefault("next_steps", ["Kiểm tra nguồn và claim", "Chỉnh script", "Mở trong AI Video khi đã duyệt"])
    provider, model = _provider_metadata(result)
    payload.setdefault("provider", provider)
    payload.setdefault("model", model)

    if request.mode == "multi_angle" and not payload.get("angles"):
        raise ContentToolsError("AI chưa tạo được góc kể nào.", error_code="CONTENT_TOOLS_INVALID_OUTPUT")
    try:
        return models.ContentToolsGenerateResponse.model_validate(payload)
    except Exception as exc:
        raise ContentToolsError(
            "AI trả về thiếu trường bắt buộc cho prompt pack; hãy thử lại.",
            error_code="CONTENT_TOOLS_INVALID_OUTPUT",
        ) from exc


__all__ = ["ContentToolsError", "build_prompt", "generate_content_tool"]
