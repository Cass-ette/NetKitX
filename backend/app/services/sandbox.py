"""Shell sandbox for terminal agent mode."""

import asyncio
import logging
import os
import re
from urllib.parse import quote, urlparse, urlunparse, unquote
from typing import Any

from app.core.config import settings

logger = logging.getLogger(__name__)

# Commands that are never allowed
COMMAND_BLACKLIST = [
    r"\brm\s+-[^\s]*r[^\s]*f\s+/",  # rm -rf /
    r"\brm\s+-[^\s]*f[^\s]*r\s+/",  # rm -fr /
    r"\bmkfs\b",
    r"\bdd\s+.*of=/dev/",
    r":\(\)\s*\{\s*:\|:\s*&\s*\}\s*;",  # fork bomb
    r"\bshutdown\b",
    r"\breboot\b",
    r"\bpoweroff\b",
    r"\binit\s+0\b",
    r"\bsudo\b",
    r"\bsu\s",
    r"\bcurl\b.*\|\s*(ba)?sh",
    r"\bwget\b.*\|\s*(ba)?sh",
    r"\bchmod\s+[0-7]*777\s+/",
    r"\bchown\s+.*\s+/",
    r"\b>(>)?\s*/dev/[hs]d",
    r"\biptables\s+-F\b",
    r"\bsystemctl\s+(stop|disable|mask)\b",
]

_BLACKLIST_PATTERNS = [re.compile(p, re.IGNORECASE) for p in COMMAND_BLACKLIST]

# Inherit system PATH so user-installed tools (Homebrew, pip, etc.) are accessible,
# with standard paths as fallback.
_SANDBOX_PATH = os.environ.get(
    "PATH",
    "/opt/homebrew/bin:/opt/homebrew/sbin:/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin",
)


_UNSAFE_QUERY_CHARS = frozenset("' \"<>{}`\\")
_DQUOTED_URL_RE = re.compile(r'"(https?://[^"]+)"')
_SQUOTED_URL_RE = re.compile(r"'(https?://[^']+)'")


def _encode_query(raw_url: str) -> str | None:
    """If query string has unsafe chars, return URL with encoded query. Else None."""
    try:
        parsed = urlparse(raw_url)
    except Exception:
        return None
    if not parsed.query:
        return None
    if not any(c in _UNSAFE_QUERY_CHARS for c in parsed.query):
        return None
    decoded_query = unquote(parsed.query)
    encoded_query = quote(decoded_query, safe="=&+%")
    return urlunparse(parsed._replace(query=encoded_query))


def _fix_curl_url(command: str) -> str:
    """Auto-encode special chars in curl URL query strings to prevent exit_code 3."""
    if "curl" not in command.lower():
        return command

    def _fix_dquoted(m: re.Match) -> str:
        fixed = _encode_query(m.group(1))
        return f'"{fixed}"' if fixed else m.group(0)

    def _fix_squoted(m: re.Match) -> str:
        fixed = _encode_query(m.group(1))
        return f"'{fixed}'" if fixed else m.group(0)

    result = _DQUOTED_URL_RE.sub(_fix_dquoted, command)
    result = _SQUOTED_URL_RE.sub(_fix_squoted, result)
    return result


def is_command_safe(command: str) -> tuple[bool, str]:
    """Check if a command is safe to execute. Returns (safe, reason)."""
    if not command or not command.strip():
        return False, "Empty command"

    for pattern in _BLACKLIST_PATTERNS:
        if pattern.search(command):
            return False, f"Blocked by security policy: {pattern.pattern}"

    return True, ""


async def execute_shell(command: str) -> dict[str, Any]:
    """Execute a shell command in a sandboxed environment."""
    command = _fix_curl_url(command)
    safe, reason = is_command_safe(command)
    if not safe:
        return {"error": f"Command blocked: {reason}", "exit_code": -1}

    timeout = settings.AGENT_COMMAND_TIMEOUT

    try:
        proc = await asyncio.create_subprocess_shell(
            command,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            cwd="/tmp",
            env={
                "PATH": _SANDBOX_PATH,
                "HOME": "/tmp",
                "TERM": "xterm-256color",
                "LANG": "en_US.UTF-8",
            },
        )

        try:
            stdout_bytes, stderr_bytes = await asyncio.wait_for(proc.communicate(), timeout=timeout)
        except asyncio.TimeoutError:
            proc.kill()
            await proc.communicate()
            return {
                "error": f"Command timed out after {timeout}s",
                "exit_code": -1,
            }

        stdout = stdout_bytes.decode("utf-8", errors="replace")
        stderr = stderr_bytes.decode("utf-8", errors="replace")

        # Truncate output
        max_stdout = 30720  # 30KB
        max_stderr = 10240  # 10KB
        if len(stdout) > max_stdout:
            stdout = stdout[:max_stdout] + "\n...(stdout truncated)"
        if len(stderr) > max_stderr:
            stderr = stderr[:max_stderr] + "\n...(stderr truncated)"

        return {
            "stdout": stdout,
            "stderr": stderr,
            "exit_code": proc.returncode,
        }

    except Exception as e:
        logger.error("Shell execution error: %s", e)
        return {"error": str(e), "exit_code": -1}
