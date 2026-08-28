from __future__ import annotations

import asyncio
from types import SimpleNamespace

from backend import models
from backend.services import video_clip_generation, video_rendering


def test_compact_prompt_for_veo_provider_keeps_provider_critical_sections():
    vietnamese_heading = "B\u1ea3n gi\u1ea3i th\u00edch ti\u1ebfng Vi\u1ec7t:"
    prompt = "\n\n".join(
        [
            (
                "Create a 10-second 16:9 video. This is segment 2 of 6. "
                "Use English voiceover narration. Timeline with exactly 3 continuous micro-scenes: "
                "0.00-3.33s enter a glowing forest. 3.33-6.67s vines close behind the hero. "
                "6.67-10.00s symbols lead toward a crystal cave."
            ),
            "Video language: English\nSegment: 2 of 6",
            (
                "Micro-scene timeline:\n"
                "0-3.3s: Ng\u01b0\u1eddi que \u0111i gi\u1eefa r\u1eebng ph\u00e1t s\u00e1ng.\n"
                "3.3-6.7s: D\u00e2y leo kh\u00e9p l\u1ea1i sau l\u01b0ng."
            ),
            "Aspect ratio: 16:9\nShot type: Cinematic forest traversal.",
            "Retention notes: Keep viewers asking whether the forest is a guide or a trap.",
            "Transition notes: Compass whip-pan into blue-violet cave light.",
            "Sound design notes: Add leaf rustle, compass ticks, and a crystal ring while voiceover stays clear.",
            "Negative prompt:\nNo readable text, no burned-in subtitles, no watermark, no logo.",
            (
                f"{vietnamese_heading}\n"
                "Ng\u01b0\u1eddi que \u0111i v\u00e0o r\u1eebng, ph\u1ea7n n\u00e0y ch\u1ec9 \u0111\u1ec3 ng\u01b0\u1eddi d\u00f9ng \u0111\u1ecdc."
            ),
        ]
    )

    compact = video_clip_generation.compact_prompt_for_veo_provider(prompt)

    assert len(compact) < len(prompt)
    assert "Create a 10-second 16:9 video" in compact
    assert "Video language: English" in compact
    assert "Retention notes:" in compact
    assert "Sound design notes:" in compact
    assert "Negative prompt:" in compact
    assert "Micro-scene timeline:" not in compact
    assert vietnamese_heading not in compact
    assert "Ng\u01b0\u1eddi que" not in compact


def test_provider_safe_prompt_for_veo_compacts_and_preserves_public_figure_safety():
    prompt = (
        "Create a 10-second 16:9 video about Messi as a stick figure explorer.\n\n"
        "Video language: English\n\n"
        "Micro-scene timeline:\n0-3s: extra duplicate notes.\n\n"
        "Retention notes: Open with a map mystery.\n\n"
        "Sound design notes: Keep voiceover clear.\n\n"
        "Negative prompt:\nNo readable text, no burned-in subtitles.\n\n"
        "B\u1ea3n gi\u1ea3i th\u00edch ti\u1ebfng Vi\u1ec7t:\nB\u1ecf ph\u1ea7n n\u00e0y khi g\u1eedi provider."
    )

    safe, changed = video_clip_generation.provider_safe_prompt_for_veo(prompt)

    assert changed is True
    assert "Messi" not in safe
    assert "an Argentina football supporter" in safe
    assert "Use only fictional simple stick-figure" in safe
    assert "B\u1ea3n gi\u1ea3i th\u00edch" not in safe


def test_provider_safe_prompt_for_veo_keeps_text_context_but_blocks_rendered_text_and_audio():
    prompt = "\n\n".join(
        [
            (
                "Create a 10-second 9:16 cinematic video. Use English voiceover narration. "
                "Timeline with three visual beats: enter, hold, exit."
            ),
            (
                "Animation and subtitle-safe rule: align visible action beats with the narration timing, "
                "use clear entry/hold/exit motion, avoid baked-in subtitles or random text, "
                "and leave the lower caption area readable for the yellow karaoke subtitle added during render."
            ),
            "Sound design notes: Add a soft riser while voiceover stays clear.",
            "Negative prompt:\nNo readable text, no burned-in subtitles, no watermark, no logo.",
        ]
    )
    narration = "He enters the room and realizes the warning was true."

    safe, changed = video_clip_generation.provider_safe_prompt_for_veo(prompt, narration_context=narration)
    lowered = safe.casefold()

    assert changed is True
    assert "Create a 10-second 9:16 cinematic video" in safe
    assert "Timeline with three visual beats" in safe
    assert "Narration/subtitle context only:" in safe
    assert narration in safe
    assert "provided only so you understand the story context and timing" in safe
    assert "Do not render subtitles, captions, spoken audio" in safe
    assert "provided the provided" not in lowered
    assert "leave the lower caption area" not in lowered
    assert "yellow karaoke subtitle added during render" not in lowered
    assert "use english voiceover narration" not in lowered
    assert "no watermark" in lowered


def test_provider_safe_prompt_for_veo_appends_exact_vietnamese_native_speech_without_audio_blocker():
    prompt = (
        "Create a 10-second 9:16 cinematic video. A young detective turns toward the camera.\n\n"
        "Retention notes: Hold on her eyes before the reveal.\n\n"
        "Negative prompt:\nNo readable text, no burned-in subtitles, no watermark."
    )
    native_speech = "\n".join(
        [
            "Vietnamese spoken dialogue — generate this as audible audio inside the Veo clip:",
            "Speaker 1: Lan",
            "- Canonical voice: warm low female voice, calm and precise",
            "- Current emotion: controlled fear",
            "- Scene context: Lan sees the hidden door open behind the suspect",
            "- Lip sync: required for the visible speaker",
            '- Speak exactly once in Vietnamese: "Tôi biết anh đã giấu cánh cửa ở đâu."',
        ]
    )

    safe, changed = video_clip_generation.provider_safe_prompt_for_veo(
        prompt,
        narration_context="This context must not be appended for native speech.",
        native_speech_section=native_speech,
    )
    lowered = safe.casefold()

    assert changed is True
    assert "Create a 10-second 9:16 cinematic video" in safe
    assert native_speech in safe
    assert '"Tôi biết anh đã giấu cánh cửa ở đâu."' in safe
    assert "warm low female voice" in safe
    assert "narration/subtitle context only" not in lowered
    assert "do not render subtitles, captions, spoken audio" not in lowered


def test_auto_render_handoff_uses_saved_project_settings(monkeypatch):
    chosen = models.VideoRenderSettings(mute_clip_audio=False, fps=60, subtitle_mode="none")
    job = SimpleNamespace(
        id="clip-job",
        project_id="project-1",
        status="completed",
        current_step="completed",
        failure_reason=None,
        render_job_id=None,
        updated_at=None,
    )
    render = SimpleNamespace(id="render-job")
    captured: dict[str, models.VideoRenderSettings] = {}

    class FakeQuery:
        def filter(self, *args):
            return self

        def first(self):
            return job

    class FakeDb:
        def query(self, model):
            return FakeQuery()

        def commit(self):
            return None

        def close(self):
            return None

    fake_db = FakeDb()
    monkeypatch.setattr(video_clip_generation, "get_db", lambda: iter([fake_db]))
    monkeypatch.setattr(
        video_rendering,
        "render_settings_for_project",
        lambda project_id, session: chosen,
    )
    monkeypatch.setattr(
        video_rendering,
        "get_render_readiness",
        lambda project_id, session, settings: models.VideoRenderReadinessResponse(
            project_id=project_id,
            ready=True,
            ffmpeg_ready=True,
            ffprobe_ready=True,
        ),
    )

    async def fake_create(project_id, data, session):
        captured["settings"] = data.settings
        return render

    monkeypatch.setattr(video_rendering, "create_render_job", fake_create)

    asyncio.run(video_clip_generation._handoff_render(job.id))

    assert captured["settings"] == chosen
    assert captured["settings"].mute_clip_audio is False
    assert job.render_job_id == "render-job"
    assert job.current_step == "auto_render_started"
