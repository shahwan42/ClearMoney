---
id: "022"
title: "Configure Claude Code session start hook"
type: chore
priority: medium
status: done
created: 2026-03-29
updated: 2026-03-29
---

## Description

Add a SessionStart hook to `.claude/settings.json` that automates dev environment setup when a Claude Code session begins. This removes manual infrastructure steps from the delivery checklist pre-flight process.

## Acceptance Criteria

- [ ] `scripts/claude-setup.sh` exists and is executable
- [ ] Script starts PostgreSQL via Docker (db service only)
- [ ] Script ensures `.env` exists (copies from `.env.example` if missing)
- [ ] Script installs git hooks if outdated
- [ ] Script applies pending migrations
- [ ] Script starts dev server in background if not running
- [ ] Script outputs JSON status report for Claude Code context
- [ ] `.claude/settings.json` has `hooks.SessionStart` configured
- [ ] Script is idempotent (safe to run multiple times)

## Progress Notes

- 2026-03-29: Started — Creating setup script and configuring SessionStart hook
- 2026-03-29: Completed — scripts/claude-setup.sh created, .claude/settings.json updated with SessionStart hook
