-- =============================================================================
-- Migration 000008: Create User Config Table
-- =============================================================================
--
-- SINGLE-ROW CONFIG TABLE PATTERN
-- ---------------------------------
-- This table is designed to hold exactly ONE row — the configuration for the
-- single user of this personal finance app.
--
-- Why a table instead of a config file or environment variables?
--   - The PIN hash and session key must persist across server restarts.
--   - They're secrets that should be in the database, not in source code.
--   - A single-row table is queryable and transactional (ACID-safe).
--
-- How "single row" is enforced:
--   There's no explicit constraint here (like CHECK or trigger), but the
--   application layer ensures only one row exists. The first-use setup flow
--   creates the row, and subsequent requests just UPDATE it.
--
--   Alternative approaches to enforce single-row:
--   1. Add a column: singleton BOOLEAN DEFAULT true UNIQUE CHECK (singleton = true)
--   2. Use a CHECK constraint on a fixed ID value
--   3. Application-level enforcement (what we do here — simpler)
--
-- Laravel equivalent:
--   // You might use a Settings model with a singleton pattern:
--   Settings::firstOrCreate([], ['pin_hash' => ..., 'session_key' => ...]);
--
-- Django equivalent:
--   // django-solo package provides a SingletonModel base class:
--   class UserConfig(SingletonModel):
--       pin_hash = models.CharField(max_length=255)
--       session_key = models.CharField(max_length=255)
--
-- AUTHENTICATION FIELDS
-- ----------------------
-- pin_hash:    bcrypt hash of the user's 4-6 digit PIN. Never store PINs in plaintext.
--              Generated with bcrypt.GenerateFromPassword() in Go.
--              Laravel: Hash::make($pin)  |  Django: make_password(pin)
--
-- session_key: a random secret used to sign HMAC session tokens (cookies).
--              When the server restarts, existing sessions remain valid because
--              the key is persisted in the DB (not generated at startup).
--
-- CREATE TABLE IF NOT EXISTS
-- ----------------------------
-- IF NOT EXISTS prevents an error if the table already exists.
-- Useful for idempotent migrations, though golang-migrate tracks which
-- migrations have run, so this is mostly a safety net.
--
-- Laravel: Schema::create() already checks existence internally.
-- Django:  migrations framework tracks state — no need for IF NOT EXISTS.
-- =============================================================================

-- Single-user configuration table.
-- Stores the PIN hash and session secret for authentication.
-- Only one row should ever exist (single-user app).
CREATE TABLE IF NOT EXISTS user_config (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    pin_hash    TEXT NOT NULL,           -- bcrypt hash of the user's 4-6 digit PIN
    session_key TEXT NOT NULL,           -- random secret for signing session cookies
    created_at  TIMESTAMPTZ DEFAULT now(),
    updated_at  TIMESTAMPTZ DEFAULT now()
);
