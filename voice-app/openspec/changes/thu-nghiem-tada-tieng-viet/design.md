## Context

Voicebox already ships a TADA backend with `tada-1b` and `tada-3b-ml`. Upstream `HumeAI/tada-3b-ml` is multilingual, but its published language list does not include Vietnamese, and `HumeAI/tada-codec` does not currently publish an `aligner-vi` folder. The current Voicebox TADA backend also loads the encoder without a `language` parameter, while TADA's multilingual path depends on choosing the language-specific aligner when the reference prompt is encoded.

Vietnamese support should therefore start as an evidence-driven experiment. The first implementation should answer whether TADA 3B can produce usable Vietnamese speech for the user's needs, without presenting Vietnamese as officially supported or silently degrading existing TADA behavior.

## Goals / Non-Goals

**Goals:**

- Create a repeatable TADA 3B Vietnamese evaluation flow using a fixed Vietnamese corpus and a real Vietnamese reference sample.
- Capture generated WAV outputs and a simple review record for pronunciation, tone marks, naturalness, speaker similarity, and stability.
- Fix the TADA prompt path so prompt encoding can be language-aware and cache-safe.
- Expose Vietnamese for TADA 3B only when the evaluation is accepted, and label it experimental.

**Non-Goals:**

- Training or fine-tuning a Vietnamese TADA aligner.
- Claiming official upstream Vietnamese support for TADA.
- Adding a new TTS engine in this change.
- Solving Vietnamese STT, dictation, subtitle, or AI video language behavior.

## Decisions

1. **Run a spike before enabling UI/API support.**

   The implementation will first add an internal/manual evaluation path that generates Vietnamese samples from TADA 3B and records the result. This avoids exposing `vi` in the normal language selector before there is evidence that the output is usable.

   Alternative considered: add `vi` directly to `ENGINE_LANGUAGES.tada` and backend validation. This was rejected because the absence of an upstream `aligner-vi` makes quality unpredictable.

2. **Make TADA voice prompt creation language-aware.**

   The TADA backend should be able to encode prompts with a requested language and include that language plus the actual aligner strategy in its cache key. This matters even for currently supported non-English TADA languages because the aligner selection happens at prompt-encoding time, not generation time.

   Because upstream does not publish `aligner-vi`, the Vietnamese spike should not pretend that a Vietnamese aligner exists. The evaluation should run a clearly labeled fallback strategy, such as `language=vi` with `aligner=default`, and record that strategy in the artifacts.

   Alternative considered: pass language only to `generate()`. This does not solve TADA alignment because the voice prompt has already been encoded by then.

3. **Treat Vietnamese as experimental and TADA-3B-only if it passes, with an explicit local bypass for testing.**

   If the spike passes, `vi` should be exposed only for the `tada:3B` selection, with UI/API copy indicating experimental/unsupported status. TADA 1B remains English-only.

   For local testing before the spike is formally accepted, Voicebox may provide an explicit developer/user-controlled bypass that allows `engine=tada`, `model_size=3B`, `language=vi` to run in normal generation surfaces, including AI Video voice generation. This bypass is only for manual quality testing with a Vietnamese profile such as "Thoai 1 Vietnamese"; it must not imply official support, must not enable TADA 1B Vietnamese, and must not silently fallback to English or another engine.

   Alternative considered: expose Vietnamese for every engine that might tokenize it. This would confuse language availability with actual speech quality.

4. **Use a small fixed corpus instead of open-ended subjective testing.**

   The spike should generate a stable corpus that includes short phrases, long sentences, diacritics, northern/southern tone-sensitive words, numbers, acronyms, punctuation, and quotation-like dialogue. Reviewers can still judge by ear, but they judge the same material each run.

   Alternative considered: ask the user to test arbitrary text in the app. This is faster, but it produces weak evidence and makes regressions hard to compare.

## Risks / Trade-offs

- **No upstream Vietnamese aligner** -> Output may have poor tones or unstable pronunciation. Mitigation: keep Vietnamese hidden unless review passes; document the failure if it does not.
- **Manual audio review is subjective** -> Results may vary between listeners. Mitigation: use fixed sentences and a simple scoring rubric with critical failures called out explicitly.
- **Experimental label can still imply support** -> Users may over-trust it. Mitigation: use clear wording in UI/docs and avoid listing Vietnamese in official TADA supported-language tables.
- **Language-aware prompt encoding touches a shared protocol** -> Existing engines should not be broken. Mitigation: add the language parameter as optional/defaulted and keep non-TADA behavior unchanged.

## Migration Plan

1. Add language-aware prompt plumbing and tests without exposing Vietnamese broadly.
2. Add the Vietnamese evaluation corpus and generation/review workflow.
3. Add an explicit local test bypass for `tada:3B + vi` so the user can generate and listen inside the app before accepting the review.
4. Run the spike locally with TADA 3B and a Vietnamese reference profile.
5. If accepted, expose `vi` as experimental for `tada:3B`; otherwise leave it hidden by default and require the bypass for further testing.
6. Rollback is straightforward: disable/remove the bypass while keeping language-aware prompt cache improvements.

## Open Questions

- What minimum quality threshold is acceptable for the user's production needs: intelligible Vietnamese only, or natural Vietnamese with reliable tone marks?
- Which Vietnamese accent should the reference sample represent for the first spike?
- Should the generated evaluation artifacts live under `output/`, `backend/tests/fixtures/`, or a gitignored data directory?
