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

	// Net worth with USD accounts converted to EGP at the latest exchange rate
	NetWorthEGP float64

	// Breakdown by category: cash (debit accounts), credit (used credit), debt
	CashTotal   float64 // sum of debit account balances
	CreditUsed  float64 // sum of credit account balances (negative)
	DebtTotal   float64 // placeholder for loans (future)

	// USD totals and conversion
	USDTotal     float64 // sum of all USD account balances
	ExchangeRate float64 // latest EGP/USD rate (0 if none available)
	USDInEGP     float64 // USDTotal * ExchangeRate

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
	institutionRepo  *repository.InstitutionRepo
	accountRepo      *repository.AccountRepo
	txRepo           *repository.TransactionRepo
	exchangeRateRepo *repository.ExchangeRateRepo
}

func NewDashboardService(institutionRepo *repository.InstitutionRepo, accountRepo *repository.AccountRepo, txRepo *repository.TransactionRepo) *DashboardService {
	return &DashboardService{
		institutionRepo: institutionRepo,
		accountRepo:     accountRepo,
		txRepo:          txRepo,
	}
}

// SetExchangeRateRepo sets the exchange rate repository for USD conversion.
func (s *DashboardService) SetExchangeRateRepo(repo *repository.ExchangeRateRepo) {
	s.exchangeRateRepo = repo
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

			if acc.Currency == models.CurrencyUSD {
				data.USDTotal += acc.CurrentBalance
			}

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

	// Get latest exchange rate for USD → EGP conversion
	if s.exchangeRateRepo != nil {
		if rate, err := s.exchangeRateRepo.GetLatest(ctx); err == nil && rate > 0 {
			data.ExchangeRate = rate
			data.USDInEGP = data.USDTotal * rate
			// NetWorthEGP = (NetWorth - USDTotal) + USDInEGP
			// i.e., replace raw USD values with their EGP equivalent
			data.NetWorthEGP = (data.NetWorth - data.USDTotal) + data.USDInEGP
		}
	}
	// If no rate available, NetWorthEGP stays 0 (template checks this)

	// Load recent transactions
	data.RecentTransactions, _ = s.txRepo.GetRecent(ctx, 10)

	return data, nil
}
