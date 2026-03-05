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

import zhCN_common from "./locales/zh-CN/common.json";
import zhCN_login from "./locales/zh-CN/login.json";
import zhCN_dashboard from "./locales/zh-CN/dashboard.json";
import zhCN_tools from "./locales/zh-CN/tools.json";
import zhCN_tasks from "./locales/zh-CN/tasks.json";
import zhCN_plugins from "./locales/zh-CN/plugins.json";
import zhCN_marketplace from "./locales/zh-CN/marketplace.json";
import zhCN_topology from "./locales/zh-CN/topology.json";
import zhCN_settings from "./locales/zh-CN/settings.json";

import ja_common from "./locales/ja/common.json";
import ja_login from "./locales/ja/login.json";
import ja_dashboard from "./locales/ja/dashboard.json";
import ja_tools from "./locales/ja/tools.json";
import ja_tasks from "./locales/ja/tasks.json";
import ja_plugins from "./locales/ja/plugins.json";
import ja_marketplace from "./locales/ja/marketplace.json";
import ja_topology from "./locales/ja/topology.json";
import ja_settings from "./locales/ja/settings.json";

import ko_common from "./locales/ko/common.json";
import ko_login from "./locales/ko/login.json";
import ko_dashboard from "./locales/ko/dashboard.json";
import ko_tools from "./locales/ko/tools.json";
import ko_tasks from "./locales/ko/tasks.json";
import ko_plugins from "./locales/ko/plugins.json";
import ko_marketplace from "./locales/ko/marketplace.json";
import ko_topology from "./locales/ko/topology.json";
import ko_settings from "./locales/ko/settings.json";

import de_common from "./locales/de/common.json";
import de_login from "./locales/de/login.json";
import de_dashboard from "./locales/de/dashboard.json";
import de_tools from "./locales/de/tools.json";
import de_tasks from "./locales/de/tasks.json";
import de_plugins from "./locales/de/plugins.json";
import de_marketplace from "./locales/de/marketplace.json";
import de_topology from "./locales/de/topology.json";
import de_settings from "./locales/de/settings.json";

import fr_common from "./locales/fr/common.json";
import fr_login from "./locales/fr/login.json";
import fr_dashboard from "./locales/fr/dashboard.json";
import fr_tools from "./locales/fr/tools.json";
import fr_tasks from "./locales/fr/tasks.json";
import fr_plugins from "./locales/fr/plugins.json";
import fr_marketplace from "./locales/fr/marketplace.json";
import fr_topology from "./locales/fr/topology.json";
import fr_settings from "./locales/fr/settings.json";

import ru_common from "./locales/ru/common.json";
import ru_login from "./locales/ru/login.json";
import ru_dashboard from "./locales/ru/dashboard.json";
import ru_tools from "./locales/ru/tools.json";
import ru_tasks from "./locales/ru/tasks.json";
import ru_plugins from "./locales/ru/plugins.json";
import ru_marketplace from "./locales/ru/marketplace.json";
import ru_topology from "./locales/ru/topology.json";
import ru_settings from "./locales/ru/settings.json";

type Namespace =
  | "common"
  | "login"
  | "dashboard"
  | "tools"
  | "tasks"
  | "plugins"
  | "marketplace"
  | "topology"
  | "settings";

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

  const t = (key: string, params?: Record<string, string | number>): string => {
    const value =
      messages[locale]?.[namespace]?.[key] ??
      messages.en[namespace]?.[key] ??
      key;
    return interpolate(value, params);
  };

  return { t, locale };
}
