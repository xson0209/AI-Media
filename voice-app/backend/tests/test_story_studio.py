from __future__ import annotations

from datetime import datetime
from types import SimpleNamespace
from typing import Any

import pytest

from backend import config, models
from backend.database import session as database_session
from backend.database import init_db
from backend.database.models import SeriesCharacterProfile as DBSeriesCharacterProfile
from backend.database.models import SeriesMemoryCard as DBSeriesMemoryCard
from backend.database.models import StoryEpisode as DBStoryEpisode
from backend.database.models import StoryEpisodeSourceChunk as DBStoryEpisodeSourceChunk
from backend.database.models import StoryEpisodeSourceDocument as DBStoryEpisodeSourceDocument
from backend.database.models import StoryScenarioCandidate as DBStoryScenarioCandidate
from backend.database.models import VideoAutoRun as DBVideoAutoRun
from backend.database.models import VideoProject as DBVideoProject
from backend.database.models import VideoRenderJob as DBVideoRenderJob
from backend.database.models import VideoSeries as DBVideoSeries
from backend.database.models import VideoShot as DBVideoShot
from backend.database.models import VideoSourceBlock as DBVideoSourceBlock
from backend.services import story_studio, video_auto_runs, video_projects, video_series_memory
from backend.services.comic_series_analysis import source_context as comic_source_context
from backend.services import video_planning_pool


def _iter_schema_nodes(schema):
    if not isinstance(schema, dict):
        return
    yield schema
    properties = schema.get("properties")
    if isinstance(properties, dict):
        for child in properties.values():
            yield from _iter_schema_nodes(child)
    items = schema.get("items")
    if isinstance(items, dict):
        yield from _iter_schema_nodes(items)
    for combinator in ("anyOf", "oneOf", "allOf"):
        children = schema.get(combinator)
        if isinstance(children, list):
            for child in children:
                yield from _iter_schema_nodes(child)


def test_story_studio_output_schemas_are_strict_json_schema_objects():
    schemas = [
        story_studio.STORY_MASTER_SCHEMA,
        story_studio.STORY_CANDIDATE_SCHEMA,
        story_studio.STORY_EVALUATION_SCHEMA,
        story_studio.STORY_SYNTHESIS_SCHEMA,
        story_studio.STORY_PROMPT_REPAIR_SCHEMA,
    ]

    for schema in schemas:
        for node in _iter_schema_nodes(schema):
            type_value = node.get("type")
            assert not isinstance(type_value, list), f"Use anyOf/oneOf instead of type unions: {node}"
            if type_value == "object":
                assert node.get("additionalProperties") is False, f"Object schema is not strict: {node}"
                properties = node.get("properties") or {}
                if properties:
                    assert set(node.get("required") or []) == set(properties), f"Object schema required keys do not match properties: {node}"
            if type_value == "array":
                assert isinstance(node.get("items"), dict) and node["items"], f"Array schema is missing item schema: {node}"


def test_story_studio_compacts_source_chunks_for_prompt():
    chunks = [
        {
            "id": f"chunk-{index}",
            "chunk_order": index,
            "chunk_type": "script" if index in {10, 60} else "dialogue",
            "text": f"noi dung chunk {index} " + ("x" * 400),
            "evidence_ids": [f"ev-{index}", "extra-1", "extra-2", "extra-3"],
            "source_revision": 1,
        }
        for index in range(100)
    ]

    compact = story_studio._compact_source_chunks_for_prompt(chunks)

    assert len(compact) <= story_studio.MAX_SOURCE_PROMPT_CHUNKS + 8
    assert compact[0]["chunk_order"] == 0
    assert compact[-1]["chunk_order"] == 99
    assert any(chunk["chunk_order"] == 10 for chunk in compact)
    assert any(chunk["chunk_order"] == 60 for chunk in compact)
    assert all(len(chunk["text"]) <= story_studio.MAX_SOURCE_CHUNK_TEXT_CHARS for chunk in compact)
    assert all(len(chunk["evidence_ids"]) <= 3 for chunk in compact)


def test_story_studio_candidate_prompt_bounds_large_context():
    episode = SimpleNamespace(
        episode_number=1,
        output_intent="truyen_anh",
        market_profile="viet_nam",
        language_profile="vi",
        source_digest="chapter digest",
        output_settings_json=None,
    )
    series = SimpleNamespace(
        id="series-1",
        title="Long Context Series",
        series_mode="image_story_only",
        character_bible="character " * 2000,
        world_bible="world " * 2000,
        style_bible="style " * 2000,
        continuity_rules="continuity " * 2000,
        negative_rules="negative " * 2000,
        previous_episode_summary="previous " * 2000,
    )
    source_chunks = [
        {
            "id": f"chunk-{index}",
            "chunk_order": index,
            "chunk_type": "visual",
            "text": "visual detail " * 80,
            "evidence_ids": [f"ev-{index}"],
            "source_revision": 1,
        }
        for index in range(80)
    ]
    creative_brief = story_studio._creative_brief(
        episode=episode,
        series=series,
        memory_text="memory " * 5000,
        profiles_text="profile " * 5000,
    )
    creative_brief["structured_source"] = {
        "source_document_id": "doc-1",
        "source_revision": 1,
        "accepted_chunk_count": len(source_chunks),
        "prompt_chunk_count": story_studio.MAX_SOURCE_PROMPT_CHUNKS,
        "fingerprint": "fp",
        "chunks": story_studio._compact_source_chunks_for_prompt(source_chunks),
    }

    prompt = story_studio._candidate_prompt(
        creative_brief=creative_brief,
        strategy_type="hook_retention",
        label=story_studio._strategy_label("hook_retention"),
        episode=episode,
        context_snapshot_id="trace-1",
        attempt=1,
    )

    assert len(creative_brief["series_memory_excerpt"]) <= story_studio.CREATIVE_BRIEF_SERIES_MEMORY_CHARS
    assert len(creative_brief["character_profiles"]) <= story_studio.CREATIVE_BRIEF_PROFILE_CHARS
    assert len(prompt) < 22_000


def test_story_candidate_prompt_uses_selected_content_language_not_ui_language():
    episode = SimpleNamespace(
        episode_number=1,
        output_intent="truyen_anh",
        market_profile="global_short",
        language_profile="ja",
        source_digest="chapter digest",
        output_settings_json={"video": {"target_language": "ja"}},
    )

    prompt = story_studio._candidate_prompt(
        creative_brief={"series_title": "Ngôn ngữ tách bạch"},
        strategy_type="hook_retention",
        label=story_studio._strategy_label("hook_retention"),
        episode=episode,
        context_snapshot_id="trace-language",
        attempt=1,
    )

    assert "Ngôn ngữ nội dung người xem đã chọn: tiếng Nhật / Japanese" in prompt
    assert "reason_vi" in prompt
    assert "vẫn phải là tiếng Việt" in prompt
    assert "full_story là Master Story nháp hoàn chỉnh bằng tiếng Việt" not in prompt


def test_story_panel_text_sanitizer_removes_ocr_labels_scene_headers_and_wrong_language():
    assert (
        story_studio._sanitize_panel_bubble_text(
            'CẢNH 6 — THƯ VIỆN LOMBARDI: "Cách đọc một bản báo cáo."',
            target_language="vi",
        )
        == "Cách đọc một bản báo cáo."
    )
    assert (
        story_studio._sanitize_panel_bubble_text(
            "[65] dialogue: Even at the last moment, you still don’t understand.",
            target_language="en",
        )
        == "Even at the last moment, you still don’t understand."
    )
    assert (
        story_studio._sanitize_panel_bubble_text(
            "Hook mở màn: Trong căn phòng bệnh đêm muộn, ông nội thú nhận sự thật.",
            target_language="vi",
        )
        == ""
    )
    assert (
        story_studio._sanitize_panel_bubble_text(
            "[46] narration: Tác phẩm này được Công ty D&C Webtoon Biz phát hành theo hợp đồng.",
            target_language="vi",
        )
        == ""
    )
    assert (
        story_studio._sanitize_panel_bubble_text(
            "[27] dialogue: Ông xin lỗi. Lẽ ra ông phải chăm sóc cháu tốt hơn...",
            target_language="en",
        )
        == ""
    )


def test_story_panel_prompt_text_policy_renders_only_approved_caption():
    note = story_studio._dialogue_note_for_panel("Xin chào.", index=1, target_language="vi")

    assert "Required in-image bubble/caption text" in note
    assert "Render exactly the quoted text" in note
    assert "Never translate it" in note
    assert "post-compositing" not in note.lower()

    empty_note = story_studio._dialogue_note_for_panel("", index=1, target_language="vi")

    assert "no readable text is required" in empty_note
    assert "Do not invent any text" in empty_note

def test_story_panel_prompt_views_are_split_for_reader_and_render():
    panel = {
        "order": 1,
        "purpose": "Mở hook bằng ánh mắt quyết tâm.",
        "caption_or_dialogue": "Tôi sẽ cứu cha.",
        "visual_description": "Lan đứng trước cửa bạc.",
        "camera_angle": "medium close-up",
        "composition_notes": "vertical 9:16",
        "prompt": "Vertical story panel. Required in-image bubble/caption text: Tôi sẽ cứu cha.",
    }

    story_studio._sync_story_panel_prompt_views(panel, target_language="vi", total_panels=3)

    assert panel["render_prompt"] == panel["prompt"]
    assert "Bản đọc" in panel["reader_prompt_vi"]
    assert "AI cần vẽ trong ảnh" in panel["reader_prompt_vi"]
    assert "Tôi sẽ cứu cha." in panel["reader_prompt_vi"]

@pytest.fixture
def db(tmp_path):
    config.set_data_dir(tmp_path)
    init_db()
    video_planning_pool.reset_for_tests()
    session = database_session.SessionLocal()
    try:
        yield session
    finally:
        session.close()
        video_planning_pool.reset_for_tests()
        database_session.engine.dispose()


def _candidate_payload(strategy_type: str, index: int = 1, **overrides):
    unique = {
        "hook_retention": {
            "title": "Bay dong ho do",
            "hook": "Mot chiec dong ho do dem nguoc ngay trong ba giay dau.",
            "beat": "dong ho do mat ma ga ngam lua chon giu chan",
            "visual": "can canh dong ho do phan chieu tren cua kinh tau dien",
        },
        "emotional_drama": {
            "title": "La thu xanh trong mua",
            "hook": "Lan nghe lai loi hua cu khi la thu xanh bi mua lam nhoe.",
            "beat": "la thu xanh loi hua gia dinh xung dot cam xuc",
            "visual": "mua xanh lanh ban tay run anh mat kim nuoc mat",
        },
        "visual_action": {
            "title": "Cau kinh vo sang",
            "hook": "Mot cay cau kinh nut sang khi nhan vat lao qua luong den truy duoi.",
            "beat": "cau kinh vo tia sang truy duoi hanh dong thi giac",
            "visual": "toan canh cau kinh vet sang chuyen dong manh",
        },
    }[strategy_type]
    data = _valid_master(
        title=f"{unique['title']} {index}",
        logline=f"{unique['beat']} mo ra mot huong ke rieng cho {strategy_type}.",
        hook=unique["hook"],
        full_story=(
            f"{unique['beat']} tao thanh cau chuyen rieng co mo dau, leo thang, cao trao va payoff. "
            f"Nhan vat giu dung fixed traits, khong doi canon va dua quyet dinh cuoi tap ro rang. "
            f"Huong {strategy_type} dung cac chi tiet doc lap de khong chi doi tieu de."
        ),
        key_beats=[unique["beat"], f"cao trao rieng {strategy_type}", f"payoff rieng {index}"],
        visual_moments=[unique["visual"], f"khung hinh dac trung {strategy_type}"],
        motion_beats=[f"motion beat rieng {strategy_type}", f"nhip chuyen canh {index}"],
        strengths_claimed=[f"Diem manh rieng cua {strategy_type}"],
        risks_claimed=[f"Rui ro can kiem soat cua {strategy_type}"],
    )
    data["strategy_type"] = strategy_type
    data["strategy_label"] = story_studio._strategy_label(strategy_type)
    data.update(overrides)
    return data

def _evaluation_payload():
    reviews = []
    for index, (strategy_type, _label) in enumerate(story_studio.STRATEGIES, start=1):
        reviews.append(
            {
                "strategy_type": strategy_type,
                "total": 82 + index,
                "criteria": {
                    "canon": 15,
                    "strategic_difference": 12,
                    "hook_retention": 12,
                    "emotion_logic": 10,
                    "visual_production": 10,
                    "pacing_payoff": 10,
                    "market_language_fit": 8,
                    "production_risk": 6,
                },
                "reason_vi": f"{strategy_type} co trong tam ro va dung duoc cho tap.",
                "evidence": [f"Bang chung {strategy_type}"],
                "strengths": [f"Manh {strategy_type}"],
                "weaknesses": [f"Yeu {strategy_type}"],
                "risks": [f"Rui ro {strategy_type}"],
                "recommended_parts": [f"Nen lay hook cua {strategy_type}"],
            }
        )
    return {
        "rubric": "rubric-test",
        "output_intent": "truyen_anh",
        "reviews": reviews,
        "synthesis_guidance": "Lay hook manh, cam xuc ro va visual de render.",
    }

@pytest.fixture(autouse=True)
def fake_story_ai(monkeypatch):
    calls: list[dict[str, Any]] = []

    def fake_run(db, prompt, schema, *, timeout_seconds=300):
        calls.append({"prompt": prompt, "schema": schema, "timeout_seconds": timeout_seconds})
        if schema is story_studio.STORY_EVALUATION_SCHEMA:
            return _evaluation_payload()
        if schema is story_studio.STORY_SYNTHESIS_SCHEMA:
            return _valid_master(
                title="Master tong hop",
                hook="Hook tong hop giu nhip cao.",
                full_story="Master tong hop giu canon, lay hook, cam xuc va visual tot nhat.",
                synthesis_sources=[
                    {"strategy_type": "hook_retention", "part": "hook", "reason": "Giu chan tot"},
                    {"strategy_type": "emotional_drama", "part": "emotion", "reason": "Cam xuc ro"},
                ],
            )
        if schema is story_studio.STORY_PROMPT_REPAIR_SCHEMA:
            return {
                "prompt": (
                    "Vertical cinematic story panel image, clear composition and framing, keep canon and character "
                    "continuity, one readable action beat, consistent style, no generated text."
                ),
                "negative_prompt": "changed face, inconsistent outfit, unreadable text",
                "caption_or_dialogue": "Caption rieng, khong yeu cau provider ve chu.",
                "visual_description": "Mot hanh dong chinh ro trong panel.",
                "changes": ["Bo mau thuan", "Them identity, framing va continuity"],
                "reason_vi": "Sua de dat quality/canon.",
            }
        if schema is story_studio.STORY_CANDIDATE_SCHEMA:
            for index, (strategy_type, _label) in enumerate(story_studio.STRATEGIES, start=1):
                if strategy_type in prompt:
                    return _candidate_payload(strategy_type, index)
            return _candidate_payload("hook_retention", 1)
        raise AssertionError("Unexpected Story Studio schema")

    monkeypatch.setattr(story_studio, "_run_structured_ai", fake_run)

    def light_project_response(project, db):
        response = models.VideoProjectResponse.model_validate(project)
        response.scene_count = video_projects._scene_count(project.id, db)
        response.shot_count = video_projects._shot_count(project.id, db)
        if project.series_id:
            series = db.query(DBVideoSeries).filter(DBVideoSeries.id == project.series_id).first()
            response.series_title = series.title if series else None
        return response

    monkeypatch.setattr(video_projects, "_project_response", light_project_response)
    return calls

def _valid_master(**overrides):
    data = {
        "title": "Master hợp lệ",
        "logline": "Một tập có đủ cấu trúc.",
        "hook": "Mở bằng biến cố rõ.",
        "full_story": "Câu chuyện đầy đủ giữ continuity và fixed traits.",
        "key_beats": ["Hook", "Cao trào", "Payoff"],
        "character_emotions": ["bất ngờ", "quyết tâm"],
        "visual_moments": ["cận mặt", "khung cảnh chính"],
        "motion_beats": ["push-in", "cut theo hành động"],
        "retention_plan": "Mỗi nhịp mở một câu hỏi mới.",
        "market_profile": "viet_nam",
        "language_profile": "vi",
        "must_have": ["Giữ nhân vật"],
        "avoid": ["Không đổi fixed traits"],
        "continuity_updates": [],
        "image_story_notes": "Panel rõ và caption ngắn.",
        "video_story_notes": "Handoff sạch sang AI Video.",
    }
    data.update(overrides)
    return data

def _story_episode_with_image_prompts(db, *, output_intent: str = "truyen_anh"):
    series = video_projects.create_series(
        models.VideoSeriesCreate(
            title="Truyện ảnh sang video",
            series_mode="image_story_only" if output_intent == "truyen_anh" else "hybrid",
            character_bible="Lan luôn mặc áo khoác xanh và giữ giọng nói bình tĩnh.",
            style_bible="Cinematic manga, dramatic close-up, vertical webtoon pacing.",
            continuity_rules="Không đổi áo khoác xanh của Lan.",
            negative_rules="changed face, wrong outfit, unreadable text",
        ),
        db,
    )
    db.add(
        DBSeriesCharacterProfile(
            id="profile-lan-video-handoff",
            series_id=series.id,
            name="Lan",
            role="nữ chính",
            face_description="mắt nâu, nét mặt lạnh",
            signature_outfit="áo khoác xanh",
            fixed_traits="Không đổi áo khoác xanh.",
            sort_order=1,
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
        )
    )
    db.commit()
    episode = story_studio.create_episode(
        series.id,
        models.StoryEpisodeCreate(
            output_intent=output_intent,
            title="Cánh cửa bạc",
            source_input="Lan mở cánh cửa bạc trong ga ngầm.",
            output_settings=models.StoryEpisodeOutputSettings(
                image=models.StoryImageOutputSettings(
                    panel_mode="manual",
                    panel_count=3,
                    aspect_ratio="9:16",
                    width=720,
                    height=1280,
                ),
                video=models.StoryVideoHandoffSettings(target_language="vi"),
            ),
        ),
        db,
    )
    story_studio.select_master_story(
        episode.id,
        models.StoryCandidateSelectionRequest(
            master_story_json=_valid_master(
                title="Cánh cửa bạc",
                logline="Lan phát hiện cánh cửa bạc có thể đổi ký ức lấy lối thoát.",
                hook="Cánh cửa bạc mở ra đúng lúc đồng hồ ngừng chạy.",
                full_story="Lan đi qua ga ngầm, nghe tiếng gọi sau cánh cửa bạc và buộc phải chọn giữ ký ức hay cứu em trai.",
                key_beats=["Cửa bạc mở", "Lan thấy ký ức bị đánh đổi", "Lan giữ áo khoác xanh như lời thề"],
                visual_moments=["cận mặt Lan", "cánh cửa bạc phát sáng", "ga ngầm tối"],
                motion_beats=["slow push-in", "handheld chase", "hard cut"],
            )
        ),
        db,
    )
    story_studio.approve_master_story(episode.id, models.StoryApprovalRequest(approved=True), db)
    image_adaptation = story_studio.create_image_adaptation(episode.id, db)
    return series, story_studio.get_episode(episode.id, db), image_adaptation


def test_story_candidates_share_context_snapshot_and_independent_evaluation(db):
    series = video_projects.create_series(
        models.VideoSeriesCreate(title="AI candidates", series_mode="image_story_only", character_bible="Lan giu ao khoac xanh."),
        db,
    )
    episode = story_studio.create_episode(
        series.id,
        models.StoryEpisodeCreate(output_intent="truyen_anh", source_input="Lan tim thay mat ma trong ga ngam."),
        db,
    )

    episode = story_studio.generate_candidates(episode.id, db)

    assert len(episode.candidates) == 3
    assert {candidate.strategy_type for candidate in episode.candidates} == {
        "hook_retention",
        "emotional_drama",
        "visual_action",
    }
    snapshot_ids = {candidate.context_snapshot_id for candidate in episode.candidates}
    assert len(snapshot_ids) == 1
    assert next(iter(snapshot_ids))
    assert {candidate.generation_attempt for candidate in episode.candidates} == {1}
    for candidate in episode.candidates:
        assert candidate.generation_status == "completed"
        assert candidate.evaluation_status == "completed"
        assert candidate.model_label
        assert candidate.evaluation_json["reason_vi"]
        assert candidate.evaluation_json["evidence"]
        assert candidate.evaluation_json["recommended_parts"]
        assert candidate.score_json["rubric"] == "rubric-test"


def test_story_candidates_use_source_package_payload_and_fingerprint(db):
    series = video_projects.create_series(
        models.VideoSeriesCreate(title="Nguồn chuẩn", series_mode="image_story_only"),
        db,
    )
    episode = story_studio.create_episode(
        series.id,
        models.StoryEpisodeCreate(output_intent="truyen_anh", source_input="Nguồn nhập tay dự phòng."),
        db,
    )
    episode_row = db.query(DBStoryEpisode).filter(DBStoryEpisode.id == episode.id).one()
    source_doc = DBStoryEpisodeSourceDocument(
        story_episode_id=episode.id,
        revision=3,
        approval_status="approved",
        source_kind="comic_analysis",
        title="Chương nguồn chuẩn",
        synopsis="Lan phát hiện cánh cửa bạc trong ga ngầm.",
        plot_structure_json={"beats": ["Lan nghe tiếng gọi", "Cánh cửa bạc mở"]},
        coverage_metrics_json={"panel_count": 2},
        limitations_json=["Một panel bị mờ"],
    )
    db.add(source_doc)
    db.flush()
    db.add_all(
        [
            DBStoryEpisodeSourceChunk(
                document_id=source_doc.id,
                story_episode_id=episode.id,
                chunk_order=1,
                chunk_type="dialogue",
                approved_text="Lan nói rằng cô sẽ không bỏ lại em trai.",
                approval_state="accepted",
                source_revision=3,
                evidence_ids_json=["bubble-1"],
            ),
            DBStoryEpisodeSourceChunk(
                document_id=source_doc.id,
                story_episode_id=episode.id,
                chunk_order=2,
                chunk_type="narration",
                approved_text="Đoạn chưa duyệt không được đưa vào candidate.",
                approval_state="unreviewed",
                source_revision=3,
            ),
        ]
    )
    episode_row.current_source_document_id = source_doc.id
    db.commit()

    expected_package = comic_source_context.compile_source_package(
        db,
        episode.id,
        char_budget=16000,
        task_type="story_candidate",
    ).source_package

    response = story_studio.generate_candidates(episode.id, db)

    assert response is not None
    assert len(response.candidates) == 3
    rows = (
        db.query(DBStoryScenarioCandidate)
        .filter(DBStoryScenarioCandidate.story_episode_id == episode.id)
        .order_by(DBStoryScenarioCandidate.strategy_type)
        .all()
    )
    assert len(rows) == 3
    for row in rows:
        assert row.source_document_id == source_doc.id
        assert row.source_document_revision == 3
        assert row.dependency_fingerprint == expected_package.fingerprint
        structured_source = row.script_json["creative_brief"]["structured_source"]
        assert structured_source["schema_version"] == "source_package.v1"
        assert structured_source["source_ref_id"] == source_doc.id
        assert structured_source["source_document_id"] == source_doc.id
        assert structured_source["source_revision"] == 3
        assert structured_source["fingerprint"] == expected_package.fingerprint
        assert structured_source["coverage_metrics"] == {"panel_count": 2}
        assert structured_source["limitations"] == ["Một panel bị mờ"]
        assert "Lan nói rằng cô sẽ không bỏ lại em trai." in str(structured_source)
        assert "Đoạn chưa duyệt không được đưa vào candidate." not in str(structured_source)


def test_story_candidate_retry_is_scoped_to_failed_strategy(db, monkeypatch):
    series = video_projects.create_series(
        models.VideoSeriesCreate(title="Retry", series_mode="image_story_only"),
        db,
    )
    episode = story_studio.create_episode(
        series.id,
        models.StoryEpisodeCreate(output_intent="truyen_anh", source_input="Can retry rieng mot huong."),
        db,
    )
    counts = {strategy_type: 0 for strategy_type, _label in story_studio.STRATEGIES}

    def flaky_run(db, prompt, schema, *, timeout_seconds=300):
        if schema is story_studio.STORY_EVALUATION_SCHEMA:
            return _evaluation_payload()
        if schema is story_studio.STORY_CANDIDATE_SCHEMA:
            for index, (strategy_type, _label) in enumerate(story_studio.STRATEGIES, start=1):
                if strategy_type in prompt:
                    counts[strategy_type] += 1
                    if strategy_type == "emotional_drama" and counts[strategy_type] == 1:
                        raise story_studio.StoryStudioError("loi tam thoi")
                    return _candidate_payload(strategy_type, index)
        raise AssertionError("Unexpected schema")

    monkeypatch.setattr(story_studio, "_run_structured_ai", flaky_run)

    episode = story_studio.generate_candidates(episode.id, db)

    assert counts == {"hook_retention": 1, "emotional_drama": 2, "visual_action": 1}
    emotional = next(candidate for candidate in episode.candidates if candidate.strategy_type == "emotional_drama")
    assert emotional.generation_attempt == 2


def test_story_candidate_timeout_uses_fallback_candidate(db, monkeypatch):
    series = video_projects.create_series(
        models.VideoSeriesCreate(title="Timeout fallback", series_mode="image_story_only"),
        db,
    )
    episode = story_studio.create_episode(
        series.id,
        models.StoryEpisodeCreate(output_intent="truyen_anh", source_input="Provider cham nhung van can du ba huong."),
        db,
    )

    def timeout_run(db, prompt, schema, *, timeout_seconds=300):
        if schema is story_studio.STORY_CANDIDATE_SCHEMA:
            if "visual_action" in prompt:
                raise story_studio.StoryStudioError("provider timed out")
            for index, (strategy_type, _label) in enumerate(story_studio.STRATEGIES, start=1):
                if strategy_type in prompt:
                    return _candidate_payload(strategy_type, index)
        if schema is story_studio.STORY_EVALUATION_SCHEMA:
            return _evaluation_payload()
        raise AssertionError("Unexpected schema")

    monkeypatch.setattr(story_studio, "_run_structured_ai", timeout_run)

    episode = story_studio.generate_candidates(episode.id, db)

    assert len(episode.candidates) == 3
    assert {candidate.generation_status for candidate in episode.candidates} == {"completed"}
    assert {candidate.evaluation_status for candidate in episode.candidates} == {"completed"}
    visual = next(candidate for candidate in episode.candidates if candidate.strategy_type == "visual_action")
    assert visual.script_json["full_story"]
    assert visual.generation_metadata_json["fallback_used"] is True
    assert "provider timed out" in visual.generation_metadata_json["fallback_reason"]


def test_story_candidate_all_timeouts_use_distinct_fallback_candidates(db, monkeypatch):
    series = video_projects.create_series(
        models.VideoSeriesCreate(title="All fallback", series_mode="image_story_only"),
        db,
    )
    episode = story_studio.create_episode(
        series.id,
        models.StoryEpisodeCreate(
            output_intent="truyen_anh",
            source_input="Tia tinh lai trong thu vien, gap lai cha, roi quyet tam cuu gia toc Lombardy.",
        ),
        db,
    )

    def timeout_run(db, prompt, schema, *, timeout_seconds=300):
        if schema is story_studio.STORY_CANDIDATE_SCHEMA:
            raise story_studio.StoryStudioError("provider timed out")
        if schema is story_studio.STORY_EVALUATION_SCHEMA:
            return _evaluation_payload()
        raise AssertionError("Unexpected schema")

    monkeypatch.setattr(story_studio, "_run_structured_ai", timeout_run)

    episode = story_studio.generate_candidates(episode.id, db)

    assert len(episode.candidates) == 3
    assert {candidate.generation_status for candidate in episode.candidates} == {"completed"}
    assert {candidate.evaluation_status for candidate in episode.candidates} == {"completed"}
    payloads = [candidate.script_json for candidate in episode.candidates]
    story_studio._validate_distinct_candidates(payloads)
    for index, left in enumerate(payloads):
        for right in payloads[index + 1 :]:
            assert story_studio._jaccard(
                story_studio._candidate_signature(left),
                story_studio._candidate_signature(right),
            ) <= 0.82

def test_story_candidate_failure_persists_status_rows(db, monkeypatch):
    series = video_projects.create_series(
        models.VideoSeriesCreate(title="Failure rows", series_mode="image_story_only"),
        db,
    )
    episode = story_studio.create_episode(
        series.id,
        models.StoryEpisodeCreate(output_intent="truyen_anh", source_input="Can luu trang thai loi."),
        db,
    )

    def failing_run(db, prompt, schema, *, timeout_seconds=300):
        if schema is story_studio.STORY_CANDIDATE_SCHEMA:
            if "visual_action" in prompt:
                raise story_studio.StoryStudioError("invalid schema for response_format")
            for index, (strategy_type, _label) in enumerate(story_studio.STRATEGIES, start=1):
                if strategy_type in prompt:
                    return _candidate_payload(strategy_type, index)
        if schema is story_studio.STORY_EVALUATION_SCHEMA:
            return _evaluation_payload()
        raise AssertionError("Unexpected schema")

    monkeypatch.setattr(story_studio, "_run_structured_ai", failing_run)

    with pytest.raises(story_studio.StoryStudioError):
        story_studio.generate_candidates(episode.id, db)

    rows = (
        db.query(DBStoryScenarioCandidate)
        .filter(DBStoryScenarioCandidate.story_episode_id == episode.id)
        .order_by(DBStoryScenarioCandidate.strategy_type)
        .all()
    )
    assert len(rows) == 3
    by_strategy = {row.strategy_type: row for row in rows}
    assert by_strategy["hook_retention"].generation_status == "completed"
    assert by_strategy["emotional_drama"].generation_status == "completed"
    assert by_strategy["visual_action"].generation_status == "failed"
    assert by_strategy["visual_action"].evaluation_status == "failed"
    assert "invalid schema" in by_strategy["visual_action"].script_json["error_message"]


def test_story_candidate_distinctness_is_enforced(db, monkeypatch):
    series = video_projects.create_series(
        models.VideoSeriesCreate(title="Distinct", series_mode="image_story_only"),
        db,
    )
    episode = story_studio.create_episode(
        series.id,
        models.StoryEpisodeCreate(output_intent="truyen_anh", source_input="Ba huong khong duoc giong nhau."),
        db,
    )

    def same_story_run(db, prompt, schema, *, timeout_seconds=300):
        if schema is story_studio.STORY_CANDIDATE_SCHEMA:
            for strategy_type, _label in story_studio.STRATEGIES:
                if strategy_type in prompt:
                    return _candidate_payload(
                        strategy_type,
                        hook="Same hook",
                        full_story="Same body " * 80,
                        key_beats=["same beat", "same middle", "same end"],
                        visual_moments=["same visual"],
                        motion_beats=["same motion"],
                    )
        if schema is story_studio.STORY_EVALUATION_SCHEMA:
            return _evaluation_payload()
        raise AssertionError("Unexpected schema")

    monkeypatch.setattr(story_studio, "_run_structured_ai", same_story_run)

    with pytest.raises(story_studio.StoryStudioError):
        story_studio.generate_candidates(episode.id, db)

def test_synthesize_master_story_keeps_sources_and_pending_approval(db):
    series = video_projects.create_series(
        models.VideoSeriesCreate(title="Synthesis", series_mode="image_story_only"),
        db,
    )
    episode = story_studio.create_episode(
        series.id,
        models.StoryEpisodeCreate(output_intent="truyen_anh", source_input="Tong hop ba huong."),
        db,
    )
    episode = story_studio.generate_candidates(episode.id, db)

    episode = story_studio.synthesize_master_story(
        episode.id,
        models.StoryCandidateSynthesisRequest(candidate_ids=[candidate.id for candidate in episode.candidates]),
        db,
    )

    assert episode.approval_status == "pending_approval"
    assert episode.master_story_json["synthesis_sources"]
    assert episode.master_story_json["canon_check"]["passed"] is True

def test_synthesize_timeout_uses_source_grounded_master_and_image_prompts(db, monkeypatch):
    series = video_projects.create_series(
        models.VideoSeriesCreate(title="Lombardi showcase", series_mode="image_story_only"),
        db,
    )
    source = """
CẢNH 1 — LỜI THỪA NHẬN QUÁ MUỘN

Trong căn phòng bệnh đêm muộn, ông nội Lombardi nhìn Florentia thật lâu. Trên bàn là những tập hồ sơ cô đã xử lý thay cả gia tộc.

ÔNG NỘI:
“Ta đã không biết cháu có năng lực đến mức này.”

Florentia không đáp. Cô chỉ khép tập hồ sơ trong tay.

ÔNG NỘI:
“Nếu ta nhận ra sớm hơn... ta đã có thể giao gia tộc này cho cháu.”

Không gian như đông cứng. Đó là lời công nhận Florentia khao khát suốt nhiều năm, nhưng nó đến quá muộn.

FLORENTIA:
“Nhưng cháu chỉ là một đứa con ngoài giá thú, thưa ông.”

CẢNH 2 — ĐỨA TRẺ MANG HỌ LOMBARDI

Florentia sinh ra trong dinh thự Lombardi nhưng không được nhìn như một người thừa kế hợp pháp. Mẹ cô là thường dân và mất khi sinh cô.

Cha cô, Gallahan Lombardi, là người duy nhất cúi xuống ngang tầm con gái và nói rằng cô là một Lombardi.

CẢNH 3 — NGÀY TẤM KHIÊN BIẾN MẤT

Vài ngày trước sinh nhật mười một tuổi, Gallahan qua đời. Florentia đứng bên giường bệnh, nhìn bàn tay cha không còn có thể đáp lại.

Từ ngày đó, cô không chỉ mất cha; cô mất người duy nhất sẵn lòng bảo vệ mình.

CẢNH 4 — BỊ LÃNG QUÊN TRONG CHÍNH DINH THỰ

Dinh thự vẫn đông người, nhưng chỗ ngồi của Florentia ngày càng xa hơn. Người ta quên hỏi cô đã ăn chưa, rồi quên gọi cô đến.

Florentia đứng ngoài ánh sáng của căn phòng lớn và hiểu rằng nếu tiếp tục chờ đợi, một ngày nào đó họ sẽ vứt bỏ cô hoàn toàn.

CẢNH 5 — TỰ CHỨNG MINH

Sau khi tròn mười lăm tuổi, Florentia ôm chồng giấy tờ tới phòng làm việc và xin được giao việc. Không ai tin cô có thể làm được.

Cô học luật lệ gia tộc, cách vận hành tiền bạc, cách đọc báo cáo và cách nhận ra sai sót người khác bỏ qua.

CẢNH 6 — NGƯỜI NẮM DÒNG TIỀN

Năm mười tám tuổi, Florentia được giao quản lý tài chính nhà Lombardi. Những người từng không nhìn thấy cô bắt đầu tìm đến cô mỗi khi sổ sách có vấn đề.

Năm mười chín tuổi, cô trở thành trợ lý kinh doanh cho ông nội. Công việc đáng lẽ thuộc về người có địa vị cao hơn, nhưng họ bất tài và chỉ dựa vào họ mình.

CẢNH 7 — CÂU HỎI CỦA TẬP SAU

Florentia đã làm mọi việc của một Lombardi, nhưng không bao giờ được quyền đòi hỏi những gì thuộc về một Lombardi. Lời thừa nhận ấy có thể là khởi đầu của biến cố thay đổi số phận cô.
""".strip()
    episode = story_studio.create_episode(
        series.id,
        models.StoryEpisodeCreate(output_intent="truyen_anh", title="Đứa Con Ngoài Giá Thú Của Lombardi", source_input=source),
        db,
    )
    episode = story_studio.generate_candidates(episode.id, db)

    def timeout_synthesis(db, prompt, schema, *, timeout_seconds=300):
        if schema is story_studio.STORY_SYNTHESIS_SCHEMA:
            raise story_studio.StoryStudioError("provider timed out")
        raise AssertionError("Only synthesis should run in this test")

    monkeypatch.setattr(story_studio, "_run_structured_ai", timeout_synthesis)

    episode = story_studio.synthesize_master_story(
        episode.id,
        models.StoryCandidateSynthesisRequest(user_direction="hook mạnh, nhiều nội dung, dùng được để tạo truyện ảnh"),
        db,
    )
    master = episode.master_story_json

    assert episode.approval_status == "pending_approval"
    assert master["fallback_used"] is True
    assert "con ngoài giá thú" in master["hook"]
    assert "Florentia" in master["full_story"]
    assert len(master["key_beats"]) >= story_studio.MIN_AUTO_IMAGE_PANEL_COUNT
    assert len(master["visual_moments"]) == len(master["key_beats"])
    assert "720x1280" in master["image_story_notes"]
    assert "placeholder" not in master["full_story"].lower()

    episode = story_studio.approve_master_story(episode.id, models.StoryApprovalRequest(approved=True), db)
    adaptation = story_studio.create_image_adaptation(episode.id, db)
    panels = adaptation.payload_json["panels"]

    assert len(panels) >= story_studio.MIN_AUTO_IMAGE_PANEL_COUNT
    first_panel = panels[0]
    assert first_panel["scene_context"]
    assert first_panel["camera_angle"]
    assert first_panel["composition_notes"]
    assert first_panel["dialogue_note"]
    assert "Scene context:" in first_panel["prompt"]
    assert "Camera angle/framing:" in first_panel["prompt"]
    assert "Dialogue/caption note:" in first_panel["prompt"]
    assert "720x1280px" in first_panel["prompt"]

def test_prompt_quality_rejects_complete_but_contradictory_prompt():
    panel = {
        "prompt": (
            "Vertical cinematic story panel image, close-up wide shot, day night, keep canon and character "
            "continuity, clear composition and framing, one readable action beat, consistent style."
        ),
        "caption_or_dialogue": "Caption rieng.",
        "visual_description": "Nhan vat thuc hien mot hanh dong chinh ro rang trong panel.",
        "character_consistency_notes": "Lan giu ao khoac xanh va fixed traits.",
        "style_notes": "Cinematic illustration",
        "purpose": "hook beat",
    }

    quality = story_studio._story_panel_quality_check(panel, canon_check={"passed": True})

    assert quality["passed"] is False
    assert "internal_contradiction" in quality["blocking_errors"]

def test_prompt_quality_allows_left_right_character_traits():
    panel = {
        "prompt": (
            "Vertical cinematic story panel image, close-up composition and framing, keep canon and character "
            "continuity. Lan has a small scar near left eyebrow. Minh has a grease mark on right cheek. "
            "One readable action beat, consistent style, story panel."
        ),
        "caption_or_dialogue": "Caption rieng.",
        "visual_description": "Lan va Minh thuc hien mot hanh dong chinh ro rang trong panel.",
        "character_consistency_notes": "Lan giu ao khoac xanh; Minh giu ban do ga.",
        "style_notes": "Cinematic illustration",
        "purpose": "hook beat",
    }

    quality = story_studio._story_panel_quality_check(panel, canon_check={"passed": True})

    assert quality["passed"] is True
    assert "internal_contradiction" not in quality["blocking_errors"]

def test_prompt_repair_versions_and_stops_after_pass(db):
    series = video_projects.create_series(
        models.VideoSeriesCreate(title="Repair", series_mode="image_story_only", character_bible="Lan giu ao khoac xanh."),
        db,
    )
    episode = story_studio.create_episode(
        series.id,
        models.StoryEpisodeCreate(output_intent="truyen_anh", source_input="Sua prompt panel."),
        db,
    )
    episode = story_studio.select_master_story(
        episode.id,
        models.StoryCandidateSelectionRequest(master_story_json=_valid_master()),
        db,
    )
    episode = story_studio.approve_master_story(episode.id, models.StoryApprovalRequest(approved=True), db)
    story_studio.create_image_adaptation(episode.id, db)
    story_studio.update_panel_prompt(
        episode.id,
        models.StoryPanelPromptUpdateRequest(
            panel_order=1,
            prompt="video prompt close-up wide shot day night",
        ),
        db,
    )

    adaptation = story_studio.repair_panel_prompt(
        episode.id,
        models.StoryPromptRepairRequest(panel_order=1, max_attempts=2),
        db,
    )
    panel = adaptation.payload_json["panels"][0]

    assert panel["repair_attempt"] == 1
    assert panel["repair_status"] == "passed"
    assert panel["quality_check"]["passed"] is True
    assert panel["prompt_status"] == "pending_approval"
    assert panel["render_status"] == "not_requested"
    assert len(panel["prompt_versions"]) >= 3

def test_story_studio_image_series_prompt_first_without_provider(db):
    series = video_projects.create_series(
        models.VideoSeriesCreate(title="Truyện ảnh", series_mode="image_story_only", character_bible="Lan là nhân vật chính."),
        db,
    )
    profile = video_projects.create_character_profile(
        series.id,
        models.SeriesCharacterProfileCreate(
            name="Lan",
            role="Nhân vật chính",
            face_description="Mặt trái xoan",
            hair_description="Tóc đen ngang vai",
            body_description="Dáng nhỏ",
            signature_outfit="Áo khoác xanh",
            personality="Can đảm",
            speech_style="Nói ngắn, rõ",
            fixed_traits="Không đổi tóc đen và áo khoác xanh",
        ),
        db,
    )

    assert profile is not None
    with pytest.raises(ValueError, match="trực tiếp"):
        video_projects.create_episode(series.id, models.VideoEpisodeCreate(topic="Không được tạo video trực tiếp"), db)

    episode = story_studio.create_episode(
        series.id,
        models.StoryEpisodeCreate(output_intent="truyen_anh", source_input="Lan tìm thấy một cánh cửa bí mật."),
        db,
    )
    assert episode is not None

    episode = story_studio.generate_candidates(episode.id, db)
    assert episode is not None
    assert len(episode.candidates) == 3

    episode = story_studio.select_master_story(
        episode.id,
        models.StoryCandidateSelectionRequest(candidate_id=episode.candidates[0].id),
        db,
    )
    assert episode.approval_status == "pending_approval"

    episode = story_studio.approve_master_story(episode.id, models.StoryApprovalRequest(approved=True), db)
    assert episode.approval_status == "approved"
    summary_cards = (
        db.query(DBSeriesMemoryCard)
        .filter(DBSeriesMemoryCard.series_id == series.id, DBSeriesMemoryCard.status == "approved")
        .all()
    )
    assert {"episode_summary", "arc_summary", "series_summary"}.issubset({card.card_type for card in summary_cards})

    adaptation = story_studio.create_image_adaptation(episode.id, db)
    panels = adaptation.payload_json["panels"]
    assert panels
    assert panels[0]["prompt_status"] == "pending_approval"
    assert panels[0]["render_status"] == "not_requested"
    assert "Không đổi tóc đen" in panels[0]["prompt"]

    adaptation = story_studio.approve_image_prompts(
        episode.id,
        models.StoryPanelPromptApprovalRequest(approved=True),
        db,
    )
    panels = adaptation.payload_json["panels"]
    assert {panel["prompt_status"] for panel in panels} == {"approved"}
    assert {panel["render_status"] for panel in panels} == {"waiting_provider"}

    adaptation = story_studio.request_image_render(episode.id, models.StoryImageRenderRequest(), db)
    assert adaptation.status == "waiting_provider"
    assert adaptation.payload_json["image_provider_configured"] is False

    memory_path = video_series_memory.sync_series_memory_file(series.id, db)
    memory = memory_path.read_text(encoding="utf-8")
    assert "voicebox:series-memory:v2" in memory
    assert "Lan" in memory
    assert "Story Studio Episode Index" in memory


def test_image_adaptation_uses_all_master_beats_not_fixed_eight(db):
    series = video_projects.create_series(
        models.VideoSeriesCreate(title="Long image story", series_mode="image_story_only"),
        db,
    )
    episode = story_studio.create_episode(
        series.id,
        models.StoryEpisodeCreate(output_intent="truyen_anh", source_input="A longer story needs more than eight panels."),
        db,
    )
    master = _valid_master(
        key_beats=[f"beat {index}" for index in range(1, 16)],
        visual_moments=[f"visual {index}" for index in range(1, 16)],
        motion_beats=[f"motion {index}" for index in range(1, 16)],
    )
    episode = story_studio.select_master_story(
        episode.id,
        models.StoryCandidateSelectionRequest(master_story_json=master),
        db,
    )
    episode = story_studio.approve_master_story(episode.id, models.StoryApprovalRequest(approved=True), db)

    adaptation = story_studio.create_image_adaptation(episode.id, db)
    panels = adaptation.payload_json["panels"]

    assert len(panels) >= story_studio.MIN_AUTO_IMAGE_PANEL_COUNT
    assert [panel["order"] for panel in panels[:15]] == list(range(1, 16))
    assert panels[14]["purpose"] == "beat 15"
    assert panels[14]["visual_description"] == "visual 15"
    assert "Motion/camera beat: motion 15" in panels[14]["prompt"]


def test_image_adaptation_manual_panel_count_and_image_size(db):
    series = video_projects.create_series(
        models.VideoSeriesCreate(title="Manual image story", series_mode="image_story_only"),
        db,
    )
    episode = story_studio.create_episode(
        series.id,
        models.StoryEpisodeCreate(
            output_intent="truyen_anh",
            source_input="Manual scroll story.",
            output_settings=models.StoryEpisodeOutputSettings(
                image=models.StoryImageOutputSettings(
                    panel_mode="manual",
                    panel_count=12,
                    aspect_ratio="4:5",
                    width=1080,
                    height=1350,
                )
            ),
        ),
        db,
    )
    master = _valid_master(
        key_beats=["beat 1", "beat 2", "beat 3"],
        visual_moments=["visual 1", "visual 2", "visual 3"],
        motion_beats=["motion 1", "motion 2", "motion 3"],
    )
    episode = story_studio.select_master_story(
        episode.id,
        models.StoryCandidateSelectionRequest(master_story_json=master),
        db,
    )
    episode = story_studio.approve_master_story(episode.id, models.StoryApprovalRequest(approved=True), db)

    adaptation = story_studio.create_image_adaptation(episode.id, db)
    payload = adaptation.payload_json
    panels = payload["panels"]

    assert len(panels) == 12
    assert payload["panel_count"] == 12
    assert payload["panel_generation_source"] == "manual_master_story"
    assert payload["output_settings"]["image"]["panel_count"] == 12
    assert payload["output_settings"]["image"]["aspect_ratio"] == "4:5"
    assert all(panel["aspect_ratio"] == "4:5" for panel in panels)
    assert all(panel["width"] == 1080 and panel["height"] == 1350 for panel in panels)
    assert all("Image format: 4:5, 1080x1350px" in panel["prompt"] for panel in panels)


def test_image_adaptation_sanitizes_panel_captions_and_prompt_text(db):
    series = video_projects.create_series(
        models.VideoSeriesCreate(title="Sanitize panels", series_mode="image_story_only", style_bible="Clean manga panel"),
        db,
    )
    episode = story_studio.create_episode(
        series.id,
        models.StoryEpisodeCreate(
            output_intent="truyen_anh",
            language_profile="en",
            source_input="OCR labels must not become rendered bubble text.",
            output_settings=models.StoryEpisodeOutputSettings(
                image=models.StoryImageOutputSettings(
                    panel_mode="manual",
                    panel_count=3,
                    aspect_ratio="9:16",
                    width=720,
                    height=1280,
                ),
                video=models.StoryVideoHandoffSettings(target_language="en"),
            ),
        ),
        db,
    )
    episode = story_studio.select_master_story(
        episode.id,
        models.StoryCandidateSelectionRequest(
            master_story_json=_valid_master(
                key_beats=[
                    "Hook mở màn: Trong căn phòng bệnh, ông nội thú nhận quá muộn.",
                    "[65] dialogue: Even at the last moment, you still don’t understand.",
                    "[46] narration: Tác phẩm này được Công ty D&C Webtoon Biz phát hành theo hợp đồng.",
                ],
                visual_moments=[
                    "Florentia holds a folder beside a hospital bed.",
                    "Close-up of Florentia's cold expression.",
                    "A quiet palace corridor after the confession.",
                ],
                motion_beats=["slow push-in", "still hold", "fade out"],
            )
        ),
        db,
    )
    episode = story_studio.approve_master_story(episode.id, models.StoryApprovalRequest(approved=True), db)

    adaptation = story_studio.create_image_adaptation(episode.id, db)
    panels = adaptation.payload_json["panels"]
    all_prompt_text = "\n".join(
        "\n".join(
            str(panel.get(key) or "")
            for key in ("caption_or_dialogue", "purpose", "visual_description", "dialogue_note", "prompt", "negative_prompt")
        )
        for panel in panels
    )

    assert panels[0]["caption_or_dialogue"] == ""
    assert panels[1]["caption_or_dialogue"] == "Even at the last moment, you still don’t understand."
    assert "Hook mở màn" not in all_prompt_text
    assert "CẢNH" not in all_prompt_text
    assert "[65]" not in all_prompt_text
    assert "[46]" not in all_prompt_text
    assert "Tác phẩm này được Công ty" not in all_prompt_text
    assert "Viewer-facing text language lock: tiếng Anh / English" in panels[0]["prompt"]


def test_image_adaptation_auto_uses_linked_video_micro_scenes(db):
    series = video_projects.create_series(
        models.VideoSeriesCreate(title="Hybrid micro scenes", series_mode="hybrid"),
        db,
    )
    episode = story_studio.create_episode(
        series.id,
        models.StoryEpisodeCreate(output_intent="ca_hai", source_input="Hybrid source."),
        db,
    )
    episode = story_studio.select_master_story(
        episode.id,
        models.StoryCandidateSelectionRequest(master_story_json=_valid_master()),
        db,
    )
    episode = story_studio.approve_master_story(episode.id, models.StoryApprovalRequest(approved=True), db)
    video_adaptation = story_studio.create_video_adaptation(
        episode.id,
        models.StoryVideoHandoffRequest(open_existing=True),
        db,
    )
    project_id = video_adaptation.linked_video_project_id
    assert project_id
    db.add_all(
        [
            DBVideoShot(
                id="shot-1",
                project_id=project_id,
                shot_order=1,
                vietnamese_description="Lan buoc vao ham",
                primary_action="Lan soi den pin",
                camera_motion="push-in",
                micro_scenes_json=[
                    {
                        "order": 1,
                        "description_vi": "Lan thay cua sat",
                        "visual_action": "Lan cham vao cua sat",
                        "camera_note": "slow push",
                        "start_seconds": 0,
                        "end_seconds": 2,
                    },
                    {
                        "order": 2,
                        "description_vi": "Cua sat mo ra",
                        "visual_action": "Anh sang lot qua khe cua",
                        "camera_note": "tilt up",
                        "start_seconds": 2,
                        "end_seconds": 4,
                    },
                ],
            ),
            DBVideoShot(
                id="shot-2",
                project_id=project_id,
                shot_order=2,
                vietnamese_description="Lan doi mat bi mat",
                primary_action="Lan dung yen",
                camera_motion="handheld",
                micro_scenes_json=[
                    {
                        "order": 1,
                        "description_vi": "Bong nguoi xuat hien",
                        "visual_action": "Bong nguoi in tren tuong",
                        "camera_note": "rack focus",
                    }
                ],
            ),
        ]
    )
    db.commit()

    image_adaptation = story_studio.create_image_adaptation(episode.id, db)
    panels = image_adaptation.payload_json["panels"]

    assert len(panels) == 3
    assert image_adaptation.payload_json["panel_generation_source"] == "video_micro_scenes"
    assert [panel["source_type"] for panel in panels] == ["video_micro_scene"] * 3
    assert [panel["source_shot_order"] for panel in panels] == [1, 1, 2]
    assert [panel["source_micro_scene_order"] for panel in panels] == [1, 2, 1]


def test_hybrid_story_video_handoff_creates_linked_ai_video_project(db):
    series = video_projects.create_series(
        models.VideoSeriesCreate(title="Series chung", series_mode="hybrid", style_bible="Cinematic webtoon"),
        db,
    )
    with pytest.raises(ValueError, match="handoff"):
        video_projects.create_episode(series.id, models.VideoEpisodeCreate(topic="Không tạo trực tiếp trong hybrid"), db)

    episode = story_studio.create_episode(
        series.id,
        models.StoryEpisodeCreate(
            output_intent="ca_hai",
            title="Cửa thứ nhất",
            source_input="Một bí mật mở đầu series.",
            output_settings=models.StoryEpisodeOutputSettings(
                video=models.StoryVideoHandoffSettings(
                    aspect_ratio="16:9",
                    target_language="en",
                    video_purpose="global_short",
                    dialogue_mode="mixed",
                    narration_density="dense",
                    call_to_action_style="soft",
                    default_shot_duration_seconds=4,
                    prompt_segment_count=6,
                    prompt_segment_duration_seconds=8,
                    micro_scenes_per_prompt=2,
                )
            ),
        ),
        db,
    )
    episode = story_studio.generate_candidates(episode.id, db)
    episode = story_studio.select_master_story(
        episode.id,
        models.StoryCandidateSelectionRequest(candidate_id=episode.candidates[0].id),
        db,
    )
    episode = story_studio.approve_master_story(episode.id, models.StoryApprovalRequest(approved=True), db)

    video_adaptation = story_studio.create_video_adaptation(
        episode.id,
        models.StoryVideoHandoffRequest(open_existing=True),
        db,
    )

    assert video_adaptation.linked_video_project_id
    project = db.get(DBVideoProject, video_adaptation.linked_video_project_id)
    assert project is not None
    assert project.series_id == series.id
    assert project.story_episode_id == episode.id
    assert project.episode_number == episode.episode_number
    assert project.phase == "phase2"
    assert project.aspect_ratio == "16:9"
    assert project.target_language == "en"
    assert project.video_purpose == "global_short"
    assert project.dialogue_mode == "mixed"
    assert project.narration_density == "dense"
    assert project.call_to_action_style == "soft"
    assert project.default_shot_duration_seconds == 4
    assert project.prompt_segment_count == 6
    assert project.prompt_segment_duration_seconds == 8
    assert project.micro_scenes_per_prompt == 2
    assert project.target_duration_seconds == 48
    source_blocks = (
        db.query(DBVideoSourceBlock)
        .filter(DBVideoSourceBlock.project_id == project.id)
        .order_by(DBVideoSourceBlock.sort_order.asc())
        .all()
    )
    assert source_blocks[0].block_type == "language_lock"
    assert "Do not copy Vietnamese dialogue" in source_blocks[0].content
    assert "Translate/rewrite for English viewer-facing output" in source_blocks[1].content
    assert video_adaptation.payload_json["handoff_only"] is True
    assert video_adaptation.payload_json["settings_source"] == "story_episode.output_settings"
    assert video_adaptation.payload_json["handoff_settings"]["aspect_ratio"] == "16:9"


def test_image_story_video_handoff_from_truyen_anh_prompts_creates_ai_video_project(db):
    _series, episode, image_adaptation = _story_episode_with_image_prompts(db, output_intent="truyen_anh")

    video_adaptation = story_studio.create_video_adaptation(
        episode.id,
        models.StoryVideoHandoffRequest(
            open_existing=True,
            source_mode="image_story_prompts",
            start_auto_run=False,
        ),
        db,
    )

    assert video_adaptation.linked_video_project_id
    payload = video_adaptation.payload_json
    assert payload["handoff_source"] == "image_story_prompts"
    assert payload["source_mode_requested"] == "image_story_prompts"
    assert payload["source_mode_resolved"] == "image_story_prompts"
    assert payload["source_panel_count"] == 3
    assert payload["source_prompt_count"] == 3
    assert payload["source_image_adaptation_id"] == image_adaptation.id
    assert payload["source_image_adaptation_revision"] == image_adaptation.revision
    assert payload["story_episode_output_intent"] == "truyen_anh"
    assert payload["ai_video_url"].endswith(video_adaptation.linked_video_project_id)

    project = db.get(DBVideoProject, video_adaptation.linked_video_project_id)
    assert project is not None
    assert project.story_episode_id == episode.id
    assert project.series_id == episode.series_id
    source_blocks = (
        db.query(DBVideoSourceBlock)
        .filter(DBVideoSourceBlock.project_id == project.id)
        .order_by(DBVideoSourceBlock.sort_order.asc())
        .all()
    )
    block_types = [block.block_type for block in source_blocks]
    all_source = "\n\n".join(block.content for block in source_blocks)
    assert "idea" in block_types
    assert any(block_type.startswith("storyboard_panels") for block_type in block_types)
    assert any(block_type.startswith("image_prompts") for block_type in block_types)
    assert "Panel 1" in all_source
    assert "Caption/dialogue" in all_source
    assert "Camera angle" in all_source
    assert "Prompt ảnh gốc" in all_source
    assert "Lan luôn mặc áo khoác xanh" in all_source
    assert "phát triển lại thành video" in all_source


def test_image_story_video_handoff_without_prompts_has_helpful_error(db):
    series = video_projects.create_series(
        models.VideoSeriesCreate(title="Thiếu prompt", series_mode="image_story_only"),
        db,
    )
    episode = story_studio.create_episode(
        series.id,
        models.StoryEpisodeCreate(output_intent="truyen_anh", source_input="Chưa tạo panel."),
        db,
    )
    story_studio.select_master_story(
        episode.id,
        models.StoryCandidateSelectionRequest(master_story_json=_valid_master()),
        db,
    )
    story_studio.approve_master_story(episode.id, models.StoryApprovalRequest(approved=True), db)

    with pytest.raises(story_studio.StoryStudioError, match="tạo panel/prompt truyện"):
        story_studio.create_video_adaptation(
            episode.id,
            models.StoryVideoHandoffRequest(source_mode="image_story_prompts"),
            db,
        )


def test_image_story_video_handoff_start_auto_run_prompts_only(db, monkeypatch):
    def fake_background_task(coro):
        coro.close()
        return None

    monkeypatch.setattr(video_auto_runs, "create_background_task", fake_background_task)
    _series, episode, _image_adaptation = _story_episode_with_image_prompts(db, output_intent="truyen_anh")

    video_adaptation = story_studio.create_video_adaptation(
        episode.id,
        models.StoryVideoHandoffRequest(
            source_mode="image_story_prompts",
            start_auto_run=True,
            material_target="prompts_only",
        ),
        db,
    )

    payload = video_adaptation.payload_json
    assert payload["handoff_source"] == "image_story_prompts"
    assert payload["auto_run_id"]
    assert payload["auto_run_material_target"] == "prompts_only"
    run = db.get(DBVideoAutoRun, payload["auto_run_id"])
    assert run is not None
    assert run.project_id == video_adaptation.linked_video_project_id
    assert run.mode == "full_auto"
    assert run.step_results_json["material_target"] == "prompts_only"
    assert db.query(DBVideoRenderJob).filter(DBVideoRenderJob.project_id == run.project_id).count() == 0


def test_character_profile_crud_reorder_and_bible_fallback(db):
    series = video_projects.create_series(
        models.VideoSeriesCreate(title="Fallback", series_mode="image_story_only", character_bible="Minh luôn đội mũ đỏ."),
        db,
    )
    first = video_projects.create_character_profile(
        series.id,
        models.SeriesCharacterProfileCreate(name="Lan", role="Bạn đồng hành", sort_order=1),
        db,
    )
    second = video_projects.create_character_profile(
        series.id,
        models.SeriesCharacterProfileCreate(name="Minh", role="Nhân vật chính", sort_order=2),
        db,
    )

    updated = video_projects.update_character_profile(
        series.id,
        first.id,
        models.SeriesCharacterProfileUpdate(fixed_traits="Không đổi khăn vàng."),
        db,
    )
    assert updated.fixed_traits == "Không đổi khăn vàng."

    reordered = video_projects.reorder_character_profiles(
        series.id,
        models.SeriesCharacterProfileReorderRequest(profile_ids=[second.id, first.id]),
        db,
    )
    assert [profile.id for profile in reordered] == [second.id, first.id]

    assert video_projects.delete_character_profile(series.id, first.id, db) is True
    assert len(video_projects.list_character_profiles(series.id, db)) == 1

    fallback_series = video_projects.create_series(
        models.VideoSeriesCreate(title="Bible only", series_mode="image_story_only", character_bible="An có áo choàng bạc."),
        db,
    )
    episode = story_studio.create_episode(
        fallback_series.id,
        models.StoryEpisodeCreate(output_intent="truyen_anh", source_input="An bước vào hang."),
        db,
    )
    episode = story_studio.generate_candidates(episode.id, db)
    episode = story_studio.select_master_story(
        episode.id,
        models.StoryCandidateSelectionRequest(candidate_id=episode.candidates[0].id),
        db,
    )
    episode = story_studio.approve_master_story(episode.id, models.StoryApprovalRequest(approved=True), db)
    adaptation = story_studio.create_image_adaptation(episode.id, db)
    assert "áo choàng bạc" in adaptation.payload_json["panels"][0]["prompt"]


def test_story_studio_approval_and_stale_guards(db):
    series = video_projects.create_series(
        models.VideoSeriesCreate(title="Guards", series_mode="image_story_only"),
        db,
    )
    episode = story_studio.create_episode(
        series.id,
        models.StoryEpisodeCreate(output_intent="truyen_anh", source_input="Một tập cần guard."),
        db,
    )

    with pytest.raises(story_studio.StoryStudioError, match="duyệt Master Story"):
        story_studio.create_image_adaptation(episode.id, db)

    episode = story_studio.generate_candidates(episode.id, db)
    with pytest.raises(story_studio.StoryStudioError, match="thiếu trường"):
        story_studio.select_master_story(
            episode.id,
            models.StoryCandidateSelectionRequest(master_story_json={"title": "Thiếu"}),
            db,
        )

    episode = story_studio.select_master_story(
        episode.id,
        models.StoryCandidateSelectionRequest(candidate_id=episode.candidates[0].id),
        db,
    )
    episode = story_studio.approve_master_story(episode.id, models.StoryApprovalRequest(approved=True), db)
    adaptation = story_studio.create_image_adaptation(episode.id, db)

    with pytest.raises(story_studio.StoryStudioError, match="đã duyệt"):
        story_studio.request_image_render(episode.id, models.StoryImageRenderRequest(), db)

    adaptation = story_studio.approve_image_prompts(
        episode.id,
        models.StoryPanelPromptApprovalRequest(approved=True),
        db,
    )
    assert adaptation.payload_json["panels"][0]["prompt_status"] == "approved"

    adaptation = story_studio.update_panel_prompt(
        episode.id,
        models.StoryPanelPromptUpdateRequest(panel_order=1, prompt="New prompt"),
        db,
    )
    assert adaptation.payload_json["panels"][0]["prompt_status"] == "pending_approval"
    assert adaptation.payload_json["panels"][0]["render_status"] == "not_requested"

    episode = story_studio.approve_master_story(episode.id, models.StoryApprovalRequest(approved=True), db)
    updated = story_studio.update_episode(
        episode.id,
        models.StoryEpisodeUpdate(
            master_story_json={
                **episode.master_story_json,
                "full_story": "Nội dung đã sửa sau khi duyệt.",
            }
        ),
        db,
    )
    assert updated.approval_status == "pending_approval"
    assert updated.adaptations[0].status == "stale"


def test_master_story_validation_keeps_existing_data_on_invalid_update(db):
    series = video_projects.create_series(
        models.VideoSeriesCreate(title="Validate master", series_mode="image_story_only"),
        db,
    )
    episode = story_studio.create_episode(
        series.id,
        models.StoryEpisodeCreate(output_intent="truyen_anh", source_input="Một tập cần validate."),
        db,
    )
    master = _valid_master(title="Master cũ", full_story="Nội dung cũ vẫn phải được giữ.")
    episode = story_studio.select_master_story(
        episode.id,
        models.StoryCandidateSelectionRequest(master_story_json=master),
        db,
    )
    assert {key: episode.master_story_json[key] for key in master} == master
    assert episode.master_story_json["canon_check"]["passed"] is True

    with pytest.raises(story_studio.StoryStudioError, match="thiếu trường"):
        story_studio.update_episode(
            episode.id,
            models.StoryEpisodeUpdate(master_story_json={"title": "Thiếu cấu trúc"}),
            db,
        )

    refreshed = story_studio.get_episode(episode.id, db)
    assert {key: refreshed.master_story_json[key] for key in master} == master
    assert refreshed.master_story_json["canon_check"]["passed"] is True

    row = db.get(DBStoryEpisode, episode.id)
    row.master_story_json = {"title": "Bị hỏng trong database"}
    row.approval_status = "pending_approval"
    db.commit()

    with pytest.raises(story_studio.StoryStudioError, match="thiếu trường"):
        story_studio.approve_master_story(episode.id, models.StoryApprovalRequest(approved=True), db)

    assert db.get(DBStoryEpisode, episode.id).approval_status == "pending_approval"


def test_image_render_job_updates_panel_asset_and_failure_state(db):
    series = video_projects.create_series(
        models.VideoSeriesCreate(title="Render jobs", series_mode="image_story_only"),
        db,
    )
    episode = story_studio.create_episode(
        series.id,
        models.StoryEpisodeCreate(output_intent="truyen_anh", source_input="Render một panel."),
        db,
    )
    episode = story_studio.select_master_story(
        episode.id,
        models.StoryCandidateSelectionRequest(master_story_json=_valid_master()),
        db,
    )
    story_studio.approve_master_story(episode.id, models.StoryApprovalRequest(approved=True), db)
    story_studio.create_image_adaptation(episode.id, db)

    with pytest.raises(story_studio.StoryStudioError, match="đã duyệt"):
        story_studio.request_image_render(
            episode.id,
            models.StoryImageRenderRequest(panel_orders=[1], image_provider_configured=True, provider="mock"),
            db,
        )

    story_studio.approve_image_prompts(
        episode.id,
        models.StoryPanelPromptApprovalRequest(panel_orders=[1, 2], approved=True),
        db,
    )
    adaptation = story_studio.request_image_render(
        episode.id,
        models.StoryImageRenderRequest(
            panel_orders=[1],
            image_provider_configured=True,
            provider="mock",
            provider_metadata={"batch": "A"},
        ),
        db,
    )
    job = adaptation.payload_json["render_jobs"][0]
    assert adaptation.payload_json["panels"][0]["render_status"] == "queued"
    assert job["provider"] == "mock"

    adaptation = story_studio.update_image_render_job(
        episode.id,
        job["id"],
        models.StoryImageRenderJobUpdateRequest(status="rendering", message="Đang render"),
        db,
    )
    assert adaptation.payload_json["panels"][0]["render_status"] == "rendering"

    with pytest.raises(story_studio.StoryStudioError, match="image_path"):
        story_studio.update_image_render_job(
            episode.id,
            job["id"],
            models.StoryImageRenderJobUpdateRequest(
                status="completed",
                results=[models.StoryImageRenderResult(panel_order=1, status="completed")],
            ),
            db,
        )

    adaptation = story_studio.update_image_render_job(
        episode.id,
        job["id"],
        models.StoryImageRenderJobUpdateRequest(
            status="completed",
            results=[
                models.StoryImageRenderResult(
                    panel_order=1,
                    status="completed",
                    image_path="story/panel-1.png",
                    provider_asset_id="asset-1",
                    provider_metadata={"seed": 123},
                )
            ],
        ),
        db,
    )
    first_panel = adaptation.payload_json["panels"][0]
    assert first_panel["render_status"] == "completed"
    assert first_panel["asset"]["image_path"] == "story/panel-1.png"
    assert first_panel["asset"]["provider_asset_id"] == "asset-1"

    failed = story_studio.request_image_render(
        episode.id,
        models.StoryImageRenderRequest(panel_orders=[2], image_provider_configured=True, provider="mock"),
        db,
    )
    failed_job = failed.payload_json["render_jobs"][-1]
    failed = story_studio.update_image_render_job(
        episode.id,
        failed_job["id"],
        models.StoryImageRenderJobUpdateRequest(status="failed", message="Provider lỗi"),
        db,
    )
    second_panel = failed.payload_json["panels"][1]
    assert second_panel["render_status"] == "failed"
    assert second_panel["failure_reason"] == "Provider lỗi"
    assert failed.status == "failed"


def test_story_suggestion_approval_is_explicit_and_updates_series_only_after_approval(db):
    series = video_projects.create_series(
        models.VideoSeriesCreate(title="Suggestions", series_mode="image_story_only"),
        db,
    )
    episode = story_studio.create_episode(
        series.id,
        models.StoryEpisodeCreate(output_intent="truyen_anh", source_input="Một tập có cập nhật."),
        db,
    )
    master = _valid_master(
        continuity_updates=["Cánh cửa bạc trở thành vật chứng của series."],
        character_profile_updates=[
            {
                "name": "Lan",
                "role": "Nhân vật chính",
                "face_description": "Mặt trái xoan",
                "fixed_traits": "Không đổi áo khoác xanh.",
            }
        ],
    )
    story_studio.select_master_story(
        episode.id,
        models.StoryCandidateSelectionRequest(master_story_json=master),
        db,
    )

    suggestion = story_studio.suggest_updates(episode.id, db)
    assert suggestion.saved is False
    original_continuity = db.get(DBVideoSeries, series.id).continuity_rules
    assert db.query(DBSeriesCharacterProfile).filter(DBSeriesCharacterProfile.series_id == series.id).count() == 0

    rejected = story_studio.approve_suggested_updates(
        episode.id,
        models.StorySuggestionApprovalRequest(approved=False, suggestions=suggestion.suggestions),
        db,
    )
    assert rejected.saved is False
    assert db.get(DBVideoSeries, series.id).continuity_rules == original_continuity
    assert db.query(DBSeriesCharacterProfile).filter(DBSeriesCharacterProfile.series_id == series.id).count() == 0

    approved = story_studio.approve_suggested_updates(
        episode.id,
        models.StorySuggestionApprovalRequest(approved=True, suggestions=suggestion.suggestions),
        db,
    )
    assert approved.saved is True
    profile = db.query(DBSeriesCharacterProfile).filter(DBSeriesCharacterProfile.series_id == series.id).one()
    assert profile.name == "Lan"
    assert profile.fixed_traits == "Không đổi áo khoác xanh."
    assert "Cánh cửa bạc" in db.get(DBVideoSeries, series.id).continuity_rules


def test_video_adaptation_reports_linked_ai_video_mp4_from_render_job(db):
    series = video_projects.create_series(
        models.VideoSeriesCreate(title="MP4 link", series_mode="hybrid"),
        db,
    )
    episode = story_studio.create_episode(
        series.id,
        models.StoryEpisodeCreate(output_intent="video_truyen", source_input="Một tập video."),
        db,
    )
    story_studio.select_master_story(
        episode.id,
        models.StoryCandidateSelectionRequest(master_story_json=_valid_master(title="Video tập 1")),
        db,
    )
    story_studio.approve_master_story(episode.id, models.StoryApprovalRequest(approved=True), db)
    video_adaptation = story_studio.create_video_adaptation(
        episode.id,
        models.StoryVideoHandoffRequest(open_existing=True),
        db,
    )
    project_id = video_adaptation.linked_video_project_id
    db.add(
        DBVideoRenderJob(
            project_id=project_id,
            status="completed",
            progress=1.0,
            output_path="renders/story-video.mp4",
            stale=False,
            current_step="Hoàn tất MP4",
            completed_at=datetime.utcnow(),
        )
    )
    db.commit()

    refreshed = story_studio.get_episode(episode.id, db)
    refreshed_video = next(item for item in refreshed.adaptations if item.kind == "video_story")

    assert refreshed_video.status == "completed"
    assert refreshed_video.payload_json["render_status"] == "completed"
    assert refreshed_video.payload_json["latest_mp4_path"] == "renders/story-video.mp4"
    assert refreshed_video.payload_json["latest_mp4_download_url"].endswith("/download")
    assert refreshed_video.payload_json["latest_render_job"]["status"] == "completed"
