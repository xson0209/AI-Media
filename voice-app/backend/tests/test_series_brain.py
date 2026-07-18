from __future__ import annotations

import pytest

from backend import config, database, models
from backend.database import SeriesCanonCheck as DBSeriesCanonCheck
from backend.database import SeriesContextTrace as DBSeriesContextTrace
from backend.database import session as database_session
from backend.services import series_brain, video_planning_pool, video_projects


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


def _series(db):
    return video_projects.create_series(
        models.VideoSeriesCreate(
            title="Series Brain",
            character_bible="Lan is the lead character.",
            world_bible="The city has a west gate and a clock tower.",
            style_bible="Cinematic webtoon, clean lighting.",
            continuity_rules="Never reset approved memories.",
            negative_rules="No unapproved canon.",
            previous_episode_summary="Episode 1: Lan found the brass key.",
        ),
        db,
    )


def test_draft_memory_card_is_not_selected_until_approved(db):
    series = _series(db)
    draft = series_brain.create_memory_card(
        series.id,
        models.SeriesMemoryCardCreate(
            card_type="canon_rule",
            title="Forbidden dragon",
            content={"forbidden_terms": ["red dragon"]},
            tags=["canon"],
            importance=1.0,
            status="draft",
        ),
        db,
    )

    compiled = series_brain.compile_context(
        series.id,
        models.SeriesContextCompileRequest(
            task_type="story_candidate",
            user_input="A red dragon appears near Lan.",
            max_chars=2400,
            persist_trace=False,
        ),
        db,
    )

    assert draft.id not in {card["id"] for card in compiled.selected_cards}
    assert "Forbidden dragon" not in compiled.context_text

    approved = series_brain.set_memory_card_status(
        series.id,
        draft.id,
        models.SeriesMemoryCardStatusRequest(status="approved"),
        db,
    )
    assert approved is not None
    compiled = series_brain.compile_context(
        series.id,
        models.SeriesContextCompileRequest(
            task_type="story_candidate",
            user_input="A red dragon appears near Lan.",
            max_chars=2400,
            persist_trace=False,
        ),
        db,
    )

    assert draft.id in {card["id"] for card in compiled.selected_cards}
    assert "red dragon" in compiled.context_text


def test_context_budget_persists_safe_trace_and_reports_groups(db):
    series = _series(db)
    card = series_brain.create_memory_card(
        series.id,
        models.SeriesMemoryCardCreate(
            card_type="location",
            title="West gate",
            content={"text": "The west gate has a broken blue lantern that stays visible in night scenes."},
            tags=["west-gate", "location"],
            entity_refs=[{"type": "location", "name": "west gate"}],
            importance=0.9,
            status="approved",
        ),
        db,
    )

    compiled = series_brain.compile_context(
        series.id,
        models.SeriesContextCompileRequest(
            task_type="image_panel_prompt",
            user_input="Lan reaches the west gate at night.",
            current_payload={"panel": "Lan checks the broken lantern."},
            max_chars=2400,
            persist_trace=True,
        ),
        db,
    )

    assert compiled.trace_id
    assert card.id in {item["id"] for item in compiled.selected_cards}
    assert {"immutable_rules", "characters_relationships", "task_payload", "output_rules"}.issubset(
        {group["group"] for group in compiled.group_usage}
    )
    trace = db.get(DBSeriesContextTrace, compiled.trace_id)
    assert trace is not None
    assert trace.context_preview
    assert len(trace.context_preview) <= series_brain.CARD_CONTEXT_PREVIEW_CHARS
    assert trace.selected_cards_json[0]["id"] == card.id


def test_canon_check_blocks_forbidden_term_and_override_records_reason(db):
    series = _series(db)
    card = series_brain.create_memory_card(
        series.id,
        models.SeriesMemoryCardCreate(
            card_type="canon_rule",
            title="No red dragon",
            content={"forbidden_terms": ["red dragon"]},
            importance=1.0,
            status="approved",
        ),
        db,
    )

    blocked = series_brain.check_canon(
        series.id,
        models.SeriesCanonCheckRequest(
            prompt="Lan rides a red dragon through the city.",
            prompt_kind="image_panel_prompt",
            prompt_ref_id="panel-1",
        ),
        db,
    )
    assert blocked.passed is False
    assert blocked.blocking_conflicts
    assert card.id in blocked.evidence_card_ids

    overridden = series_brain.check_canon(
        series.id,
        models.SeriesCanonCheckRequest(
            prompt="Lan rides a red dragon through the city.",
            prompt_kind="image_panel_prompt",
            prompt_ref_id="panel-1",
            allow_override=True,
            override_reason="The user is intentionally revising canon.",
        ),
        db,
    )
    assert overridden.passed is True
    assert overridden.override_reason == "The user is intentionally revising canon."
    rows = db.query(DBSeriesCanonCheck).filter(DBSeriesCanonCheck.series_id == series.id).all()
    assert len(rows) == 2
    assert any(row.overridden_by == "local_user" for row in rows)


def test_current_state_proposal_is_not_used_until_approved(db):
    series = _series(db)
    approved = series_brain.create_current_state(
        series.id,
        models.SeriesCurrentStateCreate(
            based_on_episode_number=1,
            prop_states={"brass key": {"holder": "Lan"}},
            open_threads=[{"title": "Find the clock tower", "status": "open"}],
            approval_status="approved",
        ),
        db,
    )
    proposed = series_brain.propose_current_state(
        series.id,
        models.SeriesStateProposalRequest(notes="Lan gives the brass key to Minh."),
        db,
    )

    compiled = series_brain.compile_context(
        series.id,
        models.SeriesContextCompileRequest(
            task_type="story_candidate",
            user_input="Who has the brass key?",
            max_chars=2400,
            persist_trace=False,
        ),
        db,
    )

    assert approved.id != proposed.id
    assert proposed.approval_status == "pending_approval"
    assert "holder: Lan" in compiled.context_text
    assert "Lan gives the brass key to Minh" not in compiled.context_text

    series_brain.set_current_state_status(
        series.id,
        proposed.id,
        models.SeriesCurrentStateStatusRequest(approval_status="approved"),
        db,
    )
    compiled = series_brain.compile_context(
        series.id,
        models.SeriesContextCompileRequest(
            task_type="story_candidate",
            user_input="What changed after the episode?",
            max_chars=2400,
            persist_trace=False,
        ),
        db,
    )
    assert "Lan gives the brass key to Minh" in compiled.context_text
