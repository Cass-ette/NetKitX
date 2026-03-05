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
}
