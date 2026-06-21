from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any, BinaryIO, TextIO

from .config import load_config
from .core import capture_payload, initialize
from .maintenance import cleanup_raw_payloads, delete_debt, delete_session, export_deep_review
from .paths import db_path, state_home
from .review import (
    apply_review_action,
    build_review_input,
    create_candidates,
    learn_one,
    list_inbox,
    parse_analysis,
    record_grasp_check,
    select_review_session,
)
from .schema import connect, migrate
from .store import list_sessions as query_sessions
from .store import recent_sessions, refresh_session_states, status_counts


SERVER_NAME = "ai-debt"
PROTOCOL_VERSION = "2024-11-05"


def main() -> int:
    return serve_stdio(sys.stdin.buffer, sys.stdout.buffer)


def serve_stdio(stdin: BinaryIO, stdout: BinaryIO) -> int:
    while True:
        message = _read_message(stdin)
        if message is None:
            return 0
        response = handle_jsonrpc(message)
        if response is not None:
            _write_message(stdout, response)


def handle_jsonrpc(message: dict[str, Any]) -> dict[str, Any] | None:
    method = message.get("method")
    request_id = message.get("id")
    try:
        if method == "initialize":
            return _response(request_id, _initialize_result())
        if method == "notifications/initialized":
            return None
        if method == "tools/list":
            return _response(request_id, {"tools": list_tools()})
        if method == "tools/call":
            params = _object(message.get("params"), "params")
            name = _string(params.get("name"), "name")
            arguments = _object(params.get("arguments", {}), "arguments")
            result = call_tool(name, arguments)
            return _response(request_id, _tool_result(result))
        if method == "resources/list":
            return _response(request_id, {"resources": list_resources()})
        if method == "resources/templates/list":
            return _response(request_id, {"resourceTemplates": list_resource_templates()})
        if method == "resources/read":
            params = _object(message.get("params"), "params")
            uri = _string(params.get("uri"), "uri")
            data = read_resource(uri)
            return _response(request_id, _resource_result(uri, data))
        return _error(request_id, -32601, f"Unknown method: {method}")
    except Exception as exc:
        return _error(request_id, -32000, str(exc))


def list_tools() -> list[dict[str, Any]]:
    return [
        _tool("record_event", "Capture one raw agent hook payload.", {"adapter": _string_schema(), "payload": _object_schema()}, ["adapter", "payload"]),
        _tool("get_status", "Return AI Debt state counts and recent sessions.", {}, []),
        _tool("list_sessions", "List recent sessions, optionally filtered by status.", {"limit": _integer_schema(), "status": _string_schema()}, []),
        _tool("get_review_input", "Return the review input package for a session.", {"session_id": _string_schema()}, []),
        _tool("submit_analysis", "Submit structured review analysis and create candidates.", {"session_id": _string_schema(), "analysis": _object_schema()}, ["session_id", "analysis"]),
        _tool("review_action", "Apply accept, skip, or already_know to a candidate.", {"candidate_id": _string_schema(), "action": _string_schema()}, ["candidate_id", "action"]),
        _tool("list_inbox", "List unresolved learning inbox items.", {}, []),
        _tool("learn_one", "Return one L2 learning item for a candidate or debt.", {"item_id": _string_schema()}, []),
        _tool("check", "Record a grasp check answer or skip.", {"debt_id": _string_schema(), "answer": _string_schema(), "skip": {"type": "boolean"}}, ["debt_id"]),
        _tool("export_deep_review", "Export a deep review Markdown artifact.", {"session_id": _string_schema()}, []),
        _tool("cleanup", "Clean up expired raw payloads.", {"dry_run": {"type": "boolean"}}, []),
        _tool("delete_item", "Delete a session or debt.", {"target": _string_schema(), "id": _string_schema()}, ["target", "id"]),
    ]


def call_tool(name: str, arguments: dict[str, Any]) -> dict[str, Any]:
    if name == "record_event":
        adapter = _string(arguments.get("adapter"), "adapter")
        payload = _object(arguments.get("payload"), "payload")
        if adapter not in {"claude-code", "codex"}:
            raise ValueError("adapter must be claude-code or codex")
        event = capture_payload(adapter, payload)
        return {"event": event, "status_line": "event captured"}
    if name == "get_status":
        return get_status()
    if name == "list_sessions":
        limit = int(arguments.get("limit") or 10)
        status = arguments.get("status")
        return {"sessions": _sessions(limit, str(status) if status else None)}
    if name == "get_review_input":
        return get_review_input(arguments.get("session_id"))
    if name == "submit_analysis":
        session_id = _string(arguments.get("session_id"), "session_id")
        analysis = _object(arguments.get("analysis"), "analysis")
        return submit_analysis(session_id, analysis)
    if name == "review_action":
        candidate_id = _string(arguments.get("candidate_id"), "candidate_id")
        action = _string(arguments.get("action"), "action")
        return review_action(candidate_id, action)
    if name == "list_inbox":
        return {"items": inbox_items()}
    if name == "learn_one":
        item_id = arguments.get("item_id")
        return learn_one_item(str(item_id) if item_id else None)
    if name == "check":
        debt_id = _string(arguments.get("debt_id"), "debt_id")
        answer = arguments.get("answer")
        skip = bool(arguments.get("skip", False))
        return check_item(debt_id, str(answer) if answer is not None else None, skip)
    if name == "export_deep_review":
        session_id = arguments.get("session_id")
        return export_review(str(session_id) if session_id else None)
    if name == "cleanup":
        return cleanup(bool(arguments.get("dry_run", False)))
    if name == "delete_item":
        target = _string(arguments.get("target"), "target")
        item_id = _string(arguments.get("id"), "id")
        return delete_item(target, item_id)
    raise ValueError(f"Unknown tool: {name}")


def list_resources() -> list[dict[str, str]]:
    return [
        {"uri": "ai-debt://status", "name": "AI Debt status", "description": "Current state counts and recent sessions.", "mimeType": "application/json"},
        {"uri": "ai-debt://sessions/recent", "name": "Recent sessions", "description": "Recent AI Debt sessions.", "mimeType": "application/json"},
        {"uri": "ai-debt://inbox", "name": "Learning inbox", "description": "Open cognitive debt inbox items.", "mimeType": "application/json"},
    ]


def list_resource_templates() -> list[dict[str, str]]:
    return [
        {
            "uriTemplate": "ai-debt://sessions/{session_id}/review-input",
            "name": "Session review input",
            "description": "Review input package for one AI Debt session.",
            "mimeType": "application/json",
        },
        {
            "uriTemplate": "ai-debt://exports/deep-review/{session_id}",
            "name": "Deep review export",
            "description": "Existing deep review Markdown export for one session.",
            "mimeType": "application/json",
        },
    ]


def read_resource(uri: str) -> dict[str, Any]:
    if uri == "ai-debt://status":
        return get_status()
    if uri == "ai-debt://sessions/recent":
        return {"sessions": _sessions(10, None)}
    if uri == "ai-debt://inbox":
        return {"items": inbox_items()}
    prefix = "ai-debt://sessions/"
    suffix = "/review-input"
    if uri.startswith(prefix) and uri.endswith(suffix):
        session_id = uri[len(prefix) : -len(suffix)]
        return get_review_input(session_id)
    export_prefix = "ai-debt://exports/deep-review/"
    if uri.startswith(export_prefix):
        session_id = uri[len(export_prefix) :]
        return _read_export(session_id)
    raise ValueError(f"Unknown resource: {uri}")


def get_status() -> dict[str, Any]:
    initialize()
    config = load_config()
    conn = connect(db_path())
    try:
        migrate(conn)
        refresh_session_states(conn, config)
        counts = status_counts(conn)
        sessions = [dict(row) for row in recent_sessions(conn)]
    finally:
        conn.close()
    return {"state_home": str(state_home()), "counts": counts, "recent_sessions": sessions}


def get_review_input(session_id: Any = None) -> dict[str, Any]:
    initialize()
    conn = connect(db_path())
    try:
        session = select_review_session(conn, str(session_id) if session_id else None)
        if session is None:
            raise ValueError("No session ready for review")
        return build_review_input(conn, session["id"])
    finally:
        conn.close()


def submit_analysis(session_id: str, analysis: dict[str, Any]) -> dict[str, Any]:
    initialize()
    parsed = parse_analysis(json.dumps(analysis, ensure_ascii=False))
    conn = connect(db_path())
    try:
        created = create_candidates(conn, session_id, parsed)
    finally:
        conn.close()
    return {"created": created}


def review_action(candidate_id: str, action: str) -> dict[str, Any]:
    initialize()
    conn = connect(db_path())
    try:
        debt_id = apply_review_action(conn, candidate_id, action)
    finally:
        conn.close()
    return {"candidate_id": candidate_id, "action": action, "debt_id": debt_id}


def inbox_items() -> list[dict[str, Any]]:
    initialize()
    conn = connect(db_path())
    try:
        return [dict(row) for row in list_inbox(conn)]
    finally:
        conn.close()


def learn_one_item(item_id: str | None = None) -> dict[str, str]:
    initialize()
    conn = connect(db_path())
    try:
        return learn_one(conn, item_id)
    finally:
        conn.close()


def check_item(debt_id: str, answer: str | None, skip: bool) -> dict[str, str]:
    initialize()
    conn = connect(db_path())
    try:
        result = record_grasp_check(conn, debt_id, answer, skipped=skip)
    finally:
        conn.close()
    return {"result": result}


def export_review(session_id: str | None = None) -> dict[str, str]:
    initialize()
    conn = connect(db_path())
    try:
        path = export_deep_review(conn, session_id)
    finally:
        conn.close()
    return {"path": str(path)}


def cleanup(dry_run: bool = False) -> dict[str, list[str]]:
    initialize()
    result = cleanup_raw_payloads(load_config(), dry_run=dry_run)
    return {"raw_payloads": [str(path) for path in result.raw_payloads]}


def delete_item(target: str, item_id: str) -> dict[str, bool]:
    initialize()
    conn = connect(db_path())
    try:
        if target == "session":
            delete_session(conn, item_id)
        elif target == "debt":
            delete_debt(conn, item_id)
        else:
            raise ValueError("target must be session or debt")
    finally:
        conn.close()
    return {"deleted": True}


def _sessions(limit: int, status: str | None) -> list[dict[str, Any]]:
    initialize()
    conn = connect(db_path())
    try:
        refresh_session_states(conn, load_config())
        return [dict(row) for row in query_sessions(conn, limit, status)]
    finally:
        conn.close()


def _read_export(session_id: str) -> dict[str, str]:
    path = state_home() / "exports" / "deep_review" / f"deep_review_{_safe_name(session_id)}.md"
    if not path.exists():
        raise ValueError(f"Deep review export not found: {session_id}")
    return {"path": str(path), "content": path.read_text(encoding="utf-8")}


def _initialize_result() -> dict[str, Any]:
    return {
        "protocolVersion": PROTOCOL_VERSION,
        "capabilities": {"tools": {}, "resources": {}},
        "serverInfo": {"name": SERVER_NAME, "version": "0.1.0"},
    }


def _tool(name: str, description: str, properties: dict[str, Any], required: list[str]) -> dict[str, Any]:
    return {
        "name": name,
        "description": description,
        "inputSchema": {"type": "object", "properties": properties, "required": required},
    }


def _tool_result(result: dict[str, Any]) -> dict[str, Any]:
    return {
        "content": [{"type": "text", "text": json.dumps(_jsonable(result), ensure_ascii=False, indent=2)}],
        "structuredContent": _jsonable(result),
        "isError": False,
    }


def _resource_result(uri: str, data: dict[str, Any]) -> dict[str, Any]:
    return {
        "contents": [
            {
                "uri": uri,
                "mimeType": "application/json",
                "text": json.dumps(_jsonable(data), ensure_ascii=False, indent=2),
            }
        ]
    }


def _response(request_id: Any, result: dict[str, Any]) -> dict[str, Any]:
    return {"jsonrpc": "2.0", "id": request_id, "result": result}


def _error(request_id: Any, code: int, message: str) -> dict[str, Any]:
    return {"jsonrpc": "2.0", "id": request_id, "error": {"code": code, "message": message}}


def _read_message(stdin: BinaryIO) -> dict[str, Any] | None:
    first = stdin.readline()
    if not first:
        return None
    if first.startswith(b"Content-Length:"):
        length = int(first.split(b":", 1)[1].strip())
        while True:
            line = stdin.readline()
            if line in {b"\r\n", b"\n", b""}:
                break
        payload = stdin.read(length)
        return json.loads(payload.decode("utf-8"))
    return json.loads(first.decode("utf-8"))


def _write_message(stdout: BinaryIO, message: dict[str, Any]) -> None:
    payload = json.dumps(message, ensure_ascii=False).encode("utf-8")
    stdout.write(f"Content-Length: {len(payload)}\r\n\r\n".encode("ascii"))
    stdout.write(payload)
    stdout.flush()


def _object(value: Any, name: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ValueError(f"{name} must be an object")
    return value


def _string(value: Any, name: str) -> str:
    if not isinstance(value, str) or not value:
        raise ValueError(f"{name} must be a non-empty string")
    return value


def _object_schema() -> dict[str, str]:
    return {"type": "object"}


def _string_schema() -> dict[str, str]:
    return {"type": "string"}


def _integer_schema() -> dict[str, str]:
    return {"type": "integer"}


def _jsonable(value: Any) -> Any:
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, dict):
        return {key: _jsonable(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_jsonable(item) for item in value]
    return value


def _safe_name(value: str) -> str:
    return "".join(char if char.isalnum() or char in {"-", "_", "."} else "_" for char in value)


if __name__ == "__main__":
    raise SystemExit(main())
