"use client";

import { Globe } from "lucide-react";
import { useLocaleStore } from "@/i18n/store";
import { LOCALES, LOCALE_KEYS } from "@/i18n/config";
import type { Locale } from "@/i18n/config";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { Button } from "@/components/ui/button";

export function LanguageSwitcher() {
  const { locale, setLocale } = useLocaleStore();
  const current = LOCALES[locale];

  return (
    <DropdownMenu>
      <DropdownMenuTrigger asChild>
        <Button variant="ghost" size="sm" className="gap-1.5">
          <Globe className="h-4 w-4" />
          <span className="text-sm">{current.flag}</span>
        </Button>
      </DropdownMenuTrigger>
      <DropdownMenuContent align="end">
        {LOCALE_KEYS.map((key) => {
          const loc = LOCALES[key];
          return (
            <DropdownMenuItem
              key={key}
              onClick={() => setLocale(key as Locale)}
              className={locale === key ? "bg-accent" : ""}
            >
              <span className="mr-2">{loc.flag}</span>
              {loc.label}
            </DropdownMenuItem>
          );
        })}
      </DropdownMenuContent>
    </DropdownMenu>
  );
}
