"""AI Agent service: plugin catalog, action parsing, agent loop."""

import json
import logging
import re
from collections.abc import AsyncIterator
from typing import Any

from app.plugins.registry import registry
from app.services.ai_service import (
    get_system_prompt,
    get_lang_reminder,
    stream_claude,
    stream_deepseek,
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

_AGENT_INSTRUCTIONS = {
    "semi_auto": AGENT_INSTRUCTION_SEMI_AUTO,
    "full_auto": AGENT_INSTRUCTION_FULL_AUTO,
    "terminal": AGENT_INSTRUCTION_TERMINAL,
}


def get_agent_system_prompt(agent_mode: str, security_mode: str, lang: str) -> str:
    """Compose full system prompt: language + security + agent instructions + plugin catalog."""
    base = get_system_prompt(security_mode, lang)
    agent_inst = _AGENT_INSTRUCTIONS.get(agent_mode, "")
    catalog = build_plugin_catalog()
    return f"{base}\n\n{agent_inst}\n\n{catalog}"


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

MAX_RESULT_CHARS = 8000


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
            result = await _execute_action(action, agent_mode)
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
    while True:
        turn += 1
        if max_turns > 0 and turn > max_turns:
            break
        yield {"event": "turn", "data": {"turn": turn, "max_turns": max_turns}}

        # Stream AI response
        full_text = ""
        if provider == "claude":
            gen = stream_claude(api_key, model, full_messages)
        elif provider == "deepseek":
            gen = stream_deepseek(api_key, model, full_messages)
        else:
            yield {"event": "text", "data": {"content": f"Unknown provider: {provider}"}}
            yield {"event": "done", "data": {"reason": "error"}}
            return

        async for chunk in gen:
            full_text += chunk
            yield {"event": "text", "data": {"content": chunk}}

        # Parse action from response
        action = parse_action(full_text)

        if not action:
            # No action — AI is done analyzing
            yield {"event": "done", "data": {"reason": "complete"}}
            return

        # Validate action type for mode
        if agent_mode == "full_auto" and action.get("type") == "shell":
            yield {
                "event": "text",
                "data": {
                    "content": "\n\n[Shell commands are not allowed in full_auto mode. Use plugin actions only.]\n"
                },
            }
            yield {"event": "done", "data": {"reason": "complete"}}
            return

        yield {"event": "action", "data": {"action": action}}

        # Mode A: pause and wait for user
        if agent_mode == "semi_auto":
            yield {"event": "waiting", "data": {}}
            yield {"event": "done", "data": {"reason": "waiting"}}
            return

        # Mode B/C: auto-execute
        yield {"event": "action_status", "data": {"status": "executing", "action": action}}
        result = await _execute_action(action, agent_mode)
        yield {"event": "action_result", "data": {"result": result, "action": action}}

        # Inject into conversation
        full_messages.append({"role": "assistant", "content": full_text})
        result_text = format_action_result(action, result)
        full_messages.append({"role": "user", "content": result_text})

    yield {"event": "done", "data": {"reason": "max_turns"}}


async def _execute_action(action: dict[str, Any], agent_mode: str) -> dict[str, Any]:
    """Execute an action based on its type."""
    action_type = action.get("type", "")

    if action_type == "plugin":
        return await execute_plugin_action(action)
    elif action_type == "shell":
        if agent_mode != "terminal":
            return {"error": "Shell commands only allowed in terminal mode"}
        from app.services.sandbox import execute_shell

        return await execute_shell(action.get("command", ""))
    else:
        return {"error": f"Unknown action type: {action_type}"}
