"""Tests for workflow service pure functions."""

import pytest

from app.services.workflow_service import (
    _summarize_result,
    build_execution_plan,
    build_reflection_prompt,
    extract_workflow_from_turns,
)


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


# ---------------------------------------------------------------------------
# build_reflection_prompt
# ---------------------------------------------------------------------------


class TestBuildReflectionPrompt:
    def test_reflection_prompt_basic(self):
        prompt = build_reflection_prompt(
            workflow_name="Port Scan Chain",
            completed_steps=[],
            current_label="port-scan",
            current_result={"items": [{"port": 80}, {"port": 443}]},
            step=1,
            total=3,
            lang="en",
        )
        assert "step 1/3" in prompt
        assert "port-scan" in prompt
        assert '"port": 80' in prompt
        assert "English" in prompt
        assert "**Findings**" in prompt
        assert "**Significance**" in prompt
        assert "**Next**" in prompt

    def test_reflection_prompt_with_history(self):
        completed = [
            {"label": "port-scan", "type": "plugin", "result_summary": "5 result(s)"},
            {"label": "dir-scan", "type": "plugin", "result_summary": "3 result(s)"},
        ]
        prompt = build_reflection_prompt(
            workflow_name="Full Chain",
            completed_steps=completed,
            current_label="sql-inject",
            current_result={"items": [{"vulnerable": True}]},
            step=3,
            total=4,
            lang="en",
        )
        assert "Completed steps:" in prompt
        assert "port-scan" in prompt
        assert "dir-scan" in prompt
        assert "5 result(s)" in prompt
        assert "sql-inject" in prompt

    def test_reflection_prompt_empty_result(self):
        prompt = build_reflection_prompt(
            workflow_name="Test",
            completed_steps=[],
            current_label="scan",
            current_result={},
            step=1,
            total=1,
            lang="en",
        )
        assert "step 1/1" in prompt
        assert "{}" in prompt

    def test_reflection_prompt_lang_zh(self):
        prompt = build_reflection_prompt(
            workflow_name="Test",
            completed_steps=[],
            current_label="scan",
            current_result={"items": []},
            step=1,
            total=2,
            lang="zh-CN",
        )
        assert "Simplified Chinese" in prompt


# ---------------------------------------------------------------------------
# build_execution_plan (DAG)
# ---------------------------------------------------------------------------


class TestBuildExecutionPlan:
    def test_linear_chain(self):
        """Linear chain: each level has exactly 1 node."""
        nodes = [
            {"id": "start", "type": "start"},
            {"id": "a", "type": "action-plugin"},
            {"id": "b", "type": "action-plugin"},
            {"id": "end", "type": "end"},
        ]
        edges = [
            {"source": "start", "target": "a"},
            {"source": "a", "target": "b"},
            {"source": "b", "target": "end"},
        ]
        levels, parents = build_execution_plan(nodes, edges)
        # start has no deps → level 0, a depends on start → level 1, etc.
        assert len(levels) >= 3
        # Each level should have at most 1 action node in linear chain
        action_levels = [lv for lv in levels if any(n not in ("start", "end") for n in lv)]
        assert all(len(lv) <= 2 for lv in action_levels)  # could include start/end in same level

    def test_diamond_dag(self):
        """Diamond: start→a,b→end → a and b should be in the same level."""
        nodes = [
            {"id": "start", "type": "start"},
            {"id": "a", "type": "action-plugin"},
            {"id": "b", "type": "action-plugin"},
            {"id": "end", "type": "end"},
        ]
        edges = [
            {"source": "start", "target": "a"},
            {"source": "start", "target": "b"},
            {"source": "a", "target": "end"},
            {"source": "b", "target": "end"},
        ]
        levels, parents = build_execution_plan(nodes, edges)
        # Find the level containing both a and b
        ab_level = None
        for level in levels:
            if "a" in level and "b" in level:
                ab_level = level
                break
        assert ab_level is not None, "a and b should be in the same level"

    def test_fan_out_fan_in(self):
        """Fan-out: scan→a,b,c→end → a,b,c should be parallel."""
        nodes = [
            {"id": "scan", "type": "action-plugin"},
            {"id": "a", "type": "action-plugin"},
            {"id": "b", "type": "action-plugin"},
            {"id": "c", "type": "action-plugin"},
            {"id": "end", "type": "end"},
        ]
        edges = [
            {"source": "scan", "target": "a"},
            {"source": "scan", "target": "b"},
            {"source": "scan", "target": "c"},
            {"source": "a", "target": "end"},
            {"source": "b", "target": "end"},
            {"source": "c", "target": "end"},
        ]
        levels, parents = build_execution_plan(nodes, edges)
        # Find the level containing a, b, c
        parallel_level = None
        for level in levels:
            if "a" in level and "b" in level and "c" in level:
                parallel_level = level
                break
        assert parallel_level is not None, "a, b, c should be in the same level"

    def test_cycle_raises(self):
        """Cycle should raise ValueError."""
        nodes = [
            {"id": "a", "type": "action-plugin"},
            {"id": "b", "type": "action-plugin"},
        ]
        edges = [
            {"source": "a", "target": "b"},
            {"source": "b", "target": "a"},
        ]
        with pytest.raises(ValueError, match="cycle"):
            build_execution_plan(nodes, edges)

    def test_empty_graph(self):
        """Empty graph returns empty levels."""
        levels, parents = build_execution_plan([], [])
        assert levels == []
        assert parents == {}

    def test_single_node(self):
        """Single node graph."""
        nodes = [{"id": "a", "type": "action-plugin"}]
        levels, parents = build_execution_plan(nodes, [])
        assert len(levels) == 1
        assert "a" in levels[0]

    def test_complex_dag(self):
        """Complex DAG: start→A,B; A,B→C; B→D; C,D→end."""
        nodes = [
            {"id": "start", "type": "start"},
            {"id": "A", "type": "action-plugin"},
            {"id": "B", "type": "action-plugin"},
            {"id": "C", "type": "action-plugin"},
            {"id": "D", "type": "action-plugin"},
            {"id": "end", "type": "end"},
        ]
        edges = [
            {"source": "start", "target": "A"},
            {"source": "start", "target": "B"},
            {"source": "A", "target": "C"},
            {"source": "B", "target": "C"},
            {"source": "B", "target": "D"},
            {"source": "C", "target": "end"},
            {"source": "D", "target": "end"},
        ]
        levels, parents = build_execution_plan(nodes, edges)
        # A and B should be parallel (same level)
        ab_level = None
        for level in levels:
            if "A" in level and "B" in level:
                ab_level = level
                break
        assert ab_level is not None

        # C depends on both A and B, D depends on B only
        assert parents["C"] == {"A", "B"}
        assert parents["D"] == {"B"}

        # Flatten levels to check ordering
        flat = [nid for level in levels for nid in level]
        assert flat.index("start") < flat.index("A")
        assert flat.index("start") < flat.index("B")
        assert flat.index("A") < flat.index("C")
        assert flat.index("B") < flat.index("C")
        assert flat.index("B") < flat.index("D")


# ---------------------------------------------------------------------------
# Multi-action workflow extraction
# ---------------------------------------------------------------------------


class TestExtractWorkflowMultiAction:
    def test_multi_action_turn_creates_fan_out(self):
        """A turn with list action should create fan-out nodes."""
        turns = [
            {
                "role": "assistant",
                "content": "Running parallel scans",
                "action": [
                    {"type": "plugin", "plugin": "port-scan", "params": {"port": "80"}},
                    {"type": "plugin", "plugin": "port-scan", "params": {"port": "443"}},
                ],
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
                "role": "action_result",
                "content": "",
                "action": None,
                "action_result": {"items": [{"port": 443}]},
                "action_status": None,
            },
        ]
        nodes, edges = extract_workflow_from_turns(turns, "Fan-out Test")
        # start + 2 action nodes + end = 4
        assert len(nodes) == 4
        action_nodes = [n for n in nodes if n["type"] not in ("start", "end")]
        assert len(action_nodes) == 2

        # Both action nodes should have edges from start
        start_edges = [e for e in edges if e["source"] == "start"]
        assert len(start_edges) == 2

        # Both action nodes should have edges to end
        end_edges = [e for e in edges if e["target"] == "end"]
        assert len(end_edges) == 2


# ---------------------------------------------------------------------------
# Deduplication
# ---------------------------------------------------------------------------


class TestExtractWorkflowDedup:
    def test_extract_workflow_dedup(self):
        """Duplicate actions across turns should be deduplicated."""
        turns = [
            # Turn 1: actions A and B
            {
                "role": "assistant",
                "content": "Running A and B",
                "action": [
                    {"type": "shell", "command": "curl http://target/?id=1' UNION SELECT 1--"},
                    {"type": "shell", "command": "curl http://target/?id=1' UNION SELECT 1,2--"},
                ],
                "action_result": None,
                "action_status": "done",
            },
            {
                "role": "action_result",
                "content": "",
                "action": None,
                "action_result": {"stdout": "ok"},
                "action_status": None,
            },
            {
                "role": "action_result",
                "content": "",
                "action": None,
                "action_result": {"stdout": "ok"},
                "action_status": None,
            },
            # Turn 2: retry sends A, B (duplicate), and new C
            {
                "role": "assistant",
                "content": "Retrying with extra",
                "action": [
                    {"type": "shell", "command": "curl http://target/?id=1' UNION SELECT 1--"},
                    {"type": "shell", "command": "curl http://target/?id=1' UNION SELECT 1,2--"},
                    {"type": "shell", "command": "curl http://target/?id=1' UNION SELECT 1,2,3--"},
                ],
                "action_result": None,
                "action_status": "done",
            },
            {
                "role": "action_result",
                "content": "",
                "action": None,
                "action_result": {"stdout": "ok"},
                "action_status": None,
            },
            {
                "role": "action_result",
                "content": "",
                "action": None,
                "action_result": {"stdout": "ok"},
                "action_status": None,
            },
            {
                "role": "action_result",
                "content": "",
                "action": None,
                "action_result": {"stdout": "ok"},
                "action_status": None,
            },
        ]
        nodes, edges = extract_workflow_from_turns(turns, "Dedup Test")
        action_nodes = [n for n in nodes if n["type"] not in ("start", "end")]
        # Should be 3 unique actions, not 5
        assert len(action_nodes) == 3

    def test_dedup_preserves_different_params(self):
        """Same plugin with different params should NOT be deduped."""
        turns = [
            {
                "role": "assistant",
                "content": "",
                "action": {"type": "plugin", "plugin": "port-scan", "params": {"port": "80"}},
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
                "content": "",
                "action": {"type": "plugin", "plugin": "port-scan", "params": {"port": "443"}},
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
        nodes, edges = extract_workflow_from_turns(turns, "Diff Params")
        action_nodes = [n for n in nodes if n["type"] not in ("start", "end")]
        assert len(action_nodes) == 2
