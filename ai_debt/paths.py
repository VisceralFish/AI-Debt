from __future__ import annotations

import os
from pathlib import Path


def state_home() -> Path:
    override = os.environ.get("AI_DEBT_HOME")
    if override:
        return Path(override).expanduser()
    return Path.home() / ".ai-debt"


def config_path(home: Path | None = None) -> Path:
    return (home or state_home()) / "config.yaml"


def db_path(home: Path | None = None) -> Path:
    return (home or state_home()) / "ai_debt.db"


def journals_path(home: Path | None = None) -> Path:
    return (home or state_home()) / "journals"


def logs_path(home: Path | None = None) -> Path:
    return (home or state_home()) / "logs"


def exports_path(home: Path | None = None) -> Path:
    return (home or state_home()) / "exports"


def hooks_path(home: Path | None = None) -> Path:
    return (home or state_home()) / "hooks"


def ensure_layout(home: Path | None = None) -> Path:
    root = home or state_home()
    root.mkdir(parents=True, exist_ok=True)
    journals_path(root).mkdir(parents=True, exist_ok=True)
    logs_path(root).mkdir(parents=True, exist_ok=True)
    exports_path(root).mkdir(parents=True, exist_ok=True)
    hooks_path(root).mkdir(parents=True, exist_ok=True)
    return root
