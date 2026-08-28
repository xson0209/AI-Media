/**
 * Per-project persistence for the quick MP4 render settings.
 *
 * Settings used to live in component state only, so a page reload dropped every choice
 * and made the toggles look like they had no effect. Stored values are merged key by key
 * onto the defaults and each key is validated on its own: a stored blob written by an
 * older build is missing keys added since, and dropping the whole blob over one unknown
 * key would lose exactly the choices this is meant to keep.
 */

import type { VideoRenderSettings } from '@/lib/api/types';

export const DEFAULT_RENDER_SETTINGS: VideoRenderSettings = {
  resolution: 'auto',
  fps: 60,
  fit_mode: 'crop',
  duration_mode: 'freeze',
  subtitle_mode: 'none',
  // Âm thanh gốc: clip_only bỏ voice và render từ audio của clip. Ghi kèm
  // mute_clip_audio: false để build cũ chỉ biết cờ boolean vẫn đọc đúng.
  mute_clip_audio: false,
  clip_audio_mode: 'clip_only',
  background_color: '#111827',
  enhanced_render: true,
  enhanced_audio: true,
  ai_review: true,
  max_fix_attempts: 0,
  watermark_cleanup: true,
  watermark_backend: 'cv2',
};

/**
 * The three audio levels offered in the UI, carried by the `clip_audio_mode` API field.
 * The older boolean `mute_clip_audio` is still written alongside it so a build that only
 * knows the boolean keeps reading the settings correctly.
 *
 * The clip-only level is not the same as the bed level: the bed level keeps the voice as the
 * main track and puts the clip audio underneath it, while the clip-only level drops the voice
 * entirely and renders from the clip audio alone — which is what makes it usable on a project
 * whose shots have narration text but no generated voice at all.
 */
export const CLIP_AUDIO_CHOICE_DROP = 'drop';
export const CLIP_AUDIO_CHOICE_BED = 'bed';
export const CLIP_AUDIO_CHOICE_CLIP_ONLY = 'clip_only';

export type ClipAudioChoice =
  | typeof CLIP_AUDIO_CHOICE_DROP
  | typeof CLIP_AUDIO_CHOICE_BED
  | typeof CLIP_AUDIO_CHOICE_CLIP_ONLY;

const CLIP_AUDIO_CHOICES: readonly ClipAudioChoice[] = [
  CLIP_AUDIO_CHOICE_DROP,
  CLIP_AUDIO_CHOICE_BED,
  CLIP_AUDIO_CHOICE_CLIP_ONLY,
];

/** Normalize an arbitrary select value; anything unknown falls back to the default level. */
export function clipAudioModeForChoice(choice: string): ClipAudioChoice {
  return CLIP_AUDIO_CHOICES.includes(choice as ClipAudioChoice)
    ? (choice as ClipAudioChoice)
    : CLIP_AUDIO_CHOICE_DROP;
}

export function clipAudioChoiceFromSettings(settings: VideoRenderSettings): ClipAudioChoice {
  const mode = settings.clip_audio_mode;
  if (mode && CLIP_AUDIO_CHOICES.includes(mode)) return mode;
  // Settings written before the level existed only carry the boolean.
  return settings.mute_clip_audio ? CLIP_AUDIO_CHOICE_DROP : CLIP_AUDIO_CHOICE_BED;
}

export function muteClipAudioForChoice(choice: string): boolean {
  const mode = clipAudioModeForChoice(choice);
  return mode !== CLIP_AUDIO_CHOICE_BED && mode !== CLIP_AUDIO_CHOICE_CLIP_ONLY;
}

/** Apply a level to the settings, writing both fields so they can never disagree. */
export function settingsForClipAudioChoice(
  settings: VideoRenderSettings,
  choice: string,
): VideoRenderSettings {
  const mode = clipAudioModeForChoice(choice);
  return { ...settings, clip_audio_mode: mode, mute_clip_audio: muteClipAudioForChoice(mode) };
}

const STORAGE_PREFIX = 'voicebox.aiVideo.renderSettings';

/** Keyed per project so one project's choices never leak into another's. */
export function renderSettingsStorageKey(projectId: string): string {
  return `${STORAGE_PREFIX}.${projectId}`;
}

type Validator = (value: unknown) => unknown | undefined;

const oneOf = (allowed: readonly string[]): Validator => (value) =>
  typeof value === 'string' && allowed.includes(value) ? value : undefined;

const boolean: Validator = (value) => (typeof value === 'boolean' ? value : undefined);

const intWithin = (allowed: readonly number[]): Validator => (value) =>
  typeof value === 'number' && Number.isInteger(value) && allowed.includes(value) ? value : undefined;

const hexColor: Validator = (value) =>
  typeof value === 'string' && /^#[0-9a-fA-F]{6}$/.test(value) ? value : undefined;

/**
 * One validator per key. A key with no validator is not restored at all, which is how a
 * setting that was removed from the UI stops having an effect without any cleanup step.
 */
const VALIDATORS: Record<keyof VideoRenderSettings, Validator> = {
  resolution: oneOf(['auto', '720p', '1080p']),
  fps: intWithin([24, 30, 60]),
  fit_mode: oneOf(['crop', 'pad']),
  duration_mode: oneOf(['freeze', 'trim_only']),
  subtitle_mode: oneOf(['burn_in', 'sidecar', 'none']),
  mute_clip_audio: boolean,
  clip_audio_mode: oneOf(CLIP_AUDIO_CHOICES),
  background_color: hexColor,
  force: boolean,
  enhanced_render: boolean,
  enhanced_audio: boolean,
  ai_review: boolean,
  max_fix_attempts: intWithin([0, 1, 2]),
  watermark_cleanup: boolean,
  watermark_backend: oneOf(['cv2', 'migan']),
};

/**
 * Merge a stored value onto the defaults, keeping only keys that validate.
 *
 * Exported separately from the storage read so the merge rules can be exercised without
 * a browser.
 */
export function mergeStoredRenderSettings(stored: unknown): VideoRenderSettings {
  const merged: VideoRenderSettings = { ...DEFAULT_RENDER_SETTINGS };
  if (!stored || typeof stored !== 'object' || Array.isArray(stored)) return merged;
  for (const [key, validate] of Object.entries(VALIDATORS) as [keyof VideoRenderSettings, Validator][]) {
    if (!(key in stored)) continue;
    const accepted = validate((stored as Record<string, unknown>)[key]);
    if (accepted !== undefined) {
      // Each key is validated in isolation, so one bad value costs only that key.
      (merged as unknown as Record<string, unknown>)[key] = accepted;
    }
  }
  // A blob written before the audio level existed carries only the boolean, so the level is
  // inferred from what was stored rather than taken from the default — otherwise upgrading
  // silently resets the user's saved choice. Both fields are then written together so the
  // level and the legacy boolean can never disagree.
  const storedMode = VALIDATORS.clip_audio_mode((stored as Record<string, unknown>).clip_audio_mode) as
    | ClipAudioChoice
    | undefined;
  const resolved = storedMode ?? (merged.mute_clip_audio ? CLIP_AUDIO_CHOICE_DROP : CLIP_AUDIO_CHOICE_BED);
  merged.clip_audio_mode = resolved;
  merged.mute_clip_audio = muteClipAudioForChoice(resolved);
  return merged;
}

/**
 * Read the saved settings for a project, falling back to the defaults.
 *
 * Unreadable storage and unparseable JSON both fall back silently: the user asked to
 * render, not to hear about a corrupt cache entry, and a thrown error here would take
 * the whole panel down with it.
 */
export function loadRenderSettings(projectId: string | null | undefined): VideoRenderSettings {
  if (!projectId || typeof window === 'undefined') return { ...DEFAULT_RENDER_SETTINGS };
  let raw: string | null = null;
  try {
    raw = window.localStorage.getItem(renderSettingsStorageKey(projectId));
  } catch {
    return { ...DEFAULT_RENDER_SETTINGS };
  }
  if (!raw) return { ...DEFAULT_RENDER_SETTINGS };
  try {
    return mergeStoredRenderSettings(JSON.parse(raw));
  } catch {
    return { ...DEFAULT_RENDER_SETTINGS };
  }
}

/** Persist the settings for a project. Storage being unavailable is not worth an error. */
export function saveRenderSettings(
  projectId: string | null | undefined,
  settings: VideoRenderSettings,
): void {
  if (!projectId || typeof window === 'undefined') return;
  try {
    window.localStorage.setItem(renderSettingsStorageKey(projectId), JSON.stringify(settings));
  } catch {
    // A full or blocked storage just means the choice does not survive the reload.
  }
}
