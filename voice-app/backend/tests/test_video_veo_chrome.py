from __future__ import annotations

import pytest

from backend.services import video_provider_sessions, video_veo_chrome


def _download_context(download_dir):
    return video_veo_chrome.DownloadContext(
        project_id="project-1",
        job_id="job-1",
        item_id="item-1",
        shot_id="shot-1",
        shot_order=1,
        prompt_id=None,
        expected_download_dir=download_dir,
        download_correlation_id="download-1",
    )


def test_configure_download_behavior_sets_browser_and_page_paths(tmp_path):
    class FakeClient:
        def __init__(self):
            self.browser_download_dir = None
            self.commands = []

        def set_download_behavior(self, download_dir):
            self.browser_download_dir = download_dir

        def command(self, method, params=None, *, timeout=15.0):
            self.commands.append((method, params, timeout))
            return {}

    client = FakeClient()
    download_dir = tmp_path / "item-download"

    video_veo_chrome._configure_download_behavior(client, download_dir)

    assert download_dir.exists()
    assert client.browser_download_dir == str(download_dir)
    assert client.commands == [
        (
            "Page.setDownloadBehavior",
            {"behavior": "allow", "downloadPath": str(download_dir)},
            5.0,
        ),
    ]


def test_configure_download_behavior_allows_one_cdp_scope_to_fail(tmp_path):
    class FakeClient:
        def set_download_behavior(self, _download_dir):
            raise RuntimeError("browser scope unsupported")

        def command(self, method, params=None, *, timeout=15.0):
            assert method == "Page.setDownloadBehavior"
            return {}

    video_veo_chrome._configure_download_behavior(FakeClient(), tmp_path / "item-download")


def test_configure_download_behavior_raises_when_all_cdp_scopes_fail(tmp_path):
    class FakeClient:
        def set_download_behavior(self, _download_dir):
            raise RuntimeError("browser scope unsupported")

        def command(self, _method, _params=None, *, timeout=15.0):
            raise RuntimeError("page scope unsupported")

    with pytest.raises(video_veo_chrome.VeoChromeError) as exc:
        video_veo_chrome._configure_download_behavior(FakeClient(), tmp_path / "item-download")

    assert exc.value.error_code == "VIDEO_DOWNLOAD_DIRECTORY_UNAVAILABLE"


def test_approve_credit_if_needed_waits_for_delayed_credit_prompt(monkeypatch):
    body_texts = iter(["", "Bạn có muốn tạo video này với chi phí là 15 tín dụng không?"])
    sleeps = []

    monkeypatch.setattr(video_veo_chrome, "_body_text", lambda _client: next(body_texts))
    monkeypatch.setattr(video_veo_chrome.time, "monotonic", lambda: 0.0)
    monkeypatch.setattr(video_veo_chrome.time, "sleep", lambda seconds: sleeps.append(seconds))
    monkeypatch.setattr(video_veo_chrome, "_approve_credit_from_text", lambda *_args, **_kwargs: 15)

    result = video_veo_chrome._approve_credit_if_needed(
        object(),
        credit_approval_policy="approve_dont_ask_again",
        max_credit_per_job=None,
        credit_spent_estimate=0,
    )

    assert result == 15
    assert sleeps == [1.0]


def test_click_download_when_ready_handles_credit_before_generation_pending(monkeypatch):
    approved = {"value": False}
    monotonic_values = iter([0.0, 0.1, 2.0])

    def fake_approve_credit(*_args, **_kwargs):
        approved["value"] = True
        return 15

    monkeypatch.setattr(video_veo_chrome.time, "monotonic", lambda: next(monotonic_values, 2.0))
    monkeypatch.setattr(video_veo_chrome.time, "sleep", lambda _seconds: None)
    monkeypatch.setattr(
        video_provider_sessions,
        "_read_page_snapshot",
        lambda _client, text_limit=5000: {"url": "https://labs.google/fx/tools/flow/project/test", "title": "Flow", "text": ""},
    )
    monkeypatch.setattr(video_veo_chrome, "_page_text_for_generation_wait", lambda _client, _snapshot: "15 tin dung dang tao")
    monkeypatch.setattr(video_veo_chrome, "_looks_like_flow_generation_pending", lambda _text: True)
    monkeypatch.setattr(video_veo_chrome, "_approve_credit_from_text", fake_approve_credit)

    with pytest.raises(video_veo_chrome.VeoChromeError) as exc:
        video_veo_chrome._click_download_when_ready(
            object(),
            timeout_seconds=1,
            baseline_media_count=0,
            credit_approval_policy="approve_dont_ask_again",
        )

    assert exc.value.error_code == "VIDEO_PROVIDER_DOWNLOAD_UNAVAILABLE"
    assert approved["value"] is True


def test_click_action_row_by_text_dispatches_native_mouse_click():
    class FakeClient:
        def __init__(self):
            self.evaluated_script = ""
            self.commands = []

        def evaluate(self, script, *, timeout=5.0):
            self.evaluated_script = script
            return {"x": 1743, "y": 473, "text": "phe duyet, khong hoi lai"}

        def command(self, method, params=None, *, timeout=15.0):
            self.commands.append((method, params))
            return {}

    client = FakeClient()

    assert video_veo_chrome._click_action_row_by_text(client, ["Phê duyệt, không hỏi lại"]) is True
    assert "getBoundingClientRect" in client.evaluated_script
    assert client.commands == [
        ("Input.dispatchMouseEvent", {"type": "mouseMoved", "x": 1743.0, "y": 473.0}),
        (
            "Input.dispatchMouseEvent",
            {"type": "mousePressed", "x": 1743.0, "y": 473.0, "button": "left", "buttons": 1, "clickCount": 1},
        ),
        (
            "Input.dispatchMouseEvent",
            {"type": "mouseReleased", "x": 1743.0, "y": 473.0, "button": "left", "buttons": 0, "clickCount": 1},
        ),
    ]


def test_wait_for_downloaded_video_raises_when_temp_download_stalls(tmp_path, monkeypatch):
    download_dir = tmp_path / "item-download"
    download_dir.mkdir()
    (download_dir / "clip.mp4.crdownload").write_bytes(b"partial")
    context = _download_context(download_dir)
    monotonic_values = iter([0.0, 0.0, 0.0, 0.0, 2.0, 2.0])

    monkeypatch.setattr(video_veo_chrome.time, "monotonic", lambda: next(monotonic_values, 2.0))
    monkeypatch.setattr(video_veo_chrome.time, "sleep", lambda _seconds: None)

    with pytest.raises(video_veo_chrome.VeoChromeError) as exc:
        video_veo_chrome.wait_for_downloaded_video(context, timeout_seconds=30, stalled_seconds=1)

    assert exc.value.error_code == "VIDEO_DOWNLOAD_STALLED"
    assert exc.value.details["download_correlation_id"] == "download-1"


def test_wait_for_downloaded_video_keeps_waiting_when_temp_download_grows(tmp_path, monkeypatch):
    download_dir = tmp_path / "item-download"
    download_dir.mkdir()
    temp_file = download_dir / "clip.mp4.crdownload"
    temp_file.write_bytes(b"a")
    context = _download_context(download_dir)
    monotonic_values = iter([0.0, 0.0, 0.0, 0.0, 1.0, 1.0, 3.0])

    def grow_download(_seconds):
        temp_file.write_bytes(temp_file.read_bytes() + b"a")

    monkeypatch.setattr(video_veo_chrome.time, "monotonic", lambda: next(monotonic_values, 3.0))
    monkeypatch.setattr(video_veo_chrome.time, "sleep", grow_download)

    with pytest.raises(video_veo_chrome.VeoChromeError) as exc:
        video_veo_chrome.wait_for_downloaded_video(context, timeout_seconds=2, stalled_seconds=1)

    assert exc.value.error_code == "VIDEO_DOWNLOAD_TIMEOUT"


def test_wait_for_downloaded_video_rejects_mp4_with_html_payload(tmp_path, monkeypatch):
    download_dir = tmp_path / "item-download"
    download_dir.mkdir()
    bad_file = download_dir / "clip.mp4"
    bad_file.write_bytes(b"<!doctype html><title>not a video</title>")
    context = _download_context(download_dir)

    monkeypatch.setattr(video_veo_chrome, "_stable_file", lambda _path: True)

    with pytest.raises(video_veo_chrome.VeoChromeError) as exc:
        video_veo_chrome.wait_for_downloaded_video(context)

    assert exc.value.error_code == "VIDEO_DOWNLOAD_INVALID_FILE"
    assert exc.value.details["filename"] == "clip.mp4"


def test_wait_for_downloaded_video_accepts_mp4_container_header(tmp_path, monkeypatch):
    download_dir = tmp_path / "item-download"
    download_dir.mkdir()
    good_file = download_dir / "clip.mp4"
    good_file.write_bytes(b"\x00\x00\x00\x20ftypisom\x00\x00\x02\x00isomiso2avc1mp41")
    context = _download_context(download_dir)

    monkeypatch.setattr(video_veo_chrome, "_stable_file", lambda _path: True)

    assert video_veo_chrome.wait_for_downloaded_video(context) == good_file


def test_download_generated_media_direct_ignores_non_video_response(tmp_path, monkeypatch):
    context = _download_context(tmp_path / "item-download")
    monkeypatch.setattr(
        video_veo_chrome,
        "_generated_media_download_info",
        lambda *_args, **_kwargs: {
            "ok": True,
            "downloadUrl": "https://example.test/thumb",
            "contentType": "image/jpeg",
        },
    )

    assert video_veo_chrome._download_generated_media_direct(object(), context) is False
    assert not context.expected_download_dir.exists()


def test_download_generated_media_direct_deletes_invalid_video_payload(tmp_path, monkeypatch):
    context = _download_context(tmp_path / "item-download")

    class FakeResponse:
        def __init__(self):
            self._chunks = iter([b"<html>not a video</html>", b""])

        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return False

        def read(self, _size):
            return next(self._chunks, b"")

    monkeypatch.setattr(
        video_veo_chrome,
        "_generated_media_download_info",
        lambda *_args, **_kwargs: {
            "ok": True,
            "downloadUrl": "https://example.test/clip.mp4",
            "contentType": "video/mp4",
        },
    )
    monkeypatch.setattr(video_veo_chrome, "urlopen", lambda *_args, **_kwargs: FakeResponse())

    assert video_veo_chrome._download_generated_media_direct(object(), context) is False
    assert list(context.expected_download_dir.iterdir()) == []


def test_click_download_when_ready_clicks_generated_video_preview_without_icon_text(monkeypatch):
    clicked = {"value": False}

    class FakeClient:
        def evaluate(self, script, *, timeout=5.0):
            # Simulates a Flow result card that contains a visible <video>, but no
            # material-icon text such as play_circle/pause_circle in body text.
            if "querySelectorAll('video,img,canvas')" in script or "matches('video,img,canvas')" in script:
                return True
            return False

    def fake_click_generated_media_download(_client):
        clicked["value"] = True
        return True

    monotonic_values = iter([0.0, 0.1, 2.0])

    monkeypatch.setattr(video_veo_chrome.time, "monotonic", lambda: next(monotonic_values, 2.0))
    monkeypatch.setattr(video_veo_chrome.time, "sleep", lambda _seconds: None)
    monkeypatch.setattr(
        video_provider_sessions,
        "_read_page_snapshot",
        lambda _client, text_limit=5000: {"url": "https://labs.google/fx/tools/flow/project/test", "title": "Flow", "text": ""},
    )
    monkeypatch.setattr(video_veo_chrome, "_body_text", lambda _client, timeout=10.0: "")
    monkeypatch.setattr(video_veo_chrome, "_generated_media_count", lambda _client: 1)
    monkeypatch.setattr(video_veo_chrome, "_click_generated_media_download", fake_click_generated_media_download)

    result = video_veo_chrome._click_download_when_ready(
        FakeClient(),
        timeout_seconds=1,
        baseline_media_count=0,
    )

    assert result is None
    assert clicked["value"] is True


def test_click_download_when_ready_downloads_visible_media_directly_when_click_fails(tmp_path, monkeypatch):
    direct_downloaded = {"value": False}
    context = _download_context(tmp_path / "item-download")
    monotonic_values = iter([0.0, 0.1, 2.0])

    monkeypatch.setattr(video_veo_chrome.time, "monotonic", lambda: next(monotonic_values, 2.0))
    monkeypatch.setattr(video_veo_chrome.time, "sleep", lambda _seconds: None)
    monkeypatch.setattr(
        video_provider_sessions,
        "_read_page_snapshot",
        lambda _client, text_limit=5000: {"url": "https://labs.google/fx/tools/flow/project/test", "title": "Flow", "text": ""},
    )
    monkeypatch.setattr(video_veo_chrome, "_body_text", lambda _client, timeout=10.0: "")
    monkeypatch.setattr(video_veo_chrome, "_generated_media_count", lambda _client: 1)
    monkeypatch.setattr(video_veo_chrome, "_has_generated_media_preview", lambda _client: True)
    monkeypatch.setattr(video_veo_chrome, "_click_generated_media_download", lambda _client: False)

    def fake_direct_download(_client, download_context, **_kwargs):
        assert download_context == context
        direct_downloaded["value"] = True
        return True

    monkeypatch.setattr(video_veo_chrome, "_download_generated_media_direct", fake_direct_download)

    result = video_veo_chrome._click_download_when_ready(
        object(),
        timeout_seconds=1,
        baseline_media_count=0,
        download_context=context,
    )

    assert result is None
    assert direct_downloaded["value"] is True


def test_click_download_when_ready_does_not_download_baseline_media(tmp_path, monkeypatch):
    context = _download_context(tmp_path / "item-download")
    monotonic_values = iter([0.0, 0.1, 2.0])

    monkeypatch.setattr(video_veo_chrome.time, "monotonic", lambda: next(monotonic_values, 2.0))
    monkeypatch.setattr(video_veo_chrome.time, "sleep", lambda _seconds: None)
    monkeypatch.setattr(
        video_provider_sessions,
        "_read_page_snapshot",
        lambda _client, text_limit=5000: {"url": "https://labs.google/fx/tools/flow/project/test", "title": "Flow", "text": ""},
    )
    monkeypatch.setattr(video_veo_chrome, "_body_text", lambda _client, timeout=10.0: "")
    monkeypatch.setattr(video_veo_chrome, "_generated_media_count", lambda _client: 1)
    monkeypatch.setattr(video_veo_chrome, "_has_generated_media_preview", lambda _client: True)
    monkeypatch.setattr(video_veo_chrome, "_generated_media_urls", lambda _client: {"https://labs.google/old-media"})
    monkeypatch.setattr(video_veo_chrome, "_click_generated_media_download", lambda _client: pytest.fail("should not click old media"))
    monkeypatch.setattr(video_veo_chrome, "_download_generated_media_direct", lambda *_args, **_kwargs: pytest.fail("should not download old media"))

    with pytest.raises(video_veo_chrome.VeoChromeError) as exc:
        video_veo_chrome._click_download_when_ready(
            object(),
            timeout_seconds=1,
            baseline_media_count=0,
            download_context=context,
            baseline_media_urls={"https://labs.google/old-media"},
        )

    assert exc.value.error_code == "VIDEO_PROVIDER_DOWNLOAD_UNAVAILABLE"


def test_click_download_when_ready_rejects_multiple_new_media(tmp_path, monkeypatch):
    context = _download_context(tmp_path / "item-download")
    monotonic_values = iter([0.0, 0.1, 2.0])

    monkeypatch.setattr(video_veo_chrome.time, "monotonic", lambda: next(monotonic_values, 2.0))
    monkeypatch.setattr(video_veo_chrome.time, "sleep", lambda _seconds: None)
    monkeypatch.setattr(
        video_provider_sessions,
        "_read_page_snapshot",
        lambda _client, text_limit=5000: {"url": "https://labs.google/fx/tools/flow/project/test", "title": "Flow", "text": ""},
    )
    monkeypatch.setattr(video_veo_chrome, "_body_text", lambda _client, timeout=10.0: "")
    monkeypatch.setattr(video_veo_chrome, "_generated_media_count", lambda _client: 3)
    monkeypatch.setattr(video_veo_chrome, "_has_generated_media_preview", lambda _client: True)
    monkeypatch.setattr(
        video_veo_chrome,
        "_generated_media_urls",
        lambda _client: {"https://labs.google/old-media", "https://labs.google/new-1", "https://labs.google/new-2"},
    )
    monkeypatch.setattr(video_veo_chrome, "_click_generated_media_download", lambda _client: pytest.fail("should not click ambiguous media"))
    monkeypatch.setattr(video_veo_chrome, "_download_generated_media_direct", lambda *_args, **_kwargs: pytest.fail("should not download ambiguous media"))

    with pytest.raises(video_veo_chrome.VeoChromeError) as exc:
        video_veo_chrome._click_download_when_ready(
            object(),
            timeout_seconds=1,
            baseline_media_count=1,
            download_context=context,
            baseline_media_urls={"https://labs.google/old-media"},
        )

    assert exc.value.error_code == "VIDEO_DOWNLOAD_AMBIGUOUS"

def test_provider_limit_text_pauses_selected_model_quota_without_fallback():
    with pytest.raises(video_veo_chrome.VeoChromeError) as exc:
        video_veo_chrome._raise_provider_limit_or_policy_if_present("model has insufficient credits")

    assert exc.value.error_code == "VIDEO_PROVIDER_MODEL_QUOTA_EXHAUSTED"

def test_open_existing_flow_project_needs_login_does_not_invalidate(monkeypatch):
    class FakeClient:
        def __init__(self):
            self.navigated_to = None

        def navigate(self, url, timeout=20.0):
            self.navigated_to = url

    client = FakeClient()
    url = "https://labs.google/fx/tools/flow/project/needs-login"
    monkeypatch.setattr(
        video_veo_chrome,
        "_wait_for_flow_project_ready",
        lambda _client: {"url": "https://accounts.google.com/", "title": "Sign in", "text": "Choose an account"},
    )

    with pytest.raises(video_veo_chrome.VeoChromeError) as exc:
        video_veo_chrome._open_existing_flow_project(client, url)

    assert exc.value.error_code == "VIDEO_PROVIDER_PROJECT_NEEDS_LOGIN"
    assert client.navigated_to == url

def test_open_existing_flow_project_invalid_is_explicit_invalid(monkeypatch):
    class FakeClient:
        def navigate(self, _url, timeout=20.0):
            return None

    monkeypatch.setattr(
        video_veo_chrome,
        "_wait_for_flow_project_ready",
        lambda _client: {
            "url": "https://labs.google/fx/tools/flow/project/missing",
            "title": "Flow",
            "text": "Project not found",
        },
    )

    with pytest.raises(video_veo_chrome.VeoChromeError) as exc:
        video_veo_chrome._open_existing_flow_project(FakeClient(), "https://labs.google/fx/tools/flow/project/missing")

    assert exc.value.error_code == "VIDEO_PROVIDER_PROJECT_INVALID"

def test_read_current_flow_model_only_evaluates_without_clicking():
    class FakeClient:
        def __init__(self):
            self.commands = []

        def evaluate(self, script, *, timeout=5.0):
            assert "dispatchMouseEvent" not in script
            return {"label": "Veo Quality 20 credits", "costLabel": "20 credits", "source": "selected"}

        def command(self, method, params=None, *, timeout=15.0):
            self.commands.append((method, params))

    client = FakeClient()
    observation = video_veo_chrome._read_current_flow_model(client)

    assert observation.label == "Veo Quality 20 credits"
    assert observation.cost_label == "20 credits"
    assert client.commands == []

def test_click_download_when_ready_allows_retry_error_to_settle(monkeypatch):
    retry_clicks = {"count": 0}
    monotonic_values = iter([0.0, 0.1, 0.2, 0.4, 1.0, 1.2, 2.1])

    def fake_retry(_client):
        retry_clicks["count"] += 1
        return True

    monkeypatch.setattr(video_veo_chrome.time, "monotonic", lambda: next(monotonic_values, 2.1))
    monkeypatch.setattr(video_veo_chrome.time, "sleep", lambda _seconds: None)
    monkeypatch.setattr(
        video_provider_sessions,
        "_read_page_snapshot",
        lambda _client, text_limit=5000: {"url": "https://labs.google/fx/tools/flow/project/test", "title": "Flow", "text": ""},
    )
    monkeypatch.setattr(video_veo_chrome, "_page_text_for_generation_wait", lambda _client, _snapshot: "something went wrong try again")
    monkeypatch.setattr(video_veo_chrome, "_click_generation_retry", fake_retry)
    monkeypatch.setattr(video_veo_chrome, "_generated_media_count", lambda _client: 0)
    monkeypatch.setattr(video_veo_chrome, "_has_generated_media_preview", lambda _client: False)

    with pytest.raises(video_veo_chrome.VeoChromeError) as exc:
        video_veo_chrome._click_download_when_ready(
            object(),
            timeout_seconds=2,
            baseline_media_count=0,
        )

    assert retry_clicks["count"] == 1
    assert exc.value.error_code == "VIDEO_PROVIDER_DOWNLOAD_UNAVAILABLE"


def test_generation_pending_detects_flow_progress_percent():
    assert video_veo_chrome._looks_like_flow_generation_pending("play_circle 6%")


def test_click_generation_retry_accepts_reuse_prompt_label(monkeypatch):
    captured = {}

    def fake_click_action(_client, texts, timeout=3.0):
        captured["texts"] = texts
        return True

    monkeypatch.setattr(video_veo_chrome, "_click_action_row_by_text", fake_click_action)

    assert video_veo_chrome._click_generation_retry(object()) is True
    assert "S\u1eed d\u1ee5ng l\u1ea1i c\u00e2u l\u1ec7nh" in captured["texts"]


def test_click_download_when_ready_treats_progress_as_pending(monkeypatch):
    monotonic_values = iter([0.0, 0.1, 1.0, 2.1])

    monkeypatch.setattr(video_veo_chrome.time, "monotonic", lambda: next(monotonic_values, 2.1))
    monkeypatch.setattr(video_veo_chrome.time, "sleep", lambda _seconds: None)
    monkeypatch.setattr(
        video_provider_sessions,
        "_read_page_snapshot",
        lambda _client, text_limit=5000: {"url": "https://labs.google/fx/tools/flow/project/test", "title": "Flow", "text": ""},
    )
    monkeypatch.setattr(video_veo_chrome, "_page_text_for_generation_wait", lambda _client, _snapshot: "warning something went wrong play_circle 6%")
    monkeypatch.setattr(video_veo_chrome, "_click_generation_retry", lambda _client: pytest.fail("progress should not click retry"))
    monkeypatch.setattr(video_veo_chrome, "_generated_media_count", lambda _client: 0)
    monkeypatch.setattr(video_veo_chrome, "_has_generated_media_preview", lambda _client: False)

    with pytest.raises(video_veo_chrome.VeoChromeError) as exc:
        video_veo_chrome._click_download_when_ready(
            object(),
            timeout_seconds=2,
            baseline_media_count=0,
        )

    assert exc.value.error_code == "VIDEO_PROVIDER_DOWNLOAD_UNAVAILABLE"


def test_click_download_when_ready_times_out_without_generated_media(monkeypatch):
    monotonic_values = iter([0.0, 0.1, 2.0])

    monkeypatch.setattr(video_veo_chrome.time, "monotonic", lambda: next(monotonic_values, 2.0))
    monkeypatch.setattr(video_veo_chrome.time, "sleep", lambda _seconds: None)
    monkeypatch.setattr(
        video_provider_sessions,
        "_read_page_snapshot",
        lambda _client, text_limit=5000: {"url": "https://labs.google/fx/tools/flow/project/test", "title": "Flow", "text": ""},
    )
    monkeypatch.setattr(video_veo_chrome, "_body_text", lambda _client, timeout=10.0: "")
    monkeypatch.setattr(video_veo_chrome, "_generated_media_count", lambda _client: 0)

    with pytest.raises(video_veo_chrome.VeoChromeError) as exc:
        video_veo_chrome._click_download_when_ready(object(), timeout_seconds=1, baseline_media_count=0)

    assert exc.value.error_code == "VIDEO_PROVIDER_DOWNLOAD_UNAVAILABLE"


def test_click_generated_media_target_dispatches_native_mouse_click():
    class FakeClient:
        def __init__(self):
            self.evaluated_script = ""
            self.commands = []

        def evaluate(self, script, *, timeout=5.0):
            self.evaluated_script = script
            return {"x": 125.5, "y": 240.25, "kind": "media"}

        def command(self, method, params=None, *, timeout=15.0):
            self.commands.append((method, params))
            return {}

    client = FakeClient()

    assert video_veo_chrome._click_generated_media_target(client) is True
    assert "querySelectorAll('video,img,canvas')" in client.evaluated_script
    assert client.commands == [
        ("Input.dispatchMouseEvent", {"type": "mouseMoved", "x": 125.5, "y": 240.25}),
        (
            "Input.dispatchMouseEvent",
            {"type": "mousePressed", "x": 125.5, "y": 240.25, "button": "left", "buttons": 1, "clickCount": 1},
        ),
        (
            "Input.dispatchMouseEvent",
            {"type": "mouseReleased", "x": 125.5, "y": 240.25, "button": "left", "buttons": 0, "clickCount": 1},
        ),
    ]
