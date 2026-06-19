from __future__ import annotations

import sqlite3
from pathlib import Path


SCHEMA_VERSION = 1


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
          session_id TEXT,
          event_id INTEGER,
          kind TEXT NOT NULL,
          ref TEXT NOT NULL,
          created_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS debt_candidates (
          id TEXT PRIMARY KEY,
          session_id TEXT NOT NULL,
          source_agent TEXT NOT NULL,
          concept TEXT NOT NULL,
          debt_dimension TEXT NOT NULL,
          why_it_matters TEXT NOT NULL,
          priority TEXT NOT NULL,
          status TEXT NOT NULL,
          payload_json TEXT NOT NULL,
          created_at TEXT NOT NULL,
          FOREIGN KEY (session_id) REFERENCES sessions(id) ON DELETE CASCADE
        );

        CREATE TABLE IF NOT EXISTS cognitive_debts (
          id TEXT PRIMARY KEY,
          concept TEXT NOT NULL,
          debt_dimension TEXT NOT NULL,
          source_session_id TEXT NOT NULL,
          source_agent TEXT NOT NULL,
          why_it_matters TEXT NOT NULL,
          priority TEXT NOT NULL,
          status TEXT NOT NULL,
          seen_count INTEGER NOT NULL DEFAULT 1,
          created_at TEXT NOT NULL,
          updated_at TEXT NOT NULL,
          resolved_at TEXT
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
          skipped INTEGER NOT NULL DEFAULT 0,
          created_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS inbox_items (
          id INTEGER PRIMARY KEY AUTOINCREMENT,
          debt_id TEXT NOT NULL,
          status TEXT NOT NULL,
          priority TEXT NOT NULL,
          next_review_at TEXT,
          created_at TEXT NOT NULL
        );
        """
    )
    conn.execute(
        "INSERT OR IGNORE INTO schema_migrations(version, applied_at) VALUES (?, datetime('now'))",
        (SCHEMA_VERSION,),
    )
    conn.commit()
