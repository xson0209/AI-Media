## 1. Contract and persistence

- [x] 1.1 Add canonical `CTA_ACTION_VALUES`, pattern, aliases, and normalization helper.
- [x] 1.2 Add nullable `cta_action` to the AI Video project model and idempotent SQLite migration.
- [x] 1.3 Add `cta_action` to create/update/episode/handoff request and response models and frontend API types.
- [x] 1.4 Include `cta_action` in project purpose settings, stale fingerprints, and publishing metadata dependencies.

## 2. Context-aware planning

- [x] 2.1 Add `cta_action` to story, shot-breakdown, and prompt-pack planning schemas and normalized context.
- [x] 2.2 Update story/shot/prompt instructions to derive CTA delivery from the approved final beat and preserve continuity.
- [x] 2.3 Add a final-shot CTA quality validator with one-action, contextual visual, speech-cue, final-hold, and no-UI-text checks.
- [x] 2.4 Ensure fallback prompts use contextual voiceover/visual delivery and never invent a generic gesture or platform button.

## 3. Frontend

- [x] 3.1 Add a Vietnamese “Hành động CTA” selector next to the existing CTA tone selector.
- [x] 3.2 Load/save the selector without changing existing projects or purpose presets unexpectedly.
- [x] 3.3 Show the selected action in project summaries and generated prompt review where available.

## 4. Verification

- [x] 4.1 Add backend tests for normalization, persistence payloads, context instructions, and final-shot validation.
- [x] 4.2 Add regression tests proving legacy projects and `cta_action=none` remain valid.
- [x] 4.3 Run backend compile checks and frontend typecheck; pytest is unavailable in the environment.
