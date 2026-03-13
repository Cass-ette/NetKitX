"""AI Agent service: plugin catalog, action parsing, agent loop."""

import json
import logging
import re
from collections.abc import AsyncIterator
from difflib import SequenceMatcher
from typing import Any

from app.core.config import settings
from app.plugins.registry import registry
from app.services.ai_service import (
    get_system_prompt,
    get_lang_reminder,
    stream_claude,
    stream_deepseek,
    stream_glm,
    stream_openai_compatible,
)

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Plugin catalog generation
# ---------------------------------------------------------------------------


def build_plugin_catalog() -> str:
    """Build a text catalog of all enabled plugins for the system prompt."""
    plugins = registry.list_enabled()
    if not plugins:
        return "No plugins available."

    lines = ["## Available Plugins\n"]
    for meta in plugins:
        lines.append(f"### {meta.name} (v{meta.version})")
        lines.append(f"Category: {meta.category} | Engine: {meta.engine}")
        lines.append(f"Description: {meta.description}")
        if meta.params:
            lines.append("Parameters:")
            for p in meta.params:
                req = " (required)" if p.get("required") else ""
                default = f" [default: {p.get('default')}]" if "default" in p else ""
                lines.append(f"  - {p['name']}: {p.get('type', 'string')}{req}{default}")
                if p.get("placeholder"):
                    lines.append(f"    hint: {p['placeholder']}")
                if p.get("options"):
                    lines.append(f"    options: {', '.join(p['options'])}")
        lines.append("")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Agent system prompts
# ---------------------------------------------------------------------------

AGENT_INSTRUCTION_SEMI_AUTO = """
## Agent Mode: Semi-Auto
You are an AI agent that can propose actions for the user to approve.
When you want to run a plugin or command, output an action block using XML tags:

<action type="plugin">
  <plugin>plugin-name</plugin>
  <params>
    <param name="key">value</param>
  </params>
  <reason>Why you want to run this</reason>
</action>

Only propose ONE action at a time. After the action, the user will decide to execute or skip.
You will receive the result and can then propose the next action.
"""

AGENT_INSTRUCTION_FULL_AUTO = """
## Agent Mode: Full-Auto (Plugin Only)
You are an autonomous AI agent that automatically executes plugins.
Output action blocks to run plugins — they will be executed automatically.

<action type="plugin">
  <plugin>plugin-name</plugin>
  <params>
    <param name="key">value</param>
  </params>
  <reason>Why you want to run this</reason>
</action>

IMPORTANT: You can ONLY use type="plugin". Shell commands are NOT allowed in this mode.

### Parallel Execution
When multiple independent actions can run at the same time, you SHOULD include multiple <action>
blocks in a single response. This saves turns and completes tasks faster. Examples:
- After recon reveals multiple services → scan each service in parallel
- Testing multiple injection types → run them simultaneously
- Checking multiple endpoints → probe all at once

Only execute sequentially when one action's result is needed to decide the next.

When your analysis is complete or no further actions are needed, respond without an action block.
"""

AGENT_INSTRUCTION_TERMINAL = """
## Agent Mode: Terminal (Plugins + Shell)
You are an autonomous AI agent that can execute plugins and shell commands.

Use the right tool for the job:
- **Plugins** return structured JSON — ideal for standard scans (port scan, dir scan, SQL injection tests).
- **Shell commands** offer full flexibility — ideal for custom payloads, command chaining, and anything plugins don't cover.
Check the Available Plugins list for built-in capabilities, but use shell freely when you need more control.

To use a plugin:

<action type="plugin">
  <plugin>plugin-name</plugin>
  <params>
    <param name="key">value</param>
  </params>
  <reason>Why you want to run this</reason>
</action>

To run a shell command:

<action type="shell">
  <command>your command here</command>
  <reason>Why you want to run this</reason>
</action>

When multiple independent actions can run at the same time, you SHOULD include multiple <action>
blocks in a single response. This saves turns and completes tasks faster. For example:

<action type="shell">
  <command>curl -s http://target/api/users</command>
  <reason>Check users endpoint</reason>
</action>
<action type="shell">
  <command>curl -s http://target/api/admin</command>
  <reason>Check admin endpoint</reason>
</action>

Good candidates for parallel execution:
- Testing multiple injection payloads on the same endpoint
- Scanning different ports or services simultaneously
- Probing multiple endpoints or URLs at once
- Running different recon tools that don't depend on each other

Only execute sequentially when one action's result is needed to decide the next.
When your analysis is complete, respond without an action block.
"""

_AGENT_ERROR_HANDLING = """
## Error Handling
If an action fails, you will receive an error message in the format [Action Failed: ...].
When this happens:
- Analyze the error message carefully before retrying.
- If a plugin was not found, check the Available Plugins list and use the exact name.
- If parameters were wrong, review the plugin's parameter requirements and correct them.
- Try a different approach, different plugin, or different parameters.
- Do NOT repeat the exact same action that just failed.
- If you have failed multiple consecutive times, continue analysis in plain text.
"""

_AGENT_STRATEGY = """
## Strategy
- RIGHT TOOL: Use plugins for standard scans (structured data, fewer tokens). Use shell for custom payloads, chaining, or when plugins don't fit. Don't force a plugin where a curl one-liner would be simpler.
- RECON FIRST: Before attacking, map the environment (OS, versions, services, technologies).
- OBSERVE, DON'T ASSUME: Infer database type, framework, and config from error messages, response headers, and behavioral differences. If clues are already visible, act on them immediately — don't waste turns on redundant fingerprinting. When truly unknown, test with version()/@@version/sqlite_version() to confirm.
- VALIDATE EXTRACTION: After each data extraction attempt, check whether YOUR injected data actually appears in the response. If the output looks the same as before or shows values other than what you injected, the extraction technique isn't working as expected. Diagnose WHY: maybe legitimate results mask your injected data, maybe the app doesn't reflect output at all. Adjust accordingly.
- ACT, DON'T REPORT: Maximize action density — include an action block in every response unless you've achieved the goal. Keep analysis brief (2-3 sentences). NEVER write a summary report or "recommended next steps" when you still have turns left. Your job is to DO the work, not plan it for a human.
- PARALLELIZE: When you have 2+ independent actions (e.g., different payloads, different endpoints, different tools), include ALL of them as separate <action> blocks in the SAME response. This halves the turns needed. Sequential only when results depend on each other.
- FILTER REPEATED QUERIES: When querying the same endpoint repeatedly, pipe output through grep/sed/cut to isolate the meaningful difference. Sending identical boilerplate wastes context.
- SAME APPROACH 3 TIMES MAX: If an approach fails 3 times, switch to a completely different technique.
- MONITOR YOUR OWN THINKING: If you catch yourself repeating similar reasoning (e.g., "let me try another upload endpoint", "let me look for another file upload path"), STOP. You are stuck in a strategic loop. Step back and ask: "What fundamentally different attack vector have I NOT tried?" Switch to a different vulnerability class entirely (e.g., from file upload to SQL injection, from brute-force to logic flaw, from client-side to server-side). Trying the same strategy with different URLs is NOT progress.
- MULTI-LAYER ENCODING: When data passes through multiple layers (shell → curl → HTTP → eval), use base64 or chr() to avoid escaping issues.
- VERIFY EACH STEP: If a command returns no useful output, verify each step individually with the simplest possible command before adding complexity.
- RECOGNIZE TARGET DATA: Learn to identify what you're looking for. CTF flags match the pattern `word{...}` (e.g. flag{xx}, CTF{xx}, any_prefix{xx}). Credentials are username/password pairs, API keys (sk-..., key-..., Bearer tokens), or session tokens. Sensitive files include /etc/shadow, .env, config files with secrets, database dumps. When ANY of these appear in a response, you have found the target.
- KNOW WHEN TO STOP: When you find the target data, IMMEDIATELY present it and stop. Do NOT continue testing or "verify" the same finding again. State the result clearly and end without an action block.
"""

_AGENT_INSTRUCTIONS = {
    "semi_auto": AGENT_INSTRUCTION_SEMI_AUTO,
    "full_auto": AGENT_INSTRUCTION_FULL_AUTO,
    "terminal": AGENT_INSTRUCTION_TERMINAL,
}


def get_agent_system_prompt(agent_mode: str, security_mode: str, lang: str) -> str:
    """Compose full system prompt: language + security + agent instructions + error handling + plugin catalog."""
    base = get_system_prompt(security_mode, lang)
    agent_inst = _AGENT_INSTRUCTIONS.get(agent_mode, "")
    catalog = build_plugin_catalog()
    return f"{base}\n\n{agent_inst}\n\n{_AGENT_ERROR_HANDLING}\n\n{_AGENT_STRATEGY}\n\n{catalog}"


# ---------------------------------------------------------------------------
# Action parsing (regex-based, tolerates XML-unfriendly content like <?php, &, >)
# ---------------------------------------------------------------------------

_ACTION_RE = re.compile(r"<action\s[^>]*>.*?</action>", re.DOTALL)
_TYPE_RE = re.compile(r'<action\s[^>]*type\s*=\s*["\'](\w+)["\']')
_TAG_RE = {
    "plugin": re.compile(r"<plugin>(.*?)</plugin>", re.DOTALL),
    "command": re.compile(r"<command>(.*?)</command>", re.DOTALL),
    "reason": re.compile(r"<reason>(.*?)</reason>", re.DOTALL),
    "params": re.compile(r"<params>(.*?)</params>", re.DOTALL),
    "param": re.compile(r'<param\s+name\s*=\s*["\']([^"\']+)["\']>(.*?)</param>', re.DOTALL),
}


def _parse_single_block(block: str) -> dict[str, Any] | None:
    """Parse a single <action>...</action> block into an action dict."""
    type_match = _TYPE_RE.search(block)
    if not type_match:
        return None

    action_type = type_match.group(1)
    result: dict[str, Any] = {"type": action_type, "raw": block}

    if action_type == "plugin":
        m = _TAG_RE["plugin"].search(block)
        result["plugin"] = m.group(1).strip() if m else ""
        params: dict[str, str] = {}
        for pm in _TAG_RE["param"].finditer(block):
            name = pm.group(1).strip()
            value = pm.group(2).strip()
            if name:
                params[name] = value
        result["params"] = params
    elif action_type == "shell":
        m = _TAG_RE["command"].search(block)
        result["command"] = m.group(1).strip() if m else ""

    m = _TAG_RE["reason"].search(block)
    result["reason"] = m.group(1).strip() if m else ""

    return result


def parse_actions(text: str) -> list[dict[str, Any]]:
    """Extract ALL <action> blocks from AI text. Returns list (may be empty)."""
    results = []
    for match in _ACTION_RE.finditer(text):
        action = _parse_single_block(match.group(0))
        if action:
            results.append(action)
    return results


def parse_action(text: str) -> dict[str, Any] | None:
    """Extract the first <action> block from AI text using regex (no strict XML parsing)."""
    actions = parse_actions(text)
    return actions[0] if actions else None


def strip_action_tags(text: str) -> str:
    """Remove <action>...</action> blocks from AI text for display."""
    return _ACTION_RE.sub("", text).strip()


_ACTION_ATTEMPT_RE = re.compile(r"<action[\s>]", re.IGNORECASE)


def has_action_attempt(text: str) -> bool:
    """Check if text looks like a failed action attempt (malformed XML)."""
    return bool(_ACTION_ATTEMPT_RE.search(text))


# ---------------------------------------------------------------------------
# Shell command preprocessing
# ---------------------------------------------------------------------------

_CURL_RE = re.compile(r"\bcurl\b")
_CURL_SILENT_RE = re.compile(r"\bcurl\s+.*-[a-zA-Z]*s")


def _preprocess_shell_command(command: str) -> str:
    """Add -s (silent) to curl commands to suppress noisy progress output."""
    if "curl" not in command:
        return command
    # Skip if any curl invocation already has -s flag
    if _CURL_SILENT_RE.search(command):
        return command
    return _CURL_RE.sub("curl -s", command)


# ---------------------------------------------------------------------------
# Plugin execution (synchronous wait for result)
# ---------------------------------------------------------------------------


async def execute_plugin_action(action: dict[str, Any]) -> dict[str, Any]:
    """Execute a plugin action and return the result."""
    plugin_name = action.get("plugin", "")
    params = action.get("params", {})

    plugin = registry.get(plugin_name)
    if not plugin:
        return {"error": f"Plugin '{plugin_name}' not found or not enabled"}

    if not registry.is_enabled(plugin_name):
        return {"error": f"Plugin '{plugin_name}' is disabled"}

    results: list[dict] = []
    logs: list[str] = []
    try:
        async for event in plugin.execute(params):
            if event.type == "result":
                results.append(event.data)
            elif event.type == "log":
                logs.append(event.data.get("message", str(event.data)))
            elif event.type == "error":
                return {"error": event.data.get("message", str(event.data))}
    except Exception as e:
        return {"error": str(e)}

    return {"items": results, "logs": logs}


# ---------------------------------------------------------------------------
# Output compression (clean result before injecting into conversation)
# ---------------------------------------------------------------------------

_HTML_TAG_RE = re.compile(r"<[^>]+>")
_ANSI_RE = re.compile(r"\x1b\[[0-9;]*[a-zA-Z]")
_BLANK_LINES_RE = re.compile(r"\n{3,}")
_WHITESPACE_LINES_RE = re.compile(r"\n[ \t]+\n")

# Tags whose attributes are security-relevant (preserve as [tag attr=val] text)
_SEC_ATTR_RE = re.compile(
    r"<(form|input|a|iframe|meta|img|button|select|option|textarea)\s+([^>]*)>",
    re.IGNORECASE,
)
_ATTR_PAIR_RE = re.compile(r'(\w+)\s*=\s*["\']([^"\']*)["\']')

# Small inline scripts (< threshold) may contain tokens/endpoints — keep them.
# Large scripts (bundled JS, libraries) are noise — strip them.
_SCRIPT_RE = re.compile(r"<script[^>]*>(.*?)</script>", re.DOTALL | re.IGNORECASE)
_SCRIPT_KEEP_THRESHOLD = 1000  # chars

# Max chars to keep from a single stdout/stderr field before smart truncation
_FIELD_MAX = 12000
_FIELD_HEAD = 5000
_FIELD_TAIL = 5000


def _preserve_sec_attrs(match: re.Match) -> str:
    """Convert security-relevant HTML tags to compact [tag attr=val] text."""
    tag = match.group(1).lower()
    attrs_str = match.group(2)
    pairs = _ATTR_PAIR_RE.findall(attrs_str)
    if pairs:
        attr_text = " ".join(f"{k}={v}" for k, v in pairs)
        return f"[{tag} {attr_text}]"
    return ""


def _strip_html(text: str) -> str:
    """Remove HTML tags, preserve security-relevant content.

    - Keeps small inline <script> bodies (may contain tokens, endpoints, secrets)
    - Strips large <script> blocks (bundled JS / library noise)
    - Extracts attributes from form/input/a/iframe/meta tags
    - Strips <style> blocks and purely presentational tags
    """
    # Strip style blocks (CSS is noise for security analysis)
    text = re.sub(r"<style[^>]*>.*?</style>", "", text, flags=re.DOTALL | re.IGNORECASE)

    # Keep small inline scripts, strip large ones (bundled JS is noise)
    def _handle_script(m: re.Match) -> str:
        content = m.group(1).strip()
        return content if len(content) <= _SCRIPT_KEEP_THRESHOLD else ""

    text = _SCRIPT_RE.sub(_handle_script, text)
    # Extract security-relevant tag attributes before stripping
    text = _SEC_ATTR_RE.sub(_preserve_sec_attrs, text)
    # Strip remaining tags
    text = _HTML_TAG_RE.sub("", text)
    # Decode common HTML entities
    for entity, char in [
        ("&amp;", "&"),
        ("&lt;", "<"),
        ("&gt;", ">"),
        ("&quot;", '"'),
        ("&#39;", "'"),
        ("&nbsp;", " "),
    ]:
        text = text.replace(entity, char)
    return text


def _compress_output(text: str) -> str:
    """Clean and compress command output for token efficiency."""
    if not text:
        return text
    # Strip ANSI color codes
    text = _ANSI_RE.sub("", text)
    # Strip HTML if detected
    if "<html" in text.lower() or "<body" in text.lower() or "<div" in text.lower():
        text = _strip_html(text)
    # Collapse excessive blank lines
    text = _WHITESPACE_LINES_RE.sub("\n\n", text)
    text = _BLANK_LINES_RE.sub("\n\n", text)
    text = text.strip()
    # Smart truncation: keep head + tail, cut middle
    if len(text) > _FIELD_MAX:
        head = text[:_FIELD_HEAD]
        tail = text[-_FIELD_TAIL:]
        cut = len(text) - _FIELD_HEAD - _FIELD_TAIL
        text = f"{head}\n\n...[{cut} chars omitted]...\n\n{tail}"
    return text


def compress_result(result: dict[str, Any]) -> dict[str, Any]:
    """Compress stdout/stderr in a shell result dict."""
    out = dict(result)
    if "stdout" in out and isinstance(out["stdout"], str):
        out["stdout"] = _compress_output(out["stdout"])
    if "stderr" in out and isinstance(out["stderr"], str):
        out["stderr"] = _compress_output(out["stderr"])
    return out


# ---------------------------------------------------------------------------
# Format result for conversation injection
# ---------------------------------------------------------------------------

MAX_RESULT_CHARS = 20000


def format_action_result(action: dict[str, Any], result: dict[str, Any]) -> str:
    """Format an action result as text to inject into the conversation."""
    action_type = action.get("type", "")
    if action_type == "plugin":
        header = f"[Plugin Result: {action.get('plugin', '?')}]"
    elif action_type == "shell":
        header = f"[Shell Result: {action.get('command', '?')[:80]}]"
    else:
        header = "[Action Result]"

    # Compress output before serialization
    compressed = compress_result(result)
    result_str = json.dumps(compressed, default=str, ensure_ascii=False)
    if len(result_str) > MAX_RESULT_CHARS:
        result_str = result_str[:MAX_RESULT_CHARS] + "...(truncated)"

    return f"{header}\n{result_str}"


# ---------------------------------------------------------------------------
# Error classification
# ---------------------------------------------------------------------------

MAX_CONSECUTIVE_ERRORS = 3

_FATAL_ERROR_PATTERNS = [
    "Unknown action type:",
    "Shell commands only allowed",
]


def classify_error(error: str) -> str:
    """Classify an action error as 'fatal' or 'retryable'."""
    for pattern in _FATAL_ERROR_PATTERNS:
        if pattern in error:
            return "fatal"
    return "retryable"


# ---------------------------------------------------------------------------
# Stagnation detection (semantic loop breaker)
# ---------------------------------------------------------------------------

STAGNATION_SIMILARITY = 0.85  # two actions >85% similar = "same approach"
STAGNATION_WARN = 5  # inject soft warning
STAGNATION_FORCE = 8  # inject hard warning
STAGNATION_STOP = 12  # terminate


def _normalize_shell_fingerprint(command: str) -> str:
    """Reduce a shell command to its semantically meaningful parts.

    For curl/wget commands the shared URL base (scheme + host + port) is
    stripped so that requests to *different* paths are not falsely flagged
    as repetition.  POST data, HTTP method and key headers are kept.
    """
    cmd = command.strip()

    # --- curl ---
    if re.match(r"curl\b", cmd):
        parts: list[str] = []
        # URL path (strip scheme + host)
        url_m = re.search(r"https?://[^/\s\"']+(/[^\s\"']*)", cmd)
        parts.append(url_m.group(1) if url_m else "/")
        # HTTP method
        method_m = re.search(r"-X\s+(\w+)", cmd)
        if method_m:
            parts.append(method_m.group(1))
        # POST data (first 120 chars)
        data_m = re.search(r"(?:--data|-d)\s+[\"']?(.{0,120})", cmd)
        if data_m:
            parts.append(data_m.group(1))
        # Important headers (Cookie, Content-Type, Authorization, User-Agent injection)
        for hdr in re.findall(r"-H\s+[\"']([^\"']{0,80})", cmd):
            parts.append(hdr)
        return "curl:" + "|".join(parts)

    # --- wget ---
    if re.match(r"wget\b", cmd):
        url_m = re.search(r"https?://[^/\s\"']+(/[^\s\"']*)", cmd)
        return "wget:" + (url_m.group(1) if url_m else "/")

    # --- sqlmap ---
    if re.match(r"sqlmap\b", cmd):
        url_m = re.search(r'-u\s+["\']?https?://[^/\s"\']+(/[^\s"\']*)', cmd)
        path = url_m.group(1) if url_m else ""
        level_m = re.search(r"--level[= ](\d+)", cmd)
        tech_m = re.search(r"--technique[= ](\S+)", cmd)
        return f"sqlmap:{path}|{level_m and level_m.group(1)}|{tech_m and tech_m.group(1)}"

    # --- everything else: return as-is ---
    return cmd


def _action_fingerprint(action: dict[str, Any]) -> str:
    """Extract a comparable fingerprint from an action dict."""
    atype = action.get("type", "")
    if atype == "shell":
        return f"shell:{_normalize_shell_fingerprint(action.get('command', ''))}"
    elif atype == "plugin":
        params_str = json.dumps(action.get("params", {}), sort_keys=True)
        return f"plugin:{action.get('plugin', '')}:{params_str}"
    return ""


_FP_TYPE_PREFIX = re.compile(r"^(?:shell|plugin):")


def _is_similar(a: str, b: str) -> bool:
    """Check if two fingerprints are similar enough to count as repetition.

    Strips the ``shell:`` / ``plugin:`` type prefix before comparing so the
    similarity ratio reflects the *meaningful* payload, not the shared prefix.
    """
    if not a or not b:
        return False
    a_core = _FP_TYPE_PREFIX.sub("", a)
    b_core = _FP_TYPE_PREFIX.sub("", b)
    return SequenceMatcher(None, a_core, b_core).ratio() >= STAGNATION_SIMILARITY


def count_similar_recent(history: list[str], current: str) -> int:
    """Count how many recent actions are similar to the current one."""
    return sum(1 for h in history if _is_similar(h, current))


# ---------------------------------------------------------------------------
# Reasoning-level stagnation (catches "same strategy, different URLs")
# ---------------------------------------------------------------------------

_ACTION_TAG_RE = re.compile(r"<action[\s\S]*?</action>", re.DOTALL)

REASONING_SIMILARITY = 0.80  # reasoning text similarity threshold
REASONING_STAGNATION_WARN = 3  # consecutive similar reasoning → soft warning
REASONING_STAGNATION_STOP = 5  # consecutive similar reasoning → terminate


def _extract_reasoning(text: str) -> str:
    """Extract the reasoning portion of an assistant message (strip action XML)."""
    cleaned = _ACTION_TAG_RE.sub("", text).strip()
    # Take first 200 chars — enough to capture the strategy statement
    return cleaned[:200].lower()


def _reasoning_stagnation(history: list[str], current: str) -> int:
    """Count consecutive similar reasoning texts from the end of history."""
    if not current:
        return 0
    count = 0
    for prev in reversed(history):
        if SequenceMatcher(None, prev, current).ratio() >= REASONING_SIMILARITY:
            count += 1
        else:
            break  # must be consecutive
    return count


# Negative-result patterns (case-insensitive substrings)
_NEGATIVE_PATTERNS = [
    "404",
    "not found",
    "unexpected path",
    "error:",
    "forbidden",
    "unauthorized",
    "denied",
    "no such",
    "refused",
    "cannot ",
    "failed to",
    "invalid",
    "405 method not allowed",
]
_POSITIVE_PATTERNS = [
    "flag{",
    "ctf{",
    "password",
    "token",
    "admin",
    "success",
    "logged in",
    "session",
    "secret",
    "key=",
    "api_key",
]


def _results_look_negative(combined_result: str) -> bool:
    """Heuristic: check if action results indicate no meaningful progress.

    Returns True when results contain only error/404-like signals and
    nothing that looks like newly discovered data.
    """
    if not combined_result:
        return True
    lower = combined_result.lower()
    has_positive = any(p in lower for p in _POSITIVE_PATTERNS)
    if has_positive:
        return False
    has_negative = any(p in lower for p in _NEGATIVE_PATTERNS)
    return has_negative


# ---------------------------------------------------------------------------
# Main agent loop
# ---------------------------------------------------------------------------


async def run_agent_loop(
    *,
    provider: str,
    api_key: str,
    model: str,
    messages: list[dict[str, str]],
    agent_mode: str,
    security_mode: str,
    lang: str,
    max_turns: int,
    confirm_action: dict | None = None,
    user_id: int | None = None,
    is_admin: bool = False,
    user_token: str | None = None,
    base_url: str | None = None,
    session_id: int | str | None = None,
) -> AsyncIterator[dict]:
    """
    Main agent loop generator. Yields SSE event dicts.

    For semi_auto: yields one AI response, parses action, yields waiting event, then stops.
    For full_auto/terminal: loops up to max_turns, auto-executing actions.
    """
    system_prompt = get_agent_system_prompt(agent_mode, security_mode, lang)
    lang_reminder = get_lang_reminder(lang)

    # RAG: inject related historical knowledge into system prompt
    if settings.RAG_ENABLED and user_id:
        user_query = next((m["content"] for m in messages if m["role"] == "user"), "")
        if user_query:
            try:
                from app.services.embedding_service import search_and_format_knowledge

                rag_context = await search_and_format_knowledge(user_query, user_id, lang)
                if rag_context:
                    system_prompt += f"\n\n{rag_context}"
            except Exception:
                logger.warning("RAG context injection failed, continuing without it")

    # If this is a confirm_action continuation (Mode A), execute and inject result
    if confirm_action is not None:
        action = confirm_action.get("action", {}) if isinstance(confirm_action, dict) else {}
        approved = (
            confirm_action.get("approved", False) if isinstance(confirm_action, dict) else False
        )

        if approved and action:
            yield {"event": "action_status", "data": {"status": "executing", "action": action}}
            result = await _execute_action(action, agent_mode, user_id, is_admin, user_token)
            yield {"event": "action_result", "data": {"result": result, "action": action}}
            # Inject result into messages
            result_text = format_action_result(action, result)
            messages.append({"role": "user", "content": result_text})
        else:
            # User skipped — inject skip note
            messages.append(
                {
                    "role": "user",
                    "content": "[User skipped the proposed action. Continue analysis.]",
                }
            )

    # Build full message list with system prompt
    full_messages = [{"role": "system", "content": system_prompt}]
    for msg in messages:
        content = msg["content"]
        if msg["role"] == "user" and lang_reminder:
            content += lang_reminder
        full_messages.append({"role": msg["role"], "content": content})

    turn = 0
    consecutive_errors = 0
    action_history: list[str] = []
    reasoning_history: list[str] = []
    while True:
        turn += 1
        if max_turns > 0 and turn > max_turns:
            break
        yield {"event": "turn", "data": {"turn": turn, "max_turns": max_turns}}

        # Stream AI response
        full_text = ""
        try:
            if base_url:
                gen = stream_openai_compatible(api_key, model, full_messages, base_url)
            elif provider == "claude":
                gen = stream_claude(api_key, model, full_messages)
            elif provider == "deepseek":
                gen = stream_deepseek(api_key, model, full_messages)
            elif provider == "glm":
                gen = stream_glm(api_key, model, full_messages)
            else:
                yield {"event": "text", "data": {"content": f"Unknown provider: {provider}"}}
                yield {"event": "done", "data": {"reason": "error"}}
                return

            async for chunk in gen:
                full_text += chunk
                yield {"event": "text", "data": {"content": chunk}}
        except Exception as e:
            logger.exception("Streaming error in agent loop")
            yield {
                "event": "action_error",
                "data": {
                    "error": str(e),
                    "error_type": "fatal",
                    "retry_count": consecutive_errors,
                    "max_retries": MAX_CONSECUTIVE_ERRORS,
                },
            }
            yield {"event": "done", "data": {"reason": "error"}}
            return

        # Parse actions from response
        actions = parse_actions(full_text)

        if not actions:
            # Check if AI attempted an action but malformed the XML
            if has_action_attempt(full_text):
                consecutive_errors += 1
                yield {
                    "event": "action_error",
                    "data": {
                        "error": "Malformed action XML",
                        "error_type": "malformed",
                        "retry_count": consecutive_errors,
                        "max_retries": MAX_CONSECUTIVE_ERRORS,
                    },
                }
                # Inject feedback so AI can correct itself
                full_messages.append({"role": "assistant", "content": full_text})
                if consecutive_errors >= MAX_CONSECUTIVE_ERRORS:
                    full_messages.append(
                        {
                            "role": "user",
                            "content": "[Action Failed: Malformed action XML after multiple attempts. "
                            "Please continue your analysis in plain text without action blocks.]",
                        }
                    )
                else:
                    full_messages.append(
                        {
                            "role": "user",
                            "content": "[Action Failed: Malformed action XML. Your <action> block could not be parsed. "
                            "Please make sure to use the correct format: "
                            '<action type="plugin"> or <action type="shell"> with proper closing </action> tag.]',
                        }
                    )
                continue

            # No action and no attempt — AI is done analyzing
            yield {"event": "done", "data": {"reason": "complete"}}
            return

        # Mode A (semi_auto): only take the first action
        if agent_mode == "semi_auto":
            action = actions[0]
            # Validate action type
            if agent_mode == "full_auto" and action.get("type") == "shell":
                yield {
                    "event": "action_error",
                    "data": {
                        "error": "Shell commands not allowed in full_auto mode",
                        "error_type": "fatal",
                        "retry_count": 0,
                        "max_retries": MAX_CONSECUTIVE_ERRORS,
                    },
                }
                yield {"event": "done", "data": {"reason": "error"}}
                return
            yield {"event": "action", "data": {"action": action}}
            yield {"event": "waiting", "data": {}}
            yield {"event": "done", "data": {"reason": "waiting"}}
            return

        # Mode B/C (full_auto / terminal): validate all actions
        for a in actions:
            if agent_mode == "full_auto" and a.get("type") == "shell":
                yield {
                    "event": "action_error",
                    "data": {
                        "error": "Shell commands not allowed in full_auto mode",
                        "error_type": "fatal",
                        "retry_count": 0,
                        "max_retries": MAX_CONSECUTIVE_ERRORS,
                    },
                }
                yield {"event": "done", "data": {"reason": "error"}}
                return

        # Emit action event(s)
        if len(actions) == 1:
            yield {"event": "action", "data": {"action": actions[0]}}
        else:
            yield {"event": "action", "data": {"action": actions[0], "actions": actions}}
        yield {
            "event": "action_status",
            "data": {"status": "executing", "count": len(actions)},
        }

        # Concurrent execution of all actions
        import asyncio

        async def _run_one(a: dict[str, Any]) -> dict[str, Any]:
            return await _execute_action(a, agent_mode, user_id, is_admin, user_token)

        try:
            results = await asyncio.gather(*[_run_one(a) for a in actions], return_exceptions=True)
        except Exception as e:
            logger.exception("Action execution error in agent loop")
            yield {
                "event": "action_error",
                "data": {
                    "error": str(e),
                    "error_type": "fatal",
                    "retry_count": consecutive_errors,
                    "max_retries": MAX_CONSECUTIVE_ERRORS,
                },
            }
            yield {"event": "done", "data": {"reason": "error"}}
            return

        # Process results
        all_ok = True
        result_texts = []
        max_similar = 0
        # Snapshot history BEFORE this turn so same-turn actions don't count
        # against each other (e.g. scanning 5 ports in parallel is not stagnation)
        history_before_turn = list(action_history)
        for action, result in zip(actions, results):
            if isinstance(result, Exception):
                result = {"error": str(result)}

            error_msg = result.get("error")
            if error_msg:
                all_ok = False
                error_type = classify_error(error_msg)
                consecutive_errors += 1
                yield {
                    "event": "action_error",
                    "data": {
                        "error": error_msg,
                        "error_type": error_type,
                        "retry_count": consecutive_errors,
                        "max_retries": MAX_CONSECUTIVE_ERRORS,
                        "action": action,
                    },
                }
                if error_type == "fatal":
                    yield {"event": "done", "data": {"reason": "error"}}
                    return
            else:
                consecutive_errors = 0
                yield {"event": "action_result", "data": {"result": result, "action": action}}

            result_texts.append(format_action_result(action, result))

            # Stagnation detection: compare against PREVIOUS turns only
            fingerprint = _action_fingerprint(action)
            similar_count = count_similar_recent(history_before_turn, fingerprint)
            action_history.append(fingerprint)
            if similar_count > max_similar:
                max_similar = similar_count
            if similar_count > 0:
                logger.warning(
                    "Stagnation check: fingerprint=%s similar=%d/%d history_size=%d",
                    fingerprint[:80],
                    similar_count,
                    STAGNATION_STOP,
                    len(history_before_turn),
                )

        if not all_ok and consecutive_errors > 0:
            full_messages.append({"role": "assistant", "content": full_text})
            if consecutive_errors >= MAX_CONSECUTIVE_ERRORS:
                full_messages.append(
                    {
                        "role": "user",
                        "content": "[Action Failed] "
                        "You have failed multiple consecutive times. "
                        "Please continue your analysis in plain text without action blocks.",
                    }
                )
            else:
                feedback_parts = []
                for action, result in zip(actions, results):
                    if isinstance(result, Exception):
                        result = {"error": str(result)}
                    label = action.get("plugin") or (action.get("command") or "?")[:60]
                    if isinstance(result, dict) and result.get("error"):
                        feedback_parts.append(f"  FAILED  {label}: {result['error']}")
                    else:
                        feedback_parts.append(f"  OK      {label}")
                detail = "\n".join(feedback_parts)
                full_messages.append(
                    {
                        "role": "user",
                        "content": f"[Parallel Action Results]\n{detail}\n\n"
                        "Only retry the FAILED actions. "
                        "Do NOT re-send actions that succeeded.",
                    }
                )
            continue

        # Inject all results into conversation
        full_messages.append({"role": "assistant", "content": full_text})
        combined_result = "\n\n---\n\n".join(result_texts)
        full_messages.append({"role": "user", "content": combined_result})

        # Reasoning-level stagnation (same strategy, different URLs)
        reasoning_fp = _extract_reasoning(full_text)
        reasoning_similar = _reasoning_stagnation(reasoning_history, reasoning_fp)
        reasoning_history.append(reasoning_fp)

        # Only escalate reasoning stagnation when results are also negative.
        # If results show new data, the AI may be legitimately persisting.
        results_negative = _results_look_negative(combined_result)
        effective_reasoning = reasoning_similar if results_negative else 0

        if reasoning_similar > 0:
            logger.warning(
                "Reasoning stagnation: %d consecutive similar, negative=%s, text=%.80s",
                reasoning_similar,
                results_negative,
                reasoning_fp,
            )

        # Pick the more severe signal between action and reasoning stagnation
        effective_stagnation = max(max_similar, effective_reasoning)

        # ---- Metrics (zero token cost) ----
        if session_id is not None:
            try:
                from app.services.agent_metrics import compute_health_score, publish_metrics

                await publish_metrics(
                    session_id,
                    {
                        "session_id": session_id,
                        "turn": turn,
                        "max_turns": max_turns,
                        "action_stagnation": max_similar,
                        "reasoning_stagnation": reasoning_similar,
                        "effective_reasoning": effective_reasoning,
                        "effective_stagnation": effective_stagnation,
                        "results_negative": results_negative,
                        "consecutive_errors": consecutive_errors,
                        "actions_count": len(actions),
                        "agent_mode": agent_mode,
                        "security_mode": security_mode,
                        "all_actions_ok": all_ok,
                        "health_score": compute_health_score(
                            effective_stagnation,
                            consecutive_errors,
                            results_negative,
                            all_actions_ok=all_ok,
                        ),
                    },
                )
            except Exception:
                pass  # monitoring must never break the agent

        if (
            effective_stagnation >= STAGNATION_STOP
            or effective_reasoning >= REASONING_STAGNATION_STOP
        ):
            logger.warning(
                "Stagnation STOP: action=%d reasoning=%d (effective=%d), terminating",
                max_similar,
                reasoning_similar,
                effective_reasoning,
            )
            yield {"event": "done", "data": {"reason": "stagnation"}}
            return
        elif (
            effective_stagnation >= STAGNATION_FORCE
            or effective_reasoning >= REASONING_STAGNATION_WARN
        ):
            logger.warning(
                "Stagnation FORCE: action=%d reasoning=%d (effective=%d), injecting warning",
                max_similar,
                reasoning_similar,
                effective_reasoning,
            )
            if effective_reasoning >= REASONING_STAGNATION_WARN:
                # Reasoning-level stagnation: same strategy, different URLs
                full_messages.append(
                    {
                        "role": "user",
                        "content": "[System Warning: STRATEGIC LOOP DETECTED] "
                        "You have been repeating the same strategic thinking for multiple turns "
                        "(same approach, just trying different URLs or parameters). "
                        "This is NOT progress. You MUST:\n"
                        "1. STOP trying variations of your current approach entirely.\n"
                        "2. Name a DIFFERENT vulnerability class or attack vector you haven't tried "
                        "(e.g., if stuck on file upload → try SQLi, XSS, SSRF, auth bypass, or API abuse).\n"
                        "3. If you've exhausted your ideas, summarize findings and stop.\n"
                        "Do NOT say 'let me try a different endpoint' — that is the SAME strategy.",
                    }
                )
            else:
                # Action-level stagnation: literally similar commands
                full_messages.append(
                    {
                        "role": "user",
                        "content": "[System Warning: STAGNATION DETECTED] "
                        "You have attempted very similar actions multiple times without progress. "
                        "You MUST either: (1) try a completely different technique/tool, or "
                        "(2) stop and provide a summary of your findings so far. "
                        "Do NOT repeat the same approach again.",
                    }
                )
        elif effective_stagnation >= STAGNATION_WARN:
            full_messages.append(
                {
                    "role": "user",
                    "content": "[System Notice: Your recent actions look very similar to previous attempts. "
                    "Consider changing your strategy — try different tools, parameters, or techniques "
                    "rather than variations of the same approach.]",
                }
            )

    yield {"event": "done", "data": {"reason": "max_turns"}}


async def _execute_action(
    action: dict[str, Any],
    agent_mode: str,
    user_id: int | None = None,
    is_admin: bool = False,
    user_token: str | None = None,
) -> dict[str, Any]:
    """Execute an action based on its type."""
    action_type = action.get("type", "")

    if action_type == "plugin":
        # Validate whitelist for non-admin users
        if not is_admin and user_id:
            from app.core.database import async_session
            from app.services.whitelist_service import validate_targets

            params = action.get("params", {})
            async with async_session() as session:
                is_valid, error_msg = await validate_targets(session, user_id, False, params)
                if not is_valid:
                    return {"error": f"Unauthorized target: {error_msg}"}

        return await execute_plugin_action(action)
    elif action_type == "shell":
        if agent_mode != "terminal":
            return {"error": "Shell commands only allowed in terminal mode"}
        from app.services.container_service import exec_in_container
        from app.services.sandbox import is_command_safe

        command = action.get("command", "")
        command = _preprocess_shell_command(command)
        safe, reason = is_command_safe(command)
        if not safe:
            return {"error": f"Command blocked: {reason}", "exit_code": -1}

        if user_id and user_token:
            return await exec_in_container(user_id, command, user_token)
        else:
            from app.services.sandbox import execute_shell

            return await execute_shell(command)
    else:
        return {"error": f"Unknown action type: {action_type}"}
