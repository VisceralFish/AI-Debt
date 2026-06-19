from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from .config import load_config, mark_adapter
from .core import capture_payload, initialize, read_json_stdin
from .hooks import write_hook_script
from .journal import utc_now
from .paths import config_path, db_path, hooks_path, journals_path, logs_path, state_home
from .maintenance import (
    cleanup_raw_payloads,
    delete_debt,
    delete_session,
    export_deep_review,
    last_hook_event,
    raw_payload_cleanup_summary,
    schema_is_valid,
)
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
from .store import recent_sessions, refresh_session_states, status_counts


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="ai-debt")
    subparsers = parser.add_subparsers(dest="command", required=True)

    init_parser = subparsers.add_parser("init")
    init_parser.add_argument("adapter", nargs="?", choices=["claude-code", "codex"])

    subparsers.add_parser("status")
    subparsers.add_parser("doctor")

    hook_parser = subparsers.add_parser("hook")
    hook_parser.add_argument("adapter", choices=["claude-code", "codex"])

    review_parser = subparsers.add_parser("review")
    review_parser.add_argument("session_id", nargs="?")
    review_parser.add_argument("--analysis-file")
    review_parser.add_argument("--action", choices=["accept", "skip", "already_know"])
    review_parser.add_argument("--candidate-id")

    subparsers.add_parser("inbox")

    learn_parser = subparsers.add_parser("learn-one")
    learn_parser.add_argument("item_id", nargs="?")

    check_parser = subparsers.add_parser("check")
    check_parser.add_argument("debt_id")
    check_parser.add_argument("--answer")
    check_parser.add_argument("--skip", action="store_true")

    cleanup_parser = subparsers.add_parser("cleanup")
    cleanup_parser.add_argument("--dry-run", action="store_true")

    delete_parser = subparsers.add_parser("delete")
    delete_parser.add_argument("target", choices=["session", "debt"])
    delete_parser.add_argument("id")

    export_parser = subparsers.add_parser("export")
    export_parser.add_argument("kind", choices=["deep-review"])
    export_parser.add_argument("session_id", nargs="?")

    args = parser.parse_args(argv)

    try:
        if args.command == "init":
            return _init(args.adapter)
        if args.command == "status":
            return _status()
        if args.command == "doctor":
            return _doctor()
        if args.command == "hook":
            return _hook(args.adapter)
        if args.command == "review":
            return _review(args.session_id, args.analysis_file, args.action, args.candidate_id)
        if args.command == "inbox":
            return _inbox()
        if args.command == "learn-one":
            return _learn_one(args.item_id)
        if args.command == "check":
            return _check(args.debt_id, args.answer, args.skip)
        if args.command == "cleanup":
            return _cleanup(args.dry_run)
        if args.command == "delete":
            return _delete(args.target, args.id)
        if args.command == "export":
            return _export(args.kind, args.session_id)
    except Exception as exc:
        print(f"ai-debt error: {exc}", file=sys.stderr)
        return 1
    return 0


def _init(adapter: str | None) -> int:
    initialize()
    if adapter:
        mark_adapter(adapter)
        hook_path = write_hook_script(adapter)
        print(f"initialized {adapter} adapter")
        print(f"hook script: {hook_path}")
        return 0
    print(f"initialized AI Debt state at {state_home()}")
    return 0


def _status() -> int:
    initialize()
    config = load_config()
    conn = connect(db_path())
    try:
        migrate(conn)
        refresh_session_states(conn, config)
        counts = status_counts(conn)
        sessions = recent_sessions(conn)
    finally:
        conn.close()

    print("AI Debt status")
    print(f"state: {state_home()}")
    print(f"recording: {counts.get('recording', 0)}")
    print(f"idle_detected: {counts.get('idle_detected', 0)}")
    print(f"pending_settlement: {counts.get('pending_settlement', 0)}")
    if sessions:
        print("recent sessions:")
        for row in sessions:
            print(f"- {row['id']} [{row['source']}] {row['status']} {row['last_activity_at']}")
    return 0


def _doctor() -> int:
    config = load_config()
    db_exists = db_path().exists()
    schema_ok = False
    hook_event = None
    if db_exists:
        conn = connect(db_path())
        try:
            schema_ok = schema_is_valid(conn)
            hook_event = last_hook_event(conn)
        finally:
            conn.close()
    raw_total, raw_expired = raw_payload_cleanup_summary(config)
    checks = [
        ("config exists", config_path().exists(), f"run: ai-debt init"),
        ("db exists", db_exists, f"run: ai-debt init"),
        ("db schema valid", schema_ok, f"run: ai-debt init"),
        ("journal path writable", _is_writable(journals_path()), "run: ai-debt init or check directory permissions"),
        ("Claude Code hook generated", config.adapters.claude_code and (hooks_path() / "claude-code-hook.ps1").exists(), "run: ai-debt init claude-code"),
        ("Codex hook generated", config.adapters.codex and (hooks_path() / "codex-hook.ps1").exists(), "run: ai-debt init codex"),
        ("last hook event received", hook_event is not None, "send a fixture or real hook event through ai-debt hook"),
        ("raw payload cleanup current", raw_expired == 0, "run: ai-debt cleanup --dry-run, then ai-debt cleanup"),
    ]
    exit_code = 0
    print("AI Debt doctor")
    for label, ok, fix in checks:
        marker = "ok" if ok else "needs_fix"
        print(f"- {marker}: {label}")
        if not ok:
            print(f"  fix: {fix}")
            exit_code = 1
    print(f"raw payloads: total={raw_total} expired={raw_expired}")
    if hook_event:
        print(f"last hook: {hook_event['source']} {hook_event['type']} {hook_event['session_id']} {hook_event['occurred_at']}")
    return exit_code


def _hook(adapter: str) -> int:
    payload = read_json_stdin(sys.stdin.read())
    event = capture_payload(adapter, payload)
    conn = connect(db_path())
    try:
        counts = status_counts(conn)
    finally:
        conn.close()
    print(f"ai-debt: {event['type']} captured; pending_settlement={counts.get('pending_settlement', 0)}")
    return 0


def _review(session_id: str | None, analysis_file: str | None, action: str | None, candidate_id: str | None) -> int:
    initialize()
    config = load_config()
    conn = connect(db_path())
    try:
        migrate(conn)
        refresh_session_states(conn, config)
        if action:
            if not candidate_id:
                raise ValueError("--candidate-id is required with --action")
            debt_id = apply_review_action(conn, candidate_id, action)
            print(f"review action recorded: {action}")
            if debt_id:
                print(f"debt_id: {debt_id}")
            return 0

        session = select_review_session(conn, session_id)
        if session is None:
            print("no sessions ready for review")
            return 0

        if analysis_file:
            raw_analysis = Path(analysis_file).read_text(encoding="utf-8")
            try:
                analysis = parse_analysis(raw_analysis)
            except ValueError as exc:
                failed_path = _write_failed_review_output(raw_analysis)
                raise ValueError(f"{exc}; raw output saved to {failed_path}") from exc
            created = create_candidates(conn, session["id"], analysis)
            print(f"review candidates created for session {session['id']}: {len(created)}")
            for item in created:
                reason_text = f" ({'; '.join(item['gate_reasons'])})" if item["gate_reasons"] else ""
                print(f"- {item['id']}: {item['status']}{reason_text}")
            return 0

        print(json.dumps(build_review_input(conn, session["id"]), ensure_ascii=False, indent=2))
        return 0
    finally:
        conn.close()


def _inbox() -> int:
    initialize()
    conn = connect(db_path())
    try:
        rows = list_inbox(conn)
    finally:
        conn.close()
    if not rows:
        print("inbox is empty")
        return 0
    print("AI Debt inbox")
    for row in rows:
        print(f"- {row['debt_id']} [{row['priority']}] {row['status']} {row['concept']} ({row['debt_dimension']})")
    return 0


def _learn_one(item_id: str | None) -> int:
    initialize()
    conn = connect(db_path())
    try:
        item = learn_one(conn, item_id)
    finally:
        conn.close()
    print(f"Learn One: {item['concept']}")
    print(f"id: {item['id']}")
    print(f"kind: {item['kind']}")
    print(f"short explanation: {item['short_explanation']}")
    print(f"why it matters: {item['why_it_matters']}")
    print(f"minimal trace: {item['minimal_trace']}")
    print(f"quick check: {item['quick_check_prompt']}")
    return 0


def _check(debt_id: str, answer: str | None, skip: bool) -> int:
    initialize()
    conn = connect(db_path())
    try:
        result = record_grasp_check(conn, debt_id, answer, skipped=skip)
    finally:
        conn.close()
    print(f"grasp check: {result}")
    return 0


def _cleanup(dry_run: bool) -> int:
    initialize()
    result = cleanup_raw_payloads(load_config(), dry_run=dry_run)
    action = "would remove" if dry_run else "removed"
    print(f"cleanup: {action} {len(result.raw_payloads)} expired raw payload(s)")
    for path in result.raw_payloads:
        print(f"- {path}")
    return 0


def _delete(target: str, item_id: str) -> int:
    initialize()
    conn = connect(db_path())
    try:
        if target == "session":
            delete_session(conn, item_id)
        elif target == "debt":
            delete_debt(conn, item_id)
        else:
            raise ValueError(f"Unsupported delete target: {target}")
    finally:
        conn.close()
    print(f"deleted {target}: {item_id}")
    return 0


def _export(kind: str, session_id: str | None) -> int:
    initialize()
    if kind != "deep-review":
        raise ValueError(f"Unsupported export kind: {kind}")
    conn = connect(db_path())
    try:
        path = export_deep_review(conn, session_id)
    finally:
        conn.close()
    print(f"deep review exported: {path}")
    return 0


def _write_failed_review_output(raw_output: str) -> Path:
    logs_path().mkdir(parents=True, exist_ok=True)
    path = logs_path() / f"review_analysis_failed_{utc_now().replace(':', '-')}.txt"
    path.write_text(raw_output, encoding="utf-8")
    return path


def _is_writable(path: Path) -> bool:
    try:
        if not path.exists():
            return False
        probe = path / ".write-test"
        probe.write_text("ok", encoding="utf-8")
        probe.unlink()
        return True
    except OSError:
        return False


if __name__ == "__main__":
    raise SystemExit(main())
