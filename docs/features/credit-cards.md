# Credit Cards

ClearMoney has specialized support for credit card accounts including statement views, billing cycle tracking, utilization charts, interest-free period monitoring, and payment guidance.

## How Credit Cards Differ

Credit cards use the same `Account` model but with key differences:

- **Type:** `credit_card` or `credit_limit`
- **Balance is negative** — represents debt (e.g., -120,000 = 120K used)
- **credit_limit field** — required for credit types, nullable for others
- **metadata JSONB** — stores billing cycle info (statement_day, due_day)
- **Available credit** = `credit_limit + current_balance` (since balance is negative)

The `is_credit_type()` check identifies credit accounts. The `neg` template filter flips the sign for display.

## Billing Cycle

### Data Storage

Billing cycle info is stored in the `metadata` JSONB column:

```json
{
  "statement_day": 15,
  "due_day": 5
}
```

### Types

**File:** `backend/core/billing.py`

- `BillingCycleInfo` — computed for current period:
  - `period_start`, `period_end` — current billing period dates
  - `due_date` — when payment is due
  - `days_until_due` — countdown (negative if overdue)
  - `is_due_soon` — true if due within 7 days

### Functions

- `parse_billing_cycle(account)` — parses metadata JSONB
- `get_billing_cycle_info(meta, now)` — computes current period dates based on today

## Statement View

**Route:** `GET /accounts/{id}/statement`

**View:** `credit_card_statement()` in `backend/accounts/views.py`

### StatementData

- `account` — the credit card
- `billing_cycle` — computed period info
- `transactions` — all transactions in the billing period
- `opening_balance` — balance at period start (computed by reversing deltas)
- `closing_balance` — current balance
- `total_spending` — sum of expenses
- `total_payments` — sum of credits/payments
- `interest_free_days`, `interest_free_remain`, `interest_free_urgent`
- `payment_history` — recent payments to card

### Statement Fetching

`get_statement_data()`:
1. Parses billing cycle from account metadata
2. Computes period dates (supports past periods via `?period=YYYY-MM` query param)
3. Loads transactions in the billing period
4. Computes opening balance by reversing deltas
5. Calculates interest-free period (55 days from statement close)
6. Loads recent payment history

## Interest-Free Period

Standard interest-free period is 55 days from statement close date.

```python
interest_free_end = period_end + timedelta(days=55)
remain = (interest_free_end - today).days
urgent = 0 < remain <= 7
```

Displayed in the statement view with an urgency indicator when ≤ 7 days remain.

## Utilization

### Calculation

**File:** `backend/accounts/services.py` — `get_credit_card_utilization()`

```python
used = -account.current_balance  # balance is negative, negate to get positive
return used / account.credit_limit * 100
```

### Donut Chart

Displayed on the account detail page as an SVG circle using `stroke-dasharray`:

```html
<circle stroke-dasharray="{{ utilization_pct }}, 100" />
```

Color thresholds:
- Green: < 50%
- Amber: 50-80%
- Red: > 80%

### Utilization Trends

Historical utilization computed from 30-day balance snapshots:

```python
utilization_history = [
    -bal / account.credit_limit * 100
    for bal in balance_history
]
```

Rendered as an SVG sparkline below the donut chart.

## Payment Guidance

Shown in the statement view when balance < 0:

- Shows full statement balance with `neg` filter (displays positive amount)
- Due date from billing cycle info
- Days until due countdown
- Currently guidance is for full balance payment (no minimum payment logic)

## Dashboard Integration

The dashboard shows credit cards with:
- Mini utilization rings (SVG with `stroke-dasharray`)
- Card name as clickable link
- Due date countdown (if billing cycle configured)
- Current balance (red if negative)
- Link to statement

## Templates

| Template | Purpose |
|----------|---------|
| `accounts/templates/accounts/account-detail.html` | Detail page with utilization donut, sparkline, billing info |
| `accounts/templates/accounts/credit-card-statement.html` | Statement view with period, interest-free tracker, payments |
| `accounts/templates/accounts/partials/credit-card-info.html` | Billing cycle info box |

## Key Files

| File | Purpose |
|------|---------|
| `backend/core/models.py` | Account model with credit_limit, metadata fields |
| `backend/core/billing.py` | BillingCycle parsing, period computation |
| `backend/accounts/services.py` | StatementData, utilization calculation |
| `backend/accounts/views.py` | AccountDetail, CreditCardStatement views |

## For Newcomers

- **Balance sign convention** is the most common source of confusion. CC balances are always negative (debt). Use `neg` in templates to display as positive amounts.
- **Billing cycle metadata** is stored as JSONB, not as separate columns. This keeps the schema simple.
- **Interest-free period** is hardcoded at 55 days. Different banks may have different periods — this could be made configurable.
- **Utilization color thresholds** (50%/80%) are consistent across the donut chart, dashboard rings, and trend sparklines.
- **Statement periods** can be viewed historically via the `?period=YYYY-MM` query parameter.

## Logging

**Page views:** `cc-statement`
