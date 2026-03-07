// Package service — RecurringService handles recurring transaction rules.
//
// When a rule's next_due_date is today or earlier:
// - auto_confirm=true: create the transaction automatically
// - auto_confirm=false: return it as "pending" for user confirmation
//
// After processing, advance next_due_date based on frequency.
package service

import (
	"context"
	"encoding/json"
	"fmt"
	"time"

	"github.com/ahmedelsamadisi/clearmoney/internal/models"
	"github.com/ahmedelsamadisi/clearmoney/internal/repository"
)

// RecurringService manages recurring transaction rules.
type RecurringService struct {
	recurringRepo *repository.RecurringRepo
	txSvc         *TransactionService
}

func NewRecurringService(recurringRepo *repository.RecurringRepo, txSvc *TransactionService) *RecurringService {
	return &RecurringService{recurringRepo: recurringRepo, txSvc: txSvc}
}

// Create creates a new recurring rule.
func (s *RecurringService) Create(ctx context.Context, rule models.RecurringRule) (models.RecurringRule, error) {
	if len(rule.TemplateTransaction) == 0 {
		return models.RecurringRule{}, fmt.Errorf("template_transaction is required")
	}
	if rule.Frequency == "" {
		return models.RecurringRule{}, fmt.Errorf("frequency is required")
	}
	if rule.NextDueDate.IsZero() {
		return models.RecurringRule{}, fmt.Errorf("next_due_date is required")
	}
	return s.recurringRepo.Create(ctx, rule)
}

// GetAll returns all recurring rules.
func (s *RecurringService) GetAll(ctx context.Context) ([]models.RecurringRule, error) {
	return s.recurringRepo.GetAll(ctx)
}

// GetDuePending returns rules that are due but need user confirmation (auto_confirm=false).
func (s *RecurringService) GetDuePending(ctx context.Context) ([]models.RecurringRule, error) {
	rules, err := s.recurringRepo.GetDue(ctx)
	if err != nil {
		return nil, err
	}
	var pending []models.RecurringRule
	for _, r := range rules {
		if !r.AutoConfirm {
			pending = append(pending, r)
		}
	}
	return pending, nil
}

// ProcessDueRules checks all due rules and auto-creates transactions for auto_confirm ones.
// Returns the number of transactions created.
func (s *RecurringService) ProcessDueRules(ctx context.Context) (int, error) {
	rules, err := s.recurringRepo.GetDue(ctx)
	if err != nil {
		return 0, err
	}

	created := 0
	for _, rule := range rules {
		if !rule.AutoConfirm {
			continue
		}

		if err := s.executeRule(ctx, rule); err != nil {
			continue // skip failed rules
		}
		created++
	}

	return created, nil
}

// ConfirmRule creates the transaction for a pending rule and advances the due date.
func (s *RecurringService) ConfirmRule(ctx context.Context, ruleID string) error {
	rule, err := s.recurringRepo.GetByID(ctx, ruleID)
	if err != nil {
		return err
	}
	return s.executeRule(ctx, rule)
}

// SkipRule advances the due date without creating a transaction.
func (s *RecurringService) SkipRule(ctx context.Context, ruleID string) error {
	rule, err := s.recurringRepo.GetByID(ctx, ruleID)
	if err != nil {
		return err
	}
	nextDate := s.advanceDueDate(rule)
	return s.recurringRepo.UpdateNextDueDate(ctx, ruleID, nextDate)
}

// Delete removes a recurring rule.
func (s *RecurringService) Delete(ctx context.Context, id string) error {
	return s.recurringRepo.Delete(ctx, id)
}

// executeRule creates a transaction from the rule template and advances the due date.
func (s *RecurringService) executeRule(ctx context.Context, rule models.RecurringRule) error {
	var tmpl models.TransactionTemplate
	if err := json.Unmarshal(rule.TemplateTransaction, &tmpl); err != nil {
		return fmt.Errorf("parsing template: %w", err)
	}

	tx := models.Transaction{
		Type:           tmpl.Type,
		Amount:         tmpl.Amount,
		Currency:       tmpl.Currency,
		AccountID:      tmpl.AccountID,
		CategoryID:     tmpl.CategoryID,
		Note:           tmpl.Note,
		Date:           rule.NextDueDate,
		RecurringRuleID: &rule.ID,
	}

	if _, _, err := s.txSvc.Create(ctx, tx); err != nil {
		return fmt.Errorf("creating transaction: %w", err)
	}

	nextDate := s.advanceDueDate(rule)
	return s.recurringRepo.UpdateNextDueDate(ctx, rule.ID, nextDate)
}

// advanceDueDate calculates the next due date based on frequency.
func (s *RecurringService) advanceDueDate(rule models.RecurringRule) time.Time {
	switch rule.Frequency {
	case models.RecurringFrequencyWeekly:
		return rule.NextDueDate.AddDate(0, 0, 7)
	case models.RecurringFrequencyMonthly:
		return rule.NextDueDate.AddDate(0, 1, 0)
	default:
		return rule.NextDueDate.AddDate(0, 1, 0)
	}
}
