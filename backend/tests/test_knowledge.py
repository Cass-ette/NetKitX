"""Unit tests for knowledge service (_events_to_turns logic + extraction helpers)."""

from unittest.mock import MagicMock

from app.services.embedding_service import build_embedding_text, format_rag_context
from app.services.knowledge_service import (
    _compress_action_result,
    _events_to_turns,
    _parse_extraction_json,
    _sanitize_extraction,
    _strip_null_bytes,
    build_session_digest,
)


class TestEventsToTurnsBasic:
    """Basic conversion of text events into turns."""

    def test_simple_text_response(self):
        messages = [{"role": "user", "content": "Hello"}]
        collected = [
            {"event": "turn", "data": {"turn": 1}},
            {"event": "text", "data": {"content": "Hi "}},
            {"event": "text", "data": {"content": "there!"}},
            {"event": "done", "data": {"reason": "complete"}},
        ]
        turns = _events_to_turns(messages, collected)

        # Should have: 1 user turn + 1 assistant turn
        assert len(turns) == 2
        assert turns[0]["role"] == "user"
        assert turns[0]["content"] == "Hello"
        assert turns[1]["role"] == "assistant"
        assert turns[1]["content"] == "Hi there!"
        assert turns[1]["turn_number"] == 1


class TestEventsToTurnsWithActions:
    """Action and action_result events preserve metadata."""

    def test_action_and_result(self):
        messages = [{"role": "user", "content": "Scan target"}]
        action_data = {"type": "plugin", "plugin": "nmap", "params": {"target": "10.0.0.1"}}
        result_data = {"items": [{"port": 80, "state": "open"}]}

        collected = [
            {"event": "turn", "data": {"turn": 1}},
            {"event": "text", "data": {"content": "Let me scan..."}},
            {"event": "action", "data": {"action": action_data}},
            {"event": "action_status", "data": {"status": "executing"}},
            {"event": "action_result", "data": {"result": result_data}},
            {"event": "turn", "data": {"turn": 2}},
            {"event": "text", "data": {"content": "Port 80 is open."}},
            {"event": "done", "data": {"reason": "complete"}},
        ]
        turns = _events_to_turns(messages, collected)

        # user, assistant (with action), action_result, assistant (analysis)
        assert len(turns) == 4

        # Assistant turn with action
        assistant_turn = turns[1]
        assert assistant_turn["role"] == "assistant"
        assert assistant_turn["content"] == "Let me scan..."
        assert assistant_turn["action"] == action_data
        assert assistant_turn["action_status"] == "done"

        # Action result turn
        result_turn = turns[2]
        assert result_turn["role"] == "action_result"
        assert result_turn["action_result"] == result_data

        # Final assistant analysis
        assert turns[3]["role"] == "assistant"
        assert turns[3]["content"] == "Port 80 is open."


class TestEventsToTurnsEmpty:
    """Empty or minimal event lists."""

    def test_no_events(self):
        turns = _events_to_turns([], [])
        assert turns == []

    def test_only_user_messages(self):
        messages = [
            {"role": "user", "content": "Hi"},
            {"role": "system", "content": "You are an assistant"},
        ]
        turns = _events_to_turns(messages, [])
        # Only user messages, system messages are skipped
        assert len(turns) == 1
        assert turns[0]["role"] == "user"

    def test_done_only(self):
        messages = [{"role": "user", "content": "test"}]
        collected = [{"event": "done", "data": {"reason": "complete"}}]
        turns = _events_to_turns(messages, collected)
        assert len(turns) == 1
        assert turns[0]["role"] == "user"


class TestEventsToTurnsMultipleTurns:
    """Multiple turn cycles."""

    def test_three_turns(self):
        messages = [{"role": "user", "content": "Start recon"}]
        collected = [
            {"event": "turn", "data": {"turn": 1}},
            {"event": "text", "data": {"content": "Starting..."}},
            {"event": "action", "data": {"action": {"type": "plugin", "plugin": "nmap"}}},
            {"event": "action_result", "data": {"result": {"items": []}}},
            {"event": "turn", "data": {"turn": 2}},
            {"event": "text", "data": {"content": "Now scanning vuln..."}},
            {"event": "action", "data": {"action": {"type": "plugin", "plugin": "nikto"}}},
            {"event": "action_result", "data": {"result": {"items": [{"vuln": "xss"}]}}},
            {"event": "turn", "data": {"turn": 3}},
            {"event": "text", "data": {"content": "Found XSS. Done."}},
            {"event": "done", "data": {"reason": "complete"}},
        ]
        turns = _events_to_turns(messages, collected)

        roles = [t["role"] for t in turns]
        assert roles == [
            "user",
            "assistant",
            "action_result",
            "assistant",
            "action_result",
            "assistant",
        ]

        # Verify turn numbers
        assert turns[1]["turn_number"] == 1
        assert turns[3]["turn_number"] == 2
        assert turns[5]["turn_number"] == 3
        assert turns[5]["content"] == "Found XSS. Done."


class TestEventsToTurnsActionError:
    """Error event handling."""

    def test_action_error_with_content(self):
        messages = [{"role": "user", "content": "test"}]
        collected = [
            {"event": "turn", "data": {"turn": 1}},
            {"event": "text", "data": {"content": "Trying..."}},
            {"event": "action", "data": {"action": {"type": "shell", "command": "ls"}}},
            {
                "event": "action_error",
                "data": {"error": "Permission denied", "error_type": "fatal"},
            },
            {"event": "done", "data": {"reason": "error"}},
        ]
        turns = _events_to_turns(messages, collected)

        assert len(turns) == 2  # user + assistant with error
        err_turn = turns[1]
        assert err_turn["role"] == "assistant"
        assert err_turn["content"] == "Trying..."
        assert err_turn["action_result"]["error"] == "Permission denied"
        assert err_turn["action_status"] == "error"

    def test_action_error_without_content(self):
        messages = [{"role": "user", "content": "test"}]
        collected = [
            {"event": "turn", "data": {"turn": 1}},
            {
                "event": "action_error",
                "data": {"error": "Malformed XML", "error_type": "malformed"},
            },
            {"event": "done", "data": {"reason": "error"}},
        ]
        turns = _events_to_turns(messages, collected)

        assert len(turns) == 2  # user + action_result with error
        err_turn = turns[1]
        assert err_turn["role"] == "action_result"
        assert err_turn["action_result"]["error_type"] == "malformed"


# =====================================================================
# Multi-action turns
# =====================================================================


class TestEventsToTurnsMultiAction:
    """Multiple actions in a single turn."""

    def test_multi_action_stored_as_list(self):
        messages = [{"role": "user", "content": "Scan all ports"}]
        action1 = {"type": "plugin", "plugin": "port-scan", "params": {"port": "80"}}
        action2 = {"type": "plugin", "plugin": "port-scan", "params": {"port": "443"}}
        result1 = {"items": [{"port": 80, "state": "open"}]}
        result2 = {"items": [{"port": 443, "state": "open"}]}

        collected = [
            {"event": "turn", "data": {"turn": 1}},
            {"event": "text", "data": {"content": "Scanning multiple ports..."}},
            {"event": "action", "data": {"action": action1, "actions": [action1, action2]}},
            {"event": "action_status", "data": {"status": "executing", "count": 2}},
            {"event": "action_result", "data": {"result": result1, "action": action1}},
            {"event": "action_result", "data": {"result": result2, "action": action2}},
            {"event": "done", "data": {"reason": "complete"}},
        ]
        turns = _events_to_turns(messages, collected)

        # user, assistant (with actions as list), result1, result2
        assert len(turns) == 4
        assistant_turn = turns[1]
        assert assistant_turn["role"] == "assistant"
        assert isinstance(assistant_turn["action"], list)
        assert len(assistant_turn["action"]) == 2
        assert assistant_turn["action"][0]["plugin"] == "port-scan"
        assert assistant_turn["action"][1]["params"]["port"] == "443"

    def test_single_action_remains_dict(self):
        """Backward compat: single action event still stores as dict."""
        messages = [{"role": "user", "content": "test"}]
        action = {"type": "plugin", "plugin": "nmap"}
        collected = [
            {"event": "turn", "data": {"turn": 1}},
            {"event": "text", "data": {"content": "Scanning..."}},
            {"event": "action", "data": {"action": action}},
            {"event": "action_result", "data": {"result": {"items": []}}},
            {"event": "done", "data": {"reason": "complete"}},
        ]
        turns = _events_to_turns(messages, collected)
        assistant_turn = turns[1]
        assert isinstance(assistant_turn["action"], dict)
        assert assistant_turn["action"]["plugin"] == "nmap"


class TestDigestMultiAction:
    """build_session_digest handles list actions."""

    def _make_turn(self, **kwargs):
        turn = MagicMock()
        turn.role = kwargs.get("role", "assistant")
        turn.content = kwargs.get("content", "")
        turn.turn_number = kwargs.get("turn_number", 0)
        turn.action = kwargs.get("action", None)
        turn.action_result = kwargs.get("action_result", None)
        return turn

    def test_multi_action_digest(self):
        turns = [
            self._make_turn(
                role="assistant",
                content="Running parallel scans",
                turn_number=1,
                action=[
                    {"type": "plugin", "plugin": "port-scan", "params": {"port": "80"}},
                    {"type": "shell", "command": "curl http://target/"},
                ],
            ),
        ]
        digest = build_session_digest(turns)
        assert "[Action] plugin: port-scan" in digest
        assert "[Action] shell: curl" in digest
        lines = digest.split("\n")
        action_lines = [line for line in lines if line.startswith("[Action]")]
        assert len(action_lines) == 2


# =====================================================================
# Phase 2: Knowledge extraction helpers
# =====================================================================


class TestStripNullBytes:
    """_strip_null_bytes removes PostgreSQL-incompatible NULL bytes."""

    def test_none_passthrough(self):
        assert _strip_null_bytes(None) is None

    def test_clean_string_unchanged(self):
        assert _strip_null_bytes("hello world") == "hello world"

    def test_null_byte_in_string(self):
        assert _strip_null_bytes("before\x00after") == "beforeafter"

    def test_null_byte_in_dict(self):
        result = _strip_null_bytes({"stdout": "data\x00here", "code": 0})
        assert result["stdout"] == "datahere"
        assert result["code"] == 0

    def test_unicode_escape_in_dict(self):
        result = _strip_null_bytes({"html": "a\\u0000b"})
        assert "\\u0000" not in str(result)

    def test_null_byte_in_list(self):
        result = _strip_null_bytes(["ok\x00bad", "clean"])
        assert result == ["okbad", "clean"]

    def test_int_passthrough(self):
        assert _strip_null_bytes(42) == 42


class TestCompressActionResult:
    """_compress_action_result produces compact strings."""

    def test_none_result(self):
        assert _compress_action_result(None) == "(no output)"

    def test_empty_dict(self):
        assert _compress_action_result({}) == "(no output)"

    def test_stdout_result(self):
        result = {"stdout": "PHP Version 5.2.17", "exit_code": 0}
        compressed = _compress_action_result(result)
        assert "exit_code=0" in compressed
        assert "PHP Version" in compressed

    def test_error_result(self):
        result = {"error": "Permission denied", "exit_code": 1}
        compressed = _compress_action_result(result)
        assert "ERROR: Permission denied" in compressed

    def test_items_result(self):
        result = {"items": [{"port": 80}, {"port": 443}]}
        compressed = _compress_action_result(result)
        assert "2 result(s)" in compressed

    def test_long_stdout_truncated(self):
        result = {"stdout": "x" * 1000}
        compressed = _compress_action_result(result)
        assert len(compressed) < 1000


class TestBuildSessionDigest:
    """build_session_digest converts SessionTurn objects to compact text."""

    def _make_turn(self, **kwargs):
        turn = MagicMock()
        turn.role = kwargs.get("role", "assistant")
        turn.content = kwargs.get("content", "")
        turn.turn_number = kwargs.get("turn_number", 0)
        turn.action = kwargs.get("action", None)
        turn.action_result = kwargs.get("action_result", None)
        return turn

    def test_user_turn(self):
        turns = [self._make_turn(role="user", content="Target: http://10.0.0.1")]
        digest = build_session_digest(turns)
        assert "[User] Target: http://10.0.0.1" in digest

    def test_assistant_with_plugin_action(self):
        turns = [
            self._make_turn(
                role="assistant",
                content="Scanning...",
                turn_number=1,
                action={"type": "plugin", "plugin": "nmap", "params": {"target": "10.0.0.1"}},
            ),
        ]
        digest = build_session_digest(turns)
        assert "[Turn 1]" in digest
        assert "[Action] plugin: nmap" in digest

    def test_assistant_with_shell_action(self):
        turns = [
            self._make_turn(
                role="assistant",
                content="Running command",
                turn_number=2,
                action={"type": "shell", "command": "curl http://target/"},
            ),
        ]
        digest = build_session_digest(turns)
        assert "shell: curl" in digest

    def test_action_result_turn(self):
        turns = [
            self._make_turn(
                role="action_result",
                action_result={"stdout": "Found flag!", "exit_code": 0},
            ),
        ]
        digest = build_session_digest(turns)
        assert "[Result]" in digest
        assert "Found flag!" in digest

    def test_full_session_digest(self):
        turns = [
            self._make_turn(role="user", content="Exploit ShellShock"),
            self._make_turn(
                role="assistant",
                content="Analyzing...",
                turn_number=1,
                action={
                    "type": "shell",
                    "command": "curl -H 'User-Agent: () { :; }; echo vulnerable' http://target/",
                },
            ),
            self._make_turn(
                role="action_result",
                action_result={"stdout": "vulnerable", "exit_code": 0},
            ),
            self._make_turn(
                role="assistant",
                content="The target is vulnerable.",
                turn_number=2,
            ),
        ]
        digest = build_session_digest(turns)
        lines = digest.split("\n")
        assert len(lines) == 5  # user, turn1, action, result, turn2


class TestParseExtractionJson:
    """_parse_extraction_json handles raw AI output."""

    def test_plain_json(self):
        raw = '{"scenario": "test", "outcome": "success"}'
        result = _parse_extraction_json(raw)
        assert result["scenario"] == "test"

    def test_markdown_fenced_json(self):
        raw = '```json\n{"scenario": "test", "outcome": "success"}\n```'
        result = _parse_extraction_json(raw)
        assert result["scenario"] == "test"

    def test_markdown_fenced_no_lang(self):
        raw = '```\n{"scenario": "fenced"}\n```'
        result = _parse_extraction_json(raw)
        assert result["scenario"] == "fenced"


class TestSanitizeExtraction:
    """_sanitize_extraction normalizes and validates fields."""

    def test_valid_data(self):
        data = {
            "scenario": "SQL injection on login",
            "target_type": "web",
            "vulnerability_type": "sqli",
            "tools_used": ["sqlmap", "curl"],
            "attack_chain": "Discovered SQLi in login form",
            "outcome": "success",
            "key_findings": "Union-based SQLi",
            "tags": ["sqli", "web"],
            "summary": "Found and exploited SQLi",
        }
        result = _sanitize_extraction(data)
        assert result["target_type"] == "web"
        assert result["vulnerability_type"] == "sqli"
        assert result["outcome"] == "success"

    def test_invalid_enums_fallback_to_defaults(self):
        data = {
            "target_type": "spaceship",
            "vulnerability_type": "magic",
            "outcome": "maybe",
        }
        result = _sanitize_extraction(data)
        assert result["target_type"] == "other"
        assert result["vulnerability_type"] == "other"
        assert result["outcome"] == "partial"

    def test_missing_fields_use_defaults(self):
        result = _sanitize_extraction({})
        assert result["scenario"] == ""
        assert result["target_type"] == "other"
        assert result["tools_used"] == []
        assert result["tags"] == []

    def test_non_list_tools_become_empty(self):
        data = {"tools_used": "nmap", "tags": 123}
        result = _sanitize_extraction(data)
        assert result["tools_used"] == []
        assert result["tags"] == []

    def test_long_strings_truncated(self):
        data = {"scenario": "x" * 1000, "attack_chain": "y" * 5000}
        result = _sanitize_extraction(data)
        assert len(result["scenario"]) == 500
        assert len(result["attack_chain"]) == 2000


# =====================================================================
# Phase 3: RAG / Embedding helpers
# =====================================================================


class TestBuildEmbeddingText:
    """build_embedding_text constructs text for embedding from a knowledge entry."""

    def test_full_entry(self):
        entry = {
            "scenario": "SQL injection on login form",
            "summary": "Found union-based SQLi",
            "key_findings": "MySQL 5.7, union select works",
            "target_type": "web",
            "vulnerability_type": "sqli",
            "tags": ["sqli", "mysql", "web"],
            "tools_used": ["sqlmap", "curl"],
        }
        text = build_embedding_text(entry)
        assert "SQL injection on login form" in text
        assert "union-based SQLi" in text
        assert "MySQL 5.7" in text
        assert "web" in text
        assert "sqli" in text
        assert "sqlmap" in text

    def test_missing_fields(self):
        entry = {"scenario": "Basic scan"}
        text = build_embedding_text(entry)
        assert "Basic scan" in text
        # Should not crash on missing fields
        assert "Tags" not in text
        assert "Tools" not in text

    def test_empty_entry(self):
        text = build_embedding_text({})
        assert text == ""

    def test_orm_like_object(self):
        mock_entry = MagicMock()
        mock_entry.scenario = "ShellShock exploit"
        mock_entry.summary = "Exploited via User-Agent header"
        mock_entry.key_findings = "CGI endpoint vulnerable"
        mock_entry.target_type = "web"
        mock_entry.vulnerability_type = "shellshock"
        mock_entry.tags = ["shellshock", "cgi"]
        mock_entry.tools_used = ["curl"]
        text = build_embedding_text(mock_entry)
        assert "ShellShock exploit" in text
        assert "CGI endpoint" in text
        assert "shellshock" in text


class TestFormatRagContext:
    """format_rag_context builds a system prompt section."""

    def _make_entry(self, **kwargs):
        entry = MagicMock()
        entry.scenario = kwargs.get("scenario", "Test scenario")
        entry.target_type = kwargs.get("target_type", "web")
        entry.vulnerability_type = kwargs.get("vulnerability_type", "sqli")
        entry.tools_used = kwargs.get("tools_used", ["nmap"])
        entry.key_findings = kwargs.get("key_findings", "Port 80 open")
        entry.outcome = kwargs.get("outcome", "success")
        return entry

    def test_empty_results(self):
        result = format_rag_context([])
        assert result == ""

    def test_single_result(self):
        entry = self._make_entry(scenario="SQL injection test")
        result = format_rag_context([(entry, 0.85)])
        assert "SQL injection test" in result
        assert "85%" in result
        assert "nmap" in result
        assert "Port 80 open" in result

    def test_multiple_results(self):
        e1 = self._make_entry(scenario="Scenario A")
        e2 = self._make_entry(scenario="Scenario B")
        result = format_rag_context([(e1, 0.9), (e2, 0.7)])
        assert "Scenario A" in result
        assert "Scenario B" in result
        assert "90%" in result
        assert "70%" in result

    def test_chinese_lang(self):
        entry = self._make_entry(scenario="SQL注入测试")
        result = format_rag_context([(entry, 0.85)], lang="zh")
        assert "相关历史经验" in result
        assert "目标类型" in result
        assert "SQL注入测试" in result

    def test_english_lang(self):
        entry = self._make_entry(scenario="SQL injection test")
        result = format_rag_context([(entry, 0.85)], lang="en")
        assert "Related Historical Experience" in result
        assert "Target type" in result
