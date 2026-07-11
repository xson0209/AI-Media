"""Local resource status and cleanup endpoints."""

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from .. import models
from ..database import get_db
from ..features.ai_video.render import clear_render_intermediate_cache
from ..features.ai_video.resources import get_resource_manager

router = APIRouter()


@router.get("/resources/status", response_model=models.ResourceStatusResponse)
async def get_resource_status(db: Session = Depends(get_db)):
    """Return RAM/GPU/model/cache state relevant to local AI Video workflows."""
    return get_resource_manager().status(db)


@router.post("/resources/cleanup", response_model=models.ResourceCleanupResponse)
async def cleanup_resources(
    request: models.ResourceCleanupRequest = models.ResourceCleanupRequest(),
    db: Session = Depends(get_db),
):
    """Free idle RAM/GPU resources without interrupting active jobs."""
    manager = get_resource_manager()
    actions = manager.cleanup(
        db=db,
        unload_idle_models=request.unload_idle_models,
        clear_voice_prompt_memory=request.clear_voice_prompt_memory,
        clear_mlx_cache=request.clear_mlx_cache,
        clear_render_cache=request.clear_render_cache,
        render_cache_project_id=request.render_cache_project_id,
    )
    return {
        "actions": [action.as_dict() for action in actions],
        "status": manager.status(db),
    }


@router.post("/resources/render-cache/clear", response_model=models.RenderCacheClearResponse)
async def clear_render_cache(
    request: models.RenderCacheClearRequest = models.RenderCacheClearRequest(),
    db: Session = Depends(get_db),
):
    """Clear AI Video render intermediate cache globally or for one project."""
    return clear_render_intermediate_cache(project_id=request.project_id, db=db)
