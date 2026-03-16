// Package models — auth_token.go defines the AuthToken model for magic link verification.
//
// Auth tokens are short-lived, single-use tokens sent via email. When a user clicks
// the magic link, the token is looked up, validated (not expired, not used), and then
// marked as used. The user is then logged in via a new Session.
//
// Laravel analogy: Like the password_resets table but for magic links — stores a
// token + email + expiry. Single-use and short-lived (15 minutes).
//
// Django analogy: Like django-sesame or django-magiclink tokens — stored in DB
// rather than signed into the URL.
package models

import "time"

// AuthToken represents a magic link token (short-lived, single-use).
type AuthToken struct {
	ID        string    `json:"id" db:"id"`
	Email     string    `json:"email" db:"email"`
	Token     string    `json:"token" db:"token"`
	Purpose   string    `json:"purpose" db:"purpose"` // "login" or "registration"
	ExpiresAt time.Time `json:"expires_at" db:"expires_at"`
	Used      bool      `json:"used" db:"used"`
	CreatedAt time.Time `json:"created_at" db:"created_at"`
}
