"""AI Agent service: main agent loop and action execution."""

import logging
from collections.abc import AsyncIterator
from typing import Any

from app.core.config import settings
from app.services.ai_service import (
    get_lang_reminder,
    stream_deepseek,
    stream_glm,
    stream_openai_compatible,
)
from app.services.agent_prompts import get_agent_system_prompt
from app.services.agent_utils import (
    MAX_CONSECUTIVE_ERRORS,
    STAGNATION_FORCE,
    STAGNATION_STOP,
    STAGNATION_WARN,
    _action_fingerprint,
    _estimate_context_chars,
    _preprocess_shell_command,
    _summarize_context,
    classify_error,
    count_similar_recent,
    execute_plugin_action,
    format_action_result,
    has_action_attempt,
    parse_actions,
)

logger = logging.getLogger(__name__)


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
) -> AsyncIterator[dict]:
    """
    Main agent loop generator. Yields SSE event dicts.

    For semi_auto: yields one AI response, parses action, yields waiting event, then stops.
    For full_auto/terminal: loops up to max_turns, auto-executing actions.
    """
    # Build system prompt once (contest: removed phase/role rotation)
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
            logger.warning("Streaming error in agent loop (turn %d): %s", turn, e)
            consecutive_errors += 1
            yield {
                "event": "action_error",
                "data": {
                    "error": f"AI streaming failed: {e}",
                    "error_type": "retryable",
                    "retry_count": consecutive_errors,
                    "max_retries": MAX_CONSECUTIVE_ERRORS,
                },
            }
            if consecutive_errors >= MAX_CONSECUTIVE_ERRORS:
                yield {"event": "done", "data": {"reason": "error"}}
                return
            # Retryable: continue to next turn
            full_messages.append(
                {
                    "role": "user",
                    "content": "[AI Streaming Error — please continue your analysis.]",
                }
            )
            continue

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
            max_similar = max(max_similar, similar_count)
            action_history.append(fingerprint)

        # Inject into conversation
        full_messages.append({"role": "assistant", "content": full_text})
        full_messages.append({"role": "user", "content": "\n\n".join(result_texts)})

        # Context compression: trigger when conversation grows too large
        if _estimate_context_chars(full_messages) > 50_000:
            full_messages = _summarize_context(full_messages)
            logger.info("Context compressed at turn %d", turn)

        if max_similar >= STAGNATION_STOP:
            yield {"event": "done", "data": {"reason": "stagnation"}}
            return
        elif max_similar >= STAGNATION_FORCE:
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
        elif max_similar >= STAGNATION_WARN:
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
