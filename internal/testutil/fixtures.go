// Fixtures provides factory functions for creating test data.
//
// These are like Laravel's model factories (User::factory()->create())
// or Django's fixture factories. They insert real data into the test DB
// and return the created model, so you can use it in assertions.
//
// Naming convention: Create<Model> for the basic factory.
// Each function inserts a row with sensible defaults that can be overridden.
package testutil

import (
	"database/sql"
	"testing"

	"github.com/ahmedelsamadisi/clearmoney/internal/models"
)

// CreateInstitution inserts a test institution and returns it with its generated ID.
// Defaults to a bank named "Test Bank" — override by passing a modified struct.
//
// Example:
//
//	inst := testutil.CreateInstitution(t, db, models.Institution{Name: "HSBC"})
func CreateInstitution(t *testing.T, db *sql.DB, inst models.Institution) models.Institution {
	t.Helper()

	// Apply defaults for required fields if not set
	if inst.Name == "" {
		inst.Name = "Test Bank"
	}
	if inst.Type == "" {
		inst.Type = models.InstitutionTypeBank
	}

	err := db.QueryRow(`
		INSERT INTO institutions (name, type, color, icon, display_order)
		VALUES ($1, $2, $3, $4, $5)
		RETURNING id, created_at, updated_at
	`, inst.Name, inst.Type, inst.Color, inst.Icon, inst.DisplayOrder,
	).Scan(&inst.ID, &inst.CreatedAt, &inst.UpdatedAt)

	if err != nil {
		t.Fatalf("creating test institution: %v", err)
	}

	return inst
}

// CreateAccount inserts a test account under the given institution.
// Defaults to EGP checking account with 0 balance.
//
// Example:
//
//	acc := testutil.CreateAccount(t, db, models.Account{
//	    InstitutionID: inst.ID,
//	    Name:          "Checking",
//	    Currency:      models.CurrencyUSD,
//	    InitialBalance: 5000,
//	})
func CreateAccount(t *testing.T, db *sql.DB, acc models.Account) models.Account {
	t.Helper()

	if acc.Name == "" {
		acc.Name = "Test Account"
	}
	if acc.Type == "" {
		acc.Type = models.AccountTypeChecking
	}
	if acc.Currency == "" {
		acc.Currency = models.CurrencyEGP
	}
	// Set current_balance to initial_balance on creation (mirrors real behavior)
	acc.CurrentBalance = acc.InitialBalance

	err := db.QueryRow(`
		INSERT INTO accounts (institution_id, name, type, currency, current_balance, initial_balance, credit_limit, is_dormant, display_order)
		VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9)
		RETURNING id, created_at, updated_at
	`, acc.InstitutionID, acc.Name, acc.Type, acc.Currency,
		acc.CurrentBalance, acc.InitialBalance, acc.CreditLimit,
		acc.IsDormant, acc.DisplayOrder,
	).Scan(&acc.ID, &acc.CreatedAt, &acc.UpdatedAt)

	if err != nil {
		t.Fatalf("creating test account: %v", err)
	}

	return acc
}

// GetFirstCategoryID returns the ID of the first category of the given type.
// Useful for creating test transactions that need a valid category_id.
func GetFirstCategoryID(t *testing.T, db *sql.DB, categoryType models.CategoryType) string {
	t.Helper()
	var id string
	err := db.QueryRow(`SELECT id FROM categories WHERE type = $1 LIMIT 1`, categoryType).Scan(&id)
	if err != nil {
		t.Fatalf("getting %s category: %v", categoryType, err)
	}
	return id
}
