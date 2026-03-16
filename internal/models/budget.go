// Package models — budget.go defines the Budget model for monthly spending limits.
//
// Budgets let users set caps on category spending (e.g., max E£3,000/month on Groceries).
// The BudgetWithSpending type adds computed fields for the current month's actual spending.
//
// Laravel analogy: Budget is an Eloquent model. BudgetWithSpending is like an
// API Resource (or View Model) that combines the model with aggregated data
// computed from related transactions — similar to when you'd do:
//   $budget->loadCount('transactions as spent')
// but the aggregation is done in the service layer, not via Eloquent.
//
// Django analogy: Budget is a Model. BudgetWithSpending is like annotating a
// queryset with .annotate(spent=Sum('transaction__amount')) and then adding
// computed properties. But since Go doesn't have queryset annotations, we
// compute these values in the service layer and return a richer struct.
package models

import "time"

// Budget represents a monthly spending limit for a specific category.
//
// One budget per category. The service layer queries transactions for the
// current month to compute actual spending against this limit.
type Budget struct {
	ID           string    `json:"id" db:"id"`
	UserID       string    `json:"user_id" db:"user_id"`
	CategoryID   string    `json:"category_id" db:"category_id"`     // FK to categories — one budget per category
	MonthlyLimit float64   `json:"monthly_limit" db:"monthly_limit"` // the spending cap in the given currency (e.g., 3000.0 for E£3,000/month)
	Currency     Currency  `json:"currency" db:"currency"`           // which currency this limit is expressed in
	IsActive     bool      `json:"is_active" db:"is_active"`         // toggle budget on/off without deleting it
	CreatedAt    time.Time `json:"created_at" db:"created_at"`
	UpdatedAt    time.Time `json:"updated_at" db:"updated_at"`
}

// BudgetWithSpending combines a budget with actual spending data for the current month.
// This is computed by the service layer (not stored in the database).
//
// STRUCT EMBEDDING explained:
// The line "Budget" (without a field name) is called an EMBEDDED struct. It means
// BudgetWithSpending "inherits" all fields and methods from Budget.
//
// This is Go's alternative to class inheritance:
//   - PHP:    class BudgetWithSpending extends Budget { ... }
//   - Python: class BudgetWithSpending(Budget): ...
//   - Go:     type BudgetWithSpending struct { Budget; ... }
//
// You can access embedded fields directly: bws.MonthlyLimit (not bws.Budget.MonthlyLimit).
// Both syntaxes work, but the short form is idiomatic.
//
// See: https://go.dev/doc/effective_go#embedding
//
// Note: The extra fields (CategoryName, Spent, etc.) have NO struct tags because
// they're never serialized to JSON or read from the database directly. They're
// computed in-memory by the service layer.
type BudgetWithSpending struct {
	Budget                        // embedded struct — "inherits" all Budget fields (ID, CategoryID, MonthlyLimit, etc.)
	CategoryName string           // joined from categories table (e.g., "Groceries")
	CategoryIcon string           // emoji icon (e.g., "🛒") — empty if not set
	Spent        float64          // total spent this month in this category
	Remaining    float64          // monthly_limit - spent (negative if over budget — user spent more than allowed)
	Percentage   float64          // (spent / monthly_limit) * 100 — used for progress bar rendering
	Status       string           // traffic-light status: "green" (0-70%), "amber" (70-90%), "red" (90%+)
}

// CategoryDisplayName returns the category name prefixed with its icon if set.
func (b BudgetWithSpending) CategoryDisplayName() string {
	if b.CategoryIcon != "" {
		return b.CategoryIcon + " " + b.CategoryName
	}
	return b.CategoryName
}
