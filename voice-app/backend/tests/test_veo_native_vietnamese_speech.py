from __future__ import annotations

import asyncio
import json
import zipfile
from types import SimpleNamespace

import pytest

from backend import config, database, models
from backend.database import (
    VideoProject as DBVideoProject,
    VideoShot as DBVideoShot,
    VideoShotClip as DBVideoShotClip,
    VideoShotPrompt as DBVideoShotPrompt,
    VideoSubtitle as DBVideoSubtitle,
    session as database_session,
)
from backend.services import (
    video_auto_runs,
    video_packages,
    video_phase2,
    video_planning_pool,
    video_projects,
    video_rendering,
    video_speech,
    video_storage,
    video_subtitles,
    video_voice,
)


@pytest.fixture
def db(tmp_path):
    config.set_data_dir(tmp_path)
    database.init_db()
    video_planning_pool.reset_for_tests()
    session = database_session.SessionLocal()
    try:
        yield session
    finally:
        session.close()
        video_planning_pool.reset_for_tests()
        database_session.engine.dispose()


def _add_vietnamese_project_shot(db, *, title: str = "Veo native Vietnamese"):
    created = video_projects.create_project(
        models.VideoProjectCreate(
            topic=title,
            phase="phase2",
            target_language="vi",
            aspect_ratio="9:16",
        ),
        db,
    )
    project = db.get(DBVideoProject, created.id)
    assert project is not None
    shot = DBVideoShot(
        project_id=project.id,
        shot_order=1,
        duration_seconds=10.0,
        vietnamese_description="Lan quay lại khi cánh cửa bí mật mở ra.",
        english_narration="Tôi biết anh đã giấu cánh cửa ở đâu.",
        primary_action="Lan turns toward the suspect while the hidden door opens.",
        retention_json={
            "visible_characters": [
                {
                    "name": "Lan",
                    "expression": "kiềm nén sợ hãi",
                    "action": "quay đầu nhìn thẳng nghi phạm",
                }
            ]
        },
        speech_cues_json=[
            {
                "speaker_name": "Lan",
                "speaker_role": "visible_character",
                "text": "Tôi biết anh đã giấu cánh cửa ở đâu.",
                "voice_description": "giọng nữ trầm ấm, rõ chữ, điềm tĩnh và nhất quán",
                "delivery": "nói chậm, dứt khoát, không lên giọng quá kịch",
                "emotion": "sợ hãi nhưng kiểm soát",
                "context": "Lan đối mặt nghi phạm khi cánh cửa bí mật vừa mở",
                "lip_sync_required": True,
            }
        ],
        status="ready",
        prompt_status="completed",
        voice_status="missing",
        subtitle_status="stale",
    )
    db.add(shot)
    db.commit()
    db.refresh(shot)
    return project, shot


def _add_ready_clip(db, project_id: str, shot_id: str, *, has_audio: bool = True, duration: float = 3.4):
    clip_path = video_storage.get_project_subdir(project_id, "shot_clips") / f"native-{shot_id}.mp4"
    clip_path.write_bytes(b"fake veo mp4")
    clip = DBVideoShotClip(
        project_id=project_id,
        shot_id=shot_id,
        source="provider",
        provider="veo",
        status="ready",
        file_path=video_storage.to_artifact_storage_path(clip_path),
        original_filename="veo-native.mp4",
        mime_type="video/mp4",
        size_bytes=clip_path.stat().st_size,
        duration_seconds=duration,
        has_audio=has_audio,
        is_active=True,
    )
    db.add(clip)
    db.commit()
    db.refresh(clip)
    return clip, clip_path


def test_speech_source_only_routes_vietnamese_to_veo_native():
    assert video_speech.speech_source_for_language("vi") == "veo_native"
    assert video_speech.speech_source_for_language("VI") == "veo_native"
    assert video_speech.speech_source_for_language("en") == "project_audio"
    assert video_speech.speech_source_for_language("ja") == "project_audio"
    assert video_speech.speech_source_for_language(None) == "project_audio"


def test_shot_breakdown_normalization_creates_structured_speech_cue_fallback():
    normalized = video_phase2._normalize_shot_breakdown_payload(
        {
            "shots": [
                {
                    "scene_order": 1,
                    "shot_order": 1,
                    "vietnamese_description": "Lan nói khi nhìn thấy cánh cửa mở.",
                    "english_narration": "Cánh cửa cuối cùng cũng mở rồi.",
                    "primary_action": "Lan looks at the opening hidden door.",
                    "visible_characters": [
                        {
                            "name": "Lan",
                            "expression": "kinh ngạc",
                        }
                    ],
                }
            ]
        },
        dialogue_mode="dialogue",
    )
    plan = video_phase2.ShotBreakdownPlan.model_validate(normalized)

    assert len(plan.shots[0].speech_cues) == 1
    cue = plan.shots[0].speech_cues[0]
    assert cue.speaker_name == "Lan"
    assert cue.text == "Cánh cửa cuối cùng cũng mở rồi."
    assert cue.speaker_role == "visible_character"
    assert cue.lip_sync_required is True


def test_veo_speech_section_contains_exact_line_voice_emotion_context_and_lip_sync(db):
    project, shot = _add_vietnamese_project_shot(db)

    section = video_speech.build_veo_native_speech_section(project, shot, db)

    assert "Vietnamese spoken dialogue" in section
    assert "Speaker 1: Lan" in section
    assert "giọng nữ trầm ấm, rõ chữ" in section
    assert "sợ hãi nhưng kiểm soát" in section
    assert "cánh cửa bí mật vừa mở" in section
    assert "Lip sync: required for the visible speaker" in section
    assert 'Speak exactly once in Vietnamese: "Tôi biết anh đã giấu cánh cửa ở đâu."' in section
    assert "No English speech" in section
    assert "no paraphrase" in section


def test_vietnamese_render_subtitle_audio_and_package_use_ready_veo_clip_without_tts(db, tmp_path, monkeypatch):
    project, shot = _add_vietnamese_project_shot(db)
    clip, clip_path = _add_ready_clip(db, project.id, shot.id, has_audio=True, duration=3.4)
    db.add(
        DBVideoShotPrompt(
            project_id=project.id,
            shot_id=shot.id,
            version=1,
            prompt="Create a cinematic clip with Lan turning toward the suspect.",
            prompt_explanation_vi="Lan quay lại nhìn nghi phạm.",
            duration_seconds=10.0,
            aspect_ratio="9:16",
            quality_status="passed",
        )
    )
    db.commit()

    subtitle = video_subtitles.generate_subtitle(project.id, db)
    assert subtitle.cues
    assert "Tôi biết anh đã giấu cánh cửa ở đâu." in " ".join(cue.text for cue in subtitle.cues)
    assert subtitle.cues[-1].end_seconds == pytest.approx(3.4)

    monkeypatch.setattr(
        video_rendering,
        "detect_tools",
        lambda: video_rendering.FFmpegTools(ffmpeg="ffmpeg", ffprobe="ffprobe"),
    )
    monkeypatch.setattr(video_rendering, "_select_subtitle_filter", lambda _ffmpeg: "subtitles")
    readiness = video_rendering.get_render_readiness(project.id, db, models.VideoRenderSettings())
    assert readiness is not None
    assert readiness.ready is True
    assert readiness.missing_voice_shot_ids == []
    assert video_rendering.resolve_shot_duration(shot, project=project, clip=clip) == pytest.approx(3.4)

    timeline = video_rendering.build_timeline_manifest(project.id, db)
    commands: list[list[str]] = []
    monkeypatch.setattr(video_rendering, "_run_command", lambda command, timeout=300: commands.append(command))
    outputs = video_rendering._build_audio_segments(
        "ffmpeg",
        project.target_language,
        timeline,
        {shot.id: shot},
        {shot.id: clip},
        tmp_path,
    )
    assert outputs == [tmp_path / "audio-001.wav"]
    assert commands
    assert "-vn" in commands[0]
    assert str(clip_path) in commands[0]
    assert "apad,atrim=duration=3.400" in commands[0]

    package_readiness = video_packages.get_package_readiness(project.id, db)
    assert package_readiness is not None
    assert package_readiness.ready is True
    assert package_readiness.speech_source == "veo_native"

    package = video_packages.create_package(project.id, db)
    assert package is not None
    download = video_packages.get_package_download(project.id, db)
    assert download is not None
    with zipfile.ZipFile(download[1]) as archive:
        names = set(archive.namelist())
        manifest_name = next(name for name in names if "Manifest -" in name)
        manifest = json.loads(archive.read(manifest_name).decode("utf-8"))
    assert manifest["speech_source"] == "veo_native"
    assert not any("03 - Giong doc" in name for name in names)


def test_vietnamese_clip_without_audio_blocks_render_subtitle_and_package(db, monkeypatch):
    project, shot = _add_vietnamese_project_shot(db, title="Missing native audio")
    clip, _ = _add_ready_clip(db, project.id, shot.id, has_audio=False, duration=3.4)
    db.add(
        DBVideoShotPrompt(
            project_id=project.id,
            shot_id=shot.id,
            version=1,
            prompt="Create the approved visual clip.",
            quality_status="passed",
        )
    )
    db.commit()

    monkeypatch.setattr(
        video_rendering,
        "detect_tools",
        lambda: video_rendering.FFmpegTools(ffmpeg="ffmpeg", ffprobe="ffprobe"),
    )
    monkeypatch.setattr(video_rendering, "_select_subtitle_filter", lambda _ffmpeg: "subtitles")
    readiness = video_rendering.get_render_readiness(project.id, db, models.VideoRenderSettings(subtitle_mode="none"))
    assert readiness is not None
    assert readiness.ready is False
    assert readiness.missing_voice_shot_ids == [shot.id]
    assert any("không có audio lời thoại" in reason for reason in readiness.missing_reasons)

    with pytest.raises(video_subtitles.VideoSubtitleError) as subtitle_error:
        video_subtitles.generate_subtitle(project.id, db)
    assert subtitle_error.value.error_code == "VIDEO_SUBTITLE_MISSING_NARRATION"
    assert "clip Veo" in str(subtitle_error.value)

    package_readiness = video_packages.get_package_readiness(project.id, db)
    assert package_readiness is not None
    assert package_readiness.ready is False
    assert package_readiness.missing_voice_shot_ids == [shot.id]
    assert any("Clip Veo thiếu audio" in reason for reason in package_readiness.missing_reasons)

    clip.has_audio = True
    db.commit()


def test_vietnamese_auto_run_skips_tts_and_manual_shot_voice_is_rejected(db):
    project, shot = _add_vietnamese_project_shot(db, title="Skip TTS")

    assert video_auto_runs._voice_action(SimpleNamespace(current_step=None), project, db) is None

    with pytest.raises(video_voice.VideoVoiceError) as voice_error:
        asyncio.run(
            video_voice.create_shot_narration(
                project.id,
                shot.id,
                models.VideoSceneNarrationRequest(),
                db,
            )
        )
    assert voice_error.value.error_code == "VIDEO_VOICE_VEO_NATIVE_SPEECH"
    assert "Veo 3" in str(voice_error.value)


def test_non_vietnamese_auto_run_still_requires_existing_voice_pipeline(db):
    project = video_projects.create_project(
        models.VideoProjectCreate(topic="English still uses project TTS", phase="phase2", target_language="en"),
        db,
    )
    db.add(
        DBVideoShot(
            project_id=project.id,
            shot_order=1,
            english_narration="The existing project voice pipeline must remain active.",
            status="ready",
            prompt_status="completed",
            voice_status="missing",
            subtitle_status="stale",
        )
    )
    db.commit()

    with pytest.raises(video_auto_runs.VideoAutoRunNeedsInputError) as error:
        video_auto_runs._voice_action(SimpleNamespace(current_step=None), project, db)
    assert error.value.error_code == "VIDEO_AUTO_RUN_VOICE_PROFILE_REQUIRED"


def test_video_shot_response_serializes_speech_cues(db):
    project, shot = _add_vietnamese_project_shot(db, title="Speech cue API")

    response = models.VideoShotResponse.model_validate(shot)

    assert response.project_id == project.id
    assert len(response.speech_cues) == 1
    assert response.speech_cues[0].speaker_name == "Lan"
    assert response.speech_cues[0].lip_sync_required is True


def test_editing_vietnamese_speech_invalidates_active_clip_subtitle_and_package(db):
    project, shot = _add_vietnamese_project_shot(db, title="Invalidate native speech")
    clip, _ = _add_ready_clip(db, project.id, shot.id, has_audio=True, duration=3.4)
    subtitle = DBVideoSubtitle(
        project_id=project.id,
        status="completed",
        cues_json=json.dumps(
            [{"start_seconds": 0.0, "end_seconds": 3.4, "text": "Tôi biết anh đã giấu cánh cửa ở đâu."}]
        ),
    )
    db.add(subtitle)
    project.package_stale = False
    db.commit()

    updated = video_phase2.update_shot(
        project.id,
        shot.id,
        models.VideoShotUpdate(
            speech_cues=[
                models.VideoShotSpeechCue(
                    speaker_name="Lan",
                    speaker_role="visible_character",
                    text="Tôi biết toàn bộ sự thật rồi.",
                    voice_description="giọng nữ trầm ấm, rõ chữ, điềm tĩnh và nhất quán",
                    emotion="bình tĩnh sau khi tìm ra sự thật",
                    context="Lan nhìn thẳng nghi phạm trong căn phòng bí mật",
                    lip_sync_required=True,
                )
            ]
        ),
        db,
    )
    assert updated is not None

    db.refresh(clip)
    db.refresh(subtitle)
    db.refresh(project)
    assert clip.status == "stale"
    assert subtitle.status == "stale"
    assert updated.subtitle_status == "stale"
    assert project.package_stale is True
