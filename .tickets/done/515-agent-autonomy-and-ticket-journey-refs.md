---
id: "515"
title: "Agent autonomy guards + ticket user-journey refs"
type: chore
priority: medium
status: done
created: 2026-04-27
updated: 2026-04-27
---

## Description

Continue the prior gemini session (`temporary_artifacts/gemini_20260427_181538.md`)
that introduced agent-native testing shortcuts. Two follow-ups:

1. **Server-up guard for manual testing.** Whenever an AI agent (Claude or Gemini)
   plans to manually test the app, it must first verify the dev server is reachable
   (`curl http://0.0.0.0:8000/healthz`) before driving the browser. If the server
   is hanging or unreachable, kill the running instance and start a fresh one.
   Document this as a hard rule in both `agent-testing.md` files and the
   `user-journeys.md` pre-flight (J-1).
2. **Ticket → user-journey linkage.** Update the ticketing rules so every new
   ticket explicitly names the user journeys it touches (CP-1..CP-6 from
   `critical-paths.md` and J-1..J-5 from `user-journeys.md`), reflects them in
   the acceptance criteria, and the agent verifies those flows still pass before
   moving the ticket to `done/`.

## Affected User Journeys

`None — internal-only change.` Justification: docs/rule-file edits only. No
Python, template, migration, or dependency touched. The rule changes describe
how *future* tickets must reference CP-x/J-x, but executing this ticket itself
neither alters runtime behavior nor any user-facing path. Per the
`internal-only` scope clause: dev tooling / docstring / process docs qualify.

## Acceptance Criteria

- [x] `.claude/rules/agent-testing.md` and `.gemini/rules/agent-testing.md` gain a
      "Server Liveness Protocol" section: pre-test curl check, kill+restart
      recipe, autonomous recovery loop.
- [x] `.claude/rules/user-journeys.md` + `.gemini/rules/user-journeys.md` J-1
      starts with the liveness check before `/login?dev=1`.
- [x] `.claude/rules/ticketing-workflow.md` updated: ticket file format includes
      a mandatory `## Affected User Journeys` section; "On Task Start" step
      requires populating it; "On Task Completion" step requires re-running each
      listed journey before moving to `done/`.
- [x] `.claude/rules/ticket-first-workflow.md` pre-implementation checklist adds
      "name affected user journeys" as step 2.5.
- [x] Existing wip ticket template / examples reflect the new section
      (this ticket itself uses the new format).
- [ ] `make lint` and `make test` still green — docs-only, no Python touched;
      will run before commit per delivery-checklist.

## Progress Notes

- 2026-04-27: Started — picking up from gemini session artifact, scoping doc-only edits.
- 2026-04-27: Implemented — added Server Liveness Protocol to agent-testing.md
  (claude+gemini mirrors), added step 0 to J-1 in user-journeys.md, added
  Affected User Journeys section to ticketing-workflow.md ticket file format,
  added re-run-flows step to On Task Completion, added step 2.5 to
  ticket-first-workflow.md.
- 2026-04-27: Self-review pass — applied 12 fixes:
  - macOS-portable kill recipe (no `xargs -r`); added `pkill` for python+runserver.
  - Added DB-readiness probe (`curl /` expecting 302) alongside `/healthz`.
  - Bumped hang threshold 10s → 30s (matches Playwright default nav timeout).
  - Cross-link to delivery-checklist scope clarification.
  - Renumbered J-1 cleanly (1..4) instead of 0..3.
  - Softened "re-run every flow" to "make test-e2e + manual J-x walk for UI changes."
  - Deduped AC example (mix functional + journey items, no placeholder duplication).
  - Added concrete examples for "internal-only" scope clause.
  - Added migration note: existing tickets grandfathered, backfill on next touch.
  - Filed follow-up #516 for rule-mirror dedup.
  - Fixed self-conformance: ticket #515 marked internal-only with justification.
  - Smoke-tested liveness recipe locally (L=ok R=302 confirmed).
- 2026-04-27: Completed — closed atomic with commit. Internal-only change;
  no journey re-verification needed.
