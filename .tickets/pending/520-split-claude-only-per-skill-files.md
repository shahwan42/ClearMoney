---
id: "520"
title: "Split .claude/claude-only/ into per-skill files if needed"
type: chore
priority: low
status: pending
created: 2026-04-27
updated: 2026-04-27
---

## Description

After `.claude/claude-only/{slash-skills,mcp-cookbook,claude-code-quirks}.md` are
populated by #516, evaluate whether any single file has grown beyond ~150 lines.
If so, split per-skill (e.g. `slash-skills/commit.md`, `slash-skills/review.md`)
so the agent can pull just-in-time references instead of loading every Claude-only
doc on every session.

## Affected User Journeys

`None — internal-only change.`

## Acceptance Criteria

- [ ] Each file in `.claude/claude-only/` is ≤150 lines, or split into sub-files.
- [ ] CLAUDE.md reference table updated to point at sub-files if split occurs.

## Progress Notes

- 2026-04-27: Filed as follow-up from #516. Premature until content stabilizes.
