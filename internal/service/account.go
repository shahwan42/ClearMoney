package service

import (
	"context"
	"encoding/json"
	"fmt"
	"strings"
	"time"

	"github.com/ahmedelsamadisi/clearmoney/internal/models"
	"github.com/ahmedelsamadisi/clearmoney/internal/repository"
)

// BillingCycleMetadata is stored in the Account.Metadata JSONB field for credit cards.
// StatementDay is the day of month the statement closes (e.g., 15).
// DueDay is the day of month payment is due (e.g., 5 of next month).
type BillingCycleMetadata struct {
	StatementDay int `json:"statement_day"`
	DueDay       int `json:"due_day"`
}

// BillingCycleInfo holds computed billing cycle information for display.
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
func GetCreditCardUtilization(acc models.Account) float64 {
	if !acc.IsCreditType() || acc.CreditLimit == nil || *acc.CreditLimit <= 0 {
		return 0
	}
	// Balance is negative for credit cards (owed). Utilization = |balance| / limit * 100
	used := -acc.CurrentBalance
	if used < 0 {
		used = 0
	}
	return used / *acc.CreditLimit * 100
}

// AccountService handles business logic for accounts.
type AccountService struct {
	repo *repository.AccountRepo
}

func NewAccountService(repo *repository.AccountRepo) *AccountService {
	return &AccountService{repo: repo}
}

// Create validates and creates a new account.
func (s *AccountService) Create(ctx context.Context, acc models.Account) (models.Account, error) {
	acc.Name = strings.TrimSpace(acc.Name)
	if acc.Name == "" {
		return models.Account{}, fmt.Errorf("account name is required")
	}
	if acc.InstitutionID == "" {
		return models.Account{}, fmt.Errorf("institution_id is required")
	}

	// Credit card/limit accounts must have a credit_limit set
	if acc.IsCreditType() && acc.CreditLimit == nil {
		return models.Account{}, fmt.Errorf("credit_limit is required for %s accounts", acc.Type)
	}

	return s.repo.Create(ctx, acc)
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
	acc.Name = strings.TrimSpace(acc.Name)
	if acc.Name == "" {
		return models.Account{}, fmt.Errorf("account name is required")
	}
	return s.repo.Update(ctx, acc)
}

func (s *AccountService) Delete(ctx context.Context, id string) error {
	return s.repo.Delete(ctx, id)
}

// ToggleDormant flips the dormant status for an account.
func (s *AccountService) ToggleDormant(ctx context.Context, id string) error {
	return s.repo.ToggleDormant(ctx, id)
}

// UpdateDisplayOrder sets the display order for an account.
func (s *AccountService) UpdateDisplayOrder(ctx context.Context, id string, order int) error {
	return s.repo.UpdateDisplayOrder(ctx, id, order)
}
