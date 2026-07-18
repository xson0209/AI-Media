"""Review-edit tests (§7.7, §7.8, §7.11, 12.9)."""

from __future__ import annotations

import pytest

from backend import config, database
from backend.database import (
    ComicAnalysisJob, ComicApprovalManifest, ComicDetectedCharacter,
    ComicPanel, ComicSpeechBubble, session as database_session,
)
from backend.services.comic_series_analysis import approval_manifest as am
from backend.services.comic_series_analysis import review_edits as re_edit
from backend.services.comic_series_analysis.contracts import ComicAnalysisError


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


def _job(db, revision=1, status="ready_for_review"):
    job = ComicAnalysisJob(source_type="upload", run_status=status, analysis_revision=revision)
    db.add(job)
    db.commit()
    return job


def test_edit_bubble_bumps_revision_and_keeps_raw(db):
    job = _job(db)
    bubble = ComicSpeechBubble(
        job_id=job.id, analysis_revision=1, raw_text="raw ocr", normalized_text="raw ocr",
        edit_source="observed",
    )
    db.add(bubble)
    db.commit()

    new_rev = re_edit.edit_bubble(db, job.id, bubble.id, approved_text="đã sửa", expected_revision=1)
    assert new_rev == 2
    db.refresh(bubble)
    assert bubble.approved_text == "đã sửa"
    assert bubble.raw_text == "raw ocr"  # raw preserved
    assert bubble.edit_source == "user_edited"


def test_edit_with_stale_revision_conflicts(db):
    job = _job(db, revision=3)
    bubble = ComicSpeechBubble(job_id=job.id, analysis_revision=3, raw_text="x")
    db.add(bubble)
    db.commit()
    with pytest.raises(ComicAnalysisError) as exc:
        re_edit.edit_bubble(db, job.id, bubble.id, approved_text="y", expected_revision=1)
    assert exc.value.error_code == "COMIC_REVISION_CONFLICT"


def test_edit_invalidates_active_approval(db):
    job = _job(db, status="approved")
    am.create_manifest(
        db, job_id=job.id, analysis_revision=1,
        accepted_items=[{"item_type": "x", "id": "a", "revision": 1}],
        excluded_items=[], unreviewed_items=[],
        development_mode="lay_cam_hung_va_viet_moi", rights_attestation_revision=0,
    )
    db.commit()
    bubble = ComicSpeechBubble(job_id=job.id, analysis_revision=1, raw_text="x")
    db.add(bubble)
    db.commit()

    re_edit.edit_bubble(db, job.id, bubble.id, approved_text="y")
    db.refresh(job)
    assert job.run_status == "ready_for_review"  # dropped from approved
    assert am.get_active_manifest(db, job.id) is None  # manifest invalidated


def test_reorder_panels(db):
    job = _job(db)
    p1 = ComicPanel(job_id=job.id, analysis_revision=1, reading_order=0)
    p2 = ComicPanel(job_id=job.id, analysis_revision=1, reading_order=1)
    db.add_all([p1, p2])
    db.commit()

    re_edit.reorder_panels(db, job.id, [p2.id, p1.id], expected_revision=1)
    db.refresh(p1)
    db.refresh(p2)
    assert p2.reading_order == 0
    assert p1.reading_order == 1


def test_merge_characters_repoints_evidence(db):
    job = _job(db)
    target = ComicDetectedCharacter(job_id=job.id, analysis_revision=1, display_name="Aki",
                                    aliases_json=[], evidence_ids_json=["e1"])
    src = ComicDetectedCharacter(job_id=job.id, analysis_revision=1, display_name="Akira",
                                 aliases_json=["A."], evidence_ids_json=["e2"])
    db.add_all([target, src])
    db.commit()
    bubble = ComicSpeechBubble(job_id=job.id, analysis_revision=1, raw_text="x",
                               speaker_character_id=src.id)
    db.add(bubble)
    db.commit()

    re_edit.merge_characters(db, job.id, source_ids=[src.id], target_id=target.id, expected_revision=1)
    db.refresh(target)
    db.refresh(bubble)
    # Speaker repointed, aliases + evidence folded, source removed.
    assert bubble.speaker_character_id == target.id
    assert "Akira" in target.aliases_json
    assert set(target.evidence_ids_json) == {"e1", "e2"}
    assert db.query(ComicDetectedCharacter).filter_by(id=src.id).first() is None


def test_split_character(db):
    job = _job(db)
    char = ComicDetectedCharacter(job_id=job.id, analysis_revision=1, display_name="Twins",
                                  evidence_ids_json=["e1", "e2", "e3"])
    db.add(char)
    db.commit()

    rev, new_id = re_edit.split_character(
        db, job.id, char.id, new_name="Twin B", moved_evidence_ids=["e3"], expected_revision=1
    )
    db.refresh(char)
    new_char = db.query(ComicDetectedCharacter).filter_by(id=new_id).first()
    assert char.evidence_ids_json == ["e1", "e2"]
    assert new_char.evidence_ids_json == ["e3"]
    assert new_char.display_name == "Twin B"
