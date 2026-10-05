## Detection

Use a small, case-insensitive vocabulary for explicit requests: `stick figure`, `stick-figure`, `stickman`, `stick person`, `stickperson`, `người que`, and `nguoi que`. Inspect the project's topic, title, visual style, continuity bible, and style bible. This keeps the feature opt-in without adding a new persisted enum or migration.

## Prompt contract

Define one positive instruction and one negative constraint at module scope. The positive instruction must say that the head is a simple round shape, the torso is a thin line/capsule, limbs are uniform rods with simple joints, and hands/feet have no human anatomy. It must explicitly allow 3D shading, depth, volumetric lighting, materials, and camera motion as rendering techniques only.

The negative constraint must block palms, fingers, toes, soles, heels, muscles, skin, shoulders, hips, chest, pelvis, detailed human faces, human proportions, and humanoid anatomical redesigns.

## Injection points

- Add the instruction to the story-development, shot-breakdown, and prompt-pack model instructions when detection is positive.
- Pass the opt-in flag into prompt-pack payload normalization and append the positive/negative constraints to every prompt item and its negative prompt.
- Keep direct callers of normalization backward compatible by making the new flag optional and false by default.

## Compatibility

This is independent of `content_genre`, `made_for_kids`, and the global 3D rendering rule. A Kids project may request a stick figure, but Kids is not required. A non-Kids project may request one. Projects without an explicit hint retain current behavior.

## UI affordance

Place a compact `Dùng preset người que chuẩn` action next to the existing visual-style textarea. It replaces that field with an explicit, editable anatomy contract. Because it uses the existing `visual_style` field, it requires no new persisted state, API contract, dropdown enum, or migration, and projects remain portable through current create/update flows.

## Testing

Unit tests should verify vocabulary matching, project-level activation, idempotent prompt/negative-prompt injection, and no injection for a normal project. Existing prompt schema and content-profile tests remain the broader regression suite.
