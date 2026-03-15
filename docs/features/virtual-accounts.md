# Virtual Accounts

Envelope-style budgeting system. Users partition money across named goals/purposes (Emergency Fund, Vacation, etc.) and allocate transactions to track progress.

## Concept

Virtual accounts don't move real money between accounts — they logically tag transactions as belonging to a virtual account. Each virtual account has:

- **Name** and optional **icon** + **color**
- **Target amount** (optional — nil means no goal)
- **Current balance** (denormalized cache of SUM allocations)
- **Archive** capability (soft-delete for completed virtual accounts)

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
    CreatedAt      time.Time
    UpdatedAt      time.Time
}
```

`ProgressPct()` method returns percentage (0 if no target, can exceed 100).

### VirtualAccountAllocation

```go
type VirtualAccountAllocation struct {
    ID                string
    TransactionID     string   // FK to transactions
    VirtualAccountID  string   // FK to virtual_accounts
    Amount            float64  // positive = contribution, negative = withdrawal
    CreatedAt         time.Time
}
```

This is a junction/pivot table linking transactions to virtual accounts.

## Database

**Migration:** `internal/database/migrations/000015_create_virtual_funds.up.sql` (original creation)
**Migration:** `internal/database/migrations/000022_rename_virtual_funds_to_virtual_accounts.up.sql` (rename)

Two tables:
1. `virtual_accounts` — virtual account definitions with cached `current_balance`
2. `virtual_account_allocations` — join table with unique constraint on `(transaction_id, virtual_account_id)`

The original migration includes a data migration that converts legacy `is_building_fund` flags to the new system.

## Repository

**File:** `internal/repository/virtual_account.go`

### Virtual Account Operations

| Method | Purpose |
|--------|---------|
| `GetAll()` | Non-archived virtual accounts, ordered by display_order |
| `GetAllIncludingArchived()` | All virtual accounts (for settings) |
| `GetByID(id)` | Single virtual account |
| `Create(account)` | Insert with RETURNING |
| `Update(account)` | Update name, target, icon, color, order |
| `Archive(id)` | Set `is_archived = true` |
| `Unarchive(id)` | Set `is_archived = false` |
| `Delete(id)` | Hard delete (only if no allocations) |

### Allocation Operations

| Method | Purpose |
|--------|---------|
| `Allocate(txID, accountID, amount)` | **UPSERT** — INSERT or UPDATE on conflict |
| `Deallocate(txID, accountID)` | Remove allocation |
| `RecalculateBalance(accountID)` | Update `current_balance = SUM(amount)` from allocations |
| `GetAllocationsForAccount(accountID)` | Allocations with joined transaction data |
| `GetTransactionsForAccount(accountID)` | Full Transaction records allocated to virtual account |
| `CountAllocationsForAccount(accountID)` | COUNT for pre-delete check |

### Denormalized Balance Pattern

`RecalculateBalance()` updates the cached `current_balance` using a correlated subquery:

```sql
UPDATE virtual_accounts
SET current_balance = COALESCE((SELECT SUM(amount) FROM virtual_account_allocations WHERE virtual_account_id = $1), 0)
WHERE id = $1
```

This avoids expensive SUM queries on every page load.

## Service

**File:** `internal/service/virtual_account.go`

| Method | Purpose |
|--------|---------|
| `GetAll()` | Non-archived virtual accounts |
| `GetAllIncludingArchived()` | All virtual accounts |
| `Create(account)` | Validation (name required, defaults color to #0d9488) |
| `Update(account)` | Validation (name required) |
| `Archive(id)` | Soft-delete |
| `Unarchive(id)` | Restore |
| `Allocate(txID, accountID, amount)` | Two-step: allocate + recalculate balance |
| `Deallocate(txID, accountID)` | Two-step: deallocate + recalculate balance |

**Key pattern:** `Allocate` and `Deallocate` always call `RecalculateBalance()` after the allocation change to keep the cache in sync.

## Handler

**File:** `internal/handler/pages.go`

| Route | Method | Handler | Purpose |
|-------|--------|---------|---------|
| `/virtual-accounts` | GET | `VirtualAccounts()` | List page with create form |
| `/virtual-accounts/add` | POST | `VirtualAccountAdd()` | Create virtual account |
| `/virtual-accounts/{id}` | GET | `VirtualAccountDetail()` | Detail page with allocations |
| `/virtual-accounts/{id}/archive` | POST | `VirtualAccountArchive()` | Archive virtual account |
| `/virtual-accounts/{id}/allocate` | POST | `VirtualAccountAllocate()` | Create transaction + allocate |

### VirtualAccountAllocate Handler

This handler does two things atomically:
1. Creates a transaction (income for contribution, expense for withdrawal)
2. Allocates the transaction to the virtual account (positive or negative amount)

## Templates

### Virtual Accounts List

**File:** `internal/templates/pages/virtual-accounts.html`

- Create form: name, target amount (optional), color picker, icon
- Active virtual accounts: icon, name, balance, progress bar (if target set), archive button
- Empty state

### Virtual Account Detail

**File:** `internal/templates/pages/virtual-account-detail.html`

- Virtual account header: icon, name, balance, progress bar
- Allocate form: type (contribution/withdrawal), amount, account, date, note
- Transaction history: allocated transactions with type coloring

## Dashboard Integration

- `DashboardData.VirtualAccounts` holds `[]models.VirtualAccount`
- Dashboard shows horizontally scrolling virtual account cards with color-coded borders
- Each card: icon, name, balance, progress bar (if target set)
- Links to detail page

## Key Files

| File | Purpose |
|------|---------|
| `internal/models/virtual_account.go` | VirtualAccount, VirtualAccountAllocation structs |
| `internal/repository/virtual_account.go` | CRUD, allocation UPSERT, balance recalculation |
| `internal/service/virtual_account.go` | Validation, allocate/deallocate with cache sync |
| `internal/handler/pages.go` | VirtualAccounts, VirtualAccountDetail, VirtualAccountAllocate handlers |
| `internal/templates/pages/virtual-accounts.html` | List page |
| `internal/templates/pages/virtual-account-detail.html` | Detail page |
| `internal/database/migrations/000015_create_virtual_funds.up.sql` | Original schema + data migration |
| `internal/database/migrations/000022_rename_virtual_funds_to_virtual_accounts.up.sql` | Rename migration |

## For Newcomers

- **Virtual accounts don't move money** — they logically tag transactions. The actual money stays in the real account.
- **Denormalized cache** — `current_balance` is cached and recalculated after every allocation change. This is a common pattern to avoid expensive SUM queries.
- **UPSERT for allocations** — `INSERT ... ON CONFLICT DO UPDATE` prevents duplicate allocations.
- **Nullable target** — `*float64` pointer means nil = "no goal set". Always nil-check before computing progress.
- **Archive vs Delete** — archived virtual accounts are soft-deleted (still in DB, just hidden). Hard delete only works if no allocations exist.

## Logging

**Service events:**

- `virtual_account.created` — new virtual account created
- `virtual_account.archived` — virtual account archived (id)
- `virtual_account.allocated` — transaction allocated to virtual account (account_id, transaction_id)

**Page views:** `virtual-accounts`, `virtual-account-detail`
