from __future__ import annotations

import io
import subprocess
import sys
import types
from pathlib import Path

import pytest
from fastapi import HTTPException, UploadFile

if "torch" not in sys.modules:
    torch_stub = types.ModuleType("torch")

    class _Tensor:
        def element_size(self):
            return 0

        def nelement(self):
            return 0

    torch_stub.Tensor = _Tensor
    torch_stub.load = lambda *args, **kwargs: None
    torch_stub.save = lambda *args, **kwargs: None
    sys.modules["torch"] = torch_stub

from backend import config, database
from backend.database import session as database_session
from backend.routes import generations as generation_routes
from backend.services import video_rendering


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


@pytest.mark.asyncio
async def test_import_audio_converts_mp4_upload_to_mp3(db, monkeypatch):
    payload = b"fake mp4 bytes"
    commands: list[list[str]] = []

    monkeypatch.setattr(
        generation_routes.video_rendering,
        "detect_tools",
        lambda: video_rendering.FFmpegTools(ffmpeg="ffmpeg-bin", ffprobe=None),
    )
    monkeypatch.setattr(
        generation_routes,
        "load_audio",
        lambda path: ([0.0] * 48_000, 24_000),
    )

    def fake_run(args, *, capture_output, text, timeout, check):
        commands.append(args)
        target_path = args[-1]
        Path(target_path).write_bytes(b"fake mp3 bytes")
        return subprocess.CompletedProcess(args, 0, stdout="", stderr="")

    monkeypatch.setattr(generation_routes.subprocess, "run", fake_run)

    upload = UploadFile(filename="source.mp4", file=io.BytesIO(payload))
    result = await generation_routes.import_audio(upload, db)

    assert result.source == "import"
    assert result.engine == "import"
    assert result.text == "source"
    assert result.duration == 2.0
    assert result.audio_path is not None
    assert result.audio_path.endswith(".mp3")

    stored_audio = config.resolve_storage_path(result.audio_path)
    assert stored_audio is not None
    assert stored_audio.exists()
    assert stored_audio.read_bytes() == b"fake mp3 bytes"
    assert not stored_audio.with_suffix(".mp4").exists()

    assert len(commands) == 1
    command = commands[0]
    assert command[0] == "ffmpeg-bin"
    assert "-vn" in command
    assert command[command.index("-map") + 1] == "0:a:0"
    assert command[-1].endswith(".mp3")


@pytest.mark.asyncio
async def test_import_audio_cleans_mp4_when_ffmpeg_missing(db, monkeypatch):
    monkeypatch.setattr(
        generation_routes.video_rendering,
        "detect_tools",
        lambda: video_rendering.FFmpegTools(ffmpeg=None, ffprobe=None),
    )

    upload = UploadFile(filename="source.mp4", file=io.BytesIO(b"fake mp4 bytes"))
    with pytest.raises(HTTPException) as exc_info:
        await generation_routes.import_audio(upload, db)

    assert exc_info.value.status_code == 400
    assert list(config.get_generations_dir().glob("*.mp4")) == []
    assert list(config.get_generations_dir().glob("*.mp3")) == []
