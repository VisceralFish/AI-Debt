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
from .ownership import task_control_report
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
    conn.execute("DELETE FROM ownership_concepts WHERE debt_id IN (SELECT id FROM ownership_debts WHERE source_session_id = ?)", (session_id,))
    conn.execute("DELETE FROM ownership_debts WHERE source_session_id = ?", (session_id,))
    conn.execute("DELETE FROM ownership_gap_candidates WHERE session_id = ?", (session_id,))
    conn.execute("DELETE FROM ownership_review_windows WHERE session_id = ?", (session_id,))
    conn.execute("DELETE FROM sessions WHERE id = ?", (session_id,))
    conn.commit()
    if journal_path.exists():
        shutil.rmtree(journal_path)


def delete_debt(conn: sqlite3.Connection, debt_id: str) -> None:
    conn.execute("DELETE FROM ownership_concepts WHERE debt_id = ?", (debt_id,))
    conn.execute("DELETE FROM grasp_checks WHERE debt_id = ?", (debt_id,))
    conn.execute("UPDATE evidence_refs SET debt_id = NULL WHERE debt_id = ?", (debt_id,))
    conn.execute("UPDATE review_actions SET debt_id = NULL WHERE debt_id = ?", (debt_id,))
    conn.execute("DELETE FROM ownership_debts WHERE id = ?", (debt_id,))
    conn.commit()


def export_task_control_report(conn: sqlite3.Connection, review_window_id: str | None = None, home: Path | None = None) -> Path:
    window = _select_export_window(conn, review_window_id)
    if window is None:
        raise ValueError("No ownership review window available for export")
    result = task_control_report(conn, window["id"], home, write_file=True)
    return Path(result["path"])


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
        "ownership_profiles",
        "ownership_review_windows",
        "ownership_gap_candidates",
        "ownership_debts",
        "ownership_concepts",
        "review_actions",
        "grasp_checks",
        "companion_notifications",
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


def _select_export_window(conn: sqlite3.Connection, review_window_id: str | None) -> sqlite3.Row | None:
    if review_window_id:
        return conn.execute("SELECT * FROM ownership_review_windows WHERE id = ?", (review_window_id,)).fetchone()
    return conn.execute(
        """
        SELECT * FROM ownership_review_windows
        WHERE status IN ('candidates_ready', 'reviewed', 'analysis_submitted', 'pending_ownership_review')
           OR id IN (SELECT source_review_window_id FROM ownership_debts)
        ORDER BY updated_at DESC
        LIMIT 1
        """
    ).fetchone()


def _safe_name(value: str) -> str:
    return "".join(char if char.isalnum() or char in {"-", "_", "."} else "_" for char in value)
