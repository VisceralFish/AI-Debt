from __future__ import annotations

import json
import os
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path

from ai_debt.adapters import normalize_payload
from ai_debt.cli import main
from ai_debt.config import default_config, load_config, save_config
from ai_debt.core import capture_payload, initialize
from ai_debt.events import validate_event
from ai_debt.maintenance import cleanup_raw_payloads, delete_debt, delete_session, export_deep_review
from ai_debt.paths import db_path
from ai_debt.review import (
    apply_review_action,
    build_review_input,
    create_candidates,
    learn_one,
    list_inbox,
    parse_analysis,
    record_grasp_check,
    select_review_session,
)
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


class SchemaTests(HomeTestCase):
    def test_migration_is_repeatable_and_supports_basic_crud(self) -> None:
        initialize(self.home)
        conn = connect(db_path(self.home))
        try:
            migrate(conn)
            migrate(conn)
            conn.execute(
                """
                INSERT INTO sessions(id, source, cwd, started_at, last_activity_at, status, journal_path)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                ("s1", "codex", ".", "2026-06-19T00:00:00Z", "2026-06-19T00:00:00Z", "recording", "journals/s1"),
            )
            conn.execute(
                """
                INSERT INTO agent_events(session_id, source, type, summary, raw_payload_ref, occurred_at, payload_json)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                ("s1", "codex", "assistant_stopped", "done", "raw.json", "2026-06-19T00:00:01Z", "{}"),
            )
            conn.commit()
            count = conn.execute("SELECT COUNT(*) FROM agent_events WHERE session_id = ?", ("s1",)).fetchone()[0]
        finally:
            conn.close()
        self.assertEqual(count, 1)


class AdapterContractTests(HomeTestCase):
    def test_claude_and_codex_emit_same_prompt_contract(self) -> None:
        claude = validate_event(
            normalize_payload(
                "claude-code",
                {
                    "hook_event_name": "UserPromptSubmit",
                    "session_id": "s1",
                    "prompt": "Build Phase 1 capture core",
                    "timestamp": "2026-06-19T00:00:00Z",
                },
                "raw/claude.json",
            )
        )
        codex = validate_event(
            normalize_payload(
                "codex",
                {
                    "event": "UserPromptSubmit",
                    "session_id": "s2",
                    "input": "Build Phase 1 capture core",
                    "timestamp": "2026-06-19T00:00:00Z",
                },
                "raw/codex.json",
            )
        )
        self.assertEqual(claude["type"], "user_prompt_submitted")
        self.assertEqual(codex["type"], "user_prompt_submitted")
        self.assertEqual(set(claude).intersection(set(codex)), {"type", "source", "session_id", "turn_id", "raw_payload_ref", "occurred_at", "prompt_summary"})

    def test_tool_event_requires_tool_name(self) -> None:
        event = normalize_payload(
            "codex",
            {"event": "PostToolUse", "session_id": "s1", "tool_name": "apply_patch"},
            "raw/tool.json",
        )
        self.assertEqual(validate_event(event)["tool_name"], "apply_patch")


class IntegrationTests(HomeTestCase):
    def test_fake_hook_event_writes_journal_and_status(self) -> None:
        capture_payload(
            "codex",
            {
                "event": "SessionStart",
                "session_id": "s1",
                "cwd": str(self.home),
            },
            self.home,
        )
        capture_payload(
            "codex",
            {
                "event": "Stop",
                "session_id": "s1",
                "last_message": "Implemented capture core",
            },
            self.home,
        )
        events_path = self.home / "journals" / "s1" / "events.jsonl"
        self.assertTrue(events_path.exists())
        lines = events_path.read_text(encoding="utf-8").splitlines()
        self.assertEqual(len(lines), 2)
        self.assertEqual(json.loads(lines[0])["type"], "session_started")

        conn = connect(db_path(self.home))
        try:
            counts = status_counts(conn)
        finally:
            conn.close()
        self.assertEqual(counts.get("recording"), 1)

    def test_missing_session_end_becomes_pending_settlement_after_idle_threshold(self) -> None:
        capture_payload(
            "claude-code",
            {
                "hook_event_name": "SessionStart",
                "session_id": "s2",
                "cwd": str(self.home),
                "timestamp": "2026-06-19T00:00:00Z",
            },
            self.home,
        )
        config = default_config()
        conn = connect(db_path(self.home))
        try:
            refresh_session_states(conn, config, datetime(2026, 6, 19, 0, 31, tzinfo=timezone.utc))
            counts = status_counts(conn)
        finally:
            conn.close()
        self.assertEqual(counts.get("pending_settlement"), 1)

    def test_cli_init_adapter_generates_hook_marker(self) -> None:
        self.assertEqual(main(["init", "codex"]), 0)
        hook_path = self.home / "hooks" / "codex-hook.ps1"
        self.assertTrue(hook_path.exists())
        hook = hook_path.read_text(encoding="utf-8")
        self.assertIn("Get-Command ai-debt", hook)
        self.assertIn("python -m ai_debt.cli hook codex", hook)
        self.assertIn("codex: true", (self.home / "config.yaml").read_text(encoding="utf-8"))

    def test_config_round_trip_preserves_top_level_thresholds(self) -> None:
        config = default_config()
        config.idle_minutes = 5
        config.pending_minutes = 9
        save_config(config, self.home)
        loaded = load_config(self.home)
        self.assertEqual(loaded.idle_minutes, 5)
        self.assertEqual(loaded.pending_minutes, 9)


class Phase2ReviewTests(HomeTestCase):
    def _create_pending_session(self) -> None:
        capture_payload(
            "codex",
            {
                "event": "SessionStart",
                "session_id": "phase2-session",
                "cwd": str(self.home),
                "timestamp": "2026-06-19T00:00:00Z",
            },
            self.home,
        )
        capture_payload(
            "codex",
            {
                "event": "PostToolUse",
                "session_id": "phase2-session",
                "tool_name": "apply_patch",
                "summary": "Added review pipeline",
                "timestamp": "2026-06-19T00:01:00Z",
            },
            self.home,
        )
        capture_payload(
            "codex",
            {
                "event": "SessionEnd",
                "session_id": "phase2-session",
                "timestamp": "2026-06-19T00:02:00Z",
            },
            self.home,
        )

    def _analysis(self) -> dict[str, object]:
        return {
            "session_summary": "Implemented Phase 2 review flow.",
            "delegation_points": [
                {
                    "id": "dp1",
                    "summary": "Agent implemented review action semantics.",
                    "event_refs": [2],
                    "diff_refs": ["diff.patch"],
                    "transcript_refs": [],
                }
            ],
            "debt_candidates": [
                {
                    "id": "cand-ready",
                    "concept": "Evidence-backed candidate acceptance",
                    "debt_dimension": "verification",
                    "why_it_matters": "Accepting candidates without evidence would corrupt the ledger.",
                    "priority": "P1",
                    "delegation_point_id": "dp1",
                    "learn_one": {
                        "short_explanation": "Only ready candidates can become ledger items.",
                        "minimal_trace": "agent_events.id=2",
                        "quick_check_prompt": "Why must accept require evidence?",
                    },
                },
                {
                    "id": "cand-rejected",
                    "concept": "Unsupported claim",
                    "debt_dimension": "intent",
                    "why_it_matters": "The candidate has no traceable support.",
                    "priority": "P2",
                },
            ],
        }

    def test_review_input_and_candidates_ready_flow(self) -> None:
        self._create_pending_session()
        conn = connect(db_path(self.home))
        try:
            session = select_review_session(conn)
            self.assertIsNotNone(session)
            review_input = build_review_input(conn, "phase2-session")
            self.assertEqual(review_input["session"]["status"], "pending_settlement")
            self.assertEqual(len(review_input["event_summaries"]), 3)

            created = create_candidates(conn, "phase2-session", parse_analysis(json.dumps(self._analysis())))
            self.assertEqual(created[0]["status"], "ready")
            self.assertEqual(created[1]["status"], "rejected_needs_evidence")
            status = conn.execute("SELECT status FROM sessions WHERE id = ?", ("phase2-session",)).fetchone()[0]
            self.assertEqual(status, "candidates_ready")
        finally:
            conn.close()

    def test_accept_writes_ledger_inbox_and_check_updates_status(self) -> None:
        self._create_pending_session()
        conn = connect(db_path(self.home))
        try:
            create_candidates(conn, "phase2-session", self._analysis())
            debt_id = apply_review_action(conn, "cand-ready", "accept")
            self.assertIsNotNone(debt_id)

            debts = conn.execute("SELECT COUNT(*) FROM cognitive_debts").fetchone()[0]
            inbox = list_inbox(conn)
            self.assertEqual(debts, 1)
            self.assertEqual(len(inbox), 1)
            self.assertEqual(inbox[0]["debt_id"], debt_id)

            learning = learn_one(conn, debt_id)
            self.assertEqual(learning["kind"], "debt")
            result = record_grasp_check(conn, debt_id, "Because evidence keeps the ledger tied to actual agent actions.")
            self.assertEqual(result, "solid")
            remaining = list_inbox(conn)
            self.assertEqual(remaining, [])
        finally:
            conn.close()

    def test_rejected_candidate_cannot_be_accepted(self) -> None:
        self._create_pending_session()
        conn = connect(db_path(self.home))
        try:
            create_candidates(conn, "phase2-session", self._analysis())
            with self.assertRaises(ValueError):
                apply_review_action(conn, "cand-rejected", "accept")
        finally:
            conn.close()

    def test_candidate_learn_one_uses_payload_content(self) -> None:
        self._create_pending_session()
        conn = connect(db_path(self.home))
        try:
            create_candidates(conn, "phase2-session", self._analysis())
            learning = learn_one(conn, "cand-ready")
            self.assertEqual(learning["kind"], "candidate")
            self.assertIn("ready candidates", learning["short_explanation"])
        finally:
            conn.close()

    def test_reimporting_same_candidate_does_not_duplicate_evidence_refs(self) -> None:
        self._create_pending_session()
        conn = connect(db_path(self.home))
        try:
            create_candidates(conn, "phase2-session", self._analysis())
            create_candidates(conn, "phase2-session", self._analysis())
            count = conn.execute("SELECT COUNT(*) FROM evidence_refs WHERE candidate_id = ?", ("cand-ready",)).fetchone()[0]
            self.assertEqual(count, 2)
        finally:
            conn.close()

    def test_invalid_review_json_is_preserved_by_cli(self) -> None:
        self._create_pending_session()
        bad_path = self.home / "bad-analysis.json"
        bad_path.write_text("{not json", encoding="utf-8")
        self.assertEqual(main(["review", "phase2-session", "--analysis-file", str(bad_path)]), 1)
        failed_logs = list((self.home / "logs").glob("review_analysis_failed_*.txt"))
        self.assertEqual(len(failed_logs), 1)


class Phase3ConvergenceTests(HomeTestCase):
    def _capture_agent_session(self, adapter: str, session_id: str) -> None:
        if adapter == "claude-code":
            capture_payload(
                adapter,
                {
                    "hook_event_name": "SessionStart",
                    "session_id": session_id,
                    "cwd": str(self.home),
                    "timestamp": "2026-06-19T00:00:00Z",
                },
                self.home,
            )
            capture_payload(
                adapter,
                {
                    "hook_event_name": "UserPromptSubmit",
                    "session_id": session_id,
                    "prompt": "Implement MVP flow",
                    "timestamp": "2026-06-19T00:01:00Z",
                },
                self.home,
            )
            capture_payload(
                adapter,
                {
                    "hook_event_name": "PostToolUse",
                    "session_id": session_id,
                    "tool_name": "apply_patch",
                    "summary": "Changed MVP files",
                    "timestamp": "2026-06-19T00:02:00Z",
                },
                self.home,
            )
            capture_payload(
                adapter,
                {
                    "hook_event_name": "SessionEnd",
                    "session_id": session_id,
                    "timestamp": "2026-06-19T00:03:00Z",
                },
                self.home,
            )
            return

        capture_payload(
            adapter,
            {
                "event": "SessionStart",
                "session_id": session_id,
                "cwd": str(self.home),
                "timestamp": "2026-06-19T00:00:00Z",
            },
            self.home,
        )
        capture_payload(
            adapter,
            {
                "event": "UserPromptSubmit",
                "session_id": session_id,
                "input": "Implement MVP flow",
                "timestamp": "2026-06-19T00:01:00Z",
            },
            self.home,
        )
        capture_payload(
            adapter,
            {
                "event": "PostToolUse",
                "session_id": session_id,
                "tool_name": "apply_patch",
                "summary": "Changed MVP files",
                "timestamp": "2026-06-19T00:02:00Z",
            },
            self.home,
        )
        capture_payload(
            adapter,
            {
                "event": "SessionEnd",
                "session_id": session_id,
                "timestamp": "2026-06-19T00:03:00Z",
            },
            self.home,
        )

    def _analysis(self, candidate_id: str) -> dict[str, object]:
        return {
            "session_summary": "Completed an end-to-end MVP flow.",
            "delegation_points": [
                {
                    "id": "dp-e2e",
                    "summary": "Agent made implementation and verification decisions.",
                    "event_refs": [3],
                    "diff_refs": ["diff.patch"],
                    "transcript_refs": [],
                }
            ],
            "debt_candidates": [
                {
                    "id": candidate_id,
                    "concept": "MVP convergence evidence",
                    "debt_dimension": "verification",
                    "why_it_matters": "The user needs to know that capture, review, ledger, learning, cleanup, and export still work together.",
                    "priority": "P1",
                    "delegation_point_id": "dp-e2e",
                    "learn_one": {
                        "short_explanation": "Convergence evidence ties the whole MVP flow together.",
                        "minimal_trace": "agent_events.id=3",
                        "quick_check_prompt": "What does convergence evidence protect?",
                    },
                }
            ],
        }

    def test_claude_and_codex_converge_on_same_mvp_flow(self) -> None:
        exported: list[Path] = []
        conn = None
        try:
            for adapter, session_id, candidate_id in [
                ("claude-code", "claude-e2e", "cand-claude-e2e"),
                ("codex", "codex-e2e", "cand-codex-e2e"),
            ]:
                self._capture_agent_session(adapter, session_id)
                conn = connect(db_path(self.home))
                create_candidates(conn, session_id, self._analysis(candidate_id))
                debt_id = apply_review_action(conn, candidate_id, "accept")
                self.assertIsNotNone(debt_id)
                self.assertEqual(learn_one(conn, debt_id)["kind"], "debt")
                self.assertEqual(record_grasp_check(conn, debt_id, None, skipped=True), "skipped")
                exported.append(export_deep_review(conn, session_id, self.home))
                conn.close()
                conn = None

            for path in exported:
                content = path.read_text(encoding="utf-8")
                self.assertIn("## Session Summary", content)
                self.assertIn("## Accepted Debts", content)
                self.assertIn("MVP convergence evidence", content)
        finally:
            if conn is not None:
                conn.close()

    def test_raw_payload_cleanup_preserves_normalized_events_and_ledger(self) -> None:
        self._capture_agent_session("codex", "cleanup-e2e")
        conn = connect(db_path(self.home))
        try:
            create_candidates(conn, "cleanup-e2e", self._analysis("cand-cleanup"))
            debt_id = apply_review_action(conn, "cand-cleanup", "accept")
            self.assertIsNotNone(debt_id)
            event_count_before = conn.execute("SELECT COUNT(*) FROM agent_events").fetchone()[0]
            debt_count_before = conn.execute("SELECT COUNT(*) FROM cognitive_debts").fetchone()[0]
            evidence_count_before = conn.execute("SELECT COUNT(*) FROM evidence_refs").fetchone()[0]
        finally:
            conn.close()

        old_time = datetime(2026, 6, 1, tzinfo=timezone.utc).timestamp()
        for path in (self.home / "journals" / "cleanup-e2e" / "raw").glob("*.json"):
            os.utime(path, (old_time, old_time))

        config = default_config()
        dry_run = cleanup_raw_payloads(config, self.home, dry_run=True, now=datetime(2026, 6, 19, tzinfo=timezone.utc))
        self.assertGreater(len(dry_run.raw_payloads), 0)
        cleanup_raw_payloads(config, self.home, now=datetime(2026, 6, 19, tzinfo=timezone.utc))

        conn = connect(db_path(self.home))
        try:
            self.assertEqual(conn.execute("SELECT COUNT(*) FROM agent_events").fetchone()[0], event_count_before)
            self.assertEqual(conn.execute("SELECT COUNT(*) FROM cognitive_debts").fetchone()[0], debt_count_before)
            self.assertEqual(conn.execute("SELECT COUNT(*) FROM evidence_refs").fetchone()[0], evidence_count_before)
            self.assertEqual(list((self.home / "journals" / "cleanup-e2e" / "raw").glob("*.json")), [])
        finally:
            conn.close()

    def test_delete_session_and_debt_update_local_state(self) -> None:
        self._capture_agent_session("codex", "delete-e2e")
        conn = connect(db_path(self.home))
        try:
            create_candidates(conn, "delete-e2e", self._analysis("cand-delete"))
            debt_id = apply_review_action(conn, "cand-delete", "accept")
            self.assertIsNotNone(debt_id)
            delete_debt(conn, debt_id)
            self.assertEqual(conn.execute("SELECT COUNT(*) FROM cognitive_debts WHERE id = ?", (debt_id,)).fetchone()[0], 0)
            self.assertEqual(conn.execute("SELECT COUNT(*) FROM inbox_items WHERE debt_id = ?", (debt_id,)).fetchone()[0], 0)

            delete_session(conn, "delete-e2e", self.home)
            self.assertEqual(conn.execute("SELECT COUNT(*) FROM sessions WHERE id = ?", ("delete-e2e",)).fetchone()[0], 0)
            self.assertFalse((self.home / "journals" / "delete-e2e").exists())
        finally:
            conn.close()

    def test_recovery_rebuilds_state_from_journal_after_db_loss(self) -> None:
        capture_payload(
            "claude-code",
            {
                "hook_event_name": "SessionStart",
                "session_id": "recover-e2e",
                "cwd": str(self.home),
                "timestamp": "2026-06-19T00:00:00Z",
            },
            self.home,
        )
        db_path(self.home).unlink()
        initialize(self.home)
        conn = connect(db_path(self.home))
        try:
            self.assertEqual(conn.execute("SELECT COUNT(*) FROM sessions WHERE id = ?", ("recover-e2e",)).fetchone()[0], 1)
            self.assertEqual(conn.execute("SELECT COUNT(*) FROM agent_events WHERE session_id = ?", ("recover-e2e",)).fetchone()[0], 1)
        finally:
            conn.close()

    def test_doctor_does_not_create_state_on_empty_home(self) -> None:
        self.assertEqual(main(["doctor"]), 1)
        self.assertFalse((self.home / "config.yaml").exists())
        self.assertFalse((self.home / "ai_debt.db").exists())


if __name__ == "__main__":
    unittest.main()
