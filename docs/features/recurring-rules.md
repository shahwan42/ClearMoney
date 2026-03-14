# Recurring Rules

Automate repetitive transactions with configurable scheduling. Rules can auto-execute or require manual confirmation.

## Concept

A recurring rule defines a transaction template that executes on a schedule. Two modes:

- **Auto-confirm** — transaction created automatically when due (processed on app startup)
- **Manual-confirm** — shows as pending for user to confirm or skip

## Model

**File:** `internal/models/recurring.go`

### RecurringRule

```go
type RecurringRule struct {
    ID                  string
    TemplateTransaction json.RawMessage  // raw JSON, parsed on demand
    Frequency           RecurringFrequency
    DayOfMonth          *int             // nullable
    NextDueDate         time.Time
    IsActive            bool
    AutoConfirm         bool
    CreatedAt           time.Time
    UpdatedAt           time.Time
}
```

### TransactionTemplate

Deserialized form of `TemplateTransaction`:

```go
type TransactionTemplate struct {
    Type       string
    Amount     float64
    Currency   string
    AccountID  string
    CategoryID *string  // nullable
    Note       *string  // nullable
}
```

**Key design:** `TemplateTransaction` is stored as `json.RawMessage` (raw JSON bytes) and only parsed with `json.Unmarshal` when the rule is executed. This avoids unnecessary deserialization.

### Frequency

- `Monthly` — advances by 1 month (`AddDate(0, 1, 0)`)
- `Weekly` — advances by 7 days (`AddDate(0, 0, 7)`)

**Note:** Go's `AddDate(0, 1, 0)` on Jan 31 gives Mar 3 (not Feb 28). This differs from Laravel's Carbon behavior.

## Database

Rules are stored with the template transaction as JSONB. The `next_due_date` column allows efficient "what's due?" queries.

## Repository

**File:** `internal/repository/recurring.go`

| Method | Purpose |
|--------|---------|
| `Create(ctx, rule)` | Insert with JSONB template_transaction |
| `GetByID(ctx, id)` | Single rule |
| `GetAll(ctx)` | All rules ordered by next_due_date ASC |
| `GetDue(ctx)` | **Key query:** Active rules where `next_due_date <= CURRENT_DATE` |
| `UpdateNextDueDate(ctx, id, date)` | Advance after execution |
| `Delete(ctx, id)` | Remove rule |
| `DeleteByAccountID(ctx, accountID)` | Cleanup stale rules when account deleted (uses JSONB `->>'account_id'`) |

### DeleteByAccountID

Uses PostgreSQL JSONB operator to find rules referencing a deleted account:

```sql
WHERE template_transaction->>'account_id' = $1
```

This prevents stale references since the account_id is inside JSON, not a real FK.

## Service

**File:** `internal/service/recurring.go`

### ProcessDueRules (line ~85)

Called on **app startup** (before HTTP server starts):
1. Gets all due rules via `GetDue()`
2. Skips `auto_confirm=false` (manual only)
3. For each auto-confirm rule, calls `executeRule()`
4. Returns count of transactions created
5. Errors don't stop server — failed rules are skipped with warning log

### executeRule (line ~130)

Core logic:
1. `json.Unmarshal(rule.TemplateTransaction, &tmpl)` — parse JSONB
2. Guard: check if accountID still exists (FK not enforced on JSONB)
3. Build Transaction from template (sets Date = NextDueDate, RecurringRuleID = rule.ID)
4. Call `txSvc.Create()` — delegates to TransactionService for balance updates
5. Call `advanceDueDate()` to compute next due date
6. Update rule's NextDueDate

### ConfirmRule / SkipRule

- **Confirm:** Gets rule, calls `executeRule()` — creates transaction and advances
- **Skip:** Advances due date without creating transaction

### advanceDueDate (line ~167)

```go
switch rule.Frequency {
case "weekly":  return current.AddDate(0, 0, 7)
case "monthly": return current.AddDate(0, 1, 0)
default:        return current.AddDate(0, 1, 0)
}
```

## Handler

**File:** `internal/handler/pages.go`

| Route | Method | Handler | Purpose |
|-------|--------|---------|---------|
| `/recurring` | GET | `Recurring()` | Page with pending + active rules |
| `/recurring/add` | POST | `RecurringAdd()` | Create rule |
| `/recurring/{id}/confirm` | POST | `RecurringConfirm()` | Confirm pending rule |
| `/recurring/{id}/skip` | POST | `RecurringSkip()` | Skip pending rule |
| `/recurring/{id}` | DELETE | `RecurringDelete()` | Delete rule |

### RecurringAdd Handler

1. Parses form (type, amount, account, category, note, frequency, next_due_date, auto_confirm)
2. Builds `TransactionTemplate` struct
3. `json.Marshal()` to get JSONB bytes
4. Looks up account to get currency
5. Builds `RecurringRule` with template
6. Creates via service

## Templates

### Page

**File:** `internal/templates/pages/recurring.html`

Sections:
1. **Pending confirmations** — amber cards with Confirm/Skip buttons
2. **Create new rule** form (recurring-form partial)
3. **Active rules** — table with note, frequency, next due, amount, auto label, delete button

### Partial

**File:** `internal/templates/partials/recurring-form.html`

Form with:
- Type toggle (Expense/Income)
- Amount input
- Account/Category dropdowns
- Note, Frequency (Monthly/Weekly), Next Due date
- Auto-confirm checkbox

## Startup Integration

**File:** `cmd/server/main.go` (lines ~93-109)

```go
// Before HTTP server starts:
recurringSvc := service.NewRecurringService(recurringRepo, txSvc)
count, err := recurringSvc.ProcessDueRules(context.Background())
slog.Info("recurring: auto-created transactions", "count", count)
```

Runs once on every app startup. Errors don't prevent server from starting.

## Key Files

| File | Purpose |
|------|---------|
| `internal/models/recurring.go` | RecurringRule, TransactionTemplate structs |
| `internal/repository/recurring.go` | CRUD, GetDue, JSONB account cleanup |
| `internal/service/recurring.go` | ProcessDueRules, executeRule, ConfirmRule, SkipRule |
| `internal/handler/pages.go` | Recurring handlers |
| `internal/templates/pages/recurring.html` | Recurring page |
| `internal/templates/partials/recurring-form.html` | Create rule form |
| `cmd/server/main.go` | Startup processing |

## For Newcomers

- **JSONB for template** — the transaction template is stored as raw JSON, not separate columns. This keeps the schema simple but means FK constraints on account_id aren't enforced by the DB.
- **Startup processing** — rules are only processed on app restart, not via a cron job. If the app is down for days, all missed rules will execute on next startup.
- **Service-to-service dependency** — RecurringService delegates to TransactionService for creating transactions (balance updates, etc.).
- **Account deletion cleanup** — `DeleteByAccountID` uses JSONB operators to find and remove rules referencing deleted accounts.
