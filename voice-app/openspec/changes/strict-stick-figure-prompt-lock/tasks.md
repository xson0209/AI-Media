## Implementation

- [x] Add opt-in stick-figure detection and reusable positive/negative prompt rules.
- [x] Inject the instruction into story, shot-breakdown, prompt-pack, and normalized prompt flows.
- [x] Add a discoverable one-click strict stick-figure preset to the existing visual-style field.
- [x] Add focused regression tests for activation, constraints, idempotency, and non-stick projects.
- [x] Run targeted tests and type/lint checks appropriate to the backend change.
- [x] Verify the implementation against this change and record residual risks.

Verification note: Python compileall, focused smoke assertions, OpenSpec strict validation, and app TypeScript typecheck pass. The repository Python environment does not currently include `pytest`; the focused test file is ready to run once the dependency is installed.
