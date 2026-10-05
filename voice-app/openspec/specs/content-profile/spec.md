# content-profile Specification

## Purpose
Define the structured semantic contract that tells AI Video what a project is for, who it targets, how it will be distributed and which safety rules apply, while preserving the legacy `video_purpose` field.
## Requirements
### Requirement: Structured content profile
The system SHALL store and return a versioned Content Profile for every AI Video project, separating content objective, genre, audience age band, format profile, primary distribution platform, interaction mode, safety policy, made-for-kids status and optional learning objective.

#### Scenario: Create a project with an explicit profile
- **WHEN** a client creates an AI Video project with valid Content Profile fields
- **THEN** the system persists and returns the resolved fields without combining them into `video_purpose`

#### Scenario: Reject unsupported profile values
- **WHEN** a client submits an unsupported objective, genre, age band, format, platform, interaction or safety value
- **THEN** the API rejects the request with validation details

### Requirement: Legacy purpose compatibility
The system MUST preserve the existing `video_purpose` contract and SHALL deterministically resolve missing Content Profile fields from legacy purpose and duration values.

#### Scenario: Load a legacy educational project
- **WHEN** an existing project has `video_purpose=educational_explainer` and no explicitly saved genre
- **THEN** the resolved profile uses an education objective and educational-explainer genre while retaining the original purpose

#### Scenario: Create through an existing client
- **WHEN** a client creates a project without any Content Profile fields
- **THEN** the project is accepted and receives a valid version-one profile derived from the existing request

### Requirement: Safe Kids invariants
The system MUST resolve every Kids genre to made-for-kids content with the strict Kids safety policy and a child-compatible age band.

#### Scenario: Contradictory Kids request
- **WHEN** a client selects a Kids genre while submitting `made_for_kids=false`, an adult age band or a non-Kids safety policy
- **THEN** the stored profile is normalized to safe Kids values

### Requirement: Profile updates invalidate dependent output
The system SHALL mark generated content and publishing output stale when a Content Profile change can alter the story, audience contract or safety rules.

#### Scenario: Change genre after planning
- **WHEN** a user changes an existing project's genre after story development
- **THEN** story approval is cleared and dependent generated artifacts are marked stale through the existing invalidation workflow

### Requirement: Discoverable profile options
The system SHALL expose a read-only API that returns supported profile values and genre-template metadata for clients.

#### Scenario: Load profile editor options
- **WHEN** a client requests Content Profile options
- **THEN** the API returns the schema version, enum options and genre templates with labels and defaults
