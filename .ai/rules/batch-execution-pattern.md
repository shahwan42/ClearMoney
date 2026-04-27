# Batch Execution Pattern — Multi-Improvement Deliverables

Structured workflow for executing grouped improvements (accessibility fixes, touch target corrections, etc.). Use when delivering 5+ related improvements in a single session.

## Pre-Batch Setup (One-Time)

### Pre-flight Checks
```bash
make test                              # Record baseline test count
make lint                              # Verify zero errors
mcp__django-ai-boost__run_check        # Django system check (Claude Code) or: python manage.py check
DISABLE_RATE_LIMIT=true make run &     # Start server
curl http://0.0.0.0:8000               # Verify server responds
git status                             # Working tree clean, on main
```

Store the baseline test count — you'll verify tests don't decrease later.

### Prepare Batch Context
- Read batch documentation (e.g., `UX_ACCESSIBILITY_AUDIT.md`)
- Use `mcp__django-ai-boost__list_models` / `list_urls` (Claude Code) or read `backend/core/models.py` directly
- Read affected templates/files to verify current implementation
- Create TodoWrite checklist with ALL improvements in this batch

### Baseline Snapshot
- Run `mcp__django-ai-boost__list_migrations`
- Note current git commit: `git log --oneline -1`

## Per-Improvement Execution (Repeat for Each Item)

### Phase 1 — Understand (5 min)

Read the specific issue in batch documentation:
- What WCAG criterion does it fix?
- Which template/component is affected?
- What's the current state?

### Phase 2 — RED → GREEN (TDD)

**RED:** Write failing test FIRST
```bash
# In e2e/tests/ or backend/tests/
# Add test that verifies the improvement (e.g., ARIA attribute presence)
make test-e2e  # Run and confirm it FAILS — RED ✓
```

**GREEN:** Implement minimal fix
```bash
# Add ARIA attributes, adjust colors, fix focus management in template
# Do NOT add extra features or refactor surrounding code
make test-e2e  # Run and confirm it PASSES — GREEN ✓
```

### Phase 3 — Verification Gate

All must pass before moving to next improvement:

```bash
make format                        # Auto-format code
mcp__django-ai-boost__run_check   # Django check (Claude Code) or: python manage.py check
make lint                          # ruff + mypy zero errors
make test                          # count >= baseline
make test-e2e                      # all Playwright tests pass
```

### Phase 4 — Accessibility QA

Follow `.ai/rules/accessibility-qa-protocol.md` checklist:

1. **Accessibility tree**: `mcp__playwright__browser_snapshot` (Claude Code) or browser DevTools accessibility panel
2. **Keyboard nav**: Tab/Shift-Tab, arrow keys, Escape
3. **Contrast**: 4.5:1 text, 3:1 non-text
4. **Screen reader**: aria-label, aria-live, role attributes announced
5. **Visual**: Light + dark modes, 200% zoom
6. **Mark done**: Update TodoWrite

### Phase 5 — Commit Immediately

```bash
git add backend/templates/component.html core/models.py  # Specific files only
git commit -m "fix: [WCAG/feature] - brief description"
```

Use `/commit` (Claude Code) or `git add <specific files> && git commit -m 'type: description'`.

**Important:** Commit after EACH improvement, not at end of batch. This keeps history clean and allows context compacting.

## After All Improvements in Batch

### Batch Final Gate

Once every improvement is committed and QA'd:

```bash
make format                 # Auto-format all code
make test                   # All tests pass
make test-e2e               # All E2E tests pass
make lint                   # Zero errors
```

### Quality Review

- Run `/qa-review` (Claude Code) or manually review test coverage for gaps across all batch improvements
- Run `/simplify` (Claude Code) or review changed code for over-engineering
- Refactor if needed — keep tests green throughout

### Compact and Reset

After batch is fully committed and QA'd:

```bash
git log --oneline -15        # Verify all batch commits present
# If using context-managing tool:
/compact                     # Clear old context, keep batch history
```

## Batch Checklist Template

```markdown
# Batch: [Name] (Est. X-Y hours)

## Improvements
- [ ] Improvement 1: [description]
  - [ ] RED (test fails)
  - [ ] GREEN (test passes)
  - [ ] Verification gate passes
  - [ ] QA checklist complete
  - [ ] Committed

- [ ] Improvement 2: [description]
  - [ ] RED
  - [ ] GREEN
  - [ ] Verification gate passes
  - [ ] QA checklist complete
  - [ ] Committed

...

## Batch Final Gate
- [ ] make test (count >= baseline)
- [ ] make test-e2e (all pass)
- [ ] make lint (zero errors)
- [ ] /qa-review (or manual coverage review) complete
- [ ] /simplify (or manual over-engineering check) run
```

## Error Recovery (Autonomous)

**If single improvement fails >2 times:**
1. Back up current work: `git stash`
2. Revert last commit: `git reset --soft HEAD~1`
3. Review error: inspect `browser_snapshot`, check test output
4. Re-implement with different approach
5. Retry verification gate
6. If still failing, move to next improvement (skip this one, return later)

**If verification gate fails:**
1. Run `mcp__django-ai-boost__run_check` (Claude Code) or `python manage.py check` — identify Django errors
2. Run `make lint` — fix linting/typing issues first
3. Check test count: `make test` — if < baseline, investigate which test broke
4. Do NOT force-commit — fix the issue first

**If context fills during batch:**
1. Commit current work: `git log --oneline -10` — verify commits present
2. Run `/compact` or start fresh session
3. Resume from next improvement: `git log` shows which ones are done
4. Re-run pre-flight checks in new session
5. Continue with next improvement

## Key Principles

- **ONE improvement per commit** — each improvement → test → commit (then next)
- **Never skip RED** — always write failing test before implementation
- **TDD all the way** — RED → GREEN → Verify → QA → Commit (repeat)
- **Specific file staging** — never `git add .` — stage only modified files for this improvement
- **Verification before next** — don't start improvement 2 until improvement 1's gate fully passes
- **Documentation matters** — batch docs should be clear enough for context recovery
- **Batch isolation** — once batch is committed and final gate passes, consider it done (move to next batch)

## Success Criteria

✅ All improvements in batch implemented
✅ Each improvement has test + implementation + QA
✅ Tests count >= baseline (no tests deleted)
✅ All tests pass (unit + E2E)
✅ Zero lint/mypy errors
✅ All commits follow conventional format
✅ Batch final gate passes
✅ No regressions found by /qa-review (or manual review)
