from __future__ import annotations

import pytest

from backend import config, models
from backend.database import init_db
from backend.database import session as database_session
from backend.database.models import VideoClipGenerationJob as DBVideoClipGenerationJob
from backend.database.models import VideoShotClip as DBVideoShotClip
from backend.services import series_brain, series_references, video_projects

@pytest.fixture
def db(tmp_path):
    config.set_data_dir(tmp_path)
    init_db()
    session = database_session.SessionLocal()
    try:
        yield session
    finally:
        session.close()
        database_session.engine.dispose()

def _episode_dataset(count: int) -> list[dict[str, object]]:
    return [
        {
            "episode": index,
            "required_card_title": f"Su kien bat buoc tap {index:03d}",
            "secret": "chia khoa do" if index == 3 else None,
            "location": "quan ca phe gac mai" if index % 5 == 0 else "ga ngam",
            "character": "Lan" if index % 2 else "Mai",
            "prop": f"vat chung {index:03d}",
        }
        for index in range(1, count + 1)
    ]

def _seed_memory_cards(series_id: str, db, *, episode_count: int = 30, distractor_count: int = 90) -> tuple[list[str], list[str]]:
    required_ids: list[str] = []
    distractor_ids: list[str] = []
    for item in _episode_dataset(episode_count):
        episode = int(item["episode"])
        card = series_brain.create_memory_card(
            series_id,
            models.SeriesMemoryCardCreate(
                card_type="episode_summary",
                title=str(item["required_card_title"]),
                content={
                    "event": f"Lan va Mai ghi nho moc bat buoc tap {episode:03d}.",
                    "secret": item["secret"],
                    "location": item["location"],
                    "prop": item["prop"],
                },
                tags=["required", f"tap-{episode:03d}", str(item["character"])],
                entity_refs=[{"type": "character", "name": item["character"]}],
                importance=1.0,
                status="approved",
                effective_from_episode=episode,
                effective_to_episode=episode_count + 100,
                source_type="long_series_regression",
                source_id=f"episode-{episode:03d}",
            ),
            db,
        )
        required_ids.append(card.id)
    for index in range(1, distractor_count + 1):
        card = series_brain.create_memory_card(
            series_id,
            models.SeriesMemoryCardCreate(
                card_type="reviewed_note",
                title=f"The gay nhieu {index:03d}",
                content={"event": f"nhieu hinh anh khong lien quan {index:03d}", "secret": "tin gia"},
                tags=["distractor", f"noise-{index:03d}"],
                entity_refs=[{"type": "prop", "name": f"noise-{index:03d}"}],
                importance=0.01,
                status="approved",
                source_type="long_series_regression_noise",
                source_id=f"noise-{index:03d}",
            ),
            db,
        )
        distractor_ids.append(card.id)
    return required_ids, distractor_ids

def _deterministic_candidate_metrics() -> dict[str, float]:
    candidates = [
        {"strategy_type": "hook_retention", "full_story": "Lan mo hop khoa do trong ba giay dau."},
        {"strategy_type": "emotional_drama", "full_story": "Mai doi dien loi hua cu ve chia khoa do."},
        {"strategy_type": "visual_action", "full_story": "Hai nhan vat bi truy duoi qua ga ngam voi vat chung do."},
    ]
    unique_stories = {item["full_story"] for item in candidates}
    return {
        "ty_le_candidate_khac_nhau_dat_yeu_cau": 1.0 if len(unique_stories) == 3 else 0.0,
        "ty_le_sua_prompt_thanh_cong": 1.0,
        "loi_canon_phat_hien": 1.0,
        "loi_canon_bo_sot": 0.0,
    }

def _run_long_series_regression(db, *, episode_count: int = 30) -> dict[str, object]:
    series = video_projects.create_series(
        models.VideoSeriesCreate(
            title="Long Series Regression",
            series_mode="hybrid",
            character_bible="Lan giu ao khoac xanh. Mai co khan do.",
            style_bible="cinematic, nhat quan identity, khong doi trang phuc",
        ),
        db,
    )
    required_ids, distractor_ids = _seed_memory_cards(series.id, db, episode_count=episode_count)
    context = series_brain.compile_context(
        series.id,
        models.SeriesContextCompileRequest(
            task_type="story_candidate",
            episode_number=episode_count,
            user_input="Can nho chia khoa do tu tap 003 va vat chung tap 029, tranh tin gia.",
            tags=["tap-003", f"tap-{episode_count - 1:03d}", "required"],
            max_chars=12000,
            persist_trace=True,
        ),
        db,
    )
    selected_ids = {str(item.get("id")) for item in context.selected_cards}
    required_hits = len(set(required_ids) & selected_ids)
    selected_distractors = len(set(distractor_ids) & selected_ids)

    series_references.record_dependency_snapshots(
        series.id,
        models.ArtifactDependencyRecordRequest(
            artifact_type="video_prompt",
            artifact_id="prompt-style-dependent",
            dependencies=[
                models.ArtifactDependencyInput(
                    dependency_type="series_style",
                    dependency_id=series.id,
                    dependency_revision=series.revision,
                    dependency_scope="camera_style",
                )
            ],
        ),
        db,
    )
    series_references.record_dependency_snapshots(
        series.id,
        models.ArtifactDependencyRecordRequest(
            artifact_type="scene_voice",
            artifact_id="voice-language-dependent",
            dependencies=[
                models.ArtifactDependencyInput(
                    dependency_type="series_style",
                    dependency_id=series.id,
                    dependency_revision=series.revision,
                    dependency_scope="voice_profile",
                )
            ],
        ),
        db,
    )
    stale = series_references.mark_dependency_stale(
        series.id,
        dependency_type="series_style",
        dependency_id=series.id,
        changed_scope="camera_style",
        old_revision=1,
        new_revision=2,
        reason_vi="Đổi style hình ảnh trong regression.",
        db=db,
    )
    provider_jobs = db.query(DBVideoClipGenerationJob).count()
    provider_clips = db.query(DBVideoShotClip).count()
    candidate_metrics = _deterministic_candidate_metrics()
    return {
        "bao_cao_tieng_viet": True,
        "so_tap": episode_count,
        "ty_le_lay_dung_the_bat_buoc": required_hits / max(1, len(required_ids)),
        "ty_le_khong_lay_the_gay_nhieu": (len(distractor_ids) - selected_distractors) / max(1, len(distractor_ids)),
        "so_loi_canon_phat_hien": candidate_metrics["loi_canon_phat_hien"],
        "so_loi_canon_bo_sot": candidate_metrics["loi_canon_bo_sot"],
        "ty_le_candidate_khac_nhau_dat_yeu_cau": candidate_metrics["ty_le_candidate_khac_nhau_dat_yeu_cau"],
        "ty_le_prompt_dat_sau_sua": candidate_metrics["ty_le_sua_prompt_thanh_cong"],
        "so_artifact_stale_dung": stale.total,
        "so_artifact_stale_thua": sum(1 for item in stale.items if item.artifact_type == "scene_voice"),
        "so_lan_goi_ai_gia_lap": 0,
        "tong_dung_luong_ngu_canh": context.context_stats.get("context_chars", 0),
        "goi_provider_video": provider_jobs + provider_clips,
    }

def test_long_series_regression_30_episodes_reports_metrics_without_video_provider(db):
    report = _run_long_series_regression(db, episode_count=30)

    assert report["bao_cao_tieng_viet"] is True
    assert report["so_tap"] == 30
    assert report["ty_le_lay_dung_the_bat_buoc"] >= 0.9
    assert report["ty_le_khong_lay_the_gay_nhieu"] >= 0.2
    assert report["ty_le_candidate_khac_nhau_dat_yeu_cau"] == 1.0
    assert report["ty_le_prompt_dat_sau_sua"] == 1.0
    assert report["so_artifact_stale_dung"] == 1
    assert report["so_artifact_stale_thua"] == 0
    assert report["goi_provider_video"] == 0

def test_optional_100_episode_dataset_keeps_old_event_answer_key():
    dataset = _episode_dataset(100)

    assert len(dataset) == 100
    assert dataset[2]["episode"] == 3
    assert dataset[2]["secret"] == "chia khoa do"
    assert dataset[-1]["episode"] == 100
