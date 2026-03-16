// Package models — user.go defines the User model for multi-user authentication.
//
// A User represents a registered account in ClearMoney. Authentication is
// passwordless (magic link via email) — there is no password hash field.
//
// Laravel analogy: Like a User Eloquent model but without the password column.
// Similar to Laravel Passwordless or Socialite where auth is delegated externally.
//
// Django analogy: Like AbstractBaseUser but with no password field — closer to
// a custom user model that relies on email-based token auth.
package models

import "time"

// User represents a registered ClearMoney user.
// Auth is magic-link only — no password stored.
type User struct {
	ID        string    `json:"id" db:"id"`
	Email     string    `json:"email" db:"email"`
	CreatedAt time.Time `json:"created_at" db:"created_at"`
	UpdatedAt time.Time `json:"updated_at" db:"updated_at"`
}
