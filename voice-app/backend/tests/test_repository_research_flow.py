from __future__ import annotations

import hashlib
import io
import json
from pathlib import Path
from types import SimpleNamespace

import pytest
from PIL import Image

from backend import config, database, models
from backend.database import session as database_session
from backend.services import research, video_projects, video_rendering, video_source_visuals, video_storage

COMPLETE_COMPONENTS = {
    "hook": 8,
    "structure": 8,
    "conflict_emotion": 8,
    "retention": 8,
    "originality": 8,
    "series_potential": 8,
    "feasibility": 8,
}


@pytest.fixture
def db(tmp_path):
    config.set_data_dir(tmp_path)
    database.init_db()
    session = database_session.SessionLocal()
    try:
        yield session
    finally:
        session.close()
        database_session.engine.dispose()


def _fingerprint(payload: dict) -> str:
    return hashlib.sha256(json.dumps(payload, ensure_ascii=False, sort_keys=True).encode()).hexdigest()


def _repository_package(source_id: str) -> dict:
    commit_sha = "a" * 40
    evidence = {
        "id": f"repo:{source_id}:readme:1",
        "kind": "repository_file",
        "source_id": source_id,
        "path": "README.md",
        "line_start": 1,
        "line_end": 3,
        "url": f"https://github.com/acme/demo/blob/{commit_sha}/README.md#L1-L3",
        "excerpt": "Demo is a command line tool for inspecting source files.",
    }
    package = {
        "schema_version": "research_source_package.v1",
        "source_id": source_id,
        "source_type": "github_repo",
        "revision": 1,
        "repository": {
            "url": "https://github.com/acme/demo",
            "requested_ref": "main",
            "commit_sha": commit_sha,
        },
        "documents": [{"path": "README.md", "commit_sha": commit_sha}],
        "evidence_refs": [evidence],
        "coverage": {"executed": False, "tree_complete": True},
        "limitations": ["Chưa chạy code hoặc benchmark."],
    }
    package["fingerprint"] = _fingerprint(package)
    return package


def test_repository_study_and_screenshot_handoff_are_project_owned(db):
    project = research.create_project(
        models.ResearchProjectCreate(
            title="GitHub explainer",
            brief="Giải thích repo này làm gì và minh họa bằng screenshot.",
        ),
        db,
    )

    repo_response = research.add_text_source(
        project.id,
        models.ResearchSourceTextCreate(
            source_type="github_repo",
            title="Demo repository",
            input_url="https://github.com/acme/demo",
            repository_ref="main",
        ),
        db,
    )
    repo = db.query(database.ResearchSource).filter_by(id=repo_response.id).one()
    repo_package = _repository_package(repo.id)
    repo.status = "ready_for_review"
    repo.result_json = repo_package
    repo.source_hash = repo_package["fingerprint"]
    repo.provenance_json = {"repository_ref": "main"}
    db.commit()

    image_buffer = io.BytesIO()
    Image.new("RGB", (320, 180), "#182235").save(image_buffer, format="PNG")
    screen_response = research.add_upload_source(
        project.id,
        "screenshot_upload",
        "README screenshot",
        "screen.png",
        image_buffer.getvalue(),
        "image/png",
        db,
    )
    screen = db.query(database.ResearchSource).filter_by(id=screen_response.id).one()
    original_path = config.resolve_storage_path(screen.file_path)
    assert original_path is not None
    assert original_path.is_file()
    digest = hashlib.sha256(original_path.read_bytes()).hexdigest()
    screen_evidence = {
        "id": f"screen:{screen.id}:region-1",
        "kind": "screen_region",
        "source_id": screen.id,
        "asset_id": screen.id,
        "region_id": "region-1",
        "sha256": digest,
        "box": [0.1, 0.1, 0.8, 0.6],
        "excerpt": "python app.py",
        "confidence": 0.98,
    }
    screen_package = {
        "schema_version": "research_source_package.v1",
        "source_id": screen.id,
        "source_type": "screenshot_upload",
        "revision": 1,
        "evidence_refs": [screen_evidence],
        "visual_assets": [{
            "id": screen.id,
            "source_id": screen.id,
            "file_path": config.to_storage_path(original_path),
            "sha256": digest,
            "width": 320,
            "height": 180,
            "regions": [{"id": "region-1", "label": "command", "text": "python app.py", "box": [0.1, 0.1, 0.8, 0.6], "confidence": 0.98}],
        }],
        "coverage": {"original_saved": True, "vision_complete": True},
        "limitations": ["Screenshot chỉ chứng minh phần đang nhìn thấy."],
    }
    screen_package["fingerprint"] = _fingerprint(screen_package)
    screen.status = "ready_for_review"
    screen.result_json = screen_package
    screen.source_hash = screen_package["fingerprint"]
    db.commit()

    run = research.create_run(
        project.id,
        models.ResearchRunCreate(mode="creative", source_ids=[repo.id, screen.id], run_ai=False),
        db,
    )
    assert run.status == "completed"
    study = run.output["repository_study"]
    assert study["facts"]
    assert all(fact["evidence"] for fact in study["facts"])
    ideas = research.list_ideas(project.id, db)
    assert ideas
    assert all(idea.content["fact_ids"] for idea in ideas)
    assert any(idea.content.get("repository_study") for idea in ideas)

    accepted = research.update_idea_status(project.id, ideas[0].id, "accepted", db)
    assert accepted is not None
    research.score_target(
        project.id,
        models.ResearchScoreRequest(
            target_type="idea",
            target_id=ideas[0].id,
            components=COMPLETE_COMPONENTS,
            evidence_refs=[{"source_id": repo.id, "excerpt": "README evidence"}],
            run_ai=False,
        ),
        db,
    )
    handoff = research.handoff(
        project.id,
        models.ResearchHandoffCreate(
            accepted_idea_ids=[ideas[0].id],
            selected_target_id=ideas[0].id,
            idempotency_key="github-screenshot-flow",
        ),
        db,
    )

    video_project = db.query(database.VideoProject).filter_by(id=handoff.target_ai_video_project_id).one()
    assert video_project.content_genre == "developer_explainer"
    assert video_project.visual_style.startswith("preserve_source:")
    assert handoff.payload["repository_findings"]
    assert {item["source_id"] for item in handoff.payload["source_revisions"]} == {repo.id, screen.id}
    blocks = db.query(database.VideoSourceBlock).filter_by(project_id=video_project.id).all()
    assert {block.block_type for block in blocks} >= {"repository_facts", "source_visuals"}
    copied_asset = next(asset for asset in handoff.payload["visual_assets"] if asset["id"] == screen.id)
    copied_path = config.resolve_storage_path(copied_asset["file_path"])
    assert copied_path is not None
    assert copied_path.is_file()
    assert copied_path.parent.name == "source_visuals"
    assert hashlib.sha256(copied_path.read_bytes()).hexdigest() == digest


def test_repository_study_rejects_changed_source_before_handoff(db):
    project = research.create_project(models.ResearchProjectCreate(title="Stale repo"), db)
    source_response = research.add_text_source(
        project.id,
        models.ResearchSourceTextCreate(source_type="github_repo", input_url="https://github.com/acme/demo"),
        db,
    )
    source = db.query(database.ResearchSource).filter_by(id=source_response.id).one()
    package = _repository_package(source.id)
    source.status = "ready_for_review"
    source.result_json = package
    source.source_hash = package["fingerprint"]
    db.commit()
    research.create_run(project.id, models.ResearchRunCreate(mode="creative", source_ids=[source.id], run_ai=False), db)
    idea = research.list_ideas(project.id, db)[0]
    research.update_idea_status(project.id, idea.id, "accepted", db)
    research.score_target(
        project.id,
        models.ResearchScoreRequest(target_type="idea", target_id=idea.id, components=COMPLETE_COMPONENTS, run_ai=False),
        db,
    )
    source.revision += 1
    db.commit()
    with pytest.raises(research.ResearchError) as exc_info:
        research.handoff(project.id, models.ResearchHandoffCreate(accepted_idea_ids=[idea.id], idempotency_key="stale-flow"), db)
    assert exc_info.value.error_code == "RESEARCH_REPOSITORY_STUDY_STALE"


def test_explicit_general_genre_overrides_repository_default(db):
    project = research.create_project(models.ResearchProjectCreate(title="Genre override"), db)
    source_response = research.add_text_source(
        project.id,
        models.ResearchSourceTextCreate(source_type="github_repo", input_url="https://github.com/acme/demo"),
        db,
    )
    source = db.query(database.ResearchSource).filter_by(id=source_response.id).one()
    package = _repository_package(source.id)
    source.status = "ready_for_review"
    source.result_json = package
    source.source_hash = package["fingerprint"]
    db.commit()
    research.create_run(project.id, models.ResearchRunCreate(mode="creative", source_ids=[source.id], run_ai=False), db)
    idea = research.list_ideas(project.id, db)[0]
    research.update_idea_status(project.id, idea.id, "accepted", db)
    research.score_target(
        project.id,
        models.ResearchScoreRequest(target_type="idea", target_id=idea.id, components=COMPLETE_COMPONENTS, run_ai=False),
        db,
    )
    handoff = research.handoff(
        project.id,
        models.ResearchHandoffCreate(
            accepted_idea_ids=[idea.id],
            content_genre="general",
            idempotency_key="explicit-general-genre",
        ),
        db,
    )
    video_project = db.query(database.VideoProject).filter_by(id=handoff.target_ai_video_project_id).one()
    assert video_project.content_genre == "general"


def test_screenshot_clip_selection_persists_original_source_metadata(db, monkeypatch):
    visual_project = video_projects.create_project(
        models.VideoProjectCreate(
            title="Screenshot render",
            topic="Show the command",
            language="en",
            target_language="en",
            phase="phase2",
            aspect_ratio="9:16",
            visual_style=video_source_visuals.STYLE,
            source_blocks=[models.VideoSourceBlockDraft(block_type="source_visuals", content="{}")],
        ),
        db,
    )
    project_id = visual_project.id
    image_path = video_storage.get_project_subdir(project_id, "source_visuals") / "original.png"
    Image.new("RGB", (320, 180), "#182235").save(image_path)
    digest = hashlib.sha256(image_path.read_bytes()).hexdigest()
    block = db.query(database.VideoSourceBlock).filter_by(project_id=project_id, block_type="source_visuals").one()
    block.content = json.dumps({
        "schema_version": "source_visuals.v1",
        "assets": [{
            "id": "screen-1",
            "file_path": config.to_storage_path(image_path),
            "sha256": digest,
            "width": 320,
            "height": 180,
            "regions": [{"id": "region-1", "label": "command", "box": [0.1, 0.2, 0.5, 0.3]}],
        }],
    })
    shot = database.VideoShot(
        id="screen-shot-1",
        project_id=project_id,
        shot_order=1,
        duration_seconds=2,
        status="ready",
        prompt_status="ready",
        voice_status="skipped",
        subtitle_status="ready",
    )
    db.add(shot)
    db.commit()

    monkeypatch.setattr(video_rendering, "detect_tools", lambda: video_rendering.FFmpegTools("fake-ffmpeg", None))
    monkeypatch.setattr(
        video_rendering,
        "probe_clip",
        lambda _path: video_rendering.ClipMetadata(2.0, 720, 1280, 30.0, "h264", False),
    )

    def fake_run(command, **_kwargs):
        Path(command[-1]).write_bytes(b"fake-mp4")
        return SimpleNamespace(returncode=0, stderr="", stdout="")

    monkeypatch.setattr(video_source_visuals.subprocess, "run", fake_run)
    clip = video_source_visuals.create_clip(
        project_id,
        shot.id,
        models.VideoScreenshotClipCreate(asset_id="screen-1", region_id="region-1", motion="zoom", highlight=True),
        db,
    )
    assert clip.source == "screenshot"
    assert clip.status == "ready"
    assert clip.provider == "original_screenshot"
    assert clip.provider_metadata["source_visual"] == {"asset_id": "screen-1", "region_id": "region-1", "motion": "zoom", "highlight": True}
    db.refresh(shot)
    assert shot.retention_json["source_visual"]["asset_id"] == "screen-1"
    assert shot.retention_json["source_visual"]["highlight"] is True

    with pytest.raises(video_source_visuals.SourceVisualError):
        video_source_visuals.create_clip(
            project_id,
            shot.id,
            models.VideoScreenshotClipCreate(asset_id="screen-1", region_id="missing-region"),
            db,
        )
