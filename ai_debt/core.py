from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .adapters import normalize_payload
from .config import load_config
from .events import validate_event
from .journal import append_event, write_raw_payload
from .maintenance import recover_from_journals
from .paths import db_path, ensure_layout
from .schema import connect, migrate
from .store import record_event, refresh_session_states


def initialize(home: Path | None = None) -> None:
    root = ensure_layout(home)
    from .config import default_config, save_config

    config_file = root / "config.yaml"
    if not config_file.exists():
        save_config(default_config(), root)
    conn = connect(db_path(root))
    try:
        migrate(conn)
        recover_from_journals(conn, load_config(root), root)
    finally:
        conn.close()


def capture_payload(adapter: str, payload: dict[str, Any], home: Path | None = None) -> dict[str, Any]:
    initialize(home)
    raw_payload_ref = write_raw_payload(_payload_session_id(payload), payload, home)
    event = validate_event(normalize_payload(adapter, payload, raw_payload_ref))
    if event["session_id"] != _payload_session_id(payload):
        Path(raw_payload_ref).unlink(missing_ok=True)
        raw_payload_ref = write_raw_payload(event["session_id"], payload, home)
        event["raw_payload_ref"] = raw_payload_ref

    append_event(event, home)
    conn = connect(db_path(home))
    try:
        migrate(conn)
        record_event(conn, event, home)
        refresh_session_states(conn, load_config(home))
    finally:
        conn.close()
    return event


def read_json_stdin(text: str) -> dict[str, Any]:
    try:
        value = json.loads(text)
    except json.JSONDecodeError as exc:
        raise ValueError(f"Invalid JSON hook payload: {exc}") from exc
    if not isinstance(value, dict):
        raise ValueError("Hook payload must be a JSON object")
    return value


def _payload_session_id(payload: dict[str, Any]) -> str:
    for key in ("session_id", "conversation_id", "id"):
        if payload.get(key):
            return str(payload[key])
    session = payload.get("session")
    if isinstance(session, dict) and session.get("id"):
        return str(session["id"])
    return "unknown-session"
