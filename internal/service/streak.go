// Package service — StreakService tracks consecutive days of transaction logging.
// Encourages the habit of daily expense tracking.
package service

import (
	"context"
	"database/sql"
	"time"
)

type StreakService struct {
	db *sql.DB
}

func NewStreakService(db *sql.DB) *StreakService {
	return &StreakService{db: db}
}

// StreakInfo holds the current streak and weekly count.
type StreakInfo struct {
	ConsecutiveDays int // consecutive days with at least one transaction
	WeeklyCount     int // transactions this week (Mon-Sun)
}

// GetStreak computes the current logging streak.
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
