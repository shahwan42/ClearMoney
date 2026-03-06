package service

import (
	"context"
	"fmt"
	"strings"

	"github.com/ahmedelsamadisi/clearmoney/internal/models"
	"github.com/ahmedelsamadisi/clearmoney/internal/repository"
)

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
