package service

import (
	"context"
	"time"

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
	CashTotal      float64 // sum of debit account balances
	CreditUsed     float64 // sum of credit account balances (negative)
	CreditAvail    float64 // total available credit across all credit accounts
	DebtTotal      float64 // placeholder for loans (future)

	// USD totals and conversion
	USDTotal     float64 // sum of all USD account balances
	ExchangeRate float64 // latest EGP/USD rate (0 if none available)
	USDInEGP     float64 // USDTotal * ExchangeRate

	// Institutions with their accounts for the expandable list
	Institutions []InstitutionGroup

	// People ledger summary
	PeopleOwedToMe float64 // sum of positive net_balance (they owe me)
	PeopleIOwe     float64 // sum of negative net_balance (I owe them)

	// Building fund balance (sum of is_building_fund transactions)
	BuildingFundBalance float64

	// Total investment portfolio value
	InvestmentTotal float64

	// Upcoming credit card due dates (within 7 days)
	DueSoonCards []DueSoonCard

	// Habit streak: consecutive days with transactions and weekly count
	Streak StreakInfo

	// Recent transactions for the feed
	RecentTransactions []models.Transaction
}

// InstitutionGroup pairs an institution with its accounts for display.
type InstitutionGroup struct {
	Institution models.Institution
	Accounts    []models.Account
	Total       float64 // sum of account balances under this institution
}

// DueSoonCard holds credit card info for the dashboard due date warning.
type DueSoonCard struct {
	AccountName  string
	DueDate      time.Time
	DaysUntilDue int
	Balance      float64
}

// DashboardService computes the dashboard view data.
type DashboardService struct {
	institutionRepo  *repository.InstitutionRepo
	accountRepo      *repository.AccountRepo
	txRepo           *repository.TransactionRepo
	exchangeRateRepo *repository.ExchangeRateRepo
	personRepo       *repository.PersonRepo
	investmentRepo   *repository.InvestmentRepo
	streakSvc        *StreakService
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

// SetPersonRepo sets the person repository for people summary.
func (s *DashboardService) SetPersonRepo(repo *repository.PersonRepo) {
	s.personRepo = repo
}

// SetInvestmentRepo sets the investment repository for portfolio value on dashboard.
func (s *DashboardService) SetInvestmentRepo(repo *repository.InvestmentRepo) {
	s.investmentRepo = repo
}

// SetStreakService sets the streak service for habit tracking on dashboard.
func (s *DashboardService) SetStreakService(svc *StreakService) {
	s.streakSvc = svc
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
				data.CreditAvail += acc.AvailableCredit()
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

	// Check for credit cards with upcoming due dates
	now := time.Now()
	for _, group := range data.Institutions {
		for _, acc := range group.Accounts {
			if !acc.IsCreditType() {
				continue
			}
			meta := ParseBillingCycle(acc)
			if meta == nil {
				continue
			}
			info := GetBillingCycleInfo(*meta, now)
			if info.IsDueSoon {
				data.DueSoonCards = append(data.DueSoonCards, DueSoonCard{
					AccountName:  acc.Name,
					DueDate:      info.DueDate,
					DaysUntilDue: info.DaysUntilDue,
					Balance:      acc.CurrentBalance,
				})
			}
		}
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

	// People ledger summary
	if s.personRepo != nil {
		if persons, err := s.personRepo.GetAll(ctx); err == nil {
			for _, p := range persons {
				if p.NetBalance > 0 {
					data.PeopleOwedToMe += p.NetBalance
				} else if p.NetBalance < 0 {
					data.PeopleIOwe += p.NetBalance // negative
				}
			}
		}
	}

	// Building fund balance: sum of all is_building_fund income minus expenses
	if balance, err := s.txRepo.GetBuildingFundBalance(ctx); err == nil {
		data.BuildingFundBalance = balance
	}

	// Investment portfolio total
	if s.investmentRepo != nil {
		if total, err := s.investmentRepo.GetTotalValuation(ctx); err == nil {
			data.InvestmentTotal = total
		}
	}

	// Habit streak
	if s.streakSvc != nil {
		if streak, err := s.streakSvc.GetStreak(ctx); err == nil {
			data.Streak = streak
		}
	}

	// Load recent transactions
	data.RecentTransactions, _ = s.txRepo.GetRecent(ctx, 10)

	return data, nil
}
