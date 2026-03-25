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

**File:** `backend/core/models.py`

`Investment` columns: `id` (UUID), `user_id` (FK), `platform`, `fund_name`, `units` (NUMERIC), `last_unit_price` (NUMERIC), `currency`, `last_updated`, `created_at`, `updated_at`.

`valuation` property: Returns `units * last_unit_price`. Called in templates via `{{ investment.valuation }}`.

## Service

**File:** `backend/investments/services.py`

| Method | Purpose |
|--------|---------|
| `Create(inv)` | Validates (fund_name required, units > 0, price > 0), defaults platform to "Thndr", currency to EGP |
| `GetAll()` | All investments, ordered by platform, fund_name |
| `GetByID(id)` | Single investment |
| `UpdateValuation(id, unit_price)` | Validates price > 0, updates last_unit_price + last_updated |
| `Delete(id)` | Remove investment |
| `GetTotalValuation()` | Portfolio total — `SELECT SUM(units * last_unit_price)` |

## Views

**File:** `backend/investments/views.py`

| Route | Method | Handler | Purpose |
|-------|--------|---------|---------|
| `/investments` | GET | `investments_page()` | Portfolio page with all holdings |
| `/investments/add` | POST | `investment_add()` | Create investment |
| `/investments/{id}/update` | POST | `investment_update()` | Update unit price |
| `/investments/{id}/delete` | POST | `investment_delete()` | Delete investment |

## Template

**File:** `backend/investments/templates/investments/investments.html`

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

Dashboard shows total investment valuation with link to `/investments`.

## Key Files

| File | Purpose |
|------|---------|
| `backend/core/models.py` | Investment model, valuation property |
| `backend/investments/services.py` | CRUD, valuation update, portfolio total |
| `backend/investments/views.py` | Views for investment pages |
| `backend/investments/templates/investments/investments.html` | Portfolio page |

## For Newcomers

- **Computed valuation** — `valuation` is a model property, not a DB column. No need to store it.
- **Platform default** — defaults to "Thndr" (Egyptian investment platform). Can be changed per investment.
- **No price history** — only the latest unit price is stored. Historical prices are not tracked.
- **Dashboard integration** — uses `GetTotalValuation()` for portfolio total on the dashboard.

## Logging

**Service events:**

- `investment.created` — new investment added (currency)
- `investment.valuation_updated` — unit price updated (id)
- `investment.deleted` — investment removed (id)

**Page views:** `investments`
