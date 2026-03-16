// auth.go — Authentication handlers for magic link login, registration, and logout.
//
// ClearMoney uses passwordless magic link authentication via email (Resend API).
// Users enter their email, receive a link, click it, and get logged in.
//
// Authentication flow:
//   1. /login: User enters email → server sends magic link (if user exists)
//   2. /register: New user enters email → server sends registration link
//   3. /auth/verify?token=xxx: User clicks link → session created → redirect to /
//   4. /logout: Session deleted, cookie cleared
//
// Anti-abuse measures:
//   - Honeypot field: hidden input that bots fill → silent reject
//   - Timing check: submit < 2s after page load → silent reject
//   - Rate limiting: per-email, per-IP, global daily (handled by service + middleware)
//   - Login only sends emails to existing users (prevent email enumeration)
//
// Form handling in Go:
//   r.ParseForm() — parses the request body
//   r.FormValue("email") — gets a form field value
//   These are like Laravel's $request->input() or Django's request.POST.get()
package handler

import (
	"log/slog"
	"net/http"
	"strconv"
	"time"

	authmw "github.com/shahwan42/clearmoney/internal/middleware"
	"github.com/shahwan42/clearmoney/internal/service"
)

// AuthHandler manages login, registration, magic link verification, and logout.
type AuthHandler struct {
	templates TemplateMap
	authSvc   *service.AuthService
}

func NewAuthHandler(templates TemplateMap, authSvc *service.AuthService) *AuthHandler {
	return &AuthHandler{templates: templates, authSvc: authSvc}
}

// LoginPage renders the email-based login form.
// GET /login
func (h *AuthHandler) LoginPage(w http.ResponseWriter, r *http.Request) {
	authmw.Log(r.Context()).Info("page viewed", "page", "login")
	data := map[string]any{
		"RenderTime": time.Now().Unix(),
	}
	RenderPage(h.templates, w, "login", PageData{Data: data})
}

// LoginSubmit processes the login form and sends a magic link.
// POST /login
//
// Always shows "Check your email" regardless of whether the email is registered.
// This prevents email enumeration attacks.
func (h *AuthHandler) LoginSubmit(w http.ResponseWriter, r *http.Request) {
	if err := r.ParseForm(); err != nil {
		http.Error(w, "invalid form", http.StatusBadRequest)
		return
	}

	// Honeypot check: hidden field that bots fill
	if r.FormValue("website") != "" {
		slog.Info("login: honeypot triggered (bot detected)")
		RenderPage(h.templates, w, "check-email", PageData{})
		return
	}

	// Timing check: reject if submitted too fast (< 2 seconds)
	if renderTime := r.FormValue("_rt"); renderTime != "" {
		if rt, err := strconv.ParseInt(renderTime, 10, 64); err == nil {
			if time.Now().Unix()-rt < 2 {
				slog.Info("login: timing check failed (too fast)")
				RenderPage(h.templates, w, "check-email", PageData{})
				return
			}
		}
	}

	email := r.FormValue("email")
	if email == "" {
		data := map[string]any{
			"Error":      "Email is required",
			"RenderTime": time.Now().Unix(),
		}
		RenderPage(h.templates, w, "login", PageData{Data: data})
		return
	}

	result, err := h.authSvc.RequestLoginLink(r.Context(), email)
	if err != nil {
		slog.Error("login: failed to request magic link", "error", err)
	}

	// Always show "check your email" — even if user doesn't exist (prevent enumeration).
	// The Hint flag shows for ALL non-sent outcomes (unknown email, cooldown, daily limit)
	// so it reveals nothing about whether the account exists.
	data := map[string]any{"Email": email}
	if result != service.SendResultSent {
		data["Hint"] = true
	}
	RenderPage(h.templates, w, "check-email", PageData{Data: data})
}

// RegisterPage renders the registration form.
// GET /register
func (h *AuthHandler) RegisterPage(w http.ResponseWriter, r *http.Request) {
	authmw.Log(r.Context()).Info("page viewed", "page", "register")
	data := map[string]any{
		"RenderTime": time.Now().Unix(),
	}
	RenderPage(h.templates, w, "register", PageData{Data: data})
}

// RegisterSubmit processes the registration form and sends a magic link.
// POST /register
func (h *AuthHandler) RegisterSubmit(w http.ResponseWriter, r *http.Request) {
	if err := r.ParseForm(); err != nil {
		http.Error(w, "invalid form", http.StatusBadRequest)
		return
	}

	// Honeypot check
	if r.FormValue("website") != "" {
		slog.Info("register: honeypot triggered (bot detected)")
		RenderPage(h.templates, w, "check-email", PageData{})
		return
	}

	// Timing check
	if renderTime := r.FormValue("_rt"); renderTime != "" {
		if rt, err := strconv.ParseInt(renderTime, 10, 64); err == nil {
			if time.Now().Unix()-rt < 2 {
				slog.Info("register: timing check failed (too fast)")
				RenderPage(h.templates, w, "check-email", PageData{})
				return
			}
		}
	}

	email := r.FormValue("email")
	if email == "" {
		data := map[string]any{
			"Error":      "Email is required",
			"RenderTime": time.Now().Unix(),
		}
		RenderPage(h.templates, w, "register", PageData{Data: data})
		return
	}

	result, err := h.authSvc.RequestRegistrationLink(r.Context(), email)
	if err != nil {
		// Show error for registration (safe to reveal "already registered" since user initiated it)
		data := map[string]any{
			"Error":      err.Error(),
			"RenderTime": time.Now().Unix(),
		}
		RenderPage(h.templates, w, "register", PageData{Data: data})
		return
	}

	// Registration already reveals email existence, so specific rate-limit messages are safe
	if result != service.SendResultSent {
		msg := rateLimitMessage(result)
		data := map[string]any{
			"Error":      msg,
			"RenderTime": time.Now().Unix(),
		}
		RenderPage(h.templates, w, "register", PageData{Data: data})
		return
	}

	RenderPage(h.templates, w, "check-email", PageData{Data: map[string]any{"Email": email}})
}

// VerifyMagicLink validates the token from a magic link and creates a session.
// GET /auth/verify?token=xxx
func (h *AuthHandler) VerifyMagicLink(w http.ResponseWriter, r *http.Request) {
	token := r.URL.Query().Get("token")
	if token == "" {
		RenderPage(h.templates, w, "link-expired", PageData{})
		return
	}

	result, err := h.authSvc.VerifyMagicLink(r.Context(), token)
	if err != nil {
		slog.Warn("auth: magic link verification failed", "error", err)
		RenderPage(h.templates, w, "link-expired", PageData{Data: map[string]any{"Error": err.Error()}})
		return
	}

	// Set session cookie and redirect
	authmw.SetSessionCookie(w, result.SessionToken)
	http.Redirect(w, r, "/", http.StatusFound)
}

// rateLimitMessage returns a user-facing message for a non-sent magic link result.
func rateLimitMessage(result service.SendResult) string {
	switch result {
	case service.SendResultReused:
		return "A sign-in link was already sent. Please check your inbox."
	case service.SendResultCooldown:
		return "Please wait a few minutes before requesting another link."
	case service.SendResultDailyLimit:
		return "You've reached the daily limit for sign-in links. Please try again tomorrow."
	case service.SendResultGlobalCap:
		return "Our email system is temporarily at capacity. Please try again later."
	default:
		return "Please try again later."
	}
}

// Logout clears the session and redirects to login.
// POST /logout
func (h *AuthHandler) Logout(w http.ResponseWriter, r *http.Request) {
	// Delete server-side session
	cookie, err := r.Cookie(service.SessionCookieName)
	if err == nil && cookie.Value != "" {
		h.authSvc.Logout(r.Context(), cookie.Value)
	}

	authmw.ClearSessionCookie(w)
	http.Redirect(w, r, "/login", http.StatusFound)
}
