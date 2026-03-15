# Virtual Accounts

Envelope-style budgeting system. Users partition money across named goals/purposes (Emergency Fund, Vacation, etc.) and allocate transactions to track progress.

## Concept

Virtual accounts don't move real money between accounts — they logically tag funds as belonging to a virtual account. Each virtual account has:

- **Name** and optional **icon** + **color**
- **Target amount** (optional — nil means no goal)
- **Current balance** (denormalized cache of SUM allocations)
- **Linked bank account** (optional — links the VA to a specific real account)
- **Archive** capability (soft-delete for completed virtual accounts)

### Two types of allocations

1. **Direct allocations** — created from the VA detail page. These earmark existing funds without creating a transaction. The bank account balance is not affected.
2. **Transaction-linked allocations** — created when selecting a VA during transaction creation. Both the transaction and the allocation are created together.

## Model

**File:** `internal/models/virtual_account.go`

### VirtualAccount

```go
type VirtualAccount struct {
    ID             string
    Name           string
    TargetAmount   *float64       // nullable pointer: nil = no target
    CurrentBalance float64        // cached denormalized sum of allocations
    Icon           string
    Color          string
    IsArchived     bool
    DisplayOrder   int
    AccountID      *string        // linked bank account (nullable for legacy VAs)
    CreatedAt      time.Time
    UpdatedAt      time.Time
}
```

`ProgressPct()` method returns percentage (0 if no target, can exceed 100).

### VirtualAccountAllocation

```go
type VirtualAccountAllocation struct {
    ID                string
    TransactionID     *string    // nullable — NULL for direct allocations
    VirtualAccountID  string     // FK to virtual_accounts
    Amount            float64    // positive = contribution, negative = withdrawal
    Note              *string    // optional note for direct allocations
    AllocatedAt       *time.Time // date of direct allocation (NULL for tx-linked)
    CreatedAt         time.Time
}
```

This is a junction/pivot table linking allocations to virtual accounts. Direct allocations have `TransactionID = NULL`.

## Database

**Migrations:**

- `000015_create_virtual_funds.up.sql` — original creation
- `000022_rename_virtual_funds_to_virtual_accounts.up.sql` — rename
- `000025_fix_virtual_account_allocations.up.sql` — add account_id, allow direct allocations

Two tables:

1. `virtual_accounts` — virtual account definitions with cached `current_balance` and optional `account_id`
2. `virtual_account_allocations` — join table with partial unique index on `(transaction_id, virtual_account_id) WHERE transaction_id IS NOT NULL`

## Repository

**File:** `internal/repository/virtual_account.go`

### Virtual Account Operations

| Method | Purpose |
|--------|---------|
| `GetAll()` | Non-archived virtual accounts, ordered by display_order |
| `GetAllIncludingArchived()` | All virtual accounts (for settings) |
| `GetByID(id)` | Single virtual account |
| `GetByAccountID(accountID)` | VAs linked to a specific bank account |
| `Create(account)` | Insert with RETURNING (includes account_id) |
| `Update(account)` | Update name, target, icon, color, order, account_id |
| `Archive(id)` | Set `is_archived = true` |
| `Unarchive(id)` | Set `is_archived = false` |
| `Delete(id)` | Hard delete (only if no allocations) |

### Allocation Operations

| Method | Purpose |
|--------|---------|
| `Allocate(alloc)` | **UPSERT** — INSERT or UPDATE on conflict (tx-linked allocations) |
| `DirectAllocate(alloc)` | INSERT direct allocation (no transaction_id) |
| `Deallocate(txID, accountID)` | Remove allocation |
| `RecalculateBalance(accountID)` | Update `current_balance = SUM(amount)` from allocations |
| `GetAllocationsForAccount(accountID)` | All allocations (direct + tx-linked) via LEFT JOIN |
| `GetTransactionsForAccount(accountID)` | Full Transaction records allocated to virtual account |
| `CountAllocationsForAccount(accountID)` | COUNT for pre-delete check |

## Service

**File:** `internal/service/virtual_account.go`

| Method | Purpose |
|--------|---------|
| `GetAll()` | Non-archived virtual accounts |
| `GetByAccountID(accountID)` | VAs linked to a bank account |
| `Create(account)` | Validation (name required, defaults color to #0d9488) |
| `Update(account)` | Validation (name required) |
| `Archive(id)` | Soft-delete |
| `Allocate(txID, vaID, amount)` | Transaction-linked allocation + recalculate balance |
| `DirectAllocate(vaID, amount, note, date)` | Direct allocation (no transaction) + recalculate balance |
| `Deallocate(txID, vaID)` | Remove allocation + recalculate balance |

## Handler

**File:** `internal/handler/pages.go`

| Route | Method | Handler | Purpose |
|-------|--------|---------|---------|
| `/virtual-accounts` | GET | `VirtualAccounts()` | List page with create form |
| `/virtual-accounts/add` | POST | `VirtualAccountAdd()` | Create virtual account (with account_id) |
| `/virtual-accounts/{id}` | GET | `VirtualAccountDetail()` | Detail page with allocation history |
| `/virtual-accounts/{id}/archive` | POST | `VirtualAccountArchive()` | Archive virtual account |
| `/virtual-accounts/{id}/allocate` | POST | `VirtualAccountAllocate()` | Direct allocation (no transaction created) |

### Account linkage validation

When creating a transaction and selecting a VA, the handler validates that the VA's `account_id` matches the transaction's `account_id`. VAs with NULL `account_id` (legacy) are allowed for any account.

### Cross-link from account detail

The bank account detail page (`/accounts/{id}`) shows a "Virtual Accounts" section listing all VAs linked to that account. Each card links to the VA detail page. This provides bidirectional navigation between accounts and their VAs.

### Over-allocation warnings

The detail page and list page show amber warnings when:

1. **Single VA exceeds account** — a VA's `current_balance` is greater than the linked bank account's `current_balance`. Shown as an amber banner on the VA detail page.
2. **Group total exceeds account** — the sum of all VA balances linked to the same bank account exceeds that account's balance. Shown as an amber banner on both the detail page and list page, plus per-card "Exceeds account balance" text on individual VA cards.

Computed in the handlers (`VirtualAccountDetail`, `VirtualAccounts`) by fetching the linked account and sibling VAs. No new database queries — reuses `GetByID` and `GetByAccountID`.

## Templates

### Virtual Accounts List

**File:** `internal/templates/pages/virtual-accounts.html`

- Create form: name, target amount, color picker, icon, **linked account** dropdown
- Active virtual accounts: icon, name, balance, progress bar, archive button

### Virtual Account Detail

**File:** `internal/templates/pages/virtual-account-detail.html`

- Header: icon, name, balance, progress bar
- Allocate form: type (contribution/withdrawal), amount, note — **no account/date fields** (direct allocation)
- History: both direct allocations and transaction-linked allocations

### Transaction Forms

VA dropdown in transaction-new.html and quick-entry.html includes `data-account-id` attributes on each option. JavaScript filters the dropdown when the account selection changes.

## Key Files

| File | Purpose |
|------|---------|
| `internal/models/virtual_account.go` | VirtualAccount, VirtualAccountAllocation structs |
| `internal/repository/virtual_account.go` | CRUD, allocation UPSERT, direct allocate, balance recalculation |
| `internal/service/virtual_account.go` | Validation, allocate/deallocate with cache sync |
| `internal/handler/pages.go` | Handlers for VA pages and allocation |
| `internal/templates/pages/virtual-accounts.html` | List page |
| `internal/templates/pages/virtual-account-detail.html` | Detail page |
| `internal/database/migrations/000025_fix_virtual_account_allocations.up.sql` | Direct allocation + account linkage migration |

## Logging

**Service events:**

- `virtual_account.created` — new virtual account created
- `virtual_account.archived` — virtual account archived (id)
- `virtual_account.allocated` — transaction allocated to virtual account (virtual_account_id, transaction_id)
- `virtual_account.direct_allocated` — direct allocation to virtual account (virtual_account_id)

**Page views:** `virtual-accounts`, `virtual-account-detail`
