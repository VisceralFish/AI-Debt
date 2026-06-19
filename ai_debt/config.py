from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from .paths import config_path


@dataclass
class PrivacyConfig:
    copy_full_transcript: bool = False
    raw_payload_retention_days: int = 7


@dataclass
class AdapterConfig:
    claude_code: bool = False
    codex: bool = False


@dataclass
class AppConfig:
    privacy: PrivacyConfig = field(default_factory=PrivacyConfig)
    adapters: AdapterConfig = field(default_factory=AdapterConfig)
    idle_minutes: int = 15
    pending_minutes: int = 30


def default_config() -> AppConfig:
    return AppConfig()


def load_config(home: Path | None = None) -> AppConfig:
    path = config_path(home)
    if not path.exists():
        return default_config()

    current_section = ""
    values: dict[str, str] = {}
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        if not raw_line.strip() or raw_line.lstrip().startswith("#"):
            continue
        if ":" not in raw_line:
            continue
        if not raw_line.startswith(" ") and raw_line.rstrip().endswith(":"):
            current_section = raw_line.strip()[:-1]
            continue
        if not raw_line.startswith(" "):
            current_section = ""
        key, value = raw_line.strip().split(":", 1)
        values[f"{current_section}.{key}" if current_section else key] = value.strip()

    config = default_config()
    config.privacy.copy_full_transcript = _as_bool(
        values.get("privacy.copy_full_transcript"),
        config.privacy.copy_full_transcript,
    )
    config.privacy.raw_payload_retention_days = _as_int(
        values.get("privacy.raw_payload_retention_days"),
        config.privacy.raw_payload_retention_days,
    )
    config.adapters.claude_code = _as_bool(values.get("adapters.claude_code"), False)
    config.adapters.codex = _as_bool(values.get("adapters.codex"), False)
    config.idle_minutes = _as_int(values.get("idle_minutes"), config.idle_minutes)
    config.pending_minutes = _as_int(values.get("pending_minutes"), config.pending_minutes)
    return config


def save_config(config: AppConfig, home: Path | None = None) -> None:
    path = config_path(home)
    path.write_text(
        "\n".join(
            [
                "privacy:",
                f"  copy_full_transcript: {_bool_text(config.privacy.copy_full_transcript)}",
                f"  raw_payload_retention_days: {config.privacy.raw_payload_retention_days}",
                "adapters:",
                f"  claude_code: {_bool_text(config.adapters.claude_code)}",
                f"  codex: {_bool_text(config.adapters.codex)}",
                f"idle_minutes: {config.idle_minutes}",
                f"pending_minutes: {config.pending_minutes}",
                "",
            ]
        ),
        encoding="utf-8",
    )


def mark_adapter(adapter: str, home: Path | None = None) -> AppConfig:
    config = load_config(home)
    if adapter == "claude-code":
        config.adapters.claude_code = True
    elif adapter == "codex":
        config.adapters.codex = True
    else:
        raise ValueError(f"Unsupported adapter: {adapter}")
    save_config(config, home)
    return config


def _as_bool(value: str | None, default: bool) -> bool:
    if value is None:
        return default
    return value.lower() in {"true", "yes", "1", "on"}


def _as_int(value: str | None, default: int) -> int:
    if value is None:
        return default
    try:
        return int(value)
    except ValueError:
        return default


def _bool_text(value: bool) -> str:
    return "true" if value else "false"
