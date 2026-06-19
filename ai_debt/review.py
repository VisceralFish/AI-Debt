from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Any
from uuid import uuid4

from .evidence import collect_evidence_refs, evaluate_candidate
from .journal import utc_now


VALID_ACTIONS = {"accept", "skip", "already_know", "learn_one"}


def select_review_session(conn: sqlite3.Connection, session_id: str | None = None) -> sqlite3.Row | None:
    if session_id:
        return conn.execute("SELECT * FROM sessions WHERE id = ?", (session_id,)).fetchone()
    return conn.execute(
        """
        SELECT * FROM sessions
        WHERE status = 'pending_settlement'
        ORDER BY last_activity_at DESC
        LIMIT 1
        """
    ).fetchone()


def build_review_input(conn: sqlite3.Connection, session_id: str) -> dict[str, Any]:
    session = conn.execute("SELECT * FROM sessions WHERE id = ?", (session_id,)).fetchone()
    if session is None:
        raise ValueError(f"Unknown session: {session_id}")
    events = conn.execute(
        """
        SELECT id, type, turn_id, summary, raw_payload_ref, occurred_at
        FROM agent_events
        WHERE session_id = ?
        ORDER BY id ASC
        """,
        (session_id,),
    ).fetchall()
    related_debts = conn.execute(
        """
        SELECT id, concept, debt_dimension, priority, status
        FROM cognitive_debts
        WHERE source_agent = ?
        ORDER BY updated_at DESC
        LIMIT 20
        """,
        (session["source"],),
    ).fetchall()
    journal_path = Path(session["journal_path"])
    return {
        "session": {
            "id": session["id"],
            "source": session["source"],
            "cwd": session["cwd"],
            "transcript_ref": session["transcript_ref"],
            "started_at": session["started_at"],
            "last_activity_at": session["last_activity_at"],
            "status": session["status"],
        },
        "event_summaries": [dict(row) for row in events],
        "diff_snapshot": _read_optional(journal_path / "diff.patch"),
        "changed_files": _read_lines(journal_path / "changed_files.txt"),
        "transcript_refs": [session["transcript_ref"]] if session["transcript_ref"] else [],
        "existing_related_debts": [dict(row) for row in related_debts],
        "expected_output_schema": {
            "session_summary": "string",
            "delegation_points": [
                {
                    "id": "string",
                    "summary": "string",
                    "event_refs": ["agent_events.id"],
                    "diff_refs": ["diff.patch"],
                    "transcript_refs": ["transcript ref"],
                }
            ],
            "debt_candidates": [
                {
                    "concept": "string",
                    "debt_dimension": "concept|code|architecture|tool|debug|intent|maintenance|verification",
                    "why_it_matters": "string",
                    "priority": "P0|P1|P2",
                    "delegation_point_id": "string",
                    "evidence_refs": [{"kind": "event|diff|transcript", "ref": "string"}],
                    "learn_one": {
                        "short_explanation": "string",
                        "minimal_trace": "string",
                        "quick_check_prompt": "string",
                    },
                }
            ],
        },
    }


def parse_analysis(text: str) -> dict[str, Any]:
    try:
        value = json.loads(text)
    except json.JSONDecodeError as exc:
        raise ValueError(f"Invalid review analysis JSON: {exc}") from exc
    if not isinstance(value, dict):
        raise ValueError("Review analysis must be a JSON object")
    if not isinstance(value.get("session_summary"), str):
        raise ValueError("Review analysis requires session_summary")
    if not isinstance(value.get("delegation_points"), list):
        raise ValueError("Review analysis requires delegation_points[]")
    if not isinstance(value.get("debt_candidates"), list):
        raise ValueError("Review analysis requires debt_candidates[]")
    return value


def create_candidates(conn: sqlite3.Connection, session_id: str, analysis: dict[str, Any]) -> list[dict[str, Any]]:
    session = conn.execute("SELECT * FROM sessions WHERE id = ?", (session_id,)).fetchone()
    if session is None:
        raise ValueError(f"Unknown session: {session_id}")

    now = utc_now()
    created: list[dict[str, Any]] = []
    delegation_points = analysis["delegation_points"]
    for raw_candidate in analysis["debt_candidates"]:
        if not isinstance(raw_candidate, dict):
            continue
        is_ready, reasons = evaluate_candidate(raw_candidate, delegation_points)
        candidate_id = str(raw_candidate.get("id") or f"cand-{uuid4().hex[:12]}")
        priority = str(raw_candidate.get("priority") or "P2")
        status = "ready" if is_ready else "rejected_needs_evidence"
        payload = {
            **raw_candidate,
            "gate": {"passed": is_ready, "reasons": reasons},
            "session_summary": analysis["session_summary"],
        }
        conn.execute(
            """
            INSERT INTO debt_candidates(
              id, session_id, source_agent, concept, debt_dimension, why_it_matters,
              priority, status, payload_json, created_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(id) DO UPDATE SET
              status = excluded.status,
              payload_json = excluded.payload_json
            """,
            (
                candidate_id,
                session_id,
                session["source"],
                str(raw_candidate.get("concept") or "Unspecified concept"),
                str(raw_candidate.get("debt_dimension") or "verification"),
                str(raw_candidate.get("why_it_matters") or "Candidate did not include why_it_matters."),
                priority,
                status,
                json.dumps(payload, ensure_ascii=False, sort_keys=True),
                now,
            ),
        )
        conn.execute("DELETE FROM evidence_refs WHERE candidate_id = ? AND debt_id IS NULL", (candidate_id,))
        for ref in collect_evidence_refs(raw_candidate, delegation_points):
            conn.execute(
                """
                INSERT INTO evidence_refs(candidate_id, session_id, kind, ref, created_at)
                VALUES (?, ?, ?, ?, ?)
                """,
                (candidate_id, session_id, ref["kind"], ref["ref"], now),
            )
        created.append({"id": candidate_id, "status": status, "gate_reasons": reasons})

    conn.execute("UPDATE sessions SET status = ? WHERE id = ?", ("candidates_ready", session_id))
    conn.commit()
    return created


def apply_review_action(conn: sqlite3.Connection, candidate_id: str, action: str) -> str | None:
    if action not in VALID_ACTIONS:
        raise ValueError(f"Unsupported review action: {action}")
    candidate = conn.execute("SELECT * FROM debt_candidates WHERE id = ?", (candidate_id,)).fetchone()
    if candidate is None:
        raise ValueError(f"Unknown candidate: {candidate_id}")
    now = utc_now()
    debt_id: str | None = None
    if action == "accept":
        if candidate["status"] != "ready":
            raise ValueError("Only evidence-backed candidates can be accepted")
        debt_id = f"debt-{uuid4().hex[:12]}"
        conn.execute(
            """
            INSERT INTO cognitive_debts(
              id, concept, debt_dimension, source_session_id, source_agent, why_it_matters,
              priority, status, seen_count, created_at, updated_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                debt_id,
                candidate["concept"],
                candidate["debt_dimension"],
                candidate["session_id"],
                candidate["source_agent"],
                candidate["why_it_matters"],
                candidate["priority"],
                "unverified",
                1,
                now,
                now,
            ),
        )
        conn.execute(
            """
            UPDATE evidence_refs
            SET debt_id = ?
            WHERE candidate_id = ? AND debt_id IS NULL
            """,
            (debt_id, candidate_id),
        )
        conn.execute(
            """
            INSERT INTO inbox_items(debt_id, status, priority, created_at)
            VALUES (?, ?, ?, ?)
            """,
            (debt_id, "open", candidate["priority"], now),
        )
        conn.execute("UPDATE debt_candidates SET status = ? WHERE id = ?", ("accepted", candidate_id))
    elif action == "skip":
        conn.execute("UPDATE debt_candidates SET status = ? WHERE id = ?", ("skipped", candidate_id))
    elif action == "already_know":
        conn.execute("UPDATE debt_candidates SET status = ? WHERE id = ?", ("dismissed_as_known", candidate_id))

    conn.execute(
        "INSERT INTO review_actions(candidate_id, debt_id, action, created_at) VALUES (?, ?, ?, ?)",
        (candidate_id, debt_id, action, now),
    )
    conn.commit()
    return debt_id


def list_inbox(conn: sqlite3.Connection) -> list[sqlite3.Row]:
    return conn.execute(
        """
        SELECT inbox_items.id AS inbox_id, cognitive_debts.id AS debt_id, cognitive_debts.concept,
               cognitive_debts.debt_dimension, cognitive_debts.priority, cognitive_debts.status,
               cognitive_debts.seen_count, inbox_items.next_review_at
        FROM inbox_items
        JOIN cognitive_debts ON cognitive_debts.id = inbox_items.debt_id
        WHERE cognitive_debts.status IN ('unverified', 'partial')
        ORDER BY cognitive_debts.priority ASC, cognitive_debts.seen_count DESC, inbox_items.next_review_at ASC
        """
    ).fetchall()


def learn_one(conn: sqlite3.Connection, item_id: str | None = None) -> dict[str, str]:
    if item_id is None:
        row = conn.execute(
            """
            SELECT cognitive_debts.*
            FROM inbox_items
            JOIN cognitive_debts ON cognitive_debts.id = inbox_items.debt_id
            WHERE cognitive_debts.status IN ('unverified', 'partial')
            ORDER BY cognitive_debts.priority ASC, cognitive_debts.seen_count DESC
            LIMIT 1
            """
        ).fetchone()
        if row is None:
            raise ValueError("No inbox item available for learn-one")
        return _debt_learning(dict(row))

    debt = conn.execute("SELECT * FROM cognitive_debts WHERE id = ?", (item_id,)).fetchone()
    if debt:
        return _debt_learning(dict(debt))

    candidate = conn.execute("SELECT * FROM debt_candidates WHERE id = ?", (item_id,)).fetchone()
    if candidate:
        payload = json.loads(candidate["payload_json"])
        return _candidate_learning(dict(candidate), payload)

    raise ValueError(f"Unknown candidate or debt: {item_id}")


def record_grasp_check(conn: sqlite3.Connection, debt_id: str, answer: str | None, skipped: bool = False) -> str:
    debt = conn.execute("SELECT * FROM cognitive_debts WHERE id = ?", (debt_id,)).fetchone()
    if debt is None:
        raise ValueError(f"Unknown debt: {debt_id}")
    now = utc_now()
    result = "skipped" if skipped else _evaluate_answer(answer)
    conn.execute(
        """
        INSERT INTO grasp_checks(debt_id, prompt, answer, result, skipped, created_at)
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        (debt_id, f"Explain {debt['concept']} in your own words.", answer, result, 1 if skipped else 0, now),
    )
    if result == "solid":
        conn.execute("UPDATE cognitive_debts SET status = ?, updated_at = ? WHERE id = ?", ("solid", now, debt_id))
    elif result == "partial":
        conn.execute("UPDATE cognitive_debts SET status = ?, updated_at = ? WHERE id = ?", ("partial", now, debt_id))
    conn.commit()
    return result


def _candidate_learning(candidate: dict[str, Any], payload: dict[str, Any]) -> dict[str, str]:
    learn = payload.get("learn_one") if isinstance(payload.get("learn_one"), dict) else {}
    return {
        "id": candidate["id"],
        "kind": "candidate",
        "concept": candidate["concept"],
        "short_explanation": str(learn.get("short_explanation") or candidate["why_it_matters"]),
        "why_it_matters": candidate["why_it_matters"],
        "minimal_trace": str(learn.get("minimal_trace") or payload.get("delegation_point_id") or "See evidence refs."),
        "quick_check_prompt": str(learn.get("quick_check_prompt") or f"Explain {candidate['concept']} in your own words."),
    }


def _debt_learning(debt: dict[str, Any]) -> dict[str, str]:
    return {
        "id": debt["id"],
        "kind": "debt",
        "concept": debt["concept"],
        "short_explanation": debt["why_it_matters"],
        "why_it_matters": debt["why_it_matters"],
        "minimal_trace": f"Source session: {debt['source_session_id']}",
        "quick_check_prompt": f"Explain {debt['concept']} in your own words.",
    }


def _evaluate_answer(answer: str | None) -> str:
    if not answer or not answer.strip():
        return "partial"
    words = answer.split()
    return "solid" if len(words) >= 8 else "partial"


def _read_optional(path: Path) -> str | None:
    if not path.exists():
        return None
    return path.read_text(encoding="utf-8")


def _read_lines(path: Path) -> list[str]:
    if not path.exists():
        return []
    return [line for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
