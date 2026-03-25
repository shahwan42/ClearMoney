# Virtual Accounts

Envelope-style budgeting system. Users partition money across named goals/purposes (Emergency Fund, Vacation, etc.) and allocate transactions to track progress.

## Concept

Virtual accounts don't move real money between accounts — they logically tag funds as belonging to a virtual account. Each virtual account has:

- **Name** and optional **icon** + **color**
- **Target amount** (optional — nil means no goal)
- **Current balance** (denormalized cache of SUM allocations)
- **Linked bank account** (optional — links the VA to a specific real account)
- **Exclude from net worth** flag — when true, the VA's balance is subtracted from net worth (money held for others)
- **Archive** capability (soft-delete for completed virtual accounts)

### Two types of allocations

1. **Direct allocations** — created from the VA detail page. These earmark existing funds without creating a transaction. The bank account balance is not affected.
2. **Transaction-linked allocations** — created when selecting a VA during transaction creation. Both the transaction and the allocation are created together.

## Model

**File:** `backend/core/models.py`

### VirtualAccount

Columns: `name`, `target_amount` (nullable — null means no goal), `current_balance` (denormalized cache of SUM of allocations), `icon`, `color`, `is_archived`, `exclude_from_net_worth`, `display_order`, `account_id` (nullable FK to bank account for legacy VAs).

`progress_pct` property returns percentage (0 if no target, can exceed 100).

### VirtualAccountAllocation

Junction/pivot table linking allocations to virtual accounts. Columns: `transaction_id` (nullable — NULL for direct allocations), `virtual_account_id` (FK), `amount` (positive = contribution, negative = withdrawal), `note` (optional), `allocated_at` (date for direct allocations, NULL for tx-linked).

Direct allocations have `transaction_id = NULL`.

## Database

**Migrations:**

- `000015_create_virtual_funds.up.sql` — original creation
- `000022_rename_virtual_funds_to_virtual_accounts.up.sql` — rename
- `000025_fix_virtual_account_allocations.up.sql` — add account_id, allow direct allocations
- `000026_add_virtual_account_exclude_net_worth.up.sql` — add exclude_from_net_worth flag

Two tables:

1. `virtual_accounts` — virtual account definitions with cached `current_balance` and optional `account_id`
2. `virtual_account_allocations` — join table with partial unique index on `(transaction_id, virtual_account_id) WHERE transaction_id IS NOT NULL`

## Service

**File:** `backend/virtual_accounts/services.py`

### Virtual Account Operations

| Method | Purpose |
|--------|---------|
| `get_all(user_id)` | Non-archived virtual accounts, ordered by display_order |
| `get_all_including_archived(user_id)` | All virtual accounts (for settings) |
| `get_by_id(user_id, va_id)` | Single virtual account |
| `get_by_account_id(user_id, account_id)` | VAs linked to a specific bank account |
| `get_total_excluded_balance(user_id)` | Sum of `current_balance` for all excluded, non-archived VAs |
| `get_excluded_balance_by_account_id(user_id, account_id)` | Sum of excluded VA balances for a specific bank account |
| `create(user_id, data)` | Insert with account_id and exclude_from_net_worth |
| `update(user_id, va_id, data)` | Update name, target, icon, color, order, account_id, exclude_from_net_worth |
| `archive(user_id, va_id)` | Set `is_archived = true` |
| `unarchive(user_id, va_id)` | Set `is_archived = false` |
| `delete(user_id, va_id)` | Hard delete (only if no allocations) |

### Allocation Operations

| Method | Purpose |
|--------|---------|
| `allocate(user_id, tx_id, va_id, amount)` | **UPSERT** — INSERT or UPDATE on conflict (tx-linked allocations) |
| `direct_allocate(user_id, va_id, amount, note, allocated_at)` | INSERT direct allocation (no transaction_id) |
| `deallocate(user_id, tx_id, va_id)` | Remove allocation |
| `recalculate_balance(user_id, va_id)` | Update `current_balance = SUM(amount)` from allocations |
| `get_allocations_for_account(user_id, va_id)` | All allocations (direct + tx-linked) via LEFT JOIN |
| `get_transactions_for_account(user_id, va_id)` | Full Transaction records allocated to virtual account |
| `count_allocations_for_account(user_id, va_id)` | COUNT for pre-delete check |

## Views

**File:** `backend/virtual_accounts/views.py`

| Route | Method | Handler | Purpose |
|-------|--------|---------|---------|
| `/virtual-accounts` | GET | `virtual_accounts_page()` | List page with create form |
| `/virtual-accounts/add` | POST | `virtual_account_add()` | Create virtual account (with account_id) |
| `/virtual-accounts/<id>` | GET | `virtual_account_detail()` | Detail page with allocation history |
| `/virtual-accounts/<id>/archive` | POST | `virtual_account_archive()` | Archive virtual account |
| `/virtual-accounts/<id>/allocate` | POST | `virtual_account_allocate()` | Direct allocation (no transaction created) |
| `/virtual-accounts/<id>/toggle-exclude` | POST | `virtual_account_toggle_exclude()` | Toggle exclude_from_net_worth flag |
| `/virtual-accounts/<id>/edit-form` | GET | `virtual_account_edit_form()` | Load edit form partial into bottom sheet |
| `/virtual-accounts/<id>/edit` | POST | `virtual_account_update()` | Update virtual account from edit form |

### Account linkage validation

When creating a transaction and selecting a VA, the handler validates that the VA's `account_id` matches the transaction's `account_id`. VAs with NULL `account_id` (legacy) are allowed for any account.

### Cross-link from account detail

The bank account detail page (`/accounts/<id>`) shows a "Virtual Accounts" section listing all VAs linked to that account. Each card links to the VA detail page. This provides bidirectional navigation between accounts and their VAs.

### Over-allocation warnings

The detail page and list page show amber warnings when:

1. **Single VA exceeds account** — a VA's `current_balance` is greater than the linked bank account's `current_balance`. Shown as an amber banner on the VA detail page.
2. **Group total exceeds account** — the sum of all VA balances linked to the same bank account exceeds that account's balance. Shown as an amber banner on both the detail page and list page, plus per-card "Exceeds account balance" text on individual VA cards.

Computed in the handlers (`virtual_account_detail()`, `virtual_accounts_page()`) by fetching the linked account and sibling VAs. No new database queries — reuses `get_by_id()` and `get_by_account_id()`.

### Exclude from net worth

Virtual accounts can be marked "Not my money" — meaning the balance is held for others (e.g., building fund contributions). When `exclude_from_net_worth` is true:

- **Dashboard**: Net worth, EGPTotal, and CashTotal are reduced by the excluded VA's balance
- **Snapshots**: Historical net worth snapshots also subtract excluded balances
- **Account detail**: Shows "Holding for others" and "Your money" (can go negative if the user has spent others' money)
- **VA list/detail**: Shows a "held" badge and a toggle button

The net balance can go negative: if the bank account has 0 but an excluded VA still has 70K, the user's net balance is -70K — clearly showing they owe 70K back.

## Templates

### Virtual Accounts List

**File:** `backend/virtual_accounts/templates/virtual_accounts/virtual-accounts.html`

- Create form: name, target amount, color picker, icon, **linked account** dropdown
- Active virtual accounts: icon, name, balance, progress bar, archive button

### Virtual Account Detail

**File:** `backend/virtual_accounts/templates/virtual_accounts/virtual-account-detail.html`

- Header: icon, name, balance, progress bar, **Edit** button (opens bottom sheet)
- Edit bottom sheet: name, target amount, color, icon, linked account, exclude from net worth
- Allocate form: type (contribution/withdrawal), amount, note — **no account/date fields** (direct allocation)
- History: both direct allocations and transaction-linked allocations

### Virtual Account Edit Form

**File:** `backend/virtual_accounts/templates/virtual_accounts/partials/virtual-account-edit-form.html`

- Loaded via HTMX into a bottom sheet from the detail page
- Pre-populated with current values (name, target, color, icon, linked account, exclude flag)
- Follows the same pattern as account editing (see `account-edit-form.html`)

### Transaction Forms

VA dropdown in transaction-new.html and quick-entry.html includes `data-account-id` attributes on each option. JavaScript filters the dropdown when the account selection changes.

## Key Files

| File | Purpose |
|------|---------|
| `backend/core/models.py` | VirtualAccount, VirtualAccountAllocation models |
| `backend/virtual_accounts/services.py` | CRUD, allocation, direct allocate, balance recalculation |
| `backend/virtual_accounts/views.py` | Views for VA pages and allocation |
| `backend/virtual_accounts/templates/virtual_accounts/virtual-accounts.html` | List page |
| `backend/virtual_accounts/templates/virtual_accounts/virtual-account-detail.html` | Detail page with edit bottom sheet |
| `backend/virtual_accounts/templates/virtual_accounts/partials/virtual-account-edit-form.html` | Edit form partial |

## Logging

**Service events:**

- `virtual_account.created` — new virtual account created
- `virtual_account.archived` — virtual account archived (id)
- `virtual_account.allocated` — transaction allocated to virtual account (virtual_account_id, transaction_id)
- `virtual_account.updated` — virtual account details edited (id)
- `virtual_account.direct_allocated` — direct allocation to virtual account (virtual_account_id)

**Page views:** `virtual-accounts`, `virtual-account-detail`
**Partial views:** `virtual-account-edit-form`
