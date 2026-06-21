from __future__ import annotations

import json
import os
import tempfile
import unittest
from io import BytesIO
from pathlib import Path

from ai_debt import mcp_server
from ai_debt.core import capture_payload
from ai_debt.paths import db_path
from ai_debt.schema import connect


class McpHomeTestCase(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.home = Path(self.tmp.name)
        self.previous_home = os.environ.get("AI_DEBT_HOME")
        os.environ["AI_DEBT_HOME"] = str(self.home)

    def tearDown(self) -> None:
        if self.previous_home is None:
            os.environ.pop("AI_DEBT_HOME", None)
        else:
            os.environ["AI_DEBT_HOME"] = self.previous_home
        self.tmp.cleanup()

    def capture_session(self, adapter: str, session_id: str, candidate_id: str) -> str:
        if adapter == "codex":
            mcp_server.call_tool("record_event", {"adapter": "codex", "payload": {"event": "SessionStart", "session_id": session_id, "cwd": str(self.home), "timestamp": "2026-06-22T00:00:00Z"}})
            mcp_server.call_tool("record_event", {"adapter": "codex", "payload": {"event": "PostToolUse", "session_id": session_id, "tool_name": "apply_patch", "summary": "Changed files", "timestamp": "2026-06-22T00:01:00Z"}})
            mcp_server.call_tool("record_event", {"adapter": "codex", "payload": {"event": "SessionEnd", "session_id": session_id, "timestamp": "2026-06-22T00:02:00Z"}})
        else:
            mcp_server.call_tool("record_event", {"adapter": "claude-code", "payload": {"hook_event_name": "SessionStart", "session_id": session_id, "cwd": str(self.home), "timestamp": "2026-06-22T00:00:00Z"}})
            mcp_server.call_tool("record_event", {"adapter": "claude-code", "payload": {"hook_event_name": "PostToolUse", "session_id": session_id, "tool_name": "apply_patch", "summary": "Changed files", "timestamp": "2026-06-22T00:01:00Z"}})
            mcp_server.call_tool("record_event", {"adapter": "claude-code", "payload": {"hook_event_name": "SessionEnd", "session_id": session_id, "timestamp": "2026-06-22T00:02:00Z"}})

        analysis = {
            "session_summary": "MCP integration test.",
            "delegation_points": [{"id": "dp-mcp", "summary": "Agent changed code.", "event_refs": [2], "diff_refs": ["diff.patch"], "transcript_refs": []}],
            "debt_candidates": [
                {
                    "id": candidate_id,
                    "concept": "MCP review flow",
                    "debt_dimension": "verification",
                    "why_it_matters": "The MCP path must match the CLI core flow.",
                    "priority": "P1",
                    "delegation_point_id": "dp-mcp",
                }
            ],
        }
        mcp_server.call_tool("submit_analysis", {"session_id": session_id, "analysis": analysis})
        accepted = mcp_server.call_tool("review_action", {"candidate_id": candidate_id, "action": "accept"})
        return str(accepted["debt_id"])


class McpContractTests(McpHomeTestCase):
    def test_list_tools_contains_required_tools(self) -> None:
        names = {tool["name"] for tool in mcp_server.list_tools()}
        self.assertTrue(
            {
                "record_event",
                "get_status",
                "list_sessions",
                "get_review_input",
                "submit_analysis",
                "review_action",
                "list_inbox",
                "learn_one",
                "check",
                "export_deep_review",
                "cleanup",
                "delete_item",
            }.issubset(names)
        )

    def test_record_event_supports_codex_and_claude_fixtures(self) -> None:
        codex = mcp_server.call_tool("record_event", {"adapter": "codex", "payload": {"event": "SessionStart", "session_id": "codex-mcp", "cwd": str(self.home)}})
        claude = mcp_server.call_tool("record_event", {"adapter": "claude-code", "payload": {"hook_event_name": "SessionStart", "session_id": "claude-mcp", "cwd": str(self.home)}})
        self.assertEqual(codex["event"]["type"], "session_started")
        self.assertEqual(claude["event"]["type"], "session_started")
        self.assertEqual(mcp_server.call_tool("get_status", {})["counts"]["recording"], 2)

    def test_jsonrpc_tools_list_shape(self) -> None:
        response = mcp_server.handle_jsonrpc({"jsonrpc": "2.0", "id": 1, "method": "tools/list", "params": {}})
        self.assertEqual(response["jsonrpc"], "2.0")
        self.assertEqual(response["id"], 1)
        self.assertIn("tools", response["result"])

    def test_jsonrpc_resource_templates_list_shape(self) -> None:
        response = mcp_server.handle_jsonrpc({"jsonrpc": "2.0", "id": 1, "method": "resources/templates/list", "params": {}})
        templates = response["result"]["resourceTemplates"]
        self.assertIn("ai-debt://sessions/{session_id}/review-input", {item["uriTemplate"] for item in templates})

    def test_stdio_accepts_content_length_framing(self) -> None:
        request = json.dumps({"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {}}).encode("utf-8")
        stdin = BytesIO(b"Content-Length: " + str(len(request)).encode("ascii") + b"\r\n\r\n" + request)
        stdout = BytesIO()
        self.assertEqual(mcp_server.serve_stdio(stdin, stdout), 0)
        output = stdout.getvalue()
        self.assertTrue(output.startswith(b"Content-Length:"))
        self.assertIn(b"serverInfo", output)


class McpIntegrationTests(McpHomeTestCase):
    def test_mcp_can_complete_codex_review_learning_and_export(self) -> None:
        debt_id = self.capture_session("codex", "codex-flow", "cand-codex-flow")
        self.assertEqual(mcp_server.call_tool("learn_one", {"item_id": debt_id})["kind"], "debt")
        self.assertEqual(mcp_server.call_tool("check", {"debt_id": debt_id, "answer": "MCP evidence keeps the review path tied to captured events."})["result"], "solid")
        exported = mcp_server.call_tool("export_deep_review", {"session_id": "codex-flow"})
        self.assertTrue(Path(exported["path"]).exists())

    def test_mcp_can_complete_claude_review_flow(self) -> None:
        debt_id = self.capture_session("claude-code", "claude-flow", "cand-claude-flow")
        inbox = mcp_server.call_tool("list_inbox", {})
        self.assertEqual(inbox["items"][0]["debt_id"], debt_id)
        self.assertEqual(mcp_server.call_tool("check", {"debt_id": debt_id, "skip": True})["result"], "skipped")

    def test_mcp_cleanup_and_delete_item_match_core_behavior(self) -> None:
        debt_id = self.capture_session("codex", "delete-flow", "cand-delete-flow")
        self.assertEqual(mcp_server.call_tool("cleanup", {"dry_run": True})["raw_payloads"], [])
        self.assertTrue(mcp_server.call_tool("delete_item", {"target": "debt", "id": debt_id})["deleted"])
        self.assertTrue(mcp_server.call_tool("delete_item", {"target": "session", "id": "delete-flow"})["deleted"])
        self.assertEqual(mcp_server.call_tool("list_sessions", {"limit": 10})["sessions"], [])

    def test_cli_and_mcp_paths_converge_on_session_and_candidate_counts(self) -> None:
        self.capture_session("codex", "mcp-count", "cand-mcp-count")
        capture_payload("codex", {"event": "SessionStart", "session_id": "cli-count", "cwd": str(self.home), "timestamp": "2026-06-22T01:00:00Z"}, self.home)
        capture_payload("codex", {"event": "PostToolUse", "session_id": "cli-count", "tool_name": "apply_patch", "timestamp": "2026-06-22T01:01:00Z"}, self.home)
        capture_payload("codex", {"event": "SessionEnd", "session_id": "cli-count", "timestamp": "2026-06-22T01:02:00Z"}, self.home)
        mcp_server.call_tool(
            "submit_analysis",
            {
                "session_id": "cli-count",
                "analysis": {
                    "session_summary": "CLI-equivalent integration test.",
                    "delegation_points": [{"id": "dp-cli", "summary": "CLI event", "event_refs": [5], "diff_refs": ["diff.patch"], "transcript_refs": []}],
                    "debt_candidates": [{"id": "cand-cli-count", "concept": "CLI review flow", "debt_dimension": "verification", "why_it_matters": "CLI and MCP should share state transitions.", "priority": "P1", "delegation_point_id": "dp-cli"}],
                },
            },
        )
        conn = connect(db_path(self.home))
        try:
            candidate_count = conn.execute("SELECT COUNT(*) FROM debt_candidates").fetchone()[0]
            session_count = conn.execute("SELECT COUNT(*) FROM sessions").fetchone()[0]
        finally:
            conn.close()
        self.assertEqual(candidate_count, 2)
        self.assertEqual(session_count, 2)


if __name__ == "__main__":
    unittest.main()
