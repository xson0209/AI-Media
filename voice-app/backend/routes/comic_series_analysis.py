"""Comic Series Analysis endpoints (prefix ``/comic-series-analysis``).

Independent of Video Inspiration: no import of its routes/services and no
AI-Video handoff endpoint. Job-start endpoints return HTTP 202; list/detail
stay lightweight and large collections are paginated (tasks 7.5, 7.6).
Asset download uses canonical storage paths keyed by asset id — never an
arbitrary client path (task 5.12, 11.5).
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from .. import config
from ..database import (
    ComicSourceAsset as DBAsset,
    ComicSourcePage as DBPage,
    ComicSpeechBubble as DBBubble,
    ComicDetectedCharacter as DBCharacter,
    get_db,
)
from ..services.comic_series_analysis import config as comic_config
from ..services.comic_series_analysis import image_pipeline
from ..services.comic_series_analysis import runner, schemas, service
from ..services.comic_series_analysis.contracts import ComicAnalysisError

router = APIRouter(prefix="/comic-series-analysis", tags=["comic-series-analysis"])


def _raise(exc: ComicAnalysisError) -> None:
    raise HTTPException(
        status_code=exc.status_code,
        detail={"message": str(exc), "error_code": exc.error_code},
    )


def _get_job_or_404(db: Session, job_id: str):
    job = service.get_job(db, job_id)
    if job is None:
        raise HTTPException(
            status_code=404,
            detail={"message": "Không tìm thấy job phân tích truyện tranh.",
                    "error_code": "COMIC_ANALYSIS_NOT_FOUND"},
        )
    return job


@router.get("/capabilities")
async def get_capabilities():
    """Codec capability + feature-flag report for the UI / health checks."""
    from ..services.comic_series_analysis import codec_registry
    return {
        "feature_enabled": comic_config.is_feature_enabled(),
        "codecs": codec_registry.capability_report(),
    }


@router.get("/jobs", response_model=schemas.ComicJobListResponse)
async def list_jobs(
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
):
    jobs = service.list_jobs(db, limit=limit, offset=offset)
    return schemas.ComicJobListResponse(
        jobs=[schemas.job_summary(j) for j in jobs],
        total=len(jobs),
        limit=limit,
        offset=offset,
    )


@router.get("/jobs/{job_id}", response_model=schemas.ComicJobDetailResponse)
async def get_job(job_id: str, db: Session = Depends(get_db)):
    job = _get_job_or_404(db, job_id)
    return schemas.job_detail(job)


@router.post("/jobs/from-url", response_model=schemas.ComicJobDetailResponse)
async def create_from_url(data: schemas.ComicUrlJobRequest, db: Session = Depends(get_db)):
    try:
        job = service.create_url_job(
            db,
            url=data.url,
            reading_mode=data.reading_mode,
            development_mode=data.development_mode,
            rights_attested=data.rights_attested,
            title=data.title,
        )
    except ComicAnalysisError as exc:
        _raise(exc)
    return schemas.job_detail(job)


@router.post("/jobs/from-upload", response_model=schemas.ComicJobDetailResponse)
async def create_from_upload(
    files: list[UploadFile] = File(...),
    reading_mode: str = Form("auto"),
    development_mode: str = Form("lay_cam_hung_va_viet_moi"),
    rights_attested: bool = Form(False),
    title: str | None = Form(None),
    db: Session = Depends(get_db),
):
    images: list[tuple[str, bytes]] = []
    for upload in files:
        data = await upload.read()
        images.append((upload.filename or "image", data))
    try:
        job = service.create_upload_job(
            db,
            images=images,
            reading_mode=reading_mode,
            development_mode=development_mode,
            rights_attested=rights_attested,
            title=title,
        )
    except ComicAnalysisError as exc:
        _raise(exc)
    return schemas.job_detail(job)


@router.post("/jobs/{job_id}/run", response_model=schemas.ComicJobDetailResponse, status_code=202)
async def run_job(job_id: str, db: Session = Depends(get_db)):
    try:
        job = runner.schedule_run(db, job_id)
    except ComicAnalysisError as exc:
        _raise(exc)
    return schemas.job_detail(job)


@router.post("/jobs/{job_id}/cancel", response_model=schemas.ComicJobDetailResponse)
async def cancel_job(job_id: str, db: Session = Depends(get_db)):
    job = runner.request_cancel(db, job_id)
    if job is None:
        _get_job_or_404(db, job_id)
    return schemas.job_detail(job)


@router.post("/jobs/{job_id}/retry", response_model=schemas.ComicJobDetailResponse, status_code=202)
async def retry_job(job_id: str, db: Session = Depends(get_db)):
    try:
        job = runner.retry_job(db, job_id)
    except ComicAnalysisError as exc:
        _raise(exc)
    return schemas.job_detail(job)


@router.delete("/jobs/{job_id}")
async def delete_job(job_id: str, db: Session = Depends(get_db)):
    if not service.delete_job(db, job_id):
        _get_job_or_404(db, job_id)
    return {"deleted": True, "job_id": job_id}


@router.post("/jobs/{job_id}/analyze", response_model=schemas.ComicJobDetailResponse, status_code=202)
def analyze_job(job_id: str, db: Session = Depends(get_db)):
    from ..services.comic_series_analysis import analysis
    _get_job_or_404(db, job_id)
    try:
        job = analysis.analyze_revision(db, job_id)
        db.commit()
    except ComicAnalysisError as exc:
        db.rollback()
        _raise(exc)
    return schemas.job_detail(job)


@router.get("/jobs/{job_id}/analysis-package")
async def get_analysis_package(job_id: str, db: Session = Depends(get_db)):
    job = _get_job_or_404(db, job_id)
    return job.analysis_package_json or {
        "analysis_revision": job.analysis_revision or 0,
        "panels": [],
        "dialogues": [],
        "characters": [],
        "locations": [],
        "plot": {},
    }


@router.post("/jobs/{job_id}/rewrite")
def rewrite_story(job_id: str, db: Session = Depends(get_db)):
    from ..services.comic_series_analysis import rewrite

    job = _get_job_or_404(db, job_id)
    previous_status = job.run_status
    previous_step = job.current_step
    previous_progress = float(job.progress or 0)
    try:
        job.run_status = "running"
        job.current_step = "rewrite_story"
        job.progress = max(previous_progress, 0.96)
        db.commit()
        db.refresh(job)

        job = rewrite.rewrite_optimized_script(db, job_id)
        job.run_status = "ready_for_review"
        job.current_step = "build_review"
        job.progress = 1.0
        db.commit()
        db.refresh(job)
    except ComicAnalysisError as exc:
        db.rollback()
        restore_job = service.get_job(db, job_id)
        if restore_job is not None:
            restore_job.run_status = previous_status
            restore_job.current_step = previous_step
            restore_job.progress = previous_progress
            db.commit()
        _raise(exc)
    return job.analysis_package_json or {}


# --- Review edits (each creates a new analysis revision) ------------------

@router.put("/jobs/{job_id}/dialogues/{bubble_id}")
async def edit_dialogue(job_id: str, bubble_id: str, data: dict, db: Session = Depends(get_db)):
    from ..services.comic_series_analysis import review_edits
    _get_job_or_404(db, job_id)
    try:
        revision = review_edits.edit_bubble(
            db, job_id, bubble_id,
            expected_revision=data.get("expected_revision"),
            approved_text=data.get("approved_text"),
            bubble_type=data.get("bubble_type"),
            speaker_character_id=data.get("speaker_character_id"),
        )
    except ComicAnalysisError as exc:
        _raise(exc)
    return {"analysis_revision": revision}


@router.put("/jobs/{job_id}/panels/reorder")
async def reorder_panels(job_id: str, data: dict, db: Session = Depends(get_db)):
    from ..services.comic_series_analysis import review_edits
    _get_job_or_404(db, job_id)
    try:
        revision = review_edits.reorder_panels(
            db, job_id, data.get("ordered_panel_ids", []),
            expected_revision=data.get("expected_revision"),
        )
    except ComicAnalysisError as exc:
        _raise(exc)
    return {"analysis_revision": revision}


@router.post("/jobs/{job_id}/characters/merge")
async def merge_characters(job_id: str, data: dict, db: Session = Depends(get_db)):
    from ..services.comic_series_analysis import review_edits
    _get_job_or_404(db, job_id)
    try:
        revision = review_edits.merge_characters(
            db, job_id,
            source_ids=data.get("source_ids", []),
            target_id=data["target_id"],
            expected_revision=data.get("expected_revision"),
        )
    except (ComicAnalysisError, KeyError) as exc:
        if isinstance(exc, ComicAnalysisError):
            _raise(exc)
        raise HTTPException(status_code=400, detail={"message": "Thiếu target_id.",
                                                     "error_code": "COMIC_ANALYSIS_INVALID_STATE"})
    return {"analysis_revision": revision}


@router.post("/jobs/{job_id}/characters/split")
async def split_character(job_id: str, data: dict, db: Session = Depends(get_db)):
    from ..services.comic_series_analysis import review_edits
    _get_job_or_404(db, job_id)
    try:
        revision, new_id = review_edits.split_character(
            db, job_id, data["character_id"],
            new_name=data.get("new_name", "Nhân vật mới"),
            moved_evidence_ids=data.get("moved_evidence_ids", []),
            expected_revision=data.get("expected_revision"),
        )
    except (ComicAnalysisError, KeyError) as exc:
        if isinstance(exc, ComicAnalysisError):
            _raise(exc)
        raise HTTPException(status_code=400, detail={"message": "Thiếu character_id.",
                                                     "error_code": "COMIC_ANALYSIS_INVALID_STATE"})
    return {"analysis_revision": revision, "new_character_id": new_id}


@router.post("/jobs/{job_id}/approve")
async def approve_job(job_id: str, data: dict, db: Session = Depends(get_db)):
    from ..services.comic_series_analysis import approval_manifest
    job = _get_job_or_404(db, job_id)
    if job.run_status not in ("ready_for_review", "approved"):
        raise HTTPException(status_code=409, detail={
            "message": "Job chưa sẵn sàng để duyệt.", "error_code": "COMIC_ANALYSIS_INVALID_STATE"})
    manifest = approval_manifest.create_manifest(
        db, job_id=job_id, analysis_revision=job.analysis_revision or 1,
        accepted_items=data.get("accepted_items", []),
        excluded_items=data.get("excluded_items", []),
        unreviewed_items=data.get("unreviewed_items", []),
        accepted_limitations=data.get("accepted_limitations", []),
        development_mode=job.development_mode,
        rights_attestation_revision=job.rights_attestation_revision or 0,
    )
    job.run_status = "approved"
    job.approval_manifest_id = manifest.id
    db.commit()
    return {"approved": True, "manifest_id": manifest.id, "manifest_hash": manifest.manifest_hash}


# --- Paginated sub-collections (task 7.6) ---------------------------------

@router.get("/jobs/{job_id}/pages", response_model=schemas.PaginatedResponse)
async def list_pages(
    job_id: str,
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
):
    _get_job_or_404(db, job_id)
    query = db.query(DBPage).filter(DBPage.job_id == job_id).order_by(DBPage.page_order)
    total = query.count()
    rows = query.offset(offset).limit(limit).all()
    items = [
        {"id": p.id, "page_order": p.page_order, "page_kind": p.page_kind,
         "asset_id": p.asset_id, "extracted_text": p.extracted_text,
         "evidence_id": p.evidence_id, "provenance": p.provenance}
        for p in rows
    ]
    return schemas.PaginatedResponse(items=items, total=total, limit=limit, offset=offset)


@router.get("/jobs/{job_id}/characters", response_model=schemas.PaginatedResponse)
async def list_characters(
    job_id: str,
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
):
    _get_job_or_404(db, job_id)
    query = db.query(DBCharacter).filter(DBCharacter.job_id == job_id)
    total = query.count()
    rows = query.offset(offset).limit(limit).all()
    items = [
        {"id": c.id, "display_name": c.display_name, "role": c.role,
         "confidence": c.confidence, "evidence_ids": c.evidence_ids_json}
        for c in rows
    ]
    return schemas.PaginatedResponse(items=items, total=total, limit=limit, offset=offset)


# --- Asset download (canonical storage path only, task 5.12) --------------

def _serve_asset_path(db: Session, asset_id: str, kind: str) -> FileResponse:
    asset = db.query(DBAsset).filter(DBAsset.id == asset_id).first()
    if asset is None:
        raise HTTPException(status_code=404, detail={"message": "Không tìm thấy asset ảnh.",
                                                     "error_code": "COMIC_ASSET_NOT_FOUND"})
    if kind == "original":
        stored = asset.original_path
        media = f"image/{asset.detected_format or 'octet-stream'}"
    else:
        derivatives = asset.derivatives_json or {}
        stored = derivatives.get(f"{kind}_path")
        media = "image/webp" if kind == "preview" else "image/png"
    if not stored:
        raise HTTPException(status_code=404, detail={"message": "Không có bản ảnh yêu cầu.",
                                                     "error_code": "COMIC_ASSET_FILE_MISSING"})
    path = config.resolve_storage_path(stored)
    if path is None or not path.exists():
        raise HTTPException(status_code=404, detail={"message": "File asset không còn tồn tại.",
                                                     "error_code": "COMIC_ASSET_FILE_MISSING"})
    filename = f"comic-{asset.id}-{kind}.{(asset.detected_format or 'bin') if kind == 'original' else ('webp' if kind == 'preview' else 'png')}"
    return FileResponse(path, media_type=media, filename=filename)


@router.get("/assets/{asset_id}/original")
async def get_asset_original(asset_id: str, db: Session = Depends(get_db)):
    return _serve_asset_path(db, asset_id, "original")


@router.get("/assets/{asset_id}/preview")
async def get_asset_preview(asset_id: str, db: Session = Depends(get_db)):
    return _serve_asset_path(db, asset_id, "preview")

@router.post("/assets/{asset_id}/exports")
async def export_asset(
    asset_id: str,
    export_format: str = Query("png", alias="format", pattern="^(png|webp|heic|heif)$"),
    db: Session = Depends(get_db),
):
    """Create and return an on-demand export from the immutable original.

    The client supplies only an asset id and target format. The source path is
    resolved from DB storage metadata and the output path is server-generated
    under the Comic Analysis exports directory, so no arbitrary path can be
    read or written (task 5.12).
    """
    asset = db.query(DBAsset).filter(DBAsset.id == asset_id).first()
    if asset is None:
        raise HTTPException(status_code=404, detail={"message": "Không tìm thấy asset ảnh.",
                                                     "error_code": "COMIC_ASSET_NOT_FOUND"})
    if not asset.original_path:
        raise HTTPException(status_code=404, detail={"message": "Không có bản ảnh gốc để export.",
                                                     "error_code": "COMIC_ASSET_FILE_MISSING"})
    original_path = config.resolve_storage_path(asset.original_path)
    if original_path is None or not original_path.exists():
        raise HTTPException(status_code=404, detail={"message": "File asset không còn tồn tại.",
                                                     "error_code": "COMIC_ASSET_FILE_MISSING"})

    fmt = export_format.lower()
    try:
        exported = image_pipeline.export_image(original_path.read_bytes(), fmt)
    except ComicAnalysisError as exc:
        _raise(exc)

    exports_dir = comic_config.get_storage_subdir("exports")
    checksum = asset.checksum or asset.id
    export_path = exports_dir / f"{checksum}.{fmt}"
    if not export_path.exists():
        tmp = export_path.with_suffix(export_path.suffix + ".tmp")
        tmp.write_bytes(exported)
        tmp.replace(export_path)

    derivatives = dict(asset.derivatives_json or {})
    exports = dict(derivatives.get("exports") or {})
    exports[fmt] = config.to_storage_path(export_path)
    derivatives["exports"] = exports
    asset.derivatives_json = derivatives
    db.commit()

    media = {
        "png": "image/png",
        "webp": "image/webp",
        "heic": "image/heic",
        "heif": "image/heif",
    }[fmt]
    return FileResponse(
        export_path,
        media_type=media,
        filename=f"comic-{asset.id}.{fmt}",
    )


# --- Series handoff (two gates; never AI Video) ---------------------------

@router.post("/jobs/{job_id}/series-handoff/preview")
async def create_handoff_preview(job_id: str, data: dict, db: Session = Depends(get_db)):
    from ..services.comic_series_analysis import handoff
    _get_job_or_404(db, job_id)
    try:
        preview = handoff.build_preview(
            db, job_id,
            target_kind=data.get("target_kind", "new_series"),
            target_series_id=data.get("target_series_id"),
            target_series_mode=data.get("target_series_mode", "image_story_only"),
            target_series_title=data.get("target_series_title"),
            episode_number=data.get("episode_number"),
            episode_title=data.get("episode_title"),
            output_intent=data.get("output_intent", "truyen_anh"),
            output_settings=data.get("output_settings"),
            market_profile=data.get("market_profile"),
            language_profile=data.get("language_profile"),
            source_input=data.get("source_input"),
            selected_items=data.get("selected_items"),
            conflict_resolutions=data.get("conflict_resolutions"),
        )
    except ComicAnalysisError as exc:
        _raise(exc)
    return {
        "handoff_id": preview.id,
        "status": preview.status,
        "preview_fingerprint": preview.preview_fingerprint,
        "target_kind": preview.target_kind,
        "target_series_mode": preview.target_series_mode,
        "target_series_title": handoff.target_series_title_for_handoff(preview),
        "output_intent": preview.output_intent,
        "output_settings": handoff.output_settings_for_handoff(preview),
        "market_profile": handoff.market_profile_for_handoff(preview),
        "language_profile": handoff.language_profile_for_handoff(preview),
        "episode_number": preview.episode_number,
        "item_decisions": preview.item_decisions_json,
    }


@router.post("/jobs/{job_id}/series-handoff/commit")
async def commit_handoff_endpoint(job_id: str, data: dict, db: Session = Depends(get_db)):
    from ..services.comic_series_analysis import handoff
    _get_job_or_404(db, job_id)
    handoff_id = data.get("handoff_id")
    idempotency_key = data.get("idempotency_key")
    if not handoff_id or not idempotency_key:
        raise HTTPException(
            status_code=400,
            detail={"message": "Thiếu handoff_id hoặc idempotency_key.",
                    "error_code": "COMIC_ANALYSIS_INVALID_STATE"},
        )
    try:
        committed = handoff.commit_handoff(db, handoff_id, idempotency_key=idempotency_key)
    except ComicAnalysisError as exc:
        _raise(exc)
    return committed.result_json or {"handoff_id": committed.id, "status": committed.status}
