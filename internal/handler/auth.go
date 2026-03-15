// auth.go — Authentication handlers for PIN-based login, first-time setup, and logout.
//
// ClearMoney uses a simple PIN-based authentication system (no usernames or passwords).
// This is a single-user app, so there's one PIN stored as a bcrypt hash in user_config.
//
// Authentication flow:
//   1. First visit: No PIN set -> redirect to /setup
//   2. /setup: User enters PIN + confirmation -> bcrypt hash stored in DB
//   3. /login: User enters PIN -> verified against bcrypt hash
//   4. On success: HMAC session token created and set as a cookie
//   5. Auth middleware checks the cookie on every protected request
//   6. /logout: Cookie cleared (MaxAge -1)
//
// Session tokens use HMAC (Hash-based Message Authentication Code):
//   - The server holds a secret key in user_config
//   - The token is an HMAC signature that the middleware can verify
//   - No server-side session storage needed (stateless)
//
// This is simpler than:
//   - Laravel: Auth::attempt(['email' => $e, 'password' => $p]) with session store
//   - Django: authenticate(request, username=u, password=p) with django.contrib.sessions
//
// Form handling in Go:
//   r.ParseForm() — parses the request body as application/x-www-form-urlencoded
//   r.FormValue("pin") — gets a form field value
//   These are like:
//     - Laravel: $request->input('pin') or $request->validate(['pin' => 'required'])
//     - Django: request.POST.get('pin') or form.cleaned_data['pin']
//
// See: https://pkg.go.dev/net/http#Request.ParseForm
// See: https://pkg.go.dev/net/http#Request.FormValue
package handler

import (
	"log/slog"
	"math"
	"net/http"
	"time"

	authmw "github.com/shahwan42/clearmoney/internal/middleware"
	"github.com/shahwan42/clearmoney/internal/service"
)

// LoginPageData carries error and lockout state to the login template.
// When the user is locked out, SecondsLeft tells the template how long to show
// the countdown timer. FailedAttempts lets us warn "1 attempt remaining."
type LoginPageData struct {
	Error          string
	Locked         bool
	SecondsLeft    int
	FailedAttempts int
}

// AuthHandler manages login, setup, and logout pages.
// Unlike other handlers that return JSON, this one renders HTML templates
// and uses form POST submissions (not JSON). It follows the traditional
// web app pattern of form submit -> server-side processing -> redirect.
type AuthHandler struct {
	templates TemplateMap
	authSvc   *service.AuthService
}

func NewAuthHandler(templates TemplateMap, authSvc *service.AuthService) *AuthHandler {
	return &AuthHandler{templates: templates, authSvc: authSvc}
}

// LoginPage renders the PIN entry form.
// GET /login
//
// Redirects to /setup if no PIN has been configured yet.
// http.Redirect sends a 302 Found response with a Location header.
// This is like Laravel's return redirect('/setup') or Django's HttpResponseRedirect('/setup').
func (h *AuthHandler) LoginPage(w http.ResponseWriter, r *http.Request) {
	authmw.Log(r.Context()).Info("page viewed", "page", "login")
	// If not set up yet, redirect to setup
	if !h.authSvc.IsSetup(r.Context()) {
		http.Redirect(w, r, "/setup", http.StatusFound)
		return
	}

	// Check if currently locked out so we show the countdown on page load
	data := LoginPageData{}
	locked, lockedUntil, err := h.authSvc.GetLockoutStatus(r.Context())
	if err == nil && locked {
		data.Locked = true
		data.SecondsLeft = int(math.Ceil(time.Until(lockedUntil).Seconds()))
	}
	RenderPage(h.templates, w, "login", PageData{Data: data})
}

// LoginSubmit verifies the PIN and creates a session.
// POST /login
//
// Flow: parse form -> verify PIN -> create session token -> set cookie -> redirect to /
// On failure: re-render the login page with an error message (no redirect).
//
// This is the PRG (Post-Redirect-Get) pattern:
//   - Success: POST /login -> 302 redirect to / -> GET /
//   - Failure: POST /login -> 200 with error message (re-render form)
func (h *AuthHandler) LoginSubmit(w http.ResponseWriter, r *http.Request) {
	if err := r.ParseForm(); err != nil {
		http.Error(w, "invalid form", http.StatusBadRequest)
		return
	}

	pin := r.FormValue("pin")
	result := h.authSvc.CheckAndVerifyPIN(r.Context(), pin)

	if result.Locked {
		slog.Warn("login: account locked", "until", result.LockedUntil)
		data := LoginPageData{
			Locked:         true,
			SecondsLeft:    int(math.Ceil(time.Until(result.LockedUntil).Seconds())),
			FailedAttempts: result.FailedAttempts,
		}
		RenderPage(h.templates, w, "login", PageData{Data: data})
		return
	}

	if !result.Success {
		slog.Warn("login: invalid PIN attempt", "failed_attempts", result.FailedAttempts)
		data := LoginPageData{
			Error:          "Invalid PIN. Please try again.",
			FailedAttempts: result.FailedAttempts,
		}
		RenderPage(h.templates, w, "login", PageData{Data: data})
		return
	}

	slog.Info("auth event", "event", "auth.login_success")

	// Create session
	sessionKey, err := h.authSvc.GetSessionKey(r.Context())
	if err != nil {
		slog.Error("login: session key error", "error", err)
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
	authmw.Log(r.Context()).Info("page viewed", "page", "setup")
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

	slog.Info("auth event", "event", "auth.setup_success")

	// Auto-login after setup
	sessionKey, err := h.authSvc.GetSessionKey(r.Context())
	if err != nil {
		slog.Error("setup: session key error after PIN setup", "error", err)
		http.Redirect(w, r, "/login", http.StatusFound)
		return
	}
	token := authmw.CreateSessionToken(sessionKey)
	authmw.SetSessionCookie(w, token)

	http.Redirect(w, r, "/", http.StatusFound)
}

// Logout clears the session and redirects to login.
// POST /logout
//
// ClearSessionCookie sets the cookie MaxAge to -1, which tells the browser
// to delete it immediately. This is the standard way to "log out" with cookies.
func (h *AuthHandler) Logout(w http.ResponseWriter, r *http.Request) {
	slog.Info("auth event", "event", "auth.logout")
	authmw.ClearSessionCookie(w)
	http.Redirect(w, r, "/login", http.StatusFound)
}
