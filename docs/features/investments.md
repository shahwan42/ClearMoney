# Investments

Portfolio tracking for fund/stock holdings. Record holdings with units and price per unit, update valuations periodically.

## Concept

Each investment tracks:
- **Platform** (e.g., "Thndr") and **fund name**
- **Units** (fractional, e.g., 152.347)
- **Last unit price** (NAV per unit)
- **Currency** (EGP or USD)

**Valuation is computed, not stored:** `Total = Units × LastUnitPrice`

## Model

**File:** `internal/models/investment.go`

```go
type Investment struct {
    ID            string
    Platform      string
    FundName      string
    Units         float64
    LastUnitPrice float64
    Currency      string
    LastUpdated   time.Time
    CreatedAt     time.Time
    UpdatedAt     time.Time
}
```

`Valuation()` method (value receiver): Returns `Units * LastUnitPrice`. Called in templates as `{{ .Valuation }}` (Go templates call zero-arg methods automatically).

## Repository

**File:** `internal/repository/investment.go`

| Method | Purpose |
|--------|---------|
| `Create(ctx, inv)` | Insert with RETURNING |
| `GetAll(ctx)` | All investments, ordered by platform, fund_name |
| `GetByID(ctx, id)` | Single investment |
| `UpdateValuation(ctx, id, unitPrice)` | Update last_unit_price + last_updated = NOW() |
| `Delete(ctx, id)` | Remove investment |
| `GetTotalValuation(ctx)` | `SELECT SUM(units * last_unit_price)` — portfolio total |

`GetTotalValuation` uses `sql.NullFloat64` to handle NULL when no investments exist.

## Service

**File:** `internal/service/investment.go`

| Method | Purpose |
|--------|---------|
| `Create(ctx, inv)` | Validates (FundName required, Units > 0, Price > 0), defaults Platform to "Thndr", Currency to EGP |
| `GetAll(ctx)` | Passthrough |
| `UpdateValuation(ctx, id, price)` | Validates price > 0, delegates to repo |
| `Delete(ctx, id)` | Passthrough |
| `GetTotalValuation(ctx)` | Portfolio aggregate for dashboard |

## Handler

**File:** `internal/handler/pages.go`

| Route | Method | Handler | Purpose |
|-------|--------|---------|---------|
| `/investments` | GET | `Investments()` | Portfolio page with all holdings |
| `/investments/add` | POST | `InvestmentAdd()` | Create investment |
| `/investments/{id}/update` | POST | `InvestmentUpdateValuation()` | Update unit price |
| `/investments/{id}` | DELETE | `InvestmentDelete()` | Delete investment |

## Template

**File:** `internal/templates/pages/investments.html`

Sections:
1. **Portfolio total** — gradient header with total valuation
2. **Add investment form** — platform, fund_name, units, unit_price, currency
3. **Holdings list** — for each investment:
   - Fund name, platform, units count
   - Valuation (formatted with currency)
   - Unit price, last updated date
   - Inline update form (new unit price)
   - Delete button

## Dashboard Integration

- `DashboardService` has `investmentRepo` via setter injection
- Calls `GetTotalValuation()` for portfolio total
- Dashboard shows total with link to `/investments`

## Key Files

| File | Purpose |
|------|---------|
| `internal/models/investment.go` | Investment struct, Valuation() method |
| `internal/repository/investment.go` | CRUD, SUM aggregate |
| `internal/service/investment.go` | Validation, defaults |
| `internal/handler/pages.go` | Investment handlers |
| `internal/templates/pages/investments.html` | Portfolio page |

## For Newcomers

- **Computed valuation** — `Valuation()` is a Go method, not a DB column. No need to store it.
- **Value receiver** — `func (i Investment) Valuation()` uses a value receiver (not pointer). This is safe for read-only computations.
- **Platform default** — defaults to "Thndr" (Egyptian investment platform). Can be changed per investment.
- **No price history** — only the latest unit price is stored. Historical prices are not tracked.
- **Dashboard integration** — uses repo directly (not service) via setter injection on DashboardService.

## Logging

**Service events:**

- `investment.created` — new investment added (currency)
- `investment.valuation_updated` — unit price updated (id)
- `investment.deleted` — investment removed (id)

**Page views:** `investments`
