## ADDED Requirements

### Requirement: Story Episode stores output production settings
Story Studio SHALL let each Story Episode store image-story and video-handoff production settings.

#### Scenario: Create episode with explicit output settings
- **WHEN** the user creates a Story Episode
- **THEN** the request MAY include output settings for image panel count, image size, video format, dialogue mode and language
- **AND** the response SHALL return the normalized output settings
- **AND** missing settings SHALL receive safe defaults

#### Scenario: Update episode output settings
- **WHEN** the user updates output settings before creating adaptations
- **THEN** subsequent image and video adaptations SHALL use the new settings

### Requirement: Image Story panel count can be automatic or manual
Story Studio SHALL support automatic image panel count and user-selected manual image panel count.

#### Scenario: Manual panel count
- **WHEN** the Story Episode output settings set image panel mode to `manual` and provide a valid panel count
- **THEN** Image Story adaptation SHALL create that many panel prompts
- **AND** each prompt SHALL include the configured image aspect ratio and size

#### Scenario: Automatic panel count from AI Video micro-scenes
- **WHEN** a linked AI Video project has generated shots with micro-scenes
- **THEN** Image Story adaptation auto mode SHALL create one image panel prompt per micro-scene
- **AND** panel metadata SHALL identify the source shot and micro-scene

#### Scenario: Automatic fallback before video shots exist
- **WHEN** no linked AI Video micro-scenes exist yet
- **THEN** Image Story adaptation auto mode SHALL derive panel count from the Master Story key beats, visual moments and motion beats
- **AND** it MUST NOT cap the result to eight panels

### Requirement: Video Story handoff uses episode settings and stops at AI Video project creation
Story Studio SHALL use Story Episode video handoff settings when creating the linked AI Video project and SHALL not auto-run later AI Video steps.

#### Scenario: Handoff with video settings
- **WHEN** the user creates a video adaptation from an approved Master Story
- **THEN** the linked AI Video project SHALL receive the configured aspect ratio, target language, dialogue mode, narration density, video purpose and prompt segment settings
- **AND** the adaptation payload SHALL state that the handoff is handoff-only

#### Scenario: User continues manually in AI Video
- **WHEN** the handoff completes
- **THEN** Story Studio SHALL provide the AI Video project link
- **AND** Story Studio SHALL NOT automatically generate story, shots, prompts, clips, voice, subtitles or final render
