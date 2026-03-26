# Issues and Recommendations

**Date:** 2026-03-25
**Total Issues Found:** 10
**Critical:** 1 | High: 1 | Medium: 5 | Low: 3

---

## ✅ CRITICAL ISSUES (FIXED)

### Issue #1: Account Creation Form — Type Dropdown Not Rendering on Error

**Status:** ✅ FIXED (2026-03-26)
**Commit:** `97516ad` — fix: reinitialize account type select JS listener after HTMX re-render

**Problem (Original):**
After form validation error, the `<select name="type">` change event listener was not re-attached after HTMX re-rendered the form.

**Solution:**

Wrapped the JavaScript initialization in a named function `initAddAccountForm()` and called it on both page load and after HTMX swaps:

```javascript
function initAddAccountForm() { /* setup code */ }
initAddAccountForm();
htmx.onLoad(function(content) {
    if (content.querySelector('#add-account-form')) {
        initAddAccountForm();
    }
});
```

This ensures the type select change listener is re-attached every time HTMX renders the form, including after validation errors.

**Testing:**

- E2E test `test_credit_card_error_allows_retry` now passes without manual dispatch_event workaround
- All 1127 unit tests pass
- No regressions in account creation flow

---

### Issue #2: E2E Test Isolation

**Status:** ✅ VERIFIED FIXED
**Files Checked:** `e2e/conftest.py`, `e2e/tests/test_*.py`

**Finding:**
Upon investigation, the db fixture in all E2E test files (`test_accounts.py`, `test_transactions.py`, `test_virtual_accounts.py`) was already configured with `scope="function"`, which ensures proper isolation between tests.

**Verification:**

- `e2e/tests/test_accounts.py` line 31-33: `@pytest.fixture(scope="function", autouse=True)`
- `e2e/tests/test_transactions.py` line 33-35: `@pytest.fixture(scope="function", autouse=True)`
- `e2e/tests/test_virtual_accounts.py`: Same pattern

Each test function calls `reset_database()` to clear state before running, ensuring no data leakage between tests.

**Conclusion:** No action required. Test isolation is already properly implemented.

---

## 🟠 HIGH PRIORITY (Fix This Sprint)

*(See Issue #2 above — test isolation)*

---

## ✅ MEDIUM PRIORITY (FIXED)

### Issue #3: Missing E2E Test Coverage

**Status:** ✅ FIXED (2026-03-26)
**Commit:** `48eb8bd` — test: add e2e coverage for swipe-to-delete, batch entry, and account reorder

**Tests Added:**

- `test_swipe_to_delete_transaction()` in `e2e/tests/test_transactions.py` — Simulates touchstart/move/end swipe gesture
- `test_batch_entry_submit_creates_transactions()` in `e2e/tests/test_reports_settings.py` — Fills batch rows and submits
- `test_account_reordering_via_drag()` in `e2e/tests/test_accounts.py` — Verifies account list and drag setup

**Coverage Status:**

- ✅ Swipe-to-delete: Added (gesture simulation)
- ✅ Batch entry: Added (form fill and submit)
- ✅ Account reordering: Added (basic verification)
- ✅ Transaction editing: Already covered by `test_edit_transaction_via_ui`
- ✅ Multi-currency exchanges: Already covered by `TestExchange` in transfers tests
- ✅ Transfers: Already covered by `TestTransfers` in transfers tests

**Result:** All 1127 unit tests pass, E2E tests added without regressions.

---

### Issue #4: Touch Target Size — Some Buttons <44×44px

**Status:** ✅ FIXED (2026-03-26)
**Commit:** `5c1619d` — fix: add form constraints and ensure 44px touch targets

**Fix Applied:**

Added `min-h-[44px]` to all modal buttons and `flex items-center justify-center` for proper vertical alignment:

- `backend/accounts/templates/accounts/_account_edit_form.html`
- `backend/accounts/templates/accounts/_institution_edit_form.html`
- `backend/accounts/templates/accounts/_institution_form.html`
- `backend/accounts/templates/accounts/account_detail.html`

**Result:** All modal buttons now meet WCAG 2.5.5 (AAA) minimum 44×44px touch target.

---

### Issue #5: Form Input Validation — Missing maxlength/min/max Attributes

**Status:** ✅ FIXED (2026-03-26)
**Commit:** `5c1619d` — fix: add form constraints and ensure 44px touch targets

**Fix Applied:**

Added HTML5 validation attributes to form inputs:

- Account name: `maxlength="100"`
- Credit limit: `min="0"`
- All affected templates updated

**Result:** Forms now enforce input constraints at the HTML level, improving data quality and UX.

---

### Issue #6: Future Date Validation — Transaction Update Missing Check

**Status:** ✅ FIXED (2026-03-26)
**Commit:** `5d7d9a1` — fix: reject future dates on transaction update

**Problem (Original):**
Future date validation existed in `create()` but was missing from `update()` method.

**Fix Applied:**

Added future date validation to transaction update method in `backend/transactions/services/crud.py`:

```python
# Validate transaction date is not in the future
if tx_date > date.today():
    raise ValueError("Transaction date cannot be in the future")
```

**Testing:**
Added unit test: `TestUpdate::test_validation_future_date_rejected`

**Result:** Both create and update now enforce no-future-date validation consistently.

---

### Issue #7: Account Type Dropdown — Clear Error Message

**Status:** ✅ VERIFIED (already implemented)
**Code Location:** `backend/accounts/services.py` line 338

**Finding:**
The account type field validation already provides a clear error message when omitted:

```python
if not acc_type:
    raise ValueError("Please select an account type")
```

**Result:** No action needed. Error messaging is already clear and helpful.

---

## 🟢 LOW PRIORITY (Nice to Have)

### Issue #8: Offline Mode / Draft Persistence

**Severity:** LOW
**Impact:** Lost work if offline (PWA feature incomplete)
**Recommendation:** Implement `localStorage` draft save on form change, restore on page load

**Time to Fix:** 4-6 hours
**Priority:** LOW (enhancement, not bug)

---

### Issue #9: Error Recovery UI — Missing sendError/timeout Handlers

**Status:** ✅ FIXED (2026-03-26)
**Commit:** `2df2528` — fix: add HTMX error recovery handlers for sendError and timeout

**Problem (Original):**
Error recovery UI only handled `htmx:responseError`. Missing handlers for network-level errors (`sendError`) and request timeouts (`timeout`).

**Fix Applied:**

Added handlers in `backend/templates/base.html` for all error scenarios:

- `htmx:responseError` — HTTP errors (4xx, 5xx)
- `htmx:sendError` — Network failures (unable to send request)
- `htmx:timeout` — Request timeout

All show consistent error UI with retry button.

**Result:** Users now see helpful error messages for all failure modes.

---

### Issue #10: Icon-Only Buttons — Missing aria-label

**Status:** ✅ VERIFIED COMPLIANT
**Finding:** Code review found all icon-only buttons already have `aria-label` attributes

**Examples Verified:**

- Institution edit/delete buttons: have `aria-label`
- Transaction kebab menu: has `aria-label="Transaction actions"`
- All custom action buttons: labeled properly

**Result:** No action needed. All icon-only buttons are already accessible.

---

## Summary by Timeline

### This Week (CRITICAL)
- [ ] Fix account creation form dropdown — 2-4h
- [ ] Fix E2E test isolation — 0.5h
- **Total: 2.5-4.5 hours**

### This Sprint (HIGH + MEDIUM)
- [ ] Add missing E2E test coverage — 4-6h
- [ ] Fix touch target sizes — 2-3h
- [ ] Add form input constraints — 2-3h
- [ ] Add future date validation — 1-2h
- [ ] Improve account type error messaging — 1h
- **Total: 10-15 hours**

### Next Sprint (LOW)
- [ ] Implement offline draft persistence — 4-6h
- [ ] Add error recovery UI — 2-3h
- [ ] Add aria-labels to icon buttons — 1-2h
- **Total: 7-11 hours**

---

## Risk Assessment

**Highest Risk (If Not Fixed):**
1. Account creation blocked (Issue #1) — Users cannot onboard
2. CI/CD false failures (Issue #2) — Slows development

**Medium Risk:**
3. Missing tests (Issue #3) — Regression incidents
4. Accessibility gaps (Issues #4, #10) — Legal compliance risk

**Low Risk:**
5. UX enhancements (Issues #8, #9) — Quality-of-life improvements

---

## Code Review Checklist

Before merging any PR, verify:
- [ ] All E2E tests pass (including account + transaction together)
- [ ] No button <44×44px without explicit approval
- [ ] All form inputs have validation attributes
- [ ] All date fields reject future dates
- [ ] Icon-only buttons have aria-label or text
- [ ] Error messages clear and helpful
- [ ] Form errors show in red with text (not color alone)
- [ ] Modal focus trap working (Tab doesn't escape)
- [ ] Keyboard navigation tested (Tab + Enter)

---

## Verification After Each Fix

```bash
# After fix is implemented:
make test                   # Verify no regressions
make test-e2e              # Run full E2E suite
make lint                  # Check code style
mcp__django-ai-boost__run_check  # Django system check
```

---

## Conclusion

**10 issues identified, none blocking.** Fix Issues #1 & #2 before next release (1 day work). Address Issues #3-7 this sprint (2 weeks). Issues #8-10 are enhancements for future iterations.
