"""Product Video prompt endpoints plus the shared AI Video render bridge.

Product Video still does not create provider-generation or TTS jobs. Users
explicitly upload clips and start rendering through the shared AI Video panel.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy.orm import Session
from starlette.concurrency import run_in_threadpool

from .. import models
from ..database import get_db
from ..database import session as database_session
from ..services import ai_planning, product_video, video_errors
from ..services.video_planning import VideoPlanningValidationError
from ..utils.http import safe_content_disposition

router = APIRouter(prefix="/product-video", tags=["product-video"], route_class=video_errors.AIVideoRoute)


async def _run_with_worker_db(callback, *args, **kwargs):
    """Run blocking Codex planning off FastAPI's event loop, on its own session."""
    worker_db = database_session.SessionLocal()
    try:
        return await run_in_threadpool(callback, *args, worker_db, **kwargs)
    finally:
        worker_db.close()


def _error(status_code: int, message: str, error_code: str, **context) -> HTTPException:
    return video_errors.api_error(status_code, message, error_code, **context)


def _not_found() -> HTTPException:
    return _error(404, "Không tìm thấy project video sản phẩm.", "PRODUCT_VIDEO_PROJECT_NOT_FOUND")


@router.get("/projects", response_model=list[models.ProductVideoProjectResponse])
async def list_product_video_projects(db: Session = Depends(get_db)):
    return product_video.list_projects(db)


@router.post("/projects", response_model=models.ProductVideoProjectDetailResponse)
async def create_product_video_project(
    data: models.ProductVideoProjectCreate,
    db: Session = Depends(get_db),
):
    return product_video.create_project(data, db)


@router.get("/projects/{project_id}", response_model=models.ProductVideoProjectDetailResponse)
async def get_product_video_project(project_id: str, db: Session = Depends(get_db)):
    project = product_video.get_project(project_id, db)
    if project is None:
        raise _not_found()
    return project


@router.put("/projects/{project_id}", response_model=models.ProductVideoProjectDetailResponse)
async def update_product_video_project(
    project_id: str,
    data: models.ProductVideoProjectUpdate,
    db: Session = Depends(get_db),
):
    project = product_video.update_project(project_id, data, db)
    if project is None:
        raise _not_found()
    return project


@router.delete("/projects/{project_id}")
async def delete_product_video_project(project_id: str, db: Session = Depends(get_db)):
    if not product_video.delete_project(project_id, db):
        raise _not_found()
    return {"status": "deleted", "project_id": project_id}


@router.post("/projects/{project_id}/shots", response_model=list[models.ProductVideoShotResponse])
async def plan_product_video_shots(project_id: str, db: Session = Depends(get_db)):
    try:
        shots = await _run_with_worker_db(product_video.plan_shots, project_id)
    except ai_planning.AIPlanningError as exc:
        raise _error(502, str(exc), exc.error_code, exc=exc, project_id=project_id, step_name="product_video_shots") from exc
    except VideoPlanningValidationError as exc:
        raise _error(
            502,
            str(exc),
            "PRODUCT_VIDEO_PLANNING_INVALID_OUTPUT",
            exc=exc,
            project_id=project_id,
            step_name="product_video_shots",
        ) from exc
    except product_video.ProductVideoRenderBridgeError as exc:
        raise _error(
            502,
            str(exc),
            "PRODUCT_VIDEO_RENDER_BRIDGE_SYNC_FAILED",
            exc=exc,
            project_id=project_id,
            step_name="product_video_render_bridge",
        ) from exc
    if shots is None:
        raise _not_found()
    return shots


@router.post("/projects/{project_id}/prompts", response_model=models.ProductVideoPromptPackResponse)
async def generate_product_video_prompts(project_id: str, db: Session = Depends(get_db)):
    try:
        pack = product_video.generate_prompt_pack(project_id, db)
    except product_video.ProductVideoValidationError as exc:
        raise _error(
            400,
            str(exc),
            "PRODUCT_VIDEO_SHOTS_REQUIRED",
            exc=exc,
            project_id=project_id,
            step_name="product_video_prompts",
        ) from exc
    except product_video.ProductVideoRenderBridgeError as exc:
        raise _error(
            502,
            str(exc),
            "PRODUCT_VIDEO_RENDER_BRIDGE_SYNC_FAILED",
            exc=exc,
            project_id=project_id,
            step_name="product_video_render_bridge",
        ) from exc
    if pack is None:
        raise _not_found()
    return pack


@router.get("/projects/{project_id}/prompt-pack")
async def download_product_video_prompt_pack(project_id: str, db: Session = Depends(get_db)):
    result = product_video.get_prompt_pack_download(project_id, db)
    if result is None:
        raise _error(404, "Chưa có prompt pack cho project này.", "PRODUCT_VIDEO_PROMPT_NOT_FOUND")
    filename, content = result
    return Response(
        content=content,
        media_type="text/plain; charset=utf-8",
        headers={"Content-Disposition": safe_content_disposition("attachment", filename)},
    )
