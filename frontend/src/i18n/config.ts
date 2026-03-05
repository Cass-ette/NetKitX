export const LOCALES = {
  en: { label: "English", flag: "🇺🇸" },
  "zh-CN": { label: "简体中文", flag: "🇨🇳" },
  "zh-TW": { label: "繁體中文", flag: "🇹🇼" },
  ja: { label: "日本語", flag: "🇯🇵" },
  ko: { label: "한국어", flag: "🇰🇷" },
  de: { label: "Deutsch", flag: "🇩🇪" },
  fr: { label: "Français", flag: "🇫🇷" },
  ru: { label: "Русский", flag: "🇷🇺" },
} as const;

export type Locale = keyof typeof LOCALES;

export const DEFAULT_LOCALE: Locale = "en";

export const LOCALE_KEYS = Object.keys(LOCALES) as Locale[];
