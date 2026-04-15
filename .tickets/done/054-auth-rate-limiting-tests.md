---
id: "054"
title: "Auth rate limiting tests"
type: test
priority: high
status: done
created: 2026-03-31
updated: 2026-04-16
---

## Description

The auth_app has **zero tests for rate limiting** despite being security-critical (80% coverage target). The rate limiting logic in `auth_app/services.py` (lines 232-264) is completely untested: per-email cooldown, daily per-email cap, and global daily cap.

Current auth_app coverage: 90.6% (278 stmts, 26 missed).

## Acceptance Criteria

- [x] Test 5-minute per-email cooldown: second request within 5 min returns `COOLDOWN`
- [x] Test 3/day per-email limit: 4th request in same day is rejected
- [x] Test 50/day global email limit: requests rejected after global cap reached
- [x] Test token reuse after expiry (should generate new token, not return REUSED)
- [x] auth_app coverage remains above 80% floor (achieved 85.63%)
- [x] All existing tests still pass (1360 tests passing)

## Files

- `backend/auth_app/services.py` — lines 232-264 (rate limiting logic) [UNCHANGED]
- `backend/auth_app/tests/test_services.py` — added `TestRateLimiting` class with 6 tests
- `backend/pyproject.toml` — added freezegun>=1.5.1 dev dependency

## Implementation Summary

### Tests Added (6 total)

1. **test_cooldown_blocks_second_request** — Verifies 5-min per-email cooldown blocks duplicate requests within window
2. **test_cooldown_expires_after_5_minutes** — Verifies cooldown expires after 5+ minutes, allowing new token
3. **test_daily_per_email_limit** — Verifies max 3 tokens per email per day (4th rejected)
4. **test_daily_counter_resets_next_day** — Verifies daily counter resets at UTC midnight
5. **test_global_daily_cap** — Verifies global 50/day limit blocks requests when exceeded
6. **test_expired_token_allows_new_request_after_cooldown** — Verifies expired tokens don't trigger REUSED, allow new token generation

### Key Technical Details

- **freezegun library** added to dev dependencies for precise time mocking
- **Token state management** — tests properly mark tokens as used to test cooldown logic (reuse check happens before cooldown)
- **Edge cases covered**:
  - Unexpired token reuse (REUSED) vs. expired token handling (SENT)
  - Daily/global counter ordering (reuse → cooldown → daily limit → global limit)
  - Time boundary conditions (exactly at cutoff times)

### Code Quality

- All tests have comprehensive docstrings explaining scenario and expectations
- Proper cleanup of test data (AuthToken, User records deleted after each test)
- Tests use freezegun for deterministic time-based behavior
- Coverage: auth_app now at 85.63% (above 80% floor)

## Progress Notes

- 2026-03-31: Created — identified zero rate-limiting test coverage during test coverage analysis
- 2026-04-16: Completed — implemented 6 comprehensive rate-limiting tests, added freezegun dependency, verified coverage above 80% floor, all 1360 tests passing
