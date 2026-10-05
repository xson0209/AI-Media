"""Public routes and legacy callers continue to use persisted AI Video data."""

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from backend import config, database, models
from backend.database import Base, VideoAutoRun, VideoProject, VideoRenderJob, VideoShot, VideoSubtitle
from backend.features.ai_video import auto_runs, projects, render, subtitles
from backend.routes.ai_video import router
from backend.services import video_auto_runs, video_projects, video_rendering, video_storage, video_subtitles


@pytest.fixture
def db(tmp_path):
    previous_data_dir = config.get_data_dir()
    config.set_data_dir(tmp_path)
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    try:
        with Session(engine, autoflush=False) as session:
            yield session
    finally:
        engine.dispose()
        config.set_data_dir(previous_data_dir)


@pytest.fixture
def client(db):
    app = FastAPI()
    app.include_router(router)
    app.dependency_overrides[database.get_db] = lambda: db
    return TestClient(app)


def test_project_created_by_legacy_caller_reopens_through_feature_and_http(db, client):
    created = video_projects.create_project(
        models.VideoProjectCreate(topic="Saved project", title="Saved project", phase="phase2", target_language="en"),
        db,
    )
    db.add(VideoShot(project_id=created.id, shot_order=1, english_narration="Persisted narration", locked=True))
    db.commit()
    with Session(db.bind, autoflush=False) as reopened:
        detail = projects.get_project(created.id, reopened)
        assert detail.id == created.id
        assert detail.shots[0].english_narration == "Persisted narration"
        assert detail.shots[0].locked is True
    response = client.get(f"/ai-video/projects/{created.id}")
    assert response.status_code == 200
    assert response.json()["shots"][0]["english_narration"] == "Persisted narration"
    assert client.get("/ai-video/projects").json()[0]["id"] == created.id


def test_existing_render_and_subtitle_paths_download_without_rewriting(db, client):
    created = projects.create_project(models.VideoProjectCreate(topic="Artifacts", phase="phase2"), db)
    project_dir = video_storage.get_project_dir(created.id)
    render_path = project_dir / "saved-output.mp4"
    subtitle_path = project_dir / "saved-subtitle.srt"
    render_path.write_bytes(b"existing-mp4-content")
    subtitle_path.write_text("1\n00:00:00,000 --> 00:00:01,000\nĐã lưu\n", encoding="utf-8")
    job = VideoRenderJob(project_id=created.id, status="completed", output_path=str(render_path))
    subtitle = VideoSubtitle(project_id=created.id, status="completed", subtitle_path=str(subtitle_path))
    db.add_all([job, subtitle])
    db.commit()
    assert render.get_render_download(created.id, job.id, db) == video_rendering.get_render_download(
        created.id, job.id, db
    )
    assert subtitles.get_subtitle_download(created.id, db) == video_subtitles.get_subtitle_download(created.id, db)
    response = client.get(f"/ai-video/projects/{created.id}/render/jobs/{job.id}/download")
    assert response.status_code == 200
    assert response.content == b"existing-mp4-content"
    response = client.get(f"/ai-video/projects/{created.id}/subtitle/download")
    assert response.status_code == 200
    assert "Đã lưu" in response.content.decode("utf-8")
    assert job.output_path == str(render_path)
    assert subtitle.subtitle_path == str(subtitle_path)


def test_cancel_and_restart_preserve_longform_checkpoint_and_approval(db, client):
    created = projects.create_project(models.VideoProjectCreate(topic="Checkpoint", phase="phase2"), db)
    project = db.get(VideoProject, created.id)
    checkpoint = {"revision": 7, "outline_approved": True, "chapters": [{"order": 1, "narration": "Saved"}]}
    project.retention_plan_json = {"longform": checkpoint}
    running = VideoAutoRun(project_id=created.id, status="running")
    queued = VideoAutoRun(project_id=created.id, status="queued")
    db.add_all([running, queued])
    db.commit()
    assert auto_runs.sync_stale_running_runs(db) == 1
    db.expire_all()
    assert video_auto_runs.get_auto_run(created.id, running.id, db).status == "failed"
    response = client.post(f"/ai-video/projects/{created.id}/auto-runs/{queued.id}/cancel")
    assert response.status_code == 200
    assert response.json()["status"] == "cancelled"
    db.refresh(project)
    assert project.retention_plan_json["longform"] == checkpoint
