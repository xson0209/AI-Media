## 1. Data Model And API

- [x] 1.1 Add nullable migration columns for `video_projects.prompt_segment_count`, `video_projects.prompt_segment_duration_seconds`, `video_projects.micro_scenes_per_prompt`, and `video_shots.micro_scenes_json`.
- [x] 1.2 Update database models to include the new project configuration fields and shot micro-scene JSON storage.
- [x] 1.3 Update backend request/response models to expose `prompt_segment_count`, `prompt_segment_duration_seconds`, `micro_scenes_per_prompt`, and structured shot `micro_scenes`.
- [x] 1.4 Update project create/update service logic to validate the new fields, derive `target_duration_seconds`, and keep legacy behavior when the fields are absent.
- [x] 1.5 Mark dependent segment/prompt/voice/subtitle/package artifacts stale or require regenerate confirmation when prompt segment configuration changes after artifacts exist.
- [x] 1.6 Update frontend API types to match the new backend project and shot response fields.

## 2. Segment Configuration Helpers

- [x] 2.1 Add a shared backend helper that resolves prompt segment config from a project, returning count, prompt duration, micro-scenes per prompt, derived total duration, and whether the project is legacy mode.
- [x] 2.2 Add a shared helper to generate timeline ranges from `prompt_segment_duration_seconds` and `micro_scenes_per_prompt` without hardcoded 10-second examples.
- [x] 2.3 Replace direct `VIDEO_PROMPT_SEGMENT_SECONDS` usage in segment count, usable duration, timeline labels, narration word range, shot duration preference, and prompt generation with the resolved project config.
- [x] 2.4 Keep `VIDEO_PROMPT_SEGMENT_SECONDS = 10` only as the legacy/default fallback for projects without explicit prompt segment configuration.

## 3. Codex Output Schema And Normalization

- [x] 3.1 Extend shot breakdown schema/model to request and accept structured `micro_scenes` for each prompt segment.
- [x] 3.2 Update Codex shot breakdown instructions to require exactly `prompt_segment_count` segments and exactly `micro_scenes_per_prompt` micro-scenes per segment.
- [x] 3.3 Normalize segment list aliases including `shots`, `segments`, `prompt_segments`, `video_segments`, and `segment_breakdown` before validation.
- [x] 3.4 Normalize nested outputs such as `scenes[].segments`, `scenes[].shots`, and `scenes[].prompt_segments` into the flat prompt segment list expected by persistence.
- [x] 3.5 Normalize micro-scene aliases including `micro_scenes`, `microScenes`, `scenes`, `beats`, `timeline`, and `timeline_beats` into one structured list.
- [x] 3.6 Parse time-coded text such as `0-3s`, `3-6s`, and `6-10s` into structured micro-scenes when Codex returns timeline text instead of an array.
- [x] 3.7 Generate evenly spaced micro-scene ranges from segment-level visual/action/camera text when Codex returns enough segment content but no usable micro-scene shape.
- [x] 3.8 Validate exact segment count and exact micro-scene count after normalization, with friendly Vietnamese errors only when required content is truly missing.
- [x] 3.9 Persist normalized micro-scenes on `video_shots` and include them in shot responses, prompt generation, and package/export data.

## 4. Prompt Generation And Export

- [x] 4.1 Update video prompt generation to include the configured prompt duration and all structured micro-scene timeline ranges in the copyable prompt.
- [x] 4.2 Update Vietnamese review text generation/fallback so each segment description mentions every configured micro-scene and its time range.
- [x] 4.3 Update package manifest, prompt text download, and shot list export to include configured prompt duration and micro-scene timeline data.
- [x] 4.4 Update readiness checks so project/package state uses configured prompt segment fields for new projects and legacy fallback for old projects.

## 5. Frontend Workflow

- [x] 5.1 Replace the editable target duration input in AI Video Assistant phase 2 with inputs for prompt count, prompt duration, and micro-scenes per prompt.
- [x] 5.2 Add UI validation and helper text for allowed ranges, recommended defaults, and too-dense micro-scene timing.
- [x] 5.3 Show derived preview values for total duration and total micro-scene count before project creation.
- [x] 5.4 Send the new prompt segment configuration fields when creating a phase 2 project.
- [x] 5.5 Display configured prompt duration and structured micro-scenes in each prompt segment card.
- [x] 5.6 Preserve legacy project display so old prompt segments still render without requiring the new fields.

## 6. Tests And Verification

- [x] 6.1 Add backend migration/model tests for the new project fields and `micro_scenes_json` storage.
- [x] 6.2 Add backend tests for `6 prompt x 10s x 3 cảnh nhỏ`, asserting 60 seconds total, 6 segments, and 18 structured micro-scenes.
- [x] 6.3 Add backend tests for a non-10-second prompt duration such as `4 prompt x 8s x 4 cảnh nhỏ`, asserting generated timeline ranges cover each 8-second prompt.
- [x] 6.4 Add backend tests proving Codex outputs using alias fields and nested `scenes[].segments` normalize successfully without validation failure.
- [x] 6.5 Add backend tests proving time-coded text timelines and missing-array-but-complete-content outputs normalize into structured micro-scenes.
- [x] 6.6 Add backend tests for incomplete Codex output to ensure the system fails with a friendly Vietnamese error instead of persisting invalid segment data.
- [x] 6.7 Add backend tests confirming old projects with only `target_duration_seconds` still use the legacy 10-second prompt segment behavior.
- [x] 6.8 Run relevant backend tests and frontend type/build checks for AI Video Assistant changes.
