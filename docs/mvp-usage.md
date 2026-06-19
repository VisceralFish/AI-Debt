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

## 2. Settlement

`session_ended` 会直接进入 `pending_settlement`。缺少 Stop/SessionEnd 时，`status` 会按 idle 阈值刷新状态；数据库丢失时会从 `journals/*/events.jsonl` 恢复。

## 3. Review

生成 review input：

```bash
ai-debt review
```

把当前 agent 生成的结构化 JSON 保存为 `result.json` 后导入：

```bash
ai-debt review <session-id> --analysis-file result.json
```

确认候选：

```bash
ai-debt review --action accept --candidate-id <candidate-id>
```

## 4. Learn And Check

```bash
ai-debt inbox
ai-debt learn-one <debt-id>
ai-debt check <debt-id> --answer "..."
```

## 5. Export

```bash
ai-debt export deep-review <session-id>
```

输出位于：

```text
~/.ai-debt/exports/deep_review/deep_review_<session-id>.md
```
