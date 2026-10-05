## 1. Content Profile Domain

- [x] 1.1 Add the versioned Content Profile enums, legacy mappings, resolver and genre-template registry.
- [x] 1.2 Add Kids & Family generation guidance and template review checks.
- [x] 1.3 Add focused unit tests for legacy defaults, format inference and Kids safety invariants.

## 2. Persistence and API

- [x] 2.1 Add Content Profile columns to the VideoProject ORM and the idempotent SQLite startup migration.
- [x] 2.2 Extend create, update, episode, localize and response models with validated profile fields.
- [x] 2.3 Persist resolved profiles, inherit them across series/localized projects and invalidate dependent output on semantic changes.
- [x] 2.4 Add the read-only Content Profile options endpoint and API tests.

## 3. Generation Integration

- [x] 3.1 Include the resolved profile and genre-template guidance in normalized phase-2 context.
- [x] 3.2 Include profile requirements in story-development instructions and cover the integration with tests.

## 4. AI Video Assistant

- [x] 4.1 Add TypeScript Content Profile types and API client support for registry options and project fields.
- [x] 4.2 Add registry-driven objective, genre, age, format, distribution, interaction, safety and learning controls to the AI Video form.
- [x] 4.3 Load/save profile values for new projects, existing projects and new series episodes while preserving fallback behavior.
- [x] 4.4 Run frontend type/build checks and targeted backend tests; fix regressions and validate the OpenSpec change.
