// Package seeds populates the database with realistic development data.
//
// Laravel equivalent: database/seeders/DatabaseSeeder.php — run with `php artisan db:seed`.
// Django equivalent:  fixtures (loaddata) or custom management commands with call_command().
//
// This seeder creates sample institutions (banks), accounts, and transactions
// so you have a working app with realistic data for development and demos.
//
// Idempotency:
//   Running seeds multiple times is safe — each seed function checks for existing
//   data before inserting. This uses SELECT EXISTS(...) checks rather than
//   INSERT ... ON CONFLICT DO NOTHING (which would also work but is less explicit).
//
//   Laravel equivalent: using firstOrCreate() or updateOrCreate() in seeders.
//   Django equivalent:  get_or_create() in data migrations or fixtures.
//
// See: https://pkg.go.dev/database/sql — the standard library database package
// See: https://pkg.go.dev/log/slog — Go's structured logging package (like Monolog in Laravel)
package seeds

import (
	"context"
	"database/sql"
	"fmt"
	"log/slog"
	"time"
)

// Run populates the database with sample institutions, accounts, and transactions.
//
// This is the main entry point — it seeds data in dependency order:
//   1. Institutions first (banks/fintechs — no FK dependencies)
//   2. Accounts second (depends on institutions via institution_id FK)
//   3. Transactions last (depends on accounts via account_id FK)
//
// Laravel equivalent: DatabaseSeeder::run() calling individual seeders in order.
// Django equivalent:  a management command that calls helper functions in sequence.
//
// Go concept — context.Background():
//   Creates a top-level context with no deadline or cancellation. Used when there's
//   no incoming request context to inherit from (seeding runs at startup, not in
//   response to an HTTP request).
//   See: https://pkg.go.dev/context#Background
//
// Go concept — slog.Info():
//   Go 1.21+ structured logging. slog produces structured log output (JSON or text)
//   with key-value pairs. Much better than fmt.Println for production logging.
//   Laravel equivalent: Log::info() facade (backed by Monolog).
//   Django equivalent:  logging.getLogger().info().
//   See: https://pkg.go.dev/log/slog
func Run(db *sql.DB) error {
	ctx := context.Background()

	slog.Info("seeding institutions...")
	if err := seedInstitutions(ctx, db); err != nil {
		return fmt.Errorf("seeding institutions: %w", err)
	}

	slog.Info("seeding accounts...")
	if err := seedAccounts(ctx, db); err != nil {
		return fmt.Errorf("seeding accounts: %w", err)
	}

	slog.Info("seeding transactions...")
	if err := seedTransactions(ctx, db); err != nil {
		return fmt.Errorf("seeding transactions: %w", err)
	}

	slog.Info("seed complete")
	return nil
}

// institution holds seed data for an institution (bank or fintech).
//
// Go concept — unexported (lowercase) struct:
//   This struct starts with a lowercase letter, so it's only visible within
//   this package. It's a data-transfer struct for seed data — no need to export it.
//   Laravel equivalent: a private array or collection in a seeder.
//   Django equivalent:  a local variable in a fixture or management command.
//
// Go concept — struct literal initialization:
//   Go structs can be initialized positionally: {"HSBC", "bank", "#db0011", "hsbc", 1}
//   or with named fields: institution{Name: "HSBC", Type: "bank", ...}.
//   Positional is shorter but fragile — adding a field breaks all existing literals.
type institution struct {
	Name  string
	Type  string
	Color string
	Icon  string
	Order int
}

// seedInstitutions inserts sample banks and fintechs (idempotent).
//
// Go concept — range over slice:
//   for _, inst := range institutions { ... } is Go's foreach loop.
//   The _ discards the index (we don't need it). inst is a copy of each element.
//   Laravel equivalent: foreach ($institutions as $inst) { ... }
//   Django equivalent:  for inst in institutions:
//
// SQL concept — parameterized queries ($1, $2, ...):
//   PostgreSQL uses numbered placeholders $1, $2, etc. for parameterized queries.
//   This prevents SQL injection — the driver handles escaping automatically.
//   Laravel equivalent: DB::insert('INSERT INTO ... VALUES (?, ?)', [$name, $type])
//   Django equivalent:  cursor.execute('INSERT INTO ... VALUES (%s, %s)', [name, type])
//   MySQL uses ? placeholders; PostgreSQL uses $1, $2, etc.
func seedInstitutions(ctx context.Context, db *sql.DB) error {
	institutions := []institution{
		{"HSBC", "bank", "#db0011", "hsbc", 1},
		{"CIB", "bank", "#003087", "cib", 2},
		{"Banque Misr", "bank", "#1a4d2e", "bm", 3},
		{"EGBank", "bank", "#0066b2", "egbank", 4},
		{"Telda", "fintech", "#7c3aed", "telda", 5},
		{"Fawry", "fintech", "#f59e0b", "fawry", 6},
		{"TRU", "fintech", "#06b6d4", "tru", 7},
		{"Cash", "wallet", "#78716c", "", 8},
	}

	for _, inst := range institutions {
		// Idempotency check: skip if this institution already exists.
		// Laravel equivalent: Institution::where('name', $name)->exists()
		// Django equivalent:  Institution.objects.filter(name=name).exists()
		var exists bool
		if err := db.QueryRowContext(ctx, "SELECT EXISTS(SELECT 1 FROM institutions WHERE name = $1)", inst.Name).Scan(&exists); err != nil {
			return fmt.Errorf("checking institution %s: %w", inst.Name, err)
		}
		if exists {
			continue
		}
		_, err := db.ExecContext(ctx, `
			INSERT INTO institutions (name, type, color, icon, display_order)
			VALUES ($1, $2, $3, $4, $5)
		`, inst.Name, inst.Type, inst.Color, inst.Icon, inst.Order)
		if err != nil {
			return fmt.Errorf("inserting %s: %w", inst.Name, err)
		}
	}
	return nil
}

// account holds seed data for an account.
type account struct {
	InstitutionName string
	Name            string
	Type            string
	Currency        string
	InitialBalance  float64
	CreditLimit     float64
	Order           int
}

// seedAccounts inserts sample accounts linked to institutions (idempotent).
//
// Notice the pattern of looking up the parent ID by name first, then inserting
// the child record. This is necessary because UUIDs are generated by PostgreSQL
// (via gen_random_uuid()), so we can't hardcode IDs in seed data.
//
// Laravel equivalent: using firstOrCreate() with a parent lookup:
//   $inst = Institution::where('name', 'HSBC')->first();
//   Account::firstOrCreate(['name' => 'HSBC Checking', 'institution_id' => $inst->id], [...]);
//
// Django equivalent:
//   inst = Institution.objects.get(name='HSBC')
//   Account.objects.get_or_create(name='HSBC Checking', institution=inst, defaults={...})
func seedAccounts(ctx context.Context, db *sql.DB) error {
	accounts := []account{
		// HSBC
		{"HSBC", "HSBC USD Checking", "current", "USD", 5000, 0, 1},
		{"HSBC", "HSBC EGP Checking", "current", "EGP", 150000, 0, 2},
		{"HSBC", "HSBC Credit Card", "credit_card", "EGP", 0, 500000, 3},
		// CIB
		{"CIB", "CIB Primary Savings", "savings", "EGP", 200000, 0, 1},
		{"CIB", "CIB Insurance Savings", "savings", "EGP", 50000, 0, 2},
		// Banque Misr
		{"Banque Misr", "BM Insurance Savings", "savings", "EGP", 30000, 0, 1},
		// EGBank
		{"EGBank", "EGBank Checking", "current", "EGP", 25000, 0, 1},
		// Telda
		{"Telda", "Telda Prepaid", "prepaid", "EGP", 5000, 0, 1},
		// Fawry
		{"Fawry", "Fawry Prepaid", "prepaid", "EGP", 2000, 0, 1},
		// TRU
		{"TRU", "TRU Credit", "credit_limit", "EGP", 0, 100000, 1},
		// Cash
		{"Cash", "EGP Cash", "cash", "EGP", 3500, 0, 1},
		{"Cash", "USD Cash", "cash", "USD", 200, 0, 2},
	}

	for _, acc := range accounts {
		// Look up institution ID by name — we can't hardcode UUIDs because
		// PostgreSQL generates them at insert time (gen_random_uuid()).
		var instID string
		err := db.QueryRowContext(ctx,
			"SELECT id FROM institutions WHERE name = $1", acc.InstitutionName,
		).Scan(&instID)
		if err != nil {
			return fmt.Errorf("finding institution %s: %w", acc.InstitutionName, err)
		}

		// Idempotency check: skip if this account already exists for this institution.
		var exists bool
		if err := db.QueryRowContext(ctx, "SELECT EXISTS(SELECT 1 FROM accounts WHERE name = $1 AND institution_id = $2)", acc.Name, instID).Scan(&exists); err != nil {
			return fmt.Errorf("checking account %s: %w", acc.Name, err)
		}
		if exists {
			continue
		}

		// Note: $5 appears twice in VALUES — initial_balance sets both
		// initial_balance and current_balance to the same starting value.
		_, err = db.ExecContext(ctx, `
			INSERT INTO accounts (institution_id, name, type, currency, initial_balance, current_balance, credit_limit, display_order)
			VALUES ($1, $2, $3, $4, $5, $5, $6, $7)
		`, instID, acc.Name, acc.Type, acc.Currency, acc.InitialBalance, acc.CreditLimit, acc.Order)
		if err != nil {
			return fmt.Errorf("inserting account %s: %w", acc.Name, err)
		}
	}
	return nil
}

// transaction holds seed data for a transaction.
type transaction struct {
	AccountName string
	Type        string
	Amount      float64
	Currency    string
	Category    string // category name to look up
	Note        string
	DaysAgo     int // how many days ago this transaction happened
}

// seedTransactions inserts sample transactions and updates account balances.
//
// This function demonstrates several important Go and SQL concepts:
//
// 1. Idempotency via count check:
//    Instead of checking each transaction individually, it skips the entire
//    batch if any transactions exist. This is a simpler "all or nothing" approach.
//
// 2. Database transactions (db.BeginTx):
//    Each transaction insert + balance update is wrapped in a DB transaction to
//    ensure atomicity — either both succeed or both are rolled back.
//
// 3. Graceful degradation:
//    If a category isn't found, it logs a warning and skips that transaction
//    instead of failing the entire seed. This makes seeds resilient to
//    partial migration states.
//
// SQL concept — database transactions (BEGIN/COMMIT/ROLLBACK):
//   A database transaction groups multiple SQL statements into an atomic unit.
//   Either ALL statements succeed (COMMIT) or ALL are undone (ROLLBACK).
//   This prevents data inconsistency — e.g., inserting a transaction but failing
//   to update the account balance would leave the data in an inconsistent state.
//
//   Laravel equivalent: DB::transaction(function () { ... })
//   Django equivalent:  with transaction.atomic(): ...
//
// Go concept — db.BeginTx():
//   Creates a database transaction. Returns a *sql.Tx that you use for all
//   queries within the transaction. You must call either Commit() or Rollback().
//   If you forget, the transaction is rolled back when the *sql.Tx is garbage collected,
//   but relying on GC for rollback is bad practice — always handle it explicitly.
//   See: https://pkg.go.dev/database/sql#DB.BeginTx
//   See: https://go.dev/doc/database/execute-transactions — official guide
func seedTransactions(ctx context.Context, db *sql.DB) error {
	// Idempotency: skip entirely if any transactions already exist.
	// This is a coarse-grained check — assumes seeds run as a batch.
	var count int
	if err := db.QueryRowContext(ctx, "SELECT COUNT(*) FROM transactions").Scan(&count); err != nil {
		return fmt.Errorf("counting transactions: %w", err)
	}
	if count > 0 {
		slog.Info("skipping transactions seed", "existing_count", count)
		return nil
	}

	// Category names must match the seeded categories in migration 000007.
	// Expense: Household, Food & Groceries, Transport, Health, Education, Mobile,
	//          Electricity, Gas, Internet, Gifts, Entertainment, Shopping,
	//          Subscriptions, Virtual Account, Insurance, Fees & Charges, Debt Payment, Other
	// Income:  Salary, Freelance, Investment Returns, Refund,
	//          Virtual Account, Loan Repayment Received, Other
	txns := []transaction{
		// Food & Groceries
		{"HSBC EGP Checking", "expense", 850, "EGP", "Food & Groceries", "Seoudi Market", 1},
		{"HSBC EGP Checking", "expense", 1200, "EGP", "Food & Groceries", "Carrefour weekly", 4},
		{"HSBC EGP Checking", "expense", 350, "EGP", "Food & Groceries", "Metro Market", 8},
		{"HSBC EGP Checking", "expense", 600, "EGP", "Food & Groceries", "Lucille's brunch", 2},
		{"HSBC EGP Checking", "expense", 450, "EGP", "Food & Groceries", "McDonald's delivery", 6},
		{"Telda Prepaid", "expense", 280, "EGP", "Food & Groceries", "Costa Coffee", 3},

		// Transport
		{"HSBC EGP Checking", "expense", 150, "EGP", "Transport", "Uber ride", 1},
		{"HSBC EGP Checking", "expense", 200, "EGP", "Transport", "Uber ride", 3},
		{"HSBC EGP Checking", "expense", 120, "EGP", "Transport", "Uber ride", 5},
		{"Telda Prepaid", "expense", 100, "EGP", "Transport", "InDrive", 7},

		// Bills & Utilities
		{"HSBC EGP Checking", "expense", 950, "EGP", "Electricity", "Electricity bill", 10},
		{"HSBC EGP Checking", "expense", 350, "EGP", "Household", "Water bill", 10},
		{"HSBC EGP Checking", "expense", 500, "EGP", "Mobile", "Vodafone monthly", 12},
		{"HSBC EGP Checking", "expense", 1200, "EGP", "Internet", "WE internet", 12},

		// Health
		{"HSBC Credit Card", "expense", 2500, "EGP", "Health", "Dr. visit + medicine", 5},
		{"HSBC Credit Card", "expense", 800, "EGP", "Health", "Pharmacy", 9},

		// Shopping & Entertainment
		{"HSBC Credit Card", "expense", 3500, "EGP", "Shopping", "Amazon order", 3},
		{"HSBC Credit Card", "expense", 1500, "EGP", "Shopping", "Noon order", 7},
		{"HSBC Credit Card", "expense", 600, "EGP", "Subscriptions", "Netflix + Spotify", 15},
		{"Telda Prepaid", "expense", 350, "EGP", "Subscriptions", "Shahid subscription", 14},

		// Education
		{"HSBC EGP Checking", "expense", 5000, "EGP", "Education", "Udemy courses", 20},

		// Household (rent)
		{"HSBC EGP Checking", "expense", 15000, "EGP", "Household", "Rent", 1},

		// Insurance
		{"CIB Insurance Savings", "expense", 3000, "EGP", "Insurance", "Monthly insurance premium", 5},

		// Income
		{"HSBC EGP Checking", "income", 45000, "EGP", "Salary", "Monthly salary", 1},
		{"HSBC USD Checking", "income", 2000, "USD", "Freelance", "Freelance payment", 5},
		{"CIB Primary Savings", "income", 1500, "EGP", "Investment Returns", "Savings interest", 15},

		// Savings transfers (modeled as income to savings accounts)
		{"CIB Primary Savings", "income", 10000, "EGP", "Salary", "Monthly savings transfer", 2},
		{"BM Insurance Savings", "income", 5000, "EGP", "Salary", "BM monthly savings", 2},

		// Small Fawry transactions
		{"Fawry Prepaid", "expense", 500, "EGP", "Electricity", "Electric meter recharge", 8},
		{"Fawry Prepaid", "expense", 200, "EGP", "Gas", "Gas recharge", 11},

		// More variety
		{"EGBank Checking", "expense", 1800, "EGP", "Food & Groceries", "Hyper One", 6},
		{"EGBank Checking", "expense", 300, "EGP", "Transport", "Parking fees", 4},
		{"EGBank Checking", "income", 8000, "EGP", "Salary", "Side income", 10},

		// TRU credit usage
		{"TRU Credit", "expense", 12000, "EGP", "Shopping", "Electronics purchase", 3},
		{"TRU Credit", "expense", 5000, "EGP", "Shopping", "Furniture", 10},

		// Recent small transactions
		{"HSBC EGP Checking", "expense", 75, "EGP", "Food & Groceries", "Street food", 0},
		{"HSBC EGP Checking", "expense", 180, "EGP", "Food & Groceries", "Corner store", 0},
		{"Telda Prepaid", "expense", 120, "EGP", "Entertainment", "Mobile game", 1},

		// More credit card
		{"HSBC Credit Card", "expense", 4200, "EGP", "Entertainment", "Hotel booking", 18},
		{"HSBC Credit Card", "expense", 1800, "EGP", "Entertainment", "Flight tickets", 20},

		// Extra income
		{"HSBC EGP Checking", "income", 45000, "EGP", "Salary", "Monthly salary", 30},
		{"HSBC USD Checking", "income", 1500, "USD", "Freelance", "Client payment", 25},
	}

	for _, tx := range txns {
		// Look up account ID by name (same pattern as seedAccounts).
		var accID string
		err := db.QueryRowContext(ctx,
			"SELECT id FROM accounts WHERE name = $1", tx.AccountName,
		).Scan(&accID)
		if err != nil {
			return fmt.Errorf("finding account %s: %w", tx.AccountName, err)
		}

		// Look up category ID by name AND type.
		// Falls back to name-only lookup if the category doesn't have a matching type.
		// This two-step lookup handles edge cases where a category name exists
		// but might be registered under a different type.
		var catID string
		err = db.QueryRowContext(ctx,
			"SELECT id FROM categories WHERE name = $1 AND type = $2 LIMIT 1",
			tx.Category, tx.Type,
		).Scan(&catID)
		if err != nil {
			// Fallback: try without type filter (some categories may be expense-only)
			err = db.QueryRowContext(ctx,
				"SELECT id FROM categories WHERE name = $1 LIMIT 1", tx.Category,
			).Scan(&catID)
			if err != nil {
				// Graceful degradation: log and skip rather than failing the entire seed.
				// slog.Warn with key-value pairs produces structured log output like:
				//   WARN category not found, skipping transaction category=Entertainment note="Mobile game"
				slog.Warn("category not found, skipping transaction", "category", tx.Category, "note", tx.Note)
				continue
			}
		}

		// time.Now().AddDate(0, 0, -tx.DaysAgo) subtracts DaysAgo days from today.
		// AddDate(years, months, days) is Go's date arithmetic.
		// NOTE: In service/handler code, always use timeutil.Now() instead (respects
		// the user's timezone). Here in seed.go, time.Now() is fine because seeds
		// populate sample data, not real user transactions.
		// Laravel equivalent: Carbon::now()->subDays($daysAgo)
		// Django equivalent:  timezone.now() - timedelta(days=days_ago)
		txDate := time.Now().AddDate(0, 0, -tx.DaysAgo)

		// Calculate balance delta: expenses decrease the balance (negative),
		// income increases it (positive). This delta is applied to current_balance.
		delta := -tx.Amount
		if tx.Type == "income" {
			delta = tx.Amount
		}

		// Database transaction: wrap the INSERT + UPDATE in a transaction
		// to ensure atomicity. If the balance update fails, the transaction
		// insert is rolled back too — no orphaned transactions without
		// corresponding balance changes.
		//
		// Go concept — BeginTx returns *sql.Tx (database transaction handle):
		//   dbTx is the database transaction handle (different from tx, which is the
		//   seed data struct from the loop above). We use dbTx (not db) for all
		//   queries that should be part of this atomic operation. The nil second
		//   argument uses the default transaction isolation level (READ COMMITTED
		//   in PostgreSQL).
		//
		// Go concept — explicit Rollback:
		//   Unlike Laravel's DB::transaction() which auto-rollbacks on exception,
		//   Go requires explicit Rollback() calls on error. If we don't rollback,
		//   the transaction stays open until garbage collection (bad practice).
		dbTx, err := db.BeginTx(ctx, nil)
		if err != nil {
			return err
		}

		_, err = dbTx.ExecContext(ctx, `
			INSERT INTO transactions (account_id, category_id, type, amount, currency, note, date)
			VALUES ($1, $2, $3, $4, $5, $6, $7)
		`, accID, catID, tx.Type, tx.Amount, tx.Currency, tx.Note, txDate)
		if err != nil {
			dbTx.Rollback()
			return fmt.Errorf("inserting transaction %q: %w", tx.Note, err)
		}

		// Update the account's current_balance atomically within the same
		// DB transaction. The += pattern (current_balance + $1) is safe for
		// concurrent access because PostgreSQL locks the row during UPDATE.
		_, err = dbTx.ExecContext(ctx, `
			UPDATE accounts SET current_balance = current_balance + $1, updated_at = NOW()
			WHERE id = $2
		`, delta, accID)
		if err != nil {
			dbTx.Rollback()
			return fmt.Errorf("updating balance for %q: %w", tx.Note, err)
		}

		// Commit makes all changes in this transaction permanent.
		// If Commit fails (rare — usually network issues), the changes are
		// automatically rolled back by PostgreSQL.
		if err := dbTx.Commit(); err != nil {
			return err
		}
	}

	return nil
}
