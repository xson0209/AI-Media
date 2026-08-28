from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest

from backend import config, database
from backend.database import session as database_session
from backend.services import ai_planning, product_video, settings as settings_service, video_phase2


@pytest.fixture
def db(tmp_path):
    config.set_data_dir(tmp_path)
    database.init_db()
    session = database_session.SessionLocal()
    try:
        yield session
    finally:
        session.close()
        database_session.engine.dispose()


def test_codex_exec_sanitizes_output_schema_for_openai_response_format(db, tmp_path, monkeypatch):
    fake_codex = tmp_path / "codex"
    fake_codex.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
    fake_codex.chmod(0o755)
    row = settings_service.update_ai_planning_settings(
        db,
        {"codex_path": str(fake_codex), "timeout_seconds": 30},
    )
    captured_schema: dict[str, object] = {}

    def fake_run(command, *, timeout_seconds, cwd=None, input_text=None):
        assert "--output-schema" in command
        schema_path = Path(command[command.index("--output-schema") + 1])
        captured_schema.update(json.loads(schema_path.read_text(encoding="utf-8")))
        output_path = command[command.index("--output-last-message") + 1]
        with open(output_path, "w", encoding="utf-8") as handle:
            handle.write('{"content_retention_beats":[]}')
        return subprocess.CompletedProcess(command, 0, stdout="", stderr="")

    monkeypatch.setattr(ai_planning, "_run_command", fake_run)

    result = ai_planning.run_codex_exec(
        row,
        "Return retention beats.",
        output_schema={
            "type": "object",
            "required": ["content_retention_beats"],
            "properties": {
                "content_retention_beats": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "evidence_refs": {
                                "type": "array",
                                "items": {
                                    "type": ["object", "null"],
                                    "properties": {
                                        "type": {"type": "string"},
                                        "id": {"type": "string"},
                                    },
                                },
                            },
                        },
                    },
                },
            },
        },
    )

    assert result == '{"content_retention_beats":[]}'
    assert captured_schema["required"] == ["content_retention_beats"]
    beat_schema = captured_schema["properties"]["content_retention_beats"]["items"]  # type: ignore[index]
    assert beat_schema["additionalProperties"] is False  # type: ignore[index]
    evidence_item = beat_schema["properties"]["evidence_refs"]["items"]  # type: ignore[index]
    assert "type" not in evidence_item
    object_variant = evidence_item["anyOf"][0]
    assert object_variant["type"] == "object"
    assert object_variant["additionalProperties"] is False
    assert object_variant["required"] == ["type", "id"]
    assert evidence_item["anyOf"][1] == {"type": "null"}


def test_codex_exec_requires_every_response_property_even_when_source_schema_marks_one_optional(db, tmp_path, monkeypatch):
    fake_codex = tmp_path / "codex"
    fake_codex.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
    fake_codex.chmod(0o755)
    row = settings_service.update_ai_planning_settings(
        db,
        {"codex_path": str(fake_codex), "timeout_seconds": 30},
    )
    captured_schema: dict[str, object] = {}

    def fake_run(command, *, timeout_seconds, cwd=None, input_text=None):
        schema_path = Path(command[command.index("--output-schema") + 1])
        captured_schema.update(json.loads(schema_path.read_text(encoding="utf-8")))
        output_path = command[command.index("--output-last-message") + 1]
        with open(output_path, "w", encoding="utf-8") as handle:
            handle.write('{"title":"A","optional_note":null}')
        return subprocess.CompletedProcess(command, 0, stdout="", stderr="")

    monkeypatch.setattr(ai_planning, "_run_command", fake_run)

    result = ai_planning.run_codex_exec(
        row,
        "Return a title.",
        output_schema={
            "type": "object",
            "properties": {
                "title": {"type": "string"},
                "optional_note": {"type": ["string", "null"]},
            },
            "required": ["optional_note"],
        },
    )

    assert result == '{"title":"A","optional_note":null}'
    assert captured_schema["required"] == ["title", "optional_note"]


def test_phase2_output_schemas_have_no_free_form_strict_objects():
    schemas = (
        video_phase2.StoryDevelopmentPlan.model_json_schema(),
        video_phase2.ShotBreakdownPlan.model_json_schema(),
        video_phase2.VideoPromptPackPlan.model_json_schema(),
        product_video.ProductVideoPlan.model_json_schema(),
    )

    def assert_strict(node):
        if isinstance(node, dict):
            if node.get("type") == "object":
                assert isinstance(node.get("properties"), dict)
                # OpenAI/Codex response_format rejects both missing and extra
                # `required` keys.  This specifically protects new fields such
                # as `visible_characters` added by the AI-video planners.
                assert set(node.get("required") or []) == set(node["properties"])
            for value in node.values():
                assert_strict(value)
        elif isinstance(node, list):
            for value in node:
                assert_strict(value)

    for schema in schemas:
        strict = ai_planning._strict_response_format_schema(schema)
        assert_strict(strict)


def test_strict_schema_rejects_free_form_object_contract():
    with pytest.raises(ValueError, match="free-form object without properties"):
        ai_planning._strict_response_format_schema(
            {"type": "object", "properties": {"quality_check": {"type": "object"}}}
        )


def test_strict_schema_discards_stale_required_keys_before_calling_provider():
    strict = ai_planning._strict_response_format_schema(
        {
            "type": "object",
            "properties": {"shots": {"type": "array", "items": {"type": "string"}}},
            # Simulates the provider-breaking mismatch reported for
            # `visible_characters`: required has a key absent from properties.
            "required": ["shots", "visible_characters"],
        }
    )
    assert strict["required"] == ["shots"]

def test_ai_planning_live_test_sends_xin_chao_and_requires_text(db, tmp_path, monkeypatch):
    fake_codex = tmp_path / "codex"
    fake_codex.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
    fake_codex.chmod(0o755)
    row = settings_service.update_ai_planning_settings(
        db,
        {
            "codex_path": str(fake_codex),
            "model": "gpt-5.5",
            "model_reasoning_effort": "xhigh",
            "timeout_seconds": 30,
        },
    )
    prompts: list[str | None] = []

    def fake_run(command, *, timeout_seconds, cwd=None, input_text=None):
        prompts.append(input_text)
        output_path = command[command.index("--output-last-message") + 1]
        with open(output_path, "w", encoding="utf-8") as handle:
            handle.write("Chào bạn, Codex đã phản hồi.")
        return subprocess.CompletedProcess(command, 0, stdout="", stderr="")

    monkeypatch.setattr(ai_planning, "_run_command", fake_run)

    result = ai_planning.test_provider_prompt(row)

    assert prompts == ["xin chào"]
    assert result.ready is True
    assert result.prompt == "xin chào"
    assert result.output_text == "Chào bạn, Codex đã phản hồi."
    assert result.requested_model == "gpt-5.5"
    assert result.requested_reasoning_effort == "xhigh"
    assert result.effective_model == "gpt-5.5"
    assert result.effective_reasoning_effort == "xhigh"
    assert result.model_verified is True
    assert result.error_code is None

    def empty_run(command, *, timeout_seconds, cwd=None, input_text=None):
        output_path = command[command.index("--output-last-message") + 1]
        with open(output_path, "w", encoding="utf-8") as handle:
            handle.write("")
        return subprocess.CompletedProcess(command, 0, stdout="", stderr="")

    monkeypatch.setattr(ai_planning, "_run_command", empty_run)

    empty_result = ai_planning.test_provider_prompt(row)

    assert empty_result.ready is False
    assert empty_result.output_text is None
    assert empty_result.error_code == "CODEX_EMPTY_OUTPUT"
