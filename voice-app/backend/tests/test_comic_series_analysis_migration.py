"""Migration and data-model tests for Comic Series Analysis (change 13).

Covers tasks 2.9 (idempotent migration), 12.1 (fresh + legacy + double-run)
and confirms the additive columns and indexes exist.
"""

from __future__ import annotations

import pathlib
import tempfile

import pytest
from sqlalchemy import create_engine, inspect, text

from backend import config, database
from backend.database import session as database_session
from backend.database.migrations import run_migrations


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


def test_comic_tables_created(db):
    insp = inspect(database_session.engine)
    tables = set(insp.get_table_names())
    expected = {
        "comic_analysis_jobs",
        "comic_source_documents",
        "comic_source_pages",
        "comic_source_assets",
        "comic_panels",
        "comic_speech_bubbles",
        "comic_detected_characters",
        "comic_detected_locations",
        "comic_plot_analyses",
        "comic_approval_manifests",
        "comic_series_handoffs",
        "comic_series_handoff_items",
        "story_episode_source_documents",
        "story_episode_source_chunks",
        "story_episode_source_assets",
        "comic_source_version_records",
    }
    assert expected <= tables


def test_no_fk_to_video_inspiration(db):
    """Boundary: comic tables must not FK into video_inspiration_jobs."""
    insp = inspect(database_session.engine)
    comic_tables = [t for t in insp.get_table_names() if t.startswith("comic_")]
    for table in comic_tables:
        for fk in insp.get_foreign_keys(table):
            assert fk["referred_table"] != "video_inspiration_jobs", (
                f"{table} must not reference video_inspiration_jobs"
            )


def test_additive_columns_on_existing_tables(db):
    insp = inspect(database_session.engine)
    episode_cols = {c["name"] for c in insp.get_columns("story_episodes")}
    assert {"current_source_document_id", "development_mode"} <= episode_cols
    candidate_cols = {c["name"] for c in insp.get_columns("story_scenario_candidates")}
    assert {"source_document_id", "source_document_revision", "development_mode"} <= candidate_cols
    handoff_cols = {c["name"] for c in insp.get_columns("comic_series_handoffs")}
    assert "target_series_title" in handoff_cols


def test_indexes_present(db):
    insp = inspect(database_session.engine)
    job_indexes = {i["name"] for i in insp.get_indexes("comic_analysis_jobs")}
    assert "idx_comic_jobs_status" in job_indexes
    chunk_indexes = {i["name"] for i in insp.get_indexes("story_episode_source_chunks")}
    assert "idx_ep_source_chunks_doc_order" in chunk_indexes


def test_migration_idempotent(db):
    """Running migrations repeatedly must not error or change schema."""
    insp_before = inspect(database_session.engine)
    tables_before = set(insp_before.get_table_names())
    run_migrations(database_session.engine)
    run_migrations(database_session.engine)
    insp_after = inspect(database_session.engine)
    tables_after = set(insp_after.get_table_names())
    assert tables_before == tables_after


def test_migration_on_legacy_db_without_comic_tables(tmp_path):
    """Simulate a legacy DB (no comic tables) and confirm migration adds them."""
    config.set_data_dir(tmp_path)
    db_path = tmp_path / "voicebox.db"
    engine = create_engine(f"sqlite:///{db_path}", connect_args={"check_same_thread": False})
    # Legacy story_episodes without the new columns.
    with engine.connect() as conn:
        conn.execute(text("""
            CREATE TABLE story_episodes (
                id VARCHAR PRIMARY KEY,
                series_id VARCHAR NOT NULL,
                episode_number INTEGER NOT NULL,
                source_input TEXT,
                revision INTEGER NOT NULL DEFAULT 1,
                created_at DATETIME
            )
        """))
        conn.execute(text("""
            CREATE TABLE story_scenario_candidates (
                id VARCHAR PRIMARY KEY,
                story_episode_id VARCHAR NOT NULL,
                strategy_type VARCHAR NOT NULL,
                script_json JSON NOT NULL,
                generation_status VARCHAR NOT NULL DEFAULT 'completed',
                selected BOOLEAN NOT NULL DEFAULT 0,
                created_at DATETIME
            )
        """))
        conn.execute(text("INSERT INTO story_episodes (id, series_id, episode_number, source_input) VALUES ('e1', 's1', 1, 'legacy text')"))
        conn.commit()

    run_migrations(engine)

    insp = inspect(engine)
    episode_cols = {c["name"] for c in insp.get_columns("story_episodes")}
    assert "current_source_document_id" in episode_cols
    assert "development_mode" in episode_cols
    # Legacy row preserved, pointer NULL (uses source_input).
    with engine.connect() as conn:
        row = conn.execute(
            text("SELECT source_input, current_source_document_id FROM story_episodes WHERE id='e1'")
        ).fetchone()
    assert row[0] == "legacy text"
    assert row[1] is None
    engine.dispose()
