// Tests for InstitutionService — validates institution CRUD business logic.
//
// These are INTEGRATION tests — they use a real PostgreSQL database.
// Requires TEST_DATABASE_URL env var.
package service

import (
	"context"
	"testing"

	"github.com/shahwan42/clearmoney/internal/models"
	"github.com/shahwan42/clearmoney/internal/repository"
	"github.com/shahwan42/clearmoney/internal/testutil"
)

func TestInstitutionService_Create_Valid(t *testing.T) {
	db := testutil.NewTestDB(t)
	testutil.CleanTable(t, db, "institutions")
	userID := testutil.SetupTestUser(t, db)
	svc := NewInstitutionService(repository.NewInstitutionRepo(db))

	inst, err := svc.Create(context.Background(), userID, models.Institution{
		Name: "HSBC",
		Type: models.InstitutionTypeBank,
	})
	if err != nil {
		t.Fatalf("create: %v", err)
	}
	if inst.ID == "" {
		t.Error("expected ID")
	}
}

func TestInstitutionService_Create_EmptyName(t *testing.T) {
	db := testutil.NewTestDB(t)
	userID := testutil.SetupTestUser(t, db)
	svc := NewInstitutionService(repository.NewInstitutionRepo(db))

	_, err := svc.Create(context.Background(), userID, models.Institution{Name: ""})
	if err == nil {
		t.Error("expected error for empty name")
	}
}

func TestInstitutionService_Create_WhitespaceName(t *testing.T) {
	db := testutil.NewTestDB(t)
	userID := testutil.SetupTestUser(t, db)
	svc := NewInstitutionService(repository.NewInstitutionRepo(db))

	_, err := svc.Create(context.Background(), userID, models.Institution{Name: "   "})
	if err == nil {
		t.Error("expected error for whitespace-only name")
	}
}

func TestInstitutionService_Create_InvalidType(t *testing.T) {
	db := testutil.NewTestDB(t)
	userID := testutil.SetupTestUser(t, db)
	svc := NewInstitutionService(repository.NewInstitutionRepo(db))

	_, err := svc.Create(context.Background(), userID, models.Institution{
		Name: "Test",
		Type: "invalid",
	})
	if err == nil {
		t.Error("expected error for invalid type")
	}
}

func TestInstitutionService_Create_DefaultsToBank(t *testing.T) {
	db := testutil.NewTestDB(t)
	testutil.CleanTable(t, db, "institutions")
	userID := testutil.SetupTestUser(t, db)
	svc := NewInstitutionService(repository.NewInstitutionRepo(db))

	inst, err := svc.Create(context.Background(), userID, models.Institution{Name: "Test"})
	if err != nil {
		t.Fatalf("create: %v", err)
	}
	if inst.Type != models.InstitutionTypeBank {
		t.Errorf("expected type bank, got %q", inst.Type)
	}
}

func TestInstitutionService_Create_Wallet(t *testing.T) {
	db := testutil.NewTestDB(t)
	testutil.CleanTable(t, db, "institutions")
	userID := testutil.SetupTestUser(t, db)
	svc := NewInstitutionService(repository.NewInstitutionRepo(db))

	inst, err := svc.Create(context.Background(), userID, models.Institution{
		Name: "Cash",
		Type: models.InstitutionTypeWallet,
	})
	if err != nil {
		t.Fatalf("create wallet institution: %v", err)
	}
	if inst.ID == "" {
		t.Error("expected ID")
	}
	if inst.Type != models.InstitutionTypeWallet {
		t.Errorf("expected type wallet, got %q", inst.Type)
	}
}
