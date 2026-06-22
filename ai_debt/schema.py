from __future__ import annotations

import sqlite3
from pathlib import Path


SCHEMA_VERSION = 3


def connect(path: Path) -> sqlite3.Connection:
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def migrate(conn: sqlite3.Connection) -> None:
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS schema_migrations (
          version INTEGER PRIMARY KEY,
          applied_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS sessions (
          id TEXT PRIMARY KEY,
          project_id TEXT,
          source TEXT NOT NULL,
          cwd TEXT,
          transcript_ref TEXT,
          started_at TEXT NOT NULL,
          last_activity_at TEXT NOT NULL,
          ended_at TEXT,
          status TEXT NOT NULL,
          journal_path TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS agent_events (
          id INTEGER PRIMARY KEY AUTOINCREMENT,
          session_id TEXT NOT NULL,
          source TEXT NOT NULL,
          type TEXT NOT NULL,
          turn_id TEXT,
          summary TEXT,
          raw_payload_ref TEXT NOT NULL,
          occurred_at TEXT NOT NULL,
          payload_json TEXT NOT NULL,
          FOREIGN KEY (session_id) REFERENCES sessions(id) ON DELETE CASCADE
        );

        CREATE TABLE IF NOT EXISTS evidence_refs (
          id INTEGER PRIMARY KEY AUTOINCREMENT,
          debt_id TEXT,
          candidate_id TEXT,
          review_window_id TEXT,
          session_id TEXT,
          event_id INTEGER,
          kind TEXT NOT NULL,
          ref TEXT NOT NULL,
          role TEXT,
          created_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS ownership_profiles (
          project_id TEXT PRIMARY KEY,
          payload_json TEXT NOT NULL,
          created_at TEXT NOT NULL,
          updated_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS ownership_review_windows (
          id TEXT PRIMARY KEY,
          session_id TEXT NOT NULL,
          project_id TEXT NOT NULL,
          started_event_id INTEGER,
          ended_event_id INTEGER,
          trigger TEXT NOT NULL,
          status TEXT NOT NULL,
          created_at TEXT NOT NULL,
          updated_at TEXT NOT NULL,
          FOREIGN KEY (session_id) REFERENCES sessions(id) ON DELETE CASCADE
        );

        CREATE TABLE IF NOT EXISTS ownership_gap_candidates (
          id TEXT PRIMARY KEY,
          review_window_id TEXT NOT NULL,
          session_id TEXT NOT NULL,
          project_id TEXT NOT NULL,
          source_agent TEXT NOT NULL,
          title TEXT NOT NULL,
          summary TEXT NOT NULL,
          dimension TEXT NOT NULL,
          priority TEXT NOT NULL,
          status TEXT NOT NULL,
          task_type TEXT NOT NULL,
          task_label TEXT,
          task_confidence REAL NOT NULL DEFAULT 0,
          control_point TEXT NOT NULL,
          gap_type TEXT NOT NULL,
          gap_reason TEXT NOT NULL,
          required_level TEXT NOT NULL,
          current_level TEXT NOT NULL,
          level_gap INTEGER NOT NULL DEFAULT 0,
          repayment_type TEXT NOT NULL,
          repayment_task TEXT NOT NULL,
          payload_json TEXT NOT NULL,
          score_json TEXT NOT NULL DEFAULT '{}',
          evidence_json TEXT NOT NULL DEFAULT '[]',
          repayment_json TEXT NOT NULL DEFAULT '{}',
          knowledge_json TEXT NOT NULL DEFAULT '{}',
          created_at TEXT NOT NULL,
          updated_at TEXT NOT NULL,
          FOREIGN KEY (review_window_id) REFERENCES ownership_review_windows(id) ON DELETE CASCADE,
          FOREIGN KEY (session_id) REFERENCES sessions(id) ON DELETE CASCADE
        );

        CREATE TABLE IF NOT EXISTS ownership_debts (
          id TEXT PRIMARY KEY,
          project_id TEXT NOT NULL,
          source_session_id TEXT NOT NULL,
          source_review_window_id TEXT NOT NULL,
          source_agent TEXT NOT NULL,
          candidate_id TEXT,
          title TEXT NOT NULL,
          summary TEXT NOT NULL,
          dimension TEXT NOT NULL,
          priority TEXT NOT NULL,
          status TEXT NOT NULL,
          seen_count INTEGER NOT NULL DEFAULT 1,
          task_type TEXT NOT NULL,
          task_label TEXT,
          task_confidence REAL NOT NULL DEFAULT 0,
          control_point TEXT NOT NULL,
          gap_type TEXT NOT NULL,
          gap_reason TEXT NOT NULL,
          required_level TEXT NOT NULL,
          current_level TEXT NOT NULL,
          level_gap INTEGER NOT NULL DEFAULT 0,
          repayment_type TEXT NOT NULL,
          repayment_task TEXT NOT NULL,
          payload_json TEXT NOT NULL,
          score_json TEXT NOT NULL DEFAULT '{}',
          evidence_json TEXT NOT NULL DEFAULT '[]',
          repayment_json TEXT NOT NULL DEFAULT '{}',
          knowledge_json TEXT NOT NULL DEFAULT '{}',
          feedback_json TEXT NOT NULL DEFAULT '{}',
          created_at TEXT NOT NULL,
          updated_at TEXT NOT NULL,
          resolved_at TEXT,
          FOREIGN KEY (source_session_id) REFERENCES sessions(id) ON DELETE CASCADE,
          FOREIGN KEY (source_review_window_id) REFERENCES ownership_review_windows(id) ON DELETE CASCADE
        );

        CREATE TABLE IF NOT EXISTS ownership_concepts (
          id INTEGER PRIMARY KEY AUTOINCREMENT,
          debt_id TEXT NOT NULL,
          project_id TEXT NOT NULL,
          concept TEXT NOT NULL,
          familiarity TEXT,
          minimum_mastery_level TEXT,
          status TEXT NOT NULL,
          created_at TEXT NOT NULL,
          updated_at TEXT NOT NULL,
          FOREIGN KEY (debt_id) REFERENCES ownership_debts(id) ON DELETE CASCADE
        );

        CREATE TABLE IF NOT EXISTS review_actions (
          id INTEGER PRIMARY KEY AUTOINCREMENT,
          candidate_id TEXT,
          debt_id TEXT,
          action TEXT NOT NULL,
          created_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS grasp_checks (
          id INTEGER PRIMARY KEY AUTOINCREMENT,
          debt_id TEXT NOT NULL,
          prompt TEXT,
          answer TEXT,
          result TEXT,
          agent_assessment_json TEXT,
          user_override TEXT,
          skipped INTEGER NOT NULL DEFAULT 0,
          created_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS companion_notifications (
          id INTEGER PRIMARY KEY AUTOINCREMENT,
          session_id TEXT NOT NULL,
          event_type TEXT NOT NULL,
          notified_at TEXT NOT NULL,
          UNIQUE(session_id, event_type),
          FOREIGN KEY (session_id) REFERENCES sessions(id) ON DELETE CASCADE
        );

        """
    )
    _add_column(conn, "sessions", "project_id", "TEXT")
    _add_column(conn, "evidence_refs", "review_window_id", "TEXT")
    _add_column(conn, "evidence_refs", "role", "TEXT")
    _add_column(conn, "grasp_checks", "agent_assessment_json", "TEXT")
    _add_column(conn, "grasp_checks", "user_override", "TEXT")
    conn.execute(
        "INSERT OR IGNORE INTO schema_migrations(version, applied_at) VALUES (?, datetime('now'))",
        (SCHEMA_VERSION,),
    )
    conn.commit()


def _add_column(conn: sqlite3.Connection, table: str, column: str, definition: str) -> None:
    columns = {row["name"] for row in conn.execute(f"PRAGMA table_info({table})").fetchall()}
    if column not in columns:
        conn.execute(f"ALTER TABLE {table} ADD COLUMN {column} {definition}")
