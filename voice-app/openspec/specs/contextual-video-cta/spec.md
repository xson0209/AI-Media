# contextual-video-cta Specification

## Purpose
TBD - created by archiving change contextual-video-cta-actions. Update Purpose after archive.
## Requirements
### Requirement: CTA action is distinct from CTA tone

The system SHALL store a normalized `cta_action` independently from `call_to_action_style`, with one primary action selected from `none`, `comment`, `like`, `share`, `follow`, `save`, and `subscribe`.

#### Scenario: Legacy project
- **WHEN** a project has no `cta_action`
- **THEN** the system SHALL treat it as `none` and preserve existing prompt behavior

#### Scenario: User selects comment CTA
- **WHEN** the user selects `comment` with any supported CTA tone
- **THEN** story, shot, prompt, voice, subtitle, and publishing context SHALL receive the normalized action

### Requirement: CTA delivery follows final-shot context

For a non-`none` action, AI planning SHALL derive the final CTA speech and visual delivery from the approved final beat, visible character, setting, props, action, and emotional state.

#### Scenario: Contextual human delivery
- **WHEN** the final beat contains a speaking character
- **THEN** the final shot SHALL use a plausible human gesture and an exact target-language `speech_cue` that naturally follows the scene

#### Scenario: No suitable visible character
- **WHEN** the final beat cannot express the action naturally through a visible character
- **THEN** the system SHALL use voiceover over the existing final composition or disable the CTA, without inventing a character

#### Scenario: Provider-safe output
- **WHEN** a CTA is generated
- **THEN** the video prompt SHALL not ask the provider to render platform buttons, UI text, subtitles, or arbitrary words; exact speech SHALL remain in `speech_cues`

### Requirement: CTA quality and safety are validated

The system SHALL validate that a non-`none` CTA has one primary action, context continuity, target-language speech, and a final hold long enough for delivery.

#### Scenario: Context mismatch
- **WHEN** the CTA introduces an unrelated character, prop, setting, or implausible gesture
- **THEN** prompt quality SHALL fail or require review and SHALL not mark the final artifact ready

#### Scenario: Kids or unsupported interaction
- **WHEN** the project is made for kids or the selected platform does not support the requested interaction
- **THEN** the system SHALL avoid an invalid direct engagement request and choose a safe alternative or `none`

### Requirement: CTA changes invalidate dependent artifacts

Changing `cta_action` SHALL mark dependent story, shot, prompt, voice, subtitle, publishing metadata, and render/package outputs stale while preserving the previous valid revision.

#### Scenario: User changes CTA action after prompt generation
- **WHEN** the user changes `cta_action` on a project with generated prompts or voice
- **THEN** dependent artifacts SHALL become stale and the previous valid artifacts SHALL remain available for inspection

