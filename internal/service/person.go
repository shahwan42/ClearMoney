// Package service — PersonService handles business logic for the people ledger.
//
// Tracks personal lending and borrowing: "I lent X to Y" / "I borrowed from Y".
// Every loan/repayment atomically updates both the account balance AND the person's
// net balance — all within a database transaction.
//
// Net balance convention:
//   - Positive: they owe me (I lent them money)
//   - Negative: I owe them (I borrowed from them)
//
// Laravel analogy: Like a PersonService that manages loan_out/loan_in transactions.
// Similar to how you'd track debts in a fintech app with Eloquent relationships
// between Person and Transaction, using DB::transaction() for atomicity.
//
// Django analogy: Like a persons/services.py module with functions that use
// transaction.atomic() to coordinate updates across multiple models.
//
// Key pattern: RecordLoan and RecordRepayment update TWO database tables atomically:
//   1. accounts.current_balance (the bank account impact)
//   2. persons.net_balance (the person-level debt tracking)
// Both must succeed or both must roll back.
package service

import (
	"context"
	"fmt"
	"time"

	"github.com/shahwan42/clearmoney/internal/logutil"
	"github.com/shahwan42/clearmoney/internal/models"
	"github.com/shahwan42/clearmoney/internal/repository"
)

// PersonService handles person CRUD and loan/repayment logic.
// It needs two repositories because loans affect both the person (debt tracking)
// and the account (balance). This cross-cutting concern requires a DB transaction
// that spans both tables.
type PersonService struct {
	personRepo *repository.PersonRepo
	txRepo     *repository.TransactionRepo
}

func NewPersonService(personRepo *repository.PersonRepo, txRepo *repository.TransactionRepo) *PersonService {
	return &PersonService{personRepo: personRepo, txRepo: txRepo}
}

func (s *PersonService) Create(ctx context.Context, p models.Person) (models.Person, error) {
	if err := requireNotEmpty(p.Name, "name"); err != nil {
		return models.Person{}, err
	}
	created, err := s.personRepo.Create(ctx, p)
	if err != nil {
		return models.Person{}, err
	}
	logutil.LogEvent(ctx, "person.created")
	return created, nil
}

func (s *PersonService) GetByID(ctx context.Context, id string) (models.Person, error) {
	return s.personRepo.GetByID(ctx, id)
}

func (s *PersonService) GetAll(ctx context.Context) ([]models.Person, error) {
	return s.personRepo.GetAll(ctx)
}

func (s *PersonService) Update(ctx context.Context, p models.Person) (models.Person, error) {
	return s.personRepo.Update(ctx, p)
}

func (s *PersonService) Delete(ctx context.Context, id string) error {
	return s.personRepo.Delete(ctx, id)
}

// RecordLoan creates a loan transaction and updates the person's net balance.
//
//   - loan_out: I lent money to them → their balance goes positive (they owe me)
//     Money leaves my account (like an expense from my perspective).
//   - loan_in: I borrowed from them → their balance goes negative (I owe them)
//     Money enters my account (like income from my perspective).
func (s *PersonService) RecordLoan(ctx context.Context, personID, accountID string, amount float64, currency models.Currency, txType models.TransactionType, note *string, date time.Time) (models.Transaction, error) {
	logutil.Log(ctx).Debug("recording loan", "person_id", personID, "type", txType, "currency", currency)
	if err := requirePositive(amount, "amount"); err != nil {
		return models.Transaction{}, err
	}
	if personID == "" || accountID == "" {
		return models.Transaction{}, fmt.Errorf("person_id and account_id are required")
	}
	if txType != models.TransactionTypeLoanOut && txType != models.TransactionTypeLoanIn {
		return models.Transaction{}, fmt.Errorf("type must be loan_out or loan_in")
	}

	date = defaultDate(date)

	dbTx, err := s.txRepo.BeginTx(ctx)
	if err != nil {
		return models.Transaction{}, fmt.Errorf("beginning transaction: %w", err)
	}
	defer dbTx.Rollback()

	// Compute balance deltas before creating the transaction
	var accountDelta, personDelta float64
	if txType == models.TransactionTypeLoanOut {
		// I lent money → money leaves my account, they owe me
		accountDelta = -amount
		personDelta = amount
	} else {
		// I borrowed → money enters my account, I owe them
		accountDelta = amount
		personDelta = -amount
	}

	tx := models.Transaction{
		Type:         txType,
		Amount:       amount,
		Currency:     currency,
		AccountID:    accountID,
		PersonID:     &personID,
		Note:         note,
		Date:         date,
		BalanceDelta: accountDelta,
	}

	created, err := s.txRepo.CreateTx(ctx, dbTx, tx)
	if err != nil {
		return models.Transaction{}, err
	}

	if err := s.txRepo.UpdateBalanceTx(ctx, dbTx, accountID, accountDelta); err != nil {
		return models.Transaction{}, fmt.Errorf("updating account balance: %w", err)
	}
	if err := s.personRepo.UpdateNetBalanceTx(ctx, dbTx, personID, personDelta, currency); err != nil {
		return models.Transaction{}, fmt.Errorf("updating person balance: %w", err)
	}

	if err := dbTx.Commit(); err != nil {
		return models.Transaction{}, fmt.Errorf("committing: %w", err)
	}

	logutil.LogEvent(ctx, "person.loan_recorded", "type", string(txType), "currency", string(currency))
	return created, nil
}

// RecordRepayment records a loan repayment and adjusts the person's net balance.
//
// Direction is determined by the current net_balance:
//   - Positive net_balance (they owe me): they're paying me back → money enters my account
//   - Negative net_balance (I owe them): I'm paying them back → money leaves my account
func (s *PersonService) RecordRepayment(ctx context.Context, personID, accountID string, amount float64, currency models.Currency, note *string, date time.Time) (models.Transaction, error) {
	logutil.Log(ctx).Debug("recording repayment", "person_id", personID, "currency", currency)
	if err := requirePositive(amount, "amount"); err != nil {
		return models.Transaction{}, err
	}
	if personID == "" || accountID == "" {
		return models.Transaction{}, fmt.Errorf("person_id and account_id are required")
	}

	person, err := s.personRepo.GetByID(ctx, personID)
	if err != nil {
		return models.Transaction{}, fmt.Errorf("person not found: %w", err)
	}

	date = defaultDate(date)

	dbTx, err := s.txRepo.BeginTx(ctx)
	if err != nil {
		return models.Transaction{}, fmt.Errorf("beginning transaction: %w", err)
	}
	defer dbTx.Rollback()

	// Determine direction based on who owes whom in this specific currency
	var relevantBalance float64
	if currency == models.CurrencyUSD {
		relevantBalance = person.NetBalanceUSD
	} else {
		relevantBalance = person.NetBalanceEGP
	}

	var accountDelta, personDelta float64
	if relevantBalance > 0 {
		// They owe me in this currency → they're paying back → money enters my account
		accountDelta = amount
		personDelta = -amount
	} else {
		// I owe them in this currency → I'm paying back → money leaves my account
		accountDelta = -amount
		personDelta = amount
	}

	tx := models.Transaction{
		Type:         models.TransactionTypeLoanRepayment,
		Amount:       amount,
		Currency:     currency,
		AccountID:    accountID,
		PersonID:     &personID,
		Note:         note,
		Date:         date,
		BalanceDelta: accountDelta,
	}

	created, err := s.txRepo.CreateTx(ctx, dbTx, tx)
	if err != nil {
		return models.Transaction{}, err
	}

	if err := s.txRepo.UpdateBalanceTx(ctx, dbTx, accountID, accountDelta); err != nil {
		return models.Transaction{}, fmt.Errorf("updating account balance: %w", err)
	}
	if err := s.personRepo.UpdateNetBalanceTx(ctx, dbTx, personID, personDelta, currency); err != nil {
		return models.Transaction{}, fmt.Errorf("updating person balance: %w", err)
	}

	if err := dbTx.Commit(); err != nil {
		return models.Transaction{}, fmt.Errorf("committing repayment: %w", err)
	}

	logutil.LogEvent(ctx, "person.repayment_recorded", "currency", string(currency))
	return created, nil
}

// CurrencyDebt holds per-currency debt totals for a person.
type CurrencyDebt struct {
	Currency      models.Currency
	TotalLent     float64 // sum of loan_out amounts in this currency
	TotalBorrowed float64 // sum of loan_in amounts in this currency
	TotalRepaid   float64 // sum of loan_repayment amounts in this currency
	NetBalance    float64 // current balance in this currency
	ProgressPct   float64 // 0–100 payoff progress for this currency
}

// DebtSummary holds computed data for a person's debt/loan detail page.
// It provides the raw data for the person-detail.html template:
// loan history, repayment progress, and projected payoff date.
//
// This is a ViewModel/DTO — a read-only aggregation of data for display.
// Not stored in the database; computed on each request.
// Like Laravel's API Resource or Django's serializer output.
type DebtSummary struct {
	Person        models.Person
	Transactions  []models.Transaction // loan + repayment history
	ByCurrency    []CurrencyDebt       // per-currency breakdown
	TotalLent     float64              // sum of loan_out amounts across all currencies
	TotalBorrowed float64              // sum of loan_in amounts across all currencies
	TotalRepaid   float64              // sum of loan_repayment amounts across all currencies
	ProgressPct   float64              // 0–100 payoff progress (aggregate)
	// Projected payoff: estimated date when debt will be fully repaid.
	// Based on average repayment frequency. Zero if no repayments yet.
	ProjectedPayoff time.Time
}

// GetDebtSummary computes the full debt/loan summary for a person.
// Used by the person detail page to show progress + projection.
//
// This method demonstrates the AGGREGATION pattern: it loads raw transaction data,
// then computes derived metrics (totals, percentages, projections) in Go code.
// The projection uses a simple linear model: average repayment rate x remaining debt.
//
// In Laravel, you might compute these aggregates with Eloquent's sum(), count(),
// and Collection methods. In Go, we iterate manually — more verbose but explicit.
func (s *PersonService) GetDebtSummary(ctx context.Context, personID string) (DebtSummary, error) {
	person, err := s.personRepo.GetByID(ctx, personID)
	if err != nil {
		return DebtSummary{}, fmt.Errorf("person not found: %w", err)
	}

	txns, err := s.txRepo.GetByPersonID(ctx, personID, 200)
	if err != nil {
		return DebtSummary{}, fmt.Errorf("loading transactions: %w", err)
	}

	summary := DebtSummary{
		Person:       person,
		Transactions: txns,
	}

	// Per-currency tallies
	currencyMap := make(map[models.Currency]*CurrencyDebt)

	// Tally up loan_out, loan_in, and repayment amounts — aggregate + per-currency
	var repaymentDates []time.Time
	for _, tx := range txns {
		cur := tx.Currency
		cd, ok := currencyMap[cur]
		if !ok {
			cd = &CurrencyDebt{Currency: cur}
			currencyMap[cur] = cd
		}

		switch tx.Type {
		case models.TransactionTypeLoanOut:
			summary.TotalLent += tx.Amount
			cd.TotalLent += tx.Amount
		case models.TransactionTypeLoanIn:
			summary.TotalBorrowed += tx.Amount
			cd.TotalBorrowed += tx.Amount
		case models.TransactionTypeLoanRepayment:
			summary.TotalRepaid += tx.Amount
			cd.TotalRepaid += tx.Amount
			repaymentDates = append(repaymentDates, tx.Date)
		}
	}

	// Compute per-currency progress and net balances
	for cur, cd := range currencyMap {
		if cur == models.CurrencyUSD {
			cd.NetBalance = person.NetBalanceUSD
		} else {
			cd.NetBalance = person.NetBalanceEGP
		}
		totalDebt := cd.TotalLent + cd.TotalBorrowed
		if totalDebt > 0 {
			cd.ProgressPct = (cd.TotalRepaid / totalDebt) * 100
			if cd.ProgressPct > 100 {
				cd.ProgressPct = 100
			}
		}
	}

	// Build ordered slice: EGP first, then USD
	if cd, ok := currencyMap[models.CurrencyEGP]; ok {
		summary.ByCurrency = append(summary.ByCurrency, *cd)
	}
	if cd, ok := currencyMap[models.CurrencyUSD]; ok {
		summary.ByCurrency = append(summary.ByCurrency, *cd)
	}

	// Aggregate progress
	totalDebt := summary.TotalLent + summary.TotalBorrowed
	if totalDebt > 0 {
		summary.ProgressPct = (summary.TotalRepaid / totalDebt) * 100
		if summary.ProgressPct > 100 {
			summary.ProgressPct = 100
		}
	}

	// Projected payoff: average repayment interval × remaining balance.
	// Uses the legacy NetBalance (sum of both currencies) for projection.
	remaining := abs(person.NetBalanceEGP) + abs(person.NetBalanceUSD)
	if len(repaymentDates) >= 2 && remaining > 0 {
		avgRepayment := summary.TotalRepaid / float64(len(repaymentDates))
		if avgRepayment > 0 {
			// repaymentDates are sorted DESC (newest first)
			first := repaymentDates[len(repaymentDates)-1]
			last := repaymentDates[0]
			totalDays := last.Sub(first).Hours() / 24
			if totalDays > 0 {
				avgIntervalDays := totalDays / float64(len(repaymentDates)-1)
				paymentsNeeded := remaining / avgRepayment
				daysToPayoff := paymentsNeeded * avgIntervalDays
				summary.ProjectedPayoff = time.Now().AddDate(0, 0, int(daysToPayoff))
			}
		}
	}

	return summary, nil
}

// GetPersonTransactions returns transactions for a specific person.
func (s *PersonService) GetPersonTransactions(ctx context.Context, personID string, limit int) ([]models.Transaction, error) {
	return s.txRepo.GetByPersonID(ctx, personID, limit)
}
