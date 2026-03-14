-- =============================================================================
-- Migration 000021 DOWN: Remove Cash Account Type and Wallet Institution Type
-- =============================================================================
--
-- WARNING: This will CASCADE-delete any cash accounts and their transactions,
-- plus any wallet-type institutions.
--
-- PostgreSQL doesn't support ALTER TYPE ... REMOVE VALUE, so we use the
-- create-new-type / cast / drop / rename pattern (same as migration 000018).
-- =============================================================================

-- Step 1: Delete cash accounts (CASCADE deletes their transactions)
DELETE FROM accounts WHERE type = 'cash';

-- Step 2: Delete wallet institutions
DELETE FROM institutions WHERE type = 'wallet';

-- Step 3: Replace account_type enum without 'cash'
CREATE TYPE account_type_new AS ENUM ('savings', 'current', 'prepaid', 'credit_card', 'credit_limit');
ALTER TABLE accounts
    ALTER COLUMN type TYPE account_type_new USING type::text::account_type_new;
DROP TYPE account_type;
ALTER TYPE account_type_new RENAME TO account_type;

-- Step 4: Replace institution_type enum without 'wallet'
CREATE TYPE institution_type_new AS ENUM ('bank', 'fintech');
ALTER TABLE institutions
    ALTER COLUMN type TYPE institution_type_new USING type::text::institution_type_new;
DROP TYPE institution_type;
ALTER TYPE institution_type_new RENAME TO institution_type;
