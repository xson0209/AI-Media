## 1. Data Model And Migration

- [x] 1.1 Audit current `video_projects`, `video_scenes`, `video_scene_prompts`, subtitle and package tables to confirm phase 2 migration points.
- [x] 1.2 Add storage for project source blocks with type, order, content, created_at and updated_at.
- [x] 1.3 Add project-level fields or artifact storage for story strategy, continuity bible, story approval and phase 2 planning status.
- [x] 1.4 Add shot storage linked to scene with shot_order, duration, descriptions, narration, shot type, camera metadata, transition note, lock state and stale/status fields.
- [x] 1.5 Add video prompt storage linked to shot with prompt, negative prompt, duration, aspect ratio, motion fields, start/end frame, continuity notes, quality status and version.
- [x] 1.6 Add storage or file-path conventions for local phase 2 debug logs without requiring a remote logging service.
- [x] 1.7 Add migration code in `backend/database/migrations.py` using the existing migration pattern, with no destructive rename/drop of phase 1 prompt tables.
- [x] 1.8 Update ORM exports and database initialization imports for the new phase 2 tables/fields.

## 2. API Models And Types

- [x] 2.1 Add Pydantic request/response models for source blocks, story strategy, continuity bible, video shots and video prompts.
- [x] 2.2 Add models for creating/updating/reordering source blocks.
- [x] 2.3 Add models for generating script development, shot breakdown and video prompt packs.
- [x] 2.4 Add models for locking/unlocking shots and regenerating one shot, one scene or all unlocked shots.
- [x] 2.5 Add readiness models that report missing/invalid video prompts, stale story/shot/prompt state and package blockers.
- [x] 2.6 Add debug/error response models that include friendly Vietnamese message, `request_id`, `step_name`, `error_code` and redacted technical details.
- [x] 2.7 Update frontend API TypeScript types to match backend models.

## 3. AI Planning Pipeline

- [x] 3.1 Define Pydantic schema for `VideoPromptPlan` with all required fields: prompt, negative_prompt, duration_seconds, aspect_ratio, shot_type, camera_angle, framing, composition, camera_motion, subject_motion, environment_motion, start_frame, end_frame, lighting, mood, continuity_notes and quality_check.
- [x] 3.2 Define structured schemas for input synthesis, story strategy, continuity bible, detailed script, scene/shot breakdown and video prompt pack.
- [x] 3.3 Update Codex prompt builder to include all source blocks with labels and user constraints.
- [x] 3.4 Implement story development generation that creates hook, conflict, emotional arc, interesting beats, climax/payoff and detailed script.
- [x] 3.5 Implement continuity bible generation for character, outfit, props, setting, mood, color, camera style and immutable details.
- [x] 3.6 Implement scene-to-shot breakdown with default 1-5 second shots, one primary action or camera angle per shot, visual-only shot support and transition notes.
- [x] 3.7 Ensure scene breakdown varies camera angle, framing, composition and camera movement so no multi-shot scene uses only one static angle.
- [x] 3.8 Implement generic English video prompt generation for each shot, including shot type, camera angle, framing, composition, camera movement, subject motion, environment motion, start/end frame, continuity and negative prompt.
- [x] 3.9 Validate every Codex output before saving and reject invalid JSON or missing required fields with friendly errors and structured logs.
- [x] 3.10 Add regenerate paths that respect locked shots and update only requested unlocked content.
- [x] 3.11 Implement shot variation validation to ensure multi-shot scenes have at least 2 different values among camera_angle, framing, composition or camera_motion.
- [x] 3.12 Add retry logic for Codex calls: max 3 retries per step, 2 second delay between retries, Vietnamese error messages on final failure.

## 4. Backend Services And State

- [x] 4.1 Add source block service functions for list/create/update/delete/reorder.
- [x] 4.2 Add project development service functions for generating and saving story strategy, continuity bible and detailed script.
- [x] 4.3 Add story approval workflow: story_approved field on project, approve/reject endpoints, block shot generation until story approved.
- [x] 4.4 Add shot service functions for creating/replacing shots under scenes, updating shots and locking/unlocking shots.
- [x] 4.5 Add video prompt service functions for creating prompt versions, retrieving copy-ready content and downloading prompt text files.
- [x] 4.6 Update stale-state logic so source, continuity, shot, narration and prompt changes mark dependent prompt, voice, subtitle and package state correctly.
- [x] 4.7 Update package readiness logic to require valid video prompts for required shots and preserve visual-only/no-narration behavior.
- [x] 4.8 Ensure phase 1 project data remains readable and voice/profile/generation flows remain unchanged.

## 5. API Routes

- [x] 5.1 Add routes for source block CRUD and reorder under `/ai-video/projects/{project_id}`.
- [x] 5.2 Add route to generate or regenerate story development artifacts for a project.
- [x] 5.3 Add approve/reject story routes and return Vietnamese blockers when shot generation is requested before approval.
- [x] 5.4 Add route to generate scene/shot breakdown from the approved developed script.
- [x] 5.5 Add routes to update, lock, unlock and regenerate shots.
- [x] 5.6 Add route to generate video prompt pack for approved/unlocked shots.
- [x] 5.7 Add routes to copy/download prompt video for a shot and download all prompt video text.
- [x] 5.8 Update debug/status endpoints to include source blocks, continuity state, shot readiness, video prompt status, latest errors and `request_id`.
- [x] 5.9 Return Vietnamese friendly errors with request IDs for planning, validation, prompt quality, voice/subtitle and package blockers.

## 6. Frontend Workflow And UI Quality

- [x] 6.1 Verify frontend dependencies before UI work: Tailwind v4, `framer-motion`, current icon package and whether `@phosphor-icons/react` or `@radix-ui/react-icons` must be added before import.
- [x] 6.2 Replace the single-topic form with a Vietnamese source-content editor supporting idea, outline, rough script, character notes, style notes, audience, must-have and avoid blocks.
- [x] 6.3 Add project setup controls for target language, aspect ratio, target duration and default shot duration.
- [x] 6.4 Add review screen for story strategy, continuity bible and detailed script before shot generation.
- [x] 6.5 Add scene/shot editor that shows Vietnamese description, English narration, shot type, duration, transition and lock state.
- [x] 6.6 Replace prompt image UI with prompt video UI: copy prompt video, copy negative prompt, download prompt, regenerate prompt and quality checklist.
- [x] 6.7 Add controls to regenerate one shot, regenerate one scene and regenerate all unlocked shots.
- [x] 6.8 Ensure locked shots are visually clear and cannot be overwritten by batch regenerate without unlocking.
- [x] 6.9 Keep UI Vietnamese and non-technical while showing English narration/prompt as copy-ready output.
- [x] 6.10 Apply `design-taste-frontend-v1` baseline: DESIGN_VARIANCE 8, MOTION_INTENSITY 6, VISUAL_DENSITY 4, workflow-first screen, no marketing hero.
- [x] 6.11 Add loading skeletons, empty states and inline error states for source analysis, story development, shot generation, prompt video generation, voice/subtitle and export.
- [x] 6.12 Structure forms with label above input, helper text below, inline validation below input and stable spacing between fields.
- [x] 6.13 Avoid emoji, neon/glow, AI-purple/blue palette, excessive gradients, generic three-card feature rows and nested cards.
- [x] 6.14 Ensure motion uses transform/opacity only, heavy or perpetual animations are isolated in small components, and active states provide tactile feedback.
- [x] 6.15 Validate mobile layout at 375px and 768px: one-column collapse, no fixed sidebar, no horizontal scroll, no text overlap and no `h-screen` traps.
- [x] 6.16 Add a hidden-by-default local debug panel with copy buttons for `request_id`, step, friendly message, error code and redacted technical details.
- [x] 6.17 Review all visible UI copy for Vietnamese clarity and ease of use by non-technical users.

## 7. Local Logging And Debug

- [x] 7.1 Add a structured logging helper/context for phase 2 pipeline actions with `request_id`, project/scene/shot IDs, `step_name`, status, duration and retry count.
- [x] 7.2 Log start/success/warning/failure events for source synthesis, story development, continuity generation, shot breakdown, prompt generation, voice generation, subtitle generation and package export.
- [x] 7.3 Include provider/model, error_code, exception class, technical message and validation errors when a step fails.
- [x] 7.4 Redact API keys, bearer tokens, environment secrets, full uploaded binary/audio data, unnecessary absolute paths and long user text before writing logs or returning debug details.
- [x] 7.5 Ensure every final user-facing error response includes a stable `request_id` and Vietnamese friendly message.
- [x] 7.6 Add debug/status service logic to fetch latest phase 2 errors and artifact states for a project.
- [x] 7.7 Add copy-ready debug payload formatting for the UI so the user can report local failures without manually finding log files.

## 8. Export Package

- [x] 8.1 Update prompt package generation to write `Prompt video` files instead of `Prompt ảnh` for phase 2 projects.
- [x] 8.2 Add `Kịch bản`, `Mô tả tiếng Việt`, `Continuity bible` and `Shot list` files to the ZIP.
- [x] 8.3 Include prompt video files ordered by scene and shot with Vietnamese-friendly filenames.
- [x] 8.4 Preserve voice, subtitle and manifest export behavior, extended with shot metadata.
- [x] 8.5 Block ZIP export with a Vietnamese checklist when required shots have missing or low-quality video prompts.
- [x] 8.6 Confirm preview images remain optional and do not block phase 2 package export.
- [x] 8.7 Log export blockers and successful ZIP creation with `request_id`, package path metadata and redacted file details.

## 9. Tests And Verification

- [x] 9.1 Add backend tests for source block CRUD and reorder behavior.
- [x] 9.2 Add backend tests for story development schema validation and invalid Codex output handling.
- [x] 9.3 Add backend tests for continuity bible and shot breakdown persistence.
- [x] 9.4 Add backend tests that verify multi-shot scenes vary camera angle, framing, composition or camera movement.
- [x] 9.5 Add backend tests for locked shot regenerate behavior.
- [x] 9.6 Add backend tests for video prompt quality readiness and missing-field blockers.
- [x] 9.7 Add backend tests for stale state when source, continuity, shot, narration or prompt changes.
- [x] 9.8 Add backend tests for structured logging, redaction and debug/status error responses.
- [x] 9.9 Add backend tests for phase 2 ZIP contents and filenames.
- [x] 9.10 Add frontend tests or focused manual QA for source editor, story review, shot editor, prompt copy/download, debug panel and package readiness.
- [x] 9.11 Run focused visual QA for the phase 2 UI at desktop, 768px and 375px viewports.
- [x] 9.12 Run relevant backend and frontend test commands and record any skipped checks with reasons.

## 10. Documentation And Review

- [x] 10.1 Update AI Video Assistant docs to explain phase 2 source input, story development, continuity and prompt video workflow.
- [x] 10.2 Add user-facing examples showing Vietnamese input, English narration and English video prompt output.
- [x] 10.3 Update any PDF/user guide references from prompt ảnh to prompt video where applicable.
- [x] 10.4 Document where local logs/debug info can be viewed and what `request_id` means.
- [x] 10.5 Review all new UI copy for Vietnamese clarity and non-technical wording.
- [x] 10.6 Run `openspec status --change mo-rong-ai-video-kich-ban-va-prompt-video` and verify all tasks/spec artifacts remain valid before implementation starts.
