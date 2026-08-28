# Product Video render parity

## ADDED Requirements

### Requirement: Product Video SHALL expose render-compatible state

The Product Video project detail MUST include a render bridge identifier and ordered AI Video-compatible shots after planning.

#### Scenario: planning creates render state

- **WHEN** a Product Video project successfully plans its shots
- **THEN** the service MUST create or synchronize a phase-2 render bridge and one ordered render shot per Product Video shot
- **AND** the detail response MUST expose the bridge identifier and render shots

### Requirement: Product Video SHALL reuse shared clip upload and render behavior

The Product Video workspace MUST support the same clip upload, replacement, deletion, batch import, readiness, render settings, MP4 render, preview, and download behavior as AI Video.

#### Scenario: user replaces an uploaded clip

- **WHEN** the user selects a replacement video for a Product Video render shot
- **THEN** the shared AI Video clip endpoint MUST deactivate the previous active clip and probe/store the replacement
- **AND** readiness and stale render state MUST refresh in the Product Video workspace

#### Scenario: user renders a product video

- **WHEN** every render shot has a valid clip and readiness requirements pass
- **THEN** the user MUST be able to start an explicit MP4 render with the selected settings
- **AND** the workspace MUST expose progress, failure, stale-output, MP4 download, AI review download, and timeline download states

### Requirement: Product Video SHALL remain prompt-specific

Product Video MUST keep its product-fidelity, motion-constraint, Vietnamese speech, and provider-schema safeguards, and MUST NOT create provider clip-generation, TTS, or render jobs automatically during planning or prompt generation.

#### Scenario: prompt generation remains isolated

- **WHEN** a user plans shots or generates a Product Video prompt pack
- **THEN** the operation MUST only create/update Product Video planning and prompt artifacts plus the internal render bridge
- **AND** no provider-generation job, TTS job, or render job MUST be queued until the user explicitly uploads clips and presses the render action

### Requirement: Product Video bridge lifecycle SHALL be safe and idempotent

Bridge synchronization MUST be repeatable, preserve valid user-uploaded clips where possible, mark completed render outputs stale when inputs change, and delete bridge artifacts when the Product Video project is deleted.

#### Scenario: re-planning an existing project

- **WHEN** a project is planned again after clips or a render exist
- **THEN** the bridge MUST synchronize the new shot/prompt state without creating duplicate bridge rows
- **AND** any completed render depending on changed inputs MUST become stale

### Requirement: Product Video SHALL expose AI Video-like creation configuration

Product Video MUST expose dialogue mode, narration density, CTA, creation mode,
automation level, output target, prompt count, seconds per prompt, and micro-scene
count with the same interaction hierarchy as AI Video. The Product Video-safe
automation boundary MUST remain explicit in the labels and behavior.

#### Scenario: quick Product Video creation

- **WHEN** the user chooses `Dựng nhanh` and creates a Product Video project
- **THEN** the selected local planning/prompt stages MAY run automatically
- **AND** the selected configuration MUST be persisted on the Product Video project
- **AND** no provider-generation, Chrome, TTS, subtitle, or render job MUST be queued

#### Scenario: manual Product Video creation

- **WHEN** the user chooses `Thủ công` and creates a Product Video project
- **THEN** the project MUST be created without running planning or prompt generation
- **AND** the existing explicit `Lập kế hoạch`, `Sinh prompt`, upload, and render actions MUST remain available.
