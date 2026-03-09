// Package service — virtual_fund.go provides business logic for virtual funds.
//
// Virtual funds are user-defined savings buckets. Unlike the old is_building_fund
// flag (which was a single hardcoded boolean), virtual funds let users create
// any number of goals: "Emergency Fund", "Vacation", "New Car", etc.
//
// In Laravel terms, this is like a Service class that sits between the Controller
// and the Eloquent model. In Django, it's similar to a service module.
package service

import (
	"context"
	"fmt"

	"github.com/ahmedelsamadisi/clearmoney/internal/models"
	"github.com/ahmedelsamadisi/clearmoney/internal/repository"
)

// VirtualFundService handles business logic for virtual funds.
type VirtualFundService struct {
	fundRepo *repository.VirtualFundRepo
}

func NewVirtualFundService(fundRepo *repository.VirtualFundRepo) *VirtualFundService {
	return &VirtualFundService{fundRepo: fundRepo}
}

// GetAll returns all active (non-archived) virtual funds.
func (s *VirtualFundService) GetAll(ctx context.Context) ([]models.VirtualFund, error) {
	return s.fundRepo.GetAll(ctx)
}

// GetAllIncludingArchived returns all virtual funds for management pages.
func (s *VirtualFundService) GetAllIncludingArchived(ctx context.Context) ([]models.VirtualFund, error) {
	return s.fundRepo.GetAllIncludingArchived(ctx)
}

// GetByID returns a single virtual fund by ID.
func (s *VirtualFundService) GetByID(ctx context.Context, id string) (models.VirtualFund, error) {
	return s.fundRepo.GetByID(ctx, id)
}

// Create creates a new virtual fund with validation.
func (s *VirtualFundService) Create(ctx context.Context, f models.VirtualFund) (models.VirtualFund, error) {
	if f.Name == "" {
		return f, fmt.Errorf("fund name is required")
	}
	if f.Color == "" {
		f.Color = "#0d9488" // default teal
	}
	return s.fundRepo.Create(ctx, f)
}

// Update modifies an existing virtual fund.
func (s *VirtualFundService) Update(ctx context.Context, f models.VirtualFund) error {
	if f.Name == "" {
		return fmt.Errorf("fund name is required")
	}
	return s.fundRepo.Update(ctx, f)
}

// Archive soft-deletes a virtual fund (hides from dashboard, keeps data).
func (s *VirtualFundService) Archive(ctx context.Context, id string) error {
	return s.fundRepo.Archive(ctx, id)
}

// Unarchive restores an archived virtual fund.
func (s *VirtualFundService) Unarchive(ctx context.Context, id string) error {
	return s.fundRepo.Unarchive(ctx, id)
}

// Allocate links a transaction to a virtual fund and recalculates the fund balance.
// Amount should be positive for contributions, negative for withdrawals.
func (s *VirtualFundService) Allocate(ctx context.Context, transactionID, fundID string, amount float64) error {
	if amount == 0 {
		return fmt.Errorf("allocation amount cannot be zero")
	}
	err := s.fundRepo.Allocate(ctx, models.FundAllocation{
		TransactionID: transactionID,
		VirtualFundID: fundID,
		Amount:        amount,
	})
	if err != nil {
		return fmt.Errorf("allocating transaction: %w", err)
	}
	// Recalculate the fund's cached balance from all allocations
	return s.fundRepo.RecalculateBalance(ctx, fundID)
}

// Deallocate removes a transaction's allocation from a fund and recalculates.
func (s *VirtualFundService) Deallocate(ctx context.Context, transactionID, fundID string) error {
	err := s.fundRepo.Deallocate(ctx, transactionID, fundID)
	if err != nil {
		return fmt.Errorf("deallocating transaction: %w", err)
	}
	return s.fundRepo.RecalculateBalance(ctx, fundID)
}

// GetFundTransactions returns transactions allocated to a fund.
func (s *VirtualFundService) GetFundTransactions(ctx context.Context, fundID string, limit int) ([]models.Transaction, error) {
	return s.fundRepo.GetTransactionsForFund(ctx, fundID, limit)
}

// GetFundAllocations returns allocation records for a fund.
func (s *VirtualFundService) GetFundAllocations(ctx context.Context, fundID string, limit int) ([]models.FundAllocation, error) {
	return s.fundRepo.GetAllocationsForFund(ctx, fundID, limit)
}

// GetTransactionAllocations returns all fund allocations for a specific transaction.
func (s *VirtualFundService) GetTransactionAllocations(ctx context.Context, txID string) ([]models.FundAllocation, error) {
	return s.fundRepo.GetAllocationsForTransaction(ctx, txID)
}
