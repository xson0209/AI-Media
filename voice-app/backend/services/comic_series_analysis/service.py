"""Job lifecycle and ingestion orchestration for Comic Series Analysis (§7).

This is the neutral-infrastructure integration layer: it owns job CRUD,
create-from-URL / create-from-upload, the ingestion pipeline (fetch →
extract → download assets → normalize → build source document), and the
source-revision finalize/re-import logic. Background scheduling, cancel and
retry live in ``runner.py``; this module is import-safe and does the DB work.
"""

from __future__ import annotations

import hashlib
import logging
import uuid
from datetime import datetime

from sqlalchemy.orm import Session

from ... import config as core_config
from ...database import (
    ComicAnalysisJob as DBJob,
    ComicSourceAsset as DBAsset,
    ComicSourceDocument as DBDoc,
    ComicSourcePage as DBPage,
)
from . import config as comic_config
from . import fetcher, html_extractor, image_pipeline, url_security
from .contracts import (
    DEFAULT_DEVELOPMENT_MODE,
    DEVELOPMENT_MODES,
    READING_MODES,
    SOURCE_PACKAGE_SCHEMA_VERSION,
    ComicAnalysisError,
    Outcome,
)

logger = logging.getLogger(__name__)


def _require_enabled() -> None:
    if not comic_config.is_feature_enabled():
        raise ComicAnalysisError("COMIC_ANALYSIS_DISABLED", status_code=403)


# --------------------------------------------------------------------------
# Job creation
# --------------------------------------------------------------------------

def create_url_job(
    db: Session,
    *,
    url: str,
    reading_mode: str = "auto",
    development_mode: str = DEFAULT_DEVELOPMENT_MODE,
    rights_attested: bool = False,
    title: str | None = None,
) -> DBJob:
    """Create a draft job from a public URL (validates URL structurally first)."""
    _require_enabled()
    if reading_mode not in READING_MODES:
        raise ComicAnalysisError("COMIC_ANALYSIS_INVALID_STATE", f"reading_mode không hợp lệ: {reading_mode}")
    if development_mode not in DEVELOPMENT_MODES:
        raise ComicAnalysisError("COMIC_ANALYSIS_INVALID_STATE", f"development_mode không hợp lệ")
    if development_mode == "bam_canon_va_phat_trien_tiep" and not rights_attested:
        raise ComicAnalysisError("COMIC_RIGHTS_REQUIRED")

    # Structural validation (no network yet) — rejects bad schemes/hosts early.
    url_security.validate_url(url)

    job = DBJob(
        source_type="url",
        source_url=url_security.redact_url(url),
        title=title,
        reading_mode=reading_mode,
        development_mode=development_mode,
        rights_attested_at=datetime.utcnow() if rights_attested else None,
        rights_attestation_revision=1 if rights_attested else 0,
        run_status="draft",
        result_completeness="unavailable",
        current_step="validate_source",
        source_package_schema_version=SOURCE_PACKAGE_SCHEMA_VERSION,
    )
    # store the raw (unredacted) URL out-of-band on the object for the run;
    # the DB only keeps the redacted form.
    job._raw_url = url  # type: ignore[attr-defined]
    db.add(job)
    db.commit()
    db.refresh(job)
    return job


def create_upload_job(
    db: Session,
    *,
    images: list[tuple[str, bytes]],
    reading_mode: str = "auto",
    development_mode: str = DEFAULT_DEVELOPMENT_MODE,
    rights_attested: bool = False,
    title: str | None = None,
) -> DBJob:
    """Create a job from uploaded images, preserving user order (task 7.4)."""
    _require_enabled()
    if not images:
        raise ComicAnalysisError("COMIC_ANALYSIS_INVALID_STATE", "Không có ảnh nào được upload.")
    cfg = comic_config.get_config()
    if len(images) > cfg.ingest.max_upload_images:
        raise ComicAnalysisError("COMIC_ANALYSIS_INVALID_STATE", "Vượt số ảnh cho phép.")

    job = DBJob(
        source_type="upload",
        title=title,
        reading_mode=reading_mode,
        development_mode=development_mode,
        rights_attested_at=datetime.utcnow() if rights_attested else None,
        rights_attestation_revision=1 if rights_attested else 0,
        run_status="draft",
        result_completeness="unavailable",
        current_step="download_assets",
        source_package_schema_version=SOURCE_PACKAGE_SCHEMA_VERSION,
    )
    db.add(job)
    db.flush()

    document = _new_document(db, job, retrieval_mode="upload")
    _ingest_upload_images(db, job, document, images)
    _finalize_document(db, job, document)

    job.current_source_document_id = document.id
    job.run_status = "source_ready"
    job.result_completeness = "complete"
    job.current_step = "panel_analysis"
    job.progress = 0.5
    db.commit()
    db.refresh(job)
    return job


# --------------------------------------------------------------------------
# Ingestion pipeline
# --------------------------------------------------------------------------

def _new_document(db: Session, job: DBJob, *, retrieval_mode: str, revision: int = 1) -> DBDoc:
    doc = DBDoc(
        job_id=job.id,
        revision=revision,
        lifecycle="collecting",
        retrieval_mode=retrieval_mode,
        requested_url=job.source_url,
        extractor_version=html_extractor.EXTRACTOR_VERSION,
    )
    db.add(doc)
    db.flush()
    return doc


def _store_asset(
    db: Session,
    job: DBJob,
    document: DBDoc,
    data: bytes,
    *,
    order: int,
    provenance: str,
    source_url: str | None = None,
) -> DBAsset | None:
    """Validate + persist one original image and its derivatives.

    Returns None (and records nothing orphaned) if the image is invalid, so
    a bad file never leaves a dangling asset (task 7.4).
    """
    validation = image_pipeline.validate_image(data)
    originals_dir = comic_config.get_storage_subdir("originals")
    checksum = validation.checksum

    asset = DBAsset(
        document_id=document.id,
        job_id=job.id,
        asset_order=order,
        source_url=source_url,
        detected_format=validation.detected_format,
        byte_size=validation.byte_size,
        width=validation.width,
        height=validation.height,
        frame_count=validation.frame_count,
        checksum=checksum,
        decoded_pixel_hash=validation.decoded_pixel_hash,
        codec_status=validation.codec_status,
        provenance=provenance,
        transform_version=image_pipeline.TRANSFORM_VERSION,
    )

    if validation.error_code in ("COMIC_UNSUPPORTED_IMAGE_FORMAT", "COMIC_IMAGE_CORRUPT"):
        # Do not create an artifact for a non-image / corrupt file.
        asset.limitations_json = [{"code": validation.error_code}]
        # Still record the failure with no stored bytes (evidence of coverage).
        asset.codec_status = validation.codec_status
        db.add(asset)
        db.flush()
        return asset

    # Preserve original bytes byte-for-byte (dedup by checksum).
    original_path = image_pipeline.save_original(data, originals_dir, checksum, validation.detected_format)
    asset.original_path = core_config.to_storage_path(original_path)

    if validation.error_code == "COMIC_CODEC_UNAVAILABLE":
        asset.codec_status = "codec_unavailable"
        asset.limitations_json = [{"code": "COMIC_CODEC_UNAVAILABLE"}]
        db.add(asset)
        db.flush()
        return asset

    if validation.error_code == "COMIC_DECOMPRESSION_BOMB":
        asset.codec_status = "ok"
        asset.limitations_json = [{"code": "COMIC_DECOMPRESSION_BOMB"}]
        db.add(asset)
        db.flush()
        return asset

    # Build derivatives (analysis PNG, preview WebP, tiles).
    try:
        derivatives = image_pipeline.make_derivatives(
            data, checksum,
            analysis_dir=comic_config.get_storage_subdir("analysis"),
            preview_dir=comic_config.get_storage_subdir("previews"),
            tiles_dir=comic_config.get_storage_subdir("tiles"),
        )
        asset.derivatives_json = {
            "analysis_path": core_config.to_storage_path(derivatives.analysis_path)
            if derivatives.analysis_path else None,
            "preview_path": core_config.to_storage_path(derivatives.preview_path)
            if derivatives.preview_path else None,
            "tiles": [
                {"index": t.index, "path": core_config.to_storage_path(t.path),
                 "x": t.x, "y": t.y, "width": t.width, "height": t.height}
                for t in derivatives.tiles
            ],
            "transform_version": derivatives.transform_version,
        }
    except ComicAnalysisError as exc:
        asset.limitations_json = [{"code": exc.error_code}]

    db.add(asset)
    db.flush()
    return asset


def _ingest_upload_images(db: Session, job: DBJob, document: DBDoc, images: list[tuple[str, bytes]]) -> None:
    order = 0
    for _filename, data in images:
        asset = _store_asset(db, job, document, data, order=order, provenance="upload")
        page = DBPage(
            document_id=document.id, job_id=job.id, page_order=order,
            page_kind="image", asset_id=asset.id if asset else None,
            evidence_id=f"page-{order}", provenance="upload",
        )
        db.add(page)
        order += 1
    db.flush()


def _compute_content_hash(document: DBDoc, db: Session) -> str:
    """Hash over ordered text chunks + ordered asset checksums (task 4.12)."""
    pages = (
        db.query(DBPage)
        .filter(DBPage.document_id == document.id)
        .order_by(DBPage.page_order)
        .all()
    )
    assets = (
        db.query(DBAsset)
        .filter(DBAsset.document_id == document.id)
        .order_by(DBAsset.asset_order)
        .all()
    )
    hasher = hashlib.sha256()
    for page in pages:
        hasher.update((page.extracted_text or "").encode("utf-8"))
        hasher.update(b"\x00")
    for asset in assets:
        hasher.update((asset.checksum or "").encode("utf-8"))
        hasher.update(b"\x00")
    return hasher.hexdigest()


def _finalize_document(db: Session, job: DBJob, document: DBDoc) -> None:
    """Freeze a source revision after collection (task 4.12, spec finalize)."""
    document.content_hash = _compute_content_hash(document, db)
    assets = (
        db.query(DBAsset)
        .filter(DBAsset.document_id == document.id)
        .order_by(DBAsset.asset_order)
        .all()
    )
    document.asset_manifest_json = [
        {"order": a.asset_order, "checksum": a.checksum, "codec_status": a.codec_status}
        for a in assets
    ]
    codec_ok = sum(1 for a in assets if a.codec_status == "ok")
    total = len(assets)
    document.coverage_metrics_json = {
        "asset_count": total,
        "asset_codec_ok": codec_ok,
        "image_coverage": (codec_ok / total) if total else 0.0,
    }
    limitations = []
    if total and codec_ok < total:
        limitations.append({"code": "COMIC_CODEC_UNAVAILABLE", "count": total - codec_ok})
    document.limitations_json = limitations
    document.lifecycle = "finalized"
    document.finalized_at = datetime.utcnow()
    db.flush()


def run_url_ingestion(db: Session, job: DBJob, raw_url: str) -> Outcome:
    """Fetch + extract a URL source into a finalized document (static-first)."""
    _require_enabled()
    job.run_status = "running"
    job.current_step = "fetch_html"
    db.commit()

    result = fetcher.fetch(raw_url, kind="any")
    if result.outcome_code:
        job.run_status = "failed"
        job.outcome_code = result.outcome_code
        job.result_completeness = "unavailable"
        job.error_code = {
            "authentication_required": "COMIC_AUTHENTICATION_REQUIRED",
            "access_denied": "COMIC_ACCESS_DENIED",
            "captcha_required": "COMIC_CAPTCHA_REQUIRED",
        }.get(result.outcome_code, "COMIC_NEEDS_UPLOAD")
        db.commit()
        return Outcome(result_completeness="unavailable", outcome_code=result.outcome_code)

    document = _new_document(db, job, retrieval_mode="static")
    document.final_url = result.final_url
    document.http_status = result.status_code

    if result.content_kind == "image":
        # Direct-image URL: a single-page source (task 4.10).
        document.retrieval_mode = "static"
        asset = _store_asset(db, job, document, result.content, order=0, provenance="web", source_url=result.final_url)
        db.add(DBPage(document_id=document.id, job_id=job.id, page_order=0,
                      page_kind="image", asset_id=asset.id if asset else None,
                      evidence_id="page-0", provenance="web"))
    elif result.content_kind == "html":
        job.current_step = "extract_content"
        db.commit()
        content = html_extractor.extract(result.content.decode("utf-8", "replace"), result.final_url)
        if content.title and not job.title:
            job.title = content.title
        document.title = content.title
        document.author = content.author
        # Text chunks → pages.
        for order, chunk in enumerate(content.text_chunks):
            db.add(DBPage(document_id=document.id, job_id=job.id, page_order=order,
                          page_kind="text", extracted_text=chunk,
                          evidence_id=f"text-{order}", provenance="web"))
        # Images → assets (best-effort download).
        job.current_step = "download_assets"
        db.commit()
        _download_html_images(db, job, document, content.images)
    else:
        job.run_status = "failed"
        job.error_code = "COMIC_UNSUPPORTED_CONTENT"
        job.result_completeness = "unavailable"
        db.commit()
        return Outcome(result_completeness="unavailable", outcome_code="unsupported_content")

    _finalize_document(db, job, document)
    job.current_source_document_id = document.id
    coverage = (document.coverage_metrics_json or {}).get("image_coverage", 1.0)
    completeness = "complete" if coverage >= 0.99 else "partial"
    job.run_status = "source_ready"
    job.result_completeness = completeness
    job.current_step = "panel_analysis"
    job.progress = 0.5
    db.commit()
    return Outcome(result_completeness=completeness)


def _download_html_images(db: Session, job: DBJob, document: DBDoc, images) -> None:
    cfg = comic_config.get_config()
    order_base = (
        db.query(DBPage).filter(DBPage.document_id == document.id).count()
    )
    stored = 0
    for i, img in enumerate(images):
        if stored >= cfg.ingest.max_images:
            break
        if img.data_uri:
            data = _decode_data_uri(img.url, cfg.network.max_data_uri_bytes)
            if data is None:
                continue
        else:
            try:
                res = fetcher.fetch(img.url, kind="image")
            except ComicAnalysisError:
                continue
            if res.content_kind != "image":
                continue
            data = res.content
        asset = _store_asset(db, job, document, data, order=i, provenance="web", source_url=img.url)
        db.add(DBPage(document_id=document.id, job_id=job.id, page_order=order_base + i,
                      page_kind="image", asset_id=asset.id if asset else None,
                      evidence_id=f"img-{i}", provenance="web"))
        stored += 1
    db.flush()


def _decode_data_uri(uri: str, max_bytes: int) -> bytes | None:
    import base64
    try:
        header, encoded = uri.split(",", 1)
    except ValueError:
        return None
    if ";base64" in header:
        try:
            data = base64.b64decode(encoded)
        except Exception:
            return None
    else:
        data = encoded.encode("utf-8")
    if len(data) > max_bytes:
        return None
    return data


# --------------------------------------------------------------------------
# Queries
# --------------------------------------------------------------------------

def get_job(db: Session, job_id: str) -> DBJob | None:
    return db.query(DBJob).filter(DBJob.id == job_id).first()


def list_jobs(db: Session, *, limit: int = 20, offset: int = 0) -> list[DBJob]:
    return (
        db.query(DBJob)
        .order_by(DBJob.created_at.desc())
        .offset(offset)
        .limit(limit)
        .all()
    )


def delete_job(db: Session, job_id: str) -> bool:
    """Delete a job and its un-handed-off artifacts (explicit cleanup, task 2.10)."""
    job = get_job(db, job_id)
    if job is None:
        return False
    # Explicit child cleanup (SQLite FK cascade is not assumed).
    doc_ids = [d.id for d in db.query(DBDoc).filter(DBDoc.job_id == job_id).all()]
    db.query(DBPage).filter(DBPage.job_id == job_id).delete(synchronize_session=False)
    db.query(DBAsset).filter(DBAsset.job_id == job_id).delete(synchronize_session=False)
    db.query(DBDoc).filter(DBDoc.job_id == job_id).delete(synchronize_session=False)
    db.delete(job)
    db.commit()
    return True


__all__ = [
    "create_upload_job",
    "create_url_job",
    "delete_job",
    "get_job",
    "list_jobs",
    "run_url_ingestion",
]
