[中文说明](README_ch.md)

# AI Debt

AI Debt is a local-first cognitive debt ledger for AI-assisted build sessions. It helps AI builders understand what the agent did on their behalf, which decisions may need review, and which accepted gaps should be tracked as learning or maintenance work.

The MVP covers the full loop:

```text
Claude Code / Codex Hook
  -> Agent Adapter
  -> Normalized AgentEvent
  -> Build Journal
  -> pending_settlement
  -> ai-debt review
  -> Debt Candidate
  -> Evidence Gate
  -> user confirmation
  -> Debt Ledger / Inbox
  -> Learn One
  -> optional Grasp Check
  -> Deep Review Markdown export
```

## Status

Phase 1, Phase 2, and Phase 3 MVP implementation are in place:

- Capture core, SQLite state, Build Journal, and normalized `AgentEvent`.
- Claude Code and Codex primary adapters.
- User-triggered review flow with Evidence Gate.
- Debt Ledger, Learning Inbox, Learn One, and skippable Grasp Check.
- Raw payload cleanup, delete support, recovery from journals, and Deep Review export.
- Convergence tests for both Claude Code and Codex fixture paths.

## Installation

This project currently uses Python standard library only.

```bash
python -m ai_debt.cli init
python -m ai_debt.cli init claude-code
python -m ai_debt.cli init codex
```

Default local state directory:

```text
~/.ai-debt/
├── config.yaml
├── ai_debt.db
├── journals/
├── logs/
├── exports/
└── hooks/
```

## Common Commands

```bash
python -m ai_debt.cli status
python -m ai_debt.cli doctor
python -m ai_debt.cli review
python -m ai_debt.cli review --analysis-file result.json
python -m ai_debt.cli review --action accept --candidate-id <candidate-id>
python -m ai_debt.cli inbox
python -m ai_debt.cli learn-one <debt-id>
python -m ai_debt.cli check <debt-id> --answer "..."
python -m ai_debt.cli export deep-review <session-id>
python -m ai_debt.cli cleanup --dry-run
python -m ai_debt.cli cleanup
python -m ai_debt.cli delete session <session-id>
python -m ai_debt.cli delete debt <debt-id>
```

## Review Flow

`ai-debt review` does not call a background LLM. It emits a structured review input package for the current agent. After the current agent generates a structured analysis JSON file, import it with:

```bash
python -m ai_debt.cli review <session-id> --analysis-file result.json
```

Only evidence-backed candidates can be accepted into the ledger:

```bash
python -m ai_debt.cli review --action accept --candidate-id <candidate-id>
```

## Privacy Defaults

AI Debt is local-first by default:

```yaml
privacy:
  copy_full_transcript: false
  raw_payload_retention_days: 7
```

Raw payloads are temporary adapter-debugging artifacts. Normalized events, evidence references, and ledger entries remain after cleanup.

## Testing

```bash
python -B -m unittest discover -s tests -v
```

## MVP Boundaries

The MVP does not include a desktop app, Terminal Pet, background automatic LLM analysis, independent provider/API key management, cloud sync, team dashboards, Cursor/OpenCode adapters, or Anki/Obsidian integrations.
