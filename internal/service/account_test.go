// Tests for account-related service logic: billing cycle parsing and computation.
//
// These are UNIT tests (no database needed) — they test pure functions that take
// inputs and return outputs. Compare to the integration tests in institution_test.go
// which require a running PostgreSQL.
//
// Go testing tip: tests in the same package (package service) can access unexported
// (lowercase) functions. This is like PHP's ReflectionMethod or Python's friend classes,
// but built into Go's test convention. Tests in a different package (package service_test)
// can only access exported (uppercase) members — use that for black-box testing.
package service

import (
	"context"
	"encoding/json"
	"fmt"
	"testing"
	"time"

	"github.com/shahwan42/clearmoney/internal/models"
	"github.com/shahwan42/clearmoney/internal/repository"
	"github.com/shahwan42/clearmoney/internal/testutil"
)

// TestParseBillingCycle_Valid verifies JSONB metadata is correctly unmarshaled.
// json.Marshal/Unmarshal in Go is like json_encode/json_decode in PHP or
// json.dumps/json.loads in Python.
func TestParseBillingCycle_Valid(t *testing.T) {
	meta := BillingCycleMetadata{StatementDay: 15, DueDay: 5}
	raw, _ := json.Marshal(meta)
	acc := models.Account{Metadata: raw}

	parsed := ParseBillingCycle(acc)
	if parsed == nil {
		t.Fatal("expected non-nil result")
	}
	if parsed.StatementDay != 15 || parsed.DueDay != 5 {
		t.Errorf("got statement=%d due=%d, want 15 and 5", parsed.StatementDay, parsed.DueDay)
	}
}

// TestParseBillingCycle_NilMetadata ensures nil JSONB returns nil (no panic).
// The zero value of models.Account{} has Metadata as nil (empty []byte).
func TestParseBillingCycle_NilMetadata(t *testing.T) {
	acc := models.Account{}
	if ParseBillingCycle(acc) != nil {
		t.Error("expected nil for empty metadata")
	}
}

func TestParseBillingCycle_ZeroFields(t *testing.T) {
	raw, _ := json.Marshal(map[string]int{"statement_day": 0, "due_day": 0})
	acc := models.Account{Metadata: raw}
	if ParseBillingCycle(acc) != nil {
		t.Error("expected nil for zero fields")
	}
}

// TestGetBillingCycleInfo_BeforeStatementDay tests billing cycle computation when
// the current day is before the statement close date. The test uses a fixed date
// (time.Date) instead of time.Now() to make the test deterministic — this is
// critical for date-dependent tests. In Laravel, you'd use Carbon::setTestNow().
func TestGetBillingCycleInfo_BeforeStatementDay(t *testing.T) {
	meta := BillingCycleMetadata{StatementDay: 15, DueDay: 5}
	// March 10 — before statement day 15
	now := time.Date(2026, 3, 10, 12, 0, 0, 0, time.UTC)

	info := GetBillingCycleInfo(meta, now)

	// Period: Feb 16 to Mar 15
	if info.PeriodStart.Month() != 2 || info.PeriodStart.Day() != 16 {
		t.Errorf("PeriodStart = %v, want Feb 16", info.PeriodStart)
	}
	if info.PeriodEnd.Month() != 3 || info.PeriodEnd.Day() != 15 {
		t.Errorf("PeriodEnd = %v, want Mar 15", info.PeriodEnd)
	}

	// Due date: Apr 5 (next month after statement closes)
	if info.DueDate.Month() != 4 || info.DueDate.Day() != 5 {
		t.Errorf("DueDate = %v, want Apr 5", info.DueDate)
	}

	// 26 days until due
	if info.DaysUntilDue < 25 || info.DaysUntilDue > 27 {
		t.Errorf("DaysUntilDue = %d, want ~26", info.DaysUntilDue)
	}
	if info.IsDueSoon {
		t.Error("should not be due soon")
	}
}

func TestGetBillingCycleInfo_AfterStatementDay(t *testing.T) {
	meta := BillingCycleMetadata{StatementDay: 15, DueDay: 5}
	// March 20 — after statement day 15
	now := time.Date(2026, 3, 20, 12, 0, 0, 0, time.UTC)

	info := GetBillingCycleInfo(meta, now)

	// Period: Mar 16 to Apr 15
	if info.PeriodStart.Month() != 3 || info.PeriodStart.Day() != 16 {
		t.Errorf("PeriodStart = %v, want Mar 16", info.PeriodStart)
	}
	if info.PeriodEnd.Month() != 4 || info.PeriodEnd.Day() != 15 {
		t.Errorf("PeriodEnd = %v, want Apr 15", info.PeriodEnd)
	}
}

func TestGetBillingCycleInfo_DueSoon(t *testing.T) {
	// Statement 5th, due 10th. On Apr 7 (after statement), period = Apr 6 to May 5,
	// due = May 10. That's ~33 days away. Not what we want.
	//
	// Instead: statement 15th, due 5th. On Apr 30, period = Apr 16 to May 15,
	// due = Jun 5. Not close.
	//
	// Simplest: statement 25th, due 28th. On Mar 25 (== statement day, before),
	// period = Feb 26 to Mar 25, due = Mar 28. That's 3 days.
	meta := BillingCycleMetadata{StatementDay: 25, DueDay: 28}
	now := time.Date(2026, 3, 25, 12, 0, 0, 0, time.UTC)

	info := GetBillingCycleInfo(meta, now)

	// Due date should be Mar 28 (DueDay > StatementDay, same month as PeriodEnd)
	if info.DueDate.Month() != 3 || info.DueDate.Day() != 28 {
		t.Errorf("DueDate = %v, want Mar 28", info.DueDate)
	}
	if !info.IsDueSoon {
		t.Errorf("expected IsDueSoon=true, DaysUntilDue=%d", info.DaysUntilDue)
	}
}

func TestGetBillingCycleInfo_DueDaySameMonth(t *testing.T) {
	// Statement on 5th, due on 25th — same month
	meta := BillingCycleMetadata{StatementDay: 5, DueDay: 25}
	now := time.Date(2026, 3, 3, 12, 0, 0, 0, time.UTC)

	info := GetBillingCycleInfo(meta, now)

	// Due date should be Mar 25 (same month as statement)
	if info.DueDate.Month() != 3 || info.DueDate.Day() != 25 {
		t.Errorf("DueDate = %v, want Mar 25", info.DueDate)
	}
}

// TestGetCreditCardUtilization_ZeroBalance verifies that a zero-balance CC
// returns 0% utilization (not "-0%"). Regression test for BUG-004.
func TestGetCreditCardUtilization_ZeroBalance(t *testing.T) {
	limit := 50000.0
	acc := models.Account{
		Type: models.AccountTypeCreditCard,
		CreditLimit: &limit,
		CurrentBalance: 0.0,
	}

	util := GetCreditCardUtilization(acc)
	if util != 0 {
		t.Errorf("expected 0, got %f", util)
	}
	// Ensure it's not negative zero
	s := fmt.Sprintf("%.0f", util)
	if s != "0" {
		t.Errorf("formatted utilization: expected %q, got %q", "0", s)
	}
}

// TestGetCreditCardUtilization_WithBalance verifies normal CC utilization.
func TestGetCreditCardUtilization_WithBalance(t *testing.T) {
	limit := 50000.0
	acc := models.Account{
		Type: models.AccountTypeCreditCard,
		CreditLimit: &limit,
		CurrentBalance: -1000.0, // owes 1000
	}

	util := GetCreditCardUtilization(acc)
	expected := 2.0 // 1000/50000*100
	if util != expected {
		t.Errorf("expected %f, got %f", expected, util)
	}
}

// TestAccountService_Create_CashWithCreditLimit verifies cash accounts cannot have a credit limit.
func TestAccountService_Create_CashWithCreditLimit(t *testing.T) {
	db := testutil.NewTestDB(t)
	testutil.CleanTable(t, db, "institutions")
	inst := testutil.CreateInstitution(t, db, models.Institution{
		Name: "Cash",
		Type: models.InstitutionTypeWallet,
	})
	svc := NewAccountService(repository.NewAccountRepo(db))

	limit := 10000.0
	_, err := svc.Create(context.Background(), models.Account{
		InstitutionID:  inst.ID,
		Name:           "Bad Cash",
		Type:           models.AccountTypeCash,
		Currency:       models.CurrencyEGP,
		CreditLimit:    &limit,
	})
	if err == nil {
		t.Error("expected error when creating cash account with credit limit")
	}
}

// TestAccountService_Create_Cash verifies cash accounts can be created successfully.
func TestAccountService_Create_Cash(t *testing.T) {
	db := testutil.NewTestDB(t)
	testutil.CleanTable(t, db, "institutions")
	inst := testutil.CreateInstitution(t, db, models.Institution{
		Name: "Cash",
		Type: models.InstitutionTypeWallet,
	})
	svc := NewAccountService(repository.NewAccountRepo(db))

	acc, err := svc.Create(context.Background(), models.Account{
		InstitutionID:  inst.ID,
		Name:           "EGP Cash",
		Type:           models.AccountTypeCash,
		Currency:       models.CurrencyEGP,
		InitialBalance: 5000,
	})
	if err != nil {
		t.Fatalf("create cash account: %v", err)
	}
	if acc.Type != models.AccountTypeCash {
		t.Errorf("expected type cash, got %q", acc.Type)
	}
}
