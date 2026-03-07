package handler

import (
	"net/http"

	authmw "github.com/ahmedelsamadisi/clearmoney/internal/middleware"
	"github.com/ahmedelsamadisi/clearmoney/internal/service"
)

// AuthHandler manages login, setup, and logout pages.
type AuthHandler struct {
	templates TemplateMap
	authSvc   *service.AuthService
}

func NewAuthHandler(templates TemplateMap, authSvc *service.AuthService) *AuthHandler {
	return &AuthHandler{templates: templates, authSvc: authSvc}
}

// LoginPage renders the PIN entry form.
// GET /login
func (h *AuthHandler) LoginPage(w http.ResponseWriter, r *http.Request) {
	// If not set up yet, redirect to setup
	if !h.authSvc.IsSetup(r.Context()) {
		http.Redirect(w, r, "/setup", http.StatusFound)
		return
	}
	RenderPage(h.templates, w, "login", PageData{})
}

// LoginSubmit verifies the PIN and creates a session.
// POST /login
func (h *AuthHandler) LoginSubmit(w http.ResponseWriter, r *http.Request) {
	if err := r.ParseForm(); err != nil {
		http.Error(w, "invalid form", http.StatusBadRequest)
		return
	}

	pin := r.FormValue("pin")
	if !h.authSvc.VerifyPIN(r.Context(), pin) {
		RenderPage(h.templates, w, "login", PageData{Data: "Invalid PIN. Please try again."})
		return
	}

	// Create session
	sessionKey, err := h.authSvc.GetSessionKey(r.Context())
	if err != nil {
		http.Error(w, "session error", http.StatusInternalServerError)
		return
	}
	token := authmw.CreateSessionToken(sessionKey)
	authmw.SetSessionCookie(w, token)

	http.Redirect(w, r, "/", http.StatusFound)
}

// SetupPage renders the first-time PIN setup form.
// GET /setup
func (h *AuthHandler) SetupPage(w http.ResponseWriter, r *http.Request) {
	// If already set up, redirect to login
	if h.authSvc.IsSetup(r.Context()) {
		http.Redirect(w, r, "/login", http.StatusFound)
		return
	}
	RenderPage(h.templates, w, "setup", PageData{})
}

// SetupSubmit saves the PIN and creates a session.
// POST /setup
func (h *AuthHandler) SetupSubmit(w http.ResponseWriter, r *http.Request) {
	if err := r.ParseForm(); err != nil {
		http.Error(w, "invalid form", http.StatusBadRequest)
		return
	}

	pin := r.FormValue("pin")
	confirmPin := r.FormValue("confirm_pin")

	if pin != confirmPin {
		RenderPage(h.templates, w, "setup", PageData{Data: "PINs do not match."})
		return
	}

	if err := h.authSvc.Setup(r.Context(), pin); err != nil {
		RenderPage(h.templates, w, "setup", PageData{Data: err.Error()})
		return
	}

	// Auto-login after setup
	sessionKey, err := h.authSvc.GetSessionKey(r.Context())
	if err != nil {
		http.Redirect(w, r, "/login", http.StatusFound)
		return
	}
	token := authmw.CreateSessionToken(sessionKey)
	authmw.SetSessionCookie(w, token)

	http.Redirect(w, r, "/", http.StatusFound)
}

// Logout clears the session and redirects to login.
// POST /logout
func (h *AuthHandler) Logout(w http.ResponseWriter, r *http.Request) {
	authmw.ClearSessionCookie(w)
	http.Redirect(w, r, "/login", http.StatusFound)
}
