[English](README.md)

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
