---
id: "517"
title: "Agent-native testing shortcuts (dev login, seed, htmx loading, testids)"
type: feature
priority: medium
status: done
created: 2026-04-27
updated: 2026-04-27
---

## Description

Backfill ticket for prior gemini-session work (artifact:
`temporary_artifacts/gemini_20260427_181538.md`). Adds agent-native testing
shortcuts so AI agents (Claude, Gemini, Playwright MCP) can drive the app
without going through magic-link email or hand-creating data:

- `/login?dev=1` — instant DEBUG-only login as `test@clearmoney.app` (creates
  user if missing, mints AuthToken, redirects through `/auth/verify`).
- "⚡ Dev Quick Login" link on `/login` page (DEBUG only).
- `GET /dev/seed` — runs `qa_seed` mgmt command for current user; populates
  3 accounts, 5 categories, basic transactions.
- "Dev Tools" seed button on `/settings` page (`data-testid="dev-seed-button"`).
- `data-htmx-loading` attribute on `<body>`, toggled by `htmx:beforeRequest` /
  `htmx:afterSettle` listeners in `base.html`. Lets Playwright wait for
  `body:not([data-htmx-loading])`.
- Stable `data-testid` attributes on bottom nav, more menu, comboboxes,
  bottom-sheet close buttons.
- Rule docs: `.claude/rules/agent-testing.md`, `.claude/rules/user-journeys.md`
  (+ gemini mirrors). Cross-refs added to `qa-guidelines.md` §11 and
  `critical-paths.md` "Agent Shortcuts" section. Fixed bad path references
  (gemini-side paths) in `.claude/rules/qa-guidelines.md`.

## Affected User Journeys

- **CP-1 (Magic Link Login)**: new alternate auth path via `?dev=1`. Standard
  magic-link flow remains unchanged; new path is gated on `settings.DEBUG`.
- **CP-6 (Per-User Data Isolation)**: dev login always lands on a fixed
  `test@clearmoney.app` user — no isolation regression (other users still
  isolated; dev shortcut is single-tenant by design).
- **J-1 (Setup & Environment Ready)**: this is the journey the change exists
  to support — `/login?dev=1` + `/dev/seed` are now its primary path.
- **J-2..J-5**: indirectly enabled — agents can now reach these flows quickly
  via J-1's shortcuts.

## Acceptance Criteria

- [x] `/login?dev=1` returns 302 to `/auth/verify?token=...` and lands on
      authenticated dashboard (CP-1 alternate path).
- [x] `/login?dev=1` returns 404/no-op when `DEBUG=False` (production safety).
- [x] `/dev/seed` returns 403 when `DEBUG=False`.
- [x] `/dev/seed` populates accounts/categories/transactions for current user.
- [x] `body[data-htmx-loading]` toggles around HTMX requests.
- [x] `data-testid` attributes present on nav-home, nav-history, nav-plus,
      nav-accounts, nav-more, menu-*, qe-account-combobox-input,
      qe-category-combobox-input, *-close.
- [x] CP-1 magic-link flow still works (unchanged).
- [x] J-1 walkthrough succeeds end-to-end via Playwright MCP.

## Progress Notes

- 2026-04-27: Backfilled — work originally completed in prior gemini session.
- 2026-04-27: Fixed `.claude/rules/qa-guidelines.md` path refs that pointed
  at `.gemini/rules/...` instead of `.claude/rules/...`.
- 2026-04-27: Completed — committed atomic with this ticket.
