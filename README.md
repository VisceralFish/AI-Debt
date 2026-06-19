# AI Debt

AI Debt is a local-first cognitive debt ledger for AI-assisted build sessions. It helps AI builders understand what the agent did on their behalf, which decisions may need review, and which accepted gaps should be tracked as learning or maintenance work.

The MVP covers the full loop:

```text
Claude Code / Codex Hook
  -> Agent Adapter
  -> Normalized AgentEvent
  -> Build Journal
  -> pending_settlement
  -> ai-debt review
  -> Debt Candidate
  -> Evidence Gate
  -> user confirmation
  -> Debt Ledger / Inbox
  -> Learn One
  -> optional Grasp Check
  -> Deep Review Markdown export
```

## Status

Phase 1, Phase 2, and Phase 3 MVP implementation are in place:

- Capture core, SQLite state, Build Journal, and normalized `AgentEvent`.
- Claude Code and Codex primary adapters.
- User-triggered review flow with Evidence Gate.
- Debt Ledger, Learning Inbox, Learn One, and skippable Grasp Check.
- Raw payload cleanup, delete support, recovery from journals, and Deep Review export.
- Convergence tests for both Claude Code and Codex fixture paths.

## Installation

This project currently uses Python standard library only.

```bash
python -m ai_debt.cli init
python -m ai_debt.cli init claude-code
python -m ai_debt.cli init codex
```

Default local state directory:

```text
~/.ai-debt/
├── config.yaml
├── ai_debt.db
├── journals/
├── logs/
├── exports/
└── hooks/
```

## Common Commands

```bash
python -m ai_debt.cli status
python -m ai_debt.cli doctor
python -m ai_debt.cli review
python -m ai_debt.cli review --analysis-file result.json
python -m ai_debt.cli review --action accept --candidate-id <candidate-id>
python -m ai_debt.cli inbox
python -m ai_debt.cli learn-one <debt-id>
python -m ai_debt.cli check <debt-id> --answer "..."
python -m ai_debt.cli export deep-review <session-id>
python -m ai_debt.cli cleanup --dry-run
python -m ai_debt.cli cleanup
python -m ai_debt.cli delete session <session-id>
python -m ai_debt.cli delete debt <debt-id>
```

## Review Flow

`ai-debt review` does not call a background LLM. It emits a structured review input package for the current agent. After the current agent generates a structured analysis JSON file, import it with:

```bash
python -m ai_debt.cli review <session-id> --analysis-file result.json
```

Only evidence-backed candidates can be accepted into the ledger:

```bash
python -m ai_debt.cli review --action accept --candidate-id <candidate-id>
```

## Privacy Defaults

AI Debt is local-first by default:

```yaml
privacy:
  copy_full_transcript: false
  raw_payload_retention_days: 7
```

Raw payloads are temporary adapter-debugging artifacts. Normalized events, evidence references, and ledger entries remain after cleanup.

## Testing

```bash
python -B -m unittest discover -s tests -v
```

## MVP Boundaries

The MVP does not include a desktop app, Terminal Pet, background automatic LLM analysis, independent provider/API key management, cloud sync, team dashboards, Cursor/OpenCode adapters, or Anki/Obsidian integrations.

---

# AI Debt 中文说明

AI Debt 是一个 local-first 的 AI-assisted build 认知债账本。它帮助 AI Builder 看清 AI agent 代自己完成了哪些判断、哪些决策需要复盘，以及哪些已确认的理解缺口应该进入学习或维护队列。

MVP 覆盖完整闭环：

```text
Claude Code / Codex Hook
  -> Agent Adapter
  -> Normalized AgentEvent
  -> Build Journal
  -> pending_settlement
  -> ai-debt review
  -> Debt Candidate
  -> Evidence Gate
  -> 用户确认
  -> Debt Ledger / Inbox
  -> Learn One
  -> 可跳过的 Grasp Check
  -> Deep Review Markdown 导出
```

## 当前状态

Phase 1、Phase 2、Phase 3 的 MVP 实现已完成：

- Capture core、SQLite state、Build Journal、统一 `AgentEvent`。
- Claude Code 和 Codex 双 primary adapter。
- 用户触发的 review flow 和 Evidence Gate。
- Debt Ledger、Learning Inbox、Learn One、可跳过的 Grasp Check。
- Raw payload cleanup、delete support、journal recovery、Deep Review export。
- 覆盖 Claude Code 和 Codex fixture path 的收敛测试。

## 安装与初始化

当前项目只依赖 Python 标准库。

```bash
python -m ai_debt.cli init
python -m ai_debt.cli init claude-code
python -m ai_debt.cli init codex
```

默认本地状态目录：

```text
~/.ai-debt/
├── config.yaml
├── ai_debt.db
├── journals/
├── logs/
├── exports/
└── hooks/
```

## 常用命令

```bash
python -m ai_debt.cli status
python -m ai_debt.cli doctor
python -m ai_debt.cli review
python -m ai_debt.cli review --analysis-file result.json
python -m ai_debt.cli review --action accept --candidate-id <candidate-id>
python -m ai_debt.cli inbox
python -m ai_debt.cli learn-one <debt-id>
python -m ai_debt.cli check <debt-id> --answer "..."
python -m ai_debt.cli export deep-review <session-id>
python -m ai_debt.cli cleanup --dry-run
python -m ai_debt.cli cleanup
python -m ai_debt.cli delete session <session-id>
python -m ai_debt.cli delete debt <debt-id>
```

## Review 流程

`ai-debt review` 不会自动调用后台 LLM。它会输出结构化 review input，供当前 agent 生成 analysis JSON。生成后导入：

```bash
python -m ai_debt.cli review <session-id> --analysis-file result.json
```

只有通过 Evidence Gate 的 candidate 才能被用户确认入账：

```bash
python -m ai_debt.cli review --action accept --candidate-id <candidate-id>
```

## 隐私默认值

AI Debt 默认 local-first：

```yaml
privacy:
  copy_full_transcript: false
  raw_payload_retention_days: 7
```

Raw payload 只作为临时 adapter debugging 产物。cleanup 后，normalized events、evidence refs 和 ledger entries 会保留。

## 测试

```bash
python -B -m unittest discover -s tests -v
```

## MVP 边界

MVP 不包含 desktop app、Terminal Pet、后台自动 LLM analysis、独立 provider/API key 管理、cloud sync、team dashboard、Cursor/OpenCode adapter 或 Anki/Obsidian integration。
