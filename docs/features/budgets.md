# Budgets

Monthly spending limits per category with traffic-light progress tracking. Budget progress is shown on both the dedicated budgets page and the dashboard.

## Concept

A budget ties a monthly spending limit to a specific expense category and currency. As you spend in that category during the month, the progress bar fills up with color-coded status:

- **Green** — under 80% of limit
- **Amber** — 80-99% of limit
- **Red** — at or over 100% of limit

## Model

**File:** `backend/core/models.py` — `Budget`

| Field | Type | Notes |
|-------|------|-------|
| `category` | FK → Category | Required |
| `user` | FK → User | Per-user isolation |
| `monthly_limit` | NUMERIC(15,2) | Must be > 0 |
| `currency` | enum | `EGP` or `USD` |
| `is_active` | bool | Defaults to True |

Unique constraint: `(user_id, category_id, currency)` — prevents duplicate budgets for the same category+currency.

## Service

**File:** `backend/budgets/services.py`

| Function | Purpose |
|----------|---------|
| `get_all_with_spending(user_id, year, month)` | Returns budgets with computed spent/remaining/percentage/status |
| `get_all(user_id)` | Simple list of active budgets |
| `create(user_id, data)` | Validates: category required, limit > 0, defaults currency to EGP |
| `delete(user_id, budget_id)` | Hard delete |

### Spending Query

`get_all_with_spending` JOINs budgets with categories and LEFT JOINs transactions filtered by:
- `type = 'expense'`
- Date within the target month
- Currency match

Computes `spent` via `COALESCE(SUM(t.amount), 0)`. The remaining/percentage/status fields are computed in Python after the query:

```python
spent = Decimal(row["spent"])
remaining = budget.monthly_limit - spent
percentage = float(spent / budget.monthly_limit * 100) if budget.monthly_limit else 0
status = "red" if percentage >= 100 else "amber" if percentage >= 80 else "green"
```

## Views

**File:** `backend/budgets/views.py`

| Route | Method | Purpose |
|-------|--------|---------|
| `/budgets` | GET | Page with form + active budgets |
| `/budgets/add` | POST | Create budget, redirect to /budgets |
| `/budgets/{id}/delete` | POST | Delete budget, redirect to /budgets |

## Template

**File:** `backend/budgets/templates/budgets/budgets.html`

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

`DashboardData.budgets` holds a list of budget dicts with spending data from `get_all_with_spending()`. Dashboard shows budgets as compact status badges with colored dots (green/amber/red) and links to `/budgets` management page.

## Key Files

| File | Purpose |
|------|---------|
| `backend/core/models.py` | Budget model |
| `backend/budgets/services.py` | Spending calculation + validation |
| `backend/budgets/views.py` | Budgets, BudgetAdd, BudgetDelete views |
| `backend/budgets/templates/budgets/budgets.html` | Budgets page template |
| `backend/budgets/tests/` | Service and view tests |

## For Newcomers

- **One budget per category+currency** — enforced by unique constraint.
- **Status thresholds** (80%/100%) are computed in Python, not stored in the DB.
- **Spending is recalculated each request** — no caching. Budget progress always reflects real-time spending.

## Logging

**Service events:**

- `budget.created` — new budget created (currency, category_id)
- `budget.deleted` — budget removed (id)

**Page views:** `budgets`
