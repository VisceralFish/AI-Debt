# MCP Plan Spec

> 旧版 MCP 计划，仅作历史参考。当前实现基准见 `docs/ownership-mcp-spec.md`，MCP surface 已切换为 Ownership Debt 语义。

## 1. 目标

为 AI Debt 增加 MCP server 形态，让 Codex、Claude Code 或其他支持 MCP 的 AI coding agent 可以通过 tool call 直接访问 AI Debt core，而不只依赖 shell command 和 hook stdin。

目标不是替换现有 CLI，而是在现有 core 之上新增一层稳定接口：

```text
AI coding agent
  -> MCP tool call
  -> AI Debt MCP server
  -> existing core/review/maintenance modules
  -> SQLite + Build Journal + exports
```

MCP 形态要解决的问题：

```text
1. 当前 agent 可以直接查询 AI Debt status / sessions / inbox。
2. 当前 agent 可以直接提交 normalized 或 raw hook event。
3. 当前 agent 可以直接生成 review input 并提交 analysis JSON。
4. 当前 agent 可以触发 accept / skip / already_know / learn-one / check / export。
5. Core 仍不包含 agent-specific if/else；agent 差异继续限制在 adapter 层。
```

## 2. 非目标

```text
不做后台自动 LLM review
不引入独立 provider/API key
不复制完整 transcript
不做 cloud sync
不做 dashboard
不替代 CLI
不让 MCP server 直接控制 Git 或编辑用户代码
```

## 3. 当前基线

当前实现已经具备可复用 core：

```text
ai_debt.core.capture_payload
ai_debt.review.build_review_input
ai_debt.review.create_candidates
ai_debt.review.apply_review_action
ai_debt.review.list_inbox
ai_debt.review.learn_one
ai_debt.review.record_grasp_check
ai_debt.maintenance.cleanup_raw_payloads
ai_debt.maintenance.delete_session
ai_debt.maintenance.delete_debt
ai_debt.maintenance.export_deep_review
```

MCP server 应只做参数校验、连接管理、结果序列化，不重写业务逻辑。

## 4. MCP Tools

### 4.1 `record_event`

用途：从 agent 提交 raw hook payload，让 AI Debt 走现有 adapter normalizer。

输入：

```json
{
  "adapter": "codex",
  "payload": {
    "event": "SessionStart",
    "session_id": "abc",
    "cwd": "/path/to/project"
  }
}
```

输出：

```json
{
  "event": {
    "type": "session_started",
    "source": "codex",
    "session_id": "abc"
  },
  "status_line": "event captured"
}
```

约束：

```text
adapter 只能是 claude-code 或 codex
payload 必须是 JSON object
不自动触发 review
```

### 4.2 `get_status`

用途：查询当前 AI Debt state。

输入：

```json
{}
```

输出：

```json
{
  "state_home": "~/.ai-debt",
  "counts": {
    "recording": 1,
    "idle_detected": 0,
    "pending_settlement": 2
  },
  "recent_sessions": []
}
```

### 4.3 `list_sessions`

用途：列出最近 sessions，供当前 agent 选择 review 对象。

输入：

```json
{
  "limit": 10,
  "status": "pending_settlement"
}
```

输出：

```json
{
  "sessions": [
    {
      "id": "abc",
      "source": "codex",
      "status": "pending_settlement",
      "last_activity_at": "2026-06-20T00:00:00Z"
    }
  ]
}
```

### 4.4 `get_review_input`

用途：返回某个 session 的 LLM review 输入包。

输入：

```json
{
  "session_id": "abc"
}
```

输出：复用 `build_review_input` 的 JSON 结构。

约束：

```text
不调用 LLM
不生成 candidate
session_id 可省略；省略时选择最近的 pending_settlement
```

### 4.5 `submit_analysis`

用途：提交当前 agent 生成的结构化 analysis JSON，生成 Debt Candidate。

输入：

```json
{
  "session_id": "abc",
  "analysis": {
    "session_summary": "...",
    "delegation_points": [],
    "debt_candidates": []
  }
}
```

输出：

```json
{
  "created": [
    {
      "id": "cand-123",
      "status": "ready",
      "gate_reasons": []
    }
  ]
}
```

约束：

```text
analysis 必须通过 JSON schema 级校验
Evidence Gate 失败的 candidate 标记为 rejected_needs_evidence
不自动 accept
```

### 4.6 `review_action`

用途：对 candidate 执行用户确认动作。

输入：

```json
{
  "candidate_id": "cand-123",
  "action": "accept"
}
```

输出：

```json
{
  "candidate_id": "cand-123",
  "action": "accept",
  "debt_id": "debt-123"
}
```

约束：

```text
action 只能是 accept / skip / already_know
只有 ready candidate 可以 accept
```

### 4.7 `list_inbox`

用途：返回 unresolved / unverified / partial debt items。

输入：

```json
{}
```

输出：

```json
{
  "items": [
    {
      "debt_id": "debt-123",
      "concept": "...",
      "priority": "P1",
      "status": "unverified"
    }
  ]
}
```

### 4.8 `learn_one`

用途：生成某个 candidate 或 debt 的 L2 学习内容。

输入：

```json
{
  "item_id": "debt-123"
}
```

输出：

```json
{
  "id": "debt-123",
  "kind": "debt",
  "concept": "...",
  "short_explanation": "...",
  "why_it_matters": "...",
  "minimal_trace": "...",
  "quick_check_prompt": "..."
}
```

### 4.9 `check`

用途：记录用户 quick Grasp Check 的回答或 skip。

输入：

```json
{
  "debt_id": "debt-123",
  "answer": "...",
  "skip": false
}
```

输出：

```json
{
  "result": "partial"
}
```

### 4.10 `export_deep_review`

用途：导出 L3 Markdown artifact。

输入：

```json
{
  "session_id": "abc"
}
```

输出：

```json
{
  "path": "~/.ai-debt/exports/deep_review/deep_review_abc.md"
}
```

### 4.11 `cleanup`

用途：清理过期 raw payload。

输入：

```json
{
  "dry_run": true
}
```

输出：

```json
{
  "raw_payloads": []
}
```

### 4.12 `delete_item`

用途：删除 session 或 debt。

输入：

```json
{
  "target": "session",
  "id": "abc"
}
```

输出：

```json
{
  "deleted": true
}
```

约束：

```text
target 只能是 session 或 debt
delete session 会删除 journal/raw payload/candidates/evidence refs
delete debt 会更新 inbox 和 review references
```

## 5. MCP Resources

优先暴露只读资源，不暴露可写资源。

建议 resources：

```text
ai-debt://status
ai-debt://sessions/recent
ai-debt://sessions/{session_id}/review-input
ai-debt://inbox
ai-debt://exports/deep-review/{session_id}
```

资源读取必须复用 core 查询函数，不直接拼 SQLite SQL 到 MCP handler 里。

## 6. 安全与隐私

```text
MCP server 默认只访问 ~/.ai-debt
不读取完整 transcript，除非 payload 中已有 transcript_ref
不把 raw payload 作为长期事实源
不自动运行 cleanup/delete，必须由 tool call 显式触发
delete tool 必须返回明确目标和结果
```

MCP server 不应该拥有任意 shell 执行能力。所有操作必须落在 AI Debt 的业务 API 里。

## 7. 当前 Codex Session 的交互方式

MCP 版本完成后，当前 Codex session 可以这样交互：

```text
1. Codex 调用 record_event，提交 session/tool/stop payload。
2. Codex 调用 get_status，查看 pending_settlement 数量。
3. Codex 调用 get_review_input，获取当前 session review input。
4. Codex 用当前模型上下文生成 analysis JSON。
5. Codex 调用 submit_analysis，生成 candidates。
6. 用户决定后，Codex 调用 review_action accept/skip/already_know。
7. Codex 调用 learn_one / check / export_deep_review 完成闭环。
```

如果 agent 本身无法自动把当前 session metadata 暴露给 MCP server，仍需要由 hook 或 wrapper 把 `session_id`、`cwd`、tool summary 等信息传入 `record_event`。

## 8. 实现阶段

### Stage M1: MCP Server Skeleton

范围：

```text
新增 ai_debt/mcp_server.py
实现 stdio MCP server 启动入口
pyproject 增加 ai-debt-mcp script
暴露 get_status / list_sessions
```

验收：

```text
MCP client 可以 list tools
get_status 返回和 CLI status 一致的 counts
不改现有 CLI 行为
```

### Stage M2: Capture And Review Tools

范围：

```text
record_event
get_review_input
submit_analysis
review_action
```

验收：

```text
Codex fixture 可以通过 MCP 完成 capture -> pending_settlement -> candidates_ready -> accepted debt
Evidence Gate 仍拦截无证据 candidate
```

### Stage M3: Learning And Maintenance Tools

范围：

```text
list_inbox
learn_one
check
export_deep_review
cleanup
delete_item
```

验收：

```text
MCP path 可以完成 ledger -> inbox -> learn/check -> export
cleanup dry-run 不删除文件
delete session/debt 行为和 CLI 一致
```

### Stage M4: Docs And Convergence

范围：

```text
docs/mcp-usage.md
README 增加 MCP quick start
MCP + CLI 收敛测试
```

验收：

```text
同一 fixture 通过 CLI 和 MCP 得到一致 state transition
Claude Code / Codex 两条 adapter path 都通过 MCP contract test
```

## 9. 测试计划

```text
unit: MCP tool input validation
unit: JSON result serialization
contract: list tools includes required tools
contract: record_event codex fixture -> AgentEvent
contract: record_event claude-code fixture -> AgentEvent
integration: MCP get_review_input -> submit_analysis -> review_action
integration: MCP learn_one -> check -> inbox update
integration: MCP export_deep_review writes markdown
convergence: CLI path and MCP path produce same session/debt counts
privacy: MCP cleanup preserves normalized events and ledger
```

## 10. 完成定义

MCP 版本完成时必须满足：

```text
1. 支持 MCP client 直接调用 AI Debt core。
2. 不破坏现有 CLI/hook 使用方式。
3. 不引入后台自动 LLM analysis。
4. 不引入独立 provider/API key。
5. Claude Code 和 Codex fixture 都能通过 MCP path 进入同一套 Core review flow。
6. CLI 与 MCP 的收敛测试通过。
```
