// account_test.go — Integration tests for account CRUD API.
//
// These tests follow the same patterns as institution_test.go.
// Key difference: accounts require a parent institution (foreign key),
// so each test creates an institution first using testutil.CreateInstitution().
//
// Test for credit card validation (TestAccountHandler_Create_CreditCardWithoutLimit):
// Credit card accounts require a credit_limit field. The service layer validates this
// and returns an error, which the handler converts to a 400 Bad Request response.
//
// See institution_test.go for detailed explanations of testing patterns.
package handler

import (
	"bytes"
	"encoding/json"
	"fmt"
	"net/http"
	"net/http/httptest"
	"testing"

	"github.com/ahmedelsamadisi/clearmoney/internal/models"
	"github.com/ahmedelsamadisi/clearmoney/internal/testutil"
)

func TestAccountHandler_CreateAndList(t *testing.T) {
	db := testutil.NewTestDB(t)
	testutil.CleanTable(t, db, "institutions")
	router, addAuth := testRouter(t, db)

	// Need an institution first
	inst := testutil.CreateInstitution(t, db, models.Institution{Name: "HSBC"})

	// POST — create account
	body := fmt.Sprintf(`{
		"institution_id": %q,
		"name": "Checking",
		"type": "checking",
		"currency": "EGP",
		"initial_balance": 50000
	}`, inst.ID)

	req := httptest.NewRequest(http.MethodPost, "/api/accounts", bytes.NewBufferString(body))
	req.Header.Set("Content-Type", "application/json")
	addAuth(req)
	w := httptest.NewRecorder()
	router.ServeHTTP(w, req)

	if w.Code != http.StatusCreated {
		t.Fatalf("create: expected 201, got %d: %s", w.Code, w.Body.String())
	}

	var created models.Account
	json.NewDecoder(w.Body).Decode(&created)
	if created.CurrentBalance != 50000 {
		t.Errorf("expected balance 50000, got %f", created.CurrentBalance)
	}

	// GET — list
	req = httptest.NewRequest(http.MethodGet, "/api/accounts", nil)
	addAuth(req)
	w = httptest.NewRecorder()
	router.ServeHTTP(w, req)

	if w.Code != http.StatusOK {
		t.Fatalf("list: expected 200, got %d", w.Code)
	}

	var list []models.Account
	json.NewDecoder(w.Body).Decode(&list)
	if len(list) < 1 {
		t.Error("expected at least 1 account")
	}
}

func TestAccountHandler_Create_CreditCardWithoutLimit(t *testing.T) {
	db := testutil.NewTestDB(t)
	testutil.CleanTable(t, db, "institutions")
	router, addAuth := testRouter(t, db)

	inst := testutil.CreateInstitution(t, db, models.Institution{Name: "HSBC"})

	body := fmt.Sprintf(`{
		"institution_id": %q,
		"name": "Credit Card",
		"type": "credit_card",
		"currency": "EGP"
	}`, inst.ID)

	req := httptest.NewRequest(http.MethodPost, "/api/accounts", bytes.NewBufferString(body))
	req.Header.Set("Content-Type", "application/json")
	addAuth(req)
	w := httptest.NewRecorder()
	router.ServeHTTP(w, req)

	if w.Code != http.StatusBadRequest {
		t.Errorf("expected 400 for credit card without limit, got %d: %s", w.Code, w.Body.String())
	}
}

func TestAccountHandler_FilterByInstitution(t *testing.T) {
	db := testutil.NewTestDB(t)
	testutil.CleanTable(t, db, "institutions")
	router, addAuth := testRouter(t, db)

	inst1 := testutil.CreateInstitution(t, db, models.Institution{Name: "HSBC"})
	inst2 := testutil.CreateInstitution(t, db, models.Institution{Name: "CIB"})

	testutil.CreateAccount(t, db, models.Account{InstitutionID: inst1.ID, Name: "A1"})
	testutil.CreateAccount(t, db, models.Account{InstitutionID: inst1.ID, Name: "A2"})
	testutil.CreateAccount(t, db, models.Account{InstitutionID: inst2.ID, Name: "B1"})

	// Filter by inst1
	req := httptest.NewRequest(http.MethodGet, "/api/accounts?institution_id="+inst1.ID, nil)
	addAuth(req)
	w := httptest.NewRecorder()
	router.ServeHTTP(w, req)

	var list []models.Account
	json.NewDecoder(w.Body).Decode(&list)
	if len(list) != 2 {
		t.Errorf("expected 2 accounts for HSBC, got %d", len(list))
	}
}
