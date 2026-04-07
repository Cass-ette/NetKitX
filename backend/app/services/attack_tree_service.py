"""Attack tree service: phase guidance, plugin recommendations, dangerous command detection."""

import re

from app.data.attack_tree import ATTACK_TREE, DANGEROUS_COMMAND_PATTERNS, KILL_CHAIN_PHASES
from app.plugins.registry import registry


def get_all_phases() -> list[str]:
    """Return all kill chain phases in order."""
    return list(KILL_CHAIN_PHASES)


def get_next_phase(current: str) -> str | None:
    """Return the next phase after current, or None if at the end."""
    try:
        idx = KILL_CHAIN_PHASES.index(current)
    except ValueError:
        return None
    if idx + 1 < len(KILL_CHAIN_PHASES):
        return KILL_CHAIN_PHASES[idx + 1]
    return None


def get_phase_info(phase: str) -> dict | None:
    """Return the ATTACK_TREE entry for a phase, or None."""
    return ATTACK_TREE.get(phase)


def get_recommended_plugins(phase: str) -> list[str]:
    """Return recommended plugin names for the current phase."""
    info = ATTACK_TREE.get(phase)
    if not info:
        return []
    return list(info.get("plugins", []))


def is_command_dangerous(command: str) -> tuple[bool, str]:
    """Check if a command matches a globally dangerous pattern."""
    for pattern, reason in DANGEROUS_COMMAND_PATTERNS:
        if re.search(pattern, command, re.IGNORECASE):
            return True, reason
    return False, ""


def build_phase_guidance_prompt(phase: str) -> str:
    """Generate guidance prompt text for the current attack phase."""
    info = ATTACK_TREE.get(phase)
    if not info:
        return ""
    next_phase = get_next_phase(phase)
    recommended = info.get("plugins", [])
    shell_patterns = info.get("shell_patterns", [])
    description = info.get("description", "")
    lines = [
        f"## Current Attack Phase: {phase}",
        f"Phase description: {description}",
        f"Recommended plugins: {', '.join(recommended) if recommended else 'none specific'}",
        f"Useful shell tools: {', '.join(shell_patterns) if shell_patterns else 'any'}",
    ]
    if next_phase:
        lines.append(f"Next phase: {next_phase}. Advance when current phase objectives are met.")
    lines.append(
        "You may use ANY shell command if it serves the current objective. "
        "Plugins above are recommended for this phase but not mandatory."
    )
    return "\n".join(lines)


def build_phase_catalog_for_prompt(phase: str) -> str:
    """Build plugin catalog annotated with phase info, marking current phase plugins."""
    plugins = registry.list_enabled()
    if not plugins:
        return "No plugins available."
    recommended = set(get_recommended_plugins(phase))
    lines = ["## Available Plugins (by Kill Chain Phase)\n"]
    for meta in plugins:
        p_phase = meta.kill_chain_phase or "general"
        marker = " [RECOMMENDED]" if meta.name in recommended else ""
        lines.append(f"### {meta.name} (v{meta.version}) [{p_phase}]{marker}")
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
                    lines.append(f"    options: {p['options']}")
    return "\n".join(lines)
