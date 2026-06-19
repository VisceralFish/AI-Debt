# AI Debt 系统设计文档（v7）

> v7 是基于 v6 review 和后续产品决策的收敛版。它替代 v6 中关于 `pending_review`、Terminal Companion、MVP 范围、Codex 支持、Intent Debt 和分析引擎的旧表述。

---

# 0. 一句话结论

**AI Debt 是一个面向 AI Builder 的 Session 级认知债管理工具。**

它在用户使用 Claude Code、Codex 等 AI coding agent 进行 Build、Debug、Refactor、Design 的过程中，通过 Hook 静默记录 Build Journal，捕获 AI 代劳点、工具调用、diff 快照和关键决策引用；当 Session 冷却后进入 `pending_settlement`，用户通过命令式 TUI 触发 LLM-based review，确认 CognitiveDebtItem，并通过 Learn One、Grasp Check、Learning Inbox 和 Debt Ledger 偿还认知债。

核心公式：

```text
AI Debt = Journal-first + LLM-based Analyzer + Evidence Gate + Command-driven Review
```

产品边界：

```text
AI Debt 不主要问代码有没有债。
AI Debt 问：AI 帮你完成之后，你是否仍然掌握系统的意图、边界、失败路径和维护方法。
```

---

# 1. v7 收敛结论

## 1.1 核心定位

AI Debt 的核心对象是 **Cognitive Debt**，不是传统技术债、代码质量分、repo dashboard 或 quiz plugin。

技术债信号仍然有价值，但只作为认知债判断的辅助证据。例如：

```text
AI 修改了认证刷新逻辑
  -> 技术信号：高风险路径变化
  -> 认知债问题：用户是否理解 token refresh 的失败路径和恢复策略
```

## 1.2 Intent Debt 的定位

`Intent Debt` 不是独立产品对象。它是 `CognitiveDebtItem` 的一个 `debt_dimension`。

统一对象：

```ts
type DebtDimension =
  | "concept"
  | "code"
  | "architecture"
  | "tool"
  | "debug"
  | "intent"
  | "maintenance"
  | "verification";
```

原因：

1. 产品语言必须围绕认知债收敛。
2. Intent、debug、tool、maintenance 都是理解缺口的不同维度。
3. Ledger 只需要管理一个长期对象：`CognitiveDebtItem`。

## 1.3 MVP 范围

MVP 不再只验证 capture，而是验证完整认知债闭环。

MVP 包含：

```text
Claude Code primary adapter
Codex primary adapter
Normalized AgentEvent
Build Journal: JSONL raw event stream
Debt Ledger: SQLite durable state
Idle detection -> pending_settlement
Command-driven Terminal Companion
ai-debt status
ai-debt review
Debt Candidate confirmation
Learning Inbox
Learn One
Skippable quick Grasp Check
Markdown Deep Review Export
```

MVP 不包含：

```text
Terminal pet
Desktop floating companion
主动插入 TUI 气泡
Cursor / OpenCode adapter
复杂 adaptive profile
dashboard
Anki / Obsidian deep integration
L4 learning path
独立 provider / API key 配置
后台自动 LLM analysis
```

## 1.4 双 primary adapter

Claude Code 和 Codex 都是 MVP primary adapter。两者必须通过同一套 core contract tests。

```text
Claude Code adapter != beta
Codex adapter != beta
```

差异必须被限制在 Adapter 层，Core 只能消费 normalized `AgentEvent`。

---

# 2. 产品原则

## 2.1 默认干中记

构建过程中默认静默记录，不教学、不阻塞、不弹交互卡片。

Hook 只做：

```text
capture event
normalize event
append journal
update session activity
optionally print one status line
```

## 2.2 按需干中学

用户主动运行命令后，系统才进入 review、learn-one 或 check。

命令式入口：

```bash
ai-debt status
ai-debt review
ai-debt inbox
ai-debt learn-one
ai-debt check <debt-id>
ai-debt export deep-review
```

## 2.3 事后集中学

AI Debt 不把 learning 变成构建阻塞项。Session 冷却后进入 `pending_settlement`，用户在合适时机触发 review。

## 2.4 LLM-based，但有证据门

AI Debt 是 LLM-based Analyzer，不是 rule-only scanner。

LLM 负责：

```text
识别 AI delegation points
生成 Debt Candidate
生成 L1 review
生成 Learn One
生成 Grasp Check
评估用户回答
生成 Markdown Deep Review Export
```

少量 deterministic rules 负责：

```text
Evidence Gate
Privacy Gate
Raw Payload retention
State machine
Priority cap
Deletion / retention
Adapter contract validation
```

核心约束：

```text
LLM 可以提出候选，但没有 evidence 的候选不能进入 Ledger。
```

---

# 3. 核心术语

## 3.1 CognitiveDebtItem

`CognitiveDebtItem` 是 Ledger 中的长期对象，记录一个 evidence-backed 的认知债。

最小字段：

```ts
type CognitiveDebtItem = {
  id: string;
  concept: string;
  debt_dimension: DebtDimension;
  source_session_id: string;
  source_agent: "claude_code" | "codex";
  why_it_matters: string;
  evidence_refs: EvidenceRef[];
  priority: "P0" | "P1" | "P2";
  status: "unverified" | "partial" | "solid" | "resolved";
  seen_count: number;
  created_at: string;
  updated_at: string;
  resolved_at?: string | null;
};
```

## 3.2 Debt Candidate

`Debt Candidate` 是 LLM 提出的候选债务。它已经通过 evidence gate，但还没有被用户接受进入 Ledger。

候选动作：

```text
accept
skip
already know
learn one
```

`already know` 不强制 Grasp Check，只记录 `ReviewAction = dismissed_as_known`。

## 3.3 Pending Settlement

`pending_settlement` 表示：

```text
Session 已经冷却，可以复盘；
但 LLM review 还没有生成。
```

它不是 `pending_review`。Review 只有在用户运行 `ai-debt review` 后才生成。

## 3.4 Terminal Companion

MVP 的 Terminal Companion 是 **command-driven terminal surface**。

包含：

```text
status line
command TUI
review candidate card
learn-one card
quick check card
```

不包含：

```text
pet
desktop floating window
animation
personality system
主动插入当前 agent 输出流的 TUI card
```

---

# 4. 总体架构

```text
┌─────────────────────────────────────────────┐
│ Agent Tools                                  │
│ Claude Code / Codex                          │
└─────────────────────────────────────────────┘
                    │ hooks
                    ▼
┌─────────────────────────────────────────────┐
│ Primary Agent Adapters                       │
│ claude-code adapter / codex adapter          │
└─────────────────────────────────────────────┘
                    │ normalized AgentEvent
                    ▼
┌─────────────────────────────────────────────┐
│ Build Journal                                │
│ events.jsonl + raw payload retention          │
└─────────────────────────────────────────────┘
                    │ snapshots / refs
                    ▼
┌─────────────────────────────────────────────┐
│ Core State                                   │
│ SQLite: sessions, ledger, inbox, actions     │
└─────────────────────────────────────────────┘
                    │ user command
                    ▼
┌─────────────────────────────────────────────┐
│ Command-driven Terminal Companion            │
│ status / review / inbox / learn-one / check  │
└─────────────────────────────────────────────┘
                    │ prompt current agent
                    ▼
┌─────────────────────────────────────────────┐
│ LLM-based Analyzer                           │
│ candidates / review / learn-one / check      │
└─────────────────────────────────────────────┘
                    │ evidence gate
                    ▼
┌─────────────────────────────────────────────┐
│ Debt Ledger                                  │
│ CognitiveDebtItem + ReviewAction + Check     │
└─────────────────────────────────────────────┘
```

---

# 5. Adapter-first 设计

## 5.1 Adapter 职责

Adapter 负责把 agent-specific hook payload 转成统一 `AgentEvent`。

Adapter 做：

```text
读取 hook stdin
识别 source
抽取 session_id / turn_id / cwd / transcript reference
抽取 tool summary / changed files hints
保留 raw payload
写入 normalized AgentEvent
```

Adapter 不做：

```text
认知债分析
Ledger 更新
Learn One
Grasp Check
长期状态判断
```

## 5.2 AgentEvent

MVP 统一事件模型：

```ts
type AgentSource = "claude_code" | "codex";

type AgentEvent =
  | {
      type: "session_started";
      source: AgentSource;
      session_id: string;
      cwd: string;
      transcript_ref?: string;
      raw_payload_ref: string;
      occurred_at: string;
    }
  | {
      type: "user_prompt_submitted";
      source: AgentSource;
      session_id: string;
      turn_id?: string;
      prompt_summary?: string;
      raw_payload_ref: string;
      occurred_at: string;
    }
  | {
      type: "tool_used";
      source: AgentSource;
      session_id: string;
      turn_id?: string;
      tool_name: string;
      files?: string[];
      tool_summary?: string;
      raw_payload_ref: string;
      occurred_at: string;
    }
  | {
      type: "assistant_stopped";
      source: AgentSource;
      session_id: string;
      turn_id?: string;
      last_message_summary?: string;
      raw_payload_ref: string;
      occurred_at: string;
    }
  | {
      type: "session_ended";
      source: AgentSource;
      session_id: string;
      raw_payload_ref: string;
      occurred_at: string;
    };
```

## 5.3 Tool event 不能作为完整事实源

Claude Code 和 Codex 的 tool event 覆盖范围、字段和版本稳定性都不同。因此 Core 不能只相信 hook payload。

MVP 必须同时记录：

```text
tool event summary
git diff snapshot
changed files snapshot
cwd
transcript reference
```

当 tool event 不完整时，diff snapshot 是 evidence fallback。

---

# 6. Build Journal 与隐私

## 6.1 Build Journal 内容

Build Journal 使用 append-only JSONL。

保存：

```text
normalized AgentEvent
raw hook payload reference
transcript_path / transcript reference
event summary
diff snapshot
changed files snapshot
session metadata
```

不保存：

```text
full transcript copy
full chat export
```

## 6.2 Raw Payload retention

Raw Payload 用于 adapter debugging 和 traceability，不是长期事实源。

默认策略：

```yaml
privacy:
  copy_full_transcript: false
  raw_payload_retention_days: 7
```

7 天后保留：

```text
normalized AgentEvent
evidence refs
diff snapshot summary
ledger records
review actions
```

删除：

```text
raw hook payload
```

## 6.3 Local-first

MVP 默认本地存储和本地分析。LLM 能力复用当前 active AI coding agent，不引入独立 provider/API key。

---

# 7. 状态机

MVP session 状态：

```text
recording
  ↓ no activity threshold reached
idle_detected
  ↓ journal closed for settlement
pending_settlement
  ↓ user runs ai-debt review
settling
  ↓ candidates generated
candidates_ready
  ↓ user actions completed
reviewed
```

`pending_settlement` 只表示 session 已准备好被 review。它不表示 review 已生成。

## 7.1 Idle detection

MVP 建议阈值：

```text
15 分钟无活动：idle_detected
30 分钟无活动：pending_settlement
```

Idle 只改变状态，不自动调用 LLM。

## 7.2 Status Line

Hook 结束时可以输出一行最小提示：

```text
AI Debt: 1 session ready for review. Run `ai-debt review`.
```

Status Line 不能：

```text
打开交互 review
显示 TUI card
插入学习内容
主动调用 LLM
```

---

# 8. Review Flow

## 8.1 ai-debt status

输出当前状态：

```text
AI Debt
recording: 1 current session
pending settlement: 1
unresolved debts: 4
next: ai-debt review
```

## 8.2 ai-debt review

默认行为：

```text
0 个 pending_settlement:
  no sessions ready for review

1 个 pending_settlement:
  直接 settle 最近 session

多个 pending_settlement:
  显示列表，默认高亮最近一个
```

Review 步骤：

```text
读取 Build Journal
读取 transcript reference / diff snapshot / event summaries
请求当前 agent 生成 Debt Candidate
运行 Evidence Gate
显示 candidate TUI
用户确认 action
写入 Ledger / ReviewAction
```

## 8.3 Candidate TUI

示例：

```text
AI Debt Review

P1  Hook / MCP / Skill boundary
Dimension: architecture
Why: AI made the tool-boundary decision during this build.
Evidence:
  - user asked whether the whole service should be MCP
  - assistant proposed Hook / Skill / MCP split
  - no follow-up explanation from user

[a] accept  [l] learn one  [k] already know  [s] skip
```

## 8.4 Review Action

```text
accept:
  write CognitiveDebtItem to Ledger

skip:
  do not write Ledger item
  record skipped action

already know:
  do not write Ledger item
  record dismissed_as_known
  do not force Grasp Check

learn one:
  open L2 flow for candidate or ledger item
```

---

# 9. Learn One 与 Grasp Check

## 9.1 Learn One

Learn One 是 L2。它可以作用于：

```text
Debt Candidate
CognitiveDebtItem
```

输出：

```text
一段短解释
为什么重要
一个最小例子或 trace
一个 quick check
```

## 9.2 Grasp Check

Learn One 结束后默认给 quick Grasp Check，但用户可跳过。

```text
answer:
  LLM evaluates answer
  update status if applicable

skip:
  no status upgrade
```

状态更新：

```text
unverified -> partial
partial -> solid
solid -> resolved
```

MVP 不把 Grasp Check 当 production readiness gate。

## 9.3 Deep Review Export

L3 不做交互式 TUI，只做 Markdown artifact。

```bash
ai-debt export deep-review
```

输出：

```text
deep_review_<session_id>.md
```

内容：

```text
session summary
delegation points
accepted debts
skipped candidates
intent rationale
risk and alternatives
recommended next checks
```

---

# 10. 数据存储

## 10.1 本地目录

```text
~/.ai-debt/
├── config.yaml
├── ai_debt.db
├── journals/
│   └── <session_id>/
│       ├── events.jsonl
│       ├── raw_payloads/
│       ├── diff.patch
│       ├── changed_files.json
│       └── session_meta.json
├── exports/
│   └── deep_review/
└── logs/
```

## 10.2 SQLite tables

### sessions

```text
id
source
cwd
transcript_ref
started_at
last_activity_at
idle_detected_at
pending_settlement_at
reviewed_at
status
```

### agent_events

```text
id
session_id
source
type
turn_id
summary
raw_payload_ref
occurred_at
```

### cognitive_debts

```text
id
concept
debt_dimension
source_session_id
source_agent
why_it_matters
priority
status
seen_count
created_at
updated_at
resolved_at
```

### evidence_refs

```text
id
debt_id
candidate_id
session_id
event_id
kind
summary
ref_path
created_at
```

### debt_candidates

```text
id
session_id
concept
debt_dimension
why_it_matters
priority
llm_output_json
evidence_gate_status
created_at
```

### review_actions

```text
id
candidate_id
debt_id
action
created_at
```

### grasp_checks

```text
id
debt_id
candidate_id
question
user_answer
llm_feedback
result
created_at
```

### inbox_items

```text
id
debt_id
status
rank_reason
next_review_at
created_at
```

---

# 11. LLM Prompt Contract

## 11.1 analyze session

输入给当前 agent 的材料必须是有限、可追溯的：

```text
session summary
event summaries
diff snapshot
changed files
transcript refs
existing related debts
user profile basics
```

输出必须是结构化 JSON：

```json
{
  "session_summary": "...",
  "delegation_points": [],
  "debt_candidates": [
    {
      "concept": "...",
      "debt_dimension": "architecture",
      "why_it_matters": "...",
      "priority": "P1",
      "evidence": [
        {
          "kind": "event",
          "summary": "...",
          "ref": "event_id_or_path"
        }
      ]
    }
  ]
}
```

## 11.2 Evidence Gate

Candidate 必须至少满足：

```text
有 AI delegation point
有 session / event / diff / transcript reference
说明用户理解缺口是什么
说明为什么影响后续维护或判断
```

不允许：

```text
泛泛知识点
没有来源的建议
只基于代码复杂度的技术债
没有用户理解缺口的 refactor 建议
```

---

# 12. MVP 验收标准

## 12.1 Adapter contract

Claude Code 和 Codex 都必须通过：

```text
prompt -> journal event
tool use -> journal event
stop -> journal event
diff snapshot -> captured
idle -> pending_settlement
ai-debt review -> candidates
accept -> ledger item
learn one -> quick check
```

## 12.2 Recovery contract

```text
terminal kill / missing SessionEnd
  -> next ai-debt status detects unfinished journal
  -> session can enter pending_settlement
  -> review can still run
```

## 12.3 Privacy contract

```text
full transcript is not copied
raw payload expires after 7 days
normalized event remains
ledger remains
user can delete session and debts
```

## 12.4 Product contract

MVP 成功条件：

```text
用户能看到 AI 替自己完成了哪些关键判断
用户能确认哪些是认知债
用户能学习一条债
用户能用 quick check 更新掌握状态
用户能在 inbox 里看到未偿还债
```

---

# 13. 风险与对策

## 13.1 LLM 误报

对策：

```text
Evidence Gate
Debt Candidate confirmation
already know action
skip action
```

## 13.2 Hook event 不完整

对策：

```text
raw payload preserved temporarily
normalized event contract
diff snapshot fallback
adapter tests
```

## 13.3 用户觉得烦

对策：

```text
command-driven TUI
no automatic review
no background LLM call
status line only
```

## 13.4 隐私风险

对策：

```text
no full transcript copy
raw payload retention 7 days
local-first
delete support
evidence refs instead of transcript archive
```

## 13.5 产品滑向技术债 scanner

对策：

```text
technical debt as signal only
ledger only stores CognitiveDebtItem
no repo dashboard in MVP
no code-quality score as primary output
```

---

# 14. 最终定义

AI Debt v7 的最终定义：

> AI Debt 是一个 Local-first、LLM-based、Session 级认知债管理工具。它通过 Claude Code 和 Codex primary adapters 以 Journal-first 方式捕获 AI-assisted build 过程，把 agent-specific hook payload 归一化为 Build Journal；Session 冷却后进入 `pending_settlement`，用户通过命令式 Terminal Companion 触发 review。当前 agent 的 LLM 能力生成 Debt Candidate，Evidence Gate 和用户确认决定是否写入 Debt Ledger。用户可通过 Learn One、skippable Grasp Check、Learning Inbox 和 Markdown Deep Review Export 逐步偿还认知债。

一句话：

```text
AI Debt 不是代码债扫描器，而是 AI Builder 的认知债账本。
```
