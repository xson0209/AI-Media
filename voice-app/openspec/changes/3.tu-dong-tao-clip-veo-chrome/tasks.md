## Status Note

Updated on 2026-07-12 after inspecting the current implementation. This change is no longer a greenfield plan: the core Veo/Chrome workflow already exists in the backend, API client, and AI Video UI. Remaining unchecked tasks are hardening, missing tests, visual/manual QA, documentation, and a few behavior gaps found during the sync.

## 1. Schema, Storage And Dependency Decision

- [x] 1.1 Choose the MVP automation path: direct Chrome DevTools Protocol against installed Chrome, not Playwright.
- [x] 1.2 Confirm no new browser dependency is required for the current CDP implementation, so no Chromium download/package change is needed.
- [x] 1.3 Add ORM model `VideoProviderSession` with provider, status, Chrome profile path, masked account hint, last checked, failure reason, identity fields, and timestamps.
- [x] 1.4 Add ORM model `VideoClipGenerationJob` with project id, provider, session id, status, current step, progress, force, auto render, render job id, download dir, credit policy, failure reason, error code, step results JSON, and timestamps.
- [x] 1.5 Add ORM model `VideoClipGenerationItem` with job id, project id, shot id, prompt id, status, attempt count, provider metadata fields, downloaded path, clip id, failure reason, and timestamps.
- [x] 1.6 Add idempotent migration and indexes for provider sessions, clip generation jobs, and clip generation items.
- [x] 1.7 Add provider storage helpers for the dedicated Chrome profile and per-project/job/item download directories.
- [x] 1.8 Keep Chrome profile/session cookies and provider download roots outside project package/debug payloads by design; debug response returns only redacted session/job metadata.
- [ ] 1.9 Add automatic cleanup for per-job provider download directories after terminal jobs where it is safe to do so; project delete cleanup already exists.

## 2. Browser Session Manager

- [x] 2.1 Implement Chrome executable detection on macOS/Windows/Linux with env-var override when auto-detect fails.
- [x] 2.2 Launch real Chrome with the dedicated Voicebox profile, configurable Flow URL, remote debugging, and provider download directory.
- [x] 2.3 Add API/service to open Chrome for manual Veo login and create/reuse the default provider session record.
- [x] 2.4 Add session check flow that detects ready, login/verification, application error, Chrome missing, and profile lock states.
- [x] 2.5 Guard one active Chrome runtime per provider and detect existing/locked profile usage.
- [x] 2.6 Redact account hint, URL-derived hashes, and technical details; do not read or store cookie/token/local storage in DB.
- [x] 2.7 Add invalidate/change-account/reconnect path for login changes, provider errors, and user-initiated account switching.

## 3. Veo Provider Adapter

- [x] 3.1 Implement the MVP provider adapter boundary as `video_veo_chrome.submit_prompt_and_download`; no multi-provider registry exists yet.
- [x] 3.2 Implement the Veo/Flow Chrome adapter in one module with selector/URL heuristics isolated from the job orchestrator.
- [x] 3.3 Submit one shot prompt using the latest completed/passed video prompt and avoid logging the full prompt.
- [x] 3.4 Wait for generation with bounded timeout, polling, and Vietnamese status callbacks for the UI.
- [x] 3.5 Detect provider errors for login/session, quota/billing/policy, public-figure policy, UI changed, app error, generation failed, and download unavailable.
- [x] 3.6 Capture downloads into the item-specific folder rather than the user's default Downloads folder.
- [x] 3.7 Check download completion by ignoring temp suffixes, requiring a stable file size, validating supported video extensions, and timing out clearly.
- [x] 3.8 Return redacted adapter result metadata including provider project hash, download hash/correlation id, filename, duration when available, and credit cost.

## 4. Clip Generation Orchestrator

- [x] 4.1 Create clip generation jobs from phase 2 projects after validating session readiness, shots, and completed/passed prompts.
- [x] 4.2 Guard active jobs on the same project/provider and also block conflicting series, auto-run, planning, and render work.
- [x] 4.3 Select runnable items by skipping existing valid provider clips when not forced and resetting failed/needs-action items for retry/resume.
- [x] 4.4 Implement item states: pending, opening provider, submitting prompt, resolving followup, credit policy check, approving credit, waiting generation, downloading, importing, completed, skipped, needs login/user action/credit, failed, and cancelled.
- [x] 4.5 Run items sequentially in the background to avoid provider account/session conflicts.
- [x] 4.6 Import provider clips through the shared render clip import helper, create `video_shot_clips` with `source = "provider"`, deactivate old active clips, and mark render outputs stale.
- [x] 4.7 Map provider/session/import failures to Vietnamese error states and retryable job statuses.
- [ ] 4.8 Harden cancel so it interrupts an already-running CDP wait/download promptly, not only before the next item boundary.
- [x] 4.9 Resume after `needs_login`, `needs_user_action`, `needs_credit_approval`, or failed states without recreating completed items unless force is enabled.
- [x] 4.10 Sync stale `queued` and `running` jobs on backend startup to failed with a Vietnamese interruption message.
- [x] 4.11 Handoff to existing render readiness/render job service when all clips are ready and auto-render is enabled.
- [x] 4.12 Return `completed_with_render_blocked` and missing render reasons when clips are ready but render prerequisites are missing.
- [ ] 4.13 Add explicit stale invalidation coverage when prompt/shot data changes after provider clips already exist.

## 5. API Backend And Types

- [x] 5.1 Add Pydantic models for provider session, session open/check/update, clip generation job/item/summary, start/retry/resume/cancel, and credit approval.
- [x] 5.2 Add routes for default Veo session, open login, check session, update label, confirm identity, invalidate, and change account.
- [x] 5.3 Add routes to start/list latest/get clip generation jobs by project.
- [x] 5.4 Add routes for retry, resume, cancel, and credit approval with AI Video error handling.
- [x] 5.5 Add frontend API client methods and TypeScript types for provider session, job, item, retry/resume/cancel, credit, and render handoff.
- [x] 5.6 Add redacted AI Video debug output for provider session and latest clip generation job without returning raw Chrome profile paths, cookies, tokens, DOM, or full prompt text.
- [x] 5.7 Block unsafe project operations when auto-run, planning, render, or Veo job state could race with clip generation.

## 6. Frontend AI Video UI

- [x] 6.1 Add `AIVideoVeoChromePanel` instead of expanding `AIVideoAssistant.tsx` further.
- [x] 6.2 Add the Veo/Chrome session status panel for not configured, needs login, checking, ready, mismatch, invalid, and error states.
- [x] 6.3 Add actions to open Chrome/login, check session, change account, edit label, and confirm identity in Vietnamese.
- [x] 6.4 Add shot list with prompt, active clip, and provider item statuses.
- [x] 6.5 Add start form with `force`, auto-render, credit policy, max credit, and disabled states for missing session/prompt/active job.
- [x] 6.6 Add job/item progress copy using Vietnamese labels rather than requiring raw status knowledge.
- [x] 6.7 Add retry, resume, cancel, and credit approval actions while preserving manual upload/render fallback panels.
- [x] 6.8 Route `needs_login` and `needs_user_action` states to open the same Chrome profile and then resume once the backend session is ready.
- [x] 6.9 Invalidate render/debug queries after auto-render handoff.
- [ ] 6.10 Run visual responsive QA for the Veo panel on desktop/mobile and fix any text overlap or cramped controls.

## 7. Backend Tests

- [ ] 7.1 Test migration creates provider session/job/item tables and indexes.
- [ ] 7.2 Test session manager does not store cookies/tokens and uses a dedicated profile path.
- [ ] 7.3 Test session check transitions for ready, needs login, Chrome missing, and profile lock.
- [ ] 7.4 Test start job success plus project missing, missing prompt, session not ready, and active job conflict.
- [ ] 7.5 Test item selection skips valid provider clips and force regenerates.
- [ ] 7.6 Test download watcher accepts completed video files, ignores `.crdownload`, times out, and rejects invalid files.
- [ ] 7.7 Test provider clip import creates `video_shot_clips` with correct source/provider/metadata and deactivates old active clips.
- [ ] 7.8 Test retry/resume/cancel preserves completed clips and does not rerun completed items unexpectedly.
- [ ] 7.9 Test startup sync for stale active jobs.
- [ ] 7.10 Test auto-render starts render when readiness passes and marks render blocked when readiness fails.
- [ ] 7.11 Test debug redaction excludes full prompt, cookie, token, DOM, credential, and Chrome profile path.

## 8. Frontend Tests And Type Checks

- [x] 8.1 TypeScript API types and client methods for the Veo panel exist.
- [x] 8.2 Add targeted static verification for session panel states.
- [x] 8.3 Add targeted static verification for job progress states.
- [x] 8.4 Add targeted static verification for retry/cancel/resume, credit approval, and auto-render invalidation hooks.
- [x] 8.5 Run app typecheck for the AI Video UI.
- [ ] 8.6 Add browser or component-level interaction tests beyond static text/type verification.

## 9. Manual QA And Documentation

- [ ] 9.1 Manual QA first login: open dedicated Chrome profile, log into the intended Google/Veo account, and check session ready.
- [ ] 9.2 Manual QA one shot: submit prompt to Veo, download clip, import to the correct shot, and see render readiness update.
- [ ] 9.3 Manual QA multiple shots sequentially and resume after the user closes Chrome mid-run.
- [ ] 9.4 Manual QA needs-login: expire/remove session, stop job, relogin, and resume from the unfinished shot.
- [ ] 9.5 Manual QA quota/provider error/download timeout and retry after user action.
- [ ] 9.6 Manual QA auto-render from ready clips/voice/SRT to final MP4.
- [ ] 9.7 Manual QA security: package/debug export excludes Chrome profile, cookies/tokens, and full long prompts.
- [ ] 9.8 Update Vietnamese AI Video docs with dedicated Chrome profile setup, why Voicebox does not auto-login or extract browser cookies, how to reduce relogins, and manual upload fallback.

## 10. Verification During This Spec Sync

- [x] 10.1 `openspec validate tu-dong-tao-clip-veo-chrome --strict` passed before the sync.
- [x] 10.2 Python syntax check passed for Veo clip generation/session/provider files before the sync.
- [x] 10.3 `npm run typecheck` passed for `app`.
- [x] 10.4 `npm run verify:ai-video-veo` passed for the static Veo panel/API verification script.
- [ ] 10.5 Run targeted backend pytest coverage once tests in section 7 are added.
