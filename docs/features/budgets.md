# Budgets

Monthly spending limits per category with traffic-light progress tracking. Budget progress is shown on both the dedicated budgets page and the dashboard.

## Concept

A budget ties a monthly spending limit to a specific expense category and currency. As you spend in that category during the month, the progress bar fills up with color-coded status:

- **Green** — under 80% of limit
- **Amber** — 80-99% of limit
- **Red** — at or over 100% of limit

## Model

**File:** `internal/models/budget.go`

### Budget

```go
type Budget struct {
    ID           string
    CategoryID   string
    MonthlyLimit float64
    Currency     string   // "EGP" or "USD"
    IsActive     bool
    CreatedAt    time.Time
    UpdatedAt    time.Time
}
```

### BudgetWithSpending

Embeds `Budget` and adds computed fields:

```go
type BudgetWithSpending struct {
    Budget                     // Go struct embedding (inherits all Budget fields)
    CategoryName  string       // from JOIN
    CategoryIcon  string       // from JOIN
    Spent         float64      // SUM of expenses this month
    Remaining     float64      // MonthlyLimit - Spent
    Percentage    float64      // Spent / MonthlyLimit * 100
    Status        string       // "green", "amber", or "red"
}
```

`CategoryDisplayName()` helper returns icon + name if icon exists.

## Database

**Migration:** `internal/database/migrations/000016_create_budgets.up.sql`

- Table: `budgets` with UUID PK, FK to categories
- Unique constraint: `(category_id, currency)` — prevents duplicate budgets for same category+currency
- Columns: `id`, `category_id`, `monthly_limit` (NUMERIC 15,2), `currency`, `is_active`, timestamps

## Repository

**File:** `internal/repository/budget.go`

| Method | Purpose |
|--------|---------|
| `GetAll()` | All active budgets |
| `GetAllWithSpending(year, month)` | Complex JOIN: budgets → categories → transactions, computes spent/remaining/status |
| `Create(ctx, budget)` | Insert with RETURNING |
| `Delete(ctx, id)` | Hard delete |
| `GetByID(ctx, id)` | Single budget |

### GetAllWithSpending Query

This is the key query — it JOINs budgets with categories and LEFT JOINs transactions filtered by:
- `type = 'expense'`
- Date within the target month
- Currency match

Computes `Spent` via `COALESCE(SUM(t.amount), 0)`. The remaining fields (Remaining, Percentage, Status) are computed in Go after the query.

## Service

**File:** `internal/service/budget.go`

| Method | Purpose |
|--------|---------|
| `GetAllWithSpending()` | Gets current year/month, calls repo |
| `GetAll()` | Simple passthrough |
| `Create(ctx, budget)` | Validates: category required, limit > 0, defaults currency to EGP |
| `Delete(ctx, id)` | Passthrough |

## Handler

**File:** `internal/handler/pages.go`

| Route | Method | Handler | Purpose |
|-------|--------|---------|---------|
| `/budgets` | GET | `Budgets()` | Page with form + active budgets |
| `/budgets/add` | POST | `BudgetAdd()` | Create budget, redirect to /budgets |
| `/budgets/{id}/delete` | POST | `BudgetDelete()` | Delete budget, redirect to /budgets |

## Template

**File:** `internal/templates/pages/budgets.html`

Sections:
1. **Create form** — category dropdown (expense categories), monthly limit input, currency select
2. **Active budgets** — for each budget:
   - Category name + icon
   - Delete button
   - "Spent / Limit" text
   - Progress bar with color-coded width
   - Remaining amount (or "Over budget by X" if negative)
3. **Empty state** if no budgets

## Dashboard Integration

**File:** `internal/service/dashboard.go`

- `DashboardData.Budgets` holds `[]models.BudgetWithSpending`
- `SetBudgetService()` setter injects the service
- Dashboard shows budgets as compact status badges with colored dots (green/amber/red)
- Links to `/budgets` management page

**File:** `internal/templates/pages/home.html` (lines ~225-249)

## Key Files

| File | Purpose |
|------|---------|
| `internal/models/budget.go` | Budget, BudgetWithSpending structs |
| `internal/repository/budget.go` | SQL queries, spending calculation |
| `internal/service/budget.go` | Validation, business logic |
| `internal/handler/pages.go` | Budgets, BudgetAdd, BudgetDelete handlers |
| `internal/templates/pages/budgets.html` | Budgets page template |
| `internal/database/migrations/000016_create_budgets.up.sql` | Schema |

## For Newcomers

- **One budget per category+currency** — enforced by unique constraint.
- **Status thresholds** (80%/100%) are computed in Go, not stored in the DB.
- **Go struct embedding** — `BudgetWithSpending` embeds `Budget`, inheriting all fields without repetition.
- **Spending is recalculated each request** — no caching. Budget progress always reflects real-time spending.
- **Dashboard integration** uses setter injection on both PageHandler and DashboardService.

## Logging

**Service events:**

- `budget.created` — new budget created (currency, category_id)
- `budget.deleted` — budget removed (id)

**Page views:** `budgets`
