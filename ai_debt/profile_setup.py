from __future__ import annotations

import json
import sqlite3
from typing import TextIO

from .ownership import default_profile, project_id_for_cwd, update_profile


ROLE_OPTIONS = {
    "1": ("independent_developer", "独立开发者 - 一个人负责需求、代码、验证和维护", "Independent developer - you own requirements, code, validation, and maintenance"),
    "2": ("tech_lead", "技术负责人 - 需要管住方案、接口、风险和演进节奏", "Tech lead - you own design direction, interfaces, risk, and evolution pace"),
    "3": ("product_engineer", "产品工程师 - 同时关心用户路径、产品判断和实现细节", "Product engineer - you care about user flow, product judgment, and implementation details"),
    "4": ("learner", "学习型构建者 - 借 AI 做项目，同时补齐技术掌控力", "Learning builder - you build with AI while improving technical ownership"),
    "5": ("other", "其他 - 暂不归类，之后可手动编辑 profile", "Other - leave it unclassified for now; you can edit the profile later"),
}

PROJECT_INTENT_OPTIONS = {
    "1": ("local_first_tool", "本地工具/个人工作流 - 主要给自己或小团队用，优先 local-first", "Local-first tool or workflow - mainly for yourself or a small team"),
    "2": ("production_app", "线上产品/生产应用 - 面向真实用户，稳定性、隐私和运维更重要", "Production app - real users, so stability, privacy, and operations matter more"),
    "3": ("prototype", "原型验证 - 重点验证方向，允许快速试错和丢弃", "Prototype - validate direction quickly, with room to discard work"),
    "4": ("learning_project", "学习/练手项目 - 重点理解技术、框架和构建过程", "Learning project - focus on understanding the technology, framework, and build process"),
    "5": ("library_or_framework", "库/框架/基础设施 - 会被其他代码依赖，API 和兼容性更重要", "Library, framework, or infrastructure - other code depends on APIs and compatibility"),
    "6": ("other", "其他 - 暂不归类，之后可手动编辑 profile", "Other - leave it unclassified for now; you can edit the profile later"),
}

TARGET_LEVEL_OPTIONS = {
    "1": ("L2", "L2 能解释并小改 - 能说清关键路径，并按指引做局部修改", "L2 explain and make small changes - understand key paths and make guided edits"),
    "2": ("L3", "L3 能独立维护 - 能定位问题、完成改动，并验证常见风险", "L3 maintain independently - diagnose, change, and validate common risks"),
    "3": ("L4", "L4 能做设计取舍 - 能评估方案边界、风险和长期影响", "L4 make design tradeoffs - assess boundaries, risks, and long-term impact"),
    "4": ("L5", "L5 能主导演进 - 能制定架构规则，审查复杂变更和系统方向", "L5 lead evolution - define architecture rules and review complex changes"),
}

LEVELS = {"L0", "L1", "L2", "L3", "L4", "L5"}
LEVEL_DESCRIPTIONS = {
    "zh": [
        "L0 完全陌生",
        "L1 看得懂一点，但不能安全修改",
        "L2 能解释并做小改",
        "L3 能独立维护常见问题",
        "L4 能设计取舍并审查方案",
        "L5 能主导长期演进",
    ],
    "en": [
        "L0 completely unfamiliar",
        "L1 can roughly read it, but cannot safely change it",
        "L2 can explain it and make small edits",
        "L3 can independently maintain common issues",
        "L4 can make design tradeoffs and review plans",
        "L5 can lead long-term evolution",
    ],
}
TEXT = {
    "zh": {
        "heading": "为当前项目设置 Ownership Profile。",
        "intro": "这些答案只用于决定 AI Debt 后续提醒、解释深度和需要你确认的控制点。",
        "role": "你在这个项目里的主要责任",
        "project_intent": "这个项目当前最接近哪种形态",
        "target_level": "你希望自己对关键控制点达到什么掌控级别",
        "critical_areas": "关键控制区",
        "critical_areas_help": "AI Debt 会优先关注这些区域，例如 data, privacy, auth, schema, core_logic",
        "unacceptable_risks": "不可接受风险",
        "unacceptable_risks_help": "出现这些风险时应该更强提醒或要求确认，例如 data_loss, privacy_leak, security_regression",
        "edit_contract": "是否现在调整 AI 控制边界？",
        "ai_free": "AI 可以直接处理",
        "ai_free_help": "低风险事项，通常不需要额外解释，例如 formatting, boilerplate, docs wording",
        "ai_explain": "AI 必须先解释",
        "ai_explain_help": "你需要理解但不一定逐项批准的事项，例如 data model, review logic, debt scoring",
        "ai_confirm": "AI 必须先确认",
        "ai_confirm_help": "执行前必须征得你同意的事项，例如 delete data, new dependency, schema migration",
        "user_own": "必须由你掌控",
        "user_own_help": "系统只能提醒和辅助，但最终判断必须由你负责的事项",
        "choose": "请选择",
        "tech_familiarity": "技术熟悉度（可选）:",
        "tech_prompt": "请输入 NAME=L0..L5，逗号分隔，例如 React=L3, SQLite=L2；留空跳过: ",
        "tech_error": "格式不正确。请使用 NAME=L0..L5，多个项目用英文逗号分隔。",
        "yes_default": "Y/n，默认是",
        "no_default": "y/N，默认否",
    },
    "en": {
        "heading": "Set up the Ownership Profile for this project.",
        "intro": "These answers decide later AI Debt reminders, explanation depth, and control points that need your confirmation.",
        "role": "Your main responsibility in this project",
        "project_intent": "Which shape best matches this project right now",
        "target_level": "Your target ownership level for key control points",
        "critical_areas": "Critical areas",
        "critical_areas_help": "AI Debt will prioritize these areas, for example data, privacy, auth, schema, core_logic",
        "unacceptable_risks": "Unacceptable risks",
        "unacceptable_risks_help": "Risks that should trigger stronger reminders or confirmation, for example data_loss, privacy_leak, security_regression",
        "edit_contract": "Edit the AI control boundary now?",
        "ai_free": "AI may handle directly",
        "ai_free_help": "Low-risk work that usually needs no extra explanation, for example formatting, boilerplate, docs wording",
        "ai_explain": "AI must explain first",
        "ai_explain_help": "Things you should understand but do not need to approve item by item, for example data model, review logic, debt scoring",
        "ai_confirm": "AI must confirm first",
        "ai_confirm_help": "Things that require your approval before execution, for example delete data, new dependency, schema migration",
        "user_own": "User must own",
        "user_own_help": "Things where the system can remind and assist, but final judgment must stay with you",
        "choose": "Choose",
        "tech_familiarity": "Tech familiarity (optional):",
        "tech_prompt": "Enter NAME=L0..L5, comma-separated, for example React=L3, SQLite=L2; leave blank to skip: ",
        "tech_error": "Invalid format. Use NAME=L0..L5 pairs separated by commas.",
        "yes_default": "Y/n, default yes",
        "no_default": "y/N, default no",
    },
}


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
    language = _language_choice(input_stream, output, str(profile.get("language") or "zh"))
    profile["language"] = language
    text = TEXT[language]
    _write(output, text["heading"])
    _write(output, text["intro"])
    _write(output, "")
    profile["role"] = _choice(
        input_stream,
        output,
        text["role"],
        ROLE_OPTIONS,
        str(profile["role"]),
        language,
    )
    profile["project_intent"] = _choice(
        input_stream,
        output,
        text["project_intent"],
        PROJECT_INTENT_OPTIONS,
        str(profile["project_intent"]),
        language,
    )
    profile["target_ownership_level"] = _choice(
        input_stream,
        output,
        text["target_level"],
        TARGET_LEVEL_OPTIONS,
        str(profile["target_ownership_level"]),
        language,
    )
    profile["critical_areas"] = _list_prompt(
        input_stream,
        output,
        text["critical_areas"],
        text["critical_areas_help"],
        profile["critical_areas"],
    )
    profile["unacceptable_risks"] = _list_prompt(
        input_stream,
        output,
        text["unacceptable_risks"],
        text["unacceptable_risks_help"],
        profile["unacceptable_risks"],
    )

    contract = profile["control_contract"]
    if _yes_no(input_stream, output, text["edit_contract"], default=False, language=language):
        contract["ai_free_to_handle"] = _list_prompt(
            input_stream,
            output,
            text["ai_free"],
            text["ai_free_help"],
            contract["ai_free_to_handle"],
        )
        contract["ai_must_explain"] = _list_prompt(
            input_stream,
            output,
            text["ai_explain"],
            text["ai_explain_help"],
            contract["ai_must_explain"],
        )
        contract["ai_must_confirm"] = _list_prompt(
            input_stream,
            output,
            text["ai_confirm"],
            text["ai_confirm_help"],
            contract["ai_must_confirm"],
        )
        contract["user_must_own"] = _list_prompt(
            input_stream,
            output,
            text["user_own"],
            text["user_own_help"],
            contract["user_must_own"],
        )
    profile["tech_familiarity"] = _tech_familiarity_prompt(input_stream, output, language)
    return profile


def _language_choice(input_stream: TextIO | None, output: TextIO | None, default: str) -> str:
    default_language = default if default in TEXT else "zh"
    default_display = "2" if default_language == "en" else "1"
    _write(output, "Language / 语言:")
    _write(output, "  1. 中文")
    _write(output, "  2. English")
    text = _read(input_stream, output, f"Choose language / 选择语言 [{default_display}]: ").strip().lower()
    if not text:
        return default_language
    if text in {"1", "zh", "cn", "中文", "chinese"}:
        return "zh"
    if text in {"2", "en", "english"}:
        return "en"
    return default_language


def _choice(
    input_stream: TextIO | None,
    output: TextIO | None,
    label: str,
    options: dict[str, tuple[str, str, str]],
    default: str,
    language: str,
) -> str:
    _write(output, f"{label}:")
    for key, option in options.items():
        _write(output, f"  {key}. {_option_description(option, language)}")
    default_key = _option_key_for_value(options, default)
    default_display = default_key or default
    text = _read(input_stream, output, f"{TEXT[language]['choose']} [{default_display}]: ").strip()
    if not text:
        return default
    option = options.get(text)
    return option[0] if option else text


def _list_prompt(
    input_stream: TextIO | None,
    output: TextIO | None,
    label: str,
    help_text: str,
    default_items: object,
) -> list[str]:
    items = [str(item) for item in default_items] if isinstance(default_items, list) else []
    default_text = ", ".join(items)
    _write(output, f"{label}: {help_text}")
    text = _read(input_stream, output, f"{label} [{default_text}]: ").strip()
    if not text:
        return items
    return [item.strip() for item in text.split(",") if item.strip()]


def _tech_familiarity_prompt(input_stream: TextIO | None, output: TextIO | None, language: str) -> dict[str, str]:
    text = TEXT[language]
    _write(output, text["tech_familiarity"])
    for item in LEVEL_DESCRIPTIONS[language]:
        _write(output, f"  {item}")
    while True:
        answer = _read(input_stream, output, text["tech_prompt"]).strip()
        if not answer:
            return {}
        result: dict[str, str] = {}
        valid = True
        for item in answer.split(","):
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
        _write(output, text["tech_error"])


def _yes_no(input_stream: TextIO | None, output: TextIO | None, question: str, default: bool, language: str) -> bool:
    suffix = TEXT[language]["yes_default"] if default else TEXT[language]["no_default"]
    text = _read(input_stream, output, f"{question} [{suffix}]: ").strip().lower()
    if not text:
        return default
    return text in {"y", "yes", "是", "好", "确认"}


def _option_key_for_value(options: dict[str, tuple[str, str, str]], value: str) -> str | None:
    for key, option in options.items():
        if option[0] == value:
            return key
    return None


def _option_description(option: tuple[str, str, str], language: str) -> str:
    return option[2] if language == "en" else option[1]


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
