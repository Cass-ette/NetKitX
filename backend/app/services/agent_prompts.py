"""Agent prompts and system prompt generation."""

from app.services.ai_service import (
    get_system_prompt,
)
from app.services.attack_tree_service import (
    build_phase_catalog_for_prompt,
    build_phase_guidance_prompt,
)
from app.plugins.registry import registry


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
Only propose ONE action per response. After execution, you will see the result and can continue.
When your analysis is complete or no further actions are needed, respond without an action block.
"""

AGENT_INSTRUCTION_TERMINAL = """
## Agent Mode: Terminal (Plugins + Shell)
You are an autonomous AI agent that can execute plugins and shell commands.

Use the right tool for the job:
- **Plugins** return structured JSON — ideal for standard scans (port scan, dir scan, SQL injection tests).
- **Shell commands** offer full flexibility — ideal for custom payloads, command chaining, and anything plugins do not cover.
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

Only propose ONE action per response. After execution, you will see the result and can continue.
When your analysis is complete, respond without an action block.
"""

_AGENT_ERROR_HANDLING = """
## Error Handling
If an action fails, you will receive an error message in the format [Action Failed: ...].
When this happens:
- Analyze the error message carefully before retrying.
- If a plugin was not found, check the Available Plugins list and use the exact name.
- If parameters were wrong, review the plugin parameter requirements and correct them.
- Try a different approach, different plugin, or different parameters.
- Do NOT repeat the exact same action that just failed.
- If you have failed multiple consecutive times, continue analysis in plain text.
"""

_AGENT_STRATEGY = """
## Strategy
- RIGHT TOOL: Use plugins for standard scans (structured data, fewer tokens). Use shell for custom payloads, chaining, or when plugins do not fit. Do not force a plugin where a curl one-liner would be simpler.
- NON-PRIVILEGED SCANNING: You are NOT running as root. Always use nmap flags that work without privileges: use `-sT` (TCP connect scan) instead of `-sS` (SYN scan), and avoid `-O` (OS detection). Example: `nmap -sT -sV -p- -T4 <target>`. If a command fails with "requires root" or "permission denied", immediately retry with non-privileged alternatives.
- RECON FIRST: Before attacking, map the environment (OS, versions, services, technologies).
- OBSERVE, DON NOT ASSUME: Infer database type, framework, and config from error messages, response headers, and behavioral differences. If clues are already visible, act on them immediately — do not waste turns on redundant fingerprinting. When truly unknown, test with version()/@@version/sqlite_version() to confirm.
- VALIDATE EXTRACTION: After each data extraction attempt, check whether YOUR injected data actually appears in the response. If the output looks the same as before or shows values other than what you injected, the extraction technique is not working as expected. Diagnose WHY: maybe legitimate results mask your injected data, maybe the app does not reflect output at all. Adjust accordingly.
- ACT, DON NOT REPORT: Maximize action density — include an action block in every response unless you have achieved the goal. Keep analysis brief (2-3 sentences). NEVER write a summary report or recommended next steps when you still have turns left. Your job is to DO the work, not plan it for a human.
- FILTER REPEATED QUERIES: When querying the same endpoint repeatedly, pipe output through grep/sed/cut to isolate the meaningful difference. Sending identical boilerplate wastes context.
- SAME APPROACH 3 TIMES MAX: If an approach fails 3 times, switch to a completely different technique.
- MULTI-LAYER ENCODING: When data passes through multiple layers (shell, curl, HTTP, eval), use base64 or chr() to avoid escaping issues.
- VERIFY EACH STEP: If a command returns no useful output, verify each step individually with the simplest possible command before adding complexity.
- RECOGNIZE TARGET DATA: Learn to identify what you are looking for. CTF flags match the pattern word{...} (e.g. flag{xx}, CTF{xx}, any_prefix{xx}). Credentials are username/password pairs, API keys (sk-..., key-..., Bearer tokens), or session tokens. Sensitive files include /etc/shadow, .env, config files with secrets, database dumps. When ANY of these appear in a response, you have found the target.
- KNOW WHEN TO STOP: When you find the target data, IMMEDIATELY present it and stop. Do NOT continue testing or verify the same finding again. State the result clearly and end without an action block.
"""

# ---------------------------------------------------------------------------
# PEP Role-based prompt extensions (Planner / Perceptor alternation)
# ---------------------------------------------------------------------------

_AGENT_ROLE_PLANNER = """
## Your Current Role: Planner
Focus on STRATEGY this turn. Analyze collected information, identify the next high-value
objective, and decide the optimal action. Think about the big picture: what do you already
know, what is missing, and what is the most efficient next step?
"""

_AGENT_ROLE_PERCEPTOR = """
## Your Current Role: Perceptor
Focus on OBSERVATION this turn. Carefully examine the latest results, extract every
useful signal, and identify patterns or anomalies. Pay special attention to: error messages,
response headers, timing differences, partial data leaks, and behavioral variations.
Report concrete findings, not assumptions.
"""

_AGENT_INSTRUCTIONS = {
    "semi_auto": AGENT_INSTRUCTION_SEMI_AUTO,
    "full_auto": AGENT_INSTRUCTION_FULL_AUTO,
    "terminal": AGENT_INSTRUCTION_TERMINAL,
}


def get_agent_system_prompt(
    agent_mode: str,
    security_mode: str,
    lang: str,
    phase: str = "reconnaissance",
    role: str | None = None,
) -> str:
    """Compose full system prompt with phase-aware catalog and optional role injection."""
    base = get_system_prompt(security_mode, lang)
    agent_inst = _AGENT_INSTRUCTIONS.get(agent_mode, "")
    # Phase-aware plugin catalog (marks recommended plugins for current phase)
    catalog = build_phase_catalog_for_prompt(phase)
    # Phase guidance (description, recommended plugins, shell tools, next phase hint)
    phase_guidance = build_phase_guidance_prompt(phase)
    prompt = (
        f"{base}\n\n{agent_inst}\n\n{_AGENT_ERROR_HANDLING}\n\n"
        f"{_AGENT_STRATEGY}\n\n{phase_guidance}\n\n{catalog}"
    )
    # Optional PEP role injection
    if role == "planner":
        prompt += f"\n\n{_AGENT_ROLE_PLANNER}"
    elif role == "perceptor":
        prompt += f"\n\n{_AGENT_ROLE_PERCEPTOR}"
    return prompt
