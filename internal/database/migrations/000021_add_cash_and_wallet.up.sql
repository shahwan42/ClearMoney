-- =============================================================================
-- Migration 000021: Add Cash Account Type and Wallet Institution Type
-- =============================================================================
--
-- Adds support for tracking physical cash (wallet money) alongside bank accounts.
--
-- This migration is FULLY ADDITIVE — no existing data or schema is modified.
-- It adds two new enum values and nothing else.
--
-- ALTER TYPE ... ADD VALUE is safe in PostgreSQL 12+ (can run in transactions).
-- The IF NOT EXISTS clause makes this idempotent.
-- =============================================================================

-- Add 'cash' to account types (for physical cash / wallet accounts)
ALTER TYPE account_type ADD VALUE IF NOT EXISTS 'cash';

-- Add 'wallet' to institution types (virtual institution to group cash accounts)
ALTER TYPE institution_type ADD VALUE IF NOT EXISTS 'wallet';
