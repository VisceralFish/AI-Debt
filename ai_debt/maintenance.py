from __future__ import annotations

import json
import shutil
import sqlite3
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from .config import AppConfig
from .events import validate_event
from .journal import utc_now
from .paths import exports_path, journals_path
from .store import record_event, refresh_session_states


@dataclass
class CleanupResult:
    raw_payloads: list[Path]


def cleanup_raw_payloads(config: AppConfig, home: Path | None = None, dry_run: bool = False, now: datetime | None = None) -> CleanupResult:
    root = journals_path(home)
    cutoff = (now or datetime.now(timezone.utc)) - timedelta(days=config.privacy.raw_payload_retention_days)
    expired: list[Path] = []
    if not root.exists():
        return CleanupResult(expired)
    for path in root.glob("*/raw/*.json"):
        modified = datetime.fromtimestamp(path.stat().st_mtime, timezone.utc)
        if modified < cutoff:
            expired.append(path)
            if not dry_run:
                path.unlink()
    return CleanupResult(expired)


def delete_session(conn: sqlite3.Connection, session_id: str, home: Path | None = None) -> None:
    journal_path = journals_path(home) / _safe_name(session_id)
    conn.execute("DELETE FROM evidence_refs WHERE session_id = ?", (session_id,))
    conn.execute("DELETE FROM debt_candidates WHERE session_id = ?", (session_id,))
    conn.execute("DELETE FROM sessions WHERE id = ?", (session_id,))
    conn.commit()
    if journal_path.exists():
        shutil.rmtree(journal_path)


def delete_debt(conn: sqlite3.Connection, debt_id: str) -> None:
    conn.execute("DELETE FROM inbox_items WHERE debt_id = ?", (debt_id,))
    conn.execute("DELETE FROM grasp_checks WHERE debt_id = ?", (debt_id,))
    conn.execute("UPDATE evidence_refs SET debt_id = NULL WHERE debt_id = ?", (debt_id,))
    conn.execute("UPDATE review_actions SET debt_id = NULL WHERE debt_id = ?", (debt_id,))
    conn.execute("DELETE FROM cognitive_debts WHERE id = ?", (debt_id,))
    conn.commit()


def export_deep_review(conn: sqlite3.Connection, session_id: str | None = None, home: Path | None = None) -> Path:
    session = _select_export_session(conn, session_id)
    if session is None:
        raise ValueError("No reviewed session available for export")

    candidates = conn.execute(
        """
        SELECT * FROM debt_candidates
        WHERE session_id = ?
        ORDER BY created_at ASC
        """,
        (session["id"],),
    ).fetchall()
    debts = conn.execute(
        """
        SELECT * FROM cognitive_debts
        WHERE source_session_id = ?
        ORDER BY created_at ASC
        """,
        (session["id"],),
    ).fetchall()
    actions = conn.execute(
        """
        SELECT * FROM review_actions
        WHERE candidate_id IN (SELECT id FROM debt_candidates WHERE session_id = ?)
        ORDER BY created_at ASC
        """,
        (session["id"],),
    ).fetchall()

    export_dir = exports_path(home) / "deep_review"
    export_dir.mkdir(parents=True, exist_ok=True)
    path = export_dir / f"deep_review_{_safe_name(session['id'])}.md"
    path.write_text(_render_deep_review(session, candidates, debts, actions), encoding="utf-8")
    return path


def recover_from_journals(conn: sqlite3.Connection, config: AppConfig, home: Path | None = None) -> int:
    recovered = 0
    for events_path in journals_path(home).glob("*/events.jsonl"):
        for line in events_path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            payload = json.loads(line)
            event = validate_event(payload)
            exists = conn.execute(
                """
                SELECT 1 FROM agent_events
                WHERE session_id = ? AND type = ? AND occurred_at = ? AND raw_payload_ref = ?
                """,
                (event["session_id"], event["type"], event["occurred_at"], event["raw_payload_ref"]),
            ).fetchone()
            if exists:
                continue
            record_event(conn, event, home)
            recovered += 1
    refresh_session_states(conn, config)
    return recovered


def schema_is_valid(conn: sqlite3.Connection) -> bool:
    required = {
        "sessions",
        "agent_events",
        "evidence_refs",
        "debt_candidates",
        "cognitive_debts",
        "review_actions",
        "grasp_checks",
        "inbox_items",
    }
    rows = conn.execute("SELECT name FROM sqlite_master WHERE type = 'table'").fetchall()
    return required.issubset({row["name"] for row in rows})


def last_hook_event(conn: sqlite3.Connection) -> sqlite3.Row | None:
    return conn.execute(
        """
        SELECT session_id, source, type, occurred_at
        FROM agent_events
        ORDER BY occurred_at DESC, id DESC
        LIMIT 1
        """
    ).fetchone()


def raw_payload_cleanup_summary(config: AppConfig, home: Path | None = None, now: datetime | None = None) -> tuple[int, int]:
    root = journals_path(home)
    if not root.exists():
        return 0, 0
    total = 0
    expired = 0
    cutoff = (now or datetime.now(timezone.utc)) - timedelta(days=config.privacy.raw_payload_retention_days)
    for path in root.glob("*/raw/*.json"):
        total += 1
        if datetime.fromtimestamp(path.stat().st_mtime, timezone.utc) < cutoff:
            expired += 1
    return total, expired


def _select_export_session(conn: sqlite3.Connection, session_id: str | None) -> sqlite3.Row | None:
    if session_id:
        return conn.execute("SELECT * FROM sessions WHERE id = ?", (session_id,)).fetchone()
    return conn.execute(
        """
        SELECT * FROM sessions
        WHERE status IN ('candidates_ready', 'pending_settlement')
           OR id IN (SELECT source_session_id FROM cognitive_debts)
        ORDER BY last_activity_at DESC
        LIMIT 1
        """
    ).fetchone()


def _render_deep_review(
    session: sqlite3.Row,
    candidates: list[sqlite3.Row],
    debts: list[sqlite3.Row],
    actions: list[sqlite3.Row],
) -> str:
    candidate_payloads = [_payload(row) for row in candidates]
    session_summary = next((payload.get("session_summary") for payload in candidate_payloads if payload.get("session_summary")), "No session summary captured.")
    delegation_points = _delegation_points(candidate_payloads)
    skipped = [row for row in candidates if row["status"] in {"skipped", "dismissed_as_known", "rejected_needs_evidence"}]
    lines = [
        f"# Deep Review: {session['id']}",
        "",
        "## Session Summary",
        str(session_summary),
        "",
        "## Delegation Points",
    ]
    if delegation_points:
        for point in delegation_points:
            lines.append(f"- {point}")
    else:
        lines.append("- No delegation points captured.")
    lines.extend(["", "## Accepted Debts"])
    if debts:
        for debt in debts:
            lines.append(f"- [{debt['priority']}] {debt['concept']} ({debt['debt_dimension']}): {debt['why_it_matters']}")
    else:
        lines.append("- No accepted debts.")
    lines.extend(["", "## Skipped Candidates"])
    if skipped:
        for candidate in skipped:
            lines.append(f"- {candidate['concept']} ({candidate['status']})")
    else:
        lines.append("- No skipped candidates.")
    lines.extend(["", "## Intent Rationale"])
    for debt in debts:
        if debt["debt_dimension"] == "intent":
            lines.append(f"- {debt['concept']}: {debt['why_it_matters']}")
    if not any(debt["debt_dimension"] == "intent" for debt in debts):
        lines.append("- No accepted intent debt.")
    lines.extend(["", "## Risks And Alternatives"])
    if actions:
        lines.append("- Review actions were recorded; inspect candidate evidence before relying on conclusions.")
    else:
        lines.append("- No review actions recorded yet.")
    lines.extend(["", "## Recommended Next Checks"])
    if debts:
        for debt in debts:
            lines.append(f"- Run `ai-debt learn-one {debt['id']}` then `ai-debt check {debt['id']}`.")
    else:
        lines.append("- Run `ai-debt review` and accept evidence-backed candidates first.")
    lines.append("")
    return "\n".join(lines)


def _payload(row: sqlite3.Row) -> dict[str, Any]:
    try:
        return json.loads(row["payload_json"])
    except json.JSONDecodeError:
        return {}


def _delegation_points(payloads: list[dict[str, Any]]) -> list[str]:
    points: list[str] = []
    seen: set[str] = set()
    for payload in payloads:
        point_id = payload.get("delegation_point_id")
        if point_id and str(point_id) not in seen:
            seen.add(str(point_id))
            points.append(str(point_id))
    return points


def _safe_name(value: str) -> str:
    return "".join(char if char.isalnum() or char in {"-", "_", "."} else "_" for char in value)
