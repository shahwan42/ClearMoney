# ClearMoney QA Issues — Quick Reference

## Critical Issues (Fix Immediately)

### ✅ #1: Floating-Point Precision Loss — FIXED
- **Where:** `transactions/services/crud.py` — All float conversions removed
- **What:** Decimal amounts converted to float → precision loss
- **Impact:** Large transactions (>10M) and running balance calculations
- **Fix:** ✅ DONE: Use `str(Decimal)` instead of `float(Decimal)` in all serialization
- **Files Modified:**
  - `backend/transactions/services/crud.py` — Updated `_tx_instance_to_dict`, `_get_account`, `_scan_tx_row`, `create`, `update`, `delete`
  - `backend/transactions/services/helpers.py` — Updated virtual account helpers
  - Tests updated to parse string amounts with `Decimal()`
- **Verification:** All 1128 tests passing
- **Commit:** Ready to commit

### 🔴 #2: Duplicate Transaction Creation
- **Where:** All transaction POST endpoints
- **What:** No idempotency protection; rapid double-click creates duplicates
- **Impact:** Data integrity; users accidentally create multiple identical transactions
- **Fix:** Add Idempotency-Key header + Redis cache deduplication
- **Effort:** 6 hours

### 🔴 #3: No Pagination (Scalability)
- **Where:** `transactions/views/transactions.py`
- **What:** All transactions loaded at once
- **Impact:** UI lag >100 items, poor mobile performance
- **Fix:** Implement offset pagination (limit 50) + HTMX infinite scroll
- **Effort:** 4 hours

---

## Medium Issues (Fix This Sprint)

### 🟠 #4: Missing Form Constraints
- **Where:** All HTML forms (`*.html` templates)
- **What:** No `maxlength`, `max`, `min` attributes
- **Impact:** Silent data truncation, poor UX
- **Fix:** Add HTML5 validation attributes
- **Effort:** 2 hours

### 🟠 #5: No Future Date Validation
- **Where:** `transactions/services/crud.py:189-191`
- **What:** Users can create transactions dated year 2099
- **Impact:** Reporting includes phantom future data
- **Fix:** Add `if tx_date > today: raise ValueError`
- **Effort:** 1 hour

### 🟠 #6: Touch Targets < 44×44px
- **Where:** Bottom nav icons, dark mode toggle, header buttons
- **What:** Multiple interactive elements below WCAG AA minimum
- **Impact:** WCAG compliance failure, mobile usability
- **Fix:** Add padding/min-width/min-height
- **Effort:** 3 hours

### 🟠 #7: No Error Recovery UI
- **Where:** All HTMX forms
- **What:** Failed requests show generic error, no retry button
- **Impact:** Users lose work, poor UX
- **Fix:** Add error toast with retry button
- **Effort:** 4 hours

### 🟠 #8: No Offline Mode / Draft Persistence
- **Where:** `service-worker.js`, all form templates
- **What:** No draft saving; failed requests lose user input
- **Impact:** Data loss on poor connections
- **Fix:** IndexedDB drafts + service worker caching
- **Effort:** 6 hours

### 🟠 #9: Missing aria-describedby
- **Where:** All form error messages
- **What:** Error messages not linked to form fields
- **Impact:** Accessibility violation; screen readers miss context
- **Fix:** Add `aria-describedby` + `aria-invalid`
- **Effort:** 2 hours

### 🟠 #10: Missing aria-live Regions
- **Where:** Dynamic content updates (HTMX targets)
- **What:** No `aria-live="polite"` on updated elements
- **Impact:** Accessibility violation; screen readers miss updates
- **Fix:** Add `aria-live` and `aria-atomic` attributes
- **Effort:** 2 hours

---

## Issue Lookup by Component

### Transactions
- #1 Floating-point precision loss
- #2 Duplicate creation on double-click
- #3 No pagination
- #5 Future date validation missing
- #7 No error recovery UI
- #8 No offline mode

### Accounts
- #4 Missing form constraints
- #6 Touch targets too small
- #9 Missing aria-describedby

### All Components
- #10 Missing aria-live regions

---

## Test Failure Root Causes

| Test | Failure | Root Cause | Fix |
|------|---------|-----------|-----|
| `test_home_nav_item_min_44x44` | Fails | Icon 24×24 < 44×44 | Issue #6 |
| `test_credit_card_shows_credit_limit` | Fails | HTMX selector mismatch | Update selectors |
| `test_fintech_preset_fills_name` | Fails | Dialog rendering issue | Check UI changes |
| `test_investments` (all) | Fail | Feature incomplete | Implement feature |
| `test_more_menu` (all) | Fail | Dialog rendering | Check template |
| `test_people` (all) | Fail | Missing data setup | Fix test fixtures |

---

## Performance Baselines

**Current State:**
- Dashboard FCP: ~1.5-2.0s
- Lighthouse Performance: ~70
- Transaction list load: O(n) all items

**Target (After Fixes):**
- Dashboard FCP: <1.0s
- Lighthouse Performance: 85+
- Transaction list load: O(1) paginated

---

## Floating-Point Precision Issue — Examples

### The Problem
```python
# Database (correct):
current_balance = Decimal('123456789.99')

# JavaScript after float conversion:
amount = 123456789.99  # Appears correct but...
amount + 0.01 = 123456790.0  # Lost precision!

# Running balance calculation:
balance = 123456789.00
balance -= 0.03  # Running 100 transactions of 0.03
balance == 123456791.00  # Should be 123456789.00!
```

### The Fix
```python
# ✅ Keep as Decimal strings in API
def transaction_to_dict(tx):
    return {
        'amount': str(tx.amount),  # '123456789.99'
        'balance_delta': str(tx.balance_delta),
        # ...
    }

# Client handles with decimal.js library
import Decimal from 'decimal.js';
const amount = new Decimal(data.amount);  // Exact arithmetic
```

---

## Duplicate Transaction Issue — Scenario

### The Problem
```
User clicks "Save Transaction"
  ↓
Button disables, request in-flight (500ms)
  ↓
User double-clicks at 400ms (impatient)
  ↓
Button re-enables prematurely (race condition)
  ↓
Server creates BOTH transactions
  ↓
User sees duplicate entry
```

### The Fix
```python
# Backend: Cache by idempotency key
import hashlib
from django.core.cache import cache

def create_transaction(request):
    # Idempotency key = hash(body + user_id)
    key_data = request.body + str(request.user_id).encode()
    idempotency_key = hashlib.sha256(key_data).hexdigest()

    # Check if already processed
    result = cache.get(f'idempotency:{idempotency_key}')
    if result:
        return JsonResponse(result)  # Return cached result

    # Create transaction
    tx = create_transaction_service.create(...)

    # Cache result (5 min dedup window)
    cache.set(f'idempotency:{idempotency_key}', tx, timeout=300)
    return JsonResponse(tx)

# Frontend: Never re-enable button
hx-on="htmx:xhr:loadstart: htmx.disabled('#save-btn', true)"
      htmx:xhr:loadend: htmx.disabled('#save-btn', false) (ONLY on success)
```

---

## WCAG Touch Target Issue

### Current (FAILING)
```html
<button class="w-6 h-6">  <!-- 24×24px = 1.5rem -->
  🌙
</button>
```

### Fixed (PASSING)
```html
<button class="p-3 flex items-center justify-center"
        style="min-width: 44px; min-height: 44px;">
  <span aria-hidden="true">🌙</span>
  <span class="sr-only">Toggle dark mode</span>
</button>
```

---

## Priority Implementation Order

### Week 1 (Critical)
- [ ] Fix floating-point precision (#1) — 4h
- [ ] Implement idempotency (#2) — 6h
- [ ] Add pagination (#3) — 4h
- **Total: 14h**

### Week 2 (Medium High)
- [ ] Add form constraints (#4) — 2h
- [ ] Future date validation (#5) — 1h
- [ ] Fix touch targets (#6) — 3h
- [ ] Error recovery UI (#7) — 4h
- **Total: 10h**

### Week 3 (Medium)
- [ ] Offline mode & drafts (#8) — 6h
- [ ] Fix aria-describedby (#9) — 2h
- [ ] Fix aria-live regions (#10) — 2h
- **Total: 10h**

---

## Quick Fix Checklist

### Before Committing
- [ ] No float() conversions of Decimal values
- [ ] All form inputs have maxlength or max
- [ ] All date inputs have max="{{ today }}"
- [ ] All buttons have min-height: 44px
- [ ] All error messages have aria-describedby
- [ ] All dynamic targets have aria-live
- [ ] All transaction creates use idempotency key
- [ ] Pagination limit set to 50 per page

### Before Release
- [ ] `make test` passes (no regressions)
- [ ] `make test-e2e` passes (140 tests)
- [ ] `make lint` passes (zero errors)
- [ ] Lighthouse Performance > 85
- [ ] Lighthouse Accessibility > 90
- [ ] No float precision issues in test data

---

## Code Review Reminders

When reviewing PRs, check for:
1. **No float() on Decimal** — Use str() instead
2. **Form constraints** — maxlength, min, max attributes
3. **Touch targets** — min 44×44px
4. **Accessibility** — aria-describedby, aria-live, role attributes
5. **Error handling** — Try/catch with user-friendly messages
6. **Performance** — Pagination for lists > 50 items
7. **Security** — Idempotency checks, CSRF protection

---

## Contact & Questions

For issues or clarifications:
- See full report: `docs/qa/QA_TESTING_REPORT.md`
- See technical details: `docs/qa/TECHNICAL_FINDINGS.md`
- Baseline metrics recorded on 2026-03-25

