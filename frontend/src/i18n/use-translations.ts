import { useCallback } from "react";
import { useLocaleStore } from "./store";
import type { Locale } from "./config";

import en_common from "./locales/en/common.json";
import en_login from "./locales/en/login.json";
import en_dashboard from "./locales/en/dashboard.json";
import en_tools from "./locales/en/tools.json";
import en_tasks from "./locales/en/tasks.json";
import en_plugins from "./locales/en/plugins.json";
import en_marketplace from "./locales/en/marketplace.json";
import en_topology from "./locales/en/topology.json";
import en_settings from "./locales/en/settings.json";
import en_ai from "./locales/en/ai.json";
import en_admin from "./locales/en/admin.json";
import en_developers from "./locales/en/developers.json";
import en_knowledge from "./locales/en/knowledge.json";

import zhCN_common from "./locales/zh-CN/common.json";
import zhCN_login from "./locales/zh-CN/login.json";
import zhCN_dashboard from "./locales/zh-CN/dashboard.json";
import zhCN_tools from "./locales/zh-CN/tools.json";
import zhCN_tasks from "./locales/zh-CN/tasks.json";
import zhCN_plugins from "./locales/zh-CN/plugins.json";
import zhCN_marketplace from "./locales/zh-CN/marketplace.json";
import zhCN_topology from "./locales/zh-CN/topology.json";
import zhCN_settings from "./locales/zh-CN/settings.json";
import zhCN_ai from "./locales/zh-CN/ai.json";
import zhCN_admin from "./locales/zh-CN/admin.json";
import zhCN_developers from "./locales/zh-CN/developers.json";
import zhCN_knowledge from "./locales/zh-CN/knowledge.json";

import zhTW_common from "./locales/zh-TW/common.json";
import zhTW_login from "./locales/zh-TW/login.json";
import zhTW_dashboard from "./locales/zh-TW/dashboard.json";
import zhTW_tools from "./locales/zh-TW/tools.json";
import zhTW_tasks from "./locales/zh-TW/tasks.json";
import zhTW_plugins from "./locales/zh-TW/plugins.json";
import zhTW_marketplace from "./locales/zh-TW/marketplace.json";
import zhTW_topology from "./locales/zh-TW/topology.json";
import zhTW_settings from "./locales/zh-TW/settings.json";
import zhTW_ai from "./locales/zh-TW/ai.json";
import zhTW_admin from "./locales/zh-TW/admin.json";
import zhTW_developers from "./locales/zh-TW/developers.json";
import zhTW_knowledge from "./locales/zh-TW/knowledge.json";

import ja_common from "./locales/ja/common.json";
import ja_login from "./locales/ja/login.json";
import ja_dashboard from "./locales/ja/dashboard.json";
import ja_tools from "./locales/ja/tools.json";
import ja_tasks from "./locales/ja/tasks.json";
import ja_plugins from "./locales/ja/plugins.json";
import ja_marketplace from "./locales/ja/marketplace.json";
import ja_topology from "./locales/ja/topology.json";
import ja_settings from "./locales/ja/settings.json";
import ja_ai from "./locales/ja/ai.json";
import ja_admin from "./locales/ja/admin.json";
import ja_developers from "./locales/ja/developers.json";
import ja_knowledge from "./locales/ja/knowledge.json";

import ko_common from "./locales/ko/common.json";
import ko_login from "./locales/ko/login.json";
import ko_dashboard from "./locales/ko/dashboard.json";
import ko_tools from "./locales/ko/tools.json";
import ko_tasks from "./locales/ko/tasks.json";
import ko_plugins from "./locales/ko/plugins.json";
import ko_marketplace from "./locales/ko/marketplace.json";
import ko_topology from "./locales/ko/topology.json";
import ko_settings from "./locales/ko/settings.json";
import ko_ai from "./locales/ko/ai.json";
import ko_admin from "./locales/ko/admin.json";
import ko_developers from "./locales/ko/developers.json";
import ko_knowledge from "./locales/ko/knowledge.json";

import de_common from "./locales/de/common.json";
import de_login from "./locales/de/login.json";
import de_dashboard from "./locales/de/dashboard.json";
import de_tools from "./locales/de/tools.json";
import de_tasks from "./locales/de/tasks.json";
import de_plugins from "./locales/de/plugins.json";
import de_marketplace from "./locales/de/marketplace.json";
import de_topology from "./locales/de/topology.json";
import de_settings from "./locales/de/settings.json";
import de_ai from "./locales/de/ai.json";
import de_admin from "./locales/de/admin.json";
import de_developers from "./locales/de/developers.json";
import de_knowledge from "./locales/de/knowledge.json";

import fr_common from "./locales/fr/common.json";
import fr_login from "./locales/fr/login.json";
import fr_dashboard from "./locales/fr/dashboard.json";
import fr_tools from "./locales/fr/tools.json";
import fr_tasks from "./locales/fr/tasks.json";
import fr_plugins from "./locales/fr/plugins.json";
import fr_marketplace from "./locales/fr/marketplace.json";
import fr_topology from "./locales/fr/topology.json";
import fr_settings from "./locales/fr/settings.json";
import fr_ai from "./locales/fr/ai.json";
import fr_admin from "./locales/fr/admin.json";
import fr_developers from "./locales/fr/developers.json";
import fr_knowledge from "./locales/fr/knowledge.json";

import ru_common from "./locales/ru/common.json";
import ru_login from "./locales/ru/login.json";
import ru_dashboard from "./locales/ru/dashboard.json";
import ru_tools from "./locales/ru/tools.json";
import ru_tasks from "./locales/ru/tasks.json";
import ru_plugins from "./locales/ru/plugins.json";
import ru_marketplace from "./locales/ru/marketplace.json";
import ru_topology from "./locales/ru/topology.json";
import ru_settings from "./locales/ru/settings.json";
import ru_ai from "./locales/ru/ai.json";
import ru_admin from "./locales/ru/admin.json";
import ru_developers from "./locales/ru/developers.json";
import ru_knowledge from "./locales/ru/knowledge.json";

type Namespace =
  | "common"
  | "login"
  | "dashboard"
  | "tools"
  | "tasks"
  | "plugins"
  | "marketplace"
  | "topology"
  | "settings"
  | "ai"
  | "admin"
  | "developers"
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
    marketplace: en_marketplace,
    topology: en_topology,
    settings: en_settings,
    ai: en_ai,
    admin: en_admin,
    developers: en_developers,
    knowledge: en_knowledge,
  },
  "zh-CN": {
    common: zhCN_common,
    login: zhCN_login,
    dashboard: zhCN_dashboard,
    tools: zhCN_tools,
    tasks: zhCN_tasks,
    plugins: zhCN_plugins,
    marketplace: zhCN_marketplace,
    topology: zhCN_topology,
    settings: zhCN_settings,
    ai: zhCN_ai,
    admin: zhCN_admin,
    developers: zhCN_developers,
    knowledge: zhCN_knowledge,
  },
  "zh-TW": {
    common: zhTW_common,
    login: zhTW_login,
    dashboard: zhTW_dashboard,
    tools: zhTW_tools,
    tasks: zhTW_tasks,
    plugins: zhTW_plugins,
    marketplace: zhTW_marketplace,
    topology: zhTW_topology,
    settings: zhTW_settings,
    ai: zhTW_ai,
    admin: zhTW_admin,
    developers: zhTW_developers,
    knowledge: zhTW_knowledge,
  },
  ja: {
    common: ja_common,
    login: ja_login,
    dashboard: ja_dashboard,
    tools: ja_tools,
    tasks: ja_tasks,
    plugins: ja_plugins,
    marketplace: ja_marketplace,
    topology: ja_topology,
    settings: ja_settings,
    ai: ja_ai,
    admin: ja_admin,
    developers: ja_developers,
    knowledge: ja_knowledge,
  },
  ko: {
    common: ko_common,
    login: ko_login,
    dashboard: ko_dashboard,
    tools: ko_tools,
    tasks: ko_tasks,
    plugins: ko_plugins,
    marketplace: ko_marketplace,
    topology: ko_topology,
    settings: ko_settings,
    ai: ko_ai,
    admin: ko_admin,
    developers: ko_developers,
    knowledge: ko_knowledge,
  },
  de: {
    common: de_common,
    login: de_login,
    dashboard: de_dashboard,
    tools: de_tools,
    tasks: de_tasks,
    plugins: de_plugins,
    marketplace: de_marketplace,
    topology: de_topology,
    settings: de_settings,
    ai: de_ai,
    admin: de_admin,
    developers: de_developers,
    knowledge: de_knowledge,
  },
  fr: {
    common: fr_common,
    login: fr_login,
    dashboard: fr_dashboard,
    tools: fr_tools,
    tasks: fr_tasks,
    plugins: fr_plugins,
    marketplace: fr_marketplace,
    topology: fr_topology,
    settings: fr_settings,
    ai: fr_ai,
    admin: fr_admin,
    developers: fr_developers,
    knowledge: fr_knowledge,
  },
  ru: {
    common: ru_common,
    login: ru_login,
    dashboard: ru_dashboard,
    tools: ru_tools,
    tasks: ru_tasks,
    plugins: ru_plugins,
    marketplace: ru_marketplace,
    topology: ru_topology,
    settings: ru_settings,
    ai: ru_ai,
    admin: ru_admin,
    developers: ru_developers,
    knowledge: ru_knowledge,
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
