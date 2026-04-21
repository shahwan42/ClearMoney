# Logging

Structured logging system for debugging and usage analytics.

## Architecture

ClearMoney uses a 3-layer logging architecture:

```text
HTTP Request → StructuredLogger (request metrics) → View (page views) → Service (event logs)
```

### Layer 1: Request Middleware (`StructuredLogger`)

Every HTTP request is logged with:

| Field | Description |
|-------|-------------|
| `status` | HTTP status code (200, 404, 500, etc.) |
| `status_class` | Status bucket (`2xx`, `4xx`, `5xx`) |
| `duration_ms` | Request processing time in milliseconds |
| `bytes` | Response body size |
| `route` | URL pattern (e.g., `/accounts/<uuid:id>`) |
| `is_htmx` | Whether `HX-Request: true` header is present |
| `device` | `mobile`, `desktop`, or `bot` (from User-Agent) |

Log level is based on status: 5xx → Error, 4xx → Warn, 2xx/3xx → Info.

Paths `/static/*` and `/healthz` are excluded to reduce noise.

### Layer 2: Page View Logging (Views)

Every page view logs which page is being viewed:

```python
logger.info("page viewed", extra={"page": "dashboard"})
```

HTMX partial handlers log:

```python
logger.info("partial loaded", extra={"partial": "recent-transactions"})
```

### Layer 3: Service Event Logging

Every mutating service method logs a structured event after success:

```python
logger.info("transaction.created", extra={"type": "expense", "currency": "EGP"})
```

Events use `entity.action` naming convention. Only IDs, types, and currencies are logged — never amounts or PII.

## Event Catalog

| Event | Service | Metadata |
|-------|---------|----------|
| `transaction.created` | TransactionService | type, currency, account_id |
| `transaction.updated` | TransactionService | id |
| `transaction.deleted` | TransactionService | id |
| `transaction.transfer_created` | TransactionService | source, dest |
| `transaction.exchange_created` | TransactionService | source, dest |
| `transaction.instapay_created` | TransactionService | — |
| `account.created` | AccountService | type, currency |
| `account.updated` | AccountService | id |
| `account.deleted` | AccountService | id |
| `account.dormant_toggled` | AccountService | id |
| `institution.created` | InstitutionService | — |
| `institution.updated` | InstitutionService | id |
| `institution.deleted` | InstitutionService | id |
| `person.created` | PersonService | — |
| `person.loan_recorded` | PersonService | type, currency |
| `person.repayment_recorded` | PersonService | currency |
| `budget.created` | BudgetService | currency, category_id |
| `budget.deleted` | BudgetService | id |
| `virtual_account.created` | VirtualAccountService | — |
| `virtual_account.archived` | VirtualAccountService | id |
| `virtual_account.allocated` | VirtualAccountService | virtual_account_id, transaction_id |
| `investment.created` | InvestmentService | currency |
| `investment.valuation_updated` | InvestmentService | id |
| `investment.deleted` | InvestmentService | id |
| `recurring.created` | RecurringService | frequency |
| `recurring.confirmed` | RecurringService | id |
| `recurring.skipped` | RecurringService | id |
| `recurring.deleted` | RecurringService | id |
| `recurring.auto_processed` | RecurringService | id |
| `salary.distributed` | SalaryService | allocation_count |
| `export.csv_downloaded` | ExportService | row_count |
| `auth.magic_link_sent` | AuthService | purpose |
| `auth.user_registered` | AuthService | — |
| `auth.login_success` | AuthService | purpose |
| `auth.logout` | AuthService | — |

## Debug Logging

Enabled with `LOG_LEVEL=debug`. Invisible at the default Info level.

- **Dashboard source timing** — each data source (institutions, exchange rate, people, virtual accounts, investments, streak, transactions, snapshots, health, budgets, spending comparison) logs its load duration in milliseconds, plus a total dashboard load time
- **Complex service methods** — entry logging for `Create`, `CreateTransfer`, `CreateExchange`, `DistributeSalary`, `RecordLoan`, `RecordRepayment`

## Key Files

| File | Purpose |
|------|---------|
| `backend/core/middleware.py` | `GoSessionAuthMiddleware`, request logging |
| `backend/core/htmx.py` | HTMX detection helpers |

## Adding Logging to New Features

1. **Service events**: Add `logger.info("entity.action", extra={...})` after successful mutations
2. **Page views**: Add `logger.info("page viewed: <name>")` as the first line of page views
3. **Debug logging**: Add `logger.debug(...)` for complex operations that benefit from development-time tracing

## Example Log Output

```
time=2025-01-15T10:30:00.000+02:00 level=INFO msg="request completed" method=POST path=/transactions status=303 duration_ms=45
time=2025-01-15T10:30:00.000+02:00 level=INFO msg="transaction.created" type=expense currency=EGP account_id=acc_123
```
