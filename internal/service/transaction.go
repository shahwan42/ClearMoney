package service

import (
	"context"
	"fmt"

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
	txRepo  *repository.TransactionRepo
	accRepo *repository.AccountRepo
}

func NewTransactionService(txRepo *repository.TransactionRepo, accRepo *repository.AccountRepo) *TransactionService {
	return &TransactionService{txRepo: txRepo, accRepo: accRepo}
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

// Delete removes a transaction and reverses its balance impact.
func (s *TransactionService) Delete(ctx context.Context, id string) error {
	// Get the transaction to know the reversal amount
	tx, err := s.txRepo.GetByID(ctx, id)
	if err != nil {
		return err
	}

	// Reverse the balance delta
	reverseDelta := -s.balanceDelta(tx)

	dbTx, err := s.txRepo.BeginTx(ctx)
	if err != nil {
		return fmt.Errorf("beginning transaction: %w", err)
	}
	defer dbTx.Rollback()

	if err := s.txRepo.DeleteTx(ctx, dbTx, id); err != nil {
		return err
	}

	if err := s.txRepo.UpdateBalanceTx(ctx, dbTx, tx.AccountID, reverseDelta); err != nil {
		return fmt.Errorf("reversing balance: %w", err)
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

// balanceDelta calculates how a transaction affects the account balance.
func (s *TransactionService) balanceDelta(tx models.Transaction) float64 {
	switch tx.Type {
	case models.TransactionTypeExpense:
		return -tx.Amount // expenses decrease balance
	case models.TransactionTypeIncome:
		return tx.Amount // income increases balance
	default:
		return 0 // transfers/exchanges handled separately
	}
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
