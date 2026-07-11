import asyncio
from datetime import datetime
from pathlib import Path

import pytest
from sqlalchemy import inspect

from backend import config, database, models
from backend.database import (
    VideoInspirationJob as DBVideoInspirationJob,
    VideoProject as DBVideoProject,
    VideoSourceBlock as DBVideoSourceBlock,
    session as database_session,
)
from backend.services import video_inspiration, video_rendering


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


def test_video_inspiration_tables_are_created(db):
    inspector = inspect(database_session.engine)
    tables = set(inspector.get_table_names())

    assert "video_inspiration_jobs" in tables
    assert "video_inspiration_frames" in tables

    job_columns = {column["name"] for column in inspector.get_columns("video_inspiration_jobs")}
    assert {
        "source_type",
        "source_url",
        "source_path",
        "audio_path",
            "source_duration_seconds",
            "target_language",
            "user_direction",
            "transcript_text",
        "visual_summary",
        "analysis_json",
        "rewritten_script",
        "created_video_project_id",
        "latest_auto_run_id",
    }.issubset(job_columns)

    frame_columns = {column["name"] for column in inspector.get_columns("video_inspiration_frames")}
    assert {"job_id", "frame_path", "timestamp_seconds", "description_vi"}.issubset(
        frame_columns,
    )


def test_upload_rejects_non_mp4_without_orphan_artifacts(db, tmp_path):
    with pytest.raises(video_inspiration.VideoInspirationError) as exc:
        video_inspiration.create_upload_job(
            data=b"not a video",
            filename="notes.txt",
            content_type="text/plain",
            target_language="vi",
            db=db,
        )

    assert exc.value.error_code == "VIDEO_INSPIRATION_MP4_REQUIRED"
    assert db.query(DBVideoInspirationJob).count() == 0
    assert not (tmp_path / "video_inspiration").exists()


def test_upload_accepts_mp4_and_stores_source_duration(db, monkeypatch):
    payload = b"fake mp4 bytes"

    def fake_validate(path, *, size_bytes):
        assert path.exists()
        assert size_bytes == len(payload)
        return {"duration_seconds": 12.5, "has_audio": True}

    monkeypatch.setattr(video_inspiration, "_validate_video_file", fake_validate)

    job = video_inspiration.create_upload_job(
        data=payload,
        filename="source.mp4",
        content_type="video/mp4",
        target_language="en",
        user_direction="Làm thành video người que 3D về nhân quả.",
        db=db,
    )

    assert job.source_type == "upload"
    assert job.target_language == "en"
    assert job.user_direction == "Làm thành video người que 3D về nhân quả."
    assert job.source_duration_seconds == 12.5
    assert job.source_path is not None
    assert config.resolve_storage_path(job.source_path).exists()


def test_social_link_without_downloader_returns_friendly_error(db, monkeypatch):
    monkeypatch.setattr(video_inspiration.shutil, "which", lambda name: None)
    monkeypatch.setattr(video_inspiration.importlib.util, "find_spec", lambda name: None)

    with pytest.raises(video_inspiration.VideoInspirationError) as exc:
        video_inspiration.create_url_job(
            url="https://www.youtube.com/watch?v=test-video",
            target_language="vi",
            db=db,
        )

    assert exc.value.error_code == "VIDEO_INSPIRATION_DOWNLOADER_MISSING"
    assert db.query(DBVideoInspirationJob).count() == 0


def test_downloader_uses_backend_python_module_when_cli_missing(monkeypatch):
    monkeypatch.setattr(video_inspiration.shutil, "which", lambda name: None)
    monkeypatch.setattr(
        video_inspiration.importlib.util,
        "find_spec",
        lambda name: object() if name == "yt_dlp" else None,
    )

    assert video_inspiration._yt_dlp_command() == [
        video_inspiration.sys.executable,
        "-m",
        "yt_dlp",
    ]

def test_detect_tools_uses_imageio_ffmpeg_candidate(tmp_path, monkeypatch):
    ffmpeg_bin = tmp_path / "ffmpeg.exe"
    ffmpeg_bin.write_text("", encoding="utf-8")
    monkeypatch.setattr(video_rendering.shutil, "which", lambda binary: None)
    monkeypatch.setattr(video_rendering, "_imageio_ffmpeg_candidate", lambda: str(ffmpeg_bin))
    monkeypatch.setattr(video_rendering, "_select_subtitle_filter", lambda ffmpeg: None)

    tools = video_rendering.detect_tools()

    assert tools.ffmpeg == str(ffmpeg_bin)
    assert tools.ffprobe is None

def test_downloader_passes_detected_ffmpeg_location(tmp_path, monkeypatch):
    ffmpeg_bin = tmp_path / "bin" / "ffmpeg.exe"
    ffmpeg_bin.parent.mkdir()
    ffmpeg_bin.write_text("", encoding="utf-8")
    monkeypatch.setattr(
        video_inspiration,
        "_tools",
        lambda: video_rendering.FFmpegTools(ffmpeg=str(ffmpeg_bin), ffprobe=None),
    )

    attempts = video_inspiration._yt_dlp_download_attempts(
        ["yt-dlp"],
        tmp_path / "download.%(ext)s",
        "https://www.youtube.com/watch?v=public-test",
    )

    assert video_inspiration._yt_dlp_ffmpeg_args() == ["--ffmpeg-location", str(ffmpeg_bin.parent)]
    assert attempts[0][attempts[0].index("--ffmpeg-location") + 1] == str(ffmpeg_bin.parent)

def test_probe_video_falls_back_to_ffmpeg_without_ffprobe(tmp_path, monkeypatch):
    clip_path = tmp_path / "clip.mp4"
    clip_path.write_bytes(b"fake video")
    monkeypatch.setattr(
        video_inspiration,
        "_tools",
        lambda: video_rendering.FFmpegTools(ffmpeg="ffmpeg-bin", ffprobe=None),
    )

    def fake_run_command(command, *, timeout_seconds=video_inspiration.FFMPEG_TIMEOUT_SECONDS):
        assert command == ["ffmpeg-bin", "-hide_banner", "-i", str(clip_path)]
        assert timeout_seconds == 60
        return video_inspiration.subprocess.CompletedProcess(
            command,
            1,
            stdout="",
            stderr=(
                "Input #0, mov,mp4,m4a,3gp,3g2,mj2, from 'clip.mp4':\n"
                "  Duration: 00:00:47.04, start: 0.000000, bitrate: 2000 kb/s\n"
                "  Stream #0:0: Video: h264 (High), yuv420p(progressive), 1080x1920, 30 fps\n"
                "  Stream #0:1: Audio: aac, 44100 Hz, stereo\n"
            ),
        )

    monkeypatch.setattr(video_inspiration, "_run_command", fake_run_command)

    metadata = video_inspiration._probe_video(clip_path)

    assert metadata["duration_seconds"] == pytest.approx(47.04)
    assert metadata["width"] == 1080
    assert metadata["height"] == 1920
    assert metadata["codec"] == "h264"
    assert metadata["has_audio"] is True

def test_social_link_retries_with_fallback_format(db, monkeypatch):
    monkeypatch.setattr(video_inspiration, "_yt_dlp_command", lambda: ["yt-dlp"])
    monkeypatch.setattr(video_inspiration, "_yt_dlp_ffmpeg_args", lambda: [])
    calls = []

    def fake_run_command(command, *, timeout_seconds=video_inspiration.FFMPEG_TIMEOUT_SECONDS):
        calls.append(command)
        if len(calls) == 1:
            return video_inspiration.subprocess.CompletedProcess(
                command,
                1,
                stdout="",
                stderr="Requested format is not available",
            )
        output_template = Path(command[command.index("-o") + 1])
        output_path = output_template.parent / "download.mp4"
        output_path.write_bytes(b"fake downloaded mp4")
        return video_inspiration.subprocess.CompletedProcess(command, 0, stdout="", stderr="")

    def fake_validate(path, *, size_bytes):
        assert path.name == "download.mp4"
        assert size_bytes > 0
        return {"duration_seconds": 10.0, "has_audio": True}

    monkeypatch.setattr(video_inspiration, "_run_command", fake_run_command)
    monkeypatch.setattr(video_inspiration, "_validate_video_file", fake_validate)

    job = video_inspiration.create_url_job(
        url="https://www.youtube.com/watch?v=public-test",
        target_language="vi",
        db=db,
    )

    assert len(calls) == 2
    assert calls[0][calls[0].index("--extractor-args") + 1] == "youtube:player_client=android,ios,web,tv"
    assert calls[1][calls[1].index("-f") + 1] == "best[height<=720]/best"
    assert "--merge-output-format" in calls[1]
    assert job.source_type == "url"
    assert job.source_path.endswith("download.mp4")

def test_prepare_downloaded_source_merges_split_video_and_audio(tmp_path, monkeypatch):
    video_path = tmp_path / "download.fdash-123v.mp4"
    audio_path = tmp_path / "download.fdash-456a.m4a"
    video_path.write_bytes(b"fake video without audio")
    audio_path.write_bytes(b"fake audio")
    merged_path = tmp_path / "download.merged.mp4"

    def fake_validate(path, *, size_bytes):
        if path == video_path:
            assert size_bytes == video_path.stat().st_size
            return {"duration_seconds": 28.75, "has_audio": False}
        if path == merged_path:
            assert size_bytes == merged_path.stat().st_size
            return {"duration_seconds": 28.75, "has_audio": True}
        raise AssertionError(f"unexpected validate path: {path}")

    def fake_mux(video, audio):
        assert video == video_path
        assert audio == audio_path
        merged_path.write_bytes(b"merged mp4")
        return merged_path

    monkeypatch.setattr(video_inspiration, "_validate_video_file", fake_validate)
    monkeypatch.setattr(video_inspiration, "_mux_downloaded_audio_video", fake_mux)

    source_path, metadata = video_inspiration._prepare_downloaded_source(tmp_path)

    assert source_path == merged_path
    assert metadata["has_audio"] is True

def test_social_link_requires_login_error_is_specific(db, monkeypatch):
    monkeypatch.setattr(video_inspiration, "_yt_dlp_command", lambda: ["yt-dlp"])
    monkeypatch.setattr(video_inspiration, "_yt_dlp_ffmpeg_args", lambda: [])

    def fake_run_command(command, *, timeout_seconds=video_inspiration.FFMPEG_TIMEOUT_SECONDS):
        return video_inspiration.subprocess.CompletedProcess(
            command,
            1,
            stdout="",
            stderr="ERROR: Sign in to confirm you are not a bot",
        )

    monkeypatch.setattr(video_inspiration, "_run_command", fake_run_command)

    with pytest.raises(video_inspiration.VideoInspirationError) as exc:
        video_inspiration.create_url_job(
            url="https://www.youtube.com/watch?v=needs-login",
            target_language="vi",
            db=db,
        )

    assert exc.value.error_code == "VIDEO_INSPIRATION_LINK_REQUIRES_LOGIN"
    assert "đăng nhập" in str(exc.value)

def test_social_link_uses_browser_cookies_only_when_requested(db, monkeypatch):
    monkeypatch.setattr(video_inspiration, "_yt_dlp_command", lambda: ["yt-dlp"])
    monkeypatch.setattr(video_inspiration, "_yt_dlp_ffmpeg_args", lambda: [])
    monkeypatch.setattr(video_inspiration, "_browser_cookie_candidates", lambda: ["edge"])
    calls = []

    def fake_run_command(command, *, timeout_seconds=video_inspiration.FFMPEG_TIMEOUT_SECONDS):
        calls.append(command)
        if "--cookies-from-browser" not in command:
            return video_inspiration.subprocess.CompletedProcess(
                command,
                1,
                stdout="",
                stderr="ERROR: Sign in to confirm you are not a bot",
            )
        output_template = Path(command[command.index("-o") + 1])
        output_path = output_template.parent / "download.mp4"
        output_path.write_bytes(b"fake downloaded mp4")
        return video_inspiration.subprocess.CompletedProcess(command, 0, stdout="", stderr="")

    def fake_validate(path, *, size_bytes):
        assert path.name == "download.mp4"
        assert size_bytes > 0
        return {"duration_seconds": 9.0, "has_audio": True}

    monkeypatch.setattr(video_inspiration, "_run_command", fake_run_command)
    monkeypatch.setattr(video_inspiration, "_validate_video_file", fake_validate)

    job = video_inspiration.create_url_job(
        url="https://www.youtube.com/watch?v=needs-browser-session",
        target_language="vi",
        use_browser_cookies=True,
        db=db,
    )

    cookie_calls = [command for command in calls if "--cookies-from-browser" in command]
    assert cookie_calls
    assert cookie_calls[0][cookie_calls[0].index("--cookies-from-browser") + 1] == "edge"
    assert job.source_type == "url"

def _seed_video_job(db, tmp_path, *, job_id="job-to-analyze") -> DBVideoInspirationJob:
    source_path = tmp_path / f"{job_id}.mp4"
    source_path.write_bytes(b"fake source")
    now = datetime.utcnow()
    job = DBVideoInspirationJob(
        id=job_id,
        source_type="upload",
        source_platform="upload",
        original_filename="source.mp4",
        source_path=config.to_storage_path(source_path),
        source_duration_seconds=8.0,
        status="uploaded",
        current_step="source_ready",
        progress=0.08,
        target_language="vi",
        rewrite_mode="bold_remix",
        created_at=now,
        updated_at=now,
    )
    db.add(job)
    db.commit()
    return job


def test_analyze_uses_audio_transcript_stub_and_saves_analysis(db, tmp_path, monkeypatch):
    job = _seed_video_job(db, tmp_path)
    audio_path = tmp_path / "speech.wav"

    def fake_extract_audio(row):
        audio_path.write_bytes(b"fake wav")
        row.audio_path = config.to_storage_path(audio_path)
        return audio_path

    async def fake_transcribe_audio(path, *, model_size):
        assert path == audio_path
        assert model_size == "turbo"
        return "Xin chào từ video gốc", "turbo"

    def fake_extract_frames(row, session):
        return []

    def fake_provider_ready(session):
        return True, "ready", None

    def fake_structured_ai(session, prompt, schema, *, timeout_seconds=600):
        assert "Xin chào từ video gốc" in prompt
        return {
            "main_idea_vi": "Ý chính",
            "hook_vi": "Hook",
            "structure_vi": "Cấu trúc",
            "characters_context_vi": "Bối cảnh",
            "visual_rhythm_vi": "Nhịp",
            "strengths_vi": ["Mạnh"],
            "weaknesses_vi": ["Yếu"],
            "rewrite_opportunities_vi": ["Viết mới"],
            "notes_vi": "Ghi chú",
        }

    monkeypatch.setattr(video_inspiration, "_extract_audio", fake_extract_audio)
    monkeypatch.setattr(video_inspiration, "_transcribe_audio", fake_transcribe_audio)
    monkeypatch.setattr(video_inspiration, "_extract_frames", fake_extract_frames)
    monkeypatch.setattr(video_inspiration, "_provider_ready", fake_provider_ready)
    monkeypatch.setattr(video_inspiration, "_run_structured_ai", fake_structured_ai)

    result = asyncio.run(
        video_inspiration.analyze_job(
            job.id,
            models.VideoInspirationAnalyzeRequest(allow_audio_only=True, stt_model="turbo"),
            db,
        ),
    )

    assert result is not None
    assert result.transcript_text == "Xin chào từ video gốc"
    assert result.transcript_status == "completed"
    assert result.audio_path is not None
    assert result.status == "analyzed"
    assert result.analysis_json["main_idea_vi"] == "Ý chính"


def test_transcribe_audio_chunks_long_wav_before_whisper(tmp_path, monkeypatch):
    audio_path = tmp_path / "speech.wav"
    audio_path.write_bytes(b"fake wav")
    commands = []
    transcribe_calls = []

    class FakeWhisper:
        model_size = "tiny"

        def __init__(self):
            self.loaded_model = None

        async def load_model_async(self, model_size):
            self.loaded_model = model_size

        async def transcribe(self, path, language, model_size):
            transcribe_calls.append((Path(path).name, language, model_size))
            return f"chunk text {len(transcribe_calls)}"

    fake_whisper = FakeWhisper()

    def fake_run_command(command, *, timeout_seconds=video_inspiration.FFMPEG_TIMEOUT_SECONDS):
        commands.append(command)
        Path(command[-1]).write_bytes(b"fake chunk")
        return video_inspiration.subprocess.CompletedProcess(command, 0, stdout="", stderr="")

    monkeypatch.setattr(video_inspiration, "get_whisper_model", lambda: fake_whisper)
    monkeypatch.setattr(video_inspiration, "_audio_duration_seconds", lambda path: 61.0)
    monkeypatch.setattr(
        video_inspiration,
        "_tools",
        lambda: video_rendering.FFmpegTools(ffmpeg="ffmpeg-bin", ffprobe=None),
    )
    monkeypatch.setattr(video_inspiration, "_run_command", fake_run_command)

    text, model_size = asyncio.run(video_inspiration._transcribe_audio(audio_path, model_size="turbo"))

    assert fake_whisper.loaded_model == "turbo"
    assert model_size == "turbo"
    assert text == "chunk text 1\nchunk text 2\nchunk text 3"
    assert [call[0] for call in transcribe_calls] == ["chunk-001.wav", "chunk-002.wav", "chunk-003.wav"]
    assert [call[1] for call in transcribe_calls] == [None, None, None]
    assert [call[2] for call in transcribe_calls] == ["turbo", "turbo", "turbo"]
    assert len(commands) == 3
    assert [command[command.index("-ss") + 1] for command in commands] == ["0.000", "25.000", "50.000"]
    assert [command[command.index("-t") + 1] for command in commands] == ["25.000", "25.000", "11.000"]

def test_analyze_requires_vision_provider_unless_audio_only_allowed(db, tmp_path, monkeypatch):
    job = _seed_video_job(db, tmp_path, job_id="job-needs-vision")
    audio_path = tmp_path / "speech-needs-vision.wav"

    def fake_extract_audio(row):
        audio_path.write_bytes(b"fake wav")
        row.audio_path = config.to_storage_path(audio_path)
        return audio_path

    async def fake_transcribe_audio(path, *, model_size):
        return "Transcript", "turbo"

    monkeypatch.setattr(video_inspiration, "_extract_audio", fake_extract_audio)
    monkeypatch.setattr(video_inspiration, "_transcribe_audio", fake_transcribe_audio)
    monkeypatch.setattr(video_inspiration, "_extract_frames", lambda row, session: [])
    monkeypatch.setattr(
        video_inspiration,
        "_provider_ready",
        lambda session: (False, "Chưa cấu hình AI", "AI_PLANNING_PROVIDER_NOT_READY"),
    )

    with pytest.raises(video_inspiration.VideoInspirationError) as exc:
        asyncio.run(
            video_inspiration.analyze_job(
                job.id,
                models.VideoInspirationAnalyzeRequest(allow_audio_only=False),
                db,
            ),
        )

    assert exc.value.error_code == "AI_PLANNING_PROVIDER_NOT_READY"
    db.refresh(job)
    assert job.status == "failed"
    assert job.error_code == "AI_PLANNING_PROVIDER_NOT_READY"


def test_rewrite_prompt_uses_target_language_and_bold_remix(db, monkeypatch):
    now = datetime.utcnow()
    job = DBVideoInspirationJob(
        id="rewrite-job-1",
        source_type="upload",
        source_platform="upload",
        status="analyzed",
        current_step="completed",
        progress=0.88,
        target_language="vi",
        rewrite_mode="bold_remix",
        transcript_text="Original transcript",
        visual_summary="Visual summary",
        analysis_json={"main_idea_vi": "Ý chính"},
        created_at=now,
        updated_at=now,
    )
    db.add(job)
    db.commit()

    captured = {}

    def fake_structured_ai(session, prompt, schema, *, timeout_seconds=600):
        captured["prompt"] = prompt
        return {
            "title": "New title",
            "big_idea": "New idea",
            "hook": "New hook",
            "script": "New English script",
            "segments": [
                {
                    "title": "Segment 1",
                    "narration": "Narration",
                    "visual_suggestion": "Visual suggestion",
                }
            ],
            "visual_suggestions": ["Visual suggestion"],
            "originality_note": "New work, not a copy.",
        }

    monkeypatch.setattr(video_inspiration, "_provider_ready", lambda session: (True, "ready", None))
    monkeypatch.setattr(video_inspiration, "_run_structured_ai", fake_structured_ai)

    result = video_inspiration.rewrite_job(
        job.id,
        models.VideoInspirationRewriteRequest(
            target_language="en",
            user_direction="Make it a 3D stick figure story about karma.",
        ),
        db,
    )

    assert result is not None
    assert "bold_remix" in captured["prompt"]
    assert "English" in captured["prompt"]
    assert "3D stick figure story about karma" in captured["prompt"]
    assert result.target_language == "en"
    assert result.user_direction == "Make it a 3D stick figure story about karma."
    assert result.script_title == "New title"
    assert "New English script" in result.rewritten_script


def test_update_direction_is_optional_and_clears_stale_script(db, tmp_path):
    job = _seed_video_job(db, tmp_path, job_id="job-direction")
    job.analysis_json = {"main_idea_vi": "Nhan qua"}
    job.rewritten_script = "Old script"
    job.script_title = "Old title"
    job.big_idea = "Old idea"
    job.hook = "Old hook"
    db.commit()

    result = video_inspiration.update_direction(
        job.id,
        models.VideoInspirationDirectionUpdate(
            user_direction="Làm thành video người que 3D, vẫn giữ chủ đề nhân quả.",
        ),
        db,
    )

    assert result is not None
    assert result.user_direction == "Làm thành video người que 3D, vẫn giữ chủ đề nhân quả."
    assert result.rewritten_script is None
    assert result.script_title is None
    assert result.big_idea is None
    assert result.hook is None
    assert result.status == "direction_edited"


def test_handoff_creates_ai_video_project_and_full_materials_auto_run(db, monkeypatch):
    now = datetime.utcnow()
    job = DBVideoInspirationJob(
        id="inspiration-job-1",
        source_type="upload",
        source_platform="upload",
        original_filename="source.mp4",
        status="rewritten",
        current_step="completed",
        progress=1.0,
        target_language="en",
        rewrite_mode="bold_remix",
        transcript_text="Original transcript",
        visual_summary="Visual notes",
        user_direction="Use 3D stick figure visuals and keep the karma theme.",
        analysis_json={"main_idea_vi": "Y chinh"},
        rewritten_script="New script for AI Video",
        script_title="New script title",
        big_idea="A stronger new idea",
        hook="A new hook",
        created_at=now,
        updated_at=now,
    )
    db.add(job)
    db.commit()

    called = {}

    async def fake_start_auto_run(project_id, data, session):
        called["project_id"] = project_id
        called["mode"] = data.mode
        called["material_target"] = data.material_target
        return None

    monkeypatch.setattr(video_inspiration.video_auto_runs, "start_auto_run", fake_start_auto_run)

    result = asyncio.run(
        video_inspiration.create_ai_video_project(
            job.id,
            models.VideoInspirationCreateProjectRequest(
                start_full_materials=True,
                mode="full_auto",
            ),
            db,
        ),
    )

    assert result is not None
    assert result.project.target_language == "en"
    assert result.ai_video_url == f"/ai-video?projectId={result.project.id}"
    assert called == {
        "project_id": result.project.id,
        "mode": "full_auto",
        "material_target": "full_materials",
    }

    project = db.query(DBVideoProject).filter(DBVideoProject.id == result.project.id).one()
    assert project.phase == "phase2"
    assert project.title == "New script title"
    assert "3D stick figure visuals" in (project.visual_style or "")

    blocks = (
        db.query(DBVideoSourceBlock)
        .filter(DBVideoSourceBlock.project_id == result.project.id)
        .all()
    )
    block_types = {row.block_type for row in blocks}
    assert {"script", "user_direction", "analysis", "visual_notes", "transcript"}.issubset(block_types)
    user_direction_block = next(row for row in blocks if row.block_type == "user_direction")
    assert "karma theme" in user_direction_block.content

    db.refresh(job)
    assert job.created_video_project_id == result.project.id
    assert job.status == "ai_video_ready"


def test_handoff_default_does_not_start_auto_run(db, monkeypatch):
    now = datetime.utcnow()
    job = DBVideoInspirationJob(
        id="inspiration-job-manual",
        source_type="upload",
        source_platform="upload",
        original_filename="source.mp4",
        status="rewritten",
        current_step="completed",
        progress=1.0,
        target_language="en",
        rewrite_mode="bold_remix",
        transcript_text="Original transcript",
        visual_summary="Visual notes",
        user_direction="Use 3D stick figure visuals and keep the karma theme.",
        analysis_json={"main_idea_vi": "Y chinh"},
        rewritten_script="New script for AI Video",
        script_title="New script title",
        big_idea="A stronger new idea",
        hook="A new hook",
        created_at=now,
        updated_at=now,
    )
    db.add(job)
    db.commit()

    async def fail_start_auto_run(project_id, data, session):
        raise AssertionError("auto-run must not start unless explicitly requested")

    monkeypatch.setattr(video_inspiration.video_auto_runs, "start_auto_run", fail_start_auto_run)

    result = asyncio.run(
        video_inspiration.create_ai_video_project(
            job.id,
            models.VideoInspirationCreateProjectRequest(),
            db,
        ),
    )

    assert result is not None
    assert result.auto_run is None
    assert result.project.target_language == "en"

    db.refresh(job)
    assert job.created_video_project_id == result.project.id
    assert job.latest_auto_run_id is None
