"""Research Workspace endpoints, isolated from existing creation routes."""

from __future__ import annotations

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile
from fastapi.responses import PlainTextResponse
from sqlalchemy.orm import Session
from starlette.concurrency import run_in_threadpool

from .. import config, models
from ..database import get_db
from ..database import session as database_session
from ..services import research, research_source_security

def require_research_feature() -> None:
    if not config.is_feature_enabled("research", default=True):
        raise HTTPException(status_code=404, detail={"message": "Research Workspace đang tắt.", "error_code": "RESEARCH_FEATURE_DISABLED"})


router = APIRouter(prefix="/research", tags=["research"], dependencies=[Depends(require_research_feature)])


def _handle(exc: research.ResearchError) -> HTTPException:
    return HTTPException(status_code=exc.status_code, detail={"message": str(exc), "error_code": exc.error_code})


@router.get("/projects", response_model=list[models.ResearchProjectResponse])
async def list_research_projects(status: str | None = Query(None), db: Session = Depends(get_db)):
    return research.list_projects(db, status=status)


@router.post("/projects", response_model=models.ResearchProjectResponse)
async def create_research_project(data: models.ResearchProjectCreate, db: Session = Depends(get_db)):
    return research.create_project(data, db)


@router.get("/projects/{project_id}", response_model=models.ResearchProjectResponse)
async def get_research_project(project_id: str, db: Session = Depends(get_db)):
    row = research.get_project(project_id, db)
    if row is None:
        raise HTTPException(status_code=404, detail={"message": "Không tìm thấy Research Project.", "error_code": "RESEARCH_PROJECT_NOT_FOUND"})
    return research._project_response(row)


@router.patch("/projects/{project_id}", response_model=models.ResearchProjectResponse)
async def update_research_project(project_id: str, data: models.ResearchProjectUpdate, db: Session = Depends(get_db)):
    row = research.update_project(project_id, data, db)
    if row is None:
        raise HTTPException(status_code=404, detail={"message": "Không tìm thấy Research Project.", "error_code": "RESEARCH_PROJECT_NOT_FOUND"})
    return row


@router.post("/context/compile", response_model=models.ResearchContextResponse)
async def compile_research_context(data: models.ResearchContextRequest, db: Session = Depends(get_db)):
    return research.compile_context(data, db)


@router.get("/projects/{project_id}/memory", response_class=PlainTextResponse)
async def get_research_memory(project_id: str, db: Session = Depends(get_db)):
    row = research.get_project(project_id, db)
    if row is None:
        raise HTTPException(status_code=404, detail="Không tìm thấy Research Project.")
    path = config.resolve_storage_path(row.memory_path)
    return path.read_text(encoding="utf-8") if path and path.exists() else ""


@router.post("/projects/{project_id}/sources", response_model=models.ResearchSourceResponse)
async def create_research_source(project_id: str, data: models.ResearchSourceTextCreate, db: Session = Depends(get_db)):
    try:
        source = research.add_text_source(project_id, data, db)
        if data.source_type in {"docs_url", "github_repo"} and data.input_url and not data.content:
            worker_db = database_session.SessionLocal()
            try:
                attached = await run_in_threadpool(
                    research.start_source_adapter,
                    project_id,
                    source.id,
                    worker_db,
                    raw_url=data.input_url,
                )
                return attached or source
            finally:
                worker_db.close()
        if data.source_type in {"video_url", "story_url"}:
            attached = research.start_source_adapter(
                project_id,
                source.id,
                db,
                raw_url=data.input_url,
            )
            return attached or source
        return source
    except research.ResearchError as exc:
        raise _handle(exc) from exc


@router.post("/projects/{project_id}/sources/series-memory", response_model=models.ResearchSourceResponse)
async def create_research_series_memory_source(
    project_id: str,
    data: models.ResearchSeriesMemorySourceCreate,
    db: Session = Depends(get_db),
):
    try:
        return research.add_series_memory_source(project_id, data, db)
    except research.ResearchError as exc:
        raise _handle(exc) from exc


@router.post("/projects/{project_id}/sources/upload", response_model=models.ResearchSourceResponse)
async def upload_research_source(
    project_id: str,
    source_type: str = Form(...),
    title: str | None = Form(None),
    repository_url: str | None = Form(None),
    repository_ref: str | None = Form(None),
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
):
    try:
        limit = (
            research_source_security.MAX_RESEARCH_IMAGE_BYTES
            if source_type in {"image_upload", "screenshot_upload"}
            else research_source_security.MAX_RESEARCH_VIDEO_BYTES
        )
        payload = await file.read(limit + 1)
        source = research.add_upload_source(
            project_id,
            source_type,
            title,
            file.filename or "source",
            payload,
            file.content_type,
            db,
            repository_url=repository_url,
            repository_ref=repository_ref,
        )
        attached = research.start_source_adapter(project_id, source.id, db)
        return attached or source
    except research.ResearchError as exc:
        raise _handle(exc) from exc


@router.get("/projects/{project_id}/sources", response_model=list[models.ResearchSourceResponse])
async def list_research_sources(project_id: str, db: Session = Depends(get_db)):
    return research.list_sources(project_id, db)


@router.get("/projects/{project_id}/sources/{source_id}", response_model=models.ResearchSourceResponse)
async def get_research_source(project_id: str, source_id: str, db: Session = Depends(get_db)):
    row = research.get_source(project_id, source_id, db)
    if row is None:
        raise HTTPException(status_code=404, detail="Không tìm thấy nguồn nghiên cứu.")
    return row


@router.post("/projects/{project_id}/sources/{source_id}/retry", response_model=models.ResearchSourceResponse)
async def retry_research_source(
    project_id: str,
    source_id: str,
    data: models.ResearchSourceRetryRequest,
    db: Session = Depends(get_db),
):
    try:
        existing = research.get_source(project_id, source_id, db)
        if existing is not None and existing.source_type == "docs_url":
            worker_db = database_session.SessionLocal()
            try:
                row = await run_in_threadpool(research.retry_source, project_id, source_id, data, worker_db)
            finally:
                worker_db.close()
        else:
            row = research.retry_source(project_id, source_id, data, db)
    except research.ResearchError as exc:
        raise _handle(exc) from exc
    if row is None:
        raise HTTPException(status_code=404, detail="Không tìm thấy nguồn nghiên cứu.")
    return row


@router.post("/projects/{project_id}/sources/{source_id}/approve", response_model=models.ResearchIdeaResponse)
async def approve_research_source(
    project_id: str,
    source_id: str,
    data: models.ResearchSourceApproveRequest,
    db: Session = Depends(get_db),
):
    try:
        row = research.approve_source(project_id, source_id, data, db)
    except research.ResearchError as exc:
        raise _handle(exc) from exc
    if row is None:
        raise HTTPException(status_code=404, detail="Không tìm thấy nguồn nghiên cứu.")
    return row


@router.post("/projects/{project_id}/runs", response_model=models.ResearchRunResponse)
async def create_research_run(project_id: str, data: models.ResearchRunCreate, db: Session = Depends(get_db)):
    del db
    worker_db = database_session.SessionLocal()
    try:
        return await run_in_threadpool(research.create_run, project_id, data, worker_db)
    except research.ResearchError as exc:
        raise _handle(exc) from exc
    finally:
        worker_db.close()


@router.get("/projects/{project_id}/runs", response_model=list[models.ResearchRunResponse])
async def list_research_runs(project_id: str, db: Session = Depends(get_db)):
    return research.list_runs(project_id, db)


@router.get("/projects/{project_id}/runs/{run_id}", response_model=models.ResearchRunResponse)
async def get_research_run(project_id: str, run_id: str, db: Session = Depends(get_db)):
    row = research.get_run(project_id, run_id, db)
    if row is None:
        raise HTTPException(status_code=404, detail="Không tìm thấy lần chạy nghiên cứu.")
    return row


@router.post("/projects/{project_id}/runs/{run_id}/retry", response_model=models.ResearchRunResponse)
async def retry_research_run(
    project_id: str,
    run_id: str,
    data: models.ResearchRunRetryRequest,
    db: Session = Depends(get_db),
):
    del db
    worker_db = database_session.SessionLocal()
    try:
        row = await run_in_threadpool(research.retry_run, project_id, run_id, data, worker_db)
    except research.ResearchError as exc:
        raise _handle(exc) from exc
    finally:
        worker_db.close()
    if row is None:
        raise HTTPException(status_code=404, detail="Không tìm thấy lần chạy nghiên cứu.")
    return row


@router.post("/projects/{project_id}/runs/{run_id}/merge", response_model=models.ResearchRunResponse)
async def merge_research_run(
    project_id: str,
    run_id: str,
    data: models.ResearchRunMergeRequest,
    db: Session = Depends(get_db),
):
    row = research.merge_run(project_id, run_id, data, db)
    if row is None:
        raise HTTPException(status_code=404, detail="Không tìm thấy lần chạy nghiên cứu.")
    return row


@router.post("/projects/{project_id}/runs/{run_id}/cancel", response_model=models.ResearchRunResponse)
async def cancel_research_run(project_id: str, run_id: str, db: Session = Depends(get_db)):
    row = research.cancel_run(project_id, run_id, db)
    if row is None:
        raise HTTPException(status_code=404, detail="Không tìm thấy lần chạy nghiên cứu.")
    return row


@router.post("/projects/{project_id}/ideas", response_model=models.ResearchIdeaResponse)
async def create_research_idea(project_id: str, data: models.ResearchIdeaCreate, db: Session = Depends(get_db)):
    try:
        return research.create_idea(project_id, data, db)
    except research.ResearchError as exc:
        raise _handle(exc) from exc


@router.get("/projects/{project_id}/ideas", response_model=list[models.ResearchIdeaResponse])
async def list_research_ideas(project_id: str, db: Session = Depends(get_db)):
    return research.list_ideas(project_id, db)


@router.post("/projects/{project_id}/ideas/{idea_id}/status", response_model=models.ResearchIdeaResponse)
async def set_research_idea_status(project_id: str, idea_id: str, data: models.ResearchStatusRequest, db: Session = Depends(get_db)):
    try:
        row = research.update_idea_status(project_id, idea_id, data.status, db)
    except research.ResearchError as exc:
        raise _handle(exc) from exc
    if row is None:
        raise HTTPException(status_code=404, detail="Không tìm thấy ý tưởng.")
    return row


@router.post("/projects/{project_id}/scripts", response_model=models.ResearchScriptResponse)
async def create_research_script(project_id: str, data: models.ResearchScriptCreate, db: Session = Depends(get_db)):
    try:
        return research.create_script(project_id, data, db)
    except research.ResearchError as exc:
        raise _handle(exc) from exc


@router.get("/projects/{project_id}/scripts", response_model=list[models.ResearchScriptResponse])
async def list_research_scripts(project_id: str, db: Session = Depends(get_db)):
    return research.list_scripts(project_id, db)


@router.post("/projects/{project_id}/scripts/{script_id}/status", response_model=models.ResearchScriptResponse)
async def set_research_script_status(project_id: str, script_id: str, data: models.ResearchStatusRequest, db: Session = Depends(get_db)):
    try:
        row = research.update_script_status(project_id, script_id, data.status, db)
    except research.ResearchError as exc:
        raise _handle(exc) from exc
    if row is None:
        raise HTTPException(status_code=404, detail="Không tìm thấy kịch bản.")
    return row


@router.post("/projects/{project_id}/scores", response_model=models.ResearchScoreResponse)
async def score_research_content(project_id: str, data: models.ResearchScoreRequest, db: Session = Depends(get_db)):
    del db
    worker_db = database_session.SessionLocal()
    try:
        return await run_in_threadpool(research.score_target, project_id, data, worker_db)
    except research.ResearchError as exc:
        raise _handle(exc) from exc
    finally:
        worker_db.close()


@router.get("/projects/{project_id}/scores", response_model=list[models.ResearchScoreResponse])
async def list_research_scores(project_id: str, db: Session = Depends(get_db)):
    return research.list_scores(project_id, db)


@router.get("/projects/{project_id}/recommendation", response_model=models.ResearchRecommendationResponse)
async def get_research_recommendation(project_id: str, db: Session = Depends(get_db)):
    try:
        return research.get_recommendation(project_id, db)
    except research.ResearchError as exc:
        raise _handle(exc) from exc


@router.post("/projects/{project_id}/scores/{score_id}/override", response_model=models.ResearchScoreResponse)
async def override_research_score(project_id: str, score_id: str, data: models.ResearchScoreOverrideRequest, db: Session = Depends(get_db)):
    try:
        row = research.override_score(project_id, score_id, data, db)
    except research.ResearchError as exc:
        raise _handle(exc) from exc
    if row is None:
        raise HTTPException(status_code=404, detail="Không tìm thấy bản chấm điểm.")
    return row


@router.post("/projects/{project_id}/chat", response_model=models.ResearchChatResponse)
async def research_chat(project_id: str, data: models.ResearchChatRequest, db: Session = Depends(get_db)):
    del db
    worker_db = database_session.SessionLocal()
    try:
        return await run_in_threadpool(research.chat, project_id, data, worker_db)
    except research.ResearchError as exc:
        raise _handle(exc) from exc
    finally:
        worker_db.close()


@router.get("/projects/{project_id}/chat/threads", response_model=list[models.ResearchChatThreadResponse])
async def list_research_chat_threads(project_id: str, db: Session = Depends(get_db)):
    return research.list_chat_threads(project_id, db)


@router.post(
    "/projects/{project_id}/chat/messages/{message_id}/approve",
    response_model=models.ResearchChatPromotionResponse,
)
async def approve_research_chat_message(
    project_id: str,
    message_id: str,
    data: models.ResearchChatApprovalRequest,
    db: Session = Depends(get_db),
):
    try:
        row = research.promote_chat_message(project_id, message_id, data, db)
    except research.ResearchError as exc:
        raise _handle(exc) from exc
    if row is None:
        raise HTTPException(status_code=404, detail="Không tìm thấy draft chat.")
    return row


@router.post(
    "/projects/{project_id}/chat/messages/{message_id}/status",
    response_model=models.ResearchChatMessageResponse,
)
async def set_research_chat_message_status(
    project_id: str,
    message_id: str,
    data: models.ResearchChatMessageStatusRequest,
    db: Session = Depends(get_db),
):
    try:
        row = research.set_chat_message_status(project_id, message_id, data.status, db)
    except research.ResearchError as exc:
        raise _handle(exc) from exc
    if row is None:
        raise HTTPException(status_code=404, detail="Không tìm thấy draft chat.")
    return row


@router.post("/projects/{project_id}/handoffs/ai-video", response_model=models.ResearchHandoffResponse)
async def handoff_research_to_ai_video(project_id: str, data: models.ResearchHandoffCreate, db: Session = Depends(get_db)):
    try:
        return research.handoff(project_id, data, db)
    except research.ResearchError as exc:
        raise _handle(exc) from exc
