# MVP Usage

## 1. Capture

初始化 adapter：

```bash
python -m pip install .
ai-debt init claude-code
ai-debt init codex
```

真实接入时，把 `~/.ai-debt/hooks/*-hook.ps1` 连接到对应 agent hook。fixture 测试时可直接调用：

```bash
ai-debt hook codex
```

并从 stdin 传入 JSON payload。

## 2. Review Window

`session_ended` 会把当前 open review window 推到 `pending_ownership_review`。缺少 Stop/SessionEnd 时，`status` 会按 idle 阈值刷新；idle timeout 是 review 触发器，不代表任务真实结束。

默认阈值：

```text
idle_minutes: 15
pending_minutes: 30
```

状态变化：

```text
无活动 >= 15 分钟:
  session.status -> idle_detected
  review_window.status -> idle_detected

无活动 >= 30 分钟:
  session.status -> pending_settlement
  review_window.status -> pending_ownership_review
```

当前实现没有后台定时器。idle / pending 状态是 lazy 刷新的，必须由一次命令或 MCP tool call 触发：

```text
ai-debt status
ai-debt review
MCP get_status
MCP list_sessions
MCP record_event
```

如果用户没有显式 Stop/SessionEnd，agent 或 MCP client 应在空闲后先调用 `get_status` 或 `list_sessions`，再调用 `get_pending_review_window`。

数据库丢失时会从 `journals/*/events.jsonl` 恢复 normalized events 和 review window。

## 3. Ownership Review

生成 window-scoped ownership review input：

```bash
ai-debt review
```

把当前 agent 生成的 ownership analysis JSON 保存为 `result.json` 后导入：

```bash
ai-debt review <review-window-id> --analysis-file result.json
```

确认候选：

```bash
ai-debt review --action accept --candidate-id <candidate-id>
ai-debt review --action ignore --candidate-id <candidate-id>
ai-debt review --action already_know --candidate-id <candidate-id>
ai-debt review --action defer --candidate-id <candidate-id>
```

## 4. Learn And Check

```bash
ai-debt inbox
ai-debt learn-one <debt-id>
ai-debt check <debt-id> --answer "..." --assessment-file assessment.json
```

没有 `assessment-file` 时，check 只记录进展，不使用字数规则判断掌握程度。

## 5. Export

```bash
ai-debt export task-control <review-window-id>
```

输出位于：

```text
~/.ai-debt/exports/task_control/task_control_<review-window-id>.md
```
