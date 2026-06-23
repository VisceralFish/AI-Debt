from __future__ import annotations

import json
import sqlite3
from typing import TextIO

from .ownership import default_profile, project_id_for_cwd, update_profile


ROLE_OPTIONS = {
    "1": "independent_developer",
    "2": "tech_lead",
    "3": "product_engineer",
    "4": "learner",
    "5": "other",
}

PROJECT_INTENT_OPTIONS = {
    "1": "local_first_tool",
    "2": "production_app",
    "3": "prototype",
    "4": "learning_project",
    "5": "library_or_framework",
    "6": "other",
}

TARGET_LEVEL_OPTIONS = {
    "1": "L2",
    "2": "L3",
    "3": "L4",
    "4": "L5",
}

LEVELS = {"L0", "L1", "L2", "L3", "L4", "L5"}


def profile_exists(conn: sqlite3.Connection, project_id: str) -> bool:
    row = conn.execute("SELECT 1 FROM ownership_profiles WHERE project_id = ?", (project_id,)).fetchone()
    return row is not None


def load_project_profile(conn: sqlite3.Connection, project_id: str) -> dict[str, object] | None:
    row = conn.execute("SELECT payload_json FROM ownership_profiles WHERE project_id = ?", (project_id,)).fetchone()
    if row is None:
        return None
    return json.loads(row["payload_json"])


def setup_project_profile(
    conn: sqlite3.Connection,
    cwd: str | None,
    force: bool = False,
    interactive: bool = False,
    input_stream: TextIO | None = None,
    output: TextIO | None = None,
) -> tuple[dict[str, object], bool]:
    project_id = project_id_for_cwd(cwd)
    if profile_exists(conn, project_id) and not force:
        profile = load_project_profile(conn, project_id)
        if profile is None:
            raise ValueError(f"Unknown ownership profile: {project_id}")
        return profile, False

    profile = default_profile(project_id)
    if interactive:
        profile = collect_profile_answers(profile, input_stream, output)
    updated = update_profile(conn, project_id, profile)
    return updated, True


def collect_profile_answers(
    base_profile: dict[str, object],
    input_stream: TextIO | None,
    output: TextIO | None,
) -> dict[str, object]:
    profile = json.loads(json.dumps(base_profile, ensure_ascii=False))
    _write(output, "Set up ownership profile for this project.")
    _write(output, "")
    profile["role"] = _choice(
        input_stream,
        output,
        "Role",
        ROLE_OPTIONS,
        str(profile["role"]),
    )
    profile["project_intent"] = _choice(
        input_stream,
        output,
        "Project intent",
        PROJECT_INTENT_OPTIONS,
        str(profile["project_intent"]),
    )
    profile["target_ownership_level"] = _choice(
        input_stream,
        output,
        "Target ownership level",
        TARGET_LEVEL_OPTIONS,
        str(profile["target_ownership_level"]),
    )
    profile["critical_areas"] = _list_prompt(input_stream, output, "Critical areas", profile["critical_areas"])
    profile["unacceptable_risks"] = _list_prompt(input_stream, output, "Unacceptable risks", profile["unacceptable_risks"])

    contract = profile["control_contract"]
    if _yes_no(input_stream, output, "Edit control contract?", default=False):
        contract["ai_free_to_handle"] = _list_prompt(input_stream, output, "AI may handle freely", contract["ai_free_to_handle"])
        contract["ai_must_explain"] = _list_prompt(input_stream, output, "AI must explain", contract["ai_must_explain"])
        contract["ai_must_confirm"] = _list_prompt(input_stream, output, "AI must confirm", contract["ai_must_confirm"])
        contract["user_must_own"] = _list_prompt(input_stream, output, "User must own", contract["user_must_own"])
    profile["tech_familiarity"] = _tech_familiarity_prompt(input_stream, output)
    return profile


def _choice(
    input_stream: TextIO | None,
    output: TextIO | None,
    label: str,
    options: dict[str, str],
    default: str,
) -> str:
    _write(output, f"{label}:")
    for key, value in options.items():
        _write(output, f"  {key}. {value}")
    text = _read(input_stream, output, f"Choose [{default}]: ").strip()
    if not text:
        return default
    return options.get(text, text)


def _list_prompt(
    input_stream: TextIO | None,
    output: TextIO | None,
    label: str,
    default_items: object,
) -> list[str]:
    items = [str(item) for item in default_items] if isinstance(default_items, list) else []
    default_text = ", ".join(items)
    text = _read(input_stream, output, f"{label} [{default_text}]: ").strip()
    if not text:
        return items
    return [item.strip() for item in text.split(",") if item.strip()]


def _tech_familiarity_prompt(input_stream: TextIO | None, output: TextIO | None) -> dict[str, str]:
    while True:
        text = _read(input_stream, output, "Tech familiarity (NAME=L0..L5, comma-separated, optional): ").strip()
        if not text:
            return {}
        result: dict[str, str] = {}
        valid = True
        for item in text.split(","):
            if "=" not in item:
                valid = False
                break
            name, level = [part.strip() for part in item.split("=", 1)]
            if not name or level not in LEVELS:
                valid = False
                break
            result[name] = level
        if valid:
            return result
        _write(output, "Use NAME=L0..L5 pairs, comma-separated.")


def _yes_no(input_stream: TextIO | None, output: TextIO | None, question: str, default: bool) -> bool:
    suffix = "Y/n" if default else "y/N"
    text = _read(input_stream, output, f"{question} [{suffix}]: ").strip().lower()
    if not text:
        return default
    return text in {"y", "yes"}


def _read(input_stream: TextIO | None, output: TextIO | None, prompt: str) -> str:
    if output is not None:
        output.write(prompt)
        output.flush()
    if input_stream is None:
        return ""
    return input_stream.readline()


def _write(output: TextIO | None, text: str) -> None:
    if output is not None:
        output.write(text + "\n")
