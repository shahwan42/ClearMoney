# Exchange Rates

Historical USD/EGP exchange rate log used for currency conversions and multi-currency net worth calculations.

## Concept

ClearMoney supports two currencies: EGP (Egyptian Pound) and USD (US Dollar). Exchange rates are logged whenever a currency exchange transaction occurs, creating an append-only historical record.

## Model

**File:** `backend/core/models.py`

`ExchangeRateLog` columns: `id` (UUID), `date`, `rate` (NUMERIC — EGP per 1 USD, e.g., 50.5), `source` (nullable, e.g., "CBE"), `note`, `created_at`.

**Key:** Rate is always "EGP per 1 USD" regardless of transaction direction. This is an **append-only immutable log** (no updated_at field).

## Service

**File:** `backend/exchange_rates/services.py`

| Method | Purpose |
|--------|---------|
| `Create(log)` | Insert rate entry |
| `GetLatest()` | Most recent exchange rate |
| `GetByDateRange(from, to)` | Historical rates for a period |

## Usage

### In Transactions

When creating a currency exchange transaction, the service:
1. Records the exchange rate on both transaction legs
2. Logs the rate to `exchange_rate_log` via the service (non-critical — doesn't fail if logging errors)

### In Dashboard

The dashboard service uses the latest exchange rate to:
- Convert USD account balances to EGP for net worth calculation
- Display the current rate in the dashboard header

### In Snapshots

Historical exchange rates are used for accurate daily net worth snapshots, converting USD balances at the rate applicable on that date.

## Rate Convention

**Always stored as "EGP per 1 USD"** (e.g., 50.5 means 1 USD = 50.5 EGP).

When the exchange direction is EGP → USD, the service internally inverts the rate for calculation, then inverts back for storage/display. See the Transactions feature doc for details.

## Key Files

| File | Purpose |
|------|---------|
| `backend/core/models.py` | ExchangeRateLog model |
| `backend/exchange_rates/services.py` | CRUD, GetLatest |
| `backend/transactions/services/` | Rate logging during exchanges |
| `backend/dashboard/services/` | Rate used for USD→EGP conversion |

## For Newcomers

- **Append-only** — rates are never updated or deleted. Each entry is a historical record.
- **Non-critical logging** — if rate logging fails during an exchange, the transaction still succeeds.
- **Single rate convention** — always EGP/USD. Internal calculations may invert, but storage is consistent.

## Logging

**Page views:** `exchange-rates`
