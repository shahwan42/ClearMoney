# Virtual Funds

Envelope-style budgeting system. Users partition money across named goals/purposes (Emergency Fund, Vacation, etc.) and allocate transactions to track progress.

## Concept

Virtual funds don't move real money between accounts — they logically tag transactions as belonging to a fund. Each fund has:

- **Name** and optional **icon** + **color**
- **Target amount** (optional — nil means no goal)
- **Current balance** (denormalized cache of SUM allocations)
- **Archive** capability (soft-delete for completed funds)

## Model

**File:** `internal/models/virtual_fund.go`

### VirtualFund

```go
type VirtualFund struct {
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

### FundAllocation

```go
type FundAllocation struct {
    ID              string
    TransactionID   string   // FK to transactions
    VirtualFundID   string   // FK to virtual_funds
    Amount          float64  // positive = contribution, negative = withdrawal
    CreatedAt       time.Time
}
```

This is a junction/pivot table linking transactions to funds.

## Database

**Migration:** `internal/database/migrations/000015_create_virtual_funds.up.sql`

Two tables:
1. `virtual_funds` — fund definitions with cached `current_balance`
2. `transaction_fund_allocations` — join table with unique constraint on `(transaction_id, virtual_fund_id)`

The migration includes a data migration that converts legacy `is_building_fund` flags to the new system.

## Repository

**File:** `internal/repository/virtual_fund.go`

### Fund Operations

| Method | Purpose |
|--------|---------|
| `GetAll()` | Non-archived funds, ordered by display_order |
| `GetAllIncludingArchived()` | All funds (for settings) |
| `GetByID(id)` | Single fund |
| `Create(fund)` | Insert with RETURNING |
| `Update(fund)` | Update name, target, icon, color, order |
| `Archive(id)` | Set `is_archived = true` |
| `Unarchive(id)` | Set `is_archived = false` |
| `Delete(id)` | Hard delete (only if no allocations) |

### Allocation Operations

| Method | Purpose |
|--------|---------|
| `Allocate(txID, fundID, amount)` | **UPSERT** — INSERT or UPDATE on conflict |
| `Deallocate(txID, fundID)` | Remove allocation |
| `RecalculateBalance(fundID)` | Update `current_balance = SUM(amount)` from allocations |
| `GetAllocationsForFund(fundID)` | Allocations with joined transaction data |
| `GetTransactionsForFund(fundID)` | Full Transaction records allocated to fund |
| `CountAllocationsForFund(fundID)` | COUNT for pre-delete check |

### Denormalized Balance Pattern

`RecalculateBalance()` updates the cached `current_balance` using a correlated subquery:

```sql
UPDATE virtual_funds
SET current_balance = COALESCE((SELECT SUM(amount) FROM transaction_fund_allocations WHERE virtual_fund_id = $1), 0)
WHERE id = $1
```

This avoids expensive SUM queries on every page load.

## Service

**File:** `internal/service/virtual_fund.go`

| Method | Purpose |
|--------|---------|
| `GetAll()` | Non-archived funds |
| `GetAllIncludingArchived()` | All funds |
| `Create(fund)` | Validation (name required, defaults color to #0d9488) |
| `Update(fund)` | Validation (name required) |
| `Archive(id)` | Soft-delete |
| `Unarchive(id)` | Restore |
| `Allocate(txID, fundID, amount)` | Two-step: allocate + recalculate balance |
| `Deallocate(txID, fundID)` | Two-step: deallocate + recalculate balance |

**Key pattern:** `Allocate` and `Deallocate` always call `RecalculateBalance()` after the allocation change to keep the cache in sync.

## Handler

**File:** `internal/handler/pages.go`

| Route | Method | Handler | Purpose |
|-------|--------|---------|---------|
| `/virtual-funds` | GET | `VirtualFunds()` | List page with create form |
| `/virtual-funds/add` | POST | `VirtualFundAdd()` | Create fund |
| `/virtual-funds/{id}` | GET | `VirtualFundDetail()` | Detail page with allocations |
| `/virtual-funds/{id}/archive` | POST | `VirtualFundArchive()` | Archive fund |
| `/virtual-funds/{id}/allocate` | POST | `VirtualFundAllocate()` | Create transaction + allocate |

### VirtualFundAllocate Handler

This handler does two things atomically:
1. Creates a transaction (income for contribution, expense for withdrawal)
2. Allocates the transaction to the fund (positive or negative amount)

## Templates

### Virtual Funds List

**File:** `internal/templates/pages/virtual-funds.html`

- Create form: name, target amount (optional), color picker, icon
- Active funds: icon, name, balance, progress bar (if target set), archive button
- Empty state

### Virtual Fund Detail

**File:** `internal/templates/pages/virtual-fund-detail.html`

- Fund header: icon, name, balance, progress bar
- Allocate form: type (contribution/withdrawal), amount, account, date, note
- Transaction history: allocated transactions with type coloring

## Dashboard Integration

- `DashboardData.VirtualFunds` holds `[]models.VirtualFund`
- Dashboard shows horizontally scrolling fund cards with color-coded borders
- Each card: icon, name, balance, progress bar (if target set)
- Links to detail page

## Key Files

| File | Purpose |
|------|---------|
| `internal/models/virtual_fund.go` | VirtualFund, FundAllocation structs |
| `internal/repository/virtual_fund.go` | CRUD, allocation UPSERT, balance recalculation |
| `internal/service/virtual_fund.go` | Validation, allocate/deallocate with cache sync |
| `internal/handler/pages.go` | VirtualFunds, VirtualFundDetail, VirtualFundAllocate handlers |
| `internal/templates/pages/virtual-funds.html` | List page |
| `internal/templates/pages/virtual-fund-detail.html` | Detail page |
| `internal/database/migrations/000015_create_virtual_funds.up.sql` | Schema + data migration |

## For Newcomers

- **Virtual funds don't move money** — they logically tag transactions. The actual money stays in the real account.
- **Denormalized cache** — `current_balance` is cached and recalculated after every allocation change. This is a common pattern to avoid expensive SUM queries.
- **UPSERT for allocations** — `INSERT ... ON CONFLICT DO UPDATE` prevents duplicate allocations.
- **Nullable target** — `*float64` pointer means nil = "no goal set". Always nil-check before computing progress.
- **Archive vs Delete** — archived funds are soft-deleted (still in DB, just hidden). Hard delete only works if no allocations exist.
