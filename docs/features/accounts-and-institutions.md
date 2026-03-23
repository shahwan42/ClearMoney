# Accounts & Institutions

Accounts and institutions form the foundational accounting system of ClearMoney. Institutions group accounts (like banks grouping your bank accounts), and accounts track balances with atomic updates.

## Concepts

### Institutions

Banks and fintechs serve as grouping containers for accounts. Each has a name, optional color, icon, and display order.

**Institution Types:**

- `bank` — Traditional banks (HSBC, CIB, NBE, Banque Misr)
- `fintech` — Digital-first institutions (Telda, ValU, Fawry)
- `wallet` — Virtual institution for physical cash/wallet accounts

### Account Types

| Type           | Behavior                                               |
| -------------- | ------------------------------------------------------ |
| `savings`      | Savings account (higher interest, fewer transactions)  |
| `current`      | Standard debit/current account                         |
| `prepaid`      | Prepaid card (e.g., Fawry)                             |
| `cash`         | Physical cash or wallet (always positive)              |
| `credit_card`  | Credit card — balance goes **negative** when you spend |
| `credit_limit` | Revolving credit line (e.g., TRU EPP)                  |

### Balance Convention

- **Debit accounts** (savings, current, prepaid, cash): Positive balance = money you have
- **Credit accounts** (credit_card, credit_limit): Negative balance = money you owe
  - Example: -120,000 means you've used 120K of your credit limit
  - Available credit = credit_limit + current_balance (since balance is negative)

## Models

**File:** `backend/core/models.py`

### Account

Key fields:

- `id` (UUID), `institution_id` (FK), `name`, `type` (account_type enum)
- `currency` (EGP or USD), `current_balance`, `initial_balance`
- `credit_limit` (NUMERIC, nullable — only for credit types)
- `is_dormant` (bool — hides from active lists but keeps in totals)
- `role_tags` (PostgreSQL text[] array)
- `display_order` (int — for UI ordering)
- `metadata` (JSONB — stores billing cycle info for credit cards)
- `health_config` (JSONB — stores min_balance/min_deposit rules)

Key methods:

- `is_credit_type()` — returns True for credit_card and credit_limit
- `available_credit` — calculates credit_limit + current_balance
- `get_health_config()` — parses JSONB health config

### Institution

Key fields: `id`, `name`, `type` (institution_type enum), `color` (nullable), `icon` (nullable), `display_order`

## Database Migrations

| Migration | Purpose |
|-----------|---------|
| 000001 | Creates `institutions` table + `institution_type` enum |
| 000002 | Creates `accounts` table + `account_type`/`currency_type` enums |
| 000017 | Adds `health_config JSONB` column |
| 000018 | Removes legacy 'checking' type, migrates to 'current' |

## Service Layer

**File:** `backend/accounts/services.py`

### AccountService

Validation rules:

- Account name required, non-empty after trim
- institution_id required
- Credit card/limit accounts must have credit_limit set
- Cash accounts cannot have credit_limit

Also handles cleanup of stale recurring rules when deleting an account.

Key operations: `create`, `update`, `delete`, `toggle_dormant`, `update_display_order`, `update_health_config`

**Balance updates use atomic SQL:** `UPDATE accounts SET current_balance = current_balance + %s WHERE id = %s` — never read-modify-write.

### InstitutionService

Validation: name required, type defaults to 'bank', validated against allowed enum values.

Operations: `create`, `update`, `delete`, `update_display_order`

### AccountHealthService

Checks all accounts against their health constraints:

- **min_balance rule:** Alert if current_balance < configured minimum
- **min_monthly_deposit rule:** Alert if no deposit >= configured amount arrived this month

Returns list of health warnings with human-readable messages. Health checks are advisory — failures don't block anything.

## Views

**File:** `backend/accounts/views.py`

| Route | Method | Handler | Purpose |
|-------|--------|---------|---------|
| `/accounts` | GET | `accounts()` | Main list page |
| `/accounts/form` | GET | `account_form()` | HTMX partial: account creation form |
| `/accounts/list` | GET | `institution_list()` | HTMX partial: institution list |
| `/accounts/{id}` | GET | `account_detail()` | Detail page with health, sparkline, utilization |
| `/accounts/{id}/statement` | GET | `credit_card_statement()` | CC statement view |
| `/accounts/{id}/dormant` | POST | `toggle_dormant()` | Toggle dormant status |
| `/accounts/{id}/health` | POST | `account_health_update()` | Save health constraints |
| `/accounts/{id}/edit-form` | GET | `account_edit_form()` | HTMX partial: edit form in bottom sheet |
| `/accounts/{id}/edit` | POST | `account_update()` | Update account fields |
| `/accounts/{id}/delete` | POST | `account_delete()` | Delete account (bottom sheet confirmation) |
| `/accounts/add` | POST | `account_add()` | Create account |
| `/accounts/reorder` | POST | `reorder_accounts()` | Drag-and-drop reorder |
| `/accounts/institution-form` | GET | `institution_form_partial()` | HTMX partial: institution form for create sheet |
| `/institutions/add` | POST | `institution_add()` | Create institution (from bottom sheet) |
| `/institutions/reorder` | POST | `reorder_institutions()` | Reorder institutions |
| `/institutions/{id}/edit-form` | GET | `institution_edit_form()` | HTMX partial: edit form for bottom sheet |
| `/institutions/{id}/edit` | POST | `institution_update()` | Update institution (from bottom sheet) |
| `/institutions/{id}/delete-confirm` | GET | `institution_delete_confirm()` | HTMX partial: delete confirmation |
| `/institutions/{id}/delete` | POST | `institution_delete()` | Delete institution (from bottom sheet) |

## Templates

### Pages

| Template | Purpose |
|----------|---------|
| `backend/accounts/templates/accounts/accounts.html` | Main accounts list page with institution cards |
| `backend/accounts/templates/accounts/account_detail.html` | Detail page: balance, sparkline, utilization, health, transactions |

### Partials

| Template | Purpose |
|----------|---------|
| `backend/accounts/templates/accounts/_institution_card.html` | Collapsible card with accounts (HTML5 `<details>/<summary>`) |
| `backend/accounts/templates/accounts/_account_form.html` | Account creation form (rendered in bottom sheet) |
| `backend/accounts/templates/accounts/_institution_form.html` | Institution creation form (loaded into create bottom sheet) |
| `backend/accounts/templates/accounts/_institution_edit_form.html` | Institution edit form (loaded into edit bottom sheet) |
| `backend/accounts/templates/accounts/_institution_delete_confirm.html` | Institution delete confirmation |
| `backend/accounts/templates/accounts/_account_edit_form.html` | Account edit form (loaded into edit bottom sheet) |

## Features Detail

### Account Editing

Edit an account via a bottom sheet on the detail page. The "Edit" button in the header opens a lazy-loaded form (fetched via HTMX) with the account's current values pre-filled. On submit, the page refreshes to show updated details.

### Dormant Toggle

Keeps account in totals but de-prioritizes in UI. Uses `is_dormant` boolean column, toggled via `NOT is_dormant` SQL update. Not the same as deleting — account can be restored.

### Reordering

Both accounts and institutions support drag-and-drop reordering via `display_order` column. The handler receives an array of IDs in the new order and updates each `display_order` to match the array index.

### Health Constraints

Stored as JSONB in `health_config` column for extensibility. Two supported rules:

- `min_balance` — alert if balance drops below threshold
- `min_monthly_deposit` — alert if no deposit >= amount arrives during month

Configured per-account on the detail page.

### Institution CRUD (Bottom Sheets)

All institution CRUD operations use the bottom sheet pattern:

- **Create:** A floating action button (FAB, teal "+" circle) in the bottom-right opens a create sheet. The form is loaded via `htmx.ajax('GET', '/accounts/institution-form')`. On success, the sheet closes after a brief toast and the institution list refreshes via OOB swap.
- **Edit:** Each institution card has an edit icon that opens an edit sheet. The form pre-fills name and type, and on success closes the sheet + OOB-updates the institution card.
- **Delete:** Each institution card has a trash icon that opens a delete confirmation sheet. The user must type the institution name to enable the delete button. On success, the institution is removed from the list.

All three sheets share the same UX: slide-up animation, dark overlay, drag-to-dismiss on the handle (100px threshold), and Cancel button.

### Account Creation (Bottom Sheet)

Create a new account via a slide-up bottom sheet on the accounts page. Click "+ Account" on any institution card to open the sheet with the form pre-filled for that institution.

- **Form fields:** name, type, currency, initial balance, credit limit (shown only for credit types)
- **On success:** sheet closes automatically, institution list refreshes via OOB swap
- **On error:** error message shown inside the sheet, form re-rendered for retry

### Account Deletion

Delete an account via a confirmation bottom sheet on the detail page. The user must type the account name to enable the delete button — prevents accidental deletion of accounts with transaction history.

- **Cascading deletes:** Transactions and snapshots are automatically removed (ON DELETE CASCADE)
- **Recurring rule cleanup:** The service layer deletes any recurring rules referencing the account before removal

### Linked Virtual Accounts

The account detail page shows any virtual accounts linked to the bank account via the `account_id` foreign key. Each VA card displays its icon, name, current balance, target (if set), and a progress bar. Clicking a VA navigates to its detail page. The section is hidden when no VAs are linked.

### Balance Sparklines

30-day inline SVG sparklines per account. Data comes from `SnapshotService.get_account_history()`. Rendered using the `chart-sparkline` partial with `sparkline_points` template filter.

### Utilization Donut

For credit accounts, shows used vs. available credit as an SVG circle with `stroke-dasharray`. Color-coded: green (<50%), amber (50-80%), red (>80%).

## Key Files

| File | Purpose |
|------|---------|
| `backend/core/models.py` | Account, Institution models; account types, health config, credit methods |
| `backend/accounts/services.py` | Account + institution validation, atomic balance updates, health checking |
| `backend/accounts/views.py` | HTML/HTMX views for accounts and institutions |
| `backend/accounts/templates/accounts/accounts.html` | Account list page |
| `backend/accounts/templates/accounts/account_detail.html` | Account detail page |

## For Newcomers

- **Balance updates are atomic** — always use `UPDATE accounts SET current_balance = current_balance + %s`, never read-modify-write.
- **JSONB for flexibility** — metadata and health_config use JSONB so new fields can be added without migrations.
- **Credit limit nullable** — `credit_limit` is NULL when not applicable (non-credit account types). Always check for None before using.
- **Display in templates** — use the `neg` template filter to flip CC balance signs for display (e.g., showing "120,000 used" instead of "-120,000").
- **Institution cards** use HTML5 `<details>/<summary>` for collapse/expand with no JavaScript.

## Logging

**Service events:**

- `account.created` — new account created (type, currency)
- `account.updated` — account modified (id)
- `account.deleted` — account removed (id)
- `account.dormant_toggled` — dormant status flipped (id)
- `institution.created` — new institution created
- `institution.updated` — institution modified (id)
- `institution.deleted` — institution removed (id)

**Page views:** `accounts`, `account-detail`
