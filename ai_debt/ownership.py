from __future__ import annotations

import hashlib
import json
import sqlite3
from pathlib import Path
from typing import Any
from uuid import uuid4

from .journal import utc_now
from .paths import exports_path


TASK_TYPES = {"creation", "maintenance", "integration", "refactor", "experiment"}
GAP_TYPES = {
    "concept_ownership_gap",
    "unanchored_design_decision",
    "root_cause_gap",
    "risky_file_change",
    "dependency_gap",
    "validation_gap",
    "workaround_gap",
    "integration_gap",
    "refactor_equivalence_gap",
}
LEVELS = {"L0": 0, "L1": 1, "L2": 2, "L3": 3, "L4": 4, "L5": 5}
PRIORITIES = {"P0": 0, "P1": 1, "P2": 2}
REPAYMENT_TYPES = {
    "explain_back",
    "modify_safely",
    "reproduce_bug",
    "break_test",
    "rebuild_minimal",
    "compare_alternatives",
    "assurance_check",
}
HIGH_RISK_GAPS = {"risky_file_change", "dependency_gap", "validation_gap", "root_cause_gap"}


def project_id_for_cwd(cwd: str | None) -> str:
    if not cwd:
        return "default"
    normalized = str(Path(cwd).expanduser()).lower()
    digest = hashlib.sha256(normalized.encode("utf-8")).hexdigest()[:12]
    return f"proj-{digest}"


def default_profile(project_id: str) -> dict[str, Any]:
    return {
        "project_id": project_id,
        "role": "independent_developer",
        "project_intent": "local_first_tool",
        "target_ownership_level": "L3",
        "critical_areas": ["data", "privacy", "core_logic"],
        "unacceptable_risks": ["data_loss", "privacy_leak", "unmaintainable"],
        "control_contract": {
            "ai_free_to_handle": ["formatting", "boilerplate", "docs wording"],
            "ai_must_explain": ["data model", "review logic", "debt scoring", "MCP contract"],
            "ai_must_confirm": ["delete data", "privacy policy change", "new dependency", "schema migration"],
            "user_must_own": ["ownership level model", "control gap rules", "local data handling"],
        },
        "tech_familiarity": {},
    }


def get_or_create_profile(conn: sqlite3.Connection, project_id: str) -> dict[str, Any]:
    row = conn.execute("SELECT payload_json FROM ownership_profiles WHERE project_id = ?", (project_id,)).fetchone()
    if row:
        return json.loads(row["payload_json"])
    now = utc_now()
    profile = default_profile(project_id)
    conn.execute(
        """
        INSERT INTO ownership_profiles(project_id, payload_json, created_at, updated_at)
        VALUES (?, ?, ?, ?)
        """,
        (project_id, json.dumps(profile, ensure_ascii=False, sort_keys=True), now, now),
    )
    conn.commit()
    return profile


def update_profile(conn: sqlite3.Connection, project_id: str, patch: dict[str, Any]) -> dict[str, Any]:
    profile = get_or_create_profile(conn, project_id)
    updated = _deep_merge(profile, patch)
    updated["project_id"] = project_id
    now = utc_now()
    conn.execute(
        """
        INSERT INTO ownership_profiles(project_id, payload_json, created_at, updated_at)
        VALUES (?, ?, ?, ?)
        ON CONFLICT(project_id) DO UPDATE SET
          payload_json = excluded.payload_json,
          updated_at = excluded.updated_at
        """,
        (project_id, json.dumps(updated, ensure_ascii=False, sort_keys=True), now, now),
    )
    conn.commit()
    return updated


def update_review_window_for_event(conn: sqlite3.Connection, event: dict[str, Any], event_id: int, project_id: str) -> None:
    event_type = event["type"]
    session_id = event["session_id"]
    if event_type == "session_started":
        _create_window(conn, session_id, project_id, event_id, "record_event", "open")
        return

    current = _open_window(conn, session_id)
    if event_type == "user_prompt_submitted":
        if current and _window_has_activity(conn, current["id"]):
            _close_window(conn, current["id"], event_id - 1, "user_prompt_submitted")
            _create_window(conn, session_id, project_id, event_id, "record_event", "open")
        elif current:
            conn.execute(
                """
                UPDATE ownership_review_windows
                SET started_event_id = ?, ended_event_id = ?, updated_at = ?
                WHERE id = ?
                """,
                (event_id, event_id, utc_now(), current["id"]),
            )
        else:
            _create_window(conn, session_id, project_id, event_id, "record_event", "open")
        return

    if current is None:
        current = _create_window(conn, session_id, project_id, event_id, "record_event", "open")

    if event_type in {"tool_used", "assistant_stopped"}:
        conn.execute(
            """
            UPDATE ownership_review_windows
            SET ended_event_id = ?, updated_at = ?
            WHERE id = ?
            """,
            (event_id, utc_now(), current["id"]),
        )
    elif event_type == "session_ended":
        _close_window(conn, current["id"], event_id, "explicit_session_end")


def refresh_review_windows_for_session_status(conn: sqlite3.Connection, session_id: str, status: str) -> None:
    current = _open_or_idle_window(conn, session_id)
    if current is None:
        return
    now = utc_now()
    if status == "idle_detected" and current["status"] == "open":
        conn.execute(
            """
            UPDATE ownership_review_windows
            SET status = ?, trigger = ?, updated_at = ?
            WHERE id = ?
            """,
            ("idle_detected", "idle_timeout", now, current["id"]),
        )
    elif status == "pending_settlement":
        conn.execute(
            """
            UPDATE ownership_review_windows
            SET status = ?, trigger = ?, updated_at = ?
            WHERE id = ?
            """,
            ("pending_ownership_review", "idle_timeout", now, current["id"]),
        )


def select_pending_review_window(conn: sqlite3.Connection, review_window_id: str | None = None) -> sqlite3.Row | None:
    if review_window_id:
        return conn.execute("SELECT * FROM ownership_review_windows WHERE id = ?", (review_window_id,)).fetchone()
    return conn.execute(
        """
        SELECT * FROM ownership_review_windows
        WHERE status IN ('pending_ownership_review', 'candidates_ready', 'analysis_submitted')
        ORDER BY updated_at DESC
        LIMIT 1
        """
    ).fetchone()


def build_ownership_review_input(conn: sqlite3.Connection, review_window_id: str | None = None) -> dict[str, Any]:
    window = select_pending_review_window(conn, review_window_id)
    if window is None:
        raise ValueError("No review window ready for ownership review")
    session = conn.execute("SELECT * FROM sessions WHERE id = ?", (window["session_id"],)).fetchone()
    if session is None:
        raise ValueError(f"Unknown session for window: {window['id']}")
    events = _events_for_window(conn, window)
    journal_path = Path(session["journal_path"])
    changed_files = _read_lines(journal_path / "changed_files.txt")
    diff_snapshot = _read_optional(journal_path / "diff.patch")
    profile = get_or_create_profile(conn, window["project_id"])
    related = conn.execute(
        """
        SELECT id, title, gap_type, dimension, priority, status, required_level, control_point
        FROM ownership_debts
        WHERE project_id = ?
        ORDER BY updated_at DESC
        LIMIT 20
        """,
        (window["project_id"],),
    ).fetchall()
    return {
        "review_window": dict(window),
        "session": {
            "id": session["id"],
            "project_id": session["project_id"],
            "source": session["source"],
            "cwd": session["cwd"],
            "transcript_ref": session["transcript_ref"],
            "started_at": session["started_at"],
            "last_activity_at": session["last_activity_at"],
            "status": session["status"],
        },
        "ownership_profile": profile,
        "control_contract": profile.get("control_contract", {}),
        "event_summaries": [dict(row) for row in events],
        "diff_snapshot": diff_snapshot,
        "diff_snapshot_scope": "latest_session_snapshot",
        "changed_files": changed_files,
        "local_hints": local_hints(changed_files, diff_snapshot or ""),
        "transcript_refs": [session["transcript_ref"]] if session["transcript_ref"] else [],
        "existing_related_debts": [dict(row) for row in related],
        "expected_output_schema": expected_ownership_analysis_schema(),
    }


def expected_ownership_analysis_schema() -> dict[str, Any]:
    return {
        "window_summary": "string",
        "task_context": {
            "task_type": "creation|maintenance|integration|refactor|experiment",
            "confidence": "number",
            "reason": "string",
        },
        "ownership_gaps": [
            {
                "title": "string",
                "summary": "string",
                "dimension": "concept|code|architecture|tool|debug|intent|maintenance|verification|data|privacy|dependency",
                "control_point": "string",
                "gap_type": "|".join(sorted(GAP_TYPES)),
                "gap_reason": "string",
                "required_level": "L0|L1|L2|L3|L4|L5",
                "current_level": "L0|L1|L2|L3|L4|L5",
                "priority": "P0|P1|P2",
                "evidence_refs": [{"kind": "event|diff|transcript|file", "ref": "string", "role": "string"}],
                "repayment": {
                    "type": "|".join(sorted(REPAYMENT_TYPES)),
                    "task": "string",
                    "validation_criteria": ["string"],
                },
                "knowledge_context": {},
            }
        ],
    }


def parse_ownership_analysis(text: str) -> dict[str, Any]:
    try:
        value = json.loads(text)
    except json.JSONDecodeError as exc:
        raise ValueError(f"Invalid ownership analysis JSON: {exc}") from exc
    if not isinstance(value, dict):
        raise ValueError("Ownership analysis must be a JSON object")
    if not isinstance(value.get("window_summary"), str):
        raise ValueError("Ownership analysis requires window_summary")
    task = value.get("task_context")
    if not isinstance(task, dict):
        raise ValueError("Ownership analysis requires task_context")
    if task.get("task_type") not in TASK_TYPES:
        raise ValueError("task_context.task_type is invalid")
    if not isinstance(value.get("ownership_gaps"), list):
        raise ValueError("Ownership analysis requires ownership_gaps[]")
    return value


def create_ownership_candidates(conn: sqlite3.Connection, review_window_id: str, analysis: dict[str, Any]) -> list[dict[str, Any]]:
    window = conn.execute("SELECT * FROM ownership_review_windows WHERE id = ?", (review_window_id,)).fetchone()
    if window is None:
        raise ValueError(f"Unknown review window: {review_window_id}")
    session = conn.execute("SELECT * FROM sessions WHERE id = ?", (window["session_id"],)).fetchone()
    if session is None:
        raise ValueError(f"Unknown session: {window['session_id']}")

    parsed = parse_ownership_analysis(json.dumps(analysis, ensure_ascii=False))
    task_context = parsed["task_context"]
    gaps = [gap for gap in parsed["ownership_gaps"] if isinstance(gap, dict)]
    ranked = _rank_gaps(gaps)
    ready_keys = {id(gap) for gap in ranked[:3]}
    now = utc_now()
    created: list[dict[str, Any]] = []

    for gap in ranked:
        reasons = _candidate_rejection_reasons(gap)
        candidate_id = str(gap.get("id") or f"cand-{uuid4().hex[:12]}")
        required = _level(str(gap.get("required_level") or "L2"))
        current = _level(str(gap.get("current_level") or "L1"))
        level_gap = max(0, required - current)
        evidence_refs = _evidence_refs(gap)
        repayment = gap.get("repayment") if isinstance(gap.get("repayment"), dict) else {}
        knowledge = gap.get("knowledge_context") if isinstance(gap.get("knowledge_context"), dict) else {}
        status = "rejected_needs_evidence" if reasons else ("ready" if id(gap) in ready_keys else "deferred")
        payload = {
            **gap,
            "window_summary": parsed["window_summary"],
            "task_context": task_context,
            "gate": {"passed": not reasons, "reasons": reasons},
        }
        conn.execute(
            """
            INSERT INTO ownership_gap_candidates(
              id, review_window_id, session_id, project_id, source_agent,
              title, summary, dimension, priority, status,
              task_type, task_label, task_confidence,
              control_point, gap_type, gap_reason,
              required_level, current_level, level_gap,
              repayment_type, repayment_task,
              payload_json, score_json, evidence_json, repayment_json, knowledge_json,
              created_at, updated_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(id) DO UPDATE SET
              status = excluded.status,
              payload_json = excluded.payload_json,
              score_json = excluded.score_json,
              evidence_json = excluded.evidence_json,
              repayment_json = excluded.repayment_json,
              knowledge_json = excluded.knowledge_json,
              updated_at = excluded.updated_at
            """,
            (
                candidate_id,
                window["id"],
                window["session_id"],
                window["project_id"],
                session["source"],
                _text(gap, "title", "Unspecified ownership gap"),
                _text(gap, "summary", _text(gap, "gap_reason", "Ownership gap requires review.")),
                _text(gap, "dimension", "concept"),
                _priority(gap.get("priority")),
                status,
                task_context["task_type"],
                str(task_context.get("label") or _task_label(str(task_context["task_type"]))),
                float(task_context.get("confidence") or 0),
                _text(gap, "control_point", "Unspecified control point"),
                _gap_type(gap.get("gap_type")),
                _text(gap, "gap_reason", "Ownership gap requires review."),
                _level_name(gap.get("required_level"), "L2"),
                _level_name(gap.get("current_level"), "L1"),
                level_gap,
                _repayment_type(repayment.get("type")),
                str(repayment.get("task") or "Explain the control point and validate the proposed recovery task."),
                json.dumps(payload, ensure_ascii=False, sort_keys=True),
                json.dumps(gap.get("score_breakdown") if isinstance(gap.get("score_breakdown"), dict) else {}, ensure_ascii=False, sort_keys=True),
                json.dumps(evidence_refs, ensure_ascii=False, sort_keys=True),
                json.dumps(repayment, ensure_ascii=False, sort_keys=True),
                json.dumps(knowledge, ensure_ascii=False, sort_keys=True),
                now,
                now,
            ),
        )
        conn.execute("DELETE FROM evidence_refs WHERE candidate_id = ? AND debt_id IS NULL", (candidate_id,))
        for ref in evidence_refs:
            conn.execute(
                """
                INSERT INTO evidence_refs(candidate_id, review_window_id, session_id, event_id, kind, ref, role, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    candidate_id,
                    window["id"],
                    window["session_id"],
                    _event_id_from_ref(ref),
                    ref["kind"],
                    ref["ref"],
                    ref.get("role"),
                    now,
                ),
            )
        created.append({"id": candidate_id, "status": status, "gate_reasons": reasons})

    conn.execute(
        "UPDATE ownership_review_windows SET status = ?, updated_at = ? WHERE id = ?",
        ("candidates_ready", now, window["id"]),
    )
    conn.commit()
    return created


def review_ownership_gap(conn: sqlite3.Connection, candidate_id: str, action: str) -> str | None:
    if action not in {"accept", "ignore", "already_know", "defer"}:
        raise ValueError("action must be accept, ignore, already_know, or defer")
    candidate = conn.execute("SELECT * FROM ownership_gap_candidates WHERE id = ?", (candidate_id,)).fetchone()
    if candidate is None:
        raise ValueError(f"Unknown ownership gap candidate: {candidate_id}")
    now = utc_now()
    debt_id: str | None = None
    if action == "accept":
        if candidate["status"] not in {"ready", "deferred"}:
            raise ValueError("Only evidence-backed ownership gap candidates can be accepted")
        debt_id = f"debt-{uuid4().hex[:12]}"
        conn.execute(
            """
            INSERT INTO ownership_debts(
              id, project_id, source_session_id, source_review_window_id, source_agent, candidate_id,
              title, summary, dimension, priority, status, seen_count,
              task_type, task_label, task_confidence,
              control_point, gap_type, gap_reason,
              required_level, current_level, level_gap,
              repayment_type, repayment_task,
              payload_json, score_json, evidence_json, repayment_json, knowledge_json, feedback_json,
              created_at, updated_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                debt_id,
                candidate["project_id"],
                candidate["session_id"],
                candidate["review_window_id"],
                candidate["source_agent"],
                candidate["id"],
                candidate["title"],
                candidate["summary"],
                candidate["dimension"],
                candidate["priority"],
                "open",
                1,
                candidate["task_type"],
                candidate["task_label"],
                candidate["task_confidence"],
                candidate["control_point"],
                candidate["gap_type"],
                candidate["gap_reason"],
                candidate["required_level"],
                candidate["current_level"],
                candidate["level_gap"],
                candidate["repayment_type"],
                candidate["repayment_task"],
                candidate["payload_json"],
                candidate["score_json"],
                candidate["evidence_json"],
                candidate["repayment_json"],
                candidate["knowledge_json"],
                "{}",
                now,
                now,
            ),
        )
        conn.execute(
            "UPDATE evidence_refs SET debt_id = ? WHERE candidate_id = ? AND debt_id IS NULL",
            (debt_id, candidate_id),
        )
        _index_concepts(conn, debt_id, candidate["project_id"], candidate["knowledge_json"], now)
        conn.execute("UPDATE ownership_gap_candidates SET status = ?, updated_at = ? WHERE id = ?", ("accepted", now, candidate_id))
    elif action == "ignore":
        conn.execute("UPDATE ownership_gap_candidates SET status = ?, updated_at = ? WHERE id = ?", ("ignored", now, candidate_id))
    elif action == "already_know":
        conn.execute("UPDATE ownership_gap_candidates SET status = ?, updated_at = ? WHERE id = ?", ("known", now, candidate_id))
    elif action == "defer":
        conn.execute("UPDATE ownership_gap_candidates SET status = ?, updated_at = ? WHERE id = ?", ("deferred", now, candidate_id))

    conn.execute(
        "INSERT INTO review_actions(candidate_id, debt_id, action, created_at) VALUES (?, ?, ?, ?)",
        (candidate_id, debt_id, action, now),
    )
    conn.commit()
    return debt_id


def list_ownership_debts(conn: sqlite3.Connection, project_id: str | None = None, status: str | None = None) -> list[sqlite3.Row]:
    clauses: list[str] = []
    params: list[Any] = []
    if project_id:
        clauses.append("project_id = ?")
        params.append(project_id)
    if status:
        clauses.append("status = ?")
        params.append(status)
    where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
    return conn.execute(
        f"""
        SELECT *
        FROM ownership_debts
        {where}
        ORDER BY priority ASC, level_gap DESC, updated_at DESC
        """,
        params,
    ).fetchall()


def learn_one(conn: sqlite3.Connection, item_id: str | None = None) -> dict[str, Any]:
    row = None
    kind = "debt"
    if item_id:
        row = conn.execute("SELECT * FROM ownership_debts WHERE id = ?", (item_id,)).fetchone()
        if row is None:
            row = conn.execute("SELECT * FROM ownership_gap_candidates WHERE id = ?", (item_id,)).fetchone()
            kind = "candidate"
    else:
        row = conn.execute(
            """
            SELECT *
            FROM ownership_debts
            WHERE status IN ('open', 'in_progress')
            ORDER BY priority ASC, level_gap DESC, updated_at DESC
            LIMIT 1
            """
        ).fetchone()
    if row is None:
        raise ValueError("No ownership debt or candidate available for learn-one")
    return _learning_payload(dict(row), kind)


def record_check(
    conn: sqlite3.Connection,
    debt_id: str,
    answer: str | None,
    agent_assessment: dict[str, Any] | None = None,
    user_override: str | None = None,
    skipped: bool = False,
) -> str:
    debt = conn.execute("SELECT * FROM ownership_debts WHERE id = ?", (debt_id,)).fetchone()
    if debt is None:
        raise ValueError(f"Unknown ownership debt: {debt_id}")
    result = _check_result(agent_assessment, user_override, skipped)
    now = utc_now()
    conn.execute(
        """
        INSERT INTO grasp_checks(debt_id, prompt, answer, result, agent_assessment_json, user_override, skipped, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            debt_id,
            f"Recover ownership of {debt['control_point']}.",
            answer,
            result,
            json.dumps(agent_assessment or {}, ensure_ascii=False, sort_keys=True),
            user_override,
            1 if skipped else 0,
            now,
        ),
    )
    if result == "verified":
        conn.execute("UPDATE ownership_debts SET status = ?, resolved_at = ?, updated_at = ? WHERE id = ?", ("verified", now, now, debt_id))
    elif result in {"partial", "needs_followup", "in_progress", "skipped"}:
        conn.execute("UPDATE ownership_debts SET status = ?, updated_at = ? WHERE id = ?", ("in_progress", now, debt_id))
    conn.commit()
    return result


def task_control_report(conn: sqlite3.Connection, review_window_id: str, home: Path | None = None, write_file: bool = False) -> dict[str, Any]:
    window = conn.execute("SELECT * FROM ownership_review_windows WHERE id = ?", (review_window_id,)).fetchone()
    if window is None:
        raise ValueError(f"Unknown review window: {review_window_id}")
    candidates = conn.execute(
        "SELECT * FROM ownership_gap_candidates WHERE review_window_id = ? ORDER BY priority ASC, level_gap DESC, created_at ASC",
        (review_window_id,),
    ).fetchall()
    debts = conn.execute(
        "SELECT * FROM ownership_debts WHERE source_review_window_id = ? ORDER BY priority ASC, level_gap DESC, created_at ASC",
        (review_window_id,),
    ).fetchall()
    report = {
        "review_window": dict(window),
        "top_ownership_gaps": [dict(row) for row in candidates if row["status"] == "ready"],
        "deferred_or_ignored": [dict(row) for row in candidates if row["status"] in {"deferred", "ignored", "known", "rejected_needs_evidence"}],
        "accepted_debts": [dict(row) for row in debts],
    }
    markdown = _render_task_control_report(report)
    path = None
    if write_file:
        export_dir = exports_path(home) / "task_control"
        export_dir.mkdir(parents=True, exist_ok=True)
        path = export_dir / f"task_control_{_safe_name(review_window_id)}.md"
        path.write_text(markdown, encoding="utf-8")
    return {"review_window_id": review_window_id, "report": report, "markdown": markdown, "path": str(path) if path else None}


def local_hints(changed_files: list[str], diff_snapshot: str) -> dict[str, list[str] | str]:
    lowered = [item.lower() for item in changed_files]
    risky = [item for item in changed_files if any(token in item.lower() for token in ["auth", "payment", "privacy", "database", "migration", "session", "scheduler", "safety", "schema"])]
    dependency = [item for item in changed_files if any(token in item.lower() for token in ["pyproject.toml", "requirements", "package.json", "poetry.lock", "lock"])]
    schema = [item for item in changed_files if any(token in item.lower() for token in ["schema", "migration", "database", "store.py"])]
    validation = [item for item in changed_files if "test" in item.lower() or item.lower().startswith("tests")]
    workaround_tokens = [" type: ignore", " any", "skip", "settimeout", "except exception", "catch", "todo"]
    workaround = [token.strip() for token in workaround_tokens if token in diff_snapshot.lower()]
    possible = "maintenance"
    if any("refactor" in item for item in lowered):
        possible = "refactor"
    elif sum(1 for item in changed_files if item.startswith("??") or item.startswith("A ")) >= 2:
        possible = "creation"
    elif any(item.startswith("??") or item.startswith("A ") for item in changed_files) and any(item.startswith(" M") or item.startswith("M ") for item in changed_files):
        possible = "integration"
    return {
        "risky_files": risky,
        "dependency_changes": dependency,
        "schema_changes": schema,
        "test_or_validation_changes": validation,
        "workaround_signals": workaround,
        "possible_task_type": possible,
    }


def _create_window(conn: sqlite3.Connection, session_id: str, project_id: str, event_id: int, trigger: str, status: str) -> sqlite3.Row:
    now = utc_now()
    window_id = f"win-{uuid4().hex[:12]}"
    conn.execute(
        """
        INSERT INTO ownership_review_windows(id, session_id, project_id, started_event_id, ended_event_id, trigger, status, created_at, updated_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (window_id, session_id, project_id, event_id, event_id, trigger, status, now, now),
    )
    return conn.execute("SELECT * FROM ownership_review_windows WHERE id = ?", (window_id,)).fetchone()


def _open_window(conn: sqlite3.Connection, session_id: str) -> sqlite3.Row | None:
    return conn.execute(
        """
        SELECT * FROM ownership_review_windows
        WHERE session_id = ? AND status = 'open'
        ORDER BY created_at DESC
        LIMIT 1
        """,
        (session_id,),
    ).fetchone()


def _open_or_idle_window(conn: sqlite3.Connection, session_id: str) -> sqlite3.Row | None:
    return conn.execute(
        """
        SELECT * FROM ownership_review_windows
        WHERE session_id = ? AND status IN ('open', 'idle_detected')
        ORDER BY created_at DESC
        LIMIT 1
        """,
        (session_id,),
    ).fetchone()


def _window_has_activity(conn: sqlite3.Connection, review_window_id: str) -> bool:
    window = conn.execute("SELECT * FROM ownership_review_windows WHERE id = ?", (review_window_id,)).fetchone()
    if window is None:
        return False
    return conn.execute(
        """
        SELECT 1 FROM agent_events
        WHERE session_id = ?
          AND id BETWEEN ? AND ?
          AND type IN ('tool_used', 'assistant_stopped')
        LIMIT 1
        """,
        (window["session_id"], window["started_event_id"] or 0, window["ended_event_id"] or window["started_event_id"] or 0),
    ).fetchone() is not None


def _close_window(conn: sqlite3.Connection, review_window_id: str, ended_event_id: int, trigger: str) -> None:
    conn.execute(
        """
        UPDATE ownership_review_windows
        SET ended_event_id = ?, trigger = ?, status = ?, updated_at = ?
        WHERE id = ?
        """,
        (ended_event_id, trigger, "pending_ownership_review", utc_now(), review_window_id),
    )


def _events_for_window(conn: sqlite3.Connection, window: sqlite3.Row) -> list[sqlite3.Row]:
    start = window["started_event_id"] or 0
    end = window["ended_event_id"] or start
    return conn.execute(
        """
        SELECT id, type, turn_id, summary, raw_payload_ref, occurred_at
        FROM agent_events
        WHERE session_id = ? AND id BETWEEN ? AND ?
        ORDER BY id ASC
        """,
        (window["session_id"], start, end),
    ).fetchall()


def _rank_gaps(gaps: list[dict[str, Any]]) -> list[dict[str, Any]]:
    deduped: list[dict[str, Any]] = []
    seen: set[tuple[str, str]] = set()
    for gap in gaps:
        key = (str(gap.get("control_point") or "").lower(), str(gap.get("gap_type") or "").lower())
        if key in seen:
            continue
        seen.add(key)
        deduped.append(gap)
    return sorted(deduped, key=_rank_key)


def _rank_key(gap: dict[str, Any]) -> tuple[int, int, int, int]:
    priority = PRIORITIES.get(str(gap.get("priority") or "P2"), 2)
    level_gap = _level(str(gap.get("required_level") or "L2")) - _level(str(gap.get("current_level") or "L1"))
    type_boost = 0 if gap.get("gap_type") in HIGH_RISK_GAPS else 1
    evidence_count = len(_evidence_refs(gap))
    return (priority, -level_gap, type_boost, -evidence_count)


def _candidate_rejection_reasons(gap: dict[str, Any]) -> list[str]:
    reasons: list[str] = []
    for field in ("title", "summary", "control_point", "gap_reason"):
        if not str(gap.get(field, "")).strip():
            reasons.append(f"missing {field}")
    if _gap_type(gap.get("gap_type")) != gap.get("gap_type"):
        reasons.append("invalid gap_type")
    if not _evidence_refs(gap):
        reasons.append("missing evidence")
    if gap.get("gap_type") in HIGH_RISK_GAPS:
        roles = {ref.get("role") for ref in _evidence_refs(gap)}
        if not roles.intersection({"change_evidence", "ai_decision"}):
            reasons.append("high risk gap requires change_evidence or ai_decision")
    return reasons


def _evidence_refs(gap: dict[str, Any]) -> list[dict[str, str]]:
    refs: list[dict[str, str]] = []
    raw = gap.get("evidence_refs")
    if not isinstance(raw, list):
        return refs
    seen: set[tuple[str, str, str]] = set()
    for item in raw:
        if not isinstance(item, dict) or not item.get("kind") or not item.get("ref"):
            continue
        ref = {
            "kind": str(item["kind"]),
            "ref": str(item["ref"]),
            "role": str(item.get("role") or "gap_signal"),
        }
        key = (ref["kind"], ref["ref"], ref["role"])
        if key in seen:
            continue
        seen.add(key)
        refs.append(ref)
    return refs


def _event_id_from_ref(ref: dict[str, str]) -> int | None:
    value = ref.get("ref", "")
    for prefix in ("agent_events.id=", "event:"):
        if value.startswith(prefix):
            try:
                return int(value[len(prefix) :])
            except ValueError:
                return None
    return None


def _index_concepts(conn: sqlite3.Connection, debt_id: str, project_id: str, knowledge_json: str, now: str) -> None:
    try:
        knowledge = json.loads(knowledge_json)
    except json.JSONDecodeError:
        knowledge = {}
    concepts = knowledge.get("introduced_concepts") if isinstance(knowledge, dict) else []
    if isinstance(concepts, str):
        concepts = [concepts]
    if not isinstance(concepts, list):
        return
    for concept in concepts:
        if not str(concept).strip():
            continue
        conn.execute(
            """
            INSERT INTO ownership_concepts(debt_id, project_id, concept, familiarity, minimum_mastery_level, status, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                debt_id,
                project_id,
                str(concept),
                str(knowledge.get("user_familiarity") or "unknown"),
                str(knowledge.get("minimum_mastery_level") or "L2"),
                "open",
                now,
                now,
            ),
        )


def _learning_payload(row: dict[str, Any], kind: str) -> dict[str, Any]:
    repayment = _json(row.get("repayment_json"), {})
    knowledge = _json(row.get("knowledge_json"), {})
    evidence = _json(row.get("evidence_json"), [])
    criteria = repayment.get("validation_criteria") if isinstance(repayment.get("validation_criteria"), list) else []
    check_prompt = f"Explain how you would recover ownership of {row['control_point']} to {row['required_level']}."
    if row.get("gap_type") == "concept_ownership_gap":
        check_prompt = f"Explain {row['title']} in this project and point to the code path where it matters."
    return {
        "id": row["id"],
        "kind": kind,
        "title": row["title"],
        "concept": row["title"],
        "gap_type": row["gap_type"],
        "dimension": row["dimension"],
        "required_level": row["required_level"],
        "current_level": row["current_level"],
        "control_point": row["control_point"],
        "short_explanation": row["summary"],
        "why_it_matters": row["gap_reason"],
        "minimal_trace": f"Review window: {row.get('source_review_window_id') or row.get('review_window_id')}",
        "repayment_task": row["repayment_task"],
        "validation_criteria": criteria,
        "check_prompt": check_prompt,
        "quick_check_prompt": check_prompt,
        "knowledge_context": knowledge,
        "evidence": evidence,
    }


def _check_result(agent_assessment: dict[str, Any] | None, user_override: str | None, skipped: bool) -> str:
    if skipped:
        return "skipped"
    if user_override in {"partial", "verified", "needs_followup"}:
        return user_override
    if agent_assessment and agent_assessment.get("result") in {"partial", "verified", "needs_followup"}:
        return str(agent_assessment["result"])
    return "in_progress"


def _render_task_control_report(report: dict[str, Any]) -> str:
    window = report["review_window"]
    lines = [
        f"# Task Control Report: {window['id']}",
        "",
        "## Task",
        f"- Session: {window['session_id']}",
        f"- Project: {window['project_id']}",
        f"- Trigger: {window['trigger']}",
        f"- Status: {window['status']}",
        "",
        "## Top Ownership Gaps",
    ]
    top = report["top_ownership_gaps"]
    if top:
        for item in top:
            lines.append(f"- [{item['priority']}] {item['title']} ({item['gap_type']}): {item['summary']}")
    else:
        lines.append("- No ready ownership gaps.")
    lines.extend(["", "## Deferred / Ignored"])
    deferred = report["deferred_or_ignored"]
    if deferred:
        for item in deferred:
            lines.append(f"- [{item['status']}] {item['title']} ({item['gap_type']})")
    else:
        lines.append("- None.")
    lines.extend(["", "## Accepted Debts"])
    debts = report["accepted_debts"]
    if debts:
        for item in debts:
            lines.append(f"- [{item['priority']}] {item['title']} -> {item['status']}")
    else:
        lines.append("- No accepted ownership debts.")
    lines.extend(["", "## Recovery Tasks"])
    if debts:
        for item in debts:
            lines.append(f"- {item['title']}: {item['repayment_task']}")
    else:
        lines.append("- Accept an ownership gap to create a recovery task.")
    lines.append("")
    return "\n".join(lines)


def _text(value: dict[str, Any], key: str, default: str) -> str:
    text = str(value.get(key) or "").strip()
    return text or default


def _priority(value: Any) -> str:
    text = str(value or "P2")
    return text if text in PRIORITIES else "P2"


def _gap_type(value: Any) -> str:
    text = str(value or "concept_ownership_gap")
    return text if text in GAP_TYPES else "concept_ownership_gap"


def _repayment_type(value: Any) -> str:
    text = str(value or "explain_back")
    return text if text in REPAYMENT_TYPES else "explain_back"


def _level_name(value: Any, default: str) -> str:
    text = str(value or default)
    return text if text in LEVELS else default


def _level(value: str) -> int:
    return LEVELS.get(value, 0)


def _task_label(task_type: str) -> str:
    return {
        "creation": "新增模块",
        "maintenance": "旧模块维护",
        "integration": "新旧接入",
        "refactor": "重构整理",
        "experiment": "实验探索",
    }.get(task_type, "旧模块维护")


def _read_optional(path: Path) -> str | None:
    if not path.exists():
        return None
    return path.read_text(encoding="utf-8")


def _read_lines(path: Path) -> list[str]:
    if not path.exists():
        return []
    return [line for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def _json(value: Any, default: Any) -> Any:
    if not isinstance(value, str):
        return default
    try:
        return json.loads(value)
    except json.JSONDecodeError:
        return default


def _safe_name(value: str) -> str:
    return "".join(char if char.isalnum() or char in {"-", "_", "."} else "_" for char in value)


def _deep_merge(base: dict[str, Any], patch: dict[str, Any]) -> dict[str, Any]:
    result = dict(base)
    for key, value in patch.items():
        if isinstance(value, dict) and isinstance(result.get(key), dict):
            result[key] = _deep_merge(result[key], value)
        else:
            result[key] = value
    return result
