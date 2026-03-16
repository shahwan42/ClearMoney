// push.go — Push notification subscription management.
//
// This handler supports the Web Push API for browser push notifications.
// The flow is:
//   1. Browser calls GET /api/push/vapid-key to get the server's VAPID public key
//   2. Browser subscribes to push via the Push API and gets a subscription object
//   3. Browser sends the subscription to POST /api/push/subscribe
//   4. Browser periodically calls GET /api/push/check to poll for pending notifications
//
// VAPID (Voluntary Application Server Identification) is a standard for identifying
// the push notification sender. The public key is shared with the browser; the private
// key is kept server-side for signing push messages.
//
// In a full implementation, subscriptions would be stored in the database and the
// server would use the Web Push protocol to send notifications. Currently, this app
// uses a polling approach (check endpoint) since it's a single-user PWA.
//
// See: https://developer.mozilla.org/en-US/docs/Web/API/Push_API
// See: https://web.dev/push-notifications-overview/
package handler

import (
	"encoding/json"
	"net/http"

	authmw "github.com/shahwan42/clearmoney/internal/middleware"
	"github.com/shahwan42/clearmoney/internal/service"
)

// PushHandler manages push notification subscriptions and checking.
// The VAPID public key is loaded from the VAPID_PUBLIC_KEY environment variable.
type PushHandler struct {
	notificationSvc *service.NotificationService
	vapidPublicKey  string
}

func NewPushHandler(notificationSvc *service.NotificationService, vapidPublicKey string) *PushHandler {
	return &PushHandler{notificationSvc: notificationSvc, vapidPublicKey: vapidPublicKey}
}

// VAPIDKey returns the VAPID public key for the browser to use when subscribing.
// GET /api/push/vapid-key
//
// The browser's Push API needs this key to create a push subscription.
// This is a simple JSON response (no database access needed).
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
//
// This is a polling endpoint — the browser's service worker calls it periodically
// to check for new notifications (budget alerts, recurring transaction reminders,
// account health warnings). This is simpler than server-push for a single-user app.
func (h *PushHandler) CheckNotifications(w http.ResponseWriter, r *http.Request) {
	userID := authmw.UserID(r.Context())
	notifications, err := h.notificationSvc.GetPendingNotifications(r.Context(), userID)
	if err != nil {
		authmw.Log(r.Context()).Error("failed to check notifications", "error", err)
		http.Error(w, err.Error(), http.StatusInternalServerError)
		return
	}

	w.Header().Set("Content-Type", "application/json")
	json.NewEncoder(w).Encode(notifications)
}
