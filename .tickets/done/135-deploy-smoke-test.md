---
id: "135"
title: "Deploy smoke test — post-deployment health verification"
type: chore
priority: high
status: done
created: 2026-04-18
updated: 2026-04-23
---

## Description

Introduce a `make deploy-test` command that runs a post-deployment smoke test
against the live production app. The test creates an isolated sentinel user,
exercises all six critical paths via real HTTP calls, then deletes every trace
of itself — even if the test process crashed mid-run.

A companion `make deploy-test-cleanup` target runs cleanup alone and is safe
to run repeatedly (idempotent).

No real user data is ever touched. The smoke user is identifiable by a fixed
sentinel email and all created records carry a `[SMOKE]` prefix.

---

## Motivation

After `make deploy` pushes a new image, there is currently no automated
verification that the live app actually works. A bad deploy (failed migration,
import error, broken static file) could silently serve errors. This smoke test
closes that gap by verifying the six critical paths within ~30 seconds of
every deploy.

---

## Acceptance Criteria

- [x] `make deploy-test` SSHes to the production VPS, runs the smoke test, and
      exits **0** on success / **non-zero** on any failure — suitable for CI
      pipelines and shell-script `&&` chains.
- [x] The smoke test covers all six critical paths from `.claude/rules/critical-paths.md`:
      CP-1 (auth), CP-2 (account + transaction + balance), CP-3 (transfer),
      CP-4 (budget), CP-5 (dashboard), CP-6 (data isolation).
- [x] The sentinel user `smoke-deploy@clearmoney.app` and all associated data
      are deleted at the end of a successful run — and remain deletable via
      `make deploy-test-cleanup` when the run failed or was interrupted.
- [x] `make deploy-test-cleanup` is **idempotent**: running it when nothing
      exists is a no-op (exit 0, prints "nothing to clean").
- [x] No existing user's data is read, modified, or deleted.
- [x] The smoke test does **not** send real emails (bypasses Resend by creating
      tokens directly in the DB — same pattern as E2E conftest).
- [x] The Django management command (`deploy_smoke_test`) is also runnable
      locally against a running dev server for easy debugging.
- [x] All new Python code passes `make lint` (ruff + mypy, zero errors).
- [x] A unit test module `backend/jobs/tests/test_smoke_test.py` covers:
      - Cleanup when no smoke user exists (no-op, no exception)
      - Cleanup when smoke user + data exists (all deleted)
      - Sentinel email constant matches what the command uses

---

## Implementation Notes

- Added `backend/jobs/management/commands/deploy_smoke_test.py` with:
  cleanup-first execution, manual `urllib` HTTP client, form/JSON coverage for
  the six critical paths, and final cleanup in `finally` unless `--no-cleanup`
  is explicitly requested.
- Added a small public helper `auth_app.services.seed_default_categories()` so
  smoke/QA flows can seed the same default categories used by registration.
- Added `make deploy-test` and `make deploy-test-cleanup`, both executed inside
  the production Django container so the server needs no extra host packages or
  ad-hoc scripts.
- Cleanup is idempotent and removes both the primary smoke user and the
  isolation-only smoke user, plus tokens and related data, inside a DB
  transaction.

## Progress Notes

- 2026-04-23: Started — Mapped production deploy flow, auth/session behavior, and the real HTTP endpoints used by the six critical paths.
- 2026-04-23: Implemented — Added the management command, cleanup-only mode, shared category seeding helper, Makefile targets, and smoke cleanup unit tests.
- 2026-04-23: Verified — `backend/jobs/tests/test_smoke_test.py` passed, the command succeeded locally against a live dev server, `make test` passed (1564 tests), `make lint` passed, and `make test-e2e` passed (273 tests).
- 2026-04-23: Completed — Deploy smoke verification is now runnable locally and on the VPS, idempotent across reruns and crash recovery, and closed out with ticket/index updates in the same commit.

---

## Architecture

### Components

```
backend/jobs/management/commands/deploy_smoke_test.py   ← management command
backend/jobs/tests/test_smoke_test.py                   ← unit tests
Makefile  (new targets: deploy-test, deploy-test-cleanup)
```

No new pip dependencies required — uses `urllib.request` (stdlib) for HTTP
calls, same as the existing E2E conftest.

### Sentinel constants

```python
SMOKE_EMAIL    = "smoke-deploy@clearmoney.app"
SMOKE_PREFIX   = "[SMOKE]"              # prepended to all created names/notes
SMOKE_INST_NAME = "[SMOKE] Test Bank"
SMOKE_ACCT_A   = "[SMOKE] Main EGP"
SMOKE_ACCT_B   = "[SMOKE] Savings EGP"
SMOKE_NOTE     = "[SMOKE] expense"
```

### Management command interface

```
python manage.py deploy_smoke_test [options]

Options:
  --app-url URL       Base URL of the app under test
                      (default: APP_URL env var, fallback http://localhost:8000)
  --cleanup-only      Skip tests; only delete smoke user + data
  --timeout SECS      Per-request HTTP timeout in seconds (default: 15)
  --no-cleanup        Keep smoke data after tests (for debugging; never use in CI)
```

---

## Implementation Plan

### Phase 1 — Management command skeleton + cleanup

**File:** `backend/jobs/management/commands/deploy_smoke_test.py`

```python
"""
Management command: deploy_smoke_test

Runs a post-deployment smoke test against a live Django app, then deletes all
sentinel data it created.

Usage (local dev):
    python manage.py deploy_smoke_test --app-url http://localhost:8000

Usage (production, via Makefile):
    make deploy-test            # runs full smoke test
    make deploy-test-cleanup    # standalone cleanup
"""
```

Implement `_cleanup(stdout)` as the first function. It must:

1. Find the smoke user by `SMOKE_EMAIL`; if absent → print "nothing to clean" → return
2. Inside `transaction.atomic()`:
   - Delete all `Session` rows for the smoke user
   - Delete all `AuthToken` rows for the smoke email
   - Delete all `Transaction` rows for the smoke user (CASCADE handles `balance_delta`)
   - Delete all `Budget` rows for the smoke user
   - Delete all `Account` rows for the smoke user
   - Delete all `Institution` rows for the smoke user
   - Delete all `Category` rows for the smoke user (user-owned categories only;
     `is_system=False` and `user_id=smoke_user.id`)
   - Delete the `User` row itself (CASCADE takes care of remaining FK children)
3. Print a summary: `"Smoke cleanup complete: deleted user + N accounts + M transactions"`

The atomic block means either everything is cleaned or nothing — no partial state.

### Phase 2 — HTTP helper

```python
def _request(
    method: str,
    url: str,
    *,
    data: dict | None = None,
    cookies: dict | None = None,
    timeout: int = 15,
    allow_redirects: bool = True,
) -> tuple[int, str, dict]:
    """
    Returns (status_code, body_text, response_cookies).
    Raises SmokeError on connection failure or timeout.
    """
```

Implement using only `urllib.request` + `urllib.error` (no third-party http
libraries needed). Cookies are manually threaded between requests via the
`response_cookies` dict.

### Phase 3 — Smoke test scenarios

Implement `_run_smoke_tests(app_url, timeout, stdout)` calling these checks in
order. Each check is a small helper that raises `SmokeError(message)` on
failure (caught at the top level to print a clear failure summary).

#### Check 1 — Health endpoint

```
GET {app_url}/healthz  →  200
```

Fail message: `"FAIL [health] /healthz returned {status}, expected 200"`

#### Check 2 — Unauthenticated redirect

```
GET {app_url}/  →  status in (301, 302, 303)  and  Location contains /login
```

Fail message: `"FAIL [auth-redirect] / should redirect to /login"`

#### Check 3 — Auth flow (CP-1)

Steps:
1. Create smoke `User` (via ORM; `User.objects.get_or_create(email=SMOKE_EMAIL)`)
2. Seed 25 default categories (call `auth_app.services.seed_default_categories(user_id)` 
   — same function called during registration)
3. Create `AuthToken(email=SMOKE_EMAIL, token=secrets.token_urlsafe(32),
   purpose="login", expires_at=now+15min)`
4. `POST {app_url}/auth/verify?token={token}` with `follow_redirects=True`
   — must receive session cookie `clearmoney_session`
5. Store session cookie for subsequent requests

Fail messages:
- `"FAIL [auth-token] Could not create magic link token"`
- `"FAIL [auth-verify] /auth/verify did not set session cookie"`

#### Check 4 — Dashboard renders (CP-5)

```
GET {app_url}/   (authenticated)  →  200  and  "Net Worth" in body
```

Fail message: `"FAIL [dashboard] Dashboard missing 'Net Worth' heading"`

#### Check 5 — Create institution + account + transaction + balance (CP-2)

Steps (all via API endpoints, authenticated):

1. `POST /api/institutions`  
   body: `{"name": "[SMOKE] Test Bank", "type": "bank", "color": "#6366f1"}`  
   → 201 or 200; parse `institution_id`

2. `POST /api/accounts`  
   body: `{"name": "[SMOKE] Main EGP", "institution_id": ..., "type": "current",
   "currency": "EGP", "initial_balance": "10000.00"}`  
   → parse `account_id`, note `current_balance = 10000.00`

3. Find a "Food" category for the smoke user:  
   `GET /api/categories` → parse first expense category id

4. `POST /api/transactions`  
   body: `{"account_id": ..., "type": "expense", "amount": "500.00",
   "category_id": ..., "note": "[SMOKE] expense", "date": today}`  
   → 200; parse balance from response OR re-fetch account

5. Verify account `current_balance == 9500.00` by querying ORM directly
   (no need for a separate GET — ORM is authoritative in the same process)

Fail messages:
- `"FAIL [institution] POST /api/institutions returned {status}"`
- `"FAIL [account] POST /api/accounts returned {status}"`
- `"FAIL [categories] No expense category found for smoke user"`
- `"FAIL [transaction] POST /api/transactions returned {status}"`
- `"FAIL [balance] Expected 9500.00, got {actual}"`

#### Check 6 — Transfer updates both balances (CP-3)

Steps:
1. `POST /api/accounts` → create `[SMOKE] Savings EGP` (EGP, balance 0)
2. `POST /api/transactions/transfer`  
   body: `{"from_account_id": main_egp_id, "to_account_id": savings_id,
   "amount": "1000.00", "date": today}`  
3. ORM assert: main_egp balance = 8500.00, savings balance = 1000.00

Fail message: `"FAIL [transfer] Expected balances 8500/1000, got {a}/{b}"`

#### Check 7 — Budget creation (CP-4)

Steps:
1. `POST /api/budgets`  
   body: `{"category_id": food_cat_id, "limit": "3000.00", "currency": "EGP"}`  
   → 200 or 201

Fail message: `"FAIL [budget] POST /api/budgets returned {status}"`

#### Check 8 — Data isolation (CP-6)

Steps:
1. Create a second throw-away user in ORM: `User.objects.create(email="smoke-isolation-check@clearmoney.app")`
2. Create a `Session` for that user → get session token
3. Make request: `GET /api/transactions` with second user's session  
   → verify smoke user's `[SMOKE] expense` transaction is NOT in the response body
4. Delete the second user immediately

Fail message: `"FAIL [isolation] Smoke data leaked to other user's transaction list"`

#### Check 9 — Logout invalidates session (part of CP-1)

Steps:
1. `POST {app_url}/logout` with smoke user session cookie → 302
2. `GET {app_url}/` with same cookie → must redirect to `/login` (302)

Fail message: `"FAIL [logout] Session still valid after logout"`

### Phase 4 — Top-level `handle()` method

```python
def handle(self, *args, **options):
    cleanup_only = options["cleanup_only"]
    no_cleanup   = options["no_cleanup"]
    app_url      = options["app_url"] or os.environ.get("APP_URL", "http://localhost:8000")
    timeout      = options["timeout"]

    if cleanup_only:
        _cleanup(self.stdout)
        return

    self.stdout.write(f"→ Smoke testing {app_url} ...")
    passed = failed = 0

    try:
        _run_smoke_tests(app_url, timeout, self.stdout)
        self.stdout.write(self.style.SUCCESS("✓ All smoke checks passed"))
    except SmokeError as e:
        self.stderr.write(self.style.ERROR(f"✗ {e}"))
        if not no_cleanup:
            _cleanup(self.stdout)
        raise SystemExit(1)
    finally:
        if not no_cleanup:
            _cleanup(self.stdout)
```

### Phase 5 — Makefile targets

```makefile
# ── Deploy smoke test ───────────────────────────────────────────────────────

DEPLOY_HOST ?= hetzner-keeper
DEPLOY_DIR  ?= ~/ClearMoney

# Run smoke tests against the live production app (after deploy).
# Exits non-zero on any failure — safe to chain: make deploy && make deploy-test
deploy-test:
	ssh $(DEPLOY_HOST) "cd $(DEPLOY_DIR) && \
	  sudo docker compose -f docker-compose.prod.yml exec -T django \
	  python manage.py deploy_smoke_test \
	  --app-url https://clearmoney.shahwan.me"

# Delete smoke test data from production (idempotent — safe to run if test crashed).
deploy-test-cleanup:
	ssh $(DEPLOY_HOST) "cd $(DEPLOY_DIR) && \
	  sudo docker compose -f docker-compose.prod.yml exec -T django \
	  python manage.py deploy_smoke_test --cleanup-only"
```

---

## Unit Tests

**File:** `backend/jobs/tests/test_smoke_test.py`

```python
"""
Unit tests for deploy_smoke_test management command.

Tests only the parts that don't require a live HTTP server:
  - cleanup helper (idempotent, correct cascade)
  - sentinel constants (guard against accidental rename)
"""

import pytest
from django.core.management import call_command

from auth_app.models import User, Session, AuthToken
from accounts.models import Account, Institution
from transactions.models import Transaction

SMOKE_EMAIL = "smoke-deploy@clearmoney.app"


class TestSmokeCleanup:
    def test_cleanup_when_no_smoke_user_is_noop(self, db, capsys):
        """Cleanup with no sentinel user should not raise and should say so."""
        call_command("deploy_smoke_test", "--cleanup-only")
        out = capsys.readouterr().out
        assert "nothing to clean" in out.lower()

    def test_cleanup_deletes_user_and_all_data(self, db):
        """After cleanup, no trace of the smoke user should remain."""
        user = User.objects.create(email=SMOKE_EMAIL)
        uid = str(user.id)
        Institution.objects.create(user_id=uid, name="[SMOKE] Test Bank", color="#000")
        Session.objects.create(
            user=user,
            token="smoke-token-abc",
            expires_at="2099-01-01T00:00:00Z",
        )
        AuthToken.objects.create(
            email=SMOKE_EMAIL,
            token="smoke-auth-abc",
            purpose="login",
            expires_at="2099-01-01T00:00:00Z",
        )

        call_command("deploy_smoke_test", "--cleanup-only")

        assert not User.objects.filter(email=SMOKE_EMAIL).exists()
        assert not Institution.objects.filter(user_id=uid).exists()
        assert not Session.objects.filter(user_id=uid).exists()
        assert not AuthToken.objects.filter(email=SMOKE_EMAIL).exists()

    def test_cleanup_is_idempotent(self, db):
        """Running cleanup twice in a row should not raise."""
        call_command("deploy_smoke_test", "--cleanup-only")
        call_command("deploy_smoke_test", "--cleanup-only")  # second call — no error

    def test_sentinel_email_constant(self):
        """Guard: if the sentinel email ever changes tests should catch it first."""
        from jobs.management.commands.deploy_smoke_test import SMOKE_EMAIL as cmd_email
        assert cmd_email == SMOKE_EMAIL

    def test_cleanup_second_user_not_deleted(self, db):
        """Cleanup must NOT delete real (non-smoke) users."""
        User.objects.create(email="real-user@clearmoney.app")
        User.objects.create(email=SMOKE_EMAIL)
        call_command("deploy_smoke_test", "--cleanup-only")
        assert User.objects.filter(email="real-user@clearmoney.app").exists()
```

---

## Safety Checklist

| Risk | Mitigation |
|------|-----------|
| Modifying real user data | All ORM writes filter strictly by `user_id == smoke_user.id`; sentinel email is non-overlapping with any real user pattern |
| Leaving dirty data on failure | `finally` block always calls `_cleanup()`; `--cleanup-only` standalone target catches crashes |
| Partial cleanup on DB error | All deletions wrapped in `transaction.atomic()` — all-or-nothing |
| Sending real emails | Never calls `AuthService.request_login_link()`; creates `AuthToken` rows directly in ORM (same as E2E conftest) |
| Port conflicts on dev | `--app-url` defaults to `APP_URL` env var; developer can target any running instance |
| Rate limiting blocking requests | `DISABLE_RATE_LIMIT=true` is set in the Django management command's env by the Makefile `deploy-test` target |
| Isolation check leaving stale data | Second throw-away user created and deleted within the same check; also caught by cleanup if check aborts |
| SSH / Docker exec permissions | Uses `docker compose exec -T` (non-interactive, safe in scripts); requires `hetzner-keeper` SSH key configured |
| Deploy-test chained with deploy | `make deploy-test` exits non-zero on failure → upstream `&&` chain halts |

---

## Local Dev Usage

```bash
# Start local server (separate terminal)
make run

# Run smoke test locally (full)
cd backend && uv run manage.py deploy_smoke_test --app-url http://localhost:8000

# Run cleanup only (after a failed test)
cd backend && uv run manage.py deploy_smoke_test --cleanup-only

# Keep smoke data for inspection (debugging)
cd backend && uv run manage.py deploy_smoke_test --app-url http://localhost:8000 --no-cleanup
# Inspect data, then:
cd backend && uv run manage.py deploy_smoke_test --cleanup-only
```

---

## Progress Notes

- 2026-04-18: Started — Designed architecture, acceptance criteria, full implementation plan
