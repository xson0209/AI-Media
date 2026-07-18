"""AI Video Assistant endpoints."""

from __future__ import annotations

import mimetypes

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile
from fastapi.responses import FileResponse, Response
from sqlalchemy.orm import Session

from .. import models
from ..database import VideoProject as DBVideoProject, VideoShot as DBVideoShot, get_db
from ..features.ai_video import (
    auto_runs as video_auto_runs,
    projects as video_projects,
    render as video_rendering,
    subtitles as video_subtitles,
)
from ..services import (
    ai_planning,
    series_references,
    series_brain,
    settings as settings_service,
    video_assets,
    video_clip_generation,
    video_debug,
    video_errors,
    video_packages,
    video_phase2,
    video_planning,
    video_planning_pool,
    video_publishing_metadata,
    video_provider_project_bindings,
    video_provider_sessions,
    video_project_memory,
    video_quality,
    video_series_memory,
    video_voice,
)
from ..utils.http import safe_content_disposition

router = APIRouter(prefix="/ai-video", tags=["ai-video"], route_class=video_errors.AIVideoRoute)


def _error(status_code: int, message: str, error_code: str, **context) -> HTTPException:
    return video_errors.api_error(status_code, message, error_code, **context)


def _planning_error_message(exc: ai_planning.AIPlanningError) -> str:
    if exc.error_code == "CODEX_EXEC_TIMEOUT":
        return "AI xử lý quá lâu khi tạo nội dung. Hãy thử lại; nếu vẫn lỗi, hãy rút ngắn nguồn nội dung hoặc tăng timeout trong Settings."
    return str(exc)


def _planning_error_status(exc: ai_planning.AIPlanningError) -> int:
    if isinstance(exc, video_planning_pool.ProjectPlanningActiveError):
        return 409
    return 502


def _audio_media_type(path) -> str:
    guessed, _ = mimetypes.guess_type(path.name)
    return guessed or "audio/wav"


def _provider_session_response(row) -> models.VideoProviderSessionResponse:
    response = models.VideoProviderSessionResponse.model_validate(row)
    response.chrome_profile_configured = bool(row.chrome_profile_path)
    return response

@router.get("/provider-sessions/veo/default", response_model=models.VideoProviderSessionResponse | None)
async def get_default_veo_provider_session(db: Session = Depends(get_db)):
    row = video_provider_sessions.get_default_session(db, create=True)
    return _provider_session_response(row) if row else None

@router.post("/provider-sessions/veo/open-login", response_model=models.VideoProviderSessionResponse)
async def open_veo_provider_login(
    data: models.VideoProviderSessionOpenRequest | None = None,
    db: Session = Depends(get_db),
):
    request = data or models.VideoProviderSessionOpenRequest()
    try:
        row = video_provider_sessions.open_login_session(db, provider=request.provider, change_account=request.change_account)
    except video_provider_sessions.VideoProviderSessionError as exc:
        raise _error(400, str(exc), exc.error_code, exc=exc, step_name="veo_open_login") from exc
    return _provider_session_response(row)

@router.post("/provider-sessions/veo/check", response_model=models.VideoProviderSessionResponse)
async def check_veo_provider_session(db: Session = Depends(get_db)):
    try:
        row = video_provider_sessions.check_session(db)
    except video_provider_sessions.VideoProviderSessionError as exc:
        raise _error(400, str(exc), exc.error_code, exc=exc, step_name="veo_check_session") from exc
    return _provider_session_response(row)

@router.put("/provider-sessions/{session_id}/label", response_model=models.VideoProviderSessionResponse)
async def update_provider_session_label(
    session_id: str,
    data: models.VideoProviderSessionLabelUpdate,
    db: Session = Depends(get_db),
):
    row = video_provider_sessions.update_connection_label(session_id, data.connection_label, db)
    if row is None:
        raise _error(404, "Không tìm thấy phiên Veo3/Chrome.", "VIDEO_PROVIDER_SESSION_NOT_FOUND")
    return _provider_session_response(row)

@router.post("/provider-sessions/{session_id}/confirm-identity", response_model=models.VideoProviderSessionResponse)
async def confirm_provider_session_identity(session_id: str, db: Session = Depends(get_db)):
    row = video_provider_sessions.confirm_identity(session_id, db)
    if row is None:
        raise _error(404, "Không tìm thấy phiên Veo3/Chrome.", "VIDEO_PROVIDER_SESSION_NOT_FOUND")
    return _provider_session_response(row)

@router.post("/provider-sessions/{session_id}/invalidate", response_model=models.VideoProviderSessionResponse)
async def invalidate_provider_session(session_id: str, db: Session = Depends(get_db)):
    row = video_provider_sessions.invalidate_session(session_id, db)
    if row is None:
        raise _error(404, "Không tìm thấy phiên Veo3/Chrome.", "VIDEO_PROVIDER_SESSION_NOT_FOUND")
    return _provider_session_response(row)

@router.post("/provider-sessions/{session_id}/change-account", response_model=models.VideoProviderSessionResponse)
async def change_provider_session_account(session_id: str, db: Session = Depends(get_db)):
    row = video_provider_sessions.invalidate_session(session_id, db, reason="Người dùng yêu cầu đổi tài khoản Google cho Veo3.")
    if row is None:
        raise _error(404, "Không tìm thấy phiên Veo3/Chrome.", "VIDEO_PROVIDER_SESSION_NOT_FOUND")
    try:
        row = video_provider_sessions.open_login_session(db, provider=row.provider, change_account=True)
    except video_provider_sessions.VideoProviderSessionError as exc:
        raise _error(400, str(exc), exc.error_code, exc=exc, step_name="veo_change_account") from exc
    return _provider_session_response(row)

@router.get("/planning/check", response_model=models.AIPlanningProviderCheckResponse)
async def check_ai_planning_provider(
    check_exec: bool = Query(False, description="Run a tiny codex exec request in addition to local checks."),
    db: Session = Depends(get_db),
):
    settings = settings_service.get_ai_planning_settings(db)
    return ai_planning.check_provider(settings, check_exec=check_exec)


@router.post("/projects/{project_id}/plan", response_model=models.VideoProjectDetailResponse)
async def generate_video_project_plan(project_id: str, db: Session = Depends(get_db)):
    try:
        project = video_planning.generate_project_plan(project_id, db)
    except ai_planning.AIPlanningError as exc:
        raise _error(
            _planning_error_status(exc),
            _planning_error_message(exc),
            exc.error_code,
            exc=exc,
            project_id=project_id,
            step_name="project_plan",
        ) from exc
    except video_planning.VideoPlanningValidationError as exc:
        raise _error(
            422, str(exc), "VIDEO_PLANNING_INVALID_OUTPUT", exc=exc, project_id=project_id, step_name="project_plan"
        ) from exc
    if project is None:
        raise _error(404, "Không tìm thấy dự án video.", "VIDEO_PROJECT_NOT_FOUND")
    return project


@router.get("/projects", response_model=list[models.VideoProjectResponse])
async def list_video_projects(db: Session = Depends(get_db)):
    return video_projects.list_projects(db)


@router.get("/series", response_model=list[models.VideoSeriesResponse])
async def list_video_series(db: Session = Depends(get_db)):
    return video_projects.list_series(db)


@router.post("/series", response_model=models.VideoSeriesResponse)
async def create_video_series(data: models.VideoSeriesCreate, db: Session = Depends(get_db)):
    return video_projects.create_series(data, db)


@router.get("/series/{series_id}", response_model=models.VideoSeriesResponse)
async def get_video_series(series_id: str, db: Session = Depends(get_db)):
    series = video_projects.get_series(series_id, db)
    if series is None:
        raise _error(404, "Không tìm thấy series AI Video.", "AI_VIDEO_SERIES_NOT_FOUND")
    return series


@router.put("/series/{series_id}", response_model=models.VideoSeriesResponse)
async def update_video_series(series_id: str, data: models.VideoSeriesUpdate, db: Session = Depends(get_db)):
    series = video_projects.update_series(series_id, data, db)
    if series is None:
        raise _error(404, "Không tìm thấy series AI Video.", "AI_VIDEO_SERIES_NOT_FOUND")
    return series


@router.get("/series/{series_id}/memory-cards", response_model=models.SeriesMemoryCardListResponse)
async def list_series_memory_cards(
    series_id: str,
    card_type: str | None = Query(None),
    status: str | None = Query(None),
    episode_number: int | None = Query(None, ge=1, le=10000),
    entity_ref: str | None = Query(None),
    tag: str | None = Query(None),
    min_importance: float | None = Query(None, ge=0.0, le=1.0),
    db: Session = Depends(get_db),
):
    try:
        return series_brain.list_memory_cards(
            series_id,
            db,
            card_type=card_type,
            status=status,
            episode_number=episode_number,
            entity_ref=entity_ref,
            tag=tag,
            min_importance=min_importance,
        )
    except series_brain.SeriesBrainError as exc:
        raise _error(404, str(exc), "SERIES_BRAIN_SERIES_NOT_FOUND") from exc


@router.post("/series/{series_id}/memory-cards", response_model=models.SeriesMemoryCardResponse)
async def create_series_memory_card(
    series_id: str,
    data: models.SeriesMemoryCardCreate,
    db: Session = Depends(get_db),
):
    try:
        card = series_brain.create_memory_card(series_id, data, db)
    except series_brain.SeriesBrainError as exc:
        raise _error(404, str(exc), "SERIES_BRAIN_SERIES_NOT_FOUND") from exc
    video_series_memory.sync_series_memory_file(series_id, db)
    return card


@router.post("/series/{series_id}/memory-cards/suggestions", response_model=models.SeriesMemorySuggestionResponse)
async def suggest_series_memory_cards(
    series_id: str,
    data: models.SeriesMemorySuggestionRequest | None = None,
    db: Session = Depends(get_db),
):
    try:
        result = series_brain.suggest_memory_cards(series_id, data or models.SeriesMemorySuggestionRequest(), db)
    except series_brain.SeriesBrainError as exc:
        raise _error(404, str(exc), "SERIES_BRAIN_SERIES_NOT_FOUND") from exc
    if result.saved:
        video_series_memory.sync_series_memory_file(series_id, db)
    return result


@router.put("/series/{series_id}/memory-cards/{card_id}", response_model=models.SeriesMemoryCardResponse)
async def update_series_memory_card(
    series_id: str,
    card_id: str,
    data: models.SeriesMemoryCardUpdate,
    db: Session = Depends(get_db),
):
    card = series_brain.update_memory_card(series_id, card_id, data, db)
    if card is None:
        raise _error(404, "Khong tim thay the nho.", "SERIES_MEMORY_CARD_NOT_FOUND")
    video_series_memory.sync_series_memory_file(series_id, db)
    return card


@router.post("/series/{series_id}/memory-cards/{card_id}/status", response_model=models.SeriesMemoryCardResponse)
async def set_series_memory_card_status(
    series_id: str,
    card_id: str,
    data: models.SeriesMemoryCardStatusRequest,
    db: Session = Depends(get_db),
):
    card = series_brain.set_memory_card_status(series_id, card_id, data, db)
    if card is None:
        raise _error(404, "Khong tim thay the nho.", "SERIES_MEMORY_CARD_NOT_FOUND")
    video_series_memory.sync_series_memory_file(series_id, db)
    return card


@router.delete("/series/{series_id}/memory-cards/{card_id}")
async def delete_series_memory_card(series_id: str, card_id: str, db: Session = Depends(get_db)):
    if not series_brain.delete_memory_card(series_id, card_id, db):
        raise _error(404, "Khong tim thay the nho.", "SERIES_MEMORY_CARD_NOT_FOUND")
    video_series_memory.sync_series_memory_file(series_id, db)
    return {"deleted": True}


@router.get("/series/{series_id}/current-states", response_model=models.SeriesCurrentStateListResponse)
async def list_series_current_states(series_id: str, db: Session = Depends(get_db)):
    try:
        return series_brain.list_current_states(series_id, db)
    except series_brain.SeriesBrainError as exc:
        raise _error(404, str(exc), "SERIES_BRAIN_SERIES_NOT_FOUND") from exc


@router.post("/series/{series_id}/current-states", response_model=models.SeriesCurrentStateResponse)
async def create_series_current_state(
    series_id: str,
    data: models.SeriesCurrentStateCreate,
    db: Session = Depends(get_db),
):
    try:
        state = series_brain.create_current_state(series_id, data, db)
    except series_brain.SeriesBrainError as exc:
        raise _error(404, str(exc), "SERIES_BRAIN_SERIES_NOT_FOUND") from exc
    video_series_memory.sync_series_memory_file(series_id, db)
    return state


@router.post("/series/{series_id}/current-states/propose", response_model=models.SeriesCurrentStateResponse)
async def propose_series_current_state(
    series_id: str,
    data: models.SeriesStateProposalRequest,
    db: Session = Depends(get_db),
):
    try:
        state = series_brain.propose_current_state(series_id, data, db)
    except series_brain.SeriesBrainError as exc:
        raise _error(404, str(exc), "SERIES_BRAIN_SERIES_NOT_FOUND") from exc
    video_series_memory.sync_series_memory_file(series_id, db)
    return state


@router.put("/series/{series_id}/current-states/{state_id}", response_model=models.SeriesCurrentStateResponse)
async def update_series_current_state(
    series_id: str,
    state_id: str,
    data: models.SeriesCurrentStateUpdate,
    db: Session = Depends(get_db),
):
    state = series_brain.update_current_state(series_id, state_id, data, db)
    if state is None:
        raise _error(404, "Khong tim thay trang thai series.", "SERIES_CURRENT_STATE_NOT_FOUND")
    video_series_memory.sync_series_memory_file(series_id, db)
    return state


@router.post("/series/{series_id}/current-states/{state_id}/status", response_model=models.SeriesCurrentStateResponse)
async def set_series_current_state_status(
    series_id: str,
    state_id: str,
    data: models.SeriesCurrentStateStatusRequest,
    db: Session = Depends(get_db),
):
    state = series_brain.set_current_state_status(series_id, state_id, data, db)
    if state is None:
        raise _error(404, "Khong tim thay trang thai series.", "SERIES_CURRENT_STATE_NOT_FOUND")
    video_series_memory.sync_series_memory_file(series_id, db)
    return state


@router.post("/series/{series_id}/context/compile", response_model=models.SeriesContextCompileResponse)
async def compile_series_context(
    series_id: str,
    data: models.SeriesContextCompileRequest,
    db: Session = Depends(get_db),
):
    try:
        return series_brain.compile_context(series_id, data, db)
    except series_brain.SeriesBrainError as exc:
        raise _error(404, str(exc), "SERIES_BRAIN_SERIES_NOT_FOUND") from exc


@router.get("/series/{series_id}/context/traces", response_model=models.SeriesContextTraceListResponse)
async def list_series_context_traces(
    series_id: str,
    task_type: str | None = Query(None),
    project_id: str | None = Query(None),
    story_episode_id: str | None = Query(None),
    limit: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db),
):
    try:
        return series_brain.list_context_traces(
            series_id,
            db,
            task_type=task_type,
            project_id=project_id,
            story_episode_id=story_episode_id,
            limit=limit,
        )
    except series_brain.SeriesBrainError as exc:
        raise _error(404, str(exc), "SERIES_BRAIN_SERIES_NOT_FOUND") from exc


@router.post("/series/{series_id}/canon-check", response_model=models.SeriesCanonCheckResponse)
async def check_series_canon(
    series_id: str,
    data: models.SeriesCanonCheckRequest,
    db: Session = Depends(get_db),
):
    try:
        return series_brain.check_canon(series_id, data, db)
    except series_brain.SeriesBrainError as exc:
        raise _error(404, str(exc), "SERIES_BRAIN_SERIES_NOT_FOUND") from exc


@router.get("/series/{series_id}/canon-checks", response_model=list[models.SeriesCanonCheckResponse])
async def list_series_canon_checks(
    series_id: str,
    project_id: str | None = Query(None),
    story_episode_id: str | None = Query(None),
    limit: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db),
):
    try:
        return series_brain.latest_canon_checks(
            series_id,
            db,
            project_id=project_id,
            story_episode_id=story_episode_id,
            limit=limit,
        )
    except series_brain.SeriesBrainError as exc:
        raise _error(404, str(exc), "SERIES_BRAIN_SERIES_NOT_FOUND") from exc


@router.get("/series/{series_id}/character-profiles", response_model=list[models.SeriesCharacterProfileResponse])
async def list_series_character_profiles(series_id: str, db: Session = Depends(get_db)):
    profiles = video_projects.list_character_profiles(series_id, db)
    if profiles is None:
        raise _error(404, "Không tìm thấy series.", "AI_VIDEO_SERIES_NOT_FOUND")
    return profiles

@router.post("/series/{series_id}/character-profiles", response_model=models.SeriesCharacterProfileResponse)
async def create_series_character_profile(
    series_id: str,
    data: models.SeriesCharacterProfileCreate,
    db: Session = Depends(get_db),
):
    profile = video_projects.create_character_profile(series_id, data, db)
    if profile is None:
        raise _error(404, "Không tìm thấy series.", "AI_VIDEO_SERIES_NOT_FOUND")
    return profile

@router.put("/series/{series_id}/character-profiles/reorder", response_model=list[models.SeriesCharacterProfileResponse])
async def reorder_series_character_profiles(
    series_id: str,
    data: models.SeriesCharacterProfileReorderRequest,
    db: Session = Depends(get_db),
):
    profiles = video_projects.reorder_character_profiles(series_id, data, db)
    if profiles is None:
        raise _error(404, "Không tìm thấy series.", "AI_VIDEO_SERIES_NOT_FOUND")
    return profiles

@router.post(
    "/series/{series_id}/character-profile-suggestions",
    response_model=models.SeriesCharacterProfileSuggestionResponse,
)
async def suggest_series_character_profiles(series_id: str, db: Session = Depends(get_db)):
    suggestion = video_projects.suggest_character_profiles_from_bible(series_id, db)
    if suggestion is None:
        raise _error(404, "Không tìm thấy series.", "AI_VIDEO_SERIES_NOT_FOUND")
    return suggestion

@router.put("/series/{series_id}/character-profiles/{profile_id}", response_model=models.SeriesCharacterProfileResponse)
async def update_series_character_profile(
    series_id: str,
    profile_id: str,
    data: models.SeriesCharacterProfileUpdate,
    db: Session = Depends(get_db),
):
    profile = video_projects.update_character_profile(series_id, profile_id, data, db)
    if profile is None:
        raise _error(404, "Không tìm thấy Hồ sơ nhân vật.", "AI_VIDEO_CHARACTER_PROFILE_NOT_FOUND")
    return profile

@router.get("/series/{series_id}/reference-assets", response_model=models.SeriesReferenceAssetListResponse)
async def list_series_reference_assets(
    series_id: str,
    entity_type: str | None = Query(None, pattern=models.SERIES_REFERENCE_ENTITY_PATTERN),
    entity_id: str | None = Query(None),
    approval_status: str | None = Query(None, pattern=models.SERIES_REFERENCE_STATUS_PATTERN),
    active: bool | None = Query(None),
    db: Session = Depends(get_db),
):
    try:
        return series_references.list_reference_assets(
            series_id,
            db,
            entity_type=entity_type,
            entity_id=entity_id,
            approval_status=approval_status,
            active=active,
        )
    except series_references.SeriesReferenceError as exc:
        raise _error(404, str(exc), "SERIES_REFERENCE_SERIES_NOT_FOUND") from exc

@router.post("/series/{series_id}/reference-assets", response_model=models.SeriesReferenceAssetResponse)
async def upload_series_reference_asset(
    series_id: str,
    entity_type: str = Form(..., pattern=models.SERIES_REFERENCE_ENTITY_PATTERN),
    entity_id: str = Form(...),
    reference_role: str = Form(..., pattern=models.SERIES_REFERENCE_ROLE_PATTERN),
    label: str | None = Form(None),
    source_type: str | None = Form("upload"),
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
):
    try:
        return series_references.upload_reference_asset(
            series_id,
            entity_type=entity_type,
            entity_id=entity_id,
            reference_role=reference_role,
            filename=file.filename or "reference.png",
            content_type=file.content_type,
            data=await file.read(),
            label=label,
            source_type=source_type,
            db=db,
        )
    except series_references.SeriesReferenceError as exc:
        raise _error(422, str(exc), "SERIES_REFERENCE_UPLOAD_INVALID") from exc

@router.get("/series/{series_id}/reference-assets/prompt-package")
async def build_series_reference_prompt_package(
    series_id: str,
    prompt_text: str | None = Query(None),
    provider: str = Query("provider-neutral"),
    provider_supports_references: bool = Query(False),
    db: Session = Depends(get_db),
):
    try:
        return series_references.build_reference_prompt_package(
            series_id,
            db,
            prompt_text=prompt_text,
            provider=provider,
            provider_supports_references=provider_supports_references,
        )
    except series_references.SeriesReferenceError as exc:
        raise _error(404, str(exc), "SERIES_REFERENCE_SERIES_NOT_FOUND") from exc

@router.post("/series/{series_id}/reference-assets/{asset_id}/status", response_model=models.SeriesReferenceAssetResponse)
async def update_series_reference_asset_status(
    series_id: str,
    asset_id: str,
    data: models.SeriesReferenceAssetStatusRequest,
    db: Session = Depends(get_db),
):
    try:
        asset = series_references.update_reference_asset_status(series_id, asset_id, data, db)
    except series_references.SeriesReferenceError as exc:
        raise _error(422, str(exc), "SERIES_REFERENCE_STATUS_INVALID") from exc
    if asset is None:
        raise _error(404, "Không tìm thấy ảnh tham chiếu.", "SERIES_REFERENCE_ASSET_NOT_FOUND")
    return asset

@router.delete("/series/{series_id}/reference-assets/{asset_id}")
async def delete_series_reference_asset(series_id: str, asset_id: str, db: Session = Depends(get_db)):
    result = series_references.delete_reference_asset(series_id, asset_id, db)
    if result is None:
        raise _error(404, "Không tìm thấy ảnh tham chiếu.", "SERIES_REFERENCE_ASSET_NOT_FOUND")
    return result

@router.get("/series/{series_id}/versions/{entity_type}/{entity_id}", response_model=models.SeriesVersionHistoryResponse)
async def get_series_version_history(series_id: str, entity_type: str, entity_id: str, db: Session = Depends(get_db)):
    try:
        return series_references.version_history(series_id, entity_type, entity_id, db)
    except series_references.SeriesReferenceError as exc:
        raise _error(404, str(exc), "SERIES_VERSION_SERIES_NOT_FOUND") from exc

@router.post("/series/{series_id}/dependencies", response_model=list[models.ArtifactDependencySnapshotResponse])
async def record_series_artifact_dependencies(
    series_id: str,
    data: models.ArtifactDependencyRecordRequest,
    db: Session = Depends(get_db),
):
    try:
        return series_references.record_dependency_snapshots(series_id, data, db)
    except series_references.SeriesReferenceError as exc:
        raise _error(404, str(exc), "SERIES_DEPENDENCY_SERIES_NOT_FOUND") from exc

@router.get("/series/{series_id}/dependencies/{artifact_type}/{artifact_id}", response_model=list[models.ArtifactDependencySnapshotResponse])
async def list_series_artifact_dependencies(
    series_id: str,
    artifact_type: str,
    artifact_id: str,
    db: Session = Depends(get_db),
):
    try:
        return series_references.dependencies_for_artifact(series_id, artifact_type, artifact_id, db)
    except series_references.SeriesReferenceError as exc:
        raise _error(404, str(exc), "SERIES_DEPENDENCY_SERIES_NOT_FOUND") from exc

@router.get("/series/{series_id}/stale-events", response_model=models.ArtifactStaleEventListResponse)
async def list_series_stale_events(
    series_id: str,
    status: str | None = Query("active"),
    artifact_type: str | None = Query(None),
    limit: int = Query(100, ge=1, le=500),
    db: Session = Depends(get_db),
):
    try:
        return series_references.list_stale_events(series_id, db, status=status, artifact_type=artifact_type, limit=limit)
    except series_references.SeriesReferenceError as exc:
        raise _error(404, str(exc), "SERIES_STALE_SERIES_NOT_FOUND") from exc

@router.post("/series/{series_id}/stale-events/mark", response_model=models.ArtifactStaleEventListResponse)
async def mark_series_dependency_stale(
    series_id: str,
    data: models.ArtifactStaleMarkRequest,
    db: Session = Depends(get_db),
):
    try:
        return series_references.mark_dependency_stale(
            series_id,
            dependency_type=data.dependency_type,
            dependency_id=data.dependency_id,
            old_revision=data.old_revision,
            new_revision=data.new_revision,
            changed_scope=data.changed_scope,
            reason_vi=data.reason_vi,
            db=db,
        )
    except series_references.SeriesReferenceError as exc:
        raise _error(404, str(exc), "SERIES_STALE_SERIES_NOT_FOUND") from exc

@router.post("/series/{series_id}/stale-events/regenerate", response_model=models.ArtifactTargetedRegenerationResponse)
async def request_series_targeted_regeneration(
    series_id: str,
    data: models.ArtifactTargetedRegenerationRequest,
    db: Session = Depends(get_db),
):
    try:
        return series_references.request_targeted_regeneration(series_id, data, db)
    except series_references.SeriesReferenceError as exc:
        raise _error(404, str(exc), "SERIES_STALE_SERIES_NOT_FOUND") from exc

@router.delete("/series/{series_id}/character-profiles/{profile_id}")
async def delete_series_character_profile(series_id: str, profile_id: str, db: Session = Depends(get_db)):
    try:
        deleted = video_projects.delete_character_profile(series_id, profile_id, db)
    except video_projects.VideoProjectOperationError as exc:
        raise _error(409, str(exc), exc.error_code, exc=exc, series_id=series_id) from exc
    if not deleted:
        raise _error(404, "Không tìm thấy Hồ sơ nhân vật.", "AI_VIDEO_CHARACTER_PROFILE_NOT_FOUND")
    return {"message": "Đã xoá Hồ sơ nhân vật."}

@router.delete("/series/{series_id}")
async def delete_video_series(
    series_id: str,
    delete_episodes: bool = Query(False),
    confirm_delete_episodes: bool = Query(False),
    db: Session = Depends(get_db),
):
    try:
        deleted = video_projects.delete_series(
            series_id,
            db,
            delete_episodes=delete_episodes,
            confirm_delete_episodes=confirm_delete_episodes,
        )
    except video_projects.VideoProjectOperationError as exc:
        raise _error(409, str(exc), exc.error_code, exc=exc, series_id=series_id, step_name="series_delete") from exc
    if not deleted:
        raise _error(404, "Không tìm thấy series AI Video.", "AI_VIDEO_SERIES_NOT_FOUND")
    return {"message": "Đã xoá series AI Video."}


@router.post("/series/{series_id}/episodes", response_model=models.VideoProjectResponse)
async def create_video_series_episode(series_id: str, data: models.VideoEpisodeCreate, db: Session = Depends(get_db)):
    try:
        project = video_projects.create_episode(series_id, data, db)
    except ValueError as exc:
        raise _error(422, str(exc), "AI_VIDEO_EPISODE_INVALID", exc=exc, series_id=series_id) from exc
    if project is None:
        raise _error(404, "Không tìm thấy series AI Video.", "AI_VIDEO_SERIES_NOT_FOUND")
    return project


@router.post("/projects", response_model=models.VideoProjectResponse)
async def create_video_project(
    data: models.VideoProjectCreate,
    db: Session = Depends(get_db),
):
    try:
        return video_projects.create_project(data, db)
    except ValueError as exc:
        raise _error(422, str(exc), "AI_VIDEO_PROJECT_CONFIG_INVALID", exc=exc) from exc


@router.get("/projects/{project_id}", response_model=models.VideoProjectDetailResponse)
async def get_video_project(project_id: str, db: Session = Depends(get_db)):
    project = video_projects.get_project(project_id, db)
    if project is None:
        raise _error(404, "Không tìm thấy dự án video.", "VIDEO_PROJECT_NOT_FOUND")
    return project


@router.get("/projects/{project_id}/memory", response_model=models.VideoProjectMemoryListResponse)
async def list_video_project_memory(project_id: str, db: Session = Depends(get_db)):
    if db.query(DBVideoProject.id).filter(DBVideoProject.id == project_id).first() is None:
        raise _error(404, "KhÃ´ng tÃ¬m tháº¥y dá»± Ã¡n video.", "VIDEO_PROJECT_NOT_FOUND")
    return video_project_memory.list_project_memory(project_id, db)

@router.get("/projects/{project_id}/target-timeline", response_model=models.VideoProjectTargetTimelineResponse)
async def list_video_project_target_timeline(project_id: str, db: Session = Depends(get_db)):
    if db.query(DBVideoProject.id).filter(DBVideoProject.id == project_id).first() is None:
        raise _error(404, "KhÃ´ng tÃ¬m tháº¥y dá»± Ã¡n video.", "VIDEO_PROJECT_NOT_FOUND")
    return video_project_memory.list_target_timeline(project_id, db)

@router.post("/projects/{project_id}/context/compile", response_model=models.VideoProjectContextSnapshotResponse)
async def compile_video_project_context(
    project_id: str,
    data: models.VideoProjectContextCompileRequest,
    db: Session = Depends(get_db),
):
    try:
        return video_project_memory.compile_context(project_id, data, db)
    except video_project_memory.VideoProjectMemoryError as exc:
        raise _error(exc.status_code, str(exc), exc.error_code, exc=exc, project_id=project_id) from exc

@router.get("/projects/{project_id}/context/snapshots", response_model=models.VideoProjectContextSnapshotListResponse)
async def list_video_project_context_snapshots(
    project_id: str,
    limit: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
):
    if db.query(DBVideoProject.id).filter(DBVideoProject.id == project_id).first() is None:
        raise _error(404, "KhÃ´ng tÃ¬m tháº¥y dá»± Ã¡n video.", "VIDEO_PROJECT_NOT_FOUND")
    return video_project_memory.list_context_snapshots(project_id, db, limit=limit)

@router.post("/projects/{project_id}/quality/reports", response_model=models.VideoQualityReportResponse)
async def run_video_project_quality_report(
    project_id: str,
    data: models.VideoQualityRunRequest | None = None,
    db: Session = Depends(get_db),
):
    try:
        report = video_quality.run_project_quality_report(project_id, data or models.VideoQualityRunRequest(), db)
    except video_quality.VideoQualityError as exc:
        raise _error(exc.status_code, str(exc), exc.error_code, exc=exc, project_id=project_id) from exc
    if report is None:
        raise _error(404, "Không tìm thấy dự án video.", "VIDEO_PROJECT_NOT_FOUND")
    return report

@router.get("/projects/{project_id}/quality/reports/latest", response_model=models.VideoQualityReportResponse | None)
async def get_latest_video_project_quality_report(project_id: str, db: Session = Depends(get_db)):
    if db.query(DBVideoProject.id).filter(DBVideoProject.id == project_id).first() is None:
        raise _error(404, "Không tìm thấy dự án video.", "VIDEO_PROJECT_NOT_FOUND")
    return video_quality.get_latest_project_report(project_id, db)

@router.get("/projects/{project_id}/quality/reports", response_model=models.VideoQualityReportListResponse)
async def list_video_project_quality_reports(
    project_id: str,
    limit: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
):
    if db.query(DBVideoProject.id).filter(DBVideoProject.id == project_id).first() is None:
        raise _error(404, "Không tìm thấy dự án video.", "VIDEO_PROJECT_NOT_FOUND")
    return video_quality.list_project_reports(project_id, db, limit=limit)

@router.post("/quality/reports/{report_id}/override", response_model=models.VideoQualityReportResponse)
async def override_video_quality_report(
    report_id: str,
    data: models.VideoQualityOverrideRequest,
    db: Session = Depends(get_db),
):
    report = video_quality.override_report(report_id, data, db)
    if report is None:
        raise _error(404, "Không tìm thấy báo cáo chất lượng.", "VIDEO_QUALITY_REPORT_NOT_FOUND")
    return report

@router.post("/projects/{project_id}/retention-datasets", response_model=models.PlatformRetentionDatasetResponse)
async def import_video_project_retention_dataset(
    project_id: str,
    data: models.PlatformRetentionDatasetCreateRequest,
    db: Session = Depends(get_db),
):
    dataset = video_quality.create_project_retention_dataset(project_id, data, db)
    if dataset is None:
        raise _error(404, "Không tìm thấy dự án video.", "VIDEO_PROJECT_NOT_FOUND")
    return dataset

@router.get("/projects/{project_id}/retention-datasets", response_model=models.PlatformRetentionDatasetListResponse)
async def list_video_project_retention_datasets(
    project_id: str,
    limit: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
):
    if db.query(DBVideoProject.id).filter(DBVideoProject.id == project_id).first() is None:
        raise _error(404, "Không tìm thấy dự án video.", "VIDEO_PROJECT_NOT_FOUND")
    return video_quality.list_project_retention_datasets(project_id, db, limit=limit)

@router.put("/projects/{project_id}", response_model=models.VideoProjectResponse)
async def update_video_project(
    project_id: str,
    data: models.VideoProjectUpdate,
    db: Session = Depends(get_db),
):
    try:
        project = video_projects.update_project(project_id, data, db)
    except ValueError as exc:
        raise _error(422, str(exc), "AI_VIDEO_PROJECT_CONFIG_INVALID", exc=exc, project_id=project_id) from exc
    if project is None:
        raise _error(404, "Không tìm thấy dự án video.", "VIDEO_PROJECT_NOT_FOUND")
    return project


@router.post("/projects/{project_id}/localize", response_model=models.VideoProjectResponse)
async def localize_video_project(
    project_id: str,
    data: models.VideoProjectLocalizeRequest,
    db: Session = Depends(get_db),
):
    try:
        project = video_projects.localize_project(project_id, data, db)
    except ValueError as exc:
        raise _error(422, str(exc), "AI_VIDEO_PROJECT_LOCALIZE_INVALID", exc=exc, project_id=project_id) from exc
    if project is None:
        raise _error(404, "Không tìm thấy dự án video.", "VIDEO_PROJECT_NOT_FOUND")
    return project


@router.get("/projects/{project_id}/source-blocks", response_model=list[models.VideoSourceBlockResponse])
async def list_video_source_blocks(project_id: str, db: Session = Depends(get_db)):
    blocks = video_phase2.list_source_blocks(project_id, db)
    if blocks is None:
        raise _error(404, "Không tìm thấy dự án video.", "VIDEO_PROJECT_NOT_FOUND")
    return blocks


@router.post("/projects/{project_id}/source-blocks", response_model=models.VideoSourceBlockResponse)
async def create_video_source_block(
    project_id: str, data: models.VideoSourceBlockCreate, db: Session = Depends(get_db)
):
    block = video_phase2.create_source_block(project_id, data, db)
    if block is None:
        raise _error(404, "Không tìm thấy dự án video.", "VIDEO_PROJECT_NOT_FOUND")
    return block


@router.put("/projects/{project_id}/source-blocks/{block_id}", response_model=models.VideoSourceBlockResponse)
async def update_video_source_block(
    project_id: str, block_id: str, data: models.VideoSourceBlockUpdate, db: Session = Depends(get_db)
):
    block = video_phase2.update_source_block(project_id, block_id, data, db)
    if block is None:
        raise _error(404, "Không tìm thấy nguồn nội dung.", "VIDEO_SOURCE_BLOCK_NOT_FOUND")
    return block


@router.delete("/projects/{project_id}/source-blocks/{block_id}")
async def delete_video_source_block(
    project_id: str,
    block_id: str,
    confirm_delete_last: bool = Query(False),
    db: Session = Depends(get_db),
):
    try:
        deleted = video_phase2.delete_source_block(project_id, block_id, db, confirm_delete_last=confirm_delete_last)
    except ValueError as exc:
        raise _error(422, str(exc), "VIDEO_SOURCE_BLOCK_LAST_CONFIRM_REQUIRED", exc=exc, project_id=project_id) from exc
    if deleted is None:
        raise _error(404, "Không tìm thấy dự án video.", "VIDEO_PROJECT_NOT_FOUND")
    if deleted is False:
        raise _error(404, "Không tìm thấy nguồn nội dung.", "VIDEO_SOURCE_BLOCK_NOT_FOUND")
    return {"message": "Đã xóa nguồn nội dung."}


@router.post("/projects/{project_id}/source-blocks/reorder", response_model=list[models.VideoSourceBlockResponse])
async def reorder_video_source_blocks(
    project_id: str, data: models.VideoSourceBlockReorderRequest, db: Session = Depends(get_db)
):
    blocks = video_phase2.reorder_source_blocks(project_id, data, db)
    if blocks is None:
        raise _error(404, "Không tìm thấy dự án video.", "VIDEO_PROJECT_NOT_FOUND")
    return blocks


@router.delete("/projects/{project_id}")
async def delete_video_project(project_id: str, db: Session = Depends(get_db)):
    try:
        deleted = video_projects.delete_project(project_id, db)
    except video_projects.VideoProjectOperationError as exc:
        raise _error(409, str(exc), exc.error_code, exc=exc, project_id=project_id, step_name="project_delete") from exc
    if not deleted:
        raise _error(404, "Không tìm thấy dự án video.", "VIDEO_PROJECT_NOT_FOUND")
    return {"message": "Đã xóa dự án video."}


@router.post("/projects/{project_id}/reset-generated-data", response_model=models.VideoGeneratedDataResetResponse)
async def reset_video_project_generated_data(project_id: str, db: Session = Depends(get_db)):
    try:
        result = video_projects.reset_generated_data(project_id, db)
    except video_projects.VideoProjectOperationError as exc:
        raise _error(
            409, str(exc), exc.error_code, exc=exc, project_id=project_id, step_name="project_reset_generated_data"
        ) from exc
    if result is None:
        raise _error(404, "Không tìm thấy dự án video.", "VIDEO_PROJECT_NOT_FOUND")
    return result


@router.post("/projects/{project_id}/series-summary", response_model=models.VideoSeriesResponse)
async def update_video_series_summary_from_project(
    project_id: str,
    data: models.VideoSeriesSummaryUpdateRequest | None = None,
    db: Session = Depends(get_db),
):
    try:
        series = video_projects.update_series_summary_from_project(
            project_id,
            data or models.VideoSeriesSummaryUpdateRequest(),
            db,
        )
    except ValueError as exc:
        raise _error(422, str(exc), "AI_VIDEO_SERIES_SUMMARY_INVALID", exc=exc, project_id=project_id) from exc
    if series is None:
        raise _error(404, "Không tìm thấy dự án video.", "VIDEO_PROJECT_NOT_FOUND")
    return series


@router.get("/projects/{project_id}/status", response_model=models.VideoProjectStatusResponse)
async def get_video_project_status(project_id: str, db: Session = Depends(get_db)):
    status = video_projects.get_project_status(project_id, db)
    if status is None:
        raise _error(404, "Không tìm thấy dự án video.", "VIDEO_PROJECT_NOT_FOUND")
    return status


@router.get("/projects/{project_id}/publishing-metadata", response_model=models.VideoPublishingMetadataResponse)
async def get_video_publishing_metadata(project_id: str, db: Session = Depends(get_db)):
    metadata = video_publishing_metadata.get_publishing_metadata(project_id, db)
    if metadata is None:
        raise _error(404, "Không tìm thấy dự án video.", "VIDEO_PROJECT_NOT_FOUND")
    return metadata

@router.post("/projects/{project_id}/publishing-metadata", response_model=models.VideoPublishingMetadataResponse)
async def generate_video_publishing_metadata(
    project_id: str,
    data: models.VideoPublishingMetadataGenerateRequest | None = None,
    db: Session = Depends(get_db),
):
    try:
        metadata = video_publishing_metadata.generate_publishing_metadata(
            project_id,
            data or models.VideoPublishingMetadataGenerateRequest(),
            db,
        )
    except video_publishing_metadata.VideoPublishingMetadataError as exc:
        raise _error(
            exc.status_code,
            str(exc),
            exc.error_code,
            exc=exc,
            project_id=project_id,
            step_name="publishing_metadata_generation",
        ) from exc
    except ai_planning.AIPlanningError as exc:
        raise _error(
            _planning_error_status(exc),
            _planning_error_message(exc),
            exc.error_code,
            exc=exc,
            project_id=project_id,
            step_name="publishing_metadata_generation",
        ) from exc
    if metadata is None:
        raise _error(404, "Không tìm thấy dự án video.", "VIDEO_PROJECT_NOT_FOUND")
    return metadata

@router.post("/projects/{project_id}/auto-runs", response_model=models.VideoAutoRunResponse)
async def start_video_auto_run(
    project_id: str,
    data: models.VideoAutoRunStartRequest | None = None,
    db: Session = Depends(get_db),
):
    try:
        run = await video_auto_runs.start_auto_run(project_id, data or models.VideoAutoRunStartRequest(), db)
    except video_auto_runs.VideoAutoRunError as exc:
        raise _error(400, str(exc), exc.error_code, exc=exc, project_id=project_id, step_name="auto_run_start") from exc
    if run is None:
        raise _error(404, "Không tìm thấy dự án video.", "VIDEO_PROJECT_NOT_FOUND")
    return run


@router.get("/projects/{project_id}/auto-runs/latest", response_model=models.VideoAutoRunResponse | None)
async def get_latest_video_auto_run(project_id: str, db: Session = Depends(get_db)):
    project_exists = db.query(DBVideoProject.id).filter(DBVideoProject.id == project_id).first()
    if project_exists is None:
        raise _error(404, "Không tìm thấy dự án video.", "VIDEO_PROJECT_NOT_FOUND")
    return video_auto_runs.get_latest_auto_run(project_id, db)


@router.get("/projects/{project_id}/auto-runs/{run_id}", response_model=models.VideoAutoRunResponse)
async def get_video_auto_run(project_id: str, run_id: str, db: Session = Depends(get_db)):
    run = video_auto_runs.get_auto_run(project_id, run_id, db)
    if run is None:
        raise _error(404, "Không tìm thấy auto-run.", "VIDEO_AUTO_RUN_NOT_FOUND")
    return run


@router.post("/projects/{project_id}/auto-runs/{run_id}/continue", response_model=models.VideoAutoRunResponse)
async def continue_video_auto_run(
    project_id: str,
    run_id: str,
    data: models.VideoAutoRunContinueRequest | None = None,
    db: Session = Depends(get_db),
):
    try:
        run = await video_auto_runs.continue_auto_run(
            project_id, run_id, data or models.VideoAutoRunContinueRequest(), db
        )
    except video_auto_runs.VideoAutoRunError as exc:
        raise _error(
            400, str(exc), exc.error_code, exc=exc, project_id=project_id, step_name="auto_run_continue"
        ) from exc
    if run is None:
        raise _error(404, "Không tìm thấy auto-run.", "VIDEO_AUTO_RUN_NOT_FOUND")
    return run


@router.post("/projects/{project_id}/auto-runs/{run_id}/cancel", response_model=models.VideoAutoRunResponse)
async def cancel_video_auto_run(project_id: str, run_id: str, db: Session = Depends(get_db)):
    run = video_auto_runs.cancel_auto_run(project_id, run_id, db)
    if run is None:
        raise _error(404, "Không tìm thấy auto-run.", "VIDEO_AUTO_RUN_NOT_FOUND")
    return run


@router.post("/projects/{project_id}/auto-runs/{run_id}/retry", response_model=models.VideoAutoRunResponse)
async def retry_video_auto_run(
    project_id: str,
    run_id: str,
    data: models.VideoAutoRunRetryRequest | None = None,
    db: Session = Depends(get_db),
):
    try:
        run = await video_auto_runs.retry_auto_run(project_id, run_id, data or models.VideoAutoRunRetryRequest(), db)
    except video_auto_runs.VideoAutoRunError as exc:
        raise _error(400, str(exc), exc.error_code, exc=exc, project_id=project_id, step_name="auto_run_retry") from exc
    if run is None:
        raise _error(404, "Không tìm thấy auto-run.", "VIDEO_AUTO_RUN_NOT_FOUND")
    return run


@router.post("/projects/{project_id}/clip-generation/jobs", response_model=models.VideoClipGenerationJobResponse)
async def start_video_clip_generation_job(
    project_id: str,
    data: models.VideoClipGenerationJobStartRequest | None = None,
    db: Session = Depends(get_db),
):
    try:
        job = await video_clip_generation.start_job(project_id, data or models.VideoClipGenerationJobStartRequest(), db)
    except video_clip_generation.VideoClipGenerationError as exc:
        raise _error(400, str(exc), exc.error_code, exc=exc, project_id=project_id, step_name="clip_generation_start") from exc
    if job is None:
        raise _error(404, "Không tìm thấy dự án video.", "VIDEO_PROJECT_NOT_FOUND")
    return job

@router.get("/projects/{project_id}/clip-generation/jobs/latest", response_model=models.VideoClipGenerationJobResponse | None)
async def get_latest_video_clip_generation_job(project_id: str, db: Session = Depends(get_db)):
    project_exists = db.query(DBVideoProject.id).filter(DBVideoProject.id == project_id).first()
    if project_exists is None:
        raise _error(404, "Không tìm thấy dự án video.", "VIDEO_PROJECT_NOT_FOUND")
    return video_clip_generation.get_latest_job(project_id, db)

@router.get("/projects/{project_id}/clip-generation/jobs/{job_id}", response_model=models.VideoClipGenerationJobResponse)
async def get_video_clip_generation_job(project_id: str, job_id: str, db: Session = Depends(get_db)):
    job = video_clip_generation.get_job(project_id, job_id, db)
    if job is None:
        raise _error(404, "Không tìm thấy job tạo clip Veo.", "VIDEO_CLIP_JOB_NOT_FOUND")
    return job

@router.get("/projects/{project_id}/provider-flow/binding", response_model=models.VideoProviderProjectBindingResponse | None)
async def get_video_provider_project_binding(project_id: str, db: Session = Depends(get_db)):
    project_exists = db.query(DBVideoProject.id).filter(DBVideoProject.id == project_id).first()
    if project_exists is None:
        raise _error(404, "Không tìm thấy dự án video.", "VIDEO_PROJECT_NOT_FOUND")
    return video_provider_project_bindings.get_project_binding(project_id, db)

@router.post("/projects/{project_id}/provider-flow/open", response_model=models.VideoProviderProjectBindingResponse)
async def open_video_provider_project_binding(project_id: str, db: Session = Depends(get_db)):
    try:
        binding = video_provider_project_bindings.open_project_binding(project_id, db)
    except video_provider_project_bindings.VideoProviderProjectBindingError as exc:
        raise _error(400, str(exc), exc.error_code, exc=exc, project_id=project_id, step_name="provider_flow_open") from exc
    if binding is None:
        raise _error(404, "Project chưa có Flow project binding active.", "VIDEO_PROVIDER_PROJECT_BINDING_NOT_FOUND")
    return binding

@router.post("/projects/{project_id}/clip-generation/jobs/{job_id}/retry", response_model=models.VideoClipGenerationJobResponse)
async def retry_video_clip_generation_job(
    project_id: str,
    job_id: str,
    data: models.VideoClipGenerationRetryRequest | None = None,
    db: Session = Depends(get_db),
):
    try:
        job = await video_clip_generation.retry_job(project_id, job_id, data or models.VideoClipGenerationRetryRequest(), db)
    except video_clip_generation.VideoClipGenerationError as exc:
        raise _error(400, str(exc), exc.error_code, exc=exc, project_id=project_id, step_name="clip_generation_retry") from exc
    if job is None:
        raise _error(404, "Không tìm thấy job tạo clip Veo.", "VIDEO_CLIP_JOB_NOT_FOUND")
    return job

@router.post("/projects/{project_id}/clip-generation/jobs/{job_id}/resume", response_model=models.VideoClipGenerationJobResponse)
async def resume_video_clip_generation_job(
    project_id: str,
    job_id: str,
    data: models.VideoClipGenerationResumeRequest | None = None,
    db: Session = Depends(get_db),
):
    try:
        job = await video_clip_generation.resume_job(project_id, job_id, data or models.VideoClipGenerationResumeRequest(), db)
    except video_clip_generation.VideoClipGenerationError as exc:
        raise _error(400, str(exc), exc.error_code, exc=exc, project_id=project_id, step_name="clip_generation_resume") from exc
    if job is None:
        raise _error(404, "Không tìm thấy job tạo clip Veo.", "VIDEO_CLIP_JOB_NOT_FOUND")
    return job

@router.post("/projects/{project_id}/clip-generation/jobs/{job_id}/cancel", response_model=models.VideoClipGenerationJobResponse)
async def cancel_video_clip_generation_job(project_id: str, job_id: str, db: Session = Depends(get_db)):
    job = video_clip_generation.cancel_job(project_id, job_id, db)
    if job is None:
        raise _error(404, "Không tìm thấy job tạo clip Veo.", "VIDEO_CLIP_JOB_NOT_FOUND")
    return job

@router.post(
    "/projects/{project_id}/clip-generation/jobs/{job_id}/items/{item_id}/credit",
    response_model=models.VideoClipGenerationJobResponse,
)
async def approve_video_clip_generation_credit(
    project_id: str,
    job_id: str,
    item_id: str,
    data: models.VideoClipGenerationCreditApprovalRequest | None = None,
    db: Session = Depends(get_db),
):
    try:
        job = video_clip_generation.approve_credit(
            project_id,
            job_id,
            item_id,
            data or models.VideoClipGenerationCreditApprovalRequest(),
            db,
        )
    except video_clip_generation.VideoClipGenerationError as exc:
        raise _error(400, str(exc), exc.error_code, exc=exc, project_id=project_id, step_name="clip_generation_credit") from exc
    if job is None:
        raise _error(404, "Không tìm thấy job tạo clip Veo.", "VIDEO_CLIP_JOB_NOT_FOUND")
    return job

@router.get("/projects/{project_id}/debug")
async def get_video_project_debug(project_id: str, db: Session = Depends(get_db)):
    details = video_debug.get_project_debug_details(project_id, db)
    if details is None:
        raise _error(404, "Không tìm thấy dự án video.", "VIDEO_PROJECT_NOT_FOUND")
    return details


@router.post("/projects/{project_id}/story", response_model=models.VideoProjectDetailResponse)
async def develop_video_story(
    project_id: str, data: models.VideoStoryDevelopRequest | None = None, db: Session = Depends(get_db)
):
    try:
        project = video_phase2.develop_story(project_id, db, force=bool(data.force if data else False))
    except ai_planning.AIPlanningError as exc:
        raise _error(
            _planning_error_status(exc),
            _planning_error_message(exc),
            exc.error_code,
            exc=exc,
            project_id=project_id,
            step_name="story_development",
        ) from exc
    except video_planning.VideoPlanningValidationError as exc:
        raise _error(
            422, str(exc), "VIDEO_STORY_INVALID_OUTPUT", exc=exc, project_id=project_id, step_name="story_development"
        ) from exc
    if project is None:
        raise _error(404, "Không tìm thấy dự án video.", "VIDEO_PROJECT_NOT_FOUND")
    return project


@router.post("/projects/{project_id}/story/approval", response_model=models.VideoProjectResponse)
async def approve_video_story(project_id: str, data: models.VideoStoryApprovalRequest, db: Session = Depends(get_db)):
    project = video_phase2.approve_story(project_id, data.approved, db)
    if project is None:
        raise _error(404, "Không tìm thấy dự án video.", "VIDEO_PROJECT_NOT_FOUND")
    return project


@router.post("/projects/{project_id}/shots", response_model=list[models.VideoShotResponse])
async def generate_video_shots(project_id: str, db: Session = Depends(get_db)):
    try:
        shots = video_phase2.generate_shots(project_id, db)
    except ai_planning.AIPlanningError as exc:
        raise _error(
            _planning_error_status(exc),
            _planning_error_message(exc),
            exc.error_code,
            exc=exc,
            project_id=project_id,
            step_name="shot_breakdown",
        ) from exc
    except video_planning.VideoPlanningValidationError as exc:
        raise _error(
            422, str(exc), "VIDEO_SHOT_INVALID_OUTPUT", exc=exc, project_id=project_id, step_name="shot_breakdown"
        ) from exc
    if shots is None:
        raise _error(404, "Không tìm thấy dự án video.", "VIDEO_PROJECT_NOT_FOUND")
    return shots


@router.put("/projects/{project_id}/shots/{shot_id}", response_model=models.VideoShotResponse)
async def update_video_shot(project_id: str, shot_id: str, data: models.VideoShotUpdate, db: Session = Depends(get_db)):
    shot = video_phase2.update_shot(project_id, shot_id, data, db)
    if shot is None:
        raise _error(404, "Không tìm thấy shot video.", "VIDEO_SHOT_NOT_FOUND")
    return shot


@router.post("/projects/{project_id}/shots/{shot_id}/lock", response_model=models.VideoShotResponse)
async def lock_video_shot(
    project_id: str, shot_id: str, data: models.VideoShotLockRequest, db: Session = Depends(get_db)
):
    shot = video_phase2.set_shot_locked(project_id, shot_id, data.locked, db)
    if shot is None:
        raise _error(404, "Không tìm thấy shot video.", "VIDEO_SHOT_NOT_FOUND")
    return shot


@router.post("/projects/{project_id}/shots/{shot_id}/regenerate", response_model=models.VideoShotResponse)
async def regenerate_video_shot(project_id: str, shot_id: str, db: Session = Depends(get_db)):
    try:
        shot = video_phase2.regenerate_shot(project_id, shot_id, db)
    except ai_planning.AIPlanningError as exc:
        raise _error(
            _planning_error_status(exc),
            _planning_error_message(exc),
            exc.error_code,
            exc=exc,
            project_id=project_id,
            shot_id=shot_id,
            step_name="shot_regenerate",
        ) from exc
    except video_planning.VideoPlanningValidationError as exc:
        raise _error(
            422,
            str(exc),
            "VIDEO_SHOT_INVALID_OUTPUT",
            exc=exc,
            project_id=project_id,
            shot_id=shot_id,
            step_name="shot_regenerate",
        ) from exc
    if shot is None:
        raise _error(404, "Không tìm thấy shot video.", "VIDEO_SHOT_NOT_FOUND")
    return shot


@router.put("/projects/{project_id}/scenes", response_model=list[models.VideoSceneResponse])
async def replace_video_project_scenes(
    project_id: str,
    data: models.VideoScenesReplaceRequest,
    db: Session = Depends(get_db),
):
    scenes = video_projects.replace_scenes(project_id, data, db)
    if scenes is None:
        raise _error(404, "Không tìm thấy dự án video.", "VIDEO_PROJECT_NOT_FOUND")
    return scenes


@router.put("/projects/{project_id}/scenes/{scene_id}", response_model=models.VideoSceneResponse)
async def update_video_scene(
    project_id: str,
    scene_id: str,
    data: models.VideoSceneUpdate,
    db: Session = Depends(get_db),
):
    scene = video_projects.update_scene(project_id, scene_id, data, db)
    if scene is None:
        raise _error(404, "Không tìm thấy cảnh video.", "VIDEO_SCENE_NOT_FOUND")
    return scene


@router.post("/projects/{project_id}/scenes/{scene_id}/regenerate", response_model=models.VideoSceneResponse)
async def regenerate_video_scene(
    project_id: str,
    scene_id: str,
    db: Session = Depends(get_db),
):
    try:
        scene = video_planning.regenerate_scene(project_id, scene_id, db)
    except ai_planning.AIPlanningError as exc:
        raise _error(
            _planning_error_status(exc),
            _planning_error_message(exc),
            exc.error_code,
            exc=exc,
            project_id=project_id,
            scene_id=scene_id,
            step_name="scene_regenerate",
        ) from exc
    except video_planning.VideoPlanningValidationError as exc:
        raise _error(
            422,
            str(exc),
            "VIDEO_PLANNING_INVALID_OUTPUT",
            exc=exc,
            project_id=project_id,
            scene_id=scene_id,
            step_name="scene_regenerate",
        ) from exc
    if scene is None:
        raise _error(404, "Không tìm thấy cảnh video.", "VIDEO_SCENE_NOT_FOUND")
    return scene


@router.post("/projects/{project_id}/prompts")
async def generate_video_prompt_pack(project_id: str, db: Session = Depends(get_db)):
    project_detail = video_projects.get_project(project_id, db)
    if project_detail is not None and project_detail.phase == "phase2":
        try:
            pack = video_phase2.generate_video_prompt_pack(project_id, db)
        except ai_planning.AIPlanningError as exc:
            raise _error(
                _planning_error_status(exc),
                _planning_error_message(exc),
                exc.error_code,
                exc=exc,
                project_id=project_id,
                step_name="video_prompt_generation",
            ) from exc
        except video_planning.VideoPlanningValidationError as exc:
            raise _error(
                422,
                str(exc),
                "VIDEO_PROMPT_INVALID_OUTPUT",
                exc=exc,
                project_id=project_id,
                step_name="video_prompt_generation",
            ) from exc
        if pack is None:
            raise _error(404, "Không tìm thấy dự án video.", "VIDEO_PROJECT_NOT_FOUND")
        return pack
    try:
        pack = video_planning.generate_prompt_pack(project_id, db)
    except ai_planning.AIPlanningError as exc:
        raise _error(
            _planning_error_status(exc),
            _planning_error_message(exc),
            exc.error_code,
            exc=exc,
            project_id=project_id,
            step_name="prompt_pack",
        ) from exc
    except video_planning.VideoPlanningValidationError as exc:
        raise _error(
            422, str(exc), "VIDEO_PROMPT_INVALID_OUTPUT", exc=exc, project_id=project_id, step_name="prompt_pack"
        ) from exc
    if pack is None:
        raise _error(404, "Không tìm thấy dự án video.", "VIDEO_PROJECT_NOT_FOUND")
    return pack


@router.get("/projects/{project_id}/prompts/download")
async def download_project_prompt_pack(project_id: str, db: Session = Depends(get_db)):
    project_detail = video_projects.get_project(project_id, db)
    result = (
        video_phase2.get_video_prompt_pack_download(project_id, db)
        if project_detail is not None and project_detail.phase == "phase2"
        else video_assets.get_prompt_pack_download(project_id, db)
    )
    if result is None:
        raise _error(404, "Không tìm thấy prompt video cho dự án này.", "VIDEO_PROMPT_NOT_FOUND")
    filename, content = result
    return Response(
        content=content,
        media_type="text/plain; charset=utf-8",
        headers={"Content-Disposition": safe_content_disposition("attachment", filename)},
    )


@router.get("/projects/{project_id}/shots/{shot_id}/prompt", response_model=models.VideoPromptContentResponse)
async def get_shot_prompt_content(project_id: str, shot_id: str, db: Session = Depends(get_db)):
    content = video_phase2.get_video_prompt_content(project_id, shot_id, db)
    if content is None:
        raise _error(404, "Không tìm thấy prompt video cho shot này.", "VIDEO_PROMPT_NOT_FOUND")
    return content


@router.get("/projects/{project_id}/shots/{shot_id}/prompt/download")
async def download_shot_prompt(project_id: str, shot_id: str, db: Session = Depends(get_db)):
    result = video_phase2.get_video_prompt_download(project_id, shot_id, db)
    if result is None:
        raise _error(404, "Không tìm thấy prompt video cho shot này.", "VIDEO_PROMPT_NOT_FOUND")
    filename, content = result
    return Response(
        content=content,
        media_type="text/plain; charset=utf-8",
        headers={"Content-Disposition": safe_content_disposition("attachment", filename)},
    )


@router.get("/projects/{project_id}/shots/{shot_id}/clip", response_model=models.VideoShotClipResponse | None)
async def get_shot_clip(project_id: str, shot_id: str, db: Session = Depends(get_db)):
    shot_exists = (
        db.query(DBVideoShot.id).filter(DBVideoShot.project_id == project_id, DBVideoShot.id == shot_id).first()
    )
    if shot_exists is None:
        raise _error(404, "Không tìm thấy shot video.", "VIDEO_SHOT_NOT_FOUND")
    clip = video_rendering.get_active_clip(project_id, shot_id, db)
    return clip


@router.get("/projects/{project_id}/shots/{shot_id}/clip/download")
async def download_shot_clip(project_id: str, shot_id: str, db: Session = Depends(get_db)):
    shot_exists = (
        db.query(DBVideoShot.id).filter(DBVideoShot.project_id == project_id, DBVideoShot.id == shot_id).first()
    )
    if shot_exists is None:
        raise _error(404, "Không tìm thấy shot video.", "VIDEO_SHOT_NOT_FOUND")
    result = video_rendering.get_active_clip_download(project_id, shot_id, db)
    if result is None:
        raise _error(404, "Shot này chưa có video clip sẵn sàng để xem.", "VIDEO_SHOT_CLIP_NOT_FOUND")
    filename, path, media_type = result
    return FileResponse(
        path,
        media_type=media_type,
        headers={"Content-Disposition": safe_content_disposition("inline", filename)},
    )


@router.post("/projects/{project_id}/shots/{shot_id}/clip", response_model=models.VideoShotClipResponse)
async def upload_shot_clip(
    project_id: str,
    shot_id: str,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
):
    try:
        clip = video_rendering.upload_shot_clip(
            project_id,
            shot_id,
            filename=file.filename or "clip.mp4",
            content_type=file.content_type,
            data=await file.read(),
            db=db,
        )
    except video_rendering.VideoRenderError as exc:
        raise _error(
            400, str(exc), exc.error_code, exc=exc, project_id=project_id, shot_id=shot_id, step_name="shot_clip_upload"
        ) from exc
    if clip is None:
        raise _error(404, "Không tìm thấy shot video.", "VIDEO_SHOT_NOT_FOUND")
    return clip


@router.delete("/projects/{project_id}/shots/{shot_id}/clip")
async def delete_shot_clip(project_id: str, shot_id: str, db: Session = Depends(get_db)):
    deleted = video_rendering.delete_shot_clip(project_id, shot_id, db)
    if deleted is None:
        raise _error(404, "Không tìm thấy shot video.", "VIDEO_SHOT_NOT_FOUND")
    if deleted is False:
        raise _error(404, "Shot này chưa có video clip để xóa.", "VIDEO_SHOT_CLIP_NOT_FOUND")
    return {"message": "Đã xóa video clip của shot."}


@router.get("/projects/{project_id}/scenes/{scene_id}/prompt", response_model=models.VideoPromptContentResponse)
async def get_scene_prompt_content(
    project_id: str,
    scene_id: str,
    db: Session = Depends(get_db),
):
    content = video_assets.get_prompt_content(project_id, scene_id, db)
    if content is None:
        raise _error(404, "Không tìm thấy prompt ảnh cho scene này.", "VIDEO_PROMPT_NOT_FOUND")
    return content


@router.get("/projects/{project_id}/scenes/{scene_id}/prompt/download")
async def download_scene_prompt(
    project_id: str,
    scene_id: str,
    db: Session = Depends(get_db),
):
    result = video_assets.get_prompt_download(project_id, scene_id, db)
    if result is None:
        raise _error(404, "Không tìm thấy prompt ảnh cho scene này.", "VIDEO_PROMPT_NOT_FOUND")
    filename, content = result
    return Response(
        content=content,
        media_type="text/plain; charset=utf-8",
        headers={"Content-Disposition": safe_content_disposition("attachment", filename)},
    )


@router.post("/projects/{project_id}/scenes/{scene_id}/preview-image", response_model=models.VideoSceneAssetResponse)
async def upload_scene_preview_image(
    project_id: str,
    scene_id: str,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
):
    try:
        asset = video_assets.upload_preview_image(
            project_id,
            scene_id,
            filename=file.filename or "preview.png",
            content_type=file.content_type,
            data=await file.read(),
            db=db,
        )
    except video_assets.VideoAssetError as exc:
        raise _error(
            400,
            str(exc),
            "VIDEO_PREVIEW_IMAGE_INVALID",
            exc=exc,
            project_id=project_id,
            scene_id=scene_id,
            step_name="preview_image_upload",
        ) from exc
    if asset is None:
        raise _error(404, "Không tìm thấy scene video.", "VIDEO_SCENE_NOT_FOUND")
    return asset


@router.get("/preview-images/{asset_id}")
async def get_preview_image(asset_id: str, db: Session = Depends(get_db)):
    asset = video_assets.get_preview_asset(asset_id, db)
    if asset is None:
        raise _error(404, "Không tìm thấy ảnh preview.", "VIDEO_PREVIEW_IMAGE_NOT_FOUND")
    path = video_assets.resolve_asset_file(asset)
    if path is None:
        raise _error(404, "File ảnh preview không còn tồn tại.", "VIDEO_PREVIEW_IMAGE_FILE_NOT_FOUND")
    return FileResponse(path, media_type=asset.mime_type or "application/octet-stream")


@router.post("/projects/{project_id}/script-approval", response_model=models.VideoProjectResponse)
async def approve_video_script(
    project_id: str,
    data: models.VideoScriptApprovalRequest,
    db: Session = Depends(get_db),
):
    project = video_projects.set_script_approved(project_id, data.approved, db)
    if project is None:
        raise _error(404, "Không tìm thấy dự án video.", "VIDEO_PROJECT_NOT_FOUND")
    return project


@router.post("/projects/{project_id}/scenes/{scene_id}/approval", response_model=models.VideoSceneResponse)
async def approve_video_scene(
    project_id: str,
    scene_id: str,
    data: models.VideoSceneApprovalRequest,
    db: Session = Depends(get_db),
):
    scene = video_projects.set_scene_approved(project_id, scene_id, data.approved, db)
    if scene is None:
        raise _error(404, "Không tìm thấy cảnh video.", "VIDEO_SCENE_NOT_FOUND")
    return scene


@router.post("/projects/{project_id}/scenes/{scene_id}/no-narration", response_model=models.VideoSceneResponse)
async def set_video_scene_no_narration(
    project_id: str,
    scene_id: str,
    data: models.VideoSceneNoNarrationRequest,
    db: Session = Depends(get_db),
):
    scene = video_projects.set_scene_no_narration(project_id, scene_id, data.no_narration, db)
    if scene is None:
        raise _error(404, "Không tìm thấy cảnh video.", "VIDEO_SCENE_NOT_FOUND")
    return scene


@router.post(
    "/projects/{project_id}/scenes/{scene_id}/voice",
    response_model=models.VideoSceneVoiceStatusResponse,
)
async def create_video_scene_voice(
    project_id: str,
    scene_id: str,
    data: models.VideoSceneNarrationRequest,
    db: Session = Depends(get_db),
):
    try:
        status = await video_voice.create_scene_narration(project_id, scene_id, data, db)
    except video_voice.VideoVoiceError as exc:
        raise _error(
            400,
            str(exc),
            exc.error_code,
            exc=exc,
            project_id=project_id,
            scene_id=scene_id,
            step_name="scene_voice_generation",
        ) from exc
    if status is None:
        raise _error(404, "Không tìm thấy cảnh video.", "VIDEO_SCENE_NOT_FOUND")
    return status


@router.get(
    "/projects/{project_id}/scenes/{scene_id}/voice/status",
    response_model=models.VideoSceneVoiceStatusResponse,
)
async def get_video_scene_voice_status(
    project_id: str,
    scene_id: str,
    db: Session = Depends(get_db),
):
    status = video_voice.sync_scene_voice_status(project_id, scene_id, db)
    if status is None:
        raise _error(404, "Không tìm thấy cảnh video.", "VIDEO_SCENE_NOT_FOUND")
    return status


@router.get("/projects/{project_id}/scenes/{scene_id}/voice/download")
async def download_video_scene_voice(
    project_id: str,
    scene_id: str,
    db: Session = Depends(get_db),
):
    result = video_voice.get_scene_audio_download(project_id, scene_id, db)
    if result is None:
        raise _error(404, "Chưa có file giọng đọc hoàn tất cho scene này.", "VIDEO_SCENE_AUDIO_NOT_FOUND")
    filename, path = result
    return FileResponse(
        path,
        media_type=_audio_media_type(path),
        headers={"Content-Disposition": safe_content_disposition("attachment", filename)},
    )


@router.post(
    "/projects/{project_id}/shots/{shot_id}/voice",
    response_model=models.VideoShotVoiceStatusResponse,
)
async def create_video_shot_voice(
    project_id: str,
    shot_id: str,
    data: models.VideoSceneNarrationRequest,
    db: Session = Depends(get_db),
):
    try:
        status = await video_voice.create_shot_narration(project_id, shot_id, data, db)
    except video_voice.VideoVoiceError as exc:
        raise _error(
            400,
            str(exc),
            exc.error_code,
            exc=exc,
            project_id=project_id,
            shot_id=shot_id,
            step_name="shot_voice_generation",
        ) from exc
    if status is None:
        raise _error(404, "Không tìm thấy shot video.", "VIDEO_SHOT_NOT_FOUND")
    return status


@router.get(
    "/projects/{project_id}/shots/{shot_id}/voice/status",
    response_model=models.VideoShotVoiceStatusResponse,
)
async def get_video_shot_voice_status(
    project_id: str,
    shot_id: str,
    db: Session = Depends(get_db),
):
    status = video_voice.sync_shot_voice_status(project_id, shot_id, db)
    if status is None:
        raise _error(404, "Không tìm thấy shot video.", "VIDEO_SHOT_NOT_FOUND")
    return status


@router.get("/projects/{project_id}/shots/{shot_id}/voice/download")
async def download_video_shot_voice(
    project_id: str,
    shot_id: str,
    db: Session = Depends(get_db),
):
    result = video_voice.get_shot_audio_download(project_id, shot_id, db)
    if result is None:
        raise _error(404, "Chưa có file giọng đọc hoàn tất cho shot này.", "VIDEO_SHOT_AUDIO_NOT_FOUND")
    filename, path = result
    return FileResponse(
        path,
        media_type=_audio_media_type(path),
        headers={"Content-Disposition": safe_content_disposition("attachment", filename)},
    )


@router.post("/projects/{project_id}/subtitle", response_model=models.VideoSubtitleResponse)
async def generate_video_subtitle(project_id: str, db: Session = Depends(get_db)):
    try:
        return video_subtitles.generate_subtitle(project_id, db)
    except video_subtitles.VideoSubtitleError as exc:
        raise _error(
            400, str(exc), exc.error_code, exc=exc, project_id=project_id, step_name="subtitle_generation"
        ) from exc


@router.get("/projects/{project_id}/subtitle", response_model=models.VideoSubtitleResponse)
async def get_video_subtitle(project_id: str, db: Session = Depends(get_db)):
    subtitle = video_subtitles.get_subtitle(project_id, db)
    if subtitle is None:
        raise _error(404, "Chưa có phụ đề cho dự án này.", "VIDEO_SUBTITLE_NOT_FOUND")
    return subtitle


@router.get("/projects/{project_id}/subtitle/download")
async def download_video_subtitle(project_id: str, db: Session = Depends(get_db)):
    result = video_subtitles.get_subtitle_download(project_id, db)
    if result is None:
        raise _error(404, "Chưa có file phụ đề hoàn tất cho dự án này.", "VIDEO_SUBTITLE_NOT_FOUND")
    filename, content = result
    return Response(
        content=content,
        media_type="application/x-subrip; charset=utf-8",
        headers={"Content-Disposition": safe_content_disposition("attachment", filename)},
    )


@router.get("/projects/{project_id}/render/readiness", response_model=models.VideoRenderReadinessResponse)
async def get_video_render_readiness(
    project_id: str,
    resolution: str = Query("auto", pattern="^(auto|720p|1080p)$"),
    fps: int = Query(30, ge=12, le=60),
    fit_mode: str = Query("crop", pattern="^(crop|pad)$"),
    duration_mode: str = Query("freeze", pattern="^(freeze|trim_only)$"),
    subtitle_mode: str = Query("burn_in", pattern="^(burn_in|sidecar|none)$"),
    mute_clip_audio: bool = Query(True),
    enhanced_render: bool = Query(False),
    enhanced_audio: bool = Query(True),
    ai_review: bool = Query(True),
    max_fix_attempts: int = Query(1, ge=0, le=2),
    db: Session = Depends(get_db),
):
    settings = models.VideoRenderSettings(
        resolution=resolution,
        fps=fps,
        fit_mode=fit_mode,
        duration_mode=duration_mode,
        subtitle_mode=subtitle_mode,
        mute_clip_audio=mute_clip_audio,
        enhanced_render=enhanced_render,
        enhanced_audio=enhanced_audio,
        ai_review=ai_review,
        max_fix_attempts=max_fix_attempts,
    )
    readiness = video_rendering.get_render_readiness(project_id, db, settings)
    if readiness is None:
        raise _error(404, "Không tìm thấy dự án video.", "VIDEO_PROJECT_NOT_FOUND")
    return readiness

@router.get("/projects/{project_id}/render/sfx-assets", response_model=list[models.VideoRenderSfxAssetResponse])
async def list_video_render_sfx_assets(project_id: str, db: Session = Depends(get_db)):
    assets = video_rendering.list_render_sfx_assets(project_id, db)
    if assets is None:
        raise _error(404, "Không tìm thấy dự án video.", "VIDEO_PROJECT_NOT_FOUND")
    return assets

@router.post("/projects/{project_id}/render/sfx-assets", response_model=models.VideoRenderSfxAssetResponse)
async def upload_video_render_sfx_asset(
    project_id: str,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
):
    try:
        asset = video_rendering.upload_render_sfx_asset(
            project_id,
            filename=file.filename or "sfx.wav",
            content_type=file.content_type,
            data=await file.read(),
            db=db,
        )
    except video_rendering.VideoRenderError as exc:
        raise _error(400, str(exc), exc.error_code, exc=exc, project_id=project_id, step_name="video_render_sfx_asset") from exc
    if asset is None:
        raise _error(404, "Không tìm thấy dự án video.", "VIDEO_PROJECT_NOT_FOUND")
    return asset

@router.delete("/projects/{project_id}/render/sfx-assets/{asset_id}")
async def delete_video_render_sfx_asset(project_id: str, asset_id: str, db: Session = Depends(get_db)):
    deleted = video_rendering.delete_render_sfx_asset(project_id, asset_id, db)
    if deleted is None:
        raise _error(404, "Không tìm thấy dự án video.", "VIDEO_PROJECT_NOT_FOUND")
    if not deleted:
        raise _error(404, "Không tìm thấy asset SFX/BGM.", "VIDEO_RENDER_SFX_ASSET_NOT_FOUND")
    return {"deleted": True}


@router.get("/projects/{project_id}/render/jobs", response_model=list[models.VideoRenderJobResponse])
async def list_video_render_jobs(project_id: str, db: Session = Depends(get_db)):
    return video_rendering.list_render_jobs(project_id, db)


@router.post("/projects/{project_id}/render/jobs", response_model=models.VideoRenderJobResponse)
async def create_video_render_job(
    project_id: str,
    data: models.VideoRenderJobCreateRequest | None = None,
    db: Session = Depends(get_db),
):
    try:
        job = await video_rendering.create_render_job(project_id, data or models.VideoRenderJobCreateRequest(), db)
    except video_rendering.VideoRenderError as exc:
        raise _error(
            400, str(exc), exc.error_code, exc=exc, project_id=project_id, step_name="video_render_job"
        ) from exc
    if job is None:
        raise _error(404, "Không tìm thấy dự án video.", "VIDEO_PROJECT_NOT_FOUND")
    return job


@router.get("/projects/{project_id}/render/jobs/latest", response_model=models.VideoRenderJobResponse | None)
async def get_latest_video_render_job(project_id: str, db: Session = Depends(get_db)):
    project_exists = db.query(DBVideoProject.id).filter(DBVideoProject.id == project_id).first()
    if project_exists is None:
        raise _error(404, "Không tìm thấy dự án video.", "VIDEO_PROJECT_NOT_FOUND")
    job = video_rendering.get_latest_render_job(project_id, db)
    return job


@router.get("/projects/{project_id}/render/jobs/{job_id}", response_model=models.VideoRenderJobResponse)
async def get_video_render_job(project_id: str, job_id: str, db: Session = Depends(get_db)):
    job = video_rendering.get_render_job(project_id, job_id, db)
    if job is None:
        raise _error(404, "Không tìm thấy render job.", "VIDEO_RENDER_JOB_NOT_FOUND")
    return job


@router.get("/projects/{project_id}/render/jobs/{job_id}/download")
async def download_video_render_job(project_id: str, job_id: str, db: Session = Depends(get_db)):
    result = video_rendering.get_render_download(project_id, job_id, db)
    if result is None:
        raise _error(404, "File MP4 render không còn tồn tại hoặc job chưa hoàn tất.", "VIDEO_RENDER_OUTPUT_NOT_FOUND")
    filename, path = result
    return FileResponse(
        path,
        media_type="video/mp4",
        headers={"Content-Disposition": safe_content_disposition("attachment", filename)},
    )


@router.get("/projects/{project_id}/render/jobs/{job_id}/enhanced-artifacts/{artifact_key:path}")
async def download_video_render_enhanced_artifact(
    project_id: str,
    job_id: str,
    artifact_key: str,
    db: Session = Depends(get_db),
):
    result = video_rendering.get_enhanced_render_artifact_download(project_id, job_id, artifact_key, db)
    if result is None:
        raise _error(404, "File enhanced render report không còn tồn tại hoặc job chưa tạo artifact.", "VIDEO_RENDER_ARTIFACT_NOT_FOUND")
    filename, path = result
    return FileResponse(
        path,
        media_type=mimetypes.guess_type(filename)[0] or "application/octet-stream",
        headers={"Content-Disposition": safe_content_disposition("attachment", filename)},
    )

@router.get("/projects/{project_id}/package/readiness", response_model=models.VideoPackageReadinessResponse)
async def get_video_package_readiness(project_id: str, db: Session = Depends(get_db)):
    readiness = video_packages.get_package_readiness(project_id, db)
    if readiness is None:
        raise _error(404, "Không tìm thấy dự án video.", "VIDEO_PROJECT_NOT_FOUND")
    return readiness


@router.post("/projects/{project_id}/package", response_model=models.VideoPackageExportResponse)
async def create_video_package(project_id: str, db: Session = Depends(get_db)):
    try:
        package = video_packages.create_package(project_id, db)
    except video_packages.VideoPackageError as exc:
        raise _error(400, str(exc), exc.error_code, exc=exc, project_id=project_id, step_name="package_export") from exc
    if package is None:
        raise _error(404, "Không tìm thấy dự án video.", "VIDEO_PROJECT_NOT_FOUND")
    return package


@router.get("/projects/{project_id}/package", response_model=models.VideoPackageExportResponse)
async def get_video_package(project_id: str, db: Session = Depends(get_db)):
    package = video_packages.get_latest_package(project_id, db)
    if package is None:
        raise _error(404, "Chưa có gói nguyên liệu cho dự án này.", "VIDEO_PACKAGE_NOT_FOUND")
    return package


@router.get("/projects/{project_id}/package/download")
async def download_video_package(project_id: str, db: Session = Depends(get_db)):
    result = video_packages.get_package_download(project_id, db)
    if result is None:
        raise _error(404, "Chưa có file ZIP nguyên liệu hoàn tất hoặc gói hiện tại đã cũ.", "VIDEO_PACKAGE_NOT_FOUND")
    filename, path = result
    return FileResponse(
        path,
        media_type="application/zip",
        headers={"Content-Disposition": safe_content_disposition("attachment", filename)},
    )
