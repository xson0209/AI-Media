/**
 * Supported languages for voice generation, per engine.
 *
 * Qwen3-TTS supports 10 languages.
 * LuxTTS is English-only.
 * Chatterbox Multilingual supports 23 languages.
 * Chatterbox Turbo is English-only.
 * Kokoro supports 8 languages.
 */

/** All languages that any engine supports. */
export const ALL_LANGUAGES = {
  ar: 'Tiếng Ả Rập',
  da: 'Tiếng Đan Mạch',
  de: 'Tiếng Đức',
  el: 'Tiếng Hy Lạp',
  en: 'Tiếng Anh',
  es: 'Tiếng Tây Ban Nha',
  fi: 'Tiếng Phần Lan',
  fr: 'Tiếng Pháp',
  he: 'Tiếng Do Thái',
  hi: 'Tiếng Hindi',
  it: 'Tiếng Ý',
  ja: 'Tiếng Nhật',
  ko: 'Tiếng Hàn',
  ms: 'Tiếng Mã Lai',
  nl: 'Tiếng Hà Lan',
  no: 'Tiếng Na Uy',
  pl: 'Tiếng Ba Lan',
  pt: 'Tiếng Bồ Đào Nha',
  ru: 'Tiếng Nga',
  sv: 'Tiếng Thụy Điển',
  sw: 'Tiếng Swahili',
  tr: 'Tiếng Thổ Nhĩ Kỳ',
  vi: 'Tiếng Việt',
  zh: 'Tiếng Trung',
} as const;

export type LanguageCode = keyof typeof ALL_LANGUAGES;

export const QWEN_VIETNAMESE_EXPERIMENTAL_MODEL_SIZE = '1.7B';

/** Per-engine supported language codes. */
export const ENGINE_LANGUAGES: Record<string, readonly LanguageCode[]> = {
  qwen: ['zh', 'en', 'ja', 'ko', 'de', 'fr', 'ru', 'pt', 'es', 'it'],
  luxtts: ['en'],
  chatterbox: [
    'ar',
    'da',
    'de',
    'el',
    'en',
    'es',
    'fi',
    'fr',
    'he',
    'hi',
    'it',
    'ja',
    'ko',
    'ms',
    'nl',
    'no',
    'pl',
    'pt',
    'ru',
    'sv',
    'sw',
    'tr',
    'zh',
  ],
  chatterbox_turbo: ['en'],
  tada: ['en', 'ar', 'zh', 'de', 'es', 'fr', 'it', 'ja', 'pl', 'pt'],
  kokoro: ['en', 'es', 'fr', 'hi', 'it', 'pt', 'ja', 'zh'],
  qwen_custom_voice: ['zh', 'en', 'ja', 'ko', 'de', 'fr', 'ru', 'pt', 'es', 'it'],
} as const;

/** Helper: get language options for a given engine. */
export function getLanguageOptionsForEngine(
  engine: string,
  options: { modelSize?: string; qwenVietnameseExperimental?: boolean } = {},
) {
  let codes = ENGINE_LANGUAGES[engine] ?? ENGINE_LANGUAGES.qwen;
  if (
    engine === 'qwen' &&
    options.modelSize === QWEN_VIETNAMESE_EXPERIMENTAL_MODEL_SIZE &&
    options.qwenVietnameseExperimental
  ) {
    codes = [...codes, 'vi'];
  }
  return codes.map((code) => ({
    value: code,
    label:
      code === 'vi' && engine === 'qwen'
        ? `${ALL_LANGUAGES[code]} (thử nghiệm)`
        : ALL_LANGUAGES[code],
  }));
}

// ── Backwards-compatible exports used elsewhere ──────────────────────
export const SUPPORTED_LANGUAGES = ALL_LANGUAGES;
export const LANGUAGE_CODES = Object.keys(ALL_LANGUAGES) as LanguageCode[];
export const LANGUAGE_OPTIONS = LANGUAGE_CODES.map((code) => ({
  value: code,
  label: ALL_LANGUAGES[code],
}));
