import { useCallback } from "react";
import { useLocaleStore } from "./store";
import type { Locale } from "./config";

import en_common from "./locales/en/common.json";
import en_login from "./locales/en/login.json";
import en_dashboard from "./locales/en/dashboard.json";
import en_tools from "./locales/en/tools.json";
import en_tasks from "./locales/en/tasks.json";
import en_plugins from "./locales/en/plugins.json";
import en_settings from "./locales/en/settings.json";
import en_ai from "./locales/en/ai.json";
import en_knowledge from "./locales/en/knowledge.json";

import zhCN_common from "./locales/zh-CN/common.json";
import zhCN_login from "./locales/zh-CN/login.json";
import zhCN_dashboard from "./locales/zh-CN/dashboard.json";
import zhCN_tools from "./locales/zh-CN/tools.json";
import zhCN_tasks from "./locales/zh-CN/tasks.json";
import zhCN_plugins from "./locales/zh-CN/plugins.json";
import zhCN_settings from "./locales/zh-CN/settings.json";
import zhCN_ai from "./locales/zh-CN/ai.json";
import zhCN_knowledge from "./locales/zh-CN/knowledge.json";

type Namespace =
  | "common"
  | "login"
  | "dashboard"
  | "tools"
  | "tasks"
  | "plugins"
  | "settings"
  | "ai"
  | "knowledge";

type Messages = Record<string, string>;

const messages: Record<Locale, Record<Namespace, Messages>> = {
  en: {
    common: en_common,
    login: en_login,
    dashboard: en_dashboard,
    tools: en_tools,
    tasks: en_tasks,
    plugins: en_plugins,
    settings: en_settings,
    ai: en_ai,
    knowledge: en_knowledge,
  },
  "zh-CN": {
    common: zhCN_common,
    login: zhCN_login,
    dashboard: zhCN_dashboard,
    tools: zhCN_tools,
    tasks: zhCN_tasks,
    plugins: zhCN_plugins,
    settings: zhCN_settings,
    ai: zhCN_ai,
    knowledge: zhCN_knowledge,
  },
};

function interpolate(
  template: string,
  params?: Record<string, string | number>,
): string {
  if (!params) return template;
  return template.replace(/\{\{(\w+)\}\}/g, (_, key) =>
    params[key] !== undefined ? String(params[key]) : `{{${key}}}`,
  );
}

export function useTranslations(namespace: Namespace) {
  const locale = useLocaleStore((s) => s.locale);

  const t = useCallback(
    (key: string, params?: Record<string, string | number>): string => {
      const value =
        messages[locale]?.[namespace]?.[key] ??
        messages.en[namespace]?.[key] ??
        key;
      return interpolate(value, params);
    },
    [locale, namespace],
  );

  return { t, locale };
}
