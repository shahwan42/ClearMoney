// Package handler — Push notification subscription management.
// Handles browser push subscription registration and notification checking.
package handler

import (
	"encoding/json"
	"net/http"

	authmw "github.com/ahmedelsamadisi/clearmoney/internal/middleware"
	"github.com/ahmedelsamadisi/clearmoney/internal/service"
)

// PushHandler manages push notification subscriptions and checking.
type PushHandler struct {
	notificationSvc *service.NotificationService
	vapidPublicKey  string
}

func NewPushHandler(notificationSvc *service.NotificationService, vapidPublicKey string) *PushHandler {
	return &PushHandler{notificationSvc: notificationSvc, vapidPublicKey: vapidPublicKey}
}

// VAPIDKey returns the VAPID public key for the browser to use when subscribing.
// GET /api/push/vapid-key
func (h *PushHandler) VAPIDKey(w http.ResponseWriter, r *http.Request) {
	w.Header().Set("Content-Type", "application/json")
	json.NewEncoder(w).Encode(map[string]string{
		"publicKey": h.vapidPublicKey,
	})
}

// Subscribe stores a push subscription from the browser.
// POST /api/push/subscribe
func (h *PushHandler) Subscribe(w http.ResponseWriter, r *http.Request) {
	var sub service.PushSubscription
	if err := json.NewDecoder(r.Body).Decode(&sub); err != nil {
		http.Error(w, "invalid subscription", http.StatusBadRequest)
		return
	}

	// In a full implementation, store the subscription in the database.
	// For now, we acknowledge receipt — the single-user app can check
	// notifications on page load instead.
	w.Header().Set("Content-Type", "application/json")
	json.NewEncoder(w).Encode(map[string]string{"status": "ok"})
}

// CheckNotifications returns pending notifications as JSON.
// GET /api/push/check
func (h *PushHandler) CheckNotifications(w http.ResponseWriter, r *http.Request) {
	notifications, err := h.notificationSvc.GetPendingNotifications(r.Context())
	if err != nil {
		authmw.Log(r.Context()).Error("failed to check notifications", "error", err)
		http.Error(w, err.Error(), http.StatusInternalServerError)
		return
	}

	w.Header().Set("Content-Type", "application/json")
	json.NewEncoder(w).Encode(notifications)
}
