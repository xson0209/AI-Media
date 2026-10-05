## Why

`video_purpose` currently mixes market, objective, workflow and configuration (for example `vietnam_market`, `educational_explainer` and `localized_variant`). That makes the AI planning prompt too generic and gives the user no reliable way to express the actual genre, audience age or safety expectations. The database snapshot already shows strong Kids/cartoon, health education and relationship content, so a structured content contract is the highest-leverage next step.

## What Changes

- Add a versioned `Content Profile` contract for AI Video projects with separate objective, genre, audience age band, format profile, distribution platform, interaction mode and safety policy fields.
- Add optional learning objective and `made_for_kids` metadata so Kids/Family content can be generated and reviewed with the right constraints.
- Keep `video_purpose` unchanged for backward compatibility and expose deterministic aliases/defaults that map legacy projects into a Content Profile.
- Add a backend genre-template registry, initially covering Kids & Family variants (educational, rescue, STEM and song) while documenting the next health, relationship, product, news and developer profiles.
- Include the resolved profile and genre guidance in story-development/phase-2 planning context so genre changes affect narrative structure, not only tone and voice settings.
- Add Content Profile controls and a compact Kids/Family guidance panel to the AI Video Assistant form; existing projects continue to load and save without migration steps for users.
- Add idempotent SQLite column migrations, API typing, validation and focused tests.

## Capabilities

### New Capabilities

- `content-profile`: Structured, versioned content metadata and legacy `video_purpose` mapping for AI Video projects.
- `genre-templates`: Genre-specific defaults and planning guidance, starting with Kids & Family templates.

### Modified Capabilities

<!-- No existing main specs are present; this change introduces the first formal capabilities. -->

## Impact

- Backend: `backend/models.py`, `backend/database/models.py`, `backend/database/migrations.py`, `backend/services/video_projects.py`, `backend/services/video_phase2.py`, and a new content-profile service.
- Frontend: AI Video Assistant form and API TypeScript models.
- Existing SQLite databases receive nullable/defaulted columns at startup; no destructive migration or provider change is required.
- Generated story/shot artifacts become stale when the content profile changes, using the same safety path as purpose/language changes.
