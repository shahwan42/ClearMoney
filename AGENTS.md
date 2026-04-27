# ClearMoney — Agent Instructions

> Personal finance tracker: Django, HTMX, Tailwind CSS, PostgreSQL. Multi-user PWA with magic link auth.

## Where to Read

- **Project rules:** `.ai/rules/` — start with `ticket-first-workflow.md` and
  `ticketing-workflow.md`, then `qa-guidelines.md`, then read the rest as needed.
- **Critical paths (must not regress):** `.ai/rules/critical-paths.md`.
- **Agent-testing shortcuts:** `.ai/rules/agent-testing.md`.

## Quick Start

- Local dev: `make run` (port 8000); verify with `curl http://0.0.0.0:8000/healthz`.
- Tests: `make test` (unit), `make test-e2e` (Playwright).
- Lint + type: `make lint`.
- Dev login: `/login?dev=1` (DEBUG-only).
- Seed data: `/dev/seed` (DEBUG-only).

## Conventions

- Ticket-first (mandatory): `.ai/rules/ticket-first-workflow.md`.
- Git workflow: `.ai/rules/git-workflow.md`.
- TDD: `.ai/rules/tdd-workflow.md`.
- Coding conventions: `.ai/rules/coding-conventions.md`.
- Production safety: `.ai/rules/production-safety.md`.
