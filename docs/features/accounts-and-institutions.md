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

- `id` (UUID), `institution_id` (FK), `name`, `type` (varchar)
- `currency` (EGP or USD), `current_balance`, `initial_balance`
- `credit_limit` (NUMERIC, nullable — only for credit types)
- `is_dormant` (bool — hides from active lists but keeps in totals)
- `display_order` (int — for UI ordering)
- `metadata` (JSONB — stores billing cycle info for credit cards)
- `health_config` (JSONB — stores min_balance/min_deposit rules)

Key methods:

- `is_credit_type()` — returns True for credit_card and credit_limit
- `available_credit` — calculates credit_limit + current_balance
- `get_health_config()` — parses JSONB health config

### Institution

Key fields: `id`, `name`, `type` (varchar), `color` (nullable), `icon` (nullable), `display_order`

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

#### Key Methods

- `get_all()` — all accounts ordered by display_order, name
- `get_by_id(account_id)` — single account or None
- `get_by_institution(institution_id)` — accounts for a specific institution
- `get_for_dropdown(include_balance=False)` — lightweight non-dormant accounts for form dropdowns
- `create(data)` — new account with validation
- `update(account_id, data)` — modifies account fields
- `delete(account_id)` — removes account with CASCADE
- `toggle_dormant(account_id)` — hides/shows account
- `reorder(ids)` — drag-and-drop reordering
- `update_health_config(account_id, config)` — saves health constraints
- `get_balance_history(account_id, days=30)` — 30-day sparkline data
- `get_utilization_history(account_id, credit_limit, days=30)` — CC utilization trend
- `get_recent_transactions(account_id, limit=50)` — transactions with running balance
- `get_linked_virtual_accounts(account_id)` — VAs linked to account
- `get_excluded_va_balance(account_id)` — excluded VA balance for net worth

### InstitutionService

Validation: name required, type defaults to 'bank'.

Key operations: `create`, `update`, `delete`, `update_display_order`, `get_or_create`

#### Key Methods

- `get_all()` — all institutions ordered by display_order
- `get_by_id(inst_id)` — single institution or None
- `create(name, inst_type, icon=None, color=None)` — new institution
- `update(inst_id, name, inst_type)` — modify institution
- `delete(inst_id)` — remove institution (CASCADE)
- `reorder(ids)` — reorder institutions
- `get_or_create(name, inst_type, icon=None, color=None)` — deduplicates by name+type; used by unified account creation

### AccountHealthService

Checks accounts against health constraints:

- **min_balance rule:** Alert if balance drops below threshold
- **min_monthly_deposit rule:** Alert if no deposit >= amount arrived this month

Returns list of health warnings. Health checks are advisory — failures don't block anything.

## Views

**File:** `backend/accounts/views.py`

### HTML Pages & Partials

| Route | Method | Handler | Purpose |
|-------|--------|---------|---------|
| `/accounts` | GET | `accounts_list()` | Main list page |
| `/accounts/add-form` | GET | `account_add_form()` | Unified account creation form with institution picker |
| `/accounts/form` | GET | `account_form()` | HTMX partial: account form for specific institution |
| `/accounts/institution-presets` | GET | `institution_presets()` | JSON API: preset institutions (banks, fintechs, wallets) |
| `/accounts/list` | GET | `institution_list_partial()` | HTMX partial: institution list |
| `/accounts/{id}` | GET | `account_detail()` | Detail page with health, sparkline, utilization, linked VAs |
| `/accounts/{id}/statement` | GET | `credit_card_statement()` | CC statement view |
| `/accounts/{id}/dormant` | POST | `toggle_dormant()` | Toggle dormant status |
| `/accounts/{id}/health` | POST | `health_update()` | Save health constraints |
| `/accounts/{id}/edit-form` | GET | `account_edit_form()` | HTMX partial: edit form |
| `/accounts/{id}/edit` | POST | `account_update()` | Update account |
| `/accounts/{id}/delete` | POST | `account_delete()` | Delete account |
| `/accounts/add` | POST | `account_add()` | Create account |
| `/accounts/reorder` | POST | `accounts_reorder()` | Reorder accounts |
| `/accounts/institution-form` | GET | `institution_form_partial()` | HTMX partial: institution form |
| `/institutions/add` | POST | `institution_add()` | Create institution |
| `/institutions/reorder` | POST | `institutions_reorder()` | Reorder institutions |
| `/institutions/{id}/edit-form` | GET | `institution_edit_form()` | HTMX partial: edit form |
| `/institutions/{id}/update` | PUT/POST | `institution_update()` | Update institution |
| `/institutions/{id}/delete-confirm` | GET | `institution_delete_confirm()` | HTMX partial: delete confirmation |
| `/institutions/{id}/delete` | DELETE/POST | `institution_delete()` | Delete institution |

### JSON API Routes

| Route | Method | Purpose |
|-------|--------|---------|
| `/api/institutions` | GET, POST | List/create institutions (JSON) |
| `/api/institutions/{id}` | GET, PUT, DELETE | Institution CRUD (JSON) |
| `/api/accounts` | GET, POST | List/create accounts (JSON) |
| `/api/accounts/{id}` | GET, PUT, DELETE | Account CRUD (JSON) |

**Note:** Computed fields `is_credit_type` and `available_credit` are stripped from JSON API responses.

## Templates

### Pages

| Template | Purpose |
|----------|---------|
| `backend/accounts/templates/accounts/accounts.html` | Main accounts list page |
| `backend/accounts/templates/accounts/account_detail.html` | Account detail page |

### Partials

| Template | Purpose |
|----------|---------|
| `backend/accounts/templates/accounts/_institution_card.html` | Collapsible institution card |
| `backend/accounts/templates/accounts/_account_form.html` | Account creation form |
| `backend/accounts/templates/accounts/_add_account_form.html` | Unified account form with institution picker |
| `backend/accounts/templates/accounts/_institution_form.html` | Institution creation form |
| `backend/accounts/templates/accounts/_institution_edit_form.html` | Institution edit form |
| `backend/accounts/templates/accounts/_institution_delete_confirm.html` | Delete confirmation |
| `backend/accounts/templates/accounts/_account_edit_form.html` | Account edit form |
| `backend/accounts/templates/accounts/_institution_list.html` | Institution list |

## Features Detail

### Account Editing

Edit an account via a bottom sheet on the detail page. The form pre-fills with current values. On submit, the page refreshes to show updated details.

### Dormant Toggle

Keeps account in totals but de-prioritizes in UI. Not the same as deleting — account can be restored.

### Reordering

Drag-and-drop reordering via `display_order` column.

### Health Constraints

Stored as JSONB. Two supported rules:

- `min_balance` — alert if below threshold
- `min_monthly_deposit` — alert if no deposit >= amount

Configured per-account on the detail page.

### Institution & Account Deletion

Both use confirmation bottom sheets. For accounts, user must type the account name to confirm. Cascading deletes remove transactions and snapshots. Recurring rules are cleaned up.

### Linked Virtual Accounts

Account detail page shows VAs linked to the account. Each card displays icon, name, balance, target, and progress bar.

### Balance Sparklines

30-day inline SVG sparklines per account. Data from `get_balance_history()`.

### Utilization Donut

For credit accounts, shows used vs. available credit. Color-coded: green (<50%), amber (50-80%), red (>80%).

### Credit Card Statement Page

Shows statement for selected billing period. Uses `get_statement_data()` to parse billing cycle, fetch transactions, calculate balances, and show interest-free days remaining.

## Key Files

| File | Purpose |
|------|---------|
| `backend/core/models.py` | Account, Institution models |
| `backend/accounts/services.py` | AccountService, InstitutionService, get_statement_data() |
| `backend/accounts/views.py` | HTML/HTMX/JSON API views |
| `backend/accounts/urls.py` | URL routing |
| `backend/accounts/templates/accounts/accounts.html` | Account list page |
| `backend/accounts/templates/accounts/account_detail.html` | Detail page |
| `backend/accounts/institution_data.py` | Preset institutions |

## For Newcomers

- **Balance updates are atomic** — always use `UPDATE accounts SET current_balance = current_balance + %s`.
- **JSONB for flexibility** — metadata and health_config use JSONB for extensibility.
- **Credit limit nullable** — NULL for non-credit accounts.
- **Display** — use the `neg` template filter to flip CC balance signs for display.
- **Institution cards** use HTML5 `<details>/<summary>` for collapse/expand.
- **Unified institution flow** — `get_or_create()` deduplicates institutions automatically.

## Logging

**Service events:**

- `account.created`, `account.updated`, `account.deleted`
- `account.dormant_toggled`, `account.health_config_updated`, `account.reordered`
- `institution.created`, `institution.updated`, `institution.deleted`, `institution.reordered`

**Page views:** `accounts`, `account-detail`, `cc-statement`
