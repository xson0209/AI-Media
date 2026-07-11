## ADDED Requirements

### Requirement: Vietnamese TADA evaluation corpus
The system SHALL provide a fixed Vietnamese evaluation corpus for testing TADA 3B speech output before Vietnamese is exposed in normal generation flows.

#### Scenario: Evaluation corpus is available
- **WHEN** a maintainer runs the Vietnamese TADA evaluation workflow
- **THEN** the workflow uses a fixed set of Vietnamese prompts covering short text, long text, tone-sensitive words, diacritics, numbers, acronyms, punctuation, and dialogue-like phrasing

#### Scenario: Evaluation corpus is repeatable
- **WHEN** the evaluation workflow is run more than once with the same reference profile and seed
- **THEN** the generated prompt list and output filenames are stable enough for side-by-side review

### Requirement: Vietnamese output review gate
The system SHALL require an explicit review result before Vietnamese TADA output is exposed as an app option.

#### Scenario: Review has not been accepted
- **WHEN** no accepted review result exists for TADA 3B Vietnamese evaluation
- **THEN** Vietnamese is not offered as a normal TADA generation language in the UI

#### Scenario: Review is rejected
- **WHEN** the Vietnamese TADA evaluation is marked rejected
- **THEN** Vietnamese remains hidden for TADA generation and the rejection reason is recorded for maintainers

#### Scenario: Review is accepted
- **WHEN** the Vietnamese TADA evaluation is marked accepted
- **THEN** Vietnamese can be exposed for TADA 3B as experimental support only

#### Scenario: Local test bypass is explicitly enabled
- **WHEN** a local developer explicitly enables the TADA 3B Vietnamese test bypass
- **THEN** Vietnamese TADA 3B generation is allowed for manual testing before the review gate is accepted
- **AND** the system clearly treats the result as experimental test output, not official supported Vietnamese
- **AND** the bypass MUST NOT enable Vietnamese for TADA 1B or silently fallback to another language

### Requirement: TADA prompt encoding is language-aware
The system SHALL account for the requested language and actual aligner strategy when encoding and caching TADA voice prompts.

#### Scenario: Prompt encoded for a non-default language
- **WHEN** TADA encodes a reference voice prompt for a requested non-English language
- **THEN** the prompt cache key includes the language and aligner strategy so it is not reused for a different language alignment path

#### Scenario: Vietnamese aligner is unavailable
- **WHEN** the Vietnamese evaluation runs without an upstream `aligner-vi`
- **THEN** the system uses a clearly recorded fallback aligner strategy instead of silently claiming native Vietnamese alignment

#### Scenario: Existing engines create prompts
- **WHEN** non-TADA engines create voice prompts
- **THEN** they continue to work without requiring language-specific prompt encoding behavior

### Requirement: Experimental Vietnamese exposure is scoped
The system SHALL expose Vietnamese for TADA only as experimental TADA 3B behavior when the evaluation gate passes.

#### Scenario: User selects TADA 1B
- **WHEN** the selected engine/model is TADA 1B
- **THEN** Vietnamese is not presented as an available language

#### Scenario: User selects TADA 3B after acceptance
- **WHEN** the selected engine/model is TADA 3B and Vietnamese evaluation has been accepted
- **THEN** Vietnamese is presented with experimental or unsupported wording

#### Scenario: API receives Vietnamese TADA request before acceptance
- **WHEN** a generation request asks for TADA Vietnamese before the evaluation gate is accepted
- **THEN** the API rejects or normalizes the request rather than silently treating Vietnamese as officially supported

#### Scenario: API receives Vietnamese TADA request with local test bypass
- **WHEN** a generation request asks for `engine = "tada"`, `model_size = "3B"` and `language = "vi"` while the local test bypass is enabled
- **THEN** the API allows the request so the user can test generated Vietnamese audio directly in the app
- **AND** logs, UI copy, or response metadata SHOULD preserve that this is experimental TADA Vietnamese output

### Requirement: Evaluation artifacts are inspectable
The system SHALL produce inspectable artifacts for each Vietnamese TADA evaluation run.

#### Scenario: Evaluation run completes
- **WHEN** a Vietnamese TADA evaluation run completes
- **THEN** the generated audio files and review metadata identify the engine, model size, language, aligner strategy, corpus version, reference profile, and pass/fail state

#### Scenario: Maintainer compares quality
- **WHEN** a maintainer reviews the evaluation artifacts
- **THEN** the artifacts provide enough context to compare pronunciation, tone quality, naturalness, speaker similarity, and stability across generated samples
