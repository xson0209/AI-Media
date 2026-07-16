"""Analysis orchestrator tests (§6.3-6.9, 12.6, 12.7)."""

from __future__ import annotations

import io

import pytest
from PIL import Image

from backend import config, database
from backend.database import (
    ComicAnalysisJob, ComicDetectedCharacter, ComicDetectedLocation, ComicPanel, ComicPlotAnalysis,
    ComicSpeechBubble,
    session as database_session,
)
from backend.services.comic_series_analysis import analysis, service, vision_adapters
from backend.services.comic_series_analysis.vision_adapters import (
    AttachmentManifest, NullVisionAdapter, VisionResult,
)


@pytest.fixture
def db(tmp_path):
    config.set_data_dir(tmp_path)
    database.init_db()
    session = database_session.SessionLocal()
    try:
        yield session
    finally:
        vision_adapters.set_vision_adapter(NullVisionAdapter())
        session.close()
        database_session.engine.dispose()


def _png():
    buf = io.BytesIO()
    Image.new("RGB", (24, 24), (5, 5, 5)).save(buf, format="PNG")
    return buf.getvalue()


def test_analysis_without_vision_is_honest(db):
    """No vision provider → panels created but no fabricated description,
    visual modality reported unavailable, no invented characters (§6.2, §6.9)."""
    vision_adapters.set_vision_adapter(NullVisionAdapter())
    job = service.create_upload_job(db, images=[("a.png", _png()), ("b.png", _png())])
    result = analysis.analyze_revision(db, job.id)
    db.commit()

    assert result.analysis_revision == 1
    panels = db.query(ComicPanel).filter_by(job_id=job.id).all()
    assert len(panels) == 2
    assert all(p.visual_description is None for p in panels)  # never fabricate
    assert all(p.needs_review for p in panels)
    # No characters invented without vision.
    assert db.query(ComicDetectedCharacter).filter_by(job_id=job.id).count() == 0
    # Visual modality flagged.
    assert result.coverage_metrics_json["visual_modality"] == "unavailable"
    assert any(l["code"] == "COMIC_VISION_UNAVAILABLE" for l in result.limitations_json)
    assert result.result_completeness == "partial"


def test_analysis_with_vision_persists_panels(db):
    """A vision-capable adapter attaches real bytes → panels get evidence."""

    class FakeVisionAdapter:
        def supports_vision(self):
            return True

        def analyze_batch(self, manifest: AttachmentManifest, instruction: str) -> VisionResult:
            return VisionResult(batch_id=manifest.batch_id, completed=True, payload={"panels": []})

    vision_adapters.set_vision_adapter(FakeVisionAdapter())
    job = service.create_upload_job(db, images=[("a.png", _png())])
    result = analysis.analyze_revision(db, job.id)
    db.commit()

    panels = db.query(ComicPanel).filter_by(job_id=job.id).all()
    assert len(panels) == 1
    assert result.coverage_metrics_json["visual_modality"] == "completed"


def test_codex_vision_adapter_snapshots_settings_without_orm_tracking(db, monkeypatch):
    """The vision adapter must not mutate a shallow-copied SQLAlchemy model."""
    import gc

    from backend.services import ai_planning, settings as settings_service

    row = settings_service.get_ai_planning_settings(db)
    row.provider = "codex-cli"
    row.codex_path = "codex"
    row.model = "gpt-5"
    row.model_reasoning_effort = "ultra"
    row.timeout_seconds = 60
    db.commit()
    del row
    gc.collect()

    monkeypatch.setattr(ai_planning, "resolve_codex_path", lambda _settings: "codex")

    adapter = vision_adapters.CodexVisionAdapter(db)

    assert adapter.supports_vision() is True
    assert adapter._settings.model_reasoning_effort == "high"
    stored = settings_service.get_ai_planning_settings(db)
    assert stored.model_reasoning_effort == "ultra"

def test_analysis_with_vision_persists_structured_story_package(db):
    """Vision output must become reviewable image/text/character/location data,
    not an empty structural panel with a misleading completed status."""

    class FakeVisionAdapter:
        def supports_vision(self):
            return True

        def analyze_batch(self, manifest: AttachmentManifest, instruction: str) -> VisionResult:
            asset_id = manifest.attachments[0].asset_id
            return VisionResult(
                batch_id=manifest.batch_id,
                completed=True,
                payload={
                    "panels": [
                        {
                            "asset_id": asset_id,
                            "reading_order": 0,
                            "visual_description": "Một nữ chính cầm ô đứng trước quán cà phê lúc mưa.",
                            "confidence": 0.94,
                            "evidence_ids": [asset_id],
                        }
                    ],
                    "dialogues": [
                        {
                            "reading_order": 0,
                            "bubble_type": "dialogue",
                            "text": "Cuối cùng mình cũng tìm thấy anh.",
                            "speaker": "Ari",
                            "confidence": 0.9,
                            "evidence_ids": [asset_id],
                        }
                    ],
                    "characters": [
                        {
                            "name": "Ari",
                            "role": "Nữ chính",
                            "face_description": "Gương mặt trái xoan",
                            "outfit_description": "Áo khoác vàng và ô đen",
                            "confidence": 0.91,
                            "evidence_ids": [asset_id],
                        }
                    ],
                    "locations": [
                        {
                            "name": "Quán cà phê đầu phố",
                            "description": "Quán nhỏ với biển đèn vàng trong cơn mưa.",
                            "confidence": 0.88,
                            "evidence_ids": [asset_id],
                        }
                    ],
                    "plot": {
                        "synopsis": "Ari tìm thấy người cô đã chờ đợi tại quán cà phê.",
                        "plot_beats": ["Ari đến quán", "Cuộc hội ngộ bắt đầu"],
                        "relationships": [{"from": "Ari", "to": "người được chờ", "type": "bí ẩn"}],
                        "evidence_ids": [asset_id],
                    },
                },
            )

    vision_adapters.set_vision_adapter(FakeVisionAdapter())
    job = service.create_upload_job(db, images=[("chapter.png", _png())])
    result = analysis.analyze_revision(db, job.id)
    db.commit()

    panel = db.query(ComicPanel).filter_by(job_id=job.id, analysis_revision=1).one()
    bubble = db.query(ComicSpeechBubble).filter_by(job_id=job.id, analysis_revision=1).one()
    character = db.query(ComicDetectedCharacter).filter_by(job_id=job.id, analysis_revision=1).one()
    location = db.query(ComicDetectedLocation).filter_by(job_id=job.id, analysis_revision=1).one()
    plot = db.query(ComicPlotAnalysis).filter_by(job_id=job.id, analysis_revision=1).one()

    assert "quán cà phê" in panel.visual_description
    assert bubble.normalized_text == "Cuối cùng mình cũng tìm thấy anh."
    assert character.display_name == "Ari"
    assert location.name == "Quán cà phê đầu phố"
    assert plot.synopsis.startswith("Ari tìm thấy")
    assert result.analysis_package_json["characters"][0]["name"] == "Ari"
    assert result.analysis_package_json["locations"][0]["name"] == "Quán cà phê đầu phố"

def test_analysis_publishes_completed_batches_while_later_batches_are_running(db):
    """A completed provider batch must be durable and visible before the whole
    vision pass finishes, otherwise the UI appears empty while Codex already
    returned useful data."""

    observed: dict[str, object] = {}

    class FakeVisionAdapter:
        def __init__(self):
            self.calls = 0

        def supports_vision(self):
            return True

        def analyze_batch(self, manifest: AttachmentManifest, instruction: str) -> VisionResult:
            self.calls += 1
            if self.calls == 1:
                asset_id = manifest.attachments[0].asset_id
                return VisionResult(
                    batch_id=manifest.batch_id,
                    completed=True,
                    payload={
                        "panels": [
                            {
                                "asset_id": asset_id,
                                "reading_order": 0,
                                "visual_description": "Trang đầu đã được Codex đọc và mô tả.",
                                "confidence": 0.9,
                                "evidence_ids": [asset_id],
                            }
                        ],
                        "dialogues": [
                            {
                                "reading_order": 0,
                                "bubble_type": "dialogue",
                                "text": "Đã nhận dữ liệu batch đầu.",
                                "speaker": "Ari",
                                "confidence": 0.84,
                                "evidence_ids": [asset_id],
                            }
                        ],
                        "characters": [
                            {
                                "name": "Ari",
                                "role": "Nhân vật xuất hiện trong batch đầu",
                                "confidence": 0.86,
                                "evidence_ids": [asset_id],
                            }
                        ],
                        "locations": [
                            {
                                "name": "Sảnh chính",
                                "description": "Không gian được nhận diện từ batch đầu.",
                                "confidence": 0.81,
                                "evidence_ids": [asset_id],
                            }
                        ],
                        "plot": {
                            "synopsis": "Batch đầu đã có nội dung phân tích.",
                            "plot_beats": ["Batch đầu hoàn tất"],
                            "relationships": [],
                            "evidence_ids": [asset_id],
                        },
                    },
                )

            observer = database_session.SessionLocal()
            try:
                observed["panel_count"] = observer.query(ComicPanel).filter_by(
                    job_id=job.id,
                    analysis_revision=1,
                ).count()
                row = observer.query(ComicAnalysisJob).filter_by(id=job.id).one()
                observed["package"] = row.analysis_package_json
            finally:
                observer.close()
            return VisionResult(
                batch_id=manifest.batch_id,
                completed=False,
                status="partial",
                error_code="CODEX_EXEC_TIMEOUT",
            )

    vision_adapters.set_vision_adapter(FakeVisionAdapter())
    job = service.create_upload_job(
        db,
        images=[
            ("a.png", _png()),
            ("b.png", _png()),
            ("c.png", _png()),
            ("d.png", _png()),
            ("e.png", _png()),
        ],
    )

    result = analysis.analyze_revision(db, job.id)
    db.commit()

    assert observed["panel_count"] == 1
    package = observed["package"]
    assert isinstance(package, dict)
    assert package["analysis_revision"] == 1
    assert package["panels"][0]["visual_description"] == "Trang đầu đã được Codex đọc và mô tả."
    assert package["characters"][0]["name"] == "Ari"
    assert package["locations"][0]["name"] == "Sảnh chính"
    assert result.result_completeness == "partial"

def test_analysis_splits_timed_out_vision_batches_and_keeps_visual_descriptions(db):
    """A 4-image timeout should retry smaller batches instead of converting
    the entire group into blank placeholder panels."""

    call_sizes: list[int] = []

    class FakeVisionAdapter:
        def supports_vision(self):
            return True

        def analyze_batch(self, manifest: AttachmentManifest, instruction: str) -> VisionResult:
            call_sizes.append(len(manifest.attachments))
            if len(manifest.attachments) > 1:
                return VisionResult(
                    batch_id=manifest.batch_id,
                    completed=False,
                    status="partial",
                    error_code="CODEX_EXEC_TIMEOUT",
                )
            attachment = manifest.attachments[0]
            return VisionResult(
                batch_id=manifest.batch_id,
                completed=True,
                payload={
                    "panels": [
                        {
                            "asset_id": attachment.asset_id,
                            "reading_order": attachment.page_order,
                            "visual_description": f"Mô tả trực tiếp cho trang {attachment.page_order}.",
                            "confidence": 0.88,
                            "evidence_ids": [attachment.asset_id],
                        }
                    ],
                    "dialogues": [],
                    "characters": [],
                    "locations": [],
                    "plot": {
                        "synopsis": "Các trang đã được retry theo batch nhỏ.",
                        "plot_beats": [f"Trang {attachment.page_order} đã được phân tích"],
                        "relationships": [],
                        "evidence_ids": [attachment.asset_id],
                    },
                },
            )

    vision_adapters.set_vision_adapter(FakeVisionAdapter())
    job = service.create_upload_job(
        db,
        images=[("a.png", _png()), ("b.png", _png()), ("c.png", _png()), ("d.png", _png())],
    )
    result = analysis.analyze_revision(db, job.id)
    db.commit()

    panels = (
        db.query(ComicPanel)
        .filter_by(job_id=job.id, analysis_revision=1)
        .order_by(ComicPanel.reading_order)
        .all()
    )

    assert call_sizes[0] == 4
    assert call_sizes.count(1) == 4
    assert len(panels) == 4
    assert all(panel.visual_description for panel in panels)
    assert result.coverage_metrics_json["visual_modality"] == "completed"


def test_text_analysis_creates_narration_with_evidence(db):
    """HTML-style text pages become narration bubbles carrying evidence ids."""
    from backend.database import ComicSourcePage, ComicSourceDocument
    vision_adapters.set_vision_adapter(NullVisionAdapter())
    job = service.create_upload_job(db, images=[("a.png", _png())])
    # Add a text page to the existing document.
    doc_id = job.current_source_document_id
    db.add(ComicSourcePage(
        document_id=doc_id, job_id=job.id, page_order=5, page_kind="text",
        extracted_text="Ngày xửa ngày xưa có một con rồng.", evidence_id="text-5",
        provenance="web",
    ))
    db.commit()

    analysis.analyze_revision(db, job.id)
    db.commit()
    bubbles = db.query(ComicSpeechBubble).filter_by(job_id=job.id).all()
    assert any(b.raw_text and "con rồng" in b.raw_text for b in bubbles)
    assert all(b.evidence_ids_json for b in bubbles)


def test_analysis_revision_increments(db):
    vision_adapters.set_vision_adapter(NullVisionAdapter())
    job = service.create_upload_job(db, images=[("a.png", _png())])
    analysis.analyze_revision(db, job.id)
    db.commit()
    analysis.analyze_revision(db, job.id)
    db.commit()
    db.refresh(job)
    assert job.analysis_revision == 2
    # Plot rows exist per revision.
    assert db.query(ComicPlotAnalysis).filter_by(job_id=job.id).count() == 2
