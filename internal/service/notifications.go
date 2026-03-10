// Package service — NotificationService generates push notification payloads.
//
// This service checks various conditions and generates notification payloads.
// It does NOT send notifications directly — the handler polls this service and
// returns the payloads to the client-side service worker for display.
//
// Notification triggers:
//   - Credit card due within 3 days (from DashboardService)
//   - Account health violations (min balance, min deposit)
//   - Budget exceeded (100%) or approaching limit (80%)
//   - Recurring transactions needing confirmation
//
// Laravel analogy: Like Laravel's Notification system (via() returns channels,
// toMail()/toDatabase() formats the message). But simpler — we only generate
// payloads; the browser's Push API handles delivery. Similar to broadcasting
// events with Laravel Echo, but polling-based instead of WebSocket.
//
// Django analogy: Like django-push-notifications or a custom notification service
// that checks conditions and returns notification dicts. The frontend polls
// an endpoint to check for new notifications.
//
// Architecture: Uses the OBSERVER pattern conceptually — NotificationService
// "observes" conditions across multiple services (dashboard, recurring) and
// generates alerts. The services are injected via constructor, nil-safe checked.
package service

import (
	"context"
	"fmt"
	"time"
)

// Notification represents a push notification payload.
// JSON tags control serialization when this struct is returned as JSON to the frontend.
// The Tag field is a deduplication key — the browser won't show duplicate notifications
// with the same tag. Like Laravel Notification's databaseType() unique identifier.
type Notification struct {
	Title string `json:"title"`
	Body  string `json:"body"`
	URL   string `json:"url"`
	Tag   string `json:"tag"` // dedup key — prevents duplicate notifications
}

// NotificationService checks for conditions that should trigger notifications.
// It depends on two other services (service-to-service composition).
// Both are nil-safe — the service works with either or both being nil.
type NotificationService struct {
	dashboardSvc *DashboardService
	recurringSvc *RecurringService
}

func NewNotificationService(dashboardSvc *DashboardService, recurringSvc *RecurringService) *NotificationService {
	return &NotificationService{dashboardSvc: dashboardSvc, recurringSvc: recurringSvc}
}

// GetPendingNotifications checks all trigger conditions and returns notifications to send.
//
// This method aggregates notification triggers from multiple sources:
//   1. Credit cards due within 3 days (via DashboardService.DueSoonCards)
//   2. Account health warnings (via DashboardService.HealthWarnings)
//   3. Budget alerts at 80%/100% (via DashboardService.Budgets)
//   4. Pending recurring transactions (via RecurringService.GetDuePending)
//
// nil-safe pattern: each source is wrapped in `if s.xxxSvc != nil { ... }`.
// This ensures the method works even if some services weren't injected.
func (s *NotificationService) GetPendingNotifications(ctx context.Context) ([]Notification, error) {
	var notifications []Notification

	// Check credit card due dates (within 3 days) and budget thresholds
	if s.dashboardSvc != nil {
		data, err := s.dashboardSvc.GetDashboard(ctx)
		if err == nil {
			for _, card := range data.DueSoonCards {
				if card.DaysUntilDue <= 3 {
					notifications = append(notifications, Notification{
						Title: "Credit Card Due Soon",
						Body:  fmt.Sprintf("%s is due in %d day(s) — balance: EGP %.2f", card.AccountName, card.DaysUntilDue, -card.Balance),
						URL:   "/accounts",
						Tag:   fmt.Sprintf("cc-due-%s-%s", card.AccountName, card.DueDate.Format("2006-01-02")),
					})
				}
			}

			// TASK-069: Account health warnings
			for _, w := range data.HealthWarnings {
				notifications = append(notifications, Notification{
					Title: "Account Health Warning",
					Body:  w.Message,
					URL:   "/accounts/" + w.AccountID,
					Tag:   fmt.Sprintf("health-%s-%s", w.Rule, w.AccountID),
				})
			}

			// TASK-067: Budget threshold alerts at 80% and 100%
			for _, b := range data.Budgets {
				if b.Percentage >= 100 {
					notifications = append(notifications, Notification{
						Title: "Budget Exceeded",
						Body:  fmt.Sprintf("%s: spent EGP %.0f of EGP %.0f limit (%.0f%%)", b.CategoryDisplayName(), b.Spent, b.MonthlyLimit, b.Percentage),
						URL:   "/budgets",
						Tag:   fmt.Sprintf("budget-exceeded-%s", b.CategoryID),
					})
				} else if b.Percentage >= 80 {
					notifications = append(notifications, Notification{
						Title: "Budget Warning",
						Body:  fmt.Sprintf("%s: %.0f%% of budget used (EGP %.0f remaining)", b.CategoryDisplayName(), b.Percentage, b.Remaining),
						URL:   "/budgets",
						Tag:   fmt.Sprintf("budget-warning-%s", b.CategoryID),
					})
				}
			}
		}
	}

	// Check recurring transactions due
	if s.recurringSvc != nil {
		pending, err := s.recurringSvc.GetDuePending(ctx)
		if err == nil {
			for _, rule := range pending {
				notifications = append(notifications, Notification{
					Title: "Recurring Transaction Due",
					Body:  fmt.Sprintf("A recurring %s transaction needs confirmation (due %s)", rule.Frequency, rule.NextDueDate.Format("Jan 2")),
					URL:   "/recurring",
					Tag:   fmt.Sprintf("recurring-%s-%s", rule.ID, rule.NextDueDate.Format("2006-01-02")),
				})
			}
		}
	}

	return notifications, nil
}

// PushSubscription stores a client's push subscription from the browser's Push API.
// This struct mirrors the JavaScript PushSubscription object that the service worker
// provides when the user grants notification permission.
// See: https://developer.mozilla.org/en-US/docs/Web/API/PushSubscription
type PushSubscription struct {
	Endpoint string `json:"endpoint"`
	Keys     struct {
		P256dh string `json:"p256dh"`
		Auth   string `json:"auth"`
	} `json:"keys"`
	CreatedAt time.Time `json:"created_at"`
}
