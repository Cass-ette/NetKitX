export interface PluginParam {
  name: string;
  label: string;
  type: "string" | "number" | "select" | "boolean";
  required?: boolean;
  default?: unknown;
  options?: string[];
  placeholder?: string;
}

export interface PluginOutput {
  type: "table" | "json" | "terminal" | "chart";
  columns?: { key: string; label: string }[];
}

export interface PluginMeta {
  name: string;
  version: string;
  description: string;
  category: "recon" | "vuln" | "exploit" | "utils";
  engine: "python" | "go" | "cli";
  params: PluginParam[];
  output: PluginOutput;
  enabled?: boolean;
}

export interface Task {
  id: number;
  plugin_name: string;
  status: "pending" | "running" | "done" | "failed";
  params: Record<string, unknown> | null;
  result: Record<string, unknown> | null;
  created_at: string;
  started_at: string | null;
  finished_at: string | null;
}

export interface User {
  id: number;
  username: string;
  email: string;
  role: "admin" | "user";
}

export interface AISettings {
  provider: string;
  api_key_masked: string;
  model: string;
  configured: boolean;
}

export interface ChatMessage {
  role: "user" | "assistant";
  content: string;
  action?: AgentAction;
  actionResult?: AgentActionResult;
  actionStatus?: "proposed" | "executing" | "done" | "skipped";
}

export type AgentMode = "chat" | "semi_auto" | "full_auto" | "terminal";

export interface AgentAction {
  type: "plugin" | "shell";
  plugin?: string;
  command?: string;
  params?: Record<string, string>;
  reason?: string;
  raw?: string;
}

export interface AgentActionResult {
  items?: unknown[];
  logs?: string[];
  stdout?: string;
  stderr?: string;
  exit_code?: number;
  error?: string;
}

export interface AgentSSEEvent {
  event: "text" | "turn" | "action" | "action_status" | "action_result" | "waiting" | "done";
  data: Record<string, unknown>;
}

export interface PluginUpdateInfo {
  plugin_name: string;
  current_version: string;
  latest_version: string;
  changelog?: string;
  published_at: string;
  has_breaking_changes: boolean;
}

export interface UpdateCheckResponse {
  updates_available: number;
  plugins: PluginUpdateInfo[];
}
