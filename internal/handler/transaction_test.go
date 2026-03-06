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

// setupTransactionHandlerTest creates a router with a test account ready for transactions.
func setupTransactionHandlerTest(t *testing.T) (*httptest.ResponseRecorder, *http.Request, func(method, path string, body string) *httptest.ResponseRecorder, models.Account) {
	t.Helper()
	db := testutil.NewTestDB(t)
	testutil.CleanTable(t, db, "transactions")
	testutil.CleanTable(t, db, "accounts")
	testutil.CleanTable(t, db, "institutions")

	inst := testutil.CreateInstitution(t, db, models.Institution{Name: "Test Bank"})
	acc := testutil.CreateAccount(t, db, models.Account{
		InstitutionID:  inst.ID,
		Name:           "Checking",
		Type:           models.AccountTypeChecking,
		Currency:       models.CurrencyEGP,
		InitialBalance: 10000,
	})

	router := NewRouter(db)

	// Helper to make HTTP requests against the router
	do := func(method, path string, body string) *httptest.ResponseRecorder {
		var req *http.Request
		if body != "" {
			req = httptest.NewRequest(method, path, bytes.NewBufferString(body))
			req.Header.Set("Content-Type", "application/json")
		} else {
			req = httptest.NewRequest(method, path, nil)
		}
		w := httptest.NewRecorder()
		router.ServeHTTP(w, req)
		return w
	}

	return nil, nil, do, acc
}

func TestTransactionHandler_Create_Expense(t *testing.T) {
	_, _, do, acc := setupTransactionHandlerTest(t)
	catID := testutil.GetFirstCategoryID(t, testutil.NewTestDB(t), models.CategoryTypeExpense)

	body := fmt.Sprintf(`{"type":"expense","amount":3000,"currency":"EGP","account_id":"%s","category_id":"%s"}`, acc.ID, catID)
	w := do("POST", "/api/transactions", body)

	if w.Code != http.StatusCreated {
		t.Fatalf("expected 201, got %d: %s", w.Code, w.Body.String())
	}

	var resp struct {
		Transaction models.Transaction `json:"transaction"`
		NewBalance  float64            `json:"new_balance"`
	}
	json.NewDecoder(w.Body).Decode(&resp)

	if resp.Transaction.ID == "" {
		t.Error("expected transaction ID")
	}
	if resp.NewBalance != 7000 {
		t.Errorf("expected balance 7000, got %f", resp.NewBalance)
	}
}

func TestTransactionHandler_Create_Income(t *testing.T) {
	_, _, do, acc := setupTransactionHandlerTest(t)

	body := fmt.Sprintf(`{"type":"income","amount":5000,"currency":"EGP","account_id":"%s"}`, acc.ID)
	w := do("POST", "/api/transactions", body)

	if w.Code != http.StatusCreated {
		t.Fatalf("expected 201, got %d: %s", w.Code, w.Body.String())
	}

	var resp struct {
		NewBalance float64 `json:"new_balance"`
	}
	json.NewDecoder(w.Body).Decode(&resp)

	if resp.NewBalance != 15000 {
		t.Errorf("expected balance 15000, got %f", resp.NewBalance)
	}
}

func TestTransactionHandler_Create_InvalidJSON(t *testing.T) {
	_, _, do, _ := setupTransactionHandlerTest(t)

	w := do("POST", "/api/transactions", "not json")
	if w.Code != http.StatusBadRequest {
		t.Errorf("expected 400, got %d", w.Code)
	}
}

func TestTransactionHandler_Create_ValidationError(t *testing.T) {
	_, _, do, acc := setupTransactionHandlerTest(t)

	// Missing amount
	body := fmt.Sprintf(`{"type":"expense","currency":"EGP","account_id":"%s"}`, acc.ID)
	w := do("POST", "/api/transactions", body)

	if w.Code != http.StatusBadRequest {
		t.Errorf("expected 400, got %d", w.Code)
	}
}

func TestTransactionHandler_List(t *testing.T) {
	_, _, do, acc := setupTransactionHandlerTest(t)

	// Create 2 transactions
	for i := 1; i <= 2; i++ {
		body := fmt.Sprintf(`{"type":"expense","amount":%d,"currency":"EGP","account_id":"%s"}`, i*100, acc.ID)
		do("POST", "/api/transactions", body)
	}

	w := do("GET", "/api/transactions", "")
	if w.Code != http.StatusOK {
		t.Fatalf("expected 200, got %d", w.Code)
	}

	var txns []models.Transaction
	json.NewDecoder(w.Body).Decode(&txns)
	if len(txns) != 2 {
		t.Errorf("expected 2, got %d", len(txns))
	}
}

func TestTransactionHandler_ListByAccount(t *testing.T) {
	_, _, do, acc := setupTransactionHandlerTest(t)

	body := fmt.Sprintf(`{"type":"expense","amount":500,"currency":"EGP","account_id":"%s"}`, acc.ID)
	do("POST", "/api/transactions", body)

	w := do("GET", "/api/transactions?account_id="+acc.ID, "")
	if w.Code != http.StatusOK {
		t.Fatalf("expected 200, got %d", w.Code)
	}

	var txns []models.Transaction
	json.NewDecoder(w.Body).Decode(&txns)
	if len(txns) != 1 {
		t.Errorf("expected 1, got %d", len(txns))
	}
}

func TestTransactionHandler_GetByID(t *testing.T) {
	_, _, do, acc := setupTransactionHandlerTest(t)

	body := fmt.Sprintf(`{"type":"expense","amount":250,"currency":"EGP","account_id":"%s"}`, acc.ID)
	createW := do("POST", "/api/transactions", body)

	var resp struct {
		Transaction models.Transaction `json:"transaction"`
	}
	json.NewDecoder(createW.Body).Decode(&resp)

	w := do("GET", "/api/transactions/"+resp.Transaction.ID, "")
	if w.Code != http.StatusOK {
		t.Fatalf("expected 200, got %d: %s", w.Code, w.Body.String())
	}

	var tx models.Transaction
	json.NewDecoder(w.Body).Decode(&tx)
	if tx.Amount != 250 {
		t.Errorf("expected amount 250, got %f", tx.Amount)
	}
}

func TestTransactionHandler_GetByID_NotFound(t *testing.T) {
	_, _, do, _ := setupTransactionHandlerTest(t)

	w := do("GET", "/api/transactions/00000000-0000-0000-0000-000000000000", "")
	if w.Code != http.StatusNotFound {
		t.Errorf("expected 404, got %d", w.Code)
	}
}

func TestTransactionHandler_Delete(t *testing.T) {
	_, _, do, acc := setupTransactionHandlerTest(t)

	// Create a transaction
	body := fmt.Sprintf(`{"type":"expense","amount":2000,"currency":"EGP","account_id":"%s"}`, acc.ID)
	createW := do("POST", "/api/transactions", body)

	var resp struct {
		Transaction models.Transaction `json:"transaction"`
	}
	json.NewDecoder(createW.Body).Decode(&resp)

	// Delete it
	w := do("DELETE", "/api/transactions/"+resp.Transaction.ID, "")
	if w.Code != http.StatusNoContent {
		t.Errorf("expected 204, got %d", w.Code)
	}

	// Verify it's gone
	w = do("GET", "/api/transactions/"+resp.Transaction.ID, "")
	if w.Code != http.StatusNotFound {
		t.Errorf("expected 404 after delete, got %d", w.Code)
	}
}

func TestTransactionHandler_Delete_NotFound(t *testing.T) {
	_, _, do, _ := setupTransactionHandlerTest(t)

	w := do("DELETE", "/api/transactions/00000000-0000-0000-0000-000000000000", "")
	if w.Code != http.StatusNotFound {
		t.Errorf("expected 404, got %d", w.Code)
	}
}

func TestTransactionHandler_Delete_RestoresBalance(t *testing.T) {
	_, _, do, acc := setupTransactionHandlerTest(t)

	// Create expense that reduces balance to 7000
	body := fmt.Sprintf(`{"type":"expense","amount":3000,"currency":"EGP","account_id":"%s"}`, acc.ID)
	createW := do("POST", "/api/transactions", body)

	var createResp struct {
		Transaction models.Transaction `json:"transaction"`
		NewBalance  float64            `json:"new_balance"`
	}
	json.NewDecoder(createW.Body).Decode(&createResp)

	if createResp.NewBalance != 7000 {
		t.Fatalf("expected 7000 after expense, got %f", createResp.NewBalance)
	}

	// Delete the expense — balance should restore to 10000
	do("DELETE", "/api/transactions/"+createResp.Transaction.ID, "")

	// Create another small expense to verify balance was restored
	body = fmt.Sprintf(`{"type":"expense","amount":1,"currency":"EGP","account_id":"%s"}`, acc.ID)
	checkW := do("POST", "/api/transactions", body)

	var checkResp struct {
		NewBalance float64 `json:"new_balance"`
	}
	json.NewDecoder(checkW.Body).Decode(&checkResp)

	if checkResp.NewBalance != 9999 {
		t.Errorf("expected balance 9999 (restored 10000 - 1), got %f", checkResp.NewBalance)
	}
}
