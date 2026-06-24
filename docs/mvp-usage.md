# MVP Usage

## 1. Capture

初始化 adapter：

```bash
python -m pip install .
ai-debt init claude-code
ai-debt init codex
```

`ai-debt init <adapter>` 会在 hook 初始化后为当前 cwd 的 project profile 做冷启动 setup。交互式终端会询问是否运行问卷；非交互运行或 `--no-profile-setup` 会写入默认 profile。已有 profile 默认不会被 init 覆盖；使用 `--profile-setup` 可从 init 入口强制重跑问卷。

Codex 接入时，`ai-debt init codex` 会默认生成当前项目的 `.codex/hooks.json`，在 `SessionStart`、`UserPromptSubmit` 和 `Stop` 时检查 review 状态。重启 Codex 后使用 `/hooks` 审查并信任这些 hooks；发现 pending review 时，Codex TUI 会显示内部 warning，不需要 Windows Toast 或独立 Companion 窗口。

Claude Code 接入或 fixture 测试时，也可以直接调用生成的 PowerShell hook：

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

idle / pending 状态可以 lazy 刷新，也可以由本地 companion watcher 主动刷新。会触发刷新的是：

```text
ai-debt status
ai-debt review
ai-debt companion
MCP get_status
MCP list_sessions
MCP record_event
```

Codex TUI hooks 会在会话启动、提交新提示或回合结束时检查一次，发现新的 pending review window 后标记为 `analysis_requested` 并显示一次 TUI warning，但不会自动调用 LLM 或生成 review candidates。Codex 当前没有可由项目自定义命令持续刷新的 `statusLine`，所以用户完全不操作时不会按 30 秒刷新；需要这种独立轮询行为时仍可手动运行 `ai-debt companion`。

数据库丢失时会从 `journals/*/events.jsonl` 恢复 normalized events 和 review window。

## 3. Ownership Review

生成 window-scoped ownership review input：

```bash
ai-debt review
```

当 window 还没有 candidates 时，`ai-debt review` 会显示 analysis-needed 指引，让用户要求当前 Claude Code / Codex agent 通过 MCP 执行：

```text
get_ownership_review_input(review_window_id)
submit_ownership_analysis(...)
```

当 candidates 已生成后，`ai-debt review` 才显示 accept / ignore / already_know / defer 的候选审核队列。

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
