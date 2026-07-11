## 1. Evaluation Foundation

- [x] 1.1 Add a fixed Vietnamese evaluation corpus with short, long, tonal, numeric, acronym, punctuation, and dialogue-like prompts.
- [x] 1.2 Define a simple review rubric for intelligibility, tone accuracy, naturalness, speaker similarity, and stability.
- [x] 1.3 Choose a gitignored artifact location for generated WAV files and review metadata.
- [x] 1.4 Document the required local prerequisites: TADA 3B model, a Vietnamese reference profile, and an accurate reference transcript.

## 2. TADA Prompt Language Plumbing

- [x] 2.1 Extend the voice prompt creation path to accept an optional requested language without breaking existing engines.
- [x] 2.2 Pass the generation language into `profiles.create_voice_prompt_for_profile()` from queued and synchronous generation paths.
- [x] 2.3 Update the TADA backend to track the requested language and actual aligner strategy when encoding a prompt.
- [x] 2.4 Include requested language and aligner strategy in the TADA prompt cache key.
- [x] 2.5 Handle Vietnamese explicitly as a fallback/default-aligner evaluation path because upstream has no `aligner-vi`.
- [x] 2.6 Add regression tests proving non-TADA prompt creation still works and TADA cache entries are not reused across language/aligner paths.

## 3. Vietnamese Evaluation Workflow

- [x] 3.1 Add a maintainer-facing workflow or script that generates the Vietnamese corpus through TADA 3B using a selected profile.
- [x] 3.2 Save each generated sample with stable filenames including engine, model size, language, aligner strategy, and corpus item id.
- [x] 3.3 Write review metadata for each run, including corpus version, profile id/name, seed, pass/fail state, and reviewer notes.
- [x] 3.4 Fail clearly when the TADA 3B model, reference profile, or reference sample transcript is missing.

## 4. Experimental Exposure Gate

- [x] 4.1 Add a gate that keeps Vietnamese hidden for normal TADA generation until an accepted evaluation result exists.
- [x] 4.2 If evaluation is accepted, expose Vietnamese only for TADA 3B and label it experimental/unsupported in UI-facing copy.
- [x] 4.3 Keep Vietnamese unavailable for TADA 1B.
- [x] 4.4 Reject or normalize API requests that ask for TADA Vietnamese before the gate is accepted.
- [x] 4.5 If evaluation is rejected, record the rejection reason and keep Vietnamese hidden.
- [x] 4.6 Add an explicit local test bypass that allows normal generation requests for `engine=tada`, `model_size=3B`, `language=vi` before review acceptance, while keeping TADA 1B blocked and preserving experimental wording.
- [x] 4.7 Ensure AI Video voice generation can opt into the same TADA 3B Vietnamese test path instead of failing with generic `VIDEO_VOICE_LANGUAGE_UNSUPPORTED`.

## 5. Verification

- [x] 5.1 Run backend tests covering language validation, prompt creation, cache behavior, and the evaluation workflow failure paths.
- [x] 5.2 Run frontend type/build checks for language selector and engine/model selection behavior if UI exposure is implemented.
- [ ] 5.3 Run the Vietnamese TADA evaluation with a real Vietnamese reference voice and record the review result.
- [x] 5.4 Update docs or project notes with the outcome: accepted experimental support, rejected TADA Vietnamese, or blocked pending better reference data.
- [ ] 5.5 Regenerate API docs/types if backend request schemas change.
- [x] 5.6 Add focused tests for the local bypass: accepted for TADA 3B Vietnamese, rejected for TADA 1B Vietnamese, and no silent fallback to English.
