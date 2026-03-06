package service

import (
	"context"

	"github.com/ahmedelsamadisi/clearmoney/internal/models"
	"github.com/ahmedelsamadisi/clearmoney/internal/repository"
)

// DashboardData holds the computed data for the home dashboard.
// Think of it as a ViewModel — combines raw data into display-ready format.
type DashboardData struct {
	// Net worth: sum of all account balances (positive = assets, negative = liabilities)
	NetWorth float64

	// Breakdown by category: cash (debit accounts), credit (used credit), debt
	CashTotal   float64 // sum of debit account balances
	CreditUsed  float64 // sum of credit account balances (negative)
	DebtTotal   float64 // placeholder for loans (future)

	// Institutions with their accounts for the expandable list
	Institutions []InstitutionGroup

	// Recent transactions for the feed
	RecentTransactions []models.Transaction
}

// InstitutionGroup pairs an institution with its accounts for display.
type InstitutionGroup struct {
	Institution models.Institution
	Accounts    []models.Account
	Total       float64 // sum of account balances under this institution
}

// DashboardService computes the dashboard view data.
type DashboardService struct {
	institutionRepo *repository.InstitutionRepo
	accountRepo     *repository.AccountRepo
	txRepo          *repository.TransactionRepo
}

func NewDashboardService(institutionRepo *repository.InstitutionRepo, accountRepo *repository.AccountRepo, txRepo *repository.TransactionRepo) *DashboardService {
	return &DashboardService{
		institutionRepo: institutionRepo,
		accountRepo:     accountRepo,
		txRepo:          txRepo,
	}
}

// GetDashboard computes the full dashboard data in a single call.
func (s *DashboardService) GetDashboard(ctx context.Context) (DashboardData, error) {
	var data DashboardData

	// Load all institutions
	institutions, err := s.institutionRepo.GetAll(ctx)
	if err != nil {
		return data, err
	}

	// For each institution, load accounts and compute totals
	for _, inst := range institutions {
		accounts, err := s.accountRepo.GetByInstitution(ctx, inst.ID)
		if err != nil {
			continue
		}

		var instTotal float64
		for _, acc := range accounts {
			instTotal += acc.CurrentBalance
			data.NetWorth += acc.CurrentBalance

			if acc.IsCreditType() {
				data.CreditUsed += acc.CurrentBalance // negative values
			} else {
				data.CashTotal += acc.CurrentBalance
			}
		}

		data.Institutions = append(data.Institutions, InstitutionGroup{
			Institution: inst,
			Accounts:    accounts,
			Total:       instTotal,
		})
	}

	// Load recent transactions
	data.RecentTransactions, _ = s.txRepo.GetRecent(ctx, 10)

	return data, nil
}
