"""Contract tests for the isolated, prompt-only product-video workflow."""

from __future__ import annotations

from types import SimpleNamespace

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import inspect

from backend import config, database, models
from backend.database import (
    ProductVideoShot as DBProductVideoShot,
    VideoProject as DBVideoProject,
    VideoShot as DBVideoShot,
    VideoShotPrompt as DBVideoShotPrompt,
)
from backend.database import migrations, session as database_session
from backend.routes.product_video import router as product_video_router
from backend.services import product_video, video_purpose


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


@pytest.fixture
def client(db):
    app = FastAPI()
    app.include_router(product_video_router)
    app.dependency_overrides[database.get_db] = lambda: db
    return TestClient(app)


def payload(**overrides):
    base = {
        "topic": "Nước ép trái cây đóng chai, vị cam tự nhiên",
        "target_language": "vi",
        "aspect_ratio": "9:16",
        "video_purpose": "sales_ad",
        "target_duration_seconds": 30,
        "visual_style": "A hand lifts the labelled bottle while background light moves softly.",
        "visual_style_preset": "ugc_street",
        "prompt_segment_duration_seconds": 8,
        "micro_scenes_per_prompt": 3,
    }
    base.update(overrides)
    return base


def create_project(client, **overrides):
    response = client.post("/product-video/projects", json=payload(**overrides))
    assert response.status_code == 200, response.text
    return response.json()


def add_shots(project_id, db, *, language="vi"):
    project = product_video.get_project_row(project_id, db)
    project.target_language = language
    project.hook_text = "Bạn có nhận ra điểm khác biệt ngay trong hai giây đầu không?"
    for order, (shot_type, framing) in enumerate(
        [("dramatic wide establishing", "medium shot"), ("macro detail", "close-up")], start=1
    ):
        db.add(
            DBProductVideoShot(
                project_id=project_id,
                shot_order=order,
                shot_type=shot_type,
                framing=framing,
                camera_angle="eye level",
                composition="The product label is centered and fully readable.",
                camera_motion="slow push in" if order == 1 else "",
                subject_motion="" if order == 1 else "a hand gently lifts the product",
                environment_motion="none",
                lighting="soft product key light",
                mood="confident and inviting",
                duration_seconds=8,
                beat_role="hook" if order == 1 else "proof",
                narration_text="Sản phẩm này giúp bạn chọn nhanh hơn mỗi ngày." if language == "vi" else "This product makes everyday choices easier.",
                retention_notes="Show a clear visual change immediately and leave a question for the next clip.",
                transition_notes="Cut on the hand movement into the next close detail.",
                sound_design_notes="Soft room ambience and a tactile packaging sound under narration.",
            )
        )
    db.commit()


def test_schema_is_created_and_product_migration_is_idempotent(db):
    tables = set(inspect(database_session.engine).get_table_names())
    assert {"product_video_projects", "product_video_shots", "product_video_shot_prompts"}.issubset(tables)
    migrations._migrate_product_video(database_session.engine)
    assert "idx_product_video_shots_project_order" in {
        item["name"] for item in inspect(database_session.engine).get_indexes("product_video_shots")
    }


@pytest.mark.parametrize(
    ("override", "expected"),
    [
        ({"aspect_ratio": "1:1"}, 422),
        ({"target_duration_seconds": 10}, 422),
        ({"target_duration_seconds": 240}, 422),
    ],
)
def test_request_validation(client, override, expected):
    assert client.post("/product-video/projects", json=payload(**override)).status_code == expected


def test_unknown_style_preset_is_stored_and_purpose_preset_applies(client):
    project = create_project(client, visual_style_preset="mot_preset_chua_ton_tai")
    expected = video_purpose.resolve_purpose_settings(
        video_purpose="sales_ad", target_language="vi", dialogue_mode=None, narration_density=None, call_to_action_style=None
    )
    assert project["visual_style_preset"] == "mot_preset_chua_ton_tai"
    assert project["target_language"] == expected["target_language"]
    assert project["narration_density"] == expected["narration_density"]
    assert project["call_to_action_style"] == expected["call_to_action_style"]


def test_derived_duration_is_honest_for_fifteen_seconds(client):
    project = create_project(client, target_duration_seconds=15, prompt_segment_duration_seconds=8)
    assert project["derived_clip_count"] == 2
    assert project["derived_duration_seconds"] == 16


def test_creation_configuration_matches_ai_video_controls_and_persists(client):
    project = create_project(
        client,
        dialogue_mode="mixed",
        narration_density="dense",
        call_to_action_style="urgent",
        creation_mode="manual",
        automation_mode="review_gated",
        output_target="prompt_pack",
    )
    assert project["dialogue_mode"] == "mixed"
    assert project["narration_density"] == "dense"
    assert project["call_to_action_style"] == "urgent"
    assert project["creation_mode"] == "manual"
    assert project["automation_mode"] == "review_gated"
    assert project["output_target"] == "prompt_pack"

    updated = client.put(
        f"/product-video/projects/{project['id']}",
        json={"creation_mode": "quick", "automation_mode": "full_auto", "output_target": "render_ready"},
    )
    assert updated.status_code == 200, updated.text
    body = updated.json()
    assert body["creation_mode"] == "quick"
    assert body["automation_mode"] == "full_auto"
    assert body["output_target"] == "render_ready"


def test_product_video_syncs_shared_render_bridge(client, db):
    project = create_project(client)
    bridge_id = project["render_project_id"]
    assert bridge_id
    assert db.query(DBVideoProject).filter(DBVideoProject.id == bridge_id).count() == 1

    add_shots(project["id"], db)
    assert client.post(f"/product-video/projects/{project['id']}/prompts").status_code == 200
    detail = client.get(f"/product-video/projects/{project['id']}")
    assert detail.status_code == 200, detail.text
    body = detail.json()
    assert body["render_project_id"] == bridge_id
    assert len(body["render_shots"]) == 2
    assert db.query(DBVideoShot).filter(DBVideoShot.project_id == bridge_id).count() == 2
    assert db.query(DBVideoShotPrompt).filter(DBVideoShotPrompt.project_id == bridge_id).count() == 2


def test_product_video_delete_removes_render_bridge(client, db):
    project = create_project(client)
    bridge_id = project["render_project_id"]
    response = client.delete(f"/product-video/projects/{project['id']}")
    assert response.status_code == 200, response.text
    assert db.query(DBVideoProject).filter(DBVideoProject.id == bridge_id).count() == 0


def test_prompt_pack_enforces_fidelity_motion_variety_vocabulary_and_vietnamese_speech(client, db):
    project = create_project(client)
    add_shots(project["id"], db)
    response = client.post(f"/product-video/projects/{project['id']}/prompts")
    assert response.status_code == 200, response.text
    pack = response.json()
    assert len(pack["prompts"]) == 2
    assert all(product_video.PRODUCT_FIDELITY_HEADING in row["prompt"] for row in pack["prompts"])
    assert all("Retention notes:" in row["prompt"] for row in pack["prompts"])
    assert all("Transition notes:" in row["prompt"] for row in pack["prompts"])
    assert all("Sound design notes:" in row["prompt"] for row in pack["prompts"])
    assert "Hook for the first 0-2 seconds:" in pack["prompts"][0]["prompt"]
    assert "Vietnamese spoken dialogue" in pack["prompts"][0]["prompt"]
    assert "18 to 20 Vietnamese words" in pack["prompts"][0]["prompt"]

    shots = product_video.ordered_shots(project["id"], db)
    assert all(shot.shot_type in product_video.PRODUCT_SHOT_TYPES for shot in shots)
    assert shots[0].shot_type == "hero shot"
    assert all(product_video.non_blank_motion_count(shot) >= 2 for shot in shots)
    assert all("none" not in (shot.environment_motion or "").lower() for shot in shots)
    assert not (shots[0].shot_type == shots[1].shot_type and shots[0].framing == shots[1].framing)


def test_non_vietnamese_pack_does_not_append_vietnamese_speech(client, db):
    project = create_project(client, target_language="en")
    add_shots(project["id"], db, language="en")
    response = client.post(f"/product-video/projects/{project['id']}/prompts")
    assert response.status_code == 200, response.text
    assert "Vietnamese spoken dialogue" not in response.json()["prompts"][0]["prompt"]


def test_motion_normalisation_treats_static_tokens_as_blank():
    shot = SimpleNamespace(camera_motion="static", subject_motion="n/a", environment_motion="none")
    project = SimpleNamespace(visual_style="moving light behind the product", visual_style_preset="studio_beauty")
    assert product_video.is_blank_motion("Environment motion: none") is False
    assert product_video.is_blank_motion("none") is True
    assert product_video.validate_motion_budget(shot, project) is True
    assert product_video.non_blank_motion_count(shot) >= 2


def test_prompt_pack_download_and_no_render_generation_endpoints(client, db):
    project = create_project(client)
    add_shots(project["id"], db)
    assert client.post(f"/product-video/projects/{project['id']}/prompts").status_code == 200
    download = client.get(f"/product-video/projects/{project['id']}/prompt-pack")
    assert download.status_code == 200
    assert "Shot 1" in download.text
    routes = {route.path for route in product_video_router.routes}
    assert not any("render" in route or "clip" in route or "voice" in route for route in routes if route.startswith("/product-video"))
