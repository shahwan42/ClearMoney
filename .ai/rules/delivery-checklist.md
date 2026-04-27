# Feature Delivery Checklist

## Pre-Flight Checks (run once at session start)

Before beginning any feature implementation or batch of work, verify the environment is ready:

0. **Remote environment?** — If running in Claude Code remote (SessionStart hook runs automatically):
   - Hook starts PostgreSQL and exports `DB_URL` with port 5432
   - If hook didn't run, see `.ai/rules/remote-environment.md` for manual steps
1. **Run tests** — `make test` — record baseline test count (e.g. "692 passed"). Store this number.
2. **Run lint** — `make lint` — zero errors required
3. **Django system check** — `mcp__django-ai-boost__run_check` (Claude Code) or `python manage.py check` — must pass clean
4. **List migrations** — `mcp__django-ai-boost__list_migrations` (Claude Code) or `make migrate --check` — all applied
5. **Start server** — `DISABLE_RATE_LIMIT=true make run` in background. Verify: `curl http://0.0.0.0:8000`
6. **Verify browser access** — `mcp__playwright__browser_navigate` (Claude Code) or open `http://0.0.0.0:8000` in browser (required for QA)
   - Claude Code setup: `npx @anthropic-ai/claude-code mcp add playwright -- npx @anthropic-ai/playwright-mcp@latest`
7. **Git status** — `git status` — working tree clean, on main branch

---

## Feature Delivery Steps (after implementation)

After completing a feature, follow these steps in order:

1. **Run tests** — `make test` — verify count >= baseline (no tests deleted)
2. **Auto-format code** — `make format` — auto-fixes style issues
3. **Run e2e + lint** — `make test-e2e && make lint` — all tests pass, zero lint errors
4. **Code review** — run `/review` (Claude Code) or do a manual review for bugs, edge cases, security issues
5. **QA review** — run `/qa-review` (Claude Code) or review test coverage manually for functional, state/interaction, data, and cleanup categories
6. **Update documentation** — `docs/features/` if applicable
7. **Restart the app** — `make run` so the user can try it at `http://0.0.0.0:8000`
8. **Show manual test steps** — list the exact UI steps to verify the feature works
9. **Ask to commit** — once approved, run `/commit` (Claude Code) or `git add <files> && git commit -m 'type: description'`
