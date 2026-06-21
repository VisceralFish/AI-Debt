# MCP Usage

AI Debt 的 MCP server 让支持 MCP 的 AI coding agent 直接调用 AI Debt core。它不替代 CLI，也不自动调用后台 LLM。

## 启动

安装后使用：

```bash
ai-debt-mcp
```

开发模式可直接运行：

```bash
python -m ai_debt.mcp_server
```

MCP server 走 stdio JSON-RPC，暴露 tools 和 resources。

## Tools

```text
record_event
get_status
list_sessions
get_review_input
submit_analysis
review_action
list_inbox
learn_one
check
export_deep_review
cleanup
delete_item
```

## 典型 Codex Flow

```text
1. record_event(adapter="codex", payload={...SessionStart...})
2. record_event(adapter="codex", payload={...PostToolUse...})
3. record_event(adapter="codex", payload={...SessionEnd...})
4. get_status()
5. get_review_input(session_id)
6. Codex 使用当前上下文生成 analysis JSON
7. submit_analysis(session_id, analysis)
8. review_action(candidate_id, "accept")
9. learn_one(debt_id)
10. check(debt_id, answer 或 skip)
11. export_deep_review(session_id)
```

## Resources

```text
ai-debt://status
ai-debt://sessions/recent
ai-debt://sessions/{session_id}/review-input
ai-debt://inbox
ai-debt://exports/deep-review/{session_id}
```

## 边界

```text
不自动运行 review
不引入独立 provider/API key
不复制完整 transcript
不提供任意 shell 执行能力
cleanup/delete 必须由显式 tool call 触发
```
