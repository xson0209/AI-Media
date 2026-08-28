## 1. Persistence and bridge model

- [x] 1.1 Add nullable `render_project_id` to `ProductVideoProject` and expose it in Product Video response types.
- [x] 1.2 Extend Product Video migration to add the column/index idempotently on existing databases.
- [x] 1.3 Add bridge synchronization helpers that create/update a phase-2 `VideoProject` from Product Video configuration.
- [x] 1.4 Add idempotent Product Video shot → `VideoShot` synchronization with motion, narration, duration, transition, sound, and retention metadata.
- [x] 1.5 Add Product Video prompt → `VideoShotPrompt` synchronization and stale-output marking.
- [x] 1.6 Delete bridge project/artifacts safely when Product Video project is deleted.

## 2. Backend API

- [x] 2.1 Include `render_project_id` and render-compatible shots in Product Video project detail response.
- [x] 2.2 Ensure create/update/plan/prompt routes synchronize bridge state and return clear bridge-sync errors.
- [x] 2.3 Add route/service tests for upload readiness via the bridge, re-planning, prompt isolation, and deletion.

## 3. Frontend parity

- [x] 3.1 Add Product Video API types/client support for render bridge metadata.
- [x] 3.2 Embed the shared `AIVideoRenderPanel` below the Product Video prompt pack when a bridge is ready.
- [x] 3.3 Wire render notices, query invalidation, loading/error states, and project switching.
- [x] 3.4 Verify resolution, FPS, fit mode, subtitles, audio, watermark cleanup, enhanced render, SFX/BGM, batch upload, per-shot re-upload, preview, delete, render, and downloads.
- [x] 3.5 Add the AI Video-like creation configuration controls with Product Video-safe quick/manual semantics.

## 4. Verification

- [x] 4.1 Run Product Video backend tests and new bridge tests.
- [x] 4.2 Run existing AI Video backend/render regression tests.
- [x] 4.3 Run frontend build, typecheck, targeted Product Video lint, and browser flow at `/product-video`.
- [ ] 4.4 Manually upload/re-upload clips, render an MP4, download the MP4 and reports, and confirm Product Video still does not enqueue provider generation/TTS automatically.
- [x] 4.5 Verify Product Video quick/manual, review/full-auto, and each output target without enqueueing provider, TTS, Chrome, subtitle, or render jobs.
