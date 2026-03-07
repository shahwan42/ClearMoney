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
