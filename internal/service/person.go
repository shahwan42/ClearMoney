// Package service — PersonService handles business logic for the people ledger.
// Tracks lending and borrowing: "I lent X to Y" / "I borrowed from Y".
//
// Net balance convention:
//   - Positive: they owe me (I lent them money)
//   - Negative: I owe them (I borrowed from them)
package service

import (
	"context"
	"fmt"
	"time"

	"github.com/ahmedelsamadisi/clearmoney/internal/models"
	"github.com/ahmedelsamadisi/clearmoney/internal/repository"
)

// PersonService handles person CRUD and loan/repayment logic.
type PersonService struct {
	personRepo *repository.PersonRepo
	txRepo     *repository.TransactionRepo
}

func NewPersonService(personRepo *repository.PersonRepo, txRepo *repository.TransactionRepo) *PersonService {
	return &PersonService{personRepo: personRepo, txRepo: txRepo}
}

func (s *PersonService) Create(ctx context.Context, p models.Person) (models.Person, error) {
	if p.Name == "" {
		return models.Person{}, fmt.Errorf("name is required")
	}
	return s.personRepo.Create(ctx, p)
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
	if amount <= 0 {
		return models.Transaction{}, fmt.Errorf("amount must be positive")
	}
	if personID == "" || accountID == "" {
		return models.Transaction{}, fmt.Errorf("person_id and account_id are required")
	}
	if txType != models.TransactionTypeLoanOut && txType != models.TransactionTypeLoanIn {
		return models.Transaction{}, fmt.Errorf("type must be loan_out or loan_in")
	}

	if date.IsZero() {
		date = time.Now()
	}

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
	if err := s.personRepo.UpdateNetBalanceTx(ctx, dbTx, personID, personDelta); err != nil {
		return models.Transaction{}, fmt.Errorf("updating person balance: %w", err)
	}

	if err := dbTx.Commit(); err != nil {
		return models.Transaction{}, fmt.Errorf("committing: %w", err)
	}

	return created, nil
}

// RecordRepayment records a loan repayment and adjusts the person's net balance.
//
// Direction is determined by the current net_balance:
//   - Positive net_balance (they owe me): they're paying me back → money enters my account
//   - Negative net_balance (I owe them): I'm paying them back → money leaves my account
func (s *PersonService) RecordRepayment(ctx context.Context, personID, accountID string, amount float64, currency models.Currency, note *string, date time.Time) (models.Transaction, error) {
	if amount <= 0 {
		return models.Transaction{}, fmt.Errorf("amount must be positive")
	}
	if personID == "" || accountID == "" {
		return models.Transaction{}, fmt.Errorf("person_id and account_id are required")
	}

	person, err := s.personRepo.GetByID(ctx, personID)
	if err != nil {
		return models.Transaction{}, fmt.Errorf("person not found: %w", err)
	}

	if date.IsZero() {
		date = time.Now()
	}

	dbTx, err := s.txRepo.BeginTx(ctx)
	if err != nil {
		return models.Transaction{}, fmt.Errorf("beginning transaction: %w", err)
	}
	defer dbTx.Rollback()

	// Determine direction based on who owes whom
	var accountDelta, personDelta float64
	if person.NetBalance > 0 {
		// They owe me → they're paying back → money enters my account
		accountDelta = amount
		personDelta = -amount
	} else {
		// I owe them → I'm paying back → money leaves my account
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
	if err := s.personRepo.UpdateNetBalanceTx(ctx, dbTx, personID, personDelta); err != nil {
		return models.Transaction{}, fmt.Errorf("updating person balance: %w", err)
	}

	if err := dbTx.Commit(); err != nil {
		return models.Transaction{}, fmt.Errorf("committing: %w", err)
	}

	return created, nil
}
