-- =============================================================================
-- Migration 000027: Multi-User Tables
-- =============================================================================
--
-- Creates the core tables for multi-user support:
--   1. users        — one row per registered user (magic link auth, no passwords)
--   2. sessions     — server-side session tokens (replaces HMAC-signed cookies)
--   3. auth_tokens  — short-lived magic link tokens (15-min TTL, single-use)
--
-- The existing single user (Ahmed) is migrated from user_config into the users
-- table. All existing data will be assigned to this user in migration 000028.
-- =============================================================================

-- Users table (magic link auth — no password column).
-- Email is the sole identifier. One row per user.
CREATE TABLE users (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    email TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Case-insensitive unique index on email.
-- Prevents duplicates like User@x.com vs user@x.com.
-- PostgreSQL functional indexes apply the function before comparing.
CREATE UNIQUE INDEX idx_users_email_lower ON users(LOWER(email));

-- Server-side sessions.
-- Each login creates a session row. The cookie stores only the random token.
-- This replaces the old HMAC-signed cookie approach which had no user identity.
--
-- ON DELETE CASCADE: when a user is deleted, all their sessions are removed.
CREATE TABLE sessions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    token TEXT NOT NULL UNIQUE,
    expires_at TIMESTAMPTZ NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_sessions_token ON sessions(token);
CREATE INDEX idx_sessions_expires ON sessions(expires_at);

-- Magic link tokens.
-- Generated when a user requests a sign-in link. Short-lived (15 min) and single-use.
-- The purpose column distinguishes login vs registration tokens.
CREATE TABLE auth_tokens (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    email TEXT NOT NULL,
    token TEXT NOT NULL UNIQUE,
    purpose TEXT NOT NULL DEFAULT 'login',
    expires_at TIMESTAMPTZ NOT NULL,
    used BOOLEAN NOT NULL DEFAULT FALSE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_auth_tokens_token ON auth_tokens(token);
CREATE INDEX idx_auth_tokens_email ON auth_tokens(email);

-- Migrate the existing single user (Ahmed) into the users table.
-- The email is hardcoded because this is a known single-user production app.
-- All existing data will be assigned to this user's ID in migration 000028.
--
-- If user_config is empty (dev/test environment), still create the user
-- so that migration 000028 has a user_id to backfill with.
INSERT INTO users (email, created_at)
SELECT 'a.shahwan42@gmail.com', COALESCE(
    (SELECT created_at FROM user_config LIMIT 1),
    NOW()
);
