import sqlite3
from pathlib import Path


DB_PATH = Path("data/voicebox.db").resolve()

KEEP_TABLES = {
    "ai_planning_settings",
    "audio_channels",
    "automation_connections",
    "capture_settings",
    "channel_device_mappings",
    "effect_presets",
    "generation_settings",
    "mcp_client_bindings",
    "profile_channel_mappings",
    "profile_samples",
    "profiles",
    "video_provider_sessions",
}

PROJECT_TABLES = {
    "artifact_dependency_snapshots",
    "artifact_stale_events",
    "automation_assets",
    "automation_publish_attempts",
    "automation_publish_jobs",
    "captures",
    "comic_analysis_jobs",
    "comic_approval_manifests",
    "comic_detected_characters",
    "comic_detected_locations",
    "comic_panels",
    "comic_plot_analyses",
    "comic_series_handoff_items",
    "comic_series_handoffs",
    "comic_source_assets",
    "comic_source_documents",
    "comic_source_pages",
    "comic_source_version_records",
    "comic_speech_bubbles",
    "generation_versions",
    "generations",
    "platform_retention_datasets",
    "projects",
    "research_chat_messages",
    "research_chat_threads",
    "research_handoffs",
    "research_ideas",
    "research_projects",
    "research_runs",
    "research_scores",
    "research_scripts",
    "research_sources",
    "series_canon_checks",
    "series_character_profiles",
    "series_context_traces",
    "series_current_states",
    "series_memory_cards",
    "series_reference_assets",
    "series_version_records",
    "stories",
    "story_adaptations",
    "story_episode_source_assets",
    "story_episode_source_chunks",
    "story_episode_source_documents",
    "story_episodes",
    "story_items",
    "story_scenario_candidates",
    "video_auto_runs",
    "video_clip_generation_items",
    "video_clip_generation_jobs",
    "video_codex_repair_attempts",
    "video_debug_events",
    "video_inspiration_audio_events",
    "video_inspiration_frames",
    "video_inspiration_handoffs",
    "video_inspiration_jobs",
    "video_inspiration_retention_beats",
    "video_inspiration_shots",
    "video_inspiration_text_events",
    "video_inspiration_transcript_segments",
    "video_package_exports",
    "video_project_context_snapshots",
    "video_project_memory_cards",
    "video_project_target_timeline_beats",
    "video_projects",
    "video_provider_project_bindings",
    "video_publishing_metadata",
    "video_quality_reports",
    "video_render_jobs",
    "video_scene_assets",
    "video_scene_prompts",
    "video_scenes",
    "video_series",
    "video_shot_clips",
    "video_shot_prompts",
    "video_shots",
    "video_source_blocks",
    "video_subtitles",
}


def main() -> None:
    connection = sqlite3.connect(DB_PATH)
    try:
        actual_tables = {
            row[0]
            for row in connection.execute(
                "SELECT name FROM sqlite_master "
                "WHERE type='table' AND name NOT LIKE 'sqlite_%'"
            )
        }
        expected_tables = KEEP_TABLES | PROJECT_TABLES
        if actual_tables != expected_tables:
            unknown = sorted(actual_tables - expected_tables)
            missing = sorted(expected_tables - actual_tables)
            raise RuntimeError(
                f"Schema safety check failed. Unknown={unknown} Missing={missing}"
            )

        rows_before = {
            table: connection.execute(
                f'SELECT count(*) FROM "{table}"'
            ).fetchone()[0]
            for table in PROJECT_TABLES
        }

        connection.execute("PRAGMA foreign_keys=OFF")
        connection.execute("BEGIN IMMEDIATE")
        for table in sorted(PROJECT_TABLES):
            connection.execute(f'DELETE FROM "{table}"')
        connection.commit()
        connection.execute("VACUUM")

        remaining = {
            table: connection.execute(
                f'SELECT count(*) FROM "{table}"'
            ).fetchone()[0]
            for table in PROJECT_TABLES
        }
        nonzero = {table: count for table, count in remaining.items() if count}
        if nonzero:
            raise RuntimeError(f"Project rows remain: {nonzero}")

        print(f"CLEARED_TABLES={len(PROJECT_TABLES)}")
        print(f"CLEARED_ROWS={sum(rows_before.values())}")
        for table in sorted(KEEP_TABLES):
            count = connection.execute(
                f'SELECT count(*) FROM "{table}"'
            ).fetchone()[0]
            print(f"KEPT\t{table}\t{count}")
    finally:
        connection.close()


if __name__ == "__main__":
    main()
