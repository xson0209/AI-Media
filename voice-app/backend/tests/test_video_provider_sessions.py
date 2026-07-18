from __future__ import annotations

import subprocess
from pathlib import Path

from backend.services import video_provider_sessions


def test_existing_chrome_runtime_detects_windows_debug_port(monkeypatch, tmp_path):
    profile_dir = tmp_path / "veo-chrome"
    command_line = (
        f'"C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe" '
        f'"--user-data-dir={profile_dir}" --remote-debugging-port=64204'
    )

    def fake_run(*_args, **_kwargs):
        return subprocess.CompletedProcess(args=[], returncode=0, stdout=command_line, stderr="")

    fetched = []

    monkeypatch.setattr(video_provider_sessions.platform, "system", lambda: "Windows")
    monkeypatch.setattr(video_provider_sessions.subprocess, "run", fake_run)
    monkeypatch.setattr(video_provider_sessions.chrome_cdp, "fetch_json", lambda url, timeout=1.0: fetched.append((url, timeout)) or {})

    runtime = video_provider_sessions._existing_chrome_runtime("veo", Path(profile_dir))

    assert runtime is not None
    assert runtime.port == 64204
    assert runtime.process is None
    assert runtime.profile_dir == profile_dir
    assert fetched == [("http://127.0.0.1:64204/json/version", 1.0)]
