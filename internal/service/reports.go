// Package service — ReportsService aggregates financial data for reports.
//
// Think of it like Laravel's Eloquent aggregate queries but wrapped
// in a service layer for reuse.
package service

import (
	"context"
	"database/sql"
	"fmt"
	"time"
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

	// Income vs expenses comparison
	CurrentMonth  MonthSummary
	PreviousMonth MonthSummary
}

// ReportsService computes report data from transactions.
type ReportsService struct {
	db *sql.DB
}

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

	return data, nil
}

// getSpendingByCategory returns expense totals grouped by category for a month.
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
