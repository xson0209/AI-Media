## What

Add episode-level production settings to Story Studio so each Story Episode can define:

- image story panel mode: automatic or manual count
- image size/aspect ratio for generated image prompts
- video handoff format, aspect ratio, duration/segment settings, dialogue mode and language
- whether Story Studio stops at AI Video handoff instead of auto-running the video pipeline

## Why

Story Studio currently creates image prompts from a small fixed slice of Master Story beats. That is too coarse for scroll-style image stories, where one episode may need many panels to cover all story beats. Hybrid episodes also need clearer handoff settings so the AI Video project receives the intended video format, dialogue style and language while leaving later AI Video steps under user control.

## Scope

- Store output settings on `StoryEpisode`.
- Use the settings when creating image adaptations and video adaptations.
- Expose the settings in the Story Studio create episode UI.
- Preserve existing episodes with safe defaults.
- Do not auto-run AI Video planning, prompt generation, clips, voice, subtitles or render after handoff.
