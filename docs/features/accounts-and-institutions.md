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

| Type | Behavior |
|------|----------|
| `savings` | Savings account (higher interest, fewer transactions) |
| `current` | Standard debit/current account |
| `prepaid` | Prepaid card (e.g., Fawry) |
| `cash` | Physical cash or wallet (always positive) |
| `credit_card` | Credit card — balance goes **negative** when you spend |
| `credit_limit` | Revolving credit line (e.g., TRU EPP) |

### Balance Convention

- **Debit accounts** (savings, current, prepaid, cash): Positive balance = money you have
- **Credit accounts** (credit_card, credit_limit): Negative balance = money you owe
  - Example: -120,000 means you've used 120K of your credit limit
  - Available credit = credit_limit + current_balance (since balance is negative)

## Models

### Account

**File:** `internal/models/account.go`

Key fields:
- `ID` (UUID), `InstitutionID` (FK), `Name`, `Type` (AccountType enum)
- `Currency` (EGP or USD), `CurrentBalance`, `InitialBalance`
- `CreditLimit` (*float64, nullable — only for credit types)
- `IsDormant` (bool — hides from active lists but keeps in totals)
- `RoleTags` ([]string — PostgreSQL text[] array)
- `DisplayOrder` (int — for UI ordering)
- `Metadata` (json.RawMessage — stores billing cycle info for credit cards)
- `HealthConfig` (json.RawMessage — stores min_balance/min_deposit rules)

Key methods:
- `IsCreditType() bool` — returns true for credit_card and credit_limit
- `AvailableCredit() float64` — calculates credit_limit + balance
- `GetHealthConfig() *AccountHealthConfig` — parses JSONB health config

### Institution

**File:** `internal/models/institution.go`

Key fields: `ID`, `Name`, `Type` (InstitutionType enum), `Color` (*string), `Icon` (*string), `DisplayOrder`

## Database Migrations

| Migration | File | Purpose |
|-----------|------|---------|
| 000001 | `create_institutions.up.sql` | Creates `institutions` table + `institution_type` enum |
| 000002 | `create_accounts.up.sql` | Creates `accounts` table + `account_type`/`currency_type` enums |
| 000017 | `add_account_health.up.sql` | Adds `health_config JSONB` column |
| 000018 | `remove_checking_account_type.up.sql` | Removes legacy 'checking' type, migrates to 'current' |

All migrations are in `internal/database/migrations/`.

## Repository Layer

### AccountRepo

**File:** `internal/repository/account.go`

| Method | Purpose |
|--------|---------|
| `Create(ctx, acc)` | Insert account, sets current_balance = initial_balance |
| `GetByID(ctx, id)` | Retrieve single account |
| `GetAll(ctx)` | All accounts, ordered by display_order, name |
| `GetByInstitution(ctx, instID)` | Accounts for a specific institution |
| `Update(ctx, acc)` | Update fields (NOT balance) |
| `UpdateBalance(ctx, id, delta)` | **Atomic** balance update: `current_balance = current_balance + $delta` |
| `UpdateHealthConfig(ctx, id, config)` | Set health_config JSONB |
| `Delete(ctx, id)` | Remove account |
| `ToggleDormant(ctx, id)` | Flip `is_dormant = NOT is_dormant` |
| `UpdateDisplayOrder(ctx, id, order)` | Set display_order for drag-and-drop |

**Important:** `UpdateBalance` uses SQL arithmetic (`current_balance + $delta`), not read-modify-write. This avoids race conditions — PostgreSQL serializes the updates atomically.

### InstitutionRepo

**File:** `internal/repository/institution.go`

Standard CRUD: `Create`, `GetByID`, `GetAll`, `Update`, `Delete`, `UpdateDisplayOrder`

## Service Layer

### AccountService

**File:** `internal/service/account.go` (line ~257)

Validation rules:
- Account name required, non-empty after trim
- InstitutionID required
- Credit card/limit accounts must have credit_limit set
- Cash accounts cannot have credit_limit

Also handles cleanup of stale recurring rules when deleting an account.

### InstitutionService

**File:** `internal/service/institution.go`

Validation: name required, type defaults to 'bank', validated against allowed enum values.

### AccountHealthService

**File:** `internal/service/account_health.go`

Checks all accounts against their health constraints:
- **MinBalance rule:** Alert if current_balance < configured minimum
- **MinMonthlyDeposit rule:** Alert if no deposit ≥ configured amount arrived this month

Returns `[]AccountHealthWarning` with human-readable messages. Health checks are advisory — failures don't block anything.

## Handler Layer

### JSON API

**File:** `internal/handler/account.go` — REST API at `/api/accounts`
**File:** `internal/handler/institution.go` — REST API at `/api/institutions`

### HTML/HTMX Routes

**File:** `internal/handler/pages.go`

| Route | Method | Handler | Purpose |
|-------|--------|---------|---------|
| `/accounts` | GET | `Accounts()` | Main list page |
| `/accounts/form` | GET | `AccountForm()` | HTMX partial: account creation form |
| `/accounts/list` | GET | `InstitutionList()` | HTMX partial: institution list |
| `/accounts/{id}` | GET | `AccountDetail()` | Detail page with health, sparkline, utilization |
| `/accounts/{id}/statement` | GET | `CreditCardStatement()` | CC statement view |
| `/accounts/{id}/dormant` | POST | `ToggleDormant()` | Toggle dormant status |
| `/accounts/{id}/health` | POST | `AccountHealthUpdate()` | Save health constraints |
| `/accounts/{id}/edit-form` | GET | `AccountEditForm()` | HTMX partial: edit form in bottom sheet |
| `/accounts/{id}/edit` | POST | `AccountUpdate()` | Update account fields |
| `/accounts/{id}` | DELETE | `AccountDelete()` | Delete account (bottom sheet confirmation) |
| `/accounts/add` | POST | `AccountAdd()` | Create account |
| `/accounts/reorder` | POST | `ReorderAccounts()` | Drag-and-drop reorder |
| `/accounts/institution-form` | GET | `InstitutionFormPartial()` | HTMX partial: institution form for create sheet |
| `/institutions/add` | POST | `InstitutionAdd()` | Create institution (from bottom sheet) |
| `/institutions/reorder` | POST | `ReorderInstitutions()` | Reorder institutions |
| `/institutions/{id}/edit-form` | GET | `InstitutionEditForm()` | HTMX partial: edit form for bottom sheet |
| `/institutions/{id}` | PUT | `InstitutionUpdate()` | Update institution (from bottom sheet) |
| `/institutions/{id}/delete-confirm` | GET | `InstitutionDeleteConfirm()` | HTMX partial: delete confirmation for bottom sheet |
| `/institutions/{id}` | DELETE | `InstitutionDelete()` | Delete institution (from bottom sheet) |

## Templates

### Pages

| Template | Purpose |
|----------|---------|
| `pages/accounts.html` | Main accounts list page with institution cards |
| `pages/account-detail.html` | Detail page: balance, sparkline, utilization, health, transactions |

### Partials

| Template | Purpose |
|----------|---------|
| `partials/institution-card.html` | Collapsible card with accounts (HTML5 `<details>/<summary>`) |
| `partials/account-form.html` | Account creation form (rendered in bottom sheet) |
| `partials/institution-form.html` | Institution creation form (loaded into create bottom sheet) |
| `partials/institution-edit-form.html` | Institution edit form (loaded into edit bottom sheet) |
| `partials/institution-delete-confirm.html` | Institution delete confirmation (loaded into delete bottom sheet) |

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
- `min_monthly_deposit` — alert if no deposit ≥ amount arrives during month

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
- **Bottom sheet UX:** Slide-up animation, swipe-to-dismiss drag handle, overlay tap-to-close, dark mode support

### Account Deletion

Delete an account via a confirmation bottom sheet on the detail page. The user must type the account name to enable the delete button — prevents accidental deletion of accounts with transaction history.

- **Cascading deletes:** Transactions and snapshots are automatically removed (ON DELETE CASCADE)
- **Blocked by installment plans:** If the account has active installment plans, a friendly error is shown in the sheet (FK RESTRICT constraint)
- **Recurring rule cleanup:** The service layer deletes any recurring rules referencing the account before removal
- **Bottom sheet UX:** Slide-up animation, swipe-to-dismiss drag handle, dark mode support

### Linked Virtual Accounts

The account detail page shows any virtual accounts linked to the bank account via the `account_id` foreign key. Each VA card displays its icon, name, current balance, target (if set), and a progress bar. Clicking a VA navigates to its detail page. The section is hidden when no VAs are linked.

### Balance Sparklines

30-day inline SVG sparklines per account. Data comes from `SnapshotService.GetAccountHistory()`. Rendered using the `chart-sparkline` partial with `sparklinePoints` template function.

### Utilization Donut

For credit accounts, shows used vs. available credit as an SVG circle with `stroke-dasharray`. Color-coded: green (<50%), amber (50-80%), red (>80%).

## Key Files

| File | Purpose |
|------|---------|
| `internal/models/account.go` | Account struct, types, health config, credit methods |
| `internal/models/institution.go` | Institution struct, types |
| `internal/repository/account.go` | Account SQL queries, atomic balance update |
| `internal/repository/institution.go` | Institution SQL queries |
| `internal/service/account.go` | Account validation + credit card billing cycle logic |
| `internal/service/institution.go` | Institution validation |
| `internal/service/account_health.go` | Health constraint checking |
| `internal/handler/account.go` | JSON API handlers |
| `internal/handler/institution.go` | JSON API handlers |
| `internal/handler/pages.go` | HTML/HTMX handlers |
| `internal/templates/pages/accounts.html` | Account list page |
| `internal/templates/pages/account-detail.html` | Account detail page |
| `internal/database/migrations/000002_create_accounts.up.sql` | Schema |

## For Newcomers

- **Balance updates are atomic** — always use `UpdateBalance(id, delta)` in the repo, never read-modify-write in Go code.
- **JSONB for flexibility** — metadata and health_config use JSONB so new fields can be added without migrations.
- **Nullable pointers** — `*float64` for credit_limit means "not applicable" when nil. Always nil-check before dereferencing.
- **Display in templates** — use the `neg` template function to flip CC balance signs for display (e.g., showing "120,000 used" instead of "-120,000").
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
