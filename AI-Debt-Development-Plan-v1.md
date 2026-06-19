# AI Debt 开发计划（v1）

> 本计划基于 `AI-Debt-System-Design-v7.md`。目标是在 MVP 阶段做出完整认知债闭环，同时保持 Terminal Companion 为命令式 TUI，不做 Terminal Pet 或桌面浮层。

---

# 0. 开发目标

MVP 要验证的不是单点功能，而是完整闭环：

```text
Claude Code / Codex Hook
  -> Agent Adapter
  -> Normalized AgentEvent
  -> Build Journal
  -> pending_settlement
  -> ai-debt review
  -> LLM-generated Debt Candidate
  -> Evidence Gate
  -> user confirmation
  -> Debt Ledger / Inbox
  -> Learn One
  -> skippable Grasp Check
  -> status update / deep review export
```

核心成功标准：

```text
1. Claude Code 和 Codex 都是 primary adapter。
2. Core 不包含 agent-specific if/else。
3. 不复制完整 transcript。
4. Raw payload 默认 7 天保留。
5. LLM 负责认知债判断，rules 只做 evidence、privacy、state gate。
6. 用户确认后才写入 Ledger。
```

---

# Phase 1: Capture Core & Primary Adapters

## 目标

建立 AI Debt 的本地基座：CLI skeleton、配置、SQLite、Build Journal、normalized AgentEvent、Claude Code/Codex 双 primary adapter，以及 `pending_settlement` 状态。

## 范围

### 1. CLI skeleton

命令：

```bash
ai-debt init
ai-debt init claude-code
ai-debt init codex
ai-debt status
ai-debt doctor
```

验收：

```text
ai-debt status 能读取本地 state。
ai-debt doctor 能检查 journal path、db path、adapter hook install 状态。
```

### 2. Local state layout

目录：

```text
~/.ai-debt/
├── config.yaml
├── ai_debt.db
├── journals/
└── logs/
```

验收：

```text
首次运行自动创建目录和 SQLite schema。
重复运行不破坏已有数据。
```

### 3. SQLite schema v1

表：

```text
sessions
agent_events
evidence_refs
debt_candidates
cognitive_debts
review_actions
grasp_checks
inbox_items
```

验收：

```text
schema migration 可重复执行。
基础 CRUD 有单元测试。
```

### 4. Build Journal

实现：

```text
append events.jsonl
write raw_payload_ref
write diff snapshot
write changed_files snapshot
write session_meta.json
```

不做：

```text
复制完整 transcript
长期保存 raw payload
```

验收：

```text
每个 hook event 都能 append normalized event。
raw payload 存在 ref，默认 retention_days = 7。
```

### 5. Normalized AgentEvent contract

事件：

```text
session_started
user_prompt_submitted
tool_used
assistant_stopped
session_ended
```

验收：

```text
Claude Code 和 Codex adapter 输出同一 schema。
Core test 使用 fixture，不依赖真实 agent。
```

### 6. Claude Code primary adapter

支持事件：

```text
SessionStart
UserPromptSubmit
PostToolUse
Stop
SessionEnd
```

验收：

```text
prompt -> event
tool -> event
stop -> event
diff snapshot captured
```

### 7. Codex primary adapter

支持事件：

```text
SessionStart
UserPromptSubmit
PostToolUse
Stop
```

验收：

```text
prompt -> event
tool -> event
stop -> event
diff snapshot captured
```

### 8. Idle detection and pending settlement

状态：

```text
recording
idle_detected
pending_settlement
```

行为：

```text
15 min inactive -> idle_detected
30 min inactive -> pending_settlement
```

验收：

```text
ai-debt status 能显示 pending settlement 数量。
Hook 后最多输出一行 status line。
不自动调用 LLM。
```

## Phase 1 不做

```text
LLM review
Learn One
Grasp Check
Deep Review Export
Terminal Pet
主动 TUI bubble
Cursor/OpenCode adapter
```

## Phase 1 测试

```text
unit: schema, journal writer, event normalizer
contract: Claude fixture -> AgentEvent
contract: Codex fixture -> AgentEvent
integration: fake hook event -> journal -> status
recovery: missing SessionEnd -> pending_settlement
```

## Phase 1 完成定义

```text
Claude Code 和 Codex 都能把真实/fixture hook payload 写成统一 Build Journal。
ai-debt status 能显示 recording / pending_settlement。
Core 没有 agent-specific branch。
```

---

# Phase 2: LLM Review, Ledger & Learning Loop

## 目标

打通用户触发的认知债分析闭环：`ai-debt review` 读取 `pending_settlement`，复用当前 agent 的 LLM 能力生成 Debt Candidate，通过 Evidence Gate 和用户确认写入 Ledger，并支持 Inbox、Learn One、Grasp Check。

## 范围

### 1. Review command

命令：

```bash
ai-debt review
```

行为：

```text
0 pending_settlement -> show empty state
1 pending_settlement -> settle directly
multiple pending_settlement -> show selectable list
default selection -> most recent
```

验收：

```text
review 不自动运行于后台。
review 必须由用户命令触发。
```

### 2. LLM-based Analyzer prompt contract

输入：

```text
session summary
event summaries
diff snapshot
changed files
transcript refs
existing related debts
```

输出：

```text
session_summary
delegation_points
debt_candidates[]
```

验收：

```text
LLM 输出必须是结构化 JSON。
解析失败时保留原始输出并提示重试。
```

### 3. Evidence Gate

规则：

```text
candidate 必须有 delegation point
candidate 必须有 event/diff/transcript ref
candidate 必须描述用户理解缺口
candidate 必须描述 why it matters
```

验收：

```text
无 evidence 的 candidate 不展示为可 accept。
低证据 candidate 可显示为 rejected/needs evidence，但不写 Ledger。
```

### 4. Candidate confirmation TUI

动作：

```text
accept
skip
already know
learn one
```

验收：

```text
accept -> cognitive_debts + evidence_refs + inbox_items
skip -> review_actions
already know -> review_actions dismissed_as_known
learn one -> open L2 flow
```

### 5. Debt Ledger

对象：

```text
CognitiveDebtItem
debt_dimension
priority
status
seen_count
evidence_refs
```

验收：

```text
Ledger 只存 CognitiveDebtItem，不存独立 IntentDebt object。
Intent Debt 只能作为 debt_dimension = intent。
```

### 6. Learning Inbox

命令：

```bash
ai-debt inbox
```

行为：

```text
显示 unresolved / unverified / partial items
按 priority、seen_count、next_review_at 排序
```

验收：

```text
accepted debt 自动进入 Inbox。
resolved debt 不再默认显示。
```

### 7. Learn One

命令：

```bash
ai-debt learn-one
ai-debt learn-one <debt-id>
```

适用对象：

```text
Debt Candidate
CognitiveDebtItem
```

输出：

```text
short explanation
why it matters
minimal trace/example
quick check prompt
```

验收：

```text
candidate learn-one 后可以 accept / skip / already know。
ledger item learn-one 后可以进入 Grasp Check。
```

### 8. Grasp Check

命令：

```bash
ai-debt check <debt-id>
```

行为：

```text
Learn One 后默认展示 quick check
用户可 answer 或 skip
answer -> LLM evaluation
skip -> no status upgrade
```

验收：

```text
用户回答后更新 grasp_checks。
根据结果可更新 debt status。
already know 不强制 Grasp Check。
```

## Phase 2 不做

```text
后台自动 LLM 分析
独立 provider/API key
复杂 adaptive profile
L4 learning path
dashboard
```

## Phase 2 测试

```text
unit: evidence gate
unit: JSON parse and validation
integration: pending_settlement -> candidates_ready
integration: candidate accept -> ledger/inbox
integration: learn-one -> check -> status update
contract: Claude/Codex both use same review pipeline
```

## Phase 2 完成定义

```text
用户可以从 pending settlement 生成 candidate。
用户确认后可入账。
用户可以学习一条债，并通过 skippable quick check 更新状态。
Claude Code 和 Codex 都走同一套 Core review flow。
```

---

# Phase 3: Hardening, Export & MVP Release

## 目标

补齐隐私、清理、导出、doctor、恢复路径和 MVP 级稳定性，形成可交付版本。

## 范围

### 1. Raw payload retention

配置：

```yaml
privacy:
  copy_full_transcript: false
  raw_payload_retention_days: 7
```

命令：

```bash
ai-debt cleanup
```

验收：

```text
过期 raw payload 被删除。
normalized event 和 ledger 保留。
cleanup 有 dry-run 模式。
```

### 2. Delete support

命令：

```bash
ai-debt delete session <session-id>
ai-debt delete debt <debt-id>
```

验收：

```text
删除 session 会删除 journal、raw payload、candidate 和 evidence refs。
删除 debt 会更新 inbox 和 review references。
```

### 3. Deep Review Export

命令：

```bash
ai-debt export deep-review
ai-debt export deep-review <session-id>
```

输出：

```text
exports/deep_review/deep_review_<session_id>.md
```

内容：

```text
session summary
delegation points
accepted debts
skipped candidates
intent rationale
risks and alternatives
recommended next checks
```

验收：

```text
L3 只生成 Markdown，不进入交互式 TUI。
```

### 4. Doctor hardening

命令：

```bash
ai-debt doctor
```

检查：

```text
config exists
db schema valid
journal writable
Claude Code hook installed
Codex hook installed
last hook event received
raw payload cleanup status
```

验收：

```text
doctor 能给出 actionable fix。
不会修改配置，除非用户运行 init。
```

### 5. Recovery hardening

场景：

```text
terminal killed
missing Stop
missing SessionEnd
tool event missing
transcript_ref missing
raw payload expired
```

验收：

```text
能从 events.jsonl 和 diff snapshot 恢复 pending_settlement。
缺 transcript_ref 时 review 仍可基于 event summary + diff snapshot 运行，但提示 evidence weaker。
```

### 6. MVP docs

文档：

```text
README.md
docs/adapter-contract.md
docs/privacy.md
docs/mvp-usage.md
```

验收：

```text
用户能按文档安装 Claude Code 和 Codex adapter。
用户能完成一次 end-to-end review。
```

## Phase 3 不做

```text
Desktop app
Terminal pet
Cursor/OpenCode adapter
cloud sync
team dashboard
Anki/Obsidian integration
L4 path generation
```

## Phase 3 测试

```text
e2e: Claude fixture end-to-end
e2e: Codex fixture end-to-end
e2e: kill recovery
e2e: raw payload cleanup
e2e: deep review export
snapshot: TUI review cards
```

## Phase 3 完成定义

```text
MVP 能在 Claude Code 和 Codex 两条 primary path 上完成 capture -> settlement -> review -> ledger -> learn/check -> export。
隐私默认值符合 v7。
所有关键状态可通过 ai-debt status / doctor 诊断。
```

---

# Phase 总览

| Phase | 名称 | 核心结果 |
|---|---|---|
| Phase 1 | Capture Core & Primary Adapters | 双 primary adapter + Journal + SQLite + pending_settlement |
| Phase 2 | LLM Review, Ledger & Learning Loop | Debt Candidate + Evidence Gate + Ledger + Inbox + Learn One + Grasp Check |
| Phase 3 | Hardening, Export & MVP Release | cleanup/delete/export/doctor/recovery/docs/e2e |

---

# MVP 总体验收

MVP 完成时必须能演示：

```text
1. 在 Claude Code 中完成一次 AI-assisted build，生成 Build Journal。
2. 在 Codex 中完成一次 AI-assisted build，生成 Build Journal。
3. 两边都进入 pending_settlement。
4. 运行 ai-debt review，生成 Debt Candidate。
5. 用户 accept 一条 candidate，写入 Ledger 和 Inbox。
6. 用户 learn one，并选择回答或跳过 quick Grasp Check。
7. 用户 export deep review markdown。
8. raw payload cleanup 不影响 Ledger 和 evidence refs。
```

不能以只跑通单 agent、只生成总结、只输出 Markdown 或没有用户确认入账作为 MVP 完成。
