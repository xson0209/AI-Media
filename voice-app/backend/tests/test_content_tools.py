from __future__ import annotations

from types import SimpleNamespace

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from pydantic import ValidationError

from backend import models
from backend.services import ai_planning, content_tools, research_ai


def _request(mode: str = "multi_angle") -> models.ContentToolsGenerateRequest:
    return models.ContentToolsGenerateRequest(
        mode=mode,
        source_text="Một bài viết nói về cách xây thói quen đọc sách mỗi ngày.",
        title="Đọc sách đều đặn",
    )


def _payload() -> dict:
    scene = {
        "order": 1,
        "title": "Mở đầu",
        "narration": "Bạn muốn đọc sách đều hơn?",
        "visual_description": "Một người đặt sách cạnh cốc nước rồi mở trang đầu tiên.",
        "video_prompt": "Vertical cinematic close-up, person opens a book, warm morning light, smooth push-in camera, consistent character.",
        "negative_prompt": "blurry text, extra fingers, jump cuts",
        "duration_seconds": 5,
    }
    return {
        "mode": "multi_angle",
        "title": "Đọc sách đều đặn",
        "source_summary": "Tóm tắt dựa trên nội dung được cung cấp.",
        "angles": [
            {
                "angle": "how_to",
                "label": "Hướng dẫn từng bước",
                "hook": "Một mẹo nhỏ để bắt đầu đọc mỗi ngày.",
                "promise": "Bạn sẽ có một quy trình dễ làm.",
                "script": "Đặt sách ở nơi dễ thấy, đọc năm phút và đánh dấu ngày hoàn thành.",
                "scenes": [scene],
            }
        ],
        "next_steps": ["Kiểm tra claim"],
    }


def test_request_rejects_missing_source():
    with pytest.raises(ValidationError):
        models.ContentToolsGenerateRequest(mode="lesson_story")


def test_multi_angle_prompt_defaults_to_all_five_angles():
    prompt = content_tools.build_prompt(_request())
    for angle in ("how_to", "story", "comparison", "counterpoint", "q_and_a"):
        assert angle in prompt


def test_generate_validates_structured_provider_output(monkeypatch):
    monkeypatch.setattr(
        research_ai,
        "run_content",
        lambda *args, **kwargs: ai_planning.CodexExecResult(
            output=__import__("json").dumps(_payload()),
            metadata={"provider": "codex", "effective_model": "gpt-6-sol"},
        ),
    )

    result = content_tools.generate_content_tool(
        _request(),
        SimpleNamespace(timeout_seconds=30),
    )

    assert result.request_id
    assert result.mode == "multi_angle"
    assert result.provider == "codex"
    assert result.model == "gpt-6-sol"
    assert result.angles[0].scenes[0].video_prompt.startswith("Vertical")


def test_generate_returns_controlled_error_for_malformed_output(monkeypatch):
    monkeypatch.setattr(
        research_ai,
        "run_content",
        lambda *args, **kwargs: research_ai.ResearchCLIResult(output="not json", metadata={}),
    )

    with pytest.raises(content_tools.ContentToolsError) as exc_info:
        content_tools.generate_content_tool(_request(), SimpleNamespace(timeout_seconds=30))

    assert exc_info.value.error_code == "CONTENT_TOOLS_INVALID_OUTPUT"


def test_generate_route_returns_reviewable_contract(monkeypatch):
    from backend.database import get_db
    from backend.routes.content_tools import router

    app = FastAPI()
    app.include_router(router)
    app.dependency_overrides[get_db] = lambda: object()
    monkeypatch.setattr(
        "backend.routes.content_tools.settings_service.get_ai_planning_settings",
        lambda db: SimpleNamespace(timeout_seconds=30),
    )
    monkeypatch.setattr(
        "backend.routes.content_tools.content_tools.generate_content_tool",
        lambda request, settings: models.ContentToolsGenerateResponse.model_validate(
            {**_payload(), "request_id": "request-1", "provider": "codex", "model": "gpt-6-sol"}
        ),
    )

    response = TestClient(app).post(
        "/content-tools/generate",
        json={"mode": "multi_angle", "source_text": "Nguồn nội dung"},
    )

    assert response.status_code == 200
    assert response.json()["request_id"] == "request-1"
    assert response.json()["angles"][0]["scenes"][0]["video_prompt"]
