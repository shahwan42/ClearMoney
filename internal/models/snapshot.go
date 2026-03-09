// Package models — snapshot.go defines structs for daily balance snapshots.
//
// Snapshots capture historical data that would otherwise be lost (account balances,
// net worth, daily spending/income). Without snapshots, we can only show current
// values — with them, we can render sparklines and trend indicators.
//
// In Django terms, this is like a model that stores daily aggregations.
// In Laravel, think of it as a daily_snapshots Eloquent model with scheduled creation.
package models

import "time"

// DailySnapshot captures a single day's aggregate financial state.
// One row per day. Used for the dashboard net worth sparkline and
// month-over-month spending comparison.
type DailySnapshot struct {
	ID            string    `json:"id" db:"id"`
	Date          time.Time `json:"date" db:"date"`                     // DATE, one per day
	NetWorthEGP   float64   `json:"net_worth_egp" db:"net_worth_egp"`   // all balances converted to EGP
	NetWorthRaw   float64   `json:"net_worth_raw" db:"net_worth_raw"`   // raw sum (no currency conversion)
	ExchangeRate  float64   `json:"exchange_rate" db:"exchange_rate"`    // USD/EGP rate at time of snapshot
	DailySpending float64   `json:"daily_spending" db:"daily_spending"`  // total expenses that day
	DailyIncome   float64   `json:"daily_income" db:"daily_income"`      // total income that day
	CreatedAt     time.Time `json:"created_at" db:"created_at"`
}

// AccountSnapshot captures one account's balance at end of day.
// One row per (date, account) pair. Used for per-account sparklines
// and credit card utilization history.
type AccountSnapshot struct {
	ID        string    `json:"id" db:"id"`
	Date      time.Time `json:"date" db:"date"`
	AccountID string    `json:"account_id" db:"account_id"`
	Balance   float64   `json:"balance" db:"balance"`
	CreatedAt time.Time `json:"created_at" db:"created_at"`
}
