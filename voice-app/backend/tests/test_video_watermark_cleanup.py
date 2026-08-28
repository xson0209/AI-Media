from __future__ import annotations

import builtins
import json
import os
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

from backend.services import video_watermark_cleanup
from backend.workers import video_watermark_worker


def _runtime(tmp_path: Path, *, revision: str = "revision-a") -> video_watermark_cleanup.WatermarkRuntimeStatus:
    package_root = tmp_path / "remove-watermark"
    worker_script = tmp_path / "worker.py"
    package_root.mkdir(exist_ok=True)
    worker_script.write_text("# worker", encoding="utf-8")
    return video_watermark_cleanup.WatermarkRuntimeStatus(
        ready=True,
        package_root=package_root,
        python=sys.executable,
        worker_script=worker_script,
        revision=revision,
        package_version="0.22.0",
    )


def test_worker_rejects_invisible_cleanup() -> None:
    with pytest.raises(ValueError, match="Invisible/SynthID"):
        video_watermark_worker.run_cleanup(
            {
                "operation": "video_all",
                "source_path": "unused.mp4",
                "output_path": "unused-output.mp4",
                "include_invisible": True,
            }
        )


def test_worker_serializes_visible_and_metadata_result(tmp_path, monkeypatch) -> None:
    source = tmp_path / "source.mp4"
    output = tmp_path / "output.mp4"
    source.write_bytes(b"source")
    captured: dict[str, object] = {}

    def fake_remove_video_all(source_path, output_path, **kwargs):
        captured.update(kwargs)
        Path(output_path).write_bytes(b"cleaned")
        return SimpleNamespace(
            visible_mark="veo",
            total_frames=12,
            visible_detected_frames=5,
            visible_removed_frames=5,
            detected_metadata={"generator": "Veo"},
            remaining_metadata={},
        )

    monkeypatch.setitem(
        sys.modules,
        "remove_ai_watermarks",
        SimpleNamespace(remove_video_all=fake_remove_video_all),
    )

    result = video_watermark_worker.run_cleanup(
        {
            "operation": "video_all",
            "source_path": str(source),
            "output_path": str(output),
            "mark": "veo",
            "backend": "cv2",
            "temporal_consistency": True,
            "include_invisible": False,
        }
    )

    assert source.read_bytes() == b"source"
    assert output.read_bytes() == b"cleaned"
    assert captured == {
        "mark": "veo",
        "backend": "cv2",
        "temporal_consistency": True,
        "include_invisible": False,
    }
    assert result["status"] == "removed"
    assert result["visible_mark"] == "veo"
    assert result["visible_removed_frames"] == 5
    assert result["invisible_removed"] is False


def test_worker_reports_no_supported_mark_without_claiming_clean(tmp_path, monkeypatch) -> None:
    source = tmp_path / "source.mp4"
    output = tmp_path / "output.mp4"
    source.write_bytes(b"source")

    def fake_remove_video_all(_source_path, output_path, **_kwargs):
        Path(output_path).write_bytes(b"passthrough")
        return SimpleNamespace(
            visible_mark=None,
            total_frames=4,
            visible_detected_frames=0,
            visible_removed_frames=0,
            detected_metadata={},
            remaining_metadata={},
        )

    monkeypatch.setitem(
        sys.modules,
        "remove_ai_watermarks",
        SimpleNamespace(remove_video_all=fake_remove_video_all),
    )

    result = video_watermark_worker.run_cleanup(
        {
            "operation": "video_all",
            "source_path": str(source),
            "output_path": str(output),
        }
    )

    assert result["status"] == "no_supported_mark"
    assert result["visible_mark"] is None


def test_configured_python_accepts_command_name(tmp_path, monkeypatch) -> None:
    executable = tmp_path / ("python.exe" if os.name == "nt" else "python")
    executable.write_bytes(b"")
    monkeypatch.setenv(video_watermark_cleanup.WATERMARK_PYTHON_ENV, "python")
    monkeypatch.setattr(
        video_watermark_cleanup.shutil,
        "which",
        lambda command: str(executable) if command == "python" else None,
    )

    assert video_watermark_cleanup._configured_python(tmp_path) == str(executable)


def test_worker_dependency_error_names_running_python_and_setup_command(monkeypatch) -> None:
    real_import = builtins.__import__

    def blocked_import(name, *args, **kwargs):
        if name in {"av", "cv2", "remove_ai_watermarks"}:
            raise ModuleNotFoundError("No module named 'cv2'")
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", blocked_import)

    payload = video_watermark_worker.check_runtime("cv2")

    assert payload["ready"] is False
    assert payload["error_code"] == "WATERMARK_WORKER_DEPENDENCY_MISSING"
    assert payload["python"] == sys.executable
    assert payload["setup_command"] == video_watermark_worker.SETUP_COMMAND_HINT
    # The machine can have two venvs with overlapping deps, so the message must
    # say which Python is running and exactly what to run.
    assert "cv2" in payload["message"]
    assert sys.executable in payload["message"]
    assert "setup-watermark-worker.ps1" in payload["message"]


def _stub_worker_video_dependencies(monkeypatch) -> None:
    """Satisfy the worker's shared video imports.

    The Voicebox backend venv deliberately lacks av/cv2/remove_ai_watermarks:
    those live only in the isolated worker venv. Tests that exercise logic past
    the shared dependency gate stub them so they run in either interpreter.
    """

    monkeypatch.setitem(sys.modules, "av", SimpleNamespace())
    monkeypatch.setitem(sys.modules, "cv2", SimpleNamespace())
    monkeypatch.setitem(
        sys.modules,
        "remove_ai_watermarks",
        SimpleNamespace(remove_video_all=lambda *args, **kwargs: None, __version__="0.22.0"),
    )


def test_worker_migan_dependency_error_names_running_python_and_migan_setup(monkeypatch) -> None:
    _stub_worker_video_dependencies(monkeypatch)
    real_import = builtins.__import__

    def blocked_import(name, *args, **kwargs):
        if name in {"huggingface_hub", "onnxruntime"}:
            raise ModuleNotFoundError("No module named 'huggingface_hub'")
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", blocked_import)
    monkeypatch.setattr(video_watermark_worker.shutil, "which", lambda _name: "ffmpeg")

    payload = video_watermark_worker.check_runtime("migan")

    assert payload["ready"] is False
    assert payload["error_code"] == "WATERMARK_WORKER_MIGAN_MISSING"
    assert payload["python"] == sys.executable
    assert payload["setup_command"].endswith("-Backend migan")
    assert "huggingface_hub" in payload["message"]
    assert sys.executable in payload["message"]
    assert "-Backend migan" in payload["message"]


@pytest.mark.parametrize(
    "cached_return, expected",
    [
        ("__EXISTING_FILE__", video_watermark_worker.MODEL_CACHE_CACHED),
        (None, video_watermark_worker.MODEL_CACHE_NOT_CACHED),
        (False, video_watermark_worker.MODEL_CACHE_NOT_CACHED),
    ],
)
def test_migan_model_cache_state_reads_local_cache_only(tmp_path, monkeypatch, cached_return, expected) -> None:
    if cached_return == "__EXISTING_FILE__":
        model_file = tmp_path / "migan.onnx"
        model_file.write_bytes(b"onnx")
        cached_return = str(model_file)
    calls: list[dict] = []

    def fake_try_to_load_from_cache(*, repo_id, filename):
        calls.append({"repo_id": repo_id, "filename": filename})
        return cached_return

    fake_module = SimpleNamespace(try_to_load_from_cache=fake_try_to_load_from_cache)
    monkeypatch.setitem(sys.modules, "huggingface_hub", fake_module)

    assert video_watermark_worker._migan_model_cache_state() == expected
    # Cache lookup only: never a download.
    assert calls == [
        {
            "repo_id": video_watermark_worker.MIGAN_MODEL_REPO,
            "filename": video_watermark_worker.MIGAN_MODEL_FILE,
        }
    ]


def test_migan_model_cache_state_degrades_to_unknown_on_error(monkeypatch) -> None:
    def exploding(*, repo_id, filename):
        raise RuntimeError("cache scan blew up")

    monkeypatch.setitem(sys.modules, "huggingface_hub", SimpleNamespace(try_to_load_from_cache=exploding))

    assert video_watermark_worker._migan_model_cache_state() == video_watermark_worker.MODEL_CACHE_UNKNOWN


def test_check_runtime_reports_model_cache_for_migan_only(monkeypatch) -> None:
    _stub_worker_video_dependencies(monkeypatch)
    monkeypatch.setitem(sys.modules, "huggingface_hub", SimpleNamespace())
    monkeypatch.setitem(sys.modules, "onnxruntime", SimpleNamespace())
    monkeypatch.setattr(video_watermark_worker.shutil, "which", lambda _name: "ffmpeg")
    monkeypatch.setattr(
        video_watermark_worker,
        "_migan_model_cache_state",
        lambda: pytest.fail("cv2 must not look up the MI-GAN model cache"),
    )

    cv2_payload = video_watermark_worker.check_runtime("cv2")

    assert cv2_payload["ready"] is True
    assert "model_cache" not in cv2_payload

    monkeypatch.setattr(
        video_watermark_worker,
        "_migan_model_cache_state",
        lambda: video_watermark_worker.MODEL_CACHE_NOT_CACHED,
    )

    migan_payload = video_watermark_worker.check_runtime("migan")

    # Missing model cache must not make the backend report as not ready.
    assert migan_payload["ready"] is True
    assert migan_payload["model_cache"] == "not_cached"


def test_runtime_status_carries_model_cache_from_worker_payload(tmp_path, monkeypatch) -> None:
    package_root = tmp_path / "remove-watermark"
    (package_root / "src" / "remove_ai_watermarks").mkdir(parents=True)
    worker_script = tmp_path / "worker.py"
    worker_script.write_text("# worker", encoding="utf-8")
    monkeypatch.setenv(video_watermark_cleanup.WATERMARK_ROOT_ENV, str(package_root))
    monkeypatch.setenv(video_watermark_cleanup.WATERMARK_WORKER_SCRIPT_ENV, str(worker_script))
    monkeypatch.setattr(video_watermark_cleanup, "_configured_python", lambda _root: sys.executable)

    def fake_run_worker(**_kwargs):
        completed = SimpleNamespace(returncode=0, stdout="", stderr="")
        payload = {"ok": True, "ready": True, "revision": "rev-1", "model_cache": "not_cached"}
        return completed, payload

    monkeypatch.setattr(video_watermark_cleanup, "_run_worker", fake_run_worker)

    status = video_watermark_cleanup.get_runtime_status(backend="migan", ffmpeg="ffmpeg", ffprobe="ffprobe")

    assert status.ready is True
    assert status.model_cache == video_watermark_cleanup.MODEL_CACHE_NOT_CACHED


def test_runtime_status_ignores_unknown_model_cache_value(tmp_path, monkeypatch) -> None:
    package_root = tmp_path / "remove-watermark"
    (package_root / "src" / "remove_ai_watermarks").mkdir(parents=True)
    worker_script = tmp_path / "worker.py"
    worker_script.write_text("# worker", encoding="utf-8")
    monkeypatch.setenv(video_watermark_cleanup.WATERMARK_ROOT_ENV, str(package_root))
    monkeypatch.setenv(video_watermark_cleanup.WATERMARK_WORKER_SCRIPT_ENV, str(worker_script))
    monkeypatch.setattr(video_watermark_cleanup, "_configured_python", lambda _root: sys.executable)
    monkeypatch.setattr(
        video_watermark_cleanup,
        "_run_worker",
        lambda **_kwargs: (
            SimpleNamespace(returncode=0, stdout="", stderr=""),
            {"ok": True, "ready": True, "model_cache": "bogus-state"},
        ),
    )

    status = video_watermark_cleanup.get_runtime_status(backend="migan", ffmpeg="ffmpeg", ffprobe="ffprobe")

    assert status.ready is True
    assert status.model_cache is None


def test_runtime_missing_root_is_reported_without_spawning_worker(tmp_path, monkeypatch) -> None:
    missing_root = tmp_path / "missing"
    monkeypatch.setenv(video_watermark_cleanup.WATERMARK_ROOT_ENV, str(missing_root))
    monkeypatch.setattr(
        video_watermark_cleanup,
        "_run_worker",
        lambda **_kwargs: pytest.fail("worker must not start when package root is missing"),
    )

    status = video_watermark_cleanup.get_runtime_status(
        backend="cv2",
        ffmpeg="ffmpeg",
        ffprobe="ffprobe",
    )

    assert status.ready is False
    assert status.error_code == "VIDEO_RENDER_WATERMARK_ROOT_MISSING"
    assert "remove-ai-watermarks" in (status.failure_reason or "")


def test_worker_environment_prepends_ffmpeg_and_ffprobe_paths(tmp_path) -> None:
    ffmpeg_dir = tmp_path / "ffmpeg-bin"
    ffprobe_dir = tmp_path / "ffprobe-bin"
    env = video_watermark_cleanup._worker_environment(
        package_root=tmp_path / "package",
        revision="abc123",
        ffmpeg=str(ffmpeg_dir / "ffmpeg.exe"),
        ffprobe=str(ffprobe_dir / "ffprobe.exe"),
    )

    path_parts = env["PATH"].split(os.pathsep)
    assert path_parts[:2] == [str(ffmpeg_dir.resolve()), str(ffprobe_dir.resolve())]
    assert env["PYTHONPATH"].split(os.pathsep)[0] == str(tmp_path / "package" / "src")
    assert env["PYTHONIOENCODING"] == "utf-8"
    assert env["VOICEBOX_WATERMARK_FFMPEG"] == str((ffmpeg_dir / "ffmpeg.exe").resolve())
    assert env["VOICEBOX_WATERMARK_FFPROBE"] == str((ffprobe_dir / "ffprobe.exe").resolve())
    assert env["VOICEBOX_WATERMARK_REVISION"] == "abc123"


def test_worker_creates_canonical_alias_for_versioned_ffmpeg(tmp_path, monkeypatch) -> None:
    suffix = ".exe" if os.name == "nt" else ""
    source = tmp_path / f"ffmpeg-versioned{suffix}"
    source.write_bytes(b"binary")
    monkeypatch.setenv(video_watermark_worker.FFMPEG_PATH_ENV, str(source))
    monkeypatch.delenv(video_watermark_worker.FFPROBE_PATH_ENV, raising=False)

    video_watermark_worker._configure_tool_aliases()

    resolved = video_watermark_worker.shutil.which("ffmpeg")
    assert resolved is not None
    assert Path(resolved).name.casefold() == f"ffmpeg{suffix}".casefold()
    assert Path(resolved).read_bytes() == b"binary"


def test_parse_worker_payload_uses_last_json_object() -> None:
    payload = video_watermark_cleanup._parse_worker_payload(
        "diagnostic line\n" + json.dumps({"ok": False}) + "\n" + json.dumps({"ok": True, "status": "removed"})
    )

    assert payload == {"ok": True, "status": "removed"}


def test_worker_timeout_has_stable_error_code(tmp_path, monkeypatch) -> None:
    runtime = _runtime(tmp_path)

    def timeout_run(*_args, **_kwargs):
        raise subprocess.TimeoutExpired(cmd=["python", "worker.py"], timeout=1)

    monkeypatch.setattr(video_watermark_cleanup.subprocess, "run", timeout_run)

    with pytest.raises(video_watermark_cleanup.VideoWatermarkCleanupError) as error:
        video_watermark_cleanup._run_worker(
            python=runtime.python or sys.executable,
            worker_script=runtime.worker_script or tmp_path / "worker.py",
            package_root=runtime.package_root or tmp_path,
            revision=runtime.revision or "unknown",
            ffmpeg="ffmpeg",
            ffprobe="ffprobe",
            request={"operation": "video_all"},
            timeout=1,
        )

    assert error.value.error_code == "VIDEO_RENDER_WATERMARK_TIMEOUT"


def test_cleanup_cache_hit_miss_invalidation_and_source_preservation(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(video_watermark_cleanup.video_storage.config, "get_data_dir", lambda: tmp_path)
    source = tmp_path / "source.mp4"
    source.write_bytes(b"source-v1")
    runtime = _runtime(tmp_path)
    calls: list[dict[str, object]] = []

    def fake_run_worker(**kwargs):
        request = dict(kwargs["request"])
        calls.append(request)
        Path(str(request["output_path"])).write_bytes(b"cleaned")
        payload = {
            "ok": True,
            "status": "no_supported_mark",
            "visible_mark": None,
            "visible_detected_frames": 0,
            "visible_removed_frames": 0,
            "detected_metadata": {},
            "remaining_metadata": {},
        }
        return subprocess.CompletedProcess(["worker"], 0, stdout=json.dumps(payload), stderr=""), payload

    monkeypatch.setattr(video_watermark_cleanup, "_run_worker", fake_run_worker)

    first_path, first = video_watermark_cleanup.cleanup_clip_with_cache(
        project_id="project-1",
        shot_id="shot-1",
        input_path=source,
        provider="veo",
        backend="cv2",
        runtime=runtime,
        ffmpeg="ffmpeg",
        ffprobe="ffprobe",
    )
    second_path, second = video_watermark_cleanup.cleanup_clip_with_cache(
        project_id="project-1",
        shot_id="shot-1",
        input_path=source,
        provider="veo",
        backend="cv2",
        runtime=runtime,
        ffmpeg="ffmpeg",
        ffprobe="ffprobe",
    )
    source.write_bytes(b"source-v2-changed")
    changed_path, changed = video_watermark_cleanup.cleanup_clip_with_cache(
        project_id="project-1",
        shot_id="shot-1",
        input_path=source,
        provider="veo",
        backend="cv2",
        runtime=runtime,
        ffmpeg="ffmpeg",
        ffprobe="ffprobe",
    )

    assert source.read_bytes() == b"source-v2-changed"
    assert first["cache_hit"] is False
    assert second["cache_hit"] is True
    assert changed["cache_hit"] is False
    assert first_path == second_path
    assert changed_path != first_path
    assert first["output_path"] == str(first_path)
    assert len(calls) == 2
    assert calls[0]["mark"] == "veo"
    assert calls[0]["include_invisible"] is False


def test_cleanup_does_not_publish_empty_worker_output(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(video_watermark_cleanup.video_storage.config, "get_data_dir", lambda: tmp_path)
    source = tmp_path / "source.mp4"
    source.write_bytes(b"source")
    runtime = _runtime(tmp_path)

    def fake_run_worker(**_kwargs):
        payload = {"ok": True, "status": "no_supported_mark"}
        return subprocess.CompletedProcess(["worker"], 0, stdout=json.dumps(payload), stderr=""), payload

    monkeypatch.setattr(video_watermark_cleanup, "_run_worker", fake_run_worker)

    with pytest.raises(video_watermark_cleanup.VideoWatermarkCleanupError) as error:
        video_watermark_cleanup.cleanup_clip_with_cache(
            project_id="project-1",
            shot_id="shot-1",
            input_path=source,
            provider=None,
            backend="cv2",
            runtime=runtime,
            ffmpeg="ffmpeg",
            ffprobe="ffprobe",
        )

    cache_root = video_watermark_cleanup.video_storage.get_project_subdir("project-1", "render_cache") / "watermark"
    assert error.value.error_code == "VIDEO_RENDER_WATERMARK_OUTPUT_MISSING"
    assert list(cache_root.glob("*.mp4")) == []
    assert list(cache_root.glob("*.json")) == []
    assert source.read_bytes() == b"source"


@pytest.mark.parametrize(
    ("provider", "expected"),
    [("veo", "veo"), ("VEO", "veo"), ("upload", "auto"), (None, "auto")],
)
def test_mark_for_provider_is_bounded(provider, expected) -> None:
    assert video_watermark_cleanup.mark_for_provider(provider) == expected


def _write_cache_report(tmp_path: Path, project_id: str, name: str, payload: dict) -> Path:
    cache_root = video_watermark_cleanup.video_storage.get_project_subdir(project_id, "render_cache") / "watermark"
    cache_root.mkdir(parents=True, exist_ok=True)
    report = cache_root / name
    report.write_text(json.dumps(payload), encoding="utf-8")
    return report


def test_resolve_clip_mark_prefers_clip_provider_over_cache_report(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(video_watermark_cleanup.video_storage.config, "get_data_dir", lambda: tmp_path)
    source = tmp_path / "source.mp4"
    source.write_bytes(b"source")
    _write_cache_report(
        tmp_path,
        "project-1",
        "old.json",
        {"ok": True, "visible_mark": "sora", "source_filename": "source.mp4", "shot_id": "shot-1"},
    )

    assert (
        video_watermark_cleanup.resolve_clip_mark(
            project_id="project-1",
            shot_id="shot-1",
            input_path=source,
            provider="veo",
        )
        == "veo"
    )


def test_resolve_clip_mark_reads_previous_cache_report_when_clip_has_no_provider(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(video_watermark_cleanup.video_storage.config, "get_data_dir", lambda: tmp_path)
    source = tmp_path / "source.mp4"
    source.write_bytes(b"source")
    _write_cache_report(
        tmp_path,
        "project-1",
        "old.json",
        {"ok": True, "visible_mark": "veo", "source_filename": "source.mp4", "shot_id": "shot-1"},
    )

    assert (
        video_watermark_cleanup.resolve_clip_mark(
            project_id="project-1",
            shot_id="shot-1",
            input_path=source,
            provider=None,
        )
        == "veo"
    )


@pytest.mark.parametrize(
    "payload",
    [
        # A failed run tells us nothing about the mark.
        {"ok": False, "visible_mark": "veo", "source_filename": "source.mp4", "shot_id": "shot-1"},
        # The worker found no supported mark, so there is nothing to narrow the scan to.
        {"ok": True, "visible_mark": None, "source_filename": "source.mp4", "shot_id": "shot-1"},
        # An unsupported mark must not be forwarded to the worker.
        {"ok": True, "visible_mark": "unknown-brand", "source_filename": "source.mp4", "shot_id": "shot-1"},
        # A report for a different clip must not leak across clips.
        {"ok": True, "visible_mark": "veo", "source_filename": "other.mp4", "shot_id": "shot-other"},
    ],
)
def test_resolve_clip_mark_falls_back_to_auto_scan(tmp_path, monkeypatch, payload) -> None:
    monkeypatch.setattr(video_watermark_cleanup.video_storage.config, "get_data_dir", lambda: tmp_path)
    source = tmp_path / "source.mp4"
    source.write_bytes(b"source")
    _write_cache_report(tmp_path, "project-1", "old.json", payload)

    assert (
        video_watermark_cleanup.resolve_clip_mark(
            project_id="project-1",
            shot_id="shot-1",
            input_path=source,
            provider=None,
        )
        == "auto"
    )


def test_resolve_clip_mark_is_auto_without_any_cache_dir(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(video_watermark_cleanup.video_storage.config, "get_data_dir", lambda: tmp_path)
    source = tmp_path / "source.mp4"
    source.write_bytes(b"source")

    assert (
        video_watermark_cleanup.resolve_clip_mark(
            project_id="project-fresh",
            shot_id="shot-1",
            input_path=source,
            provider=None,
        )
        == "auto"
    )


def test_cleanup_narrows_mark_from_previous_cache_report(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(video_watermark_cleanup.video_storage.config, "get_data_dir", lambda: tmp_path)
    source = tmp_path / "source.mp4"
    source.write_bytes(b"source")
    runtime = _runtime(tmp_path)
    _write_cache_report(
        tmp_path,
        "project-1",
        "previous-run.json",
        {"ok": True, "visible_mark": "veo", "source_filename": "source.mp4", "shot_id": "shot-1"},
    )
    calls: list[dict[str, object]] = []

    def fake_run_worker(**kwargs):
        request = dict(kwargs["request"])
        calls.append(request)
        Path(str(request["output_path"])).write_bytes(b"cleaned")
        payload = {"ok": True, "status": "cleaned", "visible_mark": "veo"}
        return subprocess.CompletedProcess(["worker"], 0, stdout=json.dumps(payload), stderr=""), payload

    monkeypatch.setattr(video_watermark_cleanup, "_run_worker", fake_run_worker)

    _, result = video_watermark_cleanup.cleanup_clip_with_cache(
        project_id="project-1",
        shot_id="shot-1",
        input_path=source,
        provider=None,
        backend="cv2",
        runtime=runtime,
        ffmpeg="ffmpeg",
        ffprobe="ffprobe",
    )

    assert calls[0]["mark"] == "veo"
    assert result["requested_mark"] == "veo"
