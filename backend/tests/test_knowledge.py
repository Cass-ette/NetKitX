"""Unit tests for knowledge service (_events_to_turns logic)."""

from app.services.knowledge_service import _events_to_turns


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
