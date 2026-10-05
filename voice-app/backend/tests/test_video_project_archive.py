from types import SimpleNamespace

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from backend import models
from backend.database.models import Base, VideoProject
from backend.features.ai_video import projects


def test_project_archive_keeps_row_and_supports_restore(tmp_path, monkeypatch):
    engine = create_engine(f"sqlite:///{tmp_path / 'project-archive.db'}")
    Base.metadata.create_all(engine)
    monkeypatch.setattr(projects, "_validate_project_operation_available", lambda *args, **kwargs: None)
    monkeypatch.setattr(
        projects,
        "_project_response",
        lambda row, _db: SimpleNamespace(archived=row.archived_at is not None),
    )

    with Session(engine) as db:
        db.add(
            VideoProject(
                id="project-1",
                title="Archive me",
                topic="A topic",
                language="vi",
                target_language="vi",
                status="draft",
            )
        )
        db.commit()

        archived = projects.update_project("project-1", models.VideoProjectUpdate(archived=True), db)
        assert archived.archived is True
        row = db.get(VideoProject, "project-1")
        assert row is not None
        assert row.archived_at is not None

        restored = projects.update_project("project-1", models.VideoProjectUpdate(archived=False), db)
        assert restored.archived is False
        assert db.get(VideoProject, "project-1").archived_at is None

    engine.dispose()
