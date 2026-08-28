# Product Video render parity

## Why

Product Video currently stops after generating Flow prompts. Users can plan and copy prompts, but they cannot upload or replace the resulting clips, inspect clip readiness, configure render options, or build/download an MP4 from the same workspace. This makes the workflow materially different from AI Video even though the downstream inputs are the same kind of ordered video shots.

## What changes

- Keep Product Video's product-specific planning and Flow prompt generation unchanged.
- Add an explicit render bridge to the existing AI Video render pipeline instead of duplicating FFmpeg, clip probing, readiness, subtitle, watermark-cleanup, enhanced-render, and download logic.
- Mirror Product Video projects/shots into render-compatible AI Video rows after planning and keep the mirror synchronized when configuration, shots, or prompts change.
- Expose the mirror project/shots to the Product Video frontend and reuse the AI Video render panel for per-shot upload, re-upload, preview, delete, batch import, render settings, readiness, MP4 render, and downloads.
- Give Product Video the same up-front creative controls as AI Video: dialogue mode, narration density, CTA, quick/manual creation, automation level, and a product-safe output target. In quick mode, automation may plan and generate Product Video prompts, but never creates a provider, TTS, Chrome, or render job.
- Preserve the boundary that Product Video does not create provider clips, Chrome jobs, TTS jobs, or MP4s automatically; users upload clips and explicitly press render.

## Out of scope

- Changing Product Video prompt wording or provider schema/fallback behavior beyond the existing product prompt contract.
- Creating a second render implementation or a second clip storage format.
- Automatically generating clips in Google Flow or uploading assets to an external provider.
