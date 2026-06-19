from __future__ import annotations

from typing import Any

from .common import (
    cwd,
    event_name,
    files_from_payload,
    first_value,
    occurred_at,
    session_id,
    summarize,
    transcript_ref,
    turn_id,
)


def normalize_codex_payload(payload: dict[str, Any], raw_payload_ref: str) -> dict[str, Any]:
    name = event_name(payload)
    base = {
        "source": "codex",
        "session_id": session_id(payload),
        "turn_id": turn_id(payload),
        "raw_payload_ref": raw_payload_ref,
        "occurred_at": occurred_at(payload),
    }
    if name in {"sessionstart", "session_start", "session_started"}:
        return {
            **base,
            "type": "session_started",
            "cwd": cwd(payload),
            "transcript_ref": transcript_ref(payload),
        }
    if name in {"userpromptsubmit", "user_prompt_submit", "user_prompt_submitted", "prompt"}:
        return {
            **base,
            "type": "user_prompt_submitted",
            "prompt_summary": summarize(first_value(payload, "prompt", "message", "input")),
        }
    if name in {"posttooluse", "tool_used", "tool_use", "tool"}:
        tool_name = first_value(payload, "tool_name", "tool.name", "name", default="unknown")
        return {
            **base,
            "type": "tool_used",
            "tool_name": str(tool_name),
            "files": files_from_payload(payload),
            "tool_summary": summarize(first_value(payload, "tool_summary", "summary", "tool_input", "tool")),
        }
    if name in {"stop", "assistant_stopped"}:
        return {
            **base,
            "type": "assistant_stopped",
            "last_message_summary": summarize(first_value(payload, "last_message", "message", "response")),
        }
    if name in {"sessionend", "session_end", "session_ended"}:
        return {**base, "type": "session_ended"}
    raise ValueError(f"Unsupported Codex hook event: {name}")
