from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any, BinaryIO

from .config import load_config
from .core import capture_payload, initialize
from .maintenance import cleanup_raw_payloads, delete_debt, delete_session, export_task_control_report
from .ownership import (
    build_ownership_review_input,
    create_ownership_candidates,
    get_or_create_profile,
    learn_one,
    list_ownership_debts,
    parse_ownership_analysis,
    project_id_for_cwd,
    record_check,
    review_ownership_gap,
    select_pending_review_window,
    task_control_report,
    update_profile,
)
from .paths import db_path, state_home
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
            return _response(request_id, _tool_result(call_tool(name, arguments)))
        if method == "resources/list":
            return _response(request_id, {"resources": list_resources()})
        if method == "resources/templates/list":
            return _response(request_id, {"resourceTemplates": list_resource_templates()})
        if method == "resources/read":
            params = _object(message.get("params"), "params")
            uri = _string(params.get("uri"), "uri")
            return _response(request_id, _resource_result(uri, read_resource(uri)))
        return _error(request_id, -32601, f"Unknown method: {method}")
    except Exception as exc:
        return _error(request_id, -32000, str(exc))


def list_tools() -> list[dict[str, Any]]:
    return [
        _tool("record_event", "Capture one raw agent hook payload.", {"adapter": _string_schema(), "payload": _object_schema()}, ["adapter", "payload"]),
        _tool("get_status", "Return AI Debt state counts and recent sessions.", {}, []),
        _tool("list_sessions", "List recent sessions, optionally filtered by status.", {"limit": _integer_schema(), "status": _string_schema()}, []),
        _tool("get_pending_review_window", "Return the next pending ownership review window.", {"review_window_id": _string_schema()}, []),
        _tool("get_ownership_profile", "Return a project ownership profile.", {"project_id": _string_schema(), "cwd": _string_schema()}, []),
        _tool("update_ownership_profile", "Patch a project ownership profile.", {"project_id": _string_schema(), "cwd": _string_schema(), "patch": _object_schema()}, ["patch"]),
        _tool("get_ownership_review_input", "Return a window-scoped ownership review input package.", {"review_window_id": _string_schema()}, []),
        _tool("submit_ownership_analysis", "Submit structured ownership analysis and create candidates.", {"review_window_id": _string_schema(), "analysis": _object_schema()}, ["review_window_id", "analysis"]),
        _tool("review_ownership_gap", "Apply accept, ignore, already_know, or defer to an ownership candidate.", {"candidate_id": _string_schema(), "action": _string_schema()}, ["candidate_id", "action"]),
        _tool("list_ownership_debts", "List accepted ownership debts.", {"project_id": _string_schema(), "status": _string_schema()}, []),
        _tool("learn_one", "Return one ownership recovery task for a candidate or debt.", {"item_id": _string_schema()}, []),
        _tool("check", "Record an ownership recovery check.", {"debt_id": _string_schema(), "answer": _string_schema(), "agent_assessment": _object_schema(), "user_override": _string_schema(), "skip": {"type": "boolean"}}, ["debt_id"]),
        _tool("export_task_control_report", "Return a task control report as JSON and Markdown.", {"review_window_id": _string_schema(), "write_file": {"type": "boolean"}}, ["review_window_id"]),
        _tool("cleanup", "Clean up expired raw payloads.", {"dry_run": {"type": "boolean"}}, []),
        _tool("delete_item", "Delete a session or ownership debt.", {"target": _string_schema(), "id": _string_schema()}, ["target", "id"]),
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
        return {"sessions": _sessions(int(arguments.get("limit") or 10), _optional_string(arguments.get("status")))}
    if name == "get_pending_review_window":
        return get_pending_review_window(_optional_string(arguments.get("review_window_id")))
    if name == "get_ownership_profile":
        return get_profile(_optional_string(arguments.get("project_id")), _optional_string(arguments.get("cwd")))
    if name == "update_ownership_profile":
        return patch_profile(_optional_string(arguments.get("project_id")), _optional_string(arguments.get("cwd")), _object(arguments.get("patch"), "patch"))
    if name == "get_ownership_review_input":
        return get_ownership_review_input(_optional_string(arguments.get("review_window_id")))
    if name == "submit_ownership_analysis":
        review_window_id = _string(arguments.get("review_window_id"), "review_window_id")
        analysis = _object(arguments.get("analysis"), "analysis")
        return submit_ownership_analysis(review_window_id, analysis)
    if name == "review_ownership_gap":
        return ownership_gap_action(_string(arguments.get("candidate_id"), "candidate_id"), _string(arguments.get("action"), "action"))
    if name == "list_ownership_debts":
        return {"items": ownership_debts(_optional_string(arguments.get("project_id")), _optional_string(arguments.get("status")))}
    if name == "learn_one":
        return learn_one_item(_optional_string(arguments.get("item_id")))
    if name == "check":
        return check_item(
            _string(arguments.get("debt_id"), "debt_id"),
            _optional_string(arguments.get("answer")),
            arguments.get("agent_assessment") if isinstance(arguments.get("agent_assessment"), dict) else None,
            _optional_string(arguments.get("user_override")),
            bool(arguments.get("skip", False)),
        )
    if name == "export_task_control_report":
        return export_report(_string(arguments.get("review_window_id"), "review_window_id"), bool(arguments.get("write_file", False)))
    if name == "cleanup":
        return cleanup(bool(arguments.get("dry_run", False)))
    if name == "delete_item":
        return delete_item(_string(arguments.get("target"), "target"), _string(arguments.get("id"), "id"))
    raise ValueError(f"Unknown tool: {name}")


def list_resources() -> list[dict[str, str]]:
    return [
        {"uri": "ai-debt://status", "name": "AI Debt status", "description": "Current state counts and recent sessions.", "mimeType": "application/json"},
        {"uri": "ai-debt://sessions/recent", "name": "Recent sessions", "description": "Recent AI Debt sessions.", "mimeType": "application/json"},
        {"uri": "ai-debt://ownership/debts", "name": "Ownership debts", "description": "Accepted ownership debts.", "mimeType": "application/json"},
    ]


def list_resource_templates() -> list[dict[str, str]]:
    return [
        {"uriTemplate": "ai-debt://ownership/windows/{review_window_id}/review-input", "name": "Ownership review input", "description": "Window-scoped ownership review input.", "mimeType": "application/json"},
        {"uriTemplate": "ai-debt://ownership/windows/{review_window_id}/task-control-report", "name": "Task control report", "description": "Task control report for one review window.", "mimeType": "application/json"},
        {"uriTemplate": "ai-debt://ownership/profiles/{project_id}", "name": "Ownership profile", "description": "Project ownership profile.", "mimeType": "application/json"},
    ]


def read_resource(uri: str) -> dict[str, Any]:
    if uri == "ai-debt://status":
        return get_status()
    if uri == "ai-debt://sessions/recent":
        return {"sessions": _sessions(10, None)}
    if uri == "ai-debt://ownership/debts":
        return {"items": ownership_debts(None, None)}
    review_prefix = "ai-debt://ownership/windows/"
    if uri.startswith(review_prefix) and uri.endswith("/review-input"):
        window_id = uri[len(review_prefix) : -len("/review-input")]
        return get_ownership_review_input(window_id)
    if uri.startswith(review_prefix) and uri.endswith("/task-control-report"):
        window_id = uri[len(review_prefix) : -len("/task-control-report")]
        return export_report(window_id, False)
    profile_prefix = "ai-debt://ownership/profiles/"
    if uri.startswith(profile_prefix):
        return get_profile(uri[len(profile_prefix) :], None)
    raise ValueError(f"Unknown resource: {uri}")


def get_status() -> dict[str, Any]:
    initialize()
    conn = connect(db_path())
    try:
        migrate(conn)
        refresh_session_states(conn, load_config())
        counts = status_counts(conn)
        sessions = [dict(row) for row in recent_sessions(conn)]
    finally:
        conn.close()
    return {"state_home": str(state_home()), "counts": counts, "recent_sessions": sessions}


def get_pending_review_window(review_window_id: str | None = None) -> dict[str, Any]:
    initialize()
    conn = connect(db_path())
    try:
        window = select_pending_review_window(conn, review_window_id)
        return {"review_window": dict(window) if window else None}
    finally:
        conn.close()


def get_profile(project_id: str | None, cwd: str | None) -> dict[str, Any]:
    initialize()
    resolved = project_id or project_id_for_cwd(cwd)
    conn = connect(db_path())
    try:
        return {"profile": get_or_create_profile(conn, resolved)}
    finally:
        conn.close()


def patch_profile(project_id: str | None, cwd: str | None, patch: dict[str, Any]) -> dict[str, Any]:
    initialize()
    resolved = project_id or project_id_for_cwd(cwd)
    conn = connect(db_path())
    try:
        return {"profile": update_profile(conn, resolved, patch)}
    finally:
        conn.close()


def get_ownership_review_input(review_window_id: str | None = None) -> dict[str, Any]:
    initialize()
    conn = connect(db_path())
    try:
        return build_ownership_review_input(conn, review_window_id)
    finally:
        conn.close()


def submit_ownership_analysis(review_window_id: str, analysis: dict[str, Any]) -> dict[str, Any]:
    initialize()
    parsed = parse_ownership_analysis(json.dumps(analysis, ensure_ascii=False))
    conn = connect(db_path())
    try:
        return {"created": create_ownership_candidates(conn, review_window_id, parsed)}
    finally:
        conn.close()


def ownership_gap_action(candidate_id: str, action: str) -> dict[str, Any]:
    initialize()
    conn = connect(db_path())
    try:
        debt_id = review_ownership_gap(conn, candidate_id, action)
    finally:
        conn.close()
    return {"candidate_id": candidate_id, "action": action, "debt_id": debt_id}


def ownership_debts(project_id: str | None, status: str | None) -> list[dict[str, Any]]:
    initialize()
    conn = connect(db_path())
    try:
        return [dict(row) for row in list_ownership_debts(conn, project_id, status)]
    finally:
        conn.close()


def learn_one_item(item_id: str | None = None) -> dict[str, Any]:
    initialize()
    conn = connect(db_path())
    try:
        return learn_one(conn, item_id)
    finally:
        conn.close()


def check_item(debt_id: str, answer: str | None, agent_assessment: dict[str, Any] | None, user_override: str | None, skip: bool) -> dict[str, str]:
    initialize()
    conn = connect(db_path())
    try:
        result = record_check(conn, debt_id, answer, agent_assessment, user_override, skipped=skip)
    finally:
        conn.close()
    return {"result": result}


def export_report(review_window_id: str, write_file: bool) -> dict[str, Any]:
    initialize()
    conn = connect(db_path())
    try:
        return task_control_report(conn, review_window_id, write_file=write_file)
    finally:
        conn.close()


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


def _initialize_result() -> dict[str, Any]:
    return {
        "protocolVersion": PROTOCOL_VERSION,
        "capabilities": {"tools": {}, "resources": {}},
        "serverInfo": {"name": SERVER_NAME, "version": "0.1.0"},
    }


def _tool(name: str, description: str, properties: dict[str, Any], required: list[str]) -> dict[str, Any]:
    return {"name": name, "description": description, "inputSchema": {"type": "object", "properties": properties, "required": required}}


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


def _optional_string(value: Any) -> str | None:
    if value is None or value == "":
        return None
    return str(value)


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


if __name__ == "__main__":
    raise SystemExit(main())
