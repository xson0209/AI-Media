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
    _migrate_video_inspiration(engine)
    _migrate_comic_series_analysis(engine)
    _migrate_research_scoring(engine)
    _migrate_automation_hub(engine)
    _migrate_product_video(engine)
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
                model_reasoning_effort VARCHAR,
                timeout_seconds INTEGER NOT NULL DEFAULT 600,
                output_schema_path VARCHAR,
                updated_at DATETIME
            )
        """))
        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS video_series (
                id VARCHAR PRIMARY KEY,
                title VARCHAR NOT NULL,
                series_mode VARCHAR NOT NULL DEFAULT 'video_story_only',
                character_bible TEXT,
                world_bible TEXT,
                style_bible TEXT,
                continuity_rules TEXT,
                negative_rules TEXT,
                previous_episode_summary TEXT,
                latest_episode_number INTEGER NOT NULL DEFAULT 0,
                revision INTEGER NOT NULL DEFAULT 1,
                created_at DATETIME,
                updated_at DATETIME
            )
        """))
        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS series_character_profiles (
                id VARCHAR PRIMARY KEY,
                series_id VARCHAR NOT NULL,
                name VARCHAR NOT NULL,
                role VARCHAR,
                face_description TEXT,
                hair_description TEXT,
                body_description TEXT,
                signature_outfit TEXT,
                personality TEXT,
                speech_style TEXT,
                fixed_traits TEXT,
                additional_notes TEXT,
                sort_order INTEGER NOT NULL DEFAULT 0,
                revision INTEGER NOT NULL DEFAULT 1,
                created_at DATETIME,
                updated_at DATETIME,
                FOREIGN KEY (series_id) REFERENCES video_series(id)
            )
        """))
        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS series_memory_cards (
                id VARCHAR PRIMARY KEY,
                series_id VARCHAR NOT NULL,
                card_type VARCHAR NOT NULL,
                title VARCHAR NOT NULL,
                content_json JSON NOT NULL,
                tags_json JSON,
                entity_refs_json JSON,
                importance FLOAT NOT NULL DEFAULT 0.5,
                status VARCHAR NOT NULL DEFAULT 'draft',
                effective_from_episode INTEGER,
                effective_to_episode INTEGER,
                source_type VARCHAR,
                source_id VARCHAR,
                revision INTEGER NOT NULL DEFAULT 1,
                approved_at DATETIME,
                created_at DATETIME,
                updated_at DATETIME,
                FOREIGN KEY (series_id) REFERENCES video_series(id)
            )
        """))
        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS series_current_states (
                id VARCHAR PRIMARY KEY,
                series_id VARCHAR NOT NULL,
                based_on_episode_number INTEGER NOT NULL DEFAULT 0,
                character_states_json JSON,
                relationship_states_json JSON,
                location_states_json JSON,
                prop_states_json JSON,
                open_threads_json JSON,
                unresolved_conflicts_json JSON,
                revision INTEGER NOT NULL DEFAULT 1,
                approval_status VARCHAR NOT NULL DEFAULT 'draft',
                source_type VARCHAR,
                source_id VARCHAR,
                previous_state_id VARCHAR,
                approved_at DATETIME,
                created_at DATETIME,
                updated_at DATETIME,
                FOREIGN KEY (series_id) REFERENCES video_series(id),
                FOREIGN KEY (previous_state_id) REFERENCES series_current_states(id)
            )
        """))
        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS story_episodes (
                id VARCHAR PRIMARY KEY,
                series_id VARCHAR NOT NULL,
                episode_number INTEGER NOT NULL,
                title VARCHAR,
                output_intent VARCHAR NOT NULL DEFAULT 'truyen_anh',
                market_profile VARCHAR NOT NULL DEFAULT 'viet_nam',
                language_profile VARCHAR NOT NULL DEFAULT 'vi',
                source_input TEXT,
                source_digest TEXT,
                output_settings_json JSON,
                master_story_json JSON,
                selection_reason TEXT,
                approval_status VARCHAR NOT NULL DEFAULT 'draft',
                approved_at DATETIME,
                revision INTEGER NOT NULL DEFAULT 1,
                created_at DATETIME,
                updated_at DATETIME,
                FOREIGN KEY (series_id) REFERENCES video_series(id)
            )
        """))
        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS story_scenario_candidates (
                id VARCHAR PRIMARY KEY,
                story_episode_id VARCHAR NOT NULL,
                strategy_type VARCHAR NOT NULL,
                script_json JSON NOT NULL,
                score_json JSON,
                strengths TEXT,
                risks TEXT,
                context_snapshot_id VARCHAR,
                model_label VARCHAR,
                generation_attempt INTEGER NOT NULL DEFAULT 1,
                generation_status VARCHAR NOT NULL DEFAULT 'completed',
                generation_metadata_json JSON,
                evaluation_status VARCHAR NOT NULL DEFAULT 'pending',
                evaluation_json JSON,
                selected BOOLEAN NOT NULL DEFAULT 0,
                created_at DATETIME,
                updated_at DATETIME,
                FOREIGN KEY (story_episode_id) REFERENCES story_episodes(id)
            )
        """))
        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS video_projects (
                id VARCHAR PRIMARY KEY,
                series_id VARCHAR,
                story_episode_id VARCHAR,
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
                FOREIGN KEY (story_episode_id) REFERENCES story_episodes(id),
                FOREIGN KEY (voice_profile_id) REFERENCES profiles(id)
            )
        """))
        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS story_adaptations (
                id VARCHAR PRIMARY KEY,
                story_episode_id VARCHAR NOT NULL,
                kind VARCHAR NOT NULL,
                status VARCHAR NOT NULL DEFAULT 'draft',
                payload_json JSON,
                linked_video_project_id VARCHAR,
                revision INTEGER NOT NULL DEFAULT 1,
                created_at DATETIME,
                updated_at DATETIME,
                FOREIGN KEY (story_episode_id) REFERENCES story_episodes(id),
                FOREIGN KEY (linked_video_project_id) REFERENCES video_projects(id)
            )
        """))
        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS series_context_traces (
                id VARCHAR PRIMARY KEY,
                series_id VARCHAR NOT NULL,
                project_id VARCHAR,
                story_episode_id VARCHAR,
                task_type VARCHAR NOT NULL,
                target_ref_type VARCHAR,
                target_ref_id VARCHAR,
                selected_cards_json JSON,
                selected_character_profiles_json JSON,
                group_budget_json JSON,
                missing_required_json JSON,
                truncated_groups_json JSON,
                context_stats_json JSON,
                reasons_json JSON,
                context_preview TEXT,
                created_at DATETIME,
                FOREIGN KEY (series_id) REFERENCES video_series(id),
                FOREIGN KEY (project_id) REFERENCES video_projects(id),
                FOREIGN KEY (story_episode_id) REFERENCES story_episodes(id)
            )
        """))
        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS series_canon_checks (
                id VARCHAR PRIMARY KEY,
                series_id VARCHAR NOT NULL,
                project_id VARCHAR,
                story_episode_id VARCHAR,
                prompt_kind VARCHAR NOT NULL,
                prompt_ref_id VARCHAR,
                passed BOOLEAN NOT NULL DEFAULT 1,
                blocking_conflicts_json JSON,
                warnings_json JSON,
                evidence_card_ids_json JSON,
                override_reason TEXT,
                overridden_by VARCHAR,
                overridden_at DATETIME,
                created_at DATETIME,
                FOREIGN KEY (series_id) REFERENCES video_series(id),
                FOREIGN KEY (project_id) REFERENCES video_projects(id),
                FOREIGN KEY (story_episode_id) REFERENCES story_episodes(id)
            )
        """))
        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS series_reference_assets (
                id VARCHAR PRIMARY KEY,
                series_id VARCHAR NOT NULL,
                entity_type VARCHAR NOT NULL,
                entity_id VARCHAR NOT NULL,
                reference_role VARCHAR NOT NULL,
                label VARCHAR,
                asset_path VARCHAR NOT NULL,
                thumbnail_path VARCHAR,
                provider_asset_id VARCHAR,
                original_filename VARCHAR,
                mime_type VARCHAR NOT NULL,
                width INTEGER,
                height INTEGER,
                file_size_bytes INTEGER,
                checksum VARCHAR NOT NULL,
                source_type VARCHAR,
                approval_status VARCHAR NOT NULL DEFAULT 'pending_approval',
                revision INTEGER NOT NULL DEFAULT 1,
                active BOOLEAN NOT NULL DEFAULT 0,
                metadata_json JSON,
                created_at DATETIME,
                updated_at DATETIME,
                FOREIGN KEY (series_id) REFERENCES video_series(id)
            )
        """))
        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS series_version_records (
                id VARCHAR PRIMARY KEY,
                series_id VARCHAR NOT NULL,
                entity_type VARCHAR NOT NULL,
                entity_id VARCHAR NOT NULL,
                revision INTEGER NOT NULL DEFAULT 1,
                snapshot_json JSON NOT NULL,
                changed_by VARCHAR,
                change_source VARCHAR,
                change_reason TEXT,
                created_at DATETIME,
                FOREIGN KEY (series_id) REFERENCES video_series(id)
            )
        """))
        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS artifact_dependency_snapshots (
                id VARCHAR PRIMARY KEY,
                series_id VARCHAR NOT NULL,
                artifact_type VARCHAR NOT NULL,
                artifact_id VARCHAR NOT NULL,
                artifact_revision INTEGER NOT NULL DEFAULT 1,
                dependency_type VARCHAR NOT NULL,
                dependency_id VARCHAR NOT NULL,
                dependency_revision INTEGER NOT NULL DEFAULT 1,
                dependency_scope VARCHAR NOT NULL,
                metadata_json JSON,
                created_at DATETIME,
                FOREIGN KEY (series_id) REFERENCES video_series(id)
            )
        """))
        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS artifact_stale_events (
                id VARCHAR PRIMARY KEY,
                series_id VARCHAR NOT NULL,
                artifact_type VARCHAR NOT NULL,
                artifact_id VARCHAR NOT NULL,
                artifact_revision INTEGER NOT NULL DEFAULT 1,
                dependency_type VARCHAR NOT NULL,
                dependency_id VARCHAR NOT NULL,
                old_revision INTEGER,
                new_revision INTEGER,
                changed_scope VARCHAR NOT NULL,
                dependency_scope VARCHAR NOT NULL,
                reason_vi TEXT NOT NULL,
                propagation_rule VARCHAR NOT NULL,
                status VARCHAR NOT NULL DEFAULT 'active',
                metadata_json JSON,
                created_at DATETIME,
                resolved_at DATETIME,
                FOREIGN KEY (series_id) REFERENCES video_series(id)
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
                revision INTEGER NOT NULL DEFAULT 1,
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
            CREATE TABLE IF NOT EXISTS video_publishing_metadata (
                id VARCHAR PRIMARY KEY,
                project_id VARCHAR NOT NULL UNIQUE,
                status VARCHAR NOT NULL DEFAULT 'missing',
                target_language VARCHAR NOT NULL DEFAULT 'en',
                platforms_json JSON NOT NULL DEFAULT '{}',
                input_fingerprint VARCHAR,
                revision INTEGER NOT NULL DEFAULT 1,
                stale BOOLEAN NOT NULL DEFAULT 0,
                failure_reason TEXT,
                error_code VARCHAR,
                request_id VARCHAR,
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
            CREATE TABLE IF NOT EXISTS video_provider_project_bindings (
                id VARCHAR PRIMARY KEY,
                project_id VARCHAR,
                series_id VARCHAR,
                provider VARCHAR NOT NULL DEFAULT 'veo',
                provider_tool VARCHAR NOT NULL DEFAULT 'veo3_flow',
                provider_project_url TEXT NOT NULL,
                provider_project_ref_hash VARCHAR NOT NULL,
                status VARCHAR NOT NULL DEFAULT 'active',
                last_checked_at DATETIME,
                last_success_at DATETIME,
                failure_reason TEXT,
                observed_model_label VARCHAR,
                observed_model_cost_label VARCHAR,
                created_at DATETIME,
                updated_at DATETIME,
                CHECK (
                    (project_id IS NOT NULL AND series_id IS NULL)
                    OR (project_id IS NULL AND series_id IS NOT NULL)
                ),
                CHECK (status IN ('active', 'needs_check', 'invalid', 'rotated')),
                FOREIGN KEY (project_id) REFERENCES video_projects(id),
                FOREIGN KEY (series_id) REFERENCES video_series(id)
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
                enable_codex_repair BOOLEAN NOT NULL DEFAULT 0,
                credit_approval_policy VARCHAR NOT NULL DEFAULT 'approve_dont_ask_again',
                max_credit_per_job INTEGER,
                credit_spent_estimate INTEGER NOT NULL DEFAULT 0,
                render_job_id VARCHAR,
                download_dir VARCHAR,
                repair_status VARCHAR,
                repair_attempt_count INTEGER NOT NULL DEFAULT 0,
                repair_report_json JSON,
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
                observed_model_label VARCHAR,
                observed_model_cost_label VARCHAR,
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
            CREATE TABLE IF NOT EXISTS video_codex_repair_attempts (
                id VARCHAR PRIMARY KEY,
                job_id VARCHAR NOT NULL,
                item_id VARCHAR,
                project_id VARCHAR NOT NULL,
                status VARCHAR NOT NULL DEFAULT 'queued',
                error_code VARCHAR NOT NULL,
                step_name VARCHAR,
                repair_context_json JSON,
                files_changed_json JSON,
                tests_run_json JSON,
                test_result VARCHAR,
                failure_reason TEXT,
                requires_approval BOOLEAN NOT NULL DEFAULT 0,
                created_at DATETIME,
                updated_at DATETIME,
                completed_at DATETIME,
                FOREIGN KEY (job_id) REFERENCES video_clip_generation_jobs(id),
                FOREIGN KEY (item_id) REFERENCES video_clip_generation_items(id),
                FOREIGN KEY (project_id) REFERENCES video_projects(id)
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
                speech_cues_json JSON,
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
                revision INTEGER NOT NULL DEFAULT 1,
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
                quality_threshold FLOAT NOT NULL DEFAULT 85,
                parent_prompt_id VARCHAR,
                repair_attempt INTEGER NOT NULL DEFAULT 0,
                repair_status VARCHAR NOT NULL DEFAULT 'none',
                repair_changes_json JSON,
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
                enhanced_plan_path VARCHAR,
                review_report_path VARCHAR,
                enhanced_artifacts_json JSON,
                review_status VARCHAR,
                fix_attempt_count INTEGER NOT NULL DEFAULT 0,
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
                revision INTEGER NOT NULL DEFAULT 1,
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
                revision INTEGER NOT NULL DEFAULT 1,
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
        conn.execute(text("CREATE UNIQUE INDEX IF NOT EXISTS ux_video_publishing_metadata_project ON video_publishing_metadata(project_id)"))
        conn.execute(text("CREATE INDEX IF NOT EXISTS idx_video_publishing_metadata_project_status ON video_publishing_metadata(project_id, status)"))
        conn.execute(text("CREATE INDEX IF NOT EXISTS idx_video_provider_sessions_provider_default ON video_provider_sessions(provider, is_default)"))
        conn.execute(text("CREATE INDEX IF NOT EXISTS idx_video_provider_sessions_status ON video_provider_sessions(provider, status)"))
        conn.execute(text("CREATE INDEX IF NOT EXISTS idx_video_provider_bindings_project_status ON video_provider_project_bindings(project_id, provider, provider_tool, status)"))
        conn.execute(text("CREATE INDEX IF NOT EXISTS idx_video_provider_bindings_series_status ON video_provider_project_bindings(series_id, provider, provider_tool, status)"))
        conn.execute(text("CREATE INDEX IF NOT EXISTS idx_video_provider_bindings_hash ON video_provider_project_bindings(provider_project_ref_hash)"))
        conn.execute(text("""
            CREATE UNIQUE INDEX IF NOT EXISTS ux_video_provider_bindings_active_project
            ON video_provider_project_bindings(project_id, provider, provider_tool)
            WHERE project_id IS NOT NULL AND status IN ('active', 'needs_check')
        """))
        conn.execute(text("""
            CREATE UNIQUE INDEX IF NOT EXISTS ux_video_provider_bindings_active_series
            ON video_provider_project_bindings(series_id, provider, provider_tool)
            WHERE series_id IS NOT NULL AND status IN ('active', 'needs_check')
        """))
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
        conn.execute(text("CREATE INDEX IF NOT EXISTS idx_series_character_profiles_series_order ON series_character_profiles(series_id, sort_order, created_at)"))
        conn.execute(text("CREATE INDEX IF NOT EXISTS idx_story_episodes_series_number ON story_episodes(series_id, episode_number)"))
        conn.execute(text("CREATE INDEX IF NOT EXISTS idx_story_candidates_episode ON story_scenario_candidates(story_episode_id, created_at)"))
        conn.execute(text("CREATE INDEX IF NOT EXISTS idx_story_adaptations_episode_kind ON story_adaptations(story_episode_id, kind)"))
        conn.execute(text("CREATE INDEX IF NOT EXISTS idx_series_reference_assets_entity ON series_reference_assets(series_id, entity_type, entity_id, approval_status, active)"))
        conn.execute(text("CREATE INDEX IF NOT EXISTS idx_series_version_records_entity ON series_version_records(series_id, entity_type, entity_id, revision)"))
        conn.execute(text("CREATE INDEX IF NOT EXISTS idx_artifact_dependency_source ON artifact_dependency_snapshots(series_id, dependency_type, dependency_id, dependency_scope)"))
        conn.execute(text("CREATE INDEX IF NOT EXISTS idx_artifact_dependency_artifact ON artifact_dependency_snapshots(series_id, artifact_type, artifact_id)"))
        conn.execute(text("CREATE INDEX IF NOT EXISTS idx_artifact_stale_events_series_status ON artifact_stale_events(series_id, status, created_at)"))
        conn.execute(text("CREATE INDEX IF NOT EXISTS idx_video_codex_repair_job_created ON video_codex_repair_attempts(job_id, created_at)"))
        conn.execute(text("CREATE INDEX IF NOT EXISTS idx_video_codex_repair_status ON video_codex_repair_attempts(status, created_at)"))
        ai_planning_columns = {row[1] for row in conn.execute(text("PRAGMA table_info(ai_planning_settings)")).fetchall()}
        if "model_reasoning_effort" not in ai_planning_columns:
            conn.execute(text("ALTER TABLE ai_planning_settings ADD COLUMN model_reasoning_effort VARCHAR"))
        story_candidate_columns = {row[1] for row in conn.execute(text("PRAGMA table_info(story_scenario_candidates)")).fetchall()}
        story_candidate_column_defaults = {
            "context_snapshot_id": "VARCHAR",
            "model_label": "VARCHAR",
            "generation_attempt": "INTEGER NOT NULL DEFAULT 1",
            "generation_status": "VARCHAR NOT NULL DEFAULT 'completed'",
            "generation_metadata_json": "JSON",
            "evaluation_status": "VARCHAR NOT NULL DEFAULT 'pending'",
            "evaluation_json": "JSON",
        }
        for column_name, column_sql in story_candidate_column_defaults.items():
            if column_name not in story_candidate_columns:
                conn.execute(text(f"ALTER TABLE story_scenario_candidates ADD COLUMN {column_name} {column_sql}"))
        series_columns = {row[1] for row in conn.execute(text("PRAGMA table_info(video_series)")).fetchall()}
        if "series_mode" not in series_columns:
            conn.execute(text("ALTER TABLE video_series ADD COLUMN series_mode VARCHAR NOT NULL DEFAULT 'video_story_only'"))
        else:
            conn.execute(text("UPDATE video_series SET series_mode = 'video_story_only' WHERE series_mode IS NULL OR TRIM(series_mode) = ''"))
        if "revision" not in series_columns:
            conn.execute(text("ALTER TABLE video_series ADD COLUMN revision INTEGER NOT NULL DEFAULT 1"))

        character_profile_columns = {row[1] for row in conn.execute(text("PRAGMA table_info(series_character_profiles)")).fetchall()}
        if "revision" not in character_profile_columns:
            conn.execute(text("ALTER TABLE series_character_profiles ADD COLUMN revision INTEGER NOT NULL DEFAULT 1"))

        story_episode_columns = {row[1] for row in conn.execute(text("PRAGMA table_info(story_episodes)")).fetchall()}
        if "output_settings_json" not in story_episode_columns:
            conn.execute(text("ALTER TABLE story_episodes ADD COLUMN output_settings_json JSON"))
        if "revision" not in story_episode_columns:
            conn.execute(text("ALTER TABLE story_episodes ADD COLUMN revision INTEGER NOT NULL DEFAULT 1"))

        story_adaptation_columns = {row[1] for row in conn.execute(text("PRAGMA table_info(story_adaptations)")).fetchall()}
        if "revision" not in story_adaptation_columns:
            conn.execute(text("ALTER TABLE story_adaptations ADD COLUMN revision INTEGER NOT NULL DEFAULT 1"))
        project_columns = {row[1] for row in conn.execute(text("PRAGMA table_info(video_projects)")).fetchall()}
        project_column_defaults = {
            "series_id": "VARCHAR",
            "story_episode_id": "VARCHAR",
            "episode_number": "INTEGER",
            "episode_title": "VARCHAR",
            "phase": "VARCHAR NOT NULL DEFAULT 'phase1'",
            "target_language": "VARCHAR NOT NULL DEFAULT 'en'",
            "speech_source": "VARCHAR",
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
        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS news_video_workflows (
                project_id VARCHAR PRIMARY KEY,
                visual_format VARCHAR NOT NULL DEFAULT 'tech_explainer',
                source_note TEXT,
                default_speech_source VARCHAR NOT NULL DEFAULT 'voicebox_khong_context',
                created_at DATETIME,
                updated_at DATETIME,
                FOREIGN KEY (project_id) REFERENCES video_projects(id)
            )
        """))
        scene_columns = {row[1] for row in conn.execute(text("PRAGMA table_info(video_scenes)")).fetchall()}
        if "approved" not in scene_columns:
            conn.execute(text("ALTER TABLE video_scenes ADD COLUMN approved BOOLEAN NOT NULL DEFAULT 0"))
        if "no_narration" not in scene_columns:
            conn.execute(text("ALTER TABLE video_scenes ADD COLUMN no_narration BOOLEAN NOT NULL DEFAULT 0"))
        if "revision" not in scene_columns:
            conn.execute(text("ALTER TABLE video_scenes ADD COLUMN revision INTEGER NOT NULL DEFAULT 1"))
        shot_columns = {row[1] for row in conn.execute(text("PRAGMA table_info(video_shots)")).fetchall()}
        shot_column_defaults = {
            "retention_json": "JSON",
            "transition_json": "JSON",
            "sound_design_json": "JSON",
            "micro_scenes_json": "JSON",
            "speech_cues_json": "JSON",
            "speech_source_override": "VARCHAR",
            "retainability_quality_check": "JSON",
            "revision": "INTEGER NOT NULL DEFAULT 1",
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
            "quality_threshold": "FLOAT NOT NULL DEFAULT 85",
            "parent_prompt_id": "VARCHAR",
            "repair_attempt": "INTEGER NOT NULL DEFAULT 0",
            "repair_status": "VARCHAR NOT NULL DEFAULT 'none'",
            "repair_changes_json": "JSON",
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
            "enable_codex_repair": "BOOLEAN NOT NULL DEFAULT 0",
            "max_credit_per_job": "INTEGER",
            "credit_spent_estimate": "INTEGER NOT NULL DEFAULT 0",
            "render_job_id": "VARCHAR",
            "download_dir": "VARCHAR",
            "repair_status": "VARCHAR",
            "repair_attempt_count": "INTEGER NOT NULL DEFAULT 0",
            "repair_report_json": "JSON",
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
            "observed_model_label": "VARCHAR",
            "observed_model_cost_label": "VARCHAR",
            "download_correlation_id": "VARCHAR",
            "download_url_hash": "VARCHAR",
            "original_filename": "VARCHAR",
            "downloaded_file_path": "VARCHAR",
            "clip_id": "VARCHAR",
        }
        for column_name, column_sql in clip_item_column_defaults.items():
            if column_name not in clip_item_columns:
                conn.execute(text(f"ALTER TABLE video_clip_generation_items ADD COLUMN {column_name} {column_sql}"))
        render_job_columns = {row[1] for row in conn.execute(text("PRAGMA table_info(video_render_jobs)")).fetchall()}
        render_job_column_defaults = {
            "enhanced_plan_path": "VARCHAR",
            "review_report_path": "VARCHAR",
            "enhanced_artifacts_json": "JSON",
            "review_status": "VARCHAR",
            "fix_attempt_count": "INTEGER NOT NULL DEFAULT 0",
        }
        for column_name, column_sql in render_job_column_defaults.items():
            if column_name not in render_job_columns:
                conn.execute(text(f"ALTER TABLE video_render_jobs ADD COLUMN {column_name} {column_sql}"))
        subtitle_columns = {row[1] for row in conn.execute(text("PRAGMA table_info(video_subtitles)")).fetchall()}
        if "revision" not in subtitle_columns:
            conn.execute(text("ALTER TABLE video_subtitles ADD COLUMN revision INTEGER NOT NULL DEFAULT 1"))
        package_export_columns = {row[1] for row in conn.execute(text("PRAGMA table_info(video_package_exports)")).fetchall()}
        if "revision" not in package_export_columns:
            conn.execute(text("ALTER TABLE video_package_exports ADD COLUMN revision INTEGER NOT NULL DEFAULT 1"))
        conn.commit()


def _migrate_video_inspiration(engine) -> None:
    """Create video inspiration tables for existing SQLite databases."""
    with engine.connect() as conn:
        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS video_inspiration_jobs (
                id VARCHAR PRIMARY KEY,
                source_type VARCHAR NOT NULL DEFAULT 'upload',
                source_url TEXT,
                original_filename VARCHAR,
                source_platform VARCHAR NOT NULL DEFAULT 'unknown',
                source_path VARCHAR,
                audio_path VARCHAR,
                source_duration_seconds FLOAT,
                status VARCHAR NOT NULL DEFAULT 'uploaded',
                current_step VARCHAR NOT NULL DEFAULT 'source_ready',
                progress FLOAT NOT NULL DEFAULT 0,
                target_language VARCHAR NOT NULL DEFAULT 'vi',
                rewrite_mode VARCHAR NOT NULL DEFAULT 'bold_remix',
                user_direction TEXT,
                transcript_text TEXT,
                transcript_language VARCHAR,
                transcript_status VARCHAR NOT NULL DEFAULT 'pending',
                analysis_schema_version VARCHAR NOT NULL DEFAULT 'video_analysis_package.v1',
                analysis_mode VARCHAR NOT NULL DEFAULT 'quick',
                analysis_package_json JSON,
                analysis_package_path VARCHAR,
                coverage_metrics_json JSON,
                limitations_json JSON,
                retention_source VARCHAR NOT NULL DEFAULT 'predicted_from_content',
                analysis_completeness VARCHAR NOT NULL DEFAULT 'not_started',
                visual_summary TEXT,
                analysis_json JSON,
                rewritten_script TEXT,
                script_title VARCHAR,
                big_idea TEXT,
                hook TEXT,
                created_video_project_id VARCHAR,
                latest_auto_run_id VARCHAR,
                failure_reason TEXT,
                error_code VARCHAR,
                created_at DATETIME,
                updated_at DATETIME,
                FOREIGN KEY (created_video_project_id) REFERENCES video_projects(id),
                FOREIGN KEY (latest_auto_run_id) REFERENCES video_auto_runs(id)
            )
        """))
        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS video_inspiration_frames (
                id VARCHAR PRIMARY KEY,
                job_id VARCHAR NOT NULL,
                shot_id VARCHAR,
                shot_order INTEGER,
                frame_role VARCHAR NOT NULL DEFAULT 'keyframe',
                frame_path VARCHAR NOT NULL,
                timestamp_seconds FLOAT NOT NULL DEFAULT 0,
                description_vi TEXT,
                technical_metadata_json JSON,
                created_at DATETIME,
                FOREIGN KEY (job_id) REFERENCES video_inspiration_jobs(id),
                FOREIGN KEY (shot_id) REFERENCES video_inspiration_shots(id)
            )
        """))
        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS video_inspiration_shots (
                id VARCHAR PRIMARY KEY,
                job_id VARCHAR NOT NULL,
                shot_order INTEGER NOT NULL,
                start_seconds FLOAT NOT NULL DEFAULT 0,
                end_seconds FLOAT NOT NULL DEFAULT 0,
                duration_seconds FLOAT NOT NULL DEFAULT 0,
                keyframe_ids_json JSON,
                visual_description_vi TEXT,
                subjects_json JSON,
                setting_json JSON,
                camera_json JSON,
                subject_motion_json JSON,
                transition_in VARCHAR,
                transition_out VARCHAR,
                on_screen_text_json JSON,
                confidence_json JSON,
                limitations_json JSON,
                created_at DATETIME,
                updated_at DATETIME,
                FOREIGN KEY (job_id) REFERENCES video_inspiration_jobs(id)
            )
        """))
        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS video_inspiration_transcript_segments (
                id VARCHAR PRIMARY KEY,
                job_id VARCHAR NOT NULL,
                segment_order INTEGER NOT NULL,
                start_seconds FLOAT NOT NULL DEFAULT 0,
                end_seconds FLOAT NOT NULL DEFAULT 0,
                text TEXT NOT NULL DEFAULT '',
                raw_text TEXT,
                language VARCHAR,
                speaker_label VARCHAR,
                source VARCHAR NOT NULL DEFAULT 'stt_raw',
                timestamp_precision VARCHAR NOT NULL DEFAULT 'chunk',
                confidence FLOAT,
                shot_ids_json JSON,
                created_at DATETIME,
                updated_at DATETIME,
                FOREIGN KEY (job_id) REFERENCES video_inspiration_jobs(id)
            )
        """))
        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS video_inspiration_audio_events (
                id VARCHAR PRIMARY KEY,
                job_id VARCHAR NOT NULL,
                event_order INTEGER NOT NULL,
                event_type VARCHAR NOT NULL,
                start_seconds FLOAT NOT NULL DEFAULT 0,
                end_seconds FLOAT NOT NULL DEFAULT 0,
                description_vi TEXT,
                confidence FLOAT,
                technical_metadata_json JSON,
                shot_ids_json JSON,
                transcript_segment_ids_json JSON,
                created_at DATETIME,
                FOREIGN KEY (job_id) REFERENCES video_inspiration_jobs(id)
            )
        """))
        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS video_inspiration_text_events (
                id VARCHAR PRIMARY KEY,
                job_id VARCHAR NOT NULL,
                shot_id VARCHAR,
                event_order INTEGER NOT NULL,
                start_seconds FLOAT NOT NULL DEFAULT 0,
                end_seconds FLOAT NOT NULL DEFAULT 0,
                text TEXT NOT NULL DEFAULT '',
                language VARCHAR,
                role VARCHAR NOT NULL DEFAULT 'unknown',
                region_json JSON,
                confidence FLOAT,
                source VARCHAR NOT NULL DEFAULT 'vision',
                created_at DATETIME,
                updated_at DATETIME,
                FOREIGN KEY (job_id) REFERENCES video_inspiration_jobs(id),
                FOREIGN KEY (shot_id) REFERENCES video_inspiration_shots(id)
            )
        """))
        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS video_inspiration_retention_beats (
                id VARCHAR PRIMARY KEY,
                job_id VARCHAR NOT NULL,
                beat_order INTEGER NOT NULL,
                start_seconds FLOAT NOT NULL DEFAULT 0,
                end_seconds FLOAT NOT NULL DEFAULT 0,
                role VARCHAR NOT NULL DEFAULT 'development',
                viewer_question_before TEXT,
                content_promise TEXT,
                new_information TEXT,
                emotional_or_stakes_change TEXT,
                question_answered TEXT,
                new_open_loop TEXT,
                micro_payoff TEXT,
                why_continue TEXT,
                drop_off_risks_json JSON,
                evidence_refs_json JSON,
                confidence FLOAT,
                created_at DATETIME,
                updated_at DATETIME,
                FOREIGN KEY (job_id) REFERENCES video_inspiration_jobs(id)
            )
        """))
        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS video_inspiration_handoffs (
                id VARCHAR PRIMARY KEY,
                job_id VARCHAR NOT NULL,
                analysis_package_path VARCHAR,
                analysis_package_revision VARCHAR NOT NULL DEFAULT 'video_analysis_package.v1',
                schema_version VARCHAR NOT NULL DEFAULT 'video_inspiration_handoff.v1',
                status VARCHAR NOT NULL DEFAULT 'draft',
                target_language VARCHAR NOT NULL DEFAULT 'vi',
                approved_script_revision INTEGER NOT NULL DEFAULT 1,
                payload_json JSON NOT NULL DEFAULT '{}',
                source_blocks_json JSON,
                created_project_id VARCHAR,
                revision INTEGER NOT NULL DEFAULT 1,
                created_at DATETIME,
                updated_at DATETIME,
                approved_at DATETIME,
                FOREIGN KEY (job_id) REFERENCES video_inspiration_jobs(id),
                FOREIGN KEY (created_project_id) REFERENCES video_projects(id)
            )
        """))
        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS video_project_memory_cards (
                id VARCHAR PRIMARY KEY,
                project_id VARCHAR NOT NULL,
                series_id VARCHAR,
                memory_scope VARCHAR NOT NULL DEFAULT 'project',
                card_type VARCHAR NOT NULL,
                title VARCHAR NOT NULL,
                content_json JSON NOT NULL DEFAULT '{}',
                status VARCHAR NOT NULL DEFAULT 'approved',
                source_type VARCHAR NOT NULL DEFAULT 'handoff',
                source_ref_id VARCHAR,
                revision INTEGER NOT NULL DEFAULT 1,
                created_at DATETIME,
                updated_at DATETIME,
                approved_at DATETIME,
                FOREIGN KEY (project_id) REFERENCES video_projects(id),
                FOREIGN KEY (series_id) REFERENCES video_series(id)
            )
        """))
        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS video_project_target_timeline_beats (
                id VARCHAR PRIMARY KEY,
                project_id VARCHAR NOT NULL,
                handoff_id VARCHAR,
                beat_order INTEGER NOT NULL,
                start_seconds FLOAT NOT NULL DEFAULT 0,
                end_seconds FLOAT NOT NULL DEFAULT 0,
                duration_seconds FLOAT NOT NULL DEFAULT 0,
                role VARCHAR NOT NULL DEFAULT 'development',
                content TEXT,
                viewer_question TEXT,
                new_information TEXT,
                micro_payoff TEXT,
                visual_direction TEXT,
                audio_direction TEXT,
                evidence_refs_json JSON,
                source_lesson_refs_json JSON,
                revision INTEGER NOT NULL DEFAULT 1,
                created_at DATETIME,
                updated_at DATETIME,
                FOREIGN KEY (project_id) REFERENCES video_projects(id),
                FOREIGN KEY (handoff_id) REFERENCES video_inspiration_handoffs(id)
            )
        """))
        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS video_project_context_snapshots (
                id VARCHAR PRIMARY KEY,
                project_id VARCHAR NOT NULL,
                task_type VARCHAR NOT NULL,
                artifact_type VARCHAR,
                artifact_id VARCHAR,
                context_json JSON NOT NULL DEFAULT '{}',
                source_refs_json JSON,
                created_at DATETIME,
                FOREIGN KEY (project_id) REFERENCES video_projects(id)
            )
        """))
        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS video_quality_reports (
                id VARCHAR PRIMARY KEY,
                project_id VARCHAR,
                job_id VARCHAR,
                scope VARCHAR NOT NULL DEFAULT 'project',
                status VARCHAR NOT NULL DEFAULT 'not_checked',
                overall_status VARCHAR NOT NULL DEFAULT 'not_checked',
                content_score FLOAT NOT NULL DEFAULT 0,
                presentation_score FLOAT NOT NULL DEFAULT 0,
                total_score FLOAT NOT NULL DEFAULT 0,
                rubric_json JSON NOT NULL DEFAULT '{}',
                sections_json JSON NOT NULL DEFAULT '{}',
                blocking_errors_json JSON,
                warnings_json JSON,
                recommended_actions_json JSON,
                evidence_json JSON,
                dependencies_json JSON,
                override_history_json JSON,
                revision INTEGER NOT NULL DEFAULT 1,
                checked_at DATETIME,
                created_at DATETIME,
                updated_at DATETIME,
                FOREIGN KEY (project_id) REFERENCES video_projects(id),
                FOREIGN KEY (job_id) REFERENCES video_inspiration_jobs(id)
            )
        """))
        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS platform_retention_datasets (
                id VARCHAR PRIMARY KEY,
                project_id VARCHAR,
                job_id VARCHAR,
                platform VARCHAR NOT NULL DEFAULT 'manual',
                video_duration_seconds FLOAT NOT NULL DEFAULT 0,
                data_points_json JSON NOT NULL DEFAULT '[]',
                normalized_points_json JSON NOT NULL DEFAULT '[]',
                average_watch_time FLOAT,
                completion_rate FLOAT,
                rewatch_rate FLOAT,
                cta_click_rate FLOAT,
                conversion_rate FLOAT,
                source_type VARCHAR NOT NULL DEFAULT 'manual',
                linked_findings_json JSON,
                imported_at DATETIME,
                created_at DATETIME,
                FOREIGN KEY (project_id) REFERENCES video_projects(id),
                FOREIGN KEY (job_id) REFERENCES video_inspiration_jobs(id)
            )
        """))
        conn.execute(text("CREATE INDEX IF NOT EXISTS idx_video_inspiration_jobs_updated ON video_inspiration_jobs(updated_at)"))
        conn.execute(text("CREATE INDEX IF NOT EXISTS idx_video_inspiration_jobs_status ON video_inspiration_jobs(status)"))
        conn.execute(text("CREATE INDEX IF NOT EXISTS idx_video_inspiration_frames_job_time ON video_inspiration_frames(job_id, timestamp_seconds)"))
        conn.execute(text("CREATE INDEX IF NOT EXISTS idx_video_inspiration_shots_job_time ON video_inspiration_shots(job_id, start_seconds, end_seconds)"))
        conn.execute(text("CREATE INDEX IF NOT EXISTS idx_video_inspiration_transcript_job_time ON video_inspiration_transcript_segments(job_id, start_seconds, end_seconds)"))
        conn.execute(text("CREATE INDEX IF NOT EXISTS idx_video_inspiration_audio_job_time ON video_inspiration_audio_events(job_id, start_seconds, end_seconds)"))
        conn.execute(text("CREATE INDEX IF NOT EXISTS idx_video_inspiration_text_job_time ON video_inspiration_text_events(job_id, start_seconds, end_seconds)"))
        conn.execute(text("CREATE INDEX IF NOT EXISTS idx_video_inspiration_retention_job_time ON video_inspiration_retention_beats(job_id, start_seconds, end_seconds)"))
        conn.execute(text("CREATE INDEX IF NOT EXISTS idx_video_inspiration_handoffs_job_status ON video_inspiration_handoffs(job_id, status)"))
        conn.execute(text("CREATE INDEX IF NOT EXISTS idx_video_project_memory_project_type ON video_project_memory_cards(project_id, card_type)"))
        conn.execute(text("CREATE INDEX IF NOT EXISTS idx_video_project_timeline_project_time ON video_project_target_timeline_beats(project_id, start_seconds, end_seconds)"))
        conn.execute(text("CREATE INDEX IF NOT EXISTS idx_video_project_context_project_task ON video_project_context_snapshots(project_id, task_type, created_at)"))
        conn.execute(text("CREATE INDEX IF NOT EXISTS idx_video_quality_reports_project_checked ON video_quality_reports(project_id, checked_at)"))
        conn.execute(text("CREATE INDEX IF NOT EXISTS idx_video_quality_reports_job_checked ON video_quality_reports(job_id, checked_at)"))
        conn.execute(text("CREATE INDEX IF NOT EXISTS idx_platform_retention_project_created ON platform_retention_datasets(project_id, created_at)"))
        conn.execute(text("CREATE INDEX IF NOT EXISTS idx_platform_retention_job_created ON platform_retention_datasets(job_id, created_at)"))
        job_columns = {row[1] for row in conn.execute(text("PRAGMA table_info(video_inspiration_jobs)")).fetchall()}
        if "source_duration_seconds" not in job_columns:
            conn.execute(text("ALTER TABLE video_inspiration_jobs ADD COLUMN source_duration_seconds FLOAT"))
        if "user_direction" not in job_columns:
            conn.execute(text("ALTER TABLE video_inspiration_jobs ADD COLUMN user_direction TEXT"))
        for column_name, column_sql in (
            ("analysis_schema_version", "VARCHAR NOT NULL DEFAULT 'video_analysis_package.v1'"),
            ("analysis_mode", "VARCHAR NOT NULL DEFAULT 'quick'"),
            ("analysis_package_json", "JSON"),
            ("analysis_package_path", "VARCHAR"),
            ("coverage_metrics_json", "JSON"),
            ("limitations_json", "JSON"),
            ("retention_source", "VARCHAR NOT NULL DEFAULT 'predicted_from_content'"),
            ("analysis_completeness", "VARCHAR NOT NULL DEFAULT 'not_started'"),
        ):
            if column_name not in job_columns:
                conn.execute(text(f"ALTER TABLE video_inspiration_jobs ADD COLUMN {column_name} {column_sql}"))
        frame_columns = {row[1] for row in conn.execute(text("PRAGMA table_info(video_inspiration_frames)")).fetchall()}
        for column_name, column_sql in (
            ("shot_id", "VARCHAR"),
            ("shot_order", "INTEGER"),
            ("frame_role", "VARCHAR NOT NULL DEFAULT 'keyframe'"),
        ):
            if column_name not in frame_columns:
                conn.execute(text(f"ALTER TABLE video_inspiration_frames ADD COLUMN {column_name} {column_sql}"))
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


def _migrate_comic_series_analysis(engine) -> None:
    """Additive migration for Comic Series Analysis (change 13).

    The new ``comic_*`` and ``story_episode_source_*`` tables are created by
    ``Base.metadata.create_all``. This migration is responsible for the two
    kinds of change ``create_all`` cannot do idempotently on existing DBs:

      1. Adding new columns to pre-existing tables (``story_episodes`` and
         ``story_scenario_candidates``).
      2. Creating indexes (task 2.7).

    It is idempotent: every column add checks existence first, and every
    index uses ``CREATE INDEX IF NOT EXISTS``. Running it twice on a legacy
    or fresh DB leaves data unchanged.
    """
    inspector = inspect(engine)
    tables = set(inspector.get_table_names())

    # --- 0. Create comic tables explicitly so indexes can build on the ----
    # first run (create_all runs after migrations). CREATE TABLE IF NOT
    # EXISTS is idempotent; create_all is a no-op for tables that exist.
    _create_comic_tables(engine)

    # --- 1. Additive columns on existing tables (tasks 2.13, 2.14) --------
    if "story_episodes" in tables:
        episode_cols = _get_columns(inspector, "story_episodes")
        additions = {
            "current_source_document_id": "current_source_document_id VARCHAR",
            "development_mode": "development_mode VARCHAR",
            "rights_attestation_revision": "rights_attestation_revision INTEGER",
            "master_story_approval_status": "master_story_approval_status VARCHAR",
            "master_story_approved_at": "master_story_approved_at DATETIME",
        }
        for name, column_sql in additions.items():
            if name not in episode_cols:
                _add_column(engine, "story_episodes", column_sql, name)

    if "story_scenario_candidates" in tables:
        candidate_cols = _get_columns(inspector, "story_scenario_candidates")
        additions = {
            "source_document_id": "source_document_id VARCHAR",
            "source_document_revision": "source_document_revision INTEGER",
            "development_mode": "development_mode VARCHAR",
            "dependency_fingerprint": "dependency_fingerprint VARCHAR",
        }
        for name, column_sql in additions.items():
            if name not in candidate_cols:
                _add_column(engine, "story_scenario_candidates", column_sql, name)

    tables = set(inspect(engine).get_table_names())
    if "comic_series_handoffs" in tables:
        handoff_cols = _get_columns(inspect(engine), "comic_series_handoffs")
        if "target_series_title" not in handoff_cols:
            _add_column(engine, "comic_series_handoffs", "target_series_title VARCHAR", "target_series_title")

    # --- 2. Indexes (task 2.7) --------------------------------------------
    # These reference comic_* tables created by create_all, which runs AFTER
    # migrations. Guard with a re-inspection so a first-ever run (where the
    # tables don't exist yet) is a no-op; create_all + next startup builds them.
    tables = set(inspect(engine).get_table_names())
    index_specs = [
        ("comic_analysis_jobs", "idx_comic_jobs_status", "run_status, updated_at"),
        ("comic_analysis_jobs", "idx_comic_jobs_source_doc", "current_source_document_id"),
        ("comic_source_documents", "idx_comic_source_docs_job", "job_id, revision"),
        ("comic_source_documents", "idx_comic_source_docs_hash", "content_hash"),
        ("comic_source_pages", "idx_comic_pages_doc_order", "document_id, page_order"),
        ("comic_source_assets", "idx_comic_assets_doc_order", "document_id, asset_order"),
        ("comic_source_assets", "idx_comic_assets_checksum", "checksum"),
        ("comic_panels", "idx_comic_panels_job_rev_order", "job_id, analysis_revision, reading_order"),
        ("comic_speech_bubbles", "idx_comic_bubbles_panel_order", "panel_id, reading_order"),
        ("comic_detected_characters", "idx_comic_characters_job_rev", "job_id, analysis_revision"),
        ("comic_detected_locations", "idx_comic_locations_job_rev", "job_id, analysis_revision"),
        ("comic_approval_manifests", "idx_comic_manifests_job_rev", "job_id, analysis_revision, active"),
        ("comic_series_handoffs", "idx_comic_handoffs_job", "job_id, created_at"),
        ("comic_series_handoffs", "idx_comic_handoffs_idempotency", "idempotency_key"),
        ("comic_series_handoff_items", "idx_comic_handoff_items_handoff", "handoff_id"),
        ("story_episode_source_documents", "idx_ep_source_docs_episode", "story_episode_id, revision"),
        ("story_episode_source_chunks", "idx_ep_source_chunks_doc_order", "document_id, chunk_order"),
        ("story_episode_source_assets", "idx_ep_source_assets_doc_order", "document_id, asset_order"),
        ("comic_source_version_records", "idx_comic_version_records_target", "target_type, target_id"),
    ]
    with engine.connect() as conn:
        did_work = False
        for table, index_name, columns in index_specs:
            if table not in tables:
                continue
            conn.execute(text(f"CREATE INDEX IF NOT EXISTS {index_name} ON {table}({columns})"))
            did_work = True
        if did_work:
            conn.commit()
            logger.info("Ensured Comic Series Analysis indexes")


def _migrate_research_scoring(engine) -> None:
    """Add ranking, completeness and provenance fields to research scores.

    Migrations run before ``Base.metadata.create_all``. A fresh database does
    not have the Research tables yet, so this helper intentionally becomes a
    no-op there; ``create_all`` then creates the complete current schema.
    """
    inspector = inspect(engine)
    if "research_scores" not in set(inspector.get_table_names()):
        return

    columns = _get_columns(inspector, "research_scores")
    additions = {
        "rank": "rank INTEGER",
        "tie_group": "tie_group INTEGER",
        "completeness_status": "completeness_status VARCHAR NOT NULL DEFAULT 'incomplete'",
        "stale_reason": "stale_reason TEXT",
        "improvement_actions_json": "improvement_actions_json JSON",
        "tradeoffs_json": "tradeoffs_json JSON",
        "safety_gate_json": "safety_gate_json JSON",
        "provider_metadata_json": "provider_metadata_json JSON",
        "cost_json": "cost_json JSON",
        "user_override_revision": "user_override_revision INTEGER NOT NULL DEFAULT 0",
        "user_override_at": "user_override_at DATETIME",
    }
    for name, column_sql in additions.items():
        if name not in columns:
            _add_column(engine, "research_scores", column_sql, name)


def _create_comic_tables(engine) -> None:
    """Create the Comic Series Analysis tables from ORM metadata if missing.

    Uses ``create_all(..., checkfirst=True)`` restricted to the comic tables
    so a first-ever migration run can immediately build indexes on them.
    Idempotent: existing tables are skipped.
    """
    from .models import (
        Base,
        ComicAnalysisJob,
        ComicApprovalManifest,
        ComicDetectedCharacter,
        ComicDetectedLocation,
        ComicPanel,
        ComicPlotAnalysis,
        ComicSeriesHandoff,
        ComicSeriesHandoffItem,
        ComicSourceAsset,
        ComicSourceDocument,
        ComicSourcePage,
        ComicSourceVersionRecord,
        ComicSpeechBubble,
        StoryEpisodeSourceAsset,
        StoryEpisodeSourceChunk,
        StoryEpisodeSourceDocument,
    )

    comic_tables = [
        model.__table__
        for model in (
            ComicSourceDocument,
            ComicAnalysisJob,
            ComicSourcePage,
            ComicSourceAsset,
            ComicPanel,
            ComicSpeechBubble,
            ComicDetectedCharacter,
            ComicDetectedLocation,
            ComicPlotAnalysis,
            ComicApprovalManifest,
            ComicSeriesHandoff,
            ComicSeriesHandoffItem,
            StoryEpisodeSourceDocument,
            StoryEpisodeSourceChunk,
            StoryEpisodeSourceAsset,
            ComicSourceVersionRecord,
        )
    ]
    Base.metadata.create_all(bind=engine, tables=comic_tables, checkfirst=True)


def _supports_drop_column(engine) -> bool:
    """Whether ``ALTER TABLE … DROP COLUMN`` is supported by the dialect +
    runtime. Non-SQLite dialects (Postgres, MySQL) have supported it for
    decades; SQLite only gained the feature in 3.35."""
    if engine.dialect.name != "sqlite":
        return True
    return tuple(int(p) for p in sqlite3.sqlite_version.split(".")[:3]) >= (3, 35, 0)


def _migrate_automation_hub(engine) -> None:
    """Create the isolated Automation Hub tables and indexes idempotently."""
    from .models import (
        AutomationAsset,
        AutomationConnection,
        AutomationPublishAttempt,
        AutomationPublishJob,
        Base,
    )

    tables = [
        AutomationConnection.__table__,
        AutomationAsset.__table__,
        AutomationPublishJob.__table__,
        AutomationPublishAttempt.__table__,
    ]
    Base.metadata.create_all(bind=engine, tables=tables, checkfirst=True)
    with engine.begin() as conn:
        conn.execute(text(
            "CREATE INDEX IF NOT EXISTS idx_automation_connections_platform_status "
            "ON automation_connections(platform, status)"
        ))
        conn.execute(text(
            "CREATE INDEX IF NOT EXISTS idx_automation_assets_sha256 "
            "ON automation_assets(sha256)"
        ))
        conn.execute(text(
            "CREATE INDEX IF NOT EXISTS idx_automation_publish_jobs_status_schedule "
            "ON automation_publish_jobs(status, scheduled_at, created_at)"
        ))
        conn.execute(text(
            "CREATE INDEX IF NOT EXISTS idx_automation_publish_jobs_connection "
            "ON automation_publish_jobs(connection_id, status)"
        ))
        conn.execute(text(
            "CREATE INDEX IF NOT EXISTS idx_automation_publish_attempts_job "
            "ON automation_publish_attempts(job_id, attempt_number)"
        ))


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
        ("video_render_jobs", "enhanced_plan_path"),
        ("video_render_jobs", "review_report_path"),
        ("video_render_jobs", "output_path"),
        ("video_render_jobs", "subtitle_ass_path"),
        ("video_provider_sessions", "chrome_profile_path"),
        ("video_clip_generation_jobs", "download_dir"),
        ("video_clip_generation_items", "downloaded_file_path"),
        ("video_inspiration_jobs", "source_path"),
        ("video_inspiration_jobs", "audio_path"),
        ("video_inspiration_jobs", "analysis_package_path"),
        ("video_inspiration_handoffs", "analysis_package_path"),
        ("video_inspiration_frames", "frame_path"),
        ("comic_analysis_jobs", "analysis_package_path"),
        ("comic_source_documents", "raw_html_quarantine_path"),
        ("comic_source_assets", "original_path"),
        ("story_episode_source_assets", "original_path"),
        ("automation_assets", "stored_path"),
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


def _migrate_product_video(engine) -> None:
    """Create the isolated Product Video tables and indexes idempotently."""
    from .models import (
        Base,
        ProductVideoProject,
        ProductVideoShot,
        ProductVideoShotPrompt,
    )

    tables = [
        ProductVideoProject.__table__,
        ProductVideoShot.__table__,
        ProductVideoShotPrompt.__table__,
    ]
    Base.metadata.create_all(bind=engine, tables=tables, checkfirst=True)
    product_project_columns = _get_columns(inspect(engine), "product_video_projects")
    with engine.begin() as conn:
        # Additive fields are guarded for both the shipped SQLite database and
        # server-backed dialects used by tests/deployments.
        additions = {
            "render_project_id": "render_project_id VARCHAR",
            "creation_mode": "creation_mode VARCHAR NOT NULL DEFAULT 'quick'",
            "automation_mode": "automation_mode VARCHAR NOT NULL DEFAULT 'full_auto'",
            "output_target": "output_target VARCHAR NOT NULL DEFAULT 'render_ready'",
        }
        for name, column_sql in additions.items():
            if name not in product_project_columns:
                conn.execute(text(f"ALTER TABLE product_video_projects ADD COLUMN {column_sql}"))
        conn.execute(text(
            "CREATE INDEX IF NOT EXISTS idx_product_video_shots_project_order "
            "ON product_video_shots(project_id, shot_order)"
        ))
        conn.execute(text(
            "CREATE INDEX IF NOT EXISTS idx_product_video_shot_prompts_project "
            "ON product_video_shot_prompts(project_id, shot_id)"
        ))
        conn.execute(text(
            "CREATE INDEX IF NOT EXISTS idx_product_video_projects_render_project "
            "ON product_video_projects(render_project_id)"
        ))
