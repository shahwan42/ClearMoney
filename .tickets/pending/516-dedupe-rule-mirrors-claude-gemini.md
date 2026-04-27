---
id: "516"
title: "Dedupe rule mirrors between .claude/ and .gemini/"
type: chore
priority: low
status: pending
created: 2026-04-27
updated: 2026-04-27
---

## Description

`.claude/rules/` and `.gemini/rules/` hold near-identical copies of every rule
file (agent-testing, user-journeys, ticketing-workflow, ticket-first-workflow,
qa-guidelines, critical-paths, etc.). Only differences are agent-name tokens
(`Claude` ↔ `Gemini`) and rule-path roots (`.claude/rules` ↔ `.gemini/rules`).

Maintaining two copies via sed is fragile — future edits to one side silently
diverge from the other. Surfaced during ticket #515 where every rule edit
required a manual `sed` mirror step.

## Affected User Journeys

`None — internal-only change.` Tooling/process docs; no runtime surface.

## Options to Evaluate

1. **Symlink one side to the other.** Pick a canonical home (e.g. `.claude/rules/`)
   and symlink `.gemini/rules/<file>` → `../../.claude/rules/<file>`. Pros:
   trivial. Cons: kills the agent-name token differences (would force one agent
   to read its sibling's name).
2. **Single source + generator.** Keep canonical source in `rules/` (root) with
   `{{AGENT}}` and `{{RULES_ROOT}}` placeholders; generate both copies via a
   make target (`make rules-sync`) and a pre-commit hook. Pros: clean. Cons:
   build step.
3. **Drop agent-name customization.** Accept "AI agent" as generic term; one
   set of files, both agents read same path via shared symlink. Pros: simplest
   long-term. Cons: rule files reference Claude-specific tooling (e.g. /commit,
   /review skills) that Gemini may not have.

## Acceptance Criteria

- [ ] Decision recorded in ticket on which option ships.
- [ ] Mirror drift impossible (or detected by CI) after change.
- [ ] No information loss — both agents still get correct paths and tooling refs.

## Progress Notes

- 2026-04-27: Filed as follow-up from #515.
