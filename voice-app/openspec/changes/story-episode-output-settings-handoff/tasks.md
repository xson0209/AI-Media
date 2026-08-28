## 1. Backend Contract

- [x] 1.1 Add `output_settings_json` to StoryEpisode model and idempotent migration.
- [x] 1.2 Add Pydantic request/response models for normalized Story Episode output settings.
- [x] 1.3 Normalize defaults for old and new episodes.

## 2. Image Story Settings

- [x] 2.1 Generate image panel prompts from manual panel count when provided.
- [x] 2.2 In auto mode, use linked AI Video shot micro-scenes when available.
- [x] 2.3 Persist image size/aspect settings in adaptation payload and panel prompts.
- [x] 2.4 Keep image prompt approval/render gates unchanged.

## 3. Video Handoff Settings

- [x] 3.1 Pass video aspect ratio, language, dialogue mode, narration density and segment settings to linked AI Video project.
- [x] 3.2 Mark handoff payload as `handoff_only` and do not auto-run downstream AI Video generation.
- [x] 3.3 Include settings source in handoff payload for debugging.

## 4. Frontend

- [x] 4.1 Add Story Studio episode form controls for image count/size and video handoff settings.
- [x] 4.2 Show selected settings on episode summary.
- [x] 4.3 Keep controls compact and usable in the existing Story Studio layout.

## 5. Verification

- [x] 5.1 Add backend regression tests for manual image count and video handoff settings.
- [x] 5.2 Run Story Studio targeted tests.
- [x] 5.3 Run frontend typecheck or equivalent targeted check.
- [x] 5.4 Run OpenSpec validation.
