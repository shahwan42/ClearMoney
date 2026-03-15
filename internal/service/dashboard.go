// dashboard.go — DashboardService aggregates data from 10+ sources for the home page.
//
// This is the most complex service in ClearMoney. It pulls data from institutions,
// accounts, transactions, exchange rates, people, investments, snapshots, virtual accounts,
// budgets, health checks, and credit card billing cycles — all to build a single
// DashboardData struct that the template renders.
//
// Laravel analogy: Like a DashboardController@index that calls 10+ repositories and
// returns a view with all the data. In Laravel, you might use a View Composer or
// a dedicated "DashboardService" class. Same idea here.
//
// Django analogy: Like a TemplateView.get_context_data() that aggregates from many
// QuerySets and services into a single context dictionary.
//
// Design patterns used:
//
// 1. SETTER INJECTION: DashboardService has a core constructor (NewDashboardService)
//    with 3 required dependencies, plus 8 optional dependencies added via Set*() methods.
//    This avoids a constructor with 11 parameters and lets the service work even when
//    some features are disabled (e.g., no snapshot service means no sparklines).
//    Like Laravel's optional bindings or Django's has_module() checks.
//
// 2. NIL-SAFE CHECKS: Before using optional services, we check if they're nil:
//    `if s.snapshotSvc != nil { ... }`. This is Go's version of optional chaining
//    ($service?->method() in PHP 8, or getattr(obj, 'method', None) in Python).
//
// 3. AGGREGATE/VIEWMODEL PATTERN: DashboardData is a "fat" struct that bundles
//    everything the template needs. The template never makes DB calls.
//
// See: https://pkg.go.dev/database/sql for direct SQL queries used in computeSpendingComparison
package service

import (
	"context"
	"database/sql"
	"log/slog"
	"time"

	"github.com/shahwan42/clearmoney/internal/logutil"
	"github.com/shahwan42/clearmoney/internal/models"
	"github.com/shahwan42/clearmoney/internal/repository"
	"github.com/shahwan42/clearmoney/internal/timeutil"
)

// DashboardData holds the computed data for the home dashboard.
// Think of it as a ViewModel — combines raw data into display-ready format.
// The handler passes this entire struct to the template. The template NEVER
// makes database calls — all data is pre-computed here.
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

	// Per-currency totals
	EGPTotal float64 // sum of all EGP account balances
	USDTotal float64 // sum of all USD account balances

	// Exchange rate (kept for institution-level conversion)
	ExchangeRate float64 // latest EGP/USD rate (0 if none available)
	USDInEGP     float64 // USDTotal * ExchangeRate

	// Institutions with their accounts for the expandable list
	Institutions []InstitutionGroup

	// People ledger summary
	PeopleOwedToMe    float64                 // legacy sum of positive net_balance (they owe me)
	PeopleIOwe        float64                 // legacy sum of negative net_balance (I owe them)
	PeopleByCurrency  []PeopleCurrencySummary // per-currency people breakdown
	HasPeopleActivity bool                    // true if any person has a non-zero balance

	// Total investment portfolio value
	InvestmentTotal float64

	// Upcoming credit card due dates (within 7 days)
	DueSoonCards []DueSoonCard

	// Habit streak: consecutive days with transactions and weekly count
	Streak StreakInfo

	// Recent transactions for the feed (enriched with account name and running balance)
	RecentTransactions []repository.TransactionDisplayRow

	// TASK-055: Net worth sparkline data (last 30 days)
	NetWorthHistory           []float64          // values for sparkline chart (EGP-converted)
	NetWorthChange            float64            // % change vs 30 days ago
	NetWorthHistoryByCurrency map[string][]float64 // per-currency sparkline data (e.g., "EGP" and "USD")

	// TASK-056: Month-over-month spending comparison
	SpendingByCurrency []CurrencySpending // per-currency spending comparison
	ThisMonthSpending  float64            // EGP-only (legacy, used by SpendingVelocity)
	LastMonthSpending  float64            // EGP-only (legacy, used by SpendingVelocity)
	SpendingChange     float64            // EGP-only % change (positive = spending more)
	TopCategories      []CategoryChange   // EGP-only top 3 categories (legacy)

	// TASK-059: Per-account balance sparklines (account ID → last 30 days)
	AccountSparklines map[string][]float64

	// TASK-060: Spending velocity — pace of spending vs last month
	SpendingVelocity SpendingVelocity

	// TASK-063: Virtual accounts for dashboard widget
	VirtualAccounts []models.VirtualAccount

	// TASK-066: Budget progress for dashboard widget
	Budgets []models.BudgetWithSpending

	// TASK-069: Account health warnings
	HealthWarnings []AccountHealthWarning

	// TASK-074: Credit card dashboard summary
	CreditCards []CreditCardSummary
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

// CurrencySpending holds per-currency month-over-month spending comparison.
// The dashboard renders one "This Month vs Last" section per currency.
type CurrencySpending struct {
	Currency      string           // "EGP" or "USD"
	ThisMonth     float64          // total spending this month in this currency
	LastMonth     float64          // total spending last month in this currency
	Change        float64          // % change (positive = spending more)
	TopCategories []CategoryChange // top 3 categories for this currency
}

// CategoryChange shows a category's spending with month-over-month change.
// Used in the dashboard's "This Month vs Last Month" section.
type CategoryChange struct {
	Name   string  // Category name (e.g., "Groceries")
	Icon   string  // Category icon emoji (e.g., "🛒")
	Amount float64 // This month's spending in this category
	Change float64 // % change vs last month (positive = spending more)
	IsUp   bool    // true if spending increased (bad for expenses)
}

// DashboardService computes the dashboard view data.
//
// PeopleCurrencySummary holds per-currency people ledger totals for the dashboard.
type PeopleCurrencySummary struct {
	Currency string  // "EGP" or "USD"
	OwedToMe float64 // sum of positive per-currency balance
	IOwe     float64 // sum of negative per-currency balance (negative number)
}

// This struct has 11 dependencies — 3 required (set in constructor) and 8 optional
// (set via setter methods). The setter injection pattern avoids a massive constructor
// and allows the service to degrade gracefully when optional features are unavailable.
//
// In Laravel, you might use a Service Container with optional bindings.
// In Django, you'd use django.apps.apps.get_model() or conditional imports.
type DashboardService struct {
	institutionRepo  *repository.InstitutionRepo
	accountRepo      *repository.AccountRepo
	txRepo           *repository.TransactionRepo
	exchangeRateRepo *repository.ExchangeRateRepo
	personRepo       *repository.PersonRepo
	investmentRepo   *repository.InvestmentRepo
	streakSvc        *StreakService
	snapshotSvc      *SnapshotService
	virtualAccountSvc *VirtualAccountService
	budgetSvc        *BudgetService
	healthSvc        *AccountHealthService
	db               *sql.DB         // for direct queries (month-over-month)
	loc              *time.Location   // User timezone for month boundaries
}

// SetTimezone sets the user's timezone for calendar-date operations.
func (s *DashboardService) SetTimezone(loc *time.Location) {
	s.loc = loc
}

// timezone returns the configured timezone or UTC as fallback.
func (s *DashboardService) timezone() *time.Location {
	if s.loc != nil {
		return s.loc
	}
	return time.UTC
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

// SetVirtualAccountService sets the virtual account service for dashboard widget (TASK-063).
func (s *DashboardService) SetVirtualAccountService(svc *VirtualAccountService) {
	s.virtualAccountSvc = svc
}

// SetBudgetService sets the budget service for dashboard widget (TASK-066).
func (s *DashboardService) SetBudgetService(svc *BudgetService) {
	s.budgetSvc = svc
}

// SetAccountHealthService sets the health service for dashboard warnings (TASK-069).
func (s *DashboardService) SetAccountHealthService(svc *AccountHealthService) {
	s.healthSvc = svc
}

// SetDB sets the database connection for direct queries (month-over-month).
func (s *DashboardService) SetDB(db *sql.DB) {
	s.db = db
}

// GetDashboard computes the full dashboard data in a single call.
//
// This method orchestrates 10+ data sources into a single DashboardData struct.
// It uses a "best effort" approach: if optional data sources fail, they're silently
// skipped (the dashboard still renders with partial data). Only the core institution/
// account load causes a hard failure.
//
// Performance note: This makes multiple sequential DB queries. In a high-traffic app,
// you'd use goroutines + channels for parallel loading. For a single-user app like
// ClearMoney, sequential is fine and much simpler to reason about.
func (s *DashboardService) GetDashboard(ctx context.Context) (DashboardData, error) {
	dashStart := time.Now()
	var data DashboardData

	// Load all institutions
	t := time.Now()
	institutions, err := s.institutionRepo.GetAll(ctx)
	if err != nil {
		return data, err
	}
	logutil.Log(ctx).Debug("dashboard: loaded institutions", "duration_ms", time.Since(t).Milliseconds(), "count", len(institutions))

	// Fetch exchange rate early so institution totals can convert USD→EGP
	var exchangeRate float64
	if s.exchangeRateRepo != nil {
		t = time.Now()
		if rate, err := s.exchangeRateRepo.GetLatest(ctx); err == nil && rate > 0 {
			exchangeRate = rate
		}
		logutil.Log(ctx).Debug("dashboard: loaded exchange rate", "duration_ms", time.Since(t).Milliseconds())
	}

	// For each institution, load accounts and compute totals
	for _, inst := range institutions {
		accounts, err := s.accountRepo.GetByInstitution(ctx, inst.ID)
		if err != nil {
			continue
		}

		var instTotal float64
		for _, acc := range accounts {
			// Institution total: convert USD to EGP so totals aren't mixed
			if acc.Currency == models.CurrencyUSD && exchangeRate > 0 {
				instTotal += acc.CurrentBalance * exchangeRate
			} else {
				instTotal += acc.CurrentBalance
			}
			data.NetWorth += acc.CurrentBalance

			switch acc.Currency {
			case models.CurrencyUSD:
				data.USDTotal += acc.CurrentBalance
			case models.CurrencyEGP:
				data.EGPTotal += acc.CurrentBalance
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

	// Check for credit cards with upcoming due dates + build CC summary (TASK-074)
	now := timeutil.Now()
	for _, group := range data.Institutions {
		for _, acc := range group.Accounts {
			if !acc.IsCreditType() {
				continue
			}
			meta := ParseBillingCycle(acc)

			ccSummary := CreditCardSummary{
				AccountID:      acc.ID,
				AccountName:    acc.Name,
				Balance:        acc.CurrentBalance,
				Utilization:    GetCreditCardUtilization(acc),
				UtilizationPct: GetCreditCardUtilization(acc),
				HasBillingCycle: meta != nil,
			}
			if acc.CreditLimit != nil {
				ccSummary.CreditLimit = *acc.CreditLimit
			}

			if meta != nil {
				info := GetBillingCycleInfo(*meta, now)
				ccSummary.DueDate = info.DueDate
				ccSummary.DaysUntilDue = info.DaysUntilDue
				ccSummary.IsDueSoon = info.IsDueSoon

				if info.IsDueSoon {
					data.DueSoonCards = append(data.DueSoonCards, DueSoonCard{
						AccountName:  acc.Name,
						DueDate:      info.DueDate,
						DaysUntilDue: info.DaysUntilDue,
						Balance:      acc.CurrentBalance,
					})
				}
			}
			data.CreditCards = append(data.CreditCards, ccSummary)
		}
	}

	// Compute net worth in EGP using the exchange rate fetched earlier
	if exchangeRate > 0 {
		data.ExchangeRate = exchangeRate
		data.USDInEGP = data.USDTotal * exchangeRate
		// NetWorthEGP = (NetWorth - USDTotal) + USDInEGP
		// i.e., replace raw USD values with their EGP equivalent
		data.NetWorthEGP = (data.NetWorth - data.USDTotal) + data.USDInEGP
	}
	// If no rate available, NetWorthEGP stays 0 (template checks this)

	// People ledger summary — grouped by currency
	if s.personRepo != nil {
		t = time.Now()
		if persons, err := s.personRepo.GetAll(ctx); err == nil {
			egpSummary := PeopleCurrencySummary{Currency: "EGP"}
			usdSummary := PeopleCurrencySummary{Currency: "USD"}
			for _, p := range persons {
				// EGP balances
				if p.NetBalanceEGP > 0 {
					egpSummary.OwedToMe += p.NetBalanceEGP
				} else if p.NetBalanceEGP < 0 {
					egpSummary.IOwe += p.NetBalanceEGP
				}
				// USD balances
				if p.NetBalanceUSD > 0 {
					usdSummary.OwedToMe += p.NetBalanceUSD
				} else if p.NetBalanceUSD < 0 {
					usdSummary.IOwe += p.NetBalanceUSD
				}
				// Legacy fields (sum across currencies)
				if p.NetBalance > 0 {
					data.PeopleOwedToMe += p.NetBalance
				} else if p.NetBalance < 0 {
					data.PeopleIOwe += p.NetBalance
				}
			}
			// Only include currencies with non-zero balances
			if egpSummary.OwedToMe != 0 || egpSummary.IOwe != 0 {
				data.PeopleByCurrency = append(data.PeopleByCurrency, egpSummary)
			}
			if usdSummary.OwedToMe != 0 || usdSummary.IOwe != 0 {
				data.PeopleByCurrency = append(data.PeopleByCurrency, usdSummary)
			}
		}
		data.HasPeopleActivity = len(data.PeopleByCurrency) > 0 || data.PeopleOwedToMe != 0 || data.PeopleIOwe != 0
		logutil.Log(ctx).Debug("dashboard: loaded people", "duration_ms", time.Since(t).Milliseconds())
	}

	// TASK-063: Load active virtual accounts for dashboard widget
	if s.virtualAccountSvc != nil {
		t = time.Now()
		if accounts, err := s.virtualAccountSvc.GetAll(ctx); err == nil {
			data.VirtualAccounts = accounts
		}
		logutil.Log(ctx).Debug("dashboard: loaded virtual accounts", "duration_ms", time.Since(t).Milliseconds())
	}

	// Investment portfolio total
	if s.investmentRepo != nil {
		t = time.Now()
		if total, err := s.investmentRepo.GetTotalValuation(ctx); err == nil {
			data.InvestmentTotal = total
		}
		logutil.Log(ctx).Debug("dashboard: loaded investments", "duration_ms", time.Since(t).Milliseconds())
	}

	// Habit streak
	if s.streakSvc != nil {
		t = time.Now()
		if streak, err := s.streakSvc.GetStreak(ctx); err == nil {
			data.Streak = streak
		}
		logutil.Log(ctx).Debug("dashboard: loaded streak", "duration_ms", time.Since(t).Milliseconds())
	}

	// Load recent transactions
	t = time.Now()
	if txns, err := s.txRepo.GetRecentEnriched(ctx, 10); err != nil {
		slog.Warn("failed to load recent transactions", "error", err)
	} else {
		data.RecentTransactions = txns
	}
	logutil.Log(ctx).Debug("dashboard: loaded recent transactions", "duration_ms", time.Since(t).Milliseconds())

	// TASK-055: Net worth sparkline (last 30 days from snapshots)
	if s.snapshotSvc != nil {
		t = time.Now()
		if history, err := s.snapshotSvc.GetNetWorthHistory(ctx, 30); err == nil && len(history) >= 2 {
			data.NetWorthHistory = history
			// % change: (current - oldest) / |oldest| * 100
			oldest := history[0]
			current := history[len(history)-1]
			if oldest != 0 {
				data.NetWorthChange = (current - oldest) / abs(oldest) * 100
			}
		}
		logutil.Log(ctx).Debug("dashboard: loaded net worth history", "duration_ms", time.Since(t).Milliseconds())

		// Per-currency net worth history for dual sparkline
		t = time.Now()
		if byCurrency, err := s.snapshotSvc.GetNetWorthByCurrency(ctx, 30); err == nil && len(byCurrency) > 0 {
			data.NetWorthHistoryByCurrency = byCurrency
		}
		logutil.Log(ctx).Debug("dashboard: loaded per-currency history", "duration_ms", time.Since(t).Milliseconds())
	}

	// TASK-059: Per-account balance sparklines (last 30 days)
	if s.snapshotSvc != nil {
		t = time.Now()
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
		logutil.Log(ctx).Debug("dashboard: loaded account sparklines", "duration_ms", time.Since(t).Milliseconds(), "count", len(sparklines))
	}

	// TASK-069: Check account health constraints
	if s.healthSvc != nil {
		t = time.Now()
		data.HealthWarnings = s.healthSvc.CheckAll(ctx)
		logutil.Log(ctx).Debug("dashboard: checked health", "duration_ms", time.Since(t).Milliseconds(), "warnings", len(data.HealthWarnings))
	}

	// TASK-066: Load budgets with spending for dashboard widget
	if s.budgetSvc != nil {
		t = time.Now()
		if budgets, err := s.budgetSvc.GetAllWithSpending(ctx); err == nil {
			data.Budgets = budgets
		}
		logutil.Log(ctx).Debug("dashboard: loaded budgets", "duration_ms", time.Since(t).Milliseconds())
	}

	// TASK-056: Month-over-month spending comparison
	if s.db != nil {
		t = time.Now()
		s.computeSpendingComparison(ctx, &data)
		logutil.Log(ctx).Debug("dashboard: computed spending comparison", "duration_ms", time.Since(t).Milliseconds())
	}

	logutil.Log(ctx).Debug("dashboard: total load time", "duration_ms", time.Since(dashStart).Milliseconds())
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
//
// This method uses *DashboardData (pointer receiver for the parameter) so it can
// mutate the caller's struct directly. In Go, struct arguments are copied by default.
// Passing a pointer (&data) lets us modify the original — like PHP's &$data or
// Python's mutable object references.
//
// Uses direct SQL via s.db.QueryContext() instead of the repository layer because
// this is a complex aggregate query with CTEs (Common Table Expressions) that doesn't
// map well to a simple CRUD repository method.
// See: https://pkg.go.dev/database/sql#DB.QueryContext
func (s *DashboardService) computeSpendingComparison(ctx context.Context, data *DashboardData) {
	now := timeutil.Now()
	thisMonthStart := timeutil.MonthStart(now, s.timezone())
	lastMonthStart := timeutil.MonthStart(thisMonthStart.AddDate(0, -1, 0), s.timezone())
	nextMonthStart := timeutil.MonthEnd(now, s.timezone())

	// Spending per currency this month
	thisMonthByCurrency := make(map[string]float64)
	rows, err := s.db.QueryContext(ctx, `
		SELECT currency, COALESCE(SUM(amount), 0)
		FROM transactions
		WHERE type = 'expense' AND date >= $1 AND date < $2
		GROUP BY currency ORDER BY currency
	`, thisMonthStart, nextMonthStart)
	if err != nil {
		slog.Warn("failed to compute this month spending by currency", "error", err)
	} else {
		defer rows.Close()
		for rows.Next() {
			var cur string
			var amt float64
			if err := rows.Scan(&cur, &amt); err == nil {
				thisMonthByCurrency[cur] = amt
			}
		}
	}

	// Spending per currency last month
	lastMonthByCurrency := make(map[string]float64)
	rows2, err := s.db.QueryContext(ctx, `
		SELECT currency, COALESCE(SUM(amount), 0)
		FROM transactions
		WHERE type = 'expense' AND date >= $1 AND date < $2
		GROUP BY currency ORDER BY currency
	`, lastMonthStart, thisMonthStart)
	if err != nil {
		slog.Warn("failed to compute last month spending by currency", "error", err)
	} else {
		defer rows2.Close()
		for rows2.Next() {
			var cur string
			var amt float64
			if err := rows2.Scan(&cur, &amt); err == nil {
				lastMonthByCurrency[cur] = amt
			}
		}
	}

	// Collect all currencies that appear in either month
	currencies := make(map[string]bool)
	for c := range thisMonthByCurrency {
		currencies[c] = true
	}
	for c := range lastMonthByCurrency {
		currencies[c] = true
	}

	// Build CurrencySpending entries, EGP first
	orderedCurrencies := []string{}
	if currencies["EGP"] {
		orderedCurrencies = append(orderedCurrencies, "EGP")
	}
	for c := range currencies {
		if c != "EGP" {
			orderedCurrencies = append(orderedCurrencies, c)
		}
	}

	for _, cur := range orderedCurrencies {
		thisAmt := thisMonthByCurrency[cur]
		lastAmt := lastMonthByCurrency[cur]
		change := 0.0
		if lastAmt > 0 {
			change = (thisAmt - lastAmt) / lastAmt * 100
		}

		cs := CurrencySpending{
			Currency:  cur,
			ThisMonth: thisAmt,
			LastMonth: lastAmt,
			Change:    change,
		}

		// Top 3 categories for this currency
		cs.TopCategories = s.queryTopCategoriesForCurrency(ctx, cur, thisMonthStart, nextMonthStart, lastMonthStart)

		data.SpendingByCurrency = append(data.SpendingByCurrency, cs)

		// Populate legacy fields with EGP-only values (used by SpendingVelocity)
		if cur == "EGP" {
			data.ThisMonthSpending = thisAmt
			data.LastMonthSpending = lastAmt
			data.SpendingChange = change
			data.TopCategories = cs.TopCategories
		}
	}

	// TASK-060: Spending velocity — uses total spending across all currencies
	// converted to EGP via exchange rate for a unified pace indicator.
	daysInMonth := nextMonthStart.Sub(thisMonthStart).Hours() / 24
	daysElapsed := now.Day()
	daysLeft := int(daysInMonth) - daysElapsed
	dayProgress := float64(daysElapsed) / daysInMonth * 100

	sv := SpendingVelocity{
		DaysElapsed: daysElapsed,
		DaysTotal:   int(daysInMonth),
		DaysLeft:    daysLeft,
		DayProgress: dayProgress,
	}
	totalThis := 0.0
	totalLast := 0.0
	for _, cs := range data.SpendingByCurrency {
		rate := 1.0
		if cs.Currency == "USD" && data.ExchangeRate > 0 {
			rate = data.ExchangeRate
		}
		totalThis += cs.ThisMonth * rate
		totalLast += cs.LastMonth * rate
	}
	if totalLast > 0 {
		sv.Percentage = totalThis / totalLast * 100
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
}

// queryTopCategoriesForCurrency returns the top 3 spending categories for a given
// currency in the current month, with their month-over-month change %.
func (s *DashboardService) queryTopCategoriesForCurrency(ctx context.Context, currency string, thisMonthStart, nextMonthStart, lastMonthStart time.Time) []CategoryChange {
	rows, err := s.db.QueryContext(ctx, `
		WITH this_month AS (
			SELECT COALESCE(c.name, 'Uncategorized') AS cat_name,
				COALESCE(c.icon, '') AS cat_icon,
				SUM(t.amount) AS amount
			FROM transactions t
			LEFT JOIN categories c ON t.category_id = c.id
			WHERE t.type = 'expense' AND t.currency = $4::currency_type
				AND t.date >= $1 AND t.date < $2
			GROUP BY c.name, c.icon
			ORDER BY SUM(t.amount) DESC
			LIMIT 3
		),
		last_month AS (
			SELECT COALESCE(c.name, 'Uncategorized') AS cat_name,
				SUM(t.amount) AS amount
			FROM transactions t
			LEFT JOIN categories c ON t.category_id = c.id
			WHERE t.type = 'expense' AND t.currency = $4::currency_type
				AND t.date >= $3 AND t.date < $1
			GROUP BY c.name
		)
		SELECT tm.cat_name, tm.cat_icon, tm.amount,
			COALESCE(lm.amount, 0) AS last_amount
		FROM this_month tm
		LEFT JOIN last_month lm ON tm.cat_name = lm.cat_name
	`, thisMonthStart, nextMonthStart, lastMonthStart, currency)
	if err != nil {
		return nil
	}
	defer rows.Close()

	var categories []CategoryChange
	for rows.Next() {
		var name, icon string
		var thisAmt, lastAmt float64
		if err := rows.Scan(&name, &icon, &thisAmt, &lastAmt); err != nil {
			continue
		}
		change := 0.0
		if lastAmt > 0 {
			change = (thisAmt - lastAmt) / lastAmt * 100
		}
		categories = append(categories, CategoryChange{
			Name:   name,
			Icon:   icon,
			Amount: thisAmt,
			Change: change,
			IsUp:   change > 0,
		})
	}
	return categories
}
