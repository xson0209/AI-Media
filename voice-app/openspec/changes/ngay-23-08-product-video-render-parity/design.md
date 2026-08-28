# Design

## Approach

Use the existing AI Video render pipeline as the single runtime for Product Video rendering.

`ProductVideoProject` receives a nullable `render_project_id` pointing to a private `VideoProject` bridge row. The bridge row uses the same project id only as an implementation detail? No: use a separate UUID so Product Video remains isolated from the AI Video project list and provider-generation APIs. The Product Video detail response returns the bridge id and render-compatible `VideoShotResponse` rows for the frontend.

After Product Video shot planning, a synchronizer creates/updates:

- one phase-2 `VideoProject` with Product Video language, aspect ratio, duration, narration mode, and render-compatible status;
- one `VideoShot` per `ProductVideoShot`, preserving order, duration, narration, motion, framing, and sound/transition metadata;
- one `VideoShotPrompt` per generated Product Video prompt for downstream timeline/package consumers.

The synchronizer is idempotent. Replanning replaces the mirror shots/prompts and marks prior render output stale; it does not delete uploaded files until the corresponding render shot is replaced. The implementation should retain active clips by matching shot order when possible, otherwise the readiness panel clearly reports missing clips.

The Product Video frontend renders `AIVideoRenderPanel` with the bridge project id and mirrored shots. All upload/re-upload/batch-import/readiness/render/download actions therefore call the existing `/ai-video/projects/{id}/...` APIs and storage. Product Video only owns prompt generation and bridge synchronization.

## Creation configuration parity

Product Video stores the user-selected creation mode (`quick` or `manual`), automation level (`review_gated` or `full_auto`), and output target (`render_ready`, `prompt_pack`, or `shots_only`) beside the existing dialogue, density, CTA, duration, clip-count, clip-duration, and micro-scene settings.

The controls intentionally mirror AI Video's configuration hierarchy but use truthful Product Video semantics:

- **Quick** performs the selected local Product Video stages after an explicit Create action. **Manual** creates only the project and leaves every stage to explicit buttons.
- **Review each stage** plans shots then stops for review. **Run all** plans and, unless the target is shots only, creates the Product Video prompt pack.
- **Ready to render MP4** means plan + prompt + render bridge ready for user-uploaded clips; it never means "send to Veo". **Prompt pack** stops at downloadable prompts. **Shots only** stops after the shot plan.

No mode is permitted to invoke a provider clip-generation endpoint, Chrome automation, TTS, subtitle generation, or MP4 render. Upload and the explicit render action remain the only route to clip and render work.

## Lifecycle

1. Create Product Video project and its render bridge.
2. Plan shots; synchronize bridge project and shots.
3. Generate product prompts; synchronize bridge prompt artifacts.
4. Upload or replace clips through the shared AI Video render panel.
5. Select render settings; readiness is computed by shared AI Video services.
6. Explicitly render MP4; poll/download the shared render job and artifacts.
7. Delete Product Video project; delete the bridge project and its artifacts safely.

## Compatibility and safeguards

- Existing Product Video prompt endpoints remain backward compatible.
- Existing AI Video endpoints remain unchanged.
- Bridge rows are not exposed as Product Video projects and are not provider-generation jobs.
- Render readiness must preserve Vietnamese Veo-native audio checks, subtitle behavior, watermark cleanup, enhanced-render fallbacks, and stale-output semantics.
- A bridge sync failure must fail the Product Video operation with a clear error and must not report prompts/shots as ready.

## Testing strategy

- Migration/idempotency tests for `render_project_id` and bridge rows.
- Service tests for create/plan/prompt synchronization and stale-output behavior.
- Route tests proving product render metadata is returned and bridge deletion is safe.
- Frontend build/typecheck and browser checks for settings, upload/re-upload, readiness, render, and download states.
- Regression run for existing AI Video backend/render tests.
