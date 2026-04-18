# Account Reconciliation

Reconciliation in ClearMoney is a two-layer system that verifies account balances match real-world bank balances. It combines manual user verification with automated balance auditing.

## Overview

| Layer | Purpose | Frequency |
|-------|---------|-----------|
| **Manual reconciliation** | User verifies transactions match bank statement | On-demand (warnings at 30+ days) |
| **System reconciliation** | Automated audit of `initial_balance + SUM(balance_delta)` vs `current_balance` | Daily (startup jobs) |

## User Reconciliation Workflow

### Step-by-Step

1. **Navigate** to `/accounts/<id>/reconcile` from the account detail page
2. **Enter real bank balance** — the balance shown in your bank's app/website
3. **Review unverified transactions** — transactions since last reconciliation appear in a checklist
4. **Select verified transactions** — check boxes for transactions you confirm are correct
5. **Submit** — marks selected transactions as `is_verified=True` and sets `last_reconciled_at`

### Visual Feedback

- **Balanced** (green) — entered balance matches system balance (difference < 0.01)
- **Difference** (red) — variance shown (e.g., "+150.00" or "-50.00")

### Warning Banners

Dashboard shows health warnings for accounts:

- `reconciliation_missing` — account has transactions but never reconciled (suppressed for accounts < 30 days old)
- `reconciliation_stale` — last reconciliation was 30+ days ago

## How It Works (Technical)

### Data Model

**Transaction model** (`backend/core/models.py`):
```python
is_verified = models.BooleanField(default=False, db_default=False)
```

**Account model** (`backend/core/models.py`):
```python
last_reconciled_at = models.DateTimeField(null=True, blank=True)
```

### Service Layer

**File:** `backend/accounts/services.py`

```python
def reconcile(self, account_id: str, verified_tx_ids: list[str]) -> None:
    """Mark transactions as verified and update account's last_reconciled_at."""
    with transaction.atomic():
        Transaction.objects.for_user(self.user_id).filter(
            account_id=account_id, id__in=verified_tx_ids
        ).update(is_verified=True, updated_at=now)

        self._qs().filter(id=account_id).update(
            last_reconciled_at=now, updated_at=now
        )
```

### Views

**File:** `backend/accounts/views.py`

| Route | Method | Handler | Purpose |
|-------|--------|---------|---------|
| `/accounts/<id>/reconcile` | GET | `reconcile_page()` | Reconciliation form |
| `/accounts/<id>/reconcile/submit` | POST | `reconcile_submit()` | Complete reconciliation |

### Template

**File:** `backend/accounts/templates/accounts/reconcile.html`

- Displays current system balance
- Input field for real bank balance
- JavaScript calculates difference in real-time
- Checklist of unverified transactions
- "Select All" button for convenience

## System Reconciliation (Automated)

**File:** `backend/jobs/services/reconcile.py`

Runs daily via `reconcile_balances` management command (part of startup jobs).

### Formula

```
expected_balance = initial_balance + SUM(balance_delta)
discrepancy = expected_balance - current_balance
```

### Implementation

```python
class ReconcileService:
    def reconcile(self, auto_fix: bool = False) -> list[Discrepancy]:
        # Correlated subquery: SUM(balance_delta) per account
        delta_sum = (
            Transaction.objects.filter(account=OuterRef("pk"))
            .values("account_id")
            .annotate(s=Sum("balance_delta"))
            .values("s")
        )

        accounts = Account.objects.annotate(
            expected_balance=F("initial_balance") + Coalesce(
                Subquery(delta_sum, output_field=DecimalField()),
                Decimal("0"),
            )
        )

        # Compare expected vs cached balance
        for account in accounts:
            diff = float(account.expected_balance) - float(account.current_balance)
            if abs(diff) > TOLERANCE:  # TOLERANCE = 0.005
                discrepancies.append(Discrepancy(...))
```

### Tolerance

- **0.005** — avoids floating-point noise on `NUMERIC(15,2)` values
- Discrepancies > 0.005 are logged and optionally auto-fixed

### Auto-Fix

```bash
# Report only
python manage.py reconcile_balances

# Auto-fix discrepancies
python manage.py reconcile_balances --fix
```

Auto-fix updates `current_balance` to match `expected_balance`. Use with caution — only appropriate for denormalization drift, not missing transactions.

## Handling Discrepancies ("Evaporated Money")

### What Users See

1. **Difference indicator** on reconcile page shows variance amount
2. **Warning banners** on dashboard for stale/missing reconciliation
3. **No automatic correction** — users must investigate and add missing transactions manually

### What Developers See

- Discrepancies logged by `ReconcileService.reconcile()`
- Can run `make reconcile` to check all accounts
- Can run `make reconcile-fix` to auto-fix denormalization drift

### What Reconciliation Does NOT Do

- **Does not create adjustment entries** — unlike real accounting software, there's no "force balance" or "unknown variance" entry type
- **Does not find missing transactions** — only flags that a discrepancy exists
- **Does not prevent future discrepancies** — users must add transactions consistently

### Recommended User Actions

If money "evaporated" (discrepancy detected):

1. **Enter real bank balance** on reconcile page
2. **Note the difference** (e.g., "-500.00" means system is 500 higher than bank)
3. **Review unverified transactions** — look for duplicates, wrong amounts
4. **Check for missing transactions** — spending not yet recorded
5. **Add missing transactions** manually via transaction form
6. **Re-reconcile** — difference should now be zero

## Comparison to Real-World Accounting

| Aspect | Real-World Accounting | ClearMoney |
|--------|----------------------|------------|
| **Core concept** | Verify books match bank statements | Same — verify system balances match real bank |
| **Frequency** | Monthly (typically) | Any time; warnings at 30+ days |
| **Unit of verification** | Statement period | Per-transaction (`is_verified` flag) |
| **Starting point** | Opening balance carried forward | `initial_balance` field |
| **Ending verification** | Closing balance must match | Enter real balance; system calculates diff |
| **What if money missing?** | Create "unknown" adjustment entry, investigate | Difference shown; user must add missing transactions manually |
| **Audit trail** | Paper receipts, bank statements | `balance_delta` per transaction, `is_verified`, `last_reconciled_at` |
| **Tolerance** | Typically $0 | 0.005 (penny) |
| **Auto-fix capability** | Never | Optional (`reconcile_balances --fix`) |

### Key Differences

**Real accounting:**
1. Trace through every transaction
2. Find error (duplicate, missing, wrong amount)
3. Create correcting journal entry with reason code
4. Reconcile to zero

**ClearMoney:**
1. System shows difference amount
2. User reviews unverified transactions
3. User adds missing transactions manually
4. Re-reconcile to verify

**Why no adjustment entries?** ClearMoney is a personal finance tracker, not double-entry accounting. Every transaction should represent a real financial event. "Unknown" adjustments would hide data quality issues rather than resolve them.

## Commands

```bash
# Check balance consistency across all accounts
make reconcile

# Auto-fix discrepancies (use with caution)
make reconcile-fix
```

## Key Files

| File | Purpose |
|------|---------|
| `backend/accounts/services.py` | `AccountService.reconcile()` — marks transactions verified |
| `backend/accounts/views.py` | `reconcile_page()`, `reconcile_submit()` — HTTP handlers |
| `backend/accounts/templates/accounts/reconcile.html` | Reconciliation form template |
| `backend/jobs/services/reconcile.py` | `ReconcileService` — automated balance auditing |
| `backend/jobs/management/commands/reconcile_balances.py` | Management command |
| `backend/accounts/models.py` | `Account.last_reconciled_at`, `Transaction.is_verified` |
| `backend/accounts/tests/test_reconciliation.py` | Unit tests for reconciliation flow |
| `e2e/tests/test_reconciliation.py` | E2E tests for reconcile page workflow |

## For Newcomers

- **Reconciliation is advisory** — doesn't block anything, just flags potential issues
- **`is_verified` is user-set** — doesn't validate correctness, just marks "I checked this"
- **`balance_delta` is critical** — system reconciliation depends on this field being correct
- **Auto-fix is for drift only** — use `reconcile_balances --fix` only for denormalization bugs, not missing transactions
- **30-day grace period** — new accounts don't show reconciliation warnings until 30 days old
- **No "force balance" button** — users must manually add missing transactions to resolve discrepancies

## Testing

### Unit Tests

```bash
# Run reconciliation unit tests
pytest backend/accounts/tests/test_reconciliation.py
pytest backend/jobs/tests/test_reconcile_service.py
```

### E2E Tests

```bash
# Run reconciliation E2E tests
cd e2e && npx playwright test tests/test_reconciliation.py
```

### Manual Testing

1. Create account with initial balance 10,000
2. Add expense transaction 500
3. Navigate to `/accounts/<id>/reconcile`
4. Enter real balance 9,500 → should show "Balanced"
5. Enter real balance 9,000 → should show difference "-500.00"
6. Select transaction, submit
7. Verify `last_reconciled_at` updated in DB

## Related Documentation

- [Transactions](transactions.md) — `balance_delta` field, transaction types
- [Accounts & Institutions](accounts-and-institutions.md) — account model, balance tracking
- [Backend Architecture](../BACKEND_ARCHITECTURE.md) — balance update atomicity
- [Test Flows](../qa/TEST-FLOWS.md) — reconciliation test scenarios
