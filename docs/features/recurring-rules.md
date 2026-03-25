# Recurring Rules

Automate repetitive transactions with configurable scheduling. Rules can auto-execute or require manual confirmation.

## Concept

A recurring rule defines a transaction template that executes on a schedule. Two modes:

- **Auto-confirm** — transaction created automatically when due (processed on app startup)
- **Manual-confirm** — shows as pending for user to confirm or skip

## Model

**File:** `backend/core/models.py`

### RecurringRule

The `RecurringRule` model stores: `template_transaction` (JSONB — parsed on demand), `frequency` (monthly/weekly), `day_of_month` (nullable), `next_due_date`, `is_active`, `auto_confirm`.

### TransactionTemplate

The JSONB `template_transaction` field contains: type, amount, currency, account_id, category_id (nullable), note (nullable).

**Key design:** `template_transaction` is stored as JSONB and only deserialized when the rule is executed. This avoids unnecessary parsing.

### Frequency

- `monthly` — advances next_due_date by 1 month
- `weekly` — advances next_due_date by 7 days

## Database

Rules are stored with the template transaction as JSONB. The `next_due_date` column allows efficient "what's due?" queries.

## Service

**File:** `backend/recurring/services.py`

### Key functions

| Function | Purpose |
|----------|---------|
| `create_rule(user_id, rule)` | Insert with JSONB template_transaction |
| `get_rule(user_id, id)` | Single rule |
| `get_all_rules(user_id)` | All rules ordered by next_due_date ASC |
| `get_due_rules(user_id)` | **Key query:** Active rules where `next_due_date <= CURRENT_DATE` |
| `update_next_due_date(user_id, id, date)` | Advance after execution |
| `delete_rule(user_id, id)` | Remove rule |
| `delete_by_account_id(user_id, account_id)` | Cleanup stale rules when account deleted (uses JSONB `->>'account_id'`) |

### delete_by_account_id

Uses PostgreSQL JSONB operator to find rules referencing a deleted account:

```sql
WHERE template_transaction->>'account_id' = $1
```

This prevents stale references since the account_id is inside JSON, not a real FK.

### process_due_rules

Called on **app startup** via the `process_recurring` management command:
1. Gets all due rules via `get_due_rules()`
2. Skips `auto_confirm=False` (manual only)
3. For each auto-confirm rule, calls `execute_rule()`
4. Returns count of transactions created
5. Errors don't stop startup — failed rules are skipped with a warning log

### execute_rule

Core logic:
1. Deserialize `template_transaction` JSONB into a template dict
2. Guard: check if account_id still exists (FK not enforced on JSONB)
3. Build transaction from template (sets date = next_due_date, recurring_rule_id = rule.id)
4. Delegates to transaction service for balance updates
5. Advances `next_due_date` via `advance_due_date()`

### confirm_rule / skip_rule

- **Confirm:** Gets rule, calls `execute_rule()` — creates transaction and advances due date
- **Skip:** Advances due date without creating a transaction

### advance_due_date

- `weekly`: adds 7 days to current due date
- `monthly`: adds 1 month to current due date

## Views

**File:** `backend/recurring/views.py`

| Route | Method | Handler | Purpose |
|-------|--------|---------|---------|
| `/recurring` | GET | `recurring_page()` | Page with pending + active rules |
| `/recurring/add` | POST | `recurring_add()` | Create rule |
| `/recurring/<id>/confirm` | POST | `recurring_confirm()` | Confirm pending rule |
| `/recurring/<id>/skip` | POST | `recurring_skip()` | Skip pending rule |
| `/recurring/<id>` | DELETE | `recurring_delete()` | Delete rule |

### recurring_add View

1. Parses form (type, amount, account, category, note, frequency, next_due_date, auto_confirm)
2. Builds template dict
3. Serializes to JSONB
4. Looks up account to get currency
5. Creates rule via service

## Templates

### Page

**File:** `backend/recurring/templates/recurring/recurring.html`

Sections:
1. **Pending confirmations** — amber cards with Confirm/Skip buttons
2. **Create new rule** form (recurring-form partial)
3. **Active rules** — table with note, frequency, next due, amount, auto label, delete button

### Partial

**File:** `backend/recurring/templates/recurring/partials/recurring-form.html`

Form with:
- Type toggle (Expense/Income)
- Amount input
- Account/Category dropdowns
- Note, Frequency (Monthly/Weekly), Next Due date
- Auto-confirm checkbox

## Startup Integration

**File:** `backend/jobs/management/commands/process_recurring.py`

Called by the `run_startup_jobs` management command on every app startup. Runs `process_due_rules()` and logs the count of auto-created transactions. Errors don't prevent startup.

## Key Files

| File | Purpose |
|------|---------|
| `backend/core/models.py` | RecurringRule model with JSONB template_transaction |
| `backend/recurring/services.py` | CRUD, get_due_rules, process_due_rules, execute_rule, confirm_rule, skip_rule |
| `backend/recurring/views.py` | Recurring views |
| `backend/recurring/templates/recurring/recurring.html` | Recurring page |
| `backend/recurring/templates/recurring/partials/recurring-form.html` | Create rule form |
| `backend/jobs/management/commands/process_recurring.py` | Startup processing |

## For Newcomers

- **JSONB for template** — the transaction template is stored as raw JSON, not separate columns. This keeps the schema simple but means FK constraints on account_id aren't enforced by the DB.
- **Startup processing** — rules are only processed on app restart, not via a cron job. If the app is down for days, all missed rules will execute on next startup.
- **Service-to-service dependency** — RecurringService delegates to TransactionService for creating transactions (balance updates, etc.).
- **Account deletion cleanup** — `delete_by_account_id()` uses JSONB operators to find and remove rules referencing deleted accounts.

## Logging

**Service events:**

- `recurring.created` — new recurring rule created (frequency)
- `recurring.confirmed` — pending rule confirmed and executed (id)
- `recurring.skipped` — pending rule skipped without executing (id)
- `recurring.deleted` — recurring rule removed (id)
- `recurring.auto_processed` — rule auto-executed on startup (id)

**Page views:** `recurring`
