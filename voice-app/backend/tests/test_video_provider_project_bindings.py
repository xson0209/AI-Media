from __future__ import annotations

from datetime import datetime

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from backend.database import (
    Base,
    VideoClipGenerationJob as DBVideoClipGenerationJob,
    VideoProject as DBVideoProject,
    VideoProviderSession as DBVideoProviderSession,
    VideoSeries as DBVideoSeries,
)
from backend.services import video_clip_generation, video_provider_project_bindings


def _db(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'bindings.db'}")
    Base.metadata.create_all(bind=engine)
    session = sessionmaker(autocommit=False, autoflush=False, bind=engine)()
    return engine, session


def _project(db, *, series_id: str | None = None) -> DBVideoProject:
    row = DBVideoProject(
        title="Video",
        topic="Topic",
        phase="phase2",
        series_id=series_id,
        package_stale=False,
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow(),
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


def test_binding_url_validation_requires_https_exact_labs_google():
    valid = "https://labs.google/fx/tools/flow/project/abc"

    assert video_provider_project_bindings.safe_provider_project_url(valid) == valid
    assert video_provider_project_bindings.safe_provider_project_url("http://labs.google/fx/tools/flow/project/abc") is None
    assert video_provider_project_bindings.safe_provider_project_url("https://evillabs.google/fx/tools/flow/project/abc") is None
    assert video_provider_project_bindings.safe_provider_project_url("https://labs.google/fx/tools/flow") is None


def test_series_project_uses_series_binding_not_project_binding(tmp_path):
    engine, db = _db(tmp_path)
    try:
        series = DBVideoSeries(title="Series", created_at=datetime.utcnow(), updated_at=datetime.utcnow())
        db.add(series)
        db.commit()
        db.refresh(series)
        project = _project(db, series_id=series.id)

        binding = video_provider_project_bindings.upsert_binding_for_project(
            project,
            db,
            provider_project_url="https://labs.google/fx/tools/flow/project/series-one",
        )

        assert binding is not None
        assert binding.series_id == series.id
        assert binding.project_id is None
        response = video_provider_project_bindings.binding_for_project_response(project, db)
        assert response is not None
        assert response.scope == "series"
        assert response.provider_project_ref_hash
    finally:
        db.close()
        engine.dispose()


def test_series_episode_reuses_existing_series_binding(tmp_path):
    engine, db = _db(tmp_path)
    try:
        series = DBVideoSeries(title="Series", created_at=datetime.utcnow(), updated_at=datetime.utcnow())
        db.add(series)
        db.commit()
        db.refresh(series)
        first = _project(db, series_id=series.id)
        second = _project(db, series_id=series.id)

        binding = video_provider_project_bindings.upsert_binding_for_project(
            first,
            db,
            provider_project_url="https://labs.google/fx/tools/flow/project/series-shared",
        )
        reused = video_provider_project_bindings.active_binding_for_project(second, db)

        assert binding is not None
        assert reused is not None
        assert reused.id == binding.id
        assert reused.series_id == series.id
        assert reused.project_id is None
    finally:
        db.close()
        engine.dispose()


def test_series_active_veo_job_blocks_other_episode(tmp_path):
    engine, db = _db(tmp_path)
    try:
        series = DBVideoSeries(title="Series", created_at=datetime.utcnow(), updated_at=datetime.utcnow())
        db.add(series)
        db.commit()
        db.refresh(series)
        first = _project(db, series_id=series.id)
        second = _project(db, series_id=series.id)
        db.add(
            DBVideoClipGenerationJob(
                project_id=first.id,
                session_id="session-1",
                provider="veo",
                status="running",
                current_step="waiting_generation",
                created_at=datetime.utcnow(),
                updated_at=datetime.utcnow(),
            )
        )
        db.commit()

        with pytest.raises(video_clip_generation.VideoClipGenerationError) as exc:
            video_clip_generation._ensure_project_can_start_clip_generation(second.id, db)

        assert exc.value.error_code == "VIDEO_CLIP_SERIES_BUSY_VEO_JOB"
    finally:
        db.close()
        engine.dispose()


def test_standalone_project_reuses_active_binding(tmp_path):
    engine, db = _db(tmp_path)
    try:
        project = _project(db)

        binding = video_provider_project_bindings.upsert_binding_for_project(
            project,
            db,
            provider_project_url="https://labs.google/fx/tools/flow/project/standalone",
        )
        reused = video_provider_project_bindings.active_binding_for_project(project, db)

        assert binding is not None
        assert reused is not None
        assert reused.id == binding.id
        assert reused.project_id == project.id
        assert reused.series_id is None
    finally:
        db.close()
        engine.dispose()


def test_binding_upsert_does_not_rotate_on_callback_mismatch(tmp_path):
    engine, db = _db(tmp_path)
    try:
        project = _project(db)
        first = video_provider_project_bindings.upsert_binding_for_project(
            project,
            db,
            provider_project_url="https://labs.google/fx/tools/flow/project/first",
        )
        second = video_provider_project_bindings.upsert_binding_for_project(
            project,
            db,
            provider_project_url="https://labs.google/fx/tools/flow/project/redirected",
        )

        assert first is not None
        assert second is not None
        assert second.id == first.id
        assert second.status == "active"
        assert second.provider_project_ref_hash == first.provider_project_ref_hash
        assert db.query(video_provider_project_bindings.DBVideoProviderProjectBinding).count() == 1
    finally:
        db.close()
        engine.dispose()


def test_invalid_binding_can_rotate_to_new_active_binding(tmp_path):
    engine, db = _db(tmp_path)
    try:
        project = _project(db)
        first = video_provider_project_bindings.upsert_binding_for_project(
            project,
            db,
            provider_project_url="https://labs.google/fx/tools/flow/project/old",
        )
        assert first is not None

        video_provider_project_bindings.mark_binding_invalid(first, db, reason="Project not found")
        second = video_provider_project_bindings.upsert_binding_for_project(
            project,
            db,
            provider_project_url="https://labs.google/fx/tools/flow/project/new",
        )

        assert second is not None
        assert second.id != first.id
        assert second.status == "active"
        assert db.query(video_provider_project_bindings.DBVideoProviderProjectBinding).count() == 2
        db.refresh(first)
        assert first.status == "invalid"
    finally:
        db.close()
        engine.dispose()


def test_job_response_redacts_legacy_provider_project_url(tmp_path, monkeypatch):
    engine, db = _db(tmp_path)
    try:
        project = _project(db)
        session = DBVideoProviderSession(
            provider="veo",
            provider_tool="veo3_flow",
            status="ready",
            chrome_profile_path=str(tmp_path / "profile"),
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
        )
        db.add(session)
        db.commit()
        db.refresh(session)
        legacy_url = "https://labs.google/fx/tools/flow/project/leaked"
        job = DBVideoClipGenerationJob(
            project_id=project.id,
            session_id=session.id,
            status="queued",
            current_step="validate",
            step_results_json={"provider_project_url": legacy_url, "events": [{"provider_project_url": legacy_url}]},
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
        )
        db.add(job)
        db.commit()
        db.refresh(job)
        monkeypatch.setattr(video_clip_generation.video_rendering, "get_render_readiness", lambda *_args, **_kwargs: None)

        response = video_clip_generation.job_response(job, db)

        dumped = response.model_dump_json()
        assert legacy_url not in dumped
        assert "provider_project_ref_hash" in dumped
    finally:
        db.close()
        engine.dispose()
