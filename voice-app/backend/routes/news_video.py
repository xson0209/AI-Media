"""Vietnamese manual Veo 3 handoff facade for News Video projects."""

from __future__ import annotations

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from fastapi.responses import PlainTextResponse
from urllib.parse import urlparse
from sqlalchemy.orm import Session

from .. import models
from ..services import video_errors
from ..database import VideoProject as DBVideoProject, VideoShot as DBVideoShot, NewsVideoWorkflow as DBNewsWorkflow, get_db
from ..services import video_phase2, video_projects, video_rendering, video_speech, video_voice, video_publishing_metadata, video_auto_runs

router = APIRouter(prefix="/news-video", tags=["news-video"], route_class=video_errors.AIVideoRoute)

def _sanitize_source_note(value: str | None) -> str | None:
    note = (value or "").strip()
    if not note:
        return None
    parsed = urlparse(note)
    if parsed.scheme and parsed.scheme.lower() not in {"http", "https"}:
        raise HTTPException(status_code=422, detail="URL nguồn chỉ được dùng http hoặc https.")
    return note[:10000]

def _sanitize_editorial_topic(value: str) -> str:
    """Keep article text while isolating common prompt-injection directives."""
    blocked = ("ignore previous instructions", "system message:", "developer message:")
    lines = [line for line in (value or "").splitlines() if not any(token in line.casefold() for token in blocked)]
    return "\n".join(lines).strip()[:4000]


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
    source_note = _sanitize_source_note(data.source_note)
    safe_topic = _sanitize_editorial_topic(data.topic)
    if not safe_topic:
        raise HTTPException(status_code=422, detail="Cần nhập nội dung bài tin sau khi loại bỏ chỉ dẫn không liên quan.")
    payload = data.model_copy(update={
        "topic": safe_topic,
        "language": "vi",
        "target_language": "vi",
        "aspect_ratio": data.aspect_ratio or "9:16",
        "phase": "phase2",
        "speech_source": data.speech_source or "voicebox_khong_context",
        "prompt_segment_duration_seconds": data.prompt_segment_duration_seconds or 8,
        "prompt_segment_count": data.prompt_segment_count or 1,
        "micro_scenes_per_prompt": data.micro_scenes_per_prompt or 1,
    })
    try:
        project = video_projects.create_project(payload, db)
        db.add(DBNewsWorkflow(project_id=project.id, visual_format=payload.aspect_ratio, source_note=source_note, default_speech_source=payload.speech_source))
        db.commit()
        return project
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.get("/projects/{project_id}", response_model=models.VideoProjectDetailResponse)
def get_news_project(project_id: str, db: Session = Depends(get_db)):
    return _project_or_404(project_id, db)

@router.get("/projects/{project_id}/workflow")
def get_news_workflow(project_id: str, db: Session = Depends(get_db)):
    _project_or_404(project_id, db)
    row = db.query(DBNewsWorkflow).filter(DBNewsWorkflow.project_id == project_id).first()
    if row is None:
        raise HTTPException(status_code=404, detail="Không tìm thấy cấu hình workflow tin tức.")
    return {"project_id": row.project_id, "visual_format": row.visual_format, "source_note": row.source_note, "default_speech_source": row.default_speech_source}

@router.patch("/projects/{project_id}/workflow")
def update_news_workflow(project_id: str, visual_format: str | None = None, source_note: str | None = None, default_speech_source: str | None = None, db: Session = Depends(get_db)):
    _project_or_404(project_id, db)
    row = db.query(DBNewsWorkflow).filter(DBNewsWorkflow.project_id == project_id).first()
    if row is None:
        raise HTTPException(status_code=404, detail="Không tìm thấy cấu hình workflow tin tức.")
    if visual_format is not None:
        if visual_format not in {"9:16", "16:9", "1:1"}:
            raise HTTPException(status_code=422, detail="visual_format không hợp lệ.")
        row.visual_format = visual_format
    if source_note is not None:
        row.source_note = _sanitize_source_note(source_note)
    if default_speech_source is not None:
        if default_speech_source not in video_speech.NEWS_SPEECH_MODES:
            raise HTTPException(status_code=422, detail="Nguồn lời không hợp lệ.")
        row.default_speech_source = default_speech_source
    db.commit(); db.refresh(row)
    return {"project_id": row.project_id, "visual_format": row.visual_format, "source_note": row.source_note, "default_speech_source": row.default_speech_source}


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
    shot = db.query(DBVideoShot).filter(DBVideoShot.id == shot_id, DBVideoShot.project_id == project_id).first()
    if shot is None:
        raise HTTPException(status_code=404, detail="Không tìm thấy shot.")
    gate = video_phase2.speech_prompt_quality(_project_or_404(project_id, db), shot, content.content)
    if gate.get("needs_review"):
        raise HTTPException(status_code=409, detail=gate.get("reason_vi") or "Prompt cần review thoại.")
    return content

@router.get("/projects/{project_id}/shots/{shot_id}/speech-review")
def review_news_shot_speech(project_id: str, shot_id: str, db: Session = Depends(get_db)):
    project = _project_or_404(project_id, db)
    shot = db.query(DBVideoShot).filter(DBVideoShot.project_id == project_id, DBVideoShot.id == shot_id).first()
    if shot is None:
        raise HTTPException(status_code=404, detail="Không tìm thấy shot.")
    mode = video_speech.speech_mode_for(project, shot)
    return {"shot_id": shot_id, "speech_mode": mode, "effective_speech_source": video_speech.effective_speech_source(project, shot), "audio_policy": video_speech.audio_policy_for(project, shot), "cues": video_speech.speech_cues_for_shot(shot, project), "text": video_speech.spoken_text_for_shot(shot, project)}

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

@router.post("/projects/{project_id}/shots/{shot_id}/voice", response_model=models.VideoShotVoiceStatusResponse)
async def create_news_shot_voice(project_id: str, shot_id: str, data: models.VideoSceneNarrationRequest, db: Session = Depends(get_db)):
    _project_or_404(project_id, db)
    try:
        result = await video_voice.create_shot_narration(project_id, shot_id, data, db)
    except video_voice.VideoVoiceError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    if result is None:
        raise HTTPException(status_code=404, detail="Không tìm thấy shot.")
    return result

@router.get("/projects/{project_id}/shots/{shot_id}/voice/status", response_model=models.VideoShotVoiceStatusResponse)
def news_shot_voice_status(project_id: str, shot_id: str, db: Session = Depends(get_db)):
    _project_or_404(project_id, db)
    result = video_voice.sync_shot_voice_status(project_id, shot_id, db)
    if result is None:
        raise HTTPException(status_code=404, detail="Không tìm thấy shot.")
    return result

@router.get("/projects/{project_id}/publishing-metadata", response_model=models.VideoPublishingMetadataResponse)
def news_publishing_metadata(project_id: str, db: Session = Depends(get_db)):
    _project_or_404(project_id, db)
    result = video_publishing_metadata.get_publishing_metadata(project_id, db)
    if result is None:
        raise HTTPException(status_code=404, detail="Chưa có dữ liệu xuất bản.")
    return result

@router.post("/projects/{project_id}/publishing-metadata", response_model=models.VideoPublishingMetadataResponse)
async def generate_news_publishing_metadata(project_id: str, data: models.VideoPublishingMetadataGenerateRequest | None = None, db: Session = Depends(get_db)):
    _project_or_404(project_id, db)
    try:
        result = video_publishing_metadata.generate_publishing_metadata(project_id, data or models.VideoPublishingMetadataGenerateRequest(), db)
    except Exception as exc:
        raise HTTPException(status_code=400, detail="Không tạo được metadata xuất bản.") from exc
    return result

@router.post("/projects/{project_id}/auto-runs", response_model=models.VideoAutoRunResponse)
async def start_news_auto_run(project_id: str, data: models.VideoAutoRunStartRequest | None = None, db: Session = Depends(get_db)):
    _project_or_404(project_id, db)
    request = data or models.VideoAutoRunStartRequest(material_target=video_auto_runs.MATERIAL_TARGET_PROMPTS_ONLY)
    try:
        return await video_auto_runs.start_auto_run(project_id, request, db)
    except video_auto_runs.VideoAutoRunError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

@router.get("/projects/{project_id}/auto-runs/latest", response_model=models.VideoAutoRunResponse | None)
def latest_news_auto_run(project_id: str, db: Session = Depends(get_db)):
    _project_or_404(project_id, db)
    return video_auto_runs.get_latest_auto_run(project_id, db)
