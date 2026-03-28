---
id: "008"
title: "E2E test isolation flakiness — fix database connection handling under load"
type: chore
priority: medium
status: done
created: 2026-03-28
updated: 2026-03-28
---

## Description

E2E test suite exhibits flakiness when running full suite or large test batches. Specifically, 5 tests that pass individually fail when run as part of the full e2e suite due to test isolation issues. Root cause is database state management and connection handling when tests run in rapid succession.

## Symptoms

**5 failing tests (only in full suite context):**
- `test_logout_clears_session` — logout endpoint doesn't clear session
- `test_logout_clears_session_and_redirects` — same as above
- `test_budget_shows_remaining_amount` — API returns 500 error under load
- `test_row_click_opens_detail_sheet` — API returns 500 error under load
- `test_swipe_to_delete_transaction` — API returns 500 error under load

**Key evidence:**
- All 5 tests PASS when run individually (`pytest e2e/tests/test_budgets.py::TestBudgets::test_budget_shows_remaining_amount`)
- All 5 tests PASS when run in small groups
- Tests FAIL at specific positions in full suite execution order
- Failures are **not random** — reproducible when running large test batches

## Root Cause Analysis

Test isolation failures stem from database connection management issues when tests rapidly create/destroy connections:

1. **Connection termination under load** — `reset_database()` function terminates idle connections with a 5-second grace period. When many tests run in succession, this timeout may be insufficient.
2. **Django ORM connection pooling** — Possible race condition where Django server's database connection isn't properly refreshed between test modules
3. **Test module sequencing** — Failures manifest at specific test boundaries (after 15+ auth tests, or after running multiple test modules together)

## Acceptance Criteria

- [ ] All 5 previously-failing tests pass in full e2e suite
- [ ] No test flakiness or intermittent failures
- [ ] Investigate and fix `reset_database()` connection termination logic
- [ ] Consider adding explicit connection closure between test modules
- [ ] All 145 e2e tests passing consistently (not just in isolation)

## Investigation Notes

**Current behavior:**
- `reset_database()` at line 130 in `e2e/conftest.py` terminates idle connections with 5-second threshold
- Connection termination query filters by `state = 'idle'` and `state_change < NOW() - INTERVAL '5 seconds'`
- When test modules run rapidly, Django server connections may still be active/transitioning

**Possible fixes:**
1. Increase grace period timeout (10-15 seconds instead of 5)
2. Add explicit `conn.close()` in conftest connection cleanup
3. Implement connection pooling reset between test modules
4. Add small delay between test modules to allow connections to fully idle

## Related Commits

- `4ae2e5a` — JSON encoding fix (resolved majority of test failures)

## Progress Notes

- 2026-03-28: Started — Investigated E2E test failures, identified test isolation as root cause of 5 remaining failures. Main JSON encoding issue already fixed in prior commit. Created this ticket to track infrastructure-level test flakiness.
- 2026-03-28: Completed — Fixed via DB connection health checks (commit 572ee8b), then unskipped quick-entry and batch-entry E2E tests (commit c86e1f1).
