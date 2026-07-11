import i18n from 'i18next';
import LanguageDetector from 'i18next-browser-languagedetector';
import { initReactI18next } from 'react-i18next';
import en from './locales/en/translation.json';
import ja from './locales/ja/translation.json';
import ptBR from './locales/pt-BR/translation.json';
import zhCN from './locales/zh-CN/translation.json';
import zhTW from './locales/zh-TW/translation.json';
import fr from './locales/fr/translation.json';
import vi from './locales/vi/translation.json';

export const SUPPORTED_LANGUAGES = [
  { code: 'vi', label: 'Tiếng Việt' },
  { code: 'en', label: 'English' },
  { code: 'pt-BR', label: 'Português (Brasil)' },
  { code: 'ja', label: '日本語' },
  { code: 'zh-CN', label: '简体中文' },
  { code: 'zh-TW', label: '繁體中文' },
  { code: 'fr', label: 'Français' },
] as const;

export type LanguageCode = (typeof SUPPORTED_LANGUAGES)[number]['code'];

const LANGUAGE_STORAGE_KEY = 'voicebox:lang';
const LANGUAGE_DEFAULTED_KEY = 'voicebox:lang-defaulted';
const DEFAULT_LANGUAGE: LanguageCode = 'vi';

function getInitialLanguage(): LanguageCode {
  if (typeof window === 'undefined') return DEFAULT_LANGUAGE;

  const stored = window.localStorage.getItem(LANGUAGE_STORAGE_KEY);
  const hasDefaultedToVietnamese =
    window.localStorage.getItem(LANGUAGE_DEFAULTED_KEY) === DEFAULT_LANGUAGE;

  if (!hasDefaultedToVietnamese) {
    window.localStorage.setItem(LANGUAGE_STORAGE_KEY, DEFAULT_LANGUAGE);
    window.localStorage.setItem(LANGUAGE_DEFAULTED_KEY, DEFAULT_LANGUAGE);
    return DEFAULT_LANGUAGE;
  }

  if (stored && SUPPORTED_LANGUAGES.some((language) => language.code === stored)) {
    return stored as LanguageCode;
  }

  return DEFAULT_LANGUAGE;
}

i18n
  .use(LanguageDetector)
  .use(initReactI18next)
  .init({
    resources: {
      vi: { translation: vi },
      en: { translation: en },
      'pt-BR': { translation: ptBR },
      ja: { translation: ja },
      'zh-CN': { translation: zhCN },
      'zh-TW': { translation: zhTW },
      fr: { translation: fr },
    },
    lng: getInitialLanguage(),
    fallbackLng: DEFAULT_LANGUAGE,
    supportedLngs: SUPPORTED_LANGUAGES.map((l) => l.code),
    load: 'currentOnly',
    interpolation: { escapeValue: false },
    react: { useSuspense: false },
    detection: {
      order: ['localStorage', 'navigator'],
      lookupLocalStorage: 'voicebox:lang',
      caches: ['localStorage'],
    },
  });

export default i18n;
