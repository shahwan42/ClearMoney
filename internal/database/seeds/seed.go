// Package seeds populates the database with realistic development data.
// Like Laravel's DatabaseSeeder or Django's loaddata/fixtures — gives you
// a working app with sample data for development and testing.
//
// Idempotent: uses INSERT ... ON CONFLICT DO NOTHING so running twice is safe.
package seeds

import (
	"context"
	"database/sql"
	"fmt"
	"log/slog"
	"time"
)

// Run populates the database with sample institutions, accounts, and transactions.
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

// institution holds seed data for an institution.
type institution struct {
	Name  string
	Type  string
	Color string
	Icon  string
	Order int
}

func seedInstitutions(ctx context.Context, db *sql.DB) error {
	institutions := []institution{
		{"HSBC", "bank", "#db0011", "hsbc", 1},
		{"CIB", "bank", "#003087", "cib", 2},
		{"Banque Misr", "bank", "#1a4d2e", "bm", 3},
		{"EGBank", "bank", "#0066b2", "egbank", 4},
		{"Telda", "fintech", "#7c3aed", "telda", 5},
		{"Fawry", "fintech", "#f59e0b", "fawry", 6},
		{"TRU", "fintech", "#06b6d4", "tru", 7},
	}

	for _, inst := range institutions {
		// Skip if already exists (idempotent)
		var exists bool
		db.QueryRowContext(ctx, "SELECT EXISTS(SELECT 1 FROM institutions WHERE name = $1)", inst.Name).Scan(&exists)
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

func seedAccounts(ctx context.Context, db *sql.DB) error {
	accounts := []account{
		// HSBC
		{"HSBC", "HSBC USD Checking", "checking", "USD", 5000, 0, 1},
		{"HSBC", "HSBC EGP Checking", "checking", "EGP", 150000, 0, 2},
		{"HSBC", "HSBC Credit Card", "credit_card", "EGP", 0, 500000, 3},
		// CIB
		{"CIB", "CIB Primary Savings", "savings", "EGP", 200000, 0, 1},
		{"CIB", "CIB Insurance Savings", "savings", "EGP", 50000, 0, 2},
		// Banque Misr
		{"Banque Misr", "BM Insurance Savings", "savings", "EGP", 30000, 0, 1},
		// EGBank
		{"EGBank", "EGBank Checking", "checking", "EGP", 25000, 0, 1},
		// Telda
		{"Telda", "Telda Prepaid", "prepaid", "EGP", 5000, 0, 1},
		// Fawry
		{"Fawry", "Fawry Prepaid", "prepaid", "EGP", 2000, 0, 1},
		// TRU
		{"TRU", "TRU Credit", "credit_limit", "EGP", 0, 100000, 1},
	}

	for _, acc := range accounts {
		// Look up institution ID by name
		var instID string
		err := db.QueryRowContext(ctx,
			"SELECT id FROM institutions WHERE name = $1", acc.InstitutionName,
		).Scan(&instID)
		if err != nil {
			return fmt.Errorf("finding institution %s: %w", acc.InstitutionName, err)
		}

		// Skip if already exists (idempotent)
		var exists bool
		db.QueryRowContext(ctx, "SELECT EXISTS(SELECT 1 FROM accounts WHERE name = $1 AND institution_id = $2)", acc.Name, instID).Scan(&exists)
		if exists {
			continue
		}

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

func seedTransactions(ctx context.Context, db *sql.DB) error {
	// Skip if transactions already exist (idempotent)
	var count int
	db.QueryRowContext(ctx, "SELECT COUNT(*) FROM transactions").Scan(&count)
	if count > 0 {
		slog.Info("skipping transactions seed", "existing_count", count)
		return nil
	}

	// Category names must match the seeded categories in migration 000007.
	// Expense: Household, Food & Groceries, Transport, Health, Education, Mobile,
	//          Electricity, Gas, Internet, Gifts, Entertainment, Shopping,
	//          Subscriptions, Building Fund, Insurance, Fees & Charges, Debt Payment, Other
	// Income:  Salary, Freelance, Investment Returns, Refund,
	//          Building Fund Collection, Loan Repayment Received, Other
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
		// Look up account ID
		var accID string
		err := db.QueryRowContext(ctx,
			"SELECT id FROM accounts WHERE name = $1", tx.AccountName,
		).Scan(&accID)
		if err != nil {
			return fmt.Errorf("finding account %s: %w", tx.AccountName, err)
		}

		// Look up category ID by name
		var catID string
		err = db.QueryRowContext(ctx,
			"SELECT id FROM categories WHERE name = $1 AND type = $2 LIMIT 1",
			tx.Category, tx.Type,
		).Scan(&catID)
		if err != nil {
			// Try without type filter (some categories may be expense-only)
			err = db.QueryRowContext(ctx,
				"SELECT id FROM categories WHERE name = $1 LIMIT 1", tx.Category,
			).Scan(&catID)
			if err != nil {
				slog.Warn("category not found, skipping transaction", "category", tx.Category, "note", tx.Note)
				continue
			}
		}

		txDate := time.Now().AddDate(0, 0, -tx.DaysAgo)

		// Determine balance delta
		delta := -tx.Amount
		if tx.Type == "income" {
			delta = tx.Amount
		}

		// Insert transaction and update balance atomically
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

		_, err = dbTx.ExecContext(ctx, `
			UPDATE accounts SET current_balance = current_balance + $1, updated_at = NOW()
			WHERE id = $2
		`, delta, accID)
		if err != nil {
			dbTx.Rollback()
			return fmt.Errorf("updating balance for %q: %w", tx.Note, err)
		}

		if err := dbTx.Commit(); err != nil {
			return err
		}
	}

	return nil
}
