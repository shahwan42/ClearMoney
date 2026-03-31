---
id: "054"
title: "Auth rate limiting tests"
type: test
priority: high
status: pending
created: 2026-03-31
updated: 2026-03-31
---

## Description

The auth_app has **zero tests for rate limiting** despite being security-critical (80% coverage target). The rate limiting logic in `auth_app/services.py` (lines 232-264) is completely untested: per-email cooldown, daily per-email cap, and global daily cap.

Current auth_app coverage: 90.6% (278 stmts, 26 missed).

## Acceptance Criteria

- [ ] Test 5-minute per-email cooldown: second request within 5 min returns `COOLDOWN`
- [ ] Test 3/day per-email limit: 4th request in same day is rejected
- [ ] Test 50/day global email limit: requests rejected after global cap reached
- [ ] Test timing anti-bot check: requests completing < 2s are rejected
- [ ] Test token reuse after expiry (should generate new token, not return REUSED)
- [ ] auth_app coverage remains above 80% floor
- [ ] All existing tests still pass

## Files

- `backend/auth_app/services.py` — lines 232-264 (rate limiting logic)
- `backend/auth_app/tests/test_services.py` — add new test class `TestRateLimiting`

## Estimated Size

Small — 5-7 new tests, no code changes needed.

## Progress Notes

- 2026-03-31: Created — identified zero rate-limiting test coverage during test coverage analysis
