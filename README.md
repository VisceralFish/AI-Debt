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
python -m pip install .
ai-debt init
ai-debt init claude-code
ai-debt init codex
```

Installing the package exposes the native `ai-debt` console command from the
script entry point in `pyproject.toml`.

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
ai-debt status
ai-debt doctor
ai-debt review
ai-debt review --analysis-file result.json
ai-debt review --action accept --candidate-id <candidate-id>
ai-debt inbox
ai-debt learn-one <debt-id>
ai-debt check <debt-id> --answer "..."
ai-debt export deep-review <session-id>
ai-debt cleanup --dry-run
ai-debt cleanup
ai-debt delete session <session-id>
ai-debt delete debt <debt-id>
```

## MCP Server

AI Debt also exposes an MCP stdio server for agents that can call MCP tools directly:

```bash
ai-debt-mcp
```

Development mode:

```bash
python -m ai_debt.mcp_server
```

See [MCP Usage](docs/mcp-usage.md) for the tool list and Codex flow.

## Review Flow

`ai-debt review` does not call a background LLM. It emits a structured review input package for the current agent. After the current agent generates a structured analysis JSON file, import it with:

```bash
ai-debt review <session-id> --analysis-file result.json
```

Only evidence-backed candidates can be accepted into the ledger:

```bash
ai-debt review --action accept --candidate-id <candidate-id>
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
