from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from uuid import uuid4


def now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def first_value(payload: dict[str, Any], *keys: str, default: Any = None) -> Any:
    for key in keys:
        value = payload
        found = True
        for part in key.split("."):
            if isinstance(value, dict) and part in value:
                value = value[part]
            else:
                found = False
                break
        if found and value not in (None, ""):
            return value
    return default


def event_name(payload: dict[str, Any]) -> str:
    return str(first_value(payload, "hook_event_name", "event", "type", "name", default="")).lower()


def session_id(payload: dict[str, Any]) -> str:
    return str(first_value(payload, "session_id", "session.id", "conversation_id", "id", default=f"session-{uuid4()}"))


def turn_id(payload: dict[str, Any]) -> str | None:
    value = first_value(payload, "turn_id", "turn.id", "message_id")
    return str(value) if value is not None else None


def occurred_at(payload: dict[str, Any]) -> str:
    return str(first_value(payload, "occurred_at", "timestamp", "created_at", default=now_iso()))


def cwd(payload: dict[str, Any]) -> str:
    return str(first_value(payload, "cwd", "workspace.cwd", "project_path", default="."))


def transcript_ref(payload: dict[str, Any]) -> str | None:
    value = first_value(payload, "transcript_ref", "transcript_path", "transcript.path")
    return str(value) if value is not None else None


def summarize(value: Any, limit: int = 240) -> str:
    if value is None:
        return ""
    text = " ".join(str(value).split())
    if len(text) <= limit:
        return text
    return text[: limit - 1] + "..."


def files_from_payload(payload: dict[str, Any]) -> list[str]:
    candidates = first_value(payload, "files", "tool.files", "tool_input.files", "changed_files", default=[])
    if isinstance(candidates, str):
        return [candidates]
    if isinstance(candidates, list):
        return [str(item) for item in candidates]
    return []
