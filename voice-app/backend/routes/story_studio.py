"""Story Studio endpoints for series image stories and video handoff."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import Response
from sqlalchemy.orm import Session

from .. import models
from ..database import get_db
from ..services import story_studio

router = APIRouter(prefix="/story-studio", tags=["story-studio"])

def _error(status_code: int, message: str, error_code: str) -> HTTPException:
    return HTTPException(status_code=status_code, detail={"message": message, "error_code": error_code})

def _story_error(exc: story_studio.StoryStudioError) -> HTTPException:
    return _error(422, str(exc), "STORY_STUDIO_INVALID_STATE")

@router.get("/series", response_model=list[models.VideoSeriesResponse])
async def list_story_studio_series(db: Session = Depends(get_db)):
    return story_studio.list_story_series(db)

@router.get("/series/{series_id}/episodes", response_model=list[models.StoryEpisodeResponse])
async def list_story_episodes(series_id: str, db: Session = Depends(get_db)):
    try:
        episodes = story_studio.list_episodes(series_id, db)
    except story_studio.StoryStudioError as exc:
        raise _story_error(exc) from exc
    if episodes is None:
        raise _error(404, "Không tìm thấy series.", "STORY_STUDIO_SERIES_NOT_FOUND")
    return episodes

@router.post("/series/{series_id}/episodes", response_model=models.StoryEpisodeResponse)
async def create_story_episode(
    series_id: str,
    data: models.StoryEpisodeCreate,
    db: Session = Depends(get_db),
):
    try:
        episode = story_studio.create_episode(series_id, data, db)
    except story_studio.StoryStudioError as exc:
        raise _story_error(exc) from exc
    if episode is None:
        raise _error(404, "Không tìm thấy series.", "STORY_STUDIO_SERIES_NOT_FOUND")
    return episode

@router.get("/episodes/{episode_id}", response_model=models.StoryEpisodeResponse)
async def get_story_episode(episode_id: str, db: Session = Depends(get_db)):
    episode = story_studio.get_episode(episode_id, db)
    if episode is None:
        raise _error(404, "Không tìm thấy Story Episode.", "STORY_STUDIO_EPISODE_NOT_FOUND")
    return episode

@router.put("/episodes/{episode_id}", response_model=models.StoryEpisodeResponse)
async def update_story_episode(
    episode_id: str,
    data: models.StoryEpisodeUpdate,
    db: Session = Depends(get_db),
):
    try:
        episode = story_studio.update_episode(episode_id, data, db)
    except story_studio.StoryStudioError as exc:
        raise _story_error(exc) from exc
    if episode is None:
        raise _error(404, "Không tìm thấy Story Episode.", "STORY_STUDIO_EPISODE_NOT_FOUND")
    return episode

@router.post("/episodes/{episode_id}/candidates", response_model=models.StoryEpisodeResponse)
async def generate_story_candidates(episode_id: str, db: Session = Depends(get_db)):
    try:
        episode = await run_in_threadpool(story_studio.generate_candidates, episode_id, db)
    except story_studio.StoryStudioError as exc:
        raise _story_error(exc) from exc
    if episode is None:
        raise _error(404, "Không tìm thấy Story Episode.", "STORY_STUDIO_EPISODE_NOT_FOUND")
    return episode

@router.post("/episodes/{episode_id}/candidates/score", response_model=models.StoryEpisodeResponse)
async def score_story_candidates(episode_id: str, db: Session = Depends(get_db)):
    try:
        episode = await run_in_threadpool(story_studio.score_candidates, episode_id, db)
    except story_studio.StoryStudioError as exc:
        raise _story_error(exc) from exc
    if episode is None:
        raise _error(404, "Không tìm thấy Story Episode.", "STORY_STUDIO_EPISODE_NOT_FOUND")
    return episode

@router.post("/episodes/{episode_id}/master-story", response_model=models.StoryEpisodeResponse)
async def select_master_story(
    episode_id: str,
    data: models.StoryCandidateSelectionRequest,
    db: Session = Depends(get_db),
):
    try:
        episode = story_studio.select_master_story(episode_id, data, db)
    except story_studio.StoryStudioError as exc:
        raise _story_error(exc) from exc
    if episode is None:
        raise _error(404, "Không tìm thấy Story Episode.", "STORY_STUDIO_EPISODE_NOT_FOUND")
    return episode

@router.post("/episodes/{episode_id}/master-story/synthesize", response_model=models.StoryEpisodeResponse)
async def synthesize_master_story(
    episode_id: str,
    data: models.StoryCandidateSynthesisRequest,
    db: Session = Depends(get_db),
):
    try:
        episode = await run_in_threadpool(story_studio.synthesize_master_story, episode_id, data, db)
    except story_studio.StoryStudioError as exc:
        raise _story_error(exc) from exc
    if episode is None:
        raise _error(404, "Không tìm thấy Story Episode.", "STORY_STUDIO_EPISODE_NOT_FOUND")
    return episode

@router.post("/episodes/{episode_id}/master-story/approval", response_model=models.StoryEpisodeResponse)
async def approve_master_story(
    episode_id: str,
    data: models.StoryApprovalRequest,
    db: Session = Depends(get_db),
):
    try:
        episode = story_studio.approve_master_story(episode_id, data, db)
    except story_studio.StoryStudioError as exc:
        raise _story_error(exc) from exc
    if episode is None:
        raise _error(404, "Không tìm thấy Story Episode.", "STORY_STUDIO_EPISODE_NOT_FOUND")
    return episode

@router.post("/episodes/{episode_id}/image-adaptation", response_model=models.StoryAdaptationResponse)
async def create_image_adaptation(episode_id: str, db: Session = Depends(get_db)):
    try:
        adaptation = story_studio.create_image_adaptation(episode_id, db)
    except story_studio.StoryStudioError as exc:
        raise _story_error(exc) from exc
    if adaptation is None:
        raise _error(404, "Không tìm thấy Story Episode.", "STORY_STUDIO_EPISODE_NOT_FOUND")
    return adaptation

@router.put("/episodes/{episode_id}/image-adaptation/panel", response_model=models.StoryAdaptationResponse)
async def update_image_panel_prompt(
    episode_id: str,
    data: models.StoryPanelPromptUpdateRequest,
    db: Session = Depends(get_db),
):
    try:
        return story_studio.update_panel_prompt(episode_id, data, db)
    except story_studio.StoryStudioError as exc:
        raise _story_error(exc) from exc

@router.post("/episodes/{episode_id}/image-adaptation/panel/repair", response_model=models.StoryAdaptationResponse)
async def repair_image_panel_prompt(
    episode_id: str,
    data: models.StoryPromptRepairRequest,
    db: Session = Depends(get_db),
):
    try:
        return story_studio.repair_panel_prompt(episode_id, data, db)
    except story_studio.StoryStudioError as exc:
        raise _story_error(exc) from exc

@router.post("/episodes/{episode_id}/image-adaptation/prompts/approval", response_model=models.StoryAdaptationResponse)
async def approve_image_prompts(
    episode_id: str,
    data: models.StoryPanelPromptApprovalRequest,
    db: Session = Depends(get_db),
):
    try:
        return story_studio.approve_image_prompts(episode_id, data, db)
    except story_studio.StoryStudioError as exc:
        raise _story_error(exc) from exc

@router.post("/episodes/{episode_id}/image-adaptation/render", response_model=models.StoryAdaptationResponse)
async def request_image_render(
    episode_id: str,
    data: models.StoryImageRenderRequest,
    db: Session = Depends(get_db),
):
    try:
        return story_studio.request_image_render(episode_id, data, db)
    except story_studio.StoryStudioError as exc:
        raise _story_error(exc) from exc

@router.put(
    "/episodes/{episode_id}/image-adaptation/render/jobs/{render_job_id}",
    response_model=models.StoryAdaptationResponse,
)
async def update_image_render_job(
    episode_id: str,
    render_job_id: str,
    data: models.StoryImageRenderJobUpdateRequest,
    db: Session = Depends(get_db),
):
    try:
        return story_studio.update_image_render_job(episode_id, render_job_id, data, db)
    except story_studio.StoryStudioError as exc:
        raise _story_error(exc) from exc

@router.get("/episodes/{episode_id}/image-adaptation/prompts/export")
async def export_image_prompts(episode_id: str, db: Session = Depends(get_db)):
    try:
        text = story_studio.export_image_prompts(episode_id, db)
    except story_studio.StoryStudioError as exc:
        raise _story_error(exc) from exc
    return Response(content=text, media_type="text/plain; charset=utf-8")

@router.post("/episodes/{episode_id}/video-adaptation", response_model=models.StoryAdaptationResponse)
async def create_video_adaptation(
    episode_id: str,
    data: models.StoryVideoHandoffRequest,
    db: Session = Depends(get_db),
):
    try:
        adaptation = story_studio.create_video_adaptation(episode_id, data, db)
    except story_studio.StoryStudioError as exc:
        raise _story_error(exc) from exc
    if adaptation is None:
        raise _error(404, "Không tìm thấy Story Episode.", "STORY_STUDIO_EPISODE_NOT_FOUND")
    return adaptation

@router.post("/episodes/{episode_id}/suggestions", response_model=models.StorySuggestionResponse)
async def suggest_story_updates(episode_id: str, db: Session = Depends(get_db)):
    suggestion = story_studio.suggest_updates(episode_id, db)
    if suggestion is None:
        raise _error(404, "Không tìm thấy Story Episode.", "STORY_STUDIO_EPISODE_NOT_FOUND")
    return suggestion

@router.post("/episodes/{episode_id}/suggestions/approval", response_model=models.StorySuggestionResponse)
async def approve_story_updates(
    episode_id: str,
    data: models.StorySuggestionApprovalRequest,
    db: Session = Depends(get_db),
):
    try:
        suggestion = story_studio.approve_suggested_updates(episode_id, data, db)
    except story_studio.StoryStudioError as exc:
        raise _story_error(exc) from exc
    if suggestion is None:
        raise _error(404, "Không tìm thấy Story Episode.", "STORY_STUDIO_EPISODE_NOT_FOUND")
    return suggestion
