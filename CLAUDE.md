# CLAUDE.md

Persistent project instructions for Claude Code in this repository. Follow these rules in every session.

- ALWAYS critique your answer before giving it — check it for flawed assumptions, gaps, or better alternatives before responding

# AARA Project Working Rules

## Documentation Rules

- Always read docs/DOCUMENT_INDEX.md first if it exists.
- Always read docs/AI_AGENT_GUIDELINES.md if it exists.
- Do not scan the entire docs directory unless explicitly requested.
- Prefer existing canonical documents over creating new documents.
- Before creating a new document, check DOCUMENT_INDEX.md.
- Keep documentation concise.
- Avoid duplicate architecture/product documents.
- Before claiming any doc is accurate/up to date, run `python tools/verify_docs.py --path <file or
  docs/>` — it catches dead file references and stale "(N lines)" claims mechanically. It cannot
  verify prose (test counts, config values, cache TTLs, cadence claims) — those still require reading
  the actual source and cross-checking by hand. (Added 2026-09-18 after a resume review found
  `docs/ARCHITECTURE.md` claiming 535 tests/8 tables/15 modules against a real 1,441/21/32 — a doc-vs-
  code drift that had gone unnoticed for ~3 months. Root cause was claiming a doc was "verified" after
  reading it for plausibility, not after checking it against the actual filesystem/config/workflow
  files it described.)

## Architecture Rules

- ADR documents are authoritative decisions.
- Frozen architecture documents must not be modified without explicit approval.
- Do not modify dashboard/ unless an ADR allows it.
- Respect sentinel_engine boundaries.
- Do not introduce dependencies across protected boundaries.

## Coding Rules

- Inspect existing architecture before implementation.
- Follow constructor injection patterns.
- Do not add business logic to UI layers.
- Keep read/write boundaries separated.
- Add tests with every implementation change.
- Keep commits small and focused.

## Token Efficiency Rules

- Do not reread unrelated files.
- Prefer summaries and indexes over large document scans.
- Only open files relevant to the current task.
- Do not regenerate documents unnecessarily.
- Use existing documentation references.

## Git Discipline

Before changing code:
- Check current branch.
- Check git status.
- Confirm allowed files.

After changes:
- Run relevant tests.
- Report changed files.
- Confirm no protected files changed.

## Project Context

Project:
AARA Intelligence Platform

Architecture style:
- Decision intelligence platform
- Governance-first
- Evidence-driven
- Human-controlled execution

Core principles:
- Evidence over emotion.
- Auditability over automation.
- Human governance over autonomous action.
