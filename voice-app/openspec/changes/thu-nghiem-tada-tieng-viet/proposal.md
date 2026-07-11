## Why

Voicebox needs a Vietnamese voice path, and TADA 3B Multilingual is already integrated as a high-quality cloned-voice engine. However, upstream TADA does not list Vietnamese as an officially supported language, so enabling it without a quality gate could expose users to broken tone, accent, or alignment behavior.

## What Changes

- Add an experimental evaluation path for Vietnamese speech generation with TADA 3B Multilingual.
- Create a repeatable Vietnamese test corpus covering short, long, tonal, numeric, and punctuation-heavy sentences.
- Generate comparison samples with a Vietnamese reference voice and capture qualitative pass/fail notes before exposing the option broadly.
- If the evaluation passes, expose Vietnamese for TADA as experimental/unsupported rather than as an official supported language.
- If the evaluation fails, keep TADA Vietnamese hidden and document why another Vietnamese-native engine or future TADA aligner work is required.

## Capabilities

### New Capabilities
- `tada-vietnamese-experimental`: Evaluates and gates experimental Vietnamese generation through the existing TADA 3B Multilingual engine.

### Modified Capabilities

None.

## Impact

- Backend TADA prompt creation and generation paths may need to carry the requested language into prompt encoding and cache keys.
- Frontend language selection may gain `vi` for TADA only if the spike passes.
- API validation may need to accept `vi` for voice profiles and generation requests when experimental Vietnamese support is enabled.
- Documentation should clearly distinguish experimental Vietnamese output from officially supported TADA languages.
- No new model dependency is expected for the initial spike; future aligner/fine-tune work remains out of scope unless the evaluation shows it is necessary.
