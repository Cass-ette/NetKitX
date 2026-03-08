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
  avatar_url?: string | null;
  created_at: string; // ISO datetime string from backend
}

export interface AISettings {
  provider: string;
  api_key_masked: string;
  model: string;
  base_url?: string | null;
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
  event: "text" | "turn" | "action" | "action_status" | "action_result" | "action_error" | "waiting" | "session_start" | "done";
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

// ── Admin Panel Types ───────────────────────────────────────────────

export interface AdminTask {
  id: number;
  plugin_name: string;
  status: "pending" | "running" | "done" | "failed";
  params: Record<string, unknown> | null;
  result: Record<string, unknown> | null;
  created_by: number | null;
  created_by_username: string | null;
  created_at: string;
  started_at: string | null;
  finished_at: string | null;
}

export interface AdminPlugin {
  name: string;
  version: string;
  description: string | null;
  category: string;
  engine: string;
  enabled: boolean;
  usage_count: number;
}

export interface AuditLog {
  id: number;
  user_id: number;
  username: string;
  action: string;
  target_type: string;
  target_id: string | null;
  details: Record<string, unknown> | null;
  created_at: string;
}

export interface UserQuota {
  user_id: number;
  username: string;
  max_concurrent_tasks: number;
  max_daily_tasks: number;
  current_running_tasks: number;
  tasks_today: number;
}

export interface Announcement {
  id: number;
  title: string;
  content: string;
  type: "info" | "warning" | "error";
  active: boolean;
  created_by: number;
  created_at: string;
  updated_at: string;
}

export interface ServiceStatus {
  name: string;
  status: "ok" | "error";
  detail?: string;
}

export interface ServerStatus {
  cpu_percent: number;
  memory_percent: number;
  memory_used_mb: number;
  memory_total_mb: number;
  disk_percent: number;
  disk_used_gb: number;
  disk_total_gb: number;
  services: ServiceStatus[];
}

// ── Knowledge / Session Types ─────────────────────────────────────────

export interface SessionTurn {
  id: number;
  session_id: number;
  turn_number: number;
  role: "user" | "assistant" | "action_result";
  content: string;
  action?: AgentAction | null;
  action_result?: AgentActionResult | null;
  action_status?: string | null;
  created_at: string;
}

export interface AgentSession {
  id: number;
  user_id: number;
  title: string;
  agent_mode: string;
  security_mode: string;
  lang: string;
  total_turns: number;
  status: "active" | "completed" | "failed";
  summary?: string | null;
  created_at: string;
  finished_at?: string | null;
}

export interface AgentSessionDetail extends AgentSession {
  turns: SessionTurn[];
}

export interface SessionListResponse {
  items: AgentSession[];
  total: number;
}

export interface KnowledgeEntry {
  id: number;
  user_id: number;
  session_id?: number | null;
  scenario: string;
  target_type: string;
  vulnerability_type: string;
  tools_used?: string[] | null;
  attack_chain: string;
  outcome: string;
  key_findings: string;
  tags?: string[] | null;
  summary: string;
  learning_report: string;
  extraction_status: string;
  created_at: string;
}
