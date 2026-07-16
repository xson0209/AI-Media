"""Series handoff tests (tasks 8.2, 8.9, 8.11, 8.13, 8.14, 12.10, 12.17)."""

from __future__ import annotations

import io

import pytest
from PIL import Image

from backend import config, database, models
from backend.database import session as database_session
from backend.services import story_studio
from backend.services.comic_series_analysis import approval_manifest as am
from backend.services.comic_series_analysis import handoff, service
from backend.services.comic_series_analysis.contracts import ComicAnalysisError


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


def _png(color=(10, 20, 30)):
    buf = io.BytesIO()
    Image.new("RGB", (24, 24), color).save(buf, format="PNG")
    return buf.getvalue()


def _approved_job(db):
    """Create an upload job and approve its analysis revision."""
    job = service.create_upload_job(db, images=[("a.png", _png()), ("b.png", _png((9, 9, 9)))])
    job.analysis_revision = 1
    db.commit()
    am.create_manifest(
        db, job_id=job.id, analysis_revision=1,
        accepted_items=[{"item_type": "episode", "id": "ep", "revision": 1}],
        excluded_items=[], unreviewed_items=[],
        development_mode="lay_cam_hung_va_viet_moi", rights_attestation_revision=0,
    )
    db.commit()
    return job


def _valid_master(**overrides):
    data = {
        "title": "Master từ comic",
        "logline": "Một tập truyện tranh có đủ hook, diễn biến và payoff.",
        "hook": "Một biểu cảm bất ngờ mở đầu khung truyện.",
        "full_story": "Nhân vật chính đối mặt một bí mật, giữ đúng canon và đi tới quyết định cuối tập.",
        "key_beats": ["Hook", "Bí mật lộ ra", "Payoff"],
        "character_emotions": ["bất ngờ", "quyết tâm"],
        "visual_moments": ["cận mặt nhân vật", "khung truyện cao trào"],
        "motion_beats": ["push-in nhẹ", "cut theo hành động"],
        "retention_plan": "Mỗi nhịp mở một câu hỏi mới cho người xem.",
        "market_profile": "viet_nam",
        "language_profile": "vi",
        "must_have": ["Giữ cảm giác truyện tranh"],
        "avoid": ["Không đổi fixed traits"],
        "continuity_updates": [],
        "image_story_notes": "Panel rõ, giữ style truyện tranh/anime.",
        "video_story_notes": "Có thể handoff thành video truyện.",
    }
    data.update(overrides)
    return data


def test_preview_requires_approval(db):
    job = service.create_upload_job(db, images=[("a.png", _png())])
    job.analysis_revision = 1
    db.commit()
    with pytest.raises(ComicAnalysisError) as exc:
        handoff.build_preview(db, job.id, target_kind="new_series")
    assert exc.value.error_code == "COMIC_REVISION_NOT_APPROVED"


def test_preview_is_side_effect_free(db):
    from backend.database import VideoSeries, StoryEpisode
    job = _approved_job(db)
    before_series = db.query(VideoSeries).count()
    before_eps = db.query(StoryEpisode).count()
    preview = handoff.build_preview(db, job.id, target_kind="new_series")
    assert preview.status == "previewed"
    assert preview.preview_fingerprint
    # No Series/Episode written during preview.
    assert db.query(VideoSeries).count() == before_series
    assert db.query(StoryEpisode).count() == before_eps


def test_commit_creates_full_source_document(db):
    from backend.database import (
        StoryEpisode, StoryEpisodeSourceDocument, StoryEpisodeSourceChunk,
        StoryEpisodeSourceAsset, VideoSeries,
    )
    job = _approved_job(db)
    preview = handoff.build_preview(db, job.id, target_kind="new_series", target_series_mode="image_story_only")
    committed = handoff.commit_handoff(db, preview.id, idempotency_key="key-1")

    assert committed.status == "committed"
    result = committed.result_json
    assert result["series_id"] and result["story_episode_id"] and result["source_document_id"]
    assert "video_project_id" not in result  # task 8.13
    assert "/story-studio?seriesId=" in result["story_studio_url"]

    # New series defaults to image_story_only (task 8.7).
    series = db.query(VideoSeries).filter_by(id=result["series_id"]).first()
    assert series.series_mode == "image_story_only"
    assert "Anime/manga/webtoon" in series.style_bible

    # Episode points at the current source document.
    episode = db.query(StoryEpisode).filter_by(id=result["story_episode_id"]).first()
    assert episode.current_source_document_id == result["source_document_id"]
    assert episode.development_mode == "lay_cam_hung_va_viet_moi"
    response = story_studio.get_episode(episode.id, db)
    assert response.current_source_document_id == result["source_document_id"]
    assert response.source_summary.has_structured_source is True
    assert response.source_summary.source_kind == "comic_analysis"
    assert response.source_summary.comic_job_id == job.id
    assert response.source_summary.comic_analysis_revision == 1
    assert response.source_summary.revision == 1
    assert response.output_settings.image.width == 720
    assert response.output_settings.image.height == 1280
    assert response.market_profile == "global_short"
    assert response.language_profile == "en"
    assert response.output_settings.video.target_language == "en"
    assert response.output_settings.video.video_purpose == "global_short"
    assert response.output_settings.video.dialogue_mode == "character_lines"
    assert response.output_settings.video.narration_density == "dense"
    assert response.output_settings.video.call_to_action_style == "direct"

    # Full source document + assets exist.
    doc = db.query(StoryEpisodeSourceDocument).filter_by(id=result["source_document_id"]).first()
    assert doc.source_kind == "comic_analysis"
    assert doc.comic_job_id == job.id
    assets = db.query(StoryEpisodeSourceAsset).filter_by(document_id=doc.id).all()
    assert len(assets) == 2  # both uploaded images linked immutably


def test_comic_handoff_image_prompt_keeps_anime_manga_webtoon_style(db):
    from backend.database import StoryEpisode, VideoSeries

    job = _approved_job(db)
    preview = handoff.build_preview(db, job.id, target_kind="new_series", target_series_mode="image_story_only")
    committed = handoff.commit_handoff(db, preview.id, idempotency_key="comic-style-key")
    series = db.query(VideoSeries).filter_by(id=committed.result_json["series_id"]).one()
    episode = db.query(StoryEpisode).filter_by(id=committed.result_json["story_episode_id"]).one()

    assert "Anime/manga/webtoon" in series.style_bible
    assert episode.output_settings_json["image"]["width"] == 720
    assert episode.output_settings_json["image"]["height"] == 1280

    selected = story_studio.select_master_story(
        episode.id,
        models.StoryCandidateSelectionRequest(master_story_json=_valid_master()),
        db,
    )
    approved = story_studio.approve_master_story(
        selected.id,
        models.StoryApprovalRequest(approved=True),
        db,
    )
    adaptation = story_studio.create_image_adaptation(approved.id, db)
    first_prompt = adaptation.payload_json["panels"][0]["prompt"]

    assert "Anime/manga/webtoon" in first_prompt
    assert "720x1280px" in first_prompt


def test_new_series_title_from_handoff_preview(db):
    from backend.database import VideoSeries

    job = _approved_job(db)
    preview = handoff.build_preview(
        db,
        job.id,
        target_kind="new_series",
        target_series_title="  Bộ truyện riêng của tôi  ",
        episode_title="Tập mở đầu",
    )
    committed = handoff.commit_handoff(db, preview.id, idempotency_key="custom-title-key")
    series = db.query(VideoSeries).filter_by(id=committed.result_json["series_id"]).one()

    assert preview.target_series_title == "Bộ truyện riêng của tôi"
    assert series.title == "Bộ truyện riêng của tôi"


def test_commit_carries_story_episode_output_settings_from_preview(db):
    from backend.database import StoryEpisode

    job = _approved_job(db)
    preview = handoff.build_preview(
        db,
        job.id,
        target_kind="new_series",
        target_series_mode="hybrid",
        episode_title="Episode with settings",
        output_intent="ca_hai",
        market_profile="global",
        language_profile="en",
        source_input="Keep the web-analysis canon and write dialogue as character lines.",
        output_settings={
            "image": {
                "panel_mode": "manual",
                "panel_count": 12,
                "aspect_ratio": "4:5",
                "width": 1080,
                "height": 1350,
            },
            "video": {
                "handoff_only": True,
                "aspect_ratio": "16:9",
                "target_language": "en",
                "video_purpose": "global_short",
                "dialogue_mode": "character_lines",
                "narration_density": "dense",
                "call_to_action_style": "none",
                "target_duration_seconds": 90,
                "default_shot_duration_seconds": 4,
                "prompt_segment_count": 6,
                "prompt_segment_duration_seconds": 10,
                "micro_scenes_per_prompt": 4,
            },
        },
    )

    committed = handoff.commit_handoff(db, preview.id, idempotency_key="settings-key")
    episode = db.query(StoryEpisode).filter_by(id=committed.result_json["story_episode_id"]).one()

    assert episode.output_intent == "ca_hai"
    assert episode.market_profile == "global"
    assert episode.language_profile == "en"
    assert "character lines" in episode.source_input
    assert episode.output_settings_json["image"]["panel_mode"] == "manual"
    assert episode.output_settings_json["image"]["panel_count"] == 12
    assert episode.output_settings_json["image"]["aspect_ratio"] == "4:5"
    assert episode.output_settings_json["video"]["aspect_ratio"] == "16:9"
    assert episode.output_settings_json["video"]["target_language"] == "en"
    assert episode.output_settings_json["video"]["dialogue_mode"] == "character_lines"


def test_commit_carries_analysis_and_optimized_script_into_story_studio_context(db):
    from backend.database import (
        ComicDetectedCharacter,
        ComicDetectedLocation,
        ComicPanel,
        ComicPlotAnalysis,
        ComicSourceAsset,
        ComicSpeechBubble,
        SeriesCharacterProfile,
        StoryEpisodeSourceChunk,
        StoryEpisodeSourceDocument,
        VideoSeries,
    )

    job = _approved_job(db)
    asset_id = db.query(ComicSourceAsset.id).filter_by(job_id=job.id).first()[0]
    character = ComicDetectedCharacter(
        job_id=job.id,
        analysis_revision=1,
        display_name="Ari",
        role="Nữ chính",
        face_description="Gương mặt trái xoan",
        outfit_description="Áo khoác vàng",
        evidence_ids_json=[asset_id],
    )
    location = ComicDetectedLocation(
        job_id=job.id,
        analysis_revision=1,
        name="Quán cà phê đầu phố",
        description="Không gian ấm áp trong đêm mưa.",
        evidence_ids_json=[asset_id],
    )
    db.add_all(
        [
            ComicPanel(
                job_id=job.id,
                analysis_revision=1,
                asset_id=asset_id,
                reading_order=0,
                visual_description="Ari đứng trong quán cà phê dưới ánh đèn vàng.",
                evidence_ids_json=[asset_id],
                confidence=0.92,
            ),
            ComicSpeechBubble(
                job_id=job.id,
                analysis_revision=1,
                reading_order=0,
                bubble_type="dialogue",
                normalized_text="Em đã đợi ngày này rất lâu.",
                evidence_ids_json=[asset_id],
            ),
            character,
            location,
            ComicPlotAnalysis(
                job_id=job.id,
                analysis_revision=1,
                synopsis="Ari bước vào cuộc hội ngộ thay đổi cuộc đời.",
                plot_beats_json=["Đến quán", "Hội ngộ"],
                relationships_json=[{"from": "Ari", "to": "Kai", "type": "định mệnh"}],
            ),
        ]
    )
    job.analysis_package_json = {
        "optimized_script": {
            "title": "Cuộc hẹn dưới mưa",
            "synopsis": "Ari gặp lại Kai tại quán cà phê.",
            "full_story": "Ari mở cửa quán cà phê. Cô nhìn thấy Kai và bắt đầu cuộc hội ngộ.",
            "plot_beats": ["Ari đến", "Ari gặp Kai"],
        }
    }
    db.flush()
    am.create_manifest(
        db,
        job_id=job.id,
        analysis_revision=1,
        accepted_items=[
            {"item_type": "episode", "id": job.id, "revision": 1},
            {"item_type": "character", "id": character.id, "revision": 1},
            {"item_type": "location", "id": location.id, "revision": 1},
        ],
        excluded_items=[],
        unreviewed_items=[],
        development_mode="lay_cam_hung_va_viet_moi",
        rights_attestation_revision=0,
    )
    db.commit()

    preview = handoff.build_preview(db, job.id, target_kind="new_series")
    committed = handoff.commit_handoff(db, preview.id, idempotency_key="structured-key")
    result = committed.result_json

    doc = db.query(StoryEpisodeSourceDocument).filter_by(id=result["source_document_id"]).one()
    chunks = db.query(StoryEpisodeSourceChunk).filter_by(document_id=doc.id).all()
    series = db.query(VideoSeries).filter_by(id=result["series_id"]).one()
    profiles = db.query(SeriesCharacterProfile).filter_by(series_id=series.id).all()

    assert doc.synopsis == "Ari gặp lại Kai tại quán cà phê."
    assert "Ari mở cửa quán cà phê" in doc.approved_text
    assert doc.plot_structure_json["locations"][0]["name"] == "Quán cà phê đầu phố"
    assert {chunk.chunk_type for chunk in chunks} >= {"visual", "dialogue", "character", "location", "script"}
    assert profiles[0].name == "Ari"
    assert "Quán cà phê đầu phố" in (series.world_bible or "")


def test_commit_idempotent(db):
    job = _approved_job(db)
    preview = handoff.build_preview(db, job.id, target_kind="new_series")
    first = handoff.commit_handoff(db, preview.id, idempotency_key="key-A")
    # Replaying the same handoff returns the committed result, no new series.
    from backend.database import VideoSeries
    series_count = db.query(VideoSeries).count()
    second = handoff.commit_handoff(db, preview.id, idempotency_key="key-A")
    assert second.id == first.id
    assert second.status == "committed"
    assert db.query(VideoSeries).count() == series_count


def test_idempotency_key_conflict(db):
    job = _approved_job(db)
    preview = handoff.build_preview(db, job.id, target_kind="new_series")
    handoff.commit_handoff(db, preview.id, idempotency_key="key-A")
    with pytest.raises(ComicAnalysisError) as exc:
        handoff.commit_handoff(db, preview.id, idempotency_key="key-B")
    assert exc.value.error_code == "COMIC_HANDOFF_IDEMPOTENCY_CONFLICT"


def test_video_only_series_rejected(db):
    from backend.database import VideoSeries
    job = _approved_job(db)
    series = VideoSeries(title="Vid", series_mode="video_story_only")
    db.add(series)
    db.commit()
    with pytest.raises(ComicAnalysisError) as exc:
        handoff.build_preview(
            db, job.id, target_kind="existing_series", target_series_id=series.id
        )
    assert exc.value.error_code == "COMIC_HANDOFF_TARGET_VIDEO_ONLY"


def test_no_video_project_created(db):
    """The whole flow must never create an AI Video project (task 12.17)."""
    from backend.database import VideoProject
    job = _approved_job(db)
    preview = handoff.build_preview(db, job.id, target_kind="new_series")
    handoff.commit_handoff(db, preview.id, idempotency_key="key-1")
    assert db.query(VideoProject).count() == 0
