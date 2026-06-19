# Adapter Contract

Adapter 只负责把 agent-specific hook payload 转换为统一 `AgentEvent`，不做认知债分析、Ledger 更新、Learn One 或 Grasp Check。

## Source

MVP primary adapter:

```text
claude_code
codex
```

## Event Types

```text
session_started
user_prompt_submitted
tool_used
assistant_stopped
session_ended
```

所有事件必须包含：

```text
type
source
session_id
raw_payload_ref
occurred_at
```

`session_started` 还必须包含 `cwd`。`tool_used` 还必须包含 `tool_name`。

## Hook 行为

hook 从 stdin 读取 JSON payload，写入 raw payload 文件，再 append normalized `events.jsonl`，最后更新 SQLite state。hook 最多输出一行 status line，不自动触发 review。
