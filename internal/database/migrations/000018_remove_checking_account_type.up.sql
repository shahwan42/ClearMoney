-- =============================================================================
-- Migration 000018: Remove 'checking' Account Type
-- =============================================================================
--
-- 'checking' and 'current' are the same thing. We keep 'current' and remove
-- 'checking'. Any existing accounts with type 'checking' are converted to 'current'.
--
-- PostgreSQL doesn't support ALTER TYPE ... REMOVE VALUE, so we:
--   1. Convert all 'checking' accounts to 'current'
--   2. Replace the enum type with a new one that excludes 'checking'
--   3. Update the column to use the new enum
-- =============================================================================

-- Step 1: Convert existing 'checking' accounts to 'current'
UPDATE accounts SET type = 'current' WHERE type = 'checking';

-- Step 2: Create the new enum without 'checking'
CREATE TYPE account_type_new AS ENUM ('savings', 'current', 'prepaid', 'credit_card', 'credit_limit');

-- Step 3: Swap the column to use the new enum
ALTER TABLE accounts
    ALTER COLUMN type TYPE account_type_new USING type::text::account_type_new;

-- Step 4: Drop old enum and rename new one
DROP TYPE account_type;
ALTER TYPE account_type_new RENAME TO account_type;
