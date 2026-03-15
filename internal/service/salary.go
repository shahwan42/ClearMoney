// Package service — SalaryService handles the salary distribution wizard (S-3).
//
// The salary flow works like a multi-step wizard:
//   1. Confirm salary amount (USD)
//   2. Enter exchange rate → auto-calc EGP equivalent
//   3. Allocate to accounts/categories (pre-filled from last month)
//   4. Review and confirm → creates all transactions atomically
//
// Laravel analogy: Like a multi-step form wizard backed by a service class.
// Imagine a SalaryWizardController with step1/step2/step3/confirm actions,
// and a SalaryService.distribute() that creates all transactions in DB::transaction().
//
// Django analogy: Like a FormWizardView backed by a service function that uses
// transaction.atomic() to create income, exchange, and transfer transactions.
//
// This is the most transaction-heavy service: a single DistributeSalary() call can
// create 5+ transactions (1 income + 2 exchange + N*2 allocation transfers).
// All must succeed atomically or all roll back.
package service

import (
	"context"
	"fmt"
	"time"

	"github.com/ahmedelsamadisi/clearmoney/internal/logutil"
	"github.com/ahmedelsamadisi/clearmoney/internal/models"
	"github.com/ahmedelsamadisi/clearmoney/internal/repository"
)

// SalaryAllocation represents a single line item in the salary distribution.
// JSON struct tags (`json:"account_id"`) control serialization — like Laravel's
// $casts or Django REST Framework's field names. These are used when the wizard
// sends allocation data as JSON from the frontend.
type SalaryAllocation struct {
	AccountID string  `json:"account_id"`
	Amount    float64 `json:"amount"`
	Note      string  `json:"note"`
}

// SalaryDistribution holds all the data for a complete salary distribution.
type SalaryDistribution struct {
	SalaryUSD    float64            `json:"salary_usd"`
	ExchangeRate float64            `json:"exchange_rate"`
	SalaryEGP    float64            `json:"salary_egp"`
	USDAccountID string             `json:"usd_account_id"`
	EGPAccountID string             `json:"egp_account_id"`
	Allocations  []SalaryAllocation `json:"allocations"`
	Date         time.Time          `json:"date"`
}

// SalaryService handles salary distribution logic.
type SalaryService struct {
	txRepo  *repository.TransactionRepo
	accRepo *repository.AccountRepo
}

func NewSalaryService(txRepo *repository.TransactionRepo, accRepo *repository.AccountRepo) *SalaryService {
	return &SalaryService{txRepo: txRepo, accRepo: accRepo}
}

// DistributeSalary creates all salary transactions atomically:
//   1. Income transaction on USD account (salary received)
//   2. Exchange from USD to EGP (two linked transactions + balance updates)
//   3. Allocation transfers from EGP account to target accounts (two linked tx per allocation)
//
// This demonstrates Go's explicit error handling at scale. Every DB operation
// returns an error that must be checked. In Laravel/Django, exceptions bubble up
// automatically. In Go, each error is handled explicitly — more verbose but you
// always know exactly what can fail and how.
//
// The pattern: `defer dbTx.Rollback()` is safe because Rollback() is a no-op
// after Commit(). So the flow is: begin → do work → commit (success) → defer Rollback (no-op).
// If any step fails: begin → do work → return error → defer Rollback (actual rollback).
func (s *SalaryService) DistributeSalary(ctx context.Context, dist SalaryDistribution) error {
	logutil.Log(ctx).Debug("distributing salary", "allocation_count", len(dist.Allocations))
	if err := requirePositive(dist.SalaryUSD, "salary amount"); err != nil {
		return err
	}
	if err := requirePositive(dist.ExchangeRate, "exchange rate"); err != nil {
		return err
	}
	if dist.USDAccountID == "" || dist.EGPAccountID == "" {
		return fmt.Errorf("USD and EGP account IDs are required")
	}

	dist.SalaryEGP = dist.SalaryUSD * dist.ExchangeRate

	dist.Date = defaultDate(dist.Date)

	// Validate allocations don't exceed salary
	var totalAlloc float64
	for _, a := range dist.Allocations {
		if a.Amount <= 0 {
			continue
		}
		totalAlloc += a.Amount
	}
	if totalAlloc > dist.SalaryEGP {
		return fmt.Errorf("allocations (%.2f) exceed salary (%.2f EGP)", totalAlloc, dist.SalaryEGP)
	}

	dbTx, err := s.txRepo.BeginTx(ctx)
	if err != nil {
		return fmt.Errorf("beginning transaction: %w", err)
	}
	defer dbTx.Rollback()

	// Step 1: Salary income on USD account
	salaryNote := "Salary"
	salaryTx := models.Transaction{
		Type:      models.TransactionTypeIncome,
		Amount:    dist.SalaryUSD,
		Currency:  models.CurrencyUSD,
		AccountID: dist.USDAccountID,
		Note:      &salaryNote,
		Date:      dist.Date,
	}
	_, err = s.txRepo.CreateTx(ctx, dbTx, salaryTx)
	if err != nil {
		return fmt.Errorf("creating salary income: %w", err)
	}
	if err := s.txRepo.UpdateBalanceTx(ctx, dbTx, dist.USDAccountID, dist.SalaryUSD); err != nil {
		return fmt.Errorf("crediting USD account: %w", err)
	}

	// Step 2: Exchange USD → EGP
	exchangeNote := "Salary exchange"
	rate := dist.ExchangeRate
	counterAmount := dist.SalaryEGP
	debit := models.Transaction{
		Type:          models.TransactionTypeExchange,
		Amount:        dist.SalaryUSD,
		Currency:      models.CurrencyUSD,
		AccountID:     dist.USDAccountID,
		CounterAccountID: &dist.EGPAccountID,
		ExchangeRate:  &rate,
		CounterAmount: &counterAmount,
		Note:          &exchangeNote,
		Date:          dist.Date,
	}
	createdDebit, err := s.txRepo.CreateTx(ctx, dbTx, debit)
	if err != nil {
		return fmt.Errorf("creating exchange debit: %w", err)
	}

	credit := models.Transaction{
		Type:          models.TransactionTypeExchange,
		Amount:        dist.SalaryEGP,
		Currency:      models.CurrencyEGP,
		AccountID:     dist.EGPAccountID,
		CounterAccountID: &dist.USDAccountID,
		ExchangeRate:  &rate,
		CounterAmount: &dist.SalaryUSD,
		Note:          &exchangeNote,
		Date:          dist.Date,
	}
	createdCredit, err := s.txRepo.CreateTx(ctx, dbTx, credit)
	if err != nil {
		return fmt.Errorf("creating exchange credit: %w", err)
	}

	if err := s.txRepo.LinkTransactionsTx(ctx, dbTx, createdDebit.ID, createdCredit.ID); err != nil {
		return fmt.Errorf("linking exchange: %w", err)
	}

	// Exchange balance: USD goes down, EGP goes up
	if err := s.txRepo.UpdateBalanceTx(ctx, dbTx, dist.USDAccountID, -dist.SalaryUSD); err != nil {
		return fmt.Errorf("debiting USD: %w", err)
	}
	if err := s.txRepo.UpdateBalanceTx(ctx, dbTx, dist.EGPAccountID, dist.SalaryEGP); err != nil {
		return fmt.Errorf("crediting EGP: %w", err)
	}

	// Step 3: Allocations (transfers from EGP account to target accounts)
	for _, alloc := range dist.Allocations {
		if alloc.Amount <= 0 || alloc.AccountID == "" || alloc.AccountID == dist.EGPAccountID {
			continue
		}

		allocNote := alloc.Note
		if allocNote == "" {
			allocNote = "Salary allocation"
		}
		transferDebit := models.Transaction{
			Type:             models.TransactionTypeTransfer,
			Amount:           alloc.Amount,
			Currency:         models.CurrencyEGP,
			AccountID:        dist.EGPAccountID,
			CounterAccountID: &alloc.AccountID,
			Note:             &allocNote,
			Date:             dist.Date,
		}
		createdTD, err := s.txRepo.CreateTx(ctx, dbTx, transferDebit)
		if err != nil {
			return fmt.Errorf("creating allocation debit: %w", err)
		}

		transferCredit := models.Transaction{
			Type:             models.TransactionTypeTransfer,
			Amount:           alloc.Amount,
			Currency:         models.CurrencyEGP,
			AccountID:        alloc.AccountID,
			CounterAccountID: &dist.EGPAccountID,
			Note:             &allocNote,
			Date:             dist.Date,
		}
		createdTC, err := s.txRepo.CreateTx(ctx, dbTx, transferCredit)
		if err != nil {
			return fmt.Errorf("creating allocation credit: %w", err)
		}

		if err := s.txRepo.LinkTransactionsTx(ctx, dbTx, createdTD.ID, createdTC.ID); err != nil {
			return fmt.Errorf("linking allocation: %w", err)
		}

		if err := s.txRepo.UpdateBalanceTx(ctx, dbTx, dist.EGPAccountID, -alloc.Amount); err != nil {
			return fmt.Errorf("debiting EGP: %w", err)
		}
		if err := s.txRepo.UpdateBalanceTx(ctx, dbTx, alloc.AccountID, alloc.Amount); err != nil {
			return fmt.Errorf("crediting allocation: %w", err)
		}
	}

	if err := dbTx.Commit(); err != nil {
		return err
	}
	logutil.LogEvent(ctx, "salary.distributed", "allocation_count", len(dist.Allocations))
	return nil
}
