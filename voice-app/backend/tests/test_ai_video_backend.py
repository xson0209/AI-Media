import asyncio
import io
import json
import subprocess
import threading
import time
import zipfile
from datetime import datetime, timedelta
from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from PIL import Image
from sqlalchemy import create_engine, inspect, text

from backend import config, database, models
from backend.database import (
    Generation as DBGeneration,
    VoiceProfile as DBVoiceProfile,
    VideoAutoRun as DBVideoAutoRun,
    VideoDebugEvent as DBVideoDebugEvent,
    VideoPackageExport as DBVideoPackageExport,
    VideoProject as DBVideoProject,
    VideoRenderJob as DBVideoRenderJob,
    VideoScenePrompt as DBVideoScenePrompt,
    VideoSeries as DBVideoSeries,
    VideoShot as DBVideoShot,
    VideoShotClip as DBVideoShotClip,
    VideoShotPrompt as DBVideoShotPrompt,
    VideoSourceBlock as DBVideoSourceBlock,
    VideoSubtitle as DBVideoSubtitle,
    session as database_session,
)
from backend.database.migrations import _migrate_ai_video_assistant
from backend.routes.ai_video import router as ai_video_router
from backend.services import (
    ai_planning,
    settings as settings_service,
    task_queue,
    video_assets,
    video_auto_runs,
    video_debug,
    video_observability,
    video_packages,
    video_phase2,
    video_planning,
    video_planning_pool,
    video_projects,
    video_rendering,
    video_storage,
    video_subtitles,
    video_voice,
)


def _add_phase2_shot(
    db,
    project_id: str,
    *,
    order: int,
    narration: str = "",
    duration_seconds: float | None = 2.0,
    voice_completed: bool = False,
    audio_duration: float | None = None,
) -> DBVideoShot:
    audio_path = None
    if voice_completed:
        audio_file = config.get_generations_dir() / f"render-shot-{order}.wav"
        audio_file.write_bytes(b"fake wav data")
        audio_path = config.to_storage_path(audio_file)
    shot = DBVideoShot(
        project_id=project_id,
        shot_order=order,
        duration_seconds=duration_seconds,
        english_narration=narration,
        status="ready",
        prompt_status="completed",
        voice_status="completed" if voice_completed else "missing",
        subtitle_status="stale",
        audio_path=audio_path,
        audio_duration=audio_duration,
    )
    db.add(shot)
    db.commit()
    db.refresh(shot)
    return shot

def _add_ready_clip(
    db,
    project_id: str,
    shot_id: str,
    *,
    duration_seconds: float = 2.0,
) -> DBVideoShotClip:
    clip_path = video_storage.get_project_subdir(project_id, "shot_clips") / f"test-{shot_id}.mp4"
    clip_path.write_bytes(b"fake mp4 data")
    clip = DBVideoShotClip(
        project_id=project_id,
        shot_id=shot_id,
        source="upload",
        status="ready",
        file_path=video_storage.to_artifact_storage_path(clip_path),
        original_filename="clip.mp4",
        mime_type="video/mp4",
        size_bytes=clip_path.stat().st_size,
        duration_seconds=duration_seconds,
        width=1080,
        height=1920,
        fps=30,
        codec="h264",
        has_audio=False,
        is_active=True,
    )
    db.add(clip)
    db.commit()
    db.refresh(clip)
    return clip

def _scene_detail_fields(**overrides):
    data = {
        "character_appearance": "Small black stickman with a round head, slim body, determined eyes, and a focused expression.",
        "wardrobe_and_sandals": "Minimal black stickman body, no visible clothing, sandals not visible in this scene.",
        "subject_motion_by_duration": "The subject performs one clear action paced to the configured shot duration with readable motion.",
        "setting_and_lighting": "Clean cinematic setting with clear directional light, soft contrast, and visible atmosphere.",
        "detailed_mood": "Focused, hopeful, and emotionally clear with a determined facial expression.",
    }
    data.update(overrides)
    return data

def _creative_direction_fields():
    return {
        "retention_plan": {
            "review_vi": "Mở bằng hình ảnh gây tò mò, tăng nhịp ở giữa và payoff rõ cuối video.",
            "hook_0_2s": "Cầu thủ nhỏ nhìn bảng tỷ số trong 0-2 giây đầu.",
            "viewer_question": "Cậu ấy có lật ngược được trận đấu không?",
            "curiosity_gap": "Giữ cú sút quyết định tới cuối.",
            "beat_curve": [
                {
                    "start_seconds": 0,
                    "end_seconds": 2,
                    "purpose": "cold open",
                    "viewer_reason": "áp lực tỷ số",
                    "pattern_interrupt": "cắt nhanh vào dây giày",
                    "visual_surprise": "mưa làm bảng tỷ số lóe sáng",
                }
            ],
            "pattern_interrupts": ["Đổi từ bảng tỷ số sang cận cảnh dây giày."],
            "payoff_plan": "Kết bằng cú sút vào lưới và khán đài bùng nổ.",
            "dropoff_risks": ["camera đứng yên quá lâu"],
        },
        "sound_design_plan": {
            "music_mood": "cinematic sports tension",
            "energy_curve": "low tension to final swell",
            "ambience_bed": "rainy stadium crowd bed",
            "sound_cues": [{"cue_type": "impact", "timing": "on reveal", "purpose": "mark the turn", "mix_note": "below voice"}],
            "silence_drops": ["short drop before the final shot"],
            "mixing_notes": "Voice stays above music and SFX.",
        },
    }


def _shot_creative_fields(*, final: bool = False, role: str = "build-up"):
    transition_type = "final hold" if final else "match cut"
    trigger = "payoff frame" if final else "action beat"
    edit_reason = "let the payoff land" if final else "carry momentum into the next beat"
    return {
        "retention_role": role,
        "open_loop": "The viewer wants to see whether the subject can finish the next beat.",
        "visual_surprise": "A clear camera scale change reveals a new detail before the segment feels static.",
        "cut_reason": edit_reason,
        "transition_pack": {
            "transition_type": transition_type,
            "trigger": trigger,
            "timing": "last half second",
            "edit_reason": edit_reason,
            "transition_sfx": "short whoosh" if not final else "soft impact resolve",
            "continuity_risk": "low; keep character, setting, style, and story state consistent",
        },
        "sound_design": {
            "music_mood": "focused cinematic tension",
            "energy_curve": "small build into the edit",
            "ambience_bed": "light ambience under the voice",
            "sound_cues": [
                {"cue_type": "whoosh", "timing": "on transition", "purpose": "accent the cut", "mix_note": "below narration"}
            ],
            "silence_drops": ["brief dip before the reveal"],
            "mixing_notes": "Keep narration clearly above music and SFX.",
        },
    }

def _prompt_creative_fields():
    return {
        "retention_notes": "Retention role: keep curiosity open with a clear visual change and payoff setup.",
        "transition_notes": "Transition: motivated cut on action with a short whoosh and low continuity risk.",
        "sound_design_notes": "Sound: subtle ambience and short SFX below the voice; SFX/BGM are editor guidance only.",
    }

@pytest.fixture
def db(tmp_path):
    config.set_data_dir(tmp_path)
    database.init_db()
    video_planning_pool.reset_for_tests()
    session = database_session.SessionLocal()
    try:
        yield session
    finally:
        session.close()
        video_planning_pool.reset_for_tests()
        database_session.engine.dispose()

def test_ai_video_tables_are_created(db):
    tables = set(inspect(database_session.engine).get_table_names())
    assert "ai_planning_settings" in tables
    assert "video_projects" in tables
    assert "video_scenes" in tables
    assert "video_scene_prompts" in tables
    assert "video_scene_assets" in tables
    assert "video_subtitles" in tables
    assert "video_package_exports" in tables
    assert "video_source_blocks" in tables
    assert "video_shots" in tables
    assert "video_shot_prompts" in tables
    assert "video_shot_clips" in tables
    assert "video_render_jobs" in tables
    assert "video_debug_events" in tables
    assert "video_auto_runs" in tables
    assert "video_series" in tables
    project_columns = {column["name"] for column in inspect(database_session.engine).get_columns("video_projects")}
    assert "story_strategy" in project_columns
    assert "continuity_bible" in project_columns
    assert "story_approved" in project_columns
    assert "last_request_id" in project_columns
    assert {"retention_plan_json", "sound_design_plan_json"}.issubset(project_columns)
    assert {"prompt_segment_count", "prompt_segment_duration_seconds", "micro_scenes_per_prompt"}.issubset(project_columns)
    assert {"series_id", "episode_number", "episode_title"}.issubset(project_columns)
    assert {"video_purpose", "dialogue_mode", "narration_density", "call_to_action_style"}.issubset(project_columns)
    series_columns = {column["name"] for column in inspect(database_session.engine).get_columns("video_series")}
    assert {
        "title",
        "character_bible",
        "world_bible",
        "style_bible",
        "continuity_rules",
        "negative_rules",
        "previous_episode_summary",
        "latest_episode_number",
    }.issubset(series_columns)
    scene_columns = {column["name"] for column in inspect(database_session.engine).get_columns("video_scenes")}
    assert "approved" in scene_columns
    assert "no_narration" in scene_columns
    clip_columns = {column["name"] for column in inspect(database_session.engine).get_columns("video_shot_clips")}
    assert {"project_id", "shot_id", "status", "file_path", "duration_seconds", "is_active"}.issubset(clip_columns)
    render_columns = {column["name"] for column in inspect(database_session.engine).get_columns("video_render_jobs")}
    assert {"project_id", "status", "progress", "settings_json", "output_path", "stale"}.issubset(render_columns)
    shot_columns = {column["name"] for column in inspect(database_session.engine).get_columns("video_shots")}
    assert {"retention_json", "transition_json", "sound_design_json", "micro_scenes_json", "retainability_quality_check"}.issubset(shot_columns)
    shot_prompt_columns = {column["name"] for column in inspect(database_session.engine).get_columns("video_shot_prompts")}
    assert {"retention_notes", "transition_notes", "sound_design_notes"}.issubset(shot_prompt_columns)
    auto_run_columns = {column["name"] for column in inspect(database_session.engine).get_columns("video_auto_runs")}
    assert {
        "project_id",
        "mode",
        "status",
        "current_step",
        "review_stage",
        "progress",
        "create_package",
        "force",
        "step_results_json",
        "failure_reason",
        "error_code",
        "started_at",
        "completed_at",
    }.issubset(auto_run_columns)

def test_ai_video_migration_upgrades_legacy_project_table_before_series_index(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'legacy.db'}")
    with engine.begin() as conn:
        conn.execute(text("""
            CREATE TABLE video_projects (
                id VARCHAR PRIMARY KEY,
                title VARCHAR NOT NULL,
                topic TEXT NOT NULL,
                language VARCHAR NOT NULL DEFAULT 'vi',
                target_duration_seconds INTEGER,
                aspect_ratio VARCHAR NOT NULL DEFAULT '9:16',
                visual_style TEXT,
                voice_profile_id VARCHAR,
                status VARCHAR NOT NULL DEFAULT 'draft',
                creative_brief TEXT,
                script_text TEXT,
                style_bible TEXT,
                character_bible TEXT,
                script_approved BOOLEAN NOT NULL DEFAULT 0,
                phase VARCHAR NOT NULL DEFAULT 'phase1',
                target_language VARCHAR NOT NULL DEFAULT 'en',
                created_at DATETIME,
                updated_at DATETIME
            )
        """))
        conn.execute(
            text("""
                INSERT INTO video_projects (id, title, topic, language, aspect_ratio, status, script_approved)
                VALUES ('legacy-project', 'Legacy project', 'Old topic', 'vi', '9:16', 'draft', 0)
            """)
        )

    _migrate_ai_video_assistant(engine)
    _migrate_ai_video_assistant(engine)

    inspector = inspect(engine)
    project_columns = {column["name"] for column in inspector.get_columns("video_projects")}
    assert {
        "series_id",
        "episode_number",
        "episode_title",
        "package_stale",
        "video_purpose",
        "dialogue_mode",
        "narration_density",
        "call_to_action_style",
    }.issubset(project_columns)
    assert "idx_video_projects_series_episode" in {index["name"] for index in inspector.get_indexes("video_projects")}
    with engine.connect() as conn:
        row = conn.execute(
            text("SELECT series_id, episode_number, episode_title, package_stale, video_purpose, dialogue_mode, narration_density, call_to_action_style FROM video_projects WHERE id = 'legacy-project'")
        ).mappings().one()
    assert row["series_id"] is None
    assert row["episode_number"] is None
    assert row["episode_title"] is None
    assert row["package_stale"] in (0, False)
    assert row["video_purpose"] == "custom"
    assert row["dialogue_mode"] == "voiceover"
    assert row["narration_density"] == "balanced"
    assert row["call_to_action_style"] is None
    engine.dispose()

def test_ai_planning_settings_default_and_invalid_path_check(db):
    row = settings_service.get_ai_planning_settings(db)
    assert row.provider == "codex-cli"
    assert row.timeout_seconds == 60

    row = settings_service.update_ai_planning_settings(db, {"codex_path": "/missing/codex"})
    result = ai_planning.check_provider(row)

    assert result.ready is False
    assert result.error_code == "CODEX_PATH_INVALID"
    assert result.request_id


def test_ai_planning_settings_repairs_stale_codex_path_when_detected(db, monkeypatch):
    detected = r"C:\Users\test\AppData\Roaming\npm\codex.cmd"
    settings_service.update_ai_planning_settings(db, {"codex_path": "/opt/homebrew/bin/codex"})
    monkeypatch.setenv("VOICEBOX_CODEX_PATH", detected)
    monkeypatch.setattr(
        settings_service,
        "_looks_like_stale_cross_platform_codex_path",
        lambda path: path == "/opt/homebrew/bin/codex",
    )

    row = settings_service.get_ai_planning_settings(db)

    assert row.codex_path == detected


def test_ai_planning_provider_check_success_with_mocked_codex(db, tmp_path, monkeypatch):
    fake_codex = tmp_path / "codex"
    fake_codex.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
    fake_codex.chmod(0o755)
    row = settings_service.update_ai_planning_settings(db, {"codex_path": str(fake_codex)})

    def fake_run(command, *, timeout_seconds, cwd=None, input_text=None):
        if command[-1] == "--version":
            return subprocess.CompletedProcess(command, 0, stdout="codex-cli 0.test\n", stderr="")
        return subprocess.CompletedProcess(command, 0, stdout="Logged in\n", stderr="")

    monkeypatch.setattr(ai_planning, "_run_command", fake_run)

    result = ai_planning.check_provider(row)

    assert result.ready is True
    assert result.version == "codex-cli 0.test"

def test_ai_planning_provider_check_command_error(db, tmp_path, monkeypatch):
    fake_codex = tmp_path / "codex"
    fake_codex.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
    fake_codex.chmod(0o755)
    row = settings_service.update_ai_planning_settings(db, {"codex_path": str(fake_codex)})

    def fake_run(command, *, timeout_seconds, cwd=None, input_text=None):
        if command[-1] == "--version":
            return subprocess.CompletedProcess(command, 0, stdout="codex-cli 0.test\n", stderr="")
        return subprocess.CompletedProcess(command, 1, stdout="", stderr="not logged in")

    monkeypatch.setattr(ai_planning, "_run_command", fake_run)

    result = ai_planning.check_provider(row)

    assert result.ready is False
    assert result.error_code == "CODEX_NOT_LOGGED_IN"

def test_ai_planning_provider_check_allows_exec_when_login_status_fails(db, tmp_path, monkeypatch):
    fake_codex = tmp_path / "codex"
    fake_codex.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
    fake_codex.chmod(0o755)
    row = settings_service.update_ai_planning_settings(db, {"codex_path": str(fake_codex)})

    def fake_run(command, *, timeout_seconds, cwd=None, input_text=None):
        if command[-1] == "--version":
            return subprocess.CompletedProcess(command, 0, stdout="codex-cli 0.test\n", stderr="")
        if command[:3] == [str(fake_codex), "login", "status"]:
            return subprocess.CompletedProcess(command, 1, stdout="Not logged in\n", stderr="")
        return subprocess.CompletedProcess(command, 0, stdout="OK\n", stderr="")

    monkeypatch.setattr(ai_planning, "_run_command", fake_run)

    result = ai_planning.check_provider(row)

    assert result.ready is True
    assert result.error_code is None
    assert "codex exec chạy được" in result.message

def test_ai_planning_provider_check_preserves_non_auth_exec_error_after_login_status_fails(db, tmp_path, monkeypatch):
    fake_codex = tmp_path / "codex"
    fake_codex.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
    fake_codex.chmod(0o755)
    row = settings_service.update_ai_planning_settings(db, {"codex_path": str(fake_codex)})

    def fake_run(command, *, timeout_seconds, cwd=None, input_text=None):
        if command[-1] == "--version":
            return subprocess.CompletedProcess(command, 0, stdout="codex-cli 0.test\n", stderr="")
        if command[:3] == [str(fake_codex), "login", "status"]:
            return subprocess.CompletedProcess(command, 1, stdout="Not logged in\n", stderr="")
        return subprocess.CompletedProcess(command, 1, stdout="", stderr="model does not exist")

    monkeypatch.setattr(ai_planning, "_run_command", fake_run)

    result = ai_planning.check_provider(row)

    assert result.ready is False
    assert result.error_code == "CODEX_EXEC_NONZERO"

def test_ai_planning_provider_check_prefers_not_logged_in_when_exec_times_out(db, tmp_path, monkeypatch):
    fake_codex = tmp_path / "codex"
    fake_codex.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
    fake_codex.chmod(0o755)
    row = settings_service.update_ai_planning_settings(db, {"codex_path": str(fake_codex)})

    def fake_run(command, *, timeout_seconds, cwd=None, input_text=None):
        if command[-1] == "--version":
            return subprocess.CompletedProcess(command, 0, stdout="codex-cli 0.test\n", stderr="")
        if command[:3] == [str(fake_codex), "login", "status"]:
            return subprocess.CompletedProcess(command, 1, stdout="Not logged in\n", stderr="")
        raise subprocess.TimeoutExpired(command, timeout_seconds)

    monkeypatch.setattr(ai_planning, "_run_command", fake_run)

    result = ai_planning.check_provider(row)

    assert result.ready is False
    assert result.error_code == "CODEX_NOT_LOGGED_IN"
    assert "chưa đăng nhập" in result.message

def test_ai_planning_provider_check_timeout(db, tmp_path, monkeypatch):
    fake_codex = tmp_path / "codex"
    fake_codex.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
    fake_codex.chmod(0o755)
    row = settings_service.update_ai_planning_settings(db, {"codex_path": str(fake_codex)})

    def fake_run(command, *, timeout_seconds, cwd=None):
        raise subprocess.TimeoutExpired(command, timeout_seconds)

    monkeypatch.setattr(ai_planning, "_run_command", fake_run)

    result = ai_planning.check_provider(row)

    assert result.ready is False
    assert result.error_code == "CODEX_CHECK_TIMEOUT"

def test_codex_exec_falls_back_when_provider_rejects_output_schema(db, tmp_path, monkeypatch):
    fake_codex = tmp_path / "codex"
    fake_codex.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
    fake_codex.chmod(0o755)
    row = settings_service.update_ai_planning_settings(
        db,
        {"codex_path": str(fake_codex), "timeout_seconds": 30},
    )
    calls = []

    def fake_run(command, *, timeout_seconds, cwd=None, input_text=None):
        calls.append((command, input_text))
        assert command[-1] == "-"
        if "--output-schema" in command:
            assert input_text == "Return ok JSON."
            return subprocess.CompletedProcess(
                command,
                1,
                stdout="",
                stderr="ERROR: unexpected status 400 Bad Request: response_format unsupported",
            )
        output_path = command[command.index("--output-last-message") + 1]
        assert input_text is not None
        assert "JSON Schema:" in input_text
        with open(output_path, "w", encoding="utf-8") as handle:
            handle.write('{"ok":"yes"}')
        return subprocess.CompletedProcess(command, 0, stdout="", stderr="")

    monkeypatch.setattr(ai_planning, "_run_command", fake_run)

    result = ai_planning.run_codex_exec(
        row,
        "Return ok JSON.",
        output_schema={
            "type": "object",
            "properties": {"ok": {"type": "string"}},
            "required": ["ok"],
        },
    )

    assert result == '{"ok":"yes"}'
    assert len(calls) == 2
    assert "--output-schema" in calls[0][0]
    assert "--output-schema" not in calls[1][0]


def test_codex_exec_sends_long_prompt_via_stdin(db, tmp_path, monkeypatch):
    fake_codex = tmp_path / "codex"
    fake_codex.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
    fake_codex.chmod(0o755)
    row = settings_service.update_ai_planning_settings(
        db,
        {"codex_path": str(fake_codex), "timeout_seconds": 30},
    )
    long_prompt = "Create a detailed plan.\n" + ("x" * 100_000)

    def fake_run(command, *, timeout_seconds, cwd=None, input_text=None):
        assert command[-1] == "-"
        assert all(long_prompt not in str(part) for part in command)
        assert input_text == long_prompt
        output_path = command[command.index("--output-last-message") + 1]
        with open(output_path, "w", encoding="utf-8") as handle:
            handle.write("done")
        return subprocess.CompletedProcess(command, 0, stdout="", stderr="")

    monkeypatch.setattr(ai_planning, "_run_command", fake_run)

    result = ai_planning.run_codex_exec(row, long_prompt)

    assert result == "done"


def test_codex_run_command_uses_utf8_for_stdin(monkeypatch):
    captured = {}

    def fake_subprocess_run(command, **kwargs):
        captured.update(kwargs)
        return subprocess.CompletedProcess(command, 0, stdout="OK", stderr="")

    monkeypatch.setattr(ai_planning.subprocess, "run", fake_subprocess_run)

    result = ai_planning._run_command(
        ["codex", "exec", "-"],
        timeout_seconds=5,
        input_text="Tạo prompt tiếng Việt có dấu.",
    )

    assert result.returncode == 0
    assert captured["input"] == "Tạo prompt tiếng Việt có dấu."
    assert captured["encoding"] == "utf-8"
    assert captured["errors"] == "replace"


def test_video_project_crud_and_scene_status(db):
    created = video_projects.create_project(
        models.VideoProjectCreate(
            topic="Một video ngắn về cà phê sáng",
            language="vi",
            aspect_ratio="9:16",
        ),
        db,
    )

    assert created.title == "Một video ngắn về cà phê sáng"
    assert created.series_id is None
    assert created.episode_number is None
    assert created.scene_count == 0
    assert (config.get_data_dir() / "video_projects" / created.id).is_dir()
    assert [project.id for project in video_projects.list_projects(db)] == [created.id]

    detail = video_projects.get_project(created.id, db)
    assert detail is not None
    assert detail.id == created.id
    assert detail.scenes == []

    scenes = video_projects.replace_scenes(
        created.id,
        models.VideoScenesReplaceRequest(
            scenes=[
                models.VideoSceneDraft(
                    title="Mở đầu",
                    dialogue="Chào buổi sáng.",
                    visual_description="Ly cà phê trên bàn gỗ.",
                    target_duration_seconds=5,
                )
            ]
        ),
        db,
    )
    assert scenes is not None
    assert len(scenes) == 1
    assert scenes[0].scene_order == 1

    approved_scene = video_projects.set_scene_approved(created.id, scenes[0].id, True, db)
    assert approved_scene is not None
    assert approved_scene.approved is True

    status = video_projects.get_project_status(created.id, db)
    assert status is not None
    assert status.missing_script is False
    assert status.missing_prompt is True
    assert status.missing_voice is True
    assert status.package_ready is False

    no_narration_scene = video_projects.set_scene_no_narration(created.id, scenes[0].id, True, db)
    assert no_narration_scene is not None
    assert no_narration_scene.no_narration is True
    assert no_narration_scene.voice_status == "skipped"

    status = video_projects.get_project_status(created.id, db)
    assert status is not None
    assert status.missing_voice is False

    assert video_projects.delete_project(created.id, db) is True
    assert video_projects.get_project(created.id, db) is None
    assert not (config.get_data_dir() / "video_projects" / created.id).exists()

def test_video_project_response_marks_latest_failed_auto_run(db):
    project = video_projects.create_project(models.VideoProjectCreate(topic="Failed project", phase="phase2"), db)
    db.add(
        DBVideoAutoRun(
            project_id=project.id,
            status="failed",
            current_step="generate_voice",
            progress=0.7,
            failure_reason="Voice failed",
            error_code="VIDEO_AUTO_RUN_VOICE_FAILED",
        )
    )
    db.commit()

    listed = {item.id: item for item in video_projects.list_projects(db)}

    assert listed[project.id].active_run_status == "failed"
    assert listed[project.id].active_run_step == "generate_voice"
    assert listed[project.id].active_run_progress == 0.7

    db.add(
        DBVideoAutoRun(
            project_id=project.id,
            status="completed",
            current_step="completed",
            progress=1.0,
            updated_at=datetime.utcnow() + timedelta(seconds=1),
        )
    )
    db.commit()

    listed = {item.id: item for item in video_projects.list_projects(db)}

    assert listed[project.id].active_run_status is None
    assert listed[project.id].active_run_step is None
    assert listed[project.id].active_run_progress is None

def test_video_project_purpose_create_update_override_and_stale(db):
    purpose_expectations = {
        "custom": ("en", "voiceover", "balanced"),
        "vietnam_market": ("vi", "voiceover", "balanced"),
        "global_short": ("en", "voiceover", "balanced"),
        "educational_explainer": ("vi", "voiceover", "dense"),
        "sales_ad": ("vi", "voiceover", "light"),
        "localized_variant": ("en", "voiceover", "balanced"),
    }
    for purpose, (language, dialogue_mode, narration_density) in purpose_expectations.items():
        created = video_projects.create_project(
            models.VideoProjectCreate(topic=f"Preset {purpose}", phase="phase2", video_purpose=purpose),
            db,
        )
        assert created.video_purpose == purpose
        assert created.target_language == language
        assert created.dialogue_mode == dialogue_mode
        assert created.narration_density == narration_density

    global_vi = video_projects.create_project(
        models.VideoProjectCreate(
            topic="Global preset nhưng xuất tiếng Việt",
            phase="phase2",
            video_purpose="global_short",
            target_language="vi",
        ),
        db,
    )
    preserved_language = video_projects.update_project(
        global_vi.id,
        models.VideoProjectUpdate(video_purpose="sales_ad"),
        db,
    )
    assert preserved_language is not None
    assert preserved_language.video_purpose == "sales_ad"
    assert preserved_language.target_language == "vi"

    vietnam = video_projects.create_project(
        models.VideoProjectCreate(topic="Video cho thị trường Việt Nam", phase="phase2", video_purpose="vietnam_market"),
        db,
    )
    assert vietnam.target_language == "vi"
    assert vietnam.video_purpose == "vietnam_market"
    assert vietnam.dialogue_mode == "voiceover"

    override = video_projects.create_project(
        models.VideoProjectCreate(
            topic="Video Việt nhưng nói tiếng Anh",
            phase="phase2",
            video_purpose="vietnam_market",
            target_language="en",
        ),
        db,
    )
    assert override.target_language == "en"
    assert override.video_purpose == "vietnam_market"

    shot = _add_phase2_shot(db, vietnam.id, order=1, narration="Lời cũ cần tạo lại.", voice_completed=True, audio_duration=2.0)
    db.add(DBVideoSubtitle(project_id=vietnam.id, status="completed"))
    db.add(DBVideoPackageExport(project_id=vietnam.id, status="completed"))
    row = db.get(DBVideoProject, vietnam.id)
    row.story_approved = True
    row.script_approved = True
    db.commit()

    updated = video_projects.update_project(
        vietnam.id,
        models.VideoProjectUpdate(video_purpose="sales_ad"),
        db,
    )
    assert updated is not None
    assert updated.target_language == "vi"
    assert updated.video_purpose == "sales_ad"
    assert updated.narration_density == "light"
    assert updated.call_to_action_style == "direct"

    refreshed_project = db.get(DBVideoProject, vietnam.id)
    refreshed_shot = db.get(DBVideoShot, shot.id)
    subtitle = db.query(DBVideoSubtitle).filter(DBVideoSubtitle.project_id == vietnam.id).one()
    assert refreshed_project.planning_status == "stale"
    assert refreshed_project.story_approved is False
    assert refreshed_shot.status == "stale"
    assert refreshed_shot.prompt_status == "stale"
    assert refreshed_shot.voice_status == "stale"
    assert refreshed_shot.subtitle_status == "stale"
    assert subtitle.status == "stale"
    assert video_projects.get_project(vietnam.id, db).package_stale is True

def test_video_series_crud_episode_creation_and_detach(db):
    standalone = video_projects.create_project(models.VideoProjectCreate(topic="Standalone video", phase="phase2"), db)
    assert standalone.series_id is None
    assert video_projects.get_project(standalone.id, db).series_id is None

    series = video_projects.create_series(
        models.VideoSeriesCreate(
            title="Stickman Adventures",
            character_bible="Same small black stickman hero.",
            world_bible="Minimal city world with clean white background.",
            style_bible="High contrast cinematic stickman style.",
            continuity_rules="Never change the hero identity.",
            negative_rules="No extra main characters.",
            previous_episode_summary="Episode 0 setup.",
        ),
        db,
    )
    assert series.episode_count == 0
    updated = video_projects.update_series(series.id, models.VideoSeriesUpdate(style_bible="Updated style bible."), db)
    assert updated is not None
    assert updated.style_bible == "Updated style bible."

    first = video_projects.create_episode(
        series.id,
        models.VideoEpisodeCreate(topic="The hero finds the first clue", episode_title="First clue", prompt_segment_count=3, prompt_segment_duration_seconds=8, micro_scenes_per_prompt=2),
        db,
    )
    second = video_projects.create_episode(
        series.id,
        models.VideoEpisodeCreate(topic="The hero follows the clue", episode_title="Second clue"),
        db,
    )
    assert first is not None and second is not None
    assert first.series_id == series.id
    assert first.episode_number == 1
    assert second.episode_number == 2
    assert second.prompt_segment_count == 3
    assert second.prompt_segment_duration_seconds == 8
    assert second.micro_scenes_per_prompt == 2

    listed = {project.id: project for project in video_projects.list_projects(db)}
    assert listed[first.id].series_title == "Stickman Adventures"
    assert listed[standalone.id].series_title is None

    assert video_projects.delete_series(series.id, db, delete_episodes=False) is True
    detached = video_projects.get_project(first.id, db)
    assert detached is not None
    assert detached.series_id is None
    assert db.get(DBVideoSeries, series.id) is None

def test_localize_project_copies_source_config_without_artifacts(db):
    source = video_projects.create_project(
        models.VideoProjectCreate(
            topic="Video bản gốc",
            phase="phase2",
            target_language="vi",
            video_purpose="vietnam_market",
            prompt_segment_count=2,
            prompt_segment_duration_seconds=8,
            micro_scenes_per_prompt=2,
            voice_profile_id="voice-vi",
            source_blocks=[
                models.VideoSourceBlockDraft(block_type="idea", content="Ý tưởng gốc"),
                models.VideoSourceBlockDraft(block_type="style_notes", content="Cinematic"),
            ],
        ),
        db,
    )
    _add_phase2_shot(db, source.id, order=1, narration="Voice cũ", voice_completed=True, audio_duration=2.0)
    db.add(DBVideoPackageExport(project_id=source.id, status="completed"))
    db.commit()

    localized = video_projects.localize_project(
        source.id,
        models.VideoProjectLocalizeRequest(target_language="en", video_purpose="localized_variant"),
        db,
    )
    assert localized is not None
    assert localized.id != source.id
    assert localized.target_language == "en"
    assert localized.video_purpose == "localized_variant"
    assert localized.prompt_segment_count == 2
    assert localized.prompt_segment_duration_seconds == 8
    assert localized.micro_scenes_per_prompt == 2
    assert localized.voice_profile_id == "voice-vi"

    detail = video_projects.get_project(localized.id, db)
    assert detail is not None
    assert [block.content for block in detail.source_blocks] == ["Ý tưởng gốc", "Cinematic"]
    assert detail.shots == []
    assert db.query(DBVideoPackageExport).filter(DBVideoPackageExport.project_id == localized.id).count() == 0

    readiness = video_packages.get_package_readiness(localized.id, db)
    assert readiness is not None
    assert readiness.language == "en"
    assert readiness.video_purpose == "localized_variant"

def test_delete_project_in_series_keeps_series(db):
    series = video_projects.create_series(models.VideoSeriesCreate(title="Keep Series"), db)
    project = video_projects.create_episode(series.id, models.VideoEpisodeCreate(topic="One episode"), db)
    assert project is not None
    db.add(DBVideoAutoRun(project_id=project.id, status="failed", current_step="generate_prompts"))
    db.commit()

    assert video_projects.delete_project(project.id, db) is True
    assert db.get(DBVideoSeries, series.id) is not None
    assert db.query(DBVideoAutoRun).filter(DBVideoAutoRun.project_id == project.id).count() == 0

def test_series_context_only_injects_for_episode_projects(db):
    standalone = video_projects.create_project(models.VideoProjectCreate(topic="Standalone context", phase="phase2"), db)
    standalone_row = db.get(DBVideoProject, standalone.id)
    assert standalone_row is not None
    assert "Series context" not in video_phase2._project_context(standalone_row, db)

    series = video_projects.create_series(
        models.VideoSeriesCreate(
            title="Continuity Series",
            character_bible="Hero keeps the same round head and black stick body.",
            world_bible="Same quiet city at night.",
            style_bible="Minimal cinematic monochrome.",
            continuity_rules="Preserve character and world.",
            negative_rules="Do not add a second hero.",
            previous_episode_summary="The hero learned the city layout.",
        ),
        db,
    )
    episode = video_projects.create_episode(series.id, models.VideoEpisodeCreate(topic="Episode context", episode_title="Night route"), db)
    assert episode is not None
    episode_row = db.get(DBVideoProject, episode.id)
    assert episode_row is not None
    context = video_phase2._project_context(episode_row, db)
    assert "Series context" in context
    assert "Continuity Series" in context
    assert "same round head" in context
    assert "Same quiet city" in context
    assert "Minimal cinematic" in context

def test_series_memory_markdown_file_is_created_and_read_by_planning_context(db):
    series = video_projects.create_series(
        models.VideoSeriesCreate(
            title="Long Stickman Series",
            character_bible="Hero is always a small black stickman.",
            world_bible="A clean white city with simple geometric streets.",
            style_bible="Minimal high-contrast cinematic comedy.",
            continuity_rules="Never reset the hero's learned skills.",
            negative_rules="No duplicate hero.",
            previous_episode_summary="Episode 0: the hero learned the city map.",
        ),
        db,
    )
    memory_path = video_storage.get_series_memory_path(series.id)
    assert memory_path.exists()
    initial_memory = memory_path.read_text(encoding="utf-8")
    assert "# Series Memory: Long Stickman Series" in initial_memory
    assert "Hero is always a small black stickman." in initial_memory

    updated = video_projects.update_series(
        series.id,
        models.VideoSeriesUpdate(previous_episode_summary="Episode 1: the hero found a glowing key."),
        db,
    )
    assert updated is not None
    assert "glowing key" in memory_path.read_text(encoding="utf-8")

    episode = video_projects.create_episode(series.id, models.VideoEpisodeCreate(topic="The hero opens the next door"), db)
    episode_row = db.get(DBVideoProject, episode.id)
    assert episode_row is not None
    context = video_phase2._project_context(episode_row, db)
    assert "Series memory file (`series-memory.md`)" in context
    assert "Episode Index" in context
    assert "glowing key" in context
    assert "The hero opens the next door" in context

def test_render_completion_updates_series_memory_markdown(db, monkeypatch):
    series = video_projects.create_series(
        models.VideoSeriesCreate(
            title="Rendered Series",
            character_bible="Same founder, navy jacket.",
            world_bible="Warm studio office.",
            style_bible="Clean cinematic realism.",
        ),
        db,
    )
    episode = video_projects.create_episode(series.id, models.VideoEpisodeCreate(topic="Founder closes the first deal", episode_title="First deal"), db)
    project = db.get(DBVideoProject, episode.id)
    assert project is not None
    project.story_strategy = "Open on pressure, reveal the client call, finish on the signed deal."
    project.continuity_bible = "Same founder, navy jacket, warm office lighting."
    project.detailed_script = "The founder reads the offer, calls the client, and signs the first deal."
    project.status = "prompts_ready"
    project.planning_status = "prompts_ready"
    db.commit()

    shot = _add_phase2_shot(db, project.id, order=1, narration="", duration_seconds=2.0)
    _add_ready_clip(db, project.id, shot.id, duration_seconds=2.0)
    settings = models.VideoRenderSettings(subtitle_mode="none", fit_mode="pad", fps=24)
    job = DBVideoRenderJob(
        project_id=project.id,
        status="queued",
        progress=0.0,
        current_step="queued",
        settings_json=settings.model_dump_json(),
        readiness_json="{}",
        stale=False,
    )
    db.add(job)
    db.commit()
    db.refresh(job)

    monkeypatch.setattr(video_rendering, "detect_tools", lambda: video_rendering.FFmpegTools(ffmpeg="ffmpeg", ffprobe="ffprobe"))

    def fake_run_command(cmd, timeout):
        output_path = Path(cmd[-1])
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_bytes(b"fake media")

    monkeypatch.setattr(video_rendering, "_run_command", fake_run_command)

    video_rendering._render_job_steps(job, db)

    refreshed_job = db.get(DBVideoRenderJob, job.id)
    assert refreshed_job.status == "completed"
    refreshed_series = db.get(DBVideoSeries, series.id)
    assert refreshed_series.latest_episode_number == 1
    assert "signed deal" in refreshed_series.previous_episode_summary

    memory_text = video_storage.get_series_memory_path(series.id).read_text(encoding="utf-8")
    assert "Latest render status: `completed`" in memory_text
    assert "Tập 01 - First deal" in memory_text
    assert "signed deal" in memory_text

def test_phase2_normalized_codex_context_and_purpose_prompt(db, monkeypatch):
    project = video_projects.create_project(
        models.VideoProjectCreate(
            topic="Explain a product clearly",
            phase="phase2",
            target_language="en",
            video_purpose="educational_explainer",
            dialogue_mode="mixed",
            narration_density="dense",
            source_blocks=[
                models.VideoSourceBlockDraft(block_type="idea", content="  Main idea  "),
                models.VideoSourceBlockDraft(block_type="rough_script", content="Second block"),
            ],
        ),
        db,
    )
    rows = {
        row.block_type: row
        for row in db.query(DBVideoSourceBlock).filter(DBVideoSourceBlock.project_id == project.id).all()
    }
    rows["idea"].sort_order = 2
    rows["idea"].content = "  Main idea trimmed  "
    rows["rough_script"].sort_order = 1
    rows["rough_script"].content = "   "
    db.commit()
    project_row = db.get(DBVideoProject, project.id)

    context = video_phase2.normalize_phase2_codex_context(project_row, db)
    assert context["target_language"] == "en"
    assert context["video_purpose"] == "educational_explainer"
    assert context["dialogue_mode"] == "mixed"
    assert context["narration_density"] == "dense"
    assert context["source_blocks"] == [
        {"id": rows["idea"].id, "sort_order": 2, "block_type": "idea", "content": "Main idea trimmed"}
    ]
    project_context = video_phase2._project_context(project_row, db)
    assert "Mục đích video: educational_explainer" in project_context
    assert "Dialogue mode: mixed" in project_context
    assert "Purpose guidance must never override target_language" in project_context

    captured_prompt = {"text": ""}

    def fake_run(settings, prompt, *, output_schema, timeout_seconds=None, cwd=None):
        assert output_schema == video_phase2.STORY_DEVELOPMENT_SCHEMA
        captured_prompt["text"] = prompt
        return json.dumps(
            {
                "input_synthesis": "Clear educational story.",
                "story_strategy": "Explain one idea clearly.",
                "continuity_bible": "Keep the same visual logic.",
                "detailed_script": "Explain the idea in English.",
                **_creative_direction_fields(),
                "scenes": [
                    {
                        "title": "Explain",
                        "vietnamese_description": "Giải thích ý chính.",
                        "voiceover_text": "This explains the idea clearly for the viewer.",
                        **_scene_detail_fields(),
                        "target_duration_seconds": 3,
                    }
                ],
            }
        )

    monkeypatch.setattr(ai_planning, "run_codex_exec", fake_run)
    assert video_phase2.develop_story(project.id, db, force=True) is not None
    assert "video_purpose=educational_explainer" in captured_prompt["text"]
    assert "dialogue_mode=mixed" in captured_prompt["text"]
    assert "Video language: English" in captured_prompt["text"]
    assert "thoại/narration phải rõ nghĩa" in captured_prompt["text"]

def test_series_context_reaches_story_shots_and_prompt_pack(db, monkeypatch):
    captured_prompts = {"story": [], "shots": [], "prompts": []}

    def fake_run(settings, prompt, *, output_schema, timeout_seconds=None, cwd=None):
        if output_schema == video_phase2.STORY_DEVELOPMENT_SCHEMA:
            captured_prompts["story"].append(prompt)
            return json.dumps(
                {
                    "input_synthesis": "A consistent hero episode.",
                    "story_strategy": "Open with the hero following one clear clue, then pay it off.",
                    "continuity_bible": "Same hero, same city, same minimal cinematic style.",
                    "detailed_script": "The hero follows the clue and finds a new door.",
                    **_creative_direction_fields(),
                    "scenes": [
                        {
                            "title": "Clue route",
                            "vietnamese_description": "Người hùng đi theo manh mối trong thành phố đêm.",
                            "english_narration": "He followed the clue through the quiet city and found the next door.",
                            **_scene_detail_fields(),
                            "target_duration_seconds": 3,
                        }
                    ],
                }
            )
        if output_schema == video_phase2.SHOT_BREAKDOWN_SCHEMA:
            captured_prompts["shots"].append(prompt)
            return json.dumps(
                {
                    "shots": [
                        {
                            "scene_order": 1,
                            "shot_order": 1,
                            "duration_seconds": 3,
                            "vietnamese_description": "Người hùng bước qua con phố đêm và nhìn thấy cánh cửa mới.",
                            "english_narration": "He found the door that changed the route.",
                            "primary_action": "The hero walks through the city and stops at a door.",
                            "purpose": "Pay off the clue.",
                            "shot_type": "wide",
                            "camera_angle": "eye level",
                            "framing": "full body in a quiet street",
                            "composition": "hero centered with the door glowing ahead",
                            "camera_motion": "slow push-in",
                            "subject_motion": "the hero walks and stops",
                            "environment_motion": "soft city lights flicker",
                            "transition_to_next": "final hold on the door",
                            **_shot_creative_fields(final=True, role="payoff"),
                        }
                    ]
                }
            )
        if output_schema == video_phase2.VIDEO_PROMPT_PACK_SCHEMA:
            captured_prompts["prompts"].append(prompt)
            return json.dumps(
                {
                    "global_continuity": "Same hero, same city, same minimal cinematic style.",
                    "negative_prompt_global": "No watermark, no subtitles, no extra main character.",
                    "prompts": [
                        {
                            "shot_order": 1,
                            "prompt": "Create a 3-second 9:16 cinematic video of the same hero walking through a quiet city street toward a glowing door.",
                            "prompt_explanation_vi": "Prompt giữ cùng nhân vật, thành phố và style khi người hùng đi tới cánh cửa phát sáng.",
                            "negative_prompt": "No watermark, no subtitles, no extra main character.",
                            "duration_seconds": 3,
                            "aspect_ratio": "9:16",
                            "shot_type": "wide",
                            "camera_angle": "eye level",
                            "framing": "full body in a quiet street",
                            "composition": "hero centered with the door glowing ahead",
                            "camera_motion": "slow push-in",
                            "subject_motion": "the hero walks and stops",
                            "environment_motion": "soft city lights flicker",
                            "start_frame": "the hero enters the street",
                            "end_frame": "the hero stops at the glowing door",
                            "lighting": "soft cinematic night lighting",
                            "mood": "mysterious and hopeful",
                            "continuity_notes": "Keep the same hero, city and style.",
                            **_prompt_creative_fields(),
                        }
                    ],
                }
            )
        raise AssertionError("unexpected schema")

    monkeypatch.setattr(ai_planning, "run_codex_exec", fake_run)

    standalone = video_projects.create_project(models.VideoProjectCreate(topic="Standalone context capture", phase="phase2"), db)
    assert video_phase2.develop_story(standalone.id, db, force=True) is not None
    assert video_phase2.approve_story(standalone.id, True, db) is not None
    assert video_phase2.generate_shots(standalone.id, db) is not None
    assert video_phase2.generate_video_prompt_pack(standalone.id, db) is not None

    series = video_projects.create_series(
        models.VideoSeriesCreate(
            title="Continuity Series",
            character_bible="Hero keeps the same round head and black stick body.",
            world_bible="Same quiet city at night.",
            style_bible="Minimal cinematic monochrome.",
            continuity_rules="Preserve character and world.",
            negative_rules="Do not add a second hero.",
            previous_episode_summary="The hero learned the city layout.",
        ),
        db,
    )
    episode = video_projects.create_episode(series.id, models.VideoEpisodeCreate(topic="Series context capture"), db)
    assert episode is not None
    assert video_phase2.develop_story(episode.id, db, force=True) is not None
    assert video_phase2.approve_story(episode.id, True, db) is not None
    assert video_phase2.generate_shots(episode.id, db) is not None
    assert video_phase2.generate_video_prompt_pack(episode.id, db) is not None

    for prompts in captured_prompts.values():
        assert len(prompts) == 2
        assert "Series context:" not in prompts[0]
        assert "Series context:" in prompts[1]
        assert "Continuity Series" in prompts[1]
        assert "same round head" in prompts[1]
        assert "Same quiet city" in prompts[1]
        assert "Minimal cinematic" in prompts[1]

def test_delete_source_block_reorders_marks_stale_and_requires_last_confirm(db):
    project = video_projects.create_project(
        models.VideoProjectCreate(
            topic="Source deletion",
            phase="phase2",
            source_blocks=[
                models.VideoSourceBlockDraft(block_type="idea", content="One"),
                models.VideoSourceBlockDraft(block_type="rough_script", content="Two"),
                models.VideoSourceBlockDraft(block_type="style_notes", content="Three"),
            ],
        ),
        db,
    )
    shot = _add_phase2_shot(db, project.id, order=1, narration="A line")
    blocks = video_phase2.list_source_blocks(project.id, db)
    assert blocks is not None and len(blocks) == 3

    assert video_phase2.delete_source_block(project.id, blocks[1].id, db) is True
    remaining = video_phase2.list_source_blocks(project.id, db)
    assert remaining is not None
    assert [block.sort_order for block in remaining] == [1, 2]
    stale_project = db.get(DBVideoProject, project.id)
    stale_shot = db.get(DBVideoShot, shot.id)
    assert stale_project.planning_status == "stale"
    assert stale_shot.prompt_status == "stale"

    assert video_phase2.delete_source_block(project.id, remaining[0].id, db) is True
    last = video_phase2.list_source_blocks(project.id, db)
    assert last is not None and len(last) == 1
    with pytest.raises(ValueError):
        video_phase2.delete_source_block(project.id, last[0].id, db)
    assert video_phase2.delete_source_block(project.id, last[0].id, db, confirm_delete_last=True) is True

def test_reset_generated_data_keeps_source_config_and_series_link(db):
    series = video_projects.create_series(models.VideoSeriesCreate(title="Reset Series"), db)
    project = video_projects.create_episode(
        series.id,
        models.VideoEpisodeCreate(
            topic="Reset episode",
            target_language="vi",
            prompt_segment_count=2,
            prompt_segment_duration_seconds=8,
            micro_scenes_per_prompt=2,
            voice_profile_id="voice-1",
        ),
        db,
    )
    assert project is not None
    row = db.get(DBVideoProject, project.id)
    row.creative_brief = "brief"
    row.script_text = "script"
    row.story_strategy = "strategy"
    row.continuity_bible = "continuity"
    row.detailed_script = "details"
    row.story_approved = True
    row.script_approved = True
    row.status = "prompts_ready"
    row.planning_status = "prompts_ready"
    scene = DBVideoScenePrompt(project_id=project.id, scene_id="scene-1", main_prompt="prompt")
    db.add(scene)
    shot = _add_phase2_shot(db, project.id, order=1, narration="Narration", voice_completed=True, audio_duration=2.0)
    prompt_path = video_storage.get_project_subdir(project.id, "video_prompts") / "old-prompt.txt"
    prompt_path.write_text("old prompt", encoding="utf-8")
    db.add(DBVideoShotPrompt(project_id=project.id, shot_id=shot.id, version=1, prompt="old", prompt_path=video_storage.to_artifact_storage_path(prompt_path)))
    subtitle_path = video_storage.get_project_subdir(project.id, "subtitles") / "old.srt"
    subtitle_path.write_text("1\n", encoding="utf-8")
    db.add(DBVideoSubtitle(project_id=project.id, status="completed", subtitle_path=video_storage.to_artifact_storage_path(subtitle_path)))
    manifest_path = video_storage.get_project_subdir(project.id, "manifests") / "manifest.json"
    zip_path = video_storage.get_project_subdir(project.id, "exports") / "export.zip"
    manifest_path.write_text("{}", encoding="utf-8")
    zip_path.write_bytes(b"zip")
    db.add(DBVideoPackageExport(project_id=project.id, status="completed", manifest_path=video_storage.to_artifact_storage_path(manifest_path), zip_path=video_storage.to_artifact_storage_path(zip_path)))
    render_path = video_storage.get_project_subdir(project.id, "render_outputs") / "render.mp4"
    render_path.write_bytes(b"mp4")
    db.add(DBVideoRenderJob(project_id=project.id, status="completed", output_path=video_storage.to_artifact_storage_path(render_path)))
    db.add(DBVideoAutoRun(project_id=project.id, status="failed", current_step="generate_prompts"))
    video_observability.log_event(db, step_name="before_reset", status="info", project_id=project.id, message="before")
    db.commit()

    result = video_projects.reset_generated_data(project.id, db)
    assert result is not None
    assert result.deleted_counts["shots"] == 1
    refreshed = video_projects.get_project(project.id, db)
    assert refreshed is not None
    assert refreshed.series_id == series.id
    assert refreshed.source_blocks
    assert refreshed.target_language == "vi"
    assert refreshed.voice_profile_id == "voice-1"
    assert refreshed.prompt_segment_count == 2
    assert refreshed.scenes == []
    assert refreshed.shots == []
    assert refreshed.story_strategy is None
    assert db.query(DBVideoShotPrompt).filter(DBVideoShotPrompt.project_id == project.id).count() == 0
    assert db.query(DBVideoSubtitle).filter(DBVideoSubtitle.project_id == project.id).count() == 0
    assert db.query(DBVideoPackageExport).filter(DBVideoPackageExport.project_id == project.id).count() == 0
    assert db.query(DBVideoRenderJob).filter(DBVideoRenderJob.project_id == project.id).count() == 0
    assert db.query(DBVideoAutoRun).filter(DBVideoAutoRun.project_id == project.id).count() == 0
    assert not prompt_path.exists()
    assert db.query(DBVideoDebugEvent).filter(DBVideoDebugEvent.project_id == project.id).count() == 1

def test_delete_reset_block_active_auto_run_planning_voice_and_render(db):
    project = video_projects.create_project(models.VideoProjectCreate(topic="Guarded delete", phase="phase2"), db)
    run = DBVideoAutoRun(project_id=project.id, status="running", current_step="develop_story")
    db.add(run)
    db.commit()
    with pytest.raises(video_projects.VideoProjectOperationError):
        video_projects.reset_generated_data(project.id, db)
    run.status = "cancelled"
    db.commit()

    with video_planning_pool.planning_slot(db, project_id=project.id, step_name="test_guard"):
        with pytest.raises(video_projects.VideoProjectOperationError):
            video_projects.delete_project(project.id, db)

    shot = _add_phase2_shot(db, project.id, order=1, narration="Voice")
    shot.voice_status = "generating"
    db.commit()
    with pytest.raises(video_projects.VideoProjectOperationError):
        video_projects.reset_generated_data(project.id, db)
    shot.voice_status = "missing"
    db.add(DBVideoRenderJob(project_id=project.id, status="queued"))
    db.commit()
    with pytest.raises(video_projects.VideoProjectOperationError):
        video_projects.delete_project(project.id, db)

def test_codex_planning_persists_script_scene_regenerate_and_prompts(db, monkeypatch):
    project = video_projects.create_project(
        models.VideoProjectCreate(topic="Video về cách pha trà", language="vi", aspect_ratio="9:16"),
        db,
    )

    def fake_run(settings, prompt, *, output_schema, timeout_seconds=None, cwd=None):
        if output_schema == video_planning.PROJECT_PLAN_SCHEMA:
            return json.dumps(
                {
                    "creative_brief": "Video nhẹ nhàng cho người mới pha trà.",
                    "script_text": "Cảnh 1: Chào mừng.",
                    "style_bible": "soft morning light",
                    "character_bible": "same narrator mood",
                    "scenes": [
                        {
                            "title": "Mở đầu",
                            "dialogue": "Hôm nay ta pha một ấm trà thật dễ.",
                            "visual_description": "Ấm trà trên bàn gỗ buổi sáng.",
                            "target_duration_seconds": 6,
                        }
                    ],
                }
            )
        if output_schema == video_planning.SCENE_PLAN_SCHEMA:
            return json.dumps(
                {
                    "title": "Mở đầu mới",
                    "dialogue": "Bắt đầu với nước nóng và một chút kiên nhẫn.",
                    "visual_description": "Hơi nước bay nhẹ cạnh ấm trà.",
                    "target_duration_seconds": 7,
                }
            )
        return json.dumps(
            {
                "style_bible": "soft morning light, warm wood, calm editorial frame",
                "character_bible": "consistent hands, no face, same tea set",
                "prompts": [
                    {
                        "scene_order": 1,
                        "main_prompt": "A warm editorial photo of a tea pot on a wooden table, soft morning light",
                        "negative_prompt": "blurry, distorted hands",
                        "style_notes": "calm, natural light",
                        "character_notes": "same tea set and hands across scenes",
                    }
                ],
            }
        )

    monkeypatch.setattr(ai_planning, "run_codex_exec", fake_run)

    planned = video_planning.generate_project_plan(project.id, db)
    assert planned is not None
    assert planned.creative_brief == "Video nhẹ nhàng cho người mới pha trà."
    assert len(planned.scenes) == 1
    assert planned.scenes[0].dialogue == "Hôm nay ta pha một ấm trà thật dễ."

    regenerated = video_planning.regenerate_scene(project.id, planned.scenes[0].id, db)
    assert regenerated is not None
    assert regenerated.title == "Mở đầu mới"
    assert regenerated.prompt_status == "stale"

    approved_scene = video_projects.set_scene_approved(project.id, regenerated.id, True, db)
    assert approved_scene is not None

    pack = video_planning.generate_prompt_pack(project.id, db)
    assert pack is not None
    assert len(pack.prompts) == 1
    assert pack.prompts[0].main_prompt.startswith("A warm editorial photo")
    prompt_path = video_storage.resolve_artifact_storage_path(pack.prompts[0].prompt_path)
    assert prompt_path is not None
    assert prompt_path.exists()
    assert "Negative prompt" in prompt_path.read_text(encoding="utf-8")

    content = video_assets.get_prompt_content(project.id, regenerated.id, db)
    assert content is not None
    assert content.filename == "Prompt ảnh - Cảnh 01.txt"
    assert "A warm editorial photo" in content.content
    assert video_assets.get_prompt_download(project.id, regenerated.id, db) == (content.filename, content.content)
    pack_filename, pack_content = video_assets.get_prompt_pack_download(project.id, db)
    assert pack_filename == "Prompt ảnh - Video về cách pha trà.txt"
    assert "# Cảnh 01" in pack_content
    assert "A warm editorial photo" in pack_content

    image = Image.new("RGB", (8, 8), color=(240, 220, 180))
    image_bytes = io.BytesIO()
    image.save(image_bytes, format="PNG")

    first_asset = video_assets.upload_preview_image(
        project.id,
        regenerated.id,
        filename="ảnh trà.png",
        content_type="image/png",
        data=image_bytes.getvalue(),
        db=db,
    )
    assert first_asset is not None
    assert first_asset.is_active is True
    assert video_assets.resolve_asset_file(video_assets.get_preview_asset(first_asset.id, db)).exists()

    second_asset = video_assets.upload_preview_image(
        project.id,
        regenerated.id,
        filename="ảnh trà 2.png",
        content_type="image/png",
        data=image_bytes.getvalue(),
        db=db,
    )
    assert second_asset is not None
    active_asset = video_assets.get_active_preview_asset(project.id, regenerated.id, db)
    assert active_asset is not None
    assert active_asset.id == second_asset.id

def test_codex_planning_invalid_output_is_rejected(db, monkeypatch):
    project = video_projects.create_project(models.VideoProjectCreate(topic="Video lỗi"), db)

    def fake_run(settings, prompt, *, output_schema, timeout_seconds=None, cwd=None):
        return json.dumps({"creative_brief": "thiếu scenes"})

    monkeypatch.setattr(ai_planning, "run_codex_exec", fake_run)

    with pytest.raises(video_planning.VideoPlanningValidationError):
        video_planning.generate_project_plan(project.id, db)

def test_vietnamese_download_filenames_are_sanitized():
    assert video_storage.prompt_filename(1) == "Prompt ảnh - Cảnh 01.txt"
    assert video_storage.voice_filename(2) == "Giọng đọc - Cảnh 02.wav"
    assert video_storage.shot_voice_filename(None, 3) == "Giọng đọc - Shot 03.wav"
    assert video_storage.shot_voice_filename(2, 3) == "Giọng đọc - Cảnh 02 - Shot 03.wav"
    assert video_storage.subtitle_filename("Dự án: test / nhanh") == "Phụ đề - Dự án test nhanh.srt"
    assert video_storage.package_filename("Video cà phê") == "Bộ nguyên liệu - Video cà phê.zip"
    assert video_storage.shot_clip_filename(2, 3) == "Video clip - Cảnh 02 - Shot 03.mp4"
    assert video_storage.render_output_filename("Dự án: test / nhanh") == "Video hoàn chỉnh - Dự án test nhanh.mp4"

def test_render_ffprobe_parser_and_missing_tools(tmp_path, monkeypatch):
    clip_path = tmp_path / "clip.mp4"
    clip_path.write_bytes(b"fake video")
    payload = {
        "streams": [
            {
                "codec_type": "video",
                "duration": "2.500000",
                "width": 1080,
                "height": 1920,
                "avg_frame_rate": "30000/1001",
                "codec_name": "h264",
            },
            {"codec_type": "audio", "codec_name": "aac"},
        ],
        "format": {"duration": "2.500000"},
    }

    def fake_run(args, *, capture_output, text, timeout, check):
        assert args[0] == "ffprobe-bin"
        return subprocess.CompletedProcess(args, 0, stdout=json.dumps(payload), stderr="")

    monkeypatch.setattr(video_rendering.subprocess, "run", fake_run)

    ffmpeg_bin = tmp_path / "ffmpeg"
    ffprobe_bin = tmp_path / "ffprobe"
    ffmpeg_bin.write_text("", encoding="utf-8")
    ffprobe_bin.write_text("", encoding="utf-8")
    monkeypatch.setenv("VOICEBOX_FFMPEG_PATH", str(ffmpeg_bin))
    monkeypatch.setenv("VOICEBOX_FFPROBE_PATH", str(ffprobe_bin))
    monkeypatch.setattr(video_rendering.shutil, "which", lambda binary: None)

    tools = video_rendering.detect_tools()
    assert tools.ffmpeg == str(ffmpeg_bin)
    assert tools.ffprobe == str(ffprobe_bin)

    metadata = video_rendering.probe_clip(clip_path, ffprobe_path="ffprobe-bin")

    assert metadata.duration_seconds == pytest.approx(2.5)
    assert metadata.width == 1080
    assert metadata.height == 1920
    assert metadata.fps == pytest.approx(29.97, rel=0.001)
    assert metadata.codec == "h264"
    assert metadata.has_audio is True

    monkeypatch.setattr(video_rendering, "detect_tools", lambda: video_rendering.FFmpegTools(ffmpeg=None, ffprobe=None))
    with pytest.raises(video_rendering.VideoRenderError) as exc_info:
        video_rendering.probe_clip(clip_path)
    assert exc_info.value.error_code == "VIDEO_RENDER_FFPROBE_MISSING"
    assert "FFprobe" in str(exc_info.value)

def test_render_prefers_subtitle_capable_ffmpeg(tmp_path, monkeypatch):
    plain_ffmpeg = tmp_path / "ffmpeg"
    full_ffmpeg = tmp_path / "ffmpeg-full"
    plain_ffmpeg.write_text("", encoding="utf-8")
    full_ffmpeg.write_text("", encoding="utf-8")

    def fake_filter_names(ffmpeg):
        return frozenset({"subtitles"}) if ffmpeg == str(full_ffmpeg) else frozenset()

    monkeypatch.setattr(video_rendering, "_ffmpeg_filter_names", fake_filter_names)

    selected = video_rendering._select_preferred_ffmpeg([str(plain_ffmpeg), str(full_ffmpeg)])

    assert selected == str(full_ffmpeg)

def test_render_clip_upload_replace_delete_and_serialization(db, monkeypatch):
    project = video_projects.create_project(models.VideoProjectCreate(topic="Render clip", phase="phase2"), db)
    shot = _add_phase2_shot(db, project.id, order=1, narration="A clear line.", voice_completed=True, audio_duration=2.0)

    monkeypatch.setattr(
        video_rendering,
        "probe_clip",
        lambda path: video_rendering.ClipMetadata(
            duration_seconds=2.2,
            width=1080,
            height=1920,
            fps=30,
            codec="h264",
            has_audio=True,
        ),
    )

    first = video_rendering.upload_shot_clip(
        project.id,
        shot.id,
        filename="cảnh đầu.mp4",
        content_type="video/mp4",
        data=b"first clip",
        db=db,
    )
    second = video_rendering.upload_shot_clip(
        project.id,
        shot.id,
        filename="cảnh đầu mới.mp4",
        content_type="video/mp4",
        data=b"second clip",
        db=db,
    )

    assert first is not None
    assert second is not None
    assert first.id != second.id
    assert second.status == "ready"
    assert second.has_audio is True
    assert models.VideoShotClipResponse.model_validate(db.get(DBVideoShotClip, second.id)).id == second.id
    assert db.get(DBVideoShotClip, first.id).is_active is False
    assert db.get(DBVideoShotClip, second.id).is_active is True

    old_clip_path = video_storage.resolve_artifact_storage_path(first.file_path)
    assert old_clip_path is not None
    assert old_clip_path.exists()

    render_job = DBVideoRenderJob(project_id=project.id, status="completed", progress=1.0, stale=False)
    db.add(render_job)
    db.commit()
    assert models.VideoRenderJobResponse.model_validate(render_job).status == "completed"

    deleted = video_rendering.delete_shot_clip(project.id, shot.id, db)

    assert deleted is True
    assert db.get(DBVideoShotClip, second.id).is_active is False
    assert db.get(DBVideoRenderJob, render_job.id).stale is True
    deleted_path = video_storage.resolve_artifact_storage_path(second.file_path)
    assert deleted_path is None or not deleted_path.exists()

def test_render_empty_state_endpoints_return_null_without_404(db):
    app = FastAPI()
    app.include_router(ai_video_router)
    from backend.database import get_db

    app.dependency_overrides[get_db] = lambda: db
    client = TestClient(app)
    project = video_projects.create_project(models.VideoProjectCreate(topic="Render empty state", phase="phase2"), db)
    shot = _add_phase2_shot(db, project.id, order=1, narration="A clear line.", duration_seconds=2.0)

    latest = client.get(f"/ai-video/projects/{project.id}/render/jobs/latest")
    assert latest.status_code == 200
    assert latest.json() is None

    clip = client.get(f"/ai-video/projects/{project.id}/shots/{shot.id}/clip")
    assert clip.status_code == 200
    assert clip.json() is None

    missing_shot = client.get(f"/ai-video/projects/{project.id}/shots/not-a-shot/clip")
    assert missing_shot.status_code == 404
    assert missing_shot.json()["detail"]["error_code"] == "VIDEO_SHOT_NOT_FOUND"

def test_render_readiness_duration_resolver_and_timeline_manifest(db, monkeypatch):
    monkeypatch.setattr(video_rendering, "detect_tools", lambda: video_rendering.FFmpegTools(ffmpeg="ffmpeg", ffprobe="ffprobe"))
    monkeypatch.setattr(video_rendering, "_select_subtitle_filter", lambda ffmpeg: "subtitles")

    incomplete = video_projects.create_project(models.VideoProjectCreate(topic="Render missing", phase="phase2"), db)
    missing_voice = _add_phase2_shot(db, incomplete.id, order=1, narration="Needs voice.", voice_completed=False)
    missing_timer = _add_phase2_shot(db, incomplete.id, order=2, narration="", duration_seconds=None)

    not_ready = video_rendering.get_render_readiness(incomplete.id, db, models.VideoRenderSettings())

    assert not_ready is not None
    assert not_ready.ready is False
    assert set(not_ready.missing_clip_shot_ids) == {missing_voice.id, missing_timer.id}
    assert not_ready.missing_voice_shot_ids == [missing_voice.id]
    assert set(not_ready.missing_timer_shot_ids) == {missing_voice.id, missing_timer.id}
    assert not_ready.missing_subtitle is True

    project = video_projects.create_project(models.VideoProjectCreate(topic="Render ready", phase="phase2", aspect_ratio="9:16"), db)
    narrated = _add_phase2_shot(
        db,
        project.id,
        order=1,
        narration="Voice duration should win.",
        duration_seconds=9.0,
        voice_completed=True,
        audio_duration=2.5,
    )
    silent = _add_phase2_shot(db, project.id, order=2, narration="", duration_seconds=1.25)
    narrated.retention_json = {"retention_role": "cold open", "visual_surprise": "rain reveal"}
    narrated.transition_json = {"transition_type": "match cut", "transition_sfx": "short whoosh"}
    narrated.sound_design_json = {"sound_cues": [{"cue_type": "riser", "timing": "before cut"}], "mixing_notes": "voice above SFX"}
    narrated.retainability_quality_check = {"passed": True, "missing_fields": []}
    _add_ready_clip(db, project.id, narrated.id, duration_seconds=4.2)
    _add_ready_clip(db, project.id, silent.id, duration_seconds=1.25)
    db.add(
        DBVideoSubtitle(
            project_id=project.id,
            status="completed",
            cues_json=json.dumps([
                {"start_seconds": 0, "end_seconds": 2.5, "text": "Voice duration should win."},
                {"start_seconds": 2.5, "end_seconds": 3.75, "text": "Silent beat."},
            ]),
        )
    )
    db.commit()

    ready = video_rendering.get_render_readiness(project.id, db, models.VideoRenderSettings())
    timeline = video_rendering.build_timeline_manifest(project.id, db)

    assert ready is not None
    assert ready.ready is True
    assert ready.missing_reasons == []
    assert any(warning.code == "VIDEO_RENDER_SOUND_DESIGN_METADATA_ONLY" for warning in ready.warnings)
    assert any(warning.shot_id == narrated.id for warning in ready.warnings)
    assert video_rendering.resolve_shot_duration(narrated) == pytest.approx(2.5)
    assert video_rendering.resolve_shot_duration(silent) == pytest.approx(1.25)
    assert [(item.start_seconds, item.end_seconds) for item in timeline] == [(0.0, 2.5), (2.5, 3.75)]
    assert timeline[0].has_narration is True
    assert timeline[0].retention["retention_role"] == "cold open"
    assert timeline[0].transition["transition_type"] == "match cut"
    assert timeline[0].sound_design["sound_cues"][0]["cue_type"] == "riser"
    assert timeline[1].has_narration is False

def test_render_readiness_flags_missing_burn_in_filter(db, monkeypatch):
    monkeypatch.setattr(video_rendering, "detect_tools", lambda: video_rendering.FFmpegTools(ffmpeg="ffmpeg", ffprobe="ffprobe"))
    monkeypatch.setattr(video_rendering, "_select_subtitle_filter", lambda ffmpeg: None)
    project = video_projects.create_project(models.VideoProjectCreate(topic="Render filter", phase="phase2"), db)
    shot = _add_phase2_shot(db, project.id, order=1, narration="", duration_seconds=1.0)
    _add_ready_clip(db, project.id, shot.id, duration_seconds=1.0)
    db.add(
        DBVideoSubtitle(
            project_id=project.id,
            status="completed",
            cues_json=json.dumps([{"start_seconds": 0, "end_seconds": 1.0, "text": "Caption."}]),
        )
    )
    db.commit()

    burn_in = video_rendering.get_render_readiness(project.id, db, models.VideoRenderSettings(subtitle_mode="burn_in"))
    sidecar = video_rendering.get_render_readiness(project.id, db, models.VideoRenderSettings(subtitle_mode="sidecar"))

    assert burn_in is not None
    assert burn_in.ready is False
    assert any("filter burn-in phụ đề" in reason for reason in burn_in.missing_reasons)
    assert sidecar is not None
    assert sidecar.ready is True

def test_render_ffmpeg_command_builders_include_expected_filters(tmp_path):
    crop_cmd = video_rendering.build_normalize_clip_command(
        ffmpeg="ffmpeg",
        input_path=tmp_path / "in.mp4",
        output_path=tmp_path / "out.mp4",
        target_duration=3.0,
        clip_duration=1.0,
        width=1080,
        height=1920,
        fps=30,
        fit_mode="crop",
        background_color="#111827",
        freeze_short_clip=True,
    )
    crop_filter = crop_cmd[crop_cmd.index("-vf") + 1]
    assert "scale=1080:1920:force_original_aspect_ratio=increase" in crop_filter
    assert "crop=1080:1920" in crop_filter
    assert "tpad=stop_mode=clone:stop_duration=2.000" in crop_filter
    assert "trim=duration=3.000" in crop_filter
    assert "-an" in crop_cmd

    pad_cmd = video_rendering.build_normalize_clip_command(
        ffmpeg="ffmpeg",
        input_path=tmp_path / "in.mp4",
        output_path=tmp_path / "out-pad.mp4",
        target_duration=2.0,
        clip_duration=5.0,
        width=1920,
        height=1080,
        fps=24,
        fit_mode="pad",
        background_color="#101010",
        freeze_short_clip=False,
    )
    pad_filter = pad_cmd[pad_cmd.index("-vf") + 1]
    assert "force_original_aspect_ratio=decrease" in pad_filter
    assert "pad=1920:1080" in pad_filter
    assert "tpad=" not in pad_filter
    assert "fps=24" in pad_filter

    ass_path = tmp_path / "sub titles.ass"
    burn_cmd = video_rendering.build_final_mux_command(
        ffmpeg="ffmpeg",
        video_path=tmp_path / "video.mp4",
        audio_path=tmp_path / "audio.wav",
        output_path=tmp_path / "final.mp4",
        subtitle_ass_path=ass_path,
    )
    sidecar_cmd = video_rendering.build_final_mux_command(
        ffmpeg="ffmpeg",
        video_path=tmp_path / "video.mp4",
        audio_path=tmp_path / "audio.wav",
        output_path=tmp_path / "final-sidecar.mp4",
    )
    assert "-vf" in burn_cmd
    assert any(part.startswith("subtitles=filename=") and "sub titles.ass" in part for part in burn_cmd)
    assert "libx264" in burn_cmd
    assert sidecar_cmd[sidecar_cmd.index("-c:v") + 1] == "copy"

def test_render_ass_subtitle_uses_social_caption_style(db, tmp_path):
    project = video_projects.create_project(models.VideoProjectCreate(topic="Styled subtitle", phase="phase2"), db)
    db.add(
        DBVideoSubtitle(
            project_id=project.id,
            status="completed",
            cues_json=json.dumps([
                {"start_seconds": 0, "end_seconds": 1.2, "text": "Dòng chữ đẹp"},
                {
                    "start_seconds": 1.2,
                    "end_seconds": 2.8,
                    "text": "Một dòng phụ đề dài cần tự xuống dòng trong khung dọc để không bị tràn",
                },
            ]),
        )
    )
    db.commit()

    ass_path = tmp_path / "styled.ass"
    video_rendering._write_ass_subtitle(project.id, ass_path, db, (1080, 1920))
    content = ass_path.read_text(encoding="utf-8")

    portrait_style = video_rendering._ass_caption_style((1080, 1920))
    landscape_style = video_rendering._ass_caption_style((1920, 1080))

    assert "Style: Default,Arial,49,&H0007D7F7,&H00FCFAF8" in content
    assert portrait_style["font_size"] < landscape_style["font_size"]
    assert portrait_style["max_line_chars"] < landscape_style["max_line_chars"]
    assert "&HA0271811" in content
    assert "{\\fad(110,110)\\blur0.35}{\\k" in content
    assert r"}Dòng\h{\k" in content
    assert r"\N{\k" in content

def test_render_job_api_lifecycle_and_download_missing_output(db, monkeypatch):
    app = FastAPI()
    app.include_router(ai_video_router)
    from backend.database import get_db

    app.dependency_overrides[get_db] = lambda: db
    client = TestClient(app)
    project = video_projects.create_project(models.VideoProjectCreate(topic="Render API", phase="phase2"), db)

    def fake_readiness(project_id, db_session, settings=None):
        return models.VideoRenderReadinessResponse(
            project_id=project_id,
            ready=True,
            ffmpeg_ready=True,
            ffprobe_ready=True,
        )

    def fake_background_task(coro):
        coro.close()

    monkeypatch.setattr(video_rendering, "get_render_readiness", fake_readiness)
    monkeypatch.setattr(video_rendering, "create_background_task", fake_background_task)

    created = client.post(
        f"/ai-video/projects/{project.id}/render/jobs",
        json={"settings": {"subtitle_mode": "sidecar", "fit_mode": "pad", "fps": 24}},
    )

    assert created.status_code == 200
    created_job = created.json()
    assert created_job["status"] == "queued"
    assert created_job["progress"] == 0.0
    assert video_rendering.sync_stale_running_jobs(db) == 1

    failed = client.get(f"/ai-video/projects/{project.id}/render/jobs/{created_job['id']}")
    assert failed.status_code == 200
    assert failed.json()["status"] == "failed"
    assert failed.json()["error_code"] == "VIDEO_RENDER_INTERRUPTED"

    output_path = video_storage.get_project_subdir(project.id, "render_outputs") / "api-output.mp4"
    job = DBVideoRenderJob(
        project_id=project.id,
        status="completed",
        progress=1.0,
        output_path=video_storage.to_artifact_storage_path(output_path),
    )
    db.add(job)
    db.commit()
    db.refresh(job)

    missing = client.get(f"/ai-video/projects/{project.id}/render/jobs/{job.id}/download")
    assert missing.status_code == 404
    assert missing.json()["detail"]["error_code"] == "VIDEO_RENDER_OUTPUT_NOT_FOUND"

    output_path.write_bytes(b"mp4 bytes")
    downloaded = client.get(f"/ai-video/projects/{project.id}/render/jobs/{job.id}/download")
    assert downloaded.status_code == 200
    assert downloaded.content == b"mp4 bytes"
    content_disposition = downloaded.headers["content-disposition"]
    assert "filename*=" in content_disposition
    assert "Render%20API.mp4" in content_disposition


def test_ai_video_error_response_has_code_and_request_id(db):
    app = FastAPI()
    app.include_router(ai_video_router)
    from backend.database import get_db

    app.dependency_overrides[get_db] = lambda: db
    client = TestClient(app)

    response = client.get("/ai-video/projects/missing-project/status", headers={"X-Request-ID": "test-request-1"})

    assert response.status_code == 404
    assert response.json()["detail"] == {
        "message": "Không tìm thấy dự án video.",
        "error_code": "VIDEO_PROJECT_NOT_FOUND",
        "request_id": "test-request-1",
    }

def test_ai_video_timeout_error_uses_friendly_message(db, monkeypatch):
    project = video_projects.create_project(
        models.VideoProjectCreate(
            topic="Video timeout",
            phase="phase2",
            source_blocks=[models.VideoSourceBlockDraft(block_type="idea", content="Tạo video dài cần nhiều chi tiết.")],
        ),
        db,
    )
    app = FastAPI()
    app.include_router(ai_video_router)
    from backend.database import get_db

    app.dependency_overrides[get_db] = lambda: db
    client = TestClient(app)

    calls = {"count": 0, "timeout_seconds": None}

    def fake_timeout(settings, prompt, *, output_schema, timeout_seconds=None, cwd=None):
        calls["count"] += 1
        calls["timeout_seconds"] = timeout_seconds
        raise ai_planning.AIPlanningError(
            "Codex CLI bị timeout khi tạo nội dung.",
            error_code="CODEX_EXEC_TIMEOUT",
        )

    monkeypatch.setattr(ai_planning, "run_codex_exec", fake_timeout)
    monkeypatch.setattr(video_phase2, "RETRY_DELAY_SECONDS", 0)

    response = client.post(
        f"/ai-video/projects/{project.id}/story",
        json={"force": True},
        headers={"X-Request-ID": "timeout-request-1"},
    )

    assert response.status_code == 502
    detail = response.json()["detail"]
    assert detail["error_code"] == "CODEX_EXEC_TIMEOUT"
    assert detail["request_id"] == "timeout-request-1"
    assert "AI xử lý quá lâu" in detail["message"]
    assert "Codex CLI" not in detail["message"]
    assert calls == {"count": 1, "timeout_seconds": video_phase2.PHASE2_DEFAULT_CODEX_TIMEOUT_SECONDS}

    events = video_observability.latest_events(project.id, db, limit=10)
    failure = next(event for event in events if event.step_name == "story_development" and event.status == "failure")
    details = json.loads(failure.technical_details or "{}")
    assert details["timeout_seconds"] == video_phase2.PHASE2_DEFAULT_CODEX_TIMEOUT_SECONDS
    assert details["prompt_chars"] > 0
    assert details["will_retry"] is False
    assert failure.error_code == "CODEX_EXEC_TIMEOUT"


def test_phase2_story_development_accepts_structured_text_fields(db, monkeypatch):
    project = video_projects.create_project(
        models.VideoProjectCreate(
            topic="Stickman hero story",
            phase="phase2",
            source_blocks=[models.VideoSourceBlockDraft(block_type="idea", content="A weak stickman trains to save the city.")],
        ),
        db,
    )

    def fake_run(settings, prompt, *, output_schema, timeout_seconds=None, cwd=None):
        assert output_schema == video_phase2.STORY_DEVELOPMENT_SCHEMA
        assert "story_strategy_vi" in prompt
        assert "continuity_bible_vi" in prompt
        assert "detailed_script_vi" in prompt
        assert "english_narration của mỗi scene phải là voiceover đủ dài" in prompt
        return json.dumps(
            {
                "input_synthesis": "A simple motivational stickman origin story.",
                "story_strategy_vi": "Chiến lược tiếng Việt: mở bằng sự chế giễu, tăng nhịp luyện tập, kết bằng chiến thắng.",
                "story_strategy": {
                    "core_premise": "A tiny stickman becomes a hero through discipline.",
                    "emotional_arc": ["Mocked", "Training", "Courage", "Victory"],
                },
                "continuity_bible_vi": "Nhân vật chính là người que nhỏ màu đen, tỷ lệ cơ thể giữ nguyên, bối cảnh tối giản.",
                "continuity_bible": {
                    "main_character": {
                        "appearance": "Small black stickman with round head.",
                        "must_remain_consistent": ["No clothes", "Same proportions"],
                    },
                    "camera_style": "Fast cinematic vertical cuts.",
                },
                "detailed_script_vi": "Cậu bị cười nhạo trong thành phố trắng, rồi luyện tập đến khi dáng đứng thay đổi.",
                "detailed_script": [
                    "He is laughed at in a white empty city.",
                    "He trains until his posture changes.",
                ],
                **_creative_direction_fields(),
                "scenes": [
                    {
                        "title": "The small dream",
                        "vietnamese_description": {"summary": "Người que nhỏ bị chê cười nhưng vẫn mơ làm anh hùng."},
                        "english_narration": "Everyone laughed at him, but he kept his dream alive.",
                        **_scene_detail_fields(
                            character_appearance={
                                "hair": "No hair, simple round head.",
                                "expression": "Determined eyes and a nervous half-smile.",
                            },
                            wardrobe_and_sandals={
                                "outfit": "Minimal black stickman body.",
                                "sandals": "Sandals not visible in this wide scene.",
                            },
                        ),
                        "target_duration_seconds": 6,
                    }
                ],
            }
        )

    monkeypatch.setattr(ai_planning, "run_codex_exec", fake_run)

    detail = video_phase2.develop_story(project.id, db, force=True)

    assert detail is not None
    assert "Bản tiếng Việt" in (detail.story_strategy or "")
    assert "Chiến lược tiếng Việt" in (detail.story_strategy or "")
    assert "Core premise" in (detail.story_strategy or "")
    assert "Emotional arc" in (detail.story_strategy or "")
    assert "Nhân vật chính" in (detail.continuity_bible or "")
    assert "Main character" in (detail.continuity_bible or "")
    assert "Cậu bị cười nhạo" in (detail.detailed_script or "")
    assert "He is laughed at" in (detail.detailed_script or "")
    assert detail.retention_plan_json is not None
    assert detail.retention_plan_json["hook_0_2s"].startswith("Cầu thủ nhỏ")
    assert detail.sound_design_plan_json is not None
    assert detail.sound_design_plan_json["mixing_notes"] == "Voice stays above music and SFX."
    assert detail.scenes[0].visual_description.startswith("Summary:")
    assert "Character appearance:" in detail.scenes[0].visual_description
    assert "Wardrobe and sandals:" in detail.scenes[0].visual_description
    assert "Subject motion by shot duration:" in detail.scenes[0].visual_description
    assert "Setting and lighting:" in detail.scenes[0].visual_description
    assert "Detailed emotion/mood:" in detail.scenes[0].visual_description

def test_scene_voice_status_syncs_from_existing_generation(db):
    project = video_projects.create_project(models.VideoProjectCreate(topic="Video voice", voice_profile_id="profile-1"), db)
    scenes = video_projects.replace_scenes(
        project.id,
        models.VideoScenesReplaceRequest(
            scenes=[models.VideoSceneDraft(dialogue="Hello everyone.", visual_description="A clean studio frame.")]
        ),
        db,
    )
    scene = scenes[0]
    generation_id = "generation-video-scene-1"
    audio_path = config.get_generations_dir() / f"{generation_id}.wav"
    audio_path.write_bytes(b"fake wav data")
    db.add(
        DBGeneration(
            id=generation_id,
            profile_id="profile-1",
            text="Hello everyone.",
            language="en",
            audio_path=config.to_storage_path(audio_path),
            duration=2.5,
            status="completed",
            source="ai_video_scene",
        )
    )
    row = database.VideoScene.__table__
    db.execute(
        row.update()
        .where(row.c.id == scene.id)
        .values(generation_id=generation_id, voice_status="generating")
    )
    db.commit()

    status = video_voice.sync_scene_voice_status(project.id, scene.id, db)

    assert status is not None
    assert status.voice_status == "completed"
    assert status.generation_id == generation_id
    assert status.audio_duration == 2.5
    assert status.audio_url == f"/audio/{generation_id}"
    download = video_voice.get_scene_audio_download(project.id, scene.id, db)
    assert download is not None
    assert download[0] == "Giọng đọc - Cảnh 01.wav"

def test_scene_voice_rejects_profile_language_mismatch(db):
    profile = DBVoiceProfile(
        id="english-profile",
        name="English profile",
        language="en",
        voice_type="cloned",
        default_engine="qwen",
    )
    db.add(profile)
    project = video_projects.create_project(
        models.VideoProjectCreate(
            topic="Video tiếng Việt",
            phase="phase2",
            target_language="vi",
            voice_profile_id=profile.id,
        ),
        db,
    )
    scene = video_projects.replace_scenes(
        project.id,
        models.VideoScenesReplaceRequest(
            scenes=[models.VideoSceneDraft(dialogue="Đây là lời tiếng Việt.", visual_description="Một cảnh đơn giản.")]
        ),
        db,
    )[0]

    with pytest.raises(video_voice.VideoVoiceError) as exc:
        asyncio.run(video_voice.create_scene_narration(project.id, scene.id, models.VideoSceneNarrationRequest(), db))

    assert exc.value.error_code == "VIDEO_VOICE_PROFILE_LANGUAGE_MISMATCH"
    assert db.query(DBGeneration).filter(DBGeneration.profile_id == profile.id).count() == 0

def test_shot_voice_vietnamese_profile_uses_qwen_1_7b_when_default_is_tada(db, monkeypatch):
    profile = DBVoiceProfile(
        id="legacy-tada-vi-profile",
        name="Legacy TADA Vietnamese profile",
        language="vi",
        voice_type="cloned",
        default_engine="tada",
    )
    db.add(profile)
    project = video_projects.create_project(
        models.VideoProjectCreate(
            topic="Video tiếng Việt bằng Qwen",
            phase="phase2",
            target_language="vi",
            voice_profile_id=profile.id,
        ),
        db,
    )
    shot = _add_phase2_shot(db, project.id, order=1, narration="Đây là lời thoại tiếng Việt.")
    enqueued: list[str] = []

    def fake_enqueue(generation_id, coro):
        enqueued.append(generation_id)
        close = getattr(coro, "close", None)
        if close:
            close()

    monkeypatch.setattr(video_voice, "enqueue_generation", fake_enqueue)

    status = asyncio.run(video_voice.create_shot_narration(project.id, shot.id, models.VideoSceneNarrationRequest(), db))

    assert status is not None
    assert status.voice_status == "generating"
    assert enqueued == [status.generation_id]
    generation = db.get(DBGeneration, status.generation_id)
    assert generation is not None
    assert generation.profile_id == profile.id
    assert generation.language == "vi"
    assert generation.engine == "qwen"
    assert generation.model_size == "1.7B"

def test_shot_voice_qwen_vietnamese_0_6b_request_uses_1_7b(db, monkeypatch):
    profile = DBVoiceProfile(
        id="qwen-vi-0-6b-profile",
        name="Qwen Vietnamese 0.6B profile",
        language="vi",
        voice_type="cloned",
        default_engine="qwen",
    )
    db.add(profile)
    project = video_projects.create_project(
        models.VideoProjectCreate(
            topic="Video tiếng Việt bằng Qwen 0.6B",
            phase="phase2",
            target_language="vi",
            voice_profile_id=profile.id,
        ),
        db,
    )
    shot = _add_phase2_shot(db, project.id, order=1, narration="Đây là lời thoại tiếng Việt.")
    enqueued: list[str] = []

    def fake_enqueue(generation_id, coro):
        enqueued.append(generation_id)
        close = getattr(coro, "close", None)
        if close:
            close()

    monkeypatch.setattr(video_voice, "enqueue_generation", fake_enqueue)

    status = asyncio.run(
        video_voice.create_shot_narration(
            project.id,
            shot.id,
            models.VideoSceneNarrationRequest(engine="qwen", model_size="0.6B"),
            db,
        )
    )

    assert enqueued == [status.generation_id]
    generation = db.get(DBGeneration, status.generation_id)
    assert generation is not None
    assert generation.engine == "qwen"
    assert generation.model_size == "1.7B"

def test_shot_voice_status_syncs_from_existing_generation(db):
    project = video_projects.create_project(
        models.VideoProjectCreate(topic="Video shot voice", phase="phase2", voice_profile_id="profile-1"),
        db,
    )
    shot = DBVideoShot(
        project_id=project.id,
        shot_order=1,
        english_narration="One tiny hero takes the first step.",
        status="ready",
        prompt_status="completed",
        voice_status="generating",
        subtitle_status="stale",
    )
    db.add(shot)
    db.commit()
    db.refresh(shot)

    generation_id = "generation-video-shot-1"
    audio_path = config.get_generations_dir() / f"{generation_id}.wav"
    audio_path.write_bytes(b"fake wav data")
    db.add(
        DBGeneration(
            id=generation_id,
            profile_id="profile-1",
            text="One tiny hero takes the first step.",
            language="en",
            audio_path=config.to_storage_path(audio_path),
            duration=1.8,
            status="completed",
            source="ai_video_shot",
        )
    )
    shot_table = database.VideoShot.__table__
    db.execute(shot_table.update().where(shot_table.c.id == shot.id).values(generation_id=generation_id))
    db.commit()

    status = video_voice.sync_shot_voice_status(project.id, shot.id, db)

    assert status is not None
    assert status.voice_status == "completed"
    assert status.generation_id == generation_id
    assert status.audio_duration == 1.8
    assert status.audio_url == f"/audio/{generation_id}"
    download = video_voice.get_shot_audio_download(project.id, shot.id, db)
    assert download is not None
    assert download[0] == "Giọng đọc - Shot 01.wav"

def test_phase2_subtitle_generation_uses_shot_audio_without_scenes(db):
    project = video_projects.create_project(
        models.VideoProjectCreate(topic="Video phase2 subtitle", phase="phase2", aspect_ratio="9:16"),
        db,
    )
    shot = DBVideoShot(
        project_id=project.id,
        shot_order=1,
        english_narration="He was small, but his dream was bigger than the city.",
        status="ready",
        prompt_status="completed",
        voice_status="missing",
        subtitle_status="stale",
    )
    db.add(shot)
    db.commit()
    db.refresh(shot)

    with pytest.raises(video_subtitles.VideoSubtitleError) as exc_info:
        video_subtitles.generate_subtitle(project.id, db)

    assert exc_info.value.error_code == "VIDEO_SUBTITLE_MISSING_NARRATION"
    assert "Shot 01" in str(exc_info.value)

    audio_path = config.get_generations_dir() / "phase2-shot-subtitle.wav"
    audio_path.write_bytes(b"fake wav data")
    shot_table = database.VideoShot.__table__
    db.execute(
        shot_table.update()
        .where(shot_table.c.id == shot.id)
        .values(voice_status="completed", audio_path=config.to_storage_path(audio_path), audio_duration=3.0)
    )
    db.commit()

    subtitle = video_subtitles.generate_subtitle(project.id, db)

    assert subtitle.status == "completed"
    assert subtitle.cues
    assert subtitle.cues[0].shot_id == shot.id
    assert subtitle.cues[-1].end_seconds == pytest.approx(3.0)


def test_subtitle_generation_uses_actual_audio_duration(db):
    project = video_projects.create_project(models.VideoProjectCreate(topic="Video subtitle", aspect_ratio="9:16"), db)
    scenes = video_projects.replace_scenes(
        project.id,
        models.VideoScenesReplaceRequest(
            scenes=[
                models.VideoSceneDraft(
                    dialogue="Hello everyone. This is a short test for subtitle timing.",
                    visual_description="Simple image.",
                )
            ]
        ),
        db,
    )
    scene = video_projects.set_scene_approved(project.id, scenes[0].id, True, db)
    audio_path = config.get_generations_dir() / "subtitle-scene.wav"
    audio_path.write_bytes(b"fake wav data")
    scene_table = database.VideoScene.__table__
    db.execute(
        scene_table.update()
        .where(scene_table.c.id == scene.id)
        .values(voice_status="completed", audio_path=config.to_storage_path(audio_path), audio_duration=4.0)
    )
    db.commit()

    subtitle = video_subtitles.generate_subtitle(project.id, db)

    assert subtitle.status == "completed"
    assert subtitle.cues
    assert subtitle.cues[-1].end_seconds == pytest.approx(4.0)
    filename, content = video_subtitles.get_subtitle_download(project.id, db)
    assert filename == "Phụ đề - Video subtitle.srt"
    assert "00:00:00,000 -->" in content


def test_subtitle_split_keeps_portrait_cues_shorter_than_landscape():
    text = (
        "Alpha beta gamma delta epsilon zeta eta theta iota kappa lambda mu nu xi "
        "omicron pi rho sigma tau upsilon phi chi psi omega"
    )

    portrait = video_subtitles._split_caption_text(text, aspect_ratio="9:16", duration=1.2)
    landscape = video_subtitles._split_caption_text(text, aspect_ratio="16:9", duration=10.0)

    assert len(portrait) > len(landscape)
    assert all(len(chunk) <= 34 for chunk in portrait)
    assert all(len(chunk) <= 68 for chunk in landscape)

def test_subtitle_chunk_durations_follow_caption_length():
    durations = video_subtitles._caption_chunk_durations(
        ["Short hook", "This longer caption should stay on screen for more of the voiceover"],
        6.0,
    )

    assert len(durations) == 2
    assert sum(durations) == pytest.approx(6.0)
    assert durations[1] > durations[0]

def test_package_readiness_zip_manifest_and_missing_artifacts(db):
    project = video_projects.create_project(
        models.VideoProjectCreate(
            topic="Video package",
            aspect_ratio="9:16",
            target_language="vi",
            video_purpose="sales_ad",
            dialogue_mode="mixed",
            narration_density="light",
        ),
        db,
    )
    scenes = video_projects.replace_scenes(
        project.id,
        models.VideoScenesReplaceRequest(
            scenes=[models.VideoSceneDraft(dialogue="Hello package.", visual_description="A package preview image.")]
        ),
        db,
    )
    scene = video_projects.set_scene_approved(project.id, scenes[0].id, True, db)
    not_ready = video_packages.get_package_readiness(project.id, db)
    assert not_ready.ready is False
    assert not_ready.language == "vi"
    assert not_ready.video_purpose == "sales_ad"
    assert not_ready.dialogue_mode == "mixed"
    assert not_ready.narration_density == "light"
    assert not_ready.missing_prompt_scene_ids == [scene.id]
    assert not_ready.missing_voice_scene_ids == [scene.id]
    assert not_ready.missing_subtitle is True

    prompt_path = video_storage.get_project_subdir(project.id, "prompts") / "scene-01-prompt.txt"
    prompt_path.write_text("A cinematic package prompt.\n", encoding="utf-8")
    db.add(
        DBVideoScenePrompt(
            project_id=project.id,
            scene_id=scene.id,
            version=1,
            main_prompt="A cinematic package prompt.",
            aspect_ratio="9:16",
            prompt_path=video_storage.to_artifact_storage_path(prompt_path),
        )
    )
    audio_path = config.get_generations_dir() / "package-scene.wav"
    audio_path.write_bytes(b"fake wav data")
    scene_table = database.VideoScene.__table__
    db.execute(
        scene_table.update()
        .where(scene_table.c.id == scene.id)
        .values(voice_status="completed", audio_path=config.to_storage_path(audio_path), audio_duration=2.0)
    )
    db.commit()
    video_subtitles.generate_subtitle(project.id, db)

    ready = video_packages.get_package_readiness(project.id, db)
    assert ready.ready is True

    package = video_packages.create_package(project.id, db)
    assert package is not None
    assert package.status == "completed"
    download = video_packages.get_package_download(project.id, db)
    assert download is not None
    filename, path = download
    assert filename == "Bộ nguyên liệu - Video package.zip"
    with zipfile.ZipFile(path) as archive:
        names = set(archive.namelist())
        manifest_name = next(name for name in names if name.endswith("Manifest - Video package.json"))
        manifest = json.loads(archive.read(manifest_name).decode("utf-8"))
    assert any(name.endswith("00 - Huong dan.txt") for name in names)
    assert any(name.endswith("Prompt ảnh - Cảnh 01.txt") for name in names)
    assert any(name.endswith("Giọng đọc - Cảnh 01.wav") for name in names)
    assert any(name.endswith("Phụ đề - Video package.srt") for name in names)
    assert any(name.endswith("Manifest - Video package.json") for name in names)
    assert manifest["language"] == "vi"
    assert manifest["video_purpose"] == "sales_ad"
    assert manifest["dialogue_mode"] == "mixed"
    assert manifest["narration_density"] == "light"

def test_phase2_shot_breakdown_accepts_common_alias_fields(db, monkeypatch):
    project = video_projects.create_project(
        models.VideoProjectCreate(
            topic="Stickman shot aliases",
            phase="phase2",
            source_blocks=[models.VideoSourceBlockDraft(block_type="idea", content="A stickman trains and saves the city.")],
        ),
        db,
    )
    second_shot_creative = _shot_creative_fields(final=True, role="payoff")
    second_shot_creative["sound_design"].pop("silence_drops")

    def fake_run(settings, prompt, *, output_schema, timeout_seconds=None, cwd=None):
        if output_schema == video_phase2.STORY_DEVELOPMENT_SCHEMA:
            return json.dumps(
                {
                    "input_synthesis": "Stickman origin story.",
                    "story_strategy": "Fast motivational arc.",
                    "continuity_bible": "Small black stickman remains visually consistent.",
                    "detailed_script": "He trains, faces fear, and wins.",
                    **_creative_direction_fields(),
                    "scenes": [
                        {
                            "title": "Training begins",
                            "vietnamese_description": "Người que bắt đầu luyện tập.",
                            "english_narration": "He chose to train every day.",
                            **_scene_detail_fields(),
                            "target_duration_seconds": 8,
                        }
                    ],
                }
            )
        if output_schema == video_phase2.SHOT_BREAKDOWN_SCHEMA:
            return json.dumps(
                {
                    "shots": [
                        {
                            "shot_number": 1,
                            "scene_number": 1,
                            "duration_seconds": 3,
                            "shot_type": "wide",
                            "camera_angle": "slightly high angle",
                            "framing": "The small stickman stands alone in a clean white training ground.",
                            "camera_movement": "slow push-in",
                            "main_action": "The stickman clenches his fists and starts running.",
                            "visual_prompt": "Wide minimalist stickman training shot, white background, high contrast.",
                            "english_narration": "He started small.",
                            "vietnamese_description": "Cảnh rộng cho thấy người que nhỏ bắt đầu luyện tập.",
                            "transition_to_next": "Whip pan into a close-up.",
                            "retention_role": "cold open",
                            "viewer_question": "Will the tiny runner keep going?",
                            "pattern_interrupt": "cut from wide frame to trembling arms",
                            "cut_reason": "cut on the first step",
                            "edit_transition": {
                                "type": "whip pan",
                                "trigger": "first step forward",
                                "timing": "last half second",
                                "reason": "increase momentum",
                                "sfx": "short whoosh",
                                "continuity_note": "same white training ground",
                            },
                            "sfx": [
                                {"type": "whoosh", "timing": "on whip pan", "purpose": "accent the cut", "mix_note": "below narration"}
                            ],
                            "sound_design": {
                                "music": "focused training pulse",
                                "audio_energy_curve": "small lift into the cut",
                                "ambience": "quiet white training ground",
                                "sfx": [
                                    {"type": "whoosh", "timing": "on whip pan", "purpose": "accent the cut", "mix_note": "below narration"}
                                ],
                                "silence_drop": "brief dip before the push-in",
                                "mix_notes": "Keep narration above the whoosh.",
                            },
                        },
                        {
                            "shot_number": 2,
                            "scene_number": 1,
                            "duration_seconds": "3 seconds",
                            "shot_type": "close-up",
                            "camera_angle": "ground level",
                            "framing": "Close on trembling arms during push-ups.",
                            "camera_movement": "tight handheld push-in",
                            "main_action": "The stickman collapses, then pushes himself up again.",
                            "visual_prompt": "Close-up minimalist action shot, consistent black stickman proportions.",
                            "english_narration": "But he stood up again.",
                            "vietnamese_description": "Cận cảnh thất bại đầu tiên nhưng cậu vẫn đứng dậy.",
                            "transition_to_next": "Match cut to the next exercise.",
                            **second_shot_creative,
                        },
                    ]
                }
            )
        raise AssertionError("unexpected schema")

    monkeypatch.setattr(ai_planning, "run_codex_exec", fake_run)

    story = video_phase2.develop_story(project.id, db, force=True)
    assert story is not None
    assert video_phase2.approve_story(project.id, True, db) is not None
    shots = video_phase2.generate_shots(project.id, db)

    assert shots is not None
    assert len(shots) == 2
    assert shots[0].scene_id is not None
    assert shots[0].primary_action == "The stickman clenches his fists and starts running."
    assert shots[0].camera_motion == "slow push-in"
    assert "Wide minimalist" in shots[0].composition
    assert shots[0].retention_json["retention_role"] == "cold open"
    assert shots[0].transition_json["transition_type"] == "whip pan"
    assert shots[0].sound_design_json["sound_cues"][0]["cue_type"] == "whoosh"
    assert shots[0].retainability_quality_check["passed"] is True
    assert shots[1].duration_seconds == pytest.approx(3)
    assert shots[1].sound_design_json["silence_drops"]
    warning = (
        db.query(DBVideoDebugEvent)
        .filter(
            DBVideoDebugEvent.project_id == project.id,
            DBVideoDebugEvent.step_name == "shot_breakdown_validation",
            DBVideoDebugEvent.error_code == "AI_VIDEO_MAPPING_FALLBACK_APPLIED",
        )
        .first()
    )
    assert warning is not None
    details = json.loads(warning.technical_details or "{}")
    assert details["fallback_fields"] == ["shots[2].sound_design.silence_drops"]

def test_phase2_retainability_quality_flags_static_and_audio_risks():
    shot = video_phase2.ShotPlan(
        scene_order=1,
        shot_order=1,
        duration_seconds=10,
        vietnamese_description="Một shot quá tĩnh cần quality gate cảnh báo.",
        english_narration="This narration must remain clear while the shot holds too long.",
        primary_action="The subject stands still.",
        shot_type="static hold",
        camera_angle="eye level",
        framing="medium frame",
        composition="centered static subject",
        camera_motion="static hold",
    )

    quality = video_phase2._shot_retainability_quality(shot, is_first=True, is_final=False)

    assert quality["passed"] is False
    assert "hook_0_2s" in quality["missing_fields"]
    assert "transition_type" in quality["missing_fields"]
    assert "sound_cues" in quality["missing_fields"]
    assert quality["weak_hook_risk"] is True
    assert quality["audio_clutter_risk"] is True
    assert quality["long_static_span_risk"] is True

def test_phase2_shot_breakdown_accepts_top_level_segments_payload(db, monkeypatch):
    project = video_projects.create_project(
        models.VideoProjectCreate(
            topic="World Cup prompt segments",
            phase="phase2",
            target_duration_seconds=20,
            source_blocks=[models.VideoSourceBlockDraft(block_type="idea", content="A small football player wins the final.")],
        ),
        db,
    )

    def fake_run(settings, prompt, *, output_schema, timeout_seconds=None, cwd=None):
        if output_schema == video_phase2.STORY_DEVELOPMENT_SCHEMA:
            return json.dumps(
                {
                    "input_synthesis": "A tiny footballer proves himself in the final.",
                    "story_strategy": "Open with doubt, build pressure, finish with the winning goal.",
                    "continuity_bible": "Same tiny player, same blue kit, same stadium floodlights.",
                    "detailed_script": "The smallest player trains, enters the final, and scores.",
                    **_creative_direction_fields(),
                    "scenes": [
                        {
                            "title": "Final night",
                            "vietnamese_description": "Cầu thủ nhỏ bước vào trận chung kết.",
                            "english_narration": "The smallest player steps into the final with the whole stadium watching.",
                            **_scene_detail_fields(),
                            "target_duration_seconds": 20,
                        }
                    ],
                }
            )
        if output_schema == video_phase2.SHOT_BREAKDOWN_SCHEMA:
            return json.dumps(
                {
                    "project_title": "World Cup prompt segments",
                    "target_language": "en",
                    "aspect_ratio": "9:16",
                    "total_duration_seconds": 20,
                    "prompt_mode": "10_second_segments",
                    "total_segments": 2,
                    "segments": [
                        {
                            "segment_order": 1,
                            "segment_duration_seconds": 10,
                            "segment_description_vi": "0-3s cầu thủ nhìn bảng tỷ số; 3-6s cậu siết dây giày; 6-10s cậu chạy vào sân.",
                            "voiceover_text": "Everyone saw only his size, but he carried the calm of someone who had practiced for this exact night.",
                            "segment_action": "The small player enters the final under pressure.",
                            "segment_purpose": "Hook with doubt and pressure.",
                            "segment_type": "opening segment",
                            "camera_angle": "child-height sideline angle",
                            "framing": "scoreboard close-up to medium player shot",
                            "visual_composition": "scoreboard high in frame, small player below stadium lights",
                            "camera_movement": "slow push-in then lateral track",
                            "subject_movement": "the player breathes, ties his boots, and runs forward",
                            "background_motion": "crowd flags ripple behind rain haze",
                            "next_transition": "match cut to the ball at midfield",
                            **_shot_creative_fields(role="cold open"),
                        },
                        {
                            "segment_order": 2,
                            "segment_duration_seconds": 10,
                            "segment_description_vi": "0-3s bóng lăn qua hàng thủ; 3-7s cầu thủ bứt tốc; 7-10s cậu sút vào góc lưới.",
                            "voiceover_text": "When the final chance arrived, he moved before fear could speak, and the whole stadium rose with the shot.",
                            "segment_action": "The small player breaks through and scores.",
                            "segment_purpose": "Pay off the comeback.",
                            "segment_type": "climax segment",
                            "camera_angle": "low goal-line angle",
                            "framing": "tracking shot into goal close-up",
                            "visual_composition": "ball foreground, player and goal framed by floodlights",
                            "camera_movement": "fast tracking move into a locked final hold",
                            "subject_movement": "the player sprints, shoots, and lands in disbelief",
                            "background_motion": "net snaps and crowd erupts",
                            "next_transition": "final hold on the net and scoreboard",
                            **_shot_creative_fields(final=True, role="payoff"),
                        },
                    ],
                }
            )
        raise AssertionError("unexpected schema")

    monkeypatch.setattr(ai_planning, "run_codex_exec", fake_run)

    story = video_phase2.develop_story(project.id, db, force=True)
    assert story is not None
    assert story.retention_plan_json is not None
    assert max(beat["end_seconds"] for beat in story.retention_plan_json["beat_curve"] if beat.get("end_seconds")) <= project.target_duration_seconds
    assert video_phase2.approve_story(project.id, True, db) is not None
    shots = video_phase2.generate_shots(project.id, db)

    assert shots is not None
    assert len(shots) == 2
    assert [shot.duration_seconds for shot in shots] == [10, 10]
    assert shots[0].shot_order == 1
    assert shots[0].vietnamese_description.startswith("0-3s cầu thủ")
    assert shots[0].english_narration.startswith("Everyone saw")
    assert shots[0].primary_action == "The small player enters the final under pressure."
    assert shots[0].camera_motion == "slow push-in then lateral track"
    assert shots[1].transition_to_next == "final hold on the net and scoreboard"

def test_phase2_segment_mode_enriches_repeated_camera_metadata(db, monkeypatch):
    project = video_projects.create_project(
        models.VideoProjectCreate(
            topic="World Cup repeated segment metadata",
            phase="phase2",
            target_duration_seconds=20,
            source_blocks=[models.VideoSourceBlockDraft(block_type="idea", content="A small football player wins the final under pressure.")],
        ),
        db,
    )

    def fake_run(settings, prompt, *, output_schema, timeout_seconds=None, cwd=None):
        if output_schema == video_phase2.STORY_DEVELOPMENT_SCHEMA:
            return json.dumps(
                {
                    "input_synthesis": "A tiny footballer proves himself in the final.",
                    "story_strategy": "Open with pressure, then pay off with the winning goal.",
                    "continuity_bible": "Same tiny player, same blue kit, same stadium floodlights.",
                    "detailed_script": "The smallest player enters the final and scores.",
                    **_creative_direction_fields(),
                    "scenes": [
                        {
                            "title": "Final night",
                            "vietnamese_description": "Cầu thủ nhỏ bước vào trận chung kết.",
                            "english_narration": "The smallest player steps into the final while the whole stadium waits.",
                            **_scene_detail_fields(),
                            "target_duration_seconds": 20,
                        }
                    ],
                }
            )
        if output_schema == video_phase2.SHOT_BREAKDOWN_SCHEMA:
            return json.dumps(
                {
                    "total_segments": 2,
                    "segments": [
                        {
                            "segment_order": 1,
                            "segment_duration_seconds": 10,
                            "segment_description_vi": "0-3s cầu thủ nhìn bảng tỷ số; 3-6s cậu siết dây giày; 6-10s cậu chạy vào sân.",
                            "voiceover_text": "Everyone saw only his size, but he carried the calm of someone ready for this exact night.",
                            "segment_action": "The small player enters the final under pressure.",
                            "segment_purpose": "Hook with doubt and pressure.",
                            "segment_type": "story segment",
                            "camera_angle": "eye level",
                            "framing": "medium frame",
                            "visual_composition": "centered player under stadium lights",
                            "camera_movement": "static hold",
                            "subject_movement": "the player breathes, ties his boots, and runs forward",
                            "background_motion": "crowd flags ripple behind rain haze",
                            "next_transition": "match cut to the ball at midfield",
                            **_shot_creative_fields(role="cold open"),
                        },
                        {
                            "segment_order": 2,
                            "segment_duration_seconds": 10,
                            "segment_description_vi": "0-3s bóng lăn qua hàng thủ; 3-7s cầu thủ bứt tốc; 7-10s cậu sút vào góc lưới.",
                            "voiceover_text": "When the last chance arrived, he moved before fear could speak, and the stadium rose with him.",
                            "segment_action": "The small player breaks through and scores.",
                            "segment_purpose": "Pay off the comeback.",
                            "segment_type": "story segment",
                            "camera_angle": "eye level",
                            "framing": "medium frame",
                            "visual_composition": "centered player under stadium lights",
                            "camera_movement": "static hold",
                            "subject_movement": "the player sprints, shoots, and lands in disbelief",
                            "background_motion": "net snaps and crowd erupts",
                            "next_transition": "final hold on the net and scoreboard",
                            **_shot_creative_fields(final=True, role="payoff"),
                        },
                    ],
                }
            )
        raise AssertionError("unexpected schema")

    monkeypatch.setattr(ai_planning, "run_codex_exec", fake_run)

    assert video_phase2.develop_story(project.id, db, force=True) is not None
    assert video_phase2.approve_story(project.id, True, db) is not None
    shots = video_phase2.generate_shots(project.id, db)

    assert shots is not None
    assert len(shots) == 2
    assert [shot.duration_seconds for shot in shots] == [10, 10]
    assert shots[0].camera_angle != shots[1].camera_angle
    assert shots[0].framing != shots[1].framing
    assert video_phase2.validate_shot_variation(db.query(DBVideoShot).filter(DBVideoShot.project_id == project.id).all()) is True

def test_phase2_video_prompt_accepts_shots_alias_payload(db, monkeypatch):
    project = video_projects.create_project(
        models.VideoProjectCreate(
            topic="Stickman prompt aliases",
            phase="phase2",
            source_blocks=[models.VideoSourceBlockDraft(block_type="idea", content="A stickman trains and saves the city.")],
        ),
        db,
    )

    def fake_run(settings, prompt, *, output_schema, timeout_seconds=None, cwd=None):
        if output_schema == video_phase2.STORY_DEVELOPMENT_SCHEMA:
            return json.dumps(
                {
                    "input_synthesis": "Stickman origin story.",
                    "story_strategy": "Fast motivational arc.",
                    "continuity_bible": "Small black stickman remains visually consistent.",
                    "detailed_script": "He trains, faces fear, and wins.",
                    **_creative_direction_fields(),
                    "scenes": [
                        {
                            "title": "Training begins",
                            "vietnamese_description": "Người que bắt đầu luyện tập.",
                            "english_narration": "He chose to train every day.",
                            **_scene_detail_fields(),
                            "target_duration_seconds": 8,
                        }
                    ],
                }
            )
        if output_schema == video_phase2.SHOT_BREAKDOWN_SCHEMA:
            return json.dumps(
                {
                    "shots": [
                        {
                            "scene_order": 1,
                            "shot_order": 1,
                            "duration_seconds": 3,
                            "vietnamese_description": "Cảnh rộng người que luyện tập.",
                            "english_narration": "He started small.",
                            "primary_action": "The stickman starts running.",
                            "purpose": "Open the training montage.",
                            "shot_type": "wide",
                            "camera_angle": "slightly high angle",
                            "framing": "Full body in a white training ground.",
                            "composition": "Centered figure with clean negative space.",
                            "camera_motion": "slow push-in",
                            "subject_motion": "The stickman runs forward.",
                            "environment_motion": "Soft shadows move subtly.",
                            "transition_to_next": "Whip pan into a close-up.",
                            **_shot_creative_fields(final=True, role="cold open"),
                        }
                    ]
                }
            )
        if output_schema == video_phase2.VIDEO_PROMPT_PACK_SCHEMA:
            return json.dumps(
                {
                    "project_name": "Stickman prompt aliases",
                    "aspect_ratio": "9:16",
                    "global_continuity": {"main_character": "Small black stickman, identical proportions."},
                    "negative_prompt_global": "No text overlay, no subtitles, no watermark.",
                    "shots": [
                        {
                            "shot_number": 1,
                            "duration_seconds": 3,
                            "aspect_ratio": "9:16",
                            "vi_description": "Cảnh rộng người que luyện tập.",
                            "narration": "He started small.",
                            "video_prompt": (
                                "Create a 3-second vertical 9:16 cinematic animated video shot. "
                                "Subject and action: the small black stickman runs forward in a clean white training ground. "
                                "Shot type: wide. Camera angle: slightly high angle. Framing: full body in open space. "
                                "Composition: centered figure with clean negative space. Camera movement: slow push-in. "
                                "Subject motion: the stickman runs forward with determination. Environment motion: soft shadows drift subtly. "
                                "Lighting: cinematic natural light. Mood: hopeful and focused. "
                                "Start frame: the stickman stands at the edge of the training ground. "
                                "End frame: the stickman runs toward camera."
                            ),
                            "prompt_explanation_vi": "Prompt yêu cầu cảnh người que nhỏ chạy luyện tập trong sân trắng, camera đẩy chậm và giữ tỷ lệ nhân vật nhất quán.",
                            "negative_prompt": "No text overlay, no watermark, no distorted proportions.",
                            **_prompt_creative_fields(),
                        }
                    ],
                }
            )
        raise AssertionError("unexpected schema")

    monkeypatch.setattr(ai_planning, "run_codex_exec", fake_run)

    assert video_phase2.develop_story(project.id, db, force=True) is not None
    assert video_phase2.approve_story(project.id, True, db) is not None
    assert video_phase2.generate_shots(project.id, db) is not None
    pack = video_phase2.generate_video_prompt_pack(project.id, db)

    assert pack is not None
    assert len(pack.prompts) == 1
    assert "Create a 3-second" in pack.prompts[0].prompt
    assert "người que nhỏ chạy luyện tập" in (pack.prompts[0].prompt_explanation_vi or "")
    assert pack.prompts[0].quality_status == "passed"
    assert pack.prompts[0].camera_motion == "slow push-in"

def test_prompt_pack_strict_mapping_rejects_wrong_order_and_preserves_old_prompt(db, monkeypatch):
    project = video_projects.create_project(models.VideoProjectCreate(topic="Strict prompt mapping", phase="phase2"), db)
    shot = _add_phase2_shot(db, project.id, order=1, narration="A strict test")
    old_path = video_storage.get_project_subdir(project.id, "video_prompts") / "old-valid.txt"
    old_path.write_text("old valid prompt", encoding="utf-8")
    db.add(
        DBVideoShotPrompt(
            project_id=project.id,
            shot_id=shot.id,
            version=1,
            prompt="old valid prompt",
            prompt_path=video_storage.to_artifact_storage_path(old_path),
            quality_status="passed",
        )
    )
    db.commit()

    def fake_run(settings, prompt, *, output_schema, timeout_seconds=None, cwd=None):
        assert output_schema == video_phase2.VIDEO_PROMPT_PACK_SCHEMA
        return json.dumps(
            {
                "prompts": [
                    {
                        "shot_order": 2,
                        "prompt": "Wrong order prompt",
                        "prompt_explanation_vi": "Sai thứ tự.",
                        "negative_prompt": "No watermark.",
                        "duration_seconds": 2,
                        "aspect_ratio": "9:16",
                        "shot_type": "wide",
                        "camera_angle": "eye level",
                        "framing": "centered",
                        "composition": "simple composition",
                        "camera_motion": "slow push",
                        "subject_motion": "subject moves",
                        "environment_motion": "background moves",
                        "start_frame": "start",
                        "end_frame": "end",
                        "lighting": "soft",
                        "mood": "focused",
                        "continuity_notes": "same subject",
                        **_prompt_creative_fields(),
                    }
                ]
            }
        )

    monkeypatch.setattr(ai_planning, "run_codex_exec", fake_run)
    with pytest.raises(video_planning.VideoPlanningValidationError) as exc_info:
        video_phase2.generate_video_prompt_pack(project.id, db)

    assert getattr(exc_info.value, "error_code", None) == "AI_VIDEO_MAPPING_ORDER_MISMATCH"
    assert db.query(DBVideoShotPrompt).filter(DBVideoShotPrompt.shot_id == shot.id).count() == 1
    assert old_path.exists()
    event = (
        db.query(DBVideoDebugEvent)
        .filter(DBVideoDebugEvent.project_id == project.id, DBVideoDebugEvent.step_name == "video_prompt_validation")
        .order_by(DBVideoDebugEvent.created_at.desc())
        .first()
    )
    assert event is not None
    assert event.error_code == "AI_VIDEO_MAPPING_ORDER_MISMATCH"
    assert "Wrong order prompt" not in (event.technical_details or "")

def test_mapping_alias_conflict_and_series_bible_validation_errors():
    normalized = video_phase2._normalize_shot_breakdown_payload(
        {
            "use_case": "sales ad",
            "voice_mode": "mixed",
            "talk_density": "dense",
            "sales_cta": "urgent",
            "segments": [
                {
                    "segment_order": 1,
                    "duration_seconds": 10,
                    "description_vi": "Một phân đoạn bán hàng ngắn.",
                    "voiceover_text": "This opening explains the offer with a clear benefit and action.",
                    "segment_action": "Presenter reveals the product benefit.",
                    "camera_angle": "eye level",
                    "framing": "medium",
                    "visual_composition": "product and presenter balanced in frame",
                    "camera_movement": "slow push",
                    "subject_movement": "presenter points to product",
                    "background_motion": "soft light movement",
                    "next_transition": "CTA card reveal",
                    **_shot_creative_fields(final=True),
                }
            ],
        }
    )
    assert normalized["video_purpose"] == "sales_ad"
    assert normalized["dialogue_mode"] == "mixed"
    assert normalized["narration_density"] == "dense"
    assert normalized["call_to_action_style"] == "urgent"
    assert normalized["shots"][0]["english_narration"].startswith("This opening explains")

    with pytest.raises(video_planning.VideoPlanningValidationError) as conflict:
        video_phase2._normalize_video_prompt_pack_payload(
            {
                "prompts": [{"shot_order": 1, "prompt": "A"}],
                "video_prompts": [{"shot_order": 1, "prompt": "B"}],
            }
        )
    assert getattr(conflict.value, "error_code", None) == "AI_VIDEO_MAPPING_ALIAS_CONFLICT"

    with pytest.raises(video_planning.VideoPlanningValidationError) as purpose_conflict:
        video_phase2._normalize_story_development_payload(
            {"video_purpose": "sales_ad", "purpose": "global_short", "scenes": []}
        )
    assert getattr(purpose_conflict.value, "error_code", None) == "AI_VIDEO_MAPPING_ALIAS_CONFLICT"

    with pytest.raises(video_planning.VideoPlanningValidationError) as narration_conflict:
        video_phase2._normalize_shot_breakdown_payload(
            {"shots": [{"english_narration": "First narration", "dialogue": "Different narration"}]}
        )
    assert getattr(narration_conflict.value, "error_code", None) == "AI_VIDEO_MAPPING_ALIAS_CONFLICT"

    with pytest.raises(video_planning.VideoPlanningValidationError) as missing:
        video_phase2.normalize_series_bible_payload({"character_bible": "Hero only"})
    assert getattr(missing.value, "error_code", None) == "AI_VIDEO_MAPPING_REQUIRED_FIELD_MISSING"

def test_shot_breakdown_normalizes_ai_shot_order_to_list_order():
    normalized = video_phase2._normalize_shot_breakdown_payload(
        {
            "segments": [
                {
                    "shot_order": 0,
                    "scene_order": 1,
                    "description_vi": "Mở đầu bằng một cảnh hook.",
                },
                {
                    "shot_order": 10,
                    "scene_order": 1,
                    "description_vi": "Cảnh thứ hai tiếp nối câu chuyện.",
                },
            ]
        }
    )

    plan = video_phase2.ShotBreakdownPlan.model_validate(normalized)

    assert [shot.shot_order for shot in plan.shots] == [1, 2]
    video_phase2._validate_shot_order_output(
        plan,
        valid_scene_orders={1},
        expected_count=2,
        first_shot_order=1,
    )

def test_shot_alias_conflict_preserves_existing_artifacts(db, monkeypatch):
    project = video_projects.create_project(models.VideoProjectCreate(topic="Alias conflict preservation", phase="phase2"), db)
    scene = video_projects.replace_scenes(
        project.id,
        models.VideoScenesReplaceRequest(
            scenes=[models.VideoSceneDraft(title="Scene", dialogue="Old dialogue", visual_description="Old visual")]
        ),
        db,
    )[0]
    video_projects.set_scene_approved(project.id, scene.id, True, db)
    project_row = db.get(DBVideoProject, project.id)
    project_row.story_approved = True
    db.commit()
    old_shot = _add_phase2_shot(db, project.id, order=1, narration="Existing narration", duration_seconds=3)

    def fake_run(settings, prompt, *, output_schema, timeout_seconds=None, cwd=None):
        assert output_schema == video_phase2.SHOT_BREAKDOWN_SCHEMA
        return json.dumps({"shots": [{"english_narration": "First", "dialogue": "Second"}]})

    monkeypatch.setattr(ai_planning, "run_codex_exec", fake_run)

    with pytest.raises(video_planning.VideoPlanningValidationError):
        video_phase2.generate_shots(project.id, db)

    preserved = db.get(DBVideoShot, old_shot.id)
    assert preserved is not None
    assert preserved.english_narration == "Existing narration"

def test_prompt_pack_retry_writes_only_valid_mapping_attempt(db, monkeypatch):
    project = video_projects.create_project(models.VideoProjectCreate(topic="Retry prompt mapping", phase="phase2"), db)
    shot = _add_phase2_shot(db, project.id, order=1, narration="Retry narration")
    calls = {"count": 0}

    def prompt_payload(shot_order: int, text: str):
        return {
            "shot_order": shot_order,
            "prompt": text,
            "prompt_explanation_vi": "Bản giải thích hợp lệ.",
            "negative_prompt": "No watermark.",
            "duration_seconds": 2,
            "aspect_ratio": "9:16",
            "shot_type": "wide",
            "camera_angle": "eye level",
            "framing": "centered",
            "composition": "simple composition",
            "camera_motion": "slow push",
            "subject_motion": "subject moves",
            "environment_motion": "background moves",
            "start_frame": "start",
            "end_frame": "end",
            "lighting": "soft",
            "mood": "focused",
            "continuity_notes": "same subject",
            **_prompt_creative_fields(),
        }

    def fake_run(settings, prompt, *, output_schema, timeout_seconds=None, cwd=None):
        assert output_schema == video_phase2.VIDEO_PROMPT_PACK_SCHEMA
        calls["count"] += 1
        if calls["count"] == 1:
            return json.dumps({"prompts": [prompt_payload(2, "Invalid first attempt")]})
        return json.dumps({"prompts": [prompt_payload(1, "Valid second attempt")]})

    monkeypatch.setattr(ai_planning, "run_codex_exec", fake_run)
    pack = video_phase2.generate_video_prompt_pack(project.id, db)

    assert pack is not None
    assert calls["count"] == 2
    assert len(pack.prompts) == 1
    assert pack.prompts[0].prompt == "Valid second attempt"
    assert db.query(DBVideoShotPrompt).filter(DBVideoShotPrompt.shot_id == shot.id).count() == 1
    warning = db.query(DBVideoDebugEvent).filter(
        DBVideoDebugEvent.project_id == project.id,
        DBVideoDebugEvent.step_name == "video_prompt_validation",
        DBVideoDebugEvent.status == "warning",
    ).first()
    assert warning is not None
    assert warning.error_code == "AI_VIDEO_MAPPING_ORDER_MISMATCH"

def test_prompt_pack_uses_shot_creative_notes_when_ai_omits_prompt_notes(db, monkeypatch):
    project = video_projects.create_project(
        models.VideoProjectCreate(topic="Prompt notes fallback", phase="phase2", aspect_ratio="9:16"),
        db,
    )
    shot = _add_phase2_shot(db, project.id, order=1, narration="A reveal keeps viewers watching.", duration_seconds=6)
    shot.prompt_status = "missing"
    shot.vietnamese_description = "Founder hé lộ hợp đồng trên bàn."
    shot.primary_action = "The founder slides the signed contract into the light."
    shot.retention_json = {
        "retention_role": "reveal payoff tension",
        "open_loop": "Viewers wait to see what is inside the folder.",
        "visual_surprise": "A hidden signature appears as the folder opens.",
    }
    shot.transition_json = {
        "transition_type": "match cut",
        "trigger": "folder snap",
        "timing": "last half second",
        "edit_reason": "carry the reveal into the next beat",
        "transition_sfx": "paper snap",
        "continuity_risk": "low; keep the same founder and desk layout",
    }
    shot.sound_design_json = {
        "music_mood": "quiet business tension",
        "sound_cues": [{"cue_type": "paper snap", "timing": "on reveal", "purpose": "mark the payoff"}],
        "mixing_notes": "Keep narration above the paper snap and music bed.",
    }
    db.commit()

    def fake_run(settings, prompt, *, output_schema, timeout_seconds=None, cwd=None):
        assert output_schema == video_phase2.VIDEO_PROMPT_PACK_SCHEMA
        return json.dumps(
            {
                "global_continuity": "Same founder, same desk, same warm cinematic office.",
                "negative_prompt_global": "No watermark, no subtitles, no distorted hands.",
                "prompts": [
                    {
                        "shot_order": 1,
                        "prompt": (
                            "Create a 6-second 9:16 cinematic video of a founder sliding a signed contract "
                            "into warm light."
                        ),
                        "prompt_explanation_vi": (
                            "Prompt tạo cảnh founder hé lộ hợp đồng đã ký trên bàn, "
                            "nhấn vào khoảnh khắc reveal."
                        ),
                        "duration_seconds": 6,
                        "aspect_ratio": "9:16",
                        "shot_type": "reveal close-up",
                        "camera_angle": "low desk angle",
                        "framing": "medium close-up on hands and contract",
                        "composition": "contract enters the key light while founder remains visible behind it",
                        "camera_motion": "slow push-in",
                        "subject_motion": "founder slides the folder open and reveals the signature",
                        "environment_motion": "warm office reflections drift subtly",
                        "start_frame": "closed folder on the desk",
                        "end_frame": "signed contract visible in warm light",
                        "lighting": "warm cinematic key light",
                        "mood": "tense and satisfying",
                    }
                ],
            }
        )

    monkeypatch.setattr(ai_planning, "run_codex_exec", fake_run)

    pack = video_phase2.generate_video_prompt_pack(project.id, db)

    assert pack is not None
    assert len(pack.prompts) == 1
    assert pack.prompts[0].quality_status == "passed"
    assert "reveal payoff tension" in (pack.prompts[0].retention_notes or "")
    assert "match cut" in (pack.prompts[0].transition_notes or "")
    assert "paper snap" in (pack.prompts[0].sound_design_notes or "")
    content = video_phase2.get_video_prompt_content(project.id, shot.id, db)
    assert content is not None
    assert "reveal payoff tension" in (content.retention_notes or "")
    assert "paper snap" in (content.sound_design_notes or "")

def test_prompt_pack_accepts_normalized_creative_note_defaults_for_multi_segment_payload(db, monkeypatch):
    project = video_projects.create_project(
        models.VideoProjectCreate(
            topic="Six segment prompt notes fallback",
            phase="phase2",
            prompt_segment_count=6,
            prompt_segment_duration_seconds=10,
            micro_scenes_per_prompt=3,
            aspect_ratio="9:16",
        ),
        db,
    )
    for order in range(1, 7):
        shot = _add_phase2_shot(
            db,
            project.id,
            order=order,
            narration=f"Narration for segment {order}.",
            duration_seconds=10,
        )
        shot.prompt_status = "missing"
        shot.vietnamese_description = f"Segment {order} giữ cùng nhân vật và tăng nhịp câu chuyện."
        shot.primary_action = f"The character performs story beat {order}."
        db.commit()

    def fake_run(settings, prompt, *, output_schema, timeout_seconds=None, cwd=None):
        assert output_schema == video_phase2.VIDEO_PROMPT_PACK_SCHEMA
        return json.dumps(
            {
                "negative_prompt_global": "No watermark, no subtitles, no distorted hands.",
                "global_continuity": "Same character, same outfit, same cinematic style.",
                "prompts": [
                    {
                        "shot_order": order,
                        "prompt": (
                            f"Create a 10-second 9:16 cinematic video. This is segment {order} of 6: "
                            f"the character performs story beat {order} with clear camera motion and continuity."
                        ),
                        "prompt_explanation_vi": (
                            f"Segment {order} mô tả beat câu chuyện bằng hình ảnh điện ảnh rõ ràng."
                        ),
                        "duration_seconds": 10,
                        "aspect_ratio": "9:16",
                        "shot_type": "cinematic story segment",
                        "camera_angle": "eye level",
                        "framing": "medium vertical frame",
                        "composition": "main character centered with readable action and background depth",
                        "camera_motion": "slow push-in",
                        "subject_motion": f"the character performs story beat {order}",
                        "environment_motion": "subtle cinematic background movement",
                        "start_frame": f"opening pose for segment {order}",
                        "end_frame": f"final visual beat for segment {order}",
                        "lighting": "cinematic natural light",
                        "mood": "focused and story-driven",
                    }
                    for order in range(1, 7)
                ],
            }
        )

    monkeypatch.setattr(ai_planning, "run_codex_exec", fake_run)

    pack = video_phase2.generate_video_prompt_pack(project.id, db)

    assert pack is not None
    assert len(pack.prompts) == 6
    for prompt in pack.prompts:
        assert prompt.quality_status == "passed"
        assert prompt.retention_notes == video_phase2.VIDEO_PROMPT_CREATIVE_NOTE_DEFAULTS["retention_notes"]
        assert prompt.transition_notes == video_phase2.VIDEO_PROMPT_CREATIVE_NOTE_DEFAULTS["transition_notes"]
        assert prompt.sound_design_notes == video_phase2.VIDEO_PROMPT_CREATIVE_NOTE_DEFAULTS["sound_design_notes"]

def test_phase2_video_prompt_accepts_top_level_segments_payload(db, monkeypatch):
    project = video_projects.create_project(
        models.VideoProjectCreate(
            topic="Stickman segment prompts",
            phase="phase2",
            target_duration_seconds=20,
            aspect_ratio="9:16",
            source_blocks=[models.VideoSourceBlockDraft(block_type="idea", content="A stickman tries every sport and wins by accident.")],
        ),
        db,
    )
    shot_one = _add_phase2_shot(db, project.id, order=1, narration="He tried to become a sports legend.", duration_seconds=10)
    shot_two = _add_phase2_shot(db, project.id, order=2, narration="Then the funniest victory found him.", duration_seconds=10)
    for index, shot in enumerate((shot_one, shot_two), start=1):
        shot.prompt_status = "missing"
        shot.vietnamese_description = f"Segment {index} có 2-4 cảnh nhỏ liên tục."
        shot.primary_action = "The stickman moves through a fast sports montage."
        shot.shot_type = "sports montage segment"
        shot.camera_angle = "low angle"
        shot.framing = "medium action frame"
        shot.composition = "stickman centered in a clean sports arena"
        shot.camera_motion = "smooth tracking move"
        shot.subject_motion = "the stickman runs, jumps, and reacts"
        shot.environment_motion = "sports props move through the background"
    db.commit()

    def fake_run(settings, prompt, *, output_schema, timeout_seconds=None, cwd=None):
        assert output_schema == video_phase2.VIDEO_PROMPT_PACK_SCHEMA
        assert "Segment X of 2" in prompt
        return json.dumps(
            {
                "project_name": "Stickman segment prompts",
                "video_language": "en",
                "aspect_ratio": "9:16",
                "negative_prompt_global": "No text overlay, no subtitles, no watermark.",
                "global_continuity_bible": "Same black stickman, same simple proportions, same comic sports montage style.",
                "segments": [
                    {
                        "segment_order": 1,
                        "segment_duration_seconds": 10,
                        "main_video_prompt": "Create a 10-second 9:16 cinematic video. This is segment 1 of 2: 0-3s the stickman sprints onto the field, 3-6s he trips through soccer practice, 6-10s he lands in a funny heroic pose.",
                        "prompt_explanation_vi": "Segment 1 mở bằng người que chạy vào sân, vấp trong buổi tập và kết bằng tư thế anh hùng hài hước.",
                        "negative": "No watermark, no subtitles, no realistic human face.",
                        "segment_type": "opening sports montage segment",
                        "camera_angle": "low comic hero angle",
                        "framing": "wide field frame into medium reaction frame",
                        "visual_composition": "stickman in the lower third with oversized sports props around him",
                        "camera_movement": "fast side track into a small push-in",
                        "subject_movement": "the stickman runs, slips, spins, and freezes in a pose",
                        "background_motion": "balls and track lines sweep behind him",
                        "opening_frame": "Stickman at the edge of the field",
                        "ending_frame": "Stickman frozen in a proud but awkward pose",
                        "lighting": "bright clean stadium lighting",
                        "mood": "comic, fast, and hopeful",
                        "segment_continuity": "Keep the same stickman and same clean sports montage world.",
                        **_prompt_creative_fields(),
                    },
                    {
                        "segment_order": 2,
                        "segment_duration_seconds": 10,
                        "segment_prompt": "Create a 10-second 9:16 cinematic video. This is segment 2 of 2: 0-3s the stickman falls into a chair, 3-7s judges stare in disbelief, 7-10s he accidentally wins the chair-sitting championship.",
                        "prompt_explanation_vi": "Segment 2 là payoff hài: người que ngã vào ghế, giám khảo kinh ngạc rồi cậu vô tình thắng giải ngồi ghế.",
                        "negative": "No watermark, no subtitles, no distorted limbs.",
                        "segment_type": "payoff comedy segment",
                        "camera_angle": "eye-level judging angle",
                        "framing": "medium chair frame into close-up trophy reveal",
                        "visual_composition": "chair centered, trophy glinting in the foreground",
                        "camera_movement": "gentle push-in with a final locked hold",
                        "subject_movement": "the stickman sits, blinks, and slowly lifts the trophy",
                        "background_motion": "judges lean forward and confetti drifts down",
                        "opening_frame": "Stickman falling backward toward a chair",
                        "ending_frame": "Stickman holding the trophy while still seated",
                        "lighting": "clean celebratory stage lighting",
                        "mood": "absurd, triumphant, and funny",
                        "segment_continuity": "Same stickman, same comic timing, final payoff of the montage.",
                        **_prompt_creative_fields(),
                    },
                ],
            }
        )

    monkeypatch.setattr(ai_planning, "run_codex_exec", fake_run)

    pack = video_phase2.generate_video_prompt_pack(project.id, db)

    assert pack is not None
    assert len(pack.prompts) == 2
    assert pack.prompts[0].duration_seconds == pytest.approx(10)
    assert "segment 1 of 2" in pack.prompts[0].prompt.lower()
    assert pack.prompts[0].camera_motion == "fast side track into a small push-in"
    assert pack.prompts[1].quality_status == "passed"

def test_phase2_video_prompt_fills_missing_continuity_notes_from_project(db, monkeypatch):
    project = video_projects.create_project(
        models.VideoProjectCreate(
            topic="Founder deal prompt continuity",
            phase="phase2",
            aspect_ratio="9:16",
        ),
        db,
    )
    project_row = db.query(database.VideoProject).filter(database.VideoProject.id == project.id).first()
    assert project_row is not None
    project_row.continuity_bible = "Same founder, navy jacket, warm office lighting, consistent cinematic realism."
    shot = _add_phase2_shot(db, project.id, order=1, narration="The founder makes the final call.", duration_seconds=10)
    shot.prompt_status = "missing"
    db.commit()
    long_prompt = (
        "Create a 10-second 9:16 cinematic video of the founder making the final deal call in a warm office. "
        "Maintain the same founder, same navy jacket, same warm office lighting, same cinematic realism, and the same story state. "
        "Use a slow push-in from a medium frame to a close-up of the phone and contract while the tension builds."
    )

    def fake_run(settings, prompt, *, output_schema, timeout_seconds=None, cwd=None):
        assert output_schema == video_phase2.VIDEO_PROMPT_PACK_SCHEMA
        return json.dumps(
            {
                "prompts": [
                    {
                        "shot_order": 1,
                        "prompt": long_prompt,
                        "prompt_explanation_vi": "Prompt tạo cảnh founder gọi cuộc chốt hợp đồng trong văn phòng ấm, giữ nhịp điện ảnh.",
                        "negative_prompt": "No watermark, no subtitles, no distorted face, no extra people.",
                        "duration_seconds": 10,
                        "aspect_ratio": "9:16",
                        "retention_notes": "Retention role: keep viewers waiting for the signed deal payoff.",
                        "transition_notes": "Transition: hold on the phone gesture with a soft impact cue.",
                        "sound_design_notes": "Sound: quiet office ambience and subtle tension bed as editor guidance only.",
                    }
                ]
            }
        )

    monkeypatch.setattr(ai_planning, "run_codex_exec", fake_run)

    pack = video_phase2.generate_video_prompt_pack(project.id, db)

    assert pack is not None
    assert len(pack.prompts) == 1
    assert pack.prompts[0].quality_status == "passed"
    assert len(pack.prompts[0].prompt) > 160
    assert "Same founder" in (pack.prompts[0].continuity_notes or "")

def test_phase2_configured_prompt_segments_create_exact_micro_scenes(db, monkeypatch):
    project = video_projects.create_project(
        models.VideoProjectCreate(
            topic="Một video 60 giây về founder chốt hợp đồng",
            phase="phase2",
            prompt_segment_count=6,
            prompt_segment_duration_seconds=10,
            micro_scenes_per_prompt=3,
            aspect_ratio="9:16",
            source_blocks=[models.VideoSourceBlockDraft(block_type="idea", content="Founder closes a deal in six beats.")],
        ),
        db,
    )
    assert project.target_duration_seconds == 60
    assert project.prompt_segment_count == 6
    assert project.prompt_segment_duration_seconds == 10
    assert project.micro_scenes_per_prompt == 3

    def fake_run(settings, prompt, *, output_schema, timeout_seconds=None, cwd=None):
        if output_schema == video_phase2.STORY_DEVELOPMENT_SCHEMA:
            return json.dumps(
                {
                    "input_synthesis": "Founder closes a deal in six beats.",
                    "story_strategy": "Six-segment pressure and payoff story.",
                    "continuity_bible": "Same founder, navy jacket, warm office lighting.",
                    "detailed_script": "A founder moves from pressure to signed deal.",
                    **_creative_direction_fields(),
                    "scenes": [
                        {
                            "title": "Deal arc",
                            "vietnamese_description": "Founder đi qua sáu nhịp chốt hợp đồng.",
                            "english_narration": "Every beat brings the deal closer.",
                            **_scene_detail_fields(),
                            "target_duration_seconds": 60,
                        }
                    ],
                }
            )
        if output_schema == video_phase2.SHOT_BREAKDOWN_SCHEMA:
            assert "Tạo đúng 6 prompt segment" in prompt
            assert "đúng 3 micro_scenes" in prompt
            segments = []
            for index in range(1, 7):
                segments.append(
                    {
                        "scene_order": 1,
                        "segment_order": index,
                        "segment_duration_seconds": 10,
                        "segment_description_vi": f"Segment {index}: 0-3.3s mở nhịp; 3.3-6.7s tăng áp lực; 6.7-10s chuyển sang nhịp sau.",
                        "voiceover_text": f"Beat {index} moves the founder closer to the signed deal.",
                        "segment_action": f"Founder completes deal beat {index}.",
                        "segment_purpose": "Build pressure and continuity.",
                        "segment_type": "deal segment",
                        "camera_angle": "eye-level office angle",
                        "framing": "medium frame into detail",
                        "visual_composition": "founder foreground, contract detail in frame",
                        "camera_movement": "slow push-in",
                        "subject_movement": "0-3.3s founder reads; 3.3-6.7s hand moves; 6.7-10s contract detail lands.",
                        "background_motion": "office lights and papers move subtly",
                        "next_transition": "match cut on contract paper",
                        "micro_scenes": [
                            {"order": 1, "start_seconds": 0, "end_seconds": 3.3, "description_vi": "Founder đọc tin nhắn.", "visual_action": "Founder reads the message.", "camera_note": "phone close-up"},
                            {"order": 2, "start_seconds": 3.3, "end_seconds": 6.7, "description_vi": "Founder đặt bút lên hợp đồng.", "visual_action": "Pen moves toward contract.", "camera_note": "hand insert"},
                            {"order": 3, "start_seconds": 6.7, "end_seconds": 10, "description_vi": "Hợp đồng lộ rõ để chuyển cảnh.", "visual_action": "Contract reveal.", "camera_note": "slow push-in"},
                        ],
                        **_shot_creative_fields(final=index == 6, role="payoff" if index == 6 else "build-up"),
                    }
                )
            return json.dumps({"segments": segments})
        raise AssertionError("unexpected schema")

    monkeypatch.setattr(ai_planning, "run_codex_exec", fake_run)

    assert video_phase2.develop_story(project.id, db, force=True) is not None
    assert video_phase2.approve_story(project.id, True, db) is not None
    shots = video_phase2.generate_shots(project.id, db)

    assert len(shots) == 6
    assert [shot.duration_seconds for shot in shots] == [10, 10, 10, 10, 10, 10]
    assert sum(len(shot.micro_scenes) for shot in shots) == 18
    assert shots[0].micro_scenes[0].start_seconds == pytest.approx(0)
    assert shots[0].micro_scenes[-1].end_seconds == pytest.approx(10)

def test_phase2_prompt_segment_config_change_marks_dependent_artifacts_stale(db):
    project = video_projects.create_project(
        models.VideoProjectCreate(
            topic="Một video 60 giây về founder chốt hợp đồng",
            phase="phase2",
            prompt_segment_count=6,
            prompt_segment_duration_seconds=10,
            micro_scenes_per_prompt=3,
            aspect_ratio="9:16",
        ),
        db,
    )
    shot = _add_phase2_shot(
        db,
        project.id,
        order=1,
        narration="This voiceover was generated for the old prompt duration.",
        duration_seconds=10,
        voice_completed=True,
        audio_duration=10,
    )
    shot.subtitle_status = "completed"
    db.add(
        DBVideoShotPrompt(
            project_id=project.id,
            shot_id=shot.id,
            prompt="Old configured segment prompt.",
            duration_seconds=10,
            quality_status="passed",
        )
    )
    db.add(DBVideoSubtitle(project_id=project.id, status="completed", format="srt"))
    db.add(DBVideoRenderJob(project_id=project.id, status="completed", progress=1.0, stale=False))
    db.add(DBVideoPackageExport(project_id=project.id, status="completed", stale=False))
    db.commit()

    updated = video_projects.update_project(
        project.id,
        models.VideoProjectUpdate(prompt_segment_duration_seconds=8),
        db,
    )

    assert updated is not None
    assert updated.target_duration_seconds == 48
    refreshed_shot = db.get(DBVideoShot, shot.id)
    assert refreshed_shot is not None
    assert refreshed_shot.status == "stale"
    assert refreshed_shot.prompt_status == "stale"
    assert refreshed_shot.voice_status == "stale"
    assert refreshed_shot.subtitle_status == "stale"
    assert db.query(DBVideoSubtitle).filter(DBVideoSubtitle.project_id == project.id).one().status == "stale"
    assert db.query(DBVideoRenderJob).filter(DBVideoRenderJob.project_id == project.id).one().stale is True
    assert db.query(DBVideoPackageExport).filter(DBVideoPackageExport.project_id == project.id).one().stale is True
    assert video_projects.get_project(project.id, db).package_stale is True

def test_phase2_prompt_segment_config_only_update_preserves_story_approval(db):
    project = video_projects.create_project(
        models.VideoProjectCreate(
            topic="Một video 60 giây đã duyệt story",
            phase="phase2",
            prompt_segment_count=6,
            prompt_segment_duration_seconds=10,
            micro_scenes_per_prompt=3,
        ),
        db,
    )
    project_row = db.query(database.VideoProject).filter(database.VideoProject.id == project.id).first()
    assert project_row is not None
    project_row.story_approved = True
    project_row.script_approved = True
    project_row.status = "story_approved"
    project_row.retention_plan_json = {"hook": "old hook"}
    project_row.sound_design_plan_json = {"music_mood": "old mood"}
    db.commit()

    updated = video_projects.update_project(
        project.id,
        models.VideoProjectUpdate(prompt_segment_count=4),
        db,
    )

    assert updated is not None
    assert updated.prompt_segment_count == 4
    assert updated.target_duration_seconds == 40
    assert updated.story_approved is True
    assert updated.script_approved is True
    refreshed = db.query(database.VideoProject).filter(database.VideoProject.id == project.id).one()
    assert refreshed.retention_plan_json == {"hook": "old hook"}
    assert refreshed.sound_design_plan_json == {"music_mood": "old mood"}

def test_phase2_generate_shots_prunes_unlocked_segments_when_locked_match_config(db, monkeypatch):
    project = video_projects.create_project(
        models.VideoProjectCreate(
            topic="Configured project with old extra unlocked segments",
            phase="phase2",
            prompt_segment_count=2,
            prompt_segment_duration_seconds=10,
            micro_scenes_per_prompt=3,
        ),
        db,
    )
    project_row = db.query(database.VideoProject).filter(database.VideoProject.id == project.id).first()
    assert project_row is not None
    project_row.story_approved = True
    project_row.script_approved = True
    first = _add_phase2_shot(db, project.id, order=1, narration="Locked one.", duration_seconds=10)
    second = _add_phase2_shot(db, project.id, order=2, narration="Locked two.", duration_seconds=10)
    first.locked = True
    second.locked = True
    _add_phase2_shot(db, project.id, order=3, narration="Old extra one.", duration_seconds=10)
    _add_phase2_shot(db, project.id, order=4, narration="Old extra two.", duration_seconds=10)
    db.commit()

    def fail_run(*args, **kwargs):
        raise AssertionError("AI should not run when locked segments already match the configured count")

    monkeypatch.setattr(ai_planning, "run_codex_exec", fail_run)

    shots = video_phase2.generate_shots(project.id, db)

    assert len(shots) == 2
    assert [shot.shot_order for shot in shots] == [1, 2]
    assert db.query(DBVideoShot).filter(DBVideoShot.project_id == project.id).count() == 2

def test_phase2_generate_shots_rejects_locked_segments_above_config(db):
    project = video_projects.create_project(
        models.VideoProjectCreate(
            topic="Configured project with too many locked segments",
            phase="phase2",
            prompt_segment_count=2,
            prompt_segment_duration_seconds=10,
            micro_scenes_per_prompt=3,
        ),
        db,
    )
    project_row = db.query(database.VideoProject).filter(database.VideoProject.id == project.id).first()
    assert project_row is not None
    project_row.story_approved = True
    project_row.script_approved = True
    for order in range(1, 4):
        shot = _add_phase2_shot(db, project.id, order=order, narration=f"Locked {order}.", duration_seconds=10)
        shot.locked = True
    db.commit()

    with pytest.raises(video_planning.VideoPlanningValidationError, match="vượt cấu hình 2 prompt"):
        video_phase2.generate_shots(project.id, db)

    assert db.query(DBVideoShot).filter(DBVideoShot.project_id == project.id).count() == 3

def test_phase2_configured_prompt_segments_accept_nested_aliases_and_non_ten_second_ranges(db, monkeypatch):
    project = video_projects.create_project(
        models.VideoProjectCreate(
            topic="Một video 32 giây về màn ra mắt sản phẩm",
            phase="phase2",
            prompt_segment_count=4,
            prompt_segment_duration_seconds=8,
            micro_scenes_per_prompt=4,
            source_blocks=[models.VideoSourceBlockDraft(block_type="idea", content="A product reveal in four configured prompt segments.")],
        ),
        db,
    )

    def fake_run(settings, prompt, *, output_schema, timeout_seconds=None, cwd=None):
        if output_schema == video_phase2.STORY_DEVELOPMENT_SCHEMA:
            return json.dumps(
                {
                    "input_synthesis": "Product reveal in four beats.",
                    "story_strategy": "Reveal, demo, proof, payoff.",
                    "continuity_bible": "Same product, same studio, clean light.",
                    "detailed_script": "A compact launch arc.",
                    **_creative_direction_fields(),
                    "scenes": [{"title": "Reveal", "vietnamese_description": "Sản phẩm được hé lộ.", "english_narration": "The reveal begins.", **_scene_detail_fields(), "target_duration_seconds": 32}],
                }
            )
        if output_schema == video_phase2.SHOT_BREAKDOWN_SCHEMA:
            assert "0-2s" in prompt
            segments = []
            for index in range(1, 5):
                segments.append(
                    {
                        "prompt_order": index,
                        "duration": "8 seconds",
                        "description_vi": f"Segment {index}: sản phẩm chuyển qua bốn cảnh nhỏ.",
                        "narration": f"Reveal beat {index} keeps momentum.",
                        "action": f"Product reveal beat {index}.",
                        "purpose": "Reveal product value.",
                        "type": "product reveal segment",
                        "angle": "clean studio angle",
                        "frame": "medium product frame",
                        "visual_composition": "product centered with reflective table",
                        "movement": "smooth orbit",
                        "subject_movement": "product rotates through the light",
                        "background_motion": "soft reflections drift",
                        "next_transition": "light wipe",
                        "beats": [
                            {"order": 1, "start": 0, "end": 2, "description": "Mở bằng silhouette.", "action": "Silhouette appears.", "camera": "wide hold"},
                            {"order": 2, "start": 2, "end": 4, "description": "Ánh sáng quét qua sản phẩm.", "action": "Light reveals surface.", "camera": "side track"},
                            {"order": 3, "start": 4, "end": 6, "description": "Chi tiết chức năng hiện ra.", "action": "Feature detail appears.", "camera": "macro insert"},
                            {"order": 4, "start": 6, "end": 8, "description": "Chuyển sang segment tiếp theo.", "action": "Product turns toward camera.", "camera": "push-in"},
                        ],
                        **_shot_creative_fields(final=index == 4),
                    }
                )
            return json.dumps({"scenes": [{"scene_order": 1, "segments": segments}]})
        raise AssertionError("unexpected schema")

    monkeypatch.setattr(ai_planning, "run_codex_exec", fake_run)

    assert video_phase2.develop_story(project.id, db, force=True) is not None
    assert video_phase2.approve_story(project.id, True, db) is not None
    shots = video_phase2.generate_shots(project.id, db)

    assert len(shots) == 4
    assert [shot.duration_seconds for shot in shots] == [8, 8, 8, 8]
    assert all(len(shot.micro_scenes) == 4 for shot in shots)
    assert [(scene.start_seconds, scene.end_seconds) for scene in shots[0].micro_scenes] == [(0, 2), (2, 4), (4, 6), (6, 8)]

def test_phase2_configured_prompt_segments_parse_timeline_text_when_micro_scene_array_missing(db, monkeypatch):
    project = video_projects.create_project(
        models.VideoProjectCreate(
            topic="Một video 20 giây về cú sút quyết định",
            phase="phase2",
            prompt_segment_count=2,
            prompt_segment_duration_seconds=10,
            micro_scenes_per_prompt=3,
            source_blocks=[models.VideoSourceBlockDraft(block_type="idea", content="A decisive football shot in two prompt segments.")],
        ),
        db,
    )

    def fake_run(settings, prompt, *, output_schema, timeout_seconds=None, cwd=None):
        if output_schema == video_phase2.STORY_DEVELOPMENT_SCHEMA:
            return json.dumps({"input_synthesis": "Football payoff.", "story_strategy": "Setup and shot.", "continuity_bible": "Same player.", "detailed_script": "Two beats.", **_creative_direction_fields(), "scenes": [{"title": "Shot", "vietnamese_description": "Cầu thủ sút bóng.", "english_narration": "The final chance arrives.", **_scene_detail_fields(), "target_duration_seconds": 20}]})
        if output_schema == video_phase2.SHOT_BREAKDOWN_SCHEMA:
            return json.dumps(
                {
                    "segments": [
                        {"segment_order": 1, "segment_duration_seconds": 10, "segment_description_vi": "0-3s cầu thủ nhìn khung thành; 3-6s cậu lấy đà; 6-10s bóng rời chân.", "voiceover_text": "He sees the opening.", "segment_action": "Player prepares and shoots.", "camera_angle": "low sideline", "framing": "medium to close", "visual_composition": "goal in background", "camera_movement": "tracking move", "subject_movement": "player runs and shoots", "background_motion": "crowd waves", "next_transition": "ball match cut", **_shot_creative_fields()},
                        {"segment_order": 2, "segment_duration_seconds": 10, "segment_description_vi": "0-3s bóng bay qua hậu vệ; 3-6s thủ môn lao người; 6-10s lưới rung và khán đài bùng nổ.", "voiceover_text": "The stadium rises with the ball.", "segment_action": "Ball scores and crowd erupts.", "camera_angle": "goal-line", "framing": "tracking close-up", "visual_composition": "net foreground", "camera_movement": "fast track", "subject_movement": "ball enters net", "background_motion": "crowd erupts", "next_transition": "final hold", **_shot_creative_fields(final=True)},
                    ]
                }
            )
        raise AssertionError("unexpected schema")

    monkeypatch.setattr(ai_planning, "run_codex_exec", fake_run)
    assert video_phase2.develop_story(project.id, db, force=True) is not None
    assert video_phase2.approve_story(project.id, True, db) is not None
    shots = video_phase2.generate_shots(project.id, db)

    assert len(shots) == 2
    assert len(shots[0].micro_scenes) == 3
    assert shots[0].micro_scenes[0].description_vi.startswith("cầu thủ nhìn")
    assert shots[1].micro_scenes[-1].end_seconds == pytest.approx(10)

def test_phase2_configured_prompt_segments_reject_incomplete_codex_output(db, monkeypatch):
    project = video_projects.create_project(
        models.VideoProjectCreate(
            topic="Incomplete configured prompt output",
            phase="phase2",
            prompt_segment_count=1,
            prompt_segment_duration_seconds=10,
            micro_scenes_per_prompt=3,
            source_blocks=[models.VideoSourceBlockDraft(block_type="idea", content="Bad output should fail.")],
        ),
        db,
    )
    project_row = db.query(database.VideoProject).filter(database.VideoProject.id == project.id).first()
    assert project_row is not None
    project_row.story_approved = True
    project_row.script_approved = True
    project_row.status = "story_approved"
    db.add(database.VideoScene(project_id=project.id, scene_order=1, title="Bad", dialogue="", visual_description="Bad"))
    db.commit()

    def fake_run(settings, prompt, *, output_schema, timeout_seconds=None, cwd=None):
        assert output_schema == video_phase2.SHOT_BREAKDOWN_SCHEMA
        return json.dumps({"segments": [{"segment_order": 1}]})

    monkeypatch.setattr(ai_planning, "run_codex_exec", fake_run)
    monkeypatch.setattr(video_phase2, "RETRY_DELAY_SECONDS", 0)

    with pytest.raises(video_planning.VideoPlanningValidationError):
        video_phase2.generate_shots(project.id, db)

    assert db.query(DBVideoShot).filter(DBVideoShot.project_id == project.id).count() == 0

def test_phase2_target_duration_creates_ten_second_prompt_segments(db, monkeypatch):
    project = video_projects.create_project(
        models.VideoProjectCreate(
            topic="Một video 25 giây về founder chốt hợp đồng",
            phase="phase2",
            target_duration_seconds=25,
            aspect_ratio="9:16",
            source_blocks=[models.VideoSourceBlockDraft(block_type="idea", content="Founder receives good news and closes a deal.")],
        ),
        db,
    )

    def fake_run(settings, prompt, *, output_schema, timeout_seconds=None, cwd=None):
        if output_schema == video_phase2.STORY_DEVELOPMENT_SCHEMA:
            return json.dumps(
                {
                    "input_synthesis": "Founder closes a deal in one evening.",
                    "story_strategy": "Hook, pressure, reveal, payoff.",
                    "continuity_bible": "Same founder, same navy jacket, warm cafe lighting.",
                    "detailed_script": "The founder receives a message, meets the client, and signs.",
                    **_creative_direction_fields(),
                    "scenes": [
                        {
                            "title": "Deal night",
                            "vietnamese_description": "Founder trong quán cà phê chốt hợp đồng.",
                            "english_narration": "One message changed the night.",
                            **_scene_detail_fields(
                                character_appearance="Vietnamese founder, short black hair, focused face.",
                                wardrobe_and_sandals="Navy jacket, white shirt, leather shoes; sandals not visible.",
                                setting_and_lighting="Warm cafe at night with rain on the window.",
                            ),
                            "target_duration_seconds": 25,
                        }
                    ],
                }
            )
        if output_schema == video_phase2.SHOT_BREAKDOWN_SCHEMA:
            assert "Tạo đúng 3 prompt segment" in prompt
            assert "đúng 3 micro_scenes" in prompt
            assert "vietnamese_description phải là bản tiếng Việt để duyệt" in prompt
            assert "bản tiếng Việt để duyệt" in prompt
            assert "giải thích nội dung narration" in prompt
            assert "english_narration phải là voiceover dài hơn" in prompt
            assert "Không viết tagline/câu cụt" in prompt
            return json.dumps(
                {
                    "shots": [
                        {
                            "scene_order": 1,
                            "shot_order": 1,
                            "duration_seconds": 3,
                            "vietnamese_description": "0-10s: điện thoại báo tin, founder đổi nét mặt, nhìn về hợp đồng.",
                            "english_narration": "The answer finally arrives.",
                            "primary_action": "Phone notification shifts the founder from tension to resolve.",
                            "purpose": "Hook and setup.",
                            "shot_type": "micro montage segment",
                            "camera_angle": "overhead to eye level",
                            "framing": "phone close-up to medium shot",
                            "composition": "phone foreground, founder and contract revealed",
                            "camera_motion": "slow dolly back",
                            "subject_motion": "0-3s phone buzzes; 3-7s founder reads; 7-10s contract is revealed.",
                            "environment_motion": "rain slides down cafe glass",
                            "transition_to_next": "match cut from contract edge to client hand",
                            **_shot_creative_fields(role="cold open"),
                        },
                        {
                            "scene_order": 1,
                            "shot_order": 2,
                            "duration_seconds": 3,
                            "vietnamese_description": "10-20s: khách hàng đến, hai người trao đổi, bút đặt lên hợp đồng.",
                            "english_narration": "The room becomes quiet.",
                            "primary_action": "Client and founder align over the contract.",
                            "purpose": "Build trust.",
                            "shot_type": "dialogue segment",
                            "camera_angle": "side angle",
                            "framing": "two-shot to hand detail",
                            "composition": "client and founder balanced across the table",
                            "camera_motion": "subtle handheld drift",
                            "subject_motion": "0-3s client sits; 3-7s they nod; 7-10s pen moves into frame.",
                            "environment_motion": "cafe light flickers softly",
                            "transition_to_next": "cut on pen touching paper",
                            **_shot_creative_fields(role="build-up"),
                        },
                        {
                            "scene_order": 1,
                            "shot_order": 3,
                            "duration_seconds": 3,
                            "vietnamese_description": "20-25s: chữ ký hoàn tất, bắt tay, giữ hình hợp đồng đã ký.",
                            "english_narration": "By midnight, it was real.",
                            "primary_action": "The contract is signed and the founder smiles.",
                            "purpose": "Payoff.",
                            "shot_type": "payoff segment",
                            "camera_angle": "low table angle",
                            "framing": "signed contract close-up to two-shot",
                            "composition": "signature foreground, handshake behind it",
                            "camera_motion": "gentle push-in",
                            "subject_motion": "0-3s signature finishes; 3-7s handshake; 7-10s hold for trim.",
                            "environment_motion": "rain and warm reflections continue",
                            "transition_to_next": "final hold",
                            **_shot_creative_fields(final=True, role="payoff"),
                        },
                    ]
                }
            )
        if output_schema == video_phase2.VIDEO_PROMPT_PACK_SCHEMA:
            assert "Segment X of 3" in prompt
            return json.dumps(
                {
                    "global_continuity": "Same founder, same navy jacket, same warm cafe night.",
                    "negative_prompt_global": "No text overlay, no watermark, no extra characters.",
                    "prompts": [
                        {"shot_order": 1, "prompt": "Founder receives the message and reveals the contract.", "prompt_explanation_vi": "Founder nhận tin nhắn, đổi biểu cảm và hé lộ hợp đồng trên bàn.", "duration_seconds": 10, **_prompt_creative_fields()},
                        {"shot_order": 2, "prompt": "Founder and client discuss the deal over the table.", "prompt_explanation_vi": "Founder và khách hàng trao đổi thương vụ qua bàn cà phê, nhịp chuyển sang cây bút.", "duration_seconds": 10, **_prompt_creative_fields()},
                        {"shot_order": 3, "prompt": "The contract is signed and held for the ending.", "prompt_explanation_vi": "Hợp đồng được ký, hai người bắt tay và giữ khung hình kết thúc.", "duration_seconds": 5, **_prompt_creative_fields()},
                    ],
                }
            )
        raise AssertionError("unexpected schema")

    monkeypatch.setattr(ai_planning, "run_codex_exec", fake_run)

    assert video_phase2.develop_story(project.id, db, force=True) is not None
    assert video_phase2.approve_story(project.id, True, db) is not None
    shots = video_phase2.generate_shots(project.id, db)

    assert shots is not None
    assert [shot.duration_seconds for shot in shots] == [10, 10, 5]

    pack = video_phase2.generate_video_prompt_pack(project.id, db)

    assert pack is not None
    assert len(pack.prompts) == 3
    assert "Create a 10-second 9:16 cinematic video" in pack.prompts[0].prompt
    assert "segment 1 of 3" in pack.prompts[0].prompt.lower()
    assert "first 5 seconds" in pack.prompts[2].prompt

def test_phase2_story_shots_prompt_video_logging_and_zip(db, monkeypatch):
    project = video_projects.create_project(
        models.VideoProjectCreate(
            topic="Một video World Cup về cú lội ngược dòng",
            title="World Cup comeback",
            language="vi",
            target_language="en",
            aspect_ratio="9:16",
            voice_profile_id="profile-1",
            phase="phase2",
            source_blocks=[
                models.VideoSourceBlockDraft(block_type="idea", content="Kể câu chuyện một đội bóng bị dẫn trước rồi thắng phút cuối."),
                models.VideoSourceBlockDraft(block_type="avoid", content="Không dùng giọng văn quảng cáo."),
            ],
        ),
        db,
    )
    blocks = video_phase2.list_source_blocks(project.id, db)
    assert blocks is not None
    assert len(blocks) == 2
    updated = video_phase2.update_source_block(
        project.id,
        blocks[0].id,
        models.VideoSourceBlockUpdate(content="World Cup comeback with emotional final-minute goal."),
        db,
    )
    assert updated is not None
    assert "World Cup" in updated.content

    created_block = video_phase2.create_source_block(
        project.id,
        models.VideoSourceBlockCreate(block_type="style_notes", content="Fast cuts, rain, tense stadium close-ups."),
        db,
    )
    assert created_block is not None
    assert created_block.sort_order == 3

    reordered = video_phase2.reorder_source_blocks(
        project.id,
        models.VideoSourceBlockReorderRequest(block_ids=[created_block.id, blocks[1].id, blocks[0].id]),
        db,
    )
    assert reordered is not None
    assert [block.id for block in reordered[:3]] == [created_block.id, blocks[1].id, blocks[0].id]
    assert [block.sort_order for block in reordered[:3]] == [1, 2, 3]

    assert video_phase2.delete_source_block(project.id, blocks[1].id, db) is True
    remaining_block_ids = [block.id for block in video_phase2.list_source_blocks(project.id, db)]
    assert blocks[1].id not in remaining_block_ids

    def fake_run(settings, prompt, *, output_schema, timeout_seconds=None, cwd=None):
        assert timeout_seconds is not None
        assert timeout_seconds >= video_phase2.PHASE2_DEFAULT_CODEX_TIMEOUT_SECONDS
        if output_schema == video_phase2.STORY_DEVELOPMENT_SCHEMA:
            return json.dumps(
                {
                    "input_synthesis": "A Vietnamese user wants an English football comeback story.",
                    "story_strategy": "Open with defeat, build tension, end with a final-minute goal.",
                    "continuity_bible": "Same stadium, same captain, rain, blue kit, cinematic handheld camera.",
                    "detailed_script": "The captain looks at the scoreboard, breathes, and leads one last attack.",
                    **_creative_direction_fields(),
                    "scenes": [
                        {
                            "title": "The impossible score",
                            "vietnamese_description": "Đội bóng bị dẫn trước trong mưa, khán giả căng thẳng.",
                            "english_narration": "Down by two goals, the captain refuses to let the dream end.",
                            **_scene_detail_fields(
                                character_appearance="Athletic male football captain with wet short dark hair, focused eyes, strong jaw, and a determined expression.",
                                wardrobe_and_sandals="Blue football kit with white trim, soaked jersey fabric, cleats visible; sandals not used because this is a football match.",
                                subject_motion_by_duration="The captain lifts his head, exhales, and takes one determined step forward within the configured shot duration.",
                                setting_and_lighting="Rainy night stadium, cold blue-white floodlights, wet grass reflections, high contrast cinematic atmosphere.",
                                detailed_mood="Tense but hopeful, pressure-heavy, heroic resolve building behind controlled fear.",
                            ),
                            "target_duration_seconds": 8,
                        }
                    ],
                }
            )
        if output_schema == video_phase2.SHOT_BREAKDOWN_SCHEMA:
            return json.dumps(
                {
                    "shots": [
                        {
                            "scene_order": 1,
                            "shot_order": 1,
                            "duration_seconds": 2,
                            "vietnamese_description": "Cận cảnh bảng tỷ số dưới mưa.",
                            "english_narration": "Two goals down.",
                            "primary_action": "The scoreboard flickers in rain.",
                            "purpose": "Hook the audience with pressure.",
                            "shot_type": "detail shot",
                            "camera_angle": "low angle",
                            "framing": "tight close-up",
                            "composition": "scoreboard dominates the top third",
                            "camera_motion": "slow push-in",
                            "subject_motion": "rain runs over the numbers",
                            "environment_motion": "crowd waves in the background",
                            "transition_to_next": "match cut from numbers to the captain's eyes",
                            **_shot_creative_fields(role="cold open"),
                        },
                        {
                            "scene_order": 1,
                            "shot_order": 2,
                            "duration_seconds": 3,
                            "vietnamese_description": "Cận cảnh đội trưởng nhìn lên khán đài.",
                            "english_narration": "But the captain still believes.",
                            "primary_action": "The captain lifts his head with resolve.",
                            "purpose": "Create emotional connection.",
                            "shot_type": "close-up",
                            "camera_angle": "eye level",
                            "framing": "face close-up",
                            "composition": "captain centered with blurred crowd lights",
                            "camera_motion": "handheld micro drift",
                            "subject_motion": "the captain exhales and nods",
                            "environment_motion": "stadium lights shimmer through rain",
                            "transition_to_next": "cut on his nod into forward movement",
                            **_shot_creative_fields(final=True, role="payoff"),
                        },
                    ]
                }
            )
        return json.dumps(
            {
                "prompts": [
                    {
                        "shot_order": 1,
                        "prompt": "Create a 2-second vertical 9:16 cinematic video of a rain-soaked football scoreboard showing a two-goal deficit, tense stadium atmosphere.",
                        "prompt_explanation_vi": "Prompt yêu cầu cận cảnh bảng tỷ số dưới mưa, không khí sân vận động căng thẳng và camera đẩy chậm.",
                        "negative_prompt": "No text overlay, no watermark, no distorted faces, no flicker, no extra players in frame.",
                        "duration_seconds": 2,
                        "aspect_ratio": "9:16",
                        "shot_type": "detail shot",
                        "camera_angle": "low angle",
                        "framing": "tight close-up",
                        "composition": "scoreboard dominates the top third",
                        "camera_motion": "slow push-in",
                        "subject_motion": "rain runs over the numbers",
                        "environment_motion": "crowd waves behind the scoreboard",
                        "start_frame": "Dark scoreboard in rain",
                        "end_frame": "Scoreboard fills the frame",
                        "lighting": "cold stadium lights",
                        "mood": "tense and dramatic",
                        "continuity_notes": "Same rainy stadium, blue kit team, cinematic handheld realism.",
                        **_prompt_creative_fields(),
                        "quality_check": {"passed": True},
                    },
                    {
                        "shot_order": 2,
                        "prompt": "Create a 3-second vertical 9:16 cinematic close-up of the team captain in a blue kit lifting his head with determination under rain and stadium lights.",
                        "prompt_explanation_vi": "Prompt yêu cầu cận cảnh đội trưởng áo xanh ngẩng đầu quyết tâm dưới mưa và ánh đèn sân vận động.",
                        "negative_prompt": "No subtitles, no watermark, no distorted hands, no extra faces, no unstable camera shake.",
                        "duration_seconds": 3,
                        "aspect_ratio": "9:16",
                        "shot_type": "close-up",
                        "camera_angle": "eye level",
                        "framing": "face close-up",
                        "composition": "captain centered with blurred crowd lights",
                        "camera_motion": "handheld micro drift",
                        "subject_motion": "the captain exhales and nods",
                        "environment_motion": "stadium lights shimmer through rain",
                        "start_frame": "Captain looking down",
                        "end_frame": "Captain looking up with resolve",
                        "lighting": "cool stadium rim light",
                        "mood": "hopeful tension",
                        "continuity_notes": "Same captain, same blue kit, rainy stadium, cinematic handheld realism.",
                        **_prompt_creative_fields(),
                        "quality_check": {"passed": True},
                    },
                ]
            }
        )

    monkeypatch.setattr(ai_planning, "run_codex_exec", fake_run)

    story = video_phase2.develop_story(project.id, db, force=True)
    assert story is not None
    assert story.story_strategy.startswith("Open with defeat")
    assert len(story.scenes) == 1

    approved = video_phase2.approve_story(project.id, True, db)
    assert approved is not None
    assert approved.story_approved is True

    shots = video_phase2.generate_shots(project.id, db)
    assert shots is not None
    assert len(shots) == 2
    assert all(1 <= (shot.duration_seconds or 0) <= 5 for shot in shots)
    assert video_phase2.validate_shot_variation(db.query(DBVideoShot).filter(DBVideoShot.project_id == project.id).all()) is True

    original_description = shots[0].vietnamese_description
    locked = video_phase2.set_shot_locked(project.id, shots[0].id, True, db)
    assert locked is not None
    assert locked.locked is True

    def fail_if_locked_regenerates(settings, prompt, *, output_schema, timeout_seconds=None, cwd=None):
        raise AssertionError("locked shot should not call Codex")

    monkeypatch.setattr(ai_planning, "run_codex_exec", fail_if_locked_regenerates)
    locked_regenerate = video_phase2.regenerate_shot(project.id, shots[0].id, db)
    assert locked_regenerate is not None
    assert locked_regenerate.vietnamese_description == original_description
    assert locked_regenerate.locked is True

    unlocked = video_phase2.set_shot_locked(project.id, shots[0].id, False, db)
    assert unlocked is not None
    assert unlocked.locked is False

    def fake_regenerate(settings, prompt, *, output_schema, timeout_seconds=None, cwd=None):
        assert timeout_seconds is not None
        assert timeout_seconds >= video_phase2.PHASE2_DEFAULT_CODEX_TIMEOUT_SECONDS
        assert output_schema == video_phase2.SHOT_BREAKDOWN_SCHEMA
        assert "english_narration phải dài hơn một câu ngắn" in prompt
        return json.dumps(
            {
                "shots": [
                    {
                        "scene_order": 1,
                        "shot_order": 1,
                        "duration_seconds": 4,
                        "vietnamese_description": "Đội trưởng lao về phía khung thành trong mưa.",
                        "english_narration": "One last run begins.",
                        "primary_action": "The captain sprints into open space.",
                        "purpose": "Raise momentum before the payoff.",
                        "shot_type": "tracking shot",
                        "camera_angle": "side angle",
                        "framing": "medium wide",
                        "composition": "captain crosses from left to right through rain",
                        "camera_motion": "fast lateral track",
                        "subject_motion": "captain accelerates with the ball",
                        "environment_motion": "rain and crowd lights streak behind him",
                        "transition_to_next": "cut on the forward kick",
                        **_shot_creative_fields(final=True, role="climax"),
                    }
                ]
            }
        )

    monkeypatch.setattr(ai_planning, "run_codex_exec", fake_regenerate)
    regenerated_shot = video_phase2.regenerate_shot(project.id, shots[0].id, db)
    assert regenerated_shot is not None
    assert regenerated_shot.vietnamese_description.startswith("Đội trưởng lao")
    assert regenerated_shot.prompt_status == "stale"

    def fake_bad_prompt(settings, prompt, *, output_schema, timeout_seconds=None, cwd=None):
        assert timeout_seconds is not None
        assert timeout_seconds >= video_phase2.PHASE2_DEFAULT_CODEX_TIMEOUT_SECONDS
        if output_schema == video_phase2.VIDEO_PROMPT_PACK_SCHEMA:
            return json.dumps(
                {
                    "prompts": [
                        {
                            "shot_order": 1,
                            "prompt": "Create a short football video.",
                            "duration_seconds": 2,
                            "aspect_ratio": "9:16",
                        }
                    ]
                }
            )
        return fake_run(settings, prompt, output_schema=output_schema, timeout_seconds=timeout_seconds, cwd=cwd)

    monkeypatch.setattr(ai_planning, "run_codex_exec", fake_bad_prompt)
    with pytest.raises(video_planning.VideoPlanningValidationError):
        video_phase2.generate_video_prompt_pack(project.id, db)
    blocked_readiness = video_packages.get_package_readiness(project.id, db)
    assert blocked_readiness.ready is False
    assert shots[0].id in blocked_readiness.missing_video_prompt_shot_ids

    monkeypatch.setattr(ai_planning, "run_codex_exec", fake_run)

    pack = video_phase2.generate_video_prompt_pack(project.id, db)
    assert pack is not None
    assert len(pack.prompts) == 2
    assert all(prompt.quality_status == "passed" for prompt in pack.prompts)
    content = video_phase2.get_video_prompt_content(project.id, shots[0].id, db)
    assert content is not None
    assert content.filename.startswith("Prompt video")
    assert "Create a 2-second" in content.content
    assert "Bản giải thích tiếng Việt" not in content.content
    assert "bảng tỷ số dưới mưa" in (content.prompt_explanation_vi or "")
    assert content.retention_notes
    assert content.transition_notes
    assert content.sound_design_notes
    prompt_download = video_phase2.get_video_prompt_download(project.id, shots[0].id, db)
    assert prompt_download is not None
    assert prompt_download[0].startswith("Prompt video")
    assert "# Prompt gốc" in prompt_download[1]
    assert "Retention:" in prompt_download[1]
    assert "Chuyển cảnh:" in prompt_download[1]
    assert "Âm thanh/SFX:" in prompt_download[1]
    assert "Bản giải thích tiếng Việt" in prompt_download[1]
    assert "bảng tỷ số dưới mưa" in prompt_download[1]

    shot_table = database.VideoShot.__table__
    for index, shot in enumerate(shots, start=1):
        audio_path = config.get_generations_dir() / f"phase2-shot-{index}.wav"
        audio_path.write_bytes(b"fake wav data")
        db.execute(
            shot_table.update()
            .where(shot_table.c.id == shot.id)
            .values(voice_status="completed", audio_path=config.to_storage_path(audio_path), audio_duration=2.0 + index)
        )
    db.commit()
    subtitle = video_subtitles.generate_subtitle(project.id, db)
    assert subtitle.status == "completed"
    assert subtitle.cues[0].shot_id == shots[0].id

    readiness = video_packages.get_package_readiness(project.id, db)
    assert readiness.ready is True
    assert readiness.missing_video_prompt_shot_ids == []
    assert readiness.missing_voice_shot_ids == []

    package = video_packages.create_package(project.id, db)
    assert package.status == "completed"
    download = video_packages.get_package_download(project.id, db)
    assert download is not None
    with zipfile.ZipFile(download[1]) as archive:
        names = set(archive.namelist())
        guide_text = archive.read(next(name for name in names if name.endswith("00 - Huong dan.txt"))).decode("utf-8")
        creative_text = archive.read(next(name for name in names if "Creative direction" in name)).decode("utf-8")
        prompt_texts = [
            archive.read(name).decode("utf-8")
            for name in names
            if "02 - Prompt video" in name and name.endswith(".txt")
        ]
    assert any("02 - Prompt video" in name and name.endswith(".txt") for name in names)
    assert any("03 - Giong doc" in name and name.endswith(".wav") for name in names)
    assert any("Segment list" in name and name.endswith(".csv") for name in names)
    assert any("Continuity bible.txt" in name for name in names)
    assert any("Creative direction" in name for name in names)
    assert "Ban giai thich tieng Viet" in guide_text
    assert "SFX/BGM" in guide_text
    assert "khong phai file phu de .srt" in guide_text
    assert "Retention map" in creative_text
    assert "Sound/SFX" in creative_text
    assert all("Bản giải thích tiếng Việt" in prompt_text for prompt_text in prompt_texts)
    assert all("Am thanh/SFX" in prompt_text for prompt_text in prompt_texts)
    assert any("bảng tỷ số dưới mưa" in prompt_text for prompt_text in prompt_texts)

def test_phase2_prompt_invalid_codex_output_preserves_existing_prompt(db, monkeypatch):
    project = video_projects.create_project(models.VideoProjectCreate(topic="Invalid prompt output", phase="phase2"), db)
    shot = _add_phase2_shot(db, project.id, order=1, narration="Keep going.", voice_completed=False)
    prompt_dir = video_storage.get_project_subdir(project.id, "video_prompts")
    old_prompt_path = prompt_dir / "old-prompt.txt"
    old_prompt_path.write_text("Old prompt", encoding="utf-8")
    old_prompt = DBVideoShotPrompt(
        project_id=project.id,
        shot_id=shot.id,
        version=1,
        prompt="Old prompt",
        prompt_explanation_vi="Bản cũ vẫn hợp lệ.",
        prompt_path=video_storage.to_artifact_storage_path(old_prompt_path),
        quality_status="passed",
        quality_check={"passed": True},
    )
    db.add(old_prompt)
    shot.prompt_status = "completed"
    db.commit()

    def fake_run(settings, prompt, *, output_schema, timeout_seconds=None, cwd=None):
        assert output_schema == video_phase2.VIDEO_PROMPT_PACK_SCHEMA
        return "not json at all"

    monkeypatch.setattr(ai_planning, "run_codex_exec", fake_run)
    monkeypatch.setattr(video_phase2, "RETRY_DELAY_SECONDS", 0)

    with pytest.raises(video_planning.VideoPlanningValidationError):
        video_phase2.generate_video_prompt_pack(project.id, db)

    prompts = db.query(DBVideoShotPrompt).filter(DBVideoShotPrompt.shot_id == shot.id).all()
    assert len(prompts) == 1
    assert prompts[0].prompt == "Old prompt"
    db.refresh(shot)
    assert shot.prompt_status == "completed"

    debug = video_debug.get_project_debug_details(project.id, db)
    assert debug is not None
    assert debug["artifact_status"]["video_prompts"] == 1
    assert any(event["step_name"] == "video_prompt_validation" and event["status"] == "failure" for event in debug["events"])

def test_phase2_legacy_prompt_without_vietnamese_explanation_still_downloads(db):
    project = video_projects.create_project(
        models.VideoProjectCreate(topic="Legacy prompt", phase="phase2", target_language="en", aspect_ratio="9:16"),
        db,
    )
    shot = _add_phase2_shot(db, project.id, order=1, narration="A legacy narration.", duration_seconds=3)
    prompt = DBVideoShotPrompt(
        id="legacy-prompt-no-explanation",
        project_id=project.id,
        shot_id=shot.id,
        version=1,
        prompt="Create a 3-second legacy video prompt.",
        negative_prompt="No watermark.",
        duration_seconds=3,
        aspect_ratio="9:16",
        quality_status="passed",
        quality_check={"passed": True, "missing_fields": []},
    )
    db.add(prompt)
    db.commit()

    content = video_phase2.get_video_prompt_content(project.id, shot.id, db)
    assert content is not None
    assert content.content == "Create a 3-second legacy video prompt."
    assert content.prompt_explanation_vi is None

    download = video_phase2.get_video_prompt_download(project.id, shot.id, db)
    assert download is not None
    assert "Create a 3-second legacy video prompt." in download[1]
    assert "Bản giải thích tiếng Việt" in download[1]
    assert "Chưa có bản giải thích tiếng Việt riêng" in download[1]

def test_phase2_rejects_low_variation_shots():
    repeated = [
        video_phase2.ShotPlan(
            scene_order=1,
            shot_order=1,
            camera_angle="eye level",
            framing="medium",
            composition="centered",
            camera_motion="static",
        ),
        video_phase2.ShotPlan(
            scene_order=1,
            shot_order=2,
            camera_angle="eye level",
            framing="medium",
            composition="centered",
            camera_motion="static",
        ),
    ]
    assert video_phase2.validate_shot_variation(repeated) is False

def test_phase2_debug_log_redacts_secrets(db):
    project = video_projects.create_project(
        models.VideoProjectCreate(topic="Debug project", phase="phase2"),
        db,
    )
    event = video_observability.log_event(
        db,
        project_id=project.id,
        step_name="debug_redaction",
        status="failure",
        error_code="TEST_ERROR",
        technical_details={"api_key": "secret-value", "message": "bearer abc123 should hide"},
        message="token=abc123 should hide",
    )
    assert "secret-value" not in (event.technical_details or "")
    assert "abc123" not in (event.technical_details or "")
    assert "abc123" not in (event.message or "")

def test_video_planning_pool_concurrency_config(monkeypatch):
    video_planning_pool.reset_for_tests()
    monkeypatch.delenv(video_planning_pool.CONCURRENCY_ENV, raising=False)
    assert video_planning_pool.get_max_concurrency() == 3

    monkeypatch.setenv(video_planning_pool.CONCURRENCY_ENV, "1")
    video_planning_pool.reset_for_tests()
    assert video_planning_pool.get_max_concurrency() == 1

    monkeypatch.setenv(video_planning_pool.CONCURRENCY_ENV, "3")
    video_planning_pool.reset_for_tests()
    assert video_planning_pool.get_max_concurrency() == 3

    monkeypatch.setenv(video_planning_pool.CONCURRENCY_ENV, "bad")
    video_planning_pool.reset_for_tests()
    assert video_planning_pool.get_max_concurrency() == 3

    monkeypatch.setenv(video_planning_pool.CONCURRENCY_ENV, "0")
    video_planning_pool.reset_for_tests()
    assert video_planning_pool.get_max_concurrency() == 3

    video_planning_pool.reset_for_tests()

def test_video_planning_pool_runs_two_projects_and_blocks_third(db, monkeypatch):
    monkeypatch.setenv(video_planning_pool.CONCURRENCY_ENV, "2")
    video_planning_pool.reset_for_tests()
    monkeypatch.setattr(video_planning_pool, "_log_event_safely", lambda *args, **kwargs: None)

    entered: list[str] = []
    entered_lock = threading.Lock()
    first_entered = threading.Event()
    second_entered = threading.Event()
    third_entered = threading.Event()
    first_release = threading.Event()
    second_release = threading.Event()
    third_release = threading.Event()

    def worker(project_id: str, entered_event: threading.Event, release_event: threading.Event):
        with video_planning_pool.planning_slot(db, project_id=project_id, step_name="test_step"):
            with entered_lock:
                entered.append(project_id)
            entered_event.set()
            assert release_event.wait(2), f"release timed out for {project_id}"

    threads = [
        threading.Thread(target=worker, args=("project-1", first_entered, first_release)),
        threading.Thread(target=worker, args=("project-2", second_entered, second_release)),
        threading.Thread(target=worker, args=("project-3", third_entered, third_release)),
    ]
    try:
        threads[0].start()
        threads[1].start()
        assert first_entered.wait(2)
        assert second_entered.wait(2)
        threads[2].start()
        time.sleep(0.15)
        assert not third_entered.is_set()
        snapshot = video_planning_pool.snapshot()
        assert snapshot.active_count == 2
        assert snapshot.waiting_count == 1

        first_release.set()
        assert third_entered.wait(2)
        assert entered[:2] == ["project-1", "project-2"]
        assert entered[2] == "project-3"
    finally:
        first_release.set()
        second_release.set()
        third_release.set()
        for thread in threads:
            thread.join(2)
        video_planning_pool.reset_for_tests()

def test_video_planning_pool_rejects_duplicate_project_before_work(db, monkeypatch):
    monkeypatch.setattr(video_planning_pool, "_log_event_safely", lambda *args, **kwargs: None)
    video_planning_pool.reset_for_tests()
    second_started = False

    with video_planning_pool.planning_slot(db, project_id="same-project", step_name="story_development"):
        with pytest.raises(video_planning_pool.ProjectPlanningActiveError) as exc_info:
            with video_planning_pool.planning_slot(db, project_id="same-project", step_name="video_prompt_generation"):
                second_started = True

    assert second_started is False
    assert exc_info.value.error_code == "AI_VIDEO_PLANNING_PROJECT_ACTIVE"
    assert "đang có bước AI planning" in str(exc_info.value)
    assert video_planning_pool.snapshot().active_count == 0

@pytest.mark.parametrize(
    "exc",
    [
        ai_planning.AIPlanningError("Codex CLI bị timeout khi tạo nội dung.", error_code="CODEX_EXEC_TIMEOUT"),
        video_planning.VideoPlanningValidationError("Codex output is not JSON."),
        RuntimeError("unexpected planning failure"),
    ],
)
def test_video_planning_pool_releases_after_errors(db, monkeypatch, exc):
    monkeypatch.setattr(video_planning_pool, "_log_event_safely", lambda *args, **kwargs: None)
    video_planning_pool.reset_for_tests()

    with pytest.raises(exc.__class__):
        with video_planning_pool.planning_slot(db, project_id="error-project", step_name="test_step"):
            raise exc

    snapshot = video_planning_pool.snapshot()
    assert snapshot.active_count == 0
    assert snapshot.waiting_count == 0
    with video_planning_pool.planning_slot(db, project_id="error-project", step_name="retry_step"):
        assert video_planning_pool.snapshot().active_count == 1

def test_video_planning_pool_logs_error_and_release_failure(db):
    project = video_projects.create_project(models.VideoProjectCreate(topic="Planning pool error logs", phase="phase2"), db)

    with pytest.raises(RuntimeError):
        with video_planning_pool.planning_slot(
            db,
            project_id=project.id,
            step_name="video_prompt_generation",
            provider="codex-cli",
            model="test-model",
            details={"prompt_chars": 123, "schema_keys": ["prompts"]},
        ):
            raise RuntimeError("simulated planning failure")

    events = video_observability.latest_events(project.id, db, limit=10)
    error_event = next(event for event in events if event.step_name == "codex_planning_error")
    release_event = next(event for event in events if event.step_name == "codex_planning_released")
    assert error_event.status == "failure"
    assert error_event.error_code == "CODEX_PLANNING_FAILED"
    assert "simulated planning failure" in (error_event.message or "")
    assert release_event.status == "failure"
    assert video_planning_pool.snapshot().active_count == 0

def test_video_planning_pool_debug_event_redacts_prompt_and_secret(db):
    project = video_projects.create_project(models.VideoProjectCreate(topic="Planning pool logs", phase="phase2"), db)
    long_prompt = "FULL_PROMPT_SHOULD_NOT_BE_STORED " * 40

    with video_planning_pool.planning_slot(
        db,
        project_id=project.id,
        step_name="video_prompt_generation",
        provider="codex-cli",
        model="test-model",
        details={"prompt_preview": long_prompt, "prompt_chars": len(long_prompt), "api_key": "secret-value"},
    ):
        pass

    events = video_observability.latest_events(project.id, db, limit=10)
    pool_events = [event for event in events if event.step_name.startswith("codex_planning_")]
    assert {event.step_name for event in pool_events} >= {"codex_planning_acquired", "codex_planning_completed", "codex_planning_released"}
    details_blob = "\n".join(event.technical_details or "" for event in pool_events)
    assert long_prompt not in details_blob
    assert "secret-value" not in details_blob
    assert "prompt_chars" in details_blob

def test_phase2_prompt_pack_uses_one_full_codex_call_and_not_tts_queue(db, monkeypatch):
    project = _ready_phase2_project(db, topic="Full prompt pack")
    shot_one = _add_phase2_shot(db, project.id, order=1, narration="", duration_seconds=2)
    shot_two = _add_phase2_shot(db, project.id, order=2, narration="", duration_seconds=3)
    codex_calls: list[str] = []
    enqueued_generation_ids: list[str] = []

    def fake_enqueue(generation_id, coro):
        enqueued_generation_ids.append(generation_id)
        close = getattr(coro, "close", None)
        if close:
            close()

    def prompt_payload(order: int, duration: int, action: str) -> dict:
        return {
            "shot_order": order,
            "prompt": f"Create a {duration}-second 9:16 cinematic video. {action} Same character, same style, no text overlay.",
            "prompt_explanation_vi": f"Prompt mô tả segment {order} với hành động rõ và continuity nhất quán.",
            "negative_prompt": "No watermark, no wrong subtitles, no distorted hands.",
            "duration_seconds": duration,
            "aspect_ratio": "9:16",
            "shot_type": "medium shot",
            "camera_angle": "eye level",
            "framing": "centered subject",
            "composition": "balanced vertical frame",
            "camera_motion": "slow push-in",
            "subject_motion": action,
            "environment_motion": "soft background motion",
            "start_frame": "Subject starts in frame",
            "end_frame": "Subject finishes the action",
            "lighting": "soft cinematic light",
            "mood": "focused and clear",
            "continuity_notes": "Keep the same character, wardrobe, setting, and visual style across every shot.",
            **_prompt_creative_fields(),
        }

    def fake_run(settings, prompt, *, output_schema, timeout_seconds=None, cwd=None):
        assert output_schema == video_phase2.VIDEO_PROMPT_PACK_SCHEMA
        codex_calls.append(prompt)
        assert f"Shot {shot_one.shot_order}" in prompt
        assert f"Shot {shot_two.shot_order}" in prompt
        return json.dumps({"prompts": [prompt_payload(1, 2, "The subject opens the scene."), prompt_payload(2, 3, "The subject resolves the scene.")]})

    monkeypatch.setattr(ai_planning, "run_codex_exec", fake_run)
    monkeypatch.setattr(task_queue, "enqueue_generation", fake_enqueue)

    pack = video_phase2.generate_video_prompt_pack(project.id, db)

    assert pack is not None
    assert len(pack.prompts) == 2
    assert len(codex_calls) == 1
    assert enqueued_generation_ids == []

def test_manual_planning_endpoint_returns_vietnamese_conflict_when_project_active(db, monkeypatch):
    project = video_projects.create_project(
        models.VideoProjectCreate(
            topic="Manual conflict",
            phase="phase2",
            source_blocks=[models.VideoSourceBlockDraft(block_type="idea", content="Một ý tưởng video ngắn.")],
        ),
        db,
    )
    app = FastAPI()
    app.include_router(ai_video_router)
    from backend.database import get_db

    app.dependency_overrides[get_db] = lambda: db
    client = TestClient(app)
    codex_called = False

    def fake_run(settings, prompt, *, output_schema, timeout_seconds=None, cwd=None):
        nonlocal codex_called
        codex_called = True
        raise AssertionError("duplicate project should be rejected before Codex starts")

    monkeypatch.setattr(ai_planning, "run_codex_exec", fake_run)

    with video_planning_pool.planning_slot(db, project_id=project.id, step_name="auto_run_planning"):
        response = client.post(f"/ai-video/projects/{project.id}/story", json={"force": True})

    assert response.status_code == 409
    detail = response.json()["detail"]
    assert detail["error_code"] == "AI_VIDEO_PLANNING_PROJECT_ACTIVE"
    assert "đang có bước AI planning" in detail["message"]
    assert codex_called is False

def test_auto_run_third_project_waits_for_planning_slot_then_continues(db, monkeypatch):
    monkeypatch.setenv(video_planning_pool.CONCURRENCY_ENV, "2")
    video_planning_pool.reset_for_tests()
    monkeypatch.setattr(video_planning_pool, "_log_event_safely", lambda *args, **kwargs: None)
    _disable_auto_run_background(monkeypatch)
    _patch_auto_planning(monkeypatch)
    project = _ready_phase2_project(db, topic="Third waits", voice_profile_id="profile-1")
    _add_phase2_shot(db, project.id, order=1, narration="Ready narration.", duration_seconds=2, voice_completed=True, audio_duration=2.0)

    def fake_run(settings, prompt, *, output_schema, timeout_seconds=None, cwd=None):
        assert output_schema == video_phase2.VIDEO_PROMPT_PACK_SCHEMA
        return json.dumps(
            {
                "prompts": [
                    {
                        "shot_order": 1,
                        "prompt": "Create a 2-second 9:16 cinematic video. The subject finishes one clear action with consistent style.",
                        "prompt_explanation_vi": "Prompt yêu cầu một segment ngắn, rõ hành động và giữ continuity.",
                        "negative_prompt": "No watermark, no subtitles, no distorted hands.",
                        "duration_seconds": 2,
                        "aspect_ratio": "9:16",
                        "shot_type": "medium shot",
                        "camera_angle": "eye level",
                        "framing": "centered subject",
                        "composition": "balanced vertical frame",
                        "camera_motion": "slow push-in",
                        "subject_motion": "The subject completes one clear action.",
                        "environment_motion": "soft background motion",
                        "start_frame": "Subject starts in frame",
                        "end_frame": "Subject finishes the action",
                        "lighting": "soft cinematic light",
                        "mood": "focused and clear",
                        "continuity_notes": "Same character, setting, wardrobe, and visual style.",
                        **_prompt_creative_fields(),
                    }
                ]
            }
        )

    monkeypatch.setattr(ai_planning, "run_codex_exec", fake_run)
    run = _start_auto_run(db, project.id, mode="full_auto")
    assert run is not None

    first_slot = video_planning_pool.planning_slot(db, project_id="held-project-1", step_name="held_step")
    second_slot = video_planning_pool.planning_slot(db, project_id="held-project-2", step_name="held_step")
    first_slot.__enter__()
    second_slot.__enter__()
    result: dict[str, object] = {}

    def advance_run():
        try:
            result["action"] = video_auto_runs._advance_auto_run_sync(run.id)
        except BaseException as exc:
            result["error"] = exc

    thread = threading.Thread(target=advance_run)
    try:
        thread.start()
        deadline = time.monotonic() + 2
        row = None
        while time.monotonic() < deadline:
            db.expire_all()
            row = db.query(DBVideoAutoRun).filter(DBVideoAutoRun.id == run.id).first()
            if row is not None and row.status == "waiting_planning":
                break
            time.sleep(0.05)
        assert row is not None
        assert row.status == "waiting_planning"
        assert row.current_step == "waiting_planning"
        assert row.step_results_json["waiting_planning"]["step"] == "generate_prompts"

        first_slot.__exit__(None, None, None)
        first_slot = None
        thread.join(3)
        assert not thread.is_alive()
        assert "error" not in result

        db.expire_all()
        row = db.query(DBVideoAutoRun).filter(DBVideoAutoRun.id == run.id).first()
        assert row is not None
        assert row.status == "completed"
        assert "waiting_planning" not in row.step_results_json
        assert row.step_results_json["last_planning_wait"]["step"] == "generate_prompts"
        assert db.query(DBVideoShotPrompt).filter(DBVideoShotPrompt.project_id == project.id).count() == 1
    finally:
        if first_slot is not None:
            first_slot.__exit__(None, None, None)
        second_slot.__exit__(None, None, None)
        thread.join(1)
        video_planning_pool.reset_for_tests()

def _disable_auto_run_background(monkeypatch):
    def fake_background_task(coro):
        coro.close()
        return

    monkeypatch.setattr(video_auto_runs, "create_background_task", fake_background_task)

def _ready_phase2_project(db, *, topic: str = "Auto material", voice_profile_id: str | None = None) -> DBVideoProject:
    created = video_projects.create_project(
        models.VideoProjectCreate(topic=topic, phase="phase2", target_language="en", voice_profile_id=voice_profile_id),
        db,
    )
    project = db.query(DBVideoProject).filter(DBVideoProject.id == created.id).first()
    assert project is not None
    project.story_strategy = "Story strategy ready."
    project.continuity_bible = "Continuity ready."
    project.detailed_script = "Detailed script ready."
    project.story_approved = True
    project.planning_status = "prompts_ready"
    db.commit()
    db.refresh(project)
    return project

def _add_passed_prompt(db, project_id: str, shot: DBVideoShot, *, prompt_id: str | None = None) -> DBVideoShotPrompt:
    prompt = DBVideoShotPrompt(
        id=prompt_id or f"prompt-{shot.id}",
        project_id=project_id,
        shot_id=shot.id,
        version=1,
        prompt="Create a clean 2-second video prompt.",
        prompt_explanation_vi="Prompt đã đủ thông tin để duyệt.",
        negative_prompt="No watermark.",
        duration_seconds=shot.duration_seconds or 2,
        aspect_ratio="9:16",
        quality_status="passed",
        quality_check={"passed": True, "missing_fields": []},
    )
    shot.prompt_status = "completed"
    db.add(prompt)
    db.commit()
    db.refresh(prompt)
    return prompt

def _patch_auto_planning(monkeypatch):
    monkeypatch.setattr(video_auto_runs, "_ensure_planning_ready", lambda _db: None)

def _patch_auto_phase2_generation(monkeypatch):
    def fake_develop_story(project_id, session, force=False):
        project = session.query(DBVideoProject).filter(DBVideoProject.id == project_id).first()
        assert project is not None
        project.story_strategy = "Generated story."
        project.continuity_bible = "Generated continuity."
        project.detailed_script = "Generated script."
        project.planning_status = "story_ready"
        session.commit()
        return project

    def fake_generate_shots(project_id, session):
        shots = session.query(DBVideoShot).filter(DBVideoShot.project_id == project_id).all()
        if not shots:
            shot = DBVideoShot(
                project_id=project_id,
                shot_order=1,
                duration_seconds=2,
                english_narration="A concise narration line.",
                vietnamese_description="Một segment ngắn để duyệt.",
                status="ready",
                prompt_status="missing",
                voice_status="missing",
                subtitle_status="stale",
            )
            session.add(shot)
            session.commit()
            session.refresh(shot)
            return [shot]
        return shots

    def fake_generate_prompts(project_id, session):
        shot = session.query(DBVideoShot).filter(DBVideoShot.project_id == project_id).order_by(DBVideoShot.shot_order.asc()).first()
        assert shot is not None
        prompt = session.query(DBVideoShotPrompt).filter(DBVideoShotPrompt.shot_id == shot.id).first()
        if prompt is None:
            prompt = _add_passed_prompt(session, project_id, shot, prompt_id=f"auto-prompt-{shot.id}")
        else:
            shot.prompt_status = "completed"
            prompt.quality_status = "passed"
            session.commit()
        return models.VideoShotPromptPackResponse(
            project_id=project_id,
            prompts=[models.VideoShotPromptResponse.model_validate(prompt)],
        )

    monkeypatch.setattr(video_phase2, "develop_story", fake_develop_story)
    monkeypatch.setattr(video_phase2, "generate_shots", fake_generate_shots)
    monkeypatch.setattr(video_phase2, "generate_video_prompt_pack", fake_generate_prompts)

def _start_auto_run(
    db,
    project_id: str,
    *,
    mode: str = "review_gated",
    material_target: str = "full_materials",
    create_package: bool = False,
):
    payload = {"mode": mode, "material_target": material_target}
    if create_package:
        payload["create_package"] = True
    return asyncio.run(
        video_auto_runs.start_auto_run(
            project_id,
            models.VideoAutoRunStartRequest(**payload),
            db,
        )
    )

def test_auto_run_start_validation_and_active_guard(db, monkeypatch):
    _disable_auto_run_background(monkeypatch)
    _patch_auto_planning(monkeypatch)
    project = _ready_phase2_project(db)

    first = _start_auto_run(db, project.id, mode="review_gated")
    second = _start_auto_run(db, project.id, mode="full_auto")

    assert first is not None
    assert second is not None
    assert second.id == first.id
    assert db.query(DBVideoAutoRun).filter(DBVideoAutoRun.project_id == project.id).count() == 1
    assert asyncio.run(video_auto_runs.start_auto_run("missing-project", models.VideoAutoRunStartRequest(), db)) is None

    empty_project = _ready_phase2_project(db, topic="Temporary")
    empty_project.topic = ""
    db.query(DBVideoSourceBlock).filter(DBVideoSourceBlock.project_id == empty_project.id).update({"content": ""})
    db.commit()
    empty_run = _start_auto_run(db, empty_project.id, mode="full_auto")
    assert empty_run is not None
    video_auto_runs._advance_auto_run_sync(empty_run.id)
    db.expire_all()
    row = db.query(DBVideoAutoRun).filter(DBVideoAutoRun.id == empty_run.id).first()
    assert row is not None
    assert row.status == "needs_input"
    assert row.error_code == "VIDEO_AUTO_RUN_SOURCE_REQUIRED"

def test_auto_run_review_gated_stops_at_story_and_prompts(db, monkeypatch):
    _disable_auto_run_background(monkeypatch)
    _patch_auto_planning(monkeypatch)
    _patch_auto_phase2_generation(monkeypatch)
    project = video_projects.create_project(models.VideoProjectCreate(topic="Review gated source", phase="phase2"), db)
    run = _start_auto_run(db, project.id, mode="review_gated")
    assert run is not None

    video_auto_runs._advance_auto_run_sync(run.id)
    db.expire_all()
    row = db.query(DBVideoAutoRun).filter(DBVideoAutoRun.id == run.id).first()
    assert row is not None
    assert row.status == "needs_review"
    assert row.review_stage == "story"
    assert db.query(DBVideoShot).filter(DBVideoShot.project_id == project.id).count() == 0

    asyncio.run(video_auto_runs.continue_auto_run(project.id, run.id, models.VideoAutoRunContinueRequest(approved=True), db))
    video_auto_runs._advance_auto_run_sync(run.id)
    db.expire_all()
    row = db.query(DBVideoAutoRun).filter(DBVideoAutoRun.id == run.id).first()
    shots = db.query(DBVideoShot).filter(DBVideoShot.project_id == project.id).all()
    prompts = db.query(DBVideoShotPrompt).filter(DBVideoShotPrompt.project_id == project.id).all()
    assert row is not None
    assert row.status == "needs_review"
    assert row.review_stage == "prompts"
    assert len(shots) == 1
    assert len(prompts) == 1
    assert shots[0].voice_status == "missing"

def test_auto_run_full_auto_approves_reviews_but_requires_voice_profile(db, monkeypatch):
    _disable_auto_run_background(monkeypatch)
    _patch_auto_planning(monkeypatch)
    _patch_auto_phase2_generation(monkeypatch)
    project = video_projects.create_project(models.VideoProjectCreate(topic="Full auto source", phase="phase2"), db)
    run = _start_auto_run(db, project.id, mode="full_auto")
    assert run is not None

    video_auto_runs._advance_auto_run_sync(run.id)
    db.expire_all()
    row = db.query(DBVideoAutoRun).filter(DBVideoAutoRun.id == run.id).first()
    project_row = db.query(DBVideoProject).filter(DBVideoProject.id == project.id).first()
    assert row is not None
    assert project_row is not None
    assert row.status == "needs_input"
    assert row.error_code == "VIDEO_AUTO_RUN_VOICE_PROFILE_REQUIRED"
    assert row.review_stage is None
    assert project_row.story_approved is True
    assert row.step_results_json["reviewed"] == {"story": True, "prompts": True}

def test_project_status_reports_active_planning_step(db):
    project = video_projects.create_project(
        models.VideoProjectCreate(topic="Planning status source", phase="phase2"),
        db,
    )

    with video_planning_pool.planning_slot(db, project_id=project.id, step_name="story_development"):
        status = video_projects.get_project_status(project.id, db)

    assert status is not None
    assert status.planning_active is True
    assert status.planning_active_step == "story_development"

def test_auto_run_waits_when_same_project_planning_is_active(db, monkeypatch):
    _disable_auto_run_background(monkeypatch)
    _patch_auto_planning(monkeypatch)
    _patch_auto_phase2_generation(monkeypatch)
    project = video_projects.create_project(
        models.VideoProjectCreate(topic="Same project planning wait", phase="phase2"),
        db,
    )
    run = _start_auto_run(db, project.id, mode="full_auto", material_target="prompts_only")
    assert run is not None

    with video_planning_pool.planning_slot(db, project_id=project.id, step_name="story_development"):
        action = video_auto_runs._advance_auto_run_sync(run.id)
        db.expire_all()
        row = db.query(DBVideoAutoRun).filter(DBVideoAutoRun.id == run.id).first()
        assert action["action"] == "wait_planning"
        assert row is not None
        assert row.status == "waiting_planning"
        assert row.error_code is None
        assert row.step_results_json["waiting_planning"]["active_project_step"] == "story_development"

    video_auto_runs._advance_auto_run_sync(run.id)
    db.expire_all()
    row = db.query(DBVideoAutoRun).filter(DBVideoAutoRun.id == run.id).first()
    assert row is not None
    assert row.status == "completed"
    assert row.error_code is None

def test_auto_run_prompts_only_completes_without_voice_profile_or_subtitle(db, monkeypatch):
    _disable_auto_run_background(monkeypatch)
    _patch_auto_planning(monkeypatch)
    _patch_auto_phase2_generation(monkeypatch)
    project = video_projects.create_project(
        models.VideoProjectCreate(topic="Prompt only source", phase="phase2"),
        db,
    )
    run = _start_auto_run(db, project.id, mode="full_auto", material_target="prompts_only")
    assert run is not None
    assert run.material_target == "prompts_only"

    video_auto_runs._advance_auto_run_sync(run.id)
    db.expire_all()
    row = db.query(DBVideoAutoRun).filter(DBVideoAutoRun.id == run.id).first()
    subtitle = db.query(DBVideoSubtitle).filter(DBVideoSubtitle.project_id == project.id).first()
    response = video_auto_runs.get_auto_run(project.id, run.id, db)

    assert row is not None
    assert row.status == "completed"
    assert row.error_code is None
    assert row.step_results_json["material_target"] == "prompts_only"
    assert "generate_voice" not in row.step_results_json["completed_steps"]
    assert subtitle is None
    assert response is not None
    assert response.summary.core_ready is True
    assert response.summary.subtitle_status == "missing"
    assert "generate_voice" not in response.pending_steps
    assert "generate_subtitle" not in response.pending_steps

def test_auto_run_prompts_only_review_gated_stops_at_prompt_then_completes(db, monkeypatch):
    _disable_auto_run_background(monkeypatch)
    _patch_auto_planning(monkeypatch)
    _patch_auto_phase2_generation(monkeypatch)
    project = video_projects.create_project(
        models.VideoProjectCreate(topic="Prompt only review source", phase="phase2"),
        db,
    )
    run = _start_auto_run(db, project.id, mode="review_gated", material_target="prompts_only")
    assert run is not None

    video_auto_runs._advance_auto_run_sync(run.id)
    asyncio.run(video_auto_runs.continue_auto_run(project.id, run.id, models.VideoAutoRunContinueRequest(approved=True), db))
    video_auto_runs._advance_auto_run_sync(run.id)
    db.expire_all()
    row = db.query(DBVideoAutoRun).filter(DBVideoAutoRun.id == run.id).first()
    assert row is not None
    assert row.status == "needs_review"
    assert row.review_stage == "prompts"

    asyncio.run(video_auto_runs.continue_auto_run(project.id, run.id, models.VideoAutoRunContinueRequest(approved=True), db))
    video_auto_runs._advance_auto_run_sync(run.id)
    db.expire_all()
    row = db.query(DBVideoAutoRun).filter(DBVideoAutoRun.id == run.id).first()
    assert row is not None
    assert row.status == "completed"
    assert row.current_step == "completed"
    assert db.query(DBVideoSubtitle).filter(DBVideoSubtitle.project_id == project.id).first() is None

def test_auto_run_waits_for_voice_then_generates_subtitle(db, monkeypatch):
    _disable_auto_run_background(monkeypatch)
    _patch_auto_planning(monkeypatch)
    project = _ready_phase2_project(db, voice_profile_id="profile-1")
    shot = _add_phase2_shot(db, project.id, order=1, narration="A finished narration line.", duration_seconds=2)
    _add_passed_prompt(db, project.id, shot)
    generation = DBGeneration(
        id="auto-voice-generation",
        profile_id="profile-1",
        text="A finished narration line.",
        language="en",
        status="generating",
        audio_path="",
        duration=0,
        source="ai_video_shot",
    )
    db.add(generation)
    shot.generation_id = generation.id
    shot.voice_status = "generating"
    db.commit()

    run = _start_auto_run(db, project.id, mode="full_auto")
    assert run is not None
    action = video_auto_runs._advance_auto_run_sync(run.id)
    db.expire_all()
    row = db.query(DBVideoAutoRun).filter(DBVideoAutoRun.id == run.id).first()
    assert action["action"] == "wait_voice"
    assert row is not None
    assert row.status == "waiting_voice"

    audio_file = config.get_generations_dir() / "auto-run-shot.wav"
    audio_file.write_bytes(b"fake wav data")
    generation = db.query(DBGeneration).filter(DBGeneration.id == "auto-voice-generation").first()
    assert generation is not None
    generation.status = "completed"
    generation.audio_path = config.to_storage_path(audio_file)
    generation.duration = 2.0
    db.commit()

    video_auto_runs._advance_auto_run_sync(run.id)
    db.expire_all()
    row = db.query(DBVideoAutoRun).filter(DBVideoAutoRun.id == run.id).first()
    subtitle = db.query(DBVideoSubtitle).filter(DBVideoSubtitle.project_id == project.id).first()
    assert row is not None
    assert row.status == "completed"
    assert row.current_step == "completed"
    assert subtitle is not None
    assert subtitle.status == "completed"

def test_auto_run_enqueues_two_voice_segments_at_a_time(db, monkeypatch):
    _disable_auto_run_background(monkeypatch)
    _patch_auto_planning(monkeypatch)
    project = _ready_phase2_project(db, voice_profile_id="profile-1")
    first = _add_phase2_shot(db, project.id, order=1, narration="First narration line.", duration_seconds=2)
    second = _add_phase2_shot(db, project.id, order=2, narration="Second narration line.", duration_seconds=2)
    third = _add_phase2_shot(db, project.id, order=3, narration="Third narration line.", duration_seconds=2)
    _add_passed_prompt(db, project.id, first)
    _add_passed_prompt(db, project.id, second)
    _add_passed_prompt(db, project.id, third)

    run = _start_auto_run(db, project.id, mode="full_auto")
    assert run is not None
    action = video_auto_runs._advance_auto_run_sync(run.id)

    assert action["action"] == "enqueue_voice"
    assert action["shot_ids"] == [first.id, second.id]

def test_auto_run_voice_failure_is_recorded_without_prompt_or_narration_leak(db, monkeypatch):
    _disable_auto_run_background(monkeypatch)
    _patch_auto_planning(monkeypatch)
    project = _ready_phase2_project(db, voice_profile_id="profile-1")
    long_narration = "This narration should never be stored in auto-run debug details. " * 12
    shot = _add_phase2_shot(db, project.id, order=1, narration=long_narration, duration_seconds=2)
    _add_passed_prompt(db, project.id, shot)
    shot.voice_status = "failed"
    shot.voice_failure_reason = "TTS engine failed " + ("because of a very long internal message. " * 12)
    db.commit()

    run = _start_auto_run(db, project.id, mode="full_auto")
    assert run is not None
    video_auto_runs._advance_auto_run_sync(run.id)
    db.expire_all()
    row = db.query(DBVideoAutoRun).filter(DBVideoAutoRun.id == run.id).first()
    assert row is not None
    assert row.status == "failed"
    assert row.error_code == "VIDEO_AUTO_RUN_VOICE_FAILED"
    failures = row.step_results_json["voice_failed_shots"]
    assert failures[0]["shot_order"] == 1
    assert "This narration should never" not in json.dumps(row.step_results_json)
    event = db.query(DBVideoDebugEvent).filter(DBVideoDebugEvent.project_id == project.id, DBVideoDebugEvent.step_name == "auto_run_failed").first()
    assert event is not None
    assert "This narration should never" not in (event.technical_details or "")

def test_auto_run_retries_interrupted_voice_failure(db, monkeypatch):
    _disable_auto_run_background(monkeypatch)
    _patch_auto_planning(monkeypatch)
    project = _ready_phase2_project(db, voice_profile_id="profile-1")
    shot = _add_phase2_shot(db, project.id, order=1, narration="Retry this interrupted narration.", duration_seconds=2)
    _add_passed_prompt(db, project.id, shot)
    generation = DBGeneration(
        id="interrupted-auto-voice-generation",
        profile_id="profile-1",
        text=shot.english_narration,
        language="en",
        status="failed",
        error="Server was shut down during generation",
        audio_path="",
        duration=0,
        source="ai_video_shot",
    )
    db.add(generation)
    shot.generation_id = generation.id
    shot.voice_status = "failed"
    shot.voice_failure_reason = "Server was shut down during generation"
    db.commit()

    run = _start_auto_run(db, project.id, mode="full_auto")
    assert run is not None
    action = video_auto_runs._advance_auto_run_sync(run.id)
    db.expire_all()
    row = db.query(DBVideoAutoRun).filter(DBVideoAutoRun.id == run.id).first()

    assert action["action"] == "enqueue_voice"
    assert action["shot_ids"] == [shot.id]
    assert row is not None
    assert row.status == "running"
    assert row.current_step == "generate_voice"
    assert "voice_failed_shots" not in row.step_results_json

def test_auto_run_retry_clears_stale_voice_failures(db, monkeypatch):
    _disable_auto_run_background(monkeypatch)
    _patch_auto_planning(monkeypatch)
    project = _ready_phase2_project(db, voice_profile_id="profile-1")
    shot = _add_phase2_shot(db, project.id, order=1, narration="Retry narration.", duration_seconds=2)
    _add_passed_prompt(db, project.id, shot)
    shot.voice_status = "failed"
    shot.voice_failure_reason = "Temporary voice failure"
    db.commit()

    run = _start_auto_run(db, project.id, mode="full_auto")
    assert run is not None
    video_auto_runs._advance_auto_run_sync(run.id)
    db.expire_all()
    row = db.query(DBVideoAutoRun).filter(DBVideoAutoRun.id == run.id).first()
    assert row is not None
    assert "voice_failed_shots" in row.step_results_json

    shot = db.query(DBVideoShot).filter(DBVideoShot.id == shot.id).first()
    assert shot is not None
    shot.voice_status = "stale"
    shot.voice_failure_reason = None
    row.current_step = "generate_voice"
    db.commit()

    asyncio.run(video_auto_runs.retry_auto_run(project.id, run.id, models.VideoAutoRunRetryRequest(), db))
    db.expire_all()
    row = db.query(DBVideoAutoRun).filter(DBVideoAutoRun.id == run.id).first()
    assert row is not None
    assert "voice_failed_shots" not in row.step_results_json

def test_auto_run_retry_cancel_invalid_state_and_ignores_legacy_package_flag(db, monkeypatch):
    _disable_auto_run_background(monkeypatch)
    _patch_auto_planning(monkeypatch)
    project = _ready_phase2_project(db, voice_profile_id="profile-1")
    shot = _add_phase2_shot(db, project.id, order=1, narration="Ready voice.", voice_completed=True, audio_duration=2.0)
    _add_passed_prompt(db, project.id, shot)
    video_subtitles.generate_subtitle(project.id, db)

    run = _start_auto_run(db, project.id, mode="full_auto", create_package=True)
    assert run is not None
    with pytest.raises(video_auto_runs.VideoAutoRunError):
        asyncio.run(video_auto_runs.retry_auto_run(project.id, run.id, models.VideoAutoRunRetryRequest(), db))

    row = db.query(DBVideoAutoRun).filter(DBVideoAutoRun.id == run.id).first()
    assert row is not None
    row.create_package = True
    db.commit()

    package_called = False

    def fail_if_package_called(project_id, session):
        nonlocal package_called
        package_called = True
        raise AssertionError("auto-run must not create ZIP packages")

    monkeypatch.setattr(video_packages, "create_package", fail_if_package_called)
    video_auto_runs._advance_auto_run_sync(run.id)
    db.expire_all()
    row = db.query(DBVideoAutoRun).filter(DBVideoAutoRun.id == run.id).first()
    assert row is not None
    assert row.status == "completed"
    assert row.current_step == "completed"
    assert row.create_package is False
    assert package_called is False
    response = video_auto_runs.get_auto_run(project.id, run.id, db)
    assert response is not None
    assert response.summary.core_ready is True

    cancelled_project = _ready_phase2_project(db, topic="Cancel project")
    cancelled = _start_auto_run(db, cancelled_project.id, mode="review_gated")
    assert cancelled is not None
    cancel_response = video_auto_runs.cancel_auto_run(cancelled_project.id, cancelled.id, db)
    assert cancel_response is not None
    assert cancel_response.status == "cancelled"
    with pytest.raises(video_auto_runs.VideoAutoRunError):
        asyncio.run(video_auto_runs.continue_auto_run(cancelled_project.id, cancelled.id, models.VideoAutoRunContinueRequest(), db))
