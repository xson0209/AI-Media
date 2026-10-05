## ADDED Requirements

### Requirement: Registry-driven genre templates
The system SHALL define genre templates in one backend registry, with each template providing a label, description, default Content Profile fields, generation guidance and review checks.

#### Scenario: Resolve a known template
- **WHEN** the content genre matches a registered template
- **THEN** the resolver applies template defaults only to profile fields that the client did not explicitly supply

#### Scenario: Resolve a general project
- **WHEN** a project has no specialized genre
- **THEN** the general template produces a valid profile without imposing Kids-specific structure

### Requirement: Kids and Family template set
The initial registry MUST include Kids educational, rescue/problem-solving, STEM/garage and song/movement templates.

#### Scenario: List initial Kids templates
- **WHEN** a client loads the Content Profile registry
- **THEN** all four Kids templates are available with distinct descriptions and defaults

### Requirement: Kids narrative guidance
Kids templates SHALL add testable story-development guidance covering a fast mission hook, one participation cue, no more than two solution steps, a clear result/emotional payoff and a short takeaway or musical close.

#### Scenario: Generate a two-minute Kids rescue story
- **WHEN** story development runs for a project using the Kids rescue template and two-minute format
- **THEN** the AI planning context includes the Kids beat structure, participation behavior and safety constraints

### Requirement: Kids content quality checks
Kids templates MUST provide review checks for age-appropriate language, imitable-action safety, positive resolution, character consistency and a memorable takeaway.

#### Scenario: Inspect template metadata
- **WHEN** a client or generation service reads a Kids template
- **THEN** the returned metadata contains the genre-specific review checks used to guide review and future quality gates

