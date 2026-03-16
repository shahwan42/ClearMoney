// Package models — session.go defines the Session model for server-side session storage.
//
// Sessions are stored in the database (not signed cookies). Each session maps a
// random token to a user_id with an expiry time. The auth middleware looks up the
// session by token on every request.
//
// Laravel analogy: Like the sessions table when using the "database" session driver
// (SESSION_DRIVER=database in .env). The token is the session ID.
//
// Django analogy: Like django_session table — stores session data server-side,
// referenced by a session key in the cookie.
package models

import "time"

// Session represents an active login session (server-side, DB-stored).
type Session struct {
	ID        string    `json:"id" db:"id"`
	UserID    string    `json:"user_id" db:"user_id"`
	Token     string    `json:"token" db:"token"`
	ExpiresAt time.Time `json:"expires_at" db:"expires_at"`
	CreatedAt time.Time `json:"created_at" db:"created_at"`
}
