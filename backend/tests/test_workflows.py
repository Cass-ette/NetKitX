"""Tests for workflow service pure functions."""

from app.services.workflow_service import _summarize_result, extract_workflow_from_turns


# ---------------------------------------------------------------------------
# _summarize_result
# ---------------------------------------------------------------------------


class TestSummarizeResult:
    def test_none(self):
        assert _summarize_result(None) == ""

    def test_error(self):
        result = {"error": "Connection refused"}
        assert _summarize_result(result) == "Error: Connection refused"

    def test_items(self):
        result = {"items": [{"port": 80}, {"port": 443}, {"port": 22}]}
        assert _summarize_result(result) == "3 result(s)"

    def test_stdout(self):
        result = {"stdout": "root:x:0:0:root:/root:/bin/bash\nnobody:x:65534:65534:..."}
        assert _summarize_result(result) == "root:x:0:0:root:/root:/bin/bash"

    def test_exit_code(self):
        result = {"exit_code": 0}
        assert _summarize_result(result) == "exit_code=0"

    def test_empty(self):
        assert _summarize_result({}) == ""


# ---------------------------------------------------------------------------
# extract_workflow_from_turns
# ---------------------------------------------------------------------------


class TestExtractWorkflowFromTurns:
    def test_empty_turns(self):
        nodes, edges = extract_workflow_from_turns([], "Test Session")
        assert len(nodes) == 2  # start + end
        assert nodes[0]["type"] == "start"
        assert nodes[1]["type"] == "end"
        assert len(edges) == 1
        assert edges[0]["source"] == "start"
        assert edges[0]["target"] == "end"

    def test_single_plugin_action(self):
        turns = [
            {
                "role": "assistant",
                "content": "Let me scan the target.",
                "action": {
                    "type": "plugin",
                    "plugin": "port-scan",
                    "params": {"target": "10.0.0.1"},
                    "reason": "Scan open ports",
                },
                "action_result": None,
                "action_status": "done",
            },
            {
                "role": "action_result",
                "content": "",
                "action": None,
                "action_result": {"items": [{"port": 80}, {"port": 443}]},
                "action_status": None,
            },
        ]
        nodes, edges = extract_workflow_from_turns(turns, "Scan Test")
        assert len(nodes) == 3  # start + action-1 + end
        assert nodes[1]["type"] == "action-plugin"
        assert nodes[1]["label"] == "port-scan"
        assert nodes[1]["data"]["plugin"] == "port-scan"
        assert nodes[1]["data"]["result_summary"] == "2 result(s)"
        assert len(edges) == 2

    def test_single_shell_action(self):
        turns = [
            {
                "role": "assistant",
                "content": "Running nmap",
                "action": {
                    "type": "shell",
                    "command": "nmap -sV 10.0.0.1",
                    "reason": "Service detection",
                },
                "action_result": None,
                "action_status": "done",
            },
            {
                "role": "action_result",
                "content": "",
                "action": None,
                "action_result": {"stdout": "22/tcp open ssh\n80/tcp open http"},
                "action_status": None,
            },
        ]
        nodes, edges = extract_workflow_from_turns(turns, "Shell Test")
        assert nodes[1]["type"] == "action-shell"
        assert "nmap" in nodes[1]["label"]
        assert nodes[1]["data"]["result_summary"] == "22/tcp open ssh"

    def test_multiple_actions(self):
        turns = [
            {
                "role": "assistant",
                "content": "Step 1",
                "action": {"type": "plugin", "plugin": "port-scan", "params": {}},
                "action_result": None,
                "action_status": "done",
            },
            {
                "role": "action_result",
                "content": "",
                "action": None,
                "action_result": {"items": [{"port": 80}]},
                "action_status": None,
            },
            {
                "role": "assistant",
                "content": "Step 2",
                "action": {"type": "plugin", "plugin": "dir-scan", "params": {}},
                "action_result": None,
                "action_status": "done",
            },
            {
                "role": "action_result",
                "content": "",
                "action": None,
                "action_result": {"items": [{"path": "/admin"}]},
                "action_status": None,
            },
            {
                "role": "assistant",
                "content": "Step 3",
                "action": {"type": "plugin", "plugin": "sql-inject", "params": {}},
                "action_result": None,
                "action_status": "done",
            },
            {
                "role": "action_result",
                "content": "",
                "action": None,
                "action_result": {"items": []},
                "action_status": None,
            },
        ]
        nodes, edges = extract_workflow_from_turns(turns, "Multi Step")
        # start + 3 actions + end = 5 nodes, 4 edges
        assert len(nodes) == 5
        assert len(edges) == 4
        assert nodes[1]["label"] == "port-scan"
        assert nodes[2]["label"] == "dir-scan"
        assert nodes[3]["label"] == "sql-inject"

    def test_action_with_result_summary(self):
        turns = [
            {
                "role": "assistant",
                "content": "",
                "action": {
                    "type": "plugin",
                    "plugin": "whois",
                    "params": {"target": "example.com"},
                },
                "action_result": None,
                "action_status": "done",
            },
            {
                "role": "action_result",
                "content": "",
                "action": None,
                "action_result": {
                    "items": [
                        {"registrar": "GoDaddy"},
                        {"ns": "ns1.example.com"},
                        {"ns": "ns2.example.com"},
                        {"expires": "2027-01-01"},
                        {"status": "active"},
                    ]
                },
                "action_status": None,
            },
        ]
        nodes, edges = extract_workflow_from_turns(turns, "Whois")
        assert nodes[1]["data"]["result_summary"] == "5 result(s)"

    def test_skips_turns_without_action(self):
        turns = [
            {
                "role": "user",
                "content": "Scan the target",
                "action": None,
                "action_result": None,
                "action_status": None,
            },
            {
                "role": "assistant",
                "content": "I'll scan now.",
                "action": None,
                "action_result": None,
                "action_status": None,
            },
            {
                "role": "assistant",
                "content": "Scanning",
                "action": {"type": "plugin", "plugin": "port-scan", "params": {}},
                "action_result": None,
                "action_status": "done",
            },
            {
                "role": "action_result",
                "content": "",
                "action": None,
                "action_result": {"items": []},
                "action_status": None,
            },
            {
                "role": "assistant",
                "content": "Done scanning.",
                "action": None,
                "action_result": None,
                "action_status": None,
            },
        ]
        nodes, edges = extract_workflow_from_turns(turns, "Skip Test")
        # Only 1 action node extracted
        assert len(nodes) == 3  # start + action-1 + end

    def test_error_result_summary(self):
        turns = [
            {
                "role": "assistant",
                "content": "",
                "action": {"type": "plugin", "plugin": "exploit", "params": {}},
                "action_result": None,
                "action_status": "done",
            },
            {
                "role": "action_result",
                "content": "",
                "action": None,
                "action_result": {"error": "Connection timed out after 30s"},
                "action_status": None,
            },
        ]
        nodes, edges = extract_workflow_from_turns(turns, "Error Test")
        assert nodes[1]["data"]["result_summary"].startswith("Error:")
        assert "timed out" in nodes[1]["data"]["result_summary"]

    def test_action_without_following_result(self):
        """Action at end of turns with no result should still create a node."""
        turns = [
            {
                "role": "assistant",
                "content": "",
                "action": {"type": "plugin", "plugin": "port-scan", "params": {}},
                "action_result": None,
                "action_status": "done",
            },
        ]
        nodes, edges = extract_workflow_from_turns(turns, "No Result")
        assert len(nodes) == 3  # start + action-1 + end
        assert nodes[1]["data"]["result_summary"] == ""

    def test_edge_chain_structure(self):
        turns = [
            {
                "role": "assistant",
                "content": "",
                "action": {"type": "plugin", "plugin": "a", "params": {}},
                "action_result": None,
                "action_status": "done",
            },
            {
                "role": "action_result",
                "content": "",
                "action": None,
                "action_result": {},
                "action_status": None,
            },
            {
                "role": "assistant",
                "content": "",
                "action": {"type": "plugin", "plugin": "b", "params": {}},
                "action_result": None,
                "action_status": "done",
            },
            {
                "role": "action_result",
                "content": "",
                "action": None,
                "action_result": {},
                "action_status": None,
            },
        ]
        nodes, edges = extract_workflow_from_turns(turns, "Chain Test")
        # Verify chain: start -> action-1 -> action-2 -> end
        assert edges[0]["source"] == "start"
        assert edges[0]["target"] == "action-1"
        assert edges[1]["source"] == "action-1"
        assert edges[1]["target"] == "action-2"
        assert edges[2]["source"] == "action-2"
        assert edges[2]["target"] == "end"
