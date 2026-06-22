# Ownership MCP Spec

## 1. 定位

AI Debt 的主产品形态是 MCP server。CLI 保留为本地初始化、doctor、cleanup、导出和调试入口。

本版本直接重构为 Ownership Debt 主模型，不保留旧 `cognitive_debts` / `debt_candidates` 作为主线，也不做旧数据迁移。旧系统尚未真实使用，优先保持新架构干净。

核心链路：

```text
Agent / MCP client
  -> record_event
  -> review window
  -> ownership profile + control contract
  -> ownership review input
  -> agent-submitted ownership analysis
  -> evidence gate + rank/dedupe
  -> ownership gap candidates
  -> user review action
  -> ownership debts / concepts / checks / report
```

## 2. 设计原则

```text
MCP 是主入口，CLI 是备份入口。
Agent 负责主要语义判断，AI Debt 负责证据、窗口、profile、校验、排序、持久化。
Idle timeout 是 review 触发器，不是任务真实结束证明。
Idle timeout 由状态刷新触发，不是后台常驻 timer。
Ownership analysis 绑定 review window，不直接绑定整个 session。
Concept learning 并入 Ownership Debt，不作为第二套账本。
Candidate 和 accepted debt 分开。
Task Control Report 是单次窗口复盘产物，Ownership Debts 是长期账本。
```

## 3. Review Window

Session 是采集容器，review window 是分析粒度。

状态：

```text
open
idle_detected
pending_ownership_review
analysis_submitted
candidates_ready
reviewed
superseded
```

触发来源：

```text
idle_timeout
explicit_session_end
manual_review
agent_task_complete
```

第一版切分规则：

```text
session_started:
  创建 open window

user_prompt_submitted:
  如果当前 open window 已有 tool_used 或 assistant_stopped，关闭旧 window 为 pending_ownership_review
  创建新 open window

tool_used / assistant_stopped:
  归入当前 open window
  更新 ended_event_id

idle timeout / pending timeout:
  无活动 >= idle_minutes 时，当前 open window 进入 idle_detected
  无活动 >= pending_minutes 时，当前 open/idle window 进入 pending_ownership_review

session_ended:
  当前 open window 进入 pending_ownership_review
```

如果 candidates 已生成后用户继续工作，旧 window 的证据范围不变，新事件进入新的 open window。

当前默认阈值来自 `config.yaml`，未配置时使用：

```text
idle_minutes: 15
pending_minutes: 30
```

当前实现没有后台定时器。Idle / pending 状态是 lazy 刷新的：

```text
MCP get_status / list_sessions 会刷新 session 和 review window 状态。
MCP record_event 在记录事件后会刷新一次状态。
CLI status / review 会刷新状态。
get_pending_review_window 本身只读取当前状态，不主动刷新。
```

因此，如果没有显式 `session_ended`，agent 或 MCP client 应在空闲后先调用 `get_status` 或 `list_sessions`，再调用 `get_pending_review_window`。

## 4. Ownership Profile

Profile 是 project-scoped 配置。`project_id` 默认由 cwd hash 生成，MCP 参数可以覆盖。

默认规则：

```text
project_id = "proj-" + sha256(normalized_cwd).hexdigest()[:12]
无 cwd 时使用 "default"
```

最小结构：

```json
{
  "project_id": "proj-...",
  "role": "independent_developer",
  "project_intent": "local_first_tool",
  "target_ownership_level": "L3",
  "critical_areas": ["data", "privacy", "core_logic"],
  "unacceptable_risks": ["data_loss", "privacy_leak", "unmaintainable"],
  "control_contract": {
    "ai_free_to_handle": ["formatting", "boilerplate", "docs wording"],
    "ai_must_explain": ["data model", "review logic", "debt scoring", "MCP contract"],
    "ai_must_confirm": ["delete data", "privacy policy change", "new dependency", "schema migration"],
    "user_must_own": ["ownership level model", "control gap rules", "local data handling"]
  },
  "tech_familiarity": {}
}
```

第一版 profile 进入 review input，scoring 只轻度使用。

## 5. Ownership Debt Model

### 5.1 Candidate

`ownership_gap_candidates` 保存系统或 agent 认为可能存在的 gap。未经过用户确认，不进入长期账本。

核心字段：

```text
id
review_window_id
session_id
project_id
source_agent

title
summary
dimension
priority
status

task_type
task_label
task_confidence

control_point
gap_type
gap_reason

required_level
current_level
level_gap

repayment_type
repayment_task

payload_json
score_json
evidence_json
repayment_json
knowledge_json

created_at
updated_at
```

状态：

```text
ready
deferred
rejected_needs_evidence
accepted
ignored
known
```

### 5.2 Debt

`ownership_debts` 是主账本，只保存用户确认需要追回控制权的 gap。

核心字段：

```text
id
project_id
source_session_id
source_review_window_id
source_agent
candidate_id

title
summary
dimension
priority
status
seen_count

task_type
task_label
task_confidence

control_point
gap_type
gap_reason

required_level
current_level
level_gap

repayment_type
repayment_task

payload_json
score_json
evidence_json
repayment_json
knowledge_json
feedback_json

created_at
updated_at
resolved_at
```

状态：

```text
open
in_progress
verified
ignored
```

## 6. Gap Type 与 Dimension

`gap_type` 表示为什么这是 ownership gap。

```text
concept_ownership_gap
unanchored_design_decision
root_cause_gap
risky_file_change
dependency_gap
validation_gap
workaround_gap
integration_gap
refactor_equivalence_gap
```

`dimension` 表示它属于哪个工程或知识领域。

```text
concept
code
architecture
tool
debug
intent
maintenance
verification
data
privacy
dependency
```

`concept_ownership_gap` 合并旧的学习新概念设计。它既可来自 AI 新引入概念，也可来自用户对既有核心概念明显不熟悉。

## 7. Knowledge Context

概念学习不作为第二套账本，而是 Ownership Debt 的一种上下文。

```json
{
  "introduced_concepts": ["MCP stdio framing"],
  "user_familiarity": "unknown",
  "why_needed_for_ownership": "It is the main MCP transport boundary.",
  "minimum_mastery_level": "L2"
}
```

新增 `ownership_concepts` 作为轻量索引，不保存完整学习内容：

```text
id
debt_id
project_id
concept
familiarity
minimum_mastery_level
status
created_at
updated_at
```

## 8. Evidence

继续复用并扩展 `evidence_refs`，不新建第二套证据表。

字段：

```text
id
debt_id
candidate_id
review_window_id
session_id
event_id
kind
ref
role
created_at
```

`role`：

```text
gap_signal
user_anchor
ai_decision
change_evidence
validation_evidence
```

第一版 Evidence Gate：

```text
每个 gap 必须有至少一个 event/diff/transcript/file evidence ref。
高风险 gap 至少需要 change_evidence 或 ai_decision。
缺少证据的 candidate 标记 rejected_needs_evidence。
```

## 9. Ownership Analysis Schema

Agent 通过 MCP 提交 analysis JSON。核心字段严格，辅助字段宽松。

必填：

```json
{
  "window_summary": "string",
  "task_context": {
    "task_type": "creation|maintenance|integration|refactor|experiment",
    "confidence": 0.84,
    "reason": "string"
  },
  "ownership_gaps": [
    {
      "title": "string",
      "summary": "string",
      "dimension": "architecture",
      "control_point": "string",
      "gap_type": "unanchored_design_decision",
      "gap_reason": "string",
      "required_level": "L4",
      "current_level": "L2",
      "priority": "P1",
      "evidence_refs": [
        {"kind": "event", "ref": "agent_events.id=3", "role": "ai_decision"}
      ],
      "repayment": {
        "type": "compare_alternatives",
        "task": "string",
        "validation_criteria": ["string"]
      },
      "knowledge_context": {}
    }
  ]
}
```

本地 rank/dedupe：

```text
priority: P0 > P1 > P2
level_gap 大的优先
risky_file_change / dependency_gap / validation_gap / root_cause_gap 提权
evidence_refs 数量多的优先
重复 control_point + gap_type 合并
ready 默认最多 3 个，其余有效 gap 标记 deferred
```

## 10. MCP Tools

新 MCP surface：

```text
record_event
get_status
get_pending_review_window
get_ownership_profile
update_ownership_profile
get_ownership_review_input
submit_ownership_analysis
review_ownership_gap
list_ownership_debts
learn_one
check
export_task_control_report
cleanup
delete_item
```

移除旧语义工具：

```text
get_review_input
submit_analysis
review_action
list_inbox
export_deep_review
```

`review_ownership_gap` action：

```text
accept
ignore
already_know
defer
```

`check` 接收本地答案、agent assessment 和用户覆盖：

```json
{
  "debt_id": "debt-...",
  "answer": "...",
  "agent_assessment": {
    "result": "partial|verified|needs_followup",
    "reason": "string",
    "missing_points": []
  },
  "user_override": "partial|verified|null"
}
```

没有 agent assessment 时，只记录为 `in_progress`，不使用字数规则判断掌握程度。

## 11. Review Input

`get_ownership_review_input` 返回 window-scoped package。

```json
{
  "review_window": {},
  "ownership_profile": {},
  "control_contract": {},
  "event_summaries": [],
  "diff_snapshot": "...",
  "diff_snapshot_scope": "latest_session_snapshot",
  "changed_files": [],
  "local_hints": {
    "risky_files": [],
    "dependency_changes": [],
    "schema_changes": [],
    "test_or_validation_changes": [],
    "workaround_signals": []
  },
  "existing_related_debts": [],
  "expected_output_schema": {}
}
```

第一版 diff snapshot 仍复用 session journal 的最新 snapshot，后续可升级为 window-scoped diff。

## 12. Task Control Report

`export_task_control_report` 同时返回结构化 JSON 和 Markdown，并可选写文件。

```json
{
  "review_window_id": "win-...",
  "report": {},
  "markdown": "# Task Control Report...",
  "path": "..."
}
```

MCP 默认返回 JSON + Markdown，不强制写文件。CLI export 默认写文件。

报告结构：

```text
# Task Control Report

## Task
类型、摘要、review window、触发方式

## Top Ownership Gaps
最多 3 个 ready gaps

## Deferred / Ignored
非主推候选

## Accepted Debts
用户已入账 debts

## Recovery Tasks
每个 debt 的补债任务和验证标准

## Evidence
关键 event/diff/file refs
```

## 13. 测试要求

```text
schema: migration repeatable and creates ownership tables
window: idle/session_end creates pending review window
profile: default profile uses cwd hash project_id
analysis: valid ownership analysis creates ranked candidates
evidence: missing evidence rejects candidate
review: accept creates ownership_debt and ownership_concepts
review: ignore/already_know/defer update candidate only
learn: concept_ownership_gap returns concept-aware recovery task
check: agent assessment verifies or progresses debt
report: returns JSON + Markdown and optional file
MCP: tools/list exposes ownership tools and removes old review tools
MCP: Codex and Claude fixtures complete ownership flow
privacy: cleanup preserves normalized events, ownership debts and evidence refs
```
