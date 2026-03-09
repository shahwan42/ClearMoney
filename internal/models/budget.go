// Package models — budget.go defines the Budget model for monthly spending limits.
//
// Budgets let users set caps on category spending (e.g., max E£3,000/month on Groceries).
// The BudgetWithSpending type adds computed fields for the current month's actual spending.
//
// In Laravel terms, Budget is an Eloquent model. BudgetWithSpending is like a
// Resource that combines the model with aggregated data from transactions.
package models

import "time"

// Budget represents a monthly spending limit for a specific category.
type Budget struct {
	ID           string    `json:"id" db:"id"`
	CategoryID   string    `json:"category_id" db:"category_id"`
	MonthlyLimit float64   `json:"monthly_limit" db:"monthly_limit"`
	Currency     Currency  `json:"currency" db:"currency"`
	IsActive     bool      `json:"is_active" db:"is_active"`
	CreatedAt    time.Time `json:"created_at" db:"created_at"`
	UpdatedAt    time.Time `json:"updated_at" db:"updated_at"`
}

// BudgetWithSpending combines a budget with actual spending data for the current month.
// This is computed by the service layer (not stored in the database).
type BudgetWithSpending struct {
	Budget
	CategoryName string  // joined from categories table
	Spent        float64 // total spent this month in this category
	Remaining    float64 // monthly_limit - spent (negative if over budget)
	Percentage   float64 // (spent / monthly_limit) * 100
	Status       string  // "green" (0-70%), "amber" (70-90%), "red" (90%+)
}
