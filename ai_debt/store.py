from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

from .config import AppConfig
from .events import AgentEvent, event_summary
from .journal import session_dir


def record_event(conn: sqlite3.Connection, event: AgentEvent, home: Path | None = None) -> None:
    status = "pending_settlement" if event["type"] == "session_ended" else "recording"
    cwd = event.get("cwd")
    transcript_ref = event.get("transcript_ref")
    started_at = event["occurred_at"]
    existing = conn.execute("SELECT id, started_at, cwd, transcript_ref FROM sessions WHERE id = ?", (event["session_id"],)).fetchone()
    if existing:
        started_at = existing["started_at"]
        cwd = cwd or existing["cwd"]
        transcript_ref = transcript_ref or existing["transcript_ref"]

    conn.execute(
        """
        INSERT INTO sessions(id, source, cwd, transcript_ref, started_at, last_activity_at, ended_at, status, journal_path)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(id) DO UPDATE SET
          source = excluded.source,
          cwd = COALESCE(excluded.cwd, sessions.cwd),
          transcript_ref = COALESCE(excluded.transcript_ref, sessions.transcript_ref),
          last_activity_at = excluded.last_activity_at,
          ended_at = COALESCE(excluded.ended_at, sessions.ended_at),
          status = excluded.status,
          journal_path = excluded.journal_path
        """,
        (
            event["session_id"],
            event["source"],
            cwd,
            transcript_ref,
            started_at,
            event["occurred_at"],
            event["occurred_at"] if event["type"] == "session_ended" else None,
            status,
            str(session_dir(event["session_id"], home)),
        ),
    )
    conn.execute(
        """
        INSERT INTO agent_events(
          session_id, source, type, turn_id, summary, raw_payload_ref, occurred_at, payload_json
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            event["session_id"],
            event["source"],
            event["type"],
            event.get("turn_id"),
            event_summary(event),
            event["raw_payload_ref"],
            event["occurred_at"],
            json.dumps(event, ensure_ascii=False, sort_keys=True),
        ),
    )
    conn.commit()


def refresh_session_states(conn: sqlite3.Connection, config: AppConfig, now: datetime | None = None) -> None:
    now = now or datetime.now(timezone.utc)
    rows = conn.execute("SELECT id, last_activity_at, ended_at, status FROM sessions WHERE status != 'pending_settlement'").fetchall()
    for row in rows:
        last_activity = _parse_time(row["last_activity_at"])
        inactive_minutes = (now - last_activity).total_seconds() / 60
        next_status = row["status"]
        if row["ended_at"] or inactive_minutes >= config.pending_minutes:
            next_status = "pending_settlement"
        elif inactive_minutes >= config.idle_minutes:
            next_status = "idle_detected"
        if next_status != row["status"]:
            conn.execute("UPDATE sessions SET status = ? WHERE id = ?", (next_status, row["id"]))
    conn.commit()


def status_counts(conn: sqlite3.Connection) -> dict[str, int]:
    rows = conn.execute("SELECT status, COUNT(*) AS count FROM sessions GROUP BY status").fetchall()
    return {row["status"]: row["count"] for row in rows}


def recent_sessions(conn: sqlite3.Connection, limit: int = 5) -> list[sqlite3.Row]:
    return conn.execute(
        """
        SELECT id, source, status, last_activity_at
        FROM sessions
        ORDER BY last_activity_at DESC
        LIMIT ?
        """,
        (limit,),
    ).fetchall()


def list_sessions(conn: sqlite3.Connection, limit: int = 10, status: str | None = None) -> list[sqlite3.Row]:
    if status:
        return conn.execute(
            """
            SELECT id, source, status, last_activity_at
            FROM sessions
            WHERE status = ?
            ORDER BY last_activity_at DESC
            LIMIT ?
            """,
            (status, limit),
        ).fetchall()
    return recent_sessions(conn, limit)


def _parse_time(value: str) -> datetime:
    if value.endswith("Z"):
        value = value[:-1] + "+00:00"
    parsed = datetime.fromisoformat(value)
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)
