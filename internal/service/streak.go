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

	"github.com/shahwan42/clearmoney/internal/timeutil"
)

// StreakService uses *sql.DB directly (like ReportsService) for specialized queries.
type StreakService struct {
	db  *sql.DB
	loc *time.Location // User timezone for "today" calculation
}

// NewStreakService creates the service with a database connection pool.
func NewStreakService(db *sql.DB) *StreakService {
	return &StreakService{db: db}
}

// SetTimezone sets the user's timezone for calendar-date operations.
func (s *StreakService) SetTimezone(loc *time.Location) {
	s.loc = loc
}

// timezone returns the configured timezone or UTC as fallback.
func (s *StreakService) timezone() *time.Location {
	if s.loc != nil {
		return s.loc
	}
	return time.UTC
}

// StreakInfo holds the current streak and weekly count.
type StreakInfo struct {
	ConsecutiveDays int  // consecutive days with at least one transaction
	WeeklyCount     int  // transactions this week (Mon-Sun)
	ActiveToday     bool // whether there's a transaction logged today
}

// GetStreak computes the current logging streak.
//
// Algorithm:
//  1. Query DISTINCT transaction dates, sorted DESC, limited to 365 days
//  2. Walk backwards from today: if the date matches expected, increment streak
//  3. If there's a gap, break
//  4. Separately count this week's total transactions (Mon-Sun)
//
// Go pattern: `defer rows.Close()` ensures the database rows are released back
// to the connection pool even if an error occurs. This is CRITICAL in Go — forgetting
// to close rows leaks database connections. Like PHP's PDO cleanup or Django's
// cursor.close(), but in Go it's your responsibility (no garbage collector for DB resources).
func (s *StreakService) GetStreak(ctx context.Context) (StreakInfo, error) {
	var info StreakInfo

	today := timeutil.Today(s.timezone())

	// Count consecutive days with transactions, going backwards from today
	rows, err := s.db.QueryContext(ctx, `
		SELECT DISTINCT date::date AS d FROM transactions
		WHERE date <= $1
		ORDER BY d DESC
		LIMIT 365
	`, today)
	if err != nil {
		return info, err
	}
	defer rows.Close()

	loc := s.timezone()
	expected := today
	for rows.Next() {
		var d time.Time
		if err := rows.Scan(&d); err != nil {
			return info, err
		}
		// Normalize DB date the same way timeutil.Today() normalizes "now":
		// interpret the calendar date as midnight in the user's timezone → UTC.
		d = time.Date(d.Year(), d.Month(), d.Day(), 0, 0, 0, 0, loc).UTC()

		if d.Equal(expected) {
			info.ConsecutiveDays++
			if expected.Equal(today) {
				info.ActiveToday = true
			}
			expected = expected.AddDate(0, 0, -1)
		} else if d.Before(expected) {
			// Grace period: if no transaction today but yesterday has one,
			// start counting from yesterday. The user still has until end
			// of today to extend their streak (like Duolingo/GitHub).
			if info.ConsecutiveDays == 0 && d.Equal(today.AddDate(0, 0, -1)) {
				info.ConsecutiveDays++
				expected = d.AddDate(0, 0, -1)
			} else {
				break
			}
		}
	}

	if err := rows.Err(); err != nil {
		return info, err
	}

	// Weekly count (current week, Mon-Sun)
	now := timeutil.Now().In(loc)
	weekday := int(now.Weekday())
	if weekday == 0 {
		weekday = 7
	}
	mon := now.AddDate(0, 0, -(weekday - 1))
	monday := time.Date(mon.Year(), mon.Month(), mon.Day(), 0, 0, 0, 0, loc).UTC()

	err = s.db.QueryRowContext(ctx, `
		SELECT COUNT(*) FROM transactions WHERE date >= $1 AND date <= $2
	`, monday, now).Scan(&info.WeeklyCount)
	if err != nil {
		return info, err
	}

	return info, nil
}
