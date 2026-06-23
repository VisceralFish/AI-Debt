[中文说明](README_ch.md)

# AI Debt

AI Debt is a local-first ownership debt ledger for AI-assisted build sessions. It helps AI builders identify which project control points an agent touched, which ownership gaps need review, and which accepted gaps should become recovery tasks.

The MVP covers the full loop:

```text
Claude Code / Codex Hook
  -> Agent Adapter
  -> Normalized AgentEvent
  -> Build Journal
  -> ownership review window
  -> ai-debt review / MCP ownership review
  -> Ownership Gap Candidate
  -> Evidence Gate
  -> user confirmation
  -> Ownership Debt Ledger
  -> Learn One
  -> agent-assessed Check
  -> Task Control Report
```

## Status

The MCP-first ownership MVP is in place:

- Capture core, SQLite state, Build Journal, and normalized `AgentEvent`.
- Claude Code and Codex primary adapters.
- Review windows triggered by explicit session end or idle timeout.
- Ownership profile, ownership gap candidates, ownership debt ledger, and concept index.
- MCP ownership tools for review input, analysis submission, user action, learning, checks, and reports.
- Raw payload cleanup, delete support, recovery from journals, and Task Control Report export.
- Ownership convergence tests for both Claude Code and Codex fixture paths.

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

`ai-debt init <adapter>` also prepares an ownership profile for the current project. In an interactive terminal it asks whether to run the cold-start profile questionnaire; in non-interactive runs or with `--no-profile-setup`, it writes the default project profile. Existing profiles are not overwritten unless you run:

```bash
ai-debt profile setup --force
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
ai-debt status
ai-debt doctor
ai-debt profile show
ai-debt profile setup
ai-debt review
ai-debt review --analysis-file result.json
ai-debt review --action accept --candidate-id <candidate-id>
ai-debt inbox
ai-debt learn-one <debt-id>
ai-debt check <debt-id> --answer "..." --assessment-file assessment.json
ai-debt export task-control <review-window-id>
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

`ai-debt review` does not call a background LLM. It emits a window-scoped ownership review input package for the current agent. After the agent generates ownership analysis JSON, import it with:

```bash
ai-debt review <review-window-id> --analysis-file result.json
```

Only evidence-backed ownership gap candidates can be accepted into the ledger:

```bash
ai-debt review --action accept --candidate-id <candidate-id>
```

Idle timeout can be refreshed lazily or by the local companion watcher. Defaults are `idle_minutes: 15` and `pending_minutes: 30`. `get_status`, `list_sessions`, `ai-debt status`, `ai-debt review`, and `record_event` refresh session/window states; `get_pending_review_window` only reads the current state. To make timeout transitions happen proactively, run:

```bash
ai-debt companion
```

The companion checks every 30 seconds, promotes cooled sessions to `pending_settlement`, marks each ready review window as `analysis_requested`, and prints a one-time local reminder. It does not call an LLM or generate review candidates automatically. Run `ai-debt review` to see the pending window and ask the current agent to analyze it through the AI Debt MCP tools.

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
