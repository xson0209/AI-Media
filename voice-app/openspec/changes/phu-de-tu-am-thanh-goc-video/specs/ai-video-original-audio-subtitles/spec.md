## ADDED Requirements

### Requirement: Original audio subtitle choice
The system SHALL allow clip-only audio projects to render with `subtitle_mode=none`, `sidecar`, or `burn_in`.

#### Scenario: No subtitles
- **WHEN** audio mode is original audio and subtitle mode is none
- **THEN** MP4 SHALL preserve original clip audio and SHALL NOT require or create a subtitle artifact.

#### Scenario: Subtitles enabled
- **WHEN** audio mode is original audio and subtitle mode is sidecar or burn_in
- **THEN** the system SHALL transcribe each active clip audio track, create timestamped cues on the render timeline, and use the existing subtitle style/render path.

#### Scenario: Voice is absent
- **WHEN** original audio subtitles are requested and TTS voice is missing
- **THEN** subtitle generation SHALL continue if clip audio is readable and SHALL NOT report missing voice as the blocker.

#### Scenario: Clip changes
- **WHEN** an active clip, its duration, or source audio changes
- **THEN** dependent subtitles SHALL become stale and the UI SHALL require regeneration before subtitle render.

