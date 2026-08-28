// Exercises the real settings store (not string assertions) for the cases that used to
// lose the user's choices: nothing saved yet, a blob from an older build missing keys,
// and a corrupt blob. Node >= 22.6 strips the TS types natively.
import { strict as assert } from 'node:assert';
import { dirname, join } from 'node:path';
import { fileURLToPath, pathToFileURL } from 'node:url';

const root = dirname(dirname(fileURLToPath(import.meta.url)));

// A localStorage stand-in installed before the module loads, since the module reads
// `window.localStorage` at call time.
class MemoryStorage {
  #entries = new Map();
  throwOnRead = false;
  throwOnWrite = false;

  getItem(key) {
    if (this.throwOnRead) throw new Error('storage blocked');
    return this.#entries.has(key) ? this.#entries.get(key) : null;
  }

  setItem(key, value) {
    if (this.throwOnWrite) throw new Error('quota exceeded');
    this.#entries.set(key, String(value));
  }

  keys() {
    return [...this.#entries.keys()];
  }
}

const storage = new MemoryStorage();
globalThis.window = { localStorage: storage };

const {
  CLIP_AUDIO_CHOICE_BED,
  CLIP_AUDIO_CHOICE_CLIP_ONLY,
  CLIP_AUDIO_CHOICE_DROP,
  DEFAULT_RENDER_SETTINGS,
  clipAudioChoiceFromSettings,
  clipAudioModeForChoice,
  loadRenderSettings,
  mergeStoredRenderSettings,
  muteClipAudioForChoice,
  renderSettingsStorageKey,
  saveRenderSettings,
  settingsForClipAudioChoice,
} = await import(pathToFileURL(join(root, 'src/lib/renderSettingsStore.ts')).href);

// --- the default keeps the original clip audio ------------------------------------
// Default level is now clip-only ("âm thanh gốc"); the boolean stays in sync for older builds.
assert.equal(DEFAULT_RENDER_SETTINGS.mute_clip_audio, false, 'default keeps the original audio');
assert.equal(
  DEFAULT_RENDER_SETTINGS.clip_audio_mode,
  CLIP_AUDIO_CHOICE_CLIP_ONLY,
  'default level is clip-only',
);

// --- the three dropdown choices map onto the boolean both ways ---------------------
// The level is the field that matters; the boolean is kept in sync for older builds.
assert.equal(muteClipAudioForChoice(CLIP_AUDIO_CHOICE_DROP), true, 'dropping the original audio means true');
assert.equal(muteClipAudioForChoice(CLIP_AUDIO_CHOICE_BED), false, 'keeping it as a bed means false');
assert.equal(muteClipAudioForChoice(CLIP_AUDIO_CHOICE_CLIP_ONLY), false, 'clip-only keeps the original audio');
assert.equal(muteClipAudioForChoice('karaoke'), true, 'an unknown choice falls back to the safe default');
assert.equal(clipAudioModeForChoice('karaoke'), CLIP_AUDIO_CHOICE_DROP, 'an unknown level normalizes to the default');
assert.equal(
  clipAudioChoiceFromSettings({ ...DEFAULT_RENDER_SETTINGS, clip_audio_mode: CLIP_AUDIO_CHOICE_CLIP_ONLY }),
  CLIP_AUDIO_CHOICE_CLIP_ONLY,
  'the stored level reads back as itself',
);
assert.equal(
  clipAudioChoiceFromSettings(DEFAULT_RENDER_SETTINGS),
  CLIP_AUDIO_CHOICE_CLIP_ONLY,
  'the default shows the clip-only choice',
);
// Settings written before the level existed carry only the boolean.
assert.equal(
  clipAudioChoiceFromSettings({ ...DEFAULT_RENDER_SETTINGS, clip_audio_mode: undefined, mute_clip_audio: false }),
  CLIP_AUDIO_CHOICE_BED,
  'a legacy false boolean reads back as the bed choice',
);
assert.equal(
  clipAudioChoiceFromSettings({ ...DEFAULT_RENDER_SETTINGS, clip_audio_mode: undefined, mute_clip_audio: true }),
  CLIP_AUDIO_CHOICE_DROP,
  'a legacy true boolean reads back as the drop choice',
);
// Every value the dropdown offers round-trips, and both fields always agree afterwards.
for (const choice of [CLIP_AUDIO_CHOICE_DROP, CLIP_AUDIO_CHOICE_BED, CLIP_AUDIO_CHOICE_CLIP_ONLY]) {
  const applied = settingsForClipAudioChoice(DEFAULT_RENDER_SETTINGS, choice);
  assert.equal(applied.clip_audio_mode, choice, 'the chosen level is written');
  assert.equal(applied.mute_clip_audio, muteClipAudioForChoice(choice), 'the legacy boolean is kept in sync');
  assert.equal(clipAudioChoiceFromSettings(applied), choice, 'the mapping round-trips');
}

// --- nothing saved yet ------------------------------------------------------------
assert.deepEqual(loadRenderSettings('proj-empty'), DEFAULT_RENDER_SETTINGS, 'no stored value means defaults');
assert.deepEqual(loadRenderSettings(null), DEFAULT_RENDER_SETTINGS, 'no project means defaults');
assert.deepEqual(loadRenderSettings(undefined), DEFAULT_RENDER_SETTINGS, 'undefined project means defaults');

// --- a choice survives a reload ---------------------------------------------------
saveRenderSettings('proj-a', {
  ...settingsForClipAudioChoice(DEFAULT_RENDER_SETTINGS, CLIP_AUDIO_CHOICE_CLIP_ONLY),
  fps: 60,
});
const reloadedA = loadRenderSettings('proj-a');
assert.equal(reloadedA.clip_audio_mode, CLIP_AUDIO_CHOICE_CLIP_ONLY, 'the chosen level survives a reload');
assert.equal(reloadedA.mute_clip_audio, false, 'keeping the original audio survives a reload');
assert.equal(reloadedA.fps, 60, 'other settings survive too');

// --- one project does not affect another ------------------------------------------
assert.equal(loadRenderSettings('proj-b').mute_clip_audio, false, 'another project still sees the default');
assert.equal(
  loadRenderSettings('proj-b').clip_audio_mode,
  CLIP_AUDIO_CHOICE_CLIP_ONLY,
  'another project still sees the default level',
);
saveRenderSettings('proj-b', { ...DEFAULT_RENDER_SETTINGS, resolution: '1080p' });
assert.equal(loadRenderSettings('proj-a').fps, 60, "project A keeps its own settings");
assert.equal(loadRenderSettings('proj-b').fps, DEFAULT_RENDER_SETTINGS.fps, 'project B keeps its own');
assert.notEqual(
  renderSettingsStorageKey('proj-a'),
  renderSettingsStorageKey('proj-b'),
  'each project gets its own key',
);

// --- a blob from an older build, missing keys added since --------------------------
// This is the upgrade case: the level did not exist yet, so it has to be inferred from the
// boolean instead of resetting to the default and losing the user's saved choice.
const partial = mergeStoredRenderSettings({ mute_clip_audio: false, fps: 24 });
assert.equal(partial.mute_clip_audio, false, 'the stored key is honoured');
assert.equal(partial.clip_audio_mode, CLIP_AUDIO_CHOICE_BED, 'the level is inferred from the stored boolean');
assert.equal(partial.fps, 24, 'the stored key is honoured');
assert.equal(partial.watermark_backend, DEFAULT_RENDER_SETTINGS.watermark_backend, 'missing key falls back');
assert.equal(partial.ai_review, DEFAULT_RENDER_SETTINGS.ai_review, 'missing key falls back');
assert.equal(
  mergeStoredRenderSettings({ mute_clip_audio: true }).clip_audio_mode,
  CLIP_AUDIO_CHOICE_DROP,
  'a legacy blob that dropped the original audio still reads as the voice-only level',
);
assert.deepEqual(
  Object.keys(partial).sort(),
  Object.keys(DEFAULT_RENDER_SETTINGS).sort(),
  'the merged result always has every key the UI reads',
);
assert.deepEqual(
  Object.keys(mergeStoredRenderSettings({ clip_audio_mode: CLIP_AUDIO_CHOICE_CLIP_ONLY })).sort(),
  Object.keys(DEFAULT_RENDER_SETTINGS).sort(),
  'the new level does not add or drop a key the UI reads',
);
assert.equal(
  mergeStoredRenderSettings({ clip_audio_mode: CLIP_AUDIO_CHOICE_CLIP_ONLY }).mute_clip_audio,
  false,
  'a stored level always writes back a matching boolean',
);

// --- an invalid value costs only its own key --------------------------------------
const invalid = mergeStoredRenderSettings({
  mute_clip_audio: false,
  clip_audio_mode: 'karaoke',
  resolution: '4k',
  fps: 'thirty',
  subtitle_mode: 'karaoke',
  max_fix_attempts: 99,
  watermark_backend: 'lama',
  background_color: 'not-a-colour',
  unknown_setting: 'ignored',
});
assert.equal(invalid.mute_clip_audio, false, 'the valid choice is kept despite invalid neighbours');
// An unusable level is treated like an absent one: infer from the boolean that did validate.
assert.equal(invalid.clip_audio_mode, CLIP_AUDIO_CHOICE_BED, 'an unknown level falls back to the stored boolean');
assert.equal(invalid.resolution, DEFAULT_RENDER_SETTINGS.resolution, 'unknown resolution falls back');
assert.equal(invalid.fps, DEFAULT_RENDER_SETTINGS.fps, 'non-numeric fps falls back');
assert.equal(invalid.subtitle_mode, DEFAULT_RENDER_SETTINGS.subtitle_mode, 'unknown subtitle mode falls back');
assert.equal(invalid.max_fix_attempts, DEFAULT_RENDER_SETTINGS.max_fix_attempts, 'out-of-range attempts falls back');
assert.equal(invalid.watermark_backend, DEFAULT_RENDER_SETTINGS.watermark_backend, 'unsupported backend falls back');
assert.equal(invalid.background_color, DEFAULT_RENDER_SETTINGS.background_color, 'malformed colour falls back');
assert.ok(!('unknown_setting' in invalid), 'an unknown key is not carried over');

// --- a corrupt blob does not take the panel down ----------------------------------
storage.setItem(renderSettingsStorageKey('proj-corrupt'), '{not json');
assert.deepEqual(loadRenderSettings('proj-corrupt'), DEFAULT_RENDER_SETTINGS, 'unparseable JSON means defaults');
for (const junk of ['null', '[]', '"a string"', '42', 'true']) {
  storage.setItem(renderSettingsStorageKey('proj-junk'), junk);
  assert.deepEqual(loadRenderSettings('proj-junk'), DEFAULT_RENDER_SETTINGS, `${junk} means defaults`);
}

// --- storage being unavailable is not an error ------------------------------------
storage.throwOnRead = true;
assert.deepEqual(loadRenderSettings('proj-a'), DEFAULT_RENDER_SETTINGS, 'a blocked read falls back');
storage.throwOnRead = false;
storage.throwOnWrite = true;
assert.doesNotThrow(() => saveRenderSettings('proj-a', DEFAULT_RENDER_SETTINGS), 'a full storage does not throw');
storage.throwOnWrite = false;

// Nothing is written when there is no project to key it under.
const keysBefore = storage.keys().length;
saveRenderSettings(null, DEFAULT_RENDER_SETTINGS);
assert.equal(storage.keys().length, keysBefore, 'no project means nothing is written');

console.log('AI Video render settings persistence verification passed.');
