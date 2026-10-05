# Context-aware video interaction CTA

## What

Add a structured CTA action (comment, like, share, follow, save, subscribe, or none) beside the existing CTA tone. The selected intent must be interpreted against the approved final beat, character, props, setting, and emotional state so the generated ending uses a plausible human action instead of a generic social-media gesture.

## Why

The current pipeline stores only `call_to_action_style` (`none`, `soft`, `direct`, `urgent`). It can ask the model to end with a CTA, but cannot distinguish a request to comment from a request to like or share, and it does not enforce contextual fit. This makes the final prompt underspecified and can produce unnatural gestures.

## Scope

- Persist and expose a normalized `cta_action` with backwards-compatible `none` behavior.
- Pass the action through project settings and AI planning schemas.
- Require the final shot to derive CTA speech and visual delivery from its approved context.
- Keep exact spoken text in `speech_cues`; keep provider prompt free of burned-in UI text.
- Add validation/tests for context anchoring, one primary action, language lock, and kids/platform safety.

## Non-goals

- Rendering platform UI buttons inside the generated video.
- Implementing platform analytics or automatic publishing interactions.
- Replacing the existing CTA tone control.
