[English](README.md)

# AI Debt 中文说明

AI Debt 是一个 local-first 的 AI-assisted build 控制权债账本。它帮助 AI Builder 看清 AI agent 触碰了哪些项目控制点，哪些 Ownership Gap 需要复盘，哪些已确认缺口应该进入恢复任务。

MVP 覆盖完整闭环：

```text
Claude Code / Codex Hook
  -> Agent Adapter
  -> Normalized AgentEvent
  -> Build Journal
  -> ownership review window
  -> ai-debt review / MCP ownership review
  -> Ownership Gap Candidate
  -> Evidence Gate
  -> 用户确认
  -> Ownership Debt Ledger
  -> Learn One
  -> agent-assessed Check
  -> Task Control Report
```

## 当前状态

MCP-first Ownership MVP 已完成：

- Capture core、SQLite state、Build Journal、统一 `AgentEvent`。
- Claude Code 和 Codex 双 primary adapter。
- 显式 session end 或 idle timeout 触发的 review window。
- Ownership profile、ownership gap candidates、ownership debt ledger、concept index。
- MCP ownership tools 覆盖 review input、analysis submission、用户动作、learning、check 和 report。
- Raw payload cleanup、delete support、journal recovery、Task Control Report export。
- 覆盖 Claude Code 和 Codex fixture path 的 ownership 收敛测试。

## 安装与初始化

当前项目只依赖 Python 标准库。

```bash
python -m ai_debt.cli init
python -m ai_debt.cli init claude-code
python -m ai_debt.cli init codex
```

`ai-debt init <adapter>` 会为当前项目准备 ownership profile。交互式终端会询问是否运行冷启动 profile 问卷；非交互运行或使用 `--no-profile-setup` 时，会写入默认 project profile。已有 profile 不会被覆盖，除非显式运行：

```bash
ai-debt profile setup --force
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
python -m ai_debt.cli profile show
python -m ai_debt.cli profile setup
python -m ai_debt.cli review
python -m ai_debt.cli review --analysis-file result.json
python -m ai_debt.cli review --action accept --candidate-id <candidate-id>
python -m ai_debt.cli inbox
python -m ai_debt.cli learn-one <debt-id>
python -m ai_debt.cli check <debt-id> --answer "..." --assessment-file assessment.json
python -m ai_debt.cli export task-control <review-window-id>
python -m ai_debt.cli cleanup --dry-run
python -m ai_debt.cli cleanup
python -m ai_debt.cli delete session <session-id>
python -m ai_debt.cli delete debt <debt-id>
```

## MCP Server

AI Debt 也提供 MCP stdio server，供支持 MCP tools 的 agent 直接调用：

```bash
ai-debt-mcp
```

开发模式可直接运行：

```bash
python -m ai_debt.mcp_server
```

工具列表和 Codex flow 见 [MCP Usage](docs/mcp-usage.md)。

## Review 流程

`ai-debt review` 不会自动调用后台 LLM。它会输出 window-scoped ownership review input，供当前 agent 生成 ownership analysis JSON。生成后导入：

```bash
python -m ai_debt.cli review <review-window-id> --analysis-file result.json
```

只有通过 Evidence Gate 的 ownership gap candidate 才能被用户确认入账：

```bash
python -m ai_debt.cli review --action accept --candidate-id <candidate-id>
```

Idle timeout 可以 lazy 刷新，也可以由本地 companion watcher 主动刷新。默认阈值是 `idle_minutes: 15` 和 `pending_minutes: 30`。`get_status`、`list_sessions`、`ai-debt status`、`ai-debt review` 和 `record_event` 会刷新 session/window 状态；`get_pending_review_window` 只读取当前状态。要让 timeout 主动发生，可以运行：

```bash
ai-debt companion
```

Companion 每 30 秒检查一次，把冷却完成的 session 推进到 `pending_settlement`，把每个待处理 review window 标记为 `analysis_requested`，并只打印一次本地提醒。它不会自动调用 LLM，也不会自动生成 review candidates。运行 `ai-debt review` 可以查看待分析 window，并让当前 agent 通过 AI Debt MCP tools 完成分析。

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
