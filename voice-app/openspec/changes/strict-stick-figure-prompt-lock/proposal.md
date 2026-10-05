## Why

The video prompt pipeline can produce a 3D-rendered character, but it does not define the anatomy of a true stick figure. A model may therefore add human-like hands, feet, muscles, facial features, or human proportions even when the user asks for a stick-figure video.

## What Changes

- Detect an explicit stick-figure request from the project's visual style and topic fields.
- Add a reusable strict stick-figure anatomy instruction to story/shot/prompt generation when requested.
- Add the same anatomy lock and negative constraints to normalized video prompts so provider copies retain the intended character definition.
- Add a one-click strict stick-figure preset beside the existing visual-style field so users do not need to author the anatomy contract manually.
- Keep the lock opt-in; ordinary, Kids, product, news, documentary, and other projects remain unchanged unless they request a stick figure.
- Add regression tests for activation, positive anatomy constraints, negative constraints, and non-stick projects.

## Scope

Backend prompt generation and normalization in `backend/services/video_phase2.py`, a small quick-preset action in the existing AI Video form, focused tests, and OpenSpec documentation. No database migration or API schema change is required: the preset writes the strict contract into the existing visual-style field, while manually entered terms such as `3D stick figure` or `người que` are also recognized.

## Acceptance Criteria

- A project whose visual style or topic explicitly requests a stick figure receives a strict non-anatomical stick-figure instruction during story, shot, and prompt-pack generation.
- Each normalized video prompt for that project contains the positive stick-figure anatomy lock.
- Each normalized negative prompt for that project blocks human hands, feet, fingers, toes, muscles, realistic human proportions, and related anatomy.
- 3D rendering remains allowed for lighting, depth, materials, and camera movement.
- Projects without a stick-figure request do not receive stick-figure constraints.
- The AI Video form exposes a one-click preset that fills the existing visual-style field with the strict stick-figure contract.
- Existing Kids/content-profile behavior and provider-neutral prompt contracts remain unchanged.
