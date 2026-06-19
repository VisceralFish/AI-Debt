# Privacy

AI Debt 默认 local-first。MVP 不复制完整 transcript，raw payload 只用于 adapter debugging 和 evidence traceability。

默认配置：

```yaml
privacy:
  copy_full_transcript: false
  raw_payload_retention_days: 7
```

## Cleanup

```bash
ai-debt cleanup --dry-run
ai-debt cleanup
```

cleanup 只删除过期 raw payload。normalized event、Debt Ledger、Inbox、review action 和 evidence ref 会保留。

## Delete

```bash
ai-debt delete session <session-id>
ai-debt delete debt <debt-id>
```

删除 session 会删除该 session 的 journal/raw payload、candidate 和 evidence refs。删除 debt 会删除 inbox/check 状态，并把 review/evidence 中的 debt reference 置空。
