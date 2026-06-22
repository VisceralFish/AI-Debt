# MCP Usage

AI Debt 的 MCP server 是 Ownership Debt 主入口。它不替代 CLI，也不自动调用后台 LLM；agent 负责生成 ownership analysis，AI Debt 负责证据、窗口、profile、校验、持久化和报告。

## 启动

安装后使用：

```bash
ai-debt-mcp
```

开发模式可直接运行：

```bash
python -m ai_debt.mcp_server
```

## Tools

```text
record_event
get_status
list_sessions
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

## 典型 Codex Flow

```text
1. record_event(adapter="codex", payload={...SessionStart...})
2. record_event(adapter="codex", payload={...PostToolUse...})
3. record_event(adapter="codex", payload={...SessionEnd...})
4. get_pending_review_window()
5. get_ownership_review_input(review_window_id)
6. Codex 使用当前上下文生成 ownership analysis JSON
7. submit_ownership_analysis(review_window_id, analysis)
8. review_ownership_gap(candidate_id, "accept" | "ignore" | "already_know" | "defer")
9. learn_one(debt_id)
10. check(debt_id, answer, agent_assessment)
11. export_task_control_report(review_window_id)
```

## Idle Timeout

MCP server 本身没有后台定时器。Idle timeout 可以由状态读取、事件写入，或本地 `ai-debt companion` watcher 刷新：

```text
record_event 记录事件后会刷新状态
get_status 会刷新状态
list_sessions 会刷新状态
get_pending_review_window 只读取当前状态，不主动刷新
ai-debt companion 每 30 秒主动刷新一次状态
```

默认阈值：

```text
idle_minutes: 15
pending_minutes: 30
```

无活动满 15 分钟后，下一次 `get_status` / `list_sessions` 会把 session 和 review window 标为 `idle_detected`。无活动满 30 分钟后，下一次刷新会把 session 标为 `pending_settlement`，并把 review window 标为 `pending_ownership_review`。

如果 agent 没有发送 `SessionEnd`，且没有运行 `ai-debt companion`，推荐 MCP flow 是：

```text
1. 等待空闲超过 pending_minutes
2. get_status()
3. get_pending_review_window()
4. get_ownership_review_input(review_window_id)
```

## Resources

```text
ai-debt://status
ai-debt://sessions/recent
ai-debt://ownership/debts
ai-debt://ownership/windows/{review_window_id}/review-input
ai-debt://ownership/windows/{review_window_id}/task-control-report
ai-debt://ownership/profiles/{project_id}
```

## 边界

```text
不自动运行 review
不引入独立 provider/API key
不复制完整 transcript
不提供任意 shell 执行能力
cleanup/delete 必须由显式 tool call 触发
```
