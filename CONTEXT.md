# AI Debt

AI Debt is a product context for managing the understanding gap created during AI-assisted build sessions. The glossary keeps product language centered on the user's grasp, not on code quality scoring.

## Language

**Cognitive Debt**:
A gap in the user's understanding, judgment, or maintainability confidence after accepting AI-generated code, designs, explanations, fixes, or decisions.
_Avoid_: Technical debt, learning debt, understanding debt

**CognitiveDebtItem**:
A ledger item that records one evidence-backed instance of cognitive debt, including its concept, source session, priority, status, and debt dimension.
_Avoid_: Intent debt item, learning item, debt card

**Debt Dimension**:
A classification inside a `CognitiveDebtItem` that names what kind of understanding gap exists, such as concept, code, architecture, tool, debug, intent, maintenance, or verification.
_Avoid_: Separate debt type, standalone product object

**Intent Debt**:
The intent dimension of cognitive debt, where the user has accepted a design decision or trade-off without understanding the rationale, rejected alternatives, assumptions, or failure conditions.
_Avoid_: Standalone intent debt object

**Terminal Companion**:
A command-driven terminal surface for showing AI Debt state through status lines, bubbles, and TUI cards while keeping the cognitive debt ledger as the source of truth.
_Avoid_: Pet, desktop pet, floating companion

**Build Journal**:
An append-only record of raw AI build events, transcript references, event summaries, and project snapshots used for evidence, recovery, and later cognitive debt analysis.
_Avoid_: Full transcript copy, chat export

**Raw Payload**:
The original hook event payload kept temporarily for adapter debugging and evidence traceability before being reduced to normalized events and evidence references.
_Avoid_: Permanent transcript archive, source of truth

**Debt Ledger**:
The durable state store for cognitive debt items, inbox entries, review actions, and grasp check results.
_Avoid_: Raw journal, transcript store

**Pending Settlement**:
A session state indicating that a build journal has cooled down and is ready for user-triggered LLM analysis, but no review has been generated yet.
_Avoid_: Pending review

**Review Command**:
The command-driven entry point that settles the most recent pending session by default, or asks the user to choose when multiple pending sessions exist.
_Avoid_: Automatic review, background analysis

**Debt Candidate**:
An LLM-proposed cognitive debt item that has passed evidence checks but has not yet been accepted into the ledger by the user.
_Avoid_: Ledger item, confirmed debt

**Review Action**:
A user's decision on a debt candidate, such as accepting it into the ledger, skipping it, marking it as already known, or opening learn-one.
_Avoid_: Grasp check result, debt status

**Learn One**:
A short L2 learning flow focused on one debt candidate or ledger item, used before or after the item is accepted into the ledger.
_Avoid_: Full course, deep review

**Grasp Check**:
A skippable quick check that follows learn-one by default and updates understanding status only when the user chooses to answer.
_Avoid_: Mandatory quiz, production readiness gate

**Deep Review Export**:
A Markdown-only L3 output for deeper review that is generated as an artifact rather than handled as an interactive TUI flow.
_Avoid_: Interactive L3, learning path

**Agent Adapter**:
A primary integration layer that converts a supported AI coding tool's hook payloads, tool events, session metadata, and transcript references into AI Debt's normalized build events.
_Avoid_: Plugin, client-specific core logic

**Primary Adapter**:
A supported adapter that must pass the same core capture, recovery, review, and ledger contract tests as every other primary adapter.
_Avoid_: Beta adapter, best-effort integration

**LLM-based Analyzer**:
The analysis layer that reuses the active AI coding agent's model context to propose cognitive debt candidates, reviews, learn-one explanations, and grasp checks while respecting deterministic evidence gates.
_Avoid_: Pure static analyzer, rule-only scorer

**Evidence Gate**:
A small deterministic rule that decides whether an LLM-proposed cognitive debt item has enough traceable support to enter the ledger.
_Avoid_: Debt scoring engine, full heuristic analyzer

**Status Line**:
A minimal hook-time notification that reports AI Debt state without opening an interactive review or inserting a TUI card.
_Avoid_: Pop-up, active review, companion bubble
