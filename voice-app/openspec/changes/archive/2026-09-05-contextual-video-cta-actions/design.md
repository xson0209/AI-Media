# Design

## Contract

`call_to_action_style` remains the tone (`none`, `soft`, `direct`, `urgent`). Add `cta_action` as the viewer action (`none`, `comment`, `like`, `share`, `follow`, `save`, `subscribe`). Only one primary action is selected per project. Missing/legacy values normalize to `none` unless an existing purpose preset explicitly supplies a safe default.

The planner receives both values plus the approved final beat. It must produce:

- a context-anchored `primary_action` for the final shot;
- an exact, target-language CTA sentence in `speech_cues` (or no speech when CTA is disabled);
- a final hold/payoff transition with enough time to hear the CTA;
- no imaginary Like/Comment/Share buttons and no provider-rendered text overlays.

If no visible character can express the CTA naturally, use voiceover over the existing final composition. For kids content or platforms where comments are unavailable, the planner must avoid an unsafe/invalid interaction request and use a context-appropriate alternative or `none`.

## Data flow

Project create/update and purpose settings -> normalized service context -> story/shot/prompt schemas -> final-shot speech/visual direction -> voice/subtitle and publishing metadata fingerprints. Changing `cta_action` makes dependent story, shot, prompt, voice, subtitle, and publishing artifacts stale.

## Compatibility

The database column is nullable and additive. Existing projects read as `none`. Existing prompt packs remain valid; the new context requirement applies when a non-`none` action is selected.

## Quality gate

For a non-`none` action, validate that the final shot has a CTA retention role, a context-linked visual action, exactly one primary intent, an exact speech cue in the project language (unless voice is intentionally disabled), and a final hold. Warn/block when the action conflicts with kids/platform policy or introduces new characters, props, locations, or UI text.
