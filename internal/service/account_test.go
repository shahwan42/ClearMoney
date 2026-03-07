package service

import (
	"encoding/json"
	"testing"
	"time"

	"github.com/ahmedelsamadisi/clearmoney/internal/models"
)

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
