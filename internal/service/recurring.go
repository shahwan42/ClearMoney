// Package service — RecurringService handles recurring transaction rules.
//
// Recurring rules define transactions that repeat on a schedule (weekly/monthly).
// When a rule's next_due_date is today or earlier:
//   - auto_confirm=true: create the transaction automatically (like a cron job)
//   - auto_confirm=false: return it as "pending" for user confirmation
//
// After processing, advance next_due_date based on frequency.
//
// Laravel analogy: Like a Scheduled Task (app/Console/Kernel.php) that checks
// recurring rules and creates transactions. ProcessDueRules() would be called
// from an Artisan command: php artisan recurring:process. In ClearMoney, it runs
// on every app startup instead.
//
// Django analogy: Like a management command (manage.py process_recurring) or a
// Celery periodic task that checks due rules and creates transactions.
//
// Key Go concept: json.RawMessage is used for TemplateTransaction — it stores raw JSON
// bytes without parsing them into a specific struct. This is like storing a JSON column
// in Laravel with $casts['template'] = 'json' or Django's JSONField. We unmarshal it
// only when executing the rule.
// See: https://pkg.go.dev/encoding/json#RawMessage
package service

import (
	"context"
	"encoding/json"
	"fmt"
	"time"

	"github.com/shahwan42/clearmoney/internal/logutil"
	"github.com/shahwan42/clearmoney/internal/models"
	"github.com/shahwan42/clearmoney/internal/repository"
	"github.com/shahwan42/clearmoney/internal/timeutil"
)

// RecurringService manages recurring transaction rules.
// Note: this service depends on TransactionService (another service), not just repositories.
// This is service-to-service dependency — the recurring service delegates transaction creation
// to TransactionService to reuse its validation and atomic balance update logic.
// In Laravel, you'd inject TransactionService into RecurringService's constructor.
type RecurringService struct {
	recurringRepo *repository.RecurringRepo
	txSvc         *TransactionService
	loc           *time.Location // User timezone for "today" calculation
}

// SetTimezone sets the user's timezone for calendar-date operations.
func (s *RecurringService) SetTimezone(loc *time.Location) {
	s.loc = loc
}

// timezone returns the configured timezone or UTC as fallback.
func (s *RecurringService) timezone() *time.Location {
	if s.loc != nil {
		return s.loc
	}
	return time.UTC
}

func NewRecurringService(recurringRepo *repository.RecurringRepo, txSvc *TransactionService) *RecurringService {
	return &RecurringService{recurringRepo: recurringRepo, txSvc: txSvc}
}

// Create creates a new recurring rule.
func (s *RecurringService) Create(ctx context.Context, userID string, rule models.RecurringRule) (models.RecurringRule, error) {
	if len(rule.TemplateTransaction) == 0 {
		return models.RecurringRule{}, fmt.Errorf("template_transaction is required")
	}
	if err := requireNotEmpty(string(rule.Frequency), "frequency"); err != nil {
		return models.RecurringRule{}, err
	}
	if rule.NextDueDate.IsZero() {
		return models.RecurringRule{}, fmt.Errorf("next_due_date is required")
	}
	rule.UserID = userID
	created, err := s.recurringRepo.Create(ctx, userID, rule)
	if err != nil {
		return models.RecurringRule{}, err
	}
	logutil.LogEvent(ctx, "recurring.created", "frequency", string(created.Frequency))
	return created, nil
}

// GetAll returns all recurring rules.
func (s *RecurringService) GetAll(ctx context.Context, userID string) ([]models.RecurringRule, error) {
	return s.recurringRepo.GetAll(ctx, userID)
}

// GetDuePending returns rules that are due but need user confirmation (auto_confirm=false).
func (s *RecurringService) GetDuePending(ctx context.Context, userID string) ([]models.RecurringRule, error) {
	rules, err := s.recurringRepo.GetDue(ctx, userID, timeutil.Today(s.timezone()))
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
func (s *RecurringService) ProcessDueRules(ctx context.Context, userID string) (int, error) {
	rules, err := s.recurringRepo.GetDue(ctx, userID, timeutil.Today(s.timezone()))
	if err != nil {
		return 0, err
	}

	created := 0
	for _, rule := range rules {
		if !rule.AutoConfirm {
			continue
		}

		if err := s.executeRule(ctx, userID, rule); err != nil {
			continue // skip failed rules
		}
		created++
		logutil.LogEvent(ctx, "recurring.auto_processed", "id", rule.ID)
	}

	return created, nil
}

// ConfirmRule creates the transaction for a pending rule and advances the due date.
func (s *RecurringService) ConfirmRule(ctx context.Context, userID string, ruleID string) error {
	rule, err := s.recurringRepo.GetByID(ctx, userID, ruleID)
	if err != nil {
		return err
	}
	if err := s.executeRule(ctx, userID, rule); err != nil {
		return err
	}
	logutil.LogEvent(ctx, "recurring.confirmed", "id", ruleID)
	return nil
}

// SkipRule advances the due date without creating a transaction.
func (s *RecurringService) SkipRule(ctx context.Context, userID string, ruleID string) error {
	rule, err := s.recurringRepo.GetByID(ctx, userID, ruleID)
	if err != nil {
		return err
	}
	nextDate := s.advanceDueDate(rule)
	if err := s.recurringRepo.UpdateNextDueDate(ctx, userID, ruleID, nextDate); err != nil {
		return err
	}
	logutil.LogEvent(ctx, "recurring.skipped", "id", ruleID)
	return nil
}

// Delete removes a recurring rule.
func (s *RecurringService) Delete(ctx context.Context, userID string, id string) error {
	if err := s.recurringRepo.Delete(ctx, userID, id); err != nil {
		return err
	}
	logutil.LogEvent(ctx, "recurring.deleted", "id", id)
	return nil
}

// executeRule creates a transaction from the rule template and advances the due date.
// This private method (lowercase) is the core logic shared by ConfirmRule and ProcessDueRules.
//
// json.Unmarshal: converts the stored JSON template bytes into a TransactionTemplate struct.
// This is like json_decode() in PHP or json.loads() in Python, but type-safe — it
// maps JSON keys to struct fields using the `json:"..."` tags.
func (s *RecurringService) executeRule(ctx context.Context, userID string, rule models.RecurringRule) error {
	var tmpl models.TransactionTemplate
	if err := json.Unmarshal(rule.TemplateTransaction, &tmpl); err != nil {
		return fmt.Errorf("parsing template: %w", err)
	}

	// Guard: account may have been deleted after the rule was created. JSONB has no FK
	// constraint, so we catch the stale reference here before hitting the DB.
	if tmpl.AccountID == "" {
		return fmt.Errorf("recurring rule %s has no account_id — account may have been deleted", rule.ID)
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
		UserID:         userID,
	}

	if _, _, err := s.txSvc.Create(ctx, userID, tx); err != nil {
		return fmt.Errorf("creating transaction: %w", err)
	}

	nextDate := s.advanceDueDate(rule)
	return s.recurringRepo.UpdateNextDueDate(ctx, userID, rule.ID, nextDate)
}

// advanceDueDate calculates the next due date based on frequency.
// time.AddDate(0, 1, 0) adds one month. Go handles month overflow correctly:
// Jan 31 + 1 month = March 3 (February has fewer days, Go rolls forward).
// This is different from Carbon in Laravel which clamps to the last day of month.
// See: https://pkg.go.dev/time#Time.AddDate
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
