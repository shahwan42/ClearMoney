// Package service — NotificationService generates push notification payloads.
// This handles the server-side logic for when to send notifications.
// Actual push delivery requires VAPID keys and a web-push library.
package service

import (
	"context"
	"fmt"
	"time"
)

// Notification represents a push notification payload.
type Notification struct {
	Title string `json:"title"`
	Body  string `json:"body"`
	URL   string `json:"url"`
	Tag   string `json:"tag"` // dedup key
}

// NotificationService checks for conditions that should trigger notifications.
type NotificationService struct {
	dashboardSvc *DashboardService
	recurringSvc *RecurringService
}

func NewNotificationService(dashboardSvc *DashboardService, recurringSvc *RecurringService) *NotificationService {
	return &NotificationService{dashboardSvc: dashboardSvc, recurringSvc: recurringSvc}
}

// GetPendingNotifications checks all trigger conditions and returns notifications to send.
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
						Body:  fmt.Sprintf("%s: spent EGP %.0f of EGP %.0f limit (%.0f%%)", b.CategoryName, b.Spent, b.MonthlyLimit, b.Percentage),
						URL:   "/budgets",
						Tag:   fmt.Sprintf("budget-exceeded-%s", b.CategoryID),
					})
				} else if b.Percentage >= 80 {
					notifications = append(notifications, Notification{
						Title: "Budget Warning",
						Body:  fmt.Sprintf("%s: %.0f%% of budget used (EGP %.0f remaining)", b.CategoryName, b.Percentage, b.Remaining),
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
type PushSubscription struct {
	Endpoint string `json:"endpoint"`
	Keys     struct {
		P256dh string `json:"p256dh"`
		Auth   string `json:"auth"`
	} `json:"keys"`
	CreatedAt time.Time `json:"created_at"`
}
