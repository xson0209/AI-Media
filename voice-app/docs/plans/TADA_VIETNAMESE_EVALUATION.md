# TADA Vietnamese Evaluation

This document describes the experimental path for checking whether `HumeAI/tada-3b-ml` is usable for Vietnamese speech in Voicebox.

## Status

Vietnamese is **not** treated as official TADA support. Upstream TADA 3B Multilingual does not list `vi`, and `HumeAI/tada-codec` does not publish `aligner-vi`. The evaluation therefore runs Vietnamese with a clearly recorded fallback aligner strategy and keeps normal TADA Vietnamese generation gated until a reviewer accepts the result.

Current outcome: blocked pending a real Vietnamese reference profile, generated TADA 3B samples, and maintainer audio review. Until `review-state.json` is marked `accepted`, Vietnamese stays hidden from normal TADA generation.

## Prerequisites

- A local Voicebox data directory with a cloned voice profile using Vietnamese reference audio.
- An accurate transcript for the reference sample. This matters because TADA's built-in ASR path is English-focused.
- The `tada-3b-ml` model available locally, or enough time and disk space for the first run to download it.
- A reviewer who can judge Vietnamese pronunciation, tones, naturalness, speaker similarity, and stability by ear.

## Output Location

Evaluation artifacts are written to:

```text
output/tada-vietnamese-eval/
```

The directory is gitignored. Each run writes generated WAV files plus JSON metadata that records the corpus version, engine, model size, language, aligner strategy, profile, seed, and review status.

## Review States

The gate reads `output/tada-vietnamese-eval/review-state.json`.

- `pending`: samples exist but are not accepted yet.
- `accepted`: normal app/API paths may expose Vietnamese as experimental TADA 3B support.
- `rejected`: Vietnamese remains hidden and the rejection notes explain why.

Do not mark a run accepted unless the fixed corpus is understandable in Vietnamese, preserves tone marks well enough for the intended use, does not switch language unexpectedly, and keeps a recognizable version of the reference speaker.
