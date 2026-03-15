-- Add brute-force login prevention columns to user_config.
-- failed_attempts tracks consecutive wrong PIN entries.
-- locked_until stores when the lockout expires (NULL = not locked).
ALTER TABLE user_config ADD COLUMN IF NOT EXISTS failed_attempts INTEGER NOT NULL DEFAULT 0;
ALTER TABLE user_config ADD COLUMN IF NOT EXISTS locked_until TIMESTAMPTZ;
