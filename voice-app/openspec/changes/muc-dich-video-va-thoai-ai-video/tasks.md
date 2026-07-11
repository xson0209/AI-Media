## 1. Data Contract And Presets

- [x] 1.1 Define supported AI Video purposes and labels: `vietnam_market`, `global_short`, `educational_explainer`, `sales_ad`, `localized_variant`, plus any `custom` fallback if needed.
- [x] 1.2 Define a shared preset map for recommended `target_language`, dialogue mode, narration density, subtitle expectation, tone guidance and optional CTA guidance.
- [x] 1.3 Add persistence for selected purpose and dialogue settings on AI Video project with safe defaults for existing projects.
- [x] 1.4 Add idempotent SQLite migration/backfill for new project fields without changing existing `target_language` values.
- [x] 1.5 Update Pydantic/API types and frontend API types for purpose, dialogue mode and narration density.
- [x] 1.6 Define canonical alias maps for purpose, dialogue mode, narration density, CTA style and narration text returned by Codex.

## 2. Backend Project Workflow

- [x] 2.1 Accept purpose/dialogue settings in create project, update project and create series episode requests.
- [x] 2.2 Resolve purpose presets without silently overriding `target_language` when API update omits language.
- [x] 2.3 Add stale handling when purpose, dialogue mode or narration density changes after story/shot/voice/subtitle/package artifacts exist.
- [x] 2.4 Include purpose and dialogue settings in project response, package manifest and debug/observability payloads.
- [x] 2.5 Ensure project duplication/localize workflow can copy sources/config while assigning a new `target_language` and purpose snapshot.

## 3. AI Planning And Dialogue Generation

- [x] 3.1 Add purpose, target language, dialogue mode and narration density to phase 2 project context builder.
- [x] 3.2 Update story development prompts so educational videos ask for clear explanatory thoại/narration and sales videos ask for hook, benefit and CTA.
- [x] 3.3 Update shot breakdown prompts so `voiceover`, `character_lines` and `mixed` modes produce the expected `scene.dialogue` or `shot.english_narration` text.
- [x] 3.4 Keep `english_narration` as compatibility field while documenting that it stores narration/voice text in the selected video language.
- [x] 3.5 Add prompt safeguards so purpose guidance cannot contradict `target_language` for viewer-facing speech, subtitle or on-screen text.
- [x] 3.6 Add a shared normalized Codex outbound context helper for phase 2 story, shot and video prompt generation.
- [x] 3.7 Normalize outbound source blocks by sort order, block type, trimmed content and safe handling of empty blocks before building Codex prompts.
- [x] 3.8 Normalize outbound series context and prompt segment config through the shared Codex context helper instead of rebuilding those values differently per prompt.
- [x] 3.9 Extend inbound Codex normalization to map purpose/dialogue/narration aliases to canonical fields before Pydantic validation.
- [x] 3.10 Reject conflicting inbound Codex aliases for purpose, dialogue mode, narration density and narration text with clear mapping errors.
- [x] 3.11 Preserve raw field type, normalized field type and validation error logging for every purpose/dialogue Codex validation failure.

## 4. Voice, Subtitle And Package Behavior

- [x] 4.1 Reuse existing voice language resolution so generated voice uses `target_language` unless request explicitly overrides language.
- [x] 4.2 Surface backend validation errors when selected voice profile, engine or model cannot produce the project language.
- [x] 4.3 Ensure subtitle generation uses the generated thoại/narration text and is stale when dialogue settings change.
- [x] 4.4 Ensure package readiness and manifest expose one video language plus the selected purpose/dialogue settings.
- [x] 4.5 Verify localize/duplicate projects keep artifact sets separate and never export mixed-language voice/subtitle artifacts in one package.

## 5. Frontend UX

- [x] 5.1 Add `Mục đích video` selector to AI Video setup with concise Vietnamese descriptions for each purpose.
- [x] 5.2 Show a preview of what the selected purpose will influence: suggested language, voice compatibility, thoại/narration density, subtitle and script tone.
- [x] 5.3 Allow users to override `Ngôn ngữ video` after choosing purpose, while clearly showing `target_language` remains the final output language.
- [x] 5.4 Add dialogue mode and narration density controls or advanced settings when the selected purpose needs them.
- [x] 5.5 Warn early when the selected voice profile/engine appears incompatible with the chosen `target_language`.
- [x] 5.6 Add localize/duplicate action copy for creating a separate English or Vietnamese version from an existing project.

## 6. Tests And Verification

- [x] 6.1 Add backend tests for create/update project with each purpose and target-language override behavior.
- [x] 6.2 Add backend tests that changing purpose/dialogue settings stales story, shot narration, voice, subtitle and package artifacts when appropriate.
- [x] 6.3 Add backend tests that AI planning prompts include purpose, dialogue mode, narration density and correct viewer-facing language instructions.
- [x] 6.4 Add backend tests for normalized outbound Codex context, including source block ordering, target-language override and series context truncation behavior.
- [x] 6.5 Add backend tests for inbound Codex alias normalization for purpose, dialogue mode, narration density, CTA style and narration text.
- [x] 6.6 Add backend tests for inbound Codex alias conflicts and verify failed mapping does not overwrite existing artifacts.
- [x] 6.7 Add backend tests for voice compatibility errors and no silent fallback from Vietnamese to English.
- [x] 6.8 Add backend tests for localized duplicate projects and one-language package manifest/export behavior.
- [x] 6.9 Add frontend type/build checks and component tests or focused manual QA for purpose selector, preview, override and voice warning states.
- [x] 6.10 Run focused AI Video backend tests plus frontend build/typecheck before marking implementation complete.

## 7. Documentation

- [x] 7.1 Update AI Video documentation to explain `Mục đích video`, `Ngôn ngữ video`, thoại/narration and localize/duplicate workflow.
- [x] 7.2 Add examples for a Vietnamese market video, a global English short, an educational explainer and a sales/ad video.
