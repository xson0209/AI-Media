# Design

## Flow
```text
clip active -> extract audio -> Whisper segments -> timeline offset -> VideoSubtitle cues
                                                        |
                                     subtitle_mode none / sidecar / burn_in
                                                        |
                                  render clip-only audio + optional ASS subtitle
```

`clip_audio_mode=clip_only` is the source of truth for original audio. For each active clip, resolve its stored file path, transcribe it with the existing Whisper service, and offset segment timestamps by the clip's render timeline cursor. Segment timestamps are preferred; when unavailable, use the clip duration for one cue. Existing cue splitting and ASS style remain shared with Voice.

Subtitle generation must not require `voice_status=completed` in clip-only mode. It must require an active clip with readable audio for each spoken shot. `subtitle_mode=none` skips generation and readiness requirements. Changing an active clip, its duration, or audio source marks the project subtitle stale.

The UI keeps the existing Audio and Subtitle selects. Selecting original audio plus burn-in/sidecar makes the render readiness path generate or request subtitles; selecting none renders audio-only.

## Risks
Whisper model availability and clips without speech. Return clear per-shot errors and never silently fall back to narration text.
