from unittest.mock import Mock

from backend import models
from backend.api.routes import register_routers
from backend.api.routes.ai_video import router as layered_ai_video_router
from backend.api.routes.health import router as layered_health_router
from backend.features.ai_video import auto_runs, projects, render, schemas, subtitles
from backend.features.ai_video.repository import VideoProject, get_project
from backend.routes import register_routers as legacy_register_routers
from backend.routes.ai_video import router as legacy_ai_video_router
from backend.routes.health import router as legacy_health_router
from backend.services import (
    video_auto_runs,
    video_projects,
    video_rendering,
    video_subtitles,
)


def test_api_route_namespace_bridges_legacy_routes():
    assert register_routers is legacy_register_routers
    assert layered_health_router is legacy_health_router
    assert layered_ai_video_router is legacy_ai_video_router


def test_ai_video_feature_bridges_existing_services():
    assert projects.list_projects is video_projects.list_projects
    assert auto_runs.start_auto_run is video_auto_runs.start_auto_run
    assert render.get_render_readiness is video_rendering.get_render_readiness
    assert subtitles.generate_subtitle is video_subtitles.generate_subtitle


def test_ai_video_schema_bridge_keeps_public_models():
    assert schemas.VideoProjectResponse is models.VideoProjectResponse
    assert schemas.VideoRenderJobResponse is models.VideoRenderJobResponse
    assert schemas.VideoSubtitleResponse is models.VideoSubtitleResponse


def test_ai_video_repository_get_project_queries_by_id():
    query = Mock()
    query.filter.return_value.first.return_value = "project-row"
    db = Mock()
    db.query.return_value = query

    assert get_project(db, "project-1") == "project-row"
    db.query.assert_called_once_with(VideoProject)
    query.filter.assert_called_once()
