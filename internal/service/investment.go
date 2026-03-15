// Package service — InvestmentService handles business logic for investment portfolio.
//
// Investments are fund holdings on platforms like Thndr (Egypt's popular investment app).
// Each investment has: fund name, number of units, and last known unit price.
// Total value = units * last_unit_price.
//
// Valuations are updated manually (the user enters the new price from their broker).
// This is simpler than an API integration but still gives useful portfolio tracking.
//
// Laravel analogy: A simple Service class with CRUD + a specialized UpdateValuation method.
// Like a PortfolioService that wraps an Eloquent model.
//
// Django analogy: A services.py module for investments with create, update_valuation, and
// get_total methods — keeping business logic out of the model.
package service

import (
	"context"
	"fmt"

	"github.com/ahmedelsamadisi/clearmoney/internal/logutil"
	"github.com/ahmedelsamadisi/clearmoney/internal/models"
	"github.com/ahmedelsamadisi/clearmoney/internal/repository"
)

// InvestmentService follows the standard service pattern: struct with repo dependency.
type InvestmentService struct {
	repo *repository.InvestmentRepo
}

// NewInvestmentService creates the service. Standard Go constructor pattern.
func NewInvestmentService(repo *repository.InvestmentRepo) *InvestmentService {
	return &InvestmentService{repo: repo}
}

// Create adds a new investment holding.
func (s *InvestmentService) Create(ctx context.Context, inv models.Investment) (models.Investment, error) {
	if inv.FundName == "" {
		return models.Investment{}, fmt.Errorf("fund_name is required")
	}
	if inv.Units <= 0 {
		return models.Investment{}, fmt.Errorf("units must be positive")
	}
	if inv.LastUnitPrice <= 0 {
		return models.Investment{}, fmt.Errorf("unit_price must be positive")
	}
	if inv.Platform == "" {
		inv.Platform = "Thndr"
	}
	if inv.Currency == "" {
		inv.Currency = models.CurrencyEGP
	}
	created, err := s.repo.Create(ctx, inv)
	if err != nil {
		return models.Investment{}, err
	}
	logutil.LogEvent(ctx, "investment.created", "currency", string(created.Currency))
	return created, nil
}

// GetAll returns all investment holdings.
func (s *InvestmentService) GetAll(ctx context.Context) ([]models.Investment, error) {
	return s.repo.GetAll(ctx)
}

// UpdateValuation updates the unit price for an investment.
func (s *InvestmentService) UpdateValuation(ctx context.Context, id string, unitPrice float64) error {
	if unitPrice <= 0 {
		return fmt.Errorf("unit_price must be positive")
	}
	if err := s.repo.UpdateValuation(ctx, id, unitPrice); err != nil {
		return err
	}
	logutil.LogEvent(ctx, "investment.valuation_updated", "id", id)
	return nil
}

// Delete removes an investment.
func (s *InvestmentService) Delete(ctx context.Context, id string) error {
	if err := s.repo.Delete(ctx, id); err != nil {
		return err
	}
	logutil.LogEvent(ctx, "investment.deleted", "id", id)
	return nil
}

// GetTotalValuation returns the total portfolio value (sum of units * price).
// This aggregate query runs in PostgreSQL: SUM(units * last_unit_price).
// Used by DashboardService to show total investment value.
func (s *InvestmentService) GetTotalValuation(ctx context.Context) (float64, error) {
	return s.repo.GetTotalValuation(ctx)
}
