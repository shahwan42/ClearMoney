# QA Guidelines — ClearMoney

> This rule governs **when** and **how** to test in ClearMoney. It integrates with:
> `.ai/rules/tdd-workflow.md` (RED→GREEN), `.ai/rules/delivery-checklist.md` (gates),
> `.ai/rules/accessibility-qa-protocol.md` (WCAG), `.ai/rules/batch-execution-pattern.md` (batch work),
> `docs/qa/TEST-FLOWS.md` (detailed scenarios), and `docs/qa/QA-ENGINEER-GUIDE.md` (manual QA setup + make commands).
>
> **QA environment setup:** `make qa-reset` → `make qa-login` → paste token URL in browser. Seeds institution, 4 accounts, 4 transactions, 2 budgets. See `docs/qa/QA-ENGINEER-GUIDE.md` for full reference.

## 1. Pre-Commit Gate (MANDATORY — no exceptions)

**ALWAYS run ALL of these before every commit:**

```bash
make test             # count must be >= baseline established at session start
make lint             # zero ruff + mypy errors
make test-e2e         # required if feature touches UI, HTMX, or auth
mcp__django-ai-boost__run_check   # Django system check (Claude Code) or: python manage.py check
```

**The pre-commit gate FAILS if:**
- Test count dropped (tests were deleted)
- Any ruff or mypy error present
- Django system check reports any error
- New feature has zero test coverage at service layer (every service method needs tests)
- New feature with UI has no E2E test (see Section 5 requirements)

Baseline test count to track: Establish at session start, e.g. "692 tests passing before this task."

---

## 2. Test Pyramid Strategy

| Layer | Tool | When to write |
|-------|------|---------------|
| **Unit: Service** | pytest-django | ALWAYS — for every service method in services.py |
| **Unit: View** | pytest-django | ALWAYS — happy path + error cases + auth redirect |
| **Integration** | pytest-django | When cross-app behavior or complex ORM queries |
| **E2E** | Playwright | Per Section 5 (E2E Requirements) |

**Core rules:**
- Unit tests are cheap → write more of them
- E2E tests are slow (~30 sec per test) → cover user journeys, not implementation details
- **Never replace unit tests with E2E-only coverage** — unit tests catch bugs faster and with more isolation
- Service tests MUST test happy path AND error/validation paths (raises ValueError, empty list, etc.)
- View tests MUST verify: HTTP 200, 302 auth redirect, correct template context, CSRF handling
- Integration tests: verify cross-app state changes (e.g., creating a transaction updates dashboard view data)

---

## 3. Financial Data Integrity Rules (MANDATORY)

### 3a. Decimal Safety

**NEVER use `float()` for financial arithmetic.** The only safe places for `float()` are:

1. **Template tags** (display formatting only): `core/templatetags/money.py` — existing helpers like `format_egp(value)` return `Decimal` → `float` for JSON
2. **JSON serialization output** (intentional): service helpers `serialize_row()` returns `float` for API clients
3. **Chart percentage calculations** (display only): `(spent / limit) * 100` for progress bars

**Use `Decimal` throughout service layer arithmetic:**

```python
# CORRECT: Decimal safe
new_balance = account.current_balance - Decimal(str(amount))
total = Decimal(str(price)) + Decimal(str(tax))

# WRONG: precision loss
new_balance = float(account.current_balance) - amount
```

**Lint audit:** Run `grep -rn 'float(' backend/*/services.py` — any new occurrence requires explicit review (commit message note why it's safe).

Test pattern: Use `Decimal(str(value))` for assertions, **never** `float == float`:
```python
assert Decimal(str(account.current_balance)) == Decimal('9500.00')  # correct
assert account.current_balance == 9500.0  # WRONG — float comparison
```

### 3b. Balance Atomicity

**All balance updates MUST use `transaction.atomic()` + Django `F()` expressions:**

```python
# CORRECT: atomic, race-condition safe
from django.db.models import F
with transaction.atomic():
    Account.objects.filter(id=account_id).update(
        current_balance=F('current_balance') - delta
    )

# WRONG: race condition, not atomic
account.current_balance -= delta
account.save()
```

**Every new service method that modifies account balance must have a test that:**
1. Verifies balance before and after
2. Asserts exact Decimal value (not float approximation)
3. Verifies balance_delta for reconciliation (see 3d below)

### 3c. Currency Enforcement

**Never trust form-submitted currency.** Service layer always overrides `tx.currency` from account record.

**Rule:** If adding a new transaction type (beyond expense, income, transfer, exchange), assert `tx["currency"] == account.currency` in the test.

```python
# In service test
tx = services.create_transaction(user_id, amount=500, currency="USD", account_id=egp_account.id)
assert tx["currency"] == "EGP"  # overridden from account, not form
```

### 3d. Balance Reconciliation Pattern

**After any create/update/delete test that modifies a balance:**

```python
# Fetch fresh from DB
account = Account.objects.get(id=account_id)
assert Decimal(str(account.current_balance)) == expected_balance

# If transaction created/modified
tx = Transaction.objects.get(id=tx_id)
assert Decimal(str(tx.balance_delta)) == expected_delta
```

---

## 4. Data Isolation Testing (MANDATORY)

**Every service that reads or modifies user data MUST have at least one isolation test:**

- Create resource for user_a (e.g., transaction for user_a)
- Create resource for user_b (same type, different user)
- Verify user_a's service cannot see/modify user_b's resource
  - Expected result: 404 on detail view, empty list on query, or ValueError on delete

**Test naming convention:**
```python
def test_cannot_access_other_users_<resource>(self, ...):
    # user_a should not see user_b's data
```

**Trigger:** Add isolation test to any new app where services filter by `user_id`. Check with:
```bash
grep -rn "user_id" backend/<app>/services.py
```

**Views:** Every detail/edit/delete view must have a test for 404 when accessing other user's resource:
```python
# From backend/transactions/tests/test_views.py pattern
def test_404_for_other_users_tx(self, auth_client, db):
    tx_user_b = TransactionFactory(user_id=other_user_id)
    response = auth_client.get(f'/transactions/{tx_user_b.id}')
    assert response.status_code == 404
```

---

## 5. E2E Test Requirements (MANDATORY for new features)

**E2E tests are REQUIRED when a feature:**
- Creates a new page or URL route
- Has an HTMX interaction (form submit via HTMX, partial reload, bottom sheet)
- Modifies account balances (must verify balance shown in UI matches DB)
- Has user-facing success/error messages ("Transaction saved!", "Budget exceeded", etc.)
- Involves auth flow or session handling

**E2E tests are OPTIONAL (but encouraged) when a feature:**
- Only changes internal service logic with no UI change
- Adds a new filter/sort to an existing list (unless it's a new list view)
- Fixes a styling issue without behavioral change

**E2E test file naming:** `e2e/tests/test_<feature>.py`

**E2E test class naming:** `class Test<Feature>:`

**Each E2E test MUST cover:**
1. **Happy path:** action succeeds → success message shown → data updated in UI (balance, list item, etc.)
2. **At least one error path:** validation failure or permission denied → error message shown, no data change

Example:
```python
# e2e/tests/test_transactions.py
class TestTransactionCreate:
    def test_create_expense_updates_balance(self, page):
        """Happy path: expense created, balance updated."""
        page.fill('input[name="amount"]', '500')
        page.click('button[type="submit"]')
        expect(page.locator('#result')).to_contain_text('Transaction saved!')
        # Verify balance in UI
        expect(page.locator('.balance')).to_contain_text('9500')

    def test_zero_amount_rejected(self, page):
        """Error path: zero amount validation."""
        page.fill('input[name="amount"]', '0')
        page.click('button[type="submit"]')
        expect(page.locator('.error')).to_contain_text('must be greater than 0')
```

---

## 6. Form Validation Standards (MANDATORY)

**Every HTML text/number/date input for user data MUST have:**

### Text inputs
- `maxlength` attribute (align with DB model `max_length`)
- `required` if field is mandatory in service layer

```html
<!-- correct -->
<input type="text" name="account_name" maxlength="100" required>
```

### Date inputs
- `max="{{ today|date:'Y-m-d' }}"` to prevent future dates
- Exception: date range filters (date_from, date_to) may allow future dates for filtering

```html
<!-- correct: blocks future dates -->
<input type="date" name="transaction_date" max="{{ today|date:'Y-m-d' }}" required>

<!-- exception: date range filter allows future dates -->
<input type="date" name="date_to" placeholder="Optional end date">
```

### Amount inputs
- `min="0.01"` or `min="0"` depending on context (zero amounts usually rejected by service)
- `step="0.01"` for monetary values (two decimal places)

```html
<!-- correct: monetary input -->
<input type="number" name="amount" min="0.01" step="0.01" required>
```

**Template audit checklist:**
```bash
# Find text inputs without maxlength
grep -rn 'type="text"' backend/templates/ | grep -v maxlength

# Find date inputs without max constraint
grep -rn 'type="date"' backend/templates/ | grep -v 'max='
```

---

## 7. HTMX-Specific Testing Patterns

HTMX responses are partial HTML fragments — test them differently from full-page views.

### Unit test pattern
```python
# Verify HTMX request handling
response = client.post(url, data, HTTP_HX_REQUEST="true")
assert response.status_code == 200  # or 400/404 for error paths
assert b"Success message" in response.content
# Verify HTML fragment is valid (not full page)
assert b"<!DOCTYPE" not in response.content
```

### E2E pattern
```python
# Verify HTMX swap behavior
with page.expect_response(lambda r: url in r.url and r.request.method == "POST"):
    page.click('button[type="submit"]')
expect(page.locator("#result-target")).to_contain_text("Success message")
```

### HTMX error responses
**MUST return HTTP 4xx** (not 200 with error HTML) so screen readers and AJAX error handlers detect failures:
- `400 Bad Request` → validation error (shown in HTMX swap target)
- `403 Forbidden` → permission denied
- `404 Not Found` → resource not found
- `422 Unprocessable Entity` → server-side validation failed

**Test both paths:**
1. Success swap (HTTP 200)
2. Error swap (HTTP 400/404)

---

## 8. Coverage Requirements (MANDATORY)

**Global floor:** 60% (do not decrease)

**Per-app minimum floors:**
```
auth_app:          80%  # security critical: magic link, sessions, rate limits
transactions:      75%  # financial core: balance updates, atomicity
accounts:          75%  # critical: current_balance tracking, dormant logic
budgets:           70%
people:            70%
virtual_accounts:  70%
dashboard:         65%
reports:           65%
recurring:         65%
investments:       60%
settings_app:      60%
push:              50%  # mostly infrastructure, less critical
```

**New apps start at 70% minimum requirement.**

**Check per-app coverage:**
```bash
cd backend
uv run pytest --cov=<app> --cov-report=term-missing --cov-fail-under=<floor>
```

---

## 9. When to Use MCP Tools vs Make Commands

> **Note:** MCP tool names below (`mcp__django-ai-boost__*`, `mcp__playwright__*`) are available in Claude Code. Other agents should use the fallback commands listed in the Note column.

| Need | Tool | Note |
|------|------|------|
| Full test suite | `make test` | Runs all unit tests with coverage |
| Parallel testing | `make test-fast` | Uses pytest-xdist for speed |
| E2E suite | `make test-e2e` | Runs Playwright tests (serial, slower) |
| Lint + mypy | `make lint` | Runs ruff check + mypy (all 3 must pass) |
| Schema exploration | `mcp__django-ai-boost__list_models` | Claude Code: fast schema lookup; fallback: read `backend/core/models.py` |
| Migration status | `mcp__django-ai-boost__list_migrations` | Claude Code; fallback: `python manage.py showmigrations` |
| URL routes | `mcp__django-ai-boost__list_urls` | Claude Code; fallback: `python manage.py show_urls` |
| Django check | `mcp__django-ai-boost__run_check` | Claude Code: faster than `make lint`; fallback: `python manage.py check` |
| Visual QA | `mcp__playwright__browser_snapshot` | Claude Code: inspect ARIA tree; fallback: browser DevTools accessibility panel |
| Keyboard nav testing | `mcp__playwright__browser_press_key` | Claude Code; fallback: manual keyboard testing in browser |
| Contrast verification | `mcp__playwright__browser_evaluate` | Claude Code: compute CSS colors; fallback: browser DevTools computed styles |
| Screen reader sim | `mcp__playwright__browser_snapshot` | Claude Code: read accessibility tree; fallback: browser accessibility inspector |

**Do NOT use** `mcp__playwright__*` **for running the automated E2E suite** — use `make test-e2e` instead.

---

## 10. Test Naming Conventions (Advisory)

### Service-level tests
```python
class TestCreate:
    def test_create_transaction_updates_balance
    def test_create_zero_amount_rejected
    def test_create_missing_required_field_rejected

class TestUpdate:
    def test_update_transaction_recalculates_balance

class TestDelete:
    def test_delete_cascade_removes_related

class TestIsolation:
    def test_cannot_access_other_users_transaction
```

### View-level tests
```python
class TestViews:
    def test_list_returns_200_for_authenticated_user
    def test_create_shows_form_on_get
    def test_create_returns_302_redirect_on_post_success
    def test_detail_returns_404_for_other_users_resource
```

### General pattern
```
def test_<action>_<condition>_<expected>
def test_create_with_valid_data_returns_success
def test_create_with_zero_amount_rejected
def test_cannot_access_other_users_transaction
```

---

## 11. Agent-Ready QA Standards

To ensure the app is easily testable by AI agents (manual or automated):

1.  **Stable Selectors:** ALWAYS use `data-testid` for navigation and form controls. Never rely solely on localized text (e.g., "Save" vs "حفظ").
2.  **HTMX Observability:** When writing Playwright tests or performing manual verification, utilize the `data-htmx-loading` body attribute. 
    *   *Rule:* Never click or assert after an HTMX action until `body:not([data-htmx-loading])`.
3.  **Bypass Barriers:** Utilize the `?dev=1` auth bypass and `/dev/seed` data shortcut for rapid environment setup.
4.  **Custom Widgets:** Ensure all custom JS widgets (Comboboxes, etc.) expose their internal inputs via `data-testid`.

See [Agent Testing Guide](./agent-testing.md) for full technical details.

---

## Integration with Other Rules

- **TDD workflow** (tdd-workflow.md): Always write RED test first, then GREEN implementation. This guideline is the **what to test**.
- **Delivery checklist** (delivery-checklist.md): Run pre-flight + feature delivery steps. Pre-commit gate is step 2.
- **Accessibility protocol** (accessibility-qa-protocol.md): Use for ARIA/keyboard/contrast verification before commit.
- **Batch execution** (batch-execution-pattern.md): This guideline applies to each improvement in the batch.
- **Test flows** (docs/qa/TEST-FLOWS.md): Detailed scenarios when planning new tests.

---

## When to Seek Help

- Uncertain if E2E is required for a feature? Check Section 5 and `docs/qa/TEST-FLOWS.md`
- Unsure what Decimal pattern to use? Search `backend/transactions/services.py` for existing examples
- Data isolation test pattern unclear? Copy pattern from `backend/transactions/tests/test_views.py::TestTransactionDetail::test_404_for_other_users_tx`
- Test failing with "precision lost"? Check Section 3a (Decimal Safety)
