// Package service — StreakService tracks consecutive days of transaction logging.
//
// Gamification feature: encourages the habit of daily expense tracking by showing
// a streak counter ("3 day streak!") and weekly transaction count on the dashboard.
//
// Laravel analogy: Like a GamificationService that queries transactions by date
// to compute streaks. You might use Carbon::today(), Carbon::yesterday(), etc.
// to walk backwards through dates. In Go, we use time.AddDate(0, 0, -1) for the
// same purpose.
//
// Django analogy: Like a service function using transactions.values('date').distinct()
// and iterating to count consecutive days. Or a raw SQL query with DISTINCT date.
//
// Design: This service uses direct SQL (*sql.DB) instead of a repository because
// the streak computation is a specialized aggregate query (DISTINCT dates, ordered DESC).
// It's too specific for a general-purpose repository method.
//
// The streak algorithm: query all distinct transaction dates descending, then walk
// backwards from today counting consecutive days. A gap breaks the streak.
//
// See: https://pkg.go.dev/database/sql#DB.QueryContext for rows-based queries
package service

import (
	"context"
	"database/sql"
	"time"
)

// StreakService uses *sql.DB directly (like ReportsService) for specialized queries.
type StreakService struct {
	db *sql.DB
}

// NewStreakService creates the service with a database connection pool.
func NewStreakService(db *sql.DB) *StreakService {
	return &StreakService{db: db}
}

// StreakInfo holds the current streak and weekly count.
type StreakInfo struct {
	ConsecutiveDays int // consecutive days with at least one transaction
	WeeklyCount     int // transactions this week (Mon-Sun)
}

// GetStreak computes the current logging streak.
//
// Algorithm:
//   1. Query DISTINCT transaction dates, sorted DESC, limited to 365 days
//   2. Walk backwards from today: if the date matches expected, increment streak
//   3. If there's a gap, break
//   4. Separately count this week's total transactions (Mon-Sun)
//
// Go pattern: `defer rows.Close()` ensures the database rows are released back
// to the connection pool even if an error occurs. This is CRITICAL in Go — forgetting
// to close rows leaks database connections. Like PHP's PDO cleanup or Django's
// cursor.close(), but in Go it's your responsibility (no garbage collector for DB resources).
func (s *StreakService) GetStreak(ctx context.Context) (StreakInfo, error) {
	var info StreakInfo

	// Count consecutive days with transactions, going backwards from today
	rows, err := s.db.QueryContext(ctx, `
		SELECT DISTINCT date::date AS d FROM transactions
		WHERE date <= CURRENT_DATE
		ORDER BY d DESC
		LIMIT 365
	`)
	if err != nil {
		return info, err
	}
	defer rows.Close()

	today := time.Now().Truncate(24 * time.Hour)
	expected := today
	for rows.Next() {
		var d time.Time
		if err := rows.Scan(&d); err != nil {
			return info, err
		}
		d = d.Truncate(24 * time.Hour)
		if d.Equal(expected) {
			info.ConsecutiveDays++
			expected = expected.AddDate(0, 0, -1)
		} else if d.Before(expected) {
			break
		}
	}

	// Weekly count (current week, Mon-Sun)
	now := time.Now()
	weekday := int(now.Weekday())
	if weekday == 0 {
		weekday = 7
	}
	monday := now.AddDate(0, 0, -(weekday - 1)).Truncate(24 * time.Hour)

	err = s.db.QueryRowContext(ctx, `
		SELECT COUNT(*) FROM transactions WHERE date >= $1 AND date <= $2
	`, monday, now).Scan(&info.WeeklyCount)
	if err != nil {
		return info, err
	}

	return info, nil
}
