"""Vietnamese manual Veo 3 handoff facade for News Video projects."""

from __future__ import annotations

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from fastapi.responses import PlainTextResponse
from sqlalchemy.orm import Session

from .. import models
from . import video_errors
from ..database import VideoProject as DBVideoProject, VideoShot as DBVideoShot, NewsVideoWorkflow as DBNewsWorkflow, get_db
from ..services import video_phase2, video_projects, video_rendering, video_speech

router = APIRouter(prefix="/news-video", tags=["news-video"], route_class=video_errors.AIVideoRoute)


def _project_or_404(project_id: str, db: Session):
    project = video_projects.get_project(project_id, db)
    if project is None:
        raise HTTPException(status_code=404, detail="Không tìm thấy dự án Video tin tức.")
    return project


@router.get("/projects", response_model=list[models.VideoProjectResponse])
def list_news_projects(db: Session = Depends(get_db)):
    # The workflow discriminator is intentionally kept in the shared project table.
    rows = {row.project_id for row in db.query(DBNewsWorkflow).all()}
    return [item for item in video_projects.list_projects(db) if item.id in rows]


@router.post("/projects", response_model=models.VideoProjectResponse)
def create_news_project(data: models.VideoProjectCreate, db: Session = Depends(get_db)):
    payload = data.model_copy(update={
        "language": "vi",
        "target_language": "vi",
        "aspect_ratio": "9:16",
        "phase": "phase2",
        "speech_source": data.speech_source or "voicebox_khong_context",
        "prompt_segment_duration_seconds": data.prompt_segment_duration_seconds or 8,
    })
    try:
        project = video_projects.create_project(payload, db)
        db.add(DBNewsWorkflow(project_id=project.id, visual_format="9:16", default_speech_source=payload.speech_source))
        db.commit()
        return project
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.get("/projects/{project_id}", response_model=models.VideoProjectDetailResponse)
def get_news_project(project_id: str, db: Session = Depends(get_db)):
    return _project_or_404(project_id, db)


@router.patch("/projects/{project_id}", response_model=models.VideoProjectResponse)
def update_news_project(project_id: str, data: models.VideoProjectUpdate, db: Session = Depends(get_db)):
    _project_or_404(project_id, db)
    try:
        if data.speech_mode is not None:
            data = data.model_copy(update={"speech_source": data.speech_mode})
        result = video_projects.update_project(project_id, data, db)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return result


@router.post("/projects/{project_id}/plan", response_model=list[models.VideoShotResponse])
def plan_news_project(project_id: str, db: Session = Depends(get_db)):
    _project_or_404(project_id, db)
    result = video_phase2.generate_shots(project_id, db)
    return result or []


@router.get("/projects/{project_id}/shots", response_model=list[models.VideoShotResponse])
def list_news_shots(project_id: str, db: Session = Depends(get_db)):
    project = db.query(DBVideoProject).filter(DBVideoProject.id == project_id).first()
    if project is None:
        raise HTTPException(status_code=404, detail="Không tìm thấy dự án Video tin tức.")
    shots = db.query(DBVideoShot).filter(DBVideoShot.project_id == project_id).order_by(DBVideoShot.shot_order.asc()).all()
    return [models.VideoShotResponse.model_validate(shot) for shot in shots]

@router.patch("/projects/{project_id}/shots/{shot_id}", response_model=models.VideoShotResponse)
def update_news_shot(project_id: str, shot_id: str, data: models.VideoShotUpdate, db: Session = Depends(get_db)):
    project = _project_or_404(project_id, db)
    if data.speech_mode is not None:
        data = data.model_copy(update={"speech_source_override": data.speech_mode})
    result = video_phase2.update_shot(project_id, shot_id, data, db)
    if result is None:
        raise HTTPException(status_code=404, detail="Không tìm thấy shot.")
    return result


@router.post("/projects/{project_id}/prompts")
def generate_news_prompts(project_id: str, db: Session = Depends(get_db)):
    _project_or_404(project_id, db)
    return video_phase2.generate_video_prompt_pack(project_id, db)


@router.get("/projects/{project_id}/shots/{shot_id}/prompt")
def get_news_shot_prompt(project_id: str, shot_id: str, db: Session = Depends(get_db)):
    _project_or_404(project_id, db)
    content = video_phase2.get_video_prompt_content(project_id, shot_id, db)
    if content is None:
        raise HTTPException(status_code=404, detail="Không tìm thấy prompt Veo 3 cho shot này.")
    return content

@router.get("/projects/{project_id}/shots/{shot_id}/speech-review")
def review_news_shot_speech(project_id: str, shot_id: str, db: Session = Depends(get_db)):
    project = _project_or_404(project_id, db)
    shot = db.query(DBVideoShot).filter(DBVideoShot.project_id == project_id, DBVideoShot.id == shot_id).first()
    if shot is None:
        raise HTTPException(status_code=404, detail="Không tìm thấy shot.")
    mode = video_speech.speech_mode_for(project, shot)
    return {"shot_id": shot_id, "speech_mode": mode, "effective_speech_source": video_speech.effective_speech_source(project, shot), "cues": video_speech.speech_cues_for_shot(shot, project), "text": video_speech.spoken_text_for_shot(shot, project)}

@router.get("/projects/{project_id}/speech-audit")
def audit_news_speech(project_id: str, db: Session = Depends(get_db)):
    project = _project_or_404(project_id, db)
    issues = []
    for shot in db.query(DBVideoShot).filter(DBVideoShot.project_id == project_id).order_by(DBVideoShot.shot_order.asc()).all():
        expected = video_speech.spoken_text_for_shot(shot, project)
        prompt = video_phase2.get_video_prompt_content(project_id, shot.id, db)
        if expected and (prompt is None or expected.casefold() not in prompt.content.casefold()):
            issues.append({"shot_id": shot.id, "shot_order": shot.shot_order, "reason": "Prompt chưa chứa đúng lời thoại.", "expected_text": expected})
    return {"project_id": project_id, "issues": issues, "count": len(issues)}

@router.get("/projects/{project_id}/prompt-pack", response_class=PlainTextResponse)
def download_news_prompt_pack(project_id: str, db: Session = Depends(get_db)):
    _project_or_404(project_id, db)
    result = video_phase2.get_video_prompt_pack_download(project_id, db)
    if result is None:
        raise HTTPException(status_code=404, detail="Chưa có prompt để tải.")
    filename, content = result
    return PlainTextResponse(content, headers={"Content-Disposition": f'attachment; filename="{filename}"'})

@router.get("/projects/{project_id}/shots/{shot_id}/prompt-download", response_class=PlainTextResponse)
def download_news_shot_prompt(project_id: str, shot_id: str, db: Session = Depends(get_db)):
    _project_or_404(project_id, db)
    result = video_phase2.get_video_prompt_download(project_id, shot_id, db)
    if result is None:
        raise HTTPException(status_code=404, detail="Chưa có prompt cho shot này.")
    filename, content = result
    return PlainTextResponse(content, headers={"Content-Disposition": f'attachment; filename="{filename}"'})


@router.post("/projects/{project_id}/shots/{shot_id}/clip", response_model=models.VideoShotClipResponse)
async def upload_news_shot_clip(
    project_id: str,
    shot_id: str,
    file: UploadFile = File(...),
    provider: str | None = Form(None),
    db: Session = Depends(get_db),
):
    _project_or_404(project_id, db)
    try:
        clip = video_rendering.upload_shot_clip(
            project_id, shot_id, filename=file.filename or "clip.mp4",
            content_type=file.content_type, data=await file.read(), provider=provider, db=db,
        )
    except video_rendering.VideoRenderError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    if clip is None:
        raise HTTPException(status_code=404, detail="Không tìm thấy shot video.")
    return clip

@router.get("/projects/{project_id}/shots/{shot_id}/clip", response_model=models.VideoShotClipResponse | None)
def get_news_shot_clip(project_id: str, shot_id: str, db: Session = Depends(get_db)):
    _project_or_404(project_id, db)
    return video_rendering.get_active_clip(project_id, shot_id, db)

@router.delete("/projects/{project_id}/shots/{shot_id}/clip")
def delete_news_shot_clip(project_id: str, shot_id: str, db: Session = Depends(get_db)):
    _project_or_404(project_id, db)
    deleted = video_rendering.delete_shot_clip(project_id, shot_id, db)
    if not deleted:
        raise HTTPException(status_code=404, detail="Không tìm thấy clip của shot.")
    return {"deleted": True}

@router.get("/projects/{project_id}/render/readiness")
def news_render_readiness(project_id: str, db: Session = Depends(get_db)):
    _project_or_404(project_id, db)
    return video_rendering.get_render_readiness(project_id, db, video_rendering.render_settings_for_project(project_id, db))

@router.post("/projects/{project_id}/render/jobs", response_model=models.VideoRenderJobResponse)
async def create_news_render_job(project_id: str, data: models.VideoRenderJobCreateRequest | None = None, db: Session = Depends(get_db)):
    _project_or_404(project_id, db)
    try:
        return await video_rendering.create_render_job(project_id, data or models.VideoRenderJobCreateRequest(), db)
    except video_rendering.VideoRenderError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
