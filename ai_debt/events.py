from __future__ import annotations

from typing import Any, Literal, TypedDict


AgentSource = Literal["claude_code", "codex"]
AgentEventType = Literal[
    "session_started",
    "user_prompt_submitted",
    "tool_used",
    "assistant_stopped",
    "session_ended",
]


class AgentEvent(TypedDict, total=False):
    type: AgentEventType
    source: AgentSource
    session_id: str
    cwd: str
    transcript_ref: str
    turn_id: str
    prompt_summary: str
    tool_name: str
    files: list[str]
    tool_summary: str
    last_message_summary: str
    raw_payload_ref: str
    occurred_at: str


VALID_EVENT_TYPES = {
    "session_started",
    "user_prompt_submitted",
    "tool_used",
    "assistant_stopped",
    "session_ended",
}


def validate_event(event: dict[str, Any]) -> AgentEvent:
    required = {"type", "source", "session_id", "raw_payload_ref", "occurred_at"}
    missing = sorted(required - event.keys())
    if missing:
        raise ValueError(f"AgentEvent missing required fields: {', '.join(missing)}")
    if event["type"] not in VALID_EVENT_TYPES:
        raise ValueError(f"Unsupported AgentEvent type: {event['type']}")
    if event["source"] not in {"claude_code", "codex"}:
        raise ValueError(f"Unsupported AgentEvent source: {event['source']}")
    if event["type"] == "tool_used" and not event.get("tool_name"):
        raise ValueError("tool_used event requires tool_name")
    if event["type"] == "session_started" and "cwd" not in event:
        raise ValueError("session_started event requires cwd")
    return event  # type: ignore[return-value]


def event_summary(event: AgentEvent) -> str:
    event_type = event["type"]
    if event_type == "user_prompt_submitted":
        return event.get("prompt_summary", "")
    if event_type == "tool_used":
        return event.get("tool_summary") or event.get("tool_name", "")
    if event_type == "assistant_stopped":
        return event.get("last_message_summary", "")
    return event_type
