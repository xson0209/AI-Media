"""Unified content repurposing route for the three short-video tools."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from starlette.concurrency import run_in_threadpool

from .. import models
from ..database import get_db
from ..services import ai_planning, content_tools, research_ai, settings as settings_service

router = APIRouter(prefix="/content-tools", tags=["content-tools"])


@router.post("/generate", response_model=models.ContentToolsGenerateResponse)
async def generate_content_tool(
    request: models.ContentToolsGenerateRequest,
    db: Session = Depends(get_db),
):
    """Generate a reviewable script and video prompt pack."""
    settings = settings_service.get_ai_planning_settings(db)
    try:
        return await run_in_threadpool(content_tools.generate_content_tool, request, settings)
    except content_tools.ContentToolsError as exc:
        raise HTTPException(status_code=502, detail={"message": str(exc), "error_code": exc.error_code}) from exc
    except (research_ai.ResearchCLIError, ai_planning.AIPlanningError) as exc:
        error_code = getattr(exc, "error_code", "CONTENT_TOOLS_PROVIDER_ERROR")
        raise HTTPException(
            status_code=502,
            detail={"message": str(exc), "error_code": error_code},
        ) from exc
