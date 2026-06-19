from __future__ import annotations

from pathlib import Path

from .paths import hooks_path


def write_hook_script(adapter: str, home: Path | None = None) -> Path:
    if adapter not in {"claude-code", "codex"}:
        raise ValueError(f"Unsupported adapter: {adapter}")
    path = hooks_path(home) / f"{adapter}-hook.ps1"
    path.write_text(
        "\n".join(
            [
                "$payload = [Console]::In.ReadToEnd()",
                f"$payload | ai-debt hook {adapter}",
                "",
            ]
        ),
        encoding="utf-8",
    )
    return path
