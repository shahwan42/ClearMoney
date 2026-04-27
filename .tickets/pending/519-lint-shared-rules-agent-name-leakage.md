---
id: "519"
title: "Pre-commit hook: lint .ai/rules/ for agent-name leakage"
type: chore
priority: low
status: pending
created: 2026-04-27
updated: 2026-04-27
---

## Description

Add a pre-commit hook (or `make lint-rules` target) that greps `.ai/rules/**/*.md`
for the literal tokens `Claude`, `Gemini`, `Codex`, `OpenCode`, `Aider` and fails
the commit if any are found in agent-neutral contexts. Whitelist legitimate references
(e.g., "Claude Code" as the IDE product name in attribution lines) via a small
allowlist comment marker.

## Affected User Journeys

`None — internal-only change.` Tooling/process. No runtime surface.

## Acceptance Criteria

- [ ] `make lint-rules` (or pre-commit hook) fails on new agent-name token in `.ai/rules/`.
- [ ] Allowlist covers "Claude Code" product name (used in tool attribution).
- [ ] CI runs the check.

## Progress Notes

- 2026-04-27: Filed as follow-up from #516. Not a launch blocker; protects future drift.
