export const LOCALES = {
  en: { label: "English", flag: "🇺🇸" },
  "zh-CN": { label: "简体中文", flag: "🇨🇳" },
} as const;

export type Locale = keyof typeof LOCALES;

export const DEFAULT_LOCALE: Locale = "en";

export const LOCALE_KEYS = Object.keys(LOCALES) as Locale[];
