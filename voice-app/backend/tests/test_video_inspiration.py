import asyncio
import importlib.machinery
import sys
import types
from datetime import datetime, timedelta
from pathlib import Path

import pytest
from sqlalchemy import inspect

if "torch" not in sys.modules:
    torch_stub = types.ModuleType("torch")
    torch_stub.__spec__ = importlib.machinery.ModuleSpec("torch", loader=None)

    class _Tensor:
        def element_size(self):
            return 0

        def nelement(self):
            return 0

    torch_stub.Tensor = _Tensor
    torch_stub.nn = types.SimpleNamespace(Module=object)
    torch_stub.load = lambda *args, **kwargs: None
    torch_stub.save = lambda *args, **kwargs: None
    sys.modules["torch"] = torch_stub

if "backend.services.transcribe" not in sys.modules:
    transcribe_stub = types.ModuleType("backend.services.transcribe")
    transcribe_stub.__spec__ = importlib.machinery.ModuleSpec("backend.services.transcribe", loader=None)
    transcribe_stub.get_whisper_model = lambda: None
    sys.modules["backend.services.transcribe"] = transcribe_stub

from backend import config, database, models
from backend.database import (
    VideoInspirationAudioEvent as DBVideoInspirationAudioEvent,
    VideoInspirationHandoff as DBVideoInspirationHandoff,
    VideoInspirationJob as DBVideoInspirationJob,
    VideoInspirationShot as DBVideoInspirationShot,
    VideoInspirationTranscriptSegment as DBVideoInspirationTranscriptSegment,
    VideoProject as DBVideoProject,
    VideoSourceBlock as DBVideoSourceBlock,
    session as database_session,
)
from backend.services import video_inspiration, video_rendering
from backend.services import video_language


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

def test_video_inspiration_output_schemas_are_strict_json_schema_objects():
    schemas = [
        video_inspiration.VISUAL_SCHEMA,
        video_inspiration.ANALYSIS_SCHEMA,
        video_inspiration.RETENTION_PLAN_SCHEMA,
        video_inspiration.SOUND_CUE_SCHEMA,
        video_inspiration.SOUND_DESIGN_PLAN_SCHEMA,
        video_inspiration.REWRITE_SEGMENT_SCHEMA,
        video_inspiration.AI_VIDEO_SOURCE_BLOCKS_SCHEMA,
        video_inspiration.REWRITE_PAYLOAD_SCHEMA,
        video_inspiration.CREATIVE_BRIEF_SCHEMA,
        video_inspiration.REWRITE_CANDIDATES_SCHEMA,
        video_inspiration.REWRITE_REVIEW_SCHEMA,
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
                assert isinstance(node.get("items"), dict), f"Array schema is missing item schema: {node}"


def test_video_inspiration_tables_are_created(db):
    inspector = inspect(database_session.engine)
    tables = set(inspector.get_table_names())

    assert "video_inspiration_jobs" in tables
    assert "video_inspiration_frames" in tables
    assert "video_inspiration_shots" in tables
    assert "video_inspiration_transcript_segments" in tables
    assert "video_inspiration_audio_events" in tables
    assert "video_inspiration_text_events" in tables
    assert "video_inspiration_retention_beats" in tables

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
        "analysis_schema_version",
        "analysis_mode",
        "analysis_package_json",
        "coverage_metrics_json",
        "limitations_json",
        "retention_source",
        "analysis_completeness",
        "rewritten_script",
        "created_video_project_id",
        "latest_auto_run_id",
    }.issubset(job_columns)

    frame_columns = {column["name"] for column in inspector.get_columns("video_inspiration_frames")}
    assert {"job_id", "shot_id", "shot_order", "frame_role", "frame_path", "timestamp_seconds", "description_vi"}.issubset(
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


def test_video_inspiration_accepts_extended_content_language():
    assert video_inspiration._validate_target_language("ja") == "ja"
    assert video_language.normalize_video_language("ja", default="") == "ja"
    assert video_language.normalize_video_language("khong-hop-le", default="") == ""

    prompt = video_inspiration._rewrite_prompt(
        types.SimpleNamespace(
            target_language="ja",
            transcript_text="Một transcript gốc.",
            analysis_json={"main_idea_vi": "Ý chính"},
            visual_summary="Một video mẫu.",
            user_direction=None,
        )
    )

    assert "Ngôn ngữ kịch bản mới: tiếng Nhật / Japanese" in prompt
    assert "Ngôn ngữ kịch bản mới: English" not in prompt


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

def test_extract_frames_creates_shot_timeline_and_keyframes(db, tmp_path, monkeypatch):
    job = _seed_video_job(db, tmp_path, job_id="shot-detection-job")
    monkeypatch.setattr(
        video_inspiration,
        "_tools",
        lambda: video_rendering.FFmpegTools(ffmpeg="ffmpeg-bin", ffprobe=None),
    )
    monkeypatch.setattr(
        video_inspiration,
        "_probe_video",
        lambda path: {"duration_seconds": 8.0, "width": 1280, "height": 720, "has_audio": True},
    )

    def fake_run_command(command, *, timeout_seconds=video_inspiration.FFMPEG_TIMEOUT_SECONDS):
        if "-vf" in command:
            return video_inspiration.subprocess.CompletedProcess(
                command,
                0,
                stdout="",
                stderr="showinfo pts_time:2.000\nshowinfo pts_time:5.000\n",
            )
        output_path = Path(command[-1])
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_bytes(b"jpeg")
        return video_inspiration.subprocess.CompletedProcess(command, 0, stdout="", stderr="")

    monkeypatch.setattr(video_inspiration, "_run_command", fake_run_command)

    frames = video_inspiration._extract_frames(job, db)
    shots = (
        db.query(DBVideoInspirationShot)
        .filter(DBVideoInspirationShot.job_id == job.id)
        .order_by(DBVideoInspirationShot.shot_order.asc())
        .all()
    )

    assert len(shots) == 3
    assert [(shot.start_seconds, shot.end_seconds) for shot in shots] == [(0.0, 2.0), (2.0, 5.0), (5.0, 8.0)]
    assert len(frames) == 3
    assert {frame.shot_id for frame in frames} == {shot.id for shot in shots}
    assert all(shot.keyframe_ids_json for shot in shots)

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


def test_active_video_inspiration_job_response_marks_stale(db, tmp_path, monkeypatch):
    job = _seed_video_job(db, tmp_path, job_id="stale-analyze")
    now = datetime(2026, 7, 13, 10, 0, 0)
    monkeypatch.setattr(video_inspiration, "_now", lambda: now)

    job.status = "analyzing"
    job.current_step = "visual_analysis"
    job.progress = 0.62
    job.updated_at = now - timedelta(seconds=video_inspiration.ACTIVE_JOB_STALE_SECONDS + 1)
    db.commit()

    result = video_inspiration.get_job(job.id, db)

    assert result is not None
    assert result.status == "analyzing"
    assert result.is_stale is True
    assert result.stale_reason


def test_fresh_active_video_inspiration_job_response_is_not_stale(db, tmp_path, monkeypatch):
    job = _seed_video_job(db, tmp_path, job_id="fresh-analyze")
    now = datetime(2026, 7, 13, 10, 0, 0)
    monkeypatch.setattr(video_inspiration, "_now", lambda: now)

    job.status = "analyzing"
    job.current_step = "visual_analysis"
    job.progress = 0.62
    job.updated_at = now
    db.commit()

    result = video_inspiration.get_job(job.id, db)

    assert result is not None
    assert result.is_stale is False
    assert result.stale_reason is None


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
    assert result.analysis_schema_version == video_inspiration.ANALYSIS_SCHEMA_VERSION
    assert result.analysis_package_json is not None
    assert result.analysis_package_json["retention_source"] == "predicted_from_content"
    assert result.coverage_metrics_json["transcript_segment_count"] == 1
    assert result.transcript_segments[0].timestamp_precision == "file"
    assert result.audio_events[0].event_type == "speech"
    assert result.content_retention_beats
    assert result.created_video_project_id is None


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
    segments = getattr(video_inspiration._transcribe_audio, "last_segments")
    assert [segment["timestamp_precision"] for segment in segments] == ["chunk", "chunk", "chunk"]
    assert [(segment["start_seconds"], segment["end_seconds"]) for segment in segments] == [
        (0.0, 25.0),
        (25.0, 50.0),
        (50.0, 61.0),
    ]
    assert [call[0] for call in transcribe_calls] == ["chunk-001.wav", "chunk-002.wav", "chunk-003.wav"]
    assert [call[1] for call in transcribe_calls] == [None, None, None]
    assert [call[2] for call in transcribe_calls] == ["turbo", "turbo", "turbo"]
    assert len(commands) == 3
    assert [command[command.index("-ss") + 1] for command in commands] == ["0.000", "25.000", "50.000"]
    assert [command[command.index("-t") + 1] for command in commands] == ["25.000", "25.000", "11.000"]

def test_transcribe_audio_filters_music_only_label(tmp_path, monkeypatch):
    audio_path = tmp_path / "speech.wav"
    audio_path.write_bytes(b"fake wav")

    class FakeWhisper:
        model_size = "tiny"

        async def load_model_async(self, model_size):
            pass

        async def transcribe(self, path, language, model_size):
            return "Music"

    monkeypatch.setattr(video_inspiration, "get_whisper_model", lambda: FakeWhisper())
    monkeypatch.setattr(video_inspiration, "_audio_duration_seconds", lambda path: 10.0)

    text, model_size = asyncio.run(video_inspiration._transcribe_audio(audio_path, model_size="turbo"))

    assert text == ""
    assert model_size == "turbo"

def test_transcribe_audio_skips_music_chunks_but_keeps_speech(tmp_path, monkeypatch):
    audio_path = tmp_path / "speech.wav"
    audio_path.write_bytes(b"fake wav")
    outputs = iter(["[Music]", "Actual spoken line", "music music"])

    class FakeWhisper:
        model_size = "tiny"

        async def load_model_async(self, model_size):
            pass

        async def transcribe(self, path, language, model_size):
            return next(outputs)

    def fake_run_command(command, *, timeout_seconds=video_inspiration.FFMPEG_TIMEOUT_SECONDS):
        Path(command[-1]).write_bytes(b"fake chunk")
        return video_inspiration.subprocess.CompletedProcess(command, 0, stdout="", stderr="")

    monkeypatch.setattr(video_inspiration, "get_whisper_model", lambda: FakeWhisper())
    monkeypatch.setattr(video_inspiration, "_audio_duration_seconds", lambda path: 61.0)
    monkeypatch.setattr(
        video_inspiration,
        "_tools",
        lambda: video_rendering.FFmpegTools(ffmpeg="ffmpeg-bin", ffprobe=None),
    )
    monkeypatch.setattr(video_inspiration, "_run_command", fake_run_command)

    text, _model_size = asyncio.run(video_inspiration._transcribe_audio(audio_path, model_size="turbo"))

    assert text == "Actual spoken line"

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


def _optimized_rewrite_payload(*, title="New title", hook_3_5s=None):
    hook_text = hook_3_5s or (
        "Open on a tiny stick figure facing a huge cracked wall, with one hammer tap and a silence drop."
    )
    return {
        "title": title,
        "big_idea": "New idea",
        "hook": "A strong hook",
        "hook_3_5s": hook_text,
        "viewer_question": "Can one small action break the wall?",
        "curiosity_gap": "The viewer waits to see whether the crack becomes a path.",
        "script": "New English script",
        "segments": [
            {
                "title": "First strike",
                "narration": "One small hit is still a beginning.",
                "visual_suggestion": "Minimal stick figure lifts a hammer beside a dark wall.",
                "retention_role": "cold open",
                "audio_cue": "single hammer tap, brief silence drop",
            }
        ],
        "visual_suggestions": ["Minimal stick figure, ivory paper, black ink wall."],
        "retention_plan": {
            "viewer_question": "Can one small action break the wall?",
            "curiosity_gap": "The crack may become a path.",
            "beat_curve": ["0-5s wall/hit", "5-15s cracks grow", "15-30s stones become steps"],
            "pattern_interrupts": ["Silence drop before hammer tap"],
            "payoff": "The fallen wall becomes stairs.",
            "drop_off_risks": ["Opening too slow"],
        },
        "sound_design_plan": {
            "music_mood": "quiet tension then hopeful lift",
            "ambience": "paper room tone",
            "sfx_cues": [{"timing": "0-3s", "cue": "hammer tap", "purpose": "mark the hook"}],
            "silence_drops": ["before first tap"],
            "mixing_notes": "Voice must stay above music and SFX.",
        },
        "audio_direction": "Use sparse taps and stone crumble; do not cover narration.",
        "ai_video_source_blocks": {
            "idea": "New idea\nHook 3-5s: tiny figure, huge wall, hammer tap.",
            "rough_script": "New English script",
            "character_notes": "Stick figure, cracked wall, paper background.",
            "style_notes": "Retention: crack becomes a path.\nSound design: hammer tap, silence, crumble.",
            "must_have": "Hook 3-5s, hammer tap, wall becomes stairs.",
            "avoid": "Do not copy original; avoid loud SFX over narration.",
        },
        "originality_note": "New work, not a copy.",
    }

def test_variant_pipeline_batches_scores_caches_and_selects_final(db, tmp_path, monkeypatch):
    job = _seed_video_job(db, tmp_path, job_id="variant-pipeline")
    job.status = "analyzed"
    job.current_step = "completed"
    job.analysis_mode = "high_quality"
    job.analysis_json = {"main_idea_vi": "Ý chính"}
    job.analysis_package_json = {"schema_version": "video_analysis_package.v1", "revision": 2}
    db.commit()

    calls = []

    def fake_structured_ai(session, prompt, schema, *, timeout_seconds=600):
        calls.append(schema)
        if schema is video_inspiration.CREATIVE_BRIEF_SCHEMA:
            return {
                "strategy_summary": "Tạo hai hướng khác nhau.",
                "core_insight": "Một hành động nhỏ tạo thay đổi lớn.",
                "audience_promise": "Có payoff rõ ràng.",
                "visual_direction": "Tối giản.",
                "constraints": ["Không copy nguồn."],
                "candidate_angles": ["Hook", "Cảm xúc"],
            }
        if schema is video_inspiration.REWRITE_CANDIDATES_SCHEMA:
            return {"candidates": [_optimized_rewrite_payload(title="A"), _optimized_rewrite_payload(title="B")]}
        if schema is video_inspiration.VARIANT_SCORE_SCHEMA:
            reviews = []
            for index in range(2):
                reviews.append({
                    "candidate_index": index,
                    "score": 8.5 - index,
                    "hook_score": 9,
                    "clarity_score": 8,
                    "originality_score": 8,
                    "retention_score": 9,
                    "production_feasibility_score": 8,
                    "sound_design_score": 8,
                    "alignment_score": 9,
                    "strengths": ["Hook tốt"],
                    "weaknesses": ["Cần gọn hơn"],
                    "best_parts": ["Mở đầu"],
                    "recommendation": "Giữ hook, rút gọn phần giữa.",
                })
            return {"reviews": reviews, "synthesis_direction": "Kết hợp hai bản.", "rubric_version": video_inspiration.VARIANT_RUBRIC_VERSION}
        if schema is video_inspiration.VARIANT_SYNTHESIS_SCHEMA:
            return {"final_versions": [{"variant_id": "final-1", "strategy": "balanced", "source_basis": ["candidate-1", "candidate-2"], "payload": _optimized_rewrite_payload(title="Final")} ]}
        raise AssertionError("unexpected schema")

    monkeypatch.setattr(video_inspiration, "_run_structured_ai", fake_structured_ai)
    monkeypatch.setattr(video_inspiration, "_variant_model_key", lambda session: "codex:test-model")

    generated = video_inspiration.generate_variant_candidates(job.id, models.VideoInspirationVariantGenerateRequest(candidate_count=2), db)
    assert generated is not None
    candidate_ids = [item["variant_id"] for item in generated.analysis_json["variant_pipeline"]["candidates"]]
    assert len(candidate_ids) == 2
    assert generated.analysis_json["variant_pipeline"]["candidate_generation"]["metrics"]["prompt_chars"] > 0

    # An identical request is served from the stage cache.
    video_inspiration.generate_variant_candidates(job.id, models.VideoInspirationVariantGenerateRequest(candidate_count=2), db)
    assert calls.count(video_inspiration.REWRITE_CANDIDATES_SCHEMA) == 1

    scored = video_inspiration.score_variant_candidates(job.id, models.VideoInspirationVariantScoreRequest(variant_ids=candidate_ids), db)
    assert scored is not None
    assert len(scored.analysis_json["variant_pipeline"]["scoring"]["reviews"]) == 2
    video_inspiration.score_variant_candidates(job.id, models.VideoInspirationVariantScoreRequest(variant_ids=candidate_ids), db)
    assert calls.count(video_inspiration.VARIANT_SCORE_SCHEMA) == 1

    synthesized = video_inspiration.synthesize_variant_versions(job.id, models.VideoInspirationVariantSynthesisRequest(variant_ids=candidate_ids), db)
    assert synthesized is not None
    final = synthesized.analysis_json["variant_pipeline"]["synthesis"]["versions"][0]
    assert final["source_basis"] == ["candidate-1", "candidate-2"]
    assert final["revision"] == 1

    selected = video_inspiration.select_variant_version(job.id, models.VideoInspirationVariantSelectRequest(variant_id="final-1"), db)
    assert selected is not None
    assert selected.script_title == "Final"
    assert "New English script" in selected.rewritten_script

def test_variant_pipeline_kill_switch(db, tmp_path, monkeypatch):
    job = _seed_video_job(db, tmp_path, job_id="variant-disabled")
    job.status = "analyzed"
    job.analysis_json = {"main_idea_vi": "Ý chính"}
    db.commit()
    monkeypatch.setenv(video_inspiration.VARIANT_PIPELINE_FEATURE_ENV, "false")

    with pytest.raises(video_inspiration.VideoInspirationError) as exc:
        video_inspiration.generate_variant_candidates(job.id, models.VideoInspirationVariantGenerateRequest(), db)

    assert exc.value.error_code == "VIDEO_INSPIRATION_VARIANTS_DISABLED"

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

    captured = []

    def fake_structured_ai(session, prompt, schema, *, timeout_seconds=600):
        captured.append((prompt, schema))
        if schema is video_inspiration.CREATIVE_BRIEF_SCHEMA:
            return {
                "strategy_summary": "Make the visual metaphor more active.",
                "core_insight": "Small actions compound.",
                "audience_promise": "A simple action can become a path.",
                "visual_direction": "Minimal stick figure and cracked wall.",
                "constraints": ["Do not copy the original."],
                "candidate_angles": ["hook-led wall strike", "emotional perseverance"],
            }
        if schema is video_inspiration.REWRITE_CANDIDATES_SCHEMA:
            return {"candidates": [_optimized_rewrite_payload(title="Candidate 1"), _optimized_rewrite_payload(title="Candidate 2")]}
        if schema is video_inspiration.REWRITE_REVIEW_SCHEMA:
            return {
                "reviews": [
                    {
                        "candidate_index": 1,
                        "score": 8.5,
                        "strengths": ["Strong hook"],
                        "weaknesses": ["Needs clearer payoff"],
                        "best_parts": ["Hammer tap hook"],
                    },
                    {
                        "candidate_index": 2,
                        "score": 8.0,
                        "strengths": ["Good emotion"],
                        "weaknesses": ["Slower open"],
                        "best_parts": ["Stairs payoff"],
                    },
                ],
                "synthesis_direction": "Use the first hook and second payoff.",
            }
        if schema is video_inspiration.REWRITE_SCHEMA:
            return _optimized_rewrite_payload()
        raise AssertionError("unexpected schema")

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
    prompts = "\n\n".join(prompt for prompt, _schema in captured)
    assert len(captured) == 4
    assert "bold_remix" in prompts
    assert "English" in prompts
    assert "3D stick figure story about karma" in prompts
    assert result.target_language == "en"
    assert result.user_direction == "Make it a 3D stick figure story about karma."
    assert result.script_title == "New title"
    assert "tiny stick figure facing a huge cracked wall" in result.hook
    assert "New English script" in result.rewritten_script
    assert "Hook 3-5 giây" in result.rewritten_script
    assert "Nhịp giữ chân" in result.rewritten_script
    assert "Âm thanh / sound design" in result.rewritten_script
    assert result.analysis_json["rewrite_creative_brief"]["core_insight"] == "Small actions compound."
    assert len(result.analysis_json["rewrite_candidates"]["candidates"]) == 2
    assert result.analysis_json["rewrite_review"]["synthesis_direction"] == "Use the first hook and second payoff."
    assert result.analysis_json["rewrite"]["retention_plan"]["payoff"] == "The fallen wall becomes stairs."
    assert result.analysis_json["rewrite"]["sound_design_plan"]["mixing_notes"] == "Voice must stay above music and SFX."
    assert "rough_script" in result.analysis_json["rewrite"]["ai_video_source_blocks"]


def test_rewrite_incomplete_final_payload_does_not_overwrite_existing_script(db, monkeypatch):
    now = datetime.utcnow()
    job = DBVideoInspirationJob(
        id="rewrite-job-incomplete",
        source_type="upload",
        source_platform="upload",
        status="rewritten",
        current_step="completed",
        progress=1.0,
        target_language="en",
        rewrite_mode="bold_remix",
        transcript_text="Original transcript",
        visual_summary="Visual summary",
        analysis_json={"main_idea_vi": "Ý chính"},
        rewritten_script="Old valid script",
        script_title="Old title",
        big_idea="Old idea",
        hook="Old hook",
        created_at=now,
        updated_at=now,
    )
    db.add(job)
    db.commit()

    def fake_structured_ai(session, prompt, schema, *, timeout_seconds=600):
        if schema is video_inspiration.CREATIVE_BRIEF_SCHEMA:
            return {
                "strategy_summary": "Brief",
                "core_insight": "Insight",
                "audience_promise": "Promise",
                "visual_direction": "Visual",
                "constraints": ["Constraint"],
                "candidate_angles": ["Angle 1", "Angle 2"],
            }
        if schema is video_inspiration.REWRITE_CANDIDATES_SCHEMA:
            return {"candidates": [_optimized_rewrite_payload(title="Candidate 1"), _optimized_rewrite_payload(title="Candidate 2")]}
        if schema is video_inspiration.REWRITE_REVIEW_SCHEMA:
            return {
                "reviews": [
                    {
                        "candidate_index": 1,
                        "score": 8,
                        "strengths": ["Strong"],
                        "weaknesses": ["Weak"],
                        "best_parts": ["Hook"],
                    }
                ],
                "synthesis_direction": "Improve final.",
            }
        payload = _optimized_rewrite_payload()
        payload.pop("hook_3_5s")
        return payload

    monkeypatch.setattr(video_inspiration, "_provider_ready", lambda session: (True, "ready", None))
    monkeypatch.setattr(video_inspiration, "_run_structured_ai", fake_structured_ai)

    with pytest.raises(video_inspiration.VideoInspirationError) as exc:
        video_inspiration.rewrite_job(job.id, models.VideoInspirationRewriteRequest(), db)

    assert exc.value.error_code == "VIDEO_INSPIRATION_REWRITE_INCOMPLETE"
    db.refresh(job)
    assert job.rewritten_script == "Old valid script"
    assert job.script_title == "Old title"
    assert job.big_idea == "Old idea"
    assert job.hook == "Old hook"

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


def test_update_transcript_keeps_raw_segment_and_adds_user_edit(db, tmp_path):
    job = _seed_video_job(db, tmp_path, job_id="job-transcript-edit")
    raw_segment = DBVideoInspirationTranscriptSegment(
        id="raw-segment-1",
        job_id=job.id,
        segment_order=1,
        start_seconds=0.0,
        end_seconds=4.0,
        text="Lời nhận diện ban đầu",
        raw_text="Lời nhận diện ban đầu",
        source="stt_raw",
        timestamp_precision="chunk",
        shot_ids_json=[],
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow(),
    )
    db.add(raw_segment)
    db.commit()

    result = video_inspiration.update_transcript(
        job.id,
        models.VideoInspirationTranscriptUpdate(transcript_text="Bản người dùng đã sửa"),
        db,
    )

    assert result is not None
    rows = (
        db.query(DBVideoInspirationTranscriptSegment)
        .filter(DBVideoInspirationTranscriptSegment.job_id == job.id)
        .all()
    )
    assert {row.source for row in rows} == {"stt_raw", "user_edited"}
    assert next(row for row in rows if row.source == "stt_raw").text == "Lời nhận diện ban đầu"
    assert next(row for row in rows if row.source == "user_edited").text == "Bản người dùng đã sửa"
    assert result.analysis_package_json is None
    assert result.analysis_completeness == "not_started"


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
        visual_summary="Visual notes " * 500,
        user_direction="Use 3D stick figure visuals and keep the karma theme.",
        analysis_json={"main_idea_vi": "Y chinh", "rewrite": _optimized_rewrite_payload()},
        analysis_package_json={
            "schema_version": "video_analysis_package.v1",
            "content_retention_beats": [
                {
                    "order": 1,
                    "role": "hook",
                    "why_continue": "A wall strike creates an open loop.",
                    "viewer_question_before": "Can the tiny figure break the wall?",
                    "new_information": "The crack grows.",
                    "micro_payoff": "The wall becomes stairs.",
                    "evidence_refs": [{"type": "shot", "id": "shot-1"}],
                }
            ],
            "transcript_segments": [{"id": "segment-1", "text": "Original transcript"}],
            "limitations": ["Predicted retention only."],
        },
        analysis_package_path="video_inspiration/inspiration-job-1/package.json",
        analysis_completeness="full",
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
    assert len(project.visual_style or "") <= 2000

    blocks = (
        db.query(DBVideoSourceBlock)
        .filter(DBVideoSourceBlock.project_id == result.project.id)
        .all()
    )
    block_types = {row.block_type for row in blocks}
    assert {"idea", "rough_script", "character_notes", "style_notes", "must_have", "avoid", "analysis", "transcript"}.issubset(block_types)
    idea_block = next(row for row in blocks if row.block_type == "idea")
    assert "A stronger new idea" in idea_block.content
    assert "A new hook" in idea_block.content
    rough_script_block = next(row for row in blocks if row.block_type == "rough_script")
    assert "New script for AI Video" in rough_script_block.content
    assert "source_transcript_is_evidence_only" in rough_script_block.content
    style_notes_block = next(row for row in blocks if row.block_type == "style_notes")
    assert "Retention" in style_notes_block.content
    assert "Sound design" in style_notes_block.content
    transcript_block = next(row for row in blocks if row.block_type == "transcript")
    assert "source_transcript_for_evidence_only" in transcript_block.content

    db.refresh(job)
    assert job.created_video_project_id == result.project.id
    assert job.status == "ai_video_ready"


def test_handoff_project_title_ignores_generic_download_filename(db):
    now = datetime.utcnow()
    job = DBVideoInspirationJob(
        id="inspiration-download-name",
        source_type="url",
        source_url="https://www.youtube.com/watch?v=example",
        source_platform="youtube",
        original_filename="download.mp4",
        status="rewritten",
        current_step="completed",
        progress=1.0,
        target_language="vi",
        rewrite_mode="bold_remix",
        transcript_text="Một câu chuyện về sống thật với chính mình.",
        visual_summary="Visual notes",
        user_direction="Tạo kịch bản video người que.",
        analysis_json={
            "main_idea_vi": "Bài học về tự chấp nhận bản thân",
            "rewrite": {"title": "download mp4"},
        },
        analysis_package_json={
            "schema_version": "video_analysis_package.v1",
            "content_retention_beats": [],
            "transcript_segments": [{"id": "segment-1", "text": "Transcript"}],
            "limitations": [],
        },
        analysis_package_path="video_inspiration/inspiration-download-name/package.json",
        analysis_completeness="partial",
        rewritten_script="Kịch bản mới cho AI Video",
        script_title="download.mp4",
        big_idea="Bài học về tự chấp nhận bản thân",
        hook="Nếu cuộn giấy trống thì bạn còn lại gì?",
        created_at=now,
        updated_at=now,
    )
    db.add(job)
    db.commit()

    result = asyncio.run(
        video_inspiration.create_ai_video_project(
            job.id,
            models.VideoInspirationCreateProjectRequest(),
            db,
        ),
    )

    assert result is not None
    assert result.project.title == "Bài học về tự chấp nhận bản thân"
    assert "download" not in result.project.title.lower()
    handoff = db.query(DBVideoInspirationHandoff).filter(DBVideoInspirationHandoff.job_id == job.id).one()
    assert handoff.payload_json["target_content"]["approved_script"]["title"] == "Bài học về tự chấp nhận bản thân"


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
        analysis_package_json={
            "schema_version": "video_analysis_package.v1",
            "content_retention_beats": [
                {
                    "order": 1,
                    "role": "hook",
                    "why_continue": "The opening creates a clear question.",
                    "viewer_question_before": "What changes next?",
                    "new_information": "The target story introduces a new choice.",
                    "micro_payoff": "The choice becomes visible.",
                }
            ],
            "transcript_segments": [{"id": "segment-1", "text": "Original transcript"}],
            "limitations": ["Predicted retention only."],
        },
        analysis_package_path="video_inspiration/inspiration-job-manual/package.json",
        analysis_completeness="full",
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
