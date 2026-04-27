---
id: "516"
title: "Dedupe rule mirrors between .claude/ and .gemini/"
type: chore
priority: low
status: done
created: 2026-04-27
updated: 2026-04-27
---

## Description

`.claude/rules/` and `.gemini/rules/` held near-identical copies of every rule
file (agent-testing, user-journeys, ticketing-workflow, ticket-first-workflow,
qa-guidelines, critical-paths, etc.). Only differences were agent-name tokens
(`Claude` ↔ `Gemini`) and rule-path roots (`.claude/rules` ↔ `.gemini/rules`).

Maintaining two copies via sed is fragile — future edits to one side silently
diverge from the other. Surfaced during ticket #515 where every rule edit
required a manual `sed` mirror step.

## Affected User Journeys

`None — internal-only change.` Tooling/process docs; no runtime surface.

## Decision

Option 3 (portable single source) with a three-tier layout:
- `.ai/rules/` — canonical, agent-neutral shared rules (18 files)
- `.claude/rules` → `../.ai/rules` symlink (mode 120000)
- `.gemini/rules` → `../.ai/rules` symlink (mode 120000)
- `AGENTS.md` (root) — open-standard pointer for Codex/OpenCode/Aider/future agents
- `GEMINI.md` → `AGENTS.md` symlink (mode 120000)
- `.claude/claude-only/` — Claude Code-specific material (slash skills, MCP cookbook, CLI tips)

## Acceptance Criteria

- [x] Decision recorded in ticket on which option ships.
- [x] Mirror drift impossible: both `.claude/rules` and `.gemini/rules` are symlinks to same `.ai/rules/` dir.
- [x] No information loss — both agents still get correct paths and tooling refs via symlinks.

## Progress Notes

- 2026-04-27: Filed as follow-up from #515.
- 2026-04-27: Started — Implementing portable multi-agent layout per plan in .ai-output/claude/portable-multi-agent-rules-plan.md.
- 2026-04-27: Completed — `.ai/rules/` created (18 files via git mv), symlinks established, portable wording applied, AGENTS.md written, GEMINI.md symlinked, CLAUDE.md updated, claude-only docs created, tickets #519/#520 filed.
