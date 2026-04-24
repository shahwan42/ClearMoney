# Recurring Rules

Automate repetitive money movements with configurable scheduling. Rules can auto-execute or require manual confirmation, and they support expenses, income, and transfers.

## Concept

A recurring rule stores a transaction template and a next due date. When the rule becomes due, it either:

- **Auto-confirm** — creates the transaction automatically during recurring processing
- **Manual-confirm** — appears in the pending section for the user to confirm or skip

Supported rule types:

- **Expense** — account + category + optional note
- **Income** — account + category + optional note
- **Transfer** — source account + destination account + optional fee + optional note

## Model

**File:** `backend/recurring/models.py`

### RecurringRule

The `RecurringRule` model stores:

- `template_transaction` — JSONB transaction template
- `frequency` — `weekly`, `biweekly`, `monthly`, `quarterly`, or `yearly`
- `day_of_month` — nullable legacy field
- `next_due_date`
- `is_active`
- `auto_confirm`

### Transaction Template

The JSONB `template_transaction` field can contain:

- `type`
- `amount`
- `currency`
- `account_id`
- `category_id` for expense/income rules
- `counter_account_id` for transfer rules
- `fee_amount` for transfer rules when fee > 0
- `note`

This template is stored as JSON and parsed only when the rule is rendered or executed.

## Service

**File:** `backend/recurring/services.py`

### Key responsibilities

- Create and delete rules scoped to the current user
- Build the template transaction from form input
- Find due rules and split pending vs auto-confirm flows
- Execute rules by delegating to `TransactionService`
- Advance `next_due_date` based on frequency
- Prepare transfer-aware view data for the UI

### build_template_transaction

Builds the JSON template from raw form data:

- Resolves account currency server-side
- Validates `account_id`
- For transfers, requires `counter_account_id`
- Rejects same-account transfers
- Persists `fee_amount` only when it is positive

### _execute_rule

When a rule is confirmed or auto-processed:

1. Reads the stored template
2. Validates referenced account ids
3. Uses `TransactionService.create_transfer(...)` for transfer rules
4. Uses `TransactionService.create(...)` for expense/income rules
5. Advances `next_due_date`

Transfer execution passes through the stored `fee_amount`, so the source account is debited by `amount + fee` while the destination receives `amount`.

### Frequencies

- `weekly` — +7 days
- `biweekly` — +14 days
- `monthly` — +1 month
- `quarterly` — +3 months
- `yearly` — +1 year

Monthly-style advancement uses `relativedelta`, so end-of-month dates clamp naturally.

## Views

**File:** `backend/recurring/views.py`

| Route | Method | Purpose |
|-------|--------|---------|
| `/recurring` | `GET` | Render recurring page with pending rules, form, and active rules |
| `/recurring/add` | `POST` | Create a new recurring rule |
| `/recurring/<id>/confirm` | `POST` | Confirm and execute a pending rule |
| `/recurring/<id>/skip` | `POST` | Skip a pending rule and advance due date |
| `/recurring/<id>` | `DELETE` | Delete a rule |

### Create flow

`recurring_add()` parses:

- `type`
- `amount`
- `account_id`
- `category_id`
- `counter_account_id`
- `fee_amount`
- `note`
- `frequency`
- `next_due_date`
- `auto_confirm`

It then calls `build_template_transaction()` and persists the rule.

## UI

**Files:** `backend/recurring/templates/recurring/recurring.html`, `backend/recurring/templates/recurring/_form.html`, `backend/recurring/templates/recurring/_rule_list.html`

### Form behavior

- Type toggle includes **Expense**, **Income**, and **Transfer**
- Transfer selection relabels the source account field to **From Account**
- Transfer selection shows:
  - destination account picker
  - optional fee input
- Transfer selection hides category selection
- Expense/income rules show category selection and hide transfer-only fields

### Rule list behavior

Transfer rules display:

- source account name
- destination account name
- fee display when present
- frequency
- next due date

## Startup / Processing

**File:** `backend/jobs/management/commands/process_recurring.py`

Due rules are processed through the recurring service. Auto-confirm rules create transactions immediately; manual rules remain pending for confirmation or skip.

## Testing Coverage

Current tests cover:

- transfer recurring rule creation in views
- transfer recurring rule creation in the browser UI
- fee persistence in the stored template
- fee-aware transfer execution and balance updates
- transfer rule rendering with source, destination, and fee display

Relevant files:

- `backend/recurring/tests/test_views.py`
- `backend/recurring/tests/test_services.py`
- `e2e/tests/test_recurring.py`

## Key Files

| File | Purpose |
|------|---------|
| `backend/recurring/models.py` | Recurring rule model |
| `backend/recurring/services.py` | Core recurring-rule business logic |
| `backend/recurring/views.py` | HTTP handlers for recurring rules |
| `backend/recurring/templates/recurring/_form.html` | Create-rule form |
| `backend/recurring/templates/recurring/_rule_list.html` | Active rule list rendering |
| `backend/jobs/management/commands/process_recurring.py` | Startup processing entry point |

## Notes

- The rule template is stored as JSONB, so account references are not protected by database FKs inside the template payload.
- Transfer rules use `counter_account_id` instead of `category_id`.
- `fee_amount` is optional and applies only to transfer rules.
- Income rules may trigger virtual-account auto-allocation after execution.
