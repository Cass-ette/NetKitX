"""AI Agent service: plugin catalog, action parsing, agent loop."""

import json
import logging
import re
from collections.abc import AsyncIterator
from difflib import SequenceMatcher
from typing import Any

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
Only propose ONE action per response. After execution, you'll see the result and can continue.
When your analysis is complete or no further actions are needed, respond without an action block.
"""

AGENT_INSTRUCTION_TERMINAL = """
## Agent Mode: Terminal (Shell Commands)
You are an autonomous AI agent that can execute shell commands directly.
Output action blocks to run commands — they will be executed automatically.

<action type="shell">
  <command>your command here</command>
  <reason>Why you want to run this</reason>
</action>

You can also use plugins:

<action type="plugin">
  <plugin>plugin-name</plugin>
  <params>
    <param name="key">value</param>
  </params>
  <reason>Why you want to run this</reason>
</action>

Only propose ONE action per response. After execution, you'll see the result and can continue.
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
    return f"{base}\n\n{agent_inst}\n\n{_AGENT_ERROR_HANDLING}\n\n{catalog}"


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


def parse_action(text: str) -> dict[str, Any] | None:
    """Extract the first <action> block from AI text using regex (no strict XML parsing)."""
    match = _ACTION_RE.search(text)
    if not match:
        return None

    block = match.group(0)

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

    result_str = json.dumps(result, default=str, ensure_ascii=False)
    if len(result_str) > MAX_RESULT_CHARS:
        result_str = result_str[:MAX_RESULT_CHARS] + "...(truncated)"

    return f"{header}\n{result_str}"


# ---------------------------------------------------------------------------
# Error classification
# ---------------------------------------------------------------------------

MAX_CONSECUTIVE_ERRORS = 3

_FATAL_ERROR_PATTERNS = [
    "Command blocked:",
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

STAGNATION_SIMILARITY = 0.7  # two actions >70% similar = "same approach"
STAGNATION_WARN = 3  # inject soft warning
STAGNATION_FORCE = 5  # inject hard warning
STAGNATION_STOP = 7  # terminate


def _action_fingerprint(action: dict[str, Any]) -> str:
    """Extract a comparable fingerprint from an action dict."""
    atype = action.get("type", "")
    if atype == "shell":
        return f"shell:{action.get('command', '')}"
    elif atype == "plugin":
        params_str = json.dumps(action.get("params", {}), sort_keys=True)
        return f"plugin:{action.get('plugin', '')}:{params_str}"
    return ""


def _is_similar(a: str, b: str) -> bool:
    """Check if two fingerprints are similar enough to count as repetition."""
    if not a or not b:
        return False
    return SequenceMatcher(None, a, b).ratio() >= STAGNATION_SIMILARITY


def count_similar_recent(history: list[str], current: str) -> int:
    """Count how many recent actions are similar to the current one."""
    return sum(1 for h in history if _is_similar(h, current))


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
    user_token: str | None = None,
    base_url: str | None = None,
) -> AsyncIterator[dict]:
    """
    Main agent loop generator. Yields SSE event dicts.

    For semi_auto: yields one AI response, parses action, yields waiting event, then stops.
    For full_auto/terminal: loops up to max_turns, auto-executing actions.
    """
    system_prompt = get_agent_system_prompt(agent_mode, security_mode, lang)
    lang_reminder = get_lang_reminder(lang)

    # If this is a confirm_action continuation (Mode A), execute and inject result
    if confirm_action is not None:
        action = confirm_action.get("action", {}) if isinstance(confirm_action, dict) else {}
        approved = (
            confirm_action.get("approved", False) if isinstance(confirm_action, dict) else False
        )

        if approved and action:
            yield {"event": "action_status", "data": {"status": "executing", "action": action}}
            result = await _execute_action(action, agent_mode, user_id, user_token)
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

        # Parse action from response
        action = parse_action(full_text)

        if not action:
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

        # Validate action type for mode
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

        # Mode A: pause and wait for user
        if agent_mode == "semi_auto":
            yield {"event": "waiting", "data": {}}
            yield {"event": "done", "data": {"reason": "waiting"}}
            return

        # Mode B/C: auto-execute
        yield {"event": "action_status", "data": {"status": "executing", "action": action}}
        try:
            result = await _execute_action(action, agent_mode, user_id, user_token)
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

        error_msg = result.get("error")
        if error_msg:
            error_type = classify_error(error_msg)
            consecutive_errors += 1

            yield {
                "event": "action_error",
                "data": {
                    "error": error_msg,
                    "error_type": error_type,
                    "retry_count": consecutive_errors,
                    "max_retries": MAX_CONSECUTIVE_ERRORS,
                },
            }

            if error_type == "fatal":
                yield {"event": "done", "data": {"reason": "error"}}
                return

            # Retryable: inject error feedback into conversation
            full_messages.append({"role": "assistant", "content": full_text})
            if consecutive_errors >= MAX_CONSECUTIVE_ERRORS:
                full_messages.append(
                    {
                        "role": "user",
                        "content": f"[Action Failed: {error_msg}] "
                        "You have failed multiple consecutive times. "
                        "Please continue your analysis in plain text without action blocks.",
                    }
                )
            else:
                full_messages.append(
                    {
                        "role": "user",
                        "content": f"[Action Failed: {error_msg}] "
                        "Please analyze the error and try a different approach.",
                    }
                )
            continue

        # Success — reset error counter
        consecutive_errors = 0
        yield {"event": "action_result", "data": {"result": result, "action": action}}

        # Stagnation detection
        fingerprint = _action_fingerprint(action)
        similar_count = count_similar_recent(action_history, fingerprint)
        action_history.append(fingerprint)

        # Inject into conversation
        full_messages.append({"role": "assistant", "content": full_text})
        result_text = format_action_result(action, result)
        full_messages.append({"role": "user", "content": result_text})

        if similar_count >= STAGNATION_STOP:
            yield {"event": "done", "data": {"reason": "stagnation"}}
            return
        elif similar_count >= STAGNATION_FORCE:
            full_messages.append(
                {
                    "role": "user",
                    "content": "[System Warning: STAGNATION DETECTED] "
                    "You have attempted very similar actions multiple times without meaningful progress. "
                    "You MUST either: (1) try a completely different technique/tool, or "
                    "(2) stop and provide a summary of your findings so far. "
                    "Do NOT repeat the same approach again.",
                }
            )
        elif similar_count >= STAGNATION_WARN:
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
    user_token: str | None = None,
) -> dict[str, Any]:
    """Execute an action based on its type."""
    action_type = action.get("type", "")

    if action_type == "plugin":
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
