// Package service — InvestmentService handles business logic for investment portfolio.
// Investments are fund holdings on platforms like Thndr, with manual valuation updates.
package service

import (
	"context"
	"fmt"

	"github.com/ahmedelsamadisi/clearmoney/internal/models"
	"github.com/ahmedelsamadisi/clearmoney/internal/repository"
)

type InvestmentService struct {
	repo *repository.InvestmentRepo
}

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
	return s.repo.Create(ctx, inv)
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
	return s.repo.UpdateValuation(ctx, id, unitPrice)
}

// Delete removes an investment.
func (s *InvestmentService) Delete(ctx context.Context, id string) error {
	return s.repo.Delete(ctx, id)
}

// GetTotalValuation returns the total portfolio value (sum of units * price).
func (s *InvestmentService) GetTotalValuation(ctx context.Context) (float64, error) {
	return s.repo.GetTotalValuation(ctx)
}
