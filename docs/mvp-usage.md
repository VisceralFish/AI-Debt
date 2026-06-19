# MVP Usage

## 1. Capture

初始化 adapter：

```bash
python -m ai_debt.cli init claude-code
python -m ai_debt.cli init codex
```

真实接入时，把 `~/.ai-debt/hooks/*-hook.ps1` 连接到对应 agent hook。fixture 测试时可直接调用：

```bash
python -m ai_debt.cli hook codex
```

并从 stdin 传入 JSON payload。

## 2. Settlement

`session_ended` 会直接进入 `pending_settlement`。缺少 Stop/SessionEnd 时，`status` 会按 idle 阈值刷新状态；数据库丢失时会从 `journals/*/events.jsonl` 恢复。

## 3. Review

生成 review input：

```bash
python -m ai_debt.cli review
```

把当前 agent 生成的结构化 JSON 保存为 `result.json` 后导入：

```bash
python -m ai_debt.cli review <session-id> --analysis-file result.json
```

确认候选：

```bash
python -m ai_debt.cli review --action accept --candidate-id <candidate-id>
```

## 4. Learn And Check

```bash
python -m ai_debt.cli inbox
python -m ai_debt.cli learn-one <debt-id>
python -m ai_debt.cli check <debt-id> --answer "..."
```

## 5. Export

```bash
python -m ai_debt.cli export deep-review <session-id>
```

输出位于：

```text
~/.ai-debt/exports/deep_review/deep_review_<session-id>.md
```
