from __future__ import annotations

import json
from pathlib import Path

from .paths import hooks_path


CODEX_TUI_HOOK_COMMAND = "ai-debt codex-tui-hook"
CODEX_TUI_HOOK_EVENTS = ("SessionStart", "UserPromptSubmit", "Stop")


def write_hook_script(adapter: str, home: Path | None = None) -> Path:
    if adapter not in {"claude-code", "codex"}:
        raise ValueError(f"Unsupported adapter: {adapter}")
    path = hooks_path(home) / f"{adapter}-hook.ps1"
    path.write_text(
        "\n".join(
            [
                "$payload = [Console]::In.ReadToEnd()",
                "$native = Get-Command ai-debt -ErrorAction SilentlyContinue",
                "if ($native) {",
                f"  $payload | & $native.Source hook {adapter}",
                "  exit $LASTEXITCODE",
                "}",
                f"$payload | python -m ai_debt.cli hook {adapter}",
                "exit $LASTEXITCODE",
                "",
            ]
        ),
        encoding="utf-8",
    )
    return path


def write_codex_tui_hooks(project_root: Path | None = None) -> Path:
    root = project_root or Path.cwd()
    path = root / ".codex" / "hooks.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    document = _read_hooks_document(path)
    hooks = document.setdefault("hooks", {})
    if not isinstance(hooks, dict):
        raise ValueError(f"Invalid Codex hooks object: {path}")

    for event_name in CODEX_TUI_HOOK_EVENTS:
        entries = hooks.setdefault(event_name, [])
        if not isinstance(entries, list):
            raise ValueError(f"Invalid Codex hook list for {event_name}: {path}")
        entries[:] = [entry for entry in entries if not _is_ai_debt_hook(entry)]
        entry: dict[str, object] = {
            "hooks": [
                {
                    "type": "command",
                    "command": CODEX_TUI_HOOK_COMMAND,
                    "timeout": 10,
                    "statusMessage": "AI Debt: checking review state",
                }
            ]
        }
        if event_name == "SessionStart":
            entry["matcher"] = "startup|resume|clear|compact"
        entries.append(entry)

    path.write_text(json.dumps(document, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return path


def _read_hooks_document(path: Path) -> dict[str, object]:
    if not path.exists():
        return {"hooks": {}}
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ValueError(f"Invalid Codex hooks JSON: {path}") from exc
    if not isinstance(value, dict):
        raise ValueError(f"Codex hooks file must contain a JSON object: {path}")
    return value


def _is_ai_debt_hook(entry: object) -> bool:
    if not isinstance(entry, dict):
        return False
    handlers = entry.get("hooks")
    if not isinstance(handlers, list):
        return False
    return any(
        isinstance(handler, dict) and handler.get("command") == CODEX_TUI_HOOK_COMMAND
        for handler in handlers
    )
