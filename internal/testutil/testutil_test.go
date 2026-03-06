package testutil

import (
	"testing"

	"github.com/ahmedelsamadisi/clearmoney/internal/models"
)

func TestNewTestDB(t *testing.T) {
	db := NewTestDB(t)

	// Verify we can query the database
	var result int
	err := db.QueryRow("SELECT 1").Scan(&result)
	if err != nil {
		t.Fatalf("query failed: %v", err)
	}
	if result != 1 {
		t.Errorf("expected 1, got %d", result)
	}
}

func TestCreateInstitution_Defaults(t *testing.T) {
	db := NewTestDB(t)
	CleanTable(t, db, "institutions")

	inst := CreateInstitution(t, db, models.Institution{})

	if inst.ID == "" {
		t.Error("expected institution to have an ID")
	}
	if inst.Name != "Test Bank" {
		t.Errorf("expected default name 'Test Bank', got %q", inst.Name)
	}
	if inst.Type != models.InstitutionTypeBank {
		t.Errorf("expected default type 'bank', got %q", inst.Type)
	}
}

func TestCreateInstitution_CustomValues(t *testing.T) {
	db := NewTestDB(t)
	CleanTable(t, db, "institutions")

	inst := CreateInstitution(t, db, models.Institution{
		Name: "HSBC",
		Type: models.InstitutionTypeBank,
	})

	if inst.Name != "HSBC" {
		t.Errorf("expected name 'HSBC', got %q", inst.Name)
	}
}

func TestCreateAccount(t *testing.T) {
	db := NewTestDB(t)
	CleanTable(t, db, "institutions")

	inst := CreateInstitution(t, db, models.Institution{Name: "CIB"})

	acc := CreateAccount(t, db, models.Account{
		InstitutionID:  inst.ID,
		Name:           "Savings",
		Type:           models.AccountTypeSavings,
		Currency:       models.CurrencyEGP,
		InitialBalance: 50000,
	})

	if acc.ID == "" {
		t.Error("expected account to have an ID")
	}
	if acc.CurrentBalance != 50000 {
		t.Errorf("expected current_balance 50000, got %f", acc.CurrentBalance)
	}
	if acc.InstitutionID != inst.ID {
		t.Error("expected account to belong to the institution")
	}
}

func TestCreateAccount_CreditCard(t *testing.T) {
	db := NewTestDB(t)
	CleanTable(t, db, "institutions")

	inst := CreateInstitution(t, db, models.Institution{})
	limit := 500000.0

	acc := CreateAccount(t, db, models.Account{
		InstitutionID: inst.ID,
		Name:          "HSBC Credit Card",
		Type:          models.AccountTypeCreditCard,
		CreditLimit:   &limit,
	})

	if acc.CreditLimit == nil || *acc.CreditLimit != 500000 {
		t.Error("expected credit limit of 500000")
	}
}

func TestGetFirstCategoryID(t *testing.T) {
	db := NewTestDB(t)

	expenseID := GetFirstCategoryID(t, db, models.CategoryTypeExpense)
	if expenseID == "" {
		t.Error("expected to find an expense category")
	}

	incomeID := GetFirstCategoryID(t, db, models.CategoryTypeIncome)
	if incomeID == "" {
		t.Error("expected to find an income category")
	}

	if expenseID == incomeID {
		t.Error("expense and income category IDs should be different")
	}
}

func TestCleanTable(t *testing.T) {
	db := NewTestDB(t)

	// Create some data
	CreateInstitution(t, db, models.Institution{Name: "To Be Deleted"})

	// Clean it
	CleanTable(t, db, "institutions")

	// Verify it's gone
	var count int
	db.QueryRow("SELECT COUNT(*) FROM institutions").Scan(&count)
	if count != 0 {
		t.Errorf("expected 0 institutions after clean, got %d", count)
	}
}
