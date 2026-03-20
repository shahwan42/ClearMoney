# Installments

Payment plan tracking for items purchased in installments. Define a plan, track payments, and monitor progress.

## Concept

An installment plan tracks:
- **Total amount** and **number of installments**
- **Monthly amount** (auto-computed or manually set)
- **Remaining installments** (decremented on each payment)
- **Associated account** (where payments come from)

## Model

**File:** `backend/core/models.py`

`InstallmentPlan` columns: `id` (UUID), `user_id` (FK), `account_id` (FK), `description`, `total_amount` (NUMERIC), `num_installments`, `monthly_amount` (NUMERIC), `start_date`, `remaining_installments`, `created_at`, `updated_at`.

Key properties:
- `is_complete` — returns `remaining_installments <= 0`
- `paid_installments` — returns `num_installments - remaining_installments`

## Service

**File:** `backend/installments/services.py`

### Create

Validates required fields, auto-computes `monthly_amount = total_amount / num_installments` if not set. Sets `remaining_installments = num_installments`.

### RecordPayment

Two-step operation:
1. Creates an **expense transaction** via TransactionService:
   - Amount = monthly_amount
   - account_id = plan's account_id
   - Note = "Installment X/Y: Description"
2. Decrements `remaining_installments`

**Order matters:** if transaction creation fails, payment is not recorded.

**Service-to-service dependency:** InstallmentService delegates to TransactionService for creating expense transactions (which handles balance updates).

## Views

**File:** `backend/installments/views.py`

| Route | Method | Handler | Purpose |
|-------|--------|---------|---------|
| `/installments` | GET | `installments()` | Page with all plans |
| `/installments/add` | POST | `installment_add()` | Create plan |
| `/installments/{id}/pay` | POST | `installment_pay()` | Record payment |
| `/installments/{id}/delete` | POST | `installment_delete()` | Delete plan |

## Template

**File:** `backend/installments/templates/installments/installments.html`

Sections:
1. **Create plan form** — description, total_amount, num_installments, account, start_date
2. **Plans list** — for each plan:
   - Description, progress (X/Y paid), monthly amount
   - Total amount, "Completed" badge or remaining count
   - Progress bar
   - Record Payment button + Delete button (if not complete)

## Key Files

| File | Purpose |
|------|---------|
| `backend/core/models.py` | InstallmentPlan model, is_complete, paid_installments |
| `backend/installments/services.py` | Validation, RecordPayment with transaction creation |
| `backend/installments/views.py` | Views for installment pages |
| `backend/installments/templates/installments/installments.html` | Installments page |

## For Newcomers

- **Service-to-service dependency** — InstallmentService creates expense transactions via TransactionService. This ensures balance updates happen correctly.
- **Auto-computed monthly amount** — `total_amount / num_installments`. May not divide evenly, so the last payment may differ slightly.
- **Atomic decrement** — `remaining_installments - 1 WHERE remaining > 0` prevents negative remaining.
- **No scheduling** — payments are manual (user clicks "Record Payment"). Unlike recurring rules, installments don't auto-execute.

## Logging

**Service events:**

- `installment.created` — new installment plan created (account_id)
- `installment.payment_recorded` — payment recorded for a plan (id)
- `installment.deleted` — installment plan removed (id)

**Page views:** `installments`
