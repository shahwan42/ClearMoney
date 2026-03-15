# Installments

Payment plan tracking for items purchased in installments. Define a plan, track payments, and monitor progress.

## Concept

An installment plan tracks:
- **Total amount** and **number of installments**
- **Monthly amount** (auto-computed or manually set)
- **Remaining installments** (decremented on each payment)
- **Associated account** (where payments come from)

## Model

**File:** `internal/models/installment.go`

```go
type InstallmentPlan struct {
    ID                    string
    AccountID             string
    Description           string
    TotalAmount           float64
    NumInstallments       int
    MonthlyAmount         float64
    StartDate             time.Time
    RemainingInstallments int
    CreatedAt             time.Time
    UpdatedAt             time.Time
}
```

Key methods:
- `IsComplete() bool` — returns `RemainingInstallments <= 0` (uses ≤ for safety)
- `PaidInstallments() int` — returns `NumInstallments - RemainingInstallments`

## Repository

**File:** `internal/repository/installment.go`

| Method | Purpose |
|--------|---------|
| `Create(ctx, plan)` | Insert with RETURNING |
| `GetAll(ctx)` | All plans, active first (ordered by remaining DESC, start_date DESC) |
| `GetByID(ctx, id)` | Single plan |
| `RecordPayment(ctx, id)` | **Atomic decrement:** `remaining_installments = remaining_installments - 1 WHERE remaining > 0` |
| `Delete(ctx, id)` | Remove plan |

`RecordPayment` uses a WHERE guard (`remaining_installments > 0`) to prevent over-decrementing.

## Service

**File:** `internal/service/installment.go`

### Create (line ~40)

Validates required fields, auto-computes `MonthlyAmount = TotalAmount / NumInstallments` if not set. Sets `RemainingInstallments = NumInstallments`.

### RecordPayment (line ~75)

Two-step operation:
1. Creates an **expense transaction** via TransactionService:
   - Amount = MonthlyAmount
   - AccountID = plan's AccountID
   - Note = "Installment X/Y: Description"
2. Calls `repo.RecordPayment()` to decrement remaining

**Order matters:** if transaction creation fails, payment is not recorded.

**Service-to-service dependency:** InstallmentService delegates to TransactionService for creating expense transactions (which handles balance updates).

## Handler

**File:** `internal/handler/pages.go`

| Route | Method | Handler | Purpose |
|-------|--------|---------|---------|
| `/installments` | GET | `Installments()` | Page with all plans |
| `/installments/add` | POST | `InstallmentAdd()` | Create plan |
| `/installments/{id}/pay` | POST | `InstallmentPay()` | Record payment |
| `/installments/{id}` | DELETE | `InstallmentDelete()` | Delete plan |

## Template

**File:** `internal/templates/pages/installments.html`

Sections:
1. **Create plan form** — description, total_amount, num_installments, account, start_date
2. **Plans list** — for each plan:
   - Description, progress (X/Y paid), monthly amount
   - Total amount, "Completed" badge or remaining count
   - Progress bar (width = `percentage` template function)
   - Record Payment button + Delete button (if not complete)

## Key Files

| File | Purpose |
|------|---------|
| `internal/models/installment.go` | InstallmentPlan struct, IsComplete(), PaidInstallments() |
| `internal/repository/installment.go` | CRUD, atomic payment decrement |
| `internal/service/installment.go` | Validation, RecordPayment with transaction creation |
| `internal/handler/pages.go` | Installment handlers |
| `internal/templates/pages/installments.html` | Installments page |

## For Newcomers

- **Service-to-service dependency** — InstallmentService creates expense transactions via TransactionService. This ensures balance updates happen correctly.
- **Auto-computed monthly amount** — `TotalAmount / NumInstallments`. This may not divide evenly (e.g., 1000/3 = 333.33), so the last payment may differ slightly.
- **Atomic decrement** — `remaining_installments - 1 WHERE remaining > 0` prevents negative remaining.
- **No scheduling** — payments are manual (user clicks "Record Payment"). Unlike recurring rules, installments don't auto-execute.

## Logging

**Service events:**

- `installment.created` — new installment plan created (account_id)
- `installment.payment_recorded` — payment recorded for a plan (id)
- `installment.deleted` — installment plan removed (id)

**Page views:** `installments`
