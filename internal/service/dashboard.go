package service

import (
	"context"
	"database/sql"
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

	// TASK-055: Net worth sparkline data (last 30 days)
	NetWorthHistory []float64 // values for sparkline chart
	NetWorthChange  float64   // % change vs 30 days ago

	// TASK-056: Month-over-month spending comparison
	ThisMonthSpending float64
	LastMonthSpending float64
	SpendingChange    float64          // % change (positive = spending more)
	TopCategories     []CategoryChange // top 3 categories with change indicators

	// TASK-059: Per-account balance sparklines (account ID → last 30 days)
	AccountSparklines map[string][]float64

	// TASK-060: Spending velocity — pace of spending vs last month
	SpendingVelocity SpendingVelocity

	// TASK-063: Virtual funds for dashboard widget
	VirtualFunds []models.VirtualFund
}

// SpendingVelocity shows the pace of spending relative to last month.
// "You've spent X% of last month's total with Y days remaining."
type SpendingVelocity struct {
	Percentage   float64 // current month spend / last month total × 100
	DaysElapsed  int     // days elapsed in current month
	DaysTotal    int     // total days in current month
	DaysLeft     int     // days remaining
	DayProgress  float64 // % of month elapsed (e.g., day 15 of 30 = 50%)
	Status       string  // "green", "amber", or "red"
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

// CategoryChange shows a category's spending with month-over-month change.
// Used in the dashboard's "This Month vs Last Month" section.
type CategoryChange struct {
	Name   string  // Category name (e.g., "Groceries")
	Amount float64 // This month's spending in this category
	Change float64 // % change vs last month (positive = spending more)
	IsUp   bool    // true if spending increased (bad for expenses)
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
	snapshotSvc      *SnapshotService
	virtualFundSvc   *VirtualFundService
	db               *sql.DB // for direct queries (month-over-month)
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

// SetSnapshotService sets the snapshot service for net worth history sparkline.
func (s *DashboardService) SetSnapshotService(svc *SnapshotService) {
	s.snapshotSvc = svc
}

// SetVirtualFundService sets the virtual fund service for dashboard widget (TASK-063).
func (s *DashboardService) SetVirtualFundService(svc *VirtualFundService) {
	s.virtualFundSvc = svc
}

// SetDB sets the database connection for direct queries (month-over-month).
func (s *DashboardService) SetDB(db *sql.DB) {
	s.db = db
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

	// Building fund balance (legacy — kept for backward compatibility)
	if balance, err := s.txRepo.GetBuildingFundBalance(ctx); err == nil {
		data.BuildingFundBalance = balance
	}

	// TASK-063: Load active virtual funds for dashboard widget
	if s.virtualFundSvc != nil {
		if funds, err := s.virtualFundSvc.GetAll(ctx); err == nil {
			data.VirtualFunds = funds
		}
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

	// TASK-055: Net worth sparkline (last 30 days from snapshots)
	if s.snapshotSvc != nil {
		if history, err := s.snapshotSvc.GetNetWorthHistory(ctx, 30); err == nil && len(history) >= 2 {
			data.NetWorthHistory = history
			// % change: (current - oldest) / |oldest| * 100
			oldest := history[0]
			current := history[len(history)-1]
			if oldest != 0 {
				data.NetWorthChange = (current - oldest) / abs(oldest) * 100
			}
		}
	}

	// TASK-059: Per-account balance sparklines (last 30 days)
	if s.snapshotSvc != nil {
		sparklines := make(map[string][]float64)
		for _, group := range data.Institutions {
			for _, acc := range group.Accounts {
				if history, err := s.snapshotSvc.GetAccountHistory(ctx, acc.ID, 30); err == nil && len(history) >= 2 {
					sparklines[acc.ID] = history
				}
			}
		}
		if len(sparklines) > 0 {
			data.AccountSparklines = sparklines
		}
	}

	// TASK-056: Month-over-month spending comparison
	if s.db != nil {
		s.computeSpendingComparison(ctx, &data)
	}

	return data, nil
}

// abs returns the absolute value of a float64.
func abs(v float64) float64 {
	if v < 0 {
		return -v
	}
	return v
}

// computeSpendingComparison calculates this month vs last month spending
// and the top 3 categories with the biggest changes.
func (s *DashboardService) computeSpendingComparison(ctx context.Context, data *DashboardData) {
	now := time.Now()
	thisMonthStart := time.Date(now.Year(), now.Month(), 1, 0, 0, 0, 0, time.UTC)
	lastMonthStart := thisMonthStart.AddDate(0, -1, 0)

	// Total spending this month vs last month
	_ = s.db.QueryRowContext(ctx, `
		SELECT COALESCE(SUM(amount), 0) FROM transactions
		WHERE type = 'expense' AND date >= $1 AND date < $2
	`, thisMonthStart, thisMonthStart.AddDate(0, 1, 0)).Scan(&data.ThisMonthSpending)

	_ = s.db.QueryRowContext(ctx, `
		SELECT COALESCE(SUM(amount), 0) FROM transactions
		WHERE type = 'expense' AND date >= $1 AND date < $2
	`, lastMonthStart, thisMonthStart).Scan(&data.LastMonthSpending)

	// Spending change %
	if data.LastMonthSpending > 0 {
		data.SpendingChange = (data.ThisMonthSpending - data.LastMonthSpending) / data.LastMonthSpending * 100
	}

	// TASK-060: Spending velocity
	daysInMonth := thisMonthStart.AddDate(0, 1, 0).Sub(thisMonthStart).Hours() / 24
	daysElapsed := now.Day()
	daysLeft := int(daysInMonth) - daysElapsed
	dayProgress := float64(daysElapsed) / daysInMonth * 100

	sv := SpendingVelocity{
		DaysElapsed: daysElapsed,
		DaysTotal:   int(daysInMonth),
		DaysLeft:    daysLeft,
		DayProgress: dayProgress,
	}
	if data.LastMonthSpending > 0 {
		sv.Percentage = data.ThisMonthSpending / data.LastMonthSpending * 100
	}
	// Color: green if pace < day%, amber if within 10%, red if ahead
	switch {
	case sv.Percentage <= dayProgress:
		sv.Status = "green"
	case sv.Percentage <= dayProgress+10:
		sv.Status = "amber"
	default:
		sv.Status = "red"
	}
	data.SpendingVelocity = sv

	// Top 3 categories with the largest spending this month + their change vs last month
	rows, err := s.db.QueryContext(ctx, `
		WITH this_month AS (
			SELECT COALESCE(c.name, 'Uncategorized') AS cat_name,
				SUM(t.amount) AS amount
			FROM transactions t
			LEFT JOIN categories c ON t.category_id = c.id
			WHERE t.type = 'expense' AND t.date >= $1 AND t.date < $2
			GROUP BY c.name
			ORDER BY SUM(t.amount) DESC
			LIMIT 3
		),
		last_month AS (
			SELECT COALESCE(c.name, 'Uncategorized') AS cat_name,
				SUM(t.amount) AS amount
			FROM transactions t
			LEFT JOIN categories c ON t.category_id = c.id
			WHERE t.type = 'expense' AND t.date >= $3 AND t.date < $1
			GROUP BY c.name
		)
		SELECT tm.cat_name, tm.amount,
			COALESCE(lm.amount, 0) AS last_amount
		FROM this_month tm
		LEFT JOIN last_month lm ON tm.cat_name = lm.cat_name
	`, thisMonthStart, thisMonthStart.AddDate(0, 1, 0), lastMonthStart)
	if err != nil {
		return
	}
	defer rows.Close()

	for rows.Next() {
		var name string
		var thisAmt, lastAmt float64
		if err := rows.Scan(&name, &thisAmt, &lastAmt); err != nil {
			continue
		}
		change := 0.0
		if lastAmt > 0 {
			change = (thisAmt - lastAmt) / lastAmt * 100
		}
		data.TopCategories = append(data.TopCategories, CategoryChange{
			Name:   name,
			Amount: thisAmt,
			Change: change,
			IsUp:   change > 0,
		})
	}
}
