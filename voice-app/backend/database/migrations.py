"""Column-level migrations for the voicebox SQLite database.

Why not Alembic?  voicebox is a single-user desktop app shipping as a
PyInstaller binary.  Every user has exactly one SQLite file.  Alembic's
strengths -- migration tracking across environments, rollback, team
coordination -- don't apply here and would add bundling complexity
(alembic.ini, env.py, versions/ directory all need to survive
PyInstaller).  The column-existence checks below are idempotent, run in
<50 ms on startup, and have worked reliably across 12 schema changes.
If the project ever moves to a server-based deployment or Postgres, this
decision should be revisited.

Adding a new migration:
    1. Append a new ``_migrate_*`` helper at the bottom of this file.
    2. Call it from ``run_migrations()`` in the appropriate spot.
    3. The helper should check column/table existence before acting
       (idempotent) and print a short message when it does real work.
"""

import json
import logging
import sqlite3

from sqlalchemy import inspect, text

from ..utils.capture_chords import (
    default_push_to_talk_chord,
    default_toggle_to_talk_chord,
)

logger = logging.getLogger(__name__)


def run_migrations(engine) -> None:
    """Run all schema migrations.  Safe to call on every startup."""
    inspector = inspect(engine)
    tables = set(inspector.get_table_names())

    _migrate_story_items(engine, inspector, tables)
    _migrate_profiles(engine, inspector, tables)
    _migrate_generations(engine, inspector, tables)
    _migrate_effect_presets(engine, inspector, tables)
    _migrate_generation_versions(engine, inspector, tables)
    _migrate_capture_settings(engine, inspector, tables)
    _migrate_ai_video_assistant(engine)
    _migrate_mcp_bindings(engine, inspector, tables)
    tables = set(inspect(engine).get_table_names())
    _normalize_storage_paths(engine, tables)


# -- helpers ---------------------------------------------------------------

def _get_columns(inspector, table: str) -> set[str]:
    return {col["name"] for col in inspector.get_columns(table)}


def _add_column(engine, table: str, column_sql: str, label: str) -> None:
    """Add a column if it doesn't already exist."""
    with engine.connect() as conn:
        conn.execute(text(f"ALTER TABLE {table} ADD COLUMN {column_sql}"))
        conn.commit()
    logger.info("Added %s column to %s", label, table)


# -- per-table migrations --------------------------------------------------

def _migrate_story_items(engine, inspector, tables: set[str]) -> None:
    if "story_items" not in tables:
        return

    columns = _get_columns(inspector, "story_items")

    # Replace position-based ordering with absolute timecodes
    if "position" in columns:
        logger.info("Migrating story_items: removing position column, using start_time_ms")
        with engine.connect() as conn:
            if "start_time_ms" not in columns:
                conn.execute(text(
                    "ALTER TABLE story_items ADD COLUMN start_time_ms INTEGER DEFAULT 0"
                ))
                result = conn.execute(text("""
                    SELECT si.id, si.story_id, si.position, g.duration
                    FROM story_items si
                    JOIN generations g ON si.generation_id = g.id
                    ORDER BY si.story_id, si.position
                """))
                current_story_id = None
                current_time_ms = 0
                for item_id, story_id, _position, duration in result.fetchall():
                    if story_id != current_story_id:
                        current_story_id = story_id
                        current_time_ms = 0
                    conn.execute(
                        text("UPDATE story_items SET start_time_ms = :time WHERE id = :id"),
                        {"time": current_time_ms, "id": item_id},
                    )
                    current_time_ms += int((duration or 0) * 1000) + 200
                conn.commit()

            # Recreate table without the position column (SQLite lacks DROP COLUMN)
            conn.execute(text("""
                CREATE TABLE story_items_new (
                    id VARCHAR PRIMARY KEY,
                    story_id VARCHAR NOT NULL,
                    generation_id VARCHAR NOT NULL,
                    start_time_ms INTEGER NOT NULL DEFAULT 0,
                    track INTEGER NOT NULL DEFAULT 0,
                    trim_start_ms INTEGER NOT NULL DEFAULT 0,
                    trim_end_ms INTEGER NOT NULL DEFAULT 0,
                    version_id VARCHAR,
                    created_at DATETIME,
                    FOREIGN KEY (story_id) REFERENCES stories(id),
                    FOREIGN KEY (generation_id) REFERENCES generations(id)
                )
            """))
            conn.execute(text("""
                INSERT INTO story_items_new (id, story_id, generation_id, start_time_ms, track, trim_start_ms, trim_end_ms, version_id, created_at)
                SELECT id, story_id, generation_id, start_time_ms,
                    COALESCE(track, 0), COALESCE(trim_start_ms, 0), COALESCE(trim_end_ms, 0), version_id, created_at
                FROM story_items
            """))
            conn.execute(text("DROP TABLE story_items"))
            conn.execute(text("ALTER TABLE story_items_new RENAME TO story_items"))
            conn.commit()

        # Re-read after table recreation
        columns = _get_columns(inspector, "story_items")

    if "track" not in columns:
        _add_column(engine, "story_items", "track INTEGER NOT NULL DEFAULT 0", "track")
    # Re-read so subsequent checks see new columns
    columns = _get_columns(inspector, "story_items")
    if "trim_start_ms" not in columns:
        _add_column(engine, "story_items", "trim_start_ms INTEGER NOT NULL DEFAULT 0", "trim_start_ms")
    if "trim_end_ms" not in columns:
        _add_column(engine, "story_items", "trim_end_ms INTEGER NOT NULL DEFAULT 0", "trim_end_ms")
    if "version_id" not in columns:
        _add_column(engine, "story_items", "version_id VARCHAR", "version_id")
    if "volume" not in columns:
        _add_column(engine, "story_items", "volume FLOAT NOT NULL DEFAULT 1.0", "volume")


def _migrate_profiles(engine, inspector, tables: set[str]) -> None:
    if "profiles" not in tables:
        return
    columns = _get_columns(inspector, "profiles")
    if "avatar_path" not in columns:
        _add_column(engine, "profiles", "avatar_path VARCHAR", "avatar_path")
    if "effects_chain" not in columns:
        _add_column(engine, "profiles", "effects_chain TEXT", "effects_chain")
    # Voice type system — v0.3.x
    if "voice_type" not in columns:
        _add_column(engine, "profiles", "voice_type VARCHAR DEFAULT 'cloned'", "voice_type")
    if "preset_engine" not in columns:
        _add_column(engine, "profiles", "preset_engine VARCHAR", "preset_engine")
    if "preset_voice_id" not in columns:
        _add_column(engine, "profiles", "preset_voice_id VARCHAR", "preset_voice_id")
    if "design_prompt" not in columns:
        _add_column(engine, "profiles", "design_prompt TEXT", "design_prompt")
    if "default_engine" not in columns:
        _add_column(engine, "profiles", "default_engine VARCHAR", "default_engine")
    if "personality" not in columns:
        _add_column(engine, "profiles", "personality TEXT", "personality")


def _migrate_generations(engine, inspector, tables: set[str]) -> None:
    if "generations" not in tables:
        return
    columns = _get_columns(inspector, "generations")
    if "status" not in columns:
        _add_column(engine, "generations", "status VARCHAR DEFAULT 'completed'", "status")
    if "error" not in columns:
        _add_column(engine, "generations", "error TEXT", "error")
    if "engine" not in columns:
        _add_column(engine, "generations", "engine VARCHAR DEFAULT 'qwen'", "engine")
    # Re-read after engine column (variable name shadows outer scope in old code)
    columns = _get_columns(inspector, "generations")
    if "model_size" not in columns:
        _add_column(engine, "generations", "model_size VARCHAR", "model_size")
    if "is_favorited" not in columns:
        _add_column(engine, "generations", "is_favorited BOOLEAN DEFAULT 0", "is_favorited")
    if "source" not in columns:
        _add_column(
            engine,
            "generations",
            "source VARCHAR NOT NULL DEFAULT 'manual'",
            "source",
        )


def _migrate_effect_presets(engine, inspector, tables: set[str]) -> None:
    if "effect_presets" not in tables:
        return
    columns = _get_columns(inspector, "effect_presets")
    if "sort_order" not in columns:
        _add_column(engine, "effect_presets", "sort_order INTEGER DEFAULT 100", "sort_order")


def _migrate_generation_versions(engine, inspector, tables: set[str]) -> None:
    if "generation_versions" not in tables:
        return
    columns = _get_columns(inspector, "generation_versions")
    if "source_version_id" not in columns:
        _add_column(engine, "generation_versions", "source_version_id VARCHAR", "source_version_id")


def _migrate_capture_settings(engine, inspector, tables: set[str]) -> None:
    if "capture_settings" not in tables:
        return
    columns = _get_columns(inspector, "capture_settings")
    push_default = json.dumps(default_push_to_talk_chord())
    toggle_default = json.dumps(default_toggle_to_talk_chord())
    if "allow_auto_paste" not in columns:
        _add_column(
            engine,
            "capture_settings",
            "allow_auto_paste BOOLEAN NOT NULL DEFAULT 1",
            "allow_auto_paste",
        )
    if "default_playback_voice_id" not in columns:
        _add_column(
            engine,
            "capture_settings",
            "default_playback_voice_id VARCHAR",
            "default_playback_voice_id",
        )
    if "chord_push_to_talk_keys" not in columns:
        _add_column(
            engine,
            "capture_settings",
            f"chord_push_to_talk_keys TEXT NOT NULL DEFAULT '{push_default}'",
            "chord_push_to_talk_keys",
        )
    if "chord_toggle_to_talk_keys" not in columns:
        _add_column(
            engine,
            "capture_settings",
            f"chord_toggle_to_talk_keys TEXT NOT NULL DEFAULT '{toggle_default}'",
            "chord_toggle_to_talk_keys",
        )
    if "hotkey_enabled" not in columns:
        _add_column(
            engine,
            "capture_settings",
            "hotkey_enabled BOOLEAN NOT NULL DEFAULT 0",
            "hotkey_enabled",
        )

def _migrate_ai_video_assistant(engine) -> None:
    """Create AI Video Assistant tables for existing SQLite databases."""
    with engine.connect() as conn:
        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS ai_planning_settings (
                id INTEGER PRIMARY KEY,
                provider VARCHAR NOT NULL DEFAULT 'codex-cli',
                codex_path VARCHAR,
                model VARCHAR,
                timeout_seconds INTEGER NOT NULL DEFAULT 60,
                output_schema_path VARCHAR,
                updated_at DATETIME
            )
        """))
        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS video_series (
                id VARCHAR PRIMARY KEY,
                title VARCHAR NOT NULL,
                character_bible TEXT,
                world_bible TEXT,
                style_bible TEXT,
                continuity_rules TEXT,
                negative_rules TEXT,
                previous_episode_summary TEXT,
                latest_episode_number INTEGER NOT NULL DEFAULT 0,
                created_at DATETIME,
                updated_at DATETIME
            )
        """))
        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS video_projects (
                id VARCHAR PRIMARY KEY,
                series_id VARCHAR,
                episode_number INTEGER,
                episode_title VARCHAR,
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
                video_purpose VARCHAR NOT NULL DEFAULT 'custom',
                dialogue_mode VARCHAR NOT NULL DEFAULT 'voiceover',
                narration_density VARCHAR NOT NULL DEFAULT 'balanced',
                call_to_action_style VARCHAR,
                default_shot_duration_seconds INTEGER,
                prompt_segment_count INTEGER,
                prompt_segment_duration_seconds INTEGER,
                micro_scenes_per_prompt INTEGER,
                input_synthesis TEXT,
                story_strategy TEXT,
                continuity_bible TEXT,
                detailed_script TEXT,
                retention_plan_json JSON,
                sound_design_plan_json JSON,
                story_approved BOOLEAN NOT NULL DEFAULT 0,
                planning_status VARCHAR NOT NULL DEFAULT 'draft',
                planning_error TEXT,
                last_request_id VARCHAR,
                package_stale BOOLEAN NOT NULL DEFAULT 0,
                created_at DATETIME,
                updated_at DATETIME,
                FOREIGN KEY (series_id) REFERENCES video_series(id),
                FOREIGN KEY (voice_profile_id) REFERENCES profiles(id)
            )
        """))
        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS video_scenes (
                id VARCHAR PRIMARY KEY,
                project_id VARCHAR NOT NULL,
                scene_order INTEGER NOT NULL DEFAULT 0,
                title VARCHAR,
                dialogue TEXT NOT NULL DEFAULT '',
                visual_description TEXT,
                target_duration_seconds INTEGER,
                approved BOOLEAN NOT NULL DEFAULT 0,
                no_narration BOOLEAN NOT NULL DEFAULT 0,
                prompt_status VARCHAR NOT NULL DEFAULT 'missing',
                voice_status VARCHAR NOT NULL DEFAULT 'missing',
                subtitle_status VARCHAR NOT NULL DEFAULT 'stale',
                generation_id VARCHAR,
                audio_path VARCHAR,
                audio_duration FLOAT,
                voice_failure_reason TEXT,
                created_at DATETIME,
                updated_at DATETIME,
                FOREIGN KEY (project_id) REFERENCES video_projects(id),
                FOREIGN KEY (generation_id) REFERENCES generations(id)
            )
        """))
        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS video_scene_prompts (
                id VARCHAR PRIMARY KEY,
                project_id VARCHAR NOT NULL,
                scene_id VARCHAR NOT NULL,
                version INTEGER NOT NULL DEFAULT 1,
                main_prompt TEXT NOT NULL,
                negative_prompt TEXT,
                aspect_ratio VARCHAR,
                style_notes TEXT,
                character_notes TEXT,
                prompt_path VARCHAR,
                created_at DATETIME,
                FOREIGN KEY (project_id) REFERENCES video_projects(id),
                FOREIGN KEY (scene_id) REFERENCES video_scenes(id)
            )
        """))
        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS video_source_blocks (
                id VARCHAR PRIMARY KEY,
                project_id VARCHAR NOT NULL,
                block_type VARCHAR NOT NULL DEFAULT 'idea',
                sort_order INTEGER NOT NULL DEFAULT 0,
                content TEXT NOT NULL DEFAULT '',
                created_at DATETIME,
                updated_at DATETIME,
                FOREIGN KEY (project_id) REFERENCES video_projects(id)
            )
        """))
        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS video_auto_runs (
                id VARCHAR PRIMARY KEY,
                project_id VARCHAR NOT NULL,
                mode VARCHAR NOT NULL DEFAULT 'review_gated',
                status VARCHAR NOT NULL DEFAULT 'queued',
                current_step VARCHAR NOT NULL DEFAULT 'validate',
                review_stage VARCHAR,
                progress FLOAT NOT NULL DEFAULT 0,
                create_package BOOLEAN NOT NULL DEFAULT 0,
                force BOOLEAN NOT NULL DEFAULT 0,
                step_results_json JSON,
                failure_reason TEXT,
                error_code VARCHAR,
                started_at DATETIME,
                completed_at DATETIME,
                created_at DATETIME,
                updated_at DATETIME,
                FOREIGN KEY (project_id) REFERENCES video_projects(id)
            )
        """))
        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS video_provider_sessions (
                id VARCHAR PRIMARY KEY,
                provider VARCHAR NOT NULL DEFAULT 'veo',
                provider_tool VARCHAR DEFAULT 'veo3_flow',
                status VARCHAR NOT NULL DEFAULT 'not_configured',
                is_default BOOLEAN NOT NULL DEFAULT 1,
                chrome_profile_path VARCHAR NOT NULL,
                connection_label VARCHAR,
                verified_account_hint VARCHAR,
                account_identifier_hash VARCHAR,
                identity_status VARCHAR NOT NULL DEFAULT 'unknown',
                identity_verified_at DATETIME,
                last_checked_at DATETIME,
                failure_reason TEXT,
                created_at DATETIME,
                updated_at DATETIME
            )
        """))
        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS video_clip_generation_jobs (
                id VARCHAR PRIMARY KEY,
                project_id VARCHAR NOT NULL,
                provider VARCHAR NOT NULL DEFAULT 'veo',
                session_id VARCHAR NOT NULL,
                status VARCHAR NOT NULL DEFAULT 'queued',
                current_step VARCHAR NOT NULL DEFAULT 'validate',
                progress FLOAT NOT NULL DEFAULT 0,
                force BOOLEAN NOT NULL DEFAULT 0,
                auto_render BOOLEAN NOT NULL DEFAULT 0,
                credit_approval_policy VARCHAR NOT NULL DEFAULT 'approve_dont_ask_again',
                max_credit_per_job INTEGER,
                credit_spent_estimate INTEGER NOT NULL DEFAULT 0,
                render_job_id VARCHAR,
                download_dir VARCHAR,
                failure_reason TEXT,
                error_code VARCHAR,
                step_results_json JSON,
                started_at DATETIME,
                completed_at DATETIME,
                created_at DATETIME,
                updated_at DATETIME,
                FOREIGN KEY (project_id) REFERENCES video_projects(id),
                FOREIGN KEY (session_id) REFERENCES video_provider_sessions(id),
                FOREIGN KEY (render_job_id) REFERENCES video_render_jobs(id)
            )
        """))
        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS video_clip_generation_items (
                id VARCHAR PRIMARY KEY,
                job_id VARCHAR NOT NULL,
                project_id VARCHAR NOT NULL,
                shot_id VARCHAR NOT NULL,
                shot_order INTEGER NOT NULL DEFAULT 0,
                prompt_id VARCHAR,
                status VARCHAR NOT NULL DEFAULT 'pending',
                attempt_count INTEGER NOT NULL DEFAULT 0,
                credit_cost INTEGER,
                provider_duration_seconds FLOAT,
                provider_asset_id VARCHAR,
                provider_project_ref_hash VARCHAR,
                download_correlation_id VARCHAR,
                download_url_hash VARCHAR,
                original_filename VARCHAR,
                downloaded_file_path VARCHAR,
                clip_id VARCHAR,
                failure_reason TEXT,
                started_at DATETIME,
                completed_at DATETIME,
                created_at DATETIME,
                updated_at DATETIME,
                FOREIGN KEY (job_id) REFERENCES video_clip_generation_jobs(id),
                FOREIGN KEY (project_id) REFERENCES video_projects(id),
                FOREIGN KEY (shot_id) REFERENCES video_shots(id),
                FOREIGN KEY (prompt_id) REFERENCES video_shot_prompts(id),
                FOREIGN KEY (clip_id) REFERENCES video_shot_clips(id)
            )
        """))
        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS video_shots (
                id VARCHAR PRIMARY KEY,
                project_id VARCHAR NOT NULL,
                scene_id VARCHAR,
                shot_order INTEGER NOT NULL DEFAULT 0,
                duration_seconds FLOAT,
                vietnamese_description TEXT,
                english_narration TEXT,
                primary_action TEXT,
                purpose TEXT,
                shot_type VARCHAR,
                camera_angle VARCHAR,
                framing VARCHAR,
                composition TEXT,
                camera_motion VARCHAR,
                subject_motion TEXT,
                environment_motion TEXT,
                transition_to_next TEXT,
                retention_json JSON,
                transition_json JSON,
                sound_design_json JSON,
                micro_scenes_json JSON,
                retainability_quality_check JSON,
                locked BOOLEAN NOT NULL DEFAULT 0,
                status VARCHAR NOT NULL DEFAULT 'draft',
                prompt_status VARCHAR NOT NULL DEFAULT 'missing',
                voice_status VARCHAR NOT NULL DEFAULT 'missing',
                subtitle_status VARCHAR NOT NULL DEFAULT 'stale',
                generation_id VARCHAR,
                audio_path VARCHAR,
                audio_duration FLOAT,
                voice_failure_reason TEXT,
                created_at DATETIME,
                updated_at DATETIME,
                FOREIGN KEY (project_id) REFERENCES video_projects(id),
                FOREIGN KEY (scene_id) REFERENCES video_scenes(id),
                FOREIGN KEY (generation_id) REFERENCES generations(id)
            )
        """))
        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS video_shot_prompts (
                id VARCHAR PRIMARY KEY,
                project_id VARCHAR NOT NULL,
                scene_id VARCHAR,
                shot_id VARCHAR NOT NULL,
                version INTEGER NOT NULL DEFAULT 1,
                prompt TEXT NOT NULL,
                prompt_explanation_vi TEXT,
                negative_prompt TEXT,
                duration_seconds FLOAT,
                aspect_ratio VARCHAR,
                camera_motion VARCHAR,
                subject_motion TEXT,
                environment_motion TEXT,
                start_frame TEXT,
                end_frame TEXT,
                lighting TEXT,
                mood TEXT,
                style_notes TEXT,
                continuity_notes TEXT,
                retention_notes TEXT,
                transition_notes TEXT,
                sound_design_notes TEXT,
                quality_status VARCHAR NOT NULL DEFAULT 'unchecked',
                quality_check JSON,
                prompt_path VARCHAR,
                created_at DATETIME,
                FOREIGN KEY (project_id) REFERENCES video_projects(id),
                FOREIGN KEY (scene_id) REFERENCES video_scenes(id),
                FOREIGN KEY (shot_id) REFERENCES video_shots(id)
            )
        """))
        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS video_shot_clips (
                id VARCHAR PRIMARY KEY,
                project_id VARCHAR NOT NULL,
                shot_id VARCHAR NOT NULL,
                source VARCHAR NOT NULL DEFAULT 'upload',
                status VARCHAR NOT NULL DEFAULT 'pending',
                file_path VARCHAR NOT NULL,
                original_filename VARCHAR,
                mime_type VARCHAR,
                size_bytes INTEGER,
                duration_seconds FLOAT,
                width INTEGER,
                height INTEGER,
                fps FLOAT,
                codec VARCHAR,
                has_audio BOOLEAN NOT NULL DEFAULT 0,
                is_active BOOLEAN NOT NULL DEFAULT 1,
                failure_reason TEXT,
                provider VARCHAR,
                provider_asset_id VARCHAR,
                provider_metadata JSON,
                created_at DATETIME,
                updated_at DATETIME,
                FOREIGN KEY (project_id) REFERENCES video_projects(id),
                FOREIGN KEY (shot_id) REFERENCES video_shots(id)
            )
        """))
        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS video_render_jobs (
                id VARCHAR PRIMARY KEY,
                project_id VARCHAR NOT NULL,
                status VARCHAR NOT NULL DEFAULT 'queued',
                progress FLOAT NOT NULL DEFAULT 0,
                current_step VARCHAR,
                settings_json TEXT,
                readiness_json TEXT,
                timeline_manifest_path VARCHAR,
                output_path VARCHAR,
                subtitle_ass_path VARCHAR,
                stale BOOLEAN NOT NULL DEFAULT 0,
                failure_reason TEXT,
                error_code VARCHAR,
                technical_details TEXT,
                started_at DATETIME,
                completed_at DATETIME,
                created_at DATETIME,
                updated_at DATETIME,
                FOREIGN KEY (project_id) REFERENCES video_projects(id)
            )
        """))
        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS video_debug_events (
                id VARCHAR PRIMARY KEY,
                request_id VARCHAR NOT NULL,
                project_id VARCHAR,
                scene_id VARCHAR,
                shot_id VARCHAR,
                step_name VARCHAR NOT NULL,
                status VARCHAR NOT NULL DEFAULT 'info',
                provider VARCHAR,
                model VARCHAR,
                duration_ms FLOAT,
                retry_count INTEGER NOT NULL DEFAULT 0,
                error_code VARCHAR,
                exception_class VARCHAR,
                message TEXT,
                technical_details TEXT,
                validation_errors JSON,
                created_at DATETIME,
                FOREIGN KEY (project_id) REFERENCES video_projects(id),
                FOREIGN KEY (scene_id) REFERENCES video_scenes(id),
                FOREIGN KEY (shot_id) REFERENCES video_shots(id)
            )
        """))
        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS video_scene_assets (
                id VARCHAR PRIMARY KEY,
                project_id VARCHAR NOT NULL,
                scene_id VARCHAR NOT NULL,
                asset_type VARCHAR NOT NULL DEFAULT 'preview_image',
                file_path VARCHAR NOT NULL,
                original_filename VARCHAR,
                mime_type VARCHAR,
                size_bytes INTEGER,
                is_active BOOLEAN NOT NULL DEFAULT 1,
                created_at DATETIME,
                FOREIGN KEY (project_id) REFERENCES video_projects(id),
                FOREIGN KEY (scene_id) REFERENCES video_scenes(id)
            )
        """))
        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS video_subtitles (
                id VARCHAR PRIMARY KEY,
                project_id VARCHAR NOT NULL,
                status VARCHAR NOT NULL DEFAULT 'missing',
                subtitle_path VARCHAR,
                format VARCHAR NOT NULL DEFAULT 'srt',
                cues_json TEXT,
                created_at DATETIME,
                updated_at DATETIME,
                FOREIGN KEY (project_id) REFERENCES video_projects(id)
            )
        """))
        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS video_package_exports (
                id VARCHAR PRIMARY KEY,
                project_id VARCHAR NOT NULL,
                status VARCHAR NOT NULL DEFAULT 'pending',
                manifest_path VARCHAR,
                zip_path VARCHAR,
                stale BOOLEAN NOT NULL DEFAULT 0,
                failure_reason TEXT,
                created_at DATETIME,
                updated_at DATETIME,
                FOREIGN KEY (project_id) REFERENCES video_projects(id)
            )
        """))
        conn.execute(text("CREATE INDEX IF NOT EXISTS idx_video_scenes_project_order ON video_scenes(project_id, scene_order)"))
        conn.execute(text("CREATE INDEX IF NOT EXISTS idx_video_scene_prompts_scene ON video_scene_prompts(scene_id)"))
        conn.execute(text("CREATE INDEX IF NOT EXISTS idx_video_source_blocks_project_order ON video_source_blocks(project_id, sort_order)"))
        conn.execute(text("CREATE INDEX IF NOT EXISTS idx_video_auto_runs_project_created ON video_auto_runs(project_id, created_at)"))
        conn.execute(text("CREATE INDEX IF NOT EXISTS idx_video_auto_runs_project_status ON video_auto_runs(project_id, status)"))
        conn.execute(text("CREATE INDEX IF NOT EXISTS idx_video_provider_sessions_provider_default ON video_provider_sessions(provider, is_default)"))
        conn.execute(text("CREATE INDEX IF NOT EXISTS idx_video_provider_sessions_status ON video_provider_sessions(provider, status)"))
        conn.execute(text("CREATE INDEX IF NOT EXISTS idx_video_clip_jobs_project_status ON video_clip_generation_jobs(project_id, provider, status)"))
        conn.execute(text("CREATE INDEX IF NOT EXISTS idx_video_clip_jobs_session_status ON video_clip_generation_jobs(session_id, status)"))
        conn.execute(text("CREATE INDEX IF NOT EXISTS idx_video_clip_jobs_project_created ON video_clip_generation_jobs(project_id, created_at)"))
        conn.execute(text("CREATE INDEX IF NOT EXISTS idx_video_clip_items_job_status ON video_clip_generation_items(job_id, status)"))
        conn.execute(text("CREATE INDEX IF NOT EXISTS idx_video_clip_items_project_shot ON video_clip_generation_items(project_id, shot_id)"))
        conn.execute(text("CREATE INDEX IF NOT EXISTS idx_video_clip_items_shot_status ON video_clip_generation_items(shot_id, status)"))
        conn.execute(text("CREATE INDEX IF NOT EXISTS idx_video_shots_project_order ON video_shots(project_id, shot_order)"))
        conn.execute(text("CREATE INDEX IF NOT EXISTS idx_video_shots_scene_order ON video_shots(scene_id, shot_order)"))
        conn.execute(text("CREATE INDEX IF NOT EXISTS idx_video_shot_prompts_shot ON video_shot_prompts(shot_id, version)"))
        conn.execute(text("CREATE INDEX IF NOT EXISTS idx_video_shot_clips_shot_active ON video_shot_clips(shot_id, is_active)"))
        conn.execute(text("CREATE INDEX IF NOT EXISTS idx_video_shot_clips_project ON video_shot_clips(project_id, created_at)"))
        conn.execute(text("CREATE INDEX IF NOT EXISTS idx_video_render_jobs_project ON video_render_jobs(project_id, created_at)"))
        conn.execute(text("CREATE INDEX IF NOT EXISTS idx_video_debug_events_project ON video_debug_events(project_id, created_at)"))
        conn.execute(text("CREATE INDEX IF NOT EXISTS idx_video_scene_assets_scene ON video_scene_assets(scene_id, is_active)"))
        conn.execute(text("CREATE INDEX IF NOT EXISTS idx_video_package_exports_project ON video_package_exports(project_id, created_at)"))
        conn.execute(text("CREATE INDEX IF NOT EXISTS idx_video_series_updated ON video_series(updated_at)"))
        project_columns = {row[1] for row in conn.execute(text("PRAGMA table_info(video_projects)")).fetchall()}
        project_column_defaults = {
            "series_id": "VARCHAR",
            "episode_number": "INTEGER",
            "episode_title": "VARCHAR",
            "phase": "VARCHAR NOT NULL DEFAULT 'phase1'",
            "target_language": "VARCHAR NOT NULL DEFAULT 'en'",
            "video_purpose": "VARCHAR NOT NULL DEFAULT 'custom'",
            "dialogue_mode": "VARCHAR NOT NULL DEFAULT 'voiceover'",
            "narration_density": "VARCHAR NOT NULL DEFAULT 'balanced'",
            "call_to_action_style": "VARCHAR",
            "default_shot_duration_seconds": "INTEGER",
            "prompt_segment_count": "INTEGER",
            "prompt_segment_duration_seconds": "INTEGER",
            "micro_scenes_per_prompt": "INTEGER",
            "input_synthesis": "TEXT",
            "story_strategy": "TEXT",
            "continuity_bible": "TEXT",
            "detailed_script": "TEXT",
            "retention_plan_json": "JSON",
            "sound_design_plan_json": "JSON",
            "story_approved": "BOOLEAN NOT NULL DEFAULT 0",
            "planning_status": "VARCHAR NOT NULL DEFAULT 'draft'",
            "planning_error": "TEXT",
            "last_request_id": "VARCHAR",
            "package_stale": "BOOLEAN NOT NULL DEFAULT 0",
        }
        for column_name, column_sql in project_column_defaults.items():
            if column_name not in project_columns:
                conn.execute(text(f"ALTER TABLE video_projects ADD COLUMN {column_name} {column_sql}"))
        conn.execute(text("CREATE INDEX IF NOT EXISTS idx_video_projects_series_episode ON video_projects(series_id, episode_number)"))
        scene_columns = {row[1] for row in conn.execute(text("PRAGMA table_info(video_scenes)")).fetchall()}
        if "approved" not in scene_columns:
            conn.execute(text("ALTER TABLE video_scenes ADD COLUMN approved BOOLEAN NOT NULL DEFAULT 0"))
        if "no_narration" not in scene_columns:
            conn.execute(text("ALTER TABLE video_scenes ADD COLUMN no_narration BOOLEAN NOT NULL DEFAULT 0"))
        shot_columns = {row[1] for row in conn.execute(text("PRAGMA table_info(video_shots)")).fetchall()}
        shot_column_defaults = {
            "retention_json": "JSON",
            "transition_json": "JSON",
            "sound_design_json": "JSON",
            "micro_scenes_json": "JSON",
            "retainability_quality_check": "JSON",
        }
        for column_name, column_sql in shot_column_defaults.items():
            if column_name not in shot_columns:
                conn.execute(text(f"ALTER TABLE video_shots ADD COLUMN {column_name} {column_sql}"))
        shot_prompt_columns = {row[1] for row in conn.execute(text("PRAGMA table_info(video_shot_prompts)")).fetchall()}
        if "prompt_explanation_vi" not in shot_prompt_columns:
            conn.execute(text("ALTER TABLE video_shot_prompts ADD COLUMN prompt_explanation_vi TEXT"))
        shot_prompt_column_defaults = {
            "retention_notes": "TEXT",
            "transition_notes": "TEXT",
            "sound_design_notes": "TEXT",
        }
        for column_name, column_sql in shot_prompt_column_defaults.items():
            if column_name not in shot_prompt_columns:
                conn.execute(text(f"ALTER TABLE video_shot_prompts ADD COLUMN {column_name} {column_sql}"))
        provider_session_columns = {row[1] for row in conn.execute(text("PRAGMA table_info(video_provider_sessions)")).fetchall()}
        provider_session_column_defaults = {
            "provider_tool": "VARCHAR DEFAULT 'veo3_flow'",
            "connection_label": "VARCHAR",
            "verified_account_hint": "VARCHAR",
            "account_identifier_hash": "VARCHAR",
            "identity_status": "VARCHAR NOT NULL DEFAULT 'unknown'",
            "identity_verified_at": "DATETIME",
            "last_checked_at": "DATETIME",
            "failure_reason": "TEXT",
        }
        for column_name, column_sql in provider_session_column_defaults.items():
            if column_name not in provider_session_columns:
                conn.execute(text(f"ALTER TABLE video_provider_sessions ADD COLUMN {column_name} {column_sql}"))
        clip_job_columns = {row[1] for row in conn.execute(text("PRAGMA table_info(video_clip_generation_jobs)")).fetchall()}
        clip_job_column_defaults = {
            "credit_approval_policy": "VARCHAR NOT NULL DEFAULT 'approve_dont_ask_again'",
            "max_credit_per_job": "INTEGER",
            "credit_spent_estimate": "INTEGER NOT NULL DEFAULT 0",
            "render_job_id": "VARCHAR",
            "download_dir": "VARCHAR",
            "step_results_json": "JSON",
        }
        for column_name, column_sql in clip_job_column_defaults.items():
            if column_name not in clip_job_columns:
                conn.execute(text(f"ALTER TABLE video_clip_generation_jobs ADD COLUMN {column_name} {column_sql}"))
        clip_item_columns = {row[1] for row in conn.execute(text("PRAGMA table_info(video_clip_generation_items)")).fetchall()}
        clip_item_column_defaults = {
            "credit_cost": "INTEGER",
            "provider_duration_seconds": "FLOAT",
            "provider_project_ref_hash": "VARCHAR",
            "download_correlation_id": "VARCHAR",
            "download_url_hash": "VARCHAR",
            "original_filename": "VARCHAR",
            "downloaded_file_path": "VARCHAR",
            "clip_id": "VARCHAR",
        }
        for column_name, column_sql in clip_item_column_defaults.items():
            if column_name not in clip_item_columns:
                conn.execute(text(f"ALTER TABLE video_clip_generation_items ADD COLUMN {column_name} {column_sql}"))
        conn.commit()


def _migrate_mcp_bindings(engine, inspector, tables: set[str]) -> None:
    """Drop the legacy ``default_intent`` column and add ``default_personality``.

    The intent tri-state (respond / rewrite / compose) has been collapsed
    to a boolean: when true, ``voicebox.speak`` rewrites input through the
    profile's personality LLM before TTS.
    """
    if "mcp_client_bindings" not in tables:
        return
    columns = _get_columns(inspector, "mcp_client_bindings")
    if "default_personality" not in columns:
        _add_column(
            engine,
            "mcp_client_bindings",
            "default_personality BOOLEAN NOT NULL DEFAULT 0",
            "default_personality",
        )
    if "default_intent" in columns:
        if _supports_drop_column(engine):
            with engine.connect() as conn:
                conn.execute(text("ALTER TABLE mcp_client_bindings DROP COLUMN default_intent"))
                conn.commit()
            logger.info("Dropped legacy default_intent column from mcp_client_bindings")
        else:
            # ALTER TABLE … DROP COLUMN on SQLite requires 3.35+ (Mar
            # 2021). Production PyInstaller builds bundle Python 3.12
            # which links to SQLite 3.40+; this branch only fires for
            # dev environments running the backend directly against an
            # old system SQLite (Ubuntu 20.04 = 3.31, Debian 11 = 3.34).
            # Leaving the unused column in place is harmless — the ORM
            # only maps declared columns, so a stray one does no work
            # and gets no reads or writes.
            logger.warning(
                "SQLite %s too old to DROP COLUMN (need 3.35+); leaving unused default_intent column on mcp_client_bindings in place.",
                sqlite3.sqlite_version,
            )


def _supports_drop_column(engine) -> bool:
    """Whether ``ALTER TABLE … DROP COLUMN`` is supported by the dialect +
    runtime. Non-SQLite dialects (Postgres, MySQL) have supported it for
    decades; SQLite only gained the feature in 3.35."""
    if engine.dialect.name != "sqlite":
        return True
    return tuple(int(p) for p in sqlite3.sqlite_version.split(".")[:3]) >= (3, 35, 0)


def _normalize_storage_paths(engine, tables: set[str]) -> None:
    """Normalize stored file paths to be relative to the configured data dir."""
    from pathlib import Path

    from ..config import resolve_storage_path, to_storage_path

    path_columns = [
        ("generations", "audio_path"),
        ("generation_versions", "audio_path"),
        ("profile_samples", "audio_path"),
        ("profiles", "avatar_path"),
        ("video_scene_prompts", "prompt_path"),
        ("video_scene_assets", "file_path"),
        ("video_shot_prompts", "prompt_path"),
        ("video_shot_clips", "file_path"),
        ("video_subtitles", "subtitle_path"),
        ("video_package_exports", "manifest_path"),
        ("video_package_exports", "zip_path"),
        ("video_render_jobs", "timeline_manifest_path"),
        ("video_render_jobs", "output_path"),
        ("video_render_jobs", "subtitle_ass_path"),
        ("video_provider_sessions", "chrome_profile_path"),
        ("video_clip_generation_jobs", "download_dir"),
        ("video_clip_generation_items", "downloaded_file_path"),
    ]

    total_fixed = 0
    with engine.connect() as conn:
        for table, column in path_columns:
            if table not in tables:
                continue
            rows = conn.execute(
                text(f"SELECT id, {column} FROM {table} WHERE {column} IS NOT NULL")
            ).fetchall()
            for row_id, path_val in rows:
                if not path_val:
                    continue
                p = Path(path_val)
                resolved = resolve_storage_path(p)
                if resolved is None:
                    continue

                normalized = to_storage_path(resolved)

                if normalized != path_val:
                    conn.execute(
                        text(f"UPDATE {table} SET {column} = :path WHERE id = :id"),
                        {"path": normalized, "id": row_id},
                    )
                    total_fixed += 1
        if total_fixed > 0:
            conn.commit()
            logger.info("Normalized %d stored file paths", total_fixed)
