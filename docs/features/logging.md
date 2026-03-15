# Logging

Structured logging system for debugging and usage analytics.

## Architecture

ClearMoney uses a 3-layer logging architecture:

```text
HTTP Request → StructuredLogger (request metrics) → Handler (page views) → Service (event logs)
```

### Layer 1: Request Middleware (`StructuredLogger`)

Every HTTP request is logged with:

| Field | Description |
|-------|-------------|
| `status` | HTTP status code (200, 404, 500, etc.) |
| `status_class` | Status bucket (`2xx`, `4xx`, `5xx`) |
| `duration_ms` | Request processing time in milliseconds |
| `bytes` | Response body size |
| `route` | Chi route pattern (e.g., `/accounts/{id}`, not `/accounts/abc123`) |
| `is_htmx` | Whether `HX-Request: true` header is present |
| `device` | `mobile`, `desktop`, or `bot` (from User-Agent) |

Log level is based on status: 5xx → Error, 4xx → Warn, 2xx/3xx → Info.

Paths `/static/*` and `/healthz` are excluded to reduce noise.

### Layer 2: Page View Logging (Handlers)

Every page handler logs which page is being viewed:

```go
authmw.Log(r.Context()).Info("page viewed", "page", "dashboard")
```

HTMX partial handlers log:

```go
authmw.Log(r.Context()).Info("partial loaded", "partial", "recent-transactions")
```

### Layer 3: Service Event Logging

Every mutating service method logs a structured event after success:

```go
logutil.LogEvent(ctx, "transaction.created", "type", "expense", "currency", "EGP")
```

Events use `entity.action` naming convention. Only IDs, types, and currencies are logged — never amounts, PINs, or PII.

## Event Catalog

| Event | Service | Metadata |
|-------|---------|----------|
| `transaction.created` | TransactionService | type, currency, account_id |
| `transaction.updated` | TransactionService | id |
| `transaction.deleted` | TransactionService | id |
| `transaction.transfer_created` | TransactionService | source, dest |
| `transaction.exchange_created` | TransactionService | source, dest |
| `transaction.instapay_created` | TransactionService | — |
| `transaction.fawry_cashout_created` | TransactionService | — |
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
| `virtual_fund.created` | VirtualFundService | — |
| `virtual_fund.archived` | VirtualFundService | id |
| `virtual_fund.allocated` | VirtualFundService | fund_id, transaction_id |
| `investment.created` | InvestmentService | currency |
| `investment.valuation_updated` | InvestmentService | id |
| `investment.deleted` | InvestmentService | id |
| `installment.created` | InstallmentService | account_id |
| `installment.payment_recorded` | InstallmentService | id |
| `installment.deleted` | InstallmentService | id |
| `recurring.created` | RecurringService | frequency |
| `recurring.confirmed` | RecurringService | id |
| `recurring.skipped` | RecurringService | id |
| `recurring.deleted` | RecurringService | id |
| `recurring.auto_processed` | RecurringService | id |
| `salary.distributed` | SalaryService | allocation_count |
| `export.csv_downloaded` | ExportService | row_count |
| `auth.setup_completed` | AuthService | — |
| `auth.pin_changed` | AuthService | — |
| `auth.login_success` | auth handler | — |
| `auth.logout` | auth handler | — |

## Debug Logging

Enabled with `LOG_LEVEL=debug`. Invisible at the default Info level.

- **Dashboard source timing** — each data source (institutions, exchange rate, people, virtual funds, investments, streak, transactions, snapshots, health, budgets, spending comparison) logs its load duration in milliseconds, plus a total dashboard load time
- **Complex service methods** — entry logging for `Create`, `CreateTransfer`, `CreateExchange`, `DistributeSalary`, `RecordLoan`, `RecordRepayment`
- **Template rendering** — which page template is being rendered and which layout (base/bare)

## Key Files

| File | Purpose |
|------|---------|
| `internal/logutil/logutil.go` | Core helpers: `SetLogger`, `Log`, `LogEvent` |
| `internal/middleware/logging.go` | `RequestLogger`, `StructuredLogger`, `ClassifyDevice` |
| `internal/handler/router.go` | Middleware stack ordering |

## Import Patterns

- **Handlers** import middleware: `authmw "github.com/shahwan42/clearmoney/internal/middleware"` → `authmw.Log(r.Context())`
- **Services** import logutil: `"github.com/shahwan42/clearmoney/internal/logutil"` → `logutil.LogEvent(ctx, ...)`
- The `logutil` package exists to break the import cycle between middleware (imports service for AuthService) and service packages

## Adding Logging to New Features

1. **Service events**: Add `logutil.LogEvent(ctx, "entity.action", ...)` after successful mutations
2. **Page views**: Add `authmw.Log(r.Context()).Info("page viewed", "page", "<name>")` as the first line of page handlers
3. **Debug logging**: Add `logutil.Log(ctx).Debug(...)` for complex operations that benefit from development-time tracing

## Example Log Output

```
time=2025-01-15T10:30:00.000+02:00 level=INFO msg="request completed" request_id=abc123 method=POST path=/transactions status=303 status_class=3xx duration_ms=45 bytes=0 route=/transactions is_htmx=true device=mobile
time=2025-01-15T10:30:00.000+02:00 level=INFO msg="operation completed" request_id=abc123 method=POST path=/transactions event=transaction.created type=expense currency=EGP account_id=acc_123
```
