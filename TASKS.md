# ClearMoney Implementation Tasks

> Auto-generated task breakdown from `clearmoney-prd.md`. Tasks are sequentially numbered and grouped by PRD phase. Each task is designed to be a single focused PR.

---

## Phase 1 -- Foundation

---

## TASK-001: Project scaffolding and Go module initialization

**Phase:** Phase 1
**Dependencies:** None
**Estimated effort:** 2h

### Description
Set up the Go module, directory structure per the PRD's project layout, and a minimal `main.go` that starts an HTTP server on port 8080 with a health-check endpoint. This is the skeleton everything else builds on.

### Scope
- [ ] Initialize Go module (`go mod init`)
- [ ] Create directory structure: `cmd/server/`, `internal/{config,database,models,repository,service,handler,middleware,jobs,templates/}`, `static/{css,js,icons}`
- [ ] Minimal `cmd/server/main.go` with chi router and `GET /healthz` returning 200
- [ ] `internal/config/config.go` loading env vars (DB URL, port, env mode)
- [ ] `.env.example` with placeholder values
- [ ] `Makefile` with targets: `run`, `build`, `test`

### Files touched
- `go.mod` (create)
- `go.sum` (create)
- `cmd/server/main.go` (create)
- `internal/config/config.go` (create)
- `.env.example` (create)
- `Makefile` (create)

### Acceptance criteria
- `go build ./cmd/server` succeeds
- `go test ./...` passes (even if no tests yet)
- Running the binary and hitting `GET /healthz` returns 200 OK

### Out of scope
- Docker setup (TASK-002)
- Database connection (TASK-003)

---

## TASK-002: Dockerfile and Docker Compose setup

**Phase:** Phase 1
**Dependencies:** TASK-001
**Estimated effort:** 2h

### Description
Create the Dockerfile for the Go app (multi-stage build) and `docker-compose.yml` with the app and PostgreSQL 16 services. This ensures identical dev and prod environments from day one.

### Scope
- [ ] Multi-stage `Dockerfile` (build stage with Go, runtime stage with minimal image)
- [ ] `docker-compose.yml` with `app` and `db` services per PRD section 10.2
- [ ] PostgreSQL 16 Alpine with volume for data persistence
- [ ] App service depends on db, reads from `.env`
- [ ] `.dockerignore` file

### Files touched
- `Dockerfile` (create)
- `docker-compose.yml` (create)
- `.dockerignore` (create)
- `.env.example` (modify -- add PostgreSQL vars)

### Acceptance criteria
- `docker compose up -d` starts both services
- `curl http://localhost:8080/healthz` returns 200
- PostgreSQL is accessible on port 5432

### Out of scope
- Caddy/Traefik reverse proxy (production concern)
- Database migrations (TASK-003)

---

## TASK-003: Database connection and migration framework

**Phase:** Phase 1
**Dependencies:** TASK-002
**Estimated effort:** 2h

### Description
Set up the PostgreSQL connection pool in Go, integrate a migration tool (golang-migrate or goose), and create the migration runner that executes on app startup. No actual schema yet -- just the infrastructure.

### Scope
- [ ] `internal/database/database.go` -- connection pool setup with `pgx` or `database/sql` + `lib/pq`
- [ ] Migration runner using `golang-migrate` (or `goose`)
- [ ] `internal/database/migrations/` directory with a `.gitkeep`
- [ ] App startup connects to DB and runs pending migrations
- [ ] Graceful shutdown closes DB pool
- [ ] `Makefile` targets: `migrate-up`, `migrate-down`, `migrate-create`

### Files touched
- `internal/database/database.go` (create)
- `internal/database/migrations/.gitkeep` (create)
- `cmd/server/main.go` (modify -- add DB init)
- `Makefile` (modify -- add migration targets)
- `go.mod` / `go.sum` (modify -- new dependencies)

### Acceptance criteria
- App starts and connects to PostgreSQL successfully
- Running with no migrations produces no errors
- `make migrate-create name=test` creates a new migration file pair

### Out of scope
- Actual schema migrations (TASK-004, TASK-005)

---

## TASK-004: Database migration -- institutions and accounts

**Phase:** Phase 1
**Dependencies:** TASK-003
**Estimated effort:** 2h

### Description
Create the SQL migration for the `institutions` and `accounts` tables per the PRD data model. These are the foundational entities that everything else references.

### Scope
- [ ] Migration: create `institutions` table (id UUID, name, type, color, icon, display_order, created_at, updated_at)
- [ ] Migration: create `accounts` table (id UUID, institution_id FK, name, type enum, currency enum, current_balance, initial_balance, credit_limit, is_dormant, role_tags, display_order, metadata JSONB, created_at, updated_at)
- [ ] Appropriate indexes (institution_id on accounts, etc.)
- [ ] Create custom enums: `account_type`, `currency_type`

### Files touched
- `internal/database/migrations/000001_create_institutions.up.sql` (create)
- `internal/database/migrations/000001_create_institutions.down.sql` (create)
- `internal/database/migrations/000002_create_accounts.up.sql` (create)
- `internal/database/migrations/000002_create_accounts.down.sql` (create)

### Acceptance criteria
- `make migrate-up` creates both tables
- `make migrate-down` drops them cleanly
- Enum constraints enforced (invalid account_type rejected)

### Out of scope
- Go model structs (TASK-006)
- Categories and transactions tables (TASK-005)

---

## TASK-005: Database migration -- categories, transactions, and related tables

**Phase:** Phase 1
**Dependencies:** TASK-004
**Estimated effort:** 3h

### Description
Create migrations for `categories`, `transactions`, `persons`, `exchange_rate_log` tables. Also seed the default expense and income categories from the PRD (C-1, C-2).

### Scope
- [ ] Migration: create `categories` table (id, name, type, icon, is_system, is_archived, display_order)
- [ ] Migration: create `persons` table (id, name, note, net_balance, created_at, updated_at)
- [ ] Migration: create `transactions` table with all columns from PRD section 5.1
- [ ] Migration: create `exchange_rate_log` table
- [ ] Seed migration: insert default expense categories (16 categories from C-1)
- [ ] Seed migration: insert default income categories (7 categories from C-2)
- [ ] Indexes on transactions: account_id, date, category_id, type

### Files touched
- `internal/database/migrations/000003_create_categories.up.sql` (create)
- `internal/database/migrations/000003_create_categories.down.sql` (create)
- `internal/database/migrations/000004_create_persons.up.sql` (create)
- `internal/database/migrations/000004_create_persons.down.sql` (create)
- `internal/database/migrations/000005_create_transactions.up.sql` (create)
- `internal/database/migrations/000005_create_transactions.down.sql` (create)
- `internal/database/migrations/000006_create_exchange_rate_log.up.sql` (create)
- `internal/database/migrations/000006_create_exchange_rate_log.down.sql` (create)
- `internal/database/migrations/000007_seed_categories.up.sql` (create)
- `internal/database/migrations/000007_seed_categories.down.sql` (create)

### Acceptance criteria
- All migrations run cleanly up and down
- Default categories exist after migration
- Transaction table has all columns from the PRD data model
- Foreign key constraints enforced

### Out of scope
- Recurring rules, installment plans, investments tables (Phase 4)
- Go model structs (TASK-006)

---

## TASK-006: Go domain models and enums

**Phase:** Phase 1
**Dependencies:** TASK-005
**Estimated effort:** 2h

### Description
Define Go structs for all core entities (Institution, Account, Transaction, Category, Person, ExchangeRateLog) matching the database schema. These are the shared types used by repository, service, and handler layers.

### Scope
- [ ] `internal/models/institution.go` -- Institution struct
- [ ] `internal/models/account.go` -- Account struct with enums for type and currency
- [ ] `internal/models/transaction.go` -- Transaction struct with type enum
- [ ] `internal/models/category.go` -- Category struct
- [ ] `internal/models/person.go` -- Person struct
- [ ] `internal/models/exchange_rate.go` -- ExchangeRateLog struct
- [ ] String constants for enums (account types, currency, transaction types)

### Files touched
- `internal/models/institution.go` (create)
- `internal/models/account.go` (create)
- `internal/models/transaction.go` (create)
- `internal/models/category.go` (create)
- `internal/models/person.go` (create)
- `internal/models/exchange_rate.go` (create)

### Acceptance criteria
- All structs have proper JSON and DB tags
- Enum constants match database enum values
- `go build ./...` succeeds

### Out of scope
- Repository methods (TASK-008, TASK-010)
- Validation logic (belongs in service layer)

---

## TASK-007: Test setup and helpers

**Phase:** Phase 1
**Dependencies:** TASK-003
**Estimated effort:** 2h

### Description
Set up the test infrastructure: a test database helper that creates/drops a test DB, runs migrations, and provides a clean database for each test suite. This unblocks all future integration tests.

### Scope
- [ ] `internal/testutil/database.go` -- helper to spin up a test DB (or use Docker test container)
- [ ] `internal/testutil/fixtures.go` -- helper functions to create test institutions, accounts, etc.
- [ ] Test configuration via environment variables
- [ ] Example test demonstrating the setup/teardown pattern
- [ ] Makefile target: `test-integration`

### Files touched
- `internal/testutil/database.go` (create)
- `internal/testutil/fixtures.go` (create)
- `internal/database/database_test.go` (create)
- `Makefile` (modify)

### Acceptance criteria
- `make test-integration` runs and passes
- Test DB is created, migrations run, and DB is cleaned up after tests
- Fixture helpers can insert test data

### Out of scope
- Unit test mocks (added as needed per feature)
- CI pipeline (TASK-045)

---

## TASK-008: Institution repository and handler (CRUD)

**Phase:** Phase 1
**Dependencies:** TASK-006, TASK-007
**Estimated effort:** 3h

### Description
Implement the full CRUD for institutions -- repository layer for DB queries, service layer (thin for now), and HTTP handlers. Institutions are the top-level grouping for accounts and must exist before accounts can be created.

### Scope
- [ ] `internal/repository/institution.go` -- Create, GetByID, GetAll, Update, Delete
- [ ] `internal/service/institution.go` -- thin wrapper with validation
- [ ] `internal/handler/institution.go` -- handlers for institution CRUD
- [ ] Routes: `GET /institutions`, `POST /institutions`, `PUT /institutions/{id}`, `DELETE /institutions/{id}`
- [ ] Integration tests for repository layer

### Files touched
- `internal/repository/institution.go` (create)
- `internal/service/institution.go` (create)
- `internal/handler/institution.go` (create)
- `internal/repository/institution_test.go` (create)
- `cmd/server/main.go` (modify -- register routes)

### Acceptance criteria
- Can create, read, update, delete institutions via HTTP
- Repository tests pass with real database
- Invalid data (empty name) returns appropriate errors

### Out of scope
- UI templates (TASK-013)
- Account CRUD (TASK-009)

---

## TASK-009: Account repository and handler (CRUD)

**Phase:** Phase 1
**Dependencies:** TASK-008
**Estimated effort:** 3h

### Description
Implement CRUD for accounts under institutions. Accounts are the core entity that transactions attach to, so this must handle all account types (checking, savings, credit card, etc.) and currency.

### Scope
- [ ] `internal/repository/account.go` -- Create, GetByID, GetAll, GetByInstitution, Update, Delete, UpdateBalance
- [ ] `internal/service/account.go` -- validation (credit_limit required for credit cards, etc.)
- [ ] `internal/handler/account.go` -- handlers for account CRUD
- [ ] Routes: `GET /accounts`, `POST /accounts`, `GET /accounts/{id}`, `PUT /accounts/{id}`, `DELETE /accounts/{id}`
- [ ] Integration tests for repository

### Files touched
- `internal/repository/account.go` (create)
- `internal/service/account.go` (create)
- `internal/handler/account.go` (create)
- `internal/repository/account_test.go` (create)
- `cmd/server/main.go` (modify -- register routes)

### Acceptance criteria
- Can create accounts under an institution with all fields
- Credit card accounts require credit_limit
- Balance field is set from initial_balance on creation
- Repository tests pass

### Out of scope
- Account detail page UI (TASK-014)
- Dormant account filtering (Phase 4)

---

## TASK-010: Category repository and handler

**Phase:** Phase 1
**Dependencies:** TASK-006
**Estimated effort:** 2h

### Description
Implement read access for seeded categories and CRUD for custom categories. Categories are needed before transactions can be entered.

### Scope
- [ ] `internal/repository/category.go` -- GetAll, GetByID, GetByType, Create, Update, Archive
- [ ] `internal/service/category.go` -- prevent modification of system categories
- [ ] `internal/handler/category.go` -- handlers
- [ ] Routes: `GET /categories`, `POST /categories`, `PUT /categories/{id}`

### Files touched
- `internal/repository/category.go` (create)
- `internal/service/category.go` (create)
- `internal/handler/category.go` (create)
- `cmd/server/main.go` (modify)

### Acceptance criteria
- Default seeded categories returned from GET
- Can create custom categories
- System categories cannot be deleted or renamed
- Archiving hides category from active list

### Out of scope
- Category icons/UI (TASK-015)
- Tags on transactions (Phase 2)

---

## TASK-011: Basic transaction repository and service (expense & income)

**Phase:** Phase 1
**Dependencies:** TASK-009, TASK-010
**Estimated effort:** 3h

### Description
Implement the core transaction creation for expense and income types. This is the most critical data operation in the app -- creating a transaction must also update the account's cached balance atomically.

### Scope
- [ ] `internal/repository/transaction.go` -- Create, GetByID, GetByAccount, GetRecent, Update, Delete
- [ ] `internal/service/transaction.go` -- create expense/income with balance update in a DB transaction
- [ ] Balance update logic: expense decrements, income increments account.current_balance
- [ ] Atomic: transaction insert + balance update in a single DB transaction
- [ ] Integration tests covering balance updates

### Files touched
- `internal/repository/transaction.go` (create)
- `internal/service/transaction.go` (create)
- `internal/repository/transaction_test.go` (create)
- `internal/service/transaction_test.go` (create)

### Acceptance criteria
- Creating an expense decrements account balance
- Creating an income increments account balance
- Deleting a transaction reverses the balance change
- Balance update is atomic (no partial state)
- Tests verify balance correctness

### Out of scope
- Transfers and exchanges (TASK-022, TASK-023)
- HTTP handlers for transactions (TASK-012)
- Credit card specific logic (TASK-024)

---

## TASK-012: Transaction HTTP handlers (expense & income)

**Phase:** Phase 1
**Dependencies:** TASK-011
**Estimated effort:** 2h

### Description
Wire up HTTP endpoints for creating, reading, updating, and deleting basic transactions. These endpoints return JSON for now; HTMX partial responses come later.

### Scope
- [ ] `internal/handler/transaction.go` -- Create, List, GetByID, Update, Delete handlers
- [ ] Routes: `POST /transactions`, `GET /transactions`, `GET /transactions/{id}`, `PUT /transactions/{id}`, `DELETE /transactions/{id}`
- [ ] Request validation (amount > 0, valid account_id, valid category_id)
- [ ] Response includes updated account balance (T-7)

### Files touched
- `internal/handler/transaction.go` (create)
- `cmd/server/main.go` (modify -- register routes)

### Acceptance criteria
- POST creates a transaction and returns it with the new balance
- GET lists transactions with basic pagination
- DELETE removes transaction and restores balance
- Invalid requests return 400 with descriptive errors

### Out of scope
- HTMX responses (TASK-018)
- Quick entry / bottom sheet UI (TASK-025)

---

## TASK-013: Base layout, templates, and Tailwind setup

**Phase:** Phase 1
**Dependencies:** TASK-001
**Estimated effort:** 3h

### Description
Set up the Go template engine, base HTML layout with Tailwind CSS (CDN for now), mobile-first responsive shell, sticky header, and bottom navigation. This is the visual foundation all pages build on.

### Scope
- [ ] Template engine setup in handler (parse templates, template functions for formatting currency/dates)
- [ ] `internal/templates/layouts/base.html` -- HTML shell with meta viewport, Tailwind CDN, HTMX script
- [ ] `internal/templates/components/header.html` -- sticky top header
- [ ] `internal/templates/components/bottom-nav.html` -- bottom nav with Home, Reports, People tabs + FAB placeholder
- [ ] `internal/templates/pages/home.html` -- placeholder dashboard page
- [ ] Template helper functions: `formatEGP`, `formatUSD`, `formatDate`
- [ ] `static/css/app.css` -- custom styles beyond Tailwind

### Files touched
- `internal/handler/templates.go` (create)
- `internal/templates/layouts/base.html` (create)
- `internal/templates/components/header.html` (create)
- `internal/templates/components/bottom-nav.html` (create)
- `internal/templates/pages/home.html` (create)
- `static/css/app.css` (create)
- `cmd/server/main.go` (modify -- serve static files, register page routes)

### Acceptance criteria
- `GET /` renders the base layout with header and bottom nav
- Page is mobile-responsive (375px viewport looks correct)
- Tailwind utility classes work
- HTMX script is loaded

### Out of scope
- Dashboard data (TASK-016)
- Dark mode (TASK-046)

---

## TASK-014: Accounts management UI page

**Phase:** Phase 1
**Dependencies:** TASK-008, TASK-009, TASK-013
**Estimated effort:** 3h

### Description
Build the accounts management page where the user can view, add, and edit institutions and accounts. This is needed before transaction entry because the user must set up their financial world first.

### Scope
- [ ] `internal/templates/pages/accounts.html` -- institution list with expandable accounts
- [ ] `internal/templates/partials/institution-card.html` -- single institution with its accounts
- [ ] `internal/templates/partials/account-form.html` -- form for adding/editing an account
- [ ] `internal/templates/partials/institution-form.html` -- form for adding/editing an institution
- [ ] HTMX: form submit creates account, swaps in updated list
- [ ] Account type selector with appropriate fields shown (credit_limit for credit cards)
- [ ] Currency selector (EGP/USD)

### Files touched
- `internal/templates/pages/accounts.html` (create)
- `internal/templates/partials/institution-card.html` (create)
- `internal/templates/partials/account-form.html` (create)
- `internal/templates/partials/institution-form.html` (create)
- `internal/handler/account.go` (modify -- add template rendering)
- `internal/handler/institution.go` (modify -- add template rendering)

### Acceptance criteria
- `GET /accounts` renders the full accounts page
- Can add a new institution via the form
- Can add a new account under an institution
- Credit card fields (credit_limit) appear conditionally
- HTMX updates the list without full page reload

### Out of scope
- Account reordering (P2 feature)
- Account detail page with transactions (TASK-027)

---

## TASK-015: Transaction entry form page

**Phase:** Phase 1
**Dependencies:** TASK-012, TASK-013
**Estimated effort:** 3h

### Description
Build the basic transaction entry form page for expenses and income. This is the first version of the entry UX -- a full-page form. The optimized bottom-sheet quick entry comes in Phase 2.

### Scope
- [ ] `internal/templates/pages/transaction-new.html` -- full transaction form
- [ ] Amount input (large, numeric-focused)
- [ ] Type selector (expense / income)
- [ ] Account dropdown populated from user's accounts
- [ ] Category dropdown populated from categories (filtered by type)
- [ ] Date picker defaulting to today
- [ ] Optional note field
- [ ] HTMX form submission with success feedback
- [ ] After save: show new balance confirmation (T-7)

### Files touched
- `internal/templates/pages/transaction-new.html` (create)
- `internal/templates/partials/transaction-success.html` (create)
- `internal/handler/transaction.go` (modify -- add template rendering, HTMX responses)

### Acceptance criteria
- `GET /transactions/new` renders the form
- Submitting creates a transaction and shows success with new balance
- Category list filters based on expense/income type selection
- Date defaults to today
- Amount field is focused on page load

### Out of scope
- Transfer/exchange types (TASK-022, TASK-023)
- Quick-entry bottom sheet (TASK-025)
- Smart defaults (TASK-026)

---

## TASK-016: Dashboard -- net worth and account balances

**Phase:** Phase 1
**Dependencies:** TASK-009, TASK-013
**Estimated effort:** 3h

### Description
Build the first real dashboard: net worth calculation and per-institution account balances display. This answers the core question "where is my money?" from the PRD vision.

### Scope
- [ ] `internal/service/dashboard.go` -- compute net worth (sum all positive balances - sum all liabilities), per-institution breakdown
- [ ] `internal/handler/dashboard.go` -- handler for `GET /`
- [ ] `internal/templates/pages/dashboard.html` -- replace placeholder with real dashboard
- [ ] Net worth display (EGP total)
- [ ] Per-institution expandable sections with account balances
- [ ] Color-coded by institution
- [ ] `internal/templates/partials/balance-summary.html` -- summary bar partial

### Files touched
- `internal/service/dashboard.go` (create)
- `internal/handler/dashboard.go` (create)
- `internal/templates/pages/dashboard.html` (create)
- `internal/templates/partials/balance-summary.html` (create)
- `cmd/server/main.go` (modify -- register dashboard handler)

### Acceptance criteria
- Dashboard shows correct net worth
- Institutions expandable to show individual accounts
- Balances formatted correctly with currency symbols
- Empty state handled (no accounts yet)

### Out of scope
- USD conversion on dashboard (TASK-035)
- Recent transactions feed (TASK-028)
- Summary cards for cash/credit/debt (TASK-036)

---

## TASK-017: Authentication -- PIN-based login

**Phase:** Phase 1
**Dependencies:** TASK-013, TASK-003
**Estimated effort:** 3h

### Description
Implement single-user PIN-based authentication per PRD section 9.1. A setup flow for first run, login screen, session management with HTTP-only cookies, and auth middleware protecting all routes.

### Scope
- [ ] Migration: create `user_config` table (id, pin_hash, created_at)
- [ ] `internal/service/auth.go` -- PIN hashing (bcrypt), verification, session creation
- [ ] `internal/middleware/auth.go` -- session cookie validation middleware
- [ ] `internal/handler/auth.go` -- login page, PIN submit, logout
- [ ] `internal/templates/pages/login.html` -- PIN entry screen
- [ ] `internal/templates/pages/setup.html` -- first-time PIN setup
- [ ] Session: HTTP-only secure cookie, 30-day expiry
- [ ] All routes except `/login`, `/setup`, `/healthz` require auth

### Files touched
- `internal/database/migrations/000008_create_user_config.up.sql` (create)
- `internal/database/migrations/000008_create_user_config.down.sql` (create)
- `internal/service/auth.go` (create)
- `internal/middleware/auth.go` (create)
- `internal/handler/auth.go` (create)
- `internal/templates/pages/login.html` (create)
- `internal/templates/pages/setup.html` (create)
- `cmd/server/main.go` (modify -- add auth middleware)

### Acceptance criteria
- First visit redirects to setup if no PIN exists
- After setup, redirects to login
- Valid PIN creates session, redirects to dashboard
- Invalid PIN shows error
- Unauthenticated requests to protected routes redirect to login
- PIN stored as bcrypt hash

### Out of scope
- Re-authentication for sensitive actions (future)
- Multi-user support (future)

---

## TASK-018: PWA manifest and basic service worker

**Phase:** Phase 1
**Dependencies:** TASK-013
**Estimated effort:** 2h

### Description
Add the PWA manifest and a basic service worker that caches the app shell. This enables "Add to Home Screen" and fast subsequent loads (P-1, P-3).

### Scope
- [ ] `static/manifest.json` -- app name, icons, theme color, display: standalone
- [ ] `static/icons/` -- app icons in required sizes (192x192, 512x512) -- simple placeholder icons
- [ ] `static/js/sw.js` -- service worker caching app shell (HTML layout, CSS, JS, icons)
- [ ] Register service worker in base layout
- [ ] Add manifest link and meta tags to base layout

### Files touched
- `static/manifest.json` (create)
- `static/icons/icon-192.png` (create)
- `static/icons/icon-512.png` (create)
- `static/js/sw.js` (create)
- `internal/templates/layouts/base.html` (modify -- add manifest link, SW registration)

### Acceptance criteria
- Chrome DevTools > Application shows valid manifest
- Service worker registers successfully
- App shell is cached (works on reload with network disabled for static assets)
- "Add to Home Screen" prompt available on mobile

### Out of scope
- Offline transaction queue (TASK-040)
- Push notifications (TASK-044)

---

## TASK-019: Seed data script for development

**Phase:** Phase 1
**Dependencies:** TASK-005, TASK-006
**Estimated effort:** 2h

### Description
Create a seed data script that populates the database with realistic test data matching the PRD's financial landscape -- HSBC, CIB, Telda, etc. with sample accounts and transactions. This accelerates development and testing.

### Scope
- [ ] `internal/database/seeds/seed.go` -- programmatic seed runner
- [ ] Seed institutions: HSBC, CIB, Banque Misr, EGBank, Telda, Fawry, TRU
- [ ] Seed accounts per institution matching PRD examples (HSBC USD Checking, HSBC EGP Checking, HSBC Credit Card, etc.)
- [ ] Seed ~50 sample transactions across various categories and accounts
- [ ] Makefile target: `seed`
- [ ] Idempotent: running twice doesn't duplicate

### Files touched
- `internal/database/seeds/seed.go` (create)
- `cmd/seed/main.go` (create)
- `Makefile` (modify -- add `seed` target)

### Acceptance criteria
- `make seed` populates the database
- Dashboard shows realistic data after seeding
- Running seed twice doesn't create duplicates
- All foreign key relationships are valid

### Out of scope
- Production data (never)
- Building fund / person data (seeded in their respective tasks)

---

## Phase 2 -- Transaction Excellence

---

## TASK-020: Transaction list page with filtering

**Phase:** Phase 2
**Dependencies:** TASK-012, TASK-013
**Estimated effort:** 3h

### Description
Build the full transaction list page with filtering by account, category, date range, and type. This is the `GET /transactions` page endpoint.

### Scope
- [ ] `internal/templates/pages/transactions.html` -- transaction list with filter bar
- [ ] `internal/templates/partials/transaction-list.html` -- transaction rows (HTMX swappable)
- [ ] `internal/templates/partials/transaction-row.html` -- single transaction row component
- [ ] Filter controls: account dropdown, category dropdown, date range, type tabs
- [ ] HTMX: filters trigger partial reload of transaction list
- [ ] Pagination (load more)
- [ ] Repository: add filter params to GetAll query

### Files touched
- `internal/templates/pages/transactions.html` (create)
- `internal/templates/partials/transaction-list.html` (create)
- `internal/templates/partials/transaction-row.html` (create)
- `internal/repository/transaction.go` (modify -- add filtering)
- `internal/handler/transaction.go` (modify -- render templates, handle filters)

### Acceptance criteria
- `GET /transactions` renders the list with all transactions
- Filtering by account returns only that account's transactions
- Filtering by date range works
- HTMX partial updates work without full page reload
- Empty state shown when no transactions match

### Out of scope
- Full-text search (Phase 4)
- CSV export (Phase 4)

---

## TASK-021: Transaction edit and delete

**Phase:** Phase 2
**Dependencies:** TASK-020
**Estimated effort:** 2h

### Description
Add edit and delete functionality to transactions from the list and detail views. Editing must recalculate balance changes, and deleting must reverse them.

### Scope
- [ ] `internal/templates/partials/transaction-edit-form.html` -- inline edit form
- [ ] Edit handler: recalculates balance diff (old amount vs new amount)
- [ ] Delete handler with confirmation dialog
- [ ] HTMX: inline edit swaps row to form, save swaps back to updated row
- [ ] HTMX: delete removes row with animation, updates balance

### Files touched
- `internal/templates/partials/transaction-edit-form.html` (create)
- `internal/handler/transaction.go` (modify -- add edit/delete template responses)
- `internal/service/transaction.go` (modify -- edit with balance recalculation)

### Acceptance criteria
- Can edit a transaction's amount, category, note, date
- Editing amount correctly adjusts account balance (delta)
- Deleting reverses the balance impact
- UI updates inline via HTMX

### Out of scope
- Editing transfer/exchange transactions (complex, later)
- Bulk delete

---

## TASK-022: Transfer between accounts

**Phase:** Phase 2
**Dependencies:** TASK-011
**Estimated effort:** 3h

### Description
Implement transfers between accounts (T-3). A transfer creates two linked transactions -- a debit from the source and a credit to the destination. Both accounts' balances update atomically.

### Scope
- [ ] Service: `CreateTransfer(sourceAccountID, destAccountID, amount, ...)` creates two linked transactions
- [ ] Linked via `linked_transaction_id` on both rows
- [ ] Source account debited, destination account credited
- [ ] Same-currency validation (cross-currency is exchange, not transfer)
- [ ] `internal/templates/partials/transfer-form.html` -- transfer entry UI
- [ ] Integration tests

### Files touched
- `internal/service/transaction.go` (modify -- add transfer logic)
- `internal/repository/transaction.go` (modify -- create linked pair)
- `internal/templates/partials/transfer-form.html` (create)
- `internal/handler/transaction.go` (modify -- transfer handler)
- `internal/service/transaction_test.go` (modify)

### Acceptance criteria
- Transfer creates two linked transactions
- Source balance decremented, destination balance incremented
- Both transactions reference each other via linked_transaction_id
- Deleting one leg deletes both and reverses both balances
- Cross-currency transfer rejected (must use exchange)

### Out of scope
- InstaPay fee calculation (TASK-029)
- Currency exchange (TASK-023)

---

## TASK-023: Currency exchange transaction

**Phase:** Phase 2
**Dependencies:** TASK-022
**Estimated effort:** 3h

### Description
Implement currency exchange transactions (T-4). User specifies source (USD), destination (EGP), and any two of: amount, rate, counter_amount -- the third is auto-calculated. Also logs the exchange rate.

### Scope
- [ ] Service: `CreateExchange(sourceAccountID, destAccountID, amount, rate, counterAmount)` with auto-calc logic
- [ ] Any two of three fields computes the third
- [ ] Creates linked transaction pair (USD debit + EGP credit)
- [ ] Logs rate to `exchange_rate_log` table
- [ ] `internal/templates/partials/exchange-form.html` -- exchange entry with auto-calc
- [ ] Minimal JS for auto-calculation in the form (compute third field on input)

### Files touched
- `internal/service/transaction.go` (modify -- add exchange logic)
- `internal/repository/exchange_rate.go` (create)
- `internal/templates/partials/exchange-form.html` (create)
- `internal/handler/transaction.go` (modify)
- `static/js/exchange.js` (create -- auto-calc logic)
- `internal/service/transaction_test.go` (modify)

### Acceptance criteria
- Exchange creates linked transactions in different currencies
- Entering amount + rate auto-calculates counter_amount
- Entering amount + counter_amount auto-calculates rate
- Exchange rate is logged
- Both accounts updated correctly

### Out of scope
- Exchange rate history page (Phase 4)
- Salary distribution wizard (TASK-033)

---

## TASK-024: Credit card transaction handling

**Phase:** Phase 2
**Dependencies:** TASK-011
**Estimated effort:** 2h

### Description
Handle credit card-specific logic (T-5, T-6). Credit card balances go negative (spending increases debt). Payments restore available credit. Track utilization against credit limit.

### Scope
- [ ] Service: credit card expense makes balance more negative
- [ ] Service: credit card payment (income type) makes balance less negative
- [ ] Validation: cannot exceed credit limit
- [ ] Available credit calculation: credit_limit + current_balance (balance is negative)
- [ ] Display available credit on account cards

### Files touched
- `internal/service/transaction.go` (modify -- credit card logic)
- `internal/service/account.go` (modify -- available credit calculation)
- `internal/templates/partials/account-card.html` (modify -- show available credit)
- `internal/service/transaction_test.go` (modify)

### Acceptance criteria
- Expense on credit card makes balance more negative
- Payment on credit card makes balance less negative (toward 0)
- Transaction rejected if it would exceed credit limit
- Available credit shown correctly on account card

### Out of scope
- Billing cycle tracking (TASK-037)
- Credit card utilization reports (Phase 4)

---

## TASK-025: Quick-entry bottom sheet UI

**Phase:** Phase 2
**Dependencies:** TASK-015
**Estimated effort:** 4h

### Description
Build the optimized quick-entry bottom sheet that slides up from the FAB button (section 8.2). This is the critical UX -- amount-first with numeric focus, account selector, category icon grid, and instant save.

### Scope
- [ ] `internal/templates/partials/quick-entry.html` -- bottom sheet template
- [ ] `static/js/quick-entry.js` -- sheet animation, touch gestures (swipe down to dismiss)
- [ ] Amount field: large, auto-focused, numeric inputmode
- [ ] Account selector: recent/favorite accounts with institution colors
- [ ] Category selector: icon grid of most-used categories
- [ ] Date (defaults today), optional note
- [ ] Save button: large, haptic feedback (Vibration API)
- [ ] HTMX: save posts to `/transactions/quick`, shows success toast
- [ ] Success animation with new balance display
- [ ] Transaction type tabs (expense/income/transfer) at top of sheet

### Files touched
- `internal/templates/partials/quick-entry.html` (create)
- `internal/templates/partials/success-toast.html` (create)
- `static/js/quick-entry.js` (create)
- `internal/handler/transaction.go` (modify -- quick entry endpoint)
- `internal/templates/components/bottom-nav.html` (modify -- wire FAB to sheet)

### Acceptance criteria
- FAB tap opens bottom sheet with smooth animation
- Amount field auto-focused with numeric keyboard on mobile
- Can complete expense entry in 3 taps: amount, account, category, save
- Success shows new balance and dismisses sheet
- Swipe down dismisses sheet
- Works well on 375px viewport

### Out of scope
- Smart defaults / last-used memory (TASK-026)
- Transfer/exchange in quick entry (use full form)

---

## TASK-026: Smart defaults and recent-used memory

**Phase:** Phase 2
**Dependencies:** TASK-025
**Estimated effort:** 2h

### Description
Implement smart defaults for transaction entry (T-8): pre-select last-used account, show recently-used categories first, and auto-default to the most frequent category if used 3+ times consecutively.

### Scope
- [ ] Repository: get last-used account, get recently-used categories (ordered by frequency)
- [ ] Service: determine smart defaults for the entry form
- [ ] Pre-select last-used account in quick entry
- [ ] Sort categories by recent usage frequency
- [ ] If same category used 3+ times in a row, auto-select it
- [ ] Store user preferences in a simple key-value config table or use existing transaction history

### Files touched
- `internal/repository/transaction.go` (modify -- add recent/frequency queries)
- `internal/service/transaction.go` (modify -- smart defaults logic)
- `internal/handler/transaction.go` (modify -- pass defaults to templates)
- `internal/templates/partials/quick-entry.html` (modify -- use defaults)

### Acceptance criteria
- Quick entry pre-selects the last-used account
- Categories sorted by recent usage
- After 3 consecutive uses of same category, it's auto-selected
- Defaults work correctly for new users (no history)

### Out of scope
- Machine learning / prediction
- Recurring transaction suggestions (Phase 4)

---

## TASK-027: Account detail page with transaction history

**Phase:** Phase 2
**Dependencies:** TASK-020, TASK-009
**Estimated effort:** 2h

### Description
Build the single account detail page (`GET /accounts/{id}`) showing account info, current balance, and transaction history filtered to that account.

### Scope
- [ ] `internal/templates/pages/account-detail.html` -- account header + transaction list
- [ ] Account info: name, institution, type, currency, balance, credit limit (if applicable)
- [ ] Reuse `transaction-list.html` partial filtered to this account
- [ ] Available credit display for credit cards
- [ ] Quick-entry pre-selects this account when opened from detail page

### Files touched
- `internal/templates/pages/account-detail.html` (create)
- `internal/handler/account.go` (modify -- detail page handler)

### Acceptance criteria
- `GET /accounts/{id}` renders account detail with transactions
- Only transactions for this account are shown
- Balance and account info displayed correctly
- Credit cards show available credit

### Out of scope
- Balance history chart (Phase 4)
- Edit/delete account from this page

---

## TASK-028: Dashboard -- recent transactions feed

**Phase:** Phase 2
**Dependencies:** TASK-016, TASK-012
**Estimated effort:** 2h

### Description
Add the recent transactions feed to the dashboard (D-5) -- last 10-15 transactions with HTMX refresh after any transaction change.

### Scope
- [ ] `internal/templates/partials/recent-transactions.html` -- transaction feed partial
- [ ] Dashboard handler fetches recent transactions
- [ ] Each row shows: category icon, description/note, amount (color-coded +/-), account name
- [ ] HTMX: `GET /partials/recent-transactions` endpoint for refresh
- [ ] After transaction entry, trigger dashboard feed refresh via HTMX OOB swap

### Files touched
- `internal/templates/partials/recent-transactions.html` (create)
- `internal/templates/pages/dashboard.html` (modify -- add feed section)
- `internal/handler/dashboard.go` (modify -- add recent transactions, partial endpoint)

### Acceptance criteria
- Dashboard shows last 15 transactions
- Transactions display amount, category, account, date
- Adding a transaction refreshes the feed via HTMX
- Empty state message when no transactions exist

### Out of scope
- Transaction duplication from feed (TASK-030)
- Infinite scroll

---

## TASK-029: InstaPay transfer with auto-calculated fee

**Phase:** Phase 2
**Dependencies:** TASK-022
**Estimated effort:** 2h

### Description
Implement InstaPay transfers (S-2) with automatic fee calculation: 0.1% of amount, minimum 0.5 EGP, maximum 20 EGP. The fee is recorded as a separate sub-entry on the source account.

### Scope
- [ ] Service: `CreateInstapayTransfer` -- calculates fee, creates transfer + fee transaction
- [ ] Fee formula: max(0.5, min(amount * 0.001, 20))
- [ ] Fee recorded as separate transaction (type: expense, category: Fees & Charges)
- [ ] UI: transfer form has "InstaPay" toggle, shows calculated fee
- [ ] Fee shown as sub-line in confirmation

### Files touched
- `internal/service/transaction.go` (modify -- InstaPay logic)
- `internal/templates/partials/transfer-form.html` (modify -- InstaPay toggle)
- `internal/service/transaction_test.go` (modify -- fee calculation tests)

### Acceptance criteria
- InstaPay transfer of 10,000 EGP charges 10 EGP fee
- InstaPay transfer of 100 EGP charges 0.5 EGP fee (minimum)
- InstaPay transfer of 50,000 EGP charges 20 EGP fee (maximum)
- Fee is a separate transaction linked to the transfer
- Fee deducted from source account

### Out of scope
- Fawry cash-out (TASK-034)

---

## TASK-030: Transaction duplication

**Phase:** Phase 2
**Dependencies:** TASK-020
**Estimated effort:** 1h

### Description
Allow users to duplicate a recent transaction and modify it (T-9). This speeds up entry for recurring-ish expenses that aren't automated.

### Scope
- [ ] "Duplicate" action on transaction rows
- [ ] Opens the entry form pre-filled with the duplicated transaction's data
- [ ] Date defaulted to today (not the original date)
- [ ] User can modify before saving

### Files touched
- `internal/handler/transaction.go` (modify -- duplicate endpoint)
- `internal/templates/partials/transaction-row.html` (modify -- add duplicate button)
- `internal/templates/pages/transaction-new.html` (modify -- accept pre-fill params)

### Acceptance criteria
- Clicking duplicate opens form pre-filled with original data
- Date is set to today, not original date
- Saving creates a new transaction (not editing the original)

### Out of scope
- Batch entry (P2 feature, TASK-043)

---

## Phase 3 -- Advanced Features

---

## TASK-031: People (persons) CRUD and lending/borrowing

**Phase:** Phase 3
**Dependencies:** TASK-011
**Estimated effort:** 3h

### Description
Implement the people ledger (S-4, S-5): CRUD for persons, recording loans (I lent X to Y / I borrowed from Y), and repayments. Updates the person's net_balance.

### Scope
- [ ] `internal/repository/person.go` -- CRUD, update net_balance
- [ ] `internal/service/person.go` -- loan and repayment logic
- [ ] `internal/handler/person.go` -- HTTP handlers
- [ ] Transaction types `loan_out` and `loan_in` create transactions linked to a person
- [ ] `loan_repayment` type adjusts the person's net_balance
- [ ] Positive net_balance = they owe me, negative = I owe them

### Files touched
- `internal/repository/person.go` (create)
- `internal/service/person.go` (create)
- `internal/handler/person.go` (create)
- `internal/service/transaction.go` (modify -- loan/repayment types)
- `cmd/server/main.go` (modify -- register routes)

### Acceptance criteria
- Can create a person
- Recording "I lent Ahmed 1000" creates a transaction and sets net_balance to 1000
- Recording partial repayment of 500 adjusts net_balance to 500
- Full repayment brings net_balance to 0
- Net balance correctly reflects all loans and repayments

### Out of scope
- People ledger UI page (TASK-032)
- Expected return date reminders

---

## TASK-032: People ledger UI page

**Phase:** Phase 3
**Dependencies:** TASK-031, TASK-013
**Estimated effort:** 2h

### Description
Build the People page (`GET /people`) showing the lending/borrowing ledger (D-6) with each person's net balance and transaction history.

### Scope
- [ ] `internal/templates/pages/people.html` -- people list with net balances
- [ ] `internal/templates/partials/person-card.html` -- person detail with loan history
- [ ] Add person form
- [ ] Record loan / repayment forms
- [ ] Color coding: green (they owe me), red (I owe them)
- [ ] HTMX: forms submit inline, update balances

### Files touched
- `internal/templates/pages/people.html` (create)
- `internal/templates/partials/person-card.html` (create)
- `internal/templates/partials/loan-form.html` (create)
- `internal/handler/person.go` (modify -- template rendering)

### Acceptance criteria
- `GET /people` renders the people ledger
- Each person shows net balance with color coding
- Can add a person, record loan, record repayment from this page
- Ledger updates via HTMX after recording

### Out of scope
- Dashboard people summary partial (TASK-036)

---

## TASK-033: Salary distribution wizard

**Phase:** Phase 3
**Dependencies:** TASK-023
**Estimated effort:** 4h

### Description
Build the multi-step salary distribution flow (S-3): confirm salary, enter exchange rate, allocate to categories, review, and confirm. Creates all transactions in one atomic batch.

### Scope
- [ ] `internal/service/salary.go` -- salary distribution logic, creates exchange + allocation transactions
- [ ] `internal/handler/salary.go` -- step-by-step wizard endpoints
- [ ] `internal/templates/partials/salary-step1.html` -- confirm salary amount (USD)
- [ ] `internal/templates/partials/salary-step2.html` -- exchange rate entry with auto-calc
- [ ] `internal/templates/partials/salary-step3.html` -- allocation table (pre-filled from last month)
- [ ] `internal/templates/partials/salary-step4.html` -- review and confirm
- [ ] HTMX: each step submits and loads next step partial
- [ ] Pre-fill allocations from last salary distribution
- [ ] "Discretionary" auto-calculated as remainder

### Files touched
- `internal/service/salary.go` (create)
- `internal/handler/salary.go` (create)
- `internal/templates/partials/salary-step1.html` (create)
- `internal/templates/partials/salary-step2.html` (create)
- `internal/templates/partials/salary-step3.html` (create)
- `internal/templates/partials/salary-step4.html` (create)
- `cmd/server/main.go` (modify -- register routes)

### Acceptance criteria
- Wizard progresses through 4 steps
- Exchange creates linked USD/EGP transactions
- Allocations create individual transactions to correct accounts
- Remainder auto-calculated for discretionary
- Last month's allocation pre-fills step 3
- All transactions created atomically (all or none)

### Out of scope
- Auto-triggering wizard on salary detection
- Custom allocation templates

---

## TASK-034: Fawry credit card cash-out flow

**Phase:** Phase 3
**Dependencies:** TASK-024
**Estimated effort:** 2h

### Description
Implement the Fawry cash-out pattern (S-1): charge to credit card, fee deducted, credit to Fawry prepaid account, with optional subsequent cash withdrawal.

### Scope
- [ ] Service: `CreateFawryCashout` -- creates credit card charge + fee + prepaid credit
- [ ] Fee configurable per cash-out
- [ ] Optional follow-up: cash withdrawal from prepaid
- [ ] `internal/templates/partials/fawry-cashout-form.html`

### Files touched
- `internal/service/transaction.go` (modify -- Fawry cashout)
- `internal/templates/partials/fawry-cashout-form.html` (create)
- `internal/handler/transaction.go` (modify)

### Acceptance criteria
- Cash-out creates credit card expense (amount + fee)
- Fawry prepaid account credited with the net amount
- Fee recorded separately
- Optional cash withdrawal decrements prepaid

### Out of scope
- Fawry-specific account auto-detection

---

## TASK-035: Dashboard -- currency conversion and exchange rate

**Phase:** Phase 3
**Dependencies:** TASK-016, TASK-023
**Estimated effort:** 2h

### Description
Add USD to EGP conversion on the dashboard (D-1, D-8). Uses the last recorded exchange rate (or a manually set preferred rate) to show unified net worth.

### Scope
- [ ] Service: fetch latest exchange rate from log
- [ ] Dashboard: net worth shows both EGP total and USD equivalent
- [ ] USD accounts converted to EGP using the rate
- [ ] Settings: set preferred exchange rate override
- [ ] `internal/templates/partials/exchange-rate-chip.html` -- current rate display

### Files touched
- `internal/service/dashboard.go` (modify -- add conversion)
- `internal/repository/exchange_rate.go` (modify -- get latest rate)
- `internal/templates/pages/dashboard.html` (modify)
- `internal/templates/partials/exchange-rate-chip.html` (create)
- `internal/handler/settings.go` (create -- rate preference)

### Acceptance criteria
- Net worth shows EGP total with USD amounts converted
- Uses latest exchange rate from log
- Can override with a preferred rate in settings
- Rate displayed on dashboard

### Out of scope
- Exchange rate history chart (Phase 4)
- External rate API

---

## TASK-036: Dashboard -- summary cards and building fund

**Phase:** Phase 3
**Dependencies:** TASK-016
**Estimated effort:** 3h

### Description
Add the summary cards row (D-2: liquid cash, credit used, credit available, total debt), people ledger summary (D-6), and building fund balance card (D-7) to the dashboard.

### Scope
- [ ] Service: calculate liquid cash, total credit used, total credit available, total debt
- [ ] `internal/templates/partials/summary-cards.html` -- the three summary cards
- [ ] `internal/templates/partials/people-summary.html` -- net lending/borrowing totals
- [ ] `internal/templates/partials/building-fund.html` -- building fund balance card
- [ ] Building fund: sum all transactions with `is_building_fund = true`
- [ ] HTMX partials: `GET /partials/people-summary`, `GET /partials/building-fund`

### Files touched
- `internal/service/dashboard.go` (modify)
- `internal/templates/partials/summary-cards.html` (create)
- `internal/templates/partials/people-summary.html` (create)
- `internal/templates/partials/building-fund.html` (create)
- `internal/templates/pages/dashboard.html` (modify)
- `internal/handler/dashboard.go` (modify)

### Acceptance criteria
- Summary cards show correct totals
- Building fund balance calculated from is_building_fund transactions
- Building fund visually separated from personal finances
- People summary shows net owed to/from
- All partials refresh via HTMX

### Out of scope
- Building fund CRUD (TASK-038)
- Monthly spending comparison (TASK-039)

---

## TASK-037: Credit card billing cycle tracking

**Phase:** Phase 3
**Dependencies:** TASK-024
**Estimated effort:** 2h

### Description
Track credit card billing cycles (A-6): statement date, due date, and compute current statement amount. Display on account detail and dashboard.

### Scope
- [ ] Account metadata JSONB: store statement_day, due_day for credit cards
- [ ] Service: calculate current billing period, amount due based on transactions within cycle
- [ ] Account detail: show billing cycle info, current amount due, due date
- [ ] Dashboard: upcoming due date warnings (within 7 days)

### Files touched
- `internal/service/account.go` (modify -- billing cycle calculation)
- `internal/templates/pages/account-detail.html` (modify)
- `internal/templates/partials/credit-card-info.html` (create)
- `internal/templates/pages/dashboard.html` (modify -- due date warning)

### Acceptance criteria
- Credit card shows current billing period
- Amount due calculated from transactions in current cycle
- Due date displayed
- Warning shown on dashboard when due date within 7 days

### Out of scope
- Credit card utilization reports (Phase 4)
- Minimum payment calculation

---

## TASK-038: Building fund sub-ledger

**Phase:** Phase 3
**Dependencies:** TASK-036
**Estimated effort:** 2h

### Description
Implement dedicated building fund entry flows (S-7): collections (income into the fund) and expenses (outflow from the fund). These use `is_building_fund = true` and always target the HSBC EGP Checking Account.

### Scope
- [ ] `internal/templates/partials/building-fund-form.html` -- collection/expense entry
- [ ] Handler: building fund collection and expense endpoints
- [ ] Transaction created with is_building_fund = true
- [ ] Building fund transaction list (filter by is_building_fund)
- [ ] `internal/templates/pages/building-fund.html` -- dedicated sub-ledger page

### Files touched
- `internal/templates/partials/building-fund-form.html` (create)
- `internal/templates/pages/building-fund.html` (create)
- `internal/handler/building_fund.go` (create)
- `cmd/server/main.go` (modify)

### Acceptance criteria
- Can record building fund collection (adds to fund balance)
- Can record building fund expense (deducts from fund balance)
- All building fund transactions tagged with is_building_fund
- Dedicated page lists all building fund transactions
- Dashboard building fund card reflects correct balance

### Out of scope
- Multi-building support
- Per-unit accounting

---

## TASK-039: Reports -- monthly spending breakdown

**Phase:** Phase 3
**Dependencies:** TASK-012, TASK-013
**Estimated effort:** 3h

### Description
Build the reports page with monthly spending breakdown by category (R-1) and income vs. expenses trend (R-2). These are the first data visualizations.

### Scope
- [ ] `internal/service/reports.go` -- aggregate spending by category for a month, income vs expense by month
- [ ] `internal/handler/reports.go` -- reports page handler
- [ ] `internal/templates/pages/reports.html` -- reports page with month selector
- [ ] Spending by category: horizontal bar chart (CSS-only or lightweight chart lib)
- [ ] Income vs expenses: monthly comparison (current vs previous)
- [ ] Month selector via HTMX

### Files touched
- `internal/service/reports.go` (create)
- `internal/handler/reports.go` (create)
- `internal/templates/pages/reports.html` (create)
- `internal/templates/partials/spending-by-category.html` (create)
- `internal/templates/partials/income-vs-expense.html` (create)
- `cmd/server/main.go` (modify)

### Acceptance criteria
- `GET /reports` renders the reports page
- Spending breakdown shows amounts per category for selected month
- Income vs expenses shows totals for current and previous months
- Month selector changes the displayed data via HTMX

### Out of scope
- Advanced charts library (keep it simple)
- Account balance history (Phase 4)
- Filtering by tags/accounts on reports (Phase 4)

---

## TASK-040: Offline transaction queue (IndexedDB + sync)

**Phase:** Phase 3
**Dependencies:** TASK-018, TASK-012
**Estimated effort:** 4h

### Description
Implement offline transaction entry (P-2): when offline, save transactions to IndexedDB, show optimistic UI, and sync when back online via the batch sync endpoint.

### Scope
- [ ] `static/js/offline.js` -- IndexedDB wrapper for transaction queue
- [ ] Service worker: intercept failed POST to `/transactions`, queue in IndexedDB
- [ ] Optimistic UI: show pending transactions with "syncing" indicator
- [ ] `POST /sync/transactions` -- batch sync endpoint that processes queued transactions
- [ ] On reconnect: auto-sync queued transactions, clear queue, refresh dashboard
- [ ] Conflict handling: basic last-write-wins

### Files touched
- `static/js/offline.js` (create)
- `static/js/sw.js` (modify -- offline interception)
- `internal/handler/sync.go` (create)
- `internal/service/sync.go` (create)
- `cmd/server/main.go` (modify)

### Acceptance criteria
- Transaction entry works with network disabled
- Queued transactions show with "pending" indicator
- On reconnect, transactions sync to server
- After sync, dashboard shows correct balances
- No duplicate transactions on sync

### Out of scope
- Full offline dashboard (read stale cache)
- Push notification on sync completion

---

## Phase 4 -- Polish & Delight

---

## TASK-041: Recurring transaction rules

**Phase:** Phase 4
**Dependencies:** TASK-012
**Estimated effort:** 3h

### Description
Implement recurring transaction rules (RC-1, RC-2): define rules for automatic or prompted transaction creation on a schedule.

### Scope
- [ ] Migration: create `recurring_rules` table per PRD data model
- [ ] `internal/repository/recurring.go` -- CRUD for rules
- [ ] `internal/service/recurring.go` -- check due rules, create transactions or reminders
- [ ] `internal/handler/recurring.go` -- manage rules UI
- [ ] `internal/templates/pages/recurring.html` -- rules management page
- [ ] `internal/templates/partials/recurring-form.html` -- create/edit rule form
- [ ] Background check on app start: process due recurring rules

### Files touched
- `internal/database/migrations/000009_create_recurring_rules.up.sql` (create)
- `internal/database/migrations/000009_create_recurring_rules.down.sql` (create)
- `internal/repository/recurring.go` (create)
- `internal/service/recurring.go` (create)
- `internal/handler/recurring.go` (create)
- `internal/templates/pages/recurring.html` (create)
- `internal/templates/partials/recurring-form.html` (create)
- `cmd/server/main.go` (modify)

### Acceptance criteria
- Can create a recurring rule (monthly, weekly)
- Due rules generate transactions (auto-confirm) or prompts (manual confirm)
- Upcoming recurring transactions shown on dashboard
- Can skip, confirm, or adjust a prompted recurring transaction

### Out of scope
- pg_cron for background scheduling (keep it app-level)
- Custom frequency beyond weekly/monthly

---

## TASK-042: Investment portfolio tracking

**Phase:** Phase 4
**Dependencies:** TASK-006
**Estimated effort:** 2h

### Description
Implement investment tracking (D-9): CRUD for investments, manual valuation updates, and display on dashboard.

### Scope
- [ ] Migration: create `investments` table per PRD
- [ ] `internal/repository/investment.go` -- CRUD, update valuation
- [ ] `internal/service/investment.go` -- compute portfolio value
- [ ] `internal/handler/investment.go` -- management page and update endpoints
- [ ] `internal/templates/pages/investments.html` -- investment list with valuations
- [ ] Dashboard: show total investment value (D-9)

### Files touched
- `internal/database/migrations/000010_create_investments.up.sql` (create)
- `internal/database/migrations/000010_create_investments.down.sql` (create)
- `internal/repository/investment.go` (create)
- `internal/service/investment.go` (create)
- `internal/handler/investment.go` (create)
- `internal/templates/pages/investments.html` (create)
- `internal/templates/pages/dashboard.html` (modify)
- `cmd/server/main.go` (modify)

### Acceptance criteria
- Can add an investment (platform, fund, units, unit price)
- Can update unit price (valuation)
- Total investment value shown on dashboard
- Last updated timestamp displayed

### Out of scope
- Automatic price fetching
- Investment return calculation / performance metrics

---

## TASK-043: Installment plan tracking and batch entry

**Phase:** Phase 4
**Dependencies:** TASK-024
**Estimated effort:** 2h

### Description
Implement installment plan (EPP) tracking (S-6) and batch transaction entry (T-10). Installment plans track TRU-style purchases with monthly payments.

### Scope
- [ ] Migration: create `installment_plans` table per PRD
- [ ] `internal/repository/installment.go` -- CRUD
- [ ] `internal/service/installment.go` -- record payment, decrement remaining
- [ ] `internal/templates/partials/installment-form.html` -- create/view plans
- [ ] Batch entry: `internal/templates/pages/batch-entry.html` -- multi-row form for catching up on missed days

### Files touched
- `internal/database/migrations/000011_create_installment_plans.up.sql` (create)
- `internal/database/migrations/000011_create_installment_plans.down.sql` (create)
- `internal/repository/installment.go` (create)
- `internal/service/installment.go` (create)
- `internal/templates/partials/installment-form.html` (create)
- `internal/templates/pages/batch-entry.html` (create)
- `internal/handler/installment.go` (create)
- `internal/handler/transaction.go` (modify -- batch endpoint)
- `cmd/server/main.go` (modify)

### Acceptance criteria
- Can create an installment plan with total, installments, monthly amount
- Recording a payment decrements remaining installments
- Plan shows completed/remaining installments
- Batch entry creates multiple transactions at once

### Out of scope
- Auto-generating installment reminders (use recurring rules)

---

## TASK-044: Push notifications

**Phase:** Phase 4
**Dependencies:** TASK-018, TASK-041
**Estimated effort:** 3h

### Description
Implement Web Push notifications (P-4) for credit card due date reminders and recurring transaction prompts.

### Scope
- [ ] `static/js/push.js` -- subscribe to push notifications, handle permission
- [ ] Service worker: handle push events, show notifications
- [ ] `internal/service/notifications.go` -- generate notification payloads
- [ ] `internal/handler/push.go` -- subscription management endpoint
- [ ] VAPID key generation and configuration
- [ ] Triggers: credit card due in 3 days, recurring transaction due

### Files touched
- `static/js/push.js` (create)
- `static/js/sw.js` (modify -- push event handling)
- `internal/service/notifications.go` (create)
- `internal/handler/push.go` (create)
- `internal/config/config.go` (modify -- VAPID keys)
- `cmd/server/main.go` (modify)

### Acceptance criteria
- User can enable push notifications
- Notification sent when credit card due date is 3 days away
- Notification sent for due recurring transactions
- Tapping notification opens the app to the relevant page

### Out of scope
- Email notifications
- SMS notifications

---

## TASK-045: CI pipeline and automated testing

**Phase:** Phase 4
**Dependencies:** TASK-007
**Estimated effort:** 2h

### Description
Set up a CI pipeline (GitHub Actions) that runs tests, linting, and builds the Docker image on every push.

### Scope
- [ ] `.github/workflows/ci.yml` -- CI pipeline
- [ ] Steps: checkout, setup Go, lint (golangci-lint), unit tests, integration tests (with PostgreSQL service), build Docker image
- [ ] PostgreSQL service container for integration tests
- [ ] Cache Go modules for speed
- [ ] Status badge in README

### Files touched
- `.github/workflows/ci.yml` (create)
- `README.md` (create -- minimal with build badge)
- `.golangci.yml` (create -- linter config)

### Acceptance criteria
- Push to main triggers CI
- CI runs linter, tests, and build
- Failing tests fail the build
- Pipeline completes in under 5 minutes

### Out of scope
- CD (auto-deploy) -- keep it `git pull && docker compose up`
- Code coverage thresholds

---

## TASK-046: Dark mode and visual polish

**Phase:** Phase 4
**Dependencies:** TASK-013
**Estimated effort:** 3h

### Description
Implement dark mode (section 8.3) and polish the visual design: color palette, typography, animations, and responsive refinements.

### Scope
- [ ] Tailwind dark mode configuration (class-based toggle)
- [ ] Dark mode color palette: dark backgrounds, teal/green for positive, amber for warnings, red for negative
- [ ] Toggle in settings and header
- [ ] Store preference in localStorage
- [ ] Polish: consistent spacing, font sizing, number formatting
- [ ] Animations: balance count-up, smooth transitions, sheet animations

### Files touched
- `static/css/app.css` (modify -- dark mode styles)
- `internal/templates/layouts/base.html` (modify -- dark mode class toggle)
- `internal/templates/components/header.html` (modify -- toggle button)
- `static/js/theme.js` (create -- dark mode toggle logic)

### Acceptance criteria
- Dark mode toggle works and persists across sessions
- All pages render correctly in both modes
- Colors match PRD spec (teal positive, amber warning, red negative)
- Animations are smooth on mobile

### Out of scope
- Per-page custom styling
- Custom fonts (use system font stack)

---

## TASK-047: Settings page and CSV export

**Phase:** Phase 4
**Dependencies:** TASK-013
**Estimated effort:** 2h

### Description
Build the settings page (`GET /settings`) with app configuration and CSV export (R-7) for transactions.

### Scope
- [ ] `internal/templates/pages/settings.html` -- settings page
- [ ] Settings: preferred exchange rate, dark mode, PIN change
- [ ] `internal/handler/settings.go` (modify -- full settings page)
- [ ] CSV export: `GET /export/transactions?from=&to=` returns CSV file
- [ ] `internal/service/export.go` -- generate CSV from transactions

### Files touched
- `internal/templates/pages/settings.html` (create)
- `internal/handler/settings.go` (modify)
- `internal/service/export.go` (create)
- `internal/handler/export.go` (create)
- `cmd/server/main.go` (modify)

### Acceptance criteria
- `GET /settings` renders settings page
- Can change PIN (requires current PIN)
- CSV export downloads valid CSV for date range
- CSV includes all transaction fields

### Out of scope
- PDF export
- Data import

---

## TASK-048: Exchange rate history and reports filtering

**Phase:** Phase 4
**Dependencies:** TASK-023, TASK-039
**Estimated effort:** 2h

### Description
Add exchange rate history page (R-6) and advanced filtering on reports (R-5): filter by account, category, tag, currency.

### Scope
- [ ] `internal/templates/pages/exchange-rates.html` -- rate history log
- [ ] Show rate per salary cycle
- [ ] Reports: add filter controls for account, category, currency
- [ ] HTMX: filter changes trigger report refresh

### Files touched
- `internal/templates/pages/exchange-rates.html` (create)
- `internal/handler/reports.go` (modify -- add exchange rate page, filtering)
- `internal/service/reports.go` (modify -- filter support)
- `internal/templates/pages/reports.html` (modify -- filter UI)

### Acceptance criteria
- Exchange rate history shows all logged rates
- Reports filterable by account, category, currency
- Filters apply via HTMX without page reload

### Out of scope
- External rate API integration
- Complex charting

---

## TASK-049: Dormant accounts and account reordering

**Phase:** Phase 4
**Dependencies:** TASK-009
**Estimated effort:** 2h

### Description
Implement dormant account handling (A-4) and account/institution reordering (A-8). Dormant accounts appear in totals but are collapsed/de-prioritized.

### Scope
- [ ] Toggle dormant status on accounts
- [ ] Dashboard: dormant accounts collapsed by default
- [ ] Drag-and-drop reordering for institutions and accounts (or simple up/down arrows)
- [ ] `display_order` field updates
- [ ] `static/js/reorder.js` -- drag-and-drop or arrow-based reordering

### Files touched
- `internal/handler/account.go` (modify -- dormant toggle, reorder)
- `internal/templates/pages/accounts.html` (modify -- dormant UI, reorder)
- `internal/templates/pages/dashboard.html` (modify -- collapse dormant)
- `static/js/reorder.js` (create)

### Acceptance criteria
- Can mark account as dormant
- Dormant accounts collapsed on dashboard
- Can reorder institutions and accounts
- Order persists across page loads

### Out of scope
- Hiding dormant accounts entirely

---

## TASK-050: Transaction search, tags, and habit streak

**Phase:** Phase 4
**Dependencies:** TASK-020
**Estimated effort:** 3h

### Description
Add transaction search (full-text on notes), freeform tags (C-4), and the habit encouragement streak UI (section 8.3).

### Scope
- [ ] Search: text search on transaction notes, filter by tags
- [ ] Tags: add freeform tags to transactions
- [ ] `internal/templates/partials/search-bar.html` -- search input with HTMX
- [ ] Tag input on transaction forms (comma-separated or chip input)
- [ ] Streak tracker: count consecutive days with at least one transaction
- [ ] `internal/templates/partials/streak-badge.html` -- streak display on dashboard
- [ ] Success messages: "Logged! 12 transactions this week" / "Streak: 15 days"

### Files touched
- `internal/repository/transaction.go` (modify -- search, tag filtering)
- `internal/service/streak.go` (create)
- `internal/templates/partials/search-bar.html` (create)
- `internal/templates/partials/streak-badge.html` (create)
- `internal/templates/pages/transactions.html` (modify -- search bar)
- `internal/templates/pages/dashboard.html` (modify -- streak)
- `internal/templates/partials/success-toast.html` (modify -- streak message)
- `internal/handler/dashboard.go` (modify)

### Acceptance criteria
- Can search transactions by note text
- Can add and filter by tags
- Streak shows consecutive days of logging
- Success toast includes transaction count / streak info

### Out of scope
- Machine learning suggestions
- Complex analytics

---

## TASK-051: Balance reconciliation job

**Phase:** Phase 4
**Dependencies:** TASK-011
**Estimated effort:** 2h

### Description
Implement the nightly balance reconciliation (section 5.3): recompute all account balances from transaction history, compare to cached values, and flag discrepancies.

### Scope
- [ ] `internal/jobs/reconcile.go` -- reconciliation logic
- [ ] Compute: `initial_balance + SUM(credits) - SUM(debits)` per account
- [ ] Compare to `current_balance`, log discrepancies
- [ ] Auto-fix option: update cached balance to match computed
- [ ] Trigger: can be run manually via `make reconcile` or on app startup

### Files touched
- `internal/jobs/reconcile.go` (create)
- `cmd/reconcile/main.go` (create)
- `Makefile` (modify)

### Acceptance criteria
- Reconciliation detects intentionally introduced discrepancies
- Discrepancies logged with account ID, cached value, computed value
- Auto-fix corrects cached balances
- No false positives on a clean database

### Out of scope
- pg_cron scheduling (run manually or via host cron)
- Alerting on discrepancies

---

## TASK-052: Performance optimization and materialized views

**Phase:** Phase 4
**Dependencies:** TASK-016, TASK-039
**Estimated effort:** 2h

### Description
Optimize dashboard and report queries with PostgreSQL materialized views and query tuning. Ensure dashboard loads in under 2 seconds.

### Scope
- [ ] Migration: create materialized views for dashboard aggregations (net worth, category totals, monthly summaries)
- [ ] Refresh materialized views after transaction changes (or on interval)
- [ ] Add database indexes identified from query analysis
- [ ] Dashboard handler uses materialized views
- [ ] Benchmark: measure dashboard load time

### Files touched
- `internal/database/migrations/000012_create_materialized_views.up.sql` (create)
- `internal/database/migrations/000012_create_materialized_views.down.sql` (create)
- `internal/repository/dashboard.go` (create -- read from materialized views)
- `internal/service/dashboard.go` (modify -- use optimized queries)

### Acceptance criteria
- Dashboard loads in under 2 seconds with 1000+ transactions
- Materialized views refresh correctly after transactions
- No stale data visible to user after transaction entry

### Out of scope
- Application-level caching (Go in-memory cache)
- CDN setup

---

*Total: 52 tasks across 4 phases*

| Phase | Tasks | Range |
|-------|-------|-------|
| Phase 1 -- Foundation | 19 | TASK-001 to TASK-019 |
| Phase 2 -- Transaction Excellence | 11 | TASK-020 to TASK-030 |
| Phase 3 -- Advanced Features | 10 | TASK-031 to TASK-040 |
| Phase 4 -- Polish & Delight | 12 | TASK-041 to TASK-052 |
