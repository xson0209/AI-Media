## Context

AI Video stores language, purpose, dialogue density and visual style directly on `video_projects`. The only semantic selector is `video_purpose`, whose values mix unrelated concerns and whose prompt guidance changes mostly tone. Existing project data must remain readable, SQLite migrations must be idempotent, and generated artifacts must be invalidated if a semantic contract changes.

The first useful vertical is Kids & Family because the repository already contains repeated robot-car/cartoon series and a researched two-minute structure. Health, relationship, product, news and developer genres need a stable extension point but do not all need complete UI/workflow support in this first change.

## Goals / Non-Goals

**Goals:**

- Represent objective, genre, audience, format, distribution, interaction and safety as separate validated fields.
- Preserve the existing `video_purpose` API and data without rewriting old rows.
- Make a selected genre materially influence AI story-development prompts.
- Provide deterministic Kids & Family defaults and quality guidance for four initial templates.
- Give the AI Video Assistant a clear, compact profile editor that works for new and existing projects.
- Keep backend and frontend options synchronized through a read-only options endpoint.

**Non-Goals:**

- Replacing `video_purpose` or migrating all historical rows eagerly.
- Implementing Narrative Contract/Beat Graph change 15, new providers, reference-image ingestion, publishing automation or market-demand analytics.
- Fully implementing health/news evidence workflows, product UGC asset handling, or developer repository ingestion.
- Adding a route or database table for each genre.

## Decisions

### 1. Use explicit project columns plus a schema version

`video_projects` gains `content_profile_version`, `content_objective`, `content_genre`, `audience_age_band`, `format_profile`, `distribution_platform`, `interaction_mode`, `safety_policy`, `made_for_kids` and `learning_objective`.

Explicit columns make validation, filtering and API typing straightforward. A single JSON blob was considered, but it would hide invalid values and make future search/reporting harder. The version field allows additive evolution while the optional/defaulted columns keep migration safe.

### 2. Resolve defaults in one backend service

A new `content_profile` service owns enum values, legacy `video_purpose` mapping, duration-based format inference, template metadata and prompt guidance. Create/update/episode/localize paths call the same resolver. Existing rows whose new columns contain defaults still receive a valid profile without a data rewrite.

The `video_purpose` service remains unchanged and continues to own language/dialogue/CTA behavior. Content Profile is an orthogonal layer, not another expansion of `VIDEO_PURPOSE_VALUES`.

### 3. Enforce safe Kids invariants server-side

Selecting a Kids genre forces `made_for_kids=true`, `safety_policy=kids_strict`, an age band below teens and a Kids-compatible interaction/format default when omitted. This prevents clients from creating contradictory metadata. User-supplied learning objectives remain optional because not every rescue/song episode has a formal curriculum statement.

### 4. Registry-driven options endpoint

`GET /ai-video/content-profile/options` returns supported values, labels, defaults and genre guidance. The UI consumes this registry and retains local fallback options so the create form remains usable during a transient fetch failure.

### 5. Treat semantic profile changes as content changes

Changing objective, genre, audience, format, interaction, safety, Kids status or learning objective invalidates story approval, retention/sound plans, unlocked prompts, subtitles, render outputs and publishing metadata through the existing stale paths. Distribution-only changes also stale publishing metadata, while profile changes that affect generation stale the planning output.

### 6. Inject profile guidance before story generation

The normalized phase-2 context includes the resolved profile and template guidance. Kids templates specify the two-minute beat pattern, simple problem-solving limits, participation cue and concrete safety restrictions. These lines are also included in fallback/provider prompts so the contract survives provider changes.

## Risks / Trade-offs

- **[Backend and frontend enum drift]** → The options endpoint is authoritative; frontend fallbacks are covered by type/build tests and intentionally minimal.
- **[Historical projects receive generic defaults]** → Legacy `video_purpose` mapping produces deterministic objective/genre values at read/generation time; no risky bulk rewrite is performed.
- **[Kids flag can be misleading if a non-Kids genre is chosen]** → `made_for_kids` remains independently editable for general family content, while Kids genres always force it on.
- **[Prompt guidance is not a full narrative compiler]** → This change creates the contract and first templates; Beat Graph/Narrative Contract stays in change 15 and can consume the same fields later.
- **[More controls can overwhelm the creation form]** → Show objective/genre/age/format first and reveal policy/interaction details in a compact profile section with template defaults.

## Migration Plan

1. Run the existing idempotent startup migration to append the new columns with safe defaults.
2. Deploy backend models/service/API and frontend types/UI together.
3. Read legacy rows through resolver defaults; do not update historical records unless the user saves the profile.
4. If rollback is needed, older application versions ignore the extra SQLite columns and continue using `video_purpose`.

## Open Questions

- Genre-specific analytical scoring weights and performance benchmarks should be calibrated with real publishing data after the first Kids pilots.
- Future profiles may need multiple distribution platforms rather than the single primary-platform field used by this MVP.
- Health/news evidence provenance and Product UGC reference assets remain separate follow-up changes because they require additional domain data, not only a genre selector.
