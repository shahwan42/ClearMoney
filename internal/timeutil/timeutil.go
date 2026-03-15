// Package timeutil provides centralized timezone-aware time helpers.
//
// All business logic should use timeutil.Now() instead of time.Now() to ensure
// consistent UTC storage. Calendar-date operations (like "today", "this month")
// should use Today() and MonthStart()/MonthEnd() with the user's timezone.
//
// This is similar to Laravel's Carbon::now('UTC') or Django's timezone.now().
//
// Key rules:
//   - Store all times in UTC (timeutil.Now())
//   - Convert to user timezone only for display (InUserTZ / template functions)
//   - Parse user date input in their timezone (ParseDateInTZ)
//   - Use Today(loc) for "what calendar day is it for the user?"
//   - Use MonthStart/MonthEnd for month-boundary queries
//
// Performance timing (request duration, debug benchmarks) should still use
// time.Now() directly — those measure wall-clock elapsed time, not user-facing dates.
package timeutil

import (
	"fmt"
	"log/slog"
	"time"
)

// Now returns the current time in UTC.
// Use this instead of time.Now() for all business logic timestamps.
func Now() time.Time {
	return time.Now().UTC()
}

// Today returns midnight of the current calendar day in the user's timezone,
// expressed as UTC. For example, if it's 11pm UTC and the user is in Cairo (UTC+2),
// it's already the next day there — Today returns that next day at midnight Cairo
// time, converted to UTC (which is 10pm UTC the previous day).
//
// This is the correct way to determine "what date is it for the user right now?"
func Today(loc *time.Location) time.Time {
	now := time.Now().In(loc)
	return time.Date(now.Year(), now.Month(), now.Day(), 0, 0, 0, 0, loc).UTC()
}

// MonthStart returns the first instant of the month that t falls in (in the
// user's timezone), converted to UTC. Used for month-range queries:
//
//	WHERE date >= $monthStart AND date < $monthEnd
func MonthStart(t time.Time, loc *time.Location) time.Time {
	local := t.In(loc)
	return time.Date(local.Year(), local.Month(), 1, 0, 0, 0, 0, loc).UTC()
}

// MonthEnd returns the first instant of the month after t (in the user's
// timezone), converted to UTC. Used as the exclusive upper bound in
// month-range queries: WHERE date >= $monthStart AND date < $monthEnd
func MonthEnd(t time.Time, loc *time.Location) time.Time {
	local := t.In(loc)
	return time.Date(local.Year(), local.Month()+1, 1, 0, 0, 0, 0, loc).UTC()
}

// ParseDateInTZ parses a "YYYY-MM-DD" string as midnight in the given timezone,
// then returns the result in UTC. This is the correct way to parse user-submitted
// date inputs — the user means "this date in my timezone."
//
// For example, parsing "2026-03-15" in Cairo (UTC+2) returns 2026-03-14T22:00:00Z.
func ParseDateInTZ(s string, loc *time.Location) (time.Time, error) {
	t, err := time.Parse("2006-01-02", s)
	if err != nil {
		return time.Time{}, fmt.Errorf("parse date %q: %w", s, err)
	}
	// Re-interpret the parsed year/month/day in the user's timezone
	return time.Date(t.Year(), t.Month(), t.Day(), 0, 0, 0, 0, loc).UTC(), nil
}

// InUserTZ converts a UTC time to the user's timezone for display purposes.
// Template functions call this before formatting dates.
func InUserTZ(t time.Time, loc *time.Location) time.Time {
	return t.In(loc)
}

// LoadLocation wraps time.LoadLocation with a fallback to UTC on error.
// Logs a warning if the requested timezone is invalid.
func LoadLocation(name string) *time.Location {
	loc, err := time.LoadLocation(name)
	if err != nil {
		slog.Warn("invalid timezone, falling back to UTC", "timezone", name, "error", err)
		return time.UTC
	}
	return loc
}
