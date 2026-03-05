import { create } from "zustand";
import type { Locale } from "./config";
import { DEFAULT_LOCALE } from "./config";

interface LocaleState {
  locale: Locale;
  _hydrated: boolean;
  setLocale: (locale: Locale) => void;
}

export const useLocaleStore = create<LocaleState>((set) => ({
  locale: DEFAULT_LOCALE,
  _hydrated: false,

  setLocale: (locale) => {
    localStorage.setItem("locale", locale);
    document.cookie = `locale=${locale};path=/;max-age=31536000`;
    document.documentElement.lang = locale;
    set({ locale });
  },
}));

// Hydrate from localStorage on client
if (typeof window !== "undefined") {
  const stored = localStorage.getItem("locale") as Locale | null;
  const locale = stored || DEFAULT_LOCALE;
  document.documentElement.lang = locale;
  useLocaleStore.setState({ locale, _hydrated: true });
}
