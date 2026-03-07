// Package service — InstallmentService handles installment plan logic.
// Installment plans track purchases split into monthly payments (like TRU EPP).
package service

import (
	"context"
	"fmt"

	"github.com/ahmedelsamadisi/clearmoney/internal/models"
	"github.com/ahmedelsamadisi/clearmoney/internal/repository"
)

type InstallmentService struct {
	repo    *repository.InstallmentRepo
	txSvc   *TransactionService
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

	return s.repo.Create(ctx, plan)
}

// GetAll returns all installment plans.
func (s *InstallmentService) GetAll(ctx context.Context) ([]models.InstallmentPlan, error) {
	return s.repo.GetAll(ctx)
}

// RecordPayment decrements remaining installments and creates an expense transaction.
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

	return s.repo.RecordPayment(ctx, planID)
}

// Delete removes an installment plan.
func (s *InstallmentService) Delete(ctx context.Context, id string) error {
	return s.repo.Delete(ctx, id)
}
