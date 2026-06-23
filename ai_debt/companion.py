from __future__ import annotations

import sqlite3
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import TextIO

from .config import AppConfig, load_config
from .core import initialize
from .paths import db_path
from .schema import connect, migrate
from .store import refresh_session_states


COMPANION_POLL_SECONDS = 30
PENDING_SETTLEMENT_EVENT = "pending_settlement"


@dataclass(frozen=True)
class CompanionNotification:
    session_id: str
    review_window_id: str
    source: str
    last_activity_at: str


def collect_pending_notifications(
    conn: sqlite3.Connection,
    config: AppConfig,
    now: datetime | None = None,
) -> list[CompanionNotification]:
    refresh_session_states(conn, config, now)
    rows = conn.execute(
        """
        SELECT
          sessions.id AS session_id,
          sessions.source AS source,
          sessions.last_activity_at AS last_activity_at,
          ownership_review_windows.id AS review_window_id
        FROM sessions
        JOIN ownership_review_windows ON ownership_review_windows.session_id = sessions.id
        WHERE sessions.status = 'pending_settlement'
          AND ownership_review_windows.status IN ('pending_ownership_review', 'analysis_requested')
          AND NOT EXISTS (
            SELECT 1
            FROM companion_notifications
            WHERE companion_notifications.session_id = sessions.id
              AND companion_notifications.event_type = ? || ':' || ownership_review_windows.id
          )
        ORDER BY sessions.last_activity_at DESC
        """,
        (PENDING_SETTLEMENT_EVENT,),
    ).fetchall()
    notified_at = _iso_utc(now)
    for row in rows:
        event_type = f"{PENDING_SETTLEMENT_EVENT}:{row['review_window_id']}"
        conn.execute(
            """
            INSERT OR IGNORE INTO companion_notifications(session_id, event_type, notified_at)
            VALUES (?, ?, ?)
            """,
            (row["session_id"], event_type, notified_at),
        )
        conn.execute(
            """
            UPDATE ownership_review_windows
            SET status = 'analysis_requested', updated_at = ?
            WHERE id = ? AND status = 'pending_ownership_review'
            """,
            (notified_at, row["review_window_id"]),
        )
    conn.commit()
    return [
        CompanionNotification(
            session_id=row["session_id"],
            review_window_id=row["review_window_id"],
            source=row["source"],
            last_activity_at=row["last_activity_at"],
        )
        for row in rows
    ]


def run_companion_once(
    home: Path | None = None,
    now: datetime | None = None,
    output: TextIO | None = None,
) -> list[CompanionNotification]:
    initialize(home)
    conn = connect(db_path(home))
    try:
        migrate(conn)
        notifications = collect_pending_notifications(conn, load_config(home), now)
    finally:
        conn.close()
    if notifications and output is not None:
        output.write(render_pending_bubble(notifications) + "\n")
    return notifications


def run_companion_loop(
    home: Path | None = None,
    interval_seconds: int = COMPANION_POLL_SECONDS,
    output: TextIO | None = None,
) -> None:
    while True:
        run_companion_once(home, output=output)
        time.sleep(interval_seconds)


def render_pending_bubble(notifications: list[CompanionNotification]) -> str:
    latest = notifications[0]
    session_label = "session" if len(notifications) == 1 else "sessions"
    lines = [
        "AI Debt: ownership analysis needed",
        f"{len(notifications)} {session_label} has pending review work",
        f"latest: {latest.session_id} [{latest.source}]",
        f"window: {latest.review_window_id}",
        "run: ai-debt review",
        'or ask agent: "Analyze pending AI Debt review"',
    ]
    width = max(len(line) for line in lines)
    border = "+" + "-" * (width + 2) + "+"
    body = [f"| {line.ljust(width)} |" for line in lines]
    return "\n".join([border, *body, border])


def _iso_utc(value: datetime | None) -> str:
    current = value or datetime.now(timezone.utc)
    if current.tzinfo is None:
        current = current.replace(tzinfo=timezone.utc)
    return current.astimezone(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
