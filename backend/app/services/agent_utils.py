"""Agent utility functions: action parsing, compression, error classification, stagnation detection."""

import json
import logging
import re
from typing import Any

from app.plugins.registry import registry

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Action parsing (regex-based, tolerates XML-unfriendly content)
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
    """Extract the first <action> block from AI text using regex."""
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
    if _CURL_SILENT_RE.search(command):
        return command
    return _CURL_RE.sub("curl -s", command)


# ---------------------------------------------------------------------------
# Plugin execution
# ---------------------------------------------------------------------------


async def execute_plugin_action(action: dict[str, Any]) -> dict[str, Any]:
    """Execute a plugin action and return the result."""
    plugin_name = action.get("plugin", "")
    params = action.get("params", {})
    logger.info("Executing plugin action plugin=%s params=%s", plugin_name, json.dumps(params))
    plugin = registry.get(plugin_name)
    if not plugin:
        logger.warning("Plugin action failed: plugin '%s' not found or not enabled", plugin_name)
        return {"error": f"Plugin '{plugin_name}' not found or not enabled"}
    if not registry.is_enabled(plugin_name):
        logger.warning("Plugin action failed: plugin '%s' is disabled", plugin_name)
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
                logger.warning(
                    "Plugin action emitted error plugin=%s error=%s",
                    plugin_name,
                    event.data,
                )
                if isinstance(event.data, dict):
                    return {
                        "error": event.data.get("message")
                        or event.data.get("error")
                        or str(event.data)
                    }
                return {"error": str(event.data)}
    except Exception as e:
        logger.exception("Plugin action crashed plugin=%s", plugin_name)
        return {"error": str(e)}
    logger.info(
        "Plugin action completed plugin=%s results=%d logs=%d",
        plugin_name,
        len(results),
        len(logs),
    )
    return {"items": results, "logs": logs}


# ---------------------------------------------------------------------------
# Output compression
# ---------------------------------------------------------------------------

_HTML_TAG_RE = re.compile(r"<[^>]+>")
_ANSI_RE = re.compile(r"\x1b\[[0-9;]*[a-zA-Z]")
_BLANK_LINES_RE = re.compile(r"\n{3,}")
_WHITESPACE_LINES_RE = re.compile(r"\n[ \t]+\n")

_SEC_ATTR_RE = re.compile(
    r"<(form|input|a|iframe|meta|img|button|select|option|textarea)\s+([^>]*)>",
    re.IGNORECASE,
)
_ATTR_PAIR_RE = re.compile(r'(\w+)\s*=\s*["\']([^"\']*)["\']')

_SCRIPT_RE = re.compile(r"<script[^>]*>(.*?)</script>", re.DOTALL | re.IGNORECASE)
_SCRIPT_KEEP_THRESHOLD = 1000

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
    """Remove HTML tags, preserve security-relevant content."""
    text = re.sub(r"<style[^>]*>.*?</style>", "", text, flags=re.DOTALL | re.IGNORECASE)

    def _handle_script(m: re.Match) -> str:
        content = m.group(1).strip()
        return content if len(content) <= _SCRIPT_KEEP_THRESHOLD else ""

    text = _SCRIPT_RE.sub(_handle_script, text)
    text = _SEC_ATTR_RE.sub(_preserve_sec_attrs, text)
    text = _HTML_TAG_RE.sub("", text)
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
    text = _ANSI_RE.sub("", text)
    if "<html" in text.lower() or "<body" in text.lower() or "<div" in text.lower():
        text = _strip_html(text)
    text = _WHITESPACE_LINES_RE.sub("\n\n", text)
    text = _BLANK_LINES_RE.sub("\n\n", text)
    text = text.strip()
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

STAGNATION_SIMILARITY = 0.7
STAGNATION_WARN = 3
STAGNATION_FORCE = 5
STAGNATION_STOP = 7

_URL_RE = re.compile(r"https?://([^/\s]+)([^\s]*)")
_CURL_METHOD_RE = re.compile(r"-X\s+(\w+)|--request\s+(\w+)")
# nmap target is typically the last non-option argument (or last argument overall)
_NMAP_TARGET_RE = re.compile(r"nmap\s+(?:-[a-zA-Z0-9,]+(?:\s+\S+)?\s+)*([^-\s][^\s]*)\s*$")


def _extract_shell_pattern(cmd: str) -> str:
    """Extract command structure pattern rather than raw arguments."""
    if not cmd:
        return ""
    parts = cmd.strip().split()
    if not parts:
        return ""

    base_cmd = parts[0]

    if base_cmd == "curl":
        method = "GET"
        m = _CURL_METHOD_RE.search(cmd)
        if m:
            method = m.group(1) or m.group(2)
        url_m = _URL_RE.search(cmd)
        if url_m:
            return f"curl:{method}:{url_m.group(1)}"
        return "curl:nohost"

    if base_cmd == "nmap":
        m = _NMAP_TARGET_RE.search(cmd)
        if m:
            return f"nmap:{m.group(1)}"
        return "nmap:notarget"

    return base_cmd


def _action_fingerprint(action: dict[str, Any]) -> str:
    """Extract a structured fingerprint from an action dict."""
    atype = action.get("type", "")

    if atype == "shell":
        return f"shell:{_extract_shell_pattern(action.get('command', ''))}"

    elif atype == "plugin":
        params = action.get("params", {})
        param_keys = ",".join(sorted(params.keys()))
        return f"plugin:{action.get('plugin', '')}:{param_keys}"

    return ""


def _is_similar(a: str, b: str) -> bool:
    """Check if two fingerprints represent the same structural pattern."""
    if not a or not b:
        return False
    return a == b


def count_similar_recent(history: list[str], current: str) -> int:
    """Count how many recent actions match the current pattern."""
    return sum(1 for h in history if _is_similar(h, current))


# ---------------------------------------------------------------------------
# Context compression
# ---------------------------------------------------------------------------

_CONTEXT_CHAR_THRESHOLD = 50_000
_CONTEXT_SUMMARY_MAX = 4_000


def _summarize_context(messages: list[dict[str, str]]) -> list[dict[str, str]]:
    """Compress conversation history by replacing middle messages with a summary."""
    if len(messages) <= 6:
        return messages
    head = messages[:2]
    tail = messages[-4:]
    middle = messages[2:-4]
    summary_parts: list[str] = []
    for msg in middle:
        role = msg.get("role", "")
        content = msg.get("content", "")
        if role == "assistant":
            preview = content[:300] + ("..." if len(content) > 300 else "")
            summary_parts.append(f"[AI] {preview}")
        elif role == "user":
            preview = content[:200] + ("..." if len(content) > 200 else "")
            summary_parts.append(f"[Result/Feedback] {preview}")
    summary_text = "\n".join(summary_parts)
    if len(summary_text) > _CONTEXT_SUMMARY_MAX:
        summary_text = summary_text[:_CONTEXT_SUMMARY_MAX] + "\n...(older context omitted)"
    summary_msg = {
        "role": "user",
        "content": f"[Context Summary - earlier conversation compressed]\n{summary_text}",
    }
    return head + [summary_msg] + tail


def _estimate_context_chars(messages: list[dict[str, str]]) -> int:
    """Estimate total character count of all messages in the conversation."""
    return sum(len(m.get("content", "")) for m in messages)
