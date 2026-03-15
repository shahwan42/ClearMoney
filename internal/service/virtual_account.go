// Package service — virtual_account.go provides business logic for virtual accounts.
//
// Virtual accounts are user-defined savings buckets (envelope budgeting pattern).
// Users can create any number of goals: "Emergency Fund", "Vacation", etc.
//
// The envelope budgeting concept: virtual accounts don't move money between accounts.
// Instead, they "tag" transactions as belonging to a virtual account. The virtual account's
// balance is the sum of all allocations — a virtual overlay on top of real account balances.
//
// Laravel analogy: Like a VirtualAccountService with a polymorphic many-to-many
// relationship (virtual_account_allocations pivot table) connecting transactions to virtual accounts.
// The Allocate/Deallocate methods manage this pivot. Similar to Laravel's
// attach/detach on BelongsToMany relationships, but with an amount column.
//
// Django analogy: Like a through model (VirtualAccountAllocation) on a ManyToManyField
// between Transaction and VirtualAccount, with extra amount data on the through table.
//
// Design: After every allocation/deallocation, the virtual account's cached balance is
// recalculated from the sum of all allocations. This denormalization trades
// write complexity for read speed (dashboard reads are frequent, allocations are rare).
package service

import (
	"context"
	"fmt"

	"github.com/ahmedelsamadisi/clearmoney/internal/logutil"
	"github.com/ahmedelsamadisi/clearmoney/internal/models"
	"github.com/ahmedelsamadisi/clearmoney/internal/repository"
)

// VirtualAccountService handles business logic for virtual accounts.
type VirtualAccountService struct {
	accountRepo *repository.VirtualAccountRepo
}

func NewVirtualAccountService(accountRepo *repository.VirtualAccountRepo) *VirtualAccountService {
	return &VirtualAccountService{accountRepo: accountRepo}
}

// GetAll returns all active (non-archived) virtual accounts.
func (s *VirtualAccountService) GetAll(ctx context.Context) ([]models.VirtualAccount, error) {
	return s.accountRepo.GetAll(ctx)
}

// GetAllIncludingArchived returns all virtual accounts for management pages.
func (s *VirtualAccountService) GetAllIncludingArchived(ctx context.Context) ([]models.VirtualAccount, error) {
	return s.accountRepo.GetAllIncludingArchived(ctx)
}

// GetByID returns a single virtual account by ID.
func (s *VirtualAccountService) GetByID(ctx context.Context, id string) (models.VirtualAccount, error) {
	return s.accountRepo.GetByID(ctx, id)
}

// Create creates a new virtual account with validation.
func (s *VirtualAccountService) Create(ctx context.Context, a models.VirtualAccount) (models.VirtualAccount, error) {
	if a.Name == "" {
		return a, fmt.Errorf("virtual account name is required")
	}
	if a.Color == "" {
		a.Color = "#0d9488" // default teal
	}
	created, err := s.accountRepo.Create(ctx, a)
	if err != nil {
		return a, err
	}
	logutil.LogEvent(ctx, "virtual_account.created")
	return created, nil
}

// Update modifies an existing virtual account.
func (s *VirtualAccountService) Update(ctx context.Context, a models.VirtualAccount) error {
	if a.Name == "" {
		return fmt.Errorf("virtual account name is required")
	}
	return s.accountRepo.Update(ctx, a)
}

// Archive soft-deletes a virtual account (hides from dashboard, keeps data).
// Like Laravel's SoftDeletes — the record remains in the DB with an archived_at
// timestamp. GetAll() excludes archived; GetAllIncludingArchived() includes them.
func (s *VirtualAccountService) Archive(ctx context.Context, id string) error {
	if err := s.accountRepo.Archive(ctx, id); err != nil {
		return err
	}
	logutil.LogEvent(ctx, "virtual_account.archived", "id", id)
	return nil
}

// Unarchive restores an archived virtual account.
func (s *VirtualAccountService) Unarchive(ctx context.Context, id string) error {
	return s.accountRepo.Unarchive(ctx, id)
}

// Allocate links a transaction to a virtual account and recalculates the balance.
// Amount should be positive for contributions, negative for withdrawals.
//
// Two-step operation: (1) create the allocation record, (2) recalculate the virtual account's
// cached balance. The recalculation runs SUM(amount) on all allocations for this virtual account.
// This ensures the cached balance is always consistent with the source data.
//
// Like Laravel's sync() or attach() on a pivot, but with a recalculation step.
func (s *VirtualAccountService) Allocate(ctx context.Context, transactionID, accountID string, amount float64) error {
	if amount == 0 {
		return fmt.Errorf("allocation amount cannot be zero")
	}
	err := s.accountRepo.Allocate(ctx, models.VirtualAccountAllocation{
		TransactionID:    transactionID,
		VirtualAccountID: accountID,
		Amount:           amount,
	})
	if err != nil {
		return fmt.Errorf("allocating transaction: %w", err)
	}
	// Recalculate the virtual account's cached balance from all allocations
	if err := s.accountRepo.RecalculateBalance(ctx, accountID); err != nil {
		return err
	}
	logutil.LogEvent(ctx, "virtual_account.allocated", "account_id", accountID, "transaction_id", transactionID)
	return nil
}

// Deallocate removes a transaction's allocation from a virtual account and recalculates.
func (s *VirtualAccountService) Deallocate(ctx context.Context, transactionID, accountID string) error {
	err := s.accountRepo.Deallocate(ctx, transactionID, accountID)
	if err != nil {
		return fmt.Errorf("deallocating transaction: %w", err)
	}
	return s.accountRepo.RecalculateBalance(ctx, accountID)
}

// GetVirtualAccountTransactions returns transactions allocated to a virtual account.
func (s *VirtualAccountService) GetVirtualAccountTransactions(ctx context.Context, accountID string, limit int) ([]models.Transaction, error) {
	return s.accountRepo.GetTransactionsForAccount(ctx, accountID, limit)
}

// GetVirtualAccountAllocations returns allocation records for a virtual account.
func (s *VirtualAccountService) GetVirtualAccountAllocations(ctx context.Context, accountID string, limit int) ([]models.VirtualAccountAllocation, error) {
	return s.accountRepo.GetAllocationsForAccount(ctx, accountID, limit)
}

// GetTransactionAllocations returns all virtual account allocations for a specific transaction.
func (s *VirtualAccountService) GetTransactionAllocations(ctx context.Context, txID string) ([]models.VirtualAccountAllocation, error) {
	return s.accountRepo.GetAllocationsForTransaction(ctx, txID)
}
