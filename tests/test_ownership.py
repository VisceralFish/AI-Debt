from __future__ import annotations

import json
import os
import tempfile
import unittest
from contextlib import redirect_stdout
from datetime import datetime, timedelta, timezone
from io import BytesIO
from io import StringIO
from pathlib import Path
from unittest.mock import patch

from ai_debt import mcp_server
from ai_debt.cli import main
from ai_debt.companion import codex_tui_hook_output, run_companion_once
from ai_debt.config import default_config
from ai_debt.core import capture_payload
from ai_debt.maintenance import cleanup_raw_payloads, delete_debt, delete_session, export_task_control_report, schema_is_valid
from ai_debt.ownership import (
    build_ownership_review_input,
    create_ownership_candidates,
    default_profile,
    get_or_create_profile,
    learn_one,
    list_ownership_debts,
    parse_ownership_analysis,
    project_id_for_cwd,
    record_check,
    review_ownership_gap,
    select_pending_review_window,
    update_profile,
)
from ai_debt.paths import db_path
from ai_debt.hooks import CODEX_TUI_HOOK_COMMAND, write_codex_tui_hooks
from ai_debt.profile_setup import collect_profile_answers
from ai_debt.schema import connect, migrate
from ai_debt.store import refresh_session_states, status_counts


class HomeTestCase(unittest.TestCase):
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

    def capture_codex_window(self, session_id: str = "codex-window") -> str:
        capture_payload(
            "codex",
            {"event": "SessionStart", "session_id": session_id, "cwd": str(self.home), "timestamp": "2026-06-22T00:00:00Z"},
            self.home,
        )
        capture_payload(
            "codex",
            {"event": "UserPromptSubmit", "session_id": session_id, "input": "Add ownership MCP review flow", "timestamp": "2026-06-22T00:01:00Z"},
            self.home,
        )
        capture_payload(
            "codex",
            {"event": "PostToolUse", "session_id": session_id, "tool_name": "apply_patch", "summary": "Changed ownership files", "timestamp": "2026-06-22T00:02:00Z"},
            self.home,
        )
        capture_payload(
            "codex",
            {"event": "SessionEnd", "session_id": session_id, "timestamp": "2026-06-22T00:03:00Z"},
            self.home,
        )
        conn = connect(db_path(self.home))
        try:
            window = select_pending_review_window(conn)
            self.assertIsNotNone(window)
            return str(window["id"])
        finally:
            conn.close()

    def ownership_analysis(self, include_rejected: bool = True) -> dict[str, object]:
        gaps: list[dict[str, object]] = [
            {
                "id": "cand-concept",
                "title": "MCP ownership tools",
                "summary": "The new MCP tool surface is the primary product boundary.",
                "dimension": "tool",
                "control_point": "Ownership MCP tools and JSON-RPC dispatch",
                "gap_type": "concept_ownership_gap",
                "gap_reason": "The user needs enough MCP ownership tool knowledge to maintain the main entrypoint.",
                "required_level": "L2",
                "current_level": "L1",
                "priority": "P1",
                "evidence_refs": [{"kind": "event", "ref": "agent_events.id=3", "role": "ai_decision"}],
                "repayment": {
                    "type": "explain_back",
                    "task": "Explain how ownership MCP tools route to the core ownership module.",
                    "validation_criteria": ["Can identify the MCP handler", "Can point to the ownership function called"],
                },
                "knowledge_context": {
                    "introduced_concepts": ["MCP ownership tools"],
                    "user_familiarity": "unknown",
                    "minimum_mastery_level": "L2",
                },
            },
            {
                "id": "cand-design",
                "title": "Review window boundary",
                "summary": "Idle timeout now triggers ownership review windows.",
                "dimension": "architecture",
                "control_point": "Review window creation and closure",
                "gap_type": "unanchored_design_decision",
                "gap_reason": "Window boundaries determine what task evidence is reviewed.",
                "required_level": "L4",
                "current_level": "L2",
                "priority": "P0",
                "evidence_refs": [{"kind": "event", "ref": "agent_events.id=4", "role": "ai_decision"}],
                "repayment": {
                    "type": "compare_alternatives",
                    "task": "Compare session-level review with review-window-level review.",
                    "validation_criteria": ["Can explain idle timeout as trigger, not proof of task end"],
                },
            },
        ]
        if include_rejected:
            gaps.append(
                {
                    "id": "cand-rejected",
                    "title": "Unsupported ownership claim",
                    "summary": "This should fail the evidence gate.",
                    "dimension": "verification",
                    "control_point": "Missing evidence gate",
                    "gap_type": "validation_gap",
                    "gap_reason": "High-risk validation claims require traceable evidence.",
                    "required_level": "L3",
                    "current_level": "L1",
                    "priority": "P1",
                    "repayment": {"type": "break_test", "task": "Add evidence.", "validation_criteria": ["Has evidence"]},
                }
            )
        return {
            "window_summary": "Implemented the ownership MCP path.",
            "task_context": {"task_type": "integration", "confidence": 0.9, "reason": "New MCP tools integrate with existing capture core."},
            "ownership_gaps": gaps,
        }


class OwnershipCoreTests(HomeTestCase):
    def test_schema_is_repeatable_and_valid(self) -> None:
        conn = connect(db_path(self.home))
        try:
            migrate(conn)
            migrate(conn)
            self.assertTrue(schema_is_valid(conn))
            tables = {row["name"] for row in conn.execute("SELECT name FROM sqlite_master WHERE type = 'table'").fetchall()}
            self.assertTrue(
                {
                    "ownership_profiles",
                    "ownership_review_windows",
                    "ownership_gap_candidates",
                    "ownership_debts",
                    "ownership_concepts",
                    "companion_notifications",
                }.issubset(tables)
            )
        finally:
            conn.close()

    def test_profile_uses_cwd_hash_and_can_be_patched(self) -> None:
        project_id = project_id_for_cwd(str(self.home))
        conn = connect(db_path(self.home))
        try:
            migrate(conn)
            profile = get_or_create_profile(conn, project_id)
            self.assertEqual(profile["project_id"], project_id)
            updated = update_profile(conn, project_id, {"target_ownership_level": "L4", "control_contract": {"ai_must_confirm": ["schema migration"]}})
            self.assertEqual(updated["target_ownership_level"], "L4")
            self.assertIn("schema migration", updated["control_contract"]["ai_must_confirm"])
        finally:
            conn.close()

    def test_init_creates_default_project_profile_non_interactively(self) -> None:
        project_id = project_id_for_cwd(str(Path.cwd()))
        output = StringIO()
        with redirect_stdout(output):
            self.assertEqual(main(["init", "claude-code", "--no-profile-setup"]), 0)
        text = output.getvalue()
        self.assertIn("initialized claude-code adapter", text)
        self.assertIn("ownership profile: default created", text)

        conn = connect(db_path(self.home))
        try:
            row = conn.execute("SELECT payload_json FROM ownership_profiles WHERE project_id = ?", (project_id,)).fetchone()
            self.assertIsNotNone(row)
            profile = json.loads(row["payload_json"])
            self.assertEqual(profile["role"], "independent_developer")
            self.assertEqual(profile["target_ownership_level"], "L3")
        finally:
            conn.close()

    def test_repeated_init_does_not_overwrite_existing_profile(self) -> None:
        project_id = project_id_for_cwd(str(Path.cwd()))
        with patch("ai_debt.cli.write_codex_tui_hooks") as write_tui_hooks:
            write_tui_hooks.return_value = Path.cwd() / ".codex" / "hooks.json"
            with redirect_stdout(StringIO()):
                self.assertEqual(main(["init", "codex", "--no-profile-setup"]), 0)
        conn = connect(db_path(self.home))
        try:
            update_profile(conn, project_id, {"role": "tech_lead"})
        finally:
            conn.close()

        output = StringIO()
        with patch("ai_debt.cli.write_codex_tui_hooks") as write_tui_hooks:
            write_tui_hooks.return_value = Path.cwd() / ".codex" / "hooks.json"
            with redirect_stdout(output):
                self.assertEqual(main(["init", "codex", "--no-profile-setup"]), 0)
            write_tui_hooks.assert_called_once_with()
        self.assertIn("ownership profile: already configured", output.getvalue())
        self.assertIn("run /hooks to review and trust", output.getvalue())

        conn = connect(db_path(self.home))
        try:
            profile = json.loads(conn.execute("SELECT payload_json FROM ownership_profiles WHERE project_id = ?", (project_id,)).fetchone()["payload_json"])
            self.assertEqual(profile["role"], "tech_lead")
        finally:
            conn.close()

    def test_init_profile_setup_forces_existing_profile_questionnaire(self) -> None:
        project_id = project_id_for_cwd(str(Path.cwd()))
        conn = connect(db_path(self.home))
        try:
            migrate(conn)
            get_or_create_profile(conn, project_id)
            update_profile(conn, project_id, {"role": "tech_lead"})
        finally:
            conn.close()

        with patch("ai_debt.cli.sys.stdin.isatty", return_value=True):
            with patch("ai_debt.cli.setup_project_profile") as setup_profile:
                setup_profile.return_value = (
                    {**default_profile(project_id), "role": "independent_developer"},
                    True,
                )
                with patch("ai_debt.cli.write_codex_tui_hooks") as write_tui_hooks:
                    write_tui_hooks.return_value = Path.cwd() / ".codex" / "hooks.json"
                    with redirect_stdout(StringIO()):
                        self.assertEqual(main(["init", "codex", "--profile-setup"]), 0)

        self.assertTrue(setup_profile.call_args.kwargs["force"])
        self.assertTrue(setup_profile.call_args.kwargs["interactive"])

    def test_codex_tui_hooks_merge_with_existing_project_hooks(self) -> None:
        codex_dir = self.home / ".codex"
        codex_dir.mkdir()
        path = codex_dir / "hooks.json"
        path.write_text(
            json.dumps(
                {
                    "hooks": {
                        "Stop": [
                            {
                                "hooks": [
                                    {"type": "command", "command": "other-tool stop"}
                                ]
                            }
                        ]
                    }
                }
            ),
            encoding="utf-8",
        )

        written = write_codex_tui_hooks(self.home)
        document = json.loads(written.read_text(encoding="utf-8"))

        self.assertEqual(written, path)
        self.assertEqual(
            document["hooks"]["Stop"][0]["hooks"][0]["command"],
            "other-tool stop",
        )
        for event_name in ("SessionStart", "UserPromptSubmit", "Stop"):
            commands = [
                handler["command"]
                for entry in document["hooks"][event_name]
                for handler in entry["hooks"]
            ]
            self.assertEqual(commands.count(CODEX_TUI_HOOK_COMMAND), 1)

        write_codex_tui_hooks(self.home)
        repeated = json.loads(written.read_text(encoding="utf-8"))
        self.assertEqual(repeated, document)

    def test_profile_show_and_force_setup(self) -> None:
        project_id = project_id_for_cwd(str(Path.cwd()))
        missing_output = StringIO()
        with redirect_stdout(missing_output):
            self.assertEqual(main(["profile", "show"]), 0)
        self.assertIn("ownership profile: not configured", missing_output.getvalue())

        with redirect_stdout(StringIO()):
            self.assertEqual(main(["profile", "setup"]), 0)
        conn = connect(db_path(self.home))
        try:
            update_profile(conn, project_id, {"role": "tech_lead"})
        finally:
            conn.close()

        show_output = StringIO()
        with redirect_stdout(show_output):
            self.assertEqual(main(["profile", "show"]), 0)
        self.assertIn('"role": "tech_lead"', show_output.getvalue())

        with redirect_stdout(StringIO()):
            self.assertEqual(main(["profile", "setup", "--force"]), 0)
        conn = connect(db_path(self.home))
        try:
            profile = json.loads(conn.execute("SELECT payload_json FROM ownership_profiles WHERE project_id = ?", (project_id,)).fetchone()["payload_json"])
            self.assertEqual(profile["role"], "independent_developer")
        finally:
            conn.close()

    def test_profile_questionnaire_uses_chinese_explanatory_labels(self) -> None:
        output = StringIO()
        answers = StringIO("\n\n\n\n\n\ny\n\n\n\n\nReact=L3, SQLite=L2\n")
        profile = collect_profile_answers(default_profile("proj-test"), answers, output)
        text = output.getvalue()

        self.assertIn("Language / 语言", text)
        self.assertIn("为当前项目设置 Ownership Profile", text)
        self.assertIn("独立开发者 - 一个人负责需求、代码、验证和维护", text)
        self.assertIn("线上产品/生产应用 - 面向真实用户", text)
        self.assertIn("L3 能独立维护 - 能定位问题", text)
        self.assertIn("AI 必须先解释", text)
        self.assertIn("L4 能设计取舍并审查方案", text)
        self.assertEqual(profile["language"], "zh")
        self.assertEqual(profile["role"], "independent_developer")
        self.assertEqual(profile["target_ownership_level"], "L3")
        self.assertEqual(profile["tech_familiarity"], {"React": "L3", "SQLite": "L2"})

    def test_profile_questionnaire_supports_english(self) -> None:
        output = StringIO()
        answers = StringIO("2\n2\n2\n3\nauth, payment\nsecurity_regression\ny\nformatting\narchitecture\nnew dependency\nproduct direction\nFastAPI=L2\n")
        profile = collect_profile_answers(default_profile("proj-test"), answers, output)
        text = output.getvalue()

        self.assertIn("Language / 语言", text)
        self.assertIn("Set up the Ownership Profile for this project.", text)
        self.assertIn("Tech lead - you own design direction", text)
        self.assertIn("Production app - real users", text)
        self.assertIn("L4 make design tradeoffs", text)
        self.assertIn("AI must explain first", text)
        self.assertEqual(profile["language"], "en")
        self.assertEqual(profile["role"], "tech_lead")
        self.assertEqual(profile["project_intent"], "production_app")
        self.assertEqual(profile["target_ownership_level"], "L4")
        self.assertEqual(profile["critical_areas"], ["auth", "payment"])
        self.assertEqual(profile["tech_familiarity"], {"FastAPI": "L2"})

    def test_session_end_creates_pending_review_window(self) -> None:
        window_id = self.capture_codex_window()
        conn = connect(db_path(self.home))
        try:
            window = select_pending_review_window(conn, window_id)
            self.assertEqual(window["status"], "pending_ownership_review")
            review_input = build_ownership_review_input(conn, window_id)
            self.assertEqual(review_input["review_window"]["id"], window_id)
            self.assertEqual(review_input["diff_snapshot_scope"], "latest_session_snapshot")
            self.assertIn("expected_output_schema", review_input)
        finally:
            conn.close()

    def test_idle_timeout_promotes_window_to_pending_review(self) -> None:
        capture_payload(
            "codex",
            {"event": "SessionStart", "session_id": "idle-session", "cwd": str(self.home), "timestamp": "2026-06-22T00:00:00Z"},
            self.home,
        )
        conn = connect(db_path(self.home))
        try:
            refresh_session_states(conn, default_config(), datetime(2026, 6, 22, 0, 31, tzinfo=timezone.utc))
            counts = status_counts(conn)
            window = select_pending_review_window(conn)
            self.assertEqual(counts.get("pending_settlement"), 1)
            self.assertEqual(window["status"], "pending_ownership_review")
        finally:
            conn.close()

    def test_companion_once_notifies_pending_settlement_once(self) -> None:
        capture_payload(
            "codex",
            {
                "event": "SessionStart",
                "session_id": "companion-session",
                "cwd": str(self.home),
                "timestamp": "2026-06-22T00:00:00Z",
            },
            self.home,
        )
        output = StringIO()
        first = run_companion_once(self.home, datetime(2026, 6, 22, 0, 31, tzinfo=timezone.utc), output)
        second_output = StringIO()
        second = run_companion_once(self.home, datetime(2026, 6, 22, 0, 32, tzinfo=timezone.utc), second_output)

        self.assertEqual([item.session_id for item in first], ["companion-session"])
        self.assertIn("AI Debt: ownership analysis needed", output.getvalue())
        self.assertIn("run: ai-debt review", output.getvalue())
        conn = connect(db_path(self.home))
        try:
            window = select_pending_review_window(conn)
            self.assertEqual(window["status"], "analysis_requested")
        finally:
            conn.close()
        self.assertEqual(second, [])
        self.assertEqual(second_output.getvalue(), "")

    def test_companion_notifies_each_review_window_in_same_session(self) -> None:
        session_id = "multi-window-session"
        start = datetime.now(timezone.utc).replace(microsecond=0)
        first_tool = start + timedelta(minutes=1)
        first_pending = first_tool + timedelta(minutes=30)
        second_prompt = first_pending + timedelta(minutes=1)
        second_tool = second_prompt + timedelta(minutes=1)
        second_pending = second_tool + timedelta(minutes=31)
        capture_payload(
            "codex",
            {"event": "SessionStart", "session_id": session_id, "cwd": str(self.home), "timestamp": _iso(start)},
            self.home,
        )
        capture_payload(
            "codex",
            {"event": "PostToolUse", "session_id": session_id, "tool_name": "apply_patch", "summary": "First change", "timestamp": _iso(first_tool)},
            self.home,
        )
        first = run_companion_once(self.home, first_pending, StringIO())
        capture_payload(
            "codex",
            {"event": "UserPromptSubmit", "session_id": session_id, "input": "Continue work", "timestamp": _iso(second_prompt)},
            self.home,
        )
        capture_payload(
            "codex",
            {"event": "PostToolUse", "session_id": session_id, "tool_name": "apply_patch", "summary": "Second change", "timestamp": _iso(second_tool)},
            self.home,
        )
        second = run_companion_once(self.home, second_pending, StringIO())

        self.assertEqual(len(first), 1)
        self.assertEqual(len(second), 1)
        self.assertNotEqual(first[0].review_window_id, second[0].review_window_id)

    def test_codex_tui_hook_surfaces_pending_review_as_system_message(self) -> None:
        session_id = "tui-session"
        now = datetime.now(timezone.utc).replace(microsecond=0)
        started_at = now - timedelta(minutes=31)
        capture_payload(
            "codex",
            {
                "hook_event_name": "SessionStart",
                "session_id": session_id,
                "cwd": str(self.home),
                "timestamp": _iso(started_at),
            },
            self.home,
        )
        result = codex_tui_hook_output(
            {
                "hook_event_name": "UserPromptSubmit",
                "session_id": session_id,
                "turn_id": "turn-2",
                "cwd": str(self.home),
                "prompt": "Continue",
                "timestamp": _iso(now),
            },
            self.home,
            now,
        )

        self.assertTrue(result["continue"])
        self.assertIn("等待分析", result["systemMessage"])
        self.assertIn("ai-debt review", result["systemMessage"])
        conn = connect(db_path(self.home))
        try:
            statuses = [
                row["status"]
                for row in conn.execute(
                    "SELECT status FROM ownership_review_windows WHERE session_id = ?",
                    (session_id,),
                ).fetchall()
            ]
            self.assertIn("analysis_requested", statuses)
        finally:
            conn.close()

        repeated = codex_tui_hook_output(
            {
                "hook_event_name": "Stop",
                "session_id": session_id,
                "turn_id": "turn-2",
                "cwd": str(self.home),
                "last_assistant_message": "Done",
                "timestamp": _iso(now + timedelta(minutes=1)),
            },
            self.home,
            now + timedelta(minutes=1),
        )
        self.assertEqual(repeated, {})

    def test_analysis_creates_candidates_and_accept_indexes_concepts(self) -> None:
        window_id = self.capture_codex_window()
        conn = connect(db_path(self.home))
        try:
            created = create_ownership_candidates(conn, window_id, self.ownership_analysis())
            statuses = {item["id"]: item["status"] for item in created}
            self.assertEqual(statuses["cand-design"], "ready")
            self.assertEqual(statuses["cand-concept"], "ready")
            self.assertEqual(statuses["cand-rejected"], "rejected_needs_evidence")

            debt_id = review_ownership_gap(conn, "cand-concept", "accept")
            self.assertIsNotNone(debt_id)
            debts = list_ownership_debts(conn)
            self.assertEqual(len(debts), 1)
            concepts = conn.execute("SELECT concept FROM ownership_concepts WHERE debt_id = ?", (debt_id,)).fetchall()
            self.assertEqual([row["concept"] for row in concepts], ["MCP ownership tools"])

            learning = learn_one(conn, debt_id)
            self.assertEqual(learning["gap_type"], "concept_ownership_gap")
            self.assertIn("MCP ownership tools", learning["check_prompt"])

            result = record_check(
                conn,
                debt_id,
                "The MCP handler dispatches tools/call into ownership functions.",
                {"result": "verified", "reason": "The answer names the route.", "missing_points": []},
            )
            self.assertEqual(result, "verified")
            self.assertEqual(conn.execute("SELECT status FROM ownership_debts WHERE id = ?", (debt_id,)).fetchone()[0], "verified")
        finally:
            conn.close()

    def test_defer_ignore_and_already_know_do_not_create_debt(self) -> None:
        window_id = self.capture_codex_window()
        conn = connect(db_path(self.home))
        try:
            create_ownership_candidates(conn, window_id, self.ownership_analysis(include_rejected=False))
            self.assertIsNone(review_ownership_gap(conn, "cand-design", "defer"))
            self.assertIsNone(review_ownership_gap(conn, "cand-concept", "already_know"))
            self.assertEqual(len(list_ownership_debts(conn)), 0)
            statuses = {
                row["id"]: row["status"]
                for row in conn.execute("SELECT id, status FROM ownership_gap_candidates").fetchall()
            }
            self.assertEqual(statuses["cand-design"], "deferred")
            self.assertEqual(statuses["cand-concept"], "known")
        finally:
            conn.close()

    def test_report_cleanup_delete_and_recovery(self) -> None:
        window_id = self.capture_codex_window("cleanup-session")
        conn = connect(db_path(self.home))
        try:
            create_ownership_candidates(conn, window_id, self.ownership_analysis(include_rejected=False))
            debt_id = review_ownership_gap(conn, "cand-concept", "accept")
            report_path = export_task_control_report(conn, window_id, self.home)
            self.assertTrue(report_path.exists())
            self.assertIn("Task Control Report", report_path.read_text(encoding="utf-8"))
            event_count = conn.execute("SELECT COUNT(*) FROM agent_events").fetchone()[0]
            debt_count = conn.execute("SELECT COUNT(*) FROM ownership_debts").fetchone()[0]
        finally:
            conn.close()

        old_time = datetime(2026, 6, 1, tzinfo=timezone.utc).timestamp()
        for path in (self.home / "journals" / "cleanup-session" / "raw").glob("*.json"):
            os.utime(path, (old_time, old_time))
        cleaned = cleanup_raw_payloads(default_config(), self.home, now=datetime(2026, 6, 22, tzinfo=timezone.utc))
        self.assertGreater(len(cleaned.raw_payloads), 0)

        conn = connect(db_path(self.home))
        try:
            self.assertEqual(conn.execute("SELECT COUNT(*) FROM agent_events").fetchone()[0], event_count)
            self.assertEqual(conn.execute("SELECT COUNT(*) FROM ownership_debts").fetchone()[0], debt_count)
            delete_debt(conn, debt_id)
            self.assertEqual(conn.execute("SELECT COUNT(*) FROM ownership_debts WHERE id = ?", (debt_id,)).fetchone()[0], 0)
            delete_session(conn, "cleanup-session", self.home)
            self.assertEqual(conn.execute("SELECT COUNT(*) FROM sessions WHERE id = ?", ("cleanup-session",)).fetchone()[0], 0)
            self.assertFalse((self.home / "journals" / "cleanup-session").exists())
        finally:
            conn.close()

    def test_invalid_analysis_is_preserved_by_cli(self) -> None:
        window_id = self.capture_codex_window("bad-analysis-session")
        bad_path = self.home / "bad-analysis.json"
        bad_path.write_text("{not json", encoding="utf-8")
        self.assertEqual(main(["review", window_id, "--analysis-file", str(bad_path)]), 1)
        failed_logs = list((self.home / "logs").glob("review_analysis_failed_*.txt"))
        self.assertEqual(len(failed_logs), 1)

    def test_review_without_candidates_shows_analysis_guidance(self) -> None:
        window_id = self.capture_codex_window("analysis-guidance-session")
        output = StringIO()
        with redirect_stdout(output):
            self.assertEqual(main(["review", window_id]), 0)
        text = output.getvalue()
        self.assertIn("AI Debt: ownership analysis needed", text)
        self.assertIn(f"get_ownership_review_input(review_window_id=\"{window_id}\")", text)
        self.assertNotIn('"expected_output_schema"', text)

    def test_review_with_candidates_shows_action_queue(self) -> None:
        window_id = self.capture_codex_window("candidate-guidance-session")
        conn = connect(db_path(self.home))
        try:
            create_ownership_candidates(conn, window_id, self.ownership_analysis(include_rejected=False))
        finally:
            conn.close()
        output = StringIO()
        with redirect_stdout(output):
            self.assertEqual(main(["review", window_id]), 0)
        text = output.getvalue()
        self.assertIn("AI Debt: ownership candidates ready", text)
        self.assertIn("--action accept|ignore|already_know|defer", text)

    def test_doctor_does_not_create_state_on_empty_home(self) -> None:
        self.assertEqual(main(["doctor"]), 1)
        self.assertFalse((self.home / "config.yaml").exists())
        self.assertFalse((self.home / "ai_debt.db").exists())


class OwnershipMcpTests(HomeTestCase):
    def capture_with_mcp(self, adapter: str, session_id: str) -> str:
        if adapter == "codex":
            mcp_server.call_tool("record_event", {"adapter": "codex", "payload": {"event": "SessionStart", "session_id": session_id, "cwd": str(self.home), "timestamp": "2026-06-22T00:00:00Z"}})
            mcp_server.call_tool("record_event", {"adapter": "codex", "payload": {"event": "PostToolUse", "session_id": session_id, "tool_name": "apply_patch", "summary": "Changed files", "timestamp": "2026-06-22T00:01:00Z"}})
            mcp_server.call_tool("record_event", {"adapter": "codex", "payload": {"event": "SessionEnd", "session_id": session_id, "timestamp": "2026-06-22T00:02:00Z"}})
        else:
            mcp_server.call_tool("record_event", {"adapter": "claude-code", "payload": {"hook_event_name": "SessionStart", "session_id": session_id, "cwd": str(self.home), "timestamp": "2026-06-22T00:00:00Z"}})
            mcp_server.call_tool("record_event", {"adapter": "claude-code", "payload": {"hook_event_name": "PostToolUse", "session_id": session_id, "tool_name": "apply_patch", "summary": "Changed files", "timestamp": "2026-06-22T00:01:00Z"}})
            mcp_server.call_tool("record_event", {"adapter": "claude-code", "payload": {"hook_event_name": "SessionEnd", "session_id": session_id, "timestamp": "2026-06-22T00:02:00Z"}})
        window = mcp_server.call_tool("get_pending_review_window", {})["review_window"]
        return str(window["id"])

    def analysis(self, candidate_id: str) -> dict[str, object]:
        return {
            "window_summary": "MCP ownership flow.",
            "task_context": {"task_type": "integration", "confidence": 0.8, "reason": "MCP tool calls reached ownership core."},
            "ownership_gaps": [
                {
                    "id": candidate_id,
                    "title": "MCP ownership flow",
                    "summary": "The MCP path must preserve ownership semantics.",
                    "dimension": "tool",
                    "control_point": "MCP ownership tool contract",
                    "gap_type": "concept_ownership_gap",
                    "gap_reason": "The primary product entrypoint is now MCP.",
                    "required_level": "L2",
                    "current_level": "L1",
                    "priority": "P1",
                    "evidence_refs": [{"kind": "event", "ref": "agent_events.id=2", "role": "ai_decision"}],
                    "repayment": {"type": "explain_back", "task": "Explain the MCP ownership flow.", "validation_criteria": ["Names the MCP tool", "Names the ownership function"]},
                    "knowledge_context": {"introduced_concepts": ["MCP ownership flow"], "user_familiarity": "unknown", "minimum_mastery_level": "L2"},
                }
            ],
        }

    def test_tools_list_uses_ownership_surface(self) -> None:
        names = {tool["name"] for tool in mcp_server.list_tools()}
        self.assertTrue({"get_ownership_review_input", "submit_ownership_analysis", "review_ownership_gap", "list_ownership_debts", "export_task_control_report"}.issubset(names))
        self.assertFalse({"get_review_input", "submit_analysis", "review_action", "list_inbox", "export_deep_review"}.intersection(names))

    def test_resource_templates_use_ownership_surface(self) -> None:
        templates = {item["uriTemplate"] for item in mcp_server.list_resource_templates()}
        self.assertIn("ai-debt://ownership/windows/{review_window_id}/review-input", templates)
        self.assertIn("ai-debt://ownership/windows/{review_window_id}/task-control-report", templates)

    def test_jsonrpc_and_stdio_shape(self) -> None:
        response = mcp_server.handle_jsonrpc({"jsonrpc": "2.0", "id": 1, "method": "tools/list", "params": {}})
        self.assertEqual(response["jsonrpc"], "2.0")
        self.assertEqual(response["id"], 1)
        self.assertIn("tools", response["result"])

        request = json.dumps({"jsonrpc": "2.0", "id": 2, "method": "initialize", "params": {}}).encode("utf-8")
        stdin = BytesIO(b"Content-Length: " + str(len(request)).encode("ascii") + b"\r\n\r\n" + request)
        stdout = BytesIO()
        self.assertEqual(mcp_server.serve_stdio(stdin, stdout), 0)
        self.assertIn(b"serverInfo", stdout.getvalue())

    def test_mcp_can_complete_codex_and_claude_ownership_flow(self) -> None:
        for adapter, session_id, candidate_id in [
            ("codex", "codex-mcp-flow", "cand-codex-mcp"),
            ("claude-code", "claude-mcp-flow", "cand-claude-mcp"),
        ]:
            window_id = self.capture_with_mcp(adapter, session_id)
            review_input = mcp_server.call_tool("get_ownership_review_input", {"review_window_id": window_id})
            self.assertEqual(review_input["review_window"]["id"], window_id)
            created = mcp_server.call_tool("submit_ownership_analysis", {"review_window_id": window_id, "analysis": self.analysis(candidate_id)})
            self.assertEqual(created["created"][0]["status"], "ready")
            accepted = mcp_server.call_tool("review_ownership_gap", {"candidate_id": candidate_id, "action": "accept"})
            debt_id = accepted["debt_id"]
            self.assertIsNotNone(debt_id)
            learning = mcp_server.call_tool("learn_one", {"item_id": debt_id})
            self.assertEqual(learning["gap_type"], "concept_ownership_gap")
            check = mcp_server.call_tool("check", {"debt_id": debt_id, "answer": "MCP routes to ownership core.", "agent_assessment": {"result": "verified", "reason": "ok"}})
            self.assertEqual(check["result"], "verified")
            report = mcp_server.call_tool("export_task_control_report", {"review_window_id": window_id, "write_file": False})
            self.assertIn("Task Control Report", report["markdown"])

    def test_profile_update_and_delete_via_mcp(self) -> None:
        profile = mcp_server.call_tool("get_ownership_profile", {"cwd": str(self.home)})["profile"]
        updated = mcp_server.call_tool("update_ownership_profile", {"project_id": profile["project_id"], "patch": {"target_ownership_level": "L5"}})["profile"]
        self.assertEqual(updated["target_ownership_level"], "L5")

        window_id = self.capture_with_mcp("codex", "delete-mcp-flow")
        mcp_server.call_tool("submit_ownership_analysis", {"review_window_id": window_id, "analysis": self.analysis("cand-delete-mcp")})
        debt_id = mcp_server.call_tool("review_ownership_gap", {"candidate_id": "cand-delete-mcp", "action": "accept"})["debt_id"]
        self.assertTrue(mcp_server.call_tool("delete_item", {"target": "debt", "id": debt_id})["deleted"])
        self.assertTrue(mcp_server.call_tool("delete_item", {"target": "session", "id": "delete-mcp-flow"})["deleted"])

def _iso(value: datetime) -> str:
    return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


if __name__ == "__main__":
    unittest.main()
