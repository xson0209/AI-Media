"""Tests for §6: vision attachment, output validation, originality, approval manifest."""

from __future__ import annotations

import pathlib
import tempfile

import pytest

from backend import config, database
from backend.database import session as database_session
from backend.services.comic_series_analysis import (
    analysis_validation as av,
    approval_manifest as am,
    vision_adapters as va,
)
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


# --- Vision adapter (tasks 6.1, 6.2, 6.12) --------------------------------

def test_null_vision_adapter_never_fabricates():
    adapter = va.NullVisionAdapter()
    assert adapter.supports_vision() is False
    manifest = va.AttachmentManifest(
        batch_id="b0",
        attachments=[va.Attachment(0, "asset1", "/nonexistent.png")],
    )
    result = adapter.analyze_batch(manifest, "describe")
    assert result.completed is False
    assert result.status == "vision_unavailable"
    assert result.payload is None  # no fabricated description


def test_validate_attachments_requires_real_files(tmp_path):
    # A real file passes.
    real = tmp_path / "a.png"
    real.write_bytes(b"\x89PNG\r\n\x1a\n" + b"\x00" * 16)
    manifest = va.AttachmentManifest(
        batch_id="b0", attachments=[va.Attachment(0, "asset1", str(real))]
    )
    va.validate_attachments(manifest)  # no raise

    # A missing file fails — this is what proves "path in prompt text" != vision.
    manifest_bad = va.AttachmentManifest(
        batch_id="b1", attachments=[va.Attachment(0, "asset2", str(tmp_path / "missing.png"))]
    )
    with pytest.raises(ComicAnalysisError) as exc:
        va.validate_attachments(manifest_bad)
    assert exc.value.error_code == "COMIC_VISION_ATTACH_FAILED"


def test_batch_attachments_respects_limit():
    from backend.services.comic_series_analysis.config import VisionPolicy
    attachments = [va.Attachment(i, f"a{i}", f"/p{i}.png") for i in range(20)]
    batches = va.batch_attachments(attachments, policy=VisionPolicy(max_attachments_per_request=8))
    assert len(batches) == 3
    assert sum(len(b.attachments) for b in batches) == 20
    # Order preserved across batches.
    flat = [a.asset_id for b in batches for a in b.attachments]
    assert flat == [f"a{i}" for i in range(20)]


# --- Structured output validation (tasks 6.13, 12.7a) ---------------------

def test_valid_output_passes():
    payload = {"name": "Aki", "confidence": 0.8, "evidence_ids": ["ev1", "ev2"]}
    result = av.validate_analysis_output(
        payload, known_evidence_ids={"ev1", "ev2"}, required_fields=("name",)
    )
    assert result.ok


def test_missing_required_field_rejected():
    result = av.validate_analysis_output({}, known_evidence_ids=set(), required_fields=("name",))
    assert not result.ok
    assert any("name" in e for e in result.errors)


def test_unknown_evidence_id_rejected():
    payload = {"evidence_ids": ["ghost"]}
    result = av.validate_analysis_output(payload, known_evidence_ids={"ev1"})
    assert not result.ok
    assert any("ghost" in e for e in result.errors)


def test_confidence_out_of_range_rejected():
    payload = {"confidence": 1.5}
    result = av.validate_analysis_output(payload, known_evidence_ids=set())
    assert not result.ok


def test_normalize_output_confidences():
    payload = {"confidence": 2.0, "child": {"confidence": -0.5}, "note": "x"}
    normalized = av.normalize_output_confidences(payload)
    assert normalized["confidence"] == 1.0
    assert normalized["child"]["confidence"] == 0.0
    assert normalized["note"] == "x"


# --- Originality (tasks 6.11, 6.16) ---------------------------------------

def test_originality_flags_verbatim_copy():
    source = ["Con mèo nhỏ ngồi trên mái nhà và ngắm nhìn thành phố về đêm rất lâu"]
    verbatim = "Con mèo nhỏ ngồi trên mái nhà và ngắm nhìn thành phố về đêm rất lâu"
    report = av.build_originality_report(verbatim, source, verbatim_threshold=8)
    assert report.exceeded_threshold
    assert report.longest_verbatim_span >= 8
    assert report.algorithm_version


def test_originality_passes_original_text():
    source = ["Con mèo nhỏ ngồi trên mái nhà"]
    original = "Một câu chuyện hoàn toàn mới về những vì sao xa xôi"
    report = av.build_originality_report(original, source, verbatim_threshold=8)
    assert not report.exceeded_threshold


# --- Approval manifest (tasks 6.15, 12.9a) --------------------------------

def test_create_manifest_and_hash_stable(db):
    accepted = [{"item_type": "character", "id": "c1", "revision": 1, "state": "accepted"}]
    excluded = [{"item_type": "character", "id": "c2", "revision": 1, "state": "excluded"}]
    m1 = am.create_manifest(
        db, job_id="job1", analysis_revision=1,
        accepted_items=accepted, excluded_items=excluded, unreviewed_items=[],
        development_mode="lay_cam_hung_va_viet_moi", rights_attestation_revision=0,
    )
    db.commit()
    assert m1.manifest_hash
    assert am.accepted_item_ids(m1) == {"c1"}
    # Accepted item passes the gate; excluded/unknown fails.
    am.assert_item_accepted(m1, "c1")
    with pytest.raises(ComicAnalysisError):
        am.assert_item_accepted(m1, "c2")


def test_new_manifest_invalidates_prior(db):
    am.create_manifest(
        db, job_id="job1", analysis_revision=1,
        accepted_items=[{"item_type": "x", "id": "a", "revision": 1}],
        excluded_items=[], unreviewed_items=[],
        development_mode="lay_cam_hung_va_viet_moi", rights_attestation_revision=0,
    )
    db.commit()
    am.create_manifest(
        db, job_id="job1", analysis_revision=2,
        accepted_items=[{"item_type": "x", "id": "a", "revision": 2}],
        excluded_items=[], unreviewed_items=[],
        development_mode="lay_cam_hung_va_viet_moi", rights_attestation_revision=0,
    )
    db.commit()
    active = am.get_active_manifest(db, "job1")
    assert active.analysis_revision == 2
    # Only one active manifest remains.
    from backend.database import ComicApprovalManifest as DBM
    actives = db.query(DBM).filter(DBM.job_id == "job1", DBM.active == True).all()  # noqa: E712
    assert len(actives) == 1
