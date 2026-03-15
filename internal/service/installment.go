// Package service — InstallmentService handles installment plan logic.
//
// Installment plans track purchases split into monthly payments (like TRU EPP —
// Egypt's Easy Payment Plan for credit cards). A plan has a total amount, number
// of installments, and tracks how many are remaining.
//
// Laravel analogy: Like an InstallmentService that creates expense transactions
// for each payment. Similar to a subscription billing service but for fixed-length
// payment plans. Uses another service (TransactionService) for creating the actual
// expense records — service-to-service dependency.
//
// Django analogy: Like an installments/services.py module that coordinates between
// the InstallmentPlan model and the transaction creation logic.
//
// Design note: RecordPayment creates an expense transaction via TransactionService,
// then decrements the remaining count. If the transaction fails (e.g., would exceed
// credit limit), the payment is not recorded.
package service

import (
	"context"
	"fmt"

	"github.com/ahmedelsamadisi/clearmoney/internal/logutil"
	"github.com/ahmedelsamadisi/clearmoney/internal/models"
	"github.com/ahmedelsamadisi/clearmoney/internal/repository"
)

// InstallmentService depends on a repo for plan CRUD and TransactionService for
// creating expense transactions on payment. This is service-to-service composition.
type InstallmentService struct {
	repo  *repository.InstallmentRepo
	txSvc *TransactionService // used to create expense transactions on RecordPayment
}

func NewInstallmentService(repo *repository.InstallmentRepo, txSvc *TransactionService) *InstallmentService {
	return &InstallmentService{repo: repo, txSvc: txSvc}
}

// Create adds a new installment plan.
func (s *InstallmentService) Create(ctx context.Context, plan models.InstallmentPlan) (models.InstallmentPlan, error) {
	if plan.Description == "" {
		return models.InstallmentPlan{}, fmt.Errorf("description is required")
	}
	if plan.TotalAmount <= 0 {
		return models.InstallmentPlan{}, fmt.Errorf("total_amount must be positive")
	}
	if plan.NumInstallments <= 0 {
		return models.InstallmentPlan{}, fmt.Errorf("num_installments must be positive")
	}
	if plan.AccountID == "" {
		return models.InstallmentPlan{}, fmt.Errorf("account_id is required")
	}

	// Auto-compute monthly amount if not set
	if plan.MonthlyAmount <= 0 {
		plan.MonthlyAmount = plan.TotalAmount / float64(plan.NumInstallments)
	}
	// Set remaining = total on creation
	plan.RemainingInstallments = plan.NumInstallments

	created, err := s.repo.Create(ctx, plan)
	if err != nil {
		return models.InstallmentPlan{}, err
	}
	logutil.LogEvent(ctx, "installment.created", "account_id", created.AccountID)
	return created, nil
}

// GetAll returns all installment plans.
func (s *InstallmentService) GetAll(ctx context.Context) ([]models.InstallmentPlan, error) {
	return s.repo.GetAll(ctx)
}

// RecordPayment decrements remaining installments and creates an expense transaction.
// This method calls TransactionService.Create() to create the expense, which handles
// atomic balance updates. Then it decrements the remaining count via the repo.
//
// Note: plan.PaidInstallments() is a computed method on the model — like a Laravel
// accessor or Django @property. It returns NumInstallments - RemainingInstallments.
func (s *InstallmentService) RecordPayment(ctx context.Context, planID string) error {
	plan, err := s.repo.GetByID(ctx, planID)
	if err != nil {
		return err
	}
	if plan.RemainingInstallments <= 0 {
		return fmt.Errorf("plan already fully paid")
	}

	// Create expense transaction for the monthly amount
	note := fmt.Sprintf("Installment %d/%d: %s", plan.PaidInstallments()+1, plan.NumInstallments, plan.Description)
	tx := models.Transaction{
		Type:      models.TransactionTypeExpense,
		Amount:    plan.MonthlyAmount,
		Currency:  models.CurrencyEGP,
		AccountID: plan.AccountID,
		Note:      &note,
	}
	if _, _, err := s.txSvc.Create(ctx, tx); err != nil {
		return fmt.Errorf("creating payment transaction: %w", err)
	}

	if err := s.repo.RecordPayment(ctx, planID); err != nil {
		return err
	}
	logutil.LogEvent(ctx, "installment.payment_recorded", "id", planID)
	return nil
}

// Delete removes an installment plan.
func (s *InstallmentService) Delete(ctx context.Context, id string) error {
	if err := s.repo.Delete(ctx, id); err != nil {
		return err
	}
	logutil.LogEvent(ctx, "installment.deleted", "id", id)
	return nil
}
