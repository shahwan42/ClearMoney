// Package service — account_health.go checks account health constraints.
//
// Accounts can have optional health rules stored as JSONB (PostgreSQL):
//   - min_balance: warns if account drops below a threshold
//   - min_monthly_deposit: warns if no deposit >= amount this month
//
// Laravel analogy: This is like a dedicated HealthCheckService that runs validation
// rules against accounts — similar to how you might schedule an Artisan command
// to check business rules and send notifications. Or think of it like Laravel's
// custom validation rules, but applied to domain objects instead of form input.
//
// Django analogy: Similar to a management command or Celery task that checks
// constraints and generates alerts. Like Django's check framework but for business rules.
//
// Design pattern: This service depends on two repositories (AccountRepo + TransactionRepo).
// Multiple dependencies are common in services that cross domain boundaries.
// In Go, we inject them via the constructor — no container magic.
//
// See: https://pkg.go.dev/encoding/json for JSON marshaling (used for health config)
package service

import (
	"context"
	"encoding/json"
	"time"

	"github.com/ahmedelsamadisi/clearmoney/internal/models"
	"github.com/ahmedelsamadisi/clearmoney/internal/repository"
)

// AccountHealthWarning represents a violated health constraint on an account.
// This is a value object (no ID, not persisted) — it's computed on-the-fly.
// In Laravel, this would be a plain data object or DTO (Data Transfer Object).
// In Django, a dataclass or namedtuple.
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
// This is an aggregation method — it loads all accounts, checks each one's config,
// and accumulates warnings into a slice.
//
// Note: returns []AccountHealthWarning (not error). On DB failure, returns nil (empty).
// This is a deliberate design choice: health checks are advisory, not critical.
// The dashboard can render normally even if health checks fail.
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
// The config is serialized to JSON and stored in the account's health_config JSONB column.
// json.Marshal converts the Go struct to JSON bytes — like json_encode() in PHP
// or json.dumps() in Python.
func (s *AccountHealthService) UpdateHealthConfig(ctx context.Context, accountID string, cfg models.AccountHealthConfig) error {
	data, err := json.Marshal(cfg)
	if err != nil {
		return err
	}
	return s.accountRepo.UpdateHealthConfig(ctx, accountID, data)
}
