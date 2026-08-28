"""Video inspiration endpoints."""

from __future__ import annotations

import asyncio
import threading
from typing import Literal

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from .. import config
from .. import models
from ..database import VideoInspirationFrame as DBVideoInspirationFrame, VideoInspirationJob as DBVideoInspirationJob, get_db
from ..services import video_inspiration, video_inspiration_runs, video_project_memory, video_quality
from ..services.task_queue import create_background_task
from ..services import video_workflow_pool

router = APIRouter(prefix="/video-inspiration", tags=["video-inspiration"])
_variant_runs_lock = threading.RLock()
_variant_runs: set[str] = set()

async def _variant_heartbeat(job_id: str, stop: asyncio.Event) -> None:
    while not stop.is_set():
        try:
            await asyncio.wait_for(stop.wait(), timeout=30)
        except asyncio.TimeoutError:
            db_iter = get_db()
            db = next(db_iter)
            try:
                row = db.query(DBVideoInspirationJob).filter(DBVideoInspirationJob.id == job_id).first()
                if row is not None and row.status == "rewriting":
                    row.updated_at = video_inspiration._now()
                    db.commit()
            finally:
                db_iter.close()

async def _run_variant_stage(operation: str, job_id: str, data: object) -> None:
    db_iter = get_db()
    db = next(db_iter)
    heartbeat_stop = asyncio.Event()
    heartbeat_task = asyncio.create_task(_variant_heartbeat(job_id, heartbeat_stop))
    try:
        fn = {
            "candidates": video_inspiration.generate_variant_candidates,
            "score": video_inspiration.score_variant_candidates,
            "synthesize": video_inspiration.synthesize_variant_versions,
        }[operation]
        async with video_workflow_pool.workflow_slot(
            work_key=f"video-inspiration:{job_id}",
            workflow_type="video_inspiration",
            operation_name=f"variant_{operation}",
        ):
            await asyncio.to_thread(fn, job_id, data, db)
    except Exception as exc:
        row = db.query(DBVideoInspirationJob).filter(DBVideoInspirationJob.id == job_id).first()
        if row is not None:
            video_inspiration._fail_job(row, db, exc)
    finally:
        heartbeat_stop.set()
        await heartbeat_task
        with _variant_runs_lock:
            _variant_runs.discard(job_id)
        db_iter.close()

def _queue_variant_stage(operation: str, job_id: str, data: object, db: Session) -> models.VideoInspirationJobResponse | None:
    row = db.query(DBVideoInspirationJob).filter(DBVideoInspirationJob.id == job_id).first()
    if row is None:
        return None
    if not video_inspiration.variant_pipeline_enabled():
        raise video_inspiration.VideoInspirationError("Tính năng nhiều phiên bản đang được tạm tắt.", error_code="VIDEO_INSPIRATION_VARIANTS_DISABLED", status_code=503)
    with _variant_runs_lock:
        if job_id in _variant_runs:
            raise video_inspiration.VideoInspirationError("Job này đang chạy một stage biến thể. Hãy chờ stage hiện tại hoàn tất.", error_code="VIDEO_INSPIRATION_VARIANT_STAGE_ACTIVE", status_code=409)
        if row.status in video_inspiration.ACTIVE_JOB_STATUSES or row.status not in {"analyzed", "rewritten"}:
            raise video_inspiration.VideoInspirationError("Cần có phân tích hoàn tất trước khi chạy stage biến thể.", error_code="VIDEO_INSPIRATION_VARIANTS_ANALYSIS_REQUIRED", status_code=409)
        _variant_runs.add(job_id)
    row.status = "rewriting"
    row.current_step = {
        "candidates": "variant_generation",
        "score": "variant_scoring",
        "synthesize": "variant_synthesis",
    }[operation]
    row.progress = 0.90
    row.updated_at = video_inspiration._now()
    db.commit()
    try:
        create_background_task(_run_variant_stage(operation, job_id, data))
    except BaseException:
        with _variant_runs_lock:
            _variant_runs.discard(job_id)
        raise
    return video_inspiration.get_job(job_id, db)

def _raise_error(exc: video_inspiration.VideoInspirationError) -> None:
    raise HTTPException(
        status_code=exc.status_code,
        detail={"message": str(exc), "error_code": exc.error_code},
    )

def _raise_memory_error(exc: video_project_memory.VideoProjectMemoryError) -> None:
    raise HTTPException(
        status_code=exc.status_code,
        detail={"message": str(exc), "error_code": exc.error_code},
    )

def _raise_quality_error(exc: video_quality.VideoQualityError) -> None:
    raise HTTPException(
        status_code=exc.status_code,
        detail={"message": str(exc), "error_code": exc.error_code},
    )

@router.get("/jobs", response_model=models.VideoInspirationListResponse)
async def list_video_inspiration_jobs(
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
):
    return video_inspiration.list_jobs(db, limit=limit, offset=offset)

@router.get("/jobs/{job_id}", response_model=models.VideoInspirationJobResponse)
async def get_video_inspiration_job(job_id: str, db: Session = Depends(get_db)):
    job = video_inspiration.get_job(job_id, db)
    if job is None:
        raise HTTPException(status_code=404, detail={"message": "Không tìm thấy job video cảm hứng.", "error_code": "VIDEO_INSPIRATION_NOT_FOUND"})
    return job

@router.get("/frames/{frame_id}")
async def get_video_inspiration_frame(frame_id: str, db: Session = Depends(get_db)):
    frame = db.query(DBVideoInspirationFrame).filter(DBVideoInspirationFrame.id == frame_id).first()
    if frame is None:
        raise HTTPException(status_code=404, detail={"message": "Không tìm thấy frame video.", "error_code": "VIDEO_INSPIRATION_FRAME_NOT_FOUND"})
    path = config.resolve_storage_path(frame.frame_path)
    if path is None or not path.exists():
        raise HTTPException(status_code=404, detail={"message": "File frame không còn tồn tại.", "error_code": "VIDEO_INSPIRATION_FRAME_FILE_NOT_FOUND"})
    return FileResponse(path, media_type="image/jpeg")

@router.post("/jobs/upload", response_model=models.VideoInspirationJobResponse)
async def upload_video_inspiration_job(
    file: UploadFile = File(...),
    target_language: str = Form("vi"),
    user_direction: str | None = Form(None),
    db: Session = Depends(get_db),
):
    try:
        data = await file.read(video_inspiration.MAX_VIDEO_BYTES + 1)
        return video_inspiration.create_upload_job(
            data=data,
            filename=file.filename or "video.mp4",
            content_type=file.content_type,
            target_language=target_language,
            user_direction=user_direction,
            db=db,
        )
    except video_inspiration.VideoInspirationError as exc:
        _raise_error(exc)

@router.post("/jobs/from-url", response_model=models.VideoInspirationJobResponse)
async def create_video_inspiration_job_from_url(
    data: models.VideoInspirationUrlRequest,
    db: Session = Depends(get_db),
):
    try:
        return video_inspiration.create_url_job(
            url=data.url,
            target_language=data.target_language,
            user_direction=data.user_direction,
            use_browser_cookies=data.use_browser_cookies,
            db=db,
        )
    except video_inspiration.VideoInspirationError as exc:
        _raise_error(exc)

@router.post("/jobs/{job_id}/analyze", response_model=models.VideoInspirationJobResponse, status_code=202)
async def analyze_video_inspiration_job(
    job_id: str,
    data: models.VideoInspirationAnalyzeRequest | None = None,
    db: Session = Depends(get_db),
):
    try:
        job = video_inspiration_runs.schedule_analyze(
            job_id,
            data or models.VideoInspirationAnalyzeRequest(),
            db,
        )
    except video_inspiration.VideoInspirationError as exc:
        _raise_error(exc)
    if job is None:
        raise HTTPException(status_code=404, detail={"message": "Không tìm thấy job video cảm hứng.", "error_code": "VIDEO_INSPIRATION_NOT_FOUND"})
    return job

@router.post("/jobs/{job_id}/deep-research", response_model=models.VideoInspirationJobResponse, status_code=202)
async def deep_research_video_inspiration_job(
    job_id: str,
    data: models.VideoInspirationAnalyzeRequest | None = None,
    db: Session = Depends(get_db),
):
    """Start the high-quality analysis profile used by the one-click AI Video handoff."""
    try:
        request = data or models.VideoInspirationAnalyzeRequest(analysis_mode="high_quality", handoff_to_ai_video=True)
        request.analysis_mode = "high_quality"
        request.handoff_to_ai_video = True
        job = video_inspiration_runs.schedule_analyze(job_id, request, db)
    except video_inspiration.VideoInspirationError as exc:
        _raise_error(exc)
    if job is None:
        raise HTTPException(status_code=404, detail={"message": "Không tìm thấy job video cảm hứng.", "error_code": "VIDEO_INSPIRATION_NOT_FOUND"})
    return job

@router.post("/jobs/{job_id}/variants/candidates", response_model=models.VideoInspirationJobResponse, status_code=202)
async def generate_video_inspiration_variants(
    job_id: str,
    data: models.VideoInspirationVariantGenerateRequest | None = None,
    db: Session = Depends(get_db),
):
    try:
        job = _queue_variant_stage("candidates", job_id, data or models.VideoInspirationVariantGenerateRequest(), db)
    except video_inspiration.VideoInspirationError as exc:
        _raise_error(exc)
    if job is None:
        raise HTTPException(status_code=404, detail={"message": "Không tìm thấy job video cảm hứng.", "error_code": "VIDEO_INSPIRATION_NOT_FOUND"})
    return job

@router.post("/jobs/{job_id}/variants/score", response_model=models.VideoInspirationJobResponse, status_code=202)
async def score_video_inspiration_variants(
    job_id: str,
    data: models.VideoInspirationVariantScoreRequest | None = None,
    db: Session = Depends(get_db),
):
    try:
        job = _queue_variant_stage("score", job_id, data or models.VideoInspirationVariantScoreRequest(), db)
    except video_inspiration.VideoInspirationError as exc:
        _raise_error(exc)
    if job is None:
        raise HTTPException(status_code=404, detail={"message": "Không tìm thấy job video cảm hứng.", "error_code": "VIDEO_INSPIRATION_NOT_FOUND"})
    return job

@router.post("/jobs/{job_id}/variants/synthesize", response_model=models.VideoInspirationJobResponse, status_code=202)
async def synthesize_video_inspiration_variants(
    job_id: str,
    data: models.VideoInspirationVariantSynthesisRequest | None = None,
    db: Session = Depends(get_db),
):
    try:
        job = _queue_variant_stage("synthesize", job_id, data or models.VideoInspirationVariantSynthesisRequest(), db)
    except video_inspiration.VideoInspirationError as exc:
        _raise_error(exc)
    if job is None:
        raise HTTPException(status_code=404, detail={"message": "Không tìm thấy job video cảm hứng.", "error_code": "VIDEO_INSPIRATION_NOT_FOUND"})
    return job

@router.post("/jobs/{job_id}/variants/select", response_model=models.VideoInspirationJobResponse)
async def select_video_inspiration_variant(
    job_id: str,
    data: models.VideoInspirationVariantSelectRequest,
    db: Session = Depends(get_db),
):
    try:
        job = video_inspiration.select_variant_version(job_id, data, db)
    except video_inspiration.VideoInspirationError as exc:
        _raise_error(exc)
    if job is None:
        raise HTTPException(status_code=404, detail={"message": "Không tìm thấy job video cảm hứng.", "error_code": "VIDEO_INSPIRATION_NOT_FOUND"})
    return job

@router.put("/jobs/{job_id}/transcript", response_model=models.VideoInspirationJobResponse)
async def update_video_inspiration_transcript(
    job_id: str,
    data: models.VideoInspirationTranscriptUpdate,
    db: Session = Depends(get_db),
):
    job = video_inspiration.update_transcript(job_id, data, db)
    if job is None:
        raise HTTPException(status_code=404, detail={"message": "Không tìm thấy job video cảm hứng.", "error_code": "VIDEO_INSPIRATION_NOT_FOUND"})
    return job

@router.put("/jobs/{job_id}/transcript-segments/{segment_id}", response_model=models.VideoInspirationJobResponse)
async def update_video_inspiration_transcript_segment(
    job_id: str,
    segment_id: str,
    data: models.VideoInspirationTranscriptSegmentUpdate,
    db: Session = Depends(get_db),
):
    try:
        job = video_inspiration.update_transcript_segment(job_id, segment_id, data, db)
    except video_inspiration.VideoInspirationError as exc:
        _raise_error(exc)
    if job is None:
        raise HTTPException(status_code=404, detail={"message": "Không tìm thấy job video cảm hứng.", "error_code": "VIDEO_INSPIRATION_NOT_FOUND"})
    return job

@router.put("/jobs/{job_id}/on-screen-text/{event_id}", response_model=models.VideoInspirationJobResponse)
async def update_video_inspiration_text_event(
    job_id: str,
    event_id: str,
    data: models.VideoInspirationTextEventUpdate,
    db: Session = Depends(get_db),
):
    try:
        job = video_inspiration.update_text_event(job_id, event_id, data, db)
    except video_inspiration.VideoInspirationError as exc:
        _raise_error(exc)
    if job is None:
        raise HTTPException(status_code=404, detail={"message": "Không tìm thấy job video cảm hứng.", "error_code": "VIDEO_INSPIRATION_NOT_FOUND"})
    return job

@router.get("/jobs/{job_id}/analysis-package")
async def get_video_inspiration_analysis_package(job_id: str, db: Session = Depends(get_db)):
    job = video_inspiration.get_job(job_id, db)
    if job is None:
        raise HTTPException(status_code=404, detail={"message": "Không tìm thấy job video cảm hứng.", "error_code": "VIDEO_INSPIRATION_NOT_FOUND"})
    return job.analysis_package_json or {
        "schema_version": job.analysis_schema_version,
        "job_id": job.id,
        "analysis_completeness": job.analysis_completeness,
        "coverage_metrics": job.coverage_metrics_json or {},
        "limitations": job.limitations_json or [],
    }

@router.post("/jobs/{job_id}/handoffs", response_model=models.VideoInspirationStructuredHandoffResponse)
async def create_video_inspiration_handoff(job_id: str, db: Session = Depends(get_db)):
    try:
        handoff = video_project_memory.create_handoff_for_job(job_id, db, status="ready_for_review")
    except video_project_memory.VideoProjectMemoryError as exc:
        _raise_memory_error(exc)
    if handoff is None:
        raise HTTPException(status_code=404, detail={"message": "Không tìm thấy job video cảm hứng.", "error_code": "VIDEO_INSPIRATION_NOT_FOUND"})
    return handoff

@router.get("/jobs/{job_id}/handoffs", response_model=models.VideoInspirationHandoffListResponse)
async def list_video_inspiration_handoffs(job_id: str, db: Session = Depends(get_db)):
    job = video_inspiration.get_job(job_id, db)
    if job is None:
        raise HTTPException(status_code=404, detail={"message": "Không tìm thấy job video cảm hứng.", "error_code": "VIDEO_INSPIRATION_NOT_FOUND"})
    return video_project_memory.list_handoffs_for_job(job_id, db)

@router.post("/jobs/{job_id}/quality/reports", response_model=models.VideoQualityReportResponse)
async def run_video_inspiration_quality_report(
    job_id: str,
    data: models.VideoQualityRunRequest | None = None,
    db: Session = Depends(get_db),
):
    try:
        report = video_quality.run_job_quality_report(job_id, data or models.VideoQualityRunRequest(), db)
    except video_quality.VideoQualityError as exc:
        _raise_quality_error(exc)
    if report is None:
        raise HTTPException(status_code=404, detail={"message": "Không tìm thấy job video cảm hứng.", "error_code": "VIDEO_INSPIRATION_NOT_FOUND"})
    return report

@router.get("/jobs/{job_id}/quality/reports/latest", response_model=models.VideoQualityReportResponse | None)
async def get_latest_video_inspiration_quality_report(job_id: str, db: Session = Depends(get_db)):
    job = video_inspiration.get_job(job_id, db)
    if job is None:
        raise HTTPException(status_code=404, detail={"message": "Không tìm thấy job video cảm hứng.", "error_code": "VIDEO_INSPIRATION_NOT_FOUND"})
    return video_quality.get_latest_job_report(job_id, db)

@router.post("/jobs/{job_id}/retention-datasets", response_model=models.PlatformRetentionDatasetResponse)
async def import_video_inspiration_retention_dataset(
    job_id: str,
    data: models.PlatformRetentionDatasetCreateRequest,
    db: Session = Depends(get_db),
):
    dataset = video_quality.create_job_retention_dataset(job_id, data, db)
    if dataset is None:
        raise HTTPException(status_code=404, detail={"message": "Không tìm thấy job video cảm hứng.", "error_code": "VIDEO_INSPIRATION_NOT_FOUND"})
    return dataset

@router.put("/jobs/{job_id}/direction", response_model=models.VideoInspirationJobResponse)
async def update_video_inspiration_direction(
    job_id: str,
    data: models.VideoInspirationDirectionUpdate,
    db: Session = Depends(get_db),
):
    job = video_inspiration.update_direction(job_id, data, db)
    if job is None:
        raise HTTPException(status_code=404, detail={"message": "Không tìm thấy job video cảm hứng.", "error_code": "VIDEO_INSPIRATION_NOT_FOUND"})
    return job

@router.post("/jobs/{job_id}/rewrite", response_model=models.VideoInspirationJobResponse, status_code=202)
async def rewrite_video_inspiration_job(
    job_id: str,
    data: models.VideoInspirationRewriteRequest | None = None,
    db: Session = Depends(get_db),
):
    try:
        job = video_inspiration_runs.schedule_rewrite(
            job_id,
            data or models.VideoInspirationRewriteRequest(),
            db,
        )
    except video_inspiration.VideoInspirationError as exc:
        _raise_error(exc)
    if job is None:
        raise HTTPException(status_code=404, detail={"message": "Không tìm thấy job video cảm hứng.", "error_code": "VIDEO_INSPIRATION_NOT_FOUND"})
    return job


@router.post("/jobs/{job_id}/cancel", response_model=models.VideoInspirationJobResponse)
async def cancel_video_inspiration_job(job_id: str, db: Session = Depends(get_db)):
    job = video_inspiration_runs.cancel_job(job_id, db)
    if job is None:
        raise HTTPException(status_code=404, detail={"message": "Không tìm thấy job video cảm hứng.", "error_code": "VIDEO_INSPIRATION_NOT_FOUND"})
    return job


@router.post("/jobs/{job_id}/retry", response_model=models.VideoInspirationJobResponse, status_code=202)
async def retry_video_inspiration_job(
    job_id: str,
    operation: Literal["analyze", "rewrite"] | None = Query(None),
    db: Session = Depends(get_db),
):
    try:
        job = video_inspiration_runs.retry_job(job_id, db, operation=operation)
    except video_inspiration.VideoInspirationError as exc:
        _raise_error(exc)
    if job is None:
        raise HTTPException(status_code=404, detail={"message": "Không tìm thấy job video cảm hứng.", "error_code": "VIDEO_INSPIRATION_NOT_FOUND"})
    return job

@router.put("/jobs/{job_id}/script", response_model=models.VideoInspirationJobResponse)
async def update_video_inspiration_script(
    job_id: str,
    data: models.VideoInspirationScriptUpdate,
    db: Session = Depends(get_db),
):
    job = video_inspiration.update_script(job_id, data, db)
    if job is None:
        raise HTTPException(status_code=404, detail={"message": "Không tìm thấy job video cảm hứng.", "error_code": "VIDEO_INSPIRATION_NOT_FOUND"})
    return job

@router.post("/jobs/{job_id}/create-ai-video-project", response_model=models.VideoInspirationHandoffResponse)
async def create_ai_video_project_from_video_inspiration(
    job_id: str,
    data: models.VideoInspirationCreateProjectRequest | None = None,
    db: Session = Depends(get_db),
):
    try:
        result = await video_inspiration.create_ai_video_project(
            job_id,
            data or models.VideoInspirationCreateProjectRequest(),
            db,
        )
    except video_inspiration.VideoInspirationError as exc:
        _raise_error(exc)
    if result is None:
        raise HTTPException(status_code=404, detail={"message": "Không tìm thấy job video cảm hứng.", "error_code": "VIDEO_INSPIRATION_NOT_FOUND"})
    return result
