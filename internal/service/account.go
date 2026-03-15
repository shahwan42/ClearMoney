// account.go — AccountService and credit card billing cycle logic.
//
// This file contains two main concerns:
//   1. AccountService: CRUD + validation for bank accounts (current, savings, credit, etc.)
//   2. Credit card billing cycle: parsing JSONB metadata, computing statement periods,
//      interest-free tracking, and utilization calculations.
//
// Laravel analogy: AccountService is like App\Services\AccountService. The billing cycle
// logic would be in a dedicated CreditCardService or as methods on the Account model.
//
// Django analogy: This is like an accounts/services.py module with both AccountService
// and credit card utility functions.
//
// Go-specific patterns used here:
//   - json.Unmarshal: Go's equivalent of json_decode() in PHP or json.loads() in Python.
//     See: https://pkg.go.dev/encoding/json
//   - Pointer fields (*float64, *string): Go's way of expressing "nullable" values.
//     In PHP, you'd use ?float. In Django, null=True on the model field.
//   - time.Time: Go's datetime type — immutable, timezone-aware.
//     See: https://pkg.go.dev/time
package service

import (
	"context"
	"encoding/json"
	"fmt"
	"time"

	"github.com/ahmedelsamadisi/clearmoney/internal/logutil"
	"github.com/ahmedelsamadisi/clearmoney/internal/models"
	"github.com/ahmedelsamadisi/clearmoney/internal/repository"
)

// BillingCycleMetadata is stored in the Account.Metadata JSONB field for credit cards.
// PostgreSQL JSONB lets us store flexible JSON data in a single column — like
// Laravel's $casts['metadata'] = 'json' or Django's JSONField.
//
// StatementDay is the day of month the statement closes (e.g., 15).
// DueDay is the day of month payment is due (e.g., 5 of next month).
//
// The struct tags (`json:"statement_day"`) control how Go marshals/unmarshals JSON.
// See: https://pkg.go.dev/encoding/json#Marshal
type BillingCycleMetadata struct {
	StatementDay int `json:"statement_day"`
	DueDay       int `json:"due_day"`
}

// BillingCycleInfo holds computed billing cycle information for display.
// This is a "computed struct" — not stored in the DB, but derived from
// BillingCycleMetadata + the current date. Like a Laravel Accessor or
// Django's @property on a model, but as a standalone struct.
type BillingCycleInfo struct {
	StatementDay  int
	DueDay        int
	PeriodStart   time.Time // start of current billing period
	PeriodEnd     time.Time // end of current billing period (statement date)
	DueDate       time.Time // when payment is due
	DaysUntilDue  int       // days until due date (negative if overdue)
	IsDueSoon     bool      // true if due within 7 days
}

// ParseBillingCycle extracts billing cycle metadata from an account's JSONB field.
// Returns nil if the account doesn't have billing cycle info.
//
// Returns *BillingCycleMetadata (pointer) — nil means "no billing cycle configured."
// In PHP, you'd return null. In Python, None. In Go, a nil pointer serves the same purpose.
// The caller checks: if meta == nil { /* no billing cycle */ }
func ParseBillingCycle(acc models.Account) *BillingCycleMetadata {
	if len(acc.Metadata) == 0 || string(acc.Metadata) == "null" {
		return nil
	}
	var meta BillingCycleMetadata
	if err := json.Unmarshal(acc.Metadata, &meta); err != nil {
		return nil
	}
	if meta.StatementDay == 0 || meta.DueDay == 0 {
		return nil
	}
	return &meta
}

// GetBillingCycleInfo computes the current billing cycle dates for a credit card.
// This is a pure function (no receiver, no side effects) — it takes inputs and returns
// a computed result. Go encourages free functions when there's no state to manage.
// In Laravel, this might be a static method; in Django, a module-level function.
//
// time.Date() constructs a date — note Go handles month overflow gracefully:
// time.Date(2026, 0, 15, ...) becomes December 15, 2025 (month 0 = previous year's Dec).
// See: https://pkg.go.dev/time#Date
func GetBillingCycleInfo(meta BillingCycleMetadata, now time.Time) BillingCycleInfo {
	info := BillingCycleInfo{
		StatementDay: meta.StatementDay,
		DueDay:       meta.DueDay,
	}

	year, month, day := now.Date()

	// Determine current billing period
	if day <= meta.StatementDay {
		// We're before the statement date this month
		// Period: previous month's statement day + 1 to this month's statement day
		prevMonth := time.Date(year, month-1, meta.StatementDay+1, 0, 0, 0, 0, now.Location())
		info.PeriodStart = prevMonth
		info.PeriodEnd = time.Date(year, month, meta.StatementDay, 23, 59, 59, 0, now.Location())
	} else {
		// We're after the statement date
		// Period: this month's statement day + 1 to next month's statement day
		info.PeriodStart = time.Date(year, month, meta.StatementDay+1, 0, 0, 0, 0, now.Location())
		info.PeriodEnd = time.Date(year, month+1, meta.StatementDay, 23, 59, 59, 0, now.Location())
	}

	// Calculate due date: if statement is on the 15th and due on the 5th,
	// then the due date is the 5th of the month after the statement closes.
	if meta.DueDay > meta.StatementDay {
		// Due date is same month as statement (e.g., statement 5th, due 25th)
		info.DueDate = time.Date(info.PeriodEnd.Year(), info.PeriodEnd.Month(), meta.DueDay, 0, 0, 0, 0, now.Location())
	} else {
		// Due date is next month after statement (e.g., statement 15th, due 5th)
		info.DueDate = time.Date(info.PeriodEnd.Year(), info.PeriodEnd.Month()+1, meta.DueDay, 0, 0, 0, 0, now.Location())
	}

	info.DaysUntilDue = int(info.DueDate.Sub(now).Hours() / 24)
	info.IsDueSoon = info.DaysUntilDue >= 0 && info.DaysUntilDue <= 7

	return info
}

// StatementData holds the data for a credit card statement view (TASK-071).
// A statement covers one billing period with all transactions.
type StatementData struct {
	Account        models.Account
	BillingCycle   BillingCycleInfo
	Transactions   []models.Transaction
	OpeningBalance float64 // balance at start of period
	TotalSpending  float64 // sum of expenses in the period
	TotalPayments  float64 // sum of payments/credits in the period
	ClosingBalance float64 // balance at end of period (current for active period)
	// TASK-072: Interest-free period tracking
	InterestFreeDays    int  // total interest-free days from statement date
	InterestFreeRemain  int  // days remaining in interest-free period
	InterestFreeUrgent  bool // true if < 7 days remaining
	// TASK-075: Payment history
	PaymentHistory []models.Transaction // recent payments to this card
}

// CreditCardSummary holds credit card summary data for the dashboard (TASK-074).
type CreditCardSummary struct {
	AccountID      string
	AccountName    string
	Balance        float64 // current balance (negative = owed)
	CreditLimit    float64
	Utilization    float64 // 0–100 percentage
	UtilizationPct float64 // for chart rendering
	DueDate        time.Time
	DaysUntilDue   int
	IsDueSoon      bool
	HasBillingCycle bool
}

// GetStatementData returns the credit card statement for a given billing period.
// If periodStr is empty, returns the current billing period.
//
// This is a free function (not a method on a struct) because it orchestrates
// data from multiple sources (account, transaction repo, snapshot service).
// In Laravel, this might be a dedicated StatementService. In Django, a service function.
//
// Error wrapping with %w: fmt.Errorf("loading: %w", err) wraps the original error
// so callers can use errors.Is() or errors.As() to inspect the chain.
// Like PHP's previous exception parameter: throw new Exception("msg", 0, $previous).
// See: https://pkg.go.dev/fmt#Errorf (the %w verb)
func GetStatementData(acc models.Account, txRepo *repository.TransactionRepo, snapshotSvc *SnapshotService, ctx context.Context, periodStr string) (*StatementData, error) {
	meta := ParseBillingCycle(acc)
	if meta == nil {
		return nil, fmt.Errorf("account has no billing cycle configuration")
	}

	now := time.Now()
	info := GetBillingCycleInfo(*meta, now)

	// If a specific period is requested (YYYY-MM), compute that period's dates
	if periodStr != "" {
		t, err := time.Parse("2006-01", periodStr)
		if err == nil {
			// Use the 1st of that month to compute the billing cycle
			info = GetBillingCycleInfo(*meta, t.AddDate(0, 0, meta.StatementDay))
		}
	}

	txns, err := txRepo.GetByAccountDateRange(ctx, acc.ID, info.PeriodStart, info.PeriodEnd)
	if err != nil {
		return nil, fmt.Errorf("loading statement transactions: %w", err)
	}

	var totalSpending, totalPayments float64
	for _, tx := range txns {
		if tx.BalanceDelta < 0 {
			totalSpending += -tx.BalanceDelta // spending makes balance more negative
		} else {
			totalPayments += tx.BalanceDelta
		}
	}

	sd := &StatementData{
		Account:        acc,
		BillingCycle:   info,
		Transactions:   txns,
		TotalSpending:  totalSpending,
		TotalPayments:  totalPayments,
		ClosingBalance: acc.CurrentBalance,
	}
	sd.OpeningBalance = sd.ClosingBalance
	for _, tx := range txns {
		sd.OpeningBalance -= tx.BalanceDelta
	}

	// TASK-072: Interest-free period tracking
	// Standard interest-free period is 55 days from statement close date.
	interestFreeDays := 55
	sd.InterestFreeDays = interestFreeDays
	interestFreeEnd := info.PeriodEnd.AddDate(0, 0, interestFreeDays)
	sd.InterestFreeRemain = int(interestFreeEnd.Sub(now).Hours() / 24)
	if sd.InterestFreeRemain < 0 {
		sd.InterestFreeRemain = 0
	}
	sd.InterestFreeUrgent = sd.InterestFreeRemain > 0 && sd.InterestFreeRemain <= 7

	// TASK-075: Payment history
	if txRepo != nil {
		payments, err := txRepo.GetPaymentsToAccount(ctx, acc.ID, 10)
		if err == nil {
			sd.PaymentHistory = payments
		}
	}

	return sd, nil
}

// GetCreditCardUtilization computes the utilization percentage for a credit card.
// Used for donut charts (TASK-073) and dashboard summary (TASK-074).
//
// Note: acc.CreditLimit is *float64 (pointer to float64, i.e., nullable).
// We must nil-check before dereferencing: *acc.CreditLimit dereferences the pointer.
// If you skip the nil check, Go panics with "nil pointer dereference" (like PHP's
// "trying to access property of null" or Python's AttributeError).
func GetCreditCardUtilization(acc models.Account) float64 {
	if !acc.IsCreditType() || acc.CreditLimit == nil || *acc.CreditLimit <= 0 {
		return 0
	}
	// Balance is negative for credit cards (owed). Utilization = |balance| / limit * 100
	used := -acc.CurrentBalance
	if used <= 0 {
		return 0
	}
	return used / *acc.CreditLimit * 100
}

// AccountService handles business logic for accounts.
// Same pattern as InstitutionService: struct with a repo dependency, explicit constructor.
//
// In Laravel: App\Services\AccountService with constructor injection.
// In Django: a service class or module-level functions in accounts/services.py.
type AccountService struct {
	repo          *repository.AccountRepo
	recurringRepo *repository.RecurringRepo // optional; set via SetRecurringRepo for cleanup on delete
}

// NewAccountService creates the service with its repository dependency.
// Go convention: constructor functions are named NewTypeName and return *TypeName.
// See: https://go.dev/doc/effective_go#composite_literals
func NewAccountService(repo *repository.AccountRepo) *AccountService {
	return &AccountService{repo: repo}
}

// SetRecurringRepo wires in the recurring repository so AccountService can clean up
// stale recurring rules when an account is deleted (BUG-012). Uses setter injection
// to avoid growing the constructor — same pattern as SetSnapshotService etc.
func (s *AccountService) SetRecurringRepo(repo *repository.RecurringRepo) {
	s.recurringRepo = repo
}

// Create validates and creates a new account.
func (s *AccountService) Create(ctx context.Context, acc models.Account) (models.Account, error) {
	var err error
	if acc.Name, err = requireTrimmedName(acc.Name, "account name"); err != nil {
		return models.Account{}, err
	}
	if err := requireNotEmpty(acc.InstitutionID, "institution_id"); err != nil {
		return models.Account{}, err
	}

	// Credit card/limit accounts must have a credit_limit set
	if acc.IsCreditType() && acc.CreditLimit == nil {
		return models.Account{}, fmt.Errorf("credit_limit is required for %s accounts", acc.Type)
	}

	// Cash accounts cannot have a credit limit
	if acc.Type == models.AccountTypeCash && acc.CreditLimit != nil {
		return models.Account{}, fmt.Errorf("cash accounts cannot have a credit limit")
	}

	created, err := s.repo.Create(ctx, acc)
	if err != nil {
		return models.Account{}, err
	}
	logutil.LogEvent(ctx, "account.created", "type", string(created.Type), "currency", string(created.Currency))
	return created, nil
}

func (s *AccountService) GetByID(ctx context.Context, id string) (models.Account, error) {
	return s.repo.GetByID(ctx, id)
}

func (s *AccountService) GetAll(ctx context.Context) ([]models.Account, error) {
	return s.repo.GetAll(ctx)
}

func (s *AccountService) GetByInstitution(ctx context.Context, institutionID string) ([]models.Account, error) {
	return s.repo.GetByInstitution(ctx, institutionID)
}

func (s *AccountService) Update(ctx context.Context, acc models.Account) (models.Account, error) {
	var err error
	if acc.Name, err = requireTrimmedName(acc.Name, "account name"); err != nil {
		return models.Account{}, err
	}
	updated, err := s.repo.Update(ctx, acc)
	if err != nil {
		return models.Account{}, err
	}
	logutil.LogEvent(ctx, "account.updated", "id", acc.ID)
	return updated, nil
}

// Delete removes an account, cleaning up any recurring rules that reference it first.
// Without this cleanup, confirming a recurring rule after its account is deleted
// causes a FK violation on transactions.account_id (BUG-012).
func (s *AccountService) Delete(ctx context.Context, id string) error {
	if s.recurringRepo != nil {
		if err := s.recurringRepo.DeleteByAccountID(ctx, id); err != nil {
			return fmt.Errorf("cleaning up recurring rules: %w", err)
		}
	}
	if err := s.repo.Delete(ctx, id); err != nil {
		return err
	}
	logutil.LogEvent(ctx, "account.deleted", "id", id)
	return nil
}

// ToggleDormant flips the dormant status for an account.
// Dormant accounts are hidden from the main dashboard but not deleted.
// Like Laravel's soft delete, but for visibility rather than existence.
func (s *AccountService) ToggleDormant(ctx context.Context, id string) error {
	if err := s.repo.ToggleDormant(ctx, id); err != nil {
		return err
	}
	logutil.LogEvent(ctx, "account.dormant_toggled", "id", id)
	return nil
}

// UpdateDisplayOrder sets the display order for an account.
func (s *AccountService) UpdateDisplayOrder(ctx context.Context, id string, order int) error {
	return s.repo.UpdateDisplayOrder(ctx, id, order)
}
