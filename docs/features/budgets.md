# Budgets

Monthly spending limits per category with traffic-light progress tracking. Budget progress is shown on both the dedicated budgets page and the dashboard.

## Concept

ClearMoney supports two types of budgets:

1. **Per-category budgets** — spending limits for individual expense categories
2. **Total monthly budget** — overall spending cap for all categories combined

### Per-Category Budget

A budget ties a monthly spending limit to a specific expense category and currency. As you spend in that category during the month, the progress bar fills up with color-coded status:

- **Green** — under 80% of limit
- **Amber** — 80-99% of limit
- **Red** — at or over 100% of limit

### Total Monthly Budget

An optional overall spending cap across all categories in a specific currency. If set, the dashboard warns if individual category budgets sum to more than the total budget.

## Models

**File:** `backend/core/models.py` — `Budget`

| Field | Type | Notes |
|-------|------|-------|
| `category` | FK → Category | Required |
| `user` | FK → User | Per-user isolation |
| `monthly_limit` | NUMERIC(15,2) | Must be > 0 |
| `currency` | varchar | `EGP` or `USD` |
| `is_active` | bool | Defaults to True |

Unique constraint: `(user_id, category_id, currency)` — prevents duplicate budgets for the same category+currency.

### TotalBudget Model

**File:** `backend/core/models.py` — `TotalBudget`

| Field | Type | Notes |
|-------|------|-------|
| `user` | FK → User | Per-user isolation |
| `amount` | NUMERIC(15,2) | Monthly total spending cap, must be > 0 |
| `currency` | varchar | `EGP` or `USD` |
| `month` | DATE | First day of month (YYYY-MM-01) |

Unique constraint: `(user_id, month, currency)` — one total budget per month per currency.

**Purpose:** Sets an overall spending ceiling for a month. Dashboard warns if individual category budgets sum to more than the total budget.

## Service

**File:** `backend/budgets/services.py`

**Per-Category Budget Methods:**

| Function | Purpose |
|----------|---------|
| `get_all_with_spending(user_id, year, month)` | Returns budgets with computed spent/remaining/percentage/status |
| `create(user_id, data)` | Validates: category required, limit > 0, defaults currency to EGP |
| `delete(user_id, budget_id)` | Hard delete |

**Total Budget Methods:**

| Function | Purpose |
|----------|---------|
| `get_total_budget(user_id, currency)` | Returns TotalBudget with computed spending + status (red/amber/green), or None if not set |
| `set_total_budget(user_id, limit, currency)` | Create or update total monthly budget |
| `delete_total_budget(user_id, currency)` | Delete total budget |

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

**Per-Category Budget Routes:**

| Route | Method | Purpose |
|-------|--------|---------|
| `/budgets` | GET | Page with form + active budgets + total budget section |
| `/budgets/add` | POST | Create per-category budget, redirect to /budgets |
| `/budgets/{id}/delete` | POST | Delete per-category budget, redirect to /budgets |

**Total Budget Routes:**

| Route | Method | Purpose |
|-------|--------|---------|
| `/budgets/total/set` | POST | Create or update total monthly budget |
| `/budgets/total/delete` | POST | Delete total monthly budget |

## Templates

**File:** `backend/budgets/templates/budgets/budgets.html`

Sections:
1. **Total budget section** (if set):
   - Display total limit + current month spending
   - "Over total budget" warning if categories sum exceeds total
   - Set/update total button
   - Delete button if total exists
2. **Create per-category form** — category dropdown (expense categories), monthly limit input, currency select
3. **Active per-category budgets** — for each budget:
   - Category name + icon
   - Delete button
   - "Spent / Limit" text
   - Progress bar with color-coded width
   - Remaining amount (or "Over budget by X" if negative)
4. **Empty state** if no budgets

## Dashboard Integration

`DashboardData.budgets` holds a list of budget dicts with spending data from `get_all_with_spending()`. Dashboard shows budgets as compact status badges with colored dots (green/amber/red) and links to `/budgets` management page.

## Key Files

| File | Purpose |
|------|---------|
| `backend/core/models.py` | Budget and TotalBudget models |
| `backend/budgets/services.py` | Budget and TotalBudget services — spending calculation, validation, creation/deletion |
| `backend/budgets/views.py` | budgets_page, budget_add, budget_delete, total_budget_set, total_budget_delete views |
| `backend/budgets/templates/budgets/budgets.html` | Budgets page template (per-category + total budget sections) |
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
