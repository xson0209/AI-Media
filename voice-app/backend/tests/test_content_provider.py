from __future__ import annotations

from types import SimpleNamespace

from sqlalchemy import create_engine, inspect, text
from sqlalchemy.orm import sessionmaker

from backend.database import migrations
from backend.database.models import AIPlanningSettings
from backend.services import ai_planning, research_ai, settings as settings_service


def _settings(provider: str = "claude", model: str = "sonnet") -> SimpleNamespace:
    return SimpleNamespace(
        content_provider=provider,
        content_model=model,
        provider="codex-cli",
        model="gpt-5.6-sol",
        model_reasoning_effort="ultra",
        timeout_seconds=60,
    )


def test_run_content_dispatches_claude_with_selected_model(monkeypatch):
    calls: list[dict] = []

    def fake_research(prompt: str, **kwargs):
        calls.append({"prompt": prompt, **kwargs})
        return research_ai.ResearchCLIResult(output="claude output", metadata={"model": "sonnet"})

    monkeypatch.setattr(research_ai, "run_research", fake_research)

    result = research_ai.run_content(
        "Tạo một ý tưởng video",
        _settings(),
        timeout_seconds=45,
        tools="",
        effort="low",
    )

    assert result.output == "claude output"
    assert result.metadata["provider"] == "claude"
    assert result.metadata["configured_model"] == "sonnet"
    assert calls == [
        {
            "prompt": "Tạo một ý tưởng video",
            "timeout_seconds": 45,
            "tools": "",
            "effort": "low",
            "model": "sonnet",
        }
    ]


def test_run_content_uses_content_model_for_codex_without_mutating_settings(monkeypatch):
    seen: dict[str, object] = {}

    def fake_codex(settings, prompt: str, *, timeout_seconds: int, return_metadata: bool):
        seen.update(
            settings=settings,
            prompt=prompt,
            timeout_seconds=timeout_seconds,
            return_metadata=return_metadata,
        )
        return ai_planning.CodexExecResult(output="codex output", metadata={})

    original = _settings(provider="codex", model="gpt-5.6-terra")
    monkeypatch.setattr(ai_planning, "run_codex_exec", fake_codex)

    result = research_ai.run_content("Tạo một kịch bản", original, timeout_seconds=30)

    assert result.output == "codex output"
    assert result.metadata["provider"] == "codex"
    assert seen["settings"].model == "gpt-5.6-terra"
    assert original.model == "gpt-5.6-sol"
    assert seen["timeout_seconds"] == 30
    assert seen["return_metadata"] is True


def test_provider_prompt_reports_claude_instead_of_legacy_codex(monkeypatch):
    monkeypatch.setattr(
        ai_planning,
        "run_codex_exec",
        lambda *args, **kwargs: ai_planning.CodexExecResult(
            output="OK",
            metadata={
                "provider": "claude",
                "requested_model": "sonnet",
                "effective_model": "sonnet",
                "model_verified": True,
                "request_id": "request-1",
            },
        ),
    )

    result = ai_planning.test_provider_prompt(_settings(), prompt="xin chào")

    assert result.ready is True
    assert result.provider == "claude-cli"
    assert result.message.startswith("Claude đã phản hồi")
    assert result.effective_model == "sonnet"


def test_ai_planning_migration_adds_content_provider_columns_idempotently(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'legacy.db'}")
    with engine.begin() as connection:
        connection.execute(
            text(
                "CREATE TABLE ai_planning_settings ("
                "id INTEGER PRIMARY KEY, provider VARCHAR NOT NULL DEFAULT 'codex-cli', "
                "codex_path VARCHAR, model VARCHAR, timeout_seconds INTEGER NOT NULL DEFAULT 60, "
                "output_schema_path VARCHAR, updated_at DATETIME)"
            )
        )

    migrations._migrate_ai_video_assistant(engine)
    migrations._migrate_ai_video_assistant(engine)

    columns = {column["name"] for column in inspect(engine).get_columns("ai_planning_settings")}
    assert {"content_provider", "content_model"}.issubset(columns)
    engine.dispose()


def test_settings_upgrade_legacy_claude_model_to_stable_cli_alias():
    engine = create_engine("sqlite:///:memory:")
    AIPlanningSettings.__table__.create(engine)
    db = sessionmaker(bind=engine)()
    try:
        db.add(
            AIPlanningSettings(
                id=1,
                provider="codex-cli",
                content_provider="claude",
                content_model="claude-sonnet-4-5",
                timeout_seconds=60,
            )
        )
        db.commit()

        row = settings_service.get_ai_planning_settings(db)

        assert row.content_provider == "claude"
        assert row.content_model == "sonnet"
    finally:
        db.close()
        engine.dispose()
