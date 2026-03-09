// Package service — account_health.go checks account health constraints.
//
// Accounts can have optional health rules like minimum balance or minimum
// monthly deposit. This service checks all accounts against their rules
// and returns warnings for any violations.
//
// In Laravel terms, this is like a Service class with validation logic.
// In Django, similar to a validation service or signal handler.
package service

import (
	"context"
	"encoding/json"
	"time"

	"github.com/ahmedelsamadisi/clearmoney/internal/models"
	"github.com/ahmedelsamadisi/clearmoney/internal/repository"
)

// AccountHealthWarning represents a violated health constraint on an account.
type AccountHealthWarning struct {
	AccountName string
	AccountID   string
	Rule        string // "min_balance" or "min_monthly_deposit"
	Message     string // human-readable warning
}

// AccountHealthService checks health constraints on accounts.
type AccountHealthService struct {
	accountRepo *repository.AccountRepo
	txRepo      *repository.TransactionRepo
}

func NewAccountHealthService(accountRepo *repository.AccountRepo, txRepo *repository.TransactionRepo) *AccountHealthService {
	return &AccountHealthService{accountRepo: accountRepo, txRepo: txRepo}
}

// CheckAll returns warnings for all accounts that violate their health constraints.
func (s *AccountHealthService) CheckAll(ctx context.Context) []AccountHealthWarning {
	accounts, err := s.accountRepo.GetAll(ctx)
	if err != nil {
		return nil
	}

	var warnings []AccountHealthWarning
	for _, acc := range accounts {
		cfg := acc.GetHealthConfig()
		if cfg == nil {
			continue
		}

		// Check minimum balance
		if cfg.MinBalance != nil && acc.CurrentBalance < *cfg.MinBalance {
			warnings = append(warnings, AccountHealthWarning{
				AccountName: acc.Name,
				AccountID:   acc.ID,
				Rule:        "min_balance",
				Message:     acc.Name + " is below minimum balance",
			})
		}

		// Check minimum monthly deposit
		if cfg.MinMonthlyDeposit != nil {
			now := time.Now()
			monthStart := time.Date(now.Year(), now.Month(), 1, 0, 0, 0, 0, time.UTC)
			monthEnd := monthStart.AddDate(0, 1, 0)
			hasDeposit := s.txRepo.HasDepositInRange(ctx, acc.ID, *cfg.MinMonthlyDeposit, monthStart, monthEnd)
			if !hasDeposit {
				warnings = append(warnings, AccountHealthWarning{
					AccountName: acc.Name,
					AccountID:   acc.ID,
					Rule:        "min_monthly_deposit",
					Message:     acc.Name + " is missing required monthly deposit",
				})
			}
		}
	}

	return warnings
}

// UpdateHealthConfig saves health constraints for an account.
func (s *AccountHealthService) UpdateHealthConfig(ctx context.Context, accountID string, cfg models.AccountHealthConfig) error {
	data, err := json.Marshal(cfg)
	if err != nil {
		return err
	}
	return s.accountRepo.UpdateHealthConfig(ctx, accountID, data)
}
