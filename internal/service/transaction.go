package service

import (
	"context"
	"fmt"
	"time"

	"github.com/ahmedelsamadisi/clearmoney/internal/models"
	"github.com/ahmedelsamadisi/clearmoney/internal/repository"
)

// TransactionService handles the business logic for creating, modifying,
// and deleting transactions — including atomic balance updates.
//
// This is the most critical service: every transaction must update the
// associated account's balance atomically within a database transaction.
// If the insert succeeds but the balance update fails, everything rolls back.
//
// Think of it like Laravel's DB::transaction() wrapping the whole operation.
type TransactionService struct {
	txRepo   *repository.TransactionRepo
	accRepo  *repository.AccountRepo
	rateRepo *repository.ExchangeRateRepo
}

func NewTransactionService(txRepo *repository.TransactionRepo, accRepo *repository.AccountRepo) *TransactionService {
	return &TransactionService{txRepo: txRepo, accRepo: accRepo}
}

// SetExchangeRateRepo sets the exchange rate repository (optional dependency).
func (s *TransactionService) SetExchangeRateRepo(repo *repository.ExchangeRateRepo) {
	s.rateRepo = repo
}

// Create validates and creates a transaction, atomically updating the account balance.
//
// Balance impact by transaction type:
//   - expense:  balance -= amount (money goes out)
//   - income:   balance += amount (money comes in)
//
// Returns the created transaction and the new account balance.
func (s *TransactionService) Create(ctx context.Context, tx models.Transaction) (models.Transaction, float64, error) {
	if err := s.validateBasic(tx); err != nil {
		return models.Transaction{}, 0, err
	}

	// Calculate balance delta based on transaction type
	delta := s.balanceDelta(tx)

	// Credit card validation: check if expense would exceed credit limit
	if delta < 0 {
		acc, err := s.accRepo.GetByID(ctx, tx.AccountID)
		if err == nil && acc.IsCreditType() && acc.CreditLimit != nil {
			newBalance := acc.CurrentBalance + delta
			if newBalance < -*acc.CreditLimit {
				return models.Transaction{}, 0, fmt.Errorf(
					"would exceed credit limit (available: %.2f)", acc.AvailableCredit())
			}
		}
	}

	// Begin a database transaction (the SQL kind, not the financial kind!)
	dbTx, err := s.txRepo.BeginTx(ctx)
	if err != nil {
		return models.Transaction{}, 0, fmt.Errorf("beginning transaction: %w", err)
	}
	// defer Rollback is safe — it's a no-op if Commit was already called.
	defer dbTx.Rollback()

	// 1. Insert the transaction record
	created, err := s.txRepo.CreateTx(ctx, dbTx, tx)
	if err != nil {
		return models.Transaction{}, 0, err
	}

	// 2. Update the account balance atomically
	if err := s.txRepo.UpdateBalanceTx(ctx, dbTx, tx.AccountID, delta); err != nil {
		return models.Transaction{}, 0, fmt.Errorf("updating balance: %w", err)
	}

	// 3. Commit both operations
	if err := dbTx.Commit(); err != nil {
		return models.Transaction{}, 0, fmt.Errorf("committing transaction: %w", err)
	}

	// Fetch the updated balance to return to the caller
	acc, err := s.accRepo.GetByID(ctx, tx.AccountID)
	if err != nil {
		return created, 0, nil // transaction succeeded, just can't return balance
	}

	return created, acc.CurrentBalance, nil
}

// CreateTransfer creates a transfer between two accounts (same currency).
// Creates two linked transactions: debit from source, credit to destination.
// Both accounts' balances are updated atomically.
func (s *TransactionService) CreateTransfer(ctx context.Context, sourceAccountID, destAccountID string, amount float64, currency models.Currency, note *string, date time.Time) (models.Transaction, models.Transaction, error) {
	if amount <= 0 {
		return models.Transaction{}, models.Transaction{}, fmt.Errorf("amount must be positive")
	}
	if sourceAccountID == "" || destAccountID == "" {
		return models.Transaction{}, models.Transaction{}, fmt.Errorf("both source and destination account_id required")
	}
	if sourceAccountID == destAccountID {
		return models.Transaction{}, models.Transaction{}, fmt.Errorf("cannot transfer to the same account")
	}

	// Verify same currency
	srcAcc, err := s.accRepo.GetByID(ctx, sourceAccountID)
	if err != nil {
		return models.Transaction{}, models.Transaction{}, fmt.Errorf("source account not found: %w", err)
	}
	destAcc, err := s.accRepo.GetByID(ctx, destAccountID)
	if err != nil {
		return models.Transaction{}, models.Transaction{}, fmt.Errorf("destination account not found: %w", err)
	}
	if srcAcc.Currency != destAcc.Currency {
		return models.Transaction{}, models.Transaction{}, fmt.Errorf("transfer requires same currency; use exchange for cross-currency")
	}

	if date.IsZero() {
		date = time.Now()
	}

	dbTx, err := s.txRepo.BeginTx(ctx)
	if err != nil {
		return models.Transaction{}, models.Transaction{}, fmt.Errorf("beginning transaction: %w", err)
	}
	defer dbTx.Rollback()

	// Create debit leg (source)
	debit := models.Transaction{
		Type:             models.TransactionTypeTransfer,
		Amount:           amount,
		Currency:         currency,
		AccountID:        sourceAccountID,
		CounterAccountID: &destAccountID,
		Note:             note,
		Date:             date,
	}
	createdDebit, err := s.txRepo.CreateTx(ctx, dbTx, debit)
	if err != nil {
		return models.Transaction{}, models.Transaction{}, fmt.Errorf("creating debit: %w", err)
	}

	// Create credit leg (destination)
	credit := models.Transaction{
		Type:             models.TransactionTypeTransfer,
		Amount:           amount,
		Currency:         currency,
		AccountID:        destAccountID,
		CounterAccountID: &sourceAccountID,
		Note:             note,
		Date:             date,
	}
	createdCredit, err := s.txRepo.CreateTx(ctx, dbTx, credit)
	if err != nil {
		return models.Transaction{}, models.Transaction{}, fmt.Errorf("creating credit: %w", err)
	}

	// Link the two transactions
	if err := s.txRepo.LinkTransactionsTx(ctx, dbTx, createdDebit.ID, createdCredit.ID); err != nil {
		return models.Transaction{}, models.Transaction{}, err
	}

	// Update balances: source loses, destination gains
	if err := s.txRepo.UpdateBalanceTx(ctx, dbTx, sourceAccountID, -amount); err != nil {
		return models.Transaction{}, models.Transaction{}, fmt.Errorf("debiting source: %w", err)
	}
	if err := s.txRepo.UpdateBalanceTx(ctx, dbTx, destAccountID, amount); err != nil {
		return models.Transaction{}, models.Transaction{}, fmt.Errorf("crediting destination: %w", err)
	}

	if err := dbTx.Commit(); err != nil {
		return models.Transaction{}, models.Transaction{}, fmt.Errorf("committing: %w", err)
	}

	// Set linked IDs on the returned structs (DB was updated by LinkTransactionsTx)
	createdDebit.LinkedTransactionID = &createdCredit.ID
	createdCredit.LinkedTransactionID = &createdDebit.ID

	return createdDebit, createdCredit, nil
}

// ExchangeParams holds the parameters for a currency exchange.
// Any two of Amount, Rate, CounterAmount must be provided; the third is auto-calculated.
type ExchangeParams struct {
	SourceAccountID string
	DestAccountID   string
	Amount          *float64 // source amount (e.g., USD)
	Rate            *float64 // exchange rate (e.g., 50.5 EGP per USD)
	CounterAmount   *float64 // destination amount (e.g., EGP)
	Note            *string
	Date            time.Time
}

// CreateExchange creates a currency exchange between two accounts in different currencies.
// Creates two linked transactions (debit in source currency, credit in dest currency).
// Logs the exchange rate.
func (s *TransactionService) CreateExchange(ctx context.Context, p ExchangeParams) (models.Transaction, models.Transaction, error) {
	if p.SourceAccountID == "" || p.DestAccountID == "" {
		return models.Transaction{}, models.Transaction{}, fmt.Errorf("both source and destination account_id required")
	}
	if p.SourceAccountID == p.DestAccountID {
		return models.Transaction{}, models.Transaction{}, fmt.Errorf("cannot exchange to the same account")
	}

	// Verify different currencies
	srcAcc, err := s.accRepo.GetByID(ctx, p.SourceAccountID)
	if err != nil {
		return models.Transaction{}, models.Transaction{}, fmt.Errorf("source account not found: %w", err)
	}
	destAcc, err := s.accRepo.GetByID(ctx, p.DestAccountID)
	if err != nil {
		return models.Transaction{}, models.Transaction{}, fmt.Errorf("destination account not found: %w", err)
	}
	if srcAcc.Currency == destAcc.Currency {
		return models.Transaction{}, models.Transaction{}, fmt.Errorf("exchange requires different currencies; use transfer for same currency")
	}

	// Auto-calculate the missing field from the other two
	amount, rate, counterAmount, err := resolveExchangeFields(p.Amount, p.Rate, p.CounterAmount)
	if err != nil {
		return models.Transaction{}, models.Transaction{}, err
	}

	if p.Date.IsZero() {
		p.Date = time.Now()
	}

	dbTx, err := s.txRepo.BeginTx(ctx)
	if err != nil {
		return models.Transaction{}, models.Transaction{}, fmt.Errorf("beginning transaction: %w", err)
	}
	defer dbTx.Rollback()

	// Debit leg (source currency, e.g., USD out)
	debit := models.Transaction{
		Type:             models.TransactionTypeExchange,
		Amount:           amount,
		Currency:         srcAcc.Currency,
		AccountID:        p.SourceAccountID,
		CounterAccountID: &p.DestAccountID,
		ExchangeRate:     &rate,
		CounterAmount:    &counterAmount,
		Note:             p.Note,
		Date:             p.Date,
	}
	createdDebit, err := s.txRepo.CreateTx(ctx, dbTx, debit)
	if err != nil {
		return models.Transaction{}, models.Transaction{}, fmt.Errorf("creating debit: %w", err)
	}

	// Credit leg (dest currency, e.g., EGP in)
	credit := models.Transaction{
		Type:             models.TransactionTypeExchange,
		Amount:           counterAmount,
		Currency:         destAcc.Currency,
		AccountID:        p.DestAccountID,
		CounterAccountID: &p.SourceAccountID,
		ExchangeRate:     &rate,
		CounterAmount:    &amount,
		Note:             p.Note,
		Date:             p.Date,
	}
	createdCredit, err := s.txRepo.CreateTx(ctx, dbTx, credit)
	if err != nil {
		return models.Transaction{}, models.Transaction{}, fmt.Errorf("creating credit: %w", err)
	}

	// Link them
	if err := s.txRepo.LinkTransactionsTx(ctx, dbTx, createdDebit.ID, createdCredit.ID); err != nil {
		return models.Transaction{}, models.Transaction{}, err
	}

	// Update balances
	if err := s.txRepo.UpdateBalanceTx(ctx, dbTx, p.SourceAccountID, -amount); err != nil {
		return models.Transaction{}, models.Transaction{}, fmt.Errorf("debiting source: %w", err)
	}
	if err := s.txRepo.UpdateBalanceTx(ctx, dbTx, p.DestAccountID, counterAmount); err != nil {
		return models.Transaction{}, models.Transaction{}, fmt.Errorf("crediting destination: %w", err)
	}

	if err := dbTx.Commit(); err != nil {
		return models.Transaction{}, models.Transaction{}, fmt.Errorf("committing: %w", err)
	}

	// Log the exchange rate (non-critical, don't fail if it errors)
	if s.rateRepo != nil {
		source := fmt.Sprintf("%s/%s", srcAcc.Currency, destAcc.Currency)
		s.rateRepo.Log(ctx, p.Date, rate, &source, p.Note)
	}

	createdDebit.LinkedTransactionID = &createdCredit.ID
	createdCredit.LinkedTransactionID = &createdDebit.ID

	return createdDebit, createdCredit, nil
}

// resolveExchangeFields computes the missing field from two provided values.
// amount * rate = counterAmount
func resolveExchangeFields(amount, rate, counterAmount *float64) (float64, float64, float64, error) {
	count := 0
	if amount != nil && *amount > 0 {
		count++
	}
	if rate != nil && *rate > 0 {
		count++
	}
	if counterAmount != nil && *counterAmount > 0 {
		count++
	}
	if count < 2 {
		return 0, 0, 0, fmt.Errorf("provide at least two of: amount, rate, counter_amount")
	}

	if amount != nil && rate != nil && *amount > 0 && *rate > 0 {
		return *amount, *rate, *amount * *rate, nil
	}
	if amount != nil && counterAmount != nil && *amount > 0 && *counterAmount > 0 {
		return *amount, *counterAmount / *amount, *counterAmount, nil
	}
	if rate != nil && counterAmount != nil && *rate > 0 && *counterAmount > 0 {
		return *counterAmount / *rate, *rate, *counterAmount, nil
	}
	return 0, 0, 0, fmt.Errorf("invalid exchange parameters")
}

// Update modifies a transaction and recalculates the balance delta.
// The balance adjustment is: reverse old delta + apply new delta.
func (s *TransactionService) Update(ctx context.Context, updated models.Transaction) (models.Transaction, float64, error) {
	if err := s.validateBasic(updated); err != nil {
		return models.Transaction{}, 0, err
	}

	// Get the old transaction to calculate the balance diff
	old, err := s.txRepo.GetByID(ctx, updated.ID)
	if err != nil {
		return models.Transaction{}, 0, err
	}

	oldDelta := s.balanceDelta(old)
	newDelta := s.balanceDelta(updated)
	balanceAdjustment := newDelta - oldDelta // net change to apply

	dbTx, err := s.txRepo.BeginTx(ctx)
	if err != nil {
		return models.Transaction{}, 0, fmt.Errorf("beginning transaction: %w", err)
	}
	defer dbTx.Rollback()

	result, err := s.txRepo.UpdateTx(ctx, dbTx, updated)
	if err != nil {
		return models.Transaction{}, 0, err
	}

	if balanceAdjustment != 0 {
		if err := s.txRepo.UpdateBalanceTx(ctx, dbTx, old.AccountID, balanceAdjustment); err != nil {
			return models.Transaction{}, 0, fmt.Errorf("adjusting balance: %w", err)
		}
	}

	if err := dbTx.Commit(); err != nil {
		return models.Transaction{}, 0, fmt.Errorf("committing: %w", err)
	}

	acc, err := s.accRepo.GetByID(ctx, old.AccountID)
	if err != nil {
		return result, 0, nil
	}
	return result, acc.CurrentBalance, nil
}

// Delete removes a transaction and reverses its balance impact.
// For linked transactions (transfers/exchanges), both legs are deleted.
func (s *TransactionService) Delete(ctx context.Context, id string) error {
	tx, err := s.txRepo.GetByID(ctx, id)
	if err != nil {
		return err
	}

	dbTx, err := s.txRepo.BeginTx(ctx)
	if err != nil {
		return fmt.Errorf("beginning transaction: %w", err)
	}
	defer dbTx.Rollback()

	// Delete this transaction
	if err := s.txRepo.DeleteTx(ctx, dbTx, id); err != nil {
		return err
	}

	isLinked := tx.LinkedTransactionID != nil && *tx.LinkedTransactionID != ""

	if isLinked {
		// Transfer/exchange: this leg's account was debited, linked leg's was credited.
		// Reverse: add amount back to this account, subtract from linked account.
		if err := s.txRepo.UpdateBalanceTx(ctx, dbTx, tx.AccountID, tx.Amount); err != nil {
			return fmt.Errorf("reversing balance: %w", err)
		}

		linked, err := s.txRepo.GetByID(ctx, *tx.LinkedTransactionID)
		if err == nil {
			if err := s.txRepo.DeleteTx(ctx, dbTx, linked.ID); err != nil {
				return fmt.Errorf("deleting linked: %w", err)
			}
			if err := s.txRepo.UpdateBalanceTx(ctx, dbTx, linked.AccountID, -linked.Amount); err != nil {
				return fmt.Errorf("reversing linked balance: %w", err)
			}
		}
	} else {
		// Simple expense/income reversal
		reverseDelta := -s.balanceDelta(tx)
		if err := s.txRepo.UpdateBalanceTx(ctx, dbTx, tx.AccountID, reverseDelta); err != nil {
			return fmt.Errorf("reversing balance: %w", err)
		}
	}

	return dbTx.Commit()
}

func (s *TransactionService) GetByID(ctx context.Context, id string) (models.Transaction, error) {
	return s.txRepo.GetByID(ctx, id)
}

func (s *TransactionService) GetRecent(ctx context.Context, limit int) ([]models.Transaction, error) {
	if limit <= 0 {
		limit = 15
	}
	return s.txRepo.GetRecent(ctx, limit)
}

func (s *TransactionService) GetByAccount(ctx context.Context, accountID string, limit int) ([]models.Transaction, error) {
	if limit <= 0 {
		limit = 50
	}
	return s.txRepo.GetByAccount(ctx, accountID, limit)
}

// balanceDelta calculates how a transaction affects its account's balance.
// For expense/income only. Transfer/exchange deltas are handled directly
// in CreateTransfer/Delete since they involve two accounts.
func (s *TransactionService) balanceDelta(tx models.Transaction) float64 {
	switch tx.Type {
	case models.TransactionTypeExpense:
		return -tx.Amount
	case models.TransactionTypeIncome:
		return tx.Amount
	default:
		return 0 // transfers/exchanges handle their own deltas
	}
}

// GetFiltered retrieves transactions matching the given filters.
func (s *TransactionService) GetFiltered(ctx context.Context, f repository.TransactionFilter) ([]models.Transaction, error) {
	if f.Limit <= 0 {
		f.Limit = 50
	}
	return s.txRepo.GetFiltered(ctx, f)
}

func (s *TransactionService) validateBasic(tx models.Transaction) error {
	if tx.Amount <= 0 {
		return fmt.Errorf("amount must be positive")
	}
	if tx.AccountID == "" {
		return fmt.Errorf("account_id is required")
	}
	if tx.Type == "" {
		return fmt.Errorf("transaction type is required")
	}
	if tx.Currency == "" {
		return fmt.Errorf("currency is required")
	}
	return nil
}
