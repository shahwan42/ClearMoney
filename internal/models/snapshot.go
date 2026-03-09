// Package models — snapshot.go defines structs for daily balance snapshots.
//
// Snapshots solve the "time travel" problem: without them, we can only show
// CURRENT account balances. With snapshots, we can render sparklines (tiny
// inline charts), trend indicators, and month-over-month comparisons.
//
// Snapshots are created by a scheduled job (internal/jobs/) that runs daily.
// Each run inserts one DailySnapshot row (aggregate net worth) and one
// AccountSnapshot row per active account (individual balance).
//
// Laravel analogy: Like an Eloquent model populated by a scheduled Artisan
// command (php artisan schedule:run). You'd register it in app/Console/Kernel.php.
// The DailySnapshot is like a Report model that stores pre-computed aggregates.
//
// Django analogy: Like a Model populated by a management command
// (python manage.py create_daily_snapshot) that runs via cron or Celery Beat.
// Similar to creating materialized summary tables for a dashboard.
//
// These tables are APPEND-ONLY (no updates) — one row per day, inserted at
// end of day. If you need to fix a past snapshot, insert a corrected row.
package models

import "time"

// DailySnapshot captures a single day's aggregate financial state.
// One row per day. Think of it as a "daily report card" for your finances.
//
// Used for:
//   - Dashboard net worth sparkline (30-day trend line)
//   - Month-over-month spending comparison ("you spent 15% less than last month")
//   - Historical net worth tracking
//
// The ExchangeRate is snapshotted alongside the financial data so that
// historical net worth values remain consistent even if exchange rates change.
type DailySnapshot struct {
	ID            string    `json:"id" db:"id"`
	Date          time.Time `json:"date" db:"date"`                    // DATE type in PostgreSQL — one row per calendar day
	NetWorthEGP   float64   `json:"net_worth_egp" db:"net_worth_egp"`  // all balances converted to EGP using that day's exchange rate
	NetWorthRaw   float64   `json:"net_worth_raw" db:"net_worth_raw"`  // raw sum without currency conversion (mixing EGP and USD — less accurate but simpler)
	ExchangeRate  float64   `json:"exchange_rate" db:"exchange_rate"`   // USD/EGP rate at time of snapshot (e.g., 50.5) — frozen for historical accuracy
	DailySpending float64   `json:"daily_spending" db:"daily_spending"` // total expense transactions that day (always positive)
	DailyIncome   float64   `json:"daily_income" db:"daily_income"`     // total income transactions that day (always positive)
	CreatedAt     time.Time `json:"created_at" db:"created_at"`         // no UpdatedAt — snapshots are immutable (append-only)
}

// AccountSnapshot captures one account's balance at end of day.
// One row per (date, account_id) pair — this is the per-account counterpart
// to DailySnapshot.
//
// Used for:
//   - Per-account balance sparklines (the tiny charts on account cards)
//   - Credit card utilization history (balance / credit_limit over time)
//   - Detecting balance trends (rising, falling, stable)
//
// Note the composite uniqueness: the combination of (Date, AccountID) should be
// unique, enforced by a database constraint. This prevents duplicate snapshots
// for the same account on the same day.
type AccountSnapshot struct {
	ID        string    `json:"id" db:"id"`
	Date      time.Time `json:"date" db:"date"`                  // DATE — one row per account per calendar day
	AccountID string    `json:"account_id" db:"account_id"`      // FK to accounts table
	Balance   float64   `json:"balance" db:"balance"`            // the account's CurrentBalance at end of this day
	CreatedAt time.Time `json:"created_at" db:"created_at"`      // no UpdatedAt — snapshots are immutable
}
