## ADDED Requirements

### Requirement: Explicit stick-figure requests use non-anatomical character constraints

The video prompt pipeline MUST recognize an explicit stick-figure request and constrain the character as a true non-anatomical stick figure.

#### Scenario: Stick-figure style is requested

- **WHEN** the project's topic, title, visual style, continuity bible, or style bible contains an explicit stick-figure term
- **THEN** story, shot, and video-prompt generation MUST receive a strict stick-figure anatomy instruction
- **AND** the instruction MUST require a simple round head, thin torso, uniform rod-like limbs, and simple joints
- **AND** the instruction MUST prohibit human hands, feet, fingers, toes, muscles, skin, detailed facial anatomy, and human body proportions

#### Scenario: 3D rendering is used for a stick figure

- **WHEN** a stick-figure project uses a 3D visual style
- **THEN** 3D depth, shading, materials, volumetric lighting, parallax, and camera movement MAY be used
- **AND** those rendering techniques MUST NOT change the character into an anatomically human or humanoid body

#### Scenario: Normalized prompt is copied to a provider

- **WHEN** a stick-figure project's video prompt payload is normalized
- **THEN** every prompt item MUST contain the positive stick-figure anatomy lock
- **AND** every negative prompt MUST block human hands, feet, fingers, toes, muscles, realistic proportions, and related anatomy

#### Scenario: No stick-figure request

- **WHEN** a project contains no explicit stick-figure request
- **THEN** the pipeline MUST NOT add stick-figure-specific anatomy constraints
- **AND** existing content-profile, Kids, and visual-style behavior MUST remain unchanged

### Requirement: Stick-figure mode is discoverable

The AI Video project form SHALL provide a one-click strict stick-figure preset through the existing visual-style control.

#### Scenario: User chooses the strict preset

- **WHEN** the user activates `Dùng preset người que chuẩn`
- **THEN** the visual-style field SHALL contain an editable definition of a non-anatomical stick figure
- **AND** saving the project SHALL use the existing `visual_style` API field without a new database or API contract
