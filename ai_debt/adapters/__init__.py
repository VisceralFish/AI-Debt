from __future__ import annotations

from typing import Any

from .claude_code import normalize_claude_code_payload
from .codex import normalize_codex_payload


def normalize_payload(adapter: str, payload: dict[str, Any], raw_payload_ref: str) -> dict[str, Any]:
    if adapter == "claude-code":
        return normalize_claude_code_payload(payload, raw_payload_ref)
    if adapter == "codex":
        return normalize_codex_payload(payload, raw_payload_ref)
    raise ValueError(f"Unsupported adapter: {adapter}")
