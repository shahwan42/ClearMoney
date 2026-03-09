// Package service — ReportsService aggregates financial data for reports.
//
// This service uses DIRECT SQL queries via *sql.DB instead of going through a
// repository. This is a pragmatic choice for complex aggregate queries with JOINs,
// GROUP BY, and CTEs — they don't fit the simple CRUD pattern of repositories.
//
// Laravel analogy: Like using DB::raw() or DB::select() for complex reporting
// queries that are too intricate for Eloquent scopes. Or like a dedicated
// ReportingService that uses raw SQL for performance.
//
// Django analogy: Like using raw SQL with connection.cursor() or aggregation
// functions (annotate, aggregate) for complex reporting queries.
//
// Go SQL patterns:
//   - QueryContext: returns multiple rows (like PDO::fetchAll or cursor.fetchall)
//   - QueryRowContext: returns a single row (like PDO::fetch or cursor.fetchone)
//   - Parameterized queries: $1, $2, $3 (PostgreSQL) — prevents SQL injection.
//     Like Laravel's ? placeholders or Django's %s parameters.
//   - rows.Close(): MUST be called (via defer) to release the DB connection back to the pool.
//
// See: https://pkg.go.dev/database/sql for Go's database/sql package
// See: https://go.dev/doc/database/querying for querying patterns
package service

import (
	"context"
	"database/sql"
	"fmt"
	"time"

	"github.com/ahmedelsamadisi/clearmoney/internal/models"
)

// CategorySpending represents spending in a single category for a period.
type CategorySpending struct {
	CategoryID   string
	CategoryName string
	Amount       float64
	Percentage   float64 // percentage of total spending
}

// MonthSummary holds income and expense totals for a single month.
type MonthSummary struct {
	Year     int
	Month    time.Month
	Income   float64
	Expenses float64
	Net      float64 // Income - Expenses
}

// ReportFilter holds optional filters for the reports query.
type ReportFilter struct {
	AccountID string // filter by specific account
	Currency  string // filter by currency (EGP or USD)
}

// ReportsData holds all data for the reports page.
type ReportsData struct {
	// Selected month
	Year  int
	Month time.Month

	// Active filters
	Filter ReportFilter

	// Spending by category for the selected month
	SpendingByCategory []CategorySpending
	TotalSpending      float64

	// TASK-057: Chart segments for the donut chart (auto-generated from SpendingByCategory)
	ChartSegments []models.ChartSegment

	// Income vs expenses comparison
	CurrentMonth  MonthSummary
	PreviousMonth MonthSummary

	// TASK-058: 6-month income vs expenses history for bar chart
	MonthlyHistory []MonthSummary
	// Pre-computed bar chart data (groups with height percentages)
	BarGroups []BarGroup
	BarLegend []LegendItem
}

// BarGroup holds one group of bars in a bar chart (e.g., one month).
type BarGroup struct {
	Label string
	Bars  []BarValue
}

// BarValue represents a single bar in a bar chart.
type BarValue struct {
	Value     float64
	HeightPct float64
	Color     string
	Label     string
}

// LegendItem is a color + label pair for chart legends.
type LegendItem struct {
	Label string
	Color string
}

// ReportsService computes report data from transactions.
// Unlike other services that depend on repositories, this one holds a direct *sql.DB
// reference because its queries are complex aggregates (GROUP BY, CTEs, JOINs)
// that don't fit the repository pattern.
//
// *sql.DB is a connection pool, not a single connection. It's safe to share across
// goroutines. See: https://pkg.go.dev/database/sql#DB
type ReportsService struct {
	db *sql.DB
}

// NewReportsService creates a reports service with a database connection pool.
func NewReportsService(db *sql.DB) *ReportsService {
	return &ReportsService{db: db}
}

// GetMonthlyReport generates the full report for a given month with optional filters.
func (s *ReportsService) GetMonthlyReport(ctx context.Context, year int, month time.Month, filter ReportFilter) (ReportsData, error) {
	data := ReportsData{
		Year:   year,
		Month:  month,
		Filter: filter,
	}

	// Spending by category
	spending, total, err := s.getSpendingByCategory(ctx, year, month, filter)
	if err != nil {
		return data, fmt.Errorf("spending by category: %w", err)
	}
	data.SpendingByCategory = spending
	data.TotalSpending = total

	// Current month summary
	data.CurrentMonth, _ = s.getMonthSummary(ctx, year, month, filter)

	// Previous month summary
	prevYear, prevMonth := year, month-1
	if prevMonth == 0 {
		prevMonth = 12
		prevYear--
	}
	data.PreviousMonth, _ = s.getMonthSummary(ctx, prevYear, prevMonth, filter)

	// TASK-057: Generate donut chart segments from spending categories.
	// Uses the 8-color chart palette, one color per category.
	data.ChartSegments = s.buildChartSegments(spending, total)

	// TASK-058: 6-month income vs expenses history for bar chart
	data.MonthlyHistory = s.getMonthlyHistory(ctx, year, month, filter)
	data.BarGroups, data.BarLegend = s.buildBarChart(data.MonthlyHistory)

	return data, nil
}

// chartPalette is the 8-color palette used for donut chart segments.
// Matches the palette defined in handler/charts.go.
var chartPalette = []string{
	"#0d9488", "#dc2626", "#2563eb", "#d97706",
	"#7c3aed", "#059669", "#db2777", "#4f46e5",
}

// buildChartSegments converts category spending into donut chart segments.
func (s *ReportsService) buildChartSegments(spending []CategorySpending, total float64) []models.ChartSegment {
	if total == 0 || len(spending) == 0 {
		return nil
	}
	segments := make([]models.ChartSegment, len(spending))
	for i, cs := range spending {
		segments[i] = models.ChartSegment{
			Label:      cs.CategoryName,
			Amount:     cs.Amount,
			Percentage: cs.Percentage,
			Color:      chartPalette[i%len(chartPalette)],
		}
	}
	return segments
}

// buildBarChart converts monthly history into bar chart groups with pre-computed heights.
func (s *ReportsService) buildBarChart(history []MonthSummary) ([]BarGroup, []LegendItem) {
	if len(history) == 0 {
		return nil, nil
	}

	// Find max value for height normalization
	maxVal := 0.0
	for _, m := range history {
		if m.Income > maxVal {
			maxVal = m.Income
		}
		if m.Expenses > maxVal {
			maxVal = m.Expenses
		}
	}

	groups := make([]BarGroup, len(history))
	for i, m := range history {
		incomeH, expenseH := 0.0, 0.0
		if maxVal > 0 {
			incomeH = m.Income / maxVal * 100
			expenseH = m.Expenses / maxVal * 100
		}
		groups[i] = BarGroup{
			Label: m.Month.String()[:3], // "Jan", "Feb", etc.
			Bars: []BarValue{
				{Value: m.Income, HeightPct: incomeH, Color: "#059669", Label: "Income"},
				{Value: m.Expenses, HeightPct: expenseH, Color: "#dc2626", Label: "Expenses"},
			},
		}
	}

	legend := []LegendItem{
		{Label: "Income", Color: "#059669"},
		{Label: "Expenses", Color: "#dc2626"},
	}

	return groups, legend
}

// getMonthlyHistory returns income/expenses for the last 6 months (for the bar chart).
func (s *ReportsService) getMonthlyHistory(ctx context.Context, year int, month time.Month, filter ReportFilter) []MonthSummary {
	var history []MonthSummary
	for i := 5; i >= 0; i-- {
		// Walk backward from current month
		m := month - time.Month(i)
		y := year
		for m <= 0 {
			m += 12
			y--
		}
		summary, err := s.getMonthSummary(ctx, y, m, filter)
		if err != nil {
			summary = MonthSummary{Year: y, Month: m}
		}
		history = append(history, summary)
	}
	return history
}

// getSpendingByCategory returns expense totals grouped by category for a month.
//
// Dynamic query building: This function conditionally appends WHERE clauses
// based on which filters are set. The argN counter tracks PostgreSQL parameter
// numbers ($1, $2, $3...). This is Go's equivalent of Laravel's Query Builder:
//   ->when($accountId, fn($q) => $q->where('account_id', $accountId))
// Or Django's conditional Q objects.
//
// The `args := []any{...}` uses Go's `any` type (alias for `interface{}`) which
// can hold any value — like PHP's mixed type or Python's Any type hint.
func (s *ReportsService) getSpendingByCategory(ctx context.Context, year int, month time.Month, filter ReportFilter) ([]CategorySpending, float64, error) {
	startDate := time.Date(year, month, 1, 0, 0, 0, 0, time.UTC)
	endDate := startDate.AddDate(0, 1, 0)

	query := `
		SELECT COALESCE(t.category_id::text, ''), COALESCE(c.name, 'Uncategorized'), SUM(t.amount)
		FROM transactions t
		LEFT JOIN categories c ON t.category_id = c.id
		WHERE t.type = 'expense' AND t.date >= $1 AND t.date < $2`
	args := []any{startDate, endDate}
	argN := 3

	if filter.AccountID != "" {
		query += fmt.Sprintf(" AND t.account_id = $%d", argN)
		args = append(args, filter.AccountID)
		argN++
	}
	if filter.Currency != "" {
		query += fmt.Sprintf(" AND t.currency = $%d", argN)
		args = append(args, filter.Currency)
		argN++
	}

	query += ` GROUP BY t.category_id, c.name ORDER BY SUM(t.amount) DESC`

	rows, err := s.db.QueryContext(ctx, query, args...)
	if err != nil {
		return nil, 0, fmt.Errorf("querying spending: %w", err)
	}
	defer rows.Close()

	var spending []CategorySpending
	var total float64
	for rows.Next() {
		var cs CategorySpending
		if err := rows.Scan(&cs.CategoryID, &cs.CategoryName, &cs.Amount); err != nil {
			return nil, 0, err
		}
		total += cs.Amount
		spending = append(spending, cs)
	}

	// Calculate percentages
	if total > 0 {
		for i := range spending {
			spending[i].Percentage = (spending[i].Amount / total) * 100
		}
	}

	return spending, total, rows.Err()
}

// getMonthSummary returns income and expense totals for a month.
func (s *ReportsService) getMonthSummary(ctx context.Context, year int, month time.Month, filter ReportFilter) (MonthSummary, error) {
	startDate := time.Date(year, month, 1, 0, 0, 0, 0, time.UTC)
	endDate := startDate.AddDate(0, 1, 0)

	summary := MonthSummary{Year: year, Month: month}

	query := `
		SELECT
			COALESCE(SUM(CASE WHEN type = 'income' THEN amount ELSE 0 END), 0),
			COALESCE(SUM(CASE WHEN type = 'expense' THEN amount ELSE 0 END), 0)
		FROM transactions
		WHERE date >= $1 AND date < $2`
	args := []any{startDate, endDate}
	argN := 3

	if filter.AccountID != "" {
		query += fmt.Sprintf(" AND account_id = $%d", argN)
		args = append(args, filter.AccountID)
		argN++
	}
	if filter.Currency != "" {
		query += fmt.Sprintf(" AND currency = $%d", argN)
		args = append(args, filter.Currency)
		argN++
	}

	err := s.db.QueryRowContext(ctx, query, args...).Scan(&summary.Income, &summary.Expenses)
	if err != nil {
		return summary, err
	}

	summary.Net = summary.Income - summary.Expenses
	return summary, nil
}
