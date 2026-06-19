from __future__ import annotations

import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import uuid4

from .events import AgentEvent
from .paths import journals_path


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def session_dir(session_id: str, home: Path | None = None) -> Path:
    return journals_path(home) / _safe_name(session_id)


def write_raw_payload(session_id: str, payload: dict[str, Any], home: Path | None = None) -> str:
    root = session_dir(session_id, home) / "raw"
    root.mkdir(parents=True, exist_ok=True)
    path = root / f"{utc_now().replace(':', '-')}-{uuid4().hex[:8]}.json"
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return str(path)


def append_event(event: AgentEvent, home: Path | None = None) -> Path:
    root = session_dir(event["session_id"], home)
    root.mkdir(parents=True, exist_ok=True)
    path = root / "events.jsonl"
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(event, ensure_ascii=False, sort_keys=True) + "\n")
    _write_session_meta(event, root)
    _write_snapshots(event, root)
    return path


def _write_session_meta(event: AgentEvent, root: Path) -> None:
    meta_path = root / "session_meta.json"
    existing: dict[str, Any] = {}
    if meta_path.exists():
        existing = json.loads(meta_path.read_text(encoding="utf-8"))
    existing.update(
        {
            "session_id": event["session_id"],
            "source": event["source"],
            "last_activity_at": event["occurred_at"],
        }
    )
    if event["type"] == "session_started":
        existing["started_at"] = event["occurred_at"]
        existing["cwd"] = event.get("cwd")
        existing["transcript_ref"] = event.get("transcript_ref")
    if event["type"] == "session_ended":
        existing["ended_at"] = event["occurred_at"]
    meta_path.write_text(json.dumps(existing, ensure_ascii=False, indent=2), encoding="utf-8")


def _write_snapshots(event: AgentEvent, root: Path) -> None:
    cwd = event.get("cwd")
    if not cwd:
        meta_path = root / "session_meta.json"
        if meta_path.exists():
            cwd = json.loads(meta_path.read_text(encoding="utf-8")).get("cwd")
    if not cwd:
        return

    cwd_path = Path(cwd)
    if not cwd_path.exists():
        return
    diff = _run_git(["git", "diff", "--"], cwd_path)
    if diff is not None:
        (root / "diff.patch").write_text(diff, encoding="utf-8")
    changed = _run_git(["git", "status", "--short"], cwd_path)
    if changed is not None:
        (root / "changed_files.txt").write_text(changed, encoding="utf-8")


def _run_git(args: list[str], cwd: Path) -> str | None:
    try:
        result = subprocess.run(args, cwd=cwd, text=True, capture_output=True, timeout=5, check=False)
    except (OSError, subprocess.SubprocessError):
        return None
    if result.returncode != 0:
        return None
    return result.stdout


def _safe_name(value: str) -> str:
    return "".join(char if char.isalnum() or char in {"-", "_", "."} else "_" for char in value)
