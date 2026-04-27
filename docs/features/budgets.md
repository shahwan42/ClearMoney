# Budgets

Monthly spending limits per category with traffic-light progress tracking.
Budget status appears on both the dedicated budgets page and the dashboard.

## Concept

ClearMoney currently supports two related budget types:

1. **Per-category budgets** — spending limits for one expense category in one
   currency
2. **Total monthly budgets** — an optional overall spending cap per currency

### Per-Category Budgets

A category budget is scoped to:

- one user
- one expense category
- one currency

Current-month spending counts against that budget only when the transaction is:

- owned by the same user
- `type = "expense"`
- in the current month (or supplied target month)
- in the same category
- in the same currency

Status colors use the computed spending percentage:

- **Green** — under 80% of effective limit
- **Amber** — 80% to under 100%
- **Red** — 100% or more

### Rollover

Category budgets can optionally carry unused money from the previous month into
the current month.

- When `rollover_enabled` is on, unused prior-month budget is added to the
  current month’s effective limit.
- Carryover is computed as `max(0, monthly_limit - previous_month_spent)`.
- If `max_rollover` is set, carryover is capped at that amount.

Current limitation:

- The list/dashboard budget calculations apply rollover.
- The budget detail page does **not** currently apply rollover to its displayed
  percentage/remaining math.

### Copy Last Month

The budgets page includes a **Copy last month** action.

- It looks at last month’s expense spending grouped by `category + currency`.
- For each group without an existing budget, it creates a new budget using last
  month’s spending total as the monthly limit.
- Existing category/currency budgets are skipped.

### Total Monthly Budgets

A total budget is optional and is scoped to:

- one user
- one currency

It measures all current-month expense spending in that currency, regardless of
category.

- Uncategorized expense transactions still count toward the total budget.
- The UI warns when the sum of category budgets in a currency exceeds the total
  budget for that currency.

## Models

**File:** `backend/budgets/models.py`

### Budget

| Field | Type | Notes |
|-------|------|-------|
| `category` | FK → Category | Required |
| `user` | FK → User | Per-user isolation |
| `monthly_limit` | NUMERIC(15,2) | Must be > 0 |
| `currency` | varchar(3) | User-selectable active currency |
| `rollover_enabled` | bool | Enables prior-month carryover |
| `max_rollover` | NUMERIC(15,2), nullable | Optional cap on carryover |
| `is_active` | bool | Defaults to True |

Unique constraint: `(user_id, category_id, currency)` — one budget per
category per currency for a user.

### TotalBudget

| Field | Type | Notes |
|-------|------|-------|
| `user` | FK → User | Per-user isolation |
| `monthly_limit` | NUMERIC(15,2) | Must be > 0 |
| `currency` | varchar(3) | Per-currency total cap |
| `is_active` | bool | Defaults to True |

Unique constraint: `(user_id, currency)` — one total budget per currency for a
user.

## Service Behavior

**File:** `backend/budgets/services.py`

### Main Methods

| Function | Purpose |
|----------|---------|
| `get_all_with_spending(target_date=None)` | Returns active budgets with computed spent/remaining/percentage/status and rollover-adjusted effective limit |
| `copy_last_month_budgets()` | Creates missing category budgets from last month’s expense totals |
| `get_budget_with_transactions(budget_id)` | Returns one budget plus matching current-month transactions |
| `create(category_id, monthly_limit, currency="", rollover_enabled=False, max_rollover=None)` | Validates and creates a budget |
| `update(budget_id, monthly_limit=None, rollover_enabled=None, max_rollover=None)` | Updates mutable budget fields |
| `delete(budget_id)` | Hard deletes a category budget |
| `get_total_budget(currency="")` | Returns total budget with computed spending/status, or `None` |
| `set_total_budget(limit, currency="")` | Creates or updates the total budget for a currency |
| `delete_total_budget(currency="")` | Deletes the total budget for a currency |

### Currency Resolution

User-selectable budget currency is not hard-coded.

- Budget create and total-budget create/update accept any **active** user
  currency.
- If the submitted currency is blank, it resolves to the user’s selected
  display currency.
- Inactive currencies are rejected.

### Spending Calculation

`get_all_with_spending()` computes budget spending from matching expense
transactions and then calculates:

- `spent`
- `remaining`
- `percentage`
- `status`
- `rollover_amount`
- `effective_limit`

The total-budget calculation separately aggregates:

- all expense spending in the currency
- the sum of active category budgets in the currency

## Views and UI

**Files:** `backend/budgets/views.py`,
`backend/budgets/templates/budgets/budgets.html`,
`backend/budgets/templates/budgets/_total_budget_card.html`

### Routes

| Route | Method | Purpose |
|-------|--------|---------|
| `/budgets` | GET | Budgets page with total budget card and existing category budgets |
| `/budgets/add-form` | GET | Render the new budget form partial for the bottom sheet |
| `/budgets/add` | POST | Create a per-category budget |
| `/budgets/copy-last-month` | POST | Create missing budgets from last month’s spending |
| `/budgets/<id>/` | GET | Budget detail with contributing current-month transactions |
| `/budgets/<id>/edit-form` | GET | Render the category budget edit form partial for the bottom sheet |
| `/budgets/<id>/edit` | POST | Update monthly limit and rollover settings from the edit sheet |
| `/budgets/<id>/delete` | POST | Delete a category budget |
| `/budgets/total/set` | POST | Create or update a per-currency total budget |
| `/budgets/total/<currency>/edit-form` | GET | Render the total budget edit form partial for the bottom sheet |
| `/budgets/total/delete` | POST | Delete a per-currency total budget |

### Budgets Page

The page currently contains:

1. **Header Actions**
   - **+ Budget** button to open the creation bottom sheet
   - **Copy last month** button
2. **Total budget card**
   - shows spent, limit, remaining, and status for the selected currency’s
     total budget
   - warns when category-budget sum exceeds total budget
   - supports set, edit in a bottom sheet, and delete
3. **Create budget bottom sheet**
   - expense-category selector
   - monthly limit input
   - active-currency selector
   - rollover toggle
   - optional max carryover input
4. **Active budget cards**
   - category name/icon
   - spent vs limit
   - progress bar
   - remaining / over-budget message
   - edit opens a bottom sheet for monthly limit and rollover settings

### Defaults

- The category-budget create form uses the user’s active currencies and selects
  the current display currency by default.
- The empty total-budget form defaults to the selected display currency.

## Dashboard Integration

Dashboard budget summaries use the same category-budget spending computation as
the budgets module. The dashboard displays compact budget status data sourced
from `get_all_with_spending()`.

## Key Files

| File | Purpose |
|------|---------|
| `backend/budgets/models.py` | `Budget` and `TotalBudget` models |
| `backend/budgets/services.py` | Spending calculation, rollover, copy-last-month, validation, total budget logic |
| `backend/budgets/views.py` | Budgets page, budget CRUD, total budget handlers |
| `backend/budgets/templates/budgets/budgets.html` | Main budgets page |
| `backend/budgets/templates/budgets/_budget_card.html` | Category budget display card |
| `backend/budgets/templates/budgets/_total_budget_card.html` | Total budget UI |
| `backend/budgets/templates/budgets/_edit_budget_form.html` | Category budget edit bottom-sheet form |
| `backend/budgets/templates/budgets/_edit_total_budget_form.html` | Total budget edit bottom-sheet form |
| `backend/budgets/tests/` | Service and view coverage |

## Notes for Newcomers

- Budget progress is recalculated from transactions on each request.
- Category budgets are category+currency scoped, not month-row scoped.
- Total budgets are currency scoped, not month-row scoped.
- Total budgets count uncategorized expenses; category budgets do not.

## Logging

**Service events:**

- `budget.created` — new budget created (`currency`, `category_id`)
- `budget.updated` — budget updated (`id`)
- `total_budget.set` — total budget created or updated
- `total_budget.deleted` — total budget removed

**Page views:** `budgets`
