"""Story Studio source-context compiler + stale tests (§9, tasks 12.11, 12.11a)."""

from __future__ import annotations

import pytest

from backend import config, database
from backend.database import (
    StoryEpisode,
    StoryEpisodeSourceChunk,
    StoryEpisodeSourceDocument,
    StoryScenarioCandidate,
    VideoSeries,
    session as database_session,
)
from backend.services.comic_series_analysis import source_context as sc
from backend.services.comic_series_analysis.contracts import STALE_STATUS


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


def _episode_with_source(db, *, chunks):
    series = VideoSeries(title="S", series_mode="image_story_only")
    db.add(series)
    db.flush()
    ep = StoryEpisode(series_id=series.id, episode_number=1)
    db.add(ep)
    db.flush()
    doc = StoryEpisodeSourceDocument(
        story_episode_id=ep.id, revision=1, approval_status="approved",
        synopsis="Tóm tắt chương", source_kind="comic_analysis",
    )
    db.add(doc)
    db.flush()
    for order, (text, state) in enumerate(chunks):
        db.add(StoryEpisodeSourceChunk(
            document_id=doc.id, story_episode_id=ep.id, chunk_order=order,
            chunk_type="text", approved_text=text, approval_state=state,
            source_revision=1,
        ))
    ep.current_source_document_id = doc.id
    db.commit()
    return ep, doc


def test_source_summary(db):
    ep, doc = _episode_with_source(db, chunks=[("a", "accepted"), ("b", "accepted")])
    summary = sc.source_summary(db, ep.id)
    assert summary.has_structured_source
    assert summary.chunk_count == 2
    assert summary.revision == 1


def test_compile_context_excludes_unreviewed(db):
    ep, doc = _episode_with_source(
        db, chunks=[("accepted text", "accepted"), ("unreviewed text", "unreviewed")]
    )
    ctx = sc.compile_context(db, ep.id)
    texts = [c["text"] for c in ctx.chunks]
    assert "accepted text" in texts
    assert "unreviewed text" not in texts  # §9.11
    assert ctx.synopsis == "Tóm tắt chương"
    assert ctx.fingerprint


def test_compile_source_package_uses_only_accepted_chunks(db):
    ep, doc = _episode_with_source(
        db, chunks=[("accepted text", "accepted"), ("unreviewed text", "unreviewed")]
    )

    summary = sc.compile_source_package(db, ep.id)
    package = summary.source_package
    package_text = str(package.to_dict())

    assert package.schema_version == "source_package.v1"
    assert package.source_kind == "story_episode_source"
    assert package.source_ref_id == doc.id
    assert package.source_revision == 1
    assert "accepted text" in package_text
    assert "unreviewed text" not in package_text
    assert package.fingerprint
    assert summary.selected_chunk_count == 1

def test_compile_source_package_fingerprint_changes_with_source_content(db):
    ep, doc = _episode_with_source(db, chunks=[("first text", "accepted")])
    fp1 = sc.compile_source_package(db, ep.id).source_package.fingerprint

    chunk = db.query(StoryEpisodeSourceChunk).filter(StoryEpisodeSourceChunk.document_id == doc.id).one()
    chunk.approved_text = "changed text"
    db.commit()

    fp2 = sc.compile_source_package(db, ep.id).source_package.fingerprint
    assert fp1 != fp2

def test_compile_context_budget_and_omission(db):
    ep, doc = _episode_with_source(
        db, chunks=[("x" * 100, "accepted"), ("y" * 100, "accepted"), ("z" * 100, "accepted")]
    )
    ctx = sc.compile_context(db, ep.id, char_budget=150)
    # Only the first chunk fits; the rest are reported omitted, not dropped silently.
    assert len(ctx.chunks) == 1
    assert ctx.omitted_chunk_count == 2


def test_context_fingerprint_changes_with_revision(db):
    ep, doc = _episode_with_source(db, chunks=[("a", "accepted")])
    fp1 = sc.compile_context(db, ep.id).fingerprint
    doc.revision = 2
    db.commit()
    fp2 = sc.compile_context(db, ep.id).fingerprint
    assert fp1 != fp2  # §9.12


def test_swap_current_source_atomic(db):
    ep, doc = _episode_with_source(db, chunks=[("a", "accepted")])
    new_doc = StoryEpisodeSourceDocument(
        story_episode_id=ep.id, revision=2, approval_status="approved",
        source_kind="comic_analysis",
    )
    db.add(new_doc)
    db.commit()
    sc.swap_current_source(db, ep.id, new_doc.id)
    db.commit()
    db.refresh(ep)
    db.refresh(doc)
    assert ep.current_source_document_id == new_doc.id
    assert doc.approval_status == "superseded"


def test_swap_rejects_unapproved(db):
    ep, doc = _episode_with_source(db, chunks=[("a", "accepted")])
    draft = StoryEpisodeSourceDocument(
        story_episode_id=ep.id, revision=2, approval_status="draft", source_kind="comic_analysis",
    )
    db.add(draft)
    db.commit()
    with pytest.raises(ValueError):
        sc.swap_current_source(db, ep.id, draft.id)


def test_mark_dependent_candidates_stale(db):
    ep, doc = _episode_with_source(db, chunks=[("a", "accepted")])
    dep = StoryScenarioCandidate(
        story_episode_id=ep.id, strategy_type="faithful", script_json={},
        generation_status="completed", evaluation_status="passed", selected=True,
        source_document_revision=1,
    )
    indep = StoryScenarioCandidate(
        story_episode_id=ep.id, strategy_type="bold", script_json={},
        generation_status="completed", evaluation_status="passed",
        source_document_revision=2,
    )
    db.add_all([dep, indep])
    db.commit()

    count = sc.mark_dependent_candidates_stale(db, ep.id, old_source_revision=1)
    db.commit()
    assert count == 1
    db.refresh(dep)
    db.refresh(indep)
    assert dep.generation_status == STALE_STATUS
    assert dep.evaluation_status == STALE_STATUS
    assert dep.selected is False
    # The candidate on a different revision is untouched (§9.13 precision).
    assert indep.generation_status == "completed"
